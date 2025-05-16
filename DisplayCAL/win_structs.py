"""This module defines Windows-specific structures and types using the `ctypes`
library. It includes utility classes such as `NTSTATUS` for representing
Windows NT status codes and `UNICODE_STRING` for handling Unicode strings
in Windows API interactions.
"""
import ctypes
import functools
from ctypes import wintypes
from typing import ClassVar


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
        return f"NTSTATUS(0x{value:08x})"


class UNICODE_STRING(ctypes.Structure):  # noqa: N801
    _fields_: ClassVar[list[tuple]] = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]
