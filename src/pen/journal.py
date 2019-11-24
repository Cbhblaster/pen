import bisect
import itertools
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, List, Optional

from .entry import Entry
from .hookspec import hookimpl
from .serializing import JournalSerializer, MarkdownSerializer, SerializationError
from .utils import open_editor, print_err, yes_no


if TYPE_CHECKING:
    from .config import AppConfig


_file_has_no_type_msg = """\
Cannot read journal at {path}.
The file type cannot be determined from the file. Try to import the journal
first using 'pen import <path>'. You might also need to install a plugin first
to add support for your format. Consult the documentation or ask for help on
the issue tracker."""


class Journal:
    def __init__(self, path: Path, config: "AppConfig", file_type: Optional[str]):
        self.path = path
        self.name = path.stem
        self.config = config
        self.file_type = file_type or self._get_file_type(path)
        self.serializer = JournalSerializer(config.pluginmanager, self.file_type)

        if not path.exists():
            print_err(f"Journal '{self.name}' does not exist at path {self.path}")
            if not yes_no("Do you want to create it", default=True):
                sys.exit(0)
            print_err()

            self._create()

    @classmethod
    def from_name(cls, name: Optional[str], config: "AppConfig") -> "Journal":
        home = config.get("journal_directory")
        name = name or config.get("default_journal")
        if not name:
            raise RuntimeError(
                "No journal specified and no default journal set in the config"
            )

        # todo journal registry/index file?
        paths = [path for path in home.iterdir() if path.stem == name]

        assert len(paths) <= 1
        journal_path = home / (name + ".md")

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
            _ = fp.readline()
            journal_text = fp.read()

        entries = self.serializer.deserialize(journal_text)
        try:
            return list(itertools.islice(entries, last_n))
        except SerializationError as err:
            raise SerializationError(
                f"Journal {self.name} at {self.path} could not be read.\n"
                f"Try running 'pen import {self.path}'.",
            ) from err

    def write(self, entries: Iterable[Entry]) -> None:
        with self.path.open("w") as fp:
            fp.write(f"file_type: {self.file_type}\n")
            fp.write(self.serializer.serialize(list(entries)))

    def edit(self, last_n: Optional[int]) -> None:
        entries = list(self.read())
        to_edit = entries[:last_n]
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
            print_err(f"Cannot read, journal '{self.name}' is empty")

        print(self.config.pluginmanager.hook.format_journal(entries=entries))

    def _create(self) -> None:
        home = self.config.get("journal_directory")
        journal_path = home / (self.name + ".txt")
        journal_path.touch(0o700)
        print_err(f"Created journal '{self.name}' at {self.path}")
        print_err()

    def _get_file_type(self, path: Path) -> str:
        with path.open("r") as fp:
            line = fp.readline()

        file_type = re.match(r"^file_type:\s*([\w\-_]*)\s*$", line)

        if file_type:
            return file_type.group(1)

        raise SerializationError(_file_has_no_type_msg.format(path=path))


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
