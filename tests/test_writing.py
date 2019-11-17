from datetime import datetime
from typing import Any, Callable

import dateparser
import hypothesis.strategies as st
import pytest

from hypothesis import assume, example, given
from jpp.writing import parse_entry


@pytest.fixture(autouse=True, scope="session")
def init_dateparser() -> None:
    """The first call to parse is really slow, which makes hypothesis unhappy because
    of inconsistent test times.
    """
    dateparser.parse("today", locales=["en"])


@pytest.fixture(autouse=True)
def lc_time(monkeypatch: Any) -> None:
    monkeypatch.setenv("LC_TIME", "en_US")


valid_dt_strings = st.sampled_from(
    ["today: ", "yesterday 5:30pm: ", "15th May 2019: ", "2099-09-09 9am: ", ""]
)
punctuation = st.text(alphabet=["!", ".", "?"])
valid_title = st.text(
    min_size=1,
    alphabet=st.characters(
        blacklist_categories=["Cs", "P"], blacklist_characters=["\n"]
    ),
)


@st.composite
def body(draw: Callable) -> None:
    """First char of body has to be non-whitespace and non-punctuation"""
    first_char = draw(st.characters(whitelist_categories=["L", "M", "S"]))
    body = draw(st.text())
    if body:
        return first_char + body

    return body


@given(valid_dt_strings, valid_title, punctuation, body())
@example(date="", title="not a date: bar", punct="", body="")
def test_parse_valid_user_input(date: str, title: str, punct: str, body: str) -> None:
    assume(not body or punct)
    assume(title.strip())

    user_input = f"{date}{title}{punct}{body}"
    entry = parse_entry(user_input)
    dt = dateparser.parse(date[:-2], locales=["en"]) or datetime.now()

    assert (
        entry.date.year == dt.year
        and entry.date.month == dt.month
        and entry.date.day == dt.day
    )
    assert entry.title == (title + punct).strip()
    assert entry.body == body.strip()
