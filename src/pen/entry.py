from datetime import datetime
from typing import Any, NamedTuple


class Entry(NamedTuple):
    """A single journal entry"""

    date: datetime
    title: str
    body: str

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False

        # datetime is only recorded in minutes
        datetime_same = _dt_equals_in_minutes(self.date, other.date)
        return datetime_same and self.title == other.title and self.body == other.body


def _dt_equals_in_minutes(dt1: datetime, dt2: datetime) -> bool:
    return dt1.replace(second=0, microsecond=0) == dt2.replace(second=0, microsecond=0)
