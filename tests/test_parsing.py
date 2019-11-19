from datetime import datetime
from typing import Callable, Optional, Tuple

import hypothesis.strategies as st
from hypothesis import given

from jpp.parsing import parse_entry

from .strategies import body, title, valid_datetime_strings


@st.composite
def user_text(draw: Callable) -> Tuple[str, str, str, str]:
    dt = draw(valid_datetime_strings)
    title_text = draw(title())
    body_text = draw(body())

    if body_text and title_text[-1] not in "!?.\n":
        title_text += "\n"

    # return title_text and body_text separately so we can test for it later
    return dt + title_text + body_text, dt, title_text, body_text


@given(user_input=user_text(), date=st.one_of(st.none(), st.datetimes()))
def test_parse_entry(
    user_input: Tuple[str, str, str, str], date: Optional[datetime]
) -> None:
    text, dt_text, title_text, body_text = user_input

    entry = parse_entry(text, date)

    assert body_text.strip() == entry.body

    if date:
        assert date == entry.date
        assert dt_text + title_text.strip() == entry.title
    else:
        assert entry.date
        assert title_text.strip() == entry.title
