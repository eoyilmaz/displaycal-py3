"""Utilities for retrieving and managing display information.

It supports various platforms and integrates with ArgyllCMS's `dispwin` tool to
enumerate displays and extract detailed display data.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

from DisplayCAL import argyll
from DisplayCAL import localization as lang
from DisplayCAL.util_dbus import BUSTYPE_SESSION, DBusException, DBusObject
from DisplayCAL.util_x import get_display as _get_x_display

_displays = None


def get_xrandr_output_xid(display_no: int = 0) -> int:
    """Return the XRandR output X11 ID of a given display.

    Args:
        display_no (int): Display number.

    Returns:
        int: The XRandR output X11 ID or 0 if not found.
    """
    display = get_display(display_no)
    if display:
        return display.get("output", 0)
    return 0


def real_display_size_mm(display_no: int = 0) -> tuple[int, int]:
    """Return the size (in mm) of a given display.

    Args:
        display_no (int): Display number.

    Returns:
        (int, int): The display size in mm.
    """
    if display := get_display(display_no):
        return display.get("size_mm", (0, 0))
    return 0, 0


class Display:
    """Store information about display."""

    def __init__(self) -> None:
        self.name = None
        """Display name."""
        self.description = None  # USED
        """Description of display or URL."""

        self.xrandr_name = None  # Generated from self.description

        self.pos = (0, 0)  # USED
        """Display offset in pixel."""
        # self.sx = None
        # """Display offset in pixels (X)."""
        # self.sy = None
        # """Display offset in pixels (Y)."""

        self.size = (0, 0)  # USED
        """Display width and height in pixels."""

        # WINDOWS / NT
        self.monitor_id = None
        """Monitor ID."""
        self.prim = None
        """ NZ if primary display monitor."""

        # APPLE
        self.display_device_id = None

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

    def from_dispwin_data(self, display_info_line: str) -> None:
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
            rb"[\s]*(?P<id>\d) = '(?P<name>.*) at (?P<x>[-\d]+), (?P<y>[-\d]+), "
            rb"width (?P<width>\d+), height (?P<height>\d+).*'",
            display_info_line,
        )
        if not match:
            raise ValueError(dispwin_error_message)
        groups_dict = match.groupdict()
        self.monitor_id = int(groups_dict["id"])
        self.name = groups_dict["name"]
        # fix the name ending with "," for ArgyllCMS<3.3.0
        if self.name.endswith(b","):
            self.name = self.name[:-1]
        x = int(groups_dict["x"])
        y = int(groups_dict["y"])
        self.pos = (x, y)
        width = int(groups_dict["width"])
        height = int(groups_dict["height"])
        self.size = (width, height)

    def to_dict(self) -> dict:
        """Return a dictionary.

        Returns:
            dict: The display data as dictionary, matching the previous
                implementation.
        """
        display_dict = {}
        if self.monitor_id is not None:
            display_dict["monid"] = self.monitor_id
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
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
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


def _enumerate_displays() -> list[dict]:
    """Generate display information data from ArgyllCMS's dispwin.

    Returns:
        list[dict]: A list of dictionary containing display data.
    """
    displays = []
    has_display = False
    dispwin_output = get_dispwin_output()
    for line in dispwin_output.split(b"\n"):
        if has_display and b"-dweb[:port]" in line:
            break
        if has_display and b"=" in line:
            display = Display()
            display.from_dispwin_data(line)
            displays.append(display.to_dict())
        if not has_display and b"-d n" in line:
            has_display = True

    return displays


def enumerate_displays() -> list[dict]:
    """Enumerate and return a list of displays.

    Returns:
        list[dict]: A list of dictionary containing display data.
    """
    global _displays
    _displays = _enumerate_displays()

    if _displays is None:
        _displays = []

    for display in _displays:
        desc = display.get("description")
        if not desc:
            continue
        match = re.findall(
            rb"(.+?),? at (-?\d+), (-?\d+), width (\d+), height (\d+)", desc
        )
        if not len(match):
            continue

        # update xrandr_name from description
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


def get_display(display_no: int = 0) -> None | dict:
    """Return display data for a given display number.

    Args:
        display_no (int): Display number.

    Returns:
        None | dict: The display data.
    """
    if _displays is None:
        enumerate_displays()

    # Ensure _displays is not None after calling enumerate_displays
    if _displays is None:
        return None

    # Translate from Argyll display index to enumerated display index using the
    # coordinates and dimensions
    from DisplayCAL.config import getcfg, is_virtual_display

    if is_virtual_display(display_no):
        return None

    getcfg_displays = getcfg("displays")
    if len(getcfg_displays) < display_no:
        return None

    argyll_display = getcfg_displays[display_no]

    if argyll_display.endswith(" [PRIMARY]"):
        argyll_display = " ".join(argyll_display.split(" ")[:-1])

    for display in _displays:
        desc = display.get("description")
        if not desc:
            continue
        geometry = b"".join(desc.split(b"@ ")[-1:])
        if argyll_display.endswith((b"@ " + geometry).decode("utf-8")):
            return display
    return None


def get_wayland_display(x: int, y: int, w: int, h: int) -> None | dict:
    """Find matching Wayland display.

    Given x, y, width and height of display geometry, find matching Wayland display.

    Args:
        x (int): X position.
        y (int): Y position.
        w (int): Width.
        h (int): Height.

    Returns:
        None | dict: The Wayland display data.
    """
    # Note that we apparently CANNOT use width and height because the reported
    # values from Argyll code and Mutter can be slightly different,
    # e.g. 3660x1941 from Mutter vs 3656x1941 from Argyll when HiDPI is enabled.
    # The xrandr output is also interesting in that case:
    # $ xrandr
    # Screen 0: minimum 320 x 200, current 3660 x 1941, maximum 8192 x 8192
    # XWAYLAND0 connected 3656x1941+0+0 (normal left inverted right x axis y axis) 0mm x 0mm,B950  # noqa: E501
    #   3656x1941     59.96*+
    # Note the apparent mismatch between first and 2nd/3rd line.
    # Look for active display at x, y instead.
    # Currently, only support for GNOME 3 / Mutter
    try:
        iface = DBusObject(
            BUSTYPE_SESSION,
            "org.gnome.Mutter.DisplayConfig",
            "/org/gnome/Mutter/DisplayConfig",
        )
        res = iface.get_resources()
    except DBusException:
        return None

    if not res or len(res) < 2:
        return None

    # See
    # https://github.com/GNOME/mutter/blob/master/src/org.gnome.Mutter.DisplayConfig.xml
    output_storage = None
    found = False
    crtcs = res[1]
    # Look for matching CRTC
    for crtc in crtcs:
        if len(crtc) < 7 or crtc[2:4] != (x, y) or crtc[6] == -1:
            continue

        # Found our CRTC
        crtc_id = crtc[0]
        # Look for matching output
        outputs = res[2]
        for output in outputs:
            if len(output) < 2:
                continue
            if output[2] == crtc_id:
                # Found our output
                found = True
                output_storage = output
                break
        if found:
            break

    if found and output_storage is not None and len(output_storage) > 7:
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
    return None


def get_x_screen_size() -> tuple[int, int, int, int] | None:
    """Return the X screen's size in pixels and millimetres.

    ArgyllCMS sizes its X11 test window from the X screen's size in mm, not
    from the size of the monitor the window is on, so the measure frame has to
    use the same density for the scale it passes to ``-P`` to match. XWayland
    always reports 96 DPI here, whatever the monitors' real sizes are.

    Returns:
        tuple[int, int, int, int] | None: Width and height in pixels, then
        width and height in millimetres, or None if there is no X display to
        ask (e.g. on macOS and Windows).
    """
    if sys.platform in ("darwin", "win32") or not os.getenv("DISPLAY"):
        return None
    try:
        from DisplayCAL import xrandr

        with xrandr.XDisplay() as x_display:
            return x_display.screen_size(_get_x_display()[2])
    except (ImportError, ValueError):
        return None


def get_x_screen_px_per_mm() -> tuple[float, float] | None:
    """Return the X screen's horizontal and vertical pixels per mm.

    ArgyllCMS sizes its X11 test window from the X screen's size in mm, not
    from the size of the monitor the window is on, so the measure frame has to
    use the same density for the scale it passes to ``-P`` to match. XWayland
    always reports 96 DPI here, whatever the monitors' real sizes are.

    Returns:
        tuple[float, float] | None: The pixels per mm, or None if there is no
        X display to ask (e.g. on macOS and Windows).
    """
    size = get_x_screen_size()
    if size is None:
        return None
    width, height, width_mm, height_mm = size
    if not (width_mm and height_mm):
        return None
    return width / width_mm, height / height_mm


def get_x_display(display_no: int = 0) -> None | str:
    """Get the X display name for a given display number.

    Args:
        display_no (int): Display number.

    Returns:
        None | str: The X display name.
    """
    if (display := get_display(display_no)) and (name := display.get("name")):
        return _get_x_display(name)
    return None


def get_x_icc_profile_atom_id(display_no: int = 0) -> None | int:
    """Get the ICC profile atom ID for a given display number.

    Args:
        display_no (int): Display number.

    Returns:
        None | int: The ICC profile atom ID.
    """
    display = get_display(display_no)
    return display.get("icc_profile_atom_id") if display else None


def get_x_icc_profile_output_atom_id(display_no: int = 0) -> None | int:
    """Get the ICC profile output atom ID for a given display number.

    Args:
        display_no (int): Display number.

    Returns:
        None | int: The ICC profile output atom ID.
    """
    display = get_display(display_no)
    return display.get("icc_profile_output_atom_id") if display else None
