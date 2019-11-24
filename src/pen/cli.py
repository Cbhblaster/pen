import os
import sys
import time
import warnings
from pathlib import Path
from typing import Any, List, Optional, Tuple

from tomlkit.toml_document import TOMLDocument

from pen.config import get_config

from .config import DEFAULT_PEN_HOME, PEN_HOME_ENV, AppConfig
from .parsing import convert_to_dateparser_locale
from .utils import ask, print_err, yes_no


_install_msg_delay = (
    0.3  # a bit of delay makes the walls of text a bit easier to follow
)

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
hooks = None


def setup_sync() -> bool:
    git_sync = yes_no("Use git sync")
    print_err(_divider)

    if git_sync:
        pass  # todo ask for url and pull repo

    return git_sync


def install(config: AppConfig) -> None:
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

        # todo check if journals already exist in journal_directory

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
    time.sleep(_install_msg_delay)

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
    input()


def _is_installed(config: AppConfig) -> bool:
    return config.config_file_exists()


def main(argv: Optional[List[str]] = None) -> None:
    if not sys.warnoptions:
        warnings.simplefilter("ignore")

    argv = argv if argv is not None else sys.argv[1:]

    plugins: List[Tuple[Any, str]] = []

    config = get_config(argv, plugins)

    if not _is_installed(config):
        install(config)

    parsed_args = config.cli_args

    if "func" in parsed_args:
        parsed_args.func(config, parsed_args)
