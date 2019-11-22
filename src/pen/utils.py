import functools
import os
import subprocess
import sys
from collections.abc import Mapping
from tempfile import mkstemp
from typing import Callable, List, Optional


_no_editor_message = """\
Editing journals or using custom prompts is not supported without
an editor. pen will try to fall back to nano, but this might fail. Please set
up your preferred editor by setting the $VISUAL environment variable.
"""


def merge_dicts(d1: dict, d2: dict) -> None:
    for k in d2:
        if k in d1 and isinstance(d1[k], dict) and isinstance(d2[k], Mapping):
            merge_dicts(d1[k], d2[k])
        else:
            d1[k] = d2[k]


def yes_no(prompt: str, default: Optional[bool] = None) -> bool:
    default_string = {True: "y", False: "n", None: None}[default]
    answer = ask(prompt, options=["y", "n"], default=default_string)
    return answer == "y"


def ask(
    prompt: str,
    options: Optional[List[str]] = None,
    default: Optional[str] = "",
    validator: Optional[Callable[[str], bool]] = None,
) -> str:
    assert not options or not validator, "Can't use both a validator and options"

    default = default or ""
    options_string = f"[{'/'.join(options)}] " if options else ""
    prompt += f" (leave blank for '{default}')" if default else ""
    prompt += "? "
    prompt += options_string

    if not options and not validator:
        return input_err(prompt) or default

    assert not default or not options or default in options

    def validate(answ: str) -> bool:
        if options:
            return answ in options

        return validator(answ) if validator else True

    answer = input_err(prompt) or default
    while not validate(answer):
        if options:
            print_err(
                f"I can't understand your answer, please type one of {options_string}"
            )
        else:
            print_err("Invalid answer, please try again")
        answer = input_err(prompt) or default

    return answer


def input_err(prompt: str = "") -> str:
    """
    Works just like input(), but writes the prompt to stderr instead of stdout.
    """
    print_err(prompt, end="")
    return input()


print_err = functools.partial(print, file=sys.stderr)


def open_editor(text: Optional[str] = None) -> str:
    # todo importing here to avoid circular import. Should be changed if possible
    from .config import user_editor

    editor = user_editor()

    if text and not editor:
        print_err(_no_editor_message)
        editor = ["/bin/nano"]

    if editor:
        print_err("Opening your editor now. Save and close to compose your entry")
        tmpfile_handle, tmpfile_path = mkstemp(suffix="-pen.txt", text=True)

        if text:
            with open(tmpfile_path, "w") as fp:
                fp.write(text)

        subprocess.call(editor + [tmpfile_path])
        os.close(tmpfile_handle)

        with open(tmpfile_path, "r") as fp:
            entry_string = fp.read()

        os.remove(tmpfile_path)
    else:
        print_err(
            "Composing a new entry, press ctrl+d to finish writing"
            " (ctrl+c to cancel)"
        )
        entry_string = sys.stdin.read()

    return entry_string
