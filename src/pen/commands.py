import sys
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from pen.journal import Journal
from pen.parsing import parse_entry
from pen.utils import open_editor, print_err


if TYPE_CHECKING:
    from pen.config import AppConfig


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
    journal.pprint(args.last_n)


def list_command(config: "AppConfig", _: Namespace) -> None:
    for journal_path in Path(config.get("journal_directory")).iterdir():
        print(f"{journal_path.stem} ({journal_path})")


def delete_command(config: "AppConfig", args: Namespace) -> None:
    journal = Journal.from_name(args.journal, config)
    journal.delete(args.last_n)
