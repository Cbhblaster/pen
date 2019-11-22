import re
from datetime import datetime
from typing import Optional

import dateparser
from dateparser import parse

from .config import app_config, user_locale
from .entry import Entry


def parse_entry(text: str, date: Optional[datetime] = None) -> Entry:
    sep = re.search(r"([?!.]+\s+|\n)", text)
    title = text[: sep.end()].strip() if sep else text.strip()
    body = text[sep.end() :].strip() if sep else ""

    if date:
        return Entry(date, title, body)

    colon_pos = title.find(": ")
    if colon_pos > 0:
        date = parse_datetime(text[:colon_pos])

    if not date:
        date = datetime.now()
    else:
        title = title[colon_pos + 1 :].strip()

    return Entry(date, title, body)


def convert_to_dateparser_locale(locale_string: Optional[str]) -> Optional[str]:
    if not locale_string:
        return None

    # easiest way to find a locale string that dateparser is happy with:
    # try it out and see if it fails
    locale_string = locale_string.replace("_", "-")
    try:
        _ = dateparser.parse("01.01.2000", locales=[locale_string])
        return locale_string
    except ValueError:
        pass

    try:
        language = locale_string.split("-")[0]
        _ = dateparser.parse("01.01.2000", locales=[language])
        return language
    except ValueError:
        pass

    return None


def parse_datetime(dt_string: str) -> datetime:
    settings = {"PREFER_DATES_FROM": "past"}
    user_locale_ = user_locale()
    locales = [convert_to_dateparser_locale(user_locale_)] if user_locale_ else None

    if app_config.get("date_format"):
        return parse(
            dt_string,
            locales=locales,
            date_formats=[app_config.get("date_format")],
            settings=settings,
        )

    if app_config.get("locale"):
        return parse(
            dt_string,
            locales=locales,
            languages=[app_config.get("locale")],
            settings=settings,
        )

    if app_config.get("date_order"):
        return parse(
            dt_string,
            locales=locales,
            settings={**settings, "DATE_ORDER": app_config.get("date_order")},
        )

    return parse(dt_string, locales=locales, settings=settings)
