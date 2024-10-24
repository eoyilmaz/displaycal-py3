# -*- coding: utf-8 -*-
"""
util_win.py.

This module provides utility functions for interacting with Windows-specific features,
such as display devices, process management, and color management.
"""
import ctypes
import platform
import struct
import sys
from ctypes import POINTER, byref, sizeof, windll, wintypes
from ctypes.wintypes import DWORD, HANDLE, LPWSTR

from DisplayCAL.util_os import quote_args
from DisplayCAL.win_structs import UNICODE_STRING

import _ctypes

import pywintypes

import win32api

from win32comext.shell import shell as win32com_shell

import win32con

import win32process

import winerror

import winreg

if not hasattr(ctypes, "c_bool"):
    # Python 2.5
    ctypes.c_bool = ctypes.c_int

if sys.getwindowsversion() >= (6,):
    LPDWORD = POINTER(DWORD)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = windll.kernel32
    QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
    QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, LPDWORD]
    QueryFullProcessImageNameW.restype = bool

try:
    psapi = ctypes.windll.psapi
except WindowsError:
    psapi = None


# Access registry directly instead of Wcs* functions that leak handles
USE_REGISTRY = True


# DISPLAY_DEVICE structure, StateFlags member
# http://msdn.microsoft.com/en-us/library/dd183569%28v=vs.85%29.aspx

# wingdi.h

# Flags for parent devices
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x1
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x8
# Represents a pseudo device used to mirror application drawing for remoting or
# other purposes.
# An invisible pseudo monitor is associated with this device.
# For example, NetMeeting uses it.
# Note that GetSystemMetrics (SM_MONITORS) only accounts for visible display monitors.
DISPLAY_DEVICE_MODESPRUNED = (
    0x8000000  # The device has more display modes than its output devices support.
)
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x4  # The primary desktop is on the device.
# For a system with a single display card, this is always set.
# For a system with multiple display cards, only one device can have this set.
DISPLAY_DEVICE_REMOVABLE = (
    0x20  # The device is removable; it cannot be the primary display.
)
DISPLAY_DEVICE_VGA_COMPATIBLE = 0x10  # The device is VGA compatible.
DISPLAY_DEVICE_DISCONNECT = 0x2000000
DISPLAY_DEVICE_MULTI_DRIVER = 0x2
DISPLAY_DEVICE_REMOTE = 0x4000000

# Flags for child devices
DISPLAY_DEVICE_ACTIVE = 0x1
# DISPLAY_DEVICE_ACTIVE specifies whether a monitor is presented as being "on"
# by the respective GDI view.
# Windows Vista:
# EnumDisplayDevices will only enumerate monitors that can be presented as being "on."
DISPLAY_DEVICE_ATTACHED = 0x2


# MONITORINFO structure, dwFlags member
# https://msdn.microsoft.com/de-de/library/windows/desktop/dd145065(v=vs.85).aspx
MONITORINFOF_PRIMARY = 0x1

# Icm.h
CLASS_MONITOR = struct.unpack("!L", b"mntr")[0]
CLASS_PRINTER = struct.unpack("!L", b"prtr")[0]
CLASS_SCANNER = struct.unpack("!L", b"scnr")[0]

# ShellExecute
SEE_MASK_FLAG_NO_UI = 0x00000400
SEE_MASK_NOASYNC = 0x00000100
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_WAITFORINPUTIDLE = 0x02000000


def _get_icm_display_device_key(devicekey):
    monkey = devicekey.split("\\")[-2:]  # pun totally intended
    subkey = "\\".join(
        [
            "Software",
            "Microsoft",
            "Windows NT",
            "CurrentVersion",
            "ICM",
            "ProfileAssociations",
            "Display",
        ]
        + monkey
    )
    return winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey)


class MSCMSLoader:
    """Loader class for MSCMS."""

    _windll = None

    @classmethod
    def get_mscms_windll(cls):
        """
        Get the MSCMS windll instance.

        Returns:
            MSCMS: The MSCMS windll instance.
        """
        if not cls._windll:
            cls._windll = MSCMS()
        return cls._windll


def _get_mscms_windll():
    return MSCMSLoader.get_mscms_windll()


def calibration_management_isenabled():
    """
    Check if calibration is enabled under Windows 7.

    Returns:
        bool: True if calibration is enabled, False otherwise.
    """
    if sys.getwindowsversion() < (6, 1):
        # Windows XP and Vista don't have calibration management
        return False
    if False:
        # Using registry - NEVER
        # Also, does not work!
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ICM\Calibration",
        ) as key:
            return bool(winreg.QueryValueEx(key, "CalibrationManagementEnabled")[0])
    else:
        # Using ctypes
        mscms = _get_mscms_windll()
        pbool = ctypes.pointer(ctypes.c_bool())
        if not mscms or not mscms.WcsGetCalibrationManagementState(pbool):
            return
        return bool(pbool.contents)


def disable_calibration_management():
    """Disable calibration loading under Windows 7."""
    enable_calibration_management(False)


def disable_per_user_profiles(display_no=0):
    """
    Disable per user profiles under Vista/Windows 7.

    Args:
        display_no (int): The display number.
    """
    enable_per_user_profiles(False, display_no)


def enable_calibration_management(enable=True):
    """
    Enable calibration loading under Windows 7.

    Args:
        enable (bool): Whether to enable calibration management.

    Returns:
        bool: True if successful, False otherwise.

    Raises:
        NotImplementedError: If the OS version is less than Windows 7.
        get_windows_error: If an error occurs while setting the calibration
            management state.
    """
    if sys.getwindowsversion() < (6, 1):
        raise NotImplementedError(
            "Calibration Management is only available in Windows 7 or later"
        )
    if False:
        # Using registry - NEVER
        # Also, does not work!
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ICM\Calibration",
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(
                key, "CalibrationManagementEnabled", 0, winreg.REG_DWORD, int(enable)
            )
    else:
        # Using ctypes (must be called with elevated permissions)
        mscms = _get_mscms_windll()
        if not mscms:
            return False
        if not mscms.WcsSetCalibrationManagementState(enable):
            raise get_windows_error(ctypes.windll.kernel32.GetLastError())
        return True


def enable_per_user_profiles(enable=True, display_no=0, devicekey=None):
    """
    Enable per user profiles under Vista/Windows 7.

    Args:
        enable (bool): Whether to enable per user profiles.
        display_no (int): The display number.
        devicekey (str): The device key.

    Returns:
        bool: True if successful, False otherwise.

    Raises:
        NotImplementedError: If the OS version is less than Windows Vista.
        get_windows_error: If an error occurs while setting the per user
            profiles state.
    """
    if sys.getwindowsversion() < (6,):
        # Windows XP doesn't have per-user profiles
        raise NotImplementedError(
            "Per-user profiles are only available in Windows Vista, 7 or later"
        )
    if not devicekey:
        device = get_display_device(display_no)
        if device:
            devicekey = device.DeviceKey
    if devicekey:
        if USE_REGISTRY:
            with _get_icm_display_device_key(devicekey) as key:
                winreg.SetValueEx(
                    key, "UsePerUserProfiles", 0, winreg.REG_DWORD, int(enable)
                )
        else:
            # Using ctypes - this leaks registry key handles internally in
            # WcsSetUsePerUserProfiles since Windows 10 1903
            mscms = _get_mscms_windll()
            if not mscms:
                return False
            if not mscms.WcsSetUsePerUserProfiles(
                str(devicekey), CLASS_MONITOR, enable
            ):
                raise get_windows_error(ctypes.windll.kernel32.GetLastError())
        return True


def get_display_devices(devicename):
    r"""
    Get all display devices of an output (there can be several).

    Example usage:
        get_display_devices('\\\\.\\DISPLAY1')
        devicename = '\\\\.\\DISPLAYn' where n is a positive integer starting at 1.

    Args:
        devicename (str): The device name.

    Returns:
        list: List of display devices.
    """
    devices = []
    n = 0
    while True:
        try:
            devices.append(win32api.EnumDisplayDevices(devicename, n))
        except pywintypes.error:
            break
        n += 1
    return devices


def get_first_display_device(devicename, exception_cls=pywintypes.error):
    """
    Get the first display of device <devicename>.

    Args:
        devicename (str): The device name.
        exception_cls (Exception): The exception class to catch.

    Returns:
        DisplayDevice: The first display device.
    """
    try:
        return win32api.EnumDisplayDevices(devicename, 0)
    except exception_cls:
        pass


def get_active_display_device(devicename, devices=None):
    r"""
    Get active display device of an output (there can only be one per output).

    Return value: display device object or None.

    Example usage:
        get_active_display_device('\\\\.\\DISPLAY1')
        devicename = '\\\\.\\DISPLAYn' where n is a positive integer starting at 1.

    Args:
        devicename (str): The device name.
        devices (list): List of devices.

    Returns:
        DisplayDevice: The active display device (display device object) or None.
    """
    if not devices:
        devices = get_display_devices(devicename)
    for device in devices:
        if device.StateFlags & DISPLAY_DEVICE_ACTIVE and (
            len(devices) == 1 or device.StateFlags & DISPLAY_DEVICE_ATTACHED
        ):
            return device


def get_active_display_devices(attrname=None):
    """
    Return active display devices.

    Args:
        attrname (str): The attribute name to get from the display device.

    Returns:
        list: List of active display devices.
    """
    devices = []
    for moninfo in get_real_display_devices_info():
        device = get_active_display_device(moninfo["Device"])
        if device:
            if attrname:
                device = getattr(device, attrname)
            devices.append(device)
    return devices


def get_display_device(
    display_no=0, use_active_display_device=False, exception_cls=pywintypes.error
):
    """
    Get the display device for a given display number.

    Args:
        display_no (int): The display number.
        use_active_display_device (bool): Whether to use the active display device.
        exception_cls (Exception): The exception class to catch.

    Returns:
        DisplayDevice: The display device.
    """
    # The ordering will work as long as Argyll continues using EnumDisplayMonitors
    monitors = get_real_display_devices_info()
    moninfo = monitors[display_no]
    if use_active_display_device:
        return get_active_display_device(moninfo["Device"])
    else:
        return get_first_display_device(moninfo["Device"], exception_cls)


def get_process_filename(pid, handle=0):
    """
    Get the filename of a process.

    Args:
        pid (int): The process ID.
        handle (int): The process handle.

    Returns:
        str: The filename of the process.

    Raises:
        WinError: If an error occurs while querying the process filename.
    """
    if sys.getwindowsversion() >= (6,):
        flags = PROCESS_QUERY_LIMITED_INFORMATION
    else:
        flags = win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ
    if not handle:
        handle = win32api.OpenProcess(flags, False, pid)
    try:
        if sys.getwindowsversion() >= (6,):
            dwSize = win32con.MAX_PATH
            while True:
                dwFlags = 0  # The name should use the Win32 path format
                lpdwSize = DWORD(dwSize)
                lpExeName = ctypes.create_unicode_buffer("", lpdwSize.value + 1)
                success = QueryFullProcessImageNameW(
                    int(handle), dwFlags, lpExeName, byref(lpdwSize)
                )
                if success and 0 < lpdwSize.value < dwSize:
                    break
                error = kernel32.GetLastError()
                if error != winerror.ERROR_INSUFFICIENT_BUFFER:
                    raise ctypes.WinError(error)
                dwSize = dwSize + 256
                if dwSize > 0x1000:
                    # This prevents an infinite loop under Windows Server 2008
                    # if the path contains spaces, see
                    # http://msdn.microsoft.com/en-us/library/ms684919(VS.85).aspx#4
                    raise ctypes.WinError(error)
            filename = lpExeName.value
        else:
            filename = win32process.GetModuleFileNameEx(handle, 0)
    finally:
        win32api.CloseHandle(handle)
    return filename


def get_file_info(filename):
    """
    Get exe/dll file information.

    Args:
        filename (str): The filename.

    Returns:
        dict: The file information.
    """
    info = {"FileInfo": None, "StringFileInfo": {}, "FileVersion": None}

    finfo = win32api.GetFileVersionInfo(filename, "\\")
    info["FileInfo"] = finfo
    info["FileVersion"] = (
        f"{finfo['FileVersionMS'] // 65536}.{finfo['FileVersionMS'] % 65536}.{finfo['FileVersionLS'] // 65536}.{finfo['FileVersionLS'] % 65536}"  # noqa: B950
    )
    for lcid, codepage in win32api.GetFileVersionInfo(
        filename, "\\VarFileInfo\\Translation"
    ):
        info["StringFileInfo"][lcid, codepage] = {}
        for name in [
            "Comments",
            "CompanyName",
            "FileDescription",
            "FileVersion",
            "InternalName",
            "LegalCopyright",
            "LegalTrademarks",
            "OriginalFilename",
            "PrivateBuild",
            "ProductName",
            "ProductVersion",
            "SpecialBuild",
        ]:
            value = win32api.GetFileVersionInfo(
                filename, f"\\StringFileInfo\\{lcid:04X}{codepage:04X}\\{name}"
            )
            if value is not None:
                info["StringFileInfo"][lcid, codepage][name] = value

    return info


def get_pids():
    """
    Get PIDs of all running processes.

    Returns:
        list: List of PIDs.

    Raises:
        ImportError: If the psapi module is not available.
        get_windows_error: If an error occurs while enumerating processes.
    """
    if psapi is None:
        raise ImportError(
            "psapi module is not available. Please ensure it is installed and accessible."  # noqa: B950
        )

    pids_count = 1024
    while True:
        pids = (DWORD * pids_count)()
        pids_size = sizeof(pids)
        bytes = DWORD()
        if not psapi.EnumProcesses(byref(pids), pids_size, byref(bytes)):
            raise get_windows_error(ctypes.windll.kernel32.GetLastError())
        if bytes.value >= pids_size:
            pids_count *= 2
            continue
        count = bytes.value / (pids_size / pids_count)
        return [_f for _f in pids[:count] if _f]


def get_real_display_devices_info():
    """
    Return info for real (non-virtual) devices.

    Returns:
        list: List of monitor info.
    """
    # See Argyll source spectro/dispwin.c MonitorEnumProc, get_displays
    monitors = []
    for monitor in win32api.EnumDisplayMonitors(None, None):
        try:
            # Convert PyHANDLE to int using the .handle attribute
            hMonitor = monitor[0].handle
            moninfo = win32api.GetMonitorInfo(hMonitor)
        except pywintypes.error:
            pass
        else:
            if moninfo and not moninfo["Device"].startswith("\\\\.\\DISPLAYV"):
                monitors.append(moninfo)
    return monitors


def get_windows_error(errorcode):
    """
    Get a Windows error message.

    Args:
        errorcode (int): The error code.

    Returns:
        ctypes.WinError: The Windows error message.
    """
    return ctypes.WinError(errorcode)


def per_user_profiles_isenabled(display_no=0, devicekey=None):
    """
    Check if per user profiles is enabled under Vista/Windows 7.

    Args:
        display_no (int): The display number.
        devicekey (str): The device key.

    Returns:
        bool: True if per user profiles is enabled, False otherwise.

    Raises:
        WindowsError: If an error occurs while querying the registry.
    """
    if sys.getwindowsversion() < (6,):
        # Windows XP doesn't have per-user profiles
        return False
    if not devicekey:
        device = get_display_device(display_no)
        if device:
            devicekey = device.DeviceKey
    if devicekey:
        if USE_REGISTRY:
            with _get_icm_display_device_key(devicekey) as key:
                try:
                    return bool(winreg.QueryValueEx(key, "UsePerUserProfiles")[0])
                except WindowsError as exception:
                    if exception.args[0] == winerror.ERROR_FILE_NOT_FOUND:
                        return False
                    raise
        else:
            # Using ctypes - this leaks registry key handles internally in
            # WcsGetUsePerUserProfiles since Windows 10 1903
            mscms = _get_mscms_windll()
            pbool = ctypes.pointer(ctypes.c_bool())
            if not mscms or not mscms.WcsGetUsePerUserProfiles(
                str(devicekey), CLASS_MONITOR, pbool
            ):
                return
            return bool(pbool.contents)


def run_as_admin(
    cmd, args, close_process=True, async_=False, wait_for_idle=False, show=True
):
    """
    Run command with elevated privileges.

    This is a wrapper around ShellExecuteEx.

    Args:
        cmd (str): The command to run.
        args (list): The arguments for the command.
        close_process (bool): Whether to close the process after execution.
        async_ (bool): Whether to run the command asynchronously.
        wait_for_idle (bool): Whether to wait for the process to be idle.
        show (bool): Whether to show the command window.

    Returns:
        dict: A dictionary with hInstApp and hProcess members.
    """
    return shell_exec(cmd, args, "runas", close_process, async_, wait_for_idle, show)


def shell_exec(
    filename,
    args,
    operation="open",
    close_process=True,
    async_=False,
    wait_for_idle=False,
    show=True,
):
    """
    Run command.

    This is a wrapper around ShellExecuteEx.

    Args:
        filename (str): The filename to execute.
        args (list): The arguments for the command.
        operation (str): The operation to perform.
        close_process (bool): Whether to close the process after execution.
        async_ (bool): Whether to run the command asynchronously.
        wait_for_idle (bool): Whether to wait for the process to be idle.
        show (bool): Whether to show the command window.

    Returns:
        dict: A dictionary with hInstApp and hProcess members.
    """
    flags = SEE_MASK_FLAG_NO_UI
    if not close_process:
        flags |= SEE_MASK_NOCLOSEPROCESS
    if not async_:
        flags |= SEE_MASK_NOASYNC
    if wait_for_idle:
        flags |= SEE_MASK_WAITFORINPUTIDLE
    params = " ".join(quote_args(args))
    if show:
        show = win32con.SW_SHOWNORMAL
    else:
        show = win32con.SW_HIDE
    return win32com_shell.ShellExecuteEx(
        fMask=flags, lpVerb=operation, lpFile=filename, lpParameters=params, nShow=show
    )


def win_ver():
    """
    Get Windows version info.

    Returns:
        tuple: A tuple containing the product name, CSD version, release, and build.
    """
    csd = sys.getwindowsversion()[-1]
    # Use the registry to get product name, e.g. 'Windows 7 Ultimate'.
    # Not recommended, but we don't care.
    pname = "Windows"
    release = ""
    build = ""
    key = None
    sam = winreg.KEY_READ
    if platform.machine() == "AMD64":
        sam |= winreg.KEY_WOW64_64KEY
    try:
        key = winreg.OpenKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            0,
            sam,
        )
        pname = winreg.QueryValueEx(key, "ProductName")[0]
        build = f"Build {winreg.QueryValueEx(key, 'CurrentBuildNumber')[0]}"
        # Since Windows 10
        release = f"Version {winreg.QueryValueEx(key, 'ReleaseId')[0]}"
        build += f".{winreg.QueryValueEx(key, 'UBR')[0]}"
    except Exception:
        pass
    finally:
        if key:
            winreg.CloseKey(key)
    return pname, csd, release, build


USE_NTDLL_LDR = False


def _free_library(handle):
    if USE_NTDLL_LDR:
        fn = ctypes.windll.ntdll.LdrUnloadDll
    else:
        fn = _ctypes.FreeLibrary
    fn(handle)


class UnloadableWinDLL(object):
    """WinDLL wrapper that allows unloading."""

    def __init__(self, dllname):
        self.dllname = dllname
        self._windll = None
        self.load()

    def __getattr__(self, name):
        """
        Get an attribute from the loaded DLL.

        Args:
            name (str): The name of the attribute.

        Returns:
            The attribute from the loaded DLL.
        """
        self.load()
        return getattr(self._windll, name)

    def __bool__(self):
        """
        Check if the DLL is loaded.

        Returns:
            bool: True if the DLL is loaded, False otherwise.
        """
        self.load()
        return bool(self._windll)

    def load(self):
        """Load the DLL."""
        if not self._windll:
            if USE_NTDLL_LDR:
                mod = byref(UNICODE_STRING(len(self.dllname) * 2, 256, self.dllname))
                handle = wintypes.HANDLE()
                ctypes.windll.ntdll.LdrLoadDll(None, 0, mod, byref(handle))
                windll = ctypes.WinDLL(self.dllname, handle=handle.value)
            else:
                windll = ctypes.WinDLL(self.dllname)
            self._windll = windll

    def unload(self):
        """Unload the DLL."""
        if self._windll:
            handle = self._windll._handle
            self._windll = None
            _free_library(handle)


class MSCMS(UnloadableWinDLL):
    """MSCMS wrapper (optionally) allowing unloading."""

    def __init__(self, bootstrap_icm32=False):
        self._icm32_handle = None
        UnloadableWinDLL.__init__(self, "mscms.dll")
        if bootstrap_icm32:
            # Need to load & unload icm32 once before unloading of mscms
            # can work in every situation
            # (some calls to mscms methods pull in icm32,
            # if we haven't loaded/unloaded it before, we won't be able to unload then)
            self._icm32_handle = ctypes.WinDLL("icm32")._handle
            _free_library(self._icm32_handle)

    def load(self):
        """Load the MSCMS DLL."""
        mscms = self._windll
        UnloadableWinDLL.load(self)
        if self._windll is not mscms:
            mscms = self._windll
            if (
                mscms
            ):  # Ensure mscms is not None
                mscms.WcsGetDefaultColorProfileSize.restype = ctypes.c_bool
                mscms.WcsGetDefaultColorProfile.restype = ctypes.c_bool
                mscms.WcsAssociateColorProfileWithDevice.restype = ctypes.c_bool
                mscms.WcsDisassociateColorProfileFromDevice.restype = ctypes.c_bool

    def unload(self):
        """Unload the MSCMS DLL.

        Raises:
            WindowsError: If an error occurs while unloading the DLL.
        """
        if self._windll:
            if self._icm32_handle:
                # Need to free icm32 first, otherwise mscms won't unload
                try:
                    _free_library(self._icm32_handle)
                except WindowsError as exception:
                    if exception.args[0] != winerror.ERROR_MOD_NOT_FOUND:
                        raise
            UnloadableWinDLL.unload(self)


if __name__ == "__main__":
    if "calibration" in sys.argv[1:]:
        if "enable" in sys.argv[1:] or "disable" in sys.argv[1:]:
            enable_calibration_management(sys.argv[1:][-1] != "disable")
        print(calibration_management_isenabled())
    elif "per_user_profiles" in sys.argv[1:]:
        if "enable" in sys.argv[1:] or "disable" in sys.argv[1:]:
            enable_per_user_profiles(sys.argv[1:][-1] != "disable")
        print(per_user_profiles_isenabled())
