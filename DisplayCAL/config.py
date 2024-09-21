# -*- coding: utf-8 -*-
"""Runtime configuration and user settings parser."""

import configparser
import os
import re
import sys

from DisplayCAL.constants import (
    appbasename,
    cfg,
    data_dirs,
    defaults,
    exe,
    exedir,
    extra_data_dirs,
    isapp,
    isexe,
    pydir,
    pyfile,
    pypath,
)
from DisplayCAL.defaultpaths import (  # noqa: F401
    appdata,
    commonappdata,  # don't remove this, imported by other modules,
)
from DisplayCAL.get_data_path import get_data_path
from DisplayCAL.get_hidpi_scaling_factor import get_hidpi_scaling_factor
from DisplayCAL.getbitmap import getbitmap
from DisplayCAL.getcfg import getcfg
# from DisplayCAL.log import logger
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug
from DisplayCAL.runtimeconfig import runtimeconfig
from DisplayCAL.util_os import expanduseru, getenvu, is_superuser
from DisplayCAL.util_str import strtr

if sys.platform == "win32":
    from DisplayCAL.defaultpaths import commonprogramfiles
elif sys.platform == "darwin":
    from DisplayCAL.defaultpaths import library, library_home, prefs, prefs_home
else:
    from DisplayCAL.defaultpaths import (  # noqa: F401
        xdg_config_dir_default,
        xdg_config_home,
        xdg_data_dirs,
        xdg_data_home,
        xdg_data_home_default,
    )

configparser.DEFAULTSECT = "Default"  # Sadly, this line needs to be here.

exename = os.path.basename(exe)

if isexe:
    _meipass2 = os.getenv("_MEIPASS2")
    if _meipass2:
        os.environ["_MEIPASS2"] = _meipass2.replace("/", os.path.sep)

pyname, pyext = (
    os.path.splitext(exe.split(os.path.sep)[-4])
    if isapp
    else os.path.splitext(os.path.basename(pypath))
)

# Search directories on PATH for data directories so Argyll reference files can         # noqa: SC100
# be found automatically if Argyll directory not explicitly configured                  # noqa: SC100
for dir_ in getenvu("PATH", "").split(os.pathsep):
    dir_parent = os.path.dirname(dir_)
    if os.path.isdir(os.path.join(dir_parent, "ref")):
        extra_data_dirs.append(dir_parent)

datahome = os.path.join(appdata, appbasename)

if sys.platform == "win32":
    if pydir.lower().startswith(exedir.lower()) and pydir != exedir:
        # We are installed in a subfolder of the executable directory                   # noqa: SC100
        # (e.g. C:\Python26\Lib\site-packages\DisplayCAL)                               # noqa: SC100
        # we need to add the executable directory to the data directories so
        # files in subfolders of the executable directory which are not in              # noqa: SC100
        # Lib\site-packages\DisplayCAL can be found
        # (e.g. Scripts\displaycal-apply-profiles)                                      # noqa: SC100
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
# (note that madVR can technically be both,
# but the endpoint is always directly connected to a display so we have videoLUT
# access via madVR's API.
# Only devices which don't support that are considered 'untethered' in this context)    # noqa: SC100
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


def get_bitmap_as_icon(size, name, scale=True):
    """
    Like geticon, but return a wx.Icon instance.

    Args:
        size (int): The size of the icon.
        name (str): The name of the icon.
        scale (bool): Whether to scale the icon.

    Returns:
        wx.Icon: The icon instance.
    """
    from DisplayCAL.wxaddons import wx

    icon = wx.EmptyIcon()
    if sys.platform == "darwin" and wx.VERSION >= (2, 9) and size > 128:
        # FIXME: wxMac 2.9 doesn't support icon sizes above 128                         # noqa: SC100
        size = 128
    bmp = geticon(size, name, scale)
    icon.CopyFromBitmap(bmp)
    return icon


def get_argyll_data_dir():
    """
    Get the Argyll data directory.

    Returns:
        str: The path to the Argyll data directory.
    """
    if getcfg("argyll.version") < "1.5.0":
        argyll_data_dirname = "color"
    else:
        argyll_data_dirname = "ArgyllCMS"
    if sys.platform == "darwin" and getcfg("argyll.version") < "1.5.0":
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
        # Assume ICO format                                                             # noqa: SC100
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
    """
    Return measurement area size adjusted for percentage of screen area.

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


def get_default_dpi():
    if sys.platform == "darwin":
        return 72.0
    else:
        return 96.0


testchart_defaults = {
    "s": {
        None: "auto"
    },  # shaper + matrix                                                               # noqa: SC100
    "l": {
        None: "auto"
    },  # lut                                                                           # noqa: SC100
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
                    f"Warning - could not create configuration directory '{confighome}': {exception}"  # noqa: B950
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
                f"Warning - could not create configuration directory '{config_sys}': {exception}"  # noqa: B950
            )
            return False
    return True


cfginited = {}

dpiset = False


def set_default_app_dpi():
    """Set application DPI."""
    # Only call this after creating the wx.App object!                                  # noqa: SC100
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
            # XDG_CURRENT_DESKTOP delimiter is colon (':')                              # noqa: SC100
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
