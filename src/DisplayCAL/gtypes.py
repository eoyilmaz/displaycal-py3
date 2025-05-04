# -*- coding: utf-8 -*-

from ctypes import Structure, c_char_p, c_int, c_uint


class gchar_p(c_char_p):
    # represents "[const] gchar*"
    pass


class gint(c_int):
    pass


class guint(c_uint):
    pass


class guint32(c_uint):
    pass


class GQuark(guint32):
    pass


class GError(Structure):
    _fields_ = [("DOMAIN", GQuark), ("code", gint), ("message", gchar_p)]
