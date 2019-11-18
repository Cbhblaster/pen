from datetime import datetime


def dt_equals_in_minutes(dt1: datetime, dt2: datetime) -> bool:
    return dt1.replace(second=0, microsecond=0) == dt2.replace(second=0, microsecond=0)
