from datetime import datetime
from typing import Any, Callable

import dateparser
import hypothesis.strategies as st
import pytest

from hypothesis import assume, example, given
from jpp.writing import Entry, md_deserialize, md_serialize, parse_entry


@pytest.fixture(autouse=True, scope="session")
def init_dateparser() -> None:
    """The first call to parse is really slow, which makes hypothesis unhappy because
    of inconsistent test times.
    """
    dateparser.parse("today", locales=["en"])


@pytest.fixture(autouse=True)
def lc_time(monkeypatch: Any) -> None:
    monkeypatch.setenv("LC_TIME", "en_US.UTF-8")


valid_dt_strings = st.sampled_from(
    ["today: ", "yesterday 5:30pm: ", "15th May 2019: ", "2099-09-09 9am: ", ""]
)
punctuation = st.text(alphabet=["!", ".", "?"])
valid_title_text = st.text(
    min_size=1,
    alphabet=st.characters(
        blacklist_categories=["Cs", "P"], blacklist_characters=["\n"]
    ),
)


@st.composite
def datetime_without_seconds(draw: Callable) -> datetime:
    dt = draw(st.datetimes(min_value=datetime(1000, 1, 1)))
    return dt.replace(second=0, microsecond=0)


@st.composite
def title(draw: Callable) -> str:
    title_string = draw(valid_title_text).lstrip()
    assume(title_string)
    punct = draw(punctuation)
    return (title_string + punct).rstrip()


@st.composite
def body(draw: Callable) -> str:
    """First char of body has to be non-whitespace and non-punctuation"""
    first_char = draw(st.characters(whitelist_categories=["L", "M", "S"]))
    body_string: str = draw(st.text())
    if body_string:
        return first_char + body_string.rstrip()

    return body_string


@given(valid_dt_strings, valid_title_text, punctuation, body())
@example(date="", title_string="not a date: but title", punct="", body_string="")
def test_parse_valid_user_input(
    date: str, title_string: str, punct: str, body_string: str
) -> None:
    assume(not body_string or punct)
    assume(title_string.strip())

    user_input = f"{date}{title_string}{punct}{body_string}"
    entry = parse_entry(user_input)
    dt = dateparser.parse(date[:-2], locales=["en"]) or datetime.now()

    assert _dt_equals_in_minutes(entry.date, dt)
    assert entry.title == (title_string + punct).strip()
    assert entry.body == body_string.strip()


@given(st.builds(Entry, datetime_without_seconds(), title(), body()))
@example(
    Entry(
        datetime(2000, 1, 1), "foo", "## needs escaping\n#### this too\nbut not this ##"
    )
)
def test_md_serialization(entry: Entry) -> None:
    serialized = md_serialize(entry)
    deserialized = md_deserialize(serialized)

    assert serialized.startswith("## ")
    assert entry.title in serialized

    assert _dt_equals_in_minutes(entry.date, deserialized.date)
    assert entry.title == deserialized.title
    assert entry.body == deserialized.body


def _dt_equals_in_minutes(dt1: datetime, dt2: datetime) -> bool:
    return dt1.replace(second=0, microsecond=0) == dt2.replace(second=0, microsecond=0)
