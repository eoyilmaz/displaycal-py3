"""Windows-specific display ICC profile get/set functions."""

from __future__ import annotations

import ctypes
import os
import sys
from typing import TYPE_CHECKING

from DisplayCAL.defaultpaths import ICCPROFILES
from DisplayCAL.icc_profile.constants import (
    COLOR_PROFILE_SUBTYPE,
    COLOR_PROFILE_TYPE,
    WCS_PROFILE_MANAGEMENT_SCOPE,
)

if sys.platform == "win32":
    import winreg

    try:
        import win32api  # noqa: F401  # availability checked via sys.modules below
        import win32gui
    except ImportError:
        pass

    from DisplayCAL import util_win
    from DisplayCAL.mscms import WCSManagerProxy

    # WCS only available under Vista and later
    mscms = None if sys.getwindowsversion() < (6,) else WCSManagerProxy()

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile


def _wcs_get_display_profile(
    devicekey: str,
    scope: int = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
    profile_type: int = COLOR_PROFILE_TYPE["ICC"],
    profile_subtype: int = COLOR_PROFILE_SUBTYPE["NONE"],
    profile_id: int = 0,
    path_only: bool = False,
    use_cache: bool = True,
) -> None | str | ICCProfile:
    """Get display profile using WCS API.

    Args:
        devicekey (str): The device key to query.
        scope (int, optional): The scope of the profile management.
        profile_type (int, optional): The type of the color profile.
        profile_subtype (int, optional): The subtype of the color profile.
        profile_id (int, optional): The ID of the color profile.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        use_cache (bool, optional): If True, use cached profile if available.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile

    prof = mscms.get_default_color_profile(
        scope, devicekey, profile_type, profile_subtype, profile_id
    )
    if prof:
        if path_only:
            return os.path.join(ICCPROFILES[0], prof)
        return ICCProfile(prof, use_cache=use_cache)
    return None


def _winreg_get_display_profile(
    monkey: list,
    current_user: bool = False,
    path_only: bool = False,
    use_cache: bool = True,
    advanced_color_active: bool | None = None,
) -> None | str | ICCProfile:
    """Get display profile from Windows registry.

    Windows keeps two separate association lists per display, ICMProfile for
    SDR and ICMProfileAC for Advanced Color (HDR or Auto Color Management),
    and the last entry of each list is that mode's default profile. Only the
    list matching the display's current mode is used, so the result doesn't
    depend on which registry value happened to be created first (issue #989).

    Args:
        monkey (list): Registry key path components for the display.
        current_user (bool): If True, use HKEY_CURRENT_USER, otherwise
            HKEY_LOCAL_MACHINE.
        path_only (bool): If True, return the profile path as a string,
            otherwise return an ICCProfile object.
        use_cache (bool): If True, use cached profile if available.
        advanced_color_active (bool | None): Whether the display is currently
            in Advanced Color (HDR) mode. If True, the ICMProfileAC default is
            used, falling back to ICMProfile if there is none. If False, only
            ICMProfile is used. None means unknown, in which case ICMProfile
            is preferred and ICMProfileAC is only used if there is no
            ICMProfile association.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile

    filenames_by_slot = _winreg_get_display_profiles_by_slot(monkey, current_user)
    sdr_filenames = filenames_by_slot["ICMProfile"]
    ac_filenames = filenames_by_slot["ICMProfileAC"]
    if advanced_color_active:
        filenames = ac_filenames or sdr_filenames
    elif advanced_color_active is False:
        filenames = sdr_filenames
    else:
        filenames = sdr_filenames or ac_filenames
    # last existing file in the list is active
    filename = filenames[-1] if filenames else None
    if not filename and not current_user:
        # fall back to sRGB
        filename = os.path.join(ICCPROFILES[0], "sRGB Color Space Profile.icm")
    if filename:
        if path_only:
            return os.path.join(ICCPROFILES[0], filename)
        return ICCProfile(filename, use_cache=use_cache)
    return None


def _winreg_get_display_profiles(
    monkey: list,
    current_user: bool = False,
    exclude_advanced_color: bool = False,
) -> list:
    """Get display profile filenames from Windows registry.

    Args:
        monkey (list): Registry key path components for the display.
        current_user (bool): If True, use HKEY_CURRENT_USER, otherwise
            HKEY_LOCAL_MACHINE.
        exclude_advanced_color (bool): If True, skip profiles stored under
            ICMProfileAC (the Windows HDR Calibration / Advanced Color profile
            slot).  Pass True when the display is not currently in HDR mode so
            the SDR profile is used instead.

    Returns:
        list: List of profile filenames.
    """
    filenames = []
    for name, slot_filenames in _winreg_get_display_profiles_by_slot(
        monkey, current_user
    ).items():
        if name == "ICMProfileAC" and exclude_advanced_color:
            continue
        filenames.extend(slot_filenames)
    return filenames


def _winreg_get_display_profiles_by_slot(
    monkey: list,
    current_user: bool = False,
) -> dict[str, list]:
    """Get display profile filenames from Windows registry, per slot.

    Args:
        monkey (list): Registry key path components for the display.
        current_user (bool): If True, use HKEY_CURRENT_USER, otherwise
            HKEY_LOCAL_MACHINE.

    Returns:
        dict[str, list]: The existing profile filenames associated in the
            "ICMProfile" (SDR) and "ICMProfileAC" (Advanced Color) slots, in
            registry enumeration order (the last entry of each slot is that
            slot's default profile). Keys are always present.
    """
    filenames_by_slot = {"ICMProfile": [], "ICMProfileAC": []}
    try:
        if current_user and sys.getwindowsversion() >= (6,):
            # Vista / Windows 7 ONLY
            # User has to place a check in 'use my settings for this device'
            # in the color management control panel at least once to cause
            # this key to be created, otherwise it won't exist
            subkey = "\\".join(
                [
                    "Software",
                    "Microsoft",
                    "Windows NT",
                    "CurrentVersion",
                    "ICM",
                    "ProfileAssociations",
                    "Display",
                    *monkey,
                ]
            )
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
        else:
            subkey = "\\".join(
                ["SYSTEM", "CurrentControlSet", "Control", "Class", *monkey]
            )
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
        numsubkeys, numvalues, mtime = winreg.QueryInfoKey(key)
        for i in range(numvalues):
            name, value, type_ = winreg.EnumValue(key, i)
            if name not in filenames_by_slot or not value:
                continue

            if type_ == winreg.REG_BINARY:
                # Win2k/XP
                # convert to list of strings
                value = value.decode("utf-16").split("\0")
            elif type_ == winreg.REG_MULTI_SZ:
                # Vista / Windows 7
                # nothing to be done, _winreg returns a list of strings
                pass
            if not isinstance(value, list):
                value = [value]
            while "" in value:
                value.remove("")
            filenames_by_slot[name].extend(value)
        winreg.CloseKey(key)
    except OSError as exception:
        if exception.args[0] == 2:
            # Key does not exist
            pass
        else:
            raise
    return {
        name: [
            filename
            for filename in filenames
            if os.path.isfile(os.path.join(ICCPROFILES[0], filename))
        ]
        for name, filenames in filenames_by_slot.items()
    }


def get_display_profile_windows(
    display_no: int = 0,
    path_only: bool = False,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
    use_registry: bool = True,
) -> None | str | ICCProfile:
    """Return ICC Profile for the given display under Windows.

    Args:
        display_no (int): The display number to query.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        devicekey (None | str, optional): The device key to query. If None, the
            active display device will be used.
        use_active_display_device (bool, optional): If True, use the active
            display device, otherwise use the first display device.
        use_registry (bool, optional): If True, use the Windows registry to
            get the display profile.

    Raises:
        ImportError: If pywin32 is not available.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile

    profile = None
    if "win32api" not in sys.modules:
        raise ImportError("pywin32 not available")
    gdi_device_name = None
    if not devicekey:
        # The ordering will work as long as Argyll continues using
        # EnumDisplayMonitors
        monitors = util_win.get_real_display_devices_info()
        moninfo = monitors[display_no]
        gdi_device_name = moninfo["Device"]
    if not mscms and not devicekey:
        # Via GetICMProfile. Sucks royally in a multi-monitor setup
        # where one monitor is disabled, because it'll always get
        # the profile of the first monitor regardless if that is the active
        # one or not. Yuck. Also, in this case it does not reflect runtime
        # changes to profile assignments. Double yuck.
        buflen = ctypes.c_ulong(260)
        dc = win32gui.CreateDC(moninfo["Device"], None, None)
        try:
            buf = ctypes.create_unicode_buffer(buflen.value)
            if ctypes.windll.gdi32.GetICMProfileW(
                dc,
                ctypes.byref(buflen),
                ctypes.byref(buf),  # WCHARs
            ):
                if path_only:
                    profile = buf.value
                else:
                    profile = ICCProfile(buf.value, use_cache=True)
        finally:
            win32gui.DeleteDC(dc)
    else:
        if devicekey:
            device = None
        elif use_active_display_device:
            # This would be the correct way. Unfortunately that is not
            # what other apps (or Windows itself) do.
            device = util_win.get_active_display_device(moninfo["Device"])
        else:
            # This is wrong, but it's what other apps use. Matches
            # GetICMProfile sucky behavior i.e. should return the same
            # profile, but atleast reflects runtime changes to profile
            # assignments.
            device = util_win.get_first_display_device(moninfo["Device"])
        if device:
            devicekey = device.DeviceKey
    if devicekey:
        if mscms:
            # Via WCS
            if util_win.per_user_profiles_isenabled(devicekey=devicekey):
                scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
            else:
                scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
            if not use_registry:
                # NOTE: WcsGetDefaultColorProfile causes the whole system
                # to hitch if the profile of the active display device is
                # queried. Windows bug?
                return _wcs_get_display_profile(
                    str(devicekey), scope, path_only=path_only
                )
        else:
            scope = None
            # Via registry
        monkey = devicekey.split("\\")[-2:]  # pun totally intended
        # Current user scope
        current_user = scope == WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        # Detect Advanced Color (HDR) state so we can skip the ICMProfileAC
        # entry when the display is in SDR mode (issue #627).
        if gdi_device_name is None:
            gdi_device_name = util_win.get_gdi_device_name_for_devicekey(devicekey)
        advanced_color_active = (
            util_win.is_advanced_color_enabled(gdi_device_name)
            if gdi_device_name
            else None
        )
        if current_user:
            profile = _winreg_get_display_profile(
                monkey,
                True,
                path_only=path_only,
                advanced_color_active=advanced_color_active,
            )
        else:
            # System scope
            profile = _winreg_get_display_profile(
                monkey,
                path_only=path_only,
                advanced_color_active=advanced_color_active,
            )

    return profile


def _wcs_set_display_profile(
    devicekey: str,
    profile_name: str,
    scope: int = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
) -> bool:
    """Set the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.

    * 0..65535 will get mapped to 0..65280, which is a Windows bug.

    Args:
        devicekey (str): The device key of the display.
        profile_name (str): The name of the profile to be set.
        scope (int): The scope of the profile management, either
            WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"] or
            WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"].

    Returns:
        bool: True if the profile was set successfully, False otherwise.
    """
    mscms.associate_color_profile_with_device(scope, profile_name, str(devicekey))
    profiles = mscms.get_device_color_profile_list(scope, str(devicekey))
    return profile_name in profiles


def _wcs_unset_display_profile(
    devicekey: str,
    profile_name: str,
    scope: int = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
) -> bool:
    """Unset the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.

    * 0..65535 will get mapped to 0..65280, which is a Windows bug.

    Args:
        devicekey (str): The device key of the display.
        profile_name (str): The name of the profile to be unset.
        scope (int): The scope of the profile management, either
            WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"] or
            WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"].

    Returns:
        bool: True if the profile was unset successfully, False otherwise.
    """
    mscms.disassociate_color_profile_from_device(scope, profile_name, str(devicekey))
    profiles = mscms.get_device_color_profile_list(scope, str(devicekey))
    return profile_name not in profiles


def set_display_profile(
    profile_name: str,
    display_no: int = 0,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
) -> bool:
    """Set the current default WCS color profile for the given device.

    Args:
        profile_name (str): The name of the profile to be set.
        display_no (int): The display number to set the profile for.
        devicekey (str): The device key of the display.
        use_active_display_device (bool): Whether to use the active display
            device.

    Returns:
        bool: True if the profile was set successfully, False otherwise.
    """
    # Currently only implemented for Windows.
    # The profile to be assigned has to be already installed!
    if not devicekey:
        device = util_win.get_display_device(display_no, use_active_display_device)
        if not device:
            return False
        devicekey = device.DeviceKey
    if mscms:
        if util_win.per_user_profiles_isenabled(devicekey=devicekey):
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        else:
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
        return _wcs_set_display_profile(str(devicekey), profile_name, scope)
    # TODO: Implement for XP
    return False


def unset_display_profile(
    profile_name: str,
    display_no: int = 0,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
) -> bool:
    """Unset the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.
    * 0..65535 will get mapped to 0..65280, which is a Windows bug.

    Args:
        profile_name (str): The name of the profile to be unset.
        display_no (int, optional): The display number to unset the profile
            for. Defaults to 0.
        devicekey (None | str): The device key of the display. Defatults to
            None, which means the active display device will be used.
        use_active_display_device (bool, optional): Whether to use the active
            display device. Defaults to True.

    Returns:
        bool: True if the profile was unset successfully, False otherwise.
    """
    # Currently only implemented for Windows.
    # The profile to be unassigned has to be already installed!
    if not devicekey:
        device = util_win.get_display_device(display_no, use_active_display_device)
        if not device:
            return False
        devicekey = device.DeviceKey
    if mscms:
        if util_win.per_user_profiles_isenabled(devicekey=devicekey):
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        else:
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
        return _wcs_unset_display_profile(str(devicekey), profile_name, scope)
    # TODO: Implement for XP
    return False
