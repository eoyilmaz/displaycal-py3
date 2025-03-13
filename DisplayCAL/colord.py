# -*- coding: utf-8 -*-
from binascii import hexlify
import os
import subprocess as sp
import sys
import warnings
from time import sleep

from DisplayCAL.options import use_colord_gi

try:
    # XXX D-Bus API is more complete currently
    if not use_colord_gi:
        raise ImportError("")
    from gi.repository import Colord
    from gi.repository import Gio
except ImportError:
    Colord = None
    Gio = None
else:
    cancellable = Gio.Cancellable.new()

from DisplayCAL.util_dbus import DBusObject, DBusException, BUSTYPE_SYSTEM

from DisplayCAL.util_os import which
from DisplayCAL.util_str import safe_str
from DisplayCAL import localization as lang

if sys.platform not in ("darwin", "win32"):
    from DisplayCAL.defaultpaths import xdg_data_home

    if not Colord:
        try:
            Colord = DBusObject(
                BUSTYPE_SYSTEM,
                "org.freedesktop.ColorManager",
                "/org/freedesktop/ColorManager",
            )
        except DBusException as exception:
            warnings.warn(safe_str(exception), Warning)


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


def client_connect():
    """Connect to colord"""
    client = Colord.Client.new()

    # Connect to colord
    if not client.connect_sync(cancellable):
        raise CDError("Couldn't connect to colord")
    return client


def device_connect(client, device_id):
    """Connect to device"""
    if isinstance(device_id, str):
        device_id = device_id.encode("UTF-8")
    try:
        device = client.find_device_sync(device_id, cancellable)
    except Exception as exception:
        raise CDError(exception.args[0])

    # Connect to device
    if not device.connect_sync(cancellable):
        raise CDError("Couldn't connect to device with ID %r" % device_id)
    return device


def device_id_from_edid(
    edid,
    quirk=False,
    use_serial_32=True,
    truncate_edid_strings=False,
    omit_manufacturer=False,
    query=False,
):
    """Assemble device key from EDID"""
    # https://github.com/hughsie/colord/blob/master/doc/device-and-profile-naming-spec.txt
    # Should match device ID returned by gcm_session_get_output_id in
    # gnome-settings-daemon/plugins/color/gsd-color-state.c
    # and Edid::deviceId in colord-kde/colord-kded/Edid.cpp respectively
    if "hash" in edid:
        device_id = device_ids.get(edid["hash"])
        if device_id:
            return device_id
        elif (
            sys.platform not in ("darwin", "win32")
            and query
            and isinstance(Colord, DBusObject)
        ):
            try:
                device = Device(
                    find("device-by-property", ["OutputEdidMd5", edid["hash"]])
                )
                device_id = device.properties.get("DeviceId")
            except CDError as exception:
                warnings.warn(safe_str(exception), Warning)
            else:
                if device_id:
                    device_ids[edid["hash"]] = device_id
                    return device_id
    parts = ["xrandr"]
    edid_keys = ["monitor_name", "serial_ascii"]
    if not omit_manufacturer:
        edid_keys.insert(0, "manufacturer")
    if use_serial_32:
        edid_keys.append("serial_32")
    for name in edid_keys:
        value = edid.get(name)
        if value:
            if name == "serial_32" and "serial_ascii" in edid:
                # Only add numeric serial if no ascii serial
                continue
            elif name == "manufacturer":
                if quirk:
                    value = quirk_manufacturer(value)
            elif isinstance(value, str) and truncate_edid_strings:
                # Older versions of colord used only the first 12 bytes
                value = value[:12]
            parts.append(str(value))
    if len(parts) > 1:
        device_id = "-".join(parts)
        return device_id


def find(what, search):
    """Find device or profile and return object path"""
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
                raise CDObjectNotFoundError(safe_str(exception))
            else:
                raise CDObjectQueryError(safe_str(exception))
        raise CDError(safe_str(exception))


def get_default_profile(device_id):
    """Get default profile for device"""
    # Find device object path
    device = Device(get_object_path(device_id, "device"))

    # Get default profile
    try:
        properties = device.properties
    except Exception as exception:
        raise CDError(safe_str(exception))
    else:
        if properties.get("ProfilingInhibitors"):
            return None
        profiles = properties.get("Profiles")
        if profiles:
            return profiles[0]
        else:
            raise CDError("Couldn't get default profile for device ID %r" % device_id)


def get_devices_by_kind(kind):
    if not isinstance(Colord, DBusObject):
        return []
    return [
        Device(str(object_path)) for object_path in Colord.get_devices_by_kind(kind)
    ]


def get_display_devices():
    return get_devices_by_kind("display")


def get_display_device_ids():
    return [
        _f
        for _f in (
            display.properties.get("DeviceId") for display in get_display_devices()
        )
        if _f
    ]


def get_object_path(search, object_type):
    """Get object path for profile or device ID"""
    result = find(object_type + "-by-id", search)
    if not result:
        raise CDObjectNotFoundError("Could not find object path for %s" % search)
    return result


def install_profile(
    device_id, profile, timeout=CD_CLIENT_IMPORT_DAEMON_TIMEOUT / 1000.0, logfn=None
):
    """Install profile for device.

    timeout: Time to allow for colord to pick up new profiles (recommended not below 2
        secs).

    """
    profile_install_name = os.path.join(
        xdg_data_home, "icc", os.path.basename(profile.fileName)
    )

    profile_exists = os.path.isfile(profile_install_name)
    if profile.fileName != profile_install_name and profile_exists:
        if logfn:
            logfn("About to overwrite existing", profile_install_name)
        profile.fileName = None

    if profile.ID == "\0" * 16:
        profile.calculateID()
        profile.fileName = None
    profile_id = "icc-" + hexlify(profile.ID).decode()

    # Write profile to destination
    profile_installdir = os.path.dirname(profile_install_name)
    if not os.path.isdir(profile_installdir):
        os.makedirs(profile_installdir)
    # colormgr seems to have a bug where the first attempt at importing a
    # specific profile can time out. This seems to be work-aroundable by
    # writing the profile ourself first, and then importing.
    if not profile.fileName or not profile_exists:
        if logfn:
            logfn("Writing", profile_install_name)
        profile.fileName = profile_install_name
        profile.write()

    cdprofile = None

    if Colord and not isinstance(Colord, DBusObject):
        client = client_connect()
    else:
        # Query colord for profile
        try:
            cdprofile = get_object_path(profile_id, "profile")
        except CDObjectQueryError:
            # Profile not found
            pass

        colormgr = which("colormgr")
        if not colormgr:
            raise CDError("colormgr helper program not found")

        from DisplayCAL.worker import printcmdline

        cmd = str(colormgr)

        if not cdprofile:
            # Import profile

            if logfn:
                logfn("-" * 80)
                logfn(lang.getstr("commandline"))

            args = [cmd, "import-profile", safe_str(profile.fileName)]
            printcmdline(args[0], args[1:], fn=logfn)
            if logfn:
                logfn("")

            # ts = time.time()

            maxtries = 3

            for n in range(1, maxtries + 1):
                if logfn:
                    logfn("Trying to import profile, attempt %i..." % n)
                try:
                    p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
                    stdout, stderr = p.communicate()
                except Exception as exception:
                    raise CDError(safe_str(exception))
                if logfn and stdout.strip():
                    logfn(stdout.strip())
                if p.returncode == 0 or os.path.isfile(profile_install_name):
                    if logfn:
                        logfn("...ok")
                    break
                elif logfn:
                    logfn("...failed!")

            if p.returncode != 0 and not os.path.isfile(profile_install_name):
                raise CDTimeout(
                    "Trying to import profile '%s' failed after "
                    "%i tries." % (profile.fileName, n)
                )

    if not cdprofile:
        # Query colord for newly added profile
        for _i in range(int(timeout / 1.0)):
            try:
                if Colord and not isinstance(Colord, DBusObject):
                    cdprofile = client.find_profile_sync(profile_id, cancellable)
                else:
                    cdprofile = get_object_path(profile_id, "profile")
            except CDObjectQueryError:
                # Profile not found
                pass
            if cdprofile:
                break
            # Give colord time to pick up the profile
            sleep(1)

        if not cdprofile:
            raise CDTimeout(
                "Querying for profile %r returned no result for %s "
                "secs" % (profile_id, timeout)
            )

    errmsg = "Could not make profile %s default for device %s" % (profile_id, device_id)

    if Colord and not isinstance(Colord, DBusObject):
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
            warnings.warn(safe_str(exception), Warning)

        # Make profile default for device
        if not device.make_profile_default_sync(cdprofile, cancellable):
            raise CDError(errmsg)
    else:
        # Find device object path
        device = get_object_path(device_id, "device")

        if logfn:
            logfn("-" * 80)
            logfn(lang.getstr("commandline"))

        # Add profile to device
        # (Ignore returncode as profile may already have been added)
        args = [cmd, "device-add-profile", device, cdprofile]
        printcmdline(args[0], args[1:], fn=logfn)
        if logfn:
            logfn("")
        try:
            p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
            stdout, stderr = p.communicate()
        except Exception as exception:
            raise CDError(safe_str(exception))
        if logfn and stdout.strip():
            logfn(stdout.strip())

        if logfn:
            logfn("")
            logfn(lang.getstr("commandline"))

        # Make profile default for device
        args = [cmd, "device-make-profile-default", device, cdprofile]
        printcmdline(args[0], args[1:], fn=logfn)
        if logfn:
            logfn("")
        try:
            p = sp.Popen(args, stdout=sp.PIPE, stderr=sp.STDOUT)
            stdout, stderr = p.communicate()
        except Exception as exception:
            raise CDError(safe_str(exception))
        else:
            if p.returncode != 0:
                raise CDError(stdout.strip() or errmsg)
        if logfn and stdout.strip():
            logfn(stdout.strip())


def quirk_manufacturer(manufacturer):
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

    manufacturer = manufacturer.rstrip()

    return manufacturer


class Object(DBusObject):
    def __init__(self, object_path, object_type):
        try:
            DBusObject.__init__(
                self,
                BUSTYPE_SYSTEM,
                "org.freedesktop.ColorManager",
                object_path,
                object_type,
            )
        except DBusException as exception:
            raise CDError(safe_str(exception))
        self._object_type = object_type

    _properties = DBusObject.properties

    @property
    def properties(self):
        try:
            properties = {}
            for key in self._properties:
                value = self._properties[key]
                if key == "Profiles":
                    value = [Profile(object_path) for object_path in value]
                properties[key] = value
            return properties
        except DBusException as exception:
            raise CDError(safe_str(exception))


class Device(Object):
    def __init__(self, object_path):
        Object.__init__(self, object_path, "Device")


class Profile(Object):
    def __init__(self, object_path):
        Object.__init__(self, object_path, "Profile")


class CDError(Exception):
    pass


class CDObjectQueryError(CDError):
    pass


class CDObjectNotFoundError(CDObjectQueryError):
    pass


class CDTimeout(CDError):
    pass


if __name__ == "__main__":
    import sys

    for arg in sys.argv[1:]:
        print(get_default_profile(arg))
