import os
from pathlib import Path
from typing import Any, Optional

from jpp.utils import merge_dicts
from tomlkit.toml_document import TOMLDocument
from tomlkit.toml_file import TOMLFile
from xdg import XDG_DATA_HOME

JPP_HOME_ENV = "JPP_HOME"
DEFAULT_JPP_HOME = XDG_DATA_HOME / "jpp"
DEFAULT_CONFIG_PATH = DEFAULT_JPP_HOME / "jpp.toml"


class AppConfig:
    """
    Config class, abstracts reading and writing to file and adding, editing
    or removing jpp settings.
    """

    default_config = {
        "tagsymbols": "@",
    }

    def __init__(self):
        self._config = TOMLDocument()
        merge_dicts(self._config, self.default_config)
        self._config_file = _config_file()
        merge_dicts(self._config, self._config_file.read())

    def get(self, key: str, default: Optional[str] = None):
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
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
    """
    Uses environment variable to get the jpp config path, if it is not set uses
    default xdg config directory instead.

    :return: path to jpp config file
    """
    config_env = os.getenv(JPP_HOME_ENV)
    config_path = Path(config_env) / "jpp.toml" if config_env else DEFAULT_CONFIG_PATH
    return config_path
