from ._version import __version__
from .config import AppConfig, ArgParser
from .entry import Entry
from .hookspec import hookimpl
from .serializing import SERIALIZER_PREFIX


__all__ = [
    "__version__",
    "Entry",
    "ArgParser",
    "AppConfig",
    "hookimpl",
    "SERIALIZER_PREFIX",
]


@hookimpl
def add_global_options(parser: ArgParser) -> None:
    parser.add_argument(
        "-V",
        "--version",
        dest="version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Prints version information and exits",
    )
