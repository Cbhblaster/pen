from datetime import datetime
from typing import Callable

from hypothesis import assume
from hypothesis import strategies as st


@st.composite
def datetime_without_seconds(draw: Callable) -> datetime:
    dt = draw(st.datetimes(min_value=datetime(1000, 1, 1)))
    return dt.replace(second=0, microsecond=0)


# we are not really testing dateparser features here, so we can just use a small
# static list for these
valid_datetime_strings = st.sampled_from(
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
