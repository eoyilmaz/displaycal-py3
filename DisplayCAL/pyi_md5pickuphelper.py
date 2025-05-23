"""This module provides a platform-specific fallback mechanism for importing
the `md5` hashing function. It ensures compatibility on systems where the
`hashlib` module is unavailable by attempting to use the `_md5` module as a
fallback, except on macOS (darwin) and Windows (win32), where such fallback is
not supported.
"""

from sys import platform

if platform not in ("darwin", "win32"):
    try:
        import _md5
    except ImportError:
        _md5 = None
try:
    from hashlib import md5
except ImportError as exception:
    if platform not in ("darwin", "win32") and _md5:
        md5 = _md5
    else:
        raise exception
