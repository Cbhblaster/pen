import locale
import os
import shlex
import sys
from pathlib import Path
from typing import Any, List, Optional

from tomlkit.toml_document import TOMLDocument
from tomlkit.toml_file import TOMLFile

from ..utils import merge_dicts


HOME = Path().home()
PEN_HOME_ENV = "PEN_HOME"
DEFAULT_CONFIG_PATH = HOME / ".config" / "pen" / "pen.toml"
DEFAULT_PEN_HOME = HOME / ".local" / "pen"


class _AppConfig:
    """
    Config class, abstracts reading and writing to file and adding, editing
    or removing pen settings.
    """

    def __init__(self) -> None:
        self._config = TOMLDocument()
        self._config_file = _config_file()
        merge_dicts(self._config, self._config_file.read())

    def get(self, key: str, default: Optional[str] = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        config = self._config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[key] = value
        self._config_file.write(self._config)


def _config_file() -> TOMLFile:
    config_path = get_config_path()
    config_file = TOMLFile(str(config_path))

    if config_path.is_file():
        return config_file

    mode = 0o700  # only current user can modify file
    config_path.parent.mkdir(mode, parents=True, exist_ok=True)
    config_path.touch(mode)

    return config_file


def get_config_path() -> Path:
    return DEFAULT_CONFIG_PATH


app_config = _AppConfig()  # todo: better way to handle configuration


def get_pen_home() -> Path:
    # get from app config?
    pen_home_env = os.getenv(PEN_HOME_ENV)
    pen_home = Path(pen_home_env) if pen_home_env else DEFAULT_PEN_HOME
    pen_home.mkdir(parents=True, exist_ok=True)  # ensure exists
    return pen_home


def env_locale() -> Optional[str]:
    _ = locale.setlocale(locale.LC_ALL, "")  # needed to initialize locales
    lc_time_tuple = locale.getlocale(locale.LC_TIME)  # = (locale, encoding)

    if not lc_time_tuple:
        return None

    # discard the encoding
    lc_time = lc_time_tuple[0]
    return lc_time


def user_locale() -> Optional[str]:
    config_locale = app_config.get("locale")

    if config_locale:
        return config_locale

    return env_locale()


def user_editor() -> Optional[List[str]]:
    editor = os.getenv("VISUAL") or os.getenv("EDITOR")
    return shlex.split(editor, posix="win" not in sys.platform) if editor else None
