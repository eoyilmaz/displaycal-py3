"""This module provides utilities for interacting with Windows system handles,
including functions to query handle information, retrieve handle names and
types, and list handles for specific processes. It uses the Windows API
through the `ctypes` library.
"""

import ctypes
import os
import sys
from ctypes import wintypes
from typing import ClassVar

from DisplayCAL.win_structs import NTSTATUS, UNICODE_STRING

PVOID = ctypes.c_void_p
PULONG = ctypes.POINTER(wintypes.ULONG)
ULONG_PTR = wintypes.WPARAM
ACCESS_MASK = wintypes.DWORD
STATUS_INFO_LENGTH_MISMATCH = NTSTATUS(0xC0000004)


class SYSTEM_INFORMATION_CLASS(ctypes.c_ulong):  # noqa: N801
    """Class representing SYSTEM_INFORMATION_CLASS values."""

    def __repr__(self) -> str:
        """Return a string representation of the SYSTEM_INFORMATION_CLASS.

        Returns:
            str: A string representation of the SYSTEM_INFORMATION_CLASS in
                hexadecimal format.
        """
        return f"{self.__class__.__name__}({self.value})"


SystemExtendedHandleInformation = SYSTEM_INFORMATION_CLASS(64)


class SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX(ctypes.Structure):  # noqa: N801
    """Class representing SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX structure."""

    _fields_: ClassVar[list[tuple]] = [
        ("Object", PVOID),
        ("UniqueProcessId", wintypes.HANDLE),
        ("HandleValue", wintypes.HANDLE),
        ("GrantedAccess", ACCESS_MASK),
        ("CreatorBackTraceIndex", wintypes.USHORT),
        ("ObjectTypeIndex", wintypes.USHORT),
        ("HandleAttributes", wintypes.ULONG),
        ("Reserved", wintypes.ULONG),
    ]


class SYSTEM_INFORMATION(ctypes.Structure):  # noqa: N801
    """Class representing SYSTEM_INFORMATION structure."""


PSYSTEM_INFORMATION = ctypes.POINTER(SYSTEM_INFORMATION)


class SYSTEM_HANDLE_INFORMATION_EX(SYSTEM_INFORMATION):  # noqa: N801
    """Class representing SYSTEM_HANDLE_INFORMATION_EX structure."""

    _fields_: ClassVar[list[tuple]] = [
        ("NumberOfHandles", ULONG_PTR),
        ("Reserved", ULONG_PTR),
        ("_Handles", SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX * 1),
    ]

    @property
    def Handles(self):
        arr_t = SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX * self.NumberOfHandles
        return ctypes.POINTER(arr_t)(self._Handles)[0]


try:
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtQuerySystemInformation.restype = NTSTATUS
    ntdll.NtQuerySystemInformation.argtypes = (
        SYSTEM_INFORMATION_CLASS,  # SystemInformationClass
        PSYSTEM_INFORMATION,  # SystemInformation
        wintypes.ULONG,  # SystemInformationLength
        PULONG,
    )  # ReturnLength
except OSError:
    # Just in case
    ntdll = None


ObjectBasicInformation = 0
ObjectNameInformation = 1
ObjectTypeInformation = 2


def _get_handle_info(handle, info_class):
    if hasattr(handle, "HandleValue"):
        handle = handle.HandleValue
    size_needed = wintypes.DWORD()
    buf = ctypes.c_buffer(0x1000)
    ntdll.NtQueryObject(
        handle,
        info_class,
        ctypes.byref(buf),
        ctypes.sizeof(buf),
        ctypes.byref(size_needed),
    )
    return UNICODE_STRING.from_buffer_copy(buf[: size_needed.value]).Buffer


def get_handle_name(handle):
    """Get the name of a handle."""
    return _get_handle_info(handle, ObjectNameInformation)


def get_handle_type(handle):
    """Get the type of a handle."""
    return _get_handle_info(handle, ObjectTypeInformation)


def get_handles():
    """Get all handles in the system."""
    info = SYSTEM_HANDLE_INFORMATION_EX()
    length = wintypes.ULONG()
    while True:
        status = ntdll.NtQuerySystemInformation(
            SystemExtendedHandleInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(length),
        )
        if status != STATUS_INFO_LENGTH_MISMATCH:
            break
        ctypes.resize(info, length.value)
    if status < 0:
        raise ctypes.WinError(ntdll.RtlNtStatusToDosError(status))
    return info.Handles


def get_process_handles(pid=None):
    """Get handles of process <pid> (current process if not specified)"""
    if not pid:
        pid = os.getpid()
    handles = []
    for handle in get_handles():
        if handle.UniqueProcessId != pid:
            continue
        handles.append(handle)
    return handles


if __name__ == "__main__":
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    for handle in get_process_handles(pid):
        print(
            f"Handle = 0x{handle.HandleValue:04x}, "
            f"Type = 0x{handle.ObjectTypeIndex:02x} {get_handle_type(handle)!r}, "
            f"Access = 0x{handle.GrantedAccess:06x}, "
            f"Name = {get_handle_name(handle)!r}"
        )
