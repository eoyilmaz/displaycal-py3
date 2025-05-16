"""This module defines custom ctypes-based types and structures that map to
common GLib types. These types are used for interoperability with C libraries
that rely on GLib.
"""

from ctypes import Structure, c_char_p, c_int, c_uint
from typing import ClassVar


class gchar_p(c_char_p):  # noqa: N801
    # represents "[const] gchar*"
    pass


class gint(c_int):  # noqa: N801
    pass


class guint(c_uint):  # noqa: N801
    pass


class guint32(c_uint):  # noqa: N801
    pass


class GQuark(guint32):
    pass


class GError(Structure):
    _fields_: ClassVar[list[tuple]] = [
        ("DOMAIN", GQuark),
        ("code", gint),
        ("message", gchar_p),
    ]
