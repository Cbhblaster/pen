import re
from datetime import datetime
from typing import Iterable, Iterator, List

from pen.hookspec import EntrySerializer
from pluggy import PluginManager

from . import hookimpl
from .entry import Entry


SERIALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M"


class SerializationError(Exception):
    pass


class JournalSerializer:
    """Handles serialization of journal based on hooks."""

    def __init__(self, pluginmanager: PluginManager, file_type: str) -> None:
        self.file_type = file_type
        serializer_name = f"serializer-{self.file_type}"
        plugins = dict(pluginmanager.list_name_plugin())

        if serializer_name not in plugins:
            raise SerializationError(
                f"File type {file_type} not supported. You may"
                f" need to install a plugin supporting this type."
                f" Available types: {list(plugins.keys())}"
            )

        self.entry_serializer = plugins[serializer_name]

    def serialize(self, entries: Iterable[Entry]) -> str:
        """Converts entries to markdown compatible string ready to write to file.
        Expects entries to be sorted by date newest to oldest."""
        entry_string = "\n\n".join(
            self.entry_serializer.serialize_entry(entry=entry)
            for entry in reversed(list(entries))
        )

        return entry_string

    def deserialize(self, journal_text: str) -> Iterator[Entry]:
        """Takes a serialized journal as text, splits the text into individual entries
        and parses each entry. Returns an iterator over the entries newest to oldest.
        """
        if not journal_text:
            return iter([])

        journal_text = journal_text.strip()
        entry_texts = self.entry_serializer.split_entries(journal_text=journal_text)
        # lazy evaluation, only deserialize the entries that are actually needed
        entries = (
            self.entry_serializer.deserialize_entry(entry_text=entry_text)
            for entry_text in reversed(entry_texts)
        )
        return entries


class MarkdownSerializer(EntrySerializer):
    file_type = "pen-default-markdown"
    entry_marker = "## "

    @hookimpl(trylast=True)
    def serialize_entry(self, entry: Entry) -> str:
        entry_date = entry.date.strftime(SERIALIZED_DATE_FORMAT)
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
            date = datetime.strptime(date_str, SERIALIZED_DATE_FORMAT)
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
