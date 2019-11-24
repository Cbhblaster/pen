from argparse import Namespace
from pathlib import Path
from typing import Any

import dateparser
import pluggy
import pytest

from pen.config import PEN_HOME_ENV, AppConfig


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
    pm = pluggy.PluginManager("pen")
    return AppConfig(Namespace(), pm)


@pytest.fixture(autouse=True)
def patch_pen_home(monkeypatch: Any, tmpdir: Path) -> None:
    monkeypatch.setenv(PEN_HOME_ENV, str(tmpdir))
    journal_dir = tmpdir / "journals"
    journal_dir.mkdir()
    monkeypatch.setattr("pen.config", "DEFAULT_PEN_HOME", str(journal_dir))
