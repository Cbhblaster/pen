import sys
import warnings
from typing import Any, List, Optional, Tuple

from pen.commands import install_command
from pen.config import get_config
from pen.exceptions import UsageError
from pen.utils import print_err

from .config import AppConfig


class InternalError(Exception):
    pass


def main(argv: Optional[List[str]] = None) -> None:
    if not sys.warnoptions:
        warnings.simplefilter("ignore")

    argv = argv if argv is not None else sys.argv[1:]

    plugins: List[Tuple[Any, str]] = []

    config = get_config(argv, plugins)

    if not _is_installed(config):
        install_command(config)

    parsed_args = config.cli_args
    if "func" in parsed_args:
        try:
            parsed_args.func(config, parsed_args)
        except UsageError as user_err:
            if parsed_args.debug:
                raise
            else:
                print_err("Error:", user_err)
        except Exception as err:
            raise InternalError(
                "Something went wrong. Please post the stacktrace above on our"
                " issue tracker so we can try to help out."
            ) from err


def _is_installed(config: AppConfig) -> bool:
    return config.config_file_exists()
