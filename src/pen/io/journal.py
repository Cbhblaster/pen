import bisect
import itertools
import re
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Type

from .. import Entry
from ..utils import open_editor, print_err, yes_no
from .config import app_config, get_pen_home


SERIALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M"


class SerializationError(Exception):
    pass


_serializer_registry: Dict[str, Type["Serializer"]] = {}


class Serializer(ABC):
    """
    Abstract base class for Journal Serializers. When subclassing, you must
    specify the file_ending in the class definition like so:

    >>> class TextSerializer(Serializer, file_ending = ".txt")
    ...    pass
    ...
    >>> TextSerializer.file_ending
    '.txt'
    """

    file_ending: str

    def __init_subclass__(cls, file_ending: str, **kwargs: Any) -> None:
        assert file_ending
        cls.file_ending = file_ending
        _serializer_registry[file_ending] = cls
        super().__init_subclass__()

    def serialize(self, entries: Iterable[Entry]) -> str:
        """Converts entries to markdown compatible string ready to write to file.
        Expects entries to be sorted by date newest to oldest."""
        entry_string = "\n\n".join(
            self._serialize_entry(entry) for entry in reversed(list(entries))
        )

        return entry_string

    def deserialize(self, journal_text: str) -> Iterator[Entry]:
        """Takes a serialized journal as text, splits the text into individual entries
        and parses each entry. Returns an iterator over the entries newest to oldest.
        """
        if not journal_text:
            return iter([])

        journal_text = journal_text.strip()
        entry_texts = self._split_entries(journal_text)
        # lazy evaluation, only deserialize the entries that are actually needed
        entries = (
            self._deserialize_entry(entry_text) for entry_text in reversed(entry_texts)
        )
        return entries

    @abstractmethod
    def _serialize_entry(self, entry_text: Entry) -> str:
        pass

    @abstractmethod
    def _split_entries(self, journal_text: str) -> List[str]:
        pass

    @abstractmethod
    def _deserialize_entry(self, entry_text: str) -> Entry:
        pass


class MarkdownSerializer(Serializer, file_ending=".md"):
    def _serialize_entry(self, entry: Entry) -> str:
        entry_date = entry.date.strftime(SERIALIZED_DATE_FORMAT)
        entry_string = f"## {entry_date} - {entry.title}"
        if entry.body:
            # we use '## ' to denote a new entry, so we need to escape occurences
            # of '#' in the body at the start of lines by adding two more '#'
            body = re.sub(r"^#", "###", entry.body, flags=re.MULTILINE)
            entry_string += "\n" + body

        entry_string += "\n"
        return entry_string

    def _split_entries(self, journal_text: str) -> List[str]:
        if not journal_text.lstrip()[:3] == "## ":
            raise SerializationError(
                f"Cannot read markdown journal, it seems to be malformed"
            )

        entry_texts = re.split(r"^## ", journal_text, flags=re.MULTILINE)
        return entry_texts[1:]  # skip first since it's an empty string

    def _deserialize_entry(self, entry_text: str) -> Entry:
        entry_text = entry_text.strip()
        title_line, *body_lines = entry_text.split("\n")

        try:
            date_str, title = title_line.split(" - ", 1)
            date = datetime.strptime(date_str, SERIALIZED_DATE_FORMAT)
        except ValueError as err:
            raise SerializationError(
                f"Cannot read entry, entry malformed:\n'{entry_text}'"
            ) from err

        if not title:
            raise SerializationError(
                f"Cannot read entry, title missing:\n'{entry_text}'"
            )

        body = "\n".join(body_lines)
        body = re.sub(r"^##(#+)", r"\g<1>", body, flags=re.MULTILINE)

        return Entry(date, title, body)


class Journal:
    def __init__(self, path: Path, serializer: Serializer):
        self.serializer = serializer
        self.path = path
        self.name = path.stem

        if not path.exists():
            print_err(f"Journal '{self.name}' does not exist at path {self.path}")
            if not yes_no("Do you want to create it", default=True):
                sys.exit(0)
            print_err()

            self._create()

    @classmethod
    def from_name(cls, name: Optional[str], file_ending: str = ".md") -> "Journal":
        home = get_pen_home()
        name = name or app_config.get("default_journal")
        if not name:
            raise RuntimeError(
                "No journal specified and no default journal set in the config"
            )

        journal_path = home / (name + file_ending)
        serializer_cls = _serializer_registry[file_ending]

        return cls(journal_path, serializer_cls())  # get serializer from index/filename

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
            journal_text = fp.read()

        entries = self.serializer.deserialize(journal_text)
        try:
            return list(itertools.islice(entries, last_n))
        except SerializationError as err:
            raise ValueError(
                f"Journal {self.name} at {self.path} could not be read."
                f" Did you modify it by hand?",
            ) from err

    def write(self, entries: Iterable[Entry]) -> None:
        with self.path.open("w") as fp:
            # reverse it again before writing to get it in the same order
            fp.write(self.serializer.serialize(entries))

    def edit(self, last_n: Optional[int]) -> None:
        entries = list(self.read())
        to_edit = entries[:last_n]
        to_edit_sting = self.serializer.serialize(to_edit)
        edited_string = open_editor(to_edit_sting)
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

        print(self.serializer.serialize(reversed(entries)))

    def _create(self) -> None:
        home = get_pen_home()
        journal_path = home / (self.name + self.serializer.file_ending)
        journal_path.touch(0o700)
        print_err(f"Created journal '{self.name}' at {self.path}")
        print_err()


def read(journal_name: Optional[str] = None, last_n: Optional[int] = None) -> None:
    journal = Journal.from_name(journal_name)
    journal.pprint(last_n)


def list_journals() -> None:
    for journal in get_pen_home().iterdir():
        print(f"{journal.stem} ({journal})")


def edit(journal_name: str, last_n: int) -> None:
    journal = Journal.from_name(journal_name)
    journal.edit(last_n)


def delete(journal_name: str, last_n: int) -> None:
    journal = Journal.from_name(journal_name)
    journal.delete(last_n)
