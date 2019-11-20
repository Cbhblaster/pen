import itertools
from datetime import datetime
from typing import List, Type

import hypothesis.strategies as st
import pytest
from hypothesis import example, given

from pen import Entry
from pen.io.journal import SerializationError, Serializer

from ..strategies import body, datetime_without_seconds, title
from ..utils import dt_equals_in_minutes


# automatically tests new Serializers when they are created, neat!
serializers = Serializer.__subclasses__()


@pytest.mark.parametrize("serializer_cls", serializers)
@given(entry=st.builds(Entry, datetime_without_seconds(), title(), body()))
@example(Entry(datetime(2000, 1, 1), "foo", "## needs escaping\n#### this too\n###"))
def test_serialization(serializer_cls: Type[Serializer], entry: Entry) -> None:
    serializer = serializer_cls()
    serialized = serializer.serialize([entry])
    deserialized = next(serializer.deserialize(serialized))

    assert entry.title in serialized  # make sure title is still readable

    assert dt_equals_in_minutes(entry.date, deserialized.date)
    assert entry.title == deserialized.title
    assert entry.body == deserialized.body


@pytest.mark.parametrize("serializer_cls", serializers)
@given(entries=st.lists(st.builds(Entry, datetime_without_seconds(), title(), body())))
def test_serialize_multiple(
    serializer_cls: Type[Serializer], entries: List[Entry]
) -> None:
    serializer = serializer_cls()
    serialized = serializer.serialize(entries)
    deserialized = list(serializer.deserialize(serialized))

    for expected, entry in zip(entries, deserialized):
        # make sure title is still readable in serialized form
        assert entry.title in serialized

        # make sure entries stay the same after being converted to string and back
        assert dt_equals_in_minutes(entry.date, expected.date)
        assert entry.title == expected.title
        assert entry.body == expected.body


_invalid_entries = [
    "## ",
    "##  - no date",
    "## 2019-01-01 09:30 - ",
    "## 2019-01-01 09:30 no seperator",
    "## 2019-30-01 09:30 - invalid date",
    "## 2019-30-01 - no time",
    "## 2019-30-01 25:30 - invalid time",
]


@pytest.mark.parametrize(
    "serializer_cls,entry_string", itertools.product(serializers, _invalid_entries)
)
def test_deserialize_fail_on_invalid(
    serializer_cls: Type[Serializer], entry_string: str
) -> None:
    serializer = serializer_cls()
    with pytest.raises(SerializationError):
        _ = list(serializer.deserialize(entry_string))
