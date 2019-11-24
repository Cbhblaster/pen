from argparse import _SubParsersAction
from typing import TYPE_CHECKING, Any, List, Tuple

import pluggy

from .entry import Entry


if TYPE_CHECKING:
    from .config import ArgParser, AppConfig


hookspec = pluggy.HookspecMarker("pen")

hookimpl = pluggy.HookimplMarker("pen")
"""Marker to be imported and used in plugins (see pluggy documentation for details)"""


class EntrySerializer:
    """Plugin spec for a Entry Serializer. A plugin implementing these methods
    *must* be given a name that starts with `pen.SERIALIZER_PREFIX`, otherwise
    pen will not pick up on it.
    """

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


class JournalFormatter:
    @hookspec(firstresult=True)
    def format_journal(self, entries: List[Entry]) -> str:
        """
        Turn a list of entries into a single string that can be directly
        printed to the console. The string should ideally put a line break at
        every 88 characters so that it is displayed correctly on all terminals.
        This can also be implemented as a @hookwrapper that only post-processes
        an already serialized entry to e.g. add color through ansi escape
        sequences.

        Must never throw an Exception.
        """


@hookspec  # todo spec
def get_env_options() -> List[Tuple[str, Any]]:
    """todo"""


@hookspec  # todo spec
def prepare_args(args: List[str], parser: "ArgParser") -> None:
    """todo"""


@hookspec  # todo spec
def add_global_options(parser: "ArgParser") -> None:
    """todo"""


@hookspec  # todo spec
def add_subparser(early_config: "AppConfig", subparsers: _SubParsersAction) -> None:
    """todo

    :param early_config: AppConfig before argparsing
    :param subparsers: The object returned by argparse.ArgumentParser.get_subparsers()
    """
