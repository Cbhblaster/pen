import pluggy


__version__ = "0.1.0"


# Marker to be imported and used in plugins (see pluggy documentation for details)
hookimpl = pluggy.HookimplMarker("pen")
