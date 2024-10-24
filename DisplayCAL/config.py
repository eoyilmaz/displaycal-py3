# -*- coding: utf-8 -*-
"""Runtime configuration and user settings parser."""

import configparser
import locale
import math
import os
import re
import string
import sys
from decimal import Decimal

from DisplayCAL import colormath
from DisplayCAL.argyll_names import intents, observers, video_encodings, viewconds
from DisplayCAL.defaultpaths import (  # noqa: F401
    appdata,
    autostart,  # don't remove this, imported by other modules
    autostart_home,  # don't remove this, imported by other modules
    commonappdata,
    home,  # don't remove this, imported by other modules
    iccprofiles,
    iccprofiles_home,
)
from DisplayCAL.meta import (  # noqa: F401
    build,  # don't remove this, imported by other modules
    name as appname,
    version,
)
from DisplayCAL.options import debug
from DisplayCAL.safe_print import (  # noqa: F401
    enc,  # don't remove this, imported by other modules
    fs_enc,
)
from DisplayCAL.util_io import (
    StringIOu as StringIO,
)
from DisplayCAL.util_os import (
    expanduseru,
    getenvu,
    is_superuser,
    listdir_re,
    which,
)
from DisplayCAL.util_str import create_replace_function, strtr
from DisplayCAL.wxaddons import wx

if sys.platform == "win32":
    from DisplayCAL.defaultpaths import commonprogramfiles
elif sys.platform == "darwin":
    from DisplayCAL.defaultpaths import library, library_home, prefs, prefs_home
else:
    from DisplayCAL.defaultpaths import (
        xdg_config_dir_default,
        xdg_config_home,
        xdg_data_dirs,
        xdg_data_home,
        xdg_data_home_default,
    )

configparser.DEFAULTSECT = "Default"  # Sadly, this line needs to be here.

exe = sys.executable
exedir = os.path.dirname(exe)
exename = os.path.basename(exe)

isexe = sys.platform != "darwin" and getattr(sys, "frozen", False)

if isexe:
    _meipass2 = os.getenv("_MEIPASS2")
    if _meipass2:
        os.environ["_MEIPASS2"] = _meipass2.replace("/", os.path.sep)

pyfile = (
    exe
    if isexe
    else (os.path.isfile(sys.argv[0]) and sys.argv[0])
    or os.path.join(os.path.dirname(__file__), "main.py")
)
pypath = exe if isexe else os.path.abspath(pyfile)
# Mac OS X: isapp should only be true for standalone, not 0install
isapp = (
    sys.platform == "darwin"
    and exe.split(os.path.sep)[-3:-1] == ["Contents", "MacOS"]
    and os.path.exists(os.path.join(exedir, "..", "Resources", "xrc"))
)
if isapp:
    pyname, pyext = os.path.splitext(exe.split(os.path.sep)[-4])
    pydir = os.path.normpath(os.path.join(exedir, "..", "Resources"))
else:
    pyname, pyext = os.path.splitext(os.path.basename(pypath))
    pydir = os.path.dirname(
        exe if isexe else os.path.abspath(os.path.dirname(__file__))
    )

# TODO: Modifying ``data_dirs`` here was not an elegant solution,
#       and it is not solving the problem either.
data_dirs = [
    # venv/share/DisplayCAL
    os.path.join(os.path.dirname(os.path.dirname(pypath)), "share", "DisplayCAL"),
    # venv/lib/python3.x/site-packages/DisplayCAL
    pydir,
    # venv/share
    os.path.join(os.path.dirname(pydir), "share"),
    # venv/lib/python3.x/site-packages/DisplayCAL-*.egg/share/DisplayCAL
    os.path.join(os.path.dirname(pydir), "share", "DisplayCAL"),
]


extra_data_dirs = []
# Search directories on PATH for data directories so Argyll reference files can
# be found automatically if Argyll directory not explicitly configured
for dir_ in getenvu("PATH", "").split(os.pathsep):
    dir_parent = os.path.dirname(dir_)
    if os.path.isdir(os.path.join(dir_parent, "ref")):
        extra_data_dirs.append(dir_parent)

appbasename = appname
# If old user data directory exists, use its basename
if os.path.isdir(os.path.join(appdata, "dispcalGUI")):
    appbasename = "dispcalGUI"
    data_dirs.append(os.path.join(appdata, appname))
datahome = os.path.join(appdata, appbasename)
if sys.platform == "win32":
    if pydir.lower().startswith(exedir.lower()) and pydir != exedir:
        # We are installed in a subfolder of the executable directory
        # (e.g. C:\Python26\Lib\site-packages\DisplayCAL)
        # we need to add the executable directory to the data directories so
        # files in subfolders of the executable directory which are not in
        # Lib\site-packages\DisplayCAL can be found
        # (e.g. Scripts\displaycal-apply-profiles)
        data_dirs.append(exedir)
    script_ext = ".cmd"
    scale_adjustment_factor = 1.0
    config_sys = os.path.join(commonappdata[0], appbasename)
    confighome = os.path.join(appdata, appbasename)
    logdir = os.path.join(datahome, "logs")
    if appbasename != appname:
        data_dirs.extend(os.path.join(dir_, appname) for dir_ in commonappdata)
        data_dirs.append(os.path.join(commonprogramfiles, appname))
    data_dirs.append(datahome)
    data_dirs.extend(os.path.join(dir_, appbasename) for dir_ in commonappdata)
    data_dirs.append(os.path.join(commonprogramfiles, appbasename))
    profile_ext = ".icm"
    exe_ext = ".exe"
else:
    if sys.platform == "darwin":
        script_ext = ".command"
        mac_create_app = True
        scale_adjustment_factor = 1.0
        config_sys = os.path.join(prefs, appbasename)
        confighome = os.path.join(prefs_home, appbasename)
        logdir = os.path.join(expanduseru("~"), "Library", "Logs", appbasename)
        if appbasename != appname:
            data_dirs.append(os.path.join(commonappdata[0], appname))
        data_dirs.append(datahome)
        data_dirs.append(os.path.join(commonappdata[0], appbasename))
    else:
        script_ext = ".sh"
        scale_adjustment_factor = 1.0
        config_sys = os.path.join(xdg_config_dir_default, appbasename)
        confighome = os.path.join(xdg_config_home, appbasename)
        logdir = os.path.join(datahome, "logs")
        if appbasename != appname:
            datahome_default = os.path.join(xdg_data_home_default, appname)
            if datahome_default not in data_dirs:
                data_dirs.append(datahome_default)
            data_dirs.extend(os.path.join(dir_, appname) for dir_ in xdg_data_dirs)
        data_dirs.append(datahome)
        datahome_default = os.path.join(xdg_data_home_default, appbasename)
        if datahome_default not in data_dirs:
            data_dirs.append(datahome_default)
        data_dirs.extend(os.path.join(dir_, appbasename) for dir_ in xdg_data_dirs)
        extra_data_dirs.extend(
            os.path.join(dir_, "argyllcms") for dir_ in xdg_data_dirs
        )
        extra_data_dirs.extend(
            os.path.join(dir_, "color", "argyll") for dir_ in xdg_data_dirs
        )
    exe_ext = ""
    profile_ext = ".icc"

storage = os.path.join(datahome, "storage")

resfiles = [
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

bitmaps = {}

# Does the device not support iterative calibration?
uncalibratable_displays = ("Untethered$",)

# Can the device generate patterns of its own?
patterngenerators = ("madVR$", "Resolve$", "Chromecast ", "Prisma ", "Prisma$")

non_argyll_displays = uncalibratable_displays + ("Resolve$",)

# Is the device directly connected or e.g. driven via network?
# (note that madVR can technically be both, but the endpoint is always directly
# connected to a display so we have videoLUT access via madVR's API.
# Only devices which don't support that are considered 'untethered' in this context)
untethered_displays = non_argyll_displays + (
    "Web$",
    "Chromecast ",
    "Prisma ",
    "Prisma$",
)

# Is the device not an actual display device (i.e. is it not a TV or monitor)?
virtual_displays = untethered_displays + ("madVR$",)


def is_special_display(display=None, tests=virtual_displays):
    """
    Check if the display is a special display.

    Args:
        display (str): The display name.
        tests (list): List of special display patterns.

    Returns:
        bool: True if the display is special, False otherwise.
    """
    if not isinstance(display, str):
        display = get_display_name(display)
    for test in tests:
        if re.match(test, display):
            return True
    return False


def is_uncalibratable_display(display=None):
    """
    Check if the display is uncalibratable.

    Args:
        display (str): The display name.

    Returns:
        bool: True if the display is uncalibratable, False otherwise.
    """
    return is_special_display(display, uncalibratable_displays)


def is_patterngenerator(display=None):
    return is_special_display(display, patterngenerators)


def is_non_argyll_display(display=None):
    return is_special_display(display, non_argyll_displays)


def is_untethered_display(display=None):
    """
    Check if the display is untethered.

    Args:
        display (str): The display name.

    Returns:
        bool: True if the display is untethered, False otherwise.
    """
    return is_special_display(display, untethered_displays)


def is_virtual_display(display=None):
    """
    Check if the display is virtual.

    Args:
        display (str): The display name.

    Returns:
        bool: True if the display is virtual, False otherwise.
    """
    return is_special_display(display, virtual_displays)


def check_3dlut_format(devicename):
    """
    Check the 3D LUT format for the given device.

    Args:
        devicename (str): The name of the device.

    Returns:
        bool: True if the 3D LUT format is correct, False otherwise.
    """
    if get_display_name(None, True) == devicename:
        if devicename == "Prisma":
            return (
                getcfg("3dlut.format") == "3dl"
                and getcfg("3dlut.size") == 17
                and getcfg("3dlut.bitdepth.input") == 10
                and getcfg("3dlut.bitdepth.output") == 12
            )


def getbitmap(name, display_missing_icon=True, scale=True, use_mask=False):
    """
    Create (if necessary) and return a named bitmap.

    name has to be a relative path to a png file, omitting the extension,
    e.g. 'theme/mybitmap' or 'theme/icons/16x16/myicon',
    which is searched for in the data directories.
    If a matching file is not found, a placeholder bitmap is returned.
    The special name 'empty' will always return a transparent bitmap of the given size,
    e.g. '16x16/empty' or just 'empty' (size defaults to 16x16 if not given).
    """
    if name not in bitmaps:
        bitmaps[name] = create_bitmap(name, display_missing_icon, scale, use_mask)
    return bitmaps[name]


def create_bitmap(name, display_missing_icon, scale, use_mask):
    """
    Create a bitmap with the specified name and dimensions.

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
    if scale:
        scale = getcfg("app.dpi") / get_default_dpi()
    else:
        scale = 1
    if scale > 1:
        # HighDPI support
        w = int(round(w * scale))
        h = int(round(h * scale))
    if parts[-1] == "empty":
        return create_empty_bitmap(w, h, use_mask)
    else:
        return load_bitmap(parts, ow, oh, w, h, scale, use_mask)


def create_empty_bitmap(w, h, use_mask):
    """
    Create an empty bitmap with the specified dimensions.

    Args:
        w (int): Width of the bitmap.
        h (int): Height of the bitmap.
        use_mask (bool): Whether to use a mask for the bitmap.

    Returns:
        wx.Bitmap: The created empty bitmap.
    """
    if wx.VERSION[0] < 3:
        use_mask = True
    if use_mask and sys.platform == "win32":
        bmp = wx.EmptyBitmap(w, h)
        bmp.SetMaskColour(wx.Colour(0, 0, 0))
    else:
        bmp = wx.EmptyBitmapRGBA(w, h, 255, 0, 255, 0)
    return bmp


def load_bitmap(parts, ow, oh, w, h, scale, use_mask):
    """
    Load a bitmap from the specified parts and dimensions.

    Args:
        parts (list): A list of parts representing the path to the bitmap.
        ow (int): Original width of the bitmap.
        oh (int): Original height of the bitmap.
        w (int): New width of the bitmap.
        h (int): New height of the bitmap.
        scale (float): Scale factor for the bitmap.
        use_mask (bool): Whether to use a mask for the bitmap.

    Returns:
        wx.Bitmap: The loaded bitmap.
    """
    if parts[-1].startswith(appname):
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
    for i in range(5):
        if scale > 1:
            if len(size) == 2:
                # Icon
                if i == 0:
                    # HighDPI support. Try scaled size
                    parts[-2] = "%ix%i" % (w, h)
                elif i == 1:
                    if scale < 1.75 or scale == 2:
                        continue
                    # HighDPI support. Try @4x version
                    parts[-2] = "%ix%i" % (ow, oh)
                    parts[-1] = name4x
                elif i == 2:
                    # HighDPI support. Try @2x version
                    parts[-2] = "%ix%i" % (ow, oh)
                    parts[-1] = name2x
                elif i == 3:
                    # HighDPI support. Try original size times two
                    parts[-2] = "%ix%i" % (ow * 2, oh * 2)
                    parts[-1] = oname
                else:
                    # Try original size
                    parts[-2] = "%ix%i" % (ow, oh)
            else:
                # Theme graphic
                if i in (0, 3):
                    continue
                elif i == 1:
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
            appname.lower()
        ):
            # Search /usr/share/icons on Linux first
            path = get_data_path(
                "{}.png".format(os.path.join(parts[-2], "apps", parts[-1]))
            )
        if not path:
            path = get_data_path("{}.png".format(os.path.sep.join(parts)))
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
                w, h = [int(round(v / (2 * (3 - i)) * scale)) for v in bmp.Size]
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
                if len(factors) > 3:
                    alpha = factors[3]
                else:
                    alpha = 1.0
                img = img.AdjustChannels(R, G, B, alpha)
            if color:
                # Hex format, RRGGBB or RRGGBBAA
                R = int(color[0:2], 16) / 255.0
                G = int(color[2:4], 16) / 255.0
                B = int(color[4:6], 16) / 255.0
                if len(color) > 6:
                    alpha = int(color[6:8], 16) / 255.0
                else:
                    alpha = 1.0
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


def get_bitmap_as_icon(size, name, scale=True):
    """
    Like geticon, but return a wx.Icon instance.

    Get a bitmap as an icon with the specified size and name.

    Args:
        size (int): The size of the icon.
        name (str): The name of the icon.
        scale (bool): Whether to scale the icon.

    Returns:
        wx.Icon: The (created) icon (instance).
    """
    from DisplayCAL.wxaddons import wx

    icon = wx.EmptyIcon()
    if sys.platform == "darwin" and wx.VERSION >= (2, 9) and size > 128:
        # FIXME: wxMac 2.9 doesn't support icon sizes above 128
        size = 128
    bmp = geticon(size, name, scale)
    icon.CopyFromBitmap(bmp)
    return icon


def get_argyll_data_dir():
    """Return ArgyllCMS data dir.

    Returns:
        str: The ArgyllCMS data dir.
    """
    argyll_version = getcfg("argyll.version")
    if isinstance(argyll_version, str):
        argyll_version = list(map(int, argyll_version.split(".")))

    if argyll_version < [1, 5, 0]:
        argyll_data_dirname = "color"
    else:
        argyll_data_dirname = "ArgyllCMS"

    if sys.platform == "darwin" and argyll_version < [1, 5, 0]:
        return os.path.join(
            library if is_superuser() else library_home, argyll_data_dirname
        )
    else:
        return os.path.join(
            commonappdata[0] if is_superuser() else appdata, argyll_data_dirname
        )


def get_display_name(disp_index=None, include_geometry=False):
    """
    Return name of currently configured display.

    Args:
        disp_index (int): The index of the display.
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


def split_display_name(display):
    """
    Split and return name part of display.

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


def get_argyll_display_number(geometry):
    """
    Translate from wx display geometry to Argyll display index.

    Args:
        geometry (tuple): The geometry of the display.

    Returns:
        int: The Argyll display index.
    """
    geometry = f"{geometry[0]}, {geometry[1]}, {geometry[2]}x{geometry[3]}"
    for i, display in enumerate(getcfg("displays")):
        if display.find(f"@ {geometry}") > -1:
            if debug:
                print(f"[D] Found display {geometry} at index {i}")
            return i


def get_display_number(display_no):
    """
    Translate from Argyll display index to wx display index.

    Args:
        display_no (int): The Argyll display index.

    Returns:
        int: The wx display index.
    """
    if is_virtual_display(display_no):
        return 0
    from DisplayCAL.wxaddons import wx

    try:
        display = getcfg("displays")[display_no]
    except IndexError:
        return 0
    else:
        if display.endswith(" [PRIMARY]"):
            display = " ".join(display.split(" ")[:-1])
        for i in range(wx.Display.GetCount()):
            geometry = "{}, {}, {}x{}".format(*wx.Display(i).Geometry)
            if display.endswith(f"@ {geometry}"):
                if debug:
                    print(f"[D] Found display {geometry} at index {i}")
                return i
    return 0


def get_display_rects():
    """
    Return the Argyll enumerated display coordinates and sizes.

    Returns:
        list: A list of wx.Rect objects representing the display coordinates and sizes.
    """
    from DisplayCAL.wxaddons import wx

    display_rects = []
    for _i, display in enumerate(getcfg("displays")):
        match = re.search(r"@ (-?\d+), (-?\d+), (\d+)x(\d+)", display)
        if match:
            display_rects.append(wx.Rect(*[int(item) for item in match.groups()]))
    return display_rects


def get_icon_bundle(sizes, name):
    """
    Return a wx.IconBundle with given icon sizes.

    Args:
        sizes (list): A list of icon sizes.
        name (str): The name of the icon.

    Returns:
        wx.IconBundle: The icon bundle.
    """
    from DisplayCAL.wxaddons import wx

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


def get_instrument_name():
    """
    Return name of currently configured instrument.

    Returns:
        str: The name of the instrument.
    """
    n = getcfg("comport.number") - 1
    instrument_names = getcfg("instruments")
    if 0 <= n < len(instrument_names):
        return instrument_names[n]
    return ""


def get_measureframe_dimensions(dimensions_measureframe=None, percent=10):
    """Return measurement area size adjusted for percentage of screen area.

    Args:
        dimensions_measureframe (str): The dimensions of the measure frame.
        percent (int): The percentage of screen area.

    Returns:
        str: The adjusted dimensions of the measure frame.
    """
    if not dimensions_measureframe:
        dimensions_measureframe = getcfg("dimensions.measureframe")
    dimensions_measureframe = [float(n) for n in dimensions_measureframe.split(",")]
    dimensions_measureframe[2] *= defaults["size.measureframe"]
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
    """
    Search data_dirs for relpath and return the path or a file list.

    If relpath is a file, return the full path, if relpath is a directory,
    return a list of files in the intersection of searched directories.
    """
    if (
        not relpath
        or relpath.endswith(os.path.sep)
        or (isinstance(os.path.altsep, str) and relpath.endswith(os.path.altsep))
    ):
        return None
    dirs = list(data_dirs)
    argyll_dir = getcfg("argyll.dir") or os.path.dirname(
        os.path.realpath(which(f"dispcal{exe_ext}") or "")
    )
    if argyll_dir and os.path.isdir(os.path.join(argyll_dir, "..", "ref")):
        dirs.append(os.path.dirname(argyll_dir))
    dirs.extend(extra_data_dirs)
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
            if pth != "ref":
                curpath = os.path.join(dir_, pth)
            else:
                curpath = dir_
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
    """
    Configure remaining runtime options and return runtype.

    You need to pass in a path to the calling script (e.g. use the __file__ attribute).
    """
    # global safe_log
    from DisplayCAL.log import setup_logging

    setup_logging(logdir, pyname, pyext, confighome=confighome)
    if debug:
        print("[D] pydir:", pydir)
    if isapp:
        runtype = ".app"
    elif isexe:
        if debug:
            print("[D] _MEIPASS2 or pydir:", getenvu("_MEIPASS2", exedir))
        if getenvu("_MEIPASS2", exedir) not in data_dirs:
            data_dirs.insert(1, getenvu("_MEIPASS2", exedir))
        runtype = exe_ext
    else:
        pydir_parent = os.path.dirname(pydir)
        if debug:
            print(
                "[D] dirname(os.path.abspath(sys.argv[0])):",
                os.path.dirname(os.path.abspath(sys.argv[0])),
            )
            print("[D] pydir parent:", pydir_parent)
        if (
            os.path.dirname(os.path.abspath(sys.argv[0])) == pydir_parent
            and pydir_parent not in data_dirs
        ):
            # Add the parent directory of the package directory to our list of
            # data directories if it is the directory containing the currently
            # run script (e.g. when running from source)
            data_dirs.insert(1, pydir_parent)
        runtype = pyext
    for dir_ in sys.path:
        if not isinstance(dir_, str):
            dir_ = dir_.encode(fs_enc)
        dir_ = os.path.abspath(os.path.join(dir_, appname))
        if dir_ not in data_dirs and os.path.isdir(dir_):
            data_dirs.append(dir_)
            if debug:
                print("[D] from sys.path:", dir_)
    if sys.platform not in ("darwin", "win32"):
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", f"{appname}-{version}")
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", "packages", appname)
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", appname)
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", appname.lower())  # Debian
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "icons", "hicolor")
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
    if debug:
        print("[D] Data files search paths:\n[D]", "\n[D] ".join(data_dirs))
    defaults["calibration.file"] = get_data_path("presets/default.icc") or ""
    defaults["measurement_report.chart"] = (
        get_data_path(os.path.join("ref", "verify_extended.ti1")) or ""
    )
    return runtype


class CaseSensitiveConfigParser(configparser.RawConfigParser):
    def optionxform(self, optionstr):
        return optionstr


# User settings
cfg = CaseSensitiveConfigParser()
cfg["Default"] = {}


valid_ranges = {
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

valid_values = {
    "3d.format": ["HTML", "VRML", "X3D"],
    "3dlut.bitdepth.input": [8, 10, 12, 14, 16],
    "3dlut.bitdepth.output": [8, 10, 12, 14, 16],
    "3dlut.encoding.input": list(video_encodings),
    # collink: xvYCC output encoding is not supported
    "3dlut.encoding.output": [v for v in video_encodings if v not in ("T", "x", "X")],
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
    "3dlut.rendering_intent": intents,
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
    "colorimeter_correction.observer": observers,
    "colorimeter_correction.observer.reference": observers,
    "colorimeter_correction.type": ["matrix", "spectral"],
    # Measurement modes as supported by Argyll -y parameter
    # 'l' = 'n' (non-refresh-type display, e.g. LCD)
    # 'c' = 'r' (refresh-type display, e.g. CRT)
    # We map 'l' and 'c' to "n" and "r" in
    # worker.Worker.add_measurement_features if using Argyll >= 1.5
    # See http://www.argyllcms.com/doc/instruments.html for description of
    # per-instrument supported modes
    "measurement_mode": [None, "auto"] + list(string.digits[1:] + string.ascii_letters),
    "gamap_default_intent": ["a", "r", "p", "s"],
    "gamap_perceptual_intent": intents,
    "gamap_saturation_intent": intents,
    "gamap_src_viewcond": viewconds,
    "gamap_out_viewcond": ["mt", "mb", "md", "jm", "jd"],
    "measurement_report.trc_gamma_type": ["b", "B"],
    "observer": observers,
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
    # Q = Argyll >= 1.1.0
    "tc_algo": ["", "t", "r", "R", "q", "Q", "i", "I"],
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

content_rgb_space = colormath.get_rgb_space("DCI P3 D65")
crx, cry = content_rgb_space[2:][0][:2]
cgx, cgy = content_rgb_space[2:][1][:2]
cbx, cby = content_rgb_space[2:][2][:2]
cwx, cwy = colormath.XYZ2xyY(*content_rgb_space[1])[:2]
defaults = {
    "3d.format": "HTML",
    "3dlut.apply_black_offset": 0,
    "3dlut.apply_trc": 1,
    "3dlut.bitdepth.input": 10,
    "3dlut.bitdepth.output": 12,
    "3dlut.content.colorspace.blue.x": cbx,
    "3dlut.content.colorspace.blue.y": cby,
    "3dlut.content.colorspace.green.x": cgx,
    "3dlut.content.colorspace.green.y": cgy,
    "3dlut.content.colorspace.red.x": crx,
    "3dlut.content.colorspace.red.y": cry,
    "3dlut.content.colorspace.white.x": cwx,
    "3dlut.content.colorspace.white.y": cwy,
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
    "copyright": f"No copyright. Created with {appname} {version} and ArgyllCMS",
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
    "profile.name": "_".join(
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
    "profile.save_path": storage,  # directory
    # Force profile type to single shaper + matrix due to OS X bugs with cLUT
    # profiles and matrix profiles with individual shaper curves
    "profile.type": "X" if sys.platform != "darwin" else "S",
    "profile.update": 0,
    "profile_loader.buggy_video_drivers": ";".join(["*"]),
    "profile_loader.check_gamma_ramps": 1,
    "profile_loader.error.show_msg": 1,
    "profile_loader.exceptions": "",
    "profile_loader.fix_profile_associations": 1,
    "profile_loader.ignore_unchanged_gamma_ramps": 1,
    "profile_loader.known_apps": ";".join(
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
    "profile_loader.known_window_classes": ";".join(["CalClient.exe"]),
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
lcode, lenc = locale.getdefaultlocale()
if lcode:
    defaults["lang"] = lcode.split("_")[0].lower()

testchart_defaults = {
    "s": {
        None: "auto"
    },  # shaper + matrix
    "l": {
        None: "auto"
    },  # lut
    "g": {None: "auto"},  # gamma + matrix
}


def _init_testcharts():
    for testcharts in list(testchart_defaults.values()):
        for chart in [value for value in list(testcharts.values()) if value != "auto"]:
            resfiles.append(os.path.join("ti1", chart))
    testchart_defaults["G"] = testchart_defaults["g"]
    testchart_defaults["S"] = testchart_defaults["s"]
    for key in ("X", "x"):
        testchart_defaults[key] = testchart_defaults["l"]


def getcfg(name, fallback=True, raw=False, cfg=cfg):
    """
    Get and return an option value from the configuration.

    If fallback evaluates to True and the option is not set, return its default value.
    """
    if name == "profile.name.expanded" and is_ccxx_testchart():
        name = "measurement.name.expanded"
    value = None
    hasdef = name in defaults
    if hasdef:
        defval = defaults[name]
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
                (name != "trc" or value not in valid_values["trc"])
                and hasdef
                and deftype in (Decimal, int, float)
            ):
                try:
                    value = deftype(value)
                except ValueError:
                    value = defval
                else:
                    valid_range = valid_ranges.get(name)
                    if valid_range:
                        value = min(max(valid_range[0], value), valid_range[1])
                    elif name in valid_values and value not in valid_values[name]:
                        value = defval
            elif name.startswith("dimensions.measureframe"):
                try:
                    value = [max(0, float(n)) for n in value.split(",")]
                    if len(value) != 3:
                        raise ValueError()
                except ValueError:
                    value = defaults[name]
                else:
                    value[0] = min(value[0], 1)
                    value[1] = min(value[1], 1)
                    value[2] = min(value[2], 50)
                    value = ",".join([str(n) for n in value])
            elif name == "profile.quality" and getcfg("profile.type") in ("g", "G"):
                # default to high quality for gamma + matrix
                value = "h"
            elif name == "trc.type" and getcfg("trc") in valid_values["trc"]:
                value = "g"
            elif name in valid_values and value not in valid_values[name]:
                if debug:
                    print(f"Invalid config value for {name}: {value}", end=" ")
                value = None
            elif name == "copyright":
                # Make sure DisplayCAL and Argyll version are up-to-date
                pattern = re.compile(
                    r"(%s(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*" % appname, re.I
                )
                repl = create_replace_function("\\1%s", version)
                value = re.sub(pattern, repl, value)
                if appbasename != appname:
                    pattern = re.compile(
                        r"(%s(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*" % appbasename,
                        re.I,
                    )
                    repl = create_replace_function("\\1%s", version)
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
                # That way we can have compatibility with old and current Argyll CMS
                value = {"n": "l", "r": "c"}.get(value, value)
    if value is None:
        if hasdef and fallback:
            value = defval
            if debug > 1:
                print(name, "- falling back to", value)
        else:
            if debug and not hasdef:
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
        # colorimeter_correction_matrix_file is special because it's not (only) a path
        if debug:
            print(f"{name} does not exist: {value}", end=" ")
        # Normalize path (important, this turns altsep into sep under Windows)
        value = os.path.normpath(value)
        # Check if this is a relative path covered by data_dirs
        if (
            value.split(os.path.sep)[-3:-2] == [appname] or not os.path.isabs(value)
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
        if debug > 1:
            print(name, "- falling back to", value)
    elif name in ("displays", "instruments"):
        if not value:
            return []
        value = [
            strtr(
                v,
                [
                    ("%{}".format(hex(ord(os.pathsep))[2:].upper()), os.pathsep),
                    ("%25", "%"),
                ],
            )
            for v in value.split(os.pathsep)
        ]
    return value


def hascfg(name, fallback=True, cfg=cfg):
    """
    Check if an option name exists in the configuration.

    Returns a boolean value.
    If fallback evaluates to True and the name does not exist, check defaults also.
    """
    if cfg.has_option(configparser.DEFAULTSECT, name):
        return True
    elif fallback:
        return name in defaults
    return False


def get_ccxx_testchart():
    """Get the path to the default chart for CCMX/CCSS creation."""
    return get_data_path(
        os.path.join("ti1", defaults["colorimeter_correction.testchart"])
    )


def get_current_profile(include_display_profile=False):
    """Get the currently selected profile (if any)."""
    path = getcfg("calibration.file", False)
    if path:
        from DisplayCAL import ICCProfile as ICCP

        try:
            profile = ICCP.ICCProfile(path, use_cache=True)
        except (IOError, ICCP.ICCProfileInvalidError):
            return
        return profile
    elif include_display_profile:
        return get_display_profile()


def get_display_profile(display_no=None):
    if display_no is None:
        display_no = max(getcfg("display.number") - 1, 0)
    if is_virtual_display(display_no):
        return None
    from DisplayCAL import ICCProfile as ICCP

    try:
        return ICCP.get_display_profile(display_no)
    except Exception:
        from DisplayCAL.log import log

        print(f"ICCP.get_display_profile({display_no}):", file=log)


standard_profiles = []


def get_standard_profiles(paths_only=False):
    if not standard_profiles:
        from DisplayCAL import ICCProfile as ICCP

        # Reference profiles (Argyll + DisplayCAL)
        ref_icc = get_data_path("ref", r"\.ic[cm]$") or []
        # Other profiles installed on the system
        other_icc = []
        rex = re.compile(r"\.ic[cm]$", re.IGNORECASE)
        for icc_dir in set(iccprofiles + iccprofiles_home):
            for dirpath, _dirnames, basenames in os.walk(icc_dir):
                for basename in filter(rex.search, basenames):
                    filename, ext = os.path.splitext(basename.lower())
                    if (
                        filename.endswith("_bas")
                        or filename.endswith("_eci")
                        or filename.endswith("adobergb1998")
                        or filename.startswith("eci-rgb")
                        or filename.startswith("ecirgb")
                        or filename.startswith("ekta space")
                        or filename.startswith("ektaspace")
                        or filename.startswith("fogra")
                        or filename.startswith("gracol")
                        or filename.startswith("iso")
                        or filename.startswith("lstar-")
                        or filename.startswith("pso")
                        or filename.startswith("prophoto")
                        or filename.startswith("psr_")
                        or filename.startswith("psrgravure")
                        or filename.startswith("snap")
                        or filename.startswith("srgb")
                        or filename.startswith("swop")
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
        if isinstance(ref_icc, str):
            ref_icc = [ref_icc]

        for path in ref_icc + other_icc:
            try:
                profile = ICCP.ICCProfile(path, load=False, use_cache=True)
            except EnvironmentError:
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
                    standard_profiles.append(profile)
    if paths_only:
        return [profile.fileName for profile in standard_profiles]
    return standard_profiles


def get_total_patches(
    white_patches=None,
    black_patches=None,
    single_channel_patches=None,
    gray_patches=None,
    multi_steps=None,
    multi_bcc_steps=None,
    fullspread_patches=None,
):
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
            for i in range(multi_bcc_steps):
                multi_values.append(str(multi_bcc_step * i))
            for i in range(multi_bcc_steps * 2 - 1):
                multi_bcc_values.append(str(multi_bcc_step / 2.0 * i))
        else:
            for i in range(multi_steps):
                multi_values.append(str(multi_step * i))
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
    """Verify and return dir and filename for a path from the user cfg, or a given path."""  # noqa: B950
    defaultPath = path or getcfg(cfg_item_name)
    defaultDir = expanduseru("~")
    defaultFile = ""
    if defaultPath:
        if os.path.exists(defaultPath):
            defaultDir, defaultFile = (
                os.path.dirname(defaultPath),
                os.path.basename(defaultPath),
            )
        elif defaults.get(cfg_item_name) and os.path.exists(defaults[cfg_item_name]):
            defaultDir, defaultFile = (
                os.path.dirname(defaults[cfg_item_name]),
                os.path.basename(defaults[cfg_item_name]),
            )
        elif os.path.exists(os.path.dirname(defaultPath)):
            defaultDir = os.path.dirname(defaultPath)
    return defaultDir, defaultFile


def is_ccxx_testchart(testchart=None):
    """
    Check whether the testchart is the default chart for CCMX/CCSS creation.

    Args:
        testchart (str, optional): The testchart to check.
            If not provided, the default testchart will be used.

    Returns:
        bool: True if the testchart is the default chart for CCMX/CCSS creation,
            False otherwise.
    """
    testchart = testchart or getcfg("testchart.file")
    return testchart == get_ccxx_testchart()


def is_profile(filename=None, include_display_profile=False):
    filename = filename or getcfg("calibration.file", False)
    if filename:
        if os.path.exists(filename):
            from DisplayCAL import ICCProfile as ICCP

            try:
                ICCP.ICCProfile(filename, use_cache=True)
            except (IOError, ICCP.ICCProfileInvalidError):
                pass
            else:
                return True
    elif include_display_profile:
        return bool(get_display_profile())
    return False


def makecfgdir(which="user", worker=None):
    if which == "user":
        if not os.path.exists(confighome):
            try:
                os.makedirs(confighome)
            except Exception as exception:
                print(
                    "Warning - could not create configuration directory "
                    f"'{confighome}': {exception}"
                )
                return False
    elif not os.path.exists(config_sys):
        try:
            if sys.platform == "win32":
                os.makedirs(config_sys)
            else:
                result = worker.exec_cmd(
                    "mkdir",
                    ["-p", config_sys],
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
                f"'{config_sys}': {exception}"
            )
            return False
    return True


cfginited = {}


def initcfg(module=None, cfg=cfg, force_load=False):
    """
    Initialize the configuration.

    Read in settings if the configuration file exists,
    else create the settings directory if nonexistent.
    """
    if module:
        cfgbasename = f"{appbasename}-{module}"
    else:
        cfgbasename = appbasename
    makecfgdir()
    if os.path.exists(confighome) and not os.path.exists(
        os.path.join(confighome, f"{cfgbasename}.ini")
    ):
        # Set default preset
        setcfg("calibration.file", defaults["calibration.file"], cfg=cfg)

    # Read cfg
    cfgnames = [appbasename]
    if module:
        cfgnames.append(cfgbasename)
    else:
        cfgnames.extend(
            f"{appbasename}-{othermod}" for othermod in ("testchart-editor",)
        )

    cfgroots = [confighome]
    if module == "apply-profiles":
        cfgroots.append(config_sys)

    cfgfiles = []
    for cfgname in cfgnames:
        for cfgroot in cfgroots:
            cfgfile = os.path.join(cfgroot, f"{cfgname}.ini")
            if os.path.isfile(cfgfile):
                try:
                    mtime = os.stat(cfgfile).st_mtime
                except EnvironmentError as exception:
                    print(f"Warning - os.stat('{cfgfile}') failed: {exception}")
                last_checked = cfginited.get(cfgfile)
                if force_load or mtime != last_checked:
                    cfginited[cfgfile] = mtime
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
        cfgfiles.sort(key=lambda cfgfile: cfginited.get(cfgfile))
    try:
        cfg.read(cfgfiles)
    # This won't raise an exception if the file does not exist,
    # only if it can't be parsed
    except Exception:
        print(
            "Warning - could not parse configuration files:\n%s".format(
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


dpiset = False


def set_default_app_dpi():
    """Set application DPI."""
    # Only call this after creating the wx.App object!
    global dpiset
    if not dpiset and not getcfg("app.dpi", False):
        # HighDPI support
        from DisplayCAL.wxaddons import wx

        dpiset = True
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
                    [
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
                try:
                    txt_scale = float(factor)
                except ValueError:
                    pass
            dpi = get_default_dpi()
            if txt_scale:
                dpi = int(round(dpi * txt_scale))
        defaults["app.dpi"] = dpi
    dpiset = True


def get_hidpi_scaling_factor():
    if sys.platform in ("darwin", "win32"):
        return 1.0  # Handled via app DPI
    else:
        # Linux
        from DisplayCAL.util_os import which

        if which("xrdb"):
            import subprocess as sp

            p = sp.Popen(
                ["xrdb", "-query"], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE
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
                from DisplayCAL.wxaddons import wx

                match = False
                app = wx.GetApp()
                if app:
                    from DisplayCAL import RealDisplaySizeMM as RDSMM

                    if not RDSMM._displays:
                        RDSMM.enumerate_displays()
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
                        for display in RDSMM._displays:
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
                ["gsettings", "get", "org.gnome.desktop.interface", "scaling-factor"],
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


def setcfg(name, value, cfg=cfg):
    """Set an option value in the configuration."""
    if value is None:
        cfg.remove_option(configparser.DEFAULTSECT, name)
    else:
        if name in ("displays", "instruments") and isinstance(value, (list, tuple)):
            value = os.pathsep.join(
                str(v)
                for v in strtr(
                    value,
                    [
                        ("%", "%25"),
                        (os.pathsep, "%{}".format(hex(ord(os.pathsep))[2:].upper())),
                    ],
                )
            )
        cfg.set(configparser.DEFAULTSECT, name, value)


def setcfg_cond(condition, name, value, set_if_backup_exists=False, restore=True):
    """
    If <condition>, backup configuration option <name> if not yet backed up and set option to <value> if backup did not previously exist or set_if_backup_exists evaluates to True.

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


def writecfg(which="user", worker=None, module=None, options=(), cfg=cfg):
    """
    Write configuration file.

    which: 'user' or 'system'
    worker: worker instance if ``which == 'system'``
    """
    if module:
        cfgbasename = f"{appbasename}-{module}"
    else:
        cfgbasename = appbasename
    # Remove unknown options
    for name, _val in cfg.items(configparser.DEFAULTSECT):
        if name not in defaults:
            print("Removing unknown option:", name)
            setcfg(name, None)
    if which == "user":
        # user config - stores everything and overrides system-wide config
        cfgfilename = os.path.join(confighome, f"{cfgbasename}.ini")
        try:
            io = StringIO()
            cfg.write(io)
            io.seek(0)
            lines = io.read().strip("\n").split("\n")
            if options:
                optionlines = []
                for optionline in lines[1:]:
                    for option in options:
                        if optionline.startswith(option):
                            optionlines.append(optionline)
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
        cfgfilename1 = os.path.join(confighome, f"{cfgbasename}.local.ini")
        cfgfilename2 = os.path.join(config_sys, f"{cfgbasename}.ini")
        if sys.platform == "win32":
            cfgfilename = cfgfilename2
        else:
            cfgfilename = cfgfilename1
        try:
            cfgfile = open(cfgfilename, "wb")
            if getcfg("argyll.dir"):
                cfgfile.write(
                    (
                        "%s%s".format(
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
            cfgfile.close()
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
runtype = runtimeconfig(pyfile)


if sys.platform in ("darwin", "win32") and not os.getenv("SSL_CERT_FILE"):
    try:
        import certifi
    except ImportError:
        cafile = None
    else:
        cafile = certifi.where()
        if cafile and not os.path.isfile(cafile):
            cafile = None
    if not cafile:
        # Use our bundled CA file
        cafile = get_data_path("cacert.pem")
    if cafile and isinstance(cafile, str):
        os.environ["SSL_CERT_FILE"] = cafile
