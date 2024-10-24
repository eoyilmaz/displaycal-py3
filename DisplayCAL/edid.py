# -*- coding: utf-8 -*-
"""
edid.py.

This module provides functionality for retrieving and parsing EDID
(Extended Display Identification Data) from various operating systems.
It includes methods for fetching EDID data from Windows, macOS,
and other platforms, as well as parsing the EDID data into a structured format.

Functions:
    get_edid(display_no=0, display_name=None, device=None):
        Get and parse EDID. Return dict.

    get_edid_windows(display_no, device):
        Get EDID for a Windows display.

    get_edid_windows_wmi(id, wmi_connection, not_main_thread):
        Get EDID using WMI for Windows Vista/Win7.

    get_edid_windows_registry(id, device):
        Get EDID using the Windows registry for Win2k/XP/2003.

    get_edid_darwin(display_name):
        Get EDID via ioreg on macOS.

    get_edid_rdsmm(display_no):
        Get EDID using RealDisplaySizeMM module.

    parse_manufacturer_id(block):
        Parse the manufacturer id and return decoded string.

    get_manufacturer_name(manufacturer_id):
        Try and get a nice descriptive string for our manufacturer id.

    load_pnpidcache():
        Load the pnpidcache from various possible locations.

    get_pnpid_paths():
        Get the list of possible paths for the pnp.ids file.

    parse_pnpid_file(pnp_ids, path):
        Parse the pnp.ids file and populate the pnpidcache.

    parse_hwdb_line(line):
        Parse a line from the hwdb file.

    parse_pnpid_line(line):
        Parse a line from the pnp.ids file.

    edid_get_bit(value, bit):
        Get the bit value at the specified position.

    edid_get_bits(value, begin, end):
        Get the bits from the specified range.

    edid_decode_fraction(high, low):
        Decode a fraction from high and low bits.

    edid_parse_string(desc):
        Parse a string from EDID data.

    parse_edid(edid):
        Parse raw EDID data (binary string) and return dict.

    fix_edid_encoding(edid):
        Fix the encoding of EDID data.

    ensure_bytes(edid):
        Ensure that the EDID data is in bytes.

    parse_edid_header(edid):
        Parse the EDID header.

    parse_edid_basic_display_parameters(edid):
        Parse the basic display parameters from the EDID data.

    parse_edid_chromaticity_coordinates(edid):
        Parse the chromaticity coordinates from the EDID data.

    parse_edid_descriptor_blocks(edid):
        Parse the descriptor blocks from the EDID data.

    parse_color_point_data(block):
        Parse the color point data from the EDID data.

    parse_edid_extension_blocks(edid):
        Parse the extension blocks from the EDID data.

Classes:
    WMIError:
        Custom exception for WMI errors.
"""
import binascii
import codecs
import math
import os
import re
import string
import struct
import subprocess
import sys

from hashlib import md5

from DisplayCAL import config
from DisplayCAL.util_str import safe_str

if sys.platform == "win32":
    from DisplayCAL import util_win
    import pythoncom
    import threading

    # Use registry as fallback for Win2k/XP/2003
    import winreg

    wmi = None
    if sys.getwindowsversion() >= (6,):
        # Use WMI for Vista/Win7
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
    """
    Combine two 8-bit values into a single 16-bit value.

    Args:
        hi (int): The high byte.
        lo (int): The low byte.

    Returns:
        int: The combined 16-bit value.
    """
    return hi << 8 | lo


def get_edid(display_no=0, display_name=None, device=None):
    """
    Get and parse EDID. Return dict.

    On Mac OS X, you need to specify a display name.
    On all other platforms, you need to specify a display number (zero-based).
    Args:
        display_no (int): The display number (zero-based).
        display_name (str): The display name (for Mac OS X).
        device (str): The device identifier.

    Returns:
        dict: Parsed EDID data.
    """
    edid = None
    if sys.platform == "win32":
        edid = get_edid_windows(display_no, device)
    elif sys.platform == "darwin":
        edid = get_edid_darwin(display_name)
    elif RDSMM:
        edid = get_edid_rdsmm(display_no)

    if edid and len(edid) >= 128:
        return parse_edid(edid)

    return {}


def get_edid_windows(display_no, device):
    """Get EDID for a Windows display.

    Args:
        display_no (int): The display number (zero-based).
        device (str): The device identifier.

    Returns:
        bytes: The EDID data.

    Raises:
        WMIError: If there is an error with WMI.
    """
    edid = None

    if not device:
        # The ordering will work as long as Argyll continues using EnumDisplayMonitors
        monitors = util_win.get_real_display_devices_info()
        moninfo = monitors[display_no]
        device = util_win.get_active_display_device(moninfo["Device"])

    if not device:
        return None

    id = device.DeviceID.split("\\")[1]
    wmi_connection = None
    not_main_thread = not isinstance(threading.current_thread(), threading.Thread)

    if wmi:
        if not_main_thread:
            pythoncom.CoInitialize()
        wmi_connection = wmi.WMI(namespace="WMI")

    if wmi_connection:
        return get_edid_windows_wmi(id, wmi_connection, not_main_thread)
    elif sys.getwindowsversion() < (6,):
        return get_edid_windows_registry(id, device)
    else:
        raise WMIError("No WMI connection")

    return edid


def get_edid_windows_wmi(id, wmi_connection, not_main_thread):
    """Get EDID using WMI for Windows Vista/Win7.

    Args:
        id (str): The device ID.
        wmi_connection (wmi.WMI): The WMI connection.
        not_main_thread (bool): Whether the current thread is not the main thread.

    Returns:
        bytes: The EDID data.

    Raises:
        WMIError: If there is an error with WMI.
    """
    edid = None

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

    return edid


def get_edid_windows_registry(id, device):
    """
    Get EDID using the Windows registry for Win2k/XP/2003.

    Args:
        id (str): The device ID.
        device (str): The device identifier.

    Returns:
        bytes: The EDID data.
    """
    edid = None

    # http://msdn.microsoft.com/en-us/library/ff546173%28VS.85%29.aspx
    # "The Enum tree is reserved for use by operating system components,
    #  and its layout is subject to change. (...)
    #  Drivers and Windows applications must not access the Enum tree directly."
    # But do we care?
    # Probably not, as older Windows' API isn't likely gonna change.
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
        return None

    numsubkeys, numvalues, mtime = winreg.QueryInfoKey(key)

    for i in range(numsubkeys):
        hkname = winreg.EnumKey(key, i)
        hk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "\\".join([subkey, hkname]))

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
                        ["HKEY_LOCAL_MACHINE", subkey, hkname, "Device Parameters"]
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
                return edid

    return edid


def get_edid_darwin(display_name):
    """Get EDID via ioreg on macOS.

    Args:
        display_name (str): The display name.

    Returns:
        dict: Parsed EDID data.
    """
    p = subprocess.Popen(
            ["ioreg", "-c", "IODisplay", "-S", "-w0"], stdout=subprocess.PIPE
        )
    stdout, stderr = p.communicate()

    if not stdout:
        return {}
    else:
        display = RDSMM.get_display(display_no)
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
            # On Mac OS X, you need to specify a display name because
            # the order is unknown
            return parsed_edid

    return {}


def get_edid_rdsmm(display_no):
    """
    Get EDID using RealDisplaySizeMM module.

    Args:
        display_no (int): The display number (zero-based).

    Returns:
        bytes: The EDID data.
    """
    if RDSMM is None:
        warnings.warn(
            "RealDisplaySizeMM module is not available.", Warning, stacklevel=2
        )
        return None

    display = RDSMM.get_display(display_no)
    if display:
        return display.get("edid")
    return None


def parse_manufacturer_id(block):
    """
    Parse the manufacturer id and return decoded string.

    The range is always ASCII charcode 64 to 95.

    Args:
        block (bytes): The block containing the manufacturer ID.

    Returns:
        str: The decoded manufacturer ID.
    """
    h = combine_hi_8lo(block[0], block[1])
    manufacturer_id = []
    for shift in (10, 5, 0):
        manufacturer_id.append(chr(((h >> shift) & 0x1F) + ord("A") - 1))
    return "".join(manufacturer_id).strip()


def get_manufacturer_name(manufacturer_id):
    """
    Try and get a nice descriptive string for our manufacturer id.

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

    Args:
        manufacturer_id (str): The manufacturer ID.

    Returns:
        str: The descriptive manufacturer name.
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
        load_pnpidcache()
    return pnpidcache.get(manufacturer_id)


def load_pnpidcache():
    """Load the pnpidcache from various possible locations."""
    paths = get_pnpid_paths()
    for path in paths:
        if os.path.isfile(path):
            try:
                with codecs.open(path, "r", "UTF-8", "replace") as pnp_ids:
                    parse_pnpid_file(pnp_ids, path)
                break
            except IOError:
                continue


def get_pnpid_paths():
    """Get the list of possible paths for the pnp.ids file.

    Returns:
        list: List of possible paths.
    """
    paths = [
        "/usr/lib/udev/hwdb.d/20-acpi-vendor.hwdb",  # systemd
        "/usr/share/hwdata/pnp.ids",  # hwdata, e.g. Red Hat
        "/usr/share/misc/pnp.ids",  # pnputils, e.g. Debian
        "/usr/share/libgnome-desktop/pnp.ids",
    ]  # fallback gnome-desktop
    if sys.platform in ("darwin", "win32"):
        # fallback
        paths.append(os.path.join(config.pydir, "pnp.ids"))
        # fallback for tests
        paths.append(os.path.join(config.pydir, "DisplayCAL", "pnp.ids"))
    return paths


def parse_pnpid_file(pnp_ids, path):
    """Parse the pnp.ids file and populate the pnpidcache.

    Args:
        pnp_ids (file): The pnp.ids file.
        path (str): The path to the pnp.ids file.
    """
    id, name = None, None
    for line in pnp_ids:
        if path.endswith("hwdb"):
            id, name = parse_hwdb_line(line)
        else:
            id, name = parse_pnpid_line(line)
        if id and name and id not in pnpidcache:
            pnpidcache[id] = name


def parse_hwdb_line(line):
    """
    Parse a line from the hwdb file.

    Args:
        line (str): The line to parse.

    Returns:
        tuple: The parsed ID and name.
    """
    id, name = None, None
    if line.strip().startswith("acpi:"):
        id = line.split(":")[1][:3]
    elif line.strip().startswith("ID_VENDOR_FROM_DATABASE"):
        name = line.split("=", 1)[1].strip()
    return id, name


def parse_pnpid_line(line):
    """
    Parse a line from the pnp.ids file.

    Args:
        line (str): The line to parse.

    Returns:
        tuple: The parsed ID and name.
    """
    try:
        # Strip leading/trailing whitespace
        # (non-breaking spaces too)
        id, name = line.strip(string.whitespace + "\u00a0").split(None, 1)
    except ValueError:
        id, name = None, None
    return id, name


def edid_get_bit(value, bit):
    """
    Get the bit value at the specified position.

    Args:
        value (int): The value to extract the bit from.
        bit (int): The bit position.

    Returns:
        int: The bit value.
    """
    return (value & (1 << bit)) >> bit


def edid_get_bits(value, begin, end):
    """
    Get the bits from the specified range.

    Args:
        value (int): The value to extract the bits from.
        begin (int): The starting bit position.
        end (int): The ending bit position.

    Returns:
        int: The extracted bits.
    """
    mask = (1 << (end - begin + 1)) - 1
    return (value >> begin) & mask


def edid_decode_fraction(high, low):
    """
    Decode a fraction from high and low bits.

    Args:
        high (int): The high bits.
        low (int): The low bits.

    Returns:
        float: The decoded fraction.
    """
    result = 0.0
    high = (high << 2) | low
    for i in range(0, 10):
        result += edid_get_bit(high, i) * math.pow(2, i - 10)
    return result


def edid_parse_string(desc):
    """
    Parse a string from EDID data.

    Args:
        desc (bytes): The description to parse.

    Returns:
        bytes: The parsed string.
    """
    # Return value should match colord's cd_edid_parse_string in cd-edid.c
    # Remember: In C, NULL terminates a string, so do the same here
    # Replace newline with NULL
    desc = desc[:13].replace(b"\n", b"\x00").replace(b"\r", b"\x00")

    # Strip anything after the first NULL byte (if any)
    null_index: int = desc.find(b"\x00")
    if null_index != -1:
        desc = desc[:null_index]

    # Strip trailing whitespace
    desc = desc.rstrip()

    # Replace all non-printable chars with NULL
    desc = bytearray(desc)
    non_printable_count = 0
    for i in range(len(desc)):
        if desc[i] < 32 or desc[i] > 126:
            desc[i] = 0
            non_printable_count += 1

    # Only use string if max 4 replaced chars
    if non_printable_count <= 4:

        # Replace any NULL chars with dashes to make a printable string
        desc = desc.replace(b"\x00", b"-")
        return bytes(desc)


def parse_edid(edid):
    """
    Parse raw EDID data (binary string) and return dict.

    Args:
        edid (bytes): The raw EDID data.

    Returns:
        dict: The parsed EDID data.
    """
    if len(edid) not in [128, 256, 384]:
        edid = fix_edid_encoding(edid)

    edid = ensure_bytes(edid)

    result = parse_edid_header(edid)
    result.update(parse_edid_basic_display_parameters(edid))
    result.update(parse_edid_chromaticity_coordinates(edid))
    result.update(parse_edid_descriptor_blocks(edid))
    result.update(parse_edid_extension_blocks(edid))

    return result


def fix_edid_encoding(edid):
    """
    Fix the encoding of EDID data.

    Args:
        edid (bytes): The EDID data to fix.

    Returns:
        bytes: The fixed EDID data.
    """
    # this is probably encoded/decoded in a wrong way and contains 2-bytes characters
    #
    # b"\xc2" and b"\xc3" are codepoints
    # they can only appear if the byte data is decoded with latin-1 and encoded
    # back with utf-8.
    # This apparently is a wrong conversion.
    if b"\xc2" in edid or b"\xc3" in edid:
        edid = edid.decode("utf-8").encode("latin-1")
    return edid


def ensure_bytes(edid):
    """
    Ensure that the EDID data is in bytes.

    Args:
        edid (bytes or str): The EDID data.

    Returns:
        bytes: The EDID data as bytes.
    """
    if isinstance(edid, str):
        edid = edid.encode("latin-1")
    return edid


def parse_edid_header(edid):
    """
    Parse the EDID header.

    Args:
        edid (bytes): The raw EDID data.

    Returns:
        dict: The parsed EDID header.
    """
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
    return result


def parse_edid_basic_display_parameters(edid):
    """
    Parse the basic display parameters from the EDID data.

    Args:
        edid (bytes): The raw EDID data.

    Returns:
        dict: The parsed basic display parameters.
    """
    result = {
        "product_id": struct.unpack("<H", edid[PRODUCT_ID[0] : PRODUCT_ID[1]])[0],
        "serial_32": struct.unpack("<I", edid[SERIAL_32[0] : SERIAL_32[1]])[0],
        "week_of_manufacture": edid[WEEK_OF_MANUFACTURE],
        "year_of_manufacture": edid[YEAR_OF_MANUFACTURE] + 1990,
        "edid_version": edid[EDID_VERSION],
        "edid_revision": edid[EDID_REVISION],
        "max_h_size_cm": edid[MAX_H_SIZE_CM],
        "max_v_size_cm": edid[MAX_V_SIZE_CM],
    }
    if edid[GAMMA] != b"\xff":
        result["gamma"] = edid[GAMMA] / 100.0 + 1
    result["features"] = edid[FEATURES]
    return result


def parse_edid_chromaticity_coordinates(edid):
    """
    Parse the chromaticity coordinates from the EDID data.

    Args:
        edid (bytes): The raw EDID data.

    Returns:
        dict: The parsed chromaticity coordinates.
    """
    result = {
        "red_x": edid_decode_fraction(
            edid[HI_R_X], edid_get_bits(edid[LO_RG_XY], 6, 7)
        ),
        "red_y": edid_decode_fraction(
            edid[HI_R_Y], edid_get_bits(edid[LO_RG_XY], 4, 5)
        ),
        "green_x": edid_decode_fraction(
            edid[HI_G_X], edid_get_bits(edid[LO_RG_XY], 2, 3)
        ),
        "green_y": edid_decode_fraction(
            edid[HI_G_Y], edid_get_bits(edid[LO_RG_XY], 0, 1)
        ),
        "blue_x": edid_decode_fraction(
            edid[HI_B_X], edid_get_bits(edid[LO_BW_XY], 6, 7)
        ),
        "blue_y": edid_decode_fraction(
            edid[HI_B_Y], edid_get_bits(edid[LO_BW_XY], 4, 5)
        ),
        "white_x": edid_decode_fraction(
            edid[HI_W_X], edid_get_bits(edid[LO_BW_XY], 2, 3)
        ),
        "white_y": edid_decode_fraction(
            edid[HI_W_Y], edid_get_bits(edid[LO_BW_XY], 0, 1)
        ),
    }
    return result


def parse_edid_descriptor_blocks(edid):
    """Parse the descriptor blocks from the EDID data.

    Args:
        edid (bytes): The raw EDID data.

    Returns:
        dict: The parsed descriptor blocks.
    """
    text_types = {
        BLOCK_TYPE_SERIAL_ASCII: "serial_ascii",
        BLOCK_TYPE_ASCII: "ascii",
        BLOCK_TYPE_MONITOR_NAME: "monitor_name",
    }
    result = {}
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
            result.update(parse_color_point_data(block))
        elif block[BLOCK_TYPE] == BLOCK_TYPE_COLOR_MANAGEMENT_DATA:
            # TODO: Implement? How could it be used?
            result["color_management_data"] = block[
                BLOCK_CONTENTS[0] : BLOCK_CONTENTS[1]
            ]
    return result


def parse_color_point_data(block):
    """
    Parse the color point data from the EDID data.

    Args:
        block (bytes): The block containing the color point data.

    Returns:
        dict: The parsed color point data.
    """
    result = {}
    for i in (5, 10):
        # 2nd white point index in range 1...255
        # 3rd white point index in range 2...255
        # 0 = do not use
        if block[i] > i / 5:
            white_x = edid_decode_fraction(
                block[i + 2], edid_get_bits(block[i + 1], 2, 3)
            )
            result["white_x_" + str(block[i])] = white_x
            if "white_x" not in result:
                result["white_x"] = white_x
            white_y = edid_decode_fraction(
                block[i + 3], edid_get_bits(block[i + 1], 0, 1)
            )
            result["white_y_" + str(block[i])] = white_y
            if "white_y" not in result:
                result["white_y"] = white_y
            if block[i + 4] != "\xff":
                gamma = block[i + 4] / 100.0 + 1
                result["gamma_" + str(block[i])] = gamma
                if "gamma" not in result:
                    result["gamma"] = gamma
    return result


def parse_edid_extension_blocks(edid):
    """
    Parse the extension blocks from the EDID data.

    Args:
        edid (bytes): The raw EDID data.

    Returns:
        dict: The parsed extension blocks.
    """
    result = {
        "ext_flag": edid[EXTENSION_FLAG],
        "checksum": edid[CHECKSUM],
        "checksum_valid": sum(char for char in edid) % 256 == 0,
    }
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
    """Custom exception for WMI errors."""

    pass
