import itertools
import locale
import os
import shlex
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pluggy
import tomlkit
from pluggy import PluginManager
from tomlkit.toml_document import TOMLDocument

import pen
from pen.exceptions import UsageError

from . import commands
from .commands import DEFAULT_CONFIG_PATH, DEFAULT_PEN_HOME, PEN_HOME_ENV
from .hookspec import hookimpl
from .journal import MarkdownPrinter
from .serializing import JrnlImporter, MarkdownSerializer
from .utils import merge_dicts, print_err


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

    def add_subparsers(self, config: "AppConfig", hook: Any) -> None:
        hook.add_subparser(early_config=config, subparsers=self._subparsers)

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
        self.path = path

    def read(self) -> TOMLDocument:
        with self.path.open() as f:
            return tomlkit.loads(f.read())

    def write(self, data: TOMLDocument) -> None:
        with self.path.open("w") as f:
            f.write(data.as_string())

    def exists(self) -> bool:
        return self.path.exists()

    def create(self) -> None:
        if not self.path.exists():
            try:
                mode = 0o700  # only current user can modify file
                self.path.parent.mkdir(mode, parents=True, exist_ok=True)
                self.path.touch(mode)
                cfg = TOMLDocument()
                cfg["pen"] = {}
                self.write(cfg)
            except Exception as err:
                try:
                    # clean up if it was created already
                    self.path.unlink()
                except FileNotFoundError:
                    pass

                raise RuntimeError(
                    f"Could not create config file at {self.path}"
                ) from err


class AppConfig:
    """
    Reads and provides configuration from args, environment variables and config files.
    """

    def __init__(self, args: List[str], pluginmanager: PluginManager) -> None:
        self.pluginmanager = pluginmanager
        self.pluginmanager.register(self)

        self._config: Dict[str, Any] = {"pen": {}}
        self._config_file = ConfigFile(_config_path())
        if self._config_file.exists():
            content = self.load()
            _verify_journal_paths(content)
            self.save(content)
            merge_dicts(self._config, content)

        env_options = self.pluginmanager.hook.get_env_options()
        for option, value in itertools.chain(*env_options):
            if not self.get(option):
                self.set(option, value)

        self.parser = ArgParser()
        self.parser.add_subparsers(self, self.pluginmanager.hook)
        self.pluginmanager.hook.add_global_options(parser=self.parser)
        self.pluginmanager.hook.prepare_args(args=args, parser=self.parser)
        parsed_args = self.parser.parse(args)
        self.cli_args = parsed_args

    def config_file_exists(self) -> bool:
        return self._config_file.exists()

    def home_directory_exists(self) -> bool:
        return Path(self.get("journal_directory")).exists()

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        keys = key.split(".")
        config = self._config["pen"]

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}

            config = config[key]

        return config.get(keys[-1], default)

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

    def load(self) -> TOMLDocument:
        content = self._config_file.read()
        if "pen" not in content:
            raise UsageError(
                f"Config file at {self._config_file.path} is invalid,"
                " no top level 'pen' table found. Please fix or remove"
                " the file and try again."
            )

        return content

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


def _verify_journal_paths(config: TOMLDocument) -> None:
    missing = []

    for journal_name, journal_config in config["pen"].get("journals", {}).items():
        if "path" in journal_config:
            path = Path(journal_config["path"])
            if not path.exists():
                print_err(
                    f"Journal at {path} does not seem to exist anymore. If you"
                    f" moved it, use 'pen import <path>' so that Pen can find it"
                    f" again."
                )
                missing.append(journal_name)

    for journal in missing:
        del config.get("journals")[journal]


def get_config(args: List[str], plugins: List[Tuple[Any, str]]) -> AppConfig:
    pm = _get_plugin_manager(plugins)
    config = AppConfig(args, pm)
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


def _get_plugin_manager(plugins: Iterable[Tuple[Any, str]]) -> pluggy.PluginManager:
    from .serializing import SERIALIZER_PREFIX, IMPORTER_PREFIX

    pm = pluggy.PluginManager("pen")
    pm.add_hookspecs(pen.hookspec)
    pm.add_hookspecs(pen.hookspec.EntrySerializer)
    pm.add_hookspecs(pen.hookspec.JournalFormatter)
    pm.load_setuptools_entrypoints("pen")

    # hooks implemented in this file (yes it's ugly) todo change this
    pm.register(__import__(__package__).config)  # type: ignore
    pm.register(pen)  # version option
    pm.register(commands)  # subcommands
    pm.register(MarkdownPrinter(), f"printer-{MarkdownSerializer.file_type}")
    pm.register(
        MarkdownSerializer(), f"{SERIALIZER_PREFIX}{MarkdownSerializer.file_type}"
    )
    pm.register(JrnlImporter(), f"{IMPORTER_PREFIX}{JrnlImporter.file_type}")

    for plugin, name in plugins:
        pm.register(plugin, name)

    return pm
