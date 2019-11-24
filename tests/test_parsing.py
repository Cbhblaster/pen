from datetime import datetime
from typing import Callable, Optional, Tuple

import hypothesis.strategies as st
from hypothesis import example, given

from pen.config import AppConfig
from pen.parsing import parse_entry

from .strategies import body, title, valid_datetime_strings


@st.composite
def user_text(draw: Callable) -> Tuple[str, str, str]:
    dt = draw(valid_datetime_strings)
    title_text = draw(title())
    body_text = draw(body())

    if body_text and not any(c in title_text for c in ["\n", ". ", "? ", "! "]):
        # make sure title and body are separated properly
        title_text += draw(st.one_of(st.just("\n"), st.just(". ")))

    # return title_text and body_text separately so we can test for it later
    return dt, title_text, body_text


@given(user_input=user_text(), date=st.one_of(st.none(), st.datetimes()))
@example(user_input=("", "decimal dot 2.718 no problem\n", ""), date=None)
@example(user_input=("", ":_: colon first char! ", "body"), date=None)
def test_parse_entry(
    empty_config: AppConfig, user_input: Tuple[str, str, str], date: Optional[datetime]
) -> None:
    dt_text, title_text, body_text = user_input
    text = dt_text + title_text + body_text

    entry = parse_entry(empty_config, text, date)

    assert body_text.strip() == entry.body

    if date:
        assert date == entry.date
        assert dt_text + title_text.strip() == entry.title
    else:
        assert entry.date
        assert title_text.strip() == entry.title
