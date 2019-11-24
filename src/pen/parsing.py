import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import dateparser
from dateparser import parse

from .entry import Entry


if TYPE_CHECKING:
    from .config import AppConfig


def parse_entry(
    config: "AppConfig", text: str, date: Optional[datetime] = None
) -> Entry:
    sep = re.search(r"([?!.]+\s+|\n)", text)
    title = text[: sep.end()].strip() if sep else text.strip()
    body = text[sep.end() :].strip() if sep else ""

    if date:
        return Entry(date, title, body)

    colon_pos = title.find(": ")
    if colon_pos > 0:
        date = parse_datetime(config, text[:colon_pos])

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


def parse_datetime(config: "AppConfig", dt_string: str) -> datetime:
    settings = {"PREFER_DATES_FROM": "past"}
    user_locale = config.get("locale")
    locales = [convert_to_dateparser_locale(user_locale)] if user_locale else None

    if config.get("date_format"):
        return parse(
            dt_string,
            locales=locales,
            date_formats=[config.get("date_format")],
            settings=settings,
        )

    if config.get("locale"):
        return parse(
            dt_string,
            locales=locales,
            languages=[config.get("locale")],
            settings=settings,
        )

    if config.get("date_order"):
        return parse(
            dt_string,
            locales=locales,
            settings={**settings, "DATE_ORDER": config.get("date_order")},
        )

    return parse(dt_string, locales=locales, settings=settings)
