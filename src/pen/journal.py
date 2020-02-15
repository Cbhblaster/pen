import bisect
import itertools
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Optional

from pen.exceptions import UsageError

from .entry import Entry
from .hookspec import hookimpl
from .serializing import JournalSerializer, MarkdownSerializer
from .utils import get_pager, open_editor, print_err, yes_no


if TYPE_CHECKING:
    from .config import AppConfig


class Journal:
    def __init__(self, path: Path, config: "AppConfig", file_type: Optional[str]):
        self.path = path
        self.name = path.stem
        self.config = config
        self.file_type = file_type or file_type_from_marker(path)
        self.serializer = JournalSerializer(config.pluginmanager, self.file_type)

    @classmethod
    def from_name(cls, name: Optional[str], config: "AppConfig") -> "Journal":
        home = Path(config.get("journal_directory"))
        name = name or config.get("default_journal")
        if not name:
            raise UsageError(
                "No journal specified and no default journal set in the config"
            )

        # todo hook based collection system
        default_path = home / (name + ".txt")
        paths = [path for path in home.iterdir() if path.stem == name]

        assert len(paths) <= 1
        journal_path = paths[0] if paths else None
        journal_path = journal_path or Path(
            config.get(f"journals.{name}.path", default_path)
        )

        if not journal_path.exists():
            print_err(f"Journal '{name}' does not exist at path {journal_path}")
            if not yes_no("Do you want to create it", default=True):
                sys.exit(0)
            print_err()

            cls.create(config, name, journal_path)

        return cls(journal_path, config, None)

    def add(self, entry: Entry) -> None:
        entries = list(reversed(self.read()))  # get entries sorted by date ascending

        # sorted O(n) insert (inserts based on entry.date which is why we needed to
        # reverse the list above)
        bisect.insort(entries, entry)

        self.write(reversed(entries))

    def read(self, last_n: Optional[int] = None) -> List[Entry]:
        """Reads journal from disk and returns the *last_n* entries, ordered by
        date from most recent to least."""
        last_n = abs(last_n) if last_n else None
        with self.path.open("r") as fp:
            marker = fp.readline()
            journal_text = fp.read()
            if _extract_file_type_marker(marker) is None:
                journal_text = marker + journal_text

        entries = self.serializer.deserialize(journal_text)
        try:
            return list(itertools.islice(entries, last_n))
        except Exception as err:
            raise UsageError(
                f"Journal {self.name} at {self.path} could not be read."
                f" Try running 'pen import {self.path}'.",
            ) from err

    def write(self, entries: Iterable[Entry]) -> None:
        with self.path.open("w") as fp:
            fp.write(f"file_type: {self.file_type}\n")
            fp.write(self.serializer.serialize(list(entries)))

    def edit(self, last_n: Optional[int]) -> None:
        entries = list(self.read())
        to_edit = entries[:last_n]
        if not to_edit:
            raise UsageError(
                f"Cannot edit anything, no entries were found in journal '{self.name}'."
            )

        to_edit_sting = self.serializer.serialize(to_edit)
        edited_string = open_editor(self.config, to_edit_sting)
        edited = list(self.serializer.deserialize(edited_string))

        num_deleted = len(to_edit) - len(edited)
        if num_deleted > 0:
            entry_entries = "entry" if num_deleted == 1 else "entries"
            print_err(f"It looks like you deleted {num_deleted} {entry_entries}. Are")
            print_err(f" you sure you want to continue?")
            cont = yes_no("Continue", default=True)

            if not cont:
                sys.exit(0)

        entries[:last_n] = edited
        self.write(entries)

    def delete(self, last_n: Optional[int] = None) -> None:
        entries = list(self.read())

        if not entries:
            print_err(f"Cannot delete anything, journal '{self.name}' is empty")
            return

        keep = [
            entry
            for entry in entries[:last_n]
            if not yes_no(f"Delete entry '{entry.date}: {entry.title}'", default=False)
        ]

        entries[:last_n] = keep

        self.write(entries)

    def pprint(self, last_n: Optional[int] = None) -> None:
        entries = self.read(last_n)

        if not entries:
            raise UsageError(
                f"Cannot read journal '{self.name}'. Journal is empty (or corrupt)"
            )

        # todo only use pager if output is longer than terminal height
        pager = get_pager(self.config)
        pager(self.config.pluginmanager.hook.format_journal(entries=entries))

    @staticmethod
    def create(config: "AppConfig", name: str, path: Path) -> "Journal":
        home = config.get("journal_directory")
        journal_path = home / (name + ".txt")
        journal_path.touch(0o700)
        # todo don't hardcode default
        file_type = config.get("default_file_type", default="pen-default-markdown")

        with journal_path.open("w") as fp:
            fp.write(f"file_type: {file_type}\n")

        print_err(f"Created journal '{name}' at {path}")
        print_err()

        return Journal(path, config, file_type)


class MarkdownPrinter:
    """Turns entries into printable string using MarkdownSerializer"""

    @hookimpl
    def format_journal(self, entries: List[Entry]) -> str:
        import locale

        try:
            locale.setlocale(locale.LC_ALL, "")  # todo only once at start
            datetime_format = locale.nl_langinfo(locale.D_T_FMT) or None

            if datetime_format:
                datetime_format = re.sub(r"(\s?%Z\s?)", "", datetime_format)
                datetime_format = re.sub(r"%T", "%H:%M", datetime_format)

        except AttributeError:
            datetime_format = None

        serializer = MarkdownSerializer(datetime_format)
        journal_string = "\n\n".join(
            serializer.serialize_entry(entry) for entry in entries
        )

        return journal_string


def file_type_from_marker(path: Path) -> str:
    with path.open("r") as fp:
        line = fp.readline()

    file_type = _extract_file_type_marker(line)

    if file_type:
        return file_type

    raise UsageError(_file_has_no_type_msg.format(path))


def _extract_file_type_marker(line: str) -> Optional[str]:
    file_type = re.match(r"^file_type:\s*([\w\-_]*)\s*$", line)
    return file_type.group(1) if file_type else None


_file_has_no_type_msg = """\
Cannot read journal at {}.
The file type cannot be determined from the file. Try to import the journal
first using 'pen import <path>'. You might also need to install a plugin first
to add support for this format. Consult the documentation or ask for help on
the issue tracker."""
