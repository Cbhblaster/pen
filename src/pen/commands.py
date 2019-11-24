import itertools
import os
import re
import sys
import time
from argparse import ArgumentParser, Namespace, _SubParsersAction
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from tomlkit.toml_document import TOMLDocument

from pen.exceptions import UsageError
from pen.serializing import available_serializers

from .hookspec import hookimpl
from .journal import Journal, file_type_from_path
from .parsing import convert_to_dateparser_locale, parse_entry
from .serializing import SerializationError
from .utils import ask, open_editor, print_err, yes_no


if TYPE_CHECKING:
    from .config import AppConfig, ArgParser, PEN_HOME_ENV, DEFAULT_PEN_HOME


def compose_command(config: "AppConfig", args: Namespace) -> None:
    min_entry_length = 1
    journal = Journal.from_name(args.journal, config)

    entry_string = open_editor(config)

    print_err()

    if len(entry_string) < min_entry_length:
        print_err("Entry not saved. Did you type something?")
        sys.exit(1)

    entry = parse_entry(config, entry_string)
    journal.add(entry)

    print_err("Entry saved")


def edit_command(config: "AppConfig", args: Namespace) -> None:
    journal = Journal.from_name(args.journal, config)
    journal.edit(args.last_n)


def read_command(config: "AppConfig", args: Namespace) -> None:
    journal = Journal.from_name(args.journal, config)
    journal.pprint(args.last_n)  # paged output?


def list_command(config: "AppConfig", _: Namespace) -> None:
    home_journals = Path(config.get("journal_directory")).iterdir()
    config_journals = (
        Path(journal_config["path"])
        for journal_config in config.get("journals", {}).values()
    )

    for journal_path in itertools.chain(home_journals, config_journals):
        print(f"{journal_path.stem} ({journal_path})")


def delete_command(config: "AppConfig", args: Namespace) -> None:
    journal = Journal.from_name(args.journal, config)
    journal.delete(args.last_n)


def install_command(config: "AppConfig") -> None:
    time_locale = ""
    date_order = ""
    time_first = None
    journal_dir = os.getenv(PEN_HOME_ENV)

    print_err(_welcome_message)
    time.sleep(_install_msg_delay)

    print_err(_returning_prompt)
    time.sleep(_install_msg_delay)
    returning = yes_no("Sync existing journals", default=False)
    print_err(_divider)
    time.sleep(_install_msg_delay)

    if returning:
        git_sync = setup_sync()
    else:
        print_err(_sync_message)
        time.sleep(_install_msg_delay)

        print_err(_sync_prompt)
        time.sleep(_install_msg_delay)

        git_sync = yes_no("Activate git sync", default=True)
        print_err(_divider)
        time.sleep(_install_msg_delay)

        if git_sync:
            from .gitsync import init

            init()

    if not journal_dir:
        print_err(_pen_dir_returning_prompt if returning else _pen_dir_prompt)
        time.sleep(_install_msg_delay)

        journal_dir = ask(
            "Where should we put your journals", default=str(DEFAULT_PEN_HOME)
        )
        journal_dir = str(Path(journal_dir).expanduser().absolute())
        print_err(_divider)
        time.sleep(_install_msg_delay)

        # todo check if journals already exist in journal_directory and import

    locale_from_env = config.get("locale")
    if locale_from_env and convert_to_dateparser_locale(locale_from_env):
        time_locale = locale_from_env
        print_err(_locale_message.format(time_locale))
        print_err(_divider)
        time.sleep(_install_msg_delay)
    else:
        date_options = ["DMY", "MDY", "YMD"]
        date_order = ask(
            "What is your preferred date ordering (for Day, Month, Year)", date_options
        )
        time.sleep(_install_msg_delay)

        time_first_answer = ask(
            "Do you prefer to input the date or time first ('July 5th 9:30' or"
            " '9:30 July 5th')",
            ["date", "time"],
            default="date",
        )
        time_first = time_first_answer == "time"
        print_err(_divider)
        time.sleep(_install_msg_delay)

    print_err(_default_journal_message)
    time.sleep(_install_msg_delay)

    default_journal = ask(
        "How do you want to call your default journal",
        default="default",
        validator=lambda s: len(s) >= 1,
    )
    print_err(_divider)
    time.sleep(_install_msg_delay * 2)

    new_config = TOMLDocument()
    new_config["pen"] = {}

    new_config["pen"]["default_journal"] = default_journal
    new_config["pen"]["journal_directory"] = journal_dir
    new_config["pen"]["git_sync"] = git_sync
    if date_order:
        new_config["pen"]["date_order"] = date_order

    if time_first:
        new_config["pen"]["time_before_date"] = time_first

    if time_locale:
        new_config["pen"]["locale"] = time_locale

    config.save(new_config)

    print_err("All done! You can now start using pen!")
    print_err("Hit enter to start writing your first entry...")
    print_err()
    input()  # just so editor doesn't open immediately after last question


def import_journals_command(config: "AppConfig", _: Namespace) -> None:
    journal_paths: List[str] = config.cli_args.path
    file_type: Optional[str] = config.cli_args.file_type

    for path in journal_paths:
        import_journal(config, Path(path), file_type)


def import_journal(config: "AppConfig", path: Path, file_type: Optional[str]) -> None:
    type_from_path = None
    file_type_options = available_serializers(config.pluginmanager)
    try:
        type_from_path = file_type_from_path(path)
    except UsageError:
        if not file_type:  # type not in journal and not supplied by user
            print_err(_file_type_not_found_prompt.format(path))
            file_type = ask(
                "Which file type (leave blank to skip)", file_type_options, default=""
            )

            if not file_type:
                print_err(f"No file type specified, skipping {path}")
                return

    if file_type and type_from_path and type_from_path != file_type:
        print_err(_file_type_warning.format(path, type_from_path))
        print_err()

    move: bool = config.cli_args.move
    file_type = file_type if file_type else type_from_path

    if file_type not in file_type_options:
        raise UsageError(_file_type_not_supported_msg.format(file_type))

    # make sure we can read it
    try:
        entries = Journal(path, config, file_type).read(last_n=1)
        if not entries:
            raise SerializationError()
    except SerializationError:
        invalid_msg = (
            "The journal type specified in the file is wrong."
            if type_from_path
            else f"Are you sure you specified the correct file type?"
        )
        print_err(f"Reading journal at {path} failed, skipping.", invalid_msg)
        return

    new_path = Path(config.get("journal_directory")) if move else path

    if not type_from_path:
        # type not in file yet, need to add file_type marker
        with path.open("r") as fp:  # just read without parsing entries
            old_journal_text = fp.read()

        with new_path.open("w") as fp:
            fp.write(f"file_type: {file_type}\n")  # prepend type marker
            fp.write(old_journal_text)
    elif move:
        import shutil

        # type in file already, just need to move it over
        shutil.move(str(path), str(new_path))

    if not move:
        # put non-default location of journal into config so we can find it later
        toml_config = config.load()
        # todo hook based name from path?
        if "journals" not in toml_config["pen"]:
            toml_config["pen"]["journals"] = {}
        toml_config["pen"]["journals"][path.stem] = {"path": str(new_path)}
        config.save(toml_config)


def setup_sync() -> bool:
    git_sync = yes_no("Use git sync")
    print_err(_divider)

    if git_sync:
        pass  # todo ask for url and pull repo

    return git_sync


@hookimpl
def add_subparser(early_config: "AppConfig", subparsers: _SubParsersAction) -> None:
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

    supported_file_types = available_serializers(early_config.pluginmanager)
    import_parser = subparsers.add_parser("import")
    import_parser.set_defaults(func=import_journals_command)
    import_parser.add_argument(
        "path",
        metavar="Path",
        type=str,
        nargs="+",
        help="Path(s) to journals you want import",
    )
    import_parser.add_argument(
        "--file-type",
        "-t",
        default=None,
        type=str,
        required=False,
        help=file_type_help.format(", ".join([f"'{t}'" for t in supported_file_types])),
    )
    import_parser.add_argument(
        "--move",
        "-m",
        default=False,
        action="store_true",
        required=False,
        help="If set, Pen will move the journals to the journal directory as defined in"
        " the config, otherwise they will stay where they are",
    )


@hookimpl
def add_global_options(parser: "ArgParser") -> None:
    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="Print additional debug information",
    )


@hookimpl
def prepare_args(args: List[str], parser: "ArgParser") -> None:
    for i, arg in enumerate(args):
        match = re.fullmatch(r"-(\d+)", arg)
        if match:
            args[i : i + 1] = ["-n", match[1]]

    # if no command given and no help sought, infer command from the other args
    if not (
        {"-h", "--help"}.intersection(args) or parser.commands.intersection(args[0:2])
    ):
        # good enough solution for now. Will not work if 'compose' ever gets options
        if any(arg.startswith("-") for arg in args):
            args.insert(0, "read")
        else:
            args.insert(0, "compose")

    if "--debug" in args:
        # debug is a global option and needs to be at the front
        args.remove("--debug")
        args.insert(0, "--debug")


_install_msg_delay = 0.3
"""a bit of delay makes the walls of text a bit easier to follow"""

file_type_help = """\
File type of the journals you want to import. Can be omitted if the journals
were created by or imported into Pen before. Currently supported file types:
{}"""

_file_type_warning = """\
Warning: The journal at {} includes a file_type marker that is
different to the --file-type option you supplied. Using the one
from the journal instead ('{}')."""

_file_type_not_found_prompt = """\
Type of journal at {} could not be determined. Please specify the file type
of this journal.
"""

_file_type_not_supported_msg = """\
Error: File type '{}' not supported. Please install a plugin that supports this format.
"""

_welcome_message = """\
********** Welcome to pen! **********
It looks like you haven't used pen before (at least on this machine). Before you
start jotting down your thoughts, please allow me to ask a few questions on how
to set up pen.
"""

_returning_prompt = """\
Have you used pen before and want to sync your existing journals to this machine
or are you a new pen user?
"""

_sync_message = """\
There's two ways you can backup and sync pen journals and settings
across your devices: either put the journals in a directory synced by your
preferred cloud storage (Dropbox, Google Cloud...) or by activating git sync.
The latter keeps a full history of all your changes, which might come in handy.
"""

_sync_prompt = """\
Do you want to activate git sync? Git sync will automatically commit changes to
your journals. This can be used only locally, or you can add a remote repository
(for example on GitHub) to let pen automatically sync from there.
"""

_pen_dir_prompt = """\
In what directory do you want to store your journals? Note that this directory
can be shared across devices, for example by syncing it using Dropbox. If you've
used pen before and synced your journals to this machine already, enter the path
to where you put them.
"""

_pen_dir_returning_prompt = """\
Enter the path to where you put your journals (e.g. your Dropbox directory) so
that pen can find them again.
"""

_locale_message = """\
pen is using the system locale settings ({}) for date parsing and formatting.
You can still change your preferred date format later by either changing the
'LC_TIME' environment variable or setting one of the date settings in the pen
configuration.
"""

_default_journal_message = """\
Now it's time to create your first journal. This will be your default journal.
You can create additional journals later if you want. For now, I need a name
for your first one, though.
"""

_divider = """
--------------------------------------------------------------------------------
"""
