# -*- coding: utf-8 -*-

import os
import re
import subprocess
import sys
from typing import List

from DisplayCAL import argyll
from DisplayCAL import localization as lang
from DisplayCAL.util_dbus import DBusObject, DBusException, BUSTYPE_SESSION
from DisplayCAL.util_x import get_display as _get_x_display


_displays = None


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


class Display(object):
    """Store information about display."""

    def __init__(self):
        self.name = None
        """Display name."""
        self.description = None  # USED
        """Description of display or URL."""

        self.xrandr_name = None  # Generated from self.description

        self.pos = (0, 0)  # USED
        """Displays offset in pixel."""
        # self.sx = None
        # """Displays offset in pixels (X)."""
        # self.sy = None
        # """Displays offset in pixels (Y)."""

        self.size = (0, 0)  # USED
        """Displays width and height in pixels."""

        # WINDOWS / NT
        self.monid = None
        """Monitor ID."""
        self.prim = None
        """ NZ if primary display monitor."""

        # APPLE
        self.ddid = None

        # UNIX
        self.screen = None
        """X11 (possibly virtual) Screen."""
        self.uscreen = None
        """Underlying Xinerama/XRandr screen."""
        self.rscreen = None
        """Underlying RAMDAC screen (user override)."""
        self.icc_atom = None
        """ICC profile root/output atom for this display."""
        self.edid = None
        """128, 256 or 384 bytes of monitor EDID, NULL if none."""
        self.edid_len = None
        """128, 256 or 384."""

        # Xrandr stuff - output is connected 1:1 to a display
        self.crtc = None
        """Associated crtc."""
        self.output = None
        """Associated output."""
        self.icc_out_atom = None
        """ICC profile atom for this output."""

    def from_dispwin_data(self, display_info_line):
        """Parse from dispwin display list data.

        Args:
            display_info_line (str): The dispwin data line.
        """
        display_info_line = display_info_line.strip()
        description_data = re.findall(
            rb"[\s\d]+= '(?P<description>.*)'", display_info_line
        )
        dispwin_error_message = lang.getstr(
            "error.generic",
            (-1, "dispwin returns no usable data while enumerating displays."),
        )
        if not description_data:
            raise ValueError(dispwin_error_message)
        self.description = description_data[0]
        match = re.match(
            rb"[\s]*(?P<id>\d) = '(?P<name>.*), at (?P<x>\d+), (?P<y>[-\d]+), "
            rb"width (?P<width>\d+), height (?P<height>\d+).*'",
            display_info_line,
        )
        if not match:
            raise ValueError(dispwin_error_message)
        groups_dict = match.groupdict()
        self.monid = int(groups_dict["id"])
        self.name = groups_dict["name"]
        x = int(groups_dict["x"])
        y = int(groups_dict["y"])
        self.pos = (x, y)
        width = int(groups_dict["width"])
        height = int(groups_dict["height"])
        self.size = (width, height)

    def to_dict(self):
        """Return a dictionary.

        Returns:
            dict: The display data as dictionary, matching the previous implementation.
        """
        display_dict = {}
        if self.monid is not None:
            display_dict["monid"] = self.monid
        if self.description is not None:
            display_dict["description"] = self.description
        if self.name is not None:
            display_dict["name"] = self.name
        if self.pos is not None:
            display_dict["pos"] = self.pos
        if self.size is not None:
            display_dict["size"] = self.size

        return display_dict


def get_dispwin_output() -> bytes:
    """Return Argyll dispwin output.

    Returns:
        bytes: The dispwin output.
    """
    dispwin_path = argyll.get_argyll_util("dispwin")
    if dispwin_path is None:
        return b""

    if sys.platform == "win32":
        startupinfo = sp.STARTUPINFO()
        startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = sp.SW_HIDE
    else:
        startupinfo = None

    # the invalid value of "-d0" is intentional,
    # we just want to get the information we want and close the dispwin,
    # if we don't supply "-d0" it will start showing color patches.
    p = subprocess.Popen(
        [dispwin_path, "-v", "-d0"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        startupinfo=startupinfo,
    )
    output, _ = p.communicate()
    return output


def _enumerate_displays() -> List[dict]:
    """Generate display information data from ArgyllCMS's dispwin.

    Returns:
        List[dict]: A list of dictionary containing display data.
    """
    displays = []
    has_display = False
    dispwin_output = get_dispwin_output()
    for line in dispwin_output.split(b"\n"):
        if b"-dweb[:port]" in line:
            break
        if has_display:
            display = Display()
            display.from_dispwin_data(line)
            displays.append(display.to_dict())
        if b"-d n" in line:
            has_display = True

    return displays


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
    print(f"_displays (1): {_displays}")
    if _displays is None:
        enumerate_displays()
    print(f"_displays (2): {_displays}")
    # Translate from Argyll display index to enumerated display index
    # using the coordinates and dimensions
    from DisplayCAL.config import getcfg, is_virtual_display

    if is_virtual_display(display_no):
        print("This is a virtual display!")
        return

    try:
        print(f'getcfg("displays"): {getcfg("displays")}')
        print(f"display_no        : {display_no}")
        argyll_display = getcfg("displays")[display_no]
        print(f"argyll_display (1): {argyll_display}")
    except IndexError:
        return
    else:
        if argyll_display.endswith(" [PRIMARY]"):
            argyll_display = " ".join(argyll_display.split(" ")[:-1])
        print(f"argyll_display (2): {argyll_display}")
        for display in _displays:
            desc = display["description"]
            print(f"desc              : {desc}")
            if desc:
                geometry = b"".join(desc.split(b"@ ")[-1:])
                print(f"geometry          : {geometry}")
                print(f'argyll_display.endswith((b"@ " + geometry).decode("utf-8")): {argyll_display.endswith((b"@ " + geometry).decode("utf-8"))}')
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
