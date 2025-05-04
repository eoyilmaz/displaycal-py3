# -*- coding: utf-8 -*-

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
