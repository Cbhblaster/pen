import re
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set

import dateparser
from pluggy import PluginManager

from pen.exceptions import UsageError

from .entry import Entry
from .hookspec import hookimpl


SERIALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M"
SERIALIZER_PREFIX = "serializer-"
IMPORTER_PREFIX = "importer-"


class SerializationError(Exception):
    pass


class JournalSerializer:
    """Handles serialization of journal based on hooks."""

    def __init__(self, pluginmanager: PluginManager, file_type: str) -> None:
        self.file_type = file_type
        serializer_name = f"{SERIALIZER_PREFIX}{self.file_type}"
        importer_name = f"{IMPORTER_PREFIX}{self.file_type}"
        plugins = dict(pluginmanager.list_name_plugin())

        if serializer_name not in plugins and importer_name not in plugins:
            options = available_serializers(pluginmanager).union(
                available_importers(pluginmanager)
            )
            raise SerializationError(
                f"File type {file_type} not supported. You may"
                f" need to install a plugin supporting this type."
                f" Available types: {options}"
            )

        self._entry_serializer = (
            plugins[serializer_name]
            if serializer_name in plugins
            else plugins[importer_name]
        )

    def serialize(self, entries: Sequence[Entry]) -> str:
        """Converts entries to markdown compatible string ready to write to file.
        Expects entries to be sorted by date newest to oldest."""
        entry_string = "\n\n".join(
            self._entry_serializer.serialize_entry(entry=entry)
            for entry in reversed(entries)
        )

        return entry_string

    def deserialize(self, journal_text: str) -> Iterator[Entry]:
        """Takes a serialized journal as text, splits the text into individual entries
        and parses each entry. Returns an iterator over the entries newest to oldest.
        """
        if not journal_text:
            return iter([])

        journal_text = journal_text.strip()
        entry_texts = self._entry_serializer.split_entries(journal_text=journal_text)

        # lazy evaluation, only deserialize the entries that are actually needed
        entries = (
            self._entry_serializer.deserialize_entry(entry_text=entry_text)
            for entry_text in reversed(entry_texts)
        )
        return entries


class MarkdownSerializer:
    file_type = "pen-default-markdown"
    entry_marker = "## "

    def __init__(self, datetime_format: Optional[str] = None):
        self.datetime_format = datetime_format or SERIALIZED_DATE_FORMAT

    @hookimpl(trylast=True)
    def serialize_entry(self, entry: Entry) -> str:
        entry_date = entry.date.strftime(self.datetime_format)
        entry_string = f"{self.entry_marker}{entry_date} - {entry.title}"
        if entry.body:
            # we use '## ' to denote a new entry, so we need to escape occurrences
            # of '#' in the body at the start of lines by adding two more '#'
            body = re.sub(r"^#", "###", entry.body, flags=re.MULTILINE)
            entry_string += "\n" + body

        entry_string += "\n"
        return entry_string

    @hookimpl(trylast=True)
    def split_entries(self, journal_text: str) -> List[str]:
        entry_texts = re.split(
            fr"^{self.entry_marker}", journal_text, flags=re.MULTILINE
        )
        entry_texts = entry_texts[1:]  # skip everything before the first entry
        # re-add the split-tokens we just removed
        entry_texts = ["## " + entry for entry in entry_texts]

        return entry_texts

    @hookimpl(trylast=True)
    def deserialize_entry(self, entry_text: str) -> Entry:
        if not entry_text[:3] == self.entry_marker:
            raise SerializationError(
                f"Cannot read entry, entry marker '{self.entry_marker}' missing:\n"
                f"Entry: '{entry_text}'"
            )

        entry_text = entry_text[3:].strip()
        title_line, *body_lines = entry_text.split("\n")

        try:
            date_str, title = title_line.split(" - ", 1)
            date = datetime.strptime(date_str, self.datetime_format)
        except ValueError as err:
            raise SerializationError(
                f"Cannot read entry, entry malformed:\nEntry: '{entry_text}'"
            ) from err

        if not title:
            raise SerializationError(
                f"Cannot read entry, title missing:\nEntry: '{entry_text}'"
            )

        body = "\n".join(body_lines)
        # unescape markdown titles
        body = re.sub(r"^##(#+)", r"\g<1>", body, flags=re.MULTILINE)

        return Entry(date, title, body)


class JrnlImporter:
    file_type = "jrnl-v2"

    def __init__(self, datetime_format: Optional[str] = None):
        self.datetime_format = datetime_format or SERIALIZED_DATE_FORMAT

    @hookimpl(trylast=True)
    def serialize_entry(self, entry: Entry) -> str:
        raise UsageError(
            "The jrnl format is currently only available for"
            " importing journals. Please use a different file type for"
            " storing your journals."
        )

    @hookimpl(trylast=True)
    def split_entries(self, journal_text: str) -> List[str]:
        entry_re = re.compile(
            r"^\[(?:[^\]]+)\] .*?(?=\n\[(?:[^\]]+)\] |\Z)",
            flags=re.MULTILINE | re.DOTALL,
        )
        entry_matches = entry_re.finditer(journal_text)
        entry_texts = [entry[0] for entry in entry_matches]

        return entry_texts

    @hookimpl(trylast=True)
    def deserialize_entry(self, entry_text: str) -> Entry:
        _, *matches = re.split(r"^\[([^\]]+)\]", entry_text, maxsplit=1)
        if not matches:
            raise SerializationError(
                f"Cannot read entry, date string not found:\n" f"Entry: '{entry_text}'"
            )

        date_str = matches[0]
        date = dateparser.parse(date_str)

        if not date:
            raise SerializationError(
                f"Cannot read entry, date parsing failed:\n"
                f"Entry: '{entry_text}'\n"
                f"Date string: '{date_str}'"
            )

        entry_text = matches[1].strip()

        # The following code is adapted from jrnl:

        title_re = re.compile(
            r"""
        (                        # A sentence ends at one of two sequences:
            [.!?\u203C\u203D\u2047\u2048\u2049\u3002\uFE52\uFE57\uFF01\uFF0E\uFF1F\uFF61]
                                 # Either, a sequence starting with a sentence terminal,
            [\'\u2019\"\u201D]?  # an optional right quote,
            [\])]*              # optional closing brackets and
            \s+                  # a sequence of required spaces.
        |                        # Otherwise,
            \n                   # a newline also terminates sentences.
        )""",
            re.VERBOSE,
        )

        title, *rest = title_re.split(entry_text, maxsplit=1)

        if not rest:
            body = ""
        else:
            title = (title + rest[0]).strip()  # end of sentence belongs to title
            body = rest[1].strip()

        return Entry(date, title, body)


def available_serializers(pm: PluginManager) -> Set[str]:
    plugins: Dict[str, Any] = dict(pm.list_name_plugin())
    supported_file_types = {
        name[len(SERIALIZER_PREFIX) :]
        for name in plugins
        if name.startswith(SERIALIZER_PREFIX)
    }
    return supported_file_types


def available_importers(pm: PluginManager) -> Set[str]:
    plugins: Dict[str, Any] = dict(pm.list_name_plugin())
    supported_file_types = {
        name[len(IMPORTER_PREFIX) :]
        for name in plugins
        if name.startswith(IMPORTER_PREFIX)
    }
    return supported_file_types
