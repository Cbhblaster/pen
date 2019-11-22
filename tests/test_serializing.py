from datetime import datetime
from typing import List, Type

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from pen.entry import Entry
from pen.hookspec import EntrySerializer
from pen.serializing import JournalSerializer, MarkdownSerializer, SerializationError
from tests.strategies import body, datetime_without_seconds, title


journal_serializers = [JournalSerializer]
entry_serializers = [MarkdownSerializer]


@pytest.mark.skip()
@pytest.mark.parametrize("journal_serializer_cls", journal_serializers)
@given(entries=st.lists(st.builds(Entry, datetime_without_seconds(), title(), body())))
def test_serialize_journal(
    journal_serializer_cls: Type[JournalSerializer], entries: List[Entry]
) -> None:
    # todo
    serializer = journal_serializer_cls(..., ...)  # type: ignore
    serialized = serializer.serialize(entries)
    deserialized = list(serializer.deserialize(serialized))

    for expected, entry in zip(entries, deserialized):
        # make sure title is still readable in serialized form
        assert entry.title in serialized
        # make sure entries stay the same after being converted to string and back
        assert entry == expected


@pytest.mark.parametrize("entry_serializer_cls", entry_serializers)
@given(entry=st.builds(Entry, datetime_without_seconds(), title(), body()))
@example(Entry(datetime(2000, 1, 1), "foo", "## needs escaping\n####"))
def test_serialize_entry(
    entry_serializer_cls: Type[EntrySerializer], entry: Entry
) -> None:
    serializer = entry_serializer_cls()
    serialized = serializer.serialize_entry(entry)
    deserialized = serializer.deserialize_entry(serialized)

    assert entry == deserialized


@pytest.mark.parametrize(
    "entry_string",
    [
        "## ",
        "##  - no date",
        "## 2019-01-01 09:30 - ",
        "## 2019-01-01 09:30   no separator",
        "## 2019-30-01 09:30 - invalid date",
        "## 2019-01-01 - no time",
        "## 2019-01-01 25:30 - invalid time",
    ],
)
def test_md_deserialize_fail_on_invalid(entry_string: str) -> None:
    serializer = MarkdownSerializer()
    with pytest.raises(SerializationError):
        _ = serializer.deserialize_entry(entry_string)
