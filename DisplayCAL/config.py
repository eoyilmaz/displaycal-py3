"""Runtime configuration and user settings parser."""

from __future__ import annotations

import configparser
import contextlib
import locale
import math
import os
import re
import string
import sys
from decimal import Decimal
from typing import TYPE_CHECKING

if sys.platform == "win32":
    pass

from DisplayCAL import colormath
from DisplayCAL.argyll_names import INTENTS, OBSERVERS, VIDEO_ENCODINGS, VIEWCONDS

if sys.platform == "win32":
    from DisplayCAL.defaultpaths import COMMON_PROGRAM_FILES
elif sys.platform == "darwin":
    from DisplayCAL.defaultpaths import LIBRARY, LIBRARY_HOME, PREFS, PREFS_HOME
else:
    from DisplayCAL.defaultpaths import (
        XDG_CONFIG_DIR_DEFAULT,
        XDG_CONFIG_HOME,
        XDG_DATA_DIRS,
        XDG_DATA_HOME,
        XDG_DATA_HOME_DEFAULT,
    )

from DisplayCAL.defaultpaths import (  # noqa: F401
    APPDATA,
    AUTOSTART,  # don't remove this, imported by other modules
    AUTOSTART_HOME,  # don't remove this, imported by other modules
    COMMONAPPDATA,
    HOME,  # don't remove this, imported by other modules
    ICCPROFILES,
    ICCPROFILES_HOME,
)
from DisplayCAL.meta import (  # noqa: F401
    BUILD,  # don't remove this, imported by other modules
    VERSION_STRING,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.options import DEBUG
from DisplayCAL.safe_print import (  # noqa: F401
    ENC,  # don't remove this, imported by other modules
    FS_ENC,
)
from DisplayCAL.util_io import StringIOu as StringIO
from DisplayCAL.util_os import (
    expanduseru,
    getenvu,
    is_superuser,
    listdir_re,
    which,
)
from DisplayCAL.util_str import create_replace_function, strtr

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL.wx_addons import wx

configparser.DEFAULTSECT = "Default"  # Sadly, this line needs to be here.

EXE = sys.executable
EXEDIR = os.path.dirname(EXE)
EXENAME = os.path.basename(EXE)

ISEXE = sys.platform != "darwin" and getattr(sys, "frozen", False)

if ISEXE and (_meipass2 := os.getenv("_MEIPASS2")):
    os.environ["_MEIPASS2"] = _meipass2.replace("/", os.path.sep)

PYFILE = (
    EXE
    if ISEXE
    else (os.path.isfile(sys.argv[0]) and sys.argv[0])
    or os.path.join(os.path.dirname(__file__), "main.py")
)
PYPATH = EXE if ISEXE else os.path.abspath(PYFILE)
# Mac OS X: isapp should only be true for standalone, not 0install
ISAPP = (
    sys.platform == "darwin"
    and EXE.split(os.path.sep)[-3:-1] == ["Contents", "MacOS"]
    and os.path.exists(os.path.join(EXEDIR, "..", "Resources", "xrc"))
)
if ISAPP:
    PYNAME, PYEXT = os.path.splitext(EXE.split(os.path.sep)[-4])
    PYDIR = os.path.normpath(os.path.join(EXEDIR, "..", "Resources"))
else:
    PYNAME, PYEXT = os.path.splitext(os.path.basename(PYPATH))
    PYDIR = os.path.dirname(
        EXE if ISEXE else os.path.abspath(os.path.dirname(__file__))
    )

# TODO: Modifying ``data_dirs`` here was not an elegant solution,
#       and it is not solving the problem either.
DATA_DIRS = [
    # venv/share/DisplayCAL
    os.path.join(os.path.dirname(os.path.dirname(PYPATH)), "share", "DisplayCAL"),
    # venv/lib/python3.x/site-packages/DisplayCAL
    PYDIR,
    # venv/share
    os.path.join(os.path.dirname(PYDIR), "share"),
    # venv/lib/python3.x/site-packages/DisplayCAL-*.egg/share/DisplayCAL
    os.path.join(os.path.dirname(PYDIR), "share", "DisplayCAL"),
]


EXTRA_DATA_DIRS = []
# Search directories on PATH for data directories so Argyll reference files can
# be found automatically if Argyll directory not explicitly configured
for dir_ in getenvu("PATH", "").split(os.pathsep):
    dir_parent = os.path.dirname(dir_)
    if os.path.isdir(os.path.join(dir_parent, "ref")):
        EXTRA_DATA_DIRS.append(dir_parent)

APPBASENAME = APPNAME
# If old user data directory exists, use its basename
if os.path.isdir(os.path.join(APPDATA, "dispcalGUI")):
    APPBASENAME = "dispcalGUI"
    DATA_DIRS.append(os.path.join(APPDATA, APPNAME))
DATA_HOME = os.path.join(APPDATA, APPBASENAME)
if sys.platform == "win32":
    if PYDIR.lower().startswith(EXEDIR.lower()) and PYDIR != EXEDIR:
        # We are installed in a subfolder of the executable directory
        # (e.g. C:\Python26\Lib\site-packages\DisplayCAL)
        # we need to add the executable directory to the data directories so
        # files in subfolders of the executable directory which are not in
        # Lib\site-packages\DisplayCAL can be found
        # (e.g. Scripts\displaycal-apply-profiles)
        DATA_DIRS.append(EXEDIR)
    SCRIPT_EXT = ".cmd"
    SCALE_ADJUSTMENT_FACTOR = 1.0
    CONFIG_SYS = os.path.join(COMMONAPPDATA[0], APPBASENAME)
    CONFIG_HOME = os.path.join(APPDATA, APPBASENAME)
    LOGDIR = os.path.join(DATA_HOME, "logs")
    if APPBASENAME != APPNAME:
        DATA_DIRS.extend(os.path.join(dir_, APPNAME) for dir_ in COMMONAPPDATA)
        DATA_DIRS.append(os.path.join(COMMON_PROGRAM_FILES, APPNAME))
    DATA_DIRS.append(DATA_HOME)
    DATA_DIRS.extend(os.path.join(dir_, APPBASENAME) for dir_ in COMMONAPPDATA)
    DATA_DIRS.append(os.path.join(COMMON_PROGRAM_FILES, APPBASENAME))
    EXE_EXT = ".exe"
    PROFILE_EXT = ".icm"
elif sys.platform == "darwin":
    SCRIPT_EXT = ".command"
    MAC_CREATE_APP = True
    SCALE_ADJUSTMENT_FACTOR = 1.0
    CONFIG_SYS = os.path.join(PREFS, APPBASENAME)
    CONFIG_HOME = os.path.join(PREFS_HOME, APPBASENAME)
    LOGDIR = os.path.join(expanduseru("~"), "Library", "Logs", APPBASENAME)
    if APPBASENAME != APPNAME:
        DATA_DIRS.append(os.path.join(COMMONAPPDATA[0], APPNAME))
    DATA_DIRS.append(DATA_HOME)
    DATA_DIRS.append(os.path.join(COMMONAPPDATA[0], APPBASENAME))
    EXE_EXT = ""
    PROFILE_EXT = ".icc"
else:  # Linux
    SCRIPT_EXT = ".sh"
    SCALE_ADJUSTMENT_FACTOR = 1.0
    CONFIG_SYS = os.path.join(XDG_CONFIG_DIR_DEFAULT, APPBASENAME)
    CONFIG_HOME = os.path.join(XDG_CONFIG_HOME, APPBASENAME)
    LOGDIR = os.path.join(DATA_HOME, "logs")
    if APPBASENAME != APPNAME:
        DATA_HOME_DEFAULT = os.path.join(XDG_DATA_HOME_DEFAULT, APPNAME)
        if DATA_HOME_DEFAULT not in DATA_DIRS:
            DATA_DIRS.append(DATA_HOME_DEFAULT)
        DATA_DIRS.extend(os.path.join(dir_, APPNAME) for dir_ in XDG_DATA_DIRS)
    DATA_DIRS.append(DATA_HOME)
    DATA_HOME_DEFAULT = os.path.join(XDG_DATA_HOME_DEFAULT, APPBASENAME)
    if DATA_HOME_DEFAULT not in DATA_DIRS:
        DATA_DIRS.append(DATA_HOME_DEFAULT)
    DATA_DIRS.extend(os.path.join(dir_, APPBASENAME) for dir_ in XDG_DATA_DIRS)
    EXTRA_DATA_DIRS.extend(os.path.join(dir_, "argyllcms") for dir_ in XDG_DATA_DIRS)
    EXTRA_DATA_DIRS.extend(
        os.path.join(dir_, "color", "argyll") for dir_ in XDG_DATA_DIRS
    )
    EXE_EXT = ""
    PROFILE_EXT = ".icc"

STORAGE = os.path.join(DATA_HOME, "storage")

RES_FILES = [
    # Only essentials
    "lang/en.yaml",
    "beep.wav",
    "camera_shutter.wav",
    "linear.cal",
    "test.cal",
    "ref/ClayRGB1998.gam",
    "ref/sRGB.gam",
    "ref/verify_extended.ti1",
    "ti1/d3-e4-s2-g28-m0-b0-f0.ti1",
    "ti1/d3-e4-s3-g52-m3-b0-f0.ti1",
    "ti1/d3-e4-s4-g52-m4-b0-f0.ti1",
    "ti1/d3-e4-s5-g52-m5-b0-f0.ti1",
    "xrc/extra.xrc",
    "xrc/gamap.xrc",
    "xrc/main.xrc",
    "xrc/mainmenu.xrc",
    "xrc/report.xrc",
    "xrc/synthicc.xrc",
]

BITMAPS = {}

# Does the device not support iterative calibration?
UNCALIBRATABLE_DISPLAYS = ("Untethered$",)

# Can the device generate patterns of its own?
PATTERN_GENERATORS = ("madVR$", "Resolve$", "Chromecast ", "Prisma ", "Prisma$")

NON_ARGYLL_DISPLAYS = (*UNCALIBRATABLE_DISPLAYS, "Resolve$")

# Is the device directly connected or e.g. driven via network?
# (note that madVR can technically be both, but the endpoint is always directly
# connected to a display so we have videoLUT access via madVR's API.
# Only devices which don't support that are considered 'untethered' in this context)
UNTETHERED_DISPLAYS = (
    *NON_ARGYLL_DISPLAYS,
    "Web$",
    "Chromecast ",
    "Prisma ",
    "Prisma$",
)

# Is the device not an actual display device (i.e. is it not a TV or monitor)?
VIRTUAL_DISPLAYS = (*UNTETHERED_DISPLAYS, "madVR$")


def is_special_display(
    display: None | str = None, tests: list[str] = VIRTUAL_DISPLAYS
) -> bool:
    """Check if the display is a special display.

    Args:
        display (str): The display name.
        tests (list): List of special display patterns.

    Returns:
        bool: True if the display is special, False otherwise.
    """
    if not isinstance(display, str):
        display = get_display_name(display)
    return any(re.match(test, display) for test in tests)


def is_uncalibratable_display(display: None | str = None) -> bool:
    """Check if the display is uncalibratable.

    Args:
        display (None | str): The display name.

    Returns:
        bool: True if the display is uncalibratable, False otherwise.
    """
    return is_special_display(display, UNCALIBRATABLE_DISPLAYS)


def is_patterngenerator(display: None | str = None) -> bool:
    """Check if the display is a pattern generator.

    Args:
        display (None | str): The display name.

    Returns:
        bool: True if the display is a pattern generator, False otherwise.
    """
    return is_special_display(display, PATTERN_GENERATORS)


def is_non_argyll_display(display=None) -> bool:
    """Check if the display is a non-Argyll display.

    Args:
        display (None | str): The display name.

    Returns:
        bool: True if the display is a non-Argyll display, False otherwise.
    """
    return is_special_display(display, NON_ARGYLL_DISPLAYS)


def is_untethered_display(display: None | str = None) -> bool:
    """Check if the display is untethered.

    Args:
        display (None | str): The display name.

    Returns:
        bool: True if the display is untethered, False otherwise.
    """
    return is_special_display(display, UNTETHERED_DISPLAYS)


def is_virtual_display(display: None | str = None) -> bool:
    """Check if the display is virtual.

    Args:
        display (None | str): The display name.

    Returns:
        bool: True if the display is virtual, False otherwise.
    """
    return is_special_display(display, VIRTUAL_DISPLAYS)


def check_3dlut_format(devicename) -> bool:
    """Check the 3D LUT format for the given device.

    Args:
        devicename (str): The name of the device.

    Returns:
        bool: True if the 3D LUT format is correct, False otherwise.
    """
    if get_display_name(None, True) == devicename and devicename == "Prisma":
        return (
            getcfg("3dlut.format") == "3dl"
            and getcfg("3dlut.size") == 17
            and getcfg("3dlut.bitdepth.input") == 10
            and getcfg("3dlut.bitdepth.output") == 12
        )
    return False


def getbitmap(
    name: str,
    display_missing_icon: bool = True,
    scale: bool = True,
    use_mask: bool = False,
) -> wx.Bitmap:
    """Create (if necessary) and return a named bitmap.

    Args:
        name (str): Has to be a relative path to a png file, omitting the extension,
            e.g. 'theme/mybitmap' or 'theme/icons/16x16/myicon', which is searched
            for in the data directories. If a matching file is not found, a
            placeholder bitmap is returned. The special name 'empty' will always
            return a transparent bitmap of the given size, e.g. '16x16/empty'
            or just 'empty' (size defaults to 16x16 if not given).
        display_missing_icon (bool): Whether to display a missing icon if the bitmap.
        scale (bool): Whether to scale the bitmap.
        use_mask (bool): Whether to use a mask for the bitmap.

    Returns:
        wx.Bitmap: The bitmap.
    """
    if name not in BITMAPS:
        BITMAPS[name] = create_bitmap(name, display_missing_icon, scale, use_mask)
    return BITMAPS[name]


def create_bitmap(
    name: str, display_missing_icon: bool, scale: bool, use_mask: bool
) -> wx.Bitmap:
    """Create a bitmap with the specified name and dimensions.

    Args:
        name (str): The name of the bitmap.
        display_missing_icon (bool): Whether to display a missing icon if the
            bitmap is not found.
        scale (bool): Whether to scale the bitmap.
        use_mask (bool): Whether to use a mask for the bitmap.

    Returns:
        wx.Bitmap: The created bitmap.
    """
    parts = name.split("/")
    w = 16
    h = 16
    size = []
    if len(parts) > 1:
        size = parts[-2].split("x")
        if len(size) == 2:
            try:
                w, h = list(map(int, size))
            except ValueError:
                size = []
    ow, oh = w, h
    set_default_app_dpi()
    scale = getcfg("app.dpi") / get_default_dpi() if scale else 1
    if scale > 1:
        # HighDPI support
        w = round(w * scale)
        h = round(h * scale)
    if parts[-1] == "empty":
        return create_empty_bitmap(w, h, use_mask)
    return load_bitmap(name, parts, ow, oh, w, h, scale, use_mask, display_missing_icon)


def create_empty_bitmap(w: int, h: int, use_mask: bool) -> wx.Bitmap:
    """Create an empty bitmap with the specified dimensions.

    Args:
        w (int): Width of the bitmap.
        h (int): Height of the bitmap.
        use_mask (bool): Whether to use a mask for the bitmap.

    Returns:
        wx.Bitmap: The created empty bitmap.
    """
    from DisplayCAL.wx_addons import wx

    if wx.VERSION[0] < 3:
        use_mask = True
    if use_mask and sys.platform == "win32":
        bmp = wx.EmptyBitmap(w, h)
        bmp.SetMaskColour(wx.Colour(0, 0, 0))
    else:
        bmp = wx.EmptyBitmapRGBA(w, h, 255, 0, 255, 0)
    return bmp


def load_bitmap(
    name: str,
    parts: list[str],
    ow: int,
    oh: int,
    w: int,
    h: int,
    scale: float,
    use_mask: bool,
    display_missing_icon: bool = True,
) -> wx.Bitmap:
    """Load a bitmap from the specified parts and dimensions.

    Args:
        name (str): The name of the bitmap.
        parts (list): A list of parts representing the path to the bitmap.
        ow (int): Original width of the bitmap.
        oh (int): Original height of the bitmap.
        w (int): New width of the bitmap.
        h (int): New height of the bitmap.
        scale (float): Scale factor for the bitmap.
        use_mask (bool): Whether to use a mask for the bitmap.
        display_missing_icon (bool): Whether to display a missing icon if the
            bitmap is not found.

    Returns:
        wx.Bitmap: The loaded bitmap.
    """
    from DisplayCAL.wx_addons import wx

    if parts[-1].startswith(APPNAME):
        parts[-1] = parts[-1].lower()
    oname = parts[-1]
    if "#" in oname:
        # Hex format, RRGGBB or RRGGBBAA
        oname, color = oname.split("#", 1)
        parts[-1] = oname
    else:
        color = None
    inverted = oname.endswith("-inverted")
    if inverted:
        oname = parts[-1] = oname.split("-inverted")[0]
    name2x = f"{oname}@2x"
    name4x = f"{oname}@4x"
    path = None
    size = []
    if len(parts) > 1:
        size = parts[-2].split("x")
        if len(size) == 2:
            try:
                w, h = list(map(int, size))
            except ValueError:
                size = []

    for i in range(5):
        if scale > 1:
            if len(size) == 2:
                # Icon
                if i == 0:
                    # HighDPI support. Try scaled size
                    parts[-2] = f"{w:d}x{h:d}"
                elif i == 1:
                    if scale < 1.75 or scale == 2:
                        continue
                    # HighDPI support. Try @4x version
                    parts[-2] = f"{ow:d}x{oh:d}"
                    parts[-1] = name4x
                elif i == 2:
                    # HighDPI support. Try @2x version
                    parts[-2] = f"{ow:d}x{oh:d}"
                    parts[-1] = name2x
                elif i == 3:
                    # HighDPI support. Try original size times two
                    parts[-2] = f"{ow * 2:d}x{oh * 2: d}"
                    parts[-1] = oname
                else:
                    # Try original size
                    parts[-2] = f"{ow:d}x{oh:d}"
            else:
                # Theme graphic
                if i in (0, 3):
                    continue
                if i == 1:
                    if scale < 1.75 or scale == 2:
                        continue
                    # HighDPI support. Try @4x version
                    parts[-1] = name4x
                elif i == 2:
                    # HighDPI support. Try @2x version
                    parts[-1] = name2x
                else:
                    # Try original size
                    parts[-1] = oname
        if sys.platform not in ("darwin", "win32") and parts[-1].startswith(
            APPNAME.lower()
        ):
            # Search /usr/share/icons on Linux first
            path = get_data_path(
                "{}.png".format(os.path.join(parts[-2], "apps", parts[-1]))
            )
        if not path:
            path = get_data_path(f"{os.path.sep.join(parts)}.png")
        if path or scale == 1:
            break
    if path:
        bmp = wx.Bitmap(path)
        if not bmp.IsOk():
            path = None
    if path:
        img = None
        if scale > 1 and i:
            rescale = False
            if i in (1, 2):
                # HighDPI support. 4x/2x version, determine scaled size
                w, h = [round(v / (2 * (3 - i)) * scale) for v in bmp.Size]
                rescale = True
            elif len(size) == 2:
                # HighDPI support. Icon
                rescale = True
            if rescale and (bmp.Size[0] != w or bmp.Size[1] != h):
                # HighDPI support. Rescale
                img = bmp.ConvertToImage()
                if not hasattr(wx, "IMAGE_QUALITY_BILINEAR") or oname == "list-add":
                    # In case bilinear is not supported,
                    # and to prevent black borders after resizing for some images
                    quality = wx.IMAGE_QUALITY_NORMAL
                elif oname in ():
                    # Hmm. Everything else looks great with bicubic,
                    # but this one gets jaggy unless we use bilinear
                    quality = wx.IMAGE_QUALITY_BILINEAR
                elif scale < 1.5 or i == 1:
                    quality = wx.IMAGE_QUALITY_BICUBIC
                else:
                    quality = wx.IMAGE_QUALITY_BILINEAR
                img.Rescale(w, h, quality=quality)
        factors = None
        if (
            not inverted
            and len(parts) > 2
            and parts[-3] == "icons"
            and (ow, oh) != (10, 10)
            and oname not in ("black_luminance", "check_all", "contrast", "luminance")
            and max(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)[:3]) < 102
        ):
            # Automatically invert B&W image if background is dark (exceptions do apply)
            if not img:
                img = bmp.ConvertToImage()
            if img.IsBW():
                inverted = True
        # Invert after resize (avoids jaggies)
        if inverted or color:
            if not img:
                img = bmp.ConvertToImage()
            alpha = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT).alpha
            if oname in [
                "applications-system",
                "color",
                "document-open",
                "document-save-as",
                "edit-delete",
                "image-x-generic",
                "info",
                "install",
                "list-add",
                "package-x-generic",
                "question",
                "rgbsquares",
                "stock_3d-color-picker",
                "stock_lock",
                "stock_lock-open",
                "stock_refresh",
                "web",
                "window-center",
                "zoom-best-fit",
                "zoom-in",
                "zoom-original",
                "zoom-out",
            ]:
                # Scale 85 to 255 and adjust alpha
                factors = (3, 3, 3, alpha / 255.0)
            else:
                if inverted:
                    img.Invert()
                if alpha != 255:
                    # Only adjust alpha
                    factors = (1, 1, 1, alpha / 255.0)
            if factors:
                R, G, B = factors[:3]
                alpha = factors[3] if len(factors) > 3 else 1.0
                img = img.AdjustChannels(R, G, B, alpha)
            if color:
                # Hex format, RRGGBB or RRGGBBAA
                R = int(color[0:2], 16) / 255.0
                G = int(color[2:4], 16) / 255.0
                B = int(color[4:6], 16) / 255.0
                alpha = int(color[6:8], 16) / 255.0 if len(color) > 6 else 1.0
                img = img.AdjustChannels(R, G, B, alpha)
        if img:
            bmp = img.ConvertToBitmap()
            if not bmp.IsOk():
                path = None
    if not path:
        print(f"Warning: Missing bitmap '{name}'")
        img = wx.Image(w, h)
        img.SetMaskColour(0, 0, 0)
        img.InitAlpha()
        bmp = img.ConvertToBitmap()
        dc = wx.MemoryDC()
        dc.SelectObject(bmp)
        if display_missing_icon:
            art = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE, size=(w, h))
            dc.DrawBitmap(art, 0, 0, True)
        dc.SelectObject(wx.NullBitmap)
    return bmp


def get_bitmap_as_icon(size: int, name: str, scale: bool = True) -> wx.Icon:
    """Return a wx.Icon instance.

    This is like geticon, but returns a wx.Icon instance instead of a wx.Bitmap
    instance.

    Get a bitmap as an icon with the specified size and name.

    Args:
        size (int): The size of the icon.
        name (str): The name of the icon.
        scale (bool): Whether to scale the icon.

    Returns:
        wx.Icon: The (created) icon (instance).
    """
    from DisplayCAL.wx_addons import wx

    icon = wx.EmptyIcon()
    if sys.platform == "darwin" and wx.VERSION >= (2, 9) and size > 128:
        # FIXME: wxMac 2.9 doesn't support icon sizes above 128
        size = 128
    bmp = geticon(size, name, scale)
    icon.CopyFromBitmap(bmp)
    return icon


def get_argyll_data_dir() -> str:
    """Return ArgyllCMS data dir.

    Returns:
        str: The ArgyllCMS data dir.
    """
    argyll_version = getcfg("argyll.version")
    if isinstance(argyll_version, str):
        argyll_version = list(map(int, argyll_version.split(".")))

    argyll_data_dirname = "color" if argyll_version < [1, 5, 0] else "ArgyllCMS"

    if sys.platform == "darwin" and argyll_version < [1, 5, 0]:
        return os.path.join(
            LIBRARY if is_superuser() else LIBRARY_HOME, argyll_data_dirname
        )
    return os.path.join(
        COMMONAPPDATA[0] if is_superuser() else APPDATA, argyll_data_dirname
    )


def get_display_name(disp_index: None | int = None, include_geometry: bool = False):
    """Return name of currently configured display.

    Args:
        disp_index (None | int): The index of the display.
        include_geometry (bool): Whether to include geometry in the display name.

    Returns:
        str: The name of the display.
    """
    if disp_index is None:
        disp_index = getcfg("display.number") - 1
    displays = getcfg("displays")
    if 0 <= disp_index < len(displays):
        return (
            displays[disp_index]
            if include_geometry
            else split_display_name(displays[disp_index])
        )
    return ""


def split_display_name(display: str) -> str:
    """Split and return name part of display.

    Args:
        display (str): The display name.

    Returns:
        str: The name part of the display.

    E.g.
    'LCD2690WUXi @ 0, 0, 1920x1200' -> 'LCD2690WUXi'
    'madVR' -> 'madVR'
    """
    if "@" in display and not display.startswith("Chromecast "):
        display = "@".join(display.split("@")[:-1])
    return display.strip()


def get_argyll_display_number(geometry: tuple[int, int, int, int]) -> None | int:
    """Translate from wx display geometry to Argyll display index.

    Args:
        geometry (tuple[int, int, int, int]): The geometry of the display.

    Returns:
        None | int: The Argyll display index.
    """
    geometry = f"{geometry[0]}, {geometry[1]}, {geometry[2]}x{geometry[3]}"
    for i, display in enumerate(getcfg("displays")):
        if display.find(f"@ {geometry}") > -1:
            if DEBUG:
                print(f"[D] Found display {geometry} at index {i}")
            return i
    return None


def get_display_number(display_no: int) -> int:
    """Translate from Argyll display index to wx display index.

    Args:
        display_no (int): The Argyll display index.

    Returns:
        int: The wx display index.
    """
    if is_virtual_display(display_no):
        return 0
    from DisplayCAL.wx_addons import wx

    try:
        display = getcfg("displays")[display_no]
    except IndexError:
        return 0
    else:
        if display.endswith(" [PRIMARY]"):
            display = " ".join(display.split(" ")[:-1])
        for i in range(wx.Display.GetCount()):
            geometry = "{:d}, {:d}, {:d}x{:d}".format(*wx.Display(i).Geometry)
            if display.endswith(f"@ {geometry}"):
                if DEBUG:
                    print(f"[D] Found display {geometry} at index {i}")
                return i
    return 0


def get_display_rects() -> list[tuple[int, int, int, int]]:
    """Return the Argyll enumerated display coordinates and sizes.

    Returns:
        list[tuple[int, int, int, int]]: A list of wx.Rect objects representing
            the display coordinates and sizes.
    """
    from DisplayCAL.wx_addons import wx

    display_rects = []
    for _i, display in enumerate(getcfg("displays")):
        match = re.search(r"@ (-?\d+), (-?\d+), (\d+)x(\d+)", display)
        if match:
            display_rects.append(wx.Rect(*[int(item) for item in match.groups()]))
    return display_rects


def get_icon_bundle(sizes, name):
    """Return a wx.IconBundle with given icon sizes.

    Args:
        sizes (list): A list of icon sizes.
        name (str): The name of the icon.

    Returns:
        wx.IconBundle: The icon bundle.
    """
    from DisplayCAL.wx_addons import wx

    iconbundle = wx.IconBundle()
    if not sizes:
        # Assume ICO format
        pth = get_data_path(f"theme/icons/{name}.ico")
        if pth:
            ico = wx.Icon(pth)
            if ico.IsOk():
                iconbundle.AddIcon(ico)
                return iconbundle
        sizes = [16]
    for size in sizes:
        iconbundle.AddIcon(get_bitmap_as_icon(size, name, False))
    return iconbundle


def get_instrument_name() -> str:
    """Return name of currently configured instrument.

    Returns:
        str: The name of the instrument.
    """
    n = getcfg("comport.number") - 1
    instrument_names = getcfg("instruments")
    if 0 <= n < len(instrument_names):
        return instrument_names[n]
    return ""


def get_measureframe_dimensions(dimensions_measureframe=None, percent=10) -> str:
    """Return measurement area size adjusted for percentage of screen area.

    Args:
        dimensions_measureframe (str): The dimensions of the measure frame.
        percent (int): The percentage of screen area.

    Returns:
        str: The coma separated measurement frame size.
    """
    if not dimensions_measureframe:
        dimensions_measureframe = getcfg("dimensions.measureframe")
    dimensions_measureframe = [float(n) for n in dimensions_measureframe.split(",")]
    dimensions_measureframe[2] *= DEFAULTS["size.measureframe"]
    dimensions_measureframe[2] /= get_display_rects()[0][2]
    dimensions_measureframe[2] *= percent
    return ",".join([str(min(n, 50)) for n in dimensions_measureframe])


def geticon(size, name, scale=True, use_mask=False):
    """Convenience function for getbitmap('theme/icons/<size>/<name>')."""
    return getbitmap(
        f"theme/icons/{size}x{size}/{name}",
        scale=scale,
        use_mask=use_mask,
    )


def get_data_path(relpath, rex=None):
    """Search data_dirs for relpath and return the path or a file list.

    If relpath is a file, return the full path, if relpath is a directory,
    return a list of files in the intersection of searched directories.
    """
    if (
        not relpath
        or relpath.endswith(os.path.sep)
        or (isinstance(os.path.altsep, str) and relpath.endswith(os.path.altsep))
    ):
        return None
    dirs = list(DATA_DIRS)
    argyll_dir = getcfg("argyll.dir") or os.path.dirname(
        os.path.realpath(which(f"dispcal{EXE_EXT}") or "")
    )
    if argyll_dir and os.path.isdir(os.path.join(argyll_dir, "..", "ref")):
        dirs.append(os.path.dirname(argyll_dir))
    dirs.extend(EXTRA_DATA_DIRS)
    intersection = []
    paths = []
    for dir_ in dirs:
        curpath = os.path.join(dir_, relpath)
        if (
            dir_.endswith("/argyll")
            and f"{relpath}/".startswith("ref/")
            and not os.path.exists(curpath)
        ):
            # Work-around distribution-specific differences for location of
            # Argyll reference files
            # Fedora and Ubuntu: /usr/share/color/argyll/ref
            # openSUSE: /usr/share/color/argyll
            pth = relpath.split("/", 1)[-1]
            curpath = os.path.join(dir_, pth) if pth != "ref" else dir_
        if os.path.exists(curpath):
            curpath = os.path.normpath(curpath)
            if os.path.isdir(curpath):
                try:
                    filelist = listdir_re(curpath, rex)
                except Exception as exception:
                    print(f"Error - directory '{curpath}' listing failed: {exception}")
                else:
                    for filename in filelist:
                        if filename not in intersection:
                            intersection.append(filename)
                            paths.append(os.path.join(curpath, filename))
            else:
                return curpath
    if paths:
        paths.sort(key=lambda path: os.path.basename(path).lower())
    return None if len(paths) == 0 else paths


def get_default_dpi() -> float:
    """Return default DPI depending on the current platform.

    Returns:
        float: The DPI value.
    """
    return 72.0 if sys.platform == "darwin" else 96.0


def runtimeconfig(pyfile):
    """Configure remaining runtime options and return runtype.

    You need to pass in a path to the calling script (e.g. use the __file__
    attribute).
    """
    # global safe_log
    from DisplayCAL.log import setup_logging

    setup_logging(LOGDIR, PYNAME, PYEXT, confighome=CONFIG_HOME)
    if DEBUG:
        print("[D] pydir:", PYDIR)
        print("[D] config_home:", CONFIG_HOME)
    if ISAPP:
        runtype = ".app"
    elif ISEXE:
        if DEBUG:
            print("[D] _MEIPASS2 or pydir:", getenvu("_MEIPASS2", EXEDIR))
        if getenvu("_MEIPASS2", EXEDIR) not in DATA_DIRS:
            DATA_DIRS.insert(1, getenvu("_MEIPASS2", EXEDIR))
        runtype = EXE_EXT
    else:
        pydir_parent = os.path.dirname(PYDIR)
        if DEBUG:
            print(
                "[D] dirname(os.path.abspath(sys.argv[0])):",
                os.path.dirname(os.path.abspath(sys.argv[0])),
            )
            print("[D] pydir parent:", pydir_parent)
        if (
            os.path.dirname(os.path.abspath(sys.argv[0])) == pydir_parent
            and pydir_parent not in DATA_DIRS
        ):
            # Add the parent directory of the package directory to our list of
            # data directories if it is the directory containing the currently
            # run script (e.g. when running from source)
            DATA_DIRS.insert(1, pydir_parent)
        runtype = PYEXT
    for dir_ in sys.path:
        if not isinstance(dir_, str):
            dir_ = dir_.encode(FS_ENC)
        dir_ = os.path.abspath(os.path.join(dir_, APPNAME))
        if dir_ not in DATA_DIRS and os.path.isdir(dir_):
            DATA_DIRS.append(dir_)
            if DEBUG:
                print("[D] from sys.path:", dir_)
    if sys.platform not in ("darwin", "win32"):
        DATA_DIRS.extend(
            [
                os.path.join(dir_, "doc", f"{APPNAME}-{VERSION_STRING}")
                for dir_ in [*XDG_DATA_DIRS, XDG_DATA_HOME]
            ]
        )
        DATA_DIRS.extend(
            [
                os.path.join(dir_, "doc", "packages", APPNAME)
                for dir_ in [*XDG_DATA_DIRS, XDG_DATA_HOME]
            ]
        )
        DATA_DIRS.extend(
            [
                os.path.join(dir_, "doc", APPNAME)
                for dir_ in [*XDG_DATA_DIRS, XDG_DATA_HOME]
            ]
        )
        DATA_DIRS.extend(
            [
                os.path.join(dir_, "doc", APPNAME.lower())  # Debian
                for dir_ in [*XDG_DATA_DIRS, XDG_DATA_HOME]
            ]
        )
        DATA_DIRS.extend(
            [
                os.path.join(dir_, "icons", "hicolor")
                for dir_ in [*XDG_DATA_DIRS, XDG_DATA_HOME]
            ]
        )
    if DEBUG:
        print("[D] Data files search paths:\n[D]", "\n[D] ".join(DATA_DIRS))
    DEFAULTS["calibration.file"] = get_data_path("presets/default.icc") or ""
    DEFAULTS["measurement_report.chart"] = (
        get_data_path(os.path.join("ref", "verify_extended.ti1")) or ""
    )
    return runtype


class CaseSensitiveConfigParser(configparser.RawConfigParser):
    """Case sensitive config parser."""

    def optionxform(self, optionstr: str) -> str:
        """Return the option string as is, preserving case sensitivity.

        Args:
            optionstr (str): The option string to be processed.
        """
        return optionstr


# User settings
CFG = CaseSensitiveConfigParser()
CFG["Default"] = {}


VALID_RANGES = {
    "3dlut.hdr_peak_luminance": [100.0, 10000.0],
    "3dlut.hdr_minmll": [0.0, 0.1],
    "3dlut.hdr_maxmll": [100.0, 10000.0],
    "3dlut.trc_gamma": [0.000001, 10],
    "3dlut.hdr_sat": [0.0, 1.0],
    "3dlut.hdr_hue": [0.0, 1.0],
    "3dlut.trc_output_offset": [0.0, 1.0],
    "app.port": [1, 65535],
    "gamma": [0.000001, 10],
    "trc": [0.000001, 10],
    # Argyll dispcal uses 20% of ambient (in lux, fixed steradiant of 3.1415) as
    # adapting luminance, but we assume it already *is* the adapting luminance.
    # To correct for this, scale so that dispcal gets the correct value.
    "calibration.ambient_viewcond_adjust.lux": [0.0, sys.maxsize / 5.0],
    "calibration.black_luminance": [0.000001, 10],
    "calibration.black_output_offset": [0, 1],
    "calibration.black_point_correction": [0, 1],
    "calibration.black_point_rate": [0.05, 20],
    "calibration.luminance": [20, 100000],
    "iccgamut.surface_detail": [1.0, 50.0],
    "measurement_report.trc_gamma": [0.01, 10],
    "measurement_report.trc_output_offset": [0.0, 1.0],
    "measure.display_settle_time_mult": [0.000001, 10000.0],
    "measure.min_display_update_delay_ms": [20, 60000],
    "multiprocessing.max_cpus": [0, 65],
    "patterngenerator.apl": [0.0, 1.0],
    "patterngenerator.ffp_insertion.duration": [0.1, 60.0],
    "patterngenerator.ffp_insertion.interval": [0.0, 3600.0],
    "patterngenerator.ffp_insertion.level": [0.0, 1.0],
    "patterngenerator.quantize_bits": [0, 32],
    "patterngenerator.resolve.port": [1, 65535],
    "profile_loader.quantize_bits": [8, 16],
    "synthprofile.trc_gamma": [0.01, 10],
    "synthprofile.trc_output_offset": [0.0, 1.0],
    "tc_export_repeat_patch_max": [1, 1000],
    "tc_export_repeat_patch_min": [1, 1000],
    "tc_vrml_black_offset": [0, 40],
    "webserver.portnumber": [1, 65535],
    "whitepoint.colortemp": [1000, 15000],
    "whitepoint.visual_editor.bg_v": [0, 255],
    "whitepoint.visual_editor.b": [0, 255],
    "whitepoint.visual_editor.g": [0, 255],
    "whitepoint.visual_editor.r": [0, 255],
}

VALID_VALUES = {
    "3d.format": ["HTML", "VRML", "X3D"],
    "3dlut.bitdepth.input": [8, 10, 12, 14, 16],
    "3dlut.bitdepth.output": [8, 10, 12, 14, 16],
    "3dlut.encoding.input": list(VIDEO_ENCODINGS),
    # collink: xvYCC output encoding is not supported
    "3dlut.encoding.output": [v for v in VIDEO_ENCODINGS if v not in ("T", "x", "X")],
    "3dlut.format": [
        "3dl",
        "cube",
        "dcl",
        "eeColor",
        "icc",
        "madVR",
        "mga",
        "png",
        "ReShade",
        "spi3d",
    ],
    "3dlut.hdr_display": [0, 1],
    "3dlut.image.layout": ["h", "v"],
    "3dlut.image.order": ["rgb", "bgr"],
    "3dlut.rendering_intent": INTENTS,
    "3dlut.size": [5, 9, 16, 17, 24, 32, 33, 64, 65],
    "3dlut.trc": [
        "bt1886",
        "customgamma",
        "gamma2.2",
        "smpte2084.hardclip",
        "smpte2084.rolloffclip",
        "hlg",
    ],
    "3dlut.trc_gamma_type": ["b", "B"],
    "calibration.quality": ["v", "l", "m", "h", "u"],
    "colorimeter_correction.observer": OBSERVERS,
    "colorimeter_correction.observer.reference": OBSERVERS,
    "colorimeter_correction.type": ["matrix", "spectral"],
    # Measurement modes as supported by Argyll -y parameter
    # 'l' = 'n' (non-refresh-type display, e.g. LCD)
    # 'c' = 'r' (refresh-type display, e.g. CRT)
    # We map 'l' and 'c' to "n" and "r" in
    # worker.Worker.add_measurement_features if using Argyll >= 1.5
    # See http://www.argyllcms.com/doc/instruments.html for description of
    # per-instrument supported modes
    "measurement_mode": [None, "auto", *list(string.digits[1:] + string.ascii_letters)],
    "gamap_default_intent": ["a", "r", "p", "s"],
    "gamap_perceptual_intent": INTENTS,
    "gamap_saturation_intent": INTENTS,
    "gamap_src_viewcond": VIEWCONDS,
    "gamap_out_viewcond": ["mt", "mb", "md", "jm", "jd"],
    "measurement_report.trc_gamma_type": ["b", "B"],
    "observer": OBSERVERS,
    "patterngenerator.detect_video_levels": [0, 1],
    "patterngenerator.prisma.preset": [
        "Movie",
        "Sports",
        "Game",
        "Animation",
        "PC/Mac",
        "Black+White",
        "Custom-1",
        "Custom-2",
    ],
    "patterngenerator.use_video_levels": [0, 1],
    "profile.black_point_compensation": [0, 1],
    "profile.install_scope": ["l", "u"],
    "profile.quality": ["l", "m", "h", "u"],
    "profile.quality.b2a": ["l", "m", "h", "u", "n", None],
    "profile.b2a.hires.size": [-1, 9, 17, 33, 45, 65],
    "profile.type": ["g", "G", "l", "s", "S", "x", "X"],
    "profile_loader.tray_icon_animation_quality": [0, 1, 2],
    "synthprofile.black_point_compensation": [0, 1],
    "synthprofile.trc_gamma_type": ["g", "G"],
    "tc_algo": ["", "t", "r", "R", "q", "Q", "i", "I"],  # Q = Argyll >= 1.1.0
    "tc_vrml_use_D50": [0, 1],
    "tc_vrml_cie_colorspace": [
        "DIN99",
        "DIN99b",
        "DIN99c",
        "DIN99d",
        "ICtCp",
        "IPT",
        "LCH(ab)",
        "LCH(uv)",
        "Lab",
        "Lpt",
        "Luv",
        "Lu'v'",
        "xyY",
    ],
    "tc_vrml_device_colorspace": ["HSI", "HSL", "HSV", "RGB"],
    "testchart.auto_optimize": list(range(19)),
    "testchart.patch_sequence": [
        "optimize_display_response_delay",
        "maximize_lightness_difference",
        "maximize_rec709_luma_difference",
        "maximize_RGB_difference",
        "vary_RGB_difference",
    ],
    "trc": ["240", "709", "l", "s", ""],
    "trc.type": ["g", "G"],
    "uniformity.cols": [3, 5, 7, 9],
    "uniformity.rows": [3, 5, 7, 9],
    "whitepoint.colortemp.locus": ["t", "T"],
}

CONTENT_RGB_SPACE = colormath.get_rgb_space("DCI P3 D65")
CRX, CRY = CONTENT_RGB_SPACE[2:][0][:2]
CGX, CGY = CONTENT_RGB_SPACE[2:][1][:2]
CBX, CBY = CONTENT_RGB_SPACE[2:][2][:2]
CWX, CWY = colormath.XYZ2xyY(*CONTENT_RGB_SPACE[1])[:2]
DEFAULTS = {
    "3d.format": "HTML",
    "3dlut.apply_black_offset": 0,
    "3dlut.apply_trc": 1,
    "3dlut.bitdepth.input": 10,
    "3dlut.bitdepth.output": 12,
    "3dlut.content.colorspace.blue.x": CBX,
    "3dlut.content.colorspace.blue.y": CBY,
    "3dlut.content.colorspace.green.x": CGX,
    "3dlut.content.colorspace.green.y": CGY,
    "3dlut.content.colorspace.red.x": CRX,
    "3dlut.content.colorspace.red.y": CRY,
    "3dlut.content.colorspace.white.x": CWX,
    "3dlut.content.colorspace.white.y": CWY,
    "3dlut.create": 0,
    "3dlut.trc": "bt1886",
    "3dlut.trc_gamma": 2.4,
    "3dlut.trc_gamma.backup": 2.4,
    "3dlut.trc_gamma_type": "B",
    "3dlut.trc_output_offset": 0.0,
    "3dlut.encoding.input": "n",
    "3dlut.encoding.input.backup": "n",
    "3dlut.encoding.output": "n",
    "3dlut.encoding.output.backup": "n",
    "3dlut.format": "cube",
    "3dlut.gamap.use_b2a": 0,
    "3dlut.hdr_display": 0,
    "3dlut.hdr_minmll": 0.0,
    "3dlut.hdr_maxmll": 10000.0,
    "3dlut.hdr_maxmll_alt_clip": 1,
    "3dlut.hdr_peak_luminance": 480.0,
    "3dlut.hdr_ambient_luminance": 5.0,
    "3dlut.hdr_sat": 0.5,
    "3dlut.hdr_hue": 0.5,
    "3dlut.image.layout": "h",
    "3dlut.image.order": "rgb",
    "3dlut.input.profile": "",
    "3dlut.abstract.profile": "",
    "3dlut.enable": 1,
    "3dlut.output.profile": "",
    "3dlut.output.profile.apply_cal": 1,
    "3dlut.preserve_sync": 0,
    "3dlut.rendering_intent": "aw",
    "3dlut.use_abstract_profile": 0,
    "3dlut.size": 65,
    "3dlut.size.backup": 65,
    "3dlut.tab.enable": 0,
    "3dlut.tab.enable.backup": 0,
    "3dlut.whitepoint.x": 0.3127,
    "3dlut.whitepoint.y": 0.329,
    "allow_skip_sensor_cal": 0,
    "app.allow_network_clients": 0,
    "app.dpi": get_default_dpi(),
    "app.port": 15411,
    "argyll.debug": 0,
    "argyll.dir": None,
    "argyll.version": "0.0.0",
    "argyll.domain": "https://www.argyllcms.com",
    "drift_compensation.blacklevel": 0,
    "drift_compensation.whitelevel": 0,
    "calibration.ambient_viewcond_adjust": 0,
    "calibration.ambient_viewcond_adjust.lux": 32.0,
    "calibration.autoload": 0,
    "calibration.black_luminance": 0.000001,
    "calibration.black_luminance.backup": 0.000001,
    "calibration.black_output_offset": 1.0,
    "calibration.black_output_offset.backup": 1.0,
    "calibration.black_point_correction": 0.0,
    "calibration.black_point_correction.auto": 0,
    "calibration.black_point_correction_choice.show": 1,
    "calibration.black_point_hack": 0,
    "calibration.black_point_rate": 4.0,
    "calibration.black_point_rate.enabled": 0,
    "calibration.continue_next": 0,
    "calibration.file": "",
    "calibration.file.previous": None,
    "calibration.interactive_display_adjustment": 1,
    "calibration.interactive_display_adjustment.backup": 1,
    "calibration.luminance": 120.0,
    "calibration.luminance.backup": 120.0,
    "calibration.quality": "l",
    "calibration.update": 0,
    "calibration.use_video_lut": 1,
    "calibration.use_video_lut.backup": 1,
    "ccmx.use_four_color_matrix_method": 0,
    "colorimeter_correction.instrument": None,
    "colorimeter_correction.instrument.reference": None,
    "colorimeter_correction.measurement_mode": "l",
    "colorimeter_correction.measurement_mode.reference.adaptive": 1,
    "colorimeter_correction.measurement_mode.reference.highres": 1,
    "colorimeter_correction.measurement_mode.reference.projector": 0,
    "colorimeter_correction.measurement_mode.reference": "l",
    "colorimeter_correction.observer": "1931_2",
    "colorimeter_correction.observer.reference": "1931_2",
    "colorimeter_correction.testchart": "ccxx.ti1",
    "colorimeter_correction_matrix_file": "AUTO:",
    "colorimeter_correction.type": "matrix",
    "comport.number": 1,
    "comport.number.backup": 1,
    # Note: worker.Worker.enumerate_displays_and_ports() overwrites copyright
    "copyright": f"No copyright. Created with {APPNAME} {VERSION_STRING} and ArgyllCMS",
    "dimensions.measureframe": "0.5,0.5,1.0",
    "dimensions.measureframe.unzoomed": "0.5,0.5,1.0",
    "dimensions.measureframe.whitepoint.visual_editor": "0.5,0.5,1.0",
    "display.number": 1,
    "display_lut.link": 1,
    "display_lut.number": 1,
    "display.technology": "LCD",
    "displays": "",
    "dry_run": 0,
    "enumerate_ports.auto": 0,
    "extra_args.collink": "",
    "extra_args.colprof": "",
    "extra_args.dispcal": "",
    "extra_args.dispread": "",
    "extra_args.spotread": "",
    "extra_args.targen": "",
    "gamap_default_intent": "p",
    "gamap_out_viewcond": None,
    "gamap_profile": "",
    "gamap_perceptual": 0,
    "gamap_perceptual_intent": "p",
    "gamap_saturation": 0,
    "gamap_saturation_intent": "s",
    "gamap_src_viewcond": None,
    "gamma": 2.2,
    "iccgamut.surface_detail": 10.0,
    "instruments": "",
    "last_3dlut_path": "",
    "last_archive_save_path": "",
    "last_cal_path": "",
    "last_cal_or_icc_path": "",
    "last_colorimeter_ti3_path": "",
    "last_testchart_export_path": "",
    "last_filedialog_path": "",
    "last_icc_path": "",
    "last_launch": "99",  # Version
    "last_reference_ti3_path": "",
    "last_ti1_path": "",
    "last_ti3_path": "",
    "last_vrml_path": "",
    "log.autoshow": 0,
    "log.show": 0,
    "lang": "en",
    # The last_[...]_path defaults are set in localization.py
    "lut_viewer.show": 0,
    "lut_viewer.show_actual_lut": 0,
    "madtpg.host": "localhost",
    "madtpg.native": 1,
    "madtpg.port": 60562,
    "measurement_mode": "l",
    "measurement_mode.adaptive": 1,
    "measurement_mode.backup": "l",
    "measurement_mode.highres": 1,
    "measurement_mode.projector": 0,
    "measurement_report.apply_black_offset": 0,
    "measurement_report.apply_trc": 0,
    "measurement_report.trc_gamma": 2.4,
    "measurement_report.trc_gamma.backup": 2.4,
    "measurement_report.trc_gamma_type": "B",
    "measurement_report.trc_output_offset": 0.0,
    "measurement_report.chart": "",
    "measurement_report.chart.fields": "RGB",
    "measurement_report.devlink_profile": "",
    "measurement_report.output_profile": "",
    "measurement_report.whitepoint.simulate": 0,
    "measurement_report.whitepoint.simulate.relative": 0,
    "measurement_report.simulation_profile": "",
    "measurement_report.use_devlink_profile": 0,
    "measurement_report.use_simulation_profile": 0,
    "measurement_report.use_simulation_profile_as_output": 0,
    "measurement.name.expanded": "",
    "measurement.play_sound": 1,
    "measurement.save_path": expanduseru("~"),
    "measure.darken_background": 0,
    "measure.darken_background.show_warning": 1,
    "measure.display_settle_time_mult": 1.0,
    "measure.display_settle_time_mult.backup": 1.0,
    "measure.min_display_update_delay_ms": 20,
    "measure.min_display_update_delay_ms.backup": 20,
    "measure.override_display_settle_time_mult": 0,
    "measure.override_display_settle_time_mult.backup": 0,
    "measure.override_min_display_update_delay_ms": 0,
    "measure.override_min_display_update_delay_ms.backup": 0,
    "multiprocessing.max_cpus": 0,
    "observer": "1931_2",
    "observer.backup": "1931_2",
    "patterngenerator.apl": 0.22,
    "patterngenerator.detect_video_levels": 1,
    "patterngenerator.ffp_insertion": 0,
    "patterngenerator.ffp_insertion.duration": 5.0,
    "patterngenerator.ffp_insertion.interval": 5.0,
    "patterngenerator.ffp_insertion.level": 0.15,
    "patterngenerator.prisma.argyll": 0,
    "patterngenerator.prisma.host": "",
    "patterngenerator.prisma.preset": "Custom-1",
    "patterngenerator.prisma.port": 80,
    "patterngenerator.quantize_bits": 0,
    "patterngenerator.resolve": "CM",
    "patterngenerator.resolve.port": 20002,
    "patterngenerator.use_pattern_window": 0,
    "patterngenerator.use_video_levels": 0,
    "position.x": 50,
    "position.y": 50,
    "position.info.x": 50,
    "position.info.y": 50,
    "position.lut_viewer.x": 50,
    "position.lut_viewer.y": 50,
    "position.lut3dframe.x": 50,
    "position.lut3dframe.y": 50,
    "position.profile_info.x": 50,
    "position.profile_info.y": 50,
    "position.progress.x": 50,
    "position.progress.y": 50,
    "position.reportframe.x": 50,
    "position.reportframe.y": 50,
    "position.scripting.x": 50,
    "position.scripting.y": 50,
    "position.synthiccframe.x": 50,
    "position.synthiccframe.y": 50,
    "position.tcgen.x": 50,
    "position.tcgen.y": 50,
    # Force black point compensation due to OS X bugs with non BPC profiles
    "profile.black_point_compensation": 0 if sys.platform != "darwin" else 1,
    "profile.black_point_correction": 0.0,
    "profile.create_gamut_views": 1,
    "profile.install_scope": (
        "l" if (sys.platform != "win32" and os.geteuid() == 0) else "u"  # Linux, OSX
    ),
    "profile.license": "Public Domain",
    "profile.load_on_login": 1,
    "profile.name": "_".join(  # noqa: FLY002
        [
            "%dns",
            "%out",
            "%Y-%m-%d_%H-%M",
            "%cb",
            "%wp",
            "%cB",
            "%ck",
            "%cg",
            "%cq-%pq",
            "%pt",
        ]
    ),
    "profile.name.expanded": "",
    "profile.quality": "h",
    "profile.quality.b2a": "h",
    "profile.b2a.hires": 1,
    "profile.b2a.hires.diagpng": 2,
    "profile.b2a.hires.size": -1,
    "profile.b2a.hires.smooth": 1,
    "profile.save_path": STORAGE,  # directory
    # Force profile type to single shaper + matrix due to OS X bugs with cLUT
    # profiles and matrix profiles with individual shaper curves
    "profile.type": "X" if sys.platform != "darwin" else "S",
    "profile.update": 0,
    "profile_loader.buggy_video_drivers": "*",
    "profile_loader.check_gamma_ramps": 1,
    "profile_loader.error.show_msg": 1,
    "profile_loader.exceptions": "",
    "profile_loader.fix_profile_associations": 1,
    "profile_loader.ignore_unchanged_gamma_ramps": 1,
    "profile_loader.known_apps": ";".join(  # noqa: FLY002
        [
            "basiccolor display.exe",
            "calclient.exe",
            "coloreyes display pro.exe",
            "colorhcfr.exe",
            "colormunkidisplay.exe",
            "colornavigator.exe",
            "cpkeeper.exe",
            "dell ultrasharp calibration solution.exe",
            "hp_dreamcolor_calibration_solution.exe",
            "i1profiler.exe",
            "icolordisplay.exe",
            "spectraview.exe",
            "spectraview profiler.exe",
            "spyder3elite.exe",
            "spyder3express.exe",
            "spyder3pro.exe",
            "spyder4elite.exe",
            "spyder4express.exe",
            "spyder4pro.exe",
            "spyder5elite.exe",
            "spyder5express.exe",
            "spyder5pro.exe",
            "spyderxelite.exe",
            "spyderxpro.exe",
            "dispcal.exe",
            "dispread.exe",
            "dispwin.exe",
            "flux.exe",
            "dccw.exe",
        ]
    ),
    "profile_loader.known_window_classes": "CalClient.exe",
    "profile_loader.quantize_bits": 16,
    "profile_loader.reset_gamma_ramps": 0,
    "profile_loader.show_notifications": 0,
    "profile_loader.smooth_bits": "8",
    "profile_loader.track_other_processes": 1,
    "profile_loader.tray_icon_animation_quality": 2,
    "profile_loader.use_madhcnet": 0,
    "profile_loader.verify_calibration": 0,
    "recent_cals": "",
    "report.pack_js": 1,
    "settings.changed": 0,
    "show_advanced_options": 0,
    "show_donation_message": 1,
    "size.info.w": 512,
    "size.info.h": 384,
    "size.lut3dframe.w": 512,
    "size.lut3dframe.h": 384,
    "size.measureframe": 300,
    "size.profile_info.w": 432,
    "size.profile_info.split.w": 960,
    "size.profile_info.h": 552,
    "size.lut_viewer.w": 432,
    "size.lut_viewer.h": 552,
    "size.reportframe.w": 512,
    "size.reportframe.h": 256,
    "size.scripting.w": 512,
    "size.scripting.h": 384,
    "size.synthiccframe.w": 512,
    "size.synthiccframe.h": 384,
    "size.tcgen.w": 0,
    "size.tcgen.h": 0,
    "skip_legacy_serial_ports": 1,
    "skip_scripts": 1,
    "splash.zoom": 0,
    "startup_sound.enable": 1,
    "sudo.preserve_environment": 1,
    "synthprofile.black_luminance": 0.0,
    "synthprofile.luminance": 120.0,
    "synthprofile.trc_gamma": 2.4,
    "synthprofile.trc_gamma_type": "G",
    "synthprofile.trc_output_offset": 0.0,
    "tc_adaption": 0.1,
    "tc_add_ti3_relative": 1,
    "tc_algo": "",
    "tc_angle": 0.3333,
    "tc_black_patches": 4,
    "tc_export_repeat_patch_max": 1,
    "tc_export_repeat_patch_min": 1,
    "tc_filter": 0,
    "tc_filter_L": 50,
    "tc_filter_a": 0,
    "tc_filter_b": 0,
    "tc_filter_rad": 255,
    "tc_fullspread_patches": 0,
    "tc_gamma": 1.0,
    "tc_gray_patches": 9,
    "tc_multi_bcc": 0,
    "tc_multi_bcc_steps": 0,
    "tc_multi_steps": 3,
    "tc_neutral_axis_emphasis": 0.5,
    "tc_dark_emphasis": 0.0,
    "tc_precond": 0,
    "tc_precond_profile": "",
    "tc.saturation_sweeps": 5,
    "tc.saturation_sweeps.custom.R": 0.0,
    "tc.saturation_sweeps.custom.G": 0.0,
    "tc.saturation_sweeps.custom.B": 0.0,
    "tc_single_channel_patches": 0,
    "tc_vrml_black_offset": 40,
    "tc_vrml_cie": 0,
    "tc_vrml_cie_colorspace": "Lab",
    "tc_vrml_device_colorspace": "RGB",
    "tc_vrml_device": 1,
    "tc_vrml_use_D50": 0,
    "tc_white_patches": 4,
    "tc.show": 0,
    # Profile type forced to matrix due to OS X bugs with cLUT profiles.
    # Set smallest testchart.
    "testchart.auto_optimize": 4 if sys.platform != "darwin" else 1,
    "testchart.file": "auto",
    "testchart.file.backup": "auto",
    "testchart.patch_sequence": "optimize_display_response_delay",
    "testchart.reference": "",
    "ti3.check_sanity.auto": 0,
    "trc": 2.2,
    "trc.backup": 2.2,
    "trc.should_use_viewcond_adjust.show_msg": 1,
    "trc.type": "g",
    "trc.type.backup": "g",
    "uniformity.cols": 5,
    "uniformity.measure.continuous": 0,
    "uniformity.rows": 5,
    "untethered.measure.auto": 1,
    "untethered.measure.manual.delay": 0.75,
    "untethered.max_delta.chroma": 0.5,
    "untethered.min_delta": 1.5,
    "untethered.min_delta.lightness": 1.0,
    "update_check": 1,
    "use_fancy_progress": 1,
    "use_separate_lut_access": 0,
    "vrml.compress": 1,
    "webserver.portnumber": 8080,
    "whitepoint.colortemp": 6500,
    "whitepoint.colortemp.backup": 6500,
    "whitepoint.colortemp.locus": "t",
    "whitepoint.visual_editor.bg_v": 255,
    "whitepoint.visual_editor.b": 255,
    "whitepoint.visual_editor.g": 255,
    "whitepoint.visual_editor.r": 255,
    "whitepoint.x": 0.3127,
    "whitepoint.x.backup": 0.3127,
    "whitepoint.y": 0.3290,
    "whitepoint.y.backup": 0.3290,
    "x3dom.cache": 1,
    "x3dom.embed": 0,
}
LCODE, LENC = locale.getlocale()
if LCODE:
    DEFAULTS["lang"] = LCODE.split("_")[0].lower()

TESTCHART_DEFAULTS = {
    "s": {None: "auto"},  # shaper + matrix
    "l": {None: "auto"},  # lut
    "g": {None: "auto"},  # gamma + matrix
}


def _init_testcharts():
    RES_FILES.extend(
        os.path.join("ti1", chart)
        for testcharts in list(TESTCHART_DEFAULTS.values())
        for chart in [value for value in list(testcharts.values()) if value != "auto"]
    )
    TESTCHART_DEFAULTS["G"] = TESTCHART_DEFAULTS["g"]
    TESTCHART_DEFAULTS["S"] = TESTCHART_DEFAULTS["s"]
    for key in ("X", "x"):
        TESTCHART_DEFAULTS[key] = TESTCHART_DEFAULTS["l"]


def getcfg(name, fallback=True, raw=False, cfg=CFG):
    """Get and return an option value from the configuration.

    If fallback evaluates to True and the option is not set,
    return its default value.
    """
    if name == "profile.name.expanded" and is_ccxx_testchart():
        name = "measurement.name.expanded"
    value = None
    hasdef = name in DEFAULTS
    if hasdef:
        defval = DEFAULTS[name]
        deftype = type(defval)

    if cfg.has_option(configparser.DEFAULTSECT, name):
        try:
            value = cfg.get(configparser.DEFAULTSECT, name)
        except UnicodeDecodeError:
            pass
        else:
            # Check for invalid types and return default if wrong type
            if raw:
                pass
            elif (
                (name != "trc" or value not in VALID_VALUES["trc"])
                and hasdef
                and isinstance(defval, (Decimal, int, float))
            ):
                try:
                    value = deftype(value)
                except ValueError:
                    value = defval
                else:
                    valid_range = VALID_RANGES.get(name)
                    if valid_range:
                        value = min(max(valid_range[0], value), valid_range[1])
                    elif name in VALID_VALUES and value not in VALID_VALUES[name]:
                        value = defval
            elif name.startswith("dimensions.measureframe"):
                try:
                    value = [max(0, float(n)) for n in value.split(",")]
                    if len(value) != 3:
                        raise ValueError
                except ValueError:
                    value = DEFAULTS[name]
                else:
                    value[0] = min(value[0], 1)
                    value[1] = min(value[1], 1)
                    value[2] = min(value[2], 50)
                    value = ",".join([str(n) for n in value])
            elif name == "profile.quality" and getcfg("profile.type") in ("g", "G"):
                # default to high quality for gamma + matrix
                value = "h"
            elif name == "trc.type" and getcfg("trc") in VALID_VALUES["trc"]:
                value = "g"
            elif name in VALID_VALUES and value not in VALID_VALUES[name]:
                if DEBUG:
                    print(f"Invalid config value for {name}: {value}", end=" ")
                value = None
            elif name == "copyright":
                # Make sure DisplayCAL and Argyll version are up-to-date
                pattern = re.compile(
                    rf"({APPNAME}(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*", re.I
                )
                repl = create_replace_function("\\1%s", VERSION_STRING)
                value = re.sub(pattern, repl, value)
                if APPBASENAME != APPNAME:
                    pattern = re.compile(
                        rf"({APPBASENAME}(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*",
                        re.I,
                    )
                    repl = create_replace_function("\\1%s", VERSION_STRING)
                    value = re.sub(pattern, repl, value)
                pattern = re.compile(
                    r"(Argyll(?:\s*CMS)?)((?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*",
                    re.I,
                )
                if defval.split()[-1] != "CMS":
                    repl = create_replace_function("\\1\\2%s", defval.split()[-1])
                else:
                    repl = "\\1"
                value = re.sub(pattern, repl, value)
            elif name == "measurement_mode":
                # Map n and r measurement modes to canonical l and c
                # the inverse mapping happens per-instrument in
                # Worker.add_measurement_features().
                # That way we can have compatibility with old and current
                # Argyll CMS
                value = {"n": "l", "r": "c"}.get(value, value)
    if value is None:
        if hasdef and fallback:
            value = defval
            if DEBUG > 1:
                print(name, "- falling back to", value)
        elif DEBUG and not hasdef:
            print("Warning - unknown option:", name)
    if raw:
        return value
    if (
        value
        and isinstance(value, str)
        and name.endswith("file")
        and name != "colorimeter_correction_matrix_file"
        and (name != "testchart.file" or value != "auto")
        and (not os.path.isabs(value) or not os.path.exists(value))
    ):
        # colorimeter_correction_matrix_file is special
        # because it's not (only) a path
        if DEBUG:
            print(f"{name} does not exist: {value}", end=" ")
        # Normalize path (important, this turns altsep into sep under Windows)
        value = os.path.normpath(value)
        # Check if this is a relative path covered by data_dirs
        if (
            value.split(os.path.sep)[-3:-2] == [APPNAME] or not os.path.isabs(value)
        ) and (
            value.split(os.path.sep)[-2:-1] == ["presets"]
            or value.split(os.path.sep)[-2:-1] == ["ref"]
            or value.split(os.path.sep)[-2:-1] == ["ti1"]
        ):
            value = os.path.join(*value.split(os.path.sep)[-2:])
            value = get_data_path(value)
        elif hasdef:
            value = None
        if not value and hasdef:
            value = defval
        if DEBUG > 1:
            print(name, "- falling back to", value)
    elif name in ("displays", "instruments"):
        if not value:
            return []
        value = [
            strtr(
                v,
                [
                    (f"%{hex(ord(os.pathsep))[2:].upper()}", os.pathsep),
                    ("%25", "%"),
                ],
            )
            for v in value.split(os.pathsep)
        ]
    return value


def hascfg(name, fallback=True, cfg=CFG):
    """Check if an option name exists in the configuration.

    Returns a boolean value.
    If fallback evaluates to True and the name does not exist, check defaults also.
    """
    if cfg.has_option(configparser.DEFAULTSECT, name):
        return True
    if fallback:
        return name in DEFAULTS
    return False


def get_ccxx_testchart():
    """Get the path to the default chart for CCMX/CCSS creation."""
    return get_data_path(
        os.path.join("ti1", DEFAULTS["colorimeter_correction.testchart"])
    )


def get_current_profile(include_display_profile=False):
    """Get the currently selected profile (if any)."""
    path = getcfg("calibration.file", False)
    if path:
        from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError

        try:
            profile = ICCProfile(path, use_cache=True)
        except (OSError, ICCProfileInvalidError):
            return None
        return profile
    if include_display_profile:
        return get_display_profile()
    return None


def get_display_profile(display_no: None | int = None) -> None | ICCProfile:
    """Get the display profile for the specified display number.

    Args:
        display_no (int, optional): The display number. If None, use the
            configured display number. Defaults to None.

    Returns:
        None | ICCProfile: The display profile if available, otherwise None.
    """
    if display_no is None:
        display_no = max(getcfg("display.number") - 1, 0)
    if is_virtual_display(display_no):
        return None
    from DisplayCAL.icc_profile import get_display_profile

    try:
        return get_display_profile(display_no)
    except Exception:
        from DisplayCAL.log import LOG

        print(f"DisplayCAL.icc_profile.get_display_profile({display_no}):", file=LOG)


STANDARD_PROFILES = []


def get_standard_profiles(paths_only: bool = False) -> list:
    """Get a list of standard ICC profiles.

    Args:
        paths_only (bool, optional): If True, return only the file paths of the
            profiles. Defaults to False.

    Returns:
        list: A list of standard ICC profiles or their file paths.
    """
    if not STANDARD_PROFILES:
        from DisplayCAL.icc_profile import ICCProfile

        # Reference profiles (Argyll + DisplayCAL)
        ref_icc = get_data_path("ref", r"\.ic[cm]$") or []
        # Other profiles installed on the system
        other_icc = []
        rex = re.compile(r"\.ic[cm]$", re.IGNORECASE)
        for icc_dir in set(ICCPROFILES + ICCPROFILES_HOME):
            for dirpath, _dirnames, basenames in os.walk(icc_dir):
                for basename in filter(rex.search, basenames):
                    filename, ext = os.path.splitext(basename.lower())
                    if (
                        filename.endswith(("_bas", "_eci", "adobergb1998"))
                        or filename.startswith(
                            (
                                "eci-rgb",
                                "ecirgb",
                                "ekta space",
                                "ektaspace",
                                "fogra",
                                "gracol",
                                "iso",
                                "lstar-",
                                "pso",
                                "prophoto",
                                "psr_",
                                "psrgravure",
                                "snap",
                                "srgb",
                                "swop",
                            )
                        )
                        or filename
                        in (
                            "applergb",
                            "bestrgb",
                            "betargb",
                            "brucergb",
                            "ciergb",
                            "cie-rgb",
                            "colormatchrgb",
                            "donrgb",
                            "widegamutrgb",
                        )
                    ):
                        other_icc.append(os.path.join(dirpath, basename))

        # Ensure ref_icc is a list
        if not isinstance(ref_icc, list):
            ref_icc = [ref_icc]

        for path in ref_icc + other_icc:
            try:
                profile = ICCProfile(path, load=False, use_cache=True)
            except OSError:
                pass
            except Exception as exception:
                print(exception)
            else:
                if (
                    profile.version < 4
                    and profile.profileClass != b"nmcl"
                    and profile.colorSpace != b"GRAY"
                    and profile.connectionColorSpace in (b"Lab", b"XYZ")
                ):
                    STANDARD_PROFILES.append(profile)
    if paths_only:
        return [profile.fileName for profile in STANDARD_PROFILES]
    return STANDARD_PROFILES


def get_total_patches(
    white_patches: None | int = None,
    black_patches: None | int = None,
    single_channel_patches: None | int = None,
    gray_patches: None | int = None,
    multi_steps: None | int = None,
    multi_bcc_steps: None | int = None,
    fullspread_patches: None | int = None,
) -> int:
    """Calculate the total number of patches in a test chart.

    Args:
        white_patches (int, optional): Number of white patches. Defaults to None.
        black_patches (int, optional): Number of black patches. Defaults to None.
        single_channel_patches (int, optional): Number of single channel patches.
            Defaults to None.
        gray_patches (int, optional): Number of gray patches. Defaults to None.
        multi_steps (int, optional): Number of multi steps. Defaults to None.
        multi_bcc_steps (int, optional): Number of multi BCC steps. Defaults to
            None.
        fullspread_patches (int, optional): Number of full spread patches.
            Defaults to None.

    Returns:
        int: Total number of patches.
    """
    if white_patches is None:
        white_patches = getcfg("tc_white_patches")
    if black_patches is None and getcfg("argyll.version") >= "1.6":
        black_patches = getcfg("tc_black_patches")
    if single_channel_patches is None:
        single_channel_patches = getcfg("tc_single_channel_patches")
    single_channel_patches_total = single_channel_patches * 3
    if gray_patches is None:
        gray_patches = getcfg("tc_gray_patches")
    if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
        gray_patches = 2
    if multi_steps is None:
        multi_steps = getcfg("tc_multi_steps")
    if multi_bcc_steps is None and getcfg("argyll.version") >= "1.6":
        multi_bcc_steps = getcfg("tc_multi_bcc_steps")
    if fullspread_patches is None:
        fullspread_patches = getcfg("tc_fullspread_patches")
    total_patches = 0
    if multi_steps > 1:
        multi_patches = int(math.pow(multi_steps, 3))
        if multi_bcc_steps > 1:
            multi_patches += int(math.pow(multi_bcc_steps - 1, 3))
        total_patches += multi_patches
        white_patches -= 1  # white always in multi channel patches

        multi_step = 255.0 / (multi_steps - 1)
        multi_values = []
        multi_bcc_values = []
        if multi_bcc_steps > 1:
            multi_bcc_step = multi_step
            multi_values.extend(str(multi_bcc_step * i) for i in range(multi_bcc_steps))
            multi_bcc_values.extend(
                str(multi_bcc_step / 2.0 * i) for i in range(multi_bcc_steps * 2 - 1)
            )
        else:
            multi_values.extend(str(multi_step * i) for i in range(multi_steps))
        if single_channel_patches > 1:
            single_channel_step = 255.0 / (single_channel_patches - 1)
            for i in range(single_channel_patches):
                if str(single_channel_step * i) in multi_values:
                    single_channel_patches_total -= 3
        if gray_patches > 1:
            gray_step = 255.0 / (gray_patches - 1)
            for i in range(gray_patches):
                if (
                    str(gray_step * i) in multi_values
                    or str(gray_step * i) in multi_bcc_values
                ):
                    gray_patches -= 1
    elif gray_patches > 1:
        white_patches -= 1  # white always in gray patches
        single_channel_patches_total -= 3  # black always in gray patches
    elif single_channel_patches_total:
        # black always only once in single channel patches
        single_channel_patches_total -= 2
    total_patches += (
        max(0, white_patches)
        + max(0, single_channel_patches_total)
        + max(0, gray_patches)
        + fullspread_patches
    )
    if black_patches:
        if gray_patches > 1 or single_channel_patches_total or multi_steps:
            black_patches -= 1  # black always in other patches
        total_patches += black_patches
    return total_patches


def get_verified_path(cfg_item_name, path=None):
    """Verify and return directory and filename for a user cfg path or given path.

    Args:
        cfg_item_name (str): Config item name to retrieve the path.
        path (str, optional): Path to verify. Defaults to None.

    Returns:
        tuple: A tuple containing the directory and filename.
    """
    defaultPath = path or getcfg(cfg_item_name)
    defaultDir = expanduseru("~")
    defaultFile = ""
    if defaultPath:
        if os.path.exists(defaultPath):
            defaultDir, defaultFile = (
                os.path.dirname(defaultPath),
                os.path.basename(defaultPath),
            )
        elif DEFAULTS.get(cfg_item_name) and os.path.exists(DEFAULTS[cfg_item_name]):
            defaultDir, defaultFile = (
                os.path.dirname(DEFAULTS[cfg_item_name]),
                os.path.basename(DEFAULTS[cfg_item_name]),
            )
        elif os.path.exists(os.path.dirname(defaultPath)):
            defaultDir = os.path.dirname(defaultPath)
    return defaultDir, defaultFile


def is_ccxx_testchart(testchart: None | str = None) -> bool:
    """Check whether the testchart is the default chart for CCMX/CCSS creation.

    Args:
        testchart (None | str): The testchart to check.
            If not provided, the default testchart will be used.

    Returns:
        bool: True if the testchart is the default chart for CCMX/CCSS creation,
            False otherwise.
    """
    testchart = testchart or getcfg("testchart.file")
    return testchart == get_ccxx_testchart()


def is_profile(
    filename: None | str = None, include_display_profile: bool = False
) -> bool:
    """Check if the given filename is a valid ICC profile.

    Args:
        filename (None | str): The filename to check.
            If not provided, the default calibration file will be used.
        include_display_profile (bool): Whether to include the display profile
            in the check. Defaults to False.

    Returns:
        bool: True if the filename is a valid ICC profile,
            False otherwise.
    """
    filename = filename or getcfg("calibration.file", False)
    if filename:
        if os.path.exists(filename):
            from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError

            try:
                ICCProfile(filename, use_cache=True)
            except (OSError, ICCProfileInvalidError):
                pass
            else:
                return True
    elif include_display_profile:
        return bool(get_display_profile())
    return False


def makecfgdir(which=None, worker=None) -> bool:
    """Create the configuration directory.

    Args:
        which (None | str): The type of configuration directory to create.
            Can be "user" or "system". Defaults to "user".
        worker (None | Worker): The worker instance to use for executing commands.
            Defaults to None.

    Returns:
        bool: True if the configuration directory was created successfully,
            False otherwise.
    """
    if which is None:
        which = "user"

    if which == "user":
        if not os.path.exists(CONFIG_HOME):
            try:
                os.makedirs(CONFIG_HOME)
            except Exception as exception:
                print(
                    "Warning - could not create configuration directory "
                    f"'{CONFIG_HOME}': {exception}"
                )
                return False
    elif not os.path.exists(CONFIG_SYS):
        try:
            if sys.platform == "win32":
                os.makedirs(CONFIG_SYS)
            else:
                result = worker.exec_cmd(
                    "mkdir",
                    ["-p", CONFIG_SYS],
                    capture_output=True,
                    low_contrast=False,
                    skip_scripts=True,
                    silent=True,
                    asroot=True,
                )
                if isinstance(result, Exception):
                    raise result
        except Exception as exception:
            print(
                "Warning - could not create configuration directory "
                f"'{CONFIG_SYS}': {exception}"
            )
            return False
    return True


CFGINITED = {}


def initcfg(module=None, cfg=CFG, force_load=False):
    """Initialize the configuration.

    Read in settings if the configuration file exists, else create the
    settings directory if nonexistent.
    """
    cfgbasename = f"{APPBASENAME}-{module}" if module else APPBASENAME
    makecfgdir()
    cfg_full_path = os.path.join(CONFIG_HOME, f"{cfgbasename}.ini")
    if os.path.exists(CONFIG_HOME) and not os.path.exists(cfg_full_path):
        if not cfg.has_section(configparser.DEFAULTSECT):
            # No Default section, add it...
            cfg.add_section(configparser.DEFAULTSECT)
        # Set default preset
        setcfg("calibration.file", DEFAULTS["calibration.file"], cfg=cfg)

    # Read cfg
    cfgnames = [APPBASENAME]
    if module:
        cfgnames.append(cfgbasename)
    else:
        cfgnames.extend(
            f"{APPBASENAME}-{othermod}" for othermod in ("testchart-editor",)
        )

    cfgroots = [CONFIG_HOME]
    if module == "apply-profiles":
        cfgroots.append(CONFIG_SYS)

    cfgfiles = []
    for cfgname in cfgnames:
        for cfgroot in cfgroots:
            cfgfile = os.path.join(cfgroot, f"{cfgname}.ini")
            if not os.path.isfile(cfgfile):
                continue
            try:
                mtime = os.stat(cfgfile).st_mtime
            except OSError as exception:
                print(f"Warning - os.stat('{cfgfile}') failed: {exception}")
            last_checked = CFGINITED.get(cfgfile)
            if force_load or mtime != last_checked:
                CFGINITED[cfgfile] = mtime
                cfgfiles.append(cfgfile)
                if force_load:
                    msg = "Force loading"
                elif last_checked:
                    msg = "Reloading"
                else:
                    msg = "Loading"
                # logger.debug(msg, cfgfile)
                print(msg, cfgfile)
            # Make user config take precedence
            break
    if not cfgfiles:
        return
    if not module:
        # Make most recent file take precedence
        cfgfiles.sort(key=lambda cfgfile: CFGINITED.get(cfgfile))
    try:
        cfg.read(cfgfiles)
    # This won't raise an exception if the file does not exist,
    # only if it can't be parsed
    except Exception:
        print(
            "Warning - could not parse configuration files:\n{}".format(
                "\n".join(cfgfiles)
            )
        )
        # Fix Python 2.7 ConfigParser option values being lists instead of
        # strings in case of a ParsingError. http://bugs.python.org/issue24142
        all_sections = [configparser.DEFAULTSECT]
        all_sections.extend(cfg.sections())
        for section in all_sections:
            for name, val in cfg.items(section):
                if isinstance(val, list):
                    cfg.set(section, name, "\n".join(val))
    finally:
        if not module and not getcfg("calibration.ambient_viewcond_adjust"):
            # Reset to default
            setcfg("calibration.ambient_viewcond_adjust.lux", None, cfg=cfg)


DPISET = False


def set_default_app_dpi():
    """Set application DPI."""
    # Only call this after creating the wx.App object!
    global DPISET
    if not DPISET and not getcfg("app.dpi", False):
        # HighDPI support
        from DisplayCAL.wx_addons import wx

        DPISET = True
        if sys.platform in ("darwin", "win32"):
            # Determine screen DPI
            dpi = wx.ScreenDC().GetPPI()[0]
        else:
            # Linux
            from DisplayCAL.util_os import which

            txt_scale = None
            # XDG_CURRENT_DESKTOP delimiter is colon (':')
            desktop = os.getenv("XDG_CURRENT_DESKTOP", "").split(":")
            if "gtk2" in wx.PlatformInfo:
                txt_scale = get_hidpi_scaling_factor()
            elif desktop[0] == "KDE":
                pass
            # Nothing to do
            elif which("gsettings"):
                import subprocess as sp

                p = sp.Popen(
                    [  # noqa: S607
                        "gsettings",
                        "get",
                        "org.gnome.desktop.interface",
                        "text-scaling-factor",
                    ],
                    stdin=sp.PIPE,
                    stdout=sp.PIPE,
                    stderr=sp.PIPE,
                )
                factor, stderr = p.communicate()
                with contextlib.suppress(ValueError):
                    txt_scale = float(factor)
            dpi = get_default_dpi()
            if txt_scale:
                dpi = round(dpi * txt_scale)
        DEFAULTS["app.dpi"] = dpi
    DPISET = True


def get_hidpi_scaling_factor() -> float:
    """Get the scaling factor for high DPI displays.

    Returns:
        float: The scaling factor for high DPI displays.
    """
    if sys.platform in ("darwin", "win32"):
        return 1.0  # Handled via app DPI
    # Linux
    from DisplayCAL.util_os import which

    if which("xrdb"):
        import subprocess as sp

        p = sp.Popen(
            ["xrdb", "-query"],  # noqa: S607
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        # Format: 'Xft.dpi:        192'
        stdout, stderr = p.communicate()
        for line in stdout.splitlines():
            line = line.decode()
            if line.startswith("Xft.dpi:"):
                split = line.split()
                dpi = split[-1]
                try:
                    return float(dpi) / get_default_dpi()
                except ValueError:
                    pass
    factor = None
    # XDG_CURRENT_DESKTOP delimiter is colon (':')
    desktop = os.getenv("XDG_CURRENT_DESKTOP", "").split(":")
    if desktop[0] == "KDE":
        # Two env-vars exist: QT_SCALE_FACTOR and QT_SCREEN_SCALE_FACTORS.
        # According to documentation[1], the latter is 'mainly useful for debugging'
        # that's not how it is used by KDE though.
        # Changing display scaling via KDE settings GUI only sets
        # QT_SCREEN_SCALE_FACTORS. We are thus currently ignoring QT_SCALE_FACTOR.
        # [1] https://doc.qt.io/qt-5/highdpi.html
        # QT_SCREEN_SCALE_FACTORS delimiter is semicolon (';')
        # Format: Mapping of XrandR display names to scale factor
        # e.g. 'VGA-1=1.5;VGA-2=2.0;'
        # or just list of scale factors e.g. '1.5;2.0;'
        screen_scale_factors = os.getenv("QT_SCREEN_SCALE_FACTORS", "").split(";")
        if screen_scale_factors:
            from DisplayCAL.wx_addons import wx

            match = False
            app = wx.GetApp()
            if app:
                from DisplayCAL import real_display_size_mm

                if not real_display_size_mm._displays:
                    real_display_size_mm.enumerate_displays()
                top = app.TopWindow
                if top:
                    tmp = False
                else:
                    # Create temp frame if no topwindow
                    top = wx.Frame(None)
                    # Move to main window location (and thus screen)
                    x, y = (
                        getcfg("position.x", False),
                        getcfg("position.y", False),
                    )
                    if None not in (x, y):
                        top.SetSaneGeometry(x, y)
                    tmp = True
                # Get wx display
                wx_display = top.GetDisplay()
                if tmp:
                    # No longer need our temp frame
                    top.Destroy()
                # Search for matching display based on geometry
                pos = wx_display.Geometry[:2]
                size = wx_display.Geometry[2:]
                for item in screen_scale_factors:
                    if not item:
                        break
                    if "=" in item:
                        name, factor = item.split("=", 1)
                    else:
                        name, factor = None, item
                    for display in real_display_size_mm._displays:
                        if display.get("pos") != pos or display.get("size") != size:
                            # No match
                            continue
                        if name and display.get("xrandr_name") != name:
                            # No match
                            continue
                        # Match found
                        match = True
                        break
                    if match:
                        break
            if not match:
                # Use first one
                factor = screen_scale_factors[0].split("=")[-1]
    if not factor and which("gsettings"):
        # GNOME
        import subprocess as sp

        p = sp.Popen(
            ["gsettings", "get", "org.gnome.desktop.interface", "scaling-factor"],  # noqa: S607
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        # Format: 'unint32 1'
        stdout, stderr = p.communicate()
        split = stdout.split()
        if split:
            factor = split[-1]
    if factor is not None:
        try:
            factor = float(factor)
        except ValueError:
            factor = None
    return factor


def setcfg(name, value, cfg=CFG):
    """Set an option value in the configuration."""
    if value is None:
        cfg.remove_option(configparser.DEFAULTSECT, name)
    else:
        if name in ("displays", "instruments") and isinstance(value, (list, tuple)):
            value = os.pathsep.join(
                strtr(
                    v,
                    [
                        ("%", "%25"),
                        (os.pathsep, f"%{hex(ord(os.pathsep))[2:].upper()}"),
                    ],
                )
                for v in value
            )
        cfg.set(configparser.DEFAULTSECT, name, value)


def setcfg_cond(condition, name, value, set_if_backup_exists=False, restore=True):
    """Set configuration conditionally.

    If <condition>, backup configuration option <name> if not yet backed up
    and set option to <value> if backup did not previously exist or
    set_if_backup_exists evaluates to True.

    If not <condition> and backed up option <name>, restore option <name> to
    backed up value and discard backup if <restore> evaluates to True

    Return whether or not configuration was changed
    """
    changed = False
    backup = getcfg(f"{name}.backup", False)
    if condition:
        if backup is None:
            setcfg(f"{name}.backup", getcfg(name))
        if backup is None or set_if_backup_exists:
            setcfg(name, value)
            changed = True
    elif backup is not None and restore:
        setcfg(name, getcfg(f"{name}.backup"))
        setcfg(f"{name}.backup", None)
        changed = True
    return changed


def writecfg(
    which: str = "user", worker=None, module=None, options=(), cfg=CFG
) -> bool:
    """Write configuration file.

    Args:
        which (str): 'user' or 'system'
        worker (DisplayCAL.worker.Worker): worker instance if ``which == 'system'``
        module (None | str): module name.
        options (tuple[str]): options to write.
        cfg (configparser.ConfigParser): configuration instance.

    Returns:
        bool: True if successful, False otherwise.
    """
    cfgbasename = f"{APPBASENAME}-{module}" if module else APPBASENAME
    # Remove unknown options
    for name, _val in cfg.items(configparser.DEFAULTSECT):
        if name not in DEFAULTS:
            print("Removing unknown option:", name)
            setcfg(name, None)
    if which == "user":
        # user config - stores everything and overrides system-wide config
        cfgfilename = os.path.join(CONFIG_HOME, f"{cfgbasename}.ini")
        try:
            io = StringIO()
            cfg.write(io)
            io.seek(0)
            lines = io.read().strip("\n").split("\n")
            if options:
                optionlines = [
                    optionline
                    for optionline in lines[1:]
                    for option in options
                    if optionline.startswith(option)
                ]
            else:
                optionlines = lines[1:]
            # Sorting works as long as config has only one section
            lines = lines[:1] + sorted(optionlines)
            with open(cfgfilename, "wb") as cfgfile:
                cfgfile.write((os.linesep.join(lines) + os.linesep).encode())
        except Exception as exception:
            print(
                "Warning - could not write user configuration file "
                f"'{cfgfilename}': {exception}"
            )
            return False
    else:
        # system-wide config - only stores essentials ie. Argyll directory
        cfgfilename1 = os.path.join(CONFIG_HOME, f"{cfgbasename}.local.ini")
        cfgfilename2 = os.path.join(CONFIG_SYS, f"{cfgbasename}.ini")
        if sys.platform == "win32":
            cfgfilename = cfgfilename2
        else:
            cfgfilename = cfgfilename1
        try:
            if getcfg("argyll.dir"):
                with open(cfgfilename, "wb") as cfgfile:
                    cfgfile.write(
                        (
                            "{}{}".format(
                                os.linesep.join(
                                    [
                                        "[Default]",
                                        f"argyll.dir = {getcfg('argyll.dir')}",
                                    ]
                                ),
                                os.linesep,
                            )
                        ).encode()
                    )
            if sys.platform != "win32":
                # on Linux and OS X, we write the file to the user's config dir
                # then 'su mv' it to the system-wide config dir
                result = worker.exec_cmd(
                    "mv",
                    ["-f", cfgfilename1, cfgfilename2],
                    capture_output=True,
                    low_contrast=False,
                    skip_scripts=True,
                    silent=True,
                    asroot=True,
                )
                if isinstance(result, Exception):
                    raise result
        except Exception as exception:
            print(
                "Warning - could not write system-wide configuration file "
                f"'{cfgfilename2}': {exception}"
            )
            return False
    return True


_init_testcharts()
RUNTYPE = runtimeconfig(PYFILE)


if sys.platform in ("darwin", "win32") and not os.getenv("SSL_CERT_FILE"):
    try:
        import certifi
    except ImportError:
        CAFILE = None
    else:
        CAFILE = certifi.where()
        if CAFILE and not os.path.isfile(CAFILE):
            CAFILE = None
    if not CAFILE:
        # Use our bundled CA file
        CAFILE = get_data_path("cacert.pem")
    if CAFILE and isinstance(CAFILE, str):
        os.environ["SSL_CERT_FILE"] = CAFILE
