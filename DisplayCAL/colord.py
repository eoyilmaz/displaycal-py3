"""Interface to the colord service for managing color profiles and devices on Linux.

It supports querying, managing, and installing color profiles for display
devices, leveraging both the D-Bus API and the `colormgr` command-line utility.
"""

from __future__ import annotations

import contextlib
import os
import subprocess as sp
import sys
import warnings
from binascii import hexlify
from time import sleep
from typing import Callable

from DisplayCAL.options import USE_COLORD_GI

try:
    # XXX D-Bus API is more complete currently
    if not USE_COLORD_GI:
        raise ImportError("")
    from gi.repository import Colord, Gio
except ImportError:
    Colord = None
    Gio = None
else:
    cancellable = Gio.Cancellable.new()

from DisplayCAL import localization as lang
from DisplayCAL.util_dbus import BUSTYPE_SYSTEM, DBusException, DBusObject
from DisplayCAL.util_os import which
from DisplayCAL.util_str import safe_str

if sys.platform not in ("darwin", "win32"):
    from DisplayCAL.defaultpaths import XDG_DATA_HOME

    if not Colord:
        try:
            Colord = DBusObject(
                BUSTYPE_SYSTEM,
                "org.freedesktop.ColorManager",
                "/org/freedesktop/ColorManager",
            )
        except DBusException as exception:
            warnings.warn(safe_str(exception), Warning, stacklevel=2)


# See colord/cd-client.c
CD_CLIENT_IMPORT_DAEMON_TIMEOUT = 5000  # ms


if (
    not Colord
    or isinstance(Colord, DBusObject)
    or not hasattr(Colord, "quirk_vendor_name")
):
    # from DisplayCAL.config import get_data_path

    # From colord/lib/colord/cd_quirk.c, cd_quirk_vendor_name
    quirk_cache = {
        "suffixes": [
            "Co.",
            "Co",
            "Inc.",
            "Inc",
            "Ltd.",
            "Ltd",
            "Corporation",
            "Incorporated",
            "Limited",
            "GmbH",
            "corp.",
        ],
        "vendor_names": {
            "Acer, inc.": "Acer",
            "Acer Technologies": "Acer",
            "AOC Intl": "AOC",
            "Apple Computer Inc": "Apple",
            "Arnos Insturments & Computer Systems": "Arnos",
            "ASUSTeK Computer Inc.": "ASUSTeK",
            "ASUSTeK Computer INC": "ASUSTeK",
            "ASUSTeK COMPUTER INC.": "ASUSTeK",
            "BTC Korea Co., Ltd": "BTC",
            "CASIO COMPUTER CO.,LTD": "Casio",
            "CLEVO": "Clevo",
            "Delta Electronics": "Delta",
            "Eizo Nanao Corporation": "Eizo",
            "Envision Peripherals,": "Envision",
            "FUJITSU": "Fujitsu",
            "Fujitsu Siemens Computers GmbH": "Fujitsu Siemens",
            "Funai Electric Co., Ltd.": "Funai",
            "Gigabyte Technology Co., Ltd.": "Gigabyte",
            "Goldstar Company Ltd": "LG",
            "LG Electronics": "LG",
            "GOOGLE": "Google",
            "Hewlett-Packard": "Hewlett Packard",
            "Hitachi America Ltd": "Hitachi",
            "HP": "Hewlett Packard",
            "HWP": "Hewlett Packard",
            "IBM France": "IBM",
            "Lenovo Group Limited": "Lenovo",
            "LENOVO": "Lenovo",
            "Iiyama North America": "Iiyama",
            "MARANTZ JAPAN, INC.": "Marantz",
            "Mitsubishi Electric Corporation": "Mitsubishi",
            "Nexgen Mediatech Inc.,": "Nexgen Mediatech",
            "NIKON": "Nikon",
            "Panasonic Industry Company": "Panasonic",
            "Philips Consumer Electronics Company": "Philips",
            "RGB Systems, Inc. dba Extron Electronics": "Extron",
            "SAM": "Samsung",
            "Samsung Electric Company": "Samsung",
            "Samsung Electronics America": "Samsung",
            "samsung": "Samsung",
            "SAMSUNG": "Samsung",
            "Sanyo Electric Co.,Ltd.": "Sanyo",
            "Sonix Technology Co.": "Sonix",
            "System manufacturer": "Unknown",
            "To Be Filled By O.E.M.": "Unknown",
            "Toshiba America Info Systems Inc": "Toshiba",
            "Toshiba Matsushita Display Technology Co.,": "Toshiba",
            "TOSHIBA": "Toshiba",
            "Unknown vendor": "Unknown",
            "Westinghouse Digital Electronics": "Westinghouse Digital",
            "Zalman Tech Co., Ltd.": "Zalman",
        },
    }


prefix = "/org/freedesktop/ColorManager/"
device_ids = {}


def client_connect() -> Colord.Client:
    """Connect to colord.

    Raises:
        CDError: If there is an error connecting to colord.

    Returns:
        Colord.Client: Colord client instance.
    """
    client = Colord.Client.new()

    # Connect to colord
    if not client.connect_sync(cancellable):
        raise CDError("Couldn't connect to colord")
    return client


def device_connect(client: Colord.Client, device_id: bytes | str) -> Device:
    """Connect to device.

    Args:
        client (Colord.Client): Colord client instance.
        device_id (bytes | str): Device ID to connect to.

    Raises:
        CDError: If there is an error connecting to the device or if the device
            could not be found.

    Returns:
        Device: Connected device object.
    """
    if isinstance(device_id, str):
        device_id = device_id.encode("UTF-8")
    try:
        device = client.find_device_sync(device_id, cancellable)
    except Exception as exception:
        raise CDError(exception.args[0]) from exception

    # Connect to device
    if not device.connect_sync(cancellable):
        raise CDError(f"Couldn't connect to device with ID {device_id!r}")
    return device


def device_id_from_edid(
    edid: dict,
    quirk: bool = False,
    use_serial_32: bool = True,
    truncate_edid_strings: bool = False,
    omit_manufacturer: bool = False,
    query: bool = False,
) -> None | str:
    """Assemble device key from EDID.

    Args:
        edid (dict): EDID data containing keys like 'manufacturer',
            'monitor_name', 'serial_ascii', and optionally 'hash'.
        quirk (bool): Whether to apply manufacturer name quirks.
        use_serial_32 (bool): Whether to include the 32-bit serial number.
        truncate_edid_strings (bool): Whether to truncate EDID strings to 12 characters.
        omit_manufacturer (bool): Whether to omit the manufacturer from the device ID.
        query (bool): Whether to query colord for the device ID.

    Returns:
        None | str: Assembled device ID string or None if no valid ID could be
            constructed.
    """
    # https://github.com/hughsie/colord/blob/master/doc/device-and-profile-naming-spec.txt
    # Should match device ID returned by gcm_session_get_output_id in
    # gnome-settings-daemon/plugins/color/gsd-color-state.c
    # and Edid::deviceId in colord-kde/colord-kded/Edid.cpp respectively
    if device_id := device_id_from_edid_hash(edid=edid, query=query):
        return device_id
    return generate_device_id(
        edid, quirk, use_serial_32, truncate_edid_strings, omit_manufacturer
    )


def generate_device_id(
    edid: dict,
    quirk: bool = False,
    use_serial_32: bool = True,
    truncate_edid_strings: bool = False,
    omit_manufacturer: bool = False,
) -> None | str:
    """Generate a device ID from EDID data.

    Args:
        edid (dict): EDID data containing keys like 'manufacturer',
            'monitor_name', 'serial_ascii', and optionally 'hash'.
        quirk (bool): Whether to apply manufacturer name quirks.
        use_serial_32 (bool): Whether to include the 32-bit serial number.
        truncate_edid_strings (bool): Whether to truncate EDID strings to 12 characters.
        omit_manufacturer (bool): Whether to omit the manufacturer from the device ID.

    Returns:
        str: A string representing the device ID based on the EDID data.
    """
    parts = ["xrandr"]
    edid_keys = ["monitor_name", "serial_ascii"]
    if not omit_manufacturer:
        edid_keys.insert(0, "manufacturer")
    if use_serial_32:
        edid_keys.append("serial_32")
    for name in edid_keys:
        if not (value := edid.get(name)):
            continue
        if name == "serial_32" and "serial_ascii" in edid:
            # Only add numeric serial if no ascii serial
            continue
        if name == "manufacturer":
            value = quirk_manufacturer(value) if quirk else value
        elif isinstance(value, str) and truncate_edid_strings:
            # Older versions of colord used only the first 12 bytes
            value = value[:12]
        parts.append(str(value))
    return "-".join(parts) if len(parts) > 1 else None


def device_id_from_edid_hash(edid: dict, query: bool = False) -> None | str:
    """Generate a device ID from EDID hash.

    Args:
        edid (dict): EDID data containing 'hash' key.
        query (bool): Whether to query colord for the device ID.

    Returns:
        None | str: A string representing the device ID based on the EDID hash.
    """
    if "hash" not in edid:
        return None

    # Placeholder implementation, replace with actual logic as needed
    if device_id := device_ids.get(edid["hash"]):
        return device_id
    if (
        sys.platform not in ("darwin", "win32")
        and query
        and isinstance(Colord, DBusObject)
    ):
        try:
            device = Device(find("device-by-property", ["OutputEdidMd5", edid["hash"]]))
            device_id = device.properties.get("DeviceId")
        except CDError as exception:
            warnings.warn(safe_str(exception), Warning, stacklevel=2)
        else:
            if device_id:
                device_ids[edid["hash"]] = device_id
                return device_id
    return None


def find(what: str, search: str | list) -> str:
    """Find device or profile and return object path.

    Args:
        what (str): Type of object to search for, e.g., "profile-by-id" or
            "device-by-property".
        search (list or str): Search criteria, e.g., profile ID or device ID.

    Raises:
        CDError: If colord API is not available or if there is an error
            querying the object.
        CDObjectNotFoundError: If the object could not be found.
        CDObjectQueryError: If there is an error querying the object.

    Returns:
        str: Object path of the found object.
    """
    if not isinstance(Colord, DBusObject):
        raise CDError("colord API not available")
    if not isinstance(search, list):
        search = [search]
    method_name = "_".join(part for part in what.split("-"))
    try:
        return getattr(Colord, "find_" + method_name)(*search)
    except Exception as exception:
        if hasattr(exception, "get_dbus_name"):
            if exception.get_dbus_name() == "org.freedesktop.ColorManager.NotFound":
                raise CDObjectNotFoundError(safe_str(exception)) from exception
            raise CDObjectQueryError(safe_str(exception)) from exception
        raise CDError(safe_str(exception)) from exception


def get_default_profile(device_id: str) -> str:
    """Get default profile for device.

    Args:
        device_id (str): Device ID to search for.

    Returns:
        str: Default profile ID for the device.
    """
    # Find device object path
    device = Device(get_object_path(device_id, "device"))

    # Get default profile
    try:
        properties = device.properties
    except Exception as exception:
        raise CDError(safe_str(exception)) from exception
    else:
        if properties.get("ProfilingInhibitors"):
            return None
        profiles = properties.get("Profiles")
        if profiles:
            return profiles[0]
        raise CDError(f"Couldn't get default profile for device ID {device_id!r}")


def get_devices_by_kind(kind: str) -> list:
    """Get devices by kind.

    Args:
        kind (str): Kind of device to search for.

    Returns:
        list: List of devices of the specified kind.
    """
    if not isinstance(Colord, DBusObject):
        return []
    return [
        Device(str(object_path)) for object_path in Colord.get_devices_by_kind(kind)
    ]


def get_display_devices() -> list:
    """Get display devices.

    Returns:
        list: List of display devices.
    """
    return get_devices_by_kind("display")


def get_display_device_ids() -> list:
    """Get display device IDs.

    Returns:
        list: List of display device IDs.
    """
    return [
        _f
        for _f in (
            display.properties.get("DeviceId") for display in get_display_devices()
        )
        if _f
    ]


def get_object_path(search: str, object_type: str) -> str:
    """Get object path for profile or device ID.

    Args:
        search (str): Profile or device ID to search for.
        object_type (str): Type of object to search for, e.g., "profile" or
            "device".

    Raises:
        CDObjectNotFoundError: If the object path could not be found.

    Returns:
        str: Object path for the specified profile or device ID.
    """
    result = find(f"{object_type}-by-id", search)
    if not result:
        raise CDObjectNotFoundError(f"Could not find object path for {search}")
    return result


def install_profile(
    device_id: str,
    profile: Profile,
    timeout: float = CD_CLIENT_IMPORT_DAEMON_TIMEOUT / 1000.0,
    logfn: None | Callable = None,
) -> None:
    """Install profile for device.

    Args:
        device_id (str): Device ID to install the profile for.
        profile (Profile): Profile object to install.
        timeout (float): Time to allow for colord to pick up new profiles (recommended
            not below 2 secs).
        logfn (callable, optional): Function to log messages. Defaults to None.
    """
    if Colord and not isinstance(Colord, DBusObject):
        install_profile_with_colord(device_id, profile, timeout=timeout, logfn=logfn)
    else:
        install_profile_with_dbus(device_id, profile, timeout=timeout, logfn=logfn)


def get_profile_install_parameters(
    profile: Profile, logfn: None | Callable = None
) -> tuple[str, bool, str]:
    """Get parameters for profile installation.

    Args:
        profile (Profile): Profile object to install.
        logfn (callable, optional): Function to log messages. Defaults to None.

    Returns:
        tuple: A tuple containing the profile installation name, whether the
            profile already exists, and the profile ID.
    """
    profile_install_name = os.path.join(
        XDG_DATA_HOME, "icc", os.path.basename(profile.filename)
    )

    profile_exists = os.path.isfile(profile_install_name)
    if profile.filename != profile_install_name and profile_exists:
        if logfn:
            logfn("About to overwrite existing", profile_install_name)
        profile.filename = None

    if profile.ID == "\0" * 16:
        profile.calculate_id()
        profile.filename = None
    profile_id = "icc-" + hexlify(profile.ID).decode()
    return profile_install_name, profile_exists, profile_id


def write_profile_to_destination(
    profile: Profile,
    profile_install_name: str,
    profile_exists: bool,
    logfn: None | Callable = None,
) -> None:
    """Write profile to destination.

    Args:
        profile (Profile): Profile object to write.
        profile_install_name (str): Path where the profile should be installed.
        profile_exists (bool): Whether the profile already exists at the
            destination.
        logfn (callable, optional): Function to log messages. Defaults to None.
    """
    profile_install_dir = os.path.dirname(profile_install_name)
    if not os.path.isdir(profile_install_dir):
        os.makedirs(profile_install_dir)
    # colormgr seems to have a bug where the first attempt at importing a
    # specific profile can time out. This seems to be work-aroundable by
    # writing the profile ourself first, and then importing.
    if not profile.filename or not profile_exists:
        if logfn:
            logfn("Writing", profile_install_name)
        profile.filename = profile_install_name
        profile.write()


def install_profile_with_colord(
    device_id: str,
    profile: Profile,
    timeout: float = CD_CLIENT_IMPORT_DAEMON_TIMEOUT / 1000.0,
    logfn: None | Callable = None,
) -> None:
    """Install profile for device.

    Args:
        device_id (str): Device ID to install the profile for.
        profile (Profile): Profile object to install.
        timeout (float): Time to allow for colord to pick up new profiles (recommended
            not below 2 secs).
        logfn (callable, optional): Function to log messages. Defaults to None.

    Raises:
        CDError: If there is an error connecting to colord or if the profile
            could not be made default for the device.
        CDTimeoutError: If querying for the profile takes too long.
    """
    profile_install_name, profile_exists, profile_id = get_profile_install_parameters(
        profile, logfn
    )
    write_profile_to_destination(profile, profile_install_name, profile_exists, logfn)

    client = client_connect()
    cdprofile = query_colord_for_newly_added_profile(profile_id, timeout=timeout)

    # Connect to profile
    if not cdprofile.connect_sync(cancellable):
        raise CDError("Could not connect to profile")

    # Connect to existing device
    device = device_connect(client, device_id)

    # Add profile to device
    try:
        device.add_profile_sync(Colord.DeviceRelation.HARD, cdprofile, cancellable)
    except Exception as exception:
        # Profile may already have been added
        warnings.warn(safe_str(exception), Warning, stacklevel=2)

    # Make profile default for device
    if not device.make_profile_default_sync(cdprofile, cancellable):
        raise CDError(
            f"Could not make profile {profile_id} default for device {device_id}"
        )


def install_profile_with_dbus(
    device_id: str,
    profile: Profile,
    timeout: float = CD_CLIENT_IMPORT_DAEMON_TIMEOUT / 1000.0,
    logfn: None | Callable = None,
) -> None:
    """Install profile for device with DBusObject.

    Args:
        device_id (str): Device ID to install the profile for.
        profile (Profile): Profile object to install.
        timeout (float): Time to allow for colord to pick up new profiles (recommended
            not below 2 secs).
        logfn (callable, optional): Function to log messages. Defaults to None.
    """
    if not logfn:
        # let's reduce complexity a bit
        def logfn(*args, **kwargs) -> None:
            """Dummy log function that does nothing."""

    profile_install_name, profile_exists, profile_id = get_profile_install_parameters(
        profile, logfn
    )
    write_profile_to_destination(profile, profile_install_name, profile_exists, logfn)

    cdprofile = None

    # Query colord for profile
    with contextlib.suppress(CDObjectQueryError):
        cdprofile = get_object_path(profile_id, "profile")
        # If profile not found, it will raise a CDObjectQueryError

    if not (colormgr := which("colormgr")):
        raise CDError("'colormgr' helper program not found!")

    cmd = str(colormgr)
    if not cdprofile:
        cdprofile = import_profile(
            cmd, profile, profile_install_name, profile_id, timeout=timeout, logfn=logfn
        )

    # Find device object path
    device = get_object_path(device_id, "device")

    add_profile_to_device(cmd, device, cdprofile, logfn)
    make_profile_default_for_device(
        cmd, profile_id, device_id, device, cdprofile, logfn=logfn
    )


def import_profile(
    cmd: str,
    profile: Profile,
    profile_install_name: str,
    profile_id: str,
    timeout: float = CD_CLIENT_IMPORT_DAEMON_TIMEOUT / 1000.0,
    logfn: None | Callable = None,
) -> None | str:
    """Import profile using colormgr.

    Args:
        cmd (str): Command to run, e.g., "colormgr".
        profile (Profile): Profile object to import.
        profile_install_name (str): Path where the profile should be installed.
        profile_id (str): ID of the profile.
        timeout (float): Time to allow for colord to pick up new profiles
            (recommended not below 2 secs).
        logfn (callable, optional): Function to log messages. Defaults to None.

    Raises:
        CDError: If there is an error running the command or if the command
            fails.
        CDTimeoutError: If querying for the profile takes too long.

    Returns:
        None | str: Object path of the imported profile.
    """
    # Import profile
    if not logfn:
        # let's reduce complexity a bit
        def logfn(*args, **kwargs) -> None:
            """Dummy log function that does nothing."""

    logfn("-" * 80)
    logfn(lang.getstr("commandline"))
    args = [cmd, "import-profile", safe_str(profile.filename)]

    from DisplayCAL.worker import printcmdline

    printcmdline(args[0], args[1:], fn=logfn)
    logfn("")
    maxtries = 3
    for n in range(1, maxtries + 1):
        logfn(f"Trying to import profile, attempt {n}...")
        try:
            process = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
            stdout, _ = process.communicate()
        except Exception as exception:
            raise CDError(safe_str(exception)) from exception
        if stdout.strip():
            logfn(stdout.strip())
        if process.returncode == 0 or os.path.isfile(profile_install_name):
            logfn("...ok")
            break
        logfn("...failed!")

    if process.returncode != 0 and not os.path.isfile(profile_install_name):
        raise CDTimeoutError(
            f"Trying to import profile '{profile.filename}' failed after {n} tries."
        )

    # Try to find the profile by the ICC profile.ID-based profile_id first.
    # If that fails (because colord uses a different ID scheme based on the
    # file checksum), fall back to finding by filename, which is reliable
    # and locale-independent.
    try:
        return query_colord_for_newly_added_profile(profile_id, timeout=timeout)
    except CDTimeoutError:
        pass

    # Fallback: use colormgr find-profile-by-filename to locate the profile
    # that was just imported. This works regardless of the ID scheme colord
    # uses internally (md5 of file contents vs. ICC profile.ID header).
    for _ in range(int(timeout / 1.0)):
        with contextlib.suppress(CDObjectQueryError, CDObjectNotFoundError):
            cdprofile = _find_profile_by_filename(cmd, profile_install_name)
            if cdprofile:
                return cdprofile
        sleep(1)

    raise CDTimeoutError(
        f"Querying for profile {profile_id!r} (and by filename "
        f"{profile_install_name!r}) returned no result for {timeout} secs"
    )


def _find_profile_by_filename(cmd: str, filename: str) -> None | str:
    """Find a profile in colord by its filename using colormgr.

    This is a fallback for when the profile ID-based lookup fails, e.g.
    because colord uses a different ID scheme (md5 of file contents) than
    the ICC profile.ID header that DisplayCAL uses.

    Args:
        cmd (str): The colormgr command path.
        filename (str): The filename of the profile to search for.

    Returns:
        None | str: The D-Bus object path of the profile, or None if not found.
    """
    args = [cmd, "find-profile-by-filename", filename]
    try:
        process = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
        stdout, _ = process.communicate()
    except Exception:
        return None
    if process.returncode != 0 or not stdout.strip():
        return None
    # Parse the object path from the output. colormgr outputs it on a line
    # like "Object path:     /org/freedesktop/ColorManager/profiles/..."
    # (or the locale-translated equivalent, e.g. "Objektsti:" in Norwegian).
    # We match by the D-Bus object path pattern which is locale-independent.
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if "/org/freedesktop/ColorManager/" in line:
            # Extract just the path (may have a label prefix in non-English locales)
            parts = line.split()
            for part in parts:
                if part.startswith("/org/freedesktop/ColorManager/"):
                    return part
    return None


def query_colord_for_newly_added_profile(
    profile_id: str, timeout: float = CD_CLIENT_IMPORT_DAEMON_TIMEOUT / 1000.0
) -> str:
    """Query colord for newly added profile.

    Args:
        profile_id (str): ID of the profile to query for.
        timeout (float): Time to allow for colord to pick up new profiles
            (recommended not below 2 secs).

    Raises:
        CDTimeoutError: If querying for the profile takes too long.

    Returns:
        str: Object path of the queried profile.
    """
    cdprofile = None
    for _ in range(int(timeout / 1.0)):
        # Profile might not be found so suppress the error
        with contextlib.suppress(CDObjectQueryError):
            cdprofile = get_object_path(profile_id, "profile")
        if cdprofile:
            break
        # Give colord time to pick up the profile
        sleep(1)

    if not cdprofile:
        raise CDTimeoutError(
            f"Querying for profile {profile_id!r} returned no result for {timeout} secs"
        )

    return cdprofile


def add_profile_to_device(
    cmd: str, device: str, cdprofile: str, logfn: None | Callable = None
) -> None:
    """Add profile to device.

    Ignore returncode as profile may already have been added.

    Args:
        cmd (str): Command to run, e.g., "colormgr".
        device (str): Device object path.
        cdprofile (str): Profile object path.
        logfn (callable, optional): Function to log messages. Defaults to None.

    Raises:
        CDError: If there is an error running the command or if the command
            fails.
    """
    from DisplayCAL.worker import printcmdline

    logfn("-" * 80)
    logfn(lang.getstr("commandline"))

    args = [cmd, "device-add-profile", device, cdprofile]

    printcmdline(args[0], args[1:], fn=logfn)
    logfn("")
    try:
        p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
        stdout, _ = p.communicate()
    except Exception as exception:
        raise CDError(safe_str(exception)) from exception

    if stdout.strip():
        logfn(stdout.strip())


def make_profile_default_for_device(
    cmd: str,
    profile_id: str,
    device_id: str,
    device: str,
    cdprofile: str,
    logfn: None | Callable = None,
) -> None:
    """Make profile default for device.

    Args:
        cmd (str): Command to run, e.g., "colormgr".
        profile_id (str): ID of the profile to make default.
        device_id (str): ID of the device to make the profile default for.
        device (str): Device object path.
        cdprofile (str): Profile object path.
        logfn (callable, optional): Function to log messages. Defaults to None.

    Raises:
        CDError: If there is an error running the command or if the command
            fails.
    """
    from DisplayCAL.worker import printcmdline

    logfn("")
    logfn(lang.getstr("commandline"))

    # Make profile default for device
    args = [cmd, "device-make-profile-default", device, cdprofile]
    printcmdline(args[0], args[1:], fn=logfn)
    logfn("")
    try:
        p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
        stdout, stderr = p.communicate()
    except Exception as exception:
        raise CDError(safe_str(exception)) from exception
    else:
        if p.returncode != 0:
            raise CDError(
                stdout.strip()
                or f"Could not make profile {profile_id} default for device {device_id}"
            )
    if stdout.strip():
        logfn(stdout.strip())


def quirk_manufacturer(manufacturer: str) -> str:
    """Correct manufacturer name for colord.

    Args:
        manufacturer (str): Manufacturer name to correct.

    Returns:
        str: Corrected manufacturer name.
    """
    if (
        Colord
        and not isinstance(Colord, DBusObject)
        and hasattr(Colord, "quirk_vendor_name")
    ):
        return Colord.quirk_vendor_name(manufacturer)

    # Correct some company names
    for old, new in quirk_cache["vendor_names"].items():
        if manufacturer.startswith(old):
            manufacturer = new
            break

    # Get rid of suffixes
    for suffix in quirk_cache["suffixes"]:
        if manufacturer.endswith(suffix):
            manufacturer = manufacturer[0 : len(manufacturer) - len(suffix)]

    return manufacturer.rstrip()


class Object(DBusObject):
    """Base class for colord objects.

    Args:
        object_path (str): D-Bus object path of the colord object.
        object_type (str): Type of the colord object, e.g., "Device" or
            "Profile".
    """

    def __init__(self, object_path: str, object_type: str) -> None:
        try:
            super().__init__(
                BUSTYPE_SYSTEM,
                "org.freedesktop.ColorManager",
                object_path,
                object_type,
            )
        except DBusException as exception:
            raise CDError(safe_str(exception)) from exception
        self._object_type = object_type

    _properties = DBusObject.properties

    @property
    def properties(self) -> dict:
        """Get properties of the object.

        Raises:
            CDError: If there is an error retrieving the properties.

        Returns:
            dict: Dictionary of properties of the object.
        """
        try:
            properties = {}
            for key in self._properties:
                value = self._properties[key]
                if key == "Profiles":
                    value = [Profile(object_path) for object_path in value]
                properties[key] = value
            return properties
        except DBusException as exception:
            raise CDError(safe_str(exception)) from exception


class Device(Object):
    """Device object.

    Args:
        object_path (str): D-Bus object path of the colord device.
    """

    def __init__(self, object_path: str) -> None:
        super().__init__(object_path, "Device")


class Profile(Object):
    """Profile object.

    Args:
        object_path (str): D-Bus object path of the colord profile.
    """

    def __init__(self, object_path: str) -> None:
        super().__init__(object_path, "Profile")


class CDError(Exception):
    """Base class for colord errors."""


class CDObjectQueryError(CDError):
    """Object query error."""


class CDObjectNotFoundError(CDObjectQueryError):
    """Object not found error."""


class CDTimeoutError(CDError):
    """Timeout error."""


if __name__ == "__main__":
    import sys

    for arg in sys.argv[1:]:
        print(get_default_profile(arg))
