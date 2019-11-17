import argparse
import functools
import locale
import os
import shlex
import subprocess
import sys
import time

from datetime import datetime
from pathlib import Path
from tempfile import mkstemp
from typing import Callable, List, Optional

from dateparser import parse
from jpp.writing import dateparse_time_locale, parse_entry

from . import __version__
from .config import _DEFAULT_JPP_HOME, JPP_HOME_ENV, AppConfig, get_config_path


msg_delay = 0.3

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


def parse_datetime(dt_string: str, config: AppConfig) -> datetime:
    if config.get("date_format"):
        return parse(dt_string, date_formats=[config.get("date_format")])

    if config.get("locales"):
        return parse(dt_string, languages=[config.get("locales")])

    if config.get("date_order"):
        return parse(dt_string, settings={"DATE_ORDER": config.get("date_order")})

    return parse(dt_string)  # let dateparser guess the locale


def compose() -> None:
    editor = _user_editor()
    if editor:
        tmpfile_handle, tmpfile_path = mkstemp(suffix="jpp.txt", text=True)
        subprocess.call(editor + [tmpfile_path])
        os.close(tmpfile_handle)

        with open(tmpfile_path, "r") as fp:
            new_entry = fp.read()

        os.unlink(tmpfile_path)
    else:
        new_entry = sys.stdin.read()

    # handle empty entry
    print_err("You wrote:", parse_entry(new_entry))


def setup_sync() -> bool:
    git_sync = yes_no("Use git sync")
    print_err(_divider)

    if git_sync:
        pass  # ask for url and pull repo

    return git_sync


def install() -> None:
    time_locale = None
    date_order = None
    time_first = None
    journal_dir = os.getenv(JPP_HOME_ENV)

    print_err(_welcome_message)
    time.sleep(msg_delay)

    print_err(_returning_prompt)
    time.sleep(msg_delay)
    returning = yes_no("Sync existing journals", default=False)
    print_err(_divider)
    time.sleep(msg_delay)

    if returning:
        git_sync = setup_sync()
    else:
        print_err(_sync_message)
        time.sleep(msg_delay)

        print_err(_sync_prompt)
        time.sleep(msg_delay)

        git_sync = yes_no("Activate git sync", default=True)
        print_err(_divider)
        time.sleep(msg_delay)

        if git_sync != "n":
            from .gitsync import init

            init()

    if not journal_dir:
        print_err(_jpp_dir_returning_prompt if returning else _jpp_dir_prompt)
        time.sleep(msg_delay)

        journal_dir = ask(
            "Where should we put your journals", default=str(_DEFAULT_JPP_HOME)
        )
        journal_dir = str(Path(journal_dir).expanduser().absolute())
        print_err(_divider)
        time.sleep(msg_delay)

        # todo check if journals already exist in journal_directory

    if dateparse_time_locale():
        time_locale = locale.getlocale(locale.LC_TIME)[0]
        print_err(_locale_message.format(time_locale))
        print_err(_divider)
        time.sleep(msg_delay)
    else:
        date_options = ["DMY", "MDY", "YMD"]
        date_order = ask(
            "What is your preferred date ordering (for Day, Month, Year)", date_options
        )
        time.sleep(msg_delay)

        time_first_answer = ask(
            "Do you prefer to input the date or time first ('July 5th 9:30' or"
            " '9:30 July 5th')",
            ["date", "time"],
            default="date",
        )
        time_first = time_first_answer == "time"
        print_err(_divider)
        time.sleep(msg_delay)

    print_err(_default_journal_message)
    time.sleep(msg_delay)

    default_journal = ask(
        "How do you want to call your default journal",
        default="default",
        validator=lambda s: len(s) >= 1,
    )
    print_err(_divider)
    time.sleep(msg_delay)

    config = AppConfig()
    config.set("default_journal", default_journal)
    config.set("journal_directory", journal_dir)
    config.set("git_sync", git_sync)
    if date_order:
        config.set("date_order", date_order)
    if time_first:
        config.set("time_before_date", time_first)
    if time_locale:
        config.set("time_locale", time_locale)

    print_err("All done! You can now start using jpp!")
    print_err("Hit enter to start writing your first entry...")
    print_err()
    input()


def yes_no(prompt: str, default: Optional[bool] = None) -> bool:
    default_string = {True: "y", False: "n", None: None}[default]
    answer = ask(prompt, options=["y", "n"], default=default_string)
    return answer == "y"


def ask(
    prompt: str,
    options: Optional[List[str]] = None,
    default: Optional[str] = "",
    validator: Optional[Callable[[str], bool]] = None,
) -> str:
    assert not options or not validator, "Can't use both a validator and options"

    default = default or ""
    options_string = f"[{'/'.join(options)}] " if options else ""
    prompt += f" (leave blank for '{default}')" if default else ""
    prompt += "? "
    prompt += options_string

    if not options and not validator:
        return input_err(prompt) or default

    assert not default or not options or default in options

    def validate(answ: str) -> bool:
        if options:
            return answ in options

        return validator(answ) if validator else True

    answer = input_err(prompt) or default
    while not validate(answer):
        if options:
            print_err(
                f"I can't understand your answer, please type one of {options_string}"
            )
        else:
            print_err("Invalid answer, please try again")
        answer = input_err(prompt) or default

    return answer


def input_err(prompt: str = "") -> str:
    """
    Works just like input(), but writes the prompt to stderr instead of stdout.
    """
    print_err(prompt, end="")
    return input()


print_err = functools.partial(print, file=sys.stderr)


def _user_editor() -> Optional[List[str]]:
    editor = os.getenv("VISUAL") or os.getenv("EDITOR")
    return shlex.split(editor, posix="win" not in sys.platform) if editor else None


def _is_installed() -> bool:
    return get_config_path().exists()


def main() -> None:
    parser = argparse.ArgumentParser(prog="jpp")
    parser.add_argument(
        "-V",
        "--version",
        dest="version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Prints version information and exits",
    )

    args = parser.parse_args()
    if "func" in args:
        args.func()

    if not _is_installed():
        install()

    compose()
