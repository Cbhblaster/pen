import pluggy

from .entry import Entry


__version__ = "0.1.0"

__all__ = [
    "Entry",
    "hookimpl",
]

# Marker to be imported and used in plugins (see pluggy documentation for details)
hookimpl = pluggy.HookimplMarker("pen")
