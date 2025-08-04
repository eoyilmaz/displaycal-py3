import ctypes

from ctypes import c_wchar_p
from ctypes import create_unicode_buffer
from ctypes import POINTER
from ctypes import Structure
from ctypes import WinError
from ctypes import WINFUNCTYPE
from ctypes import wstring_at
from ctypes.wintypes import BOOL
from ctypes.wintypes import DWORD
from ctypes.wintypes import LPWSTR

from enum import auto
from enum import IntEnum
from enum import IntFlag

from typing import Any
from typing import Callable
from typing import List
from typing_extensions import Self

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

dwResolutionArray = DWORD * 2
dwAttributesArray = DWORD * 2
WCS_PROF_SCOPE_t = DWORD
COLORPROFILETYPE_t = DWORD
COLORPROFILESUBTYPE_t = DWORD
PCWSTR = c_wchar_p

ENUM_TYPE_VERSION = DWORD(0x0300)  # Profile enumeration marker
WIN_ERRNO_SUCCESS = 0


class dwDeviceClass(IntEnum):
    """Available device classes to be used in the dwDeviceClass field"""

    CLASS_SCANNER = int.from_bytes(b"scnr", byteorder="big")
    CLASS_MONITOR = int.from_bytes(b"mntr", byteorder="big")
    CLASS_PRINTER = int.from_bytes(b"prtr", byteorder="big")


class dwFieldsUsed(IntFlag):
    """Available fields to be used in the ENUMTYPEW structure"""

    ET_DEVICENAME = 0x00000001
    ET_MEDIATYPE = 0x00000002
    ET_DITHERMODE = 0x00000004
    ET_RESOLUTION = 0x00000008
    ET_CMMTYPE = 0x00000010
    ET_CLASS = 0x00000020
    ET_DATACOLORSPACE = 0x00000040
    ET_CONNECTIONSPACE = 0x00000080
    ET_SIGNATURE = 0x00000100
    ET_PLATFORM = 0x00000200
    ET_PROFILEFLAGS = 0x00000400
    ET_MANUFACTURER = 0x00000800
    ET_MODEL = 0x00001000
    ET_ATTRIBUTES = 0x00002000
    ET_RENDERINGINTENT = 0x00004000
    ET_CREATOR = 0x00008000
    ET_DEVICECLASS = 0x00010000


class ENUMTYPEW(Structure):
    _fields_ = [
        ("dwSize", DWORD),  # size of structure
        ("dwVersion", DWORD),  # should be equal to ENUM_TYPE_VERSION
        (
            "dwFields",
            DWORD,
        ),  # indicates which fields in this structure are being used. Can be set to any combination of the dwFieldsUsed enum
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

    def __init__(self):
        self.dwSize = ctypes.sizeof(ENUMTYPEW)
        self.dwVersion = ENUM_TYPE_VERSION

    @classmethod
    def create_monitor_profile_filter(
        cls, device_key: str, device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR
    ) -> Self:
        enumDesc = cls()
        enumDesc.dwDeviceClass = device_class
        enumDesc.pDeviceName = device_key
        enumDesc.dwFields = dwFieldsUsed.ET_DEVICECLASS | dwFieldsUsed.ET_DEVICENAME
        return enumDesc


class WCS_PROF_SCOPE(IntEnum):
    SYSTEM_WIDE = 0
    CURRENT_USER = 1


class COLORPROFILETYPE(IntEnum):
    CPT_ICC = 0
    CPT_DMP = auto()
    CPT_CAMP = auto()
    CPT_GMMP = auto()


class COLORPROFILESUBTYPE(IntEnum):
    # intent
    CPST_PERCEPTUAL = 0
    CPST_RELATIVE_COLORIMETRIC = auto()
    CPST_SATURATION = auto()
    CPST_ABSOLUTE_COLORIMETRIC = auto()
    # working space
    CPST_NONE = auto()  # makes the API deduct profile subtype from the profile itself
    CPST_RGB_WORKING_SPACE = auto()
    CPST_CUSTOM_WORKING_SPACE = auto()
    CPST_STANDARD_DISPLAY_COLOR_MODE = auto()
    CPST_EXTENDED_DISPLAY_COLOR_MODE = auto()


def _errcheck_simple_bool(result: Any, func: Callable[..., Any], args: Any):
    if not result:
        raise WinError()
    return result


def _errcheck_args_ret(result: Any, func: Callable[..., Any], args: Any):
    errno = ctypes.GetLastError()
    if not result and errno != WIN_ERRNO_SUCCESS:
        raise WinError(errno)
    return args


def _wrap_wcsAssociateColorProfileWithDevice():
    proto = WINFUNCTYPE(BOOL, WCS_PROF_SCOPE_t, LPWSTR, LPWSTR)
    paramflags = (
        (1, "scope"),
        (1, "pProfileName"),
        (1, "pDeviceName"),
    )

    AssociateColorProfileWithDevice = proto(
        ("WcsAssociateColorProfileWithDevice", ctypes.windll.mscms),
        paramflags,
    )
    AssociateColorProfileWithDevice.errcheck = _errcheck_simple_bool
    return AssociateColorProfileWithDevice


def _wrap_wcsDisassociateColorProfileFromDevice():
    proto = WINFUNCTYPE(BOOL, WCS_PROF_SCOPE_t, LPWSTR, LPWSTR)
    paramflags = (
        (1, "scope"),
        (1, "pProfileName"),
        (1, "pDeviceName"),
    )
    DisassociateColorProfileFromDevice = proto(
        ("WcsDisassociateColorProfileFromDevice", ctypes.windll.mscms),
        paramflags,
    )
    DisassociateColorProfileFromDevice.errcheck = _errcheck_simple_bool
    return DisassociateColorProfileFromDevice


def _wrap_wcsEnumColorProfiles():
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

    EnumColorProfiles = proto(("WcsEnumColorProfiles", ctypes.windll.mscms), paramflags)
    EnumColorProfiles.errcheck = _errcheck_args_ret
    return EnumColorProfiles


def _wrap_wcsEnumColorProfilesSize():
    proto = WINFUNCTYPE(BOOL, WCS_PROF_SCOPE_t, POINTER(ENUMTYPEW), POINTER(DWORD))
    paramflags = (
        (1, "scope"),
        (1, "pEnumRecord"),
        (2, "pdwSize", DWORD(0)),
    )
    EnumColorProfilesSize = proto(
        ("WcsEnumColorProfilesSize", ctypes.windll.mscms), paramflags
    )
    EnumColorProfilesSize.errcheck = _errcheck_args_ret
    return EnumColorProfilesSize


def _wrap_wcsGetCalibrationManagementState():
    proto = WINFUNCTYPE(BOOL, POINTER(BOOL))
    paramflags = ((2, "pbIsEnabled", BOOL(False)),)
    GetCalibrationManagementState = proto(
        ("WcsGetCalibrationManagementState", ctypes.windll.mscms),
        paramflags,
    )
    GetCalibrationManagementState.errcheck = _errcheck_args_ret
    return GetCalibrationManagementState


def _wrap_wcsSetCalibrationManagementState():
    proto = WINFUNCTYPE(BOOL, BOOL)
    paramflags = ((1, "pbIsEnabled"),)
    SetCalibrationManagementState = proto(
        ("WcsSetCalibrationManagementState", ctypes.windll.mscms),
        paramflags,
    )
    SetCalibrationManagementState.errcheck = _errcheck_simple_bool
    return SetCalibrationManagementState


def _wrap_wcsGetDefaultColorProfile():
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
    GetDefaultColorProfile = proto(
        ("WcsGetDefaultColorProfile", ctypes.windll.mscms), paramflags
    )
    GetDefaultColorProfile.errcheck = _errcheck_args_ret
    return GetDefaultColorProfile


def _wrap_wcsGetDefaultColorProfileSize():
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
    GetDefaultColorProfileSize = proto(
        ("WcsGetDefaultColorProfileSize", ctypes.windll.mscms),
        paramflags,
    )
    GetDefaultColorProfileSize.errcheck = _errcheck_args_ret
    return GetDefaultColorProfileSize


def _wrap_wcsSetDefaultColorProfile():
    proto = WINFUNCTYPE(
        BOOL,
        WCS_PROF_SCOPE_t,
        PCWSTR,
        COLORPROFILETYPE_t,
        COLORPROFILETYPE_t,
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
    SetDefaultColorProfile = proto(
        ("WcsSetDefaultColorProfile", ctypes.windll.mscms), paramflags
    )
    SetDefaultColorProfile.errcheck = _errcheck_simple_bool
    return SetDefaultColorProfile


def _wrap_wcsGetUsePerUserProfiles():
    proto = WINFUNCTYPE(BOOL, LPWSTR, DWORD, POINTER(BOOL))
    paramflags = (
        (1, "pDeviceName"),
        (1, "dwDeviceClass"),
        (2, "pUsePerUserProfiles", BOOL(False)),
    )
    GetUsePerUserProfiles = proto(
        ("WcsGetUsePerUserProfiles", ctypes.windll.mscms),
        paramflags,
    )
    GetUsePerUserProfiles.errcheck = _errcheck_args_ret
    return GetUsePerUserProfiles


def _wrap_wcsSetUsePerUserProfiles():
    set_user_per_user_proto = WINFUNCTYPE(BOOL, LPWSTR, DWORD, BOOL)
    set_use_per_user_paramflags = (
        (1, "pDeviceName"),
        (1, "dwDeviceClass"),
        (1, "pUsePerUserProfiles"),
    )
    SetUsePerUserProfiles = set_user_per_user_proto(
        ("WcsSetUsePerUserProfiles", ctypes.windll.mscms),
        set_use_per_user_paramflags,
    )
    SetUsePerUserProfiles.errcheck = _errcheck_simple_bool
    return SetUsePerUserProfiles


class WCS:
    def __init__(self):
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

    def AssociateColorProfileWithDevice(
        self, scope: WCS_PROF_SCOPE, profile_name: str, device_key: str
    ) -> None:
        """Associates a specified WCS color profile with a specified device.
        
        This API does not support "advanced color" profiles for HDR monitors

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            profile (str): file name of the profile to disassociate
            device_key (str): device key of the device from which to disassociate the profile

        Raises:
            OSError: in case of Win API errors
        """
        self._wcsAssociateColorProfileWithDevice(scope, profile_name, device_key)

    def DisassociateColorProfileFromDevice(
        self, scope: WCS_PROF_SCOPE, profile_name: str, device_key: str
    ) -> None:
        """Disassociates a specified WCS color profile from a specified device on a computer.
        
        This API does not support "advanced color" profiles for HDR monitors. Can, apparently return random
        errors, even though it does it's job

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            profile_name (str): file name of the profile to disassociate
            device_key (str): device key of the device from which to disassociate the profile

        Raises:
            OSError: in case of Win API errors
        """
        try:
            self._wcsDisassociateColorProfileFromDevice(scope, profile_name, device_key)
        except OSError as e:
            # quirk: returns error, but errno signifies success and the profile is disassociated
            if e.winerror != WIN_ERRNO_SUCCESS:
                raise

    def EnumColorProfiles(
        self, scope: WCS_PROF_SCOPE, enum_record: ENUMTYPEW, prof_size: int
    ) -> List[str]:
        """Enumerates color profiles associated with any device, in the specified scope.
        
        This API does not support "advanced color" profiles for HDR monitors

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            enum_record (ENUMTYPEW): structure specifying the enumeration criteria
            prof_size (int): size, in bytes, of the buffer that is needed to enumerate color profiles

        Raises:
            ValueError: on parsing errors
            OSError: in case of Win API errors

        Returns:
            List[str]: array of profile names
        """
        buf = create_unicode_buffer(prof_size)
        profiles, p_num = self._wcsEnumColorProfiles(scope, enum_record, buf, prof_size)
        if p_num == 0:
            return []
        prof_arr = wstring_at(profiles, prof_size).strip("\x00").split("\x00")
        if len(prof_arr) != p_num:
            raise ValueError(
                f"Parsing error: profile number mismatch: reported {p_num} != {len(prof_arr)} got"
            )
        return prof_arr

    def EnumColorProfilesSize(
        self, scope: WCS_PROF_SCOPE, enum_record: ENUMTYPEW
    ) -> int:
        """Returns the size, in bytes, of the buffer that is required by the EnumColorProfiles function
        to enumerate color profiles. 
        
        This API does not support "advanced color" profiles for HDR monitors

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            enum_record (ENUMTYPEW): structure specifying the enumeration criteria

        Raises:
            OSError: in case of Win API errors

        Returns:
            int: size, in bytes, of the buffer that is needed to enumerate color profiles
        """
        return self._wcsEnumColorProfilesSize(scope, enum_record)

    def GetCalibrationManagementState(self) -> bool:
        """Determines whether system management of the display calibration state is enabled

        Raises:
            OSError: in case of Win API errors

        Returns:
            bool: True if system management of the display calibration state is enabled; otherwise False
        """
        return bool(self._wcsGetCalibrationManagementState())

    def SetCalibrationManagementState(self, new_state: bool) -> None:
        """Enables or disables system management of the display calibration state

        Args:
            new_state (bool): True to enable system management of the display calibration state. False to disable system management of the display calibration state

        Raises:
            OSError: in case of Win API errors
        """
        self._wcsSetCalibrationManagementState(new_state)

    def GetDefaultColorProfile(
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        prof_size: int,
        c_prof_type: COLORPROFILETYPE = COLORPROFILETYPE.CPT_ICC,
        c_prof_subtype: COLORPROFILESUBTYPE = COLORPROFILESUBTYPE.CPST_NONE,
        profile_id: int = 0,
    ) -> str:
        """Retrieves the default color profile for a device, or for a device-independent default if the device is not specified.
        
        This API does not support "advanced color" profiles for HDR monitors. Note: if HDR enabled on a device causes OSError

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            device_key (str): device key of the device for which the default color profile is obtained. If None, a device-independent default profile is obtained
            prof_size (int): size, in bytes, of the buffer that is sufficient to contain profile name
            c_prof_type (COLORPROFILETYPE, optional): value specifying the color profile type. Defaults to COLORPROFILETYPE.CPT_ICC
            c_prof_subtype (COLORPROFILESUBTYPE, optional): value specifying the color profile subtype. Defaults to COLORPROFILESUBTYPE.CPST_NONE
            profile_id (int, optional): ID of the color space that the color profile represents. Defaults to 0

        Raises:
            OSError: in case of Win API errors

        Returns:
            str: the name of the default color profile for a device
        """
        buf = create_unicode_buffer(prof_size)
        self._wcsGetDefaultColorProfile(
            scope, device_key, c_prof_type, c_prof_subtype, profile_id, prof_size, buf
        )
        return wstring_at(buf, prof_size).strip("\x00")

    def GetDefaultColorProfileSize(
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        c_prof_type: COLORPROFILETYPE = COLORPROFILETYPE.CPT_ICC,
        c_prof_subtype: COLORPROFILESUBTYPE = COLORPROFILESUBTYPE.CPST_NONE,
        profile_id: int = 0,
    ) -> int:
        """Returns the size, in bytes, of the default color profile name (including the NULL terminator), for a device.
        
        This API does not support "advanced color" profiles for HDR monitors. Note: if HDR enabled on a device returns 0

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            device_key (str): device key of the device for which the default color profile is obtained. If None, a device-independent default profile is obtained
            c_prof_type (COLORPROFILETYPE, optional): value specifying the color profile type. Defaults to COLORPROFILETYPE.CPT_ICC
            c_prof_subtype (COLORPROFILESUBTYPE, optional): value specifying the color profile subtype. Defaults to COLORPROFILESUBTYPE.CPST_NONE
            profile_id (int, optional): ID of the color space that the color profile represents. Defaults to 0

        Raises:
            OSError: in case of Win API errors

        Returns:
            int: size, in bytes, of the buffer that is sufficient to contain profile name
        """
        return self._wcsGetDefaultColorProfileSize(
            scope, device_key, c_prof_type, c_prof_subtype, profile_id
        )

    def SetDefaultColorProfile(
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        profile_name: str,
        c_prof_type: COLORPROFILETYPE = COLORPROFILETYPE.CPT_ICC,
        c_prof_subtype: COLORPROFILESUBTYPE = COLORPROFILESUBTYPE.CPST_NONE,
        profile_id: int = 0,
    ) -> None:
        """Sets the default color profile name for the specified profile type in the specified profile management scope.
        
        This API does not support "advanced color" profiles for HDR monitors

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            device_key (str): device key of the device for which the default color profile is to be set. If None, a device-independent default profile is set
            profile_name (str): file name of the profile
            c_prof_type (COLORPROFILETYPE, optional): value specifying the color profile type. Defaults to COLORPROFILETYPE.CPT_ICC
            c_prof_subtype (COLORPROFILESUBTYPE, optional): value specifying the color profile subtype. Defaults to COLORPROFILESUBTYPE.CPST_NONE
            profile_id (int, optional): ID of the color space that the color profile represents. Defaults to 0

        Raises:
            OSError: in case of Win API errors
        """
        self._wcsSetDefaultColorProfile(
            scope, device_key, c_prof_type, c_prof_subtype, profile_id, profile_name
        )

    def GetUsePerUserProfiles(
        self, device_key: str, device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR
    ) -> bool:
        """Determines whether the user chose to use a per-user profile association list for the specified device

        Args:
            device_key (str): device key of the device
            device_class (dwDeviceClass, optional): the class of the device. Defaults to dwDeviceClass.CLASS_MONITOR

        Raises:
            OSError: in case of Win API errors

        Returns:
            bool: True if the user chose to use a per-user profile association list for the specified device; otherwise False
        """
        return bool(self._wcsGetUsePerUserProfiles(device_key, device_class))

    def SetUsePerUserProfiles(
        self,
        device_key: str,
        new_state: bool,
        device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR,
    ) -> None:
        """Enables a user to specify whether or not to use a per-user profile association list for the specified device

        Args:
            device_key (str): device key of the device
            new_state (bool): True if the user wants to use a per-user profile association list for the specified device; otherwise False
            device_class (dwDeviceClass, optional): the class of the device. Defaults to dwDeviceClass.CLASS_MONITOR

        Raises:
            OSError: in case of Win API errors
        """
        self._wcsSetUsePerUserProfiles(device_key, device_class, new_state)

    def getDeviceColorProfileList(
        self,
        scope: WCS_PROF_SCOPE,
        device_key: str,
        device_class: dwDeviceClass = dwDeviceClass.CLASS_MONITOR,
    ) -> List[str]:
        """Higher abstraction level function to get color profile list for a device. Also dodges the issue
        with serialization of some ctypes structures in multiprocess context

        Args:
            scope (WCS_PROF_SCOPE): specifies the scope of this profile management operation, which could be system-wide or for the current user
            device_key (str): device key of the device

        Raises:
            OSError: in case of Win API errors
            ValueError: on parsing errors

        Returns:
            List[str]: array of color profile names
        """
        enum_record = ENUMTYPEW.create_monitor_profile_filter(device_key)
        size = self.EnumColorProfilesSize(scope, enum_record)
        prof_list = self.EnumColorProfiles(scope, enum_record, size)
        return prof_list
