"""macOS-specific display ICC profile get function."""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
from typing import TYPE_CHECKING

from DisplayCAL.icc_profile.constants import FS_ENC
from DisplayCAL.util_list import intlist

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile


def colorsync_profile_path(display_no: int) -> None | str:
    """Return the file of a display's current profile, as ColorSync has it.

    Displays are numbered in ``CGGetActiveDisplayList`` order, which is the
    order ArgyllCMS lists them in on macOS.

    Args:
        display_no: Zero-based display number.

    Returns:
        The profile's path, None if unknown (no such display, a profile
        without a file, or the frameworks not loadable).
    """
    try:
        graphics = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        colorsync = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ColorSync"))
        foundation = ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("CoreFoundation")
        )
    except (OSError, TypeError):
        return None
    uint32 = ctypes.c_uint32
    graphics.CGGetActiveDisplayList.argtypes = [
        uint32,
        ctypes.POINTER(uint32),
        ctypes.POINTER(uint32),
    ]
    ids = (uint32 * 32)()
    count = uint32()
    if graphics.CGGetActiveDisplayList(32, ids, ctypes.byref(count)) != 0:
        return None
    if not 0 <= display_no < count.value:
        return None
    colorsync.ColorSyncProfileCreateWithDisplayID.restype = ctypes.c_void_p
    colorsync.ColorSyncProfileCreateWithDisplayID.argtypes = [uint32]
    colorsync.ColorSyncProfileGetURL.restype = ctypes.c_void_p
    colorsync.ColorSyncProfileGetURL.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    foundation.CFURLGetFileSystemRepresentation.restype = ctypes.c_bool
    foundation.CFURLGetFileSystemRepresentation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_char_p,
        ctypes.c_long,
    ]
    foundation.CFRelease.argtypes = [ctypes.c_void_p]
    profile = colorsync.ColorSyncProfileCreateWithDisplayID(ids[display_no])
    if not profile:
        return None
    try:
        url = colorsync.ColorSyncProfileGetURL(profile, None)  # not owned
        buffer = ctypes.create_string_buffer(4096)
        if not url or not foundation.CFURLGetFileSystemRepresentation(
            url, True, buffer, len(buffer)
        ):
            return None
        return buffer.value.decode(FS_ENC)
    finally:
        foundation.CFRelease(profile)


def get_display_profile_macos(
    display_no: int = 0,
    path_only: bool = False,
) -> None | str | ICCProfile:
    """Return ICC Profile for the given display under macOS.

    Asks ColorSync first. AppleScript's Image Events, the older way, no
    longer answers on macOS 15 ("Can't get display profile", -1728).

    Args:
        display_no (int, optional): The display number to query. Defaults to 0.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.

    Raises:
        OSError: If there is an error executing the AppleScript command.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL import util_mac

    filename = colorsync_profile_path(display_no)
    if filename:
        return filename if path_only else ICCProfile(filename, use_cache=True)

    if intlist(platform.mac_ver()[0].split(".")) >= [10, 6]:
        options = ["Image Events"]
    else:
        options = ["ColorSyncScripting"]

    profile = None
    for option in options:
        # applescript: one-based index
        applescript = [
            f'tell app "{option}"',
            "set displayProfile to location of display profile of "
            f"display {int(display_no + 1):d}",
            "return POSIX path of displayProfile",
            "end tell",
        ]
        retcode, output, errors = util_mac.osascript(applescript)
        if retcode == 0 and output.strip():
            filename = output.strip(b"\n").decode(FS_ENC)
            profile = filename if path_only else ICCProfile(filename, use_cache=True)
        elif errors.strip():
            raise OSError(errors.strip())

    return profile
