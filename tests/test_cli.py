from typing import List, Optional
from unittest.mock import patch

import pytest

from jpp.utils import ask, yes_no


@pytest.mark.parametrize(
    "inputs,default,expected",
    [
        (["y"], None, True),
        (["n"], None, False),
        (["foo", "y"], None, True),
        ([""], True, True),
        ([""], False, False),
    ],
)
def test_yes_no(inputs: List[str], default: Optional[bool], expected: bool) -> None:
    question = "foobar"
    with patch("builtins.input", side_effect=iter(inputs)):
        answer = yes_no(question, default)

    assert answer is expected


@pytest.mark.parametrize(
    "inputs,options,default,expected",
    [
        (["foo"], None, None, "foo"),
        (["foo"], ["foo", "bar"], None, "foo"),
        (["funk", "bar"], ["foo", "bar"], None, "bar"),
        ([""], ["foo", "bar"], "bar", "bar"),
    ],
)
def test_ask(
    inputs: List[str], options: Optional[List[str]], default: str, expected: str
) -> None:
    question = "foobar"
    with patch("builtins.input", side_effect=iter(inputs)):
        answer = ask(question, options, default)

    assert answer is expected


def test_ask_validator() -> None:
    question = "foobar"
    expected = "bar"
    with patch("builtins.input", side_effect=iter(["foo", "bar"])):
        answer = ask(question, validator=lambda s: s == "bar")

    assert answer is expected
