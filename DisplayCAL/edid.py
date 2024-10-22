# -*- coding: utf-8 -*-

from hashlib import md5
import codecs
import math
import os
import re
import string
import struct
import subprocess
import sys


if sys.platform == "win32":
    from threading import _MainThread, currentThread

    wmi = None
    if sys.getwindowsversion() >= (6,):
        # Use WMI for Vista/Win7
        import pythoncom

        try:
            import wmi
        except Exception:
            pass
    else:
        # Use registry as fallback for Win2k/XP/2003
        import winreg
    import pywintypes
    import win32api
elif sys.platform == "darwin":
    import binascii

from DisplayCAL import config
from DisplayCAL import RealDisplaySizeMM as RDSMM
from DisplayCAL.util_os import which
from DisplayCAL.util_str import make_ascii_printable, safe_str, strtr

if sys.platform == "win32":
    from DisplayCAL import util_win

HEADER = (0, 8)
MANUFACTURER_ID = (8, 10)
PRODUCT_ID = (10, 12)
SERIAL_32 = (12, 16)
WEEK_OF_MANUFACTURE = 16
YEAR_OF_MANUFACTURE = 17
EDID_VERSION = 18
EDID_REVISION = 19
MAX_H_SIZE_CM = 21
MAX_V_SIZE_CM = 22
GAMMA = 23
FEATURES = 24
LO_RG_XY = 25
LO_BW_XY = 26
HI_R_X = 27
HI_R_Y = 28
HI_G_X = 29
HI_G_Y = 30
HI_B_X = 31
HI_B_Y = 32
HI_W_X = 33
HI_W_Y = 34
BLOCKS = ((54, 72), (72, 90), (90, 108), (108, 126))
BLOCK_TYPE = 3
BLOCK_CONTENTS = (5, 18)
BLOCK_TYPE_SERIAL_ASCII = b"\xff"
BLOCK_TYPE_ASCII = b"\xfe"
BLOCK_TYPE_MONITOR_NAME = b"\xfc"
BLOCK_TYPE_COLOR_POINT = b"\xfb"
BLOCK_TYPE_COLOR_MANAGEMENT_DATA = b"\xf9"
EXTENSION_FLAG = 126
CHECKSUM = 127
BLOCK_DI_EXT = b"\x40"
TRC = (81, 127)

pnpidcache = {}


def combine_hi_8lo(hi, lo):
    return hi << 8 | lo


def get_edid(display_no=0, display_name=None, device=None):
    """Get and parse EDID. Return dict.

    On Mac OS X, you need to specify a display name.
    On all other platforms, you need to specify a display number (zero-based).
    """
    edid = None
    if sys.platform == "win32":
        if not device:
            # The ordering will work as long as Argyll continues using
            # EnumDisplayMonitors
            monitors = util_win.get_real_display_devices_info()
            moninfo = monitors[display_no]
            device = util_win.get_active_display_device(moninfo["Device"])
        if not device:
            return {}
        id = device.DeviceID.split("\\")[1]
        wmi_connection = None
        not_main_thread = currentThread().__class__ is not _MainThread
        if wmi:
            if not_main_thread:
                pythoncom.CoInitialize()
            wmi_connection = wmi.WMI(namespace="WMI")
        if wmi_connection:
            # Use WMI for Vista/Win7
            # http://msdn.microsoft.com/en-us/library/Aa392707
            try:
                msmonitors = wmi_connection.WmiMonitorDescriptorMethods()
            except Exception as exception:
                if not_main_thread:
                    pythoncom.CoUninitialize()
                raise WMIError(safe_str(exception))
            for msmonitor in msmonitors:
                if msmonitor.InstanceName.split("\\")[1] == id:
                    try:
                        edid = msmonitor.WmiGetMonitorRawEEdidV1Block(0)
                    except Exception:
                        # No EDID entry
                        pass
                    else:
                        edid = "".join(chr(i) for i in edid[0])
                    break
            if not_main_thread:
                pythoncom.CoUninitialize()
        elif sys.getwindowsversion() < (6,):
            # Use registry as fallback for Win2k/XP/2003
            # http://msdn.microsoft.com/en-us/library/ff546173%28VS.85%29.aspx
            # "The Enum tree is reserved for use by operating system components,
            #  and its layout is subject to change. (...) Drivers and Windows
            #  applications must not access the Enum tree directly."
            # But do we care? Probably not, as older Windows' API isn't likely
            # gonna change.
            driver = "\\".join(device.DeviceID.split("\\")[-2:])
            subkey = "\\".join(["SYSTEM", "CurrentControlSet", "Enum", "DISPLAY", id])
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
            except WindowsError:
                # Registry error
                print(
                    "Windows registry error: Key",
                    "\\".join(["HKEY_LOCAL_MACHINE", subkey]),
                    "does not exist.",
                )
                return {}
            numsubkeys, numvalues, mtime = winreg.QueryInfoKey(key)
            for i in range(numsubkeys):
                hkname = winreg.EnumKey(key, i)
                hk = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, "\\".join([subkey, hkname])
                )
                try:
                    test = winreg.QueryValueEx(hk, "Driver")[0]
                except WindowsError:
                    # No Driver entry
                    continue
                if test == driver:
                    # Found our display device
                    try:
                        devparms = winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE,
                            "\\".join([subkey, hkname, "Device Parameters"]),
                        )
                    except WindowsError:
                        # No Device Parameters (registry error?)
                        print(
                            "Windows registry error: Key",
                            "\\".join(
                                [
                                    "HKEY_LOCAL_MACHINE",
                                    subkey,
                                    hkname,
                                    "Device Parameters",
                                ]
                            ),
                            "does not exist.",
                        )
                        continue
                    try:
                        edid = winreg.QueryValueEx(devparms, "EDID")[0]
                    except WindowsError:
                        # No EDID entry
                        pass
        else:
            raise WMIError("No WMI connection")
    elif sys.platform == "darwin":
        # Get EDID via ioreg
        p = subprocess.Popen(
            ["ioreg", "-c", "IODisplay", "-S", "-w0"], stdout=subprocess.PIPE
        )
        stdout, stderr = p.communicate()
        if not stdout:
            return {}
        for edid in [
            binascii.unhexlify(edid_hex)
            for edid_hex in re.findall(
                r'"IODisplayEDID"\s*=\s*<([0-9A-Fa-f]*)>', stdout.decode()
            )
        ]:
            if not edid or len(edid) < 128:
                continue
            parsed_edid = parse_edid(edid)
            if (
                parsed_edid.get("monitor_name", parsed_edid.get("ascii"))
                == display_name
            ):
                # On Mac OS X, you need to specify a display name
                # because the order is unknown
                return parsed_edid
        return {}
    else:
        display = RDSMM.get_display(display_no)
        print(f"display (3)       : {display}")
        if not display:
            return {}

        p = subprocess.Popen([which("xrandr"), "--verbose"], stdout=subprocess.PIPE)
        stdout, stderr = p.communicate()

        if not stdout:
            return {}

        found_display = False
        found_edid = False
        edid_data = []
        for line in stdout.splitlines():
            if found_edid:
                if line.startswith(b"\t\t"):
                    # extract the edid data
                    edid_data.append(line.strip())
                else:
                    # read all data, exit
                    break
            if found_display:
                # try to find EDID
                if b"EDID" in line:
                    found_edid = True
            # try to find the display
            if (display["name"] + b" connected") in line:
                found_display = True

        edid = b"".join(edid_data)

    if edid and len(edid) >= 128:
        return parse_edid(edid)
    return {}


def parse_manufacturer_id(block):
    """Parse the manufacturer id and return decoded string.

    The range is always ASCII charcode 64 to 95.
    """
    h = combine_hi_8lo(block[0], block[1])
    manufacturer_id = []
    for shift in (10, 5, 0):
        manufacturer_id.append(chr(((h >> shift) & 0x1F) + ord("A") - 1))
    return "".join(manufacturer_id).strip()


def get_manufacturer_name(manufacturer_id):
    """Try and get a nice descriptive string for our manufacturer id.
    This uses either hwdb or pnp.ids which will be looked for in several places.
    If it can't find the file, it returns None.

    Examples:
    SAM -> Samsung Electric Company
    NEC -> NEC Corporation

    hwdb/pnp.ids can be created from Excel data available from uefi.org:
    http://www.uefi.org/PNP_ACPI_Registry
    http://www.uefi.org/uefi-pnp-export
    http://www.uefi.org/uefi-acpi-export

    But it is probably a better idea to use HWDB as it contains various
    additions from other sources:
    https://github.com/systemd/systemd/blob/master/hwdb/20-acpi-vendor.hwdb

    """
    if not pnpidcache:
        paths = [
            "/usr/lib/udev/hwdb.d/20-acpi-vendor.hwdb",  # systemd
            "/usr/share/hwdata/pnp.ids",  # hwdata, e.g. Red Hat
            "/usr/share/misc/pnp.ids",  # pnputils, e.g. Debian
            "/usr/share/libgnome-desktop/pnp.ids",
        ]  # fallback gnome-desktop
        # if sys.platform in ("darwin", "win32"):
        paths.append(os.path.join(config.pydir, "pnp.ids"))  # fallback
        # fallback for tests
        paths.append(os.path.join(config.pydir, "DisplayCAL", "pnp.ids"))
        for path in paths:
            if os.path.isfile(path):
                try:
                    pnp_ids = codecs.open(path, "r", "UTF-8", "replace")
                except IOError:
                    pass
                else:
                    id, name = None, None
                    try:
                        for line in pnp_ids:
                            if path.endswith("hwdb"):
                                if line.strip().startswith("acpi:"):
                                    id = line.split(":")[1][:3]
                                    continue
                                elif line.strip().startswith("ID_VENDOR_FROM_DATABASE"):
                                    name = line.split("=", 1)[1].strip()
                                else:
                                    continue
                                if not id or not name or id in pnpidcache:
                                    continue
                            else:
                                try:
                                    # Strip leading/trailing whitespace
                                    # (non-breaking spaces too)
                                    id, name = line.strip(
                                        string.whitespace + "\u00a0"
                                    ).split(None, 1)
                                except ValueError:
                                    continue
                            pnpidcache[id] = name
                    except OSError:
                        continue
                    finally:
                        pnp_ids.close()
                    break
    return pnpidcache.get(manufacturer_id)


def edid_get_bit(value, bit):
    return (value & (1 << bit)) >> bit


def edid_get_bits(value, begin, end):
    mask = (1 << (end - begin + 1)) - 1
    return (value >> begin) & mask


def edid_decode_fraction(high, low):
    result = 0.0
    high = (high << 2) | low
    for i in range(0, 10):
        result += edid_get_bit(high, i) * math.pow(2, i - 10)
    return result


def edid_parse_string(desc):
    # Return value should match colord's cd_edid_parse_string in cd-edid.c
    # Remember: In C, NULL terminates a string, so do the same here
    # Replace newline with NULL, then strip anything after first NULL byte
    # (if any), then strip trailing whitespace
    desc = strtr(desc[:13], {b"\n": b"\x00", b"\r": b"\x00"}).split(b"\x00")[0].rstrip()
    if desc:
        # Replace all non-printable chars with NULL
        # Afterwards, the amount of NULL bytes is the number of replaced chars
        desc = make_ascii_printable(desc, substitute=b"\x00")
        if desc.count(b"\x00") <= 4:
            # Only use string if max 4 replaced chars
            # Replace any NULL chars with dashes to make a printable string
            return desc.replace(b"\0", b"-")


def parse_edid(edid):
    """Parse raw EDID data (binary string) and return dict."""
    if len(edid) not in [128, 256, 384]:
        # this is probably encoded/decoded in a wrong way and contains 2-bytes
        # characters
        #
        # b"\xc2" and b"\xc3" are codepoints
        # they can only appear if the byte data is decoded with latin-1 and encoded back
        # with utf-8.
        # This apparently is a wrong conversion.
        edid = edid.decode("utf-8").encode("latin-1")

    result = {
        "edid": edid,
        "hash": md5(edid).hexdigest(),
        "header": edid[HEADER[0] : HEADER[1]],
        "manufacturer_id": parse_manufacturer_id(
            edid[MANUFACTURER_ID[0] : MANUFACTURER_ID[1]]
        ),
    }
    manufacturer = get_manufacturer_name(result["manufacturer_id"])
    if manufacturer:
        result["manufacturer"] = manufacturer

    result["product_id"] = struct.unpack("<H", edid[PRODUCT_ID[0] : PRODUCT_ID[1]])[0]
    result["serial_32"] = struct.unpack("<I", edid[SERIAL_32[0] : SERIAL_32[1]])[0]
    result["week_of_manufacture"] = edid[WEEK_OF_MANUFACTURE]
    result["year_of_manufacture"] = edid[YEAR_OF_MANUFACTURE] + 1990
    result["edid_version"] = edid[EDID_VERSION]
    result["edid_revision"] = edid[EDID_REVISION]

    result["max_h_size_cm"] = edid[MAX_H_SIZE_CM]
    result["max_v_size_cm"] = edid[MAX_V_SIZE_CM]
    if edid[GAMMA] != b"\xff":
        result["gamma"] = edid[GAMMA] / 100.0 + 1
    result["features"] = edid[FEATURES]

    result["red_x"] = edid_decode_fraction(
        edid[HI_R_X], edid_get_bits(edid[LO_RG_XY], 6, 7)
    )
    result["red_y"] = edid_decode_fraction(
        edid[HI_R_Y], edid_get_bits(edid[LO_RG_XY], 4, 5)
    )

    result["green_x"] = edid_decode_fraction(
        edid[HI_G_X], edid_get_bits(edid[LO_RG_XY], 2, 3)
    )
    result["green_y"] = edid_decode_fraction(
        edid[HI_G_Y], edid_get_bits(edid[LO_RG_XY], 0, 1)
    )

    result["blue_x"] = edid_decode_fraction(
        edid[HI_B_X], edid_get_bits(edid[LO_BW_XY], 6, 7)
    )
    result["blue_y"] = edid_decode_fraction(
        edid[HI_B_Y], edid_get_bits(edid[LO_BW_XY], 4, 5)
    )

    result["white_x"] = edid_decode_fraction(
        edid[HI_W_X], edid_get_bits(edid[LO_BW_XY], 2, 3)
    )
    result["white_y"] = edid_decode_fraction(
        edid[HI_W_Y], edid_get_bits(edid[LO_BW_XY], 0, 1)
    )

    text_types = {
        BLOCK_TYPE_SERIAL_ASCII: "serial_ascii",
        BLOCK_TYPE_ASCII: "ascii",
        BLOCK_TYPE_MONITOR_NAME: "monitor_name",
    }
    # Parse descriptor blocks
    for start, stop in BLOCKS:
        block = edid[start:stop]
        if block[:BLOCK_TYPE] != b"\x00\x00\x00":
            # Ignore pixel clock data
            continue
        text_type = text_types.get(block[BLOCK_TYPE : BLOCK_TYPE + 1])
        if text_type:
            desc = edid_parse_string(block[BLOCK_CONTENTS[0] : BLOCK_CONTENTS[1]])
            if desc is not None:
                result[text_type] = desc.decode("utf-8")
        elif block[BLOCK_TYPE] == BLOCK_TYPE_COLOR_POINT:
            for i in (5, 10):
                # 2nd white point index in range 1...255
                # 3rd white point index in range 2...255
                # 0 = do not use
                if block[i] > i / 5:
                    white_x = edid_decode_fraction(
                        edid[i + 2], edid_get_bits(edid[i + 1], 2, 3)
                    )
                    result["white_x_" + str(block[i])] = white_x
                    if not result.get("white_x"):
                        result["white_x"] = white_x
                    white_y = edid_decode_fraction(
                        edid[i + 3], edid_get_bits(edid[i + 1], 0, 1)
                    )
                    result["white_y_" + str(block[i])] = white_y
                    if not result.get("white_y"):
                        result["white_y"] = white_y
                    if block[i + 4] != "\xff":
                        gamma = block[i + 4] / 100.0 + 1
                        result["gamma_" + str(block[i])] = gamma
                        if not result.get("gamma"):
                            result["gamma"] = gamma
        elif block[BLOCK_TYPE] == BLOCK_TYPE_COLOR_MANAGEMENT_DATA:
            # TODO: Implement? How could it be used?
            result["color_management_data"] = block[
                BLOCK_CONTENTS[0] : BLOCK_CONTENTS[1]
            ]

    result["ext_flag"] = edid[EXTENSION_FLAG]
    result["checksum"] = edid[CHECKSUM]
    result["checksum_valid"] = sum(char for char in edid) % 256 == 0

    if len(edid) > 128 and result["ext_flag"] > 0:
        # Parse extension blocks
        block = edid[128:]
        while block:
            if block[0] == BLOCK_DI_EXT:
                if block[TRC[0]] != "\0":
                    # TODO: Implement
                    pass
            block = block[128:]

    return result


class WMIError(Exception):
    pass
