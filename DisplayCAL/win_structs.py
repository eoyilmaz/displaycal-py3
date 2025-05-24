"""This module defines Windows-specific structures and types using the `ctypes`
library. It includes utility classes such as `NTSTATUS` for representing
Windows NT status codes and `UNICODE_STRING` for handling Unicode strings
in Windows API interactions.
"""

from __future__ import annotations

import ctypes
import functools
from ctypes import wintypes
from typing import ClassVar


@functools.total_ordering
class NTSTATUS(ctypes.c_long):
    """Class representing NTSTATUS values."""

    def __eq__(self, other: int | NTSTATUS) -> bool:
        """Compare the NTSTATUS value with another value.

        Args:
            other (int | NTSTATUS): The value to compare with.

        Returns:
            bool: True if the NTSTATUS value is equal to the other value,
                False otherwise.
        """
        if hasattr(other, "value"):
            other = other.value
        return self.value == other

    def __ne__(self, other: int | NTSTATUS) -> bool:
        """Compare the NTSTATUS value with another value.

        Args:
            other (int | NTSTATUS): The value to compare with.

        Returns:
            bool: True if the NTSTATUS value is not equal to the other value,
                False otherwise.
        """
        if hasattr(other, "value"):
            other = other.value
        return self.value != other

    def __lt__(self, other: int | NTSTATUS) -> bool:
        """Compare the NTSTATUS value with another value.

        Args:
            other (int | NTSTATUS): The value to compare with.

        Returns:
            bool: True if the NTSTATUS value is less than the other value,
                False otherwise.
        """
        if hasattr(other, "value"):
            other = other.value
        return self.value < other

    def __bool__(self) -> bool:
        """Check if the NTSTATUS value indicates success.

        Returns:
            bool: True if the NTSTATUS value indicates success (0 or greater),
                False otherwise.
        """
        return self.value >= 0

    def __repr__(self) -> str:
        """Return a string representation of the NTSTATUS value.

        Returns:
            str: A string representation of the NTSTATUS value in hexadecimal format.
        """
        value = ctypes.c_ulong.from_buffer(self).value
        return f"NTSTATUS(0x{value:08x})"


class UNICODE_STRING(ctypes.Structure):  # noqa: N801
    """Class representing a UNICODE_STRING structure."""

    _fields_: ClassVar[list[tuple]] = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]
