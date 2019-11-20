import os
import re
import sys
import time
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import List, Optional, Set

from . import __version__
from .io.config import (
    DEFAULT_JPP_HOME,
    JPP_HOME_ENV,
    app_config,
    env_locale,
    get_config_path,
)
from .io.journal import Journal, delete, edit, list_journals, read
from .parsing import convert_to_dateparser_locale, parse_entry
from .utils import ask, open_editor, print_err, yes_no


_install_min_entry_length = 1
_install_msg_delay = (
    0.3  # a bit of delay makes the walls of text a bit easier to follow
)
_default_command = "compose"

_welcome_message = """\
********** Welcome to jpp! **********
It looks like you haven't used jpp before (at least on this machine). Before you
start jotting down your thoughts, please allow me to ask a few questions on how
to set up jpp.
"""

_returning_prompt = """\
Have you used jpp before and want to sync your existing journals to this machine
or are you a new jpp user?
"""

_sync_message = """\
There's two ways you can backup and sync jpp journals and settings
across your devices: either put the journals in a directory synced by your
preferred cloud storage (Dropbox, Google Cloud...) or by activating git sync.
The latter keeps a full history of all your changes, which might come in handy.
"""

_sync_prompt = """\
Do you want to activate git sync? Git sync will automatically commit changes to
your journals. This can be used only locally, or you can add a remote repository
(for example on GitHub) to let jpp automatically sync from there.
"""

_jpp_dir_prompt = """\
In what directory do you want to store your journals? Note that this directory
can be shared across devices, for example by syncing it using Dropbox. If you've
used jpp before and synced your journals to this machine already, enter the path
to where you put them.
"""

_jpp_dir_returning_prompt = """\
Enter the path to where you put your journals (e.g. your Dropbox directory) so
that jpp can find them again.
"""

_locale_message = """\
jpp is using the system locale settings ({}) for date parsing and formatting.
You can still change your preferred date format later by either changing the
'LC_TIME' environment variable or setting one of the date settings in the jpp
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


def compose(journal_name: Optional[str]) -> None:
    journal = Journal.from_name(journal_name)

    entry_string = open_editor()

    print_err()

    if len(entry_string) < _install_min_entry_length:
        print_err("Entry not saved. Did you type something?")
        sys.exit(1)

    entry = parse_entry(entry_string)
    journal.add(entry)

    print_err("Entry saved")


def setup_sync() -> bool:
    git_sync = yes_no("Use git sync")
    print_err(_divider)

    if git_sync:
        pass  # todo ask for url and pull repo

    return git_sync


def install() -> None:
    time_locale = ""
    date_order = ""
    time_first = None
    journal_dir = os.getenv(JPP_HOME_ENV)

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
        print_err(_jpp_dir_returning_prompt if returning else _jpp_dir_prompt)
        time.sleep(_install_msg_delay)

        journal_dir = ask(
            "Where should we put your journals", default=str(DEFAULT_JPP_HOME)
        )
        journal_dir = str(Path(journal_dir).expanduser().absolute())
        print_err(_divider)
        time.sleep(_install_msg_delay)

        # todo check if journals already exist in journal_directory

    locale_from_env = env_locale()
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
    time.sleep(_install_msg_delay)

    app_config.set("default_journal", default_journal)
    app_config.set("journal_directory", journal_dir)
    app_config.set("git_sync", git_sync)
    if date_order:
        app_config.set("date_order", date_order)

    if time_first:
        app_config.set("time_before_date", time_first)

    if time_locale:
        app_config.set("locale", time_locale)

    print_err("All done! You can now start using jpp!")
    print_err("Hit enter to start writing your first entry...")
    print_err()
    input()


def compose_command(args: Namespace) -> None:
    compose(args.journal)


def edit_command(args: Namespace) -> None:
    edit(args.journal, args.last_n)


def read_command(args: Namespace) -> None:
    read(args.journal, args.last_n)


def list_command(_: Namespace) -> None:
    list_journals()


def delete_command(args: Namespace) -> None:
    delete(args.journal, args.last_n)


def _is_installed() -> bool:
    return get_config_path().exists()


def _prepare_args(argv: List[str], commands: Set[str]) -> List[str]:
    for i, arg in enumerate(argv):
        match = re.fullmatch(r"-(\d+)", arg)
        if match:
            argv[i : i + 1] = ["-n", match[1]]

    # if user not asking for help or typing a specific command, add default command
    if not ({"-h", "--help"}.intersection(argv) or commands.intersection(argv[0:1])):
        argv = [_default_command] + argv

    return argv


def main(argv: Optional[List[str]] = None) -> None:
    argv = argv or sys.argv[1:]
    parser = ArgumentParser(prog="jpp", formatter_class=RawTextHelpFormatter)

    parser.add_argument(
        "-V",
        "--version",
        dest="version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Prints version information and exits",
    )

    journal_parser = ArgumentParser(add_help=False)
    journal_parser.add_argument(
        "journal",
        default=None,
        type=str,
        nargs="?",
        help="Journal you want to use (default can be set in your jpp config)",
    )

    filter_parser = ArgumentParser(add_help=False)  # used as parent parser
    filter_parser.add_argument(
        "-n",
        dest="last_n",
        default=None,
        metavar="N",
        type=int,
        help="Only use the <n> most recent entries. You can also use '-<num>'"
        " instead of '-n <num>', for example '-6' is equivalent to '-n 6'.",
    )

    _commands_description = """
compose:   Create a new journal entry (default command)
read:      Read from your journals
edit:      Edit old entries
delete:    Delete old entries (can't be undone!)
list:      List journals you have created and their paths

See 'jpp <command> --help' to read more about a specific command.
"""

    subparsers = parser.add_subparsers(
        title="These are all the jpp commands available",
        metavar="",
        description=_commands_description,
    )

    compose_parser = subparsers.add_parser("compose", parents=[journal_parser])
    compose_parser.set_defaults(func=compose_command)

    edit_parser = subparsers.add_parser("edit", parents=[journal_parser, filter_parser])
    edit_parser.set_defaults(func=edit_command)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=list_command)

    delete_parser = subparsers.add_parser(
        "delete", parents=[journal_parser, filter_parser]
    )
    delete_parser.set_defaults(func=delete_command)

    read_parser = subparsers.add_parser("read", parents=[journal_parser, filter_parser])
    read_parser.set_defaults(func=read_command)

    commands = set(subparsers.choices.keys())
    argv = _prepare_args(argv, commands)

    parsed_args = parser.parse_args(argv)

    if not _is_installed():
        install()

    if "func" in parsed_args:
        parsed_args.func(parsed_args)
