"""This module defines custom ctypes-based types and structures that map to
common GLib types. These types are used for interoperability with C libraries
that rely on GLib.
"""

from ctypes import Structure, c_char_p, c_int, c_uint
from typing import ClassVar


class gchar_p(c_char_p):  # noqa: N801
    """Represents a pointer to a null-terminated string."""
    # represents "[const] gchar*"


class gint(c_int):  # noqa: N801
    """Represents a signed integer."""


class guint(c_uint):  # noqa: N801
    """Represents a unsigned integer."""


class guint32(c_uint):  # noqa: N801
    """Represents a 32-bit unsigned integer."""


class GQuark(guint32):
    """Represents a GQuark, which is a unique identifier for a string."""


class GError(Structure):
    """Structure representing a GError."""

    _fields_: ClassVar[list[tuple]] = [
        ("DOMAIN", GQuark),
        ("code", gint),
        ("message", gchar_p),
    ]
