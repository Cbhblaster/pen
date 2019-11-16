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

import dateparser
from dateparser import parse

from . import __version__
from .config import JPP_HOME_ENV, AppConfig, get_config_path


def parse_datetime(dt_string: str, config: AppConfig) -> datetime:
    if config.get("date_format"):
        return parse(dt_string, date_formats=[config.get("date_format")])

    if config.get("locales"):
        return parse(dt_string, languages=[config.get("locales")])

    if config.get("date_order"):
        return parse(dt_string, settings={"DATE_ORDER": config.get("date_order")})

    return parse(dt_string)  # let dateparser guess the locale


def compose():
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
    print_err("You wrote:", new_entry)


def install():
    welcome_message = """\
********** Welcome to jpp! **********
Before you start jotting down your thoughts, please allow me to ask a few
questions on how to set up jpp.
"""

    sync_message = """\
There's two ways you can backup and sync jpp journals and settings
across your devices: either put the journals in a directory synced by your
preferred cloud storage (Dropbox, Google Cloud...) or by activating git sync.
The latter keeps a full history of all your changes, which might come in handy.
"""

    sync_prompt = """\
Do you want to activate git sync? Git sync will automatically commit changes to
your journals. You can also set up a remote later on to automatically push and
pull from there. By default, this will be set to "detect", which means it will
detect whether your jpp home is a git repository or not.
"""

    jpp_dir_prompt = """\
In what directory do you want to put your journals? Note that this directory can
be shared across devices, for example by syncing it using Dropbox.
"""

    locale_message = """\
jpp is using the system locale settings ({}) for date parsing and formatting.
You can still change your preferred date format later by either changing the
'LC_TIME' environment variable or setting one of the date settings in the jpp
configuration.
"""

    default_journal_message = """\
Now it's time to create your first journal. This will be your default journal.
You can create additional journals later if you want. For now, I need a name
for your first one, though.
"""

    time_locale = ""
    date_order = ""
    time_first = ""
    journal_directory = os.getenv(JPP_HOME_ENV)

    print_err(welcome_message)
    time.sleep(0.3)

    print_err(sync_message)
    time.sleep(0.3)

    print_err(sync_prompt)

    git_sync = ask("Activate git sync", options=["y", "n", "detect"], default="detect")
    print_err()

    if git_sync == "y":
        from .gitsync import init

        init()

    if not journal_directory:
        print_err(jpp_dir_prompt)

        journal_directory = ask("Where")
        journal_directory = str(Path(journal_directory).expanduser().absolute())
        print_err(f"")

    if _dateparse_time_locale():
        time_locale = locale.getlocale(locale.LC_TIME)[0]
        print_err(locale_message.format(time_locale))
    else:
        date_options = ["DMY", "MDY", "YMD"]
        date_order = ask(
            "What is your preferred date ordering (for Day, Month, Year)", date_options
        )

        time_first = ask(
            "Do you prefer to input the date or time first ('July 5th 9:30' or"
            " '9:30 July 5th')",
            ["date", "time"],
            default="date",
        )
        time_first = time_first == "time"

    # todo check if journals already exist in journal_directory

    print_err(default_journal_message)
    default_journal = ask(
        "How do you want to call your default journal",
        default="default",
        validator=lambda s: len(s) >= 1,
    )

    config = AppConfig()
    config.set("default_journal", default_journal)
    config.set("journal_directory", journal_directory)
    config.set("git_sync", git_sync)
    config.set("date_order", date_order)
    config.set("time_before_date", time_first)
    config.set("time_locale", time_locale)

    print_err()
    print_err("All done! You can now start writing your first entry")
    print_err("Hit enter to start writing your first entry")
    input()


def yes_no(prompt: str, default: Optional[bool] = None) -> bool:
    default_string = {True: "y", False: "n", None: ""}[default]
    answer = ask(prompt, options=["y", "n"], default=default_string)
    return answer == "y"


def ask(
    prompt: str,
    options: Optional[List[str]] = None,
    default: str = "",
    validator: Optional[Callable[[str], bool]] = None,
) -> str:
    assert not options or not validator, "Can't use both a validator and options"

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


def _dateparse_time_locale() -> Optional[str]:
    _ = locale.setlocale(locale.LC_ALL, "")
    lc_time = locale.getlocale(locale.LC_TIME)[0]

    try:
        _ = dateparser.parse("01.01.2000", locales=[lc_time.replace("_", "-")])
        return lc_time
    except ValueError:
        try:
            language = lc_time.replace("_", "-").split("-")[0]
            _ = dateparser.parse("01.01.2000", locales=[language])
            return language
        except ValueError:
            pass

    return None


def main():
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
