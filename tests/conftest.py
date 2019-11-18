from typing import Any

import dateparser
import pytest


@pytest.fixture(autouse=True, scope="session")
def init_dateparser() -> None:
    """The first call to parse is really slow, which makes hypothesis unhappy because
    of inconsistent test times. So we just call it once here to make it load its data.
    """
    dateparser.parse("today", locales=["en"])


@pytest.fixture(autouse=True)
def lc_time(monkeypatch: Any) -> None:
    monkeypatch.setenv("LC_TIME", "en_US.UTF-8")
