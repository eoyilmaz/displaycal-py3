# -*- coding: utf-8 -*-
"""Runtime configuration and user settings parser."""
import configparser
import locale
import os
import re
import string
import sys

from DisplayCAL import colormath
from DisplayCAL.argyll_names import intents, observers, video_encodings, viewconds
from DisplayCAL.constants import data_dirs, extra_data_dirs
from DisplayCAL.defaultpaths import (  # noqa: F401
    appdata,
    autostart,  # don't remove this, imported by other modules
    autostart_home,  # don't remove this, imported by other modules
    commonappdata,
    home,  # don't remove this, imported by other modules,
)
from DisplayCAL.get_data_path import get_data_path
from DisplayCAL.get_hidpi_scaling_factor import get_hidpi_scaling_factor
from DisplayCAL.getbitmap import getbitmap
from DisplayCAL.getcfg import getcfg
from DisplayCAL.meta import name as appname, version
from DisplayCAL.options import debug
from DisplayCAL.runtimeconfig import runtimeconfig
from DisplayCAL.safe_print import (  # noqa: F401
    enc,  # don't remove this, imported by other modules,
)
from DisplayCAL.util_os import expanduseru, getenvu, is_superuser
from DisplayCAL.util_str import strtr

# from DisplayCAL.log import logger

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

import build  # don't remove this, imported by other modules                            # noqa: F401

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
# Mac OS X: isapp should only be true for standalone, not 0install                      # noqa: SC100
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
    pydir = os.path.dirname(exe if isexe else os.path.abspath(__file__))

# Search directories on PATH for data directories so Argyll reference files can         # noqa: SC100
# be found automatically if Argyll directory not explicitly configured                  # noqa: SC100
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
    if not isinstance(display, str):
        display = get_display_name(display)
    for test in tests:
        if re.match(test, display):
            return True
    return False


def is_uncalibratable_display(display=None):
    return is_special_display(display, uncalibratable_displays)


def is_patterngenerator(display=None):
    return is_special_display(display, patterngenerators)


def is_non_argyll_display(display=None):
    return is_special_display(display, non_argyll_displays)


def is_untethered_display(display=None):
    return is_special_display(display, untethered_displays)


def is_virtual_display(display=None):
    return is_special_display(display, virtual_displays)


def check_3dlut_format(devicename):
    if get_display_name(None, True) == devicename:
        if devicename == "Prisma":
            return (
                getcfg("3dlut.format") == "3dl"
                and getcfg("3dlut.size") == 17
                and getcfg("3dlut.bitdepth.input") == 10
                and getcfg("3dlut.bitdepth.output") == 12
            )


def get_bitmap_as_icon(size, name, scale=True):
    """Like geticon, but return a wx.Icon instance."""
    from DisplayCAL.wxaddons import wx

    icon = wx.EmptyIcon()
    if sys.platform == "darwin" and wx.VERSION >= (2, 9) and size > 128:
        # FIXME: wxMac 2.9 doesn't support icon sizes above 128                         # noqa: SC100
        size = 128
    bmp = geticon(size, name, scale)
    icon.CopyFromBitmap(bmp)
    return icon


def get_argyll_data_dir():
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
    """Return name of currently configured display."""
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

    E.g.
    'LCD2690WUXi @ 0, 0, 1920x1200' -> 'LCD2690WUXi'
    'madVR' -> 'madVR'
    """
    if "@" in display and not display.startswith("Chromecast "):
        display = "@".join(display.split("@")[:-1])
    return display.strip()


def get_argyll_display_number(geometry):
    """Translate from wx display geometry to Argyll display index."""
    geometry = f"{geometry[0]}, {geometry[1]}, {geometry[2]}x{geometry[3]}"
    for i, display in enumerate(getcfg("displays")):
        if display.find(f"@ {geometry}") > -1:
            if debug:
                print(f"[D] Found display {geometry} at index {i}")
            return i


def get_display_number(display_no):
    """Translate from Argyll display index to wx display index."""
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
    """Return the Argyll enumerated display coordinates and sizes."""
    from DisplayCAL.wxaddons import wx

    display_rects = []
    for _i, display in enumerate(getcfg("displays")):
        match = re.search(r"@ (-?\d+), (-?\d+), (\d+)x(\d+)", display)
        if match:
            display_rects.append(wx.Rect(*[int(item) for item in match.groups()]))
    return display_rects


def get_icon_bundle(sizes, name):
    """Return a wx.IconBundle with given icon sizes."""
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
    """Return name of currently configured instrument."""
    n = getcfg("comport.number") - 1
    instrument_names = getcfg("instruments")
    if 0 <= n < len(instrument_names):
        return instrument_names[n]
    return ""


def get_measureframe_dimensions(dimensions_measureframe=None, percent=10):
    """Return measurement area size adjusted for percentage of screen area."""
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
    # Argyll dispcal uses 20% of ambient (in lux, fixed steradiant of 3.1415) as        # noqa: SC100
    # adapting luminance, but we assume it already *is* the adapting luminance.         # noqa: SC100
    # To correct for this, scale so that dispcal gets the correct value.                # noqa: SC100
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
    # collink: xvYCC output encoding is not supported                                   # noqa: SC100
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
    # Measurement modes as supported by Argyll -y parameter                             # noqa: SC100
    # 'l' = 'n' (non-refresh-type display, e.g. LCD)
    # 'c' = 'r' (refresh-type display, e.g. CRT)
    # We map 'l' and 'c' to "n" and "r" in
    # worker.Worker.add_measurement_features if using Argyll >= 1.5                     # noqa: SC100
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
    # Q = Argyll >= 1.1.0                                                               # noqa: SC100
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
    # Force black point compensation due to OS X bugs with non BPC profiles             # noqa: SC100
    "profile.black_point_compensation": 0 if sys.platform != "darwin" else 1,
    "profile.black_point_correction": 0.0,
    "profile.create_gamut_views": 1,
    "profile.install_scope": (
        "l"
        if (sys.platform != "win32" and os.geteuid() == 0)
        # or (sys.platform == "win32" and sys.getwindowsversion() >= (6, ))             # noqa: SC100
        else "u"
    ),  # Linux, OSX                                                                    # noqa: SC100
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
    # Force profile type to single shaper + matrix due to OS X bugs with cLUT           # noqa: SC100
    # profiles and matrix profiles with individual shaper curves                        # noqa: SC100
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
    # Set smallest testchart.                                                           # noqa: SC100
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


def is_ccxx_testchart(testchart=None):
    """Check whether the testchart is the default chart for CCMX/CCSS creation."""
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
