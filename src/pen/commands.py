import itertools
import os
import re
import shutil
import sys
import time
from argparse import ArgumentParser, Namespace, _SubParsersAction
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Optional, Set

from tomlkit.toml_document import TOMLDocument

from pen.exceptions import UsageError
from pen.serializing import (
    MarkdownSerializer,
    available_importers,
    available_serializers,
)

from .hookspec import hookimpl
from .journal import Journal, file_type_from_marker
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
    journals = _iter_journals(config)

    for journal_path in journals:
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


def setup_sync() -> bool:
    git_sync = yes_no("Use git sync")
    print_err(_divider)

    if git_sync:
        pass  # todo ask for url and pull repo

    return git_sync


def import_journals_command(config: "AppConfig", _: Namespace) -> None:
    journal_paths: List[str] = config.cli_args.path
    to_file_type: Optional[str] = config.cli_args.to_file_type

    for path in journal_paths:
        import_journal(config, Path(path), to_file_type)


def import_journal(
    config: "AppConfig", old_path: Path, new_file_type: Optional[str]
) -> None:
    serializer_options = available_serializers(config.pluginmanager)
    importer_options = available_importers(config.pluginmanager)
    all_import_options = serializer_options.union(importer_options)

    if old_path.stem in [path.stem for path in _iter_journals(config)]:
        raise UsageError(  # todo allow transforming types with same name
            f"Journal {old_path.stem} exists already in Pen. Rename "
            f"the journal you want to import or remove the other one."
        )

    if new_file_type and new_file_type not in serializer_options:
        raise UsageError(
            f"File type {new_file_type} is currently not supported for"
            f" storing journals"
        )

    old_file_type = None
    try:
        old_file_type = file_type_from_marker(old_path)
        contains_file_marker = True
    except UsageError:
        # file type not in journal
        contains_file_marker = False

    old_file_type = old_file_type or _try_all_importers(
        old_path, config, all_import_options
    )
    if not old_file_type:
        # still nothing? We have to ask the user
        print_err(_file_type_not_found_prompt.format(old_path))
        old_file_type = ask(
            "Which type (leave blank to skip)", all_import_options, default=""
        )
        print_err()
        time.sleep(_install_msg_delay)

        if not old_file_type:
            print_err(f"No file type specified, skipping {old_path}")
            return

    if not new_file_type and old_file_type not in serializer_options:
        print_err(_only_import_msg)
        time.sleep(_install_msg_delay)
        if len(serializer_options) > 1:
            new_file_type = ask(
                "Which file type do you want to use for Pen",
                options=serializer_options,
                default=MarkdownSerializer.file_type,
            )
        else:
            new_file_type = serializer_options.pop()
            print_err(f"Using '{new_file_type}' for now. You can change this later.")
        print_err()
        time.sleep(_install_msg_delay)
    elif not new_file_type:
        new_file_type = old_file_type

    if new_file_type not in all_import_options:
        raise UsageError(_file_type_not_supported_msg.format(new_file_type))

    # make sure we can read it
    try:
        entries = Journal(old_path, config, old_file_type).read(last_n=1)
        if not entries:
            raise SerializationError()
    except SerializationError:
        invalid_msg = (
            "The journal type specified in the file is wrong."
            if contains_file_marker
            else f"Are you sure you specified the correct file type?"
        )
        print_err(f"Reading journal at {old_path} failed.", invalid_msg, "Skipping.")
        time.sleep(_install_msg_delay)
        return

    # check if user wants to move journal or not
    if old_path == Path(config.get("journal_directory")):
        move = False  # journal already in journal_directory
    elif not config.cli_args.move and not config.cli_args.keep:
        print_err(
            f"We can move the journal to your normal journal directory for you"
            f" now or keep it where it is and add its location to the config."
        )
        time.sleep(_install_msg_delay)
        move = yes_no("Do you want to move it")
        print_err()
        time.sleep(_install_msg_delay)
    else:
        move = bool(config.cli_args.move)

    new_path = (
        Path(config.get("journal_directory")) / old_path.name if move else old_path
    )

    if not move and old_file_type != new_file_type:
        _make_backup(old_path)  # only create a backup if we overwrite the old one

    if old_file_type != new_file_type:
        # need to read and parse all entries and then write them back with new format
        entries = Journal(old_path, config, old_file_type).read()
        Journal(new_path, config, new_file_type).write(entries)
    elif move:
        import shutil

        # type in file already, just need to move it over
        shutil.move(str(old_path), str(new_path))

    elif not contains_file_marker:
        # type not in file yet, need to add file_type marker
        with old_path.open("r") as fp:  # just read without parsing entries
            journal_text = fp.read()

        with new_path.open("w") as fp:
            fp.write(f"file_type: {new_file_type}\n")  # prepend type marker
            fp.write(journal_text)

    if not move:
        # put non-default location of journal into config so we can find it later
        toml_config = config.load()
        # todo hook based name from path?
        if "journals" not in toml_config["pen"]:
            toml_config["pen"]["journals"] = {}
        toml_config["pen"]["journals"][old_path.stem] = {"path": str(new_path)}
        config.save(toml_config)

    print_err(f"Successfully imported {old_path}")


def _try_all_importers(
    path: Path, config: "AppConfig", options: Set[str]
) -> Optional[str]:
    # try to read at least 3 entries to make sure we have the right importer
    # note that the journal might have less than 3 entries, but we want to make
    # sure here we don't just read one or two random garbled entries by accident.
    for option in options:
        try:
            entries = Journal(path, config, option).read(last_n=3)
            if (
                not entries
                or len(entries) < 3
                or any(not entry.title or not entry.date for entry in entries)
            ):
                continue
            return option
        except Exception:
            pass
    return None


def _make_backup(old_path: Path) -> None:
    backup_path = old_path.with_suffix(old_path.suffix + ".bak")
    print_err(
        f"The import will overwrite your old journal. To avoid any accidental"
        f" data loss, we will backup your journal to {backup_path} now."
    )
    shutil.copy2(str(old_path), str(backup_path))


def _iter_journals(config: "AppConfig") -> Iterable[Path]:
    home_journals = Path(config.get("journal_directory")).iterdir()
    config_journals = (
        Path(journal_config["path"])
        for journal_config in config.get("journals", {}).values()
    )

    return itertools.chain(home_journals, config_journals)


@hookimpl
def add_subparser(early_config: "AppConfig", subparsers: _SubParsersAction) -> None:
    journal_parser = ArgumentParser(add_help=False)  # used as parent parser
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
    compose_parser.set_defaults(func=compose_command)  # todo description

    edit_parser = subparsers.add_parser("edit", parents=[journal_parser, filter_parser])
    edit_parser.set_defaults(func=edit_command)  # todo description

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=list_command)  # todo description

    delete_parser = subparsers.add_parser(
        "delete", parents=[journal_parser, filter_parser]
    )  # todo --force
    delete_parser.set_defaults(func=delete_command)  # todo description

    read_parser = subparsers.add_parser("read", parents=[journal_parser, filter_parser])
    read_parser.set_defaults(func=read_command)  # todo --title/--short/--oneline

    supported_file_types = available_serializers(early_config.pluginmanager)
    import_parser = subparsers.add_parser("import")  # todo description
    # todo --merge into an existing journal
    import_parser.set_defaults(func=import_journals_command)
    import_parser.add_argument(
        "path",
        metavar="Path",
        type=str,
        nargs="+",
        help="Path(s) to journals you want import",
    )
    import_parser.add_argument(
        "--to-file-type",
        "-t",
        default=None,
        type=str,
        required=False,
        help=file_type_help.format(", ".join([f"'{t}'" for t in supported_file_types])),
    )
    group = import_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--move",
        "-m",
        default=False,
        action="store_true",
        required=False,
        help="If set, Pen will move the journals to the journal directory as defined in"
        " the config",
    )
    group.add_argument(
        "--keep",
        "-k",
        default=False,
        action="store_true",
        required=False,
        help="If set, Pen will not move the journals to the journal directory and"
        " and will instead leave them where they are now",
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
What file type you want to store the journals in after importing. Currently
supported file types: {}"""

_file_type_warning = """\
The journal at {} seems to be written in a format that is different
to the new file type you supplied. We will transform your journal into the new
format '{}' now."""

_file_type_not_found_prompt = """\
Type of journal at {} could not be determined automatically. Please specify the
file type of this journal.
"""

_only_import_msg = """\
Pen is able to import your journal, however we do not support this format actively.
Therefore, we need to transform your journal into a type that Pen understands.
"""

_file_type_not_supported_msg = """\
File type '{}' not supported. Please install a plugin that supports this format.
"""

_welcome_message = """\
PLEASE NOTE: THIS IS AN ALPHA RELEASE - this means important features are missing,
bugs may occur and upgrading might break Pen. You have been warned.

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
