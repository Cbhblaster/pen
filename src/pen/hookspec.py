from typing import List

import pluggy

from .entry import Entry


hookspec = pluggy.HookspecMarker("pen")


class EntrySerializer:
    # todo: what if no file_type available? Try and see if exception thrown?
    #  maybe use hookwrapper to turn exceptions into None unless
    #  'pen install' is run. still less efficient than firstresult=True though...

    @hookspec(firstresult=True)
    def serialize_entry(self, entry: Entry) -> str:
        """
        Serialize a single entry into a string. The string must to be
        deserializable into the exact same Entry again by `deserialize_entry`.
        Must never throw an Exception.
        """

    @hookspec(firstresult=True)
    def split_entries(self, journal_text: str) -> List[str]:
        """
        todo also return start (and end?) lines for entries for efficient processing
        Split a string containing 0:n entries into a list of entry strings
        for later deserialization. The returned entries must be ordered
        by their date **ascending**, so that the first entry in the list is the oldest.

        Throw `pen.SerializationException` if journal_text is corrupted.
        """

    @hookspec(firstresult=True)
    def deserialize_entry(self, entry_text: str) -> Entry:
        """
        Turn a serialized entry back to an Entry.

        Throw `pen.SerializationException` entry_text is corrupted.
        """
