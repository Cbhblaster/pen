import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Optional

import dateparser

SERIALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M"


class Entry(NamedTuple):
    date: datetime
    title: str
    body: str


class Journal:
    def __init__(self, name: str, path: Path):
        assert path.exists()
        assert name
        self.name = name
        self.path = path


def md_serialize(entry: Entry):
    """Converts entry to markdown compatible string ready to write to file"""
    entry_date = entry.date.strftime(SERIALIZED_DATE_FORMAT)
    entry_string = f"## {entry_date} {entry.title}"
    if entry.body:
        entry_string += "\n" + entry.body

    return entry_string


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
    return dateparser.parse(date_string, locales=["en"])  # todo user preferences
