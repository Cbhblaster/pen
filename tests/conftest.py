from pathlib import Path
from typing import Any

import dateparser
import pytest

import pen
from pen.config import PEN_HOME_ENV, AppConfig, _get_plugin_manager


@pytest.fixture(autouse=True, scope="session")
def init_dateparser() -> None:
    """The first call to parse is really slow, which makes hypothesis unhappy because
    of inconsistent test times. So we just call it once here to make it load its data.
    """
    dateparser.parse("today", locales=["en"])


@pytest.fixture(autouse=True)
def lc_time(monkeypatch: Any) -> None:
    monkeypatch.setenv("LC_TIME", "en_US.UTF-8")


@pytest.fixture
def empty_config() -> AppConfig:
    pm = _get_plugin_manager([])
    return AppConfig([], pm)


@pytest.fixture(autouse=True)
def pen_home(monkeypatch: Any, tmpdir: Path) -> Path:
    journal_dir = tmpdir / "journals"
    journal_dir.mkdir()
    monkeypatch.setenv(PEN_HOME_ENV, str(journal_dir))
    monkeypatch.setattr(pen.config, "DEFAULT_PEN_HOME", str(journal_dir))
    return journal_dir
