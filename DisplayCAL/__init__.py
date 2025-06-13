try:  # noqa: N999
    from DisplayCAL import __version__
except ImportError:
    __version__ = "0.0.0.0"  # noqa: S104
else:
    __version__ = __version__.VERSION_STRING
