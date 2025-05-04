# -*- coding: utf-8 -*-

from ctypes import wintypes
import ctypes
import os

from DisplayCAL.win_structs import NTSTATUS, UNICODE_STRING

PVOID = ctypes.c_void_p
PULONG = ctypes.POINTER(wintypes.ULONG)
ULONG_PTR = wintypes.WPARAM
ACCESS_MASK = wintypes.DWORD
STATUS_INFO_LENGTH_MISMATCH = NTSTATUS(0xC0000004)


class SYSTEM_INFORMATION_CLASS(ctypes.c_ulong):
    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"


SystemExtendedHandleInformation = SYSTEM_INFORMATION_CLASS(64)


class SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX(ctypes.Structure):
    _fields_ = [
        ("Object", PVOID),
        ("UniqueProcessId", wintypes.HANDLE),
        ("HandleValue", wintypes.HANDLE),
        ("GrantedAccess", ACCESS_MASK),
        ("CreatorBackTraceIndex", wintypes.USHORT),
        ("ObjectTypeIndex", wintypes.USHORT),
        ("HandleAttributes", wintypes.ULONG),
        ("Reserved", wintypes.ULONG),
    ]


class SYSTEM_INFORMATION(ctypes.Structure):
    pass


PSYSTEM_INFORMATION = ctypes.POINTER(SYSTEM_INFORMATION)


class SYSTEM_HANDLE_INFORMATION_EX(SYSTEM_INFORMATION):
    _fields_ = [
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
except WindowsError:
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
    return _get_handle_info(handle, ObjectNameInformation)


def get_handle_type(handle):
    return _get_handle_info(handle, ObjectTypeInformation)


def get_handles():
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
    import sys

    if len(sys.argv) > 1:
        pid = int(sys.argv[1])
    else:
        pid = None
    for handle in get_process_handles(pid):
        print(
            (
                "Handle = 0x%04x, Type = 0x%02x %r, Access = 0x%06x, Name = %r"
                % (
                    handle.HandleValue,
                    handle.ObjectTypeIndex,
                    get_handle_type(handle),
                    handle.GrantedAccess,
                    get_handle_name(handle),
                )
            )
        )
