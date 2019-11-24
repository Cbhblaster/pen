import itertools
import locale
import os
import re
import shlex
import sys
from argparse import (
    ArgumentParser,
    Namespace,
    RawDescriptionHelpFormatter,
    _SubParsersAction,
)
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pluggy
import tomlkit
from pluggy import PluginManager
from tomlkit.toml_document import TOMLDocument

import pen

from ._version import __version__
from .commands import (
    compose_command,
    delete_command,
    edit_command,
    list_command,
    read_command,
)
from .hookspec import hookimpl
from .journal import MarkdownPrinter
from .serializing import MarkdownSerializer
from .utils import merge_dicts


HOME = Path().home()
PEN_HOME_ENV = "PEN_HOME"
DEFAULT_CONFIG_PATH = HOME / ".config" / "pen" / "pen.toml"
DEFAULT_PEN_HOME = HOME / ".local" / "pen"


_commands_description = """
compose:   Create a new journal entry (default command)
read:      Read from your journals
edit:      Edit old entries
delete:    Delete old entries
list:      List journals you have created and their paths

See 'pen <command> --help' to read more about a specific command.
"""


class ArgParser:
    def __init__(self) -> None:
        self._parser = ArgumentParser(
            prog="pen", formatter_class=RawDescriptionHelpFormatter
        )

        self._subparsers = self._parser.add_subparsers(
            title="These are all the Pen commands available",
            metavar="",
            description=_commands_description,
        )

    def parse(self, args: List[str]) -> Namespace:
        return self._parser.parse_args(args)

    def add_subparsers(self, hook: Any) -> None:
        hook.add_subparser(subparsers=self._subparsers)

    def add_argument(self, *args: Any, **kwargs: Any) -> None:
        """ Adds an argument to the command line parser. This takes the
            same arguments as argparse.ArgumentParser.add_argument.
        """
        self._parser.add_argument(*args, **kwargs)

    @property
    def commands(self) -> Set[str]:
        return set(self._subparsers.choices.keys())


class ConfigFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> TOMLDocument:
        with self._path.open() as f:
            return tomlkit.loads(f.read())

    def write(self, data: TOMLDocument) -> None:
        with self._path.open("w") as f:
            f.write(data.as_string())

    def exists(self) -> bool:
        return self._path.exists()

    def create(self) -> None:
        if not self._path.exists():
            try:
                mode = 0o700  # only current user can modify file
                self._path.parent.mkdir(mode, parents=True, exist_ok=True)
                self._path.touch(mode)
                cfg = TOMLDocument()
                cfg["pen"] = {}
                self.write(cfg)
            except Exception as err:
                try:
                    # clean up if it was created already
                    self._path.unlink()
                except FileNotFoundError:
                    pass

                raise RuntimeError(
                    f"Could not create config file at {self._path}"
                ) from err


class AppConfig:
    """
    Reads and provides configuration from args, environment variables and config files.
    Does not allow saving new configuration to file currently.
    """

    def __init__(self, argv: Namespace, pluginmanager: PluginManager) -> None:
        self.cli_args = argv
        self.pluginmanager = pluginmanager
        self.pluginmanager.register(self)
        self.parser = ArgParser()
        self._config: Dict[str, Any] = {"pen": {}}
        self._config_file = ConfigFile(_config_path())
        if self._config_file.exists():
            content = self._config_file.read()
            if "pen" not in content:
                raise RuntimeError(
                    "Config file invalid, no top level 'pen' table found"
                )

            merge_dicts(self._config, content)

        env_options = self.pluginmanager.hook.get_env_options()
        for option, value in itertools.chain(*env_options):
            if not self.get(option):
                self.set(option, value)

    def config_file_exists(self) -> bool:
        return self._config_file.exists()

    def home_directory_exists(self) -> bool:
        return Path(self.get("journal_directory")).exists()

    def get(self, key: str, default: Optional[str] = None) -> Any:
        keys = key.split(".")
        config = self._config["pen"]

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}

            config = config[key]

        return config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Adds setting to config, does *not* write it to pen.toml file as this
        config also contains configuration from sys.args and environment variables.
        """
        keys = key.split(".")
        config = self._config["pen"]

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}

            config = config[key]

        config[key] = value

    def save(self, config: TOMLDocument) -> None:
        self._config_file.write(config)

    def _create_file(self) -> None:
        self._config_file.create()


@hookimpl
def get_env_options() -> List[Tuple[str, Any]]:
    env_vars = [
        ("journal_directory", _env_pen_home()),
        ("locale", _env_locale()),
        ("editor", _env_editor()),
    ]

    return env_vars


@hookimpl
def prepare_args(args: List[str], parser: ArgParser) -> None:
    for i, arg in enumerate(args):
        match = re.fullmatch(r"-(\d+)", arg)
        if match:
            args[i : i + 1] = ["-n", match[1]]

    # if no command given and no help sought, infer command from the other args
    if not (
        {"-h", "--help"}.intersection(args) or parser.commands.intersection(args[0:1])
    ):
        # good enough solution for now. Will not work if 'compose' ever gets options
        if any(arg.startswith("-") for arg in args):
            args.insert(0, "read")
        else:
            args.insert(0, "compose")


@hookimpl
def add_global_options(parser: ArgParser) -> None:
    parser.add_argument(
        "-V",
        "--version",
        dest="version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Prints version information and exits",
    )


@hookimpl
def add_subparser(subparsers: _SubParsersAction) -> None:
    journal_parser = ArgumentParser(add_help=False)
    journal_parser.add_argument(
        "journal",
        default=None,
        type=str,
        nargs="?",
        help="Journal you want to use (default can be set in your pen config)",
    )

    filter_parser = ArgumentParser(add_help=False)  # used as parent parser
    filter_parser.add_argument(
        "-n",
        dest="last_n",
        default=None,
        metavar="N",
        type=int,
        help="Only use the <n> most recent entries. You can also use '-N'"
        " instead of '-n N', for example '-6' is equivalent to '-n "
        "6'.",
    )

    compose_parser = subparsers.add_parser("compose", parents=[journal_parser])
    compose_parser.set_defaults(func=compose_command)

    edit_parser = subparsers.add_parser("edit", parents=[journal_parser, filter_parser])
    edit_parser.set_defaults(func=edit_command)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=list_command)

    delete_parser = subparsers.add_parser(
        "delete", parents=[journal_parser, filter_parser]
    )  # todo --force
    delete_parser.set_defaults(func=delete_command)

    read_parser = subparsers.add_parser("read", parents=[journal_parser, filter_parser])
    read_parser.set_defaults(func=read_command)  # todo --title/--short/--oneline


def get_config(args: List[str], plugins: List[Tuple[Any, str]]) -> AppConfig:
    parser = ArgParser()
    pm = _get_plugin_manager(plugins)
    pm.hook.add_global_options(parser=parser)
    parser.add_subparsers(pm.hook)

    prepare_args(args, parser)
    parsed_args = parser.parse(args)

    config = AppConfig(parsed_args, pm)
    return config


def _config_path() -> Path:
    return DEFAULT_CONFIG_PATH


def _env_pen_home() -> Path:
    pen_home_env = os.getenv(PEN_HOME_ENV)
    pen_home = Path(pen_home_env) if pen_home_env else DEFAULT_PEN_HOME
    pen_home.mkdir(parents=True, exist_ok=True)  # ensure exists
    return pen_home


def _env_locale() -> Optional[str]:
    _ = locale.setlocale(locale.LC_ALL, "")  # needed to initialize locales
    lc_time_tuple = locale.getlocale(locale.LC_TIME)  # = (locale, encoding)

    if not lc_time_tuple:
        return None

    # discard the encoding
    lc_time = lc_time_tuple[0]
    return lc_time


def _env_editor() -> Optional[List[str]]:
    editor = os.getenv("VISUAL") or os.getenv("EDITOR")
    return shlex.split(editor, posix="win" not in sys.platform) if editor else None


def _get_plugin_manager(plugins: List[Tuple[Any, str]]) -> pluggy.PluginManager:
    pm = pluggy.PluginManager("pen")
    pm.add_hookspecs(pen.hookspec)
    pm.add_hookspecs(pen.hookspec.EntrySerializer)
    pm.add_hookspecs(pen.hookspec.JournalFormatter)
    pm.load_setuptools_entrypoints("pen")

    # hooks implemented in this file (yes it's ugly) todo change this
    pm.register(__import__(__name__).config)  # type: ignore
    pm.register(MarkdownPrinter(), f"printer-{MarkdownSerializer.file_type}")
    pm.register(MarkdownSerializer(), f"serializer-{MarkdownSerializer.file_type}")

    for plugin, name in plugins:
        pm.register(plugin, name)

    return pm
