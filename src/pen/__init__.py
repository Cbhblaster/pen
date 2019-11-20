from datetime import datetime
from typing import NamedTuple


__version__ = "0.1.0"


class Entry(NamedTuple):
    date: datetime
    title: str
    body: str
