"""Wrapper for WCS API calls."""

from __future__ import annotations

import ctypes
from ctypes import (
    POINTER,
    WINFUNCTYPE,
    Structure,
    WinError,
    c_wchar_p,
    create_unicode_buffer,
    wstring_at,
)
from ctypes.wintypes import BOOL, DWORD, LPWSTR
from typing import Any, Callable, Self

from DisplayCAL.mscms_types import (
    COLORPROFILESUBTYPE,
    COLORPROFILETYPE,
    WCS_PROF_SCOPE,
    dwDeviceClass,
    dwFieldsUsed,
)

# mscms calls used:
#  + WcsAssociateColorProfileWithDevice
#  + WcsDisassociateColorProfileFromDevice
#  + WcsEnumColorProfiles
#  + WcsEnumColorProfilesSize
#  + WcsGetCalibrationManagementState
#  + WcsSetCalibrationManagementState
#  + WcsGetDefaultColorProfile (leaks)
#  + WcsGetDefaultColorProfileSize (leaks)
#  + WcsGetUsePerUserProfiles (leaks)
#  + WcsSetUsePerUserProfiles

dwResolutionArray = DWORD * 2  # noqa: N816
dwAttributesArray = DWORD * 2  # noqa: N816
WCS_PROF_SCOPE_t = DWORD
COLORPROFILETYPE_t = DWORD
COLORPROFILESUBTYPE_t = DWORD
PCWSTR = c_wchar_p

ENUM_TYPE_VERSION = DWORD(0x0300)  # Profile enumeration marker
WIN_ERRNO_SUCCESS = 0
WIN_ERRNO_PROFILE_NOT_ASSOCIATED = 2015


class ENUMTYPEW(Structure):
    """The ENUMTYPEW structure specifies the criteria for enumerating color profiles."""

    _fields_ = [
        ("dwSize", DWORD),  # size of structure
        ("dwVersion", DWORD),  # should be equal to ENUM_TYPE_VERSION
        (
            "dwFields",
            DWORD,
        ),  # indicates which fields in this structure are being used.
        # Can be set to any combination of the dwFieldsUsed enum.
        ("pDeviceName", LPWSTR),
        ("dwMediaType", DWORD),
        ("dwDitheringMode", DWORD),
        ("dwResolution", dwResolutionArray),
        ("dwCMMType", DWORD),
        ("dwClass", DWORD),
        ("dwDataColorSpace", DWORD),
        ("dwConnectionSpace", DWORD),
        ("dwSignature", DWORD),
        ("dwPlatform", DWORD),
        ("dwProfileFlags", DWORD),
        ("dwManufacturer", DWORD),
        ("dwModel", DWORD),
        ("dwAttributes", dwAttributesArray),
        ("dwRenderingIntent", DWORD),
        ("dwCreator", DWORD),
        ("dwDeviceClass", DWORD),
    ]

    def __init__(self) -> None:
        self.dwSize = ctypes.sizeof(ENUMTYPEW)
        self.dwVersion = ENUM_TYPE_VERSION

    @classmethod
    def create_monitor_profile_filter(
        cls, device_key: str, device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR
    ) -> Self:
        """Create an ENUMTYPEW structure for monitor profile filtering.

        This is used for profile enumeration for a monitor device.

        Args:
            device_key (str): Device key of the monitor device for which to
                filter.
            device_class (dwDeviceClass, optional): The class of the device.
                Defaults to dwDeviceClass.CLASS_MONITOR.

        Returns:
            ENUMTYPEW: An initialized ENUMTYPEW structure for monitor profile
                filtering.
        """
        enum_desc = cls()
        enum_desc.dwDeviceClass = device_class
        enum_desc.pDeviceName = device_key
        enum_desc.dwFields = dwFieldsUsed.ET_DEVICECLASS | dwFieldsUsed.ET_DEVICENAME
        return enum_desc


def _errcheck_simple_bool(result: Any, func: Callable[..., Any], args: Any) -> Any:  # noqa: ANN401
    if not result:
        raise WinError()
    return result


def _errcheck_args_ret(result: Any, func: Callable[..., Any], args: Any) -> Any:  # noqa: ANN401
    errno = ctypes.GetLastError()
    if not result and errno != WIN_ERRNO_SUCCESS:
        raise WinError(errno)
    return args


def _wrap_wcsAssociateColorProfileWithDevice() -> Callable[..., Any]:  # noqa: ANN401, N802
    proto = WINFUNCTYPE(BOOL, WCS_PROF_SCOPE_t, LPWSTR, LPWSTR)
    paramflags = (
        (1, "scope"),
        (1, "pProfileName"),
        (1, "pDeviceName"),
    )

    associate_color_profile_with_device = proto(
        ("WcsAssociateColorProfileWithDevice", ctypes.windll.mscms),
        paramflags,
    )
    associate_color_profile_with_device.errcheck = _errcheck_simple_bool
    return associate_color_profile_with_device


def _wrap_wcsDisassociateColorProfileFromDevice() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(BOOL, WCS_PROF_SCOPE_t, LPWSTR, LPWSTR)
    paramflags = (
        (1, "scope"),
        (1, "pProfileName"),
        (1, "pDeviceName"),
    )
    disassociate_color_profile_from_device = proto(
        ("WcsDisassociateColorProfileFromDevice", ctypes.windll.mscms),
        paramflags,
    )
    disassociate_color_profile_from_device.errcheck = _errcheck_simple_bool
    return disassociate_color_profile_from_device


def _wrap_wcsEnumColorProfiles() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(
        BOOL, WCS_PROF_SCOPE_t, POINTER(ENUMTYPEW), LPWSTR, DWORD, POINTER(DWORD)
    )
    paramflags = (
        (1, "scope"),
        (1, "pEnumRecord"),
        (3, "pBuffer"),
        (1, "dwSize"),
        (2, "pnProfiles", DWORD(0)),
    )

    enum_color_profiles = proto(
        ("WcsEnumColorProfiles", ctypes.windll.mscms), paramflags
    )
    enum_color_profiles.errcheck = _errcheck_args_ret
    return enum_color_profiles


def _wrap_wcsEnumColorProfilesSize() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(BOOL, WCS_PROF_SCOPE_t, POINTER(ENUMTYPEW), POINTER(DWORD))
    paramflags = (
        (1, "scope"),
        (1, "pEnumRecord"),
        (2, "pdwSize", DWORD(0)),
    )
    get_enum_color_profiles_size = proto(
        ("WcsEnumColorProfilesSize", ctypes.windll.mscms), paramflags
    )
    get_enum_color_profiles_size.errcheck = _errcheck_args_ret
    return get_enum_color_profiles_size


def _wrap_wcsGetCalibrationManagementState() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(BOOL, POINTER(BOOL))
    paramflags = ((2, "pbIsEnabled", BOOL(False)),)
    get_calibration_management_state = proto(
        ("WcsGetCalibrationManagementState", ctypes.windll.mscms),
        paramflags,
    )
    get_calibration_management_state.errcheck = _errcheck_args_ret
    return get_calibration_management_state


def _wrap_wcsSetCalibrationManagementState() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(BOOL, BOOL)
    paramflags = ((1, "pbIsEnabled"),)
    set_calibration_management_state = proto(
        ("WcsSetCalibrationManagementState", ctypes.windll.mscms),
        paramflags,
    )
    set_calibration_management_state.errcheck = _errcheck_simple_bool
    return set_calibration_management_state


def _wrap_wcsGetDefaultColorProfile() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(
        BOOL,
        WCS_PROF_SCOPE_t,
        PCWSTR,
        COLORPROFILETYPE_t,
        COLORPROFILESUBTYPE_t,
        DWORD,
        DWORD,
        LPWSTR,
    )
    paramflags = (
        (1, "scope"),
        (1, "pDeviceName"),
        (1, "cptColorProfileType"),
        (1, "cpstColorProfileSubType"),
        (1, "dwProfileID"),
        (1, "cbProfileName"),
        (3, "pProfileName"),
    )
    get_default_color_profile = proto(
        ("WcsGetDefaultColorProfile", ctypes.windll.mscms), paramflags
    )
    get_default_color_profile.errcheck = _errcheck_args_ret
    return get_default_color_profile


def _wrap_wcsGetDefaultColorProfileSize() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(
        BOOL,
        WCS_PROF_SCOPE_t,
        PCWSTR,
        COLORPROFILETYPE_t,
        COLORPROFILESUBTYPE_t,
        DWORD,
        POINTER(DWORD),
    )
    paramflags = (
        (1, "scope"),
        (1, "pDeviceName"),
        (1, "cptColorProfileType"),
        (1, "cpstColorProfileSubType"),
        (1, "dwProfileID"),
        (2, "pcbProfileName", DWORD(0)),
    )
    get_default_color_profile_size = proto(
        ("WcsGetDefaultColorProfileSize", ctypes.windll.mscms),
        paramflags,
    )
    get_default_color_profile_size.errcheck = _errcheck_args_ret
    return get_default_color_profile_size


def _wrap_wcsSetDefaultColorProfile() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(
        BOOL,
        WCS_PROF_SCOPE_t,
        PCWSTR,
        COLORPROFILETYPE_t,
        COLORPROFILESUBTYPE_t,
        DWORD,
        LPWSTR,
    )
    paramflags = (
        (1, "scope"),
        (1, "pDeviceName"),
        (1, "cptColorProfileType"),
        (1, "cpstColorProfileSubType"),
        (1, "dwProfileID"),
        (1, "pProfileName"),
    )
    set_default_color_profile = proto(
        ("WcsSetDefaultColorProfile", ctypes.windll.mscms), paramflags
    )
    set_default_color_profile.errcheck = _errcheck_simple_bool
    return set_default_color_profile


def _wrap_wcsGetUsePerUserProfiles() -> Callable[..., Any]:  # noqa: N802
    proto = WINFUNCTYPE(BOOL, LPWSTR, DWORD, POINTER(BOOL))
    paramflags = (
        (1, "pDeviceName"),
        (1, "dwDeviceClass"),
        (2, "pUsePerUserProfiles", BOOL(False)),
    )
    get_use_per_user_profiles = proto(
        ("WcsGetUsePerUserProfiles", ctypes.windll.mscms),
        paramflags,
    )
    get_use_per_user_profiles.errcheck = _errcheck_args_ret
    return get_use_per_user_profiles


def _wrap_wcsSetUsePerUserProfiles() -> Callable[..., Any]:  # noqa: N802
    set_use_per_user_proto = WINFUNCTYPE(BOOL, LPWSTR, DWORD, BOOL)
    set_use_per_user_paramflags = (
        (1, "pDeviceName"),
        (1, "dwDeviceClass"),
        (1, "pUsePerUserProfiles"),
    )
    set_use_per_user_profiles = set_use_per_user_proto(
        ("WcsSetUsePerUserProfiles", ctypes.windll.mscms),
        set_use_per_user_paramflags,
    )
    set_use_per_user_profiles.errcheck = _errcheck_simple_bool
    return set_use_per_user_profiles


class WCS:
    """Wrapper for WCS API calls."""

    def __init__(self) -> None:
        self._wcsAssociateColorProfileWithDevice = (
            _wrap_wcsAssociateColorProfileWithDevice()
        )
        self._wcsDisassociateColorProfileFromDevice = (
            _wrap_wcsDisassociateColorProfileFromDevice()
        )
        self._wcsEnumColorProfiles = _wrap_wcsEnumColorProfiles()
        self._wcsEnumColorProfilesSize = _wrap_wcsEnumColorProfilesSize()
        self._wcsGetCalibrationManagementState = (
            _wrap_wcsGetCalibrationManagementState()
        )
        self._wcsSetCalibrationManagementState = (
            _wrap_wcsSetCalibrationManagementState()
        )
        self._wcsGetDefaultColorProfile = _wrap_wcsGetDefaultColorProfile()
        self._wcsGetDefaultColorProfileSize = _wrap_wcsGetDefaultColorProfileSize()
        self._wcsSetDefaultColorProfile = _wrap_wcsSetDefaultColorProfile()
        self._wcsGetUsePerUserProfiles = _wrap_wcsGetUsePerUserProfiles()
        self._wcsSetUsePerUserProfiles = _wrap_wcsSetUsePerUserProfiles()

    def AssociateColorProfileWithDevice(  # noqa: N802
        self, scope: WCS_PROF_SCOPE, profile_name: str, device_key: str
    ) -> None:
        """Associate a specified WCS color profile with a specified device.

        This API does not support "advanced color" profiles for HDR monitors

        Note: this API makes the added profile also be the default one

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            profile_name (str): File name of the profile to associate.
            device_key (str): Device key of the device with which to
                associate the profile.

        Raises:
            OSError: If a Win API error occurs.
        """
        self._wcsAssociateColorProfileWithDevice(scope, profile_name, device_key)

    def DisassociateColorProfileFromDevice(  # noqa: N802
        self, scope: WCS_PROF_SCOPE, profile_name: str, device_key: str
    ) -> None:
        """Disassociate a specified WCS color profile from a specified device.

        This API does not support "advanced color" profiles for HDR monitors.

        Note: very unreliable due to quirks, the actual result should be
        double-checked with profile listing

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            profile_name (str): File name of the profile to disassociate.
            device_key (str): Device key of the device from which to
                disassociate the profile.

        Raises:
            OSError: If a Win API error occurs (apart from the ones caught
                during handling its quirks).
        """
        try:
            self._wcsDisassociateColorProfileFromDevice(scope, profile_name, device_key)
        except OSError as e:
            # quirks: very very quirky: either returns error with errno success
            # or errno profile not associated with device. Why? Because Windows,
            # that's why.
            if e.winerror not in (WIN_ERRNO_SUCCESS, WIN_ERRNO_PROFILE_NOT_ASSOCIATED):
                raise

    def EnumColorProfiles(  # noqa: N802
        self, scope: WCS_PROF_SCOPE, enum_record: ENUMTYPEW, prof_size: int
    ) -> list[str]:
        """Enumerate color profiles associated with any device, in the specified scope.

        This API does not support "advanced color" profiles for HDR monitors

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            enum_record (ENUMTYPEW): Structure specifying the enumeration
                criteria.
            prof_size (int): Size, in bytes, of the buffer that is needed to
                enumerate color profiles.

        Raises:
            ValueError: On parsing errors.
            OSError: If a Win API error occurs.

        Returns:
            list[str]: Array of profile names.
        """
        wchar_size = ctypes.sizeof(ctypes.c_wchar)
        char_count = max(1, (prof_size + wchar_size - 1) // wchar_size)
        buf = create_unicode_buffer(char_count)
        profiles, p_num = self._wcsEnumColorProfiles(scope, enum_record, buf, prof_size)
        if p_num == 0:
            return []
        prof_arr = wstring_at(profiles, char_count).strip("\x00").split("\x00")
        if len(prof_arr) != p_num:
            raise ValueError(
                "Parsing error: profile number mismatch: "
                f"reported {p_num} != {len(prof_arr)} got"
            )
        return prof_arr

    def EnumColorProfilesSize(  # noqa: N802
        self, scope: WCS_PROF_SCOPE, enum_record: ENUMTYPEW
    ) -> int:
        """Get the size in bytes of the buffer needed to enumerate color profiles.

        This API does not support "advanced color" profiles for HDR monitors

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            enum_record (ENUMTYPEW): Structure specifying the enumeration criteria.

        Raises:
            OSError: In case of Win API errors.

        Returns:
            int: Size, in bytes, of the buffer that is needed to enumerate
                color profiles.
        """
        return self._wcsEnumColorProfilesSize(scope, enum_record)

    def GetCalibrationManagementState(self) -> bool:  # noqa: N802
        """Check if system management of the display calibration state is enabled.

        Raises:
            OSError: If a Win API error occurs.

        Returns:
            bool: True if system management of the display calibration state is
                enabled; otherwise False.
        """
        return bool(self._wcsGetCalibrationManagementState())

    def SetCalibrationManagementState(self, new_state: bool) -> None:  # noqa: N802
        """Enable or disable system management of the display calibration state.

        Args:
            new_state (bool): True to enable system management of the display
                calibration state. False to disable system management of the
                display calibration state.

        Raises:
            OSError: If a Win API error occurs.
        """
        self._wcsSetCalibrationManagementState(new_state)

    def GetDefaultColorProfile(  # noqa: N802
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        prof_size: int,
        c_prof_type: COLORPROFILETYPE = COLORPROFILETYPE.CPT_ICC,
        c_prof_subtype: COLORPROFILESUBTYPE = COLORPROFILESUBTYPE.CPST_NONE,
        profile_id: int = 0,
    ) -> str:
        """Get the default color profile for a device.

        This API does not support "advanced color" profiles for HDR monitors.
        Note: if HDR enabled on a device causes OSError

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            device_key (str): Device key of the device for which the default
                color profile is obtained. If None, a device-independent
                default profile is obtained.
            prof_size (int): Size, in bytes, of the buffer that is sufficient
                to contain the profile name.
            c_prof_type (COLORPROFILETYPE, optional): Value specifying the
                color profile type. Defaults to COLORPROFILETYPE.CPT_ICC.
            c_prof_subtype (COLORPROFILESUBTYPE, optional): Value specifying
                the color profile subtype. Defaults to
                COLORPROFILESUBTYPE.CPST_NONE.
            profile_id (int, optional): ID of the color space that the color
                profile represents. Defaults to 0.

        Raises:
            OSError: In case of Win API errors.

        Returns:
            str: The name of the default color profile for a device.
        """
        wchar_size = ctypes.sizeof(ctypes.c_wchar)
        char_count = max(1, (prof_size + wchar_size - 1) // wchar_size)
        buf = create_unicode_buffer(char_count)
        self._wcsGetDefaultColorProfile(
            scope, device_key, c_prof_type, c_prof_subtype, profile_id, prof_size, buf
        )
        return buf.value

    def GetDefaultColorProfileSize(  # noqa: N802
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        c_prof_type: COLORPROFILETYPE = COLORPROFILETYPE.CPT_ICC,
        c_prof_subtype: COLORPROFILESUBTYPE = COLORPROFILESUBTYPE.CPST_NONE,
        profile_id: int = 0,
    ) -> int:
        """Get the size in bytes of the default color profile name for a device.

        This API does not support "advanced color" profiles for HDR monitors.
        Note: if HDR enabled on a device returns 0.

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            device_key (str): Device key of the device for which the default
                color profile is obtained. If None, a device-independent
                default profile is obtained.
            c_prof_type (COLORPROFILETYPE, optional): Value specifying the
                color profile type. Defaults to COLORPROFILETYPE.CPT_ICC.
            c_prof_subtype (COLORPROFILESUBTYPE, optional): Value specifying
                the color profile subtype. Defaults to COLORPROFILESUBTYPE.CPST_NONE.
            profile_id (int, optional): ID of the color space that the color
                profile represents. Defaults to 0.

        Raises:
            OSError: If a Win API error occurs.

        Returns:
            int: size, in bytes, of the buffer that is sufficient to contain
                profile name.
        """
        return self._wcsGetDefaultColorProfileSize(
            scope, device_key, c_prof_type, c_prof_subtype, profile_id
        )

    def SetDefaultColorProfile(  # noqa: N802
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        profile_name: str,
        c_prof_type: COLORPROFILETYPE = COLORPROFILETYPE.CPT_ICC,
        c_prof_subtype: COLORPROFILESUBTYPE = COLORPROFILESUBTYPE.CPST_NONE,
        profile_id: int = 0,
    ) -> None:
        """Set the default color profile for the specified device.

        This API does not support "advanced color" profiles for HDR monitors.

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            device_key (str): Device key of the device for which the default
                color profile is to be set. If None, a device-independent
                default profile is set.
            profile_name (str): File name of the profile.
            c_prof_type (COLORPROFILETYPE, optional): Value specifying the
                color profile type. Defaults to COLORPROFILETYPE.CPT_ICC.
            c_prof_subtype (COLORPROFILESUBTYPE, optional): Value specifying
                the color profile subtype. Defaults to
                COLORPROFILESUBTYPE.CPST_NONE.
            profile_id (int, optional): ID of the color space that the color
                profile represents. Defaults to 0.

        Raises:
            OSError: If a Win API error occurs.
        """
        self._wcsSetDefaultColorProfile(
            scope, device_key, c_prof_type, c_prof_subtype, profile_id, profile_name
        )

    def GetUsePerUserProfiles(  # noqa: N802
        self, device_key: str, device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR
    ) -> bool:
        """Determine if per-user profile association is enabled for the device.

        Args:
            device_key (str): Device key of the device.
            device_class (dwDeviceClass, optional): The class of the device.
                Defaults to dwDeviceClass.CLASS_MONITOR.

        Raises:
            OSError: If a Win API error occurs.

        Returns:
            bool: True if the user chose to use a per-user profile association
                list for the specified device; otherwise False
        """
        return bool(self._wcsGetUsePerUserProfiles(device_key, device_class))

    def SetUsePerUserProfiles(  # noqa: N802
        self,
        device_key: str,
        new_state: bool,
        device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR,
    ) -> None:
        """Enable or disable per-user profile association for the specified device.

        Args:
            device_key (str): Device key of the device.
            new_state (bool): True if the user wants to use a per-user profile
                association list for the specified device; otherwise False.
            device_class (dwDeviceClass, optional): The class of the device.
                Defaults to dwDeviceClass.CLASS_MONITOR.

        Raises:
            OSError: If a Win API error occurs.
        """
        self._wcsSetUsePerUserProfiles(device_key, device_class, new_state)

    def getDeviceColorProfileList(  # noqa: N802
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR,
    ) -> list[str]:
        """Higher abstraction level function to get color profile list for a device.

        Also dodges the issue with serialization of some ctypes structures in
        multiprocess context.

        Args:
            scope (WCS_PROF_SCOPE): The scope of this profile management
                operation, which could be system-wide or for the current user.
            device_key (str): Device key of the device.
            device_class (dwDeviceClass, optional): The class of the device.
                Defaults to dwDeviceClass.CLASS_MONITOR.

        Raises:
            OSError: If a Win API error occurs.
            ValueError: If a parsing error occurs.

        Returns:
            list[str]: array of color profile names
        """
        enum_record = ENUMTYPEW.create_monitor_profile_filter(device_key)
        size = self.EnumColorProfilesSize(scope, enum_record)
        return self.EnumColorProfiles(scope, enum_record, size)
