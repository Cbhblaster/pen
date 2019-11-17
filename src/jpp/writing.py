import bisect
import locale
import re

from datetime import datetime
from pathlib import Path
from typing import List, NamedTuple, Optional

import dateparser

from .config import get_jpp_home


SERIALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M"


class Entry(NamedTuple):
    date: datetime
    title: str
    body: str


class Journal:
    def __init__(self, path: Path):
        self.name = path.stem
        self.path = path

    @classmethod
    def from_name(cls, name: str) -> "Journal":
        home = get_jpp_home()
        journal_path = home / name
        return cls(journal_path)

    def add(self, entry: Entry) -> None:
        entries = self.read()
        bisect.insort(entries, entry)  # sorted insert (sorts based on entry.date)

        with self.path.open("a") as fp:
            fp.write("\n\n")
            fp.write(md_serialize(entry))

    def read(self) -> List[Entry]:
        with self.path.open("r") as fp:
            journal_text = fp.read()

        entry_texts = re.split(r"^## ", journal_text, flags=re.MULTILINE)
        entry_texts = entry_texts[1:]  # skip first since it's an empty string
        entries = [md_deserialize(text) for text in entry_texts]
        return entries


def md_serialize(entry: Entry) -> str:
    """Converts entry to markdown compatible string ready to write to file"""
    entry_date = entry.date.strftime(SERIALIZED_DATE_FORMAT)
    entry_string = f"## {entry_date}: {entry.title}"
    if entry.body:
        # we use '## ' to denote a new entry, so we need to escape occurences of '#' in
        # the body at the start of lines by adding two more '#'
        body = re.sub(r"^#", "###", entry.body, flags=re.MULTILINE)
        entry_string += "\n" + body

    return entry_string


def md_deserialize(entry_text: str) -> Entry:
    entry_text = entry_text.strip()
    if not entry_text[0:3] == "## ":
        raise ValueError(f"Cannot read entry, malformed:\n'{entry_text}'")

    entry_text = entry_text[3:]
    title_line, *body_lines = entry_text.split("\n")
    date_str, title = title_line.split(": ")
    date = datetime.strptime(date_str, SERIALIZED_DATE_FORMAT)
    if not date:
        raise ValueError(f"Cannot read entry, date missing:\n'{entry_text}'")

    if not title:
        raise ValueError(f"Cannot read entry, title missing:\n'{entry_text}'")

    body = "\n".join(body_lines) if body_lines else ""
    body = re.sub(r"^##(#*) ", r"\g<1> ", body, flags=re.MULTILINE)

    return Entry(date, title, body)


def parse_entry(text: str, date: Optional[datetime] = None) -> Entry:
    sep = re.search(r"([?!.]+\s*\n?|\n)", text)
    title = text[: sep.end()].strip() if sep else text.strip()
    body = text[sep.end() :].strip() if sep else ""

    if date:
        return Entry(date, title, body)

    colon_pos = title.find(": ")
    if colon_pos > 0:
        date = parse_date(text[:colon_pos])

    if not date:
        date = datetime.now()
    else:
        title = title[colon_pos + 1 :].strip()

    return Entry(date, title, body)


def parse_date(date_string: str) -> datetime:
    user_locale = dateparse_time_locale() or "en"
    return dateparser.parse(date_string, locales=[user_locale])


def dateparse_time_locale() -> Optional[str]:
    _ = locale.setlocale(locale.LC_ALL, "")  # needed to initialize locales
    lc_time = locale.getlocale(locale.LC_TIME)[0]
    lc_time = lc_time.split(".")[0]  # remove potential encoding

    try:
        _ = dateparser.parse("01.01.2000", locales=[lc_time.replace("_", "-")])
        return lc_time
    except ValueError:
        try:
            language = lc_time.replace("_", "-").split("-")[0]
            _ = dateparser.parse("01.01.2000", locales=[language])
            return language
        except ValueError:
            pass

    return None
