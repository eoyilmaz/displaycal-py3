# -*- coding: utf-8 -*-

import os
import platform
import re
import sys

from DisplayCAL.util_dbus import DBusObject, DBusException, BUSTYPE_SESSION
from DisplayCAL.util_x import get_display as _get_x_display

if sys.platform == "darwin":
    # Mac OS X has universal binaries in three flavors:
    # - i386 & PPC
    # - i386 & x86_64
    # - i386 & ARM
    if platform.architecture()[0].startswith("64"):
        # TODO: Intel vs ARM (Apple Silicon) distinction
        from DisplayCAL.lib64.RealDisplaySizeMM import *
else:
    # elif sys.platform == "win32":
    # Windows have separate files
    if sys.version_info[:2] == (3, 8):
        from DisplayCAL.lib64.python38.RealDisplaySizeMM import *
    elif sys.version_info[:2] == (3, 9):
        from DisplayCAL.lib64.python39.RealDisplaySizeMM import *
    elif sys.version_info[:2] == (3, 10):
        from DisplayCAL.lib64.python310.RealDisplaySizeMM import *
    elif sys.version_info[:2] == (3, 11):
        from DisplayCAL.lib64.python311.RealDisplaySizeMM import *
# else:
#     pass

# TODO: For Linux use the ``xrandr`` command output which supplies everything.
#
# ``xrandr --verbose`` gives all the info we need, including EDID which needs to
# be decoded:
#
# ```python
# import codecs
# edid = codecs.decode(xrandr_edid_data, "hex")
# ```
#


_displays = None

_GetXRandROutputXID = GetXRandROutputXID
_RealDisplaySizeMM = RealDisplaySizeMM
_enumerate_displays = enumerate_displays


def GetXRandROutputXID(display_no=0):
    """Return the XRandR output X11 ID of a given display.

    Args:
        display_no (int): Display number.

    Returns:
        dict:
    """
    display = get_display(display_no)
    if display:
        return display.get("output", 0)
    return 0


def RealDisplaySizeMM(display_no=0):
    """Return the size (in mm) of a given display.

    Args:
        display_no (int): Display number.

    Returns:
        (int, int): The display size in mm.
    """
    if display := get_display(display_no):
        return display.get("size_mm", (0, 0))
    return 0, 0


def enumerate_displays():
    """Enumerate and return a list of displays."""
    global _displays
    _displays = _enumerate_displays()
    for display in _displays:
        desc = display["description"]
        if desc:
            match = re.findall(
                rb"(.+?),? at (-?\d+), (-?\d+), width (\d+), height (\d+)", desc
            )
            if len(match):
                if sys.platform not in ("darwin", "win32"):
                    if (
                        os.getenv("XDG_SESSION_TYPE") == "wayland"
                        and "pos" in display
                        and "size" in display
                    ):
                        x, y, w, h = display["pos"] + display["size"]
                        wayland_display = get_wayland_display(x, y, w, h)
                        if wayland_display:
                            display.update(wayland_display)
                    else:
                        xrandr_name = re.search(rb", Output (.+)", match[0][0])
                        if xrandr_name:
                            display["xrandr_name"] = xrandr_name.group(1)
                desc = b"%s @ %s, %s, %sx%s" % match[0]
                display["description"] = desc
    return _displays


def get_display(display_no=0):
    if _displays is None:
        enumerate_displays()
    # Translate from Argyll display index to enumerated display index
    # using the coordinates and dimensions
    from DisplayCAL.config import getcfg, is_virtual_display

    if is_virtual_display(display_no):
        return
    try:
        argyll_display = getcfg("displays")[display_no]
    except IndexError:
        return
    else:
        if argyll_display.endswith(" [PRIMARY]"):
            argyll_display = " ".join(argyll_display.split(" ")[:-1])
        for display in _displays:
            if desc := display["description"]:
                geometry = b"".join(desc.split(b"@ ")[-1:])
                if argyll_display.endswith((b"@ " + geometry).decode("utf-8")):
                    return display


def get_wayland_display(x, y, w, h):
    """Find matching Wayland display.

    Given x, y, width and height of display geometry, find matching Wayland display.
    """
    # Note that we apparently CANNNOT use width and height
    # because the reported values from Argyll code and Mutter can be slightly
    # different, e.g. 3660x1941 from Mutter vs 3656x1941 from Argyll when
    # HiDPI is enabled. The xrandr output is also interesting in that case:
    # $ xrandr
    # Screen 0: minimum 320 x 200, current 3660 x 1941, maximum 8192 x 8192
    # XWAYLAND0 connected 3656x1941+0+0 (normal left inverted right x axis y axis) 0mm x 0mm
    #   3656x1941     59.96*+
    # Note the apparent mismatch between first and 2nd/3rd line.
    # Look for active display at x, y instead.
    # Currently, only support for GNOME3/Mutter
    try:
        iface = DBusObject(
            BUSTYPE_SESSION,
            "org.gnome.Mutter.DisplayConfig",
            "/org/gnome/Mutter/DisplayConfig",
        )
        res = iface.get_resources()
    except DBusException:
        pass
    else:
        # See
        # https://github.com/GNOME/mutter/blob/master/src/org.gnome.Mutter.DisplayConfig.xml
        output_storage = None
        try:
            found = False
            crtcs = res[1]
            # Look for matching CRTC
            for crtc in crtcs:
                if crtc[2:4] == (x, y) and crtc[6] != -1:
                    # Found our CRTC
                    crtc_id = crtc[0]
                    # Look for matching output
                    outputs = res[2]
                    for output in outputs:
                        if output[2] == crtc_id:
                            # Found our output
                            found = True
                            output_storage = output
                            break
                    if found:
                        break
            if found and output_storage is not None:
                properties = output_storage[7]
                wayland_display = {"xrandr_name": output_storage[4]}
                raw_edid = properties.get("edid", ())
                edid = b"".join(v.to_bytes(1, "big") for v in raw_edid)

                if edid:
                    wayland_display["edid"] = edid
                w_mm = properties.get("width-mm")
                h_mm = properties.get("height-mm")
                if w_mm and h_mm:
                    wayland_display["size_mm"] = (w_mm, h_mm)
                return wayland_display
        except (IndexError, KeyError):
            pass


def get_x_display(display_no=0):
    if display := get_display(display_no):
        if name := display.get("name"):
            return _get_x_display(name)


def get_x_icc_profile_atom_id(display_no=0):
    if display := get_display(display_no):
        return display.get("icc_profile_atom_id")


def get_x_icc_profile_output_atom_id(display_no=0):
    if display := get_display(display_no):
        return display.get("icc_profile_output_atom_id")
