# -*- coding: utf-8 -*-

from ctypes import wintypes
import ctypes
import functools


@functools.total_ordering
class NTSTATUS(ctypes.c_long):
    def __eq__(self, other):
        if hasattr(other, "value"):
            other = other.value
        return self.value == other

    def __ne__(self, other):
        if hasattr(other, "value"):
            other = other.value
        return self.value != other

    def __lt__(self, other):
        if hasattr(other, "value"):
            other = other.value
        return self.value < other

    def __bool__(self):
        return self.value >= 0

    def __repr__(self):
        value = ctypes.c_ulong.from_buffer(self).value
        return "NTSTATUS(0x%08x)" % value


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]
