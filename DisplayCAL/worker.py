# -*- coding: utf-8 -*-

# stdlib
import codecs
from binascii import hexlify
import atexit
import ctypes
import datetime

import getpass
import http.client
import math
import mimetypes
import os
from io import BytesIO
from pathlib import Path

import distro
import platform
import re
import socket
import shutil
import string
import struct
import subprocess as sp
import sys
import tempfile
import textwrap
import threading
import traceback
import urllib.request
import urllib.parse
import urllib.error
import warnings
import zipfile
import zlib
from collections import UserString
from hashlib import md5, sha256
from threading import currentThread
from time import sleep, strftime, time

from send2trash import send2trash

if sys.platform == "darwin":
    from platform import mac_ver
    from _thread import start_new_thread
elif sys.platform == "win32":
    from ctypes import windll
else:
    import grp

# 3rd party
if sys.platform == "win32":
    from win32com.shell import shell as win32com_shell
    import pythoncom
    import win32api
    import win32con
    import win32event
    import pywintypes
    import winerror

# custom
from DisplayCAL import CGATS
from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import audio
from DisplayCAL import colormath
from DisplayCAL import config
from DisplayCAL import defaultpaths
from DisplayCAL import imfile
from DisplayCAL import localization as lang
from DisplayCAL import wexpect
from DisplayCAL.argyll import (
    check_argyll_bin,
    get_argyll_util,
    get_argyll_utilname,
    get_argyll_version_string as base_get_argyll_version_string,
    parse_argyll_version_string,
)
from DisplayCAL.argyll_cgats import (
    add_dispcal_options_to_cal,
    add_options_to_ti3,
    cal_to_fake_profile,
    cal_to_vcgt,
    extract_cal_from_profile,
    extract_cal_from_ti3,
    extract_device_gray_primaries,
    extract_fix_copy_cal,
    ti3_to_ti1,
    verify_cgats,
    verify_ti1_rgb_xyz,
)
from DisplayCAL.argyll_instruments import (
    get_canonical_instrument_name,
    instruments as all_instruments,
)
from DisplayCAL.argyll_names import (
    names as argyll_names,
    altnames as argyll_altnames,
    optional as argyll_optional,
    viewconds,
    intents,
    observers,
)
from DisplayCAL.colormath import VidRGB_to_eeColor, eeColor_to_VidRGB
from DisplayCAL.config import (
    autostart,
    autostart_home,
    script_ext,
    defaults,
    enc,
    exe,
    exedir,
    exe_ext,
    fs_enc,
    getcfg,
    geticon,
    get_data_path,
    get_total_patches,
    get_verified_path,
    isapp,
    is_ccxx_testchart,
    profile_ext,
    pydir,
    setcfg,
    setcfg_cond,
    split_display_name,
    writecfg,
    appbasename,
)
from DisplayCAL.debughelpers import (
    Error,
    DownloadError,
    Info,
    UnloggedError,
    UnloggedInfo,
    UnloggedWarning,
    UntracedError,
    Warn,
    handle_error,
)
from DisplayCAL.defaultpaths import (
    cache,
    iccprofiles_home,
    iccprofiles_display_home,
    appdata,
)
from DisplayCAL.edid import WMIError, get_edid
from DisplayCAL.log import DummyLogger, LogFile, get_file_logger, log
from DisplayCAL import madvr
from DisplayCAL.meta import VERSION, VERSION_BASE, DOMAIN, name as appname, version
from DisplayCAL.multiprocess import cpu_count, pool_slice
from DisplayCAL.options import (
    always_fail_download,
    debug,
    eecolor65,
    experimental,
    test,
    test_badssl,
    test_require_sensor_cal,
    verbose,
)

from DisplayCAL.network import LoggingHTTPRedirectHandler, NoHTTPRedirectHandler
from DisplayCAL.patterngenerators import (
    PrismaPatternGeneratorClient,
    ResolveLSPatternGeneratorServer,
    ResolveCMPatternGeneratorServer,
    WebWinHTTPPatternGeneratorServer,
)
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_dict import dict_sort
from DisplayCAL.util_http import encode_multipart_formdata
from DisplayCAL.util_io import (
    EncodedWriter,
    Files,
    GzipFileProper,
    LineBufferedStream,
    LineCache,
    StringIOu as StringIO,
    TarFileProper,
)
from DisplayCAL.util_list import intlist, natsort

if sys.platform == "darwin":
    from DisplayCAL.util_mac import (
        mac_app_activate,
        mac_terminal_do_script,
        mac_terminal_set_colors,
        osascript,
        get_model_id,
    )
elif sys.platform == "win32":
    from DisplayCAL import util_win
    from DisplayCAL.util_win import run_as_admin, shell_exec, win_ver

    try:
        import wmi
    except Exception as exception:
        print("Error - could not import WMI:", exception)
        wmi = None
else:
    # Linux
    from DisplayCAL.defaultpaths import xdg_data_home

    try:
        from DisplayCAL.util_dbus import (
            DBusObject,
            DBusException,
            BUSTYPE_SESSION,
            dbus_session,
            dbus_system,
        )
    except ImportError:
        dbus_session = None
        dbus_system = None
from DisplayCAL import colord
from DisplayCAL.util_os import (
    dlopen,
    getenvu,
    is_superuser,
    launch_file,
    make_win32_compatible_long_path,
    mksfile,
    mkstemp_bypath,
    quote_args,
    safe_glob,
    which,
)

if sys.platform not in ("darwin", "win32"):
    from DisplayCAL.util_os import getgroups
if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
    from DisplayCAL.util_os import win64_disable_file_system_redirection

from DisplayCAL.util_str import (
    make_filename_safe,
    safe_basestring,
    safe_asciize,
    safe_str,
    strtr,
    universal_newlines,
)
from DisplayCAL.worker_base import (
    MP_Xicclu,
    WorkerBase,
    Xicclu,
    _mp_generate_B2A_clut,
    _mp_xicclu,
    printcmdline,
)
from DisplayCAL.wxaddons import BetterCallLater, BetterWindowDisabler, wx
from DisplayCAL.wxwindows import (
    ConfirmDialog,
    HtmlInfoDialog,
    InfoDialog,
    ProgressDialog,
    SimpleTerminal,
    show_result_dialog,
)
from DisplayCAL.wxDisplayAdjustmentFrame import DisplayAdjustmentFrame
from DisplayCAL.wxDisplayUniformityFrame import DisplayUniformityFrame
from DisplayCAL.wxUntetheredFrame import UntetheredFrame

RDSMM = None
if sys.platform not in ("darwin", "win32"):
    try:
        from DisplayCAL import RealDisplaySizeMM as RDSMM
    except ImportError as exception:
        warnings.warn(str(exception), ImportWarning)
import wx.lib.delayedresult as delayedresult


INST_CAL_MSGS = [
    "Do a reflective white calibration",
    "Do a transmissive white calibration",
    "Do a transmissive dark calibration",
    "Place the instrument on its reflective white reference",
    "Click the instrument on its reflective white reference",
    "Place the instrument in the dark",
    "Place cap on the instrument",  # i1 Pro/SpyderX
    "Place ambient adapter and cap on the instrument",
    "Set instrument sensor to calibration position",  # ColorMunki
    "Place the instrument on its transmissive white source",
    "Use the appropriate tramissive blocking",
    "Change filter on instrument to",
]
USE_WPOPEN = 0

keycodes = {
    wx.WXK_NUMPAD0: ord("0"),
    wx.WXK_NUMPAD1: ord("1"),
    wx.WXK_NUMPAD2: ord("2"),
    wx.WXK_NUMPAD3: ord("3"),
    wx.WXK_NUMPAD4: ord("4"),
    wx.WXK_NUMPAD5: ord("5"),
    wx.WXK_NUMPAD6: ord("6"),
    wx.WXK_NUMPAD7: ord("7"),
    wx.WXK_NUMPAD8: ord("8"),
    wx.WXK_NUMPAD9: ord("9"),
    wx.WXK_NUMPAD_ADD: ord("+"),
    wx.WXK_NUMPAD_ENTER: ord("\n"),
    wx.WXK_NUMPAD_EQUAL: ord("="),
    wx.WXK_NUMPAD_DIVIDE: ord("/"),
    wx.WXK_NUMPAD_MULTIPLY: ord("*"),
    wx.WXK_NUMPAD_SUBTRACT: ord("-"),
}


workers = []


WAIT_FILE_TEMPLATE = """# coding=utf-8
import os, sys, time
if sys.platform != "win32":
    print(*(["\\nCurrent RGB"] + sys.argv[1:]))
abortfilename = os.path.join(r"{script_dir}", ".abort")
okfilename = os.path.join(r"{script_dir}", ".ok")
while True:
    if os.path.isfile(abortfilename):
        break
    if os.path.isfile(okfilename):
        try:
            os.remove(okfilename)
        except OSError as e:
            pass
        else:
            break
    time.sleep(0.001)
"""


def add_keywords_to_cgats(cgats, keywords):
    """Add keywords to CGATS"""
    if not isinstance(cgats, CGATS.CGATS):
        cgats = CGATS.CGATS(cgats)
    for keyword in keywords:
        value = keywords[keyword]
        cgats[0].add_keyword(keyword, value)
    return cgats


def check_create_dir(path):
    """Try to create a directory and show an error message on failure."""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception as exception:
            return Error(f"{lang.getstr('error.dir_creation', path)}\n\n{exception}")
    if not os.path.isdir(path):
        return Error(lang.getstr("error.dir_notdir", path))
    return True


def check_cal_isfile(cal=None, missing_msg=None, notfile_msg=None, silent=False):
    """Check if a calibration file exists and show an error message if not."""
    if not silent:
        if not missing_msg:
            missing_msg = lang.getstr("error.calibration.file_missing", cal)
        if not notfile_msg:
            notfile_msg = lang.getstr("file_notfile", cal)
    return check_file_isfile(cal, missing_msg, notfile_msg, silent)


def check_profile_isfile(
    profile_path=None, missing_msg=None, notfile_msg=None, silent=False
):
    """Check if a profile exists and show an error message if not."""
    if not silent:
        if not missing_msg:
            missing_msg = lang.getstr("error.profile.file_missing", profile_path)
        if not notfile_msg:
            notfile_msg = lang.getstr("file_notfile", profile_path)
    return check_file_isfile(profile_path, missing_msg, notfile_msg, silent)


def check_file_isfile(filename, missing_msg=None, notfile_msg=None, silent=False):
    """Check if a file exists and show an error message if not."""
    if not os.path.exists(filename):
        if not silent:
            if not missing_msg:
                missing_msg = lang.getstr("file.missing", filename)
            return Error(missing_msg)
        return False
    if not os.path.isfile(filename):
        if not silent:
            if not notfile_msg:
                notfile_msg = lang.getstr("file.notfile", filename)
            return Error(notfile_msg)
        return False
    return True


def check_set_argyll_bin(paths=None):
    """Check if Argyll binaries can be found, otherwise let the user choose."""
    if check_argyll_bin(paths):
        return True
    else:
        return set_argyll_bin()


def check_ti3_criteria1(
    RGB,
    XYZ,
    black_XYZ,
    white_XYZ,
    delta_to_sRGB_threshold_E=10,
    delta_to_sRGB_threshold_L=10,
    delta_to_sRGB_threshold_C=75,
    delta_to_sRGB_threshold_H=75,
    print_debuginfo=True,
):
    sRGBLab = colormath.RGB2Lab(
        RGB[0] / 100.0, RGB[1] / 100.0, RGB[2] / 100.0, noadapt=not white_XYZ
    )
    if white_XYZ:
        if black_XYZ:
            black_Lab = colormath.XYZ2Lab(
                *colormath.adapt(black_XYZ[0], black_XYZ[1], black_XYZ[2], white_XYZ)
            )
            black_C = math.sqrt(math.pow(black_Lab[1], 2) + math.pow(black_Lab[2], 2))
            if black_Lab[0] < 3 and black_C < 3:
                # Sanity check: Is this color reasonably dark and achromatic?
                # Then do BPC so we can compare better to perfect black sRGB
                XYZ = colormath.blend_blackpoint(
                    XYZ[0], XYZ[1], XYZ[2], black_XYZ, None, white_XYZ
                )
        XYZ = colormath.adapt(XYZ[0], XYZ[1], XYZ[2], white_XYZ)
    Lab = colormath.XYZ2Lab(*XYZ)

    delta_to_sRGB = colormath.delta(*sRGBLab + Lab + (2000,))

    # Depending on how (a)chromatic the sRGB color is, scale the thresholds
    # Use math derived from DE2000 formula to get chroma and hue angle
    L, a, b = sRGBLab
    b_pow = math.pow(b, 2)
    C = math.sqrt(math.pow(a, 2) + b_pow)
    C_pow = math.pow(C, 7)
    G = 0.5 * (1 - math.sqrt(C_pow / (C_pow + math.pow(25, 7))))
    a = (1 + G) * a
    C = math.sqrt(math.pow(a, 2) + b_pow)
    h = (
        0
        if a == 0 and b == 0
        else math.degrees(math.atan2(b, a)) + (0 if b >= 0 else 360.0)
    )
    # C and h scaling factors
    C_scale = C / 100.0
    h_scale = h / 360.0
    # RGB hue, saturation and value scaling factors
    H, S, V = colormath.RGB2HSV(*[v / 100.0 for v in RGB])
    SV_scale = S * V
    # Scale the thresholds
    delta_to_sRGB_threshold_E += delta_to_sRGB_threshold_E * max(C_scale, SV_scale)
    delta_to_sRGB_threshold_L += delta_to_sRGB_threshold_L * max(C_scale, SV_scale)
    # Allow higher chroma errors as luminance of reference decreases
    L_scale = max(1 - (1 * C_scale) + (100.0 - L) / 100.0, 1)
    delta_to_sRGB_threshold_C = (
        delta_to_sRGB_threshold_C * max(C_scale, SV_scale) + 2
    ) * L_scale
    delta_to_sRGB_threshold_H = (
        delta_to_sRGB_threshold_H * max(C_scale, h_scale, H, SV_scale) + 2
    ) * L_scale

    criteria1 = delta_to_sRGB["E"] > delta_to_sRGB_threshold_E and (
        abs(delta_to_sRGB["L"]) > delta_to_sRGB_threshold_L
        or abs(delta_to_sRGB["C"]) > delta_to_sRGB_threshold_C
        or abs(delta_to_sRGB["H"]) > delta_to_sRGB_threshold_H
    )
    # This patch has an unusually high delta 00 to its sRGB equivalent

    delta_to_sRGB["E_ok"] = delta_to_sRGB["E"] <= delta_to_sRGB_threshold_E
    delta_to_sRGB["L_ok"] = abs(delta_to_sRGB["L"]) <= delta_to_sRGB_threshold_L
    delta_to_sRGB["C_ok"] = abs(delta_to_sRGB["C"]) <= delta_to_sRGB_threshold_C
    delta_to_sRGB["H_ok"] = abs(delta_to_sRGB["H"]) <= delta_to_sRGB_threshold_H
    delta_to_sRGB["ok"] = (
        delta_to_sRGB["E_ok"]
        and delta_to_sRGB["L_ok"]
        and delta_to_sRGB["C_ok"]
        and delta_to_sRGB["H_ok"]
    )

    debuginfo = (
        "RGB: %6.2f %6.2f %6.2f  RGB(sRGB)->Lab(D50): %6.2f %6.2f %6.2f  "
        "L_scale: %5.3f   C: %5.2f C_scale: %5.3f  h: %5.2f  "
        "h_scale: %5.3f  H: %5.2f  H_scale: %5.3f  S: %5.2f  "
        "V: %5.2f  SV_scale: %5.3f  Thresholds: E %5.2f  L %5.2f  "
        "C %5.2f  H %5.2f   XYZ->Lab(D50): %6.2f %6.2f %6.2f  delta "
        "RGB(sRGB)->Lab(D50) to XYZ->Lab(D50): dE %5.2f  dL %5.2f  dC "
        "%5.2f  dH %5.2f"
        % (
            RGB[0],
            RGB[1],
            RGB[2],
            sRGBLab[0],
            sRGBLab[1],
            sRGBLab[2],
            L_scale,
            C,
            C_scale,
            h,
            h_scale,
            H * 360,
            H,
            S,
            V,
            SV_scale,
            delta_to_sRGB_threshold_E,
            delta_to_sRGB_threshold_L,
            delta_to_sRGB_threshold_C,
            delta_to_sRGB_threshold_H,
            Lab[0],
            Lab[1],
            Lab[2],
            delta_to_sRGB["E"],
            delta_to_sRGB["L"],
            delta_to_sRGB["C"],
            delta_to_sRGB["H"],
        )
    )
    if print_debuginfo:
        print(debuginfo)

    return sRGBLab, Lab, delta_to_sRGB, criteria1, debuginfo


def check_ti3_criteria2(
    prev_Lab, Lab, prev_sRGBLab, sRGBLab, prev_RGB, RGB, sRGB_delta_E_scale_factor=0.5
):
    delta = colormath.delta(*prev_Lab + Lab + (2000,))
    sRGB_delta = colormath.delta(*prev_sRGBLab + sRGBLab + (2000,))
    sRGB_delta["E"] *= sRGB_delta_E_scale_factor

    criteria2 = delta["E"] < sRGB_delta["E"]
    # These two patches have different RGB values
    # but suspiciously low delta E 76.

    if criteria2 and (
        prev_RGB[0] == prev_RGB[1] == prev_RGB[2] and RGB[0] == RGB[1] == RGB[2]
    ):
        # If RGB gray, check if the Y difference makes sense
        criteria2 = (RGB[0] > prev_RGB[0] and Lab[0] <= prev_Lab[0]) or (
            RGB[0] < prev_RGB[0] and Lab[0] >= prev_Lab[0]
        )
        delta["L_ok"] = not criteria2
        delta["E_ok"] = True
    else:
        delta["E_ok"] = not criteria2
        delta["L_ok"] = True

    return delta, sRGB_delta, criteria2


def check_ti3(ti3, print_debuginfo=True):
    """Check subsequent patches' expected vs real deltaE and collect patches
    with different RGB values, but suspiciously low delta E

    Used as a means to find misreads.

    The expected dE is calculated by converting from a patches RGB values
    (assuming sRGB) to Lab and comparing the values.

    """
    if not isinstance(ti3, CGATS.CGATS):
        ti3 = CGATS.CGATS(ti3)
    data = ti3.queryv1("DATA")
    datalen = len(data)
    black = data.queryi1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
    if black:
        black = black["XYZ_X"], black["XYZ_Y"], black["XYZ_Z"]
    elif print_debuginfo:
        print("Warning - no black patch found in CGATS")
    white = data.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
    if white:
        white = white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]
    elif print_debuginfo:
        print("Warning - no white patch found in CGATS")
    suspicious = []
    prev = {}
    delta = {}
    for index in data:
        item = data[index]
        (sRGBLab, Lab, delta_to_sRGB, criteria1, debuginfo) = check_ti3_criteria1(
            (item["RGB_R"], item["RGB_G"], item["RGB_B"]),
            (item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"]),
            black,
            white,
            print_debuginfo=False,
        )
        if criteria1 or (
            prev
            and (
                max(prev["item"]["RGB_R"], item["RGB_R"])
                - min(prev["item"]["RGB_R"], item["RGB_R"])
                > 1.0 / 2.55
                or max(prev["item"]["RGB_G"], item["RGB_G"])
                - min(prev["item"]["RGB_G"], item["RGB_G"])
                > 1.0 / 2.55
                or max(prev["item"]["RGB_B"], item["RGB_B"])
                - min(prev["item"]["RGB_B"], item["RGB_B"])
                > 1.0 / 2.55
            )
        ):
            if prev:
                (delta, sRGB_delta, criteria2) = check_ti3_criteria2(
                    prev["Lab"],
                    Lab,
                    prev["sRGBLab"],
                    sRGBLab,
                    (
                        prev["item"]["RGB_R"],
                        prev["item"]["RGB_G"],
                        prev["item"]["RGB_B"],
                    ),
                    (item["RGB_R"], item["RGB_G"], item["RGB_B"]),
                )
            else:
                criteria2 = False
            if criteria1 or criteria2:
                if print_debuginfo:
                    if criteria2:
                        debuginfo = (
                            "%s  dE to previous XYZ->Lab(D50): "
                            "%5.3f  dE_OK: %s  L_OK: %s  "
                            "0.5 dE RGB(sRGB)->Lab(D50) to previous "
                            "RGB(sRGB)->Lab(D50): %5.3f"
                        ) % (
                            debuginfo,
                            delta["E"],
                            delta["E_ok"],
                            delta["L_ok"],
                            sRGB_delta["E"],
                        )
                    sample_id = "Patch #%%.0%id" % len(str(datalen))
                    print(sample_id % item.SAMPLE_ID, debuginfo)
                suspicious.append(
                    (
                        prev["item"] if criteria2 else None,
                        item,
                        delta if criteria2 else None,
                        sRGB_delta if criteria2 else None,
                        prev["delta_to_sRGB"] if criteria2 else None,
                        delta_to_sRGB,
                    )
                )
        prev["item"] = item
        prev["sRGBLab"] = sRGBLab
        prev["Lab"] = Lab
        prev["delta_to_sRGB"] = delta_to_sRGB
    return suspicious


def create_shaper_curves(
    RGB_XYZ,
    bwd_mtx,
    single_curve=False,
    bpc=True,
    logfn=None,
    slope_limit=False,
    profile=None,
    options_dispcal=None,
    optimize=False,
    cat="Bradford",
):
    """Create input (device to PCS) shaper curves"""
    RGB_XYZ = dict_sort(RGB_XYZ)
    R_R = []
    G_G = []
    B_B = []
    R_X = []
    G_Y = []
    B_Z = []
    XYZbp = None
    XYZwp = None
    for R, G, B in RGB_XYZ:
        X, Y, Z = RGB_XYZ[(R, G, B)]
        X, Y, Z = colormath.adapt(X, Y, Z, RGB_XYZ[(100, 100, 100)], cat=cat)
        if 100 > R > 0 and min(X, Y, Z) < 100.0 / 65535:
            # Skip non-black/non-white gray values not encodable in 16-bit
            continue
        if 100 > R > 0 and G_Y and (Y < G_Y[-1] * 100 or Y > 100):
            # Skip values with negative Y increments,
            # or Y above 100 with RGB < 100
            if logfn:
                logfn(
                    "Warning: Skipping RGB %.2f %.2f %.2f XYZ %.6f %.6f %.6f"
                    % (R, G, B, X, Y, Z),
                    "because Y is not monotonically increasing",
                )
            continue
        R_R.append(R / 100.0)
        G_G.append(G / 100.0)
        B_B.append(B / 100.0)
        R_X.append(X / 100.0)
        G_Y.append(Y / 100.0)
        B_Z.append(Z / 100.0)
        if R == G == B == 0:
            XYZbp = [v / 100.0 for v in (X, Y, Z)]
        elif R == G == B == 100:
            XYZwp = [v / 100.0 for v in (X, Y, Z)]

    numvalues = len(R_R)

    if numvalues <= 2 or XYZbp[1] >= XYZwp[1] * 0.9:
        # Botched measurements
        raise UntracedError(lang.getstr("error.luminance.not_monotonically_increasing"))

    if XYZwp[1] <= 0 or math.isnan(XYZwp[1]):
        raise UntracedError(lang.getstr("error.luminance.invalid"))

    # Scale black to zero
    for i in range(numvalues):
        if bwd_mtx * [1, 1, 1] == [1, 1, 1]:
            (R_X[i], G_Y[i], B_Z[i]) = colormath.apply_bpc(
                R_X[i], G_Y[i], B_Z[i], XYZbp, (0, 0, 0), XYZwp
            )
        else:
            (R_X[i], G_Y[i], B_Z[i]) = colormath.blend_blackpoint(
                R_X[i], G_Y[i], B_Z[i], XYZbp
            )

    # Interpolate TRC

    use_individual_channel_gammas = True

    gammas = [[], [], []]
    for j, gamma in enumerate(gammas):
        values = []
        for i, v in enumerate((R_R, G_G, B_B)[j]):
            channel = (R_X, G_Y, B_Z)[j]
            vv = colormath.convert_range(
                channel[i], channel[0], XYZwp[j], channel[0], 1
            )
            if use_individual_channel_gammas:
                channel[i] = vv
            values.append((v, vv))
        gamma[:] = colormath.get_gamma(values, average=False)
        gamma.insert(0, gamma[0])
        gamma.append(gamma[-1])

    if bwd_mtx * [1, 1, 1] == [1, 1, 1]:
        # cLUT profile
        final = 2049
    else:
        # Shaper + matrix profile
        final = 256

    if all(len(gamma) == numvalues for gamma in gammas):
        # Follow curvature by using gamma as hint
        # This can be used to fill in 'missing' values with the right slope
        # E.g. suppose we have measured at signal levels 0%, 25%, 50%, 75%, 100%
        # Linearly interpolating between those (or even using polynomials)
        # will yield unacceptable results especially near black due to not
        # following the typical curvature of additive displays. Using this
        # method, a sensible curvature is maintained.

        numentries = numvalues
        while numentries < 2**12 + 1:
            numentries = (numentries - 1) * 2 + 1

        RGB = (R_R, G_G, B_B)

        gammas_resized = [
            gamma
            and colormath.interp_fill(
                RGB[j],
                gamma,
                (numvalues - 1) * 2 + 1,
                # numentries,
                True,
            )
            for j, gamma in enumerate(gammas)
        ]

        for gamma in gammas_resized:
            gamma[1:-1] = colormath.smooth_avg(gamma[1:-1], 1)

        gammas_resized = [
            gamma and colormath.interp_resize(gamma, numentries, True)
            for gamma in gammas_resized
        ]

        for i in range(1, numvalues - 1):
            X, Y, Z = R_X[i], G_Y[i], B_Z[i]
            if use_individual_channel_gammas:
                R_X[i], G_Y[i], B_Z[i] = (
                    v ** (1.0 / gammas[j][i]) for j, v in enumerate((X, Y, Z))
                )
            else:
                if Y < 0:
                    # This should NOT happen - is this check needed?
                    if logfn:
                        logfn("Warning: Y is negative - clamping to  zero")
                    Y = 0
                if Y:
                    Y2 = Y ** (1.0 / gammas[1][i])
                    R_X[i], G_Y[i], B_Z[i] = (v / Y * Y2 for v in (X, Y, Z))

        for j, values in enumerate((R_X, G_Y, B_Z)):
            values[:] = colormath.interp_fill(RGB[j], values, numentries, True)

        for i in range(1, numentries - 1):
            X, Y, Z = R_X[i], G_Y[i], B_Z[i]
            if use_individual_channel_gammas:
                X, Y, Z = (
                    colormath.convert_range(
                        v ** gammas_resized[j][i],
                        (R_X, G_Y, B_Z)[j][0],
                        1,
                        (R_X, G_Y, B_Z)[j][0],
                        XYZwp[j],
                    )
                    for j, v in enumerate((X, Y, Z))
                )
                R_X[i], G_Y[i], B_Z[i] = X, Y, Z
            else:
                if Y:
                    Y2 = Y ** gammas_resized[1][i]
                    R_X[i], G_Y[i], B_Z[i] = (v / Y * Y2 for v in (X, Y, Z))

        for values in RGB:
            values[:] = colormath.interp_fill(values, values, numentries, True)

        # for i in range(numentries):
        #     print(i, R_R[i], G_G[i], B_B[i], gammas_resized[0][i],
        #           gammas_resized[1][i], gammas_resized[2][i], R_X[i],
        #           G_Y[i], B_Z[i])

        numentries = final
    else:
        # Hmm. Can this happen? Use old (pre 3.8.9.2) interpolation
        numentries = 33

    rinterp = colormath.Interp(R_R, R_X, use_numpy=True)
    ginterp = colormath.Interp(G_G, G_Y, use_numpy=True)
    binterp = colormath.Interp(B_B, B_Z, use_numpy=True)

    curves = []
    for i in range(3):
        curves.append([])

    maxval = numentries - 1.0
    powinterp = {
        "r": colormath.Interp([], []),
        "g": colormath.Interp([], []),
        "b": colormath.Interp([], []),
    }
    RGBwp = bwd_mtx * XYZwp
    for n in range(numentries):
        n /= maxval
        if numentries < final:
            # Apply slight power to input value so we sample near
            # black more accurately
            n **= 1.2
        Y = ginterp(n)
        X = rinterp(n)
        Z = binterp(n)
        if Y >= 1:
            # Fix Y >= 1 to whitepoint. Mainly for HDR with PQ clipping,
            # where input gray < 1 can result in >= white Y
            X, Y, Z = XYZwp
        elif single_curve:
            X, Y, Z = [v * Y for v in XYZwp]
        RGB = bwd_mtx * (X, Y, Z)
        for i, channel in enumerate("rgb"):
            v = RGB[i]
            v = min(max(v, 0), 1)
            if slope_limit:
                v = max(v, n / 64.25)
            if numentries < final:
                powinterp[channel].xp.append(n)
                powinterp[channel].fp.append(v)
            else:
                curves[i].append(v)
    if numentries < final:
        for n in range(numentries):
            for i, channel in enumerate("rgb"):
                v = powinterp[channel](n / maxval)
                curves[i].append(v)

    for curve in curves:
        # Ensure monotonically increasing
        curve[:] = colormath.make_monotonically_increasing(curve)
        if numentries < final:
            # Interpolate to final resolution
            # Spline interpolation to larger size
            x = (i / (final - 1.0) * (len(curve) - 1) for i in range(final))
            spline = ICCP.CRInterpolation(curve)
            curve[:] = (min(max(spline(v), 0), 1) for v in x)
            # Ensure still monotonically increasing
            curve[:] = colormath.make_monotonically_increasing(curve)

    if optimize:
        curves = _create_optimized_shaper_curves(
            bwd_mtx, bpc, single_curve, curves, profile, options_dispcal, XYZbp, logfn
        )

    return curves


def _create_optimized_shaper_curves(
    bwd_mtx, bpc, single_curve, curves, profile, options_dispcal, XYZbp=None, logfn=None
):
    # Get black and white luminance
    if isinstance(profile.tags.get("lumi"), ICCP.XYZType):
        white_cdm2 = profile.tags.lumi.Y
    else:
        white_cdm2 = 100.0
    black_Y = XYZbp and XYZbp[1] or 0
    black_cdm2 = black_Y * white_cdm2

    # Calibration gamma defaults
    gamma_type = None
    calgamma = 0
    outoffset = None
    # Get actual calibration gamma (if any)
    calgarg = get_arg("g", options_dispcal)
    if not calgarg:
        calgarg = get_arg("G", options_dispcal)
    if (
        calgarg
        and isinstance(profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
        and not profile.tags.vcgt.is_linear()
    ):
        calgamma = {"l": -3.0, "s": -2.4, "709": -709, "240": -240}.get(
            calgarg[1][1:], calgamma
        )
        if not calgamma:
            try:
                calgamma = float(calgarg[1][1:])
            except ValueError:
                # Not a gamma value
                pass
        if calgamma:
            gamma_type = calgarg[1][0]
            outoffset = defaults["calibration.black_output_offset"]
            calfarg = get_arg("f", options_dispcal)
            if calfarg:
                try:
                    outoffset = float(calfarg[1][1:])
                except ValueError:
                    pass
            caltrc = ICCP.CurveType(profile=profile)
            if calgamma > 0:
                caltrc.set_bt1886_trc(black_Y, outoffset, calgamma, gamma_type)
            else:
                caltrc.set_trc(calgamma)
            caltf = caltrc.get_transfer_function(True, (0, 1), black_Y, outoffset)
    logfn and logfn("Black relative luminance = %.6f" % round(black_Y, 6))
    if outoffset is not None:
        logfn and logfn("Black output offset = %.2f" % round(outoffset, 2))
    if calgamma > 0:
        logfn and logfn(
            "Calibration gamma = %.2f %s"
            % (round(calgamma, 2), {"g": "relative", "G": "absolute"}.get(gamma_type))
        )
    if calgamma:
        logfn and logfn(
            "Calibration overall transfer function "
            "≈ %s (Δ %.2f%%)" % (caltf[0][0], 100 - caltf[1] * 100)
        )
    if calgamma > 0 and black_Y:
        # Calculate effective gamma
        midpoint = colormath.interp(
            (len(caltrc) - 1) / 2.0, list(range(len(caltrc))), caltrc
        )
        gamma = colormath.get_gamma([(0.5, midpoint / 65535.0)])
        logfn and logfn("Calibration effective gamma = %.2f" % gamma)
    tfs = []
    for i, channel in enumerate("rgb"):
        trc = ICCP.CurveType(profile=profile)
        trc[:] = [v / float(curves[i][-1]) * 65535 for v in curves[i]]
        # Get transfer function and see if we have a good match
        # to a standard. If we do, use the standard transfer
        # function instead of our measurement based one.
        # This avoids artifacts when processing is done in
        # limited (e.g. 8 bit) precision by a color managed
        # application and the source profile uses the same
        # standard transfer function.
        tf = trc.get_transfer_function(True, (0, 1), black_Y, outoffset)
        label = ["Transfer function", channel.upper()]
        label.append("≈ %s (Δ %.2f%%)" % (tf[0][0], 100 - tf[1] * 100))
        logfn and logfn(" ".join(label))
        gamma = tf[0][1]
        if gamma > 0 and black_Y:
            # Calculate effective gamma
            gamma = colormath.get_gamma([(0.5, 0.5**gamma)], vmin=-black_Y)
            logfn and logfn("Effective gamma = %.2f" % round(gamma, 2))
        # Only use standard transfer function if we got a good match
        if tf[1] >= 0.98:
            # Good match
            logfn and logfn("Got good match (+-2%)")
            if (
                single_curve
                and calgamma
                and round(tf[0][1], 1) == round(caltf[0][1], 1)
            ):
                # Use calibration gamma
                tf = caltf
                logfn and logfn("Using calibration transfer function")
            tfs.append((tf, trc))

    if len(tfs) == 3:
        # Only use standard transfer function if we got a good
        # identical match for all three channels.
        optcurves = []
        for i, channel in enumerate("rgb"):
            tf, trc = tfs[i]
            gamma = tf[0][1]
            if gamma > 0 and black_Y:
                # Calculate effective gamma
                egamma = colormath.get_gamma([(0.5, 0.5**gamma)], vmin=-black_Y)
            else:
                egamma = gamma
            if outoffset is None:
                outoffset = tf[0][2]
            if (
                gamma > 0
                and bpc
                and (outoffset == 1.0 or not black_Y)
                and bwd_mtx * [1, 1, 1] != [1, 1, 1]
            ):
                # Single gamma value, BPC, all output offset or
                # zero black luminance
                if gamma_type == "g":
                    gamma = egamma
                trc.set_trc(gamma, 1)
            else:
                # Complex or gamma with offset
                if gamma == -1023:
                    # DICOM is a special case
                    trc.set_dicom_trc(black_cdm2, white_cdm2)
                elif gamma == -1886:
                    # BT.1886 is a special case
                    trc.set_bt1886_trc(black_Y)
                elif gamma == -2084:
                    # SMPTE 2084 is a special case
                    trc.set_smpte2084_trc(black_cdm2, white_cdm2)
                elif gamma > 0 and black_Y:
                    # BT.1886-like or power law with offset
                    if bpc and gamma_type == "g":
                        # Use effective gamma needed to
                        # achieve target effective gamma
                        # after accounting for BPC
                        eegamma = colormath.get_gamma(
                            [(0.5, 0.5**egamma)], vmin=-black_Y
                        )
                    else:
                        eegamma = egamma
                    trc.set_bt1886_trc(black_Y, outoffset, eegamma, "g")
                else:
                    # L*, sRGB, Rec. 709, SMPTE 240M, or
                    # power law without offset
                    if bpc and gamma_type == "g":
                        # Use effective gamma
                        gamma = egamma
                    trc.set_trc(gamma)
            trc.apply_bpc()
            tf = trc.get_transfer_function(True, (0, 1), black_Y, outoffset)
            logfn and logfn(
                "Using transfer function for %s: %s" % (channel.upper(), tf[0][0])
            )
            gamma = tf[0][1]
            if gamma > 0 and black_Y:
                # Calculate effective gamma
                gamma = colormath.get_gamma([(0.5, 0.5**gamma)], vmin=-black_Y)
                logfn and logfn("Effective gamma = %.2f" % round(gamma, 2))
            optcurves.append([v / 65535.0 * curves[i][-1] for v in trc])
        curves = optcurves

    return curves


def _applycal_bug_workaround(profile):
    # Argyll applycal can't deal with single gamma TRC tags
    # or TRC tags with less than 256 entries
    for channel in "rgb":
        trc_tag = profile.tags.get(channel + "TRC")
        if isinstance(trc_tag, ICCP.CurveType) and len(trc_tag) < 256:
            num_entries = len(trc_tag)
            if num_entries <= 1:
                # Single gamma
                if num_entries:
                    gamma = trc_tag[0]
                else:
                    gamma = 1.0
                trc_tag.set_trc(gamma, 256)
            else:
                # Interpolate to 256 entries
                entry_max = num_entries - 1.0
                interp = colormath.Interp(
                    [i / entry_max for i in range(num_entries)], trc_tag[:]
                )
                trc_tag[:] = [interp(i / 255.0) for i in range(256)]


def get_argyll_version(name, silent=False, paths=None):
    """Determine version of a certain Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        silent (bool): Silently check Argyll version. Default is False.
        paths (Union[list, None]): Paths to look for Argyll executables.

    Returns:
        str: The Argyll utility version.
    """
    argyll_version_string = get_argyll_version_string(name, silent, paths)
    return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(name, silent=False, paths=None):
    """Return the version of the requested Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        silent (bool): Silently check Argyll version. Default is False.
        paths (Union[list, None]): Paths to look for Argyll executables.

    Returns:
        str: The Argyll utility version.
    """
    argyll_version_string = "0.0.0"
    if (silent and check_argyll_bin(paths)) or (
        not silent and check_set_argyll_bin(paths)
    ):
        argyll_version_string = base_get_argyll_version_string(name, paths)
    return argyll_version_string


def get_current_profile_path(
    include_display_profile=True, save_profile_if_no_path=False
):
    profile = None
    profile_path = getcfg("calibration.file", False)
    if profile_path:
        filename, ext = os.path.splitext(profile_path)
        if ext.lower() in (".icc", ".icm"):
            try:
                profile = ICCP.ICCProfile(profile_path)
            except Exception as exception:
                print("ICCP.ICCProfile(%r):" % profile_path, exception)
    elif include_display_profile:
        profile = config.get_display_profile()
        if profile and not profile.fileName and save_profile_if_no_path:
            if profile.ID == "\0" * 16:
                profile.calculateID()
            profile_cache_path = os.path.join(cache, "icc")
            if check_create_dir(profile_cache_path) is True:
                profile.fileName = os.path.join(
                    profile_cache_path,
                    "id=" + hexlify(profile.ID).decode() + profile_ext,
                )
                if not os.path.isfile(profile.fileName):
                    profile.write()
    if profile:
        return profile.fileName


def parse_argument_string(args):
    """Parses an argument string and returns a list of arguments."""
    return [
        re.sub(r'^["\']|["\']$', "", arg)
        for arg in re.findall(
            r'(?:^|\s+)(-[^\s"\']+|"[^"]+?"|\'[^\']+?\'|[^\s"\']+)', args
        )
    ]


def get_cfg_option_from_args(option_name, argmatch, args, whole=False):
    """Parse args and return option (if found), otherwise default"""
    option = defaults[option_name]
    iarg = get_arg(argmatch, args, whole)
    if iarg:
        if len(iarg[1]) == len(argmatch):
            # Option value is the next argument
            if len(args) > iarg[0] + 1:
                option = args[iarg[0] + 1]
        else:
            # Option value follows argument directly
            option = iarg[1][len(argmatch) :]
    return option


def get_options_from_args(dispcal_args=None, colprof_args=None) -> ([str], [str]):
    """Extract options used for dispcal and colprof from argument strings."""
    re_options_dispcal = [
        r"[moupHVFE]",
        r"d(?:\d+(?:,\d+)?|madvr|web)",
        r"[cv]\d+",
        r"q(?:%s)" % "|".join(config.valid_values["calibration.quality"]),
        r"y(?:%s)"
        % "|".join([_f for _f in config.valid_values["measurement_mode"] if _f]),
        r"[tT](?:\d+(?:\.\d+)?)?",
        r"w\d+(?:\.\d+)?,\d+(?:\.\d+)?",
        r"[bfakAB]\d+(?:\.\d+)?",
        r"(?:g(?:240|709|l|s)|[gG]\d+(?:\.\d+)?)",
        r"[pP]\d+(?:\.\d+)?,\d+(?:\.\d+)?,\d+(?:\.\d+)?",
        r'X(?:\s*\d+|\s+["\'][^"\']+?["\'])',  # Argyll >= 1.3.0 colorimeter correction matrix / Argyll >= 1.3.4 calibration spectral sample
        r"I[bw]{,2}",  # Argyll >= 1.3.0 drift compensation
        r"YA",  # Argyll >= 1.5.0 disable adaptive mode
        r"Q\w+",
    ]
    re_options_colprof = [
        r"q[lmh]",
        r"b[lmh]",  # B2A quality
        r"a(?:%s)" % "|".join(config.valid_values["profile.type"]),
        r'[sSMA]\s+["\'][^"\']+?["\']',
        r"[cd](?:%s)(?=\W|$)" % "|".join(viewconds),
        r"[tT](?:%s)(?=\W|$)" % "|".join(intents),
    ]
    options_dispcal = []
    options_colprof = []

    if dispcal_args:
        if isinstance(dispcal_args, bytes):
            dispcal_args = dispcal_args.decode("UTF-8")
        options_dispcal = re.findall(
            r" -(%s)" % "|".join(re_options_dispcal), " %s" % dispcal_args
        )
    if colprof_args:
        if isinstance(colprof_args, bytes):
            colprof_args = colprof_args.decode("UTF-8")
        options_colprof = re.findall(
            r" -(" + "|".join(re_options_colprof) + ")", " " + colprof_args
        )
    return options_dispcal, options_colprof


def get_options_from_cprt(cprt):
    """Extract options used for dispcal and colprof from profile copyright."""
    if not isinstance(cprt, str):
        if isinstance(cprt, (ICCP.TextDescriptionType, ICCP.MultiLocalizedUnicodeType)):
            cprt = str(cprt)
        else:
            cprt = str(cprt, fs_enc, "replace")
    dispcal_args = cprt.split(" dispcal ")
    colprof_args = None
    if len(dispcal_args) > 1:
        dispcal_args[1] = dispcal_args[1].split(" colprof ")
        if len(dispcal_args[1]) > 1:
            colprof_args = dispcal_args[1][1]
        dispcal_args = dispcal_args[1][0]
    else:
        dispcal_args = None
        colprof_args = cprt.split(" colprof ")
        if len(colprof_args) > 1:
            colprof_args = colprof_args[1]
        else:
            colprof_args = None
    return dispcal_args, colprof_args


def get_options_from_cal(cal) -> ([str], [str]):
    if not isinstance(cal, CGATS.CGATS):
        cal = CGATS.CGATS(cal)
    if 0 in cal:
        cal = cal[0]
    if not cal or "ARGYLL_DISPCAL_ARGS" not in cal or not cal.ARGYLL_DISPCAL_ARGS:
        return [], []
    dispcal_args = cal.ARGYLL_DISPCAL_ARGS[0]
    return get_options_from_args(dispcal_args)


def get_options_from_profile(profile):
    """Try and get options from profile. First, try the 'targ' tag and
    look for the special DisplayCAL sections 'ARGYLL_DISPCAL_ARGS' and
    'ARGYLL_COLPROF_ARGS'. If either does not exist, fall back to the
    copyright tag (DisplayCAL < 0.4.0.2)"""
    if not isinstance(profile, ICCP.ICCProfile):
        profile = ICCP.ICCProfile(profile)
    dispcal_args = None
    colprof_args = None
    if "targ" in profile.tags:
        ti3 = CGATS.CGATS(profile.tags.targ)
        if 1 in ti3 and "ARGYLL_DISPCAL_ARGS" in ti3[1] and ti3[1].ARGYLL_DISPCAL_ARGS:
            dispcal_args = ti3[1].ARGYLL_DISPCAL_ARGS[0]
        if 0 in ti3 and "ARGYLL_COLPROF_ARGS" in ti3[0] and ti3[0].ARGYLL_COLPROF_ARGS:
            colprof_args = ti3[0].ARGYLL_COLPROF_ARGS[0]
    if not dispcal_args and "cprt" in profile.tags:
        dispcal_args = get_options_from_cprt(profile.getCopyright())[0]
    if not colprof_args and "cprt" in profile.tags:
        colprof_args = get_options_from_cprt(profile.getCopyright())[1]
    return get_options_from_args(dispcal_args, colprof_args)


def get_options_from_ti3(ti3):
    """Try and get options from TI3 file by looking for the special
    DisplayCAL sections 'ARGYLL_DISPCAL_ARGS' and 'ARGYLL_COLPROF_ARGS'.
    """
    if not isinstance(ti3, CGATS.CGATS):
        ti3 = CGATS.CGATS(ti3)
    dispcal_args = None
    colprof_args = None
    if 1 in ti3 and "ARGYLL_DISPCAL_ARGS" in ti3[1] and ti3[1].ARGYLL_DISPCAL_ARGS:
        dispcal_args = ti3[1].ARGYLL_DISPCAL_ARGS[0]
    if 0 in ti3 and "ARGYLL_COLPROF_ARGS" in ti3[0] and ti3[0].ARGYLL_COLPROF_ARGS:
        colprof_args = ti3[0].ARGYLL_COLPROF_ARGS[0]
    return get_options_from_args(dispcal_args, colprof_args)


def get_pattern_geometry():
    """Return pattern geometry for pattern generator"""
    x, y, size = [float(v) for v in getcfg("dimensions.measureframe").split(",")]
    if os.getenv("XDG_SESSION_TYPE") == "wayland":
        # No way to get coordinates under Wayland, default to center
        x = y = 0.5
    size = size * defaults["size.measureframe"]
    match = re.search(r"@ -?\d+, -?\d+, (\d+)x(\d+)", getcfg("displays", raw=True))
    if match:
        display_size = [int(item) for item in match.groups()]
    else:
        display_size = 1920, 1080
    w, h = [min(size / v, 1.0) for v in display_size]
    if config.get_display_name(None, True) == "Prisma":
        w = h
    x = (display_size[0] - w * display_size[0]) * x / display_size[0]
    y = (display_size[1] - h * display_size[1]) * y / display_size[1]
    x, y, w, h = [max(v, 0) for v in (x, y, w, h)]
    size = w * h
    return x, y, w, h, size


def get_python_and_pythonpath():
    """Return (system) python and pythonpath"""
    # Determine the path of python, and python module search paths
    # If we are running 'frozen', expect python.exe in the same directory
    # as the packed executable.
    # py2exe: The python executable can be included via setup script by
    # adding it to 'data_files'
    pythonpath = list(sys.path)
    dirname = os.path.dirname(sys.executable)
    if sys.platform == "win32":
        if getattr(sys, "frozen", False):
            pythonpath = [dirname]
            # If we are running 'frozen', add library.zip and lib\library.zip
            # to sys.path
            # py2exe: Needs appropriate 'zipfile' option in setup script and
            # 'bundle_files' 3
            pythonpath.append(os.path.join(dirname, "library.zip"))
            pythonpath.append(os.path.join(dirname, "library.zip", appname))
            if os.path.isdir(os.path.join(dirname, "lib")):
                dirname = os.path.join(dirname, "lib")
                pythonpath.append(os.path.join(dirname, "library.zip"))
                pythonpath.append(os.path.join(dirname, "library.zip", appname))
        python = os.path.join(dirname, "python.exe")
    else:
        # Linux / Mac OS X
        if isapp:
            python = os.path.join(dirname, "python")
        else:
            paths = os.defpath.split(os.pathsep)
            python = (
                which("python3.7", paths)
                or which("python3.6", paths)
                or "/usr/bin/env python"
            )
    return (python, pythonpath)


def get_arg(argmatch, args, whole=False):
    """Return first found entry beginning with the argmatch string or None"""
    for i, arg in enumerate(args):
        if (whole and arg == argmatch) or (not whole and arg.startswith(argmatch)):
            return i, arg


def get_default_headers():
    """Get default headers for HTTP request"""
    if sys.platform == "darwin":
        # Python's platform.platform output is useless under Mac OS X
        # (e.g. 'Darwin-15.0.0-x86_64-i386-64bit' for Mac OS X 10.11 El Capitan)
        oscpu = "Mac OS X %s; %s" % (mac_ver()[0], mac_ver()[-1])
    elif sys.platform == "win32":
        machine = platform.machine()
        oscpu = "%s; %s" % (
            safe_str(" ".join([v for v in win_ver() if v]), "ASCII", "asciize"),
            {"AMD64": "x86_64"}.get(machine, machine),
        )
    else:
        # Linux
        oscpu = "%s; %s" % (
            " ".join([distro.id(), distro.version(), distro.codename()]),
            platform.machine(),
        )
    return {
        "User-Agent": "%s/%s (%s)" % (appname, version, oscpu),
        "Accept-Language": "%s,*;q=0.5" % lang.getcode(),
    }


def http_request(
    parent=None,
    domain=None,
    request_type="GET",
    path="",
    params=None,
    files=None,
    headers=None,
    charset="UTF-8",
    failure_msg="",
    silent=False,
):
    """HTTP request wrapper"""
    if params is None:
        params = {}
    if files:
        content_type, params = encode_multipart_formdata(iter(params.items()), files)
    else:
        for key in params:
            params[key] = safe_str(params[key], charset)
        params = urllib.parse.urlencode(params)
    if headers is None:
        headers = get_default_headers()
        if request_type == "GET":
            path += "?" + params
            params = None
        else:
            if files:
                headers.update(
                    {"Content-Type": content_type, "Content-Length": str(len(params))}
                )
            else:
                headers.update(
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "text/plain",
                    }
                )
    conn = http.client.HTTPConnection(domain)
    try:
        conn.request(request_type, path, params, headers)
        resp = conn.getresponse()
    except (socket.error, http.client.HTTPException) as exception:
        msg = " ".join(
            [
                failure_msg,
                lang.getstr(
                    "connection.fail", " ".join([str(arg) for arg in exception.args])
                ),
            ]
        ).strip()
        print(msg)
        if not silent:
            wx.CallAfter(
                InfoDialog,
                parent,
                msg=msg,
                ok=lang.getstr("ok"),
                bitmap=geticon(32, "dialog-error"),
                log=False,
            )
        return False
    if resp.status >= 400:
        uri = "http://" + domain + path
        msg = (
            " ".join(
                [
                    failure_msg,
                    lang.getstr(
                        "connection.fail.http",
                        " ".join([str(resp.status), resp.reason]),
                    ),
                ]
            ).strip()
            + "\n"
            + uri
        )
        print(msg)
        html = universal_newlines(resp.read().strip())
        html = re.sub(
            re.compile(r"<script.*?</script>", re.I | re.S),
            "<!-- SCRIPT removed -->",
            html,
        )
        html = re.sub(
            re.compile(r"<style.*?</style>", re.I | re.S),
            "<!-- STYLE removed -->",
            html,
        )
        print(html)
        if not silent:
            wx.CallAfter(
                HtmlInfoDialog,
                parent,
                msg=msg,
                html=html,
                ok=lang.getstr("ok"),
                bitmap=geticon(32, "dialog-error"),
                log=False,
            )
        return False
    return resp


def insert_ti_patches_omitting_RGB_duplicates(cgats1, cgats2_path, logfn=print):
    """Insert patches from first TI file after first patch of second TI,
    ignoring RGB duplicates. Return second TI as CGATS instance.
    """
    cgats2 = CGATS.CGATS(cgats2_path)
    cgats1_data = cgats1.queryv1("DATA")
    data = cgats2.queryv1("DATA")
    data_format = cgats2.queryv1("DATA_FORMAT")
    # Get only RGB data
    data.parent.DATA_FORMAT = CGATS.CGATS()
    data.parent.DATA_FORMAT.key = "DATA_FORMAT"
    data.parent.DATA_FORMAT.parent = data
    data.parent.DATA_FORMAT.root = data.root
    data.parent.DATA_FORMAT.type = b"DATA_FORMAT"
    for i, label in enumerate(("RGB_R", "RGB_G", "RGB_B")):
        data.parent.DATA_FORMAT[i] = label
    cgats1_data.parent.DATA_FORMAT = data.parent.DATA_FORMAT
    rgbdata = str(data)
    # Restore DATA_FORMAT
    data.parent.DATA_FORMAT = data_format
    # Collect all preconditioning point datasets not in data
    cgats1_data.vmaxlen = data.vmaxlen
    cgats1_datasets = []
    for i in cgats1_data:
        dataset = cgats1_data[i]
        if str(dataset) not in rgbdata:
            # Not a duplicate
            cgats1_datasets.append(dataset)
    if cgats1_datasets:
        # Insert preconditioned point datasets after first patch
        if logfn:
            logfn(
                "%s: Adding %i fixed points to %s"
                % (appname, len(cgats1_datasets), cgats2_path)
            )
        data.moveby1(1, len(cgats1_datasets))
        for i, dataset in enumerate(cgats1_datasets):
            dataset.key = i + 1
            dataset.parent = data
            dataset.root = data.root
            data[dataset.key] = dataset
    return cgats2


def make_argyll_compatible_path(path):
    """Make the path compatible with the Argyll utilities.

    This is currently only effective under Windows to make sure that any
    unicode 'division' slashes in the profile name are replaced with
    underscores.
    """
    skip = -1
    regex = r"\\\\\?\\"
    driver_letter_escape_char = ":"
    os_path_sep = os.path.sep
    if isinstance(path, bytes):
        regex = regex.encode("utf-8")
        driver_letter_escape_char = driver_letter_escape_char.encode("utf-8")
        os_path_sep = os_path_sep.encode("utf-8")

    if re.match(regex, path, re.I):
        # Don't forget about UNC paths:
        # \\?\UNC\Server\Volume\File
        # \\?\C:\File
        skip = 2

    parts = path.split(os_path_sep)
    if sys.platform == "win32" and len(parts) > skip + 1:
        driveletterpart = parts[skip + 1]
        if (
            len(driveletterpart) == 2
            and driveletterpart[0].upper() in string.ascii_uppercase
            and driveletterpart[1] == driver_letter_escape_char
        ):
            skip += 1

    for i, part in enumerate(parts):
        if i > skip:
            parts[i] = make_filename_safe(part)
    return os_path_sep.join(parts)


def set_argyll_bin(parent=None, silent=False, callafter=None, callafter_args=()):
    """Set the directory containing the Argyll CMS binary executables."""
    if parent and not parent.IsShownOnScreen():
        parent = None  # do not center on parent if not visible
    # Check if Argyll version on PATH is newer than configured Argyll version
    paths = getenvu("PATH", os.defpath).split(os.pathsep)
    argyll_version_string = get_argyll_version_string("dispwin", True, paths)
    argyll_version = parse_argyll_version_string(argyll_version_string)
    argyll_version_string_cfg = get_argyll_version_string("dispwin", True)
    argyll_version_cfg = parse_argyll_version_string(argyll_version_string_cfg)
    # Don't prompt for 1.2.3_foo if current version is 1.2.3
    # but prompt for 1.2.3 if current version is 1.2.3_foo
    # Also prompt for 1.2.3_beta2 if current version is 1.2.3_beta
    if (
        argyll_version > argyll_version_cfg
        and (
            argyll_version[:4] == argyll_version_cfg[:4]
            or not argyll_version_string.startswith(argyll_version_string_cfg)
        )
    ) or (
        argyll_version < argyll_version_cfg
        and argyll_version_string_cfg.startswith(argyll_version_string)
        and "beta" in argyll_version_string_cfg.lower()
    ):
        argyll_dir = os.path.dirname(get_argyll_util("dispwin", paths) or "")
        dlg = ConfirmDialog(
            parent,
            msg=lang.getstr(
                "dialog.select_argyll_version",
                (argyll_version_string, argyll_version_string_cfg),
            ),
            ok=lang.getstr("ok"),
            cancel=lang.getstr("cancel"),
            alt=lang.getstr("browse"),
            bitmap=geticon(32, "dialog-question"),
        )
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if dlg_result == wx.ID_OK:
            setcfg("argyll.dir", None)
            # Always write cfg directly after setting Argyll directory so
            # subprocesses that read the configuration will use the right
            # executables
            writecfg()
            return True
        if dlg_result == wx.ID_CANCEL:
            if callafter:
                callafter(*callafter_args)
            return False
    else:
        argyll_dir = None
    if parent and not check_argyll_bin():
        dlg = ConfirmDialog(
            parent,
            msg=lang.getstr("dialog.argyll.notfound.choice"),
            ok=lang.getstr("download"),
            cancel=lang.getstr("cancel"),
            alt=lang.getstr("browse"),
            bitmap=geticon(32, "dialog-question"),
        )
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if dlg_result == wx.ID_OK:
            # Download Argyll CMS
            from DisplayCAL.display_cal import app_update_check

            app_update_check(parent, silent, argyll=True)
            return False
        elif dlg_result == wx.ID_CANCEL:
            if callafter:
                callafter(*callafter_args)
            return False
    defaultPath = os.path.join(*get_verified_path("argyll.dir", path=argyll_dir))
    dlg = wx.DirDialog(
        parent,
        lang.getstr("dialog.set_argyll_bin"),
        defaultPath=defaultPath,
        style=wx.DD_DIR_MUST_EXIST,
    )
    dlg.Center(wx.BOTH)
    result = False
    while not result:
        result = dlg.ShowModal() == wx.ID_OK
        if result:
            path = dlg.GetPath().rstrip(os.path.sep)
            if os.path.basename(path) != "bin":
                path = os.path.join(path, "bin")
            result = check_argyll_bin([path])
            if result:
                if verbose >= 3:
                    print("Setting Argyll binary directory:", path)
                setcfg("argyll.dir", path)
                # Always write cfg directly after setting Argyll directory so
                # subprocesses that read the configuration will use the right
                # executables
                writecfg()
                break
            else:
                not_found = []
                for name in argyll_names:
                    if (
                        not get_argyll_util(name, [path])
                        and name not in argyll_optional
                    ):
                        not_found.append(
                            (" " + lang.getstr("or") + " ").join(
                                [
                                    altname
                                    for altname in [
                                        altname + exe_ext
                                        for altname in argyll_altnames[name]
                                    ]
                                    if "argyll" not in altname
                                ]
                            )
                        )
                InfoDialog(
                    parent,
                    msg=path
                    + "\n\n"
                    + lang.getstr("argyll.dir.invalid", ", ".join(not_found)),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
        else:
            break
    dlg.Destroy()
    if not result and callafter:
        callafter(*callafter_args)
    return result


class EvalFalse(object):
    """Evaluate to False in boolean comparisons."""

    def __init__(self, wrapped_object):
        self._wrapped_object = wrapped_object

    def __getattribute__(self, name):
        return getattr(object.__getattribute__(self, "_wrapped_object"), name)

    def __bool__(self):
        return False


class DummyDialog(object):
    def __init__(self, *args, **kwargs):
        self.is_shown_on_screen = True

    def Close(self, force=False):
        pass

    def Destroy(self):
        pass

    def EndModal(self, id=-1):
        return id

    def Hide(self):
        pass

    def IsShownOnScreen(self):
        return self.is_shown_on_screen

    def Show(self, show=True):
        self.is_shown_on_screen = show

    def ShowModal(self):
        pass


class FilteredStream:
    """Wrap a stream and filter all lines written to it."""

    # Discard the whole line if it is empty after replacing patterns
    discard = ""

    # If one of the triggers is contained in a line, skip the whole line
    triggers = [
        "Place instrument on test window",
        "key to continue",
        "key to retry",
        "key to take a reading",
        "] to read",
        "' to set",
        "' to report",
        "' to toggle",
        " or Q to ",
        "place on the white calibration reference",
        "or place on the calibration reference",
        "read failed due to the sensor being in the wrong position",
        "Ambient filter should be removed",
        "The instrument can be removed from the screen",
    ] + INST_CAL_MSGS

    substitutions = {
        r"\^\[": "",  # ESC key on Linux/OSX
        "patch ": "Patch ",
        re.compile(r"Point \d+", re.I): "",
    }

    # Strip these patterns from input before writing. Note that this only works
    # on full lines (ending with linesep_in)
    prestrip = ""

    def __init__(
        self,
        stream,
        data_encoding=None,
        file_encoding=None,
        errors="replace",
        discard=None,
        linesep_in="\r\n",
        linesep_out="\n",
        substitutions=None,
        triggers=None,
        prestrip=None,
    ):
        self.stream = stream
        self.data_encoding = data_encoding
        self.file_encoding = file_encoding
        self.errors = errors
        if discard is not None:
            self.discard = discard
        self.linesep_in = linesep_in
        self.linesep_out = linesep_out
        if substitutions is not None:
            self.substitutions = substitutions
        if triggers is not None:
            self.triggers = triggers
        if prestrip is not None:
            self.prestrip = prestrip
        self._buffer = ""

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def write(self, data):
        """Write data to stream, stripping all unwanted output.

        Incoming lines are expected to be delimited by linesep_in.
        """
        if not data:
            return

        if isinstance(data, bytes):
            data = data.decode()

        if self.prestrip and (re.search(self.prestrip, data) or self._buffer):
            if not data.endswith(self.linesep_in):
                # Buffer all data until we see a line ending
                self._buffer += data
                return
            elif self._buffer:
                # Assemble the full line from the buffer
                data = self._buffer + data
                self._buffer = ""
            data = re.sub(self.prestrip, "", data)

        lines = []
        for line in data.split(self.linesep_in):
            if line and not re.sub(self.discard, "", line):
                line = ""
            write = True
            for trigger in self.triggers:
                if trigger.lower() in line.lower():
                    write = False
                    break
            if write:
                if self.data_encoding and not isinstance(line, str):
                    line = line.decode(self.data_encoding, self.errors)
                for search in self.substitutions:
                    sub = self.substitutions[search]
                    line = re.sub(search, sub, line)
                if self.file_encoding:
                    line = line.encode(self.file_encoding, self.errors)
                lines.append(line)
        if lines:
            self.stream.write(self.linesep_out.join(lines))


class Producer(object):
    """Generic producer."""

    def __init__(self, worker, producer, continue_next=False):
        self.worker = worker
        self.producer = producer
        self.continue_next = continue_next

    def __call__(self, *args, **kwargs):
        try:
            result = self.producer(*args, **kwargs)
        except Exception as exception:
            if debug:
                messages = traceback.format_exception(exception)
                print(
                    "[D] Worker raised an unhandled exception: \n" + "\n".join(messages)
                )
            raise
        if not self.continue_next and self.worker._progress_wnd:
            if hasattr(
                self.worker.progress_wnd, "animbmp"
            ) and self.worker.progress_wnd.progress_type in (0, 2):
                # Allow time for animation fadeout
                wx.CallAfter(self.worker.progress_wnd.stop_timer, False)
                if self.worker.progress_wnd.progress_type == 0:
                    sleep(4)
                else:
                    sleep(1)
        return result


class StringWithLengthOverride(UserString):
    """Allow defined behavior in comparisons and when evaluating length."""

    def __init__(self, seq, length=None):
        UserString.__init__(self, seq)
        if length is None:
            length = len(seq)
        self.length = length

    def __len__(self):
        return self.length


class Sudo(object):
    """Determine if a command can be run via sudo"""

    def __init__(self):
        self.availoptions = {}
        self.sudo = which("sudo")
        if self.sudo:
            # Determine available sudo options
            man = which("man")
            if man:
                manproc = sp.Popen([man, "sudo"], stdout=sp.PIPE, stderr=sp.PIPE)
                # Strip formatting
                stdout = re.sub(b".\x08", b"", manproc.communicate()[0])
                self.availoptions = {
                    "E": bool(re.search(rb"-E\W", stdout)),
                    "l [command]": bool(re.search(rb"-l\W(?:.*?\W)?command\W", stdout)),
                    "K": bool(re.search(rb"-K\W", stdout)),
                    "k": bool(re.search(rb"-k\W", stdout)),
                }
            if debug:
                print(
                    "[D] Available sudo options:",
                    ", ".join(
                        [
                            option
                            for option in list(self.availoptions.keys())
                            if self.availoptions[option]
                        ]
                    ),
                )

    def __len__(self):
        return int(bool(self.sudo))

    def __str__(self):
        return str(self.sudo or "")

    def _expect_timeout(self, patterns, timeout=-1, child_timeout=1):
        """wexpect.spawn.expect with better timeout handling.

        The default expect can block up to timeout seconds if the child is already dead.
        To prevent this, we run expect in a loop until a pattern is matched, timeout is
        reached or an exception occurs. The max time an expect call will block if the
        child is already dead can be set with the child_timeout parameter.
        """
        if timeout == -1:
            timeout = self.subprocess.timeout
        patterns = list(patterns)
        if wexpect.TIMEOUT not in patterns:
            patterns.append(wexpect.TIMEOUT)
        start = time()
        while True:
            result = self.subprocess.expect(patterns, timeout=child_timeout)
            if (
                self.subprocess.after is not wexpect.TIMEOUT
                or time() - start >= timeout
            ):
                break
        return result

    def _terminate(self):
        """Terminate running sudo subprocess."""
        self.subprocess.sendcontrol("C")
        self._expect_timeout([wexpect.EOF], 10)
        if self.subprocess.after is wexpect.TIMEOUT:
            print("Warning: sudo timed out")
            if not self.subprocess.terminate(force=True):
                print("Warning: Couldn't terminate timed-out sudo subprocess")
        else:
            subprocess_before = self.subprocess.before.strip()
            if isinstance(subprocess_before, bytes):
                subprocess_before = subprocess_before.decode(enc, "replace")
            print(subprocess_before)

    def authenticate(self, args, title, parent=None):
        """Authenticate for a given command

        The return value will be a tuple (auth_successful, password).

        auth_successful will be a custom class that will always have length 0 if
        authentication was not successful or the command is not allowed (even
        if the actual string length is non-zero), thus allowing for easy
        boolean comparisons.

        """
        # Authentication using sudo is pretty convoluted if dealing with
        # platform and configuration differences. Ask for a password by first
        # clearing any cached credentials (sudo -K) so that sudo is guaranteed
        # to ask for a password if a command is run through it, then we spawn
        # sudo true (with true being the standard GNU utility that always
        # has an exit status of 0) and expect the password prompt. The user
        # is then given the opportunity to enter a password, which is then fed
        # to sudo. If sudo exits with a status of 0, the password must have
        # been accepted, but we still don't know for sure if our command is
        # allowed, so we run sudo -l <command> to determine if it is
        # indeed allowed.
        pwd = ""
        dlg = ConfirmDialog(
            parent,
            title=title,
            msg=lang.getstr("dialog.enter_password"),
            ok=lang.getstr("ok"),
            cancel=lang.getstr("cancel"),
            bitmap=geticon(32, "lock"),
        )
        dlg.pwd_txt_ctrl = wx.TextCtrl(
            dlg, -1, pwd, size=(320, -1), style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER
        )
        dlg.pwd_txt_ctrl.Bind(wx.EVT_TEXT_ENTER, lambda event: dlg.EndModal(wx.ID_OK))
        dlg.sizer3.Add(
            dlg.pwd_txt_ctrl,
            1,
            # flag=wx.TOP | wx.ALIGN_LEFT, border=12)
            flag=wx.TOP,
            border=12,
        )
        dlg.ok.SetDefault()
        dlg.sizer0.SetSizeHints(dlg)
        dlg.sizer0.Layout()
        # Remove cached credentials
        self.kill()
        sudo_args = ["-p", "Password:", "true"]
        try:
            p = self.subprocess = wexpect.spawn(safe_str(self.sudo), sudo_args)
        except Exception as exception:
            return (
                StringWithLengthOverride(
                    "Could not run {} {}: {}".format(
                        self.sudo, " ".join(sudo_args), exception
                    ),
                    0,
                ),
                pwd,
            )
        self._expect_timeout(["Password:", wexpect.EOF], 10)
        # We need to call isalive() to set the exitstatus
        while p.isalive() and p.after == "Password:":
            # Ask for password
            dlg.pwd_txt_ctrl.SetFocus()
            result = dlg.ShowModal()
            pwd = dlg.pwd_txt_ctrl.GetValue()
            if result != wx.ID_OK:
                self._terminate()
                return False, pwd
            p.send(pwd + os.linesep)
            self._expect_timeout(["Password:", wexpect.EOF], 10)
            if p.after == "Password:":
                msg = lang.getstr("dialog.enter_password")
                errstr = p.before.strip()
                if errstr:
                    print(errstr)
                    msg = "\n\n".join([errstr, msg])
                dlg.message.SetLabel(msg)
                dlg.message.Wrap(dlg.GetSize()[0] - 32 - 12 * 2)
                dlg.pwd_txt_ctrl.SetValue("")
                dlg.sizer0.SetSizeHints(dlg)
                dlg.sizer0.Layout()
        dlg.Destroy()
        if p.after is wexpect.TIMEOUT:
            print("Error: sudo timed out")
            if not p.terminate(force=True):
                print("Warning: Couldn't terminate timed-out sudo subprocess")
            return StringWithLengthOverride("sudo timed out", 0), pwd
        if p.exitstatus != 0:
            return (
                StringWithLengthOverride(
                    p.before.strip().decode(enc, "replace")
                    or ("sudo exited prematurely with status %s" % p.exitstatus),
                    0,
                ),
                pwd,
            )
        # Password was accepted, check if command is allowed
        return self.is_allowed(args, pwd), pwd

    def is_allowed(self, args=None, pwd=""):
        """Check if a command is allowed via sudo.

        Return either a string listing allowed and forbidden commands, or the
        fully-qualified path of the command along with any arguments, or an error
        message in case the command is not allowed, or False if the password was not
        accepted.

        The returned error is a custom class that will always have length 0
        if the command is not allowed (even if the actual string length is
        non-zero), thus allowing for easy boolean comparisons.
        """
        sudo_args = ["-p", "Password:", "-l"]
        # Set sudo args based on available options
        if self.availoptions.get("l [command]") and args:
            sudo_args += args
        try:
            p = self.subprocess = wexpect.spawn(safe_str(self.sudo), sudo_args)
        except Exception as exception:
            return StringWithLengthOverride(
                "Could not run %s %s: %s" % (self.sudo, " ".join(sudo_args), exception),
                0,
            )
        self._expect_timeout(["Password:", wexpect.EOF], 10)
        # We need to call isalive() to set the exitstatus
        while p.isalive() and p.after == "Password:":
            p.send(pwd + os.linesep)
            self._expect_timeout(["Password:", wexpect.EOF], 10)
            if p.after == "Password:":
                # Password was not accepted
                self._terminate()
                return StringWithLengthOverride(p.before.strip(), 0)
        if p.after is wexpect.TIMEOUT:
            print("Error: sudo timed out")
            if not p.terminate(force=True):
                print("Warning: Couldn't terminate timed-out sudo " "subprocess")
            return StringWithLengthOverride("sudo timed out", 0)
        if p.exitstatus != 0:
            return StringWithLengthOverride(
                p.before.strip()
                or ("sudo exited prematurely with " "status %s" % p.exitstatus),
                0,
            )
        return p.before.strip()

    def kill(self):
        """Remove cached credentials"""
        kill_arg = None
        if self.availoptions.get("K"):
            kill_arg = "-K"
        elif self.availoptions.get("k"):
            kill_arg = "-k"
        if kill_arg:
            sp.call([safe_str(self.sudo), kill_arg])


class WPopen(sp.Popen):
    def __init__(self, *args, **kwargs):
        sp.Popen.__init__(self, *args, **kwargs)
        self._seekpos = 0
        self._stdout = kwargs["stdout"]
        self.after = None
        self.before = None
        self.exitstatus = None
        self.logfile_read = None
        self.match = None
        self.maxlen = 80
        self.timeout = 30

    def isalive(self):
        self.exitstatus = self.poll()
        return self.exitstatus is None

    def expect(self, patterns, timeout=-1):
        if not isinstance(patterns, list):
            patterns = [patterns]
        if timeout == -1:
            timeout = self.timeout
        if timeout is not None:
            end = time() + timeout
        while timeout is None or time() < end:
            self._stdout.seek(self._seekpos)
            buf = self._stdout.read()
            self._seekpos += len(buf)
            if not buf and not self.isalive():
                self.match = wexpect.EOF(
                    "End Of File (EOF) in expect() - dead child process"
                )
                if wexpect.EOF in patterns:
                    return self.match
                raise self.match
            if buf and self.logfile_read:
                self.logfile_read.write(buf)
            for pattern in patterns:
                if isinstance(pattern, str) and pattern in buf:
                    offset = buf.find(pattern)
                    self.after = buf[offset:]
                    self.before = buf[:offset]
                    self.match = buf[offset : offset + len(pattern)]
                    return self.match
            sleep(0.01)
        if timeout is not None:
            self.match = wexpect.TIMEOUT("Timeout exceeded in expect()")
            if wexpect.TIMEOUT in patterns:
                return self.match
            raise self.match

    def send(self, s):
        self.stdin.write(s)
        self._stdout.seek(self._seekpos)
        buf = self._stdout.read()
        self._seekpos += len(buf)
        if buf and self.logfile_read:
            self.logfile_read.write(buf)

    def terminate(self, force=False):
        sp.Popen.terminate(self)


class Worker(WorkerBase):
    def __init__(self, owner=None):
        """Create and return a new worker instance."""
        WorkerBase.__init__(self)
        self.argyll_bin_dir = None
        self.argyll_version = [0, 0, 0]
        self.argyll_version_string = "0.0.0"
        self._displays = []
        self.display_edid = []
        self.display_manufacturers = []
        self.display_names = []
        self.display_rects = []
        self.displays = []
        self.instruments = []
        self.lut_access = []
        self.paused = False
        self._patterngenerator_wait = False

        self.send_buffer = None
        self.partial_data = ""
        self.owner = owner  # owner should be a wxFrame or similar
        if sys.platform == "win32":
            self.pty_encoding = "cp%i" % windll.kernel32.GetACP()
        else:
            self.pty_encoding = enc
        self.cmdrun = False
        self.dispcal_create_fast_matrix_shaper = False
        self.dispread_after_dispcal = False
        self.finished = True
        self.instrument_on_screen = False
        self.interactive = False
        self.spotread_just_do_instrument_calibration = False
        self.lastcmdname = None
        # Filter out warnings from OS components (e.g. shared libraries)
        # E.g.:
        # Nov 26 16:28:16  dispcal[1006] <Warning>: void CGSUpdateManager::log() const: conn 0x1ec57 token 0x3ffffffffffd0a
        prestrip = re.compile(
            r"\D+\s+\d+\s+\d+:\d+:\d+\s+\w+\[\d+]\s+<Warning>:[\S\s]*"
        )
        discard = [r"[\*\.]+|Current (?:RGB|XYZ)(?: +.*)?"]
        self.lastmsg_discard = re.compile(r"|".join(discard))
        self._init_sounds(dummy=True)
        self.options_colprof = []
        self.options_dispcal = []
        self.options_dispread = []
        self.options_targen = []
        self.pauseable = False
        discard = [
            r"^Display type is .+",
            r"^Doing (?:some initial|check) measurements",
            r"^Adjust .+? Press space when done\.\s*",
            r"^\s*(?:[/\\]\s+)?(?:Adjusted )?(Current",
            r"Initial",
            r"[Tt]arget) (?:Br(?:ightness)?",
            r"50% Level",
            r"white",
            r"(?:Near )?[Bb]lack",
            r"(?:advertised )?gamma",
            r"RGB",
            r"\d(?:\.\d+)?).*",
            r"^Gamma curve .+",
            r"^Display adjustment menu:",
            r"^Press",
            r"^\d\).+",
            r"^(?:1%|Black|Red|Green|Blue|White|Grey)\s+=.+",
            r"^\s*patch \d+ of \d+.*",
            r"^\s*point \d+.*",
            r"^\s*Added \d+/\d+",
            # These need to be last because they're very generic!
            r"[\*\.]+",
            r"\s*\d*%?",
        ]
        self.recent_discard = re.compile(r"|".join(discard), re.I)
        self.resume = False
        self.sudo = None
        self.auth_timestamp = 0
        self.sessionlogfiles = {}
        self.triggers = ["Password:"]
        self.recent = FilteredStream(
            LineCache(maxlines=3),
            self.pty_encoding,
            discard=self.recent_discard,
            triggers=self.triggers + ["stopped at user request"],
            prestrip=prestrip,
        )
        self.lastmsg = FilteredStream(
            LineCache(),
            self.pty_encoding,
            discard=self.lastmsg_discard,
            triggers=self.triggers,
            prestrip=prestrip,
        )
        self.clear_argyll_info()
        self.set_argyll_version_from_string(getcfg("argyll.version"), False)
        self.clear_cmd_output()
        self._detecting_video_levels = False
        self._detected_output_levels = False
        self._patterngenerators = {}
        self._progress_dlgs = {}
        self._progress_wnd = None
        self._pwdstr = ""
        workers.append(self)

    def _init_sounds(self, dummy=False):
        if dummy:
            self.measurement_sound = audio.DummySound()
            self.commit_sound = audio.DummySound()
        else:
            # Sounds when measuring
            # Needs to be stereo!
            self.measurement_sound = audio.Sound(get_data_path("beep.wav"))
            self.commit_sound = audio.Sound(get_data_path("camera_shutter.wav"))

    def add_measurement_features(
        self,
        args,
        display=True,
        ignore_display_name=False,
        allow_nondefault_observer=False,
        ambient=False,
        allow_video_levels=True,
        quantize=False,
        cmd=None,
    ):
        """Add common options and to dispcal, dispread and spotread arguments"""
        if display and not get_arg("-d", args):
            args.append("-d" + self.get_display())
        if display and allow_video_levels:
            self.add_video_levels_arg(args)
        if (
            display
            and quantize
            and not get_arg("-Z", args)
            and getcfg("patterngenerator.quantize_bits")
        ):
            # dispread only
            args.append("-Z%i" % getcfg("patterngenerator.quantize_bits"))
        if not get_arg("-c", args):
            args.append("-c%s" % getcfg("comport.number"))
        instrument_name = self.get_instrument_name()
        measurement_mode = getcfg("measurement_mode")
        if measurement_mode == "auto":
            # Make changes in DisplayCAL.MainFrame.set_ccxx_measurement_mode too!
            if instrument_name == "ColorHug":
                measurement_mode = "R"
            elif instrument_name == "ColorHug2":
                measurement_mode = "F"
            else:
                measurement_mode = "l"
        instrument_features = self.get_instrument_features()
        if (
            not ambient
            and measurement_mode
            and not get_arg("-y", args)
            and instrument_name != "specbos 1201"
        ):
            # Always specify -y for colorimeters (won't be read from cal
            # when updating)
            # The specbos 1201 (unlike 1211) doesn't support measurement
            # mode selection
            if self.argyll_version >= [1, 5, 0]:
                measurement_mode_map = instrument_features.get(
                    "measurement_mode_map", {}
                )
                measurement_mode = measurement_mode_map.get(
                    measurement_mode[0], measurement_mode
                )
            args.append("-y" + measurement_mode[0])
        if (
            getcfg("measurement_mode.projector")
            and instrument_features.get("projector_mode")
            and self.argyll_version >= [1, 1, 0]
            and not get_arg("-p", args)
        ):
            # Projector mode, Argyll >= 1.1.0 Beta
            args.append("-p")
        if instrument_features.get("adaptive_mode"):
            if getcfg("measurement_mode.adaptive"):
                if (
                    (
                        self.argyll_version[0:3] > [1, 1, 0]
                        or (
                            self.argyll_version[0:3] == [1, 1, 0]
                            and "Beta" not in self.argyll_version_string
                            and "RC1" not in self.argyll_version_string
                            and "RC2" not in self.argyll_version_string
                        )
                    )
                    and self.argyll_version[0:3] < [1, 5, 0]
                    and not get_arg("-V", args, True)
                ):
                    # Adaptive measurement mode, Argyll >= 1.1.0 RC3
                    args.append("-V")
            else:
                if self.argyll_version[0:3] >= [1, 5, 0]:
                    # Disable adaptive measurement mode
                    args.append("-YA")
        if (
            instrument_name in ("Spyder4", "Spyder5")
            and self.argyll_version == [1, 7, 0]
            and measurement_mode in ("f", "e")
            and not get_arg("-YR:", args)
        ):
            # Prevent 'Warning - Spyder: measuring refresh rate failed'
            args.append("-YR:60")
        non_argyll_prisma = (
            config.get_display_name() == "Prisma"
            and not defaults["patterngenerator.prisma.argyll"]
        )
        if display and not (get_arg("-dweb", args) or get_arg("-dmadvr", args)):
            if (
                (self.argyll_version <= [1, 0, 4] and not get_arg("-p", args))
                or (self.argyll_version > [1, 0, 4] and not get_arg("-P", args))
                and f"-d{self.argyll_virtual_display}" not in args
            ):
                if (
                    config.get_display_name() == "Resolve" or non_argyll_prisma
                ) and not ignore_display_name:
                    # Move Argyll test window to lower right corner and make it
                    # very small
                    dimensions_measureframe = "1,1,0.01"
                else:
                    if os.getenv("XDG_SESSION_TYPE") == "wayland":
                        # The following is a workaround for Wayland not exposing the
                        # absolute screen positions of a window.
                        dimensions_measureframe = "0.5,0.5,1.5"
                    else:
                        dimensions_measureframe = getcfg("dimensions.measureframe")
                    if get_arg("-dcc", args):
                        # Rescale for Chromecast default patch size of 10%
                        dimensions_measureframe = config.get_measureframe_dimensions(
                            dimensions_measureframe, 10
                        )
                args.append(f"-P{dimensions_measureframe}")
            farg = get_arg("-F", args, True)
            if (
                config.get_display_name() == "Resolve" or non_argyll_prisma
            ) and not ignore_display_name:
                if farg:
                    # Remove -F (darken background) as we relay colors to
                    # pattern generator
                    args = args[: farg[0]] + args[farg[0] + 1 :]
            elif getcfg("measure.darken_background") and not farg:
                args.append("-F")
        if (
            getcfg("measurement_mode.highres")
            and instrument_features.get("highres_mode")
            and not get_arg("-H", args, True)
        ):
            args.append("-H")
        if (
            allow_nondefault_observer
            and self.instrument_can_use_nondefault_observer()
            and getcfg("observer") != defaults["observer"]
            and not get_arg("-Q", args)
        ):
            args.append("-Q" + getcfg("observer"))
        if (
            not ambient
            and self.instrument_can_use_ccxx()
            and not is_ccxx_testchart()
            and not get_arg("-X", args)
        ):
            # Use colorimeter correction?
            ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
            if len(ccmx) > 1 and ccmx[1]:
                ccmx = ccmx[1]
            else:
                ccmx = None
            if ccmx and (
                not ccmx.lower().endswith(".ccss") or self.instrument_supports_ccss()
            ):
                result = check_file_isfile(ccmx)
                if isinstance(result, Exception):
                    return result
                try:
                    cgats = CGATS.CGATS(ccmx)
                except (IOError, CGATS.CGATSError) as exception:
                    return exception
                else:
                    ccxx_instrument_from_cgats = cgats.queryv1("INSTRUMENT") or b""
                    ccxx_instrument = get_canonical_instrument_name(
                        ccxx_instrument_from_cgats,
                        {
                            "DTP94-LCD mode": "DTP94",
                            "eye-one display": "i1 Display",
                            "Spyder 2 LCD": "Spyder2",
                            "Spyder 3": "Spyder3",
                        },
                    )
                    if isinstance(ccxx_instrument, bytes):
                        ccxx_instrument = ccxx_instrument.decode("utf-8")
                if (
                    ccxx_instrument
                    and instrument_name.lower().replace(" ", "")
                    in ccxx_instrument.lower().replace(" ", "")
                ) or ccmx.lower().endswith(".ccss"):
                    tempdir = self.create_tempdir()
                    if isinstance(tempdir, Exception):
                        return tempdir
                    ccmxcopy = os.path.join(tempdir, os.path.basename(ccmx))
                    if not os.path.isfile(ccmxcopy):
                        if 0 in cgats and cgats[0].type.strip() == b"CCMX":
                            # Add display base ID if missing
                            cbid_added = self.check_add_display_type_base_id(cgats)
                        else:
                            cbid_added = False
                        try:
                            # Copy ccmx to profile dir
                            if cbid_added:
                                # Write updated CCMX
                                cgats.write(ccmxcopy)
                            else:
                                # Copy original
                                shutil.copyfile(ccmx, ccmxcopy)
                        except Exception as exception:
                            return Error(
                                lang.getstr("error.copy_failed", (ccmx, ccmxcopy))
                                + "\n\n"
                                + str(exception)
                            )
                        result = check_file_isfile(ccmxcopy)
                        if isinstance(result, Exception):
                            return result
                    args.append("-X")
                    args.append(os.path.basename(ccmxcopy))
        if (
            display
            and (
                getcfg("drift_compensation.blacklevel")
                or getcfg("drift_compensation.whitelevel")
            )
            and self.argyll_version >= [1, 3, 0]
            and not get_arg("-I", args)
        ):
            args.append("-I")
            if getcfg("drift_compensation.blacklevel"):
                args[-1] += "b"
            if getcfg("drift_compensation.whitelevel"):
                args[-1] += "w"
        # TTBD/FIXME: Skipping of sensor calibration can't be done in
        # emissive mode (see Argyll source spectro/ss.c, around line 40)
        # (is this still the case though?)
        # Note we implicitly skip sensor calibration if already done during
        # output levels detection or if using spotread, but only for colorimeters
        if (
            (
                getcfg("allow_skip_sensor_cal")
                or (
                    not instrument_features.get("spectral")
                    and (
                        self._detected_output_levels
                        or (self.dispread_after_dispcal and self.resume)
                        or cmd == get_argyll_util("spotread")
                    )
                    and not self._detecting_video_levels
                )
            )
            and instrument_features.get("skip_sensor_cal")
            and self.argyll_version >= [1, 1, 0]
            and not get_arg("-N", args, True)
            and not self.spotread_just_do_instrument_calibration
        ):
            args.append("-N")
        return True

    def add_video_levels_arg(self, args):
        if (
            config.get_display_name() not in ("madVR", "Resolve", "Prisma")
            and getcfg("patterngenerator.use_video_levels")
            and self.argyll_version >= [1, 6]
            and self.get_display() != self.argyll_virtual_display
        ):
            # For madVR and dummy display, -E is invalid
            args.append("-E")

    def authenticate(self, cmd, title=appname, parent=None):
        """Athenticate (using sudo) for a given command

        The return value will either be True (authentication successful and
        command allowed), False (in case of the user cancelling the password
        dialog), None (Windows or running as root) or an error.

        """
        if sys.platform == "win32" or os.geteuid() == 0:
            return
        self.auth_timestamp = 0
        ocmd = cmd
        if cmd and not os.path.isabs(cmd):
            cmd = get_argyll_util(ocmd)
            if not cmd:
                cmd = which(ocmd)
        if not cmd or not os.path.isfile(cmd):
            return Error(lang.getstr("file.missing", ocmd))
        _disabler = BetterWindowDisabler()
        result = True
        if not self.sudo:
            self.sudo = Sudo()
            if not self.sudo:
                result = Error(lang.getstr("file.missing", "sudo"))
        if result is True:
            pwd = self.pwd
            args = [cmd, "-?"]
            if not pwd or not self.sudo.is_allowed(args, pwd):
                # If no password was previously available, or if the requested
                # command cannot be run via sudo regardless of password (we check
                # this with sudo -l <command>), we ask for a password.
                print(lang.getstr("auth"))
                progress_dlg = self._progress_wnd or getattr(
                    wx.GetApp(), "progress_dlg", None
                )
                if parent is None:
                    if progress_dlg and progress_dlg.IsShownOnScreen():
                        parent = progress_dlg
                    else:
                        parent = self.owner
                result, pwd = self.sudo.authenticate(args, title, parent)
                if result:
                    self.pwd = pwd
                    result = True
                elif result is False:
                    print(lang.getstr("aborted"))
                else:
                    result = Error(result)
            if result is True:
                self.auth_timestamp = time()
        del _disabler
        return result

    def blend_profile_blackpoint(
        self,
        profile1,
        profile2,
        XYZbp=None,
        outoffset=0.0,
        gamma=2.4,
        gamma_type="B",
        size=None,
        apply_trc=True,
        white_cdm2=100,
        minmll=0,
        maxmll=10000,
        use_alternate_master_white_clip=True,
        ambient_cdm2=5,
        content_rgb_space="DCI P3",
        hdr_chroma_compression=False,
        hdr_sat=0.5,
        hdr_hue=0.5,
        hdr_target_profile=None,
    ):
        """Apply BT.1886-like tone response to profile1 using profile2 blackpoint.

        profile1 has to be a matrix profile

        """
        odata = self.xicclu(profile2, (0, 0, 0), pcs="x")
        if len(odata) != 1 or len(odata[0]) != 3:
            raise ValueError("Blackpoint is invalid: %s" % odata)
        oXYZbp = odata[0]
        if not XYZbp:
            XYZbp = oXYZbp
        smpte2084 = gamma in ("smpte2084.hardclip", "smpte2084.rolloffclip")
        hlg = gamma == "hlg"
        hdr = smpte2084 or hlg
        lumi = profile2.tags.get("lumi", ICCP.XYZType())
        if not lumi.Y:
            lumi.Y = 100.0
        profile_black_cdm2 = XYZbp[1] * lumi.Y
        if smpte2084:
            # SMPTE ST.2084 (PQ)
            if gamma != "smpte2084.rolloffclip":
                maxmll = white_cdm2
            self.log(
                os.path.basename(profile1.fileName)
                + " → "
                + lang.getstr("trc." + gamma)
                + (
                    " %i cd/m² (mastering %s-%i cd/m²)"
                    % (white_cdm2, stripzeros("%.4f" % minmll), maxmll)
                )
            )
        elif hlg:
            # Hybrid Log-Gamma (HLG)
            outoffset = 1.0
            self.log(
                os.path.basename(profile1.fileName)
                + " → "
                + lang.getstr("trc." + gamma)
                + (
                    " %i cd/m² (ambient %s cd/m²)"
                    % (lumi.Y, stripzeros("%.2f" % ambient_cdm2))
                )
            )
        elif apply_trc:
            self.log(
                "Applying BT.1886-like TRC to " + os.path.basename(profile1.fileName)
            )
        else:
            self.log(
                "Applying BT.1886-like black offset to "
                + os.path.basename(profile1.fileName)
            )
        self.log(
            "Black XYZ (normalized 0..100) = %.6f %.6f %.6f"
            % tuple([v * 100 for v in XYZbp])
        )
        self.log(
            "Black Lab = %.6f %.6f %.6f"
            % tuple(colormath.XYZ2Lab(*[v * 100 for v in XYZbp]))
        )
        self.log("Output offset = %.2f%%" % (outoffset * 100))
        if hdr:
            odesc = profile1.getDescription()
            desc = re.sub(
                r"\s*(?:color profile|primaries with \S+ transfer function)$", "", odesc
            )
            if smpte2084:
                # SMPTE ST.2084 (PQ)
                black_cdm2 = profile_black_cdm2 * (1 - outoffset)
                if XYZbp[1]:
                    XYZbp_cdm2 = [v / XYZbp[1] * black_cdm2 for v in XYZbp]
                else:
                    XYZbp_cdm2 = [0, 0, 0]
                profile1.set_smpte2084_trc(
                    XYZbp_cdm2,
                    white_cdm2,
                    minmll,
                    maxmll,
                    use_alternate_master_white_clip,
                    rolloff=True,
                    blend_blackpoint=False,
                )
                desc += (
                    " "
                    + lang.getstr("trc." + gamma)
                    + (
                        " %s-%i cd/m² (mastering %s-%i cd/m²)"
                        % (
                            stripzeros("%.4f" % profile_black_cdm2),
                            white_cdm2,
                            stripzeros("%.4f" % minmll),
                            maxmll,
                        )
                    )
                )
            elif hlg:
                # Hybrid Log-Gamma (HLG)
                black_cdm2 = 0  # Black offset will be applied separate for HLG
                white_cdm2 = lumi.Y
                profile1.set_hlg_trc((0, 0, 0), white_cdm2, 1.2, ambient_cdm2)
                desc += (
                    " "
                    + lang.getstr("trc." + gamma)
                    + (
                        " %s-%i cd/m² (ambient %s cd/m²)"
                        % (
                            stripzeros("%.4f" % profile_black_cdm2),
                            white_cdm2,
                            stripzeros("%.2f" % ambient_cdm2),
                        )
                    )
                )
            profile1.setDescription(desc)
            if gamma == "smpte2084.rolloffclip" or hlg:
                rgb_space = profile1.get_rgb_space()
                if not rgb_space:
                    raise Error(
                        odesc
                        + ": "
                        + lang.getstr(
                            "profile.unsupported",
                            (lang.getstr("unknown"), profile1.colorSpace),
                        )
                    )
                rgb_space[0] = 1.0  # Set gamma to 1.0 (not actually used)
                rgb_space = colormath.get_rgb_space(rgb_space)
                self.recent.write(desc + "\n")
                linebuffered_logfiles = []
                if sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
                    linebuffered_logfiles.append(print)
                else:
                    linebuffered_logfiles.append(log)
                if self.sessionlogfile:
                    linebuffered_logfiles.append(self.sessionlogfile)
                logfiles = Files(
                    [
                        LineBufferedStream(
                            FilteredStream(
                                Files(linebuffered_logfiles),
                                enc,
                                discard="",
                                linesep_in="\n",
                                triggers=[],
                            )
                        ),
                        self.recent,
                        self.lastmsg,
                    ]
                )
                if hdr_chroma_compression:
                    xf = Xicclu(
                        hdr_target_profile, "r", direction="f", pcs="x", worker=self
                    )
                    xb = MP_Xicclu(
                        hdr_target_profile,
                        "r",
                        direction="if",
                        pcs="x",
                        use_cam_clipping=True,
                        worker=self,
                        logfile=logfiles,
                    )
                    if content_rgb_space:
                        content_rgb_space = colormath.get_rgb_space(content_rgb_space)
                        for i, color in enumerate(("white", "red", "green", "blue")):
                            if i == 0:
                                xyY = colormath.XYZ2xyY(*content_rgb_space[1])
                            else:
                                xyY = content_rgb_space[2:][i - 1]
                            for j, coord in enumerate("xy"):
                                v = xyY[j]
                                self.log(
                                    lang.getstr("3dlut.content.colorspace")
                                    + " "
                                    + lang.getstr(color)
                                    + " "
                                    + coord
                                    + " %6.4f" % v
                                )
                else:
                    xf = None
                    xb = None
                if smpte2084:
                    hdr_format = "PQ"
                elif hlg:
                    hdr_format = "HLG"
                cat = profile1.guess_cat() or "Bradford"
                self.log("Using chromatic adaptation transform matrix:", cat)
                profile = ICCP.create_synthetic_hdr_clut_profile(
                    hdr_format,
                    rgb_space,
                    desc,
                    black_cdm2,
                    white_cdm2,
                    minmll,  # Not used for HLG
                    maxmll,  # Not used for HLG
                    use_alternate_master_white_clip,  # Not used for HLG
                    system_gamma=1.2,  # Not used for PQ
                    ambient_cdm2=ambient_cdm2,  # Not used for PQ
                    maxsignal=1.0,  # Not used for PQ
                    content_rgb_space=content_rgb_space,
                    sat=hdr_sat,
                    hue=hdr_hue,
                    forward_xicclu=xf,
                    backward_xicclu=xb,
                    worker=self,
                    logfile=logfiles,
                    cat=cat,
                )
                profile1.tags.A2B0 = profile.tags.A2B0
                profile1.tags.DBG0 = profile.tags.DBG0
                profile1.tags.DBG1 = profile.tags.DBG1
                profile1.tags.DBG2 = profile.tags.DBG2
                profile1.tags.kTRC = profile.tags.kTRC
        elif apply_trc:
            # Apply BT.1886-like TRC
            if gamma_type in ("b", "g"):
                # Get technical gamma needed to achieve effective gamma
                self.log("Effective gamma = %.2f" % gamma)
                tgamma = colormath.xicc_tech_gamma(gamma, XYZbp[1], outoffset)
            else:
                tgamma = gamma
            self.log("Technical gamma = %.2f" % tgamma)
            profile1.set_bt1886_trc(XYZbp, outoffset, gamma, gamma_type, size)
        if not apply_trc or hdr or XYZbp is not oXYZbp:
            # Apply black offset
            logfiles = self.get_logfiles()
            logfiles.write(
                "Applying black offset (normalized 0..100) "
                "%.6f %.6f %.6f...\n" % tuple([v * 100 for v in oXYZbp])
            )
            profile1.apply_black_offset(
                oXYZbp,
                logfiles=logfiles,
                thread_abort=self.thread_abort,
                abortmessage=lang.getstr("aborted"),
            )

    def calibrate_instrument_producer(self):
        cmd, args = get_argyll_util("spotread"), ["-v", "-e"]
        if cmd:
            self.spotread_just_do_instrument_calibration = True
            result = self.add_measurement_features(args, display=False)
            if isinstance(result, Exception):
                self.spotread_just_do_instrument_calibration = False
                return result
            result = self.exec_cmd(cmd, args, skip_scripts=True)
            self.spotread_just_do_instrument_calibration = False
            return result
        else:
            return Error(lang.getstr("argyll.util.not_found", "spotread"))

    def instrument_can_use_ccxx(
        self, check_measurement_mode=True, instrument_name=None
    ):
        """Return boolean whether the instrument in its current measurement mode
        can use a CCMX or CCSS colorimeter correction

        """
        # Special cases:
        # Spectrometer (not needed),
        # ColorHug (only sensible in factory or raw measurement mode),
        # ColorMunki Smile (only generic LCD CCFL measurement mode),
        # Colorimétre HCFR (only raw measurement mode),
        # DTP94 (only LCD, refresh and generic measurement modes)
        # Spyder4/5 (only generic LCD and refresh measurement modes)
        # K-10 (only factory measurement mode)

        # IMPORTANT: Make changes aswell in the following locations:
        # - DisplayCAL.MainFrame.create_colorimeter_correction_handler
        # - DisplayCAL.MainFrame.get_ccxx_measurement_modes
        # - DisplayCAL.MainFrame.set_ccxx_measurement_mode
        # - DisplayCAL.MainFrame.update_colorimeter_correction_matrix_ctrl_items
        # - worker.Worker.check_add_display_type_base_id
        if not instrument_name:
            instrument_name = self.get_instrument_name()
        return (
            self.argyll_version >= [1, 3, 0]
            and bool(instrument_name)
            and not self.get_instrument_features(instrument_name).get("spectral")
            and (
                not check_measurement_mode
                or getcfg("measurement_mode") == "auto"
                or (
                    (
                        instrument_name not in ("ColorHug", "ColorHug2")
                        or getcfg("measurement_mode") in ("F", "R")
                    )
                    and (
                        instrument_name != "ColorMunki Smile"
                        or getcfg("measurement_mode") == "f"
                    )
                    and (
                        instrument_name != "Colorimtre HCFR"
                        or getcfg("measurement_mode") == "R"  # Missing é is NOT a typo
                    )
                    and (
                        instrument_name != "DTP94"
                        or getcfg("measurement_mode") in ("l", "c", "g")
                    )
                    and (
                        instrument_name not in ("Spyder4", "Spyder5")
                        or getcfg("measurement_mode") in ("l", "c")
                    )
                    and (
                        instrument_name != "SpyderX"
                        or getcfg("measurement_mode") == "l"
                    )
                    and (instrument_name != "K-10" or getcfg("measurement_mode") == "F")
                )
            )
        )

    def instrument_can_use_nondefault_observer(self, instrument_name=None):
        if not instrument_name:
            instrument_name = self.get_instrument_name()
        return bool(
            self.get_instrument_features(instrument_name).get("spectral")
            or self.instrument_supports_ccss(instrument_name)
        )

    @property
    def progress_wnd(self):
        if not self._progress_wnd:
            if (
                getattr(self, "progress_start_timer", None)
                and self.progress_start_timer.IsRunning()
            ):
                if currentThread().__class__.__name__ != "_MainThread":
                    raise RuntimeError("GUI access in non-main thread!")
                # Instantiate the progress dialog instantly on access
                self.progress_start_timer.Notify()
                self.progress_start_timer.Stop()
        return self._progress_wnd

    @progress_wnd.setter
    def progress_wnd(self, progress_wnd):
        self._progress_wnd = progress_wnd

    @property
    def progress_wnds(self):
        progress_wnds = list(self._progress_dlgs.values())
        if hasattr(self, "terminal"):
            progress_wnds.append(self.terminal)
        return progress_wnds

    @property
    def pwd(self):
        return codecs.decode(
            self._pwdstr[10:]
            .ljust(int(math.ceil(len(self._pwdstr[10:]) / 4.0) * 4), "=")
            .encode(),
            "base64",
        ).decode("utf-8")

    @pwd.setter
    def pwd(self, pwd):
        encoded_user_name = codecs.encode(
            md5(getpass.getuser().encode()).hexdigest().encode(), "base64"
        )[:5].decode("utf-8")
        encoded_pwd = (
            codecs.encode(pwd.encode(), "base64").decode("utf-8").rstrip("=\n")
        )
        self._pwdstr = "/tmp/%s%s" % (encoded_user_name, encoded_pwd)

    def get_argyll_instrument_conf(self, what=None):
        """Check for Argyll CMS udev rules/hotplug scripts"""
        filenames = []
        if what == "installed":
            for filename in (
                "/etc/udev/rules.d/55-Argyll.rules",
                "/etc/udev/rules.d/45-Argyll.rules",
                "/etc/hotplug/Argyll",
                "/etc/hotplug/Argyll.usermap",
                "/lib/udev/rules.d/55-Argyll.rules",
                "/lib/udev/rules.d/69-cd-sensors.rules",
            ):
                if os.path.isfile(filename):
                    filenames.append(filename)
        else:
            if what == "expected":
                fn = lambda filename: filename
            else:
                fn = get_data_path
            if os.path.isdir("/etc/udev/rules.d"):
                if safe_glob("/dev/bus/usb/*/*"):
                    # USB and serial instruments using udev, where udev
                    # already creates /dev/bus/usb/00X/00X devices
                    filenames.append(fn("usb/55-Argyll.rules"))
                else:
                    # USB using udev, where there are NOT /dev/bus/usb/00X/00X
                    # devices
                    filenames.append(fn("usb/45-Argyll.rules"))
            else:
                if os.path.isdir("/etc/hotplug"):
                    # USB using hotplug and Serial using udev
                    # (older versions of Linux)
                    filenames.extend(
                        fn(filename)
                        for filename in ("usb/Argyll", "usb/Argyll.usermap")
                    )
        return [filename for filename in filenames if filename]

    def check_add_display_type_base_id(self, cgats, cfgname="measurement_mode"):
        """Add DISPLAY_TYPE_BASE_ID to CCMX"""
        if not cgats.queryv1("DISPLAY_TYPE_BASE_ID"):
            # c, l (most colorimeters)
            # R (ColorHug and Colorimétre HCFR)
            # F (ColorHug)
            # f (ColorMunki Smile)
            # g (DTP94)

            # IMPORTANT: Make changes aswell in the following locations:
            # - DisplayCAL.MainFrame.create_colorimeter_correction_handler
            # - DisplayCAL.MainFrame.get_ccxx_measurement_modes
            # - DisplayCAL.MainFrame.set_ccxx_measurement_modes
            # - DisplayCAL.MainFrame.update_colorimeter_correction_matrix_ctrl_items
            # - worker.Worker.instrument_can_use_ccxx
            cgats[0].add_keyword(
                "DISPLAY_TYPE_BASE_ID",
                {"c": 2, "l": 1, "R": 2, "F": 1, "f": 1, "g": 3}.get(
                    getcfg(cfgname), 1
                ),
            )
            print("Added DISPLAY_TYPE_BASE_ID %r" % cgats[0].DISPLAY_TYPE_BASE_ID)
            return True

    def check_display_conf_oy_compat(self, display_no):
        """Check the screen configuration for oyranos-monitor compatibility

        oyranos-monitor works off screen coordinates, so it will not handle
        overlapping screens (like separate X screens, which will usually
        have the same x, y coordinates)!
        So, oyranos-monitor can only be used if:
        - The wx.Display count is > 1 which means NOT separate X screens
          OR if we use the 1st screen
        - The screens don't overlap

        """
        oyranos = False
        if wx.Display.GetCount() > 1 or display_no == 1:
            oyranos = True
            for display_rect_1 in self.display_rects:
                for display_rect_2 in self.display_rects:
                    if display_rect_1 is not display_rect_2:
                        if display_rect_1.Intersects(display_rect_2):
                            oyranos = False
                            break
                if not oyranos:
                    break
        return oyranos

    def check_is_single_measurement(self, txt):
        if (
            "ambient light measuring" in txt.lower()
            or "Will use emissive mode instead" in txt
        ) and not getattr(self, "is_ambient_measurement", False):
            self.is_ambient_measurement = True
            self.is_single_measurement = True
        if (
            getattr(self, "is_single_measurement", False)
            and self.instrument_place_on_spot_msg
        ):
            self.is_single_measurement = False
            self.do_single_measurement()
            self.is_ambient_measurement = False

    def do_single_measurement(self):
        if getattr(self, "subprocess_abort", False) or getattr(
            self, "thread_abort", False
        ):
            # If we are aborting, ignore request
            return
        self.progress_wnd.Pulse(" " * 4)
        if self.is_ambient_measurement:
            self.is_ambient_measurement = False
            dlg = ConfirmDialog(
                self.progress_wnd,
                msg=lang.getstr("instrument.measure_ambient"),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                bitmap=geticon(32, "dialog-information"),
            )
            self.progress_wnd.dlg = dlg
            dlg_result = dlg.ShowModal()
            dlg.Destroy()
            if self.finished:
                return
            if dlg_result != wx.ID_OK:
                self.abort_subprocess()
                return False
        if self.safe_send(" "):
            self.progress_wnd.Pulse(lang.getstr("please_wait"))

    def check_instrument_calibration(self, txt):
        """Check if current instrument needs sensor calibration by looking
        at Argyll CMS command output"""
        if not self.instrument_calibration_complete:
            if "calibration complete" in txt.lower():
                self.log(
                    "%s: Detected instrument calibration complete message" % appname
                )
                self.instrument_calibration_complete = True
            else:
                for calmsg in INST_CAL_MSGS:
                    if calmsg in txt or "calibration failed" in txt.lower():
                        self.log(
                            "%s: Detected instrument calibration message" % appname
                        )
                        self.do_instrument_calibration(
                            "calibration failed" in txt.lower()
                        )
                        break

    def check_instrument_calibration_file(self):
        # XXX: Check instrument calibration for SpyderX. For some reason,
        # users tend to leave the instrument on screen despite being told
        # otherwise...
        if self._detected_instrument and "SpyderX" in self._detected_instrument:
            if sys.platform == "win32":
                cachepath = os.path.join(appdata, "Cache")
            else:
                cachepath = cache
            spydx_cal_fn = os.path.join(
                cachepath,
                "ArgyllCMS",
                ".spydX_%s.cal" % self._detected_instrument_serial,
            )
            if os.path.isfile(spydx_cal_fn):
                # Argyll sensor cal file format offsets and lengths depend on
                # the size of various C data types as seen by Argyll.
                # We can determine the needed offset and length of the cal info
                # (C 'int') by subtracting the length of the NULL-terminated
                # serial string and size of time_t from the file size, then
                # dividing by the number of C 'int's in the file.
                # File structure for SpyderX cal:
                # Argyll version (C 'int')
                # Size of spydX (2x C 'int')
                # NULL-terminated serial string (variable length)
                # Black cal done (C 'int')
                # Date & time (time_t)
                # Calibration info (3x C 'int')
                # Checksum (C 'int')
                serial0 = self._detected_instrument_serial + "\0"
                numints = 8
                spydx_cal_size = os.stat(spydx_cal_fn).st_size
                spydx_cal_int_bytes = 4  # C 'int'
                # time_t might be 8 or 4 bytes, 0 is sentinel
                for time_t_size in (8, 4, 0):
                    if (
                        spydx_cal_size - len(serial0) - time_t_size
                    ) == spydx_cal_int_bytes * numints:
                        break
                if not time_t_size:
                    self.log(
                        appname + ": Warning - could not determine SpyderX "
                        "sensor cal file format"
                    )
                    self.exec_cmd_returnvalue = Error(
                        "Could not determine " "SpyderX sensor cal file " "format"
                    )
                    self.abort_subprocess()
                    return False
                self.log(appname + ": SpyderX cal time_t size =", time_t_size)
                try:
                    with open(spydx_cal_fn, "rb") as spydx_cal:
                        # Seek to cal entries offset
                        spydx_cal.seek(
                            spydx_cal_int_bytes * 4 + len(serial0) + time_t_size
                        )
                        # Read three entries black cal
                        spydx_bcal = spydx_cal.read(spydx_cal_int_bytes * 3)
                except EnvironmentError as exception:
                    self.log(
                        appname + ": Warning - could not read SpyderX " "sensor cal:",
                        exception,
                    )
                    self.exec_cmd_returnvalue = Error(
                        "Could not read " "SpyderX sensor cal: %s" % safe_str(exception)
                    )
                    self.abort_subprocess()
                    return False
                else:
                    if len(spydx_bcal) < spydx_cal_int_bytes * 3:
                        self.log(
                            appname + ": Warning - SpyderX "
                            "sensor cal has unexpected length: %s != %i"
                            % (len(spydx_bcal), spydx_cal_int_bytes * 3)
                        )
                        self.exec_cmd_returnvalue = Error(
                            "SpyderX sensor cal "
                            "has unexpected "
                            "length: %s != %i"
                            % (len(spydx_bcal), spydx_cal_int_bytes * 3)
                        )
                        self.abort_subprocess()
                        return False
                    else:
                        fmt = {2: "<HHH", 4: "<III", 8: "<QQQ"}[spydx_cal_int_bytes]
                        spydx_bcal = struct.unpack(fmt, spydx_bcal)
                        self.log(appname + ": SpyderX sensor cal %i %i %i" % spydx_bcal)
                        if max(spydx_bcal) > 15:
                            # Black cal offsets too high - user error?
                            self.exec_cmd_returnvalue = Error(
                                lang.getstr("error.spyderx.black_cal_offsets_too_high")
                            )
                            self.abort_subprocess()
                            # Nuke the cal file
                            try:
                                os.remove(spydx_cal_fn)
                            except OSError:
                                self.log(
                                    appname + ": Warning - Could not remove "
                                    "SpyderX sensor cal file",
                                    spydx_cal_fn,
                                )
                            return False
        return True

    def check_instrument_place_on_screen(self, txt):
        """Check if instrument should be placed on screen by looking at Argyll CMS command output"""
        self.instrument_place_on_spot_msg = False
        if "place instrument on test window" in txt.lower():
            self.instrument_place_on_screen_msg = True
        elif "place instrument on spot" in txt.lower():
            self.instrument_place_on_spot_msg = True
        if self.instrument_place_on_screen_msg or self.instrument_place_on_spot_msg:
            if not self.check_instrument_calibration_file():
                return
        if (
            self.instrument_place_on_screen_msg and "key to continue" in txt.lower()
        ) or (
            self.instrument_calibration_complete
            and self.instrument_place_on_spot_msg
            and self.progress_wnd is getattr(self, "terminal", None)
        ):
            self.log(
                "%s: Detected instrument placement (screen/spot) message" % appname
            )
            self.instrument_place_on_screen_msg = False
            if (
                self.cmdname == get_argyll_utilname("dispcal")
                and sys.platform == "darwin"
            ):
                # On the Mac dispcal's test window
                # hides the cursor and steals focus
                start_new_thread(mac_app_activate, (1, wx.GetApp().AppName))
            # IMPORTANT: When making changes to the instrument on screen
            # detection, also apply them to appropriate part in Worker.exec_cmd
            if self.instrument_calibration_complete or (
                (
                    config.is_untethered_display()
                    or getcfg("measure.darken_background")
                    or self.madtpg_fullscreen is False
                )
                and (
                    not self.dispread_after_dispcal
                    or self.cmdname == get_argyll_utilname("dispcal")
                    or self._detecting_video_levels
                )
                and not self.instrument_on_screen
            ):
                # Show a dialog asking user to place the instrument on the
                # screen if the instrument calibration was completed,
                # or if we measure a remote ("Web") display,
                # or if we use a black background during measurements,
                # but in case of the latter two only if dispread is not
                # run directly after dispcal
                self.instrument_calibration_complete = False
                self.instrument_place_on_screen()
            else:
                if self.isalive():
                    # Delay to work-around a problem with i1D2 and Argyll 1.7
                    # to 1.8.3 under Mac OS X 10.11 El Capitan where skipping
                    # interactive display adjustment would botch the first
                    # reading (black)
                    wx.CallLater(1500, self.instrument_on_screen_continue)
        elif self.instrument_place_on_spot_msg:
            self.log("%s: Assuming instrument on screen" % appname)
            self.instrument_on_screen = True

    def instrument_on_screen_continue(self):
        self.log("%s: Skipping place instrument on screen message..." % appname)
        self.safe_send(" ")
        self.pauseable_now = True
        self.instrument_on_screen = True

    def check_instrument_sensor_position(self, txt):
        """Check instrument sensor position by looking
        at Argyll CMS command output"""
        if "read failed due to the sensor being in the wrong position" in txt.lower():
            self.instrument_sensor_position_msg = True
        if self.instrument_sensor_position_msg and " or q to " in txt.lower():
            self.log(f"{appname}: Detected read failed due to wrong sensor position")
            self.instrument_sensor_position_msg = False
            self.instrument_reposition_sensor()

    def check_retry_measurement(self, txt):
        if (
            "key to retry:" in txt
            and "read stopped at user request!" not in self.recent.read()
            and (
                "Sample read failed due to misread" in self.recent.read()
                or "Sample read failed due to communication problem"
                in self.recent.read()
            )
            and not self.subprocess_abort
        ):
            self.retrycount += 1
            self.log("%s: Retrying (%s)..." % (appname, self.retrycount))
            self.recent.write("\r\n%s: Retrying (%s)..." % (appname, self.retrycount))
            self.safe_send(" ")

    def check_spotread_result(self, txt):
        """Check if spotread returned a result"""
        if (
            self.cmdname == get_argyll_utilname("spotread")
            and (
                self.progress_wnd is not getattr(self, "terminal", None)
                or getattr(self.terminal, "Name", None) == "VisualWhitepointEditor"
            )
            and (
                "Result is XYZ:" in txt
                or "Result is Y:" in txt
                or (
                    self.instrument_calibration_complete
                    and self.spotread_just_do_instrument_calibration
                )
            )
        ):
            # Single spotread reading, we are done
            wx.CallLater(1000, self.quit_terminate_cmd)

    def get_skip_video_levels_detection(self):
        """Should we skip video levels detection?"""
        return (
            self._detected_output_levels
            or not getcfg("patterngenerator.detect_video_levels")
            or config.get_display_name() == "Untethered"
            or is_ccxx_testchart()
        )

    def detect_video_levels(self):
        """Detect wether we need video (16..235) or data (0..255) levels"""
        if self.get_skip_video_levels_detection():
            return True
        self._detecting_video_levels = True
        try:
            while True:
                result = self._detect_video_levels()
                if result is not None:
                    return result
        finally:
            self._detecting_video_levels = False

    def _detect_video_levels(self):
        """Detect black clipping due to incorrect levels"""
        self.log("Detecting output levels range...")
        tempdir = self.create_tempdir()
        if isinstance(tempdir, Exception):
            return tempdir
        ti1_path = os.path.join(tempdir, "0_16.ti1")
        try:
            with open(ti1_path, "wb") as ti1:
                ti1.write(
                    """CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
ORIGINATOR "Argyll targen"
CREATED "Thu Apr 20 12:22:05 2017"
APPROX_WHITE_POINT "95.045781 100.000003 108.905751"
COLOR_REP "RGB"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 100.00 100.00 100.00 95.046 100.00 108.91
2 0.0000 0.0000 0.0000 0.0000 0.0000 0.0000
3 6.2500 6.2500 6.2500 0.2132 0.2241 0.2443
END_DATA
""".encode()
                )
        except Exception as exception:
            return exception
        setcfg("patterngenerator.use_video_levels", 0)
        result = self.measure_ti1(
            ti1_path, get_data_path("linear.cal"), allow_video_levels=False
        )
        if result is None:
            return False
        if isinstance(result, Exception) or not result:
            return result
        ti3_path = os.path.join(tempdir, "0_16.ti3")
        try:
            ti3 = CGATS.CGATS(ti3_path)
        except (IOError, CGATS.CGATSError) as exception:
            return exception
        try:
            verify_ti1_rgb_xyz(ti3)
        except CGATS.CGATSError as exception:
            return exception
        luminance_XYZ_cdm2 = ti3.queryv1("LUMINANCE_XYZ_CDM2")
        if not luminance_XYZ_cdm2:
            return Error(
                lang.getstr(
                    "error.testchart.missing_fields", (ti3_path, "LUMINANCE_XYZ_CDM2")
                )
            )
        try:
            Y_cdm2 = float(luminance_XYZ_cdm2.split()[1])
        except (IndexError, ValueError):
            return Error(lang.getstr("error.testchart.invalid", ti3_path))
        if Y_cdm2 <= 0 or math.isnan(Y_cdm2):
            return Error(lang.getstr("error.luminance.invalid"))
        black_0 = ti3[0].DATA[1]
        black_16 = ti3[0].DATA[2]
        if black_0 and black_16:
            self.log("RGB level 0 is %.6f cd/m2" % (black_0["XYZ_Y"] / 100.0 * Y_cdm2))
            self.log(
                "RGB level 16 is %.6f cd/m2" % (black_16["XYZ_Y"] / 100.0 * Y_cdm2)
            )
            # Check delta cd/m2 to determine if data or video levels
            # We need to take the display white luminance into account
            threshold = 0.02 / Y_cdm2 * 100  # Threshold 0.02 cd/m2
            assume_video_levels = black_16["XYZ_Y"] - black_0["XYZ_Y"] < threshold
            if assume_video_levels:
                if config.get_display_name() == "madVR":
                    # This is an error
                    return Error(lang.getstr("madvr.wrong_levels_detected"))
                if not config.is_virtual_display():
                    # Could be a misconfiguration of display or graphics driver.
                    # Make the user aware.
                    self._detected_levels_issue_confirm_wait = True
                    wx.CallAfter(self.detected_levels_issue_confirm)
                    # Wait for call to return
                    while (
                        self._detected_levels_issue_confirm_wait
                        and not self.subprocess_abort
                    ):
                        sleep(0.05)
                    if self._use_detected_video_levels is False:
                        return False
                    elif self._use_detected_video_levels is None:
                        # Retry
                        return
                self.log("Using limited range output levels")
            else:
                self.log("Assuming full range output levels")
            setcfg("patterngenerator.use_video_levels", int(assume_video_levels))
            if not config.is_patterngenerator() and sys.platform == "darwin":
                # macOS video levels encoding seems to only work right on
                # some machines if not using videoLUT to do the scaling
                setcfg_cond(assume_video_levels, "calibration.use_video_lut", 0)
            self._detected_output_levels = True
        else:
            return Error(
                lang.getstr(
                    "error.testchart.missing_fields",
                    (ti3_path, ", ".join(list(black_0.keys()))),
                )
            )
        return True

    def detected_levels_issue_confirm(self):
        dlg = ConfirmDialog(
            None,
            msg=lang.getstr("display.levels_issue_detected"),
            ok=lang.getstr("retry"),
            alt=lang.getstr("fix_output_levels_using_vcgt"),
            wrap=100,
        )
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_OK:
            # Retry
            self._use_detected_video_levels = None
        elif result == wx.ID_CANCEL:
            self._use_detected_video_levels = False
        else:
            # Fix output levels using calibration
            self._use_detected_video_levels = True
        self._detected_levels_issue_confirm_wait = False

    def do_instrument_calibration(self, failed=False):
        """Ask user to initiate sensor calibration and execute.
        Give an option to cancel."""
        if getattr(self, "subprocess_abort", False) or getattr(
            self, "thread_abort", False
        ):
            # If we are aborting, ignore request
            return
        self.instrument_on_screen = False
        self.log("%s: Prompting to calibrate instrument" % appname)
        self.progress_wnd.Pulse(" " * 4)
        if failed:
            msg = lang.getstr("failure")
        elif self.get_instrument_name() == "ColorMunki":
            msg = lang.getstr("instrument.calibrate.colormunki")
        else:
            # Detect type of calibration (emissive dark or reflective)
            # by looking for serial number of calibration tile
            # Argyll up to 1.8.3: 'Serial no.'
            # Argyll 1.9.x: 'S/N'
            serial = re.search(r"(?:Serial no.|S/N) (\S+)", self.recent.read(), re.I)
            if serial:
                # Reflective calibration, white reference tile required
                # (e.g. i1 Pro hires mode)
                msg = lang.getstr("instrument.calibrate.reflective", serial.group(1))
            elif self._detected_instrument and "SpyderX" in self._detected_instrument:
                msg = lang.getstr("instrument.calibrate.spyderx")
            else:
                # Emissive dark calibration
                msg = lang.getstr("instrument.calibrate")
        if self.use_madvr:
            fullscreen = self.madtpg.is_fullscreen()
            self.madtpg_show_osd(
                msg, sys.platform == "win32" and self.single_real_display()
            )
        dlg = ConfirmDialog(
            self.progress_wnd,
            msg=msg
            + "\n\n"
            + (
                self._detected_instrument
                and "%s%s"
                % (
                    self._detected_instrument,
                    self._detected_instrument_serial
                    and " (%s %s)"
                    % (lang.getstr("serial_number"), self._detected_instrument_serial)
                    or "",
                )
                or self.get_instrument_name()
            ),
            ok=lang.getstr("ok"),
            cancel=lang.getstr("cancel"),
            bitmap=geticon(32, "dialog-information"),
        )
        self.progress_wnd.dlg = dlg
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if self.finished:
            self.log(
                "%s: Ignoring instrument calibration prompt (worker "
                "thread finished)" % appname
            )
            return
        if dlg_result != wx.ID_OK:
            self.log("%s: Canceled instrument calibration prompt" % appname)
            self.abort_subprocess()
            return False
        self.log("%s: About to calibrate instrument" % appname)
        self.progress_wnd.Pulse(lang.getstr("please_wait"))
        if self.safe_send(" "):
            self.progress_wnd.Pulse(lang.getstr("instrument.calibrating"))
        if self.use_madvr:
            if sys.platform == "win32":
                self.madtpg.set_osd_text("\u25b6")  # "Play" symbol
            self.madtpg_restore_settings(False, fullscreen)

    def abort_all(self, confirm=False):
        aborted = False
        for worker in workers:
            if not getattr(worker, "finished", True):
                worker.abort_subprocess(confirm)
                aborted = True
        return aborted

    def abort_subprocess(self, confirm=False):
        """Abort the current subprocess or thread"""
        if getattr(self, "abort_requested", False):
            return
        self.abort_requested = True
        if confirm and getattr(self, "progress_wnd", None):
            prev_dlg = getattr(self.progress_wnd, "dlg", None)
            if (
                prev_dlg
                and prev_dlg.IsShownOnScreen()
                and not isinstance(prev_dlg, DummyDialog)
            ):
                self.abort_requested = False
                return
            pause = not getattr(self.progress_wnd, "paused", False) and hasattr(
                self.progress_wnd, "pause_continue_handler"
            )
            if pause:
                self.progress_wnd.pause_continue_handler(True)
                self.pause_continue()
            dlg = ConfirmDialog(
                self.progress_wnd,
                msg=lang.getstr("dialog.confirm_cancel"),
                ok=lang.getstr("yes"),
                cancel=lang.getstr("no"),
                bitmap=geticon(32, "dialog-warning"),
            )
            self.progress_wnd.dlg = dlg
            dlg_result = dlg.ShowModal()
            if isinstance(prev_dlg, DummyDialog):
                self.progress_wnd.dlg = prev_dlg
            dlg.Destroy()
            if dlg_result != wx.ID_OK:
                if pause:
                    self.progress_wnd.Resume()
                else:
                    self.progress_wnd.keepGoing = True
                    if hasattr(self.progress_wnd, "cancel"):
                        self.progress_wnd.cancel.Enable()
                self.abort_requested = False
                return
        self.patch_count = 0
        self.subprocess_abort = True
        self.thread_abort = True
        if self.use_patterngenerator or self.use_madnet_tpg:
            abortfilename = os.path.join(self.tempdir, ".abort")
            open(abortfilename, "w").close()
        delayedresult.startWorker(self.quit_terminate_consumer, self.quit_terminate_cmd)

    def quit_terminate_consumer(self, delayedResult):
        try:
            result = delayedResult.get()
        except Exception as exception:
            if hasattr(exception, "originalTraceback"):
                self.log(exception.originalTraceback, fn=log)
            else:
                self.log(traceback.format_exc(), fn=log)
            result = UnloggedError(safe_str(exception))
        if isinstance(result, Exception):
            show_result_dialog(result, getattr(self, "progress_wnd", None))
            result = False
        self.subprocess_abort = False
        if not result:
            self.thread_abort = False
            self.abort_requested = False
            if getattr(self, "progress_wnd", None):
                self.progress_wnd.Resume()

    def instrument_place_on_screen(self):
        """Show a dialog asking user to place the instrument on the screen
        and give an option to cancel"""
        if getattr(self, "subprocess_abort", False) or getattr(
            self, "thread_abort", False
        ):
            # If we are aborting, ignore request
            return
        self.log("%s: Prompting to place instrument on screen" % appname)
        self.progress_wnd.Pulse(" " * 4)
        if self.use_madvr:
            fullscreen = self.madtpg.is_fullscreen()
            self.madtpg_show_osd(
                lang.getstr("instrument.place_on_screen"),
                sys.platform == "win32" and self.single_real_display(),
            )
        dlg = ConfirmDialog(
            self.progress_wnd,
            msg=lang.getstr("instrument.place_on_screen")
            + "\n\n"
            + (
                self._detected_instrument
                and "%s%s"
                % (
                    self._detected_instrument,
                    self._detected_instrument_serial
                    and " (%s %s)"
                    % (lang.getstr("serial_number"), self._detected_instrument_serial)
                    or "",
                )
                or self.get_instrument_name()
            ),
            ok=lang.getstr("ok"),
            cancel=lang.getstr("cancel"),
            bitmap=geticon(32, "dialog-information"),
        )
        self.progress_wnd.dlg = dlg
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if self.finished:
            self.log(
                "%s: Ignoring instrument placement prompt (worker thread "
                "finished)" % appname
            )
            return
        if dlg_result != wx.ID_OK:
            self.log("%s: Canceled instrument placement prompt" % appname)
            self.abort_subprocess()
            return False
        self.instrument_on_screen = True
        self.log("%s: Instrument on screen" % appname)
        if not isinstance(self.progress_wnd, (UntetheredFrame, DisplayUniformityFrame)):
            self.safe_send(" ")
            self.pauseable_now = True
        if self.use_madvr:
            if sys.platform == "win32":
                self.madtpg.set_osd_text("\u25b6")  # "Play" symbol
            self.madtpg_restore_settings(False, fullscreen)

    def instrument_reposition_sensor(self):
        if getattr(self, "subprocess_abort", False) or getattr(
            self, "thread_abort", False
        ):
            # If we are aborting, ignore request
            return
        self.log("%s: Prompting to reposition instrument sensor" % appname)
        self.progress_wnd.Pulse(" " * 4)
        fullscreen = False
        if self.use_madvr:
            fullscreen = self.madtpg.is_fullscreen()
            self.madtpg_show_osd(
                lang.getstr("instrument.reposition_sensor"),
                sys.platform == "win32" and self.single_real_display(),
            )
        dlg = ConfirmDialog(
            self.progress_wnd,
            msg=lang.getstr("instrument.reposition_sensor"),
            ok=lang.getstr("ok"),
            cancel=lang.getstr("cancel"),
            bitmap=geticon(32, "dialog-warning"),
        )
        self.progress_wnd.dlg = dlg
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if self.finished:
            self.log(
                "%s: Ignoring instrument sensor repositioning prompt "
                "(worker thread finished)" % appname
            )
            return
        if dlg_result != wx.ID_OK:
            self.log("%s: Canceled instrument sensor repositioning prompt" % appname)
            self.abort_subprocess()
            return False
        self.safe_send(" ")
        if self.use_madvr:
            if sys.platform == "win32":
                self.madtpg.set_osd_text("\u25b6")  # "Play" symbol
            self.madtpg_restore_settings(False, fullscreen)

    def clear_argyll_info(self):
        """Clear Argyll CMS version, detected displays and instruments."""
        self.argyll_bin_dir = None
        self.argyll_version = [0, 0, 0]
        self.argyll_version_string = "0.0.0"
        self._displays = []
        self.display_edid = []
        self.display_manufacturers = []
        self.display_names = []
        self.display_rects = []
        self.displays = []
        self.instruments = []
        self.lut_access = []
        self.reset_argyll_enum()

    def reset_argyll_enum(self):
        """Reset auto-detected (during display/instrument enumeration) properties"""
        self.measurement_modes = {}
        self.argyll_virtual_display = None

    def clear_cmd_output(self):
        """Clear any output from the last run command."""
        self.cmd = None
        self.cmdname = None
        self.retcode = -1
        self.output = []
        self.errors = []
        self.recent.clear()
        self.retrycount = 0
        self.lastmsg.clear()
        self.repeat = False
        self.send_buffer = None
        # Log interaction with Argyll tools
        if not hasattr(self, "logger") or (
            isinstance(self.logger, DummyLogger)
            and self.owner
            and self.owner.Name == "mainframe"
        ):
            if not self.owner or self.owner.Name != "mainframe":
                self.logger = DummyLogger()
            else:
                self.logger = get_file_logger("interact")
        if hasattr(self, "thread") and self.thread.is_alive() and self.interactive:
            self.logger.info("-" * 80)
        self.sessionlogfile = None
        self.madtpg_bw_lvl = None
        self.madtpg_fullscreen = None
        self.use_madvr = False
        self.use_madnet_tpg = False
        self.use_patterngenerator = False
        self.patch_sequence = False
        self.patch_count = 0
        self.patterngenerator_sent_count = 0
        self.exec_cmd_returnvalue = None
        self.tmpfiles = {}
        self.buffer = []
        self._detected_instrument = None
        self._detected_instrument_serial = None

    def lut3d_get_filename(
        self, path=None, include_input_profile=True, include_ext=True
    ):
        # 3D LUT filename with crcr32 hash before extension - up to DCG 2.9.0.7
        profile_save_path = os.path.splitext(
            path or getcfg("calibration.file") or defaults["calibration.file"]
        )[0]
        lut3d = [
            getcfg("3dlut.gamap.use_b2a") and "gg" or "G",
            "i" + getcfg("3dlut.rendering_intent"),
            "r%i" % getcfg("3dlut.size"),
            "e" + getcfg("3dlut.encoding.input"),
            "E" + getcfg("3dlut.encoding.output"),
            "I%s:%s:%s"
            % (
                getcfg("3dlut.trc_gamma_type"),
                getcfg("3dlut.trc_output_offset"),
                getcfg("3dlut.trc_gamma"),
            ),
        ]
        if getcfg("3dlut.format") == "3dl":
            lut3d.append(str(getcfg("3dlut.bitdepth.input")))
        if getcfg("3dlut.format") in ("3dl", "png", "ReShade"):
            lut3d.append(str(getcfg("3dlut.bitdepth.output")))
        if include_ext:
            lut3d_ext = getcfg("3dlut.format")
            if lut3d_ext == "eeColor":
                lut3d_ext = "txt"
            elif lut3d_ext == "madVR":
                lut3d_ext = "3dlut"
            elif lut3d_ext == "ReShade":
                lut3d_ext = "png"
            elif lut3d_ext == "icc":
                lut3d_ext = profile_ext[1:]
        else:
            lut3d_ext = ""
        if include_input_profile:
            input_profname = os.path.splitext(
                os.path.basename(getcfg("3dlut.input.profile"))
            )[0]
        else:
            input_profname = ""
        lut3d_path = ".".join(
            [
                _f
                for _f in [
                    profile_save_path,
                    input_profname,
                    "%X" % (zlib.crc32("-".join(lut3d).encode()) & 0xFFFFFFFF),
                    lut3d_ext,
                ]
                if _f
            ]
        )
        if not include_input_profile or not os.path.isfile(lut3d_path):
            # 3D LUT filename with plain options before extension - DCG 2.9.0.8+
            enc_in = lut3d[3][1:]
            enc_out = lut3d[4][1:]
            encoding = enc_in
            if enc_in != enc_out:
                encoding += enc_out
            if getcfg("3dlut.output.profile.apply_cal"):
                cal_exclude = ""
            else:
                cal_exclude = "e"
            if getcfg("3dlut.trc").startswith("smpte2084"):
                lut3dp = [str(getcfg("3dlut.trc_output_offset")) + ",2084"]
                if (
                    getcfg("3dlut.hdr_peak_luminance") < 10000
                    or getcfg("3dlut.trc") == "smpte2084.rolloffclip"
                    or getcfg("3dlut.hdr_minmll")
                    or getcfg("3dlut.hdr_maxmll") < 10000
                ):
                    lut3dp.append("@%i" % getcfg("3dlut.hdr_peak_luminance"))
                    if getcfg("3dlut.trc") == "smpte2084.hardclip":
                        lut3dp.append("h")
                    else:
                        lut3dp.append("s")
                        # Alternate clip - softer
                        if getcfg("3dlut.hdr_maxmll_alt_clip"):
                            lut3dp.append("s")
                    if getcfg("3dlut.hdr_minmll"):
                        lut3dp.append("%.4f" % getcfg("3dlut.hdr_minmll"))
                    if (
                        getcfg("3dlut.hdr_minmll")
                        and getcfg("3dlut.hdr_maxmll") < 10000
                    ):
                        lut3dp.append("-")
                    if getcfg("3dlut.hdr_maxmll") < 10000:
                        lut3dp.append("%i" % getcfg("3dlut.hdr_maxmll"))
                    if getcfg("3dlut.trc") == "smpte2084.rolloffclip":
                        # Hue and chroma preservation
                        if getcfg("3dlut.hdr_sat") != 0.5:
                            lut3dp.append("s%.1f" % getcfg("3dlut.hdr_sat"))
                        if getcfg("3dlut.hdr_hue") != 1.0:
                            lut3dp.append("h%.1f" % getcfg("3dlut.hdr_hue"))
            elif getcfg("3dlut.trc") == "hlg":
                lut3dp = ["HLG"]
                if getcfg("3dlut.hdr_ambient_luminance") != 5:
                    ambient = stripzeros(getcfg("3dlut.hdr_ambient_luminance"))
                    lut3dp.append("@%s" % ambient)
            elif getcfg("3dlut.apply_trc"):
                lut3dp = [
                    lut3d[5][1].replace("b", "bb") + lut3d[5][3:].replace(":", ",")
                ]  # TRC
            else:
                # Use src profile TRC unmodified
                lut3dp = []
            lut3dp.extend(
                [
                    cal_exclude,
                    lut3d[0],  # Gamut mapping mode
                    lut3d[1][1:],  # Rendering intent
                    encoding,
                    lut3d[2][1:],
                ]
            )  # Resolution
            bitdepth_in = None
            bitdepth_out = None
            if len(lut3d) > 6:
                bitdepth_in = lut3d[6]  # Input bitdepth
            if len(lut3d) > 7:
                bitdepth_out = lut3d[7]  # Output bitdepth
            if bitdepth_in or bitdepth_out:
                bitdepth = bitdepth_in
                if bitdepth_out and bitdepth_in != bitdepth_out:
                    bitdepth += bitdepth_out
                lut3dp.append(bitdepth)
            lut3d_path = ".".join(
                [
                    _f
                    for _f in [
                        profile_save_path,
                        input_profname,
                        "".join(lut3dp),
                        lut3d_ext,
                    ]
                    if _f
                ]
            )
        return lut3d_path

    def create_3dlut(
        self,
        profile_in,
        path,
        profile_abst=None,
        profile_out=None,
        apply_cal=True,
        intent="r",
        format="cube",
        size=17,
        input_bits=10,
        output_bits=12,
        maxval=None,
        input_encoding="n",
        output_encoding="n",
        trc_gamma=None,
        trc_gamma_type="B",
        trc_output_offset=0.0,
        save_link_icc=True,
        apply_black_offset=True,
        use_b2a=False,
        white_cdm2=100,
        minmll=0,
        maxmll=10000,
        use_alternate_master_white_clip=True,
        hdr_sat=0.5,
        hdr_hue=0.5,
        ambient_cdm2=5,
        content_rgb_space="DCI P3",
        hdr_display=False,
        XYZwp=None,
    ):
        """Create a 3D LUT from one (device link) or two (device) profiles,
        optionally incorporating an abstract profile."""
        # .cube: http://doc.iridas.com/index.php?title=LUT_Formats
        # .3dl: http://www.kodak.com/US/plugins/acrobat/en/motion/products/look/UserGuide.pdf
        #       http://download.autodesk.com/us/systemdocs/pdf/lustre_color_management_user_guide.pdf
        # .spi3d: https://github.com/imageworks/OpenColorIO/blob/master/src/core/FileFormatSpi3D.cpp
        # .mga: http://pogle.pandora-int.com/download/manual/lut3d_format.html

        print("-" * 80)
        print(lang.getstr("3dlut.create"))

        for profile in (profile_in, profile_out):
            if (
                profile.profileClass not in (b"mntr", b"link", b"scnr", b"spac")
                or profile.colorSpace != b"RGB"
            ):
                raise NotImplementedError(
                    lang.getstr(
                        "profile.unsupported",
                        (profile.profileClass, profile.colorSpace),
                    )
                )
            if profile_in.profileClass == b"link":
                break

        # Setup temp dir
        cwd = self.create_tempdir()
        if isinstance(cwd, Exception):
            raise cwd

        result = None

        path = os.path.split(path)
        path = os.path.join(path[0], make_argyll_compatible_path(path[1]))
        filename, ext = os.path.splitext(path)
        name = os.path.basename(filename)

        if profile_in.profileClass == b"link":
            link_basename = os.path.basename(profile_in.fileName)
            link_filename = os.path.join(cwd, link_basename)
            profile_in.write(link_filename)
        else:
            collink = get_argyll_util("collink")
            if not collink:
                raise Error(lang.getstr("argyll.util.not_found", "collink"))

            extra_args = parse_argument_string(getcfg("extra_args.collink"))

            smpte2084 = trc_gamma in ("smpte2084.hardclip", "smpte2084.rolloffclip")
            hlg = trc_gamma == "hlg"
            hdr = smpte2084 or hlg

            profile_in_basename = make_argyll_compatible_path(
                os.path.basename(profile_in.fileName)
            )

            # XXX: collink creates dark blotch in yellow with perceptual intent
            # when using HDR PQ tonemapping - force to colorimetric and rely on
            # our own perceptual mapping
            if hdr and not hlg:
                if intent == "p":
                    intent = "r"
                elif intent == "pa":
                    intent = "aw"

            hdr_use_src_gamut = (
                hdr
                and profile_in_basename == "Rec2020.icm"
                and intent in ("la", "lp", "p", "pa", "ms", "s", "aa")
                and not get_arg("-G", extra_args)
                and not get_arg("-g", extra_args)
            )

            if hdr and not hdr_use_src_gamut and not use_b2a:
                # Always use B2A instead of inverse forward table (faster and
                # better result if B2A table has enough effective resolution)
                # for HDR with colorimetric intents
                # Check B2A resolution and regenerate on-the-fly if too low
                # and created by ArgyllCMS
                b2a = profile_out.tags.get("B2A1", profile_out.tags.get("B2A0"))
                a2b = profile_out.tags.get("A2B1", profile_out.tags.get("A2B0"))
                if (
                    not b2a
                    or (
                        isinstance(b2a, ICCP.LUT16Type)
                        and b2a.clut_grid_steps < 17
                        and profile_out.creator == "argl"
                    )
                ) and a2b:
                    clutres = getcfg("profile.b2a.hires.size")
                    b2aresult = self.update_profile_B2A(profile_out, clutres=clutres)
                    if isinstance(b2aresult, Exception):
                        raise b2aresult
                    profile_out.write()
                if "B2A1" in profile_out.tags or "B2A0" in profile_out.tags:
                    use_b2a = True

            # Argyll applycal can't deal with single gamma TRC tags
            # or TRC tags with less than 256 entries
            _applycal_bug_workaround(profile_out)

            # Prepare building a device link
            link_basename = name + profile_ext
            link_filename = os.path.join(cwd, link_basename)

            profile_out_basename = make_argyll_compatible_path(
                os.path.basename(profile_out.fileName)
            )
            if profile_in_basename == profile_out_basename:
                (profile_out_filename, profile_out_ext) = os.path.splitext(
                    profile_out_basename
                )
                profile_out_basename = "%s (2)%s" % (
                    profile_out_filename,
                    profile_out_ext,
                )
            profile_out.fileName = os.path.join(cwd, profile_out_basename)
            profile_out.write()
            profile_out_cal_path = os.path.splitext(profile_out.fileName)[0] + ".cal"

            manufacturer = profile_out.getDeviceManufacturerDescription()
            model = profile_out.getDeviceModelDescription()
            device_manufacturer = profile_out.device["manufacturer"]
            device_model = profile_out.device["model"]
            mmod = profile_out.tags.get("mmod")

            self.set_sessionlogfile(None, name, cwd)

            collink_version_string = get_argyll_version_string("collink")
            collink_version = parse_argyll_version_string(collink_version_string)
            use_collink_bt1886 = trc_gamma and not hdr

            # The display profile may not reflect the measured black point.
            # Get it from the embedded TI3 instead if zero from lookup.
            odata = self.xicclu(profile_out, (0, 0, 0), pcs="x")
            if len(odata) != 1 or len(odata[0]) != 3:
                raise ValueError("Blackpoint is invalid: %s" % odata)
            XYZbp = odata[0]
            if not XYZbp[1] and isinstance(profile_out.tags.get("targ"), ICCP.Text):
                XYZbp = profile_out.get_chardata_bkpt()
                if XYZbp:
                    XYZbp = [
                        v * XYZbp[1] for v in list(profile_out.tags.wtpt.pcs.values())
                    ]
                    self.log(
                        "Using black Y from destination profile "
                        "characterization data (normalized 0..100): "
                        "%.6f" % (XYZbp[1] * 100)
                    )
                    use_collink_bt1886 = False
            elif XYZbp[1]:
                # Use display profile blackpoint
                XYZbp = None

            # Using xicclu instead of collink is more accurate on and near
            # the gray axis (in some cases, i.e. HDR and cLUT res < 65,
            # significantly so)
            use_xicclu = (
                (experimental or hdr)
                and not profile_abst
                and intent in ("a", "aw", "r")
                and input_encoding in ("n", "t", "T")
                and output_encoding in ("n", "t")
            )

            # Apply calibration?
            if apply_cal:
                extract_cal_from_profile(profile_out, profile_out_cal_path)

                if self.argyll_version < [1, 6] or use_xicclu:
                    # Can't apply the calibration with old collink versions -
                    # apply the calibration to the 'out' profile prior to
                    # device linking instead
                    applycal = get_argyll_util("applycal")
                    if not applycal:
                        raise Error(lang.getstr("argyll.util.not_found", "applycal"))
                    self.log(lang.getstr("apply_cal"))
                    result = self.exec_cmd(
                        applycal,
                        [
                            "-v",
                            profile_out_cal_path,
                            profile_out_basename,
                            profile_out.fileName,
                        ],
                        capture_output=True,
                        skip_scripts=True,
                        sessionlogfile=self.sessionlogfile,
                    )
                    if isinstance(result, Exception) and not getcfg("dry_run"):
                        raise result
                    elif not result:
                        raise Error(
                            "\n\n".join(
                                [lang.getstr("apply_cal.error"), "\n".join(self.errors)]
                            )
                        )
                    profile_out = ICCP.ICCProfile(profile_out.fileName)

            in_rgb_space = profile_in.get_rgb_space()
            if in_rgb_space:
                in_colors = colormath.get_rgb_space_primaries_wp_xy(in_rgb_space)
                if format == "madVR":
                    # Use a D65 white for the 3D LUT Input_Primaries as
                    # madVR can only deal correctly with D65
                    # Use the same D65 xy values as written by madVR
                    # 3D LUT install API (ASTM E308-01)
                    in_colors[6:] = [0.31273, 0.32902]
            else:
                in_colors = []

            if hdr_use_src_gamut:
                content_rgb_space = colormath.get_rgb_space(content_rgb_space)
                # Always force content RGB space whitepoint to D65 so
                # default RGB to ICtCp matrix gives Ct=Cp=0 for R=G=B
                # when tone mapping
                content_rgb_space = list(content_rgb_space)
                content_rgb_space[1] = colormath.get_whitepoint("D65")
                content_colors = colormath.get_rgb_space_primaries_wp_xy(
                    content_rgb_space
                )

            if hdr_use_src_gamut and content_colors[:6] != in_colors[:6]:
                # Use source gamut to preserve more saturation.
                # Assume content colorspace (i.e. DCI P3) encoded within
                # container colorspace (i.e. Rec. 2020)

                # Get source profile
                crx, cry = content_rgb_space[2:][0][:2]
                cgx, cgy = content_rgb_space[2:][1][:2]
                cbx, cby = content_rgb_space[2:][2][:2]
                cwx, cwy = colormath.XYZ2xyY(*content_rgb_space[1])[:2]
                rgb_space_name = (
                    colormath.find_primaries_wp_xy_rgb_space_name(content_colors)
                    or "Custom"
                )
                cat = profile_in.guess_cat() or "Bradford"
                self.log(
                    "Using chromatic adaptation transform matrix from "
                    "input profile for content colorspace:",
                    cat,
                )
                profile_src = ICCP.ICCProfile.from_chromaticities(
                    crx,
                    cry,
                    cgx,
                    cgy,
                    cbx,
                    cby,
                    cwx,
                    cwy,
                    2.2,
                    rgb_space_name,
                    "",
                    cat=cat,
                )
                fd, profile_src.fileName = tempfile.mkstemp(
                    profile_ext, "%s-" % rgb_space_name, dir=cwd
                )
                stream = os.fdopen(fd, "wb")
                profile_src.write(stream)
                stream.close()
            else:
                profile_src = profile_out

            # Deal with applying TRC
            if trc_gamma:
                if (
                    use_collink_bt1886
                    and not use_xicclu
                    and (collink_version >= [1, 7] or not trc_output_offset)
                ):
                    # Make sure the profile has the expected Rec. 709 TRC
                    # for BT.1886
                    self.log(
                        f"{appname}: Applying Rec. 709 TRC to "
                        f"{os.path.basename(profile_in.fileName)}"
                    )
                    for i, channel in enumerate(("r", "g", "b")):
                        if channel + "TRC" in profile_in.tags:
                            profile_in.tags[channel + "TRC"].set_trc(-709)
                else:
                    # For HDR or Argyll < 1.7 beta, alter profile TRC
                    # Argyll CMS prior to 1.7 beta development code 2014-07-10
                    # does not support output offset, alter the source profile
                    # instead (note that accuracy is limited due to 16-bit
                    # encoding used in ICC profile, collink 1.7 can use full
                    # floating point processing and will be more precise)
                    self.blend_profile_blackpoint(
                        profile_in,
                        profile_out,
                        XYZbp,
                        trc_output_offset,
                        trc_gamma,
                        trc_gamma_type,
                        white_cdm2=white_cdm2,
                        minmll=minmll,
                        maxmll=maxmll,
                        use_alternate_master_white_clip=use_alternate_master_white_clip,
                        ambient_cdm2=ambient_cdm2,
                        content_rgb_space=content_rgb_space,
                        hdr_chroma_compression=not hdr_use_src_gamut
                        or content_colors[:6] != in_colors[:6],
                        hdr_sat=hdr_sat,
                        hdr_hue=hdr_hue,
                        hdr_target_profile=profile_src,
                    )
            elif apply_black_offset:
                # Apply only the black point blending portion of BT.1886 mapping
                self.blend_profile_blackpoint(
                    profile_in, profile_out, XYZbp, 1.0, apply_trc=False
                )

            # Deal with whitepoint
            profile_in_wtpt_XYZ = list(profile_in.tags.wtpt.ir.values())
            if XYZwp:
                # Quantize to ICC s15Fixed16Number encoding
                XYZwp = [
                    ICCP.s15Fixed16Number(ICCP.s15Fixed16Number_tohex(v)) for v in XYZwp
                ]
            else:
                XYZwp = profile_in_wtpt_XYZ
            if XYZwp != profile_in_wtpt_XYZ:
                self.log(
                    "Using whitepoint chromaticity %.4f %.4f for input"
                    % tuple(colormath.XYZ2xyY(*XYZwp)[:2])
                )
                (
                    profile_in.tags.wtpt.X,
                    profile_in.tags.wtpt.Y,
                    profile_in.tags.wtpt.Z,
                ) = XYZwp

            profile_in.fileName = os.path.join(cwd, profile_in_basename)
            profile_in.write()

            if hdr_use_src_gamut and content_colors[:6] != in_colors[:6] and False:
                # XXX: Old code - could be removed?
                # Use source gamut to preserve more saturation.
                # Assume content colorspace (i.e. DCI P3) encoded within
                # container colorspace (i.e. Rec. 2020)

                tools = {}
                for toolname in (  # "iccgamut",
                    # "timage",
                    "cctiff",
                    "tiffgamut",
                ):
                    tools[toolname] = get_argyll_util(toolname)
                    if not tools[toolname]:
                        raise Error(lang.getstr("argyll.util.not_found", toolname))

                # Apply HDR TRC to source
                self.blend_profile_blackpoint(
                    profile_src,
                    profile_out,
                    XYZbp,
                    trc_output_offset,
                    trc_gamma,
                    trc_gamma_type,
                    white_cdm2=white_cdm2,
                    minmll=minmll,
                    maxmll=maxmll,
                    use_alternate_master_white_clip=use_alternate_master_white_clip,
                    ambient_cdm2=ambient_cdm2,
                    hdr_chroma_compression=False,
                    hdr_sat=hdr_sat,
                    hdr_hue=hdr_hue,
                )

                profile_src.write()

                # Create link from source to destination profile
                gam_link_filename = tempfile.mktemp(profile_ext, "gam-link-", dir=cwd)
                result = self.exec_cmd(
                    collink,
                    [
                        "-v",
                        "-G",
                        "-ir",
                        profile_src.fileName,
                        profile_in_basename,
                        gam_link_filename,
                    ],
                    capture_output=True,
                    skip_scripts=True,
                    sessionlogfile=self.sessionlogfile,
                )
                if isinstance(result, Exception) and not getcfg("dry_run"):
                    raise result
                elif not result:
                    raise Error(
                        "\n".join(self.errors)
                        or "%s %s" % (collink, lang.getstr("error"))
                    )

                # Create RGB image
                # gam_in_tiff = tempfile.mktemp(".tif", "gam-in-", dir=cwd)
                # result = self.exec_cmd(tools["timage"], ["-x", gam_in_tiff],
                # capture_output=True,
                # skip_scripts=True,
                # sessionlogfile=self.sessionlogfile)
                # if isinstance(result, Exception) and not getcfg("dry_run"):
                # raise result
                # elif not result:
                # raise Error("\n".join(self.errors) or lang.getstr("error"))
                fd, gam_in_tiff = tempfile.mkstemp(".tif", "gam-in-", dir=cwd)
                stream = os.fdopen(fd, "wb")
                imfile.write_rgb_clut(stream, 65, format="TIFF")
                stream.close()

                # Convert RGB image from source to destination to get source
                # encoded within destination.
                gam_out_tiff = tempfile.mktemp(".tif", "gam-out-", dir=cwd)
                result = self.exec_cmd(
                    tools["cctiff"],
                    ["-p", gam_link_filename, gam_in_tiff, gam_out_tiff],
                    capture_output=True,
                    skip_scripts=True,
                    sessionlogfile=self.sessionlogfile,
                )
                if isinstance(result, Exception) and not getcfg("dry_run"):
                    raise result
                elif not result:
                    raise Error(
                        "\n".join(self.errors)
                        or "%s %s" % (tools["cctiff"], lang.getstr("error"))
                    )

                # Create gamut surface from image
                # gam_filename = os.path.splitext(profile_src.fileName)[0] + ".gam"
                # result = self.exec_cmd(tools["iccgamut"], ["-ir", "-pj",
                # profile_src.fileName],
                # capture_output=True,
                # skip_scripts=True,
                # sessionlogfile=self.sessionlogfile)
                gam_filename = os.path.splitext(gam_out_tiff)[0] + ".gam"
                result = self.exec_cmd(
                    tools["tiffgamut"],
                    ["-ir", "-pj", profile_in.fileName, gam_out_tiff],
                    capture_output=True,
                    skip_scripts=True,
                    sessionlogfile=self.sessionlogfile,
                )
                if isinstance(result, Exception) and not getcfg("dry_run"):
                    raise result
                elif not result:
                    raise Error(
                        "\n".join(self.errors)
                        or "%s %s" % (tools["tiffgamut"], lang.getstr("error"))
                    )
            else:
                gam_filename = None

            # Now build the device link
            args = [
                "-v",
                "-qh",
                "-g" if use_b2a else "-G",
                "-i%s" % intent,
                "-r%i" % size,
                "-n",
            ]
            if gam_filename:
                # Use source gamut
                args.insert(3, gam_filename)
            if profile_abst:
                profile_abst.write(os.path.join(cwd, "abstract.icc"))
                args.extend(["-p", "abstract.icc"])
            if self.argyll_version >= [1, 6]:
                if format == "madVR":
                    args.append("-3m")
                elif format == "eeColor" and not test:
                    args.append("-3e")
                elif format == "cube" and collink_version >= [1, 7] and not test:
                    args.append("-3c")
                args.append("-e%s" % input_encoding)
                args.append("-E%s" % output_encoding)
                if collink_version >= [1, 7]:
                    args.append("-b")  # Use RGB->RGB forced black point hack
                if use_collink_bt1886 and trc_gamma_type in ("b", "B"):
                    if collink_version >= [1, 7]:
                        args.append(
                            "-I%s:%s:%s"
                            % (trc_gamma_type, trc_output_offset, trc_gamma)
                        )
                    elif not trc_output_offset:
                        args.append("-I%s:%s" % (trc_gamma_type, trc_gamma))
                if apply_cal:
                    # Apply the calibration when building our device link
                    # i.e. use collink -a parameter (apply calibration curves
                    # to link output and append linear)
                    args.extend(["-a", os.path.basename(profile_out_cal_path)])
            if extra_args:
                args += extra_args

            # cLUT Input value tweaks to make Video encoded black land on
            # 65 res grid nodes, which should help 33 and 17 res cLUTs too
            def cLUT65_to_VidRGB(v):
                if size not in (17, 33, 65):
                    return v
                return colormath.cLUT65_to_VidRGB(v)

            def VidRGB_to_cLUT65(v):
                if size not in (17, 33, 65):
                    return v
                return colormath.VidRGB_to_cLUT65(v)

            logfiles = self.get_logfiles()

            xts = time()
            if use_xicclu:
                # Create device link using xicclu
                is_argyll_lut_format = format == "icc"

                def clipVidRGB(RGB, black_hack=True):
                    """Clip a value to the RGB Video range 16..235 RGB.

                    Clip the incoming value RGB[] in place.
                    Return a bit mask of the channels that have/would clip,
                    scale all non-black values to avoid positive clipping and
                    return the restoring scale factor (> 1.0) if this has occured,
                    return the full value in the clip direction in full[],
                    and return the uncliped value in unclipped[].

                    """

                    clipmask = 0
                    scale = 1.0
                    full = [None] * 3
                    unclipped = list(RGB)

                    # Locate the channel with the largest value
                    mx = max(RGB)
                    # One channel positively clipping
                    if mx > 235.0 / 255.0:
                        scale = ((235.0 - 16.0) / 255.0) / (mx - (16.0 / 255.0))

                        # Scale all non-black value down towards black, to avoid clipping
                        for i, v in enumerate(RGB):
                            # Note if channel would clip in itself
                            if v > 235.0 / 255.0:
                                full[i] = 1.0
                                clipmask |= 1 << i
                            if v > 16.0 / 255.0:
                                RGB[i] = (v - 16.0 / 255.0) * scale + 16.0 / 255.0

                    # See if any values negatively clip
                    for i, v in enumerate(RGB):
                        if black_hack:
                            cond = v <= 16.0 / 255.0
                        else:
                            cond = v < 16.0 / 255.0
                        if cond:
                            RGB[i] = 16.0 / 255.0
                            full[i] = 0.0
                            clipmask |= 1 << i

                    scale = 1.0 / scale

                    return clipmask, scale, full, unclipped, RGB

                logfiles.write("Generating input values...\n")
                clip = {}
                seen = {}  # Seen RGB input values
                seenkeys = {}
                RGB_src_in = []
                maxind = size - 1.0
                level_16 = VidRGB_to_cLUT65(16.0 / 255) * maxind
                level_235 = VidRGB_to_cLUT65(235.0 / 255) * maxind
                prevperc = 0
                cliphack = False  # Clip TV levels BtB/WtW in for full range out?
                for a in range(size):
                    for b in range(size):
                        for c in range(size):
                            if self.thread_abort:
                                raise Info(lang.getstr("aborted"))
                            abc = (a, b, c)
                            RGB = [v / maxind for v in abc]
                            if input_encoding in ("t", "T"):
                                # TV levels in
                                if (
                                    cliphack
                                    and output_encoding == "n"
                                    and (
                                        min(abc) < level_16
                                        or max(abc) > math.ceil(level_235)
                                    )
                                ):
                                    # Don't lookup out of range values
                                    continue
                                else:
                                    RGB = [cLUT65_to_VidRGB(v) for v in RGB]
                                    clip[abc] = clipVidRGB(RGB)
                                    if a == b == c and a in (
                                        math.ceil(level_16),
                                        math.ceil(level_235),
                                    ):
                                        self.log(
                                            "Input RGB (0..255) %f %f %f"
                                            % tuple(v * 255 for v in RGB)
                                        )
                                    # Convert 16..235 to 0..255 for xicclu
                                    RGB = [
                                        colormath.convert_range(
                                            v, 16.0 / 255, 235.0 / 255, 0, 1
                                        )
                                        for v in RGB
                                    ]
                            RGB = [min(max(v, 0), 1) * 255 for v in RGB]
                            seenkey = tuple(int(round(v * 257)) for v in RGB)
                            seenkeys[abc] = seenkey
                            if seenkey in seen:
                                continue
                            seen[seenkey] = True
                            RGB_src_in.append(RGB)
                        perc = round(
                            ((a + 1) * (b + 1) * (c + 1)) / float(size**3) * 100
                        )
                        if perc > prevperc:
                            logfiles.write("\r%i%%" % perc)
                            prevperc = perc
                logfiles.write("\n")
                self.log("Skipped", size**3 - len(seen), "duplicate input values")
                # Forward lookup input RGB through source profile
                logfiles.write("Looking up input values through source profile...\n")
                XYZ_src_out = self.xicclu(
                    profile_in,
                    RGB_src_in,
                    intent[0],
                    pcs="x",
                    scale=255,
                    logfile=logfiles,
                )
                del RGB_src_in
                if intent == "aw":
                    XYZw = self.xicclu(profile_in, [[1, 1, 1]], intent[0], pcs="x")[0]
                    # Lookup scaled down white XYZ
                    logfiles.write("Looking for solution...\n")
                    for n in range(9):
                        XYZscaled = []
                        for i in range(2001):
                            XYZscaled.append(
                                [v * (1 - (n * 2001 + i) / 20000.0) for v in XYZw]
                            )
                        RGBscaled = self.xicclu(
                            profile_out,
                            XYZscaled,
                            "a",
                            "b" if use_b2a else "if",
                            pcs="x",
                            get_clip=True,
                        )
                        # Find point at which it no longer clips
                        XYZwscaled = None
                        for i, RGBclip in enumerate(RGBscaled):
                            if self.thread_abort:
                                raise Info(lang.getstr("aborted"))
                            if RGBclip[3] is True or max(RGBclip[:3]) > 1:
                                # Clipped, skip
                                continue
                            # Found
                            XYZwscaled = XYZscaled[i]
                            logfiles.write(
                                "Solution found at index %i "
                                "(step size %f)\n" % (i, 1 / 2000.0)
                            )
                            logfiles.write(
                                "RGB white %6.4f %6.4f %6.4f\n" % tuple(RGBclip[:3])
                            )
                            logfiles.write(
                                "XYZ white %6.4f %6.4f %6.4f, "
                                "CCT %.1f K\n"
                                % tuple(XYZscaled[i] + [colormath.XYZ2CCT(*XYZwscaled)])
                            )
                            break
                        else:
                            if n == 8:
                                break
                        if XYZwscaled:
                            # Found solution
                            break
                    if not XYZwscaled:
                        raise Error(
                            "No solution found in %i "
                            "iterations with %i steps" % (n, i)
                        )
                    for i, XYZ in enumerate(XYZ_src_out):
                        XYZ[:] = [v / XYZw[1] * XYZwscaled[1] for v in XYZ]
                    del RGBscaled
                # Inverse forward lookup source profile output XYZ through
                # destination profile
                num_cpus = cpu_count()
                num_workers = min(max(num_cpus, 1), size)
                if "A2B0" in profile_out.tags and not use_b2a:
                    if num_cpus > 2:
                        num_workers = int(num_workers * 0.75)
                    num_batches = size // 9
                else:
                    if num_cpus > 2:
                        num_workers = 2
                    num_batches = 1
                if use_b2a:
                    direction = "backward"
                else:
                    direction = "inverse forward"
                logfiles.write(
                    "Creating device link from %s lookup "
                    "(%i workers)...\n" % (direction, num_workers)
                )
                RGB_dst_out = []
                for slices in pool_slice(
                    _mp_xicclu,
                    XYZ_src_out,
                    (profile_out.fileName, intent[0], "b" if use_b2a else "if"),
                    {
                        "pcs": "x",
                        "use_cam_clipping": True,
                        "abortmessage": lang.getstr("aborted"),
                    },
                    num_workers,
                    self.thread_abort,
                    logfiles,
                    num_batches=num_batches,
                ):
                    RGB_dst_out.extend(slices)
                del XYZ_src_out
                logfiles.write("\n")
                logfiles.write("Filling cLUT...\n")
                profile_link = ICCP.ICCProfile()
                profile_link.profileClass = b"link"
                profile_link.connectionColorSpace = b"RGB"
                profile_link.setDescription(name)
                profile_link.setCopyright(getcfg("copyright"))
                profile_link.tags.pseq = ICCP.ProfileSequenceDescType(
                    profile=profile_link
                )
                profile_link.tags.pseq.add(profile_in)
                profile_link.tags.pseq.add(profile_out)
                profile_link.tags.A2B0 = A2B0 = ICCP.LUT16Type(
                    None, "A2B0", profile_link
                )
                A2B0.matrix = colormath.Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
                if input_encoding in ("t", "T"):
                    A2B0.input = [[]] * 3
                    for i in range(2048):
                        A2B0.input[0].append(VidRGB_to_cLUT65(i / 2047.0) * 65535)
                else:
                    A2B0.input = [[0, 65535]] * 3
                A2B0.output = [[0, 65535]] * 3
                A2B0.clut = []
                clut = {}
                n = 0
                for a in range(size):
                    for b in range(size):
                        for c in range(size):
                            abc = (a, b, c)
                            if (
                                cliphack
                                and input_encoding in ("t", "T")
                                and output_encoding == "n"
                                and (
                                    min(abc) < level_16
                                    or max(abc) > math.ceil(level_235)
                                )
                            ):
                                # TV levels in, no value from lookup, full
                                # range out
                                continue
                            seenkey = seenkeys[abc]
                            if seenkey in seen and seen[seenkey] is not True:
                                RGB = seen[seenkey]
                            else:
                                if input_encoding in ("t", "T"):
                                    cond = min(abc) <= level_16 and min(abc) == max(abc)
                                else:
                                    cond = max(abc) == 0
                                if cond:
                                    # Black hack
                                    self.log(
                                        "Black hack - forcing output RGB %i %i %i"
                                        % tuple(
                                            cLUT65_to_VidRGB(v / maxind) * 255
                                            for v in abc
                                        )
                                    )
                                    RGB = [0] * 3
                                else:
                                    RGB = RGB_dst_out[n]
                                seen[seenkey] = RGB
                                n += 1
                            clut[abc] = RGB
                del seen
                del seenkeys
                del RGB_dst_out
                preserve_sync = getcfg("3dlut.preserve_sync")
                prevperc = 0
                for a in range(size):
                    for b in range(size):
                        A2B0.clut.append([])
                        for c in range(size):
                            abc = (a, b, c)
                            if (
                                cliphack
                                and input_encoding in ("t", "T")
                                and output_encoding == "n"
                                and (
                                    min(abc) < level_16
                                    or max(abc) > math.ceil(level_235)
                                )
                            ):
                                # TV levels in, no value from lookup, full
                                # range out
                                key = tuple(
                                    min(
                                        max(v, math.ceil(level_16)),
                                        math.ceil(level_235),
                                    )
                                    for v in abc
                                )
                                RGB = clut[key]
                            else:
                                # Got value from lookup
                                RGB = clut[abc]
                                del clut[abc]
                                if output_encoding == "t":
                                    # TV levels out
                                    # Convert 0..255 to 16..235
                                    RGB = [
                                        colormath.convert_range(
                                            v, 0, 1, 16.0 / 255, 235.0 / 255
                                        )
                                        for v in RGB
                                    ]

                                    if input_encoding in ("t", "T"):
                                        # TV levels in, scale/extrapolate clip
                                        clipmask, scale, full, uci, cin = clip[abc]
                                        del clip[abc]
                                        for j, v in enumerate(RGB):

                                            if clipmask:

                                                if input_encoding != "T" and scale > 1:
                                                    # We got +ve clipping

                                                    # Re-scale all non-black values
                                                    if v > 16.0 / 255.0:
                                                        v = (
                                                            v - 16.0 / 255.0
                                                        ) * scale + 16.0 / 255.0

                                                # Deal with -ve clipping and sync
                                                if clipmask & (1 << j):

                                                    if full[j] == 0.0:
                                                        # Only extrapolate in black direction
                                                        ifull = (
                                                            1.0 - full[j]
                                                        )  # Opposite limit to full

                                                        # Do simple extrapolation (Not perfect though)
                                                        v = ifull + (v - ifull) * (
                                                            uci[j] - ifull
                                                        ) / (cin[j] - ifull)

                                                    # Clip or pass sync through
                                                    if (
                                                        v < 0.0
                                                        or v > 1.0
                                                        or (
                                                            preserve_sync
                                                            and abs(uci[j] - full[j])
                                                            < 1e-6
                                                        )
                                                    ):
                                                        v = full[j]

                                            RGB[j] = v

                            RGB = [min(max(v, 0), 1) * 65535 for v in RGB]
                            A2B0.clut[-1].append(RGB)
                        perc = round(len(A2B0.clut) / float(size**2) * 100)
                        if perc > prevperc:
                            logfiles.write("\r%i%%" % perc)
                            prevperc = perc
                logfiles.write("\n")
                profile_link.write(link_filename)
                self.log("Finished creating device link in", time() - xts, "seconds")
                result = True
                del clip
                del clut
                del A2B0
            else:
                # Create device link (and 3D LUT, if applicable) using collink
                is_argyll_lut_format = (
                    self.argyll_version >= [1, 6]
                    and (
                        (
                            (
                                format == "eeColor"
                                or (format == "cube" and collink_version >= [1, 7])
                            )
                            and not test
                        )
                        or format == "madVR"
                    )
                    or format == "icc"
                )
                result = self.exec_cmd(
                    collink,
                    args + [profile_in_basename, profile_out_basename, link_filename],
                    capture_output=True,
                    skip_scripts=True,
                )
                if result and not isinstance(result, Exception):
                    self.log("Finished creating 3D LUT in", time() - xts, "seconds")

            if (
                result
                and not isinstance(result, Exception)
                and save_link_icc
                and os.path.isfile(link_filename)
            ):
                profile_link = ICCP.ICCProfile(link_filename)
                profile_link.setDescription(name)
                profile_link.setCopyright(getcfg("copyright"))
                if manufacturer:
                    profile_link.setDeviceManufacturerDescription(manufacturer)
                if model:
                    profile_link.setDeviceModelDescription(model)
                profile_link.device["manufacturer"] = device_manufacturer
                profile_link.device["model"] = device_model
                if mmod:
                    profile_link.tags.mmod = mmod
                profile_link.tags.meta = ICCP.DictType()
                profile_link.tags.meta.update(
                    [
                        ("CMF_product", appname),
                        ("CMF_binary", appname),
                        ("CMF_version", version),
                        (
                            "collink.args",
                            sp.list2cmdline(
                                args
                                + [
                                    profile_in_basename,
                                    profile_out_basename,
                                    link_basename,
                                ]
                            ),
                        ),
                        ("collink.version", collink_version_string),
                        ("encoding.input", input_encoding),
                        ("encoding.output", output_encoding),
                    ]
                )
                profile_link.calculateID()
                profile_link.write(f"{filename}{profile_ext}")
                profile_link.tags.A2B0.clut_writepng(f"{filename}.A2B0.CLUT.png")
                del profile_link

                if use_xicclu and format == "madVR":
                    # We need to up-interpolate the device link ourself
                    # Call this in a separate process so I/O congestion
                    # doesn't interfere with UI updates and audio
                    # madvr.icc_device_link_to_madvr(link_filename,
                    # rgb_space=profile_in.get_rgb_space(),
                    # hdr=smpte2084 + hdr_display,
                    # logfile=logfiles,
                    # convert_video_rgb_to_clut65=True)
                    interp_args = []
                    if os.path.basename(exe).lower().startswith("python"):
                        if os.path.basename(exe).lower().startswith("pythonw"):
                            cmd = os.path.join(
                                exedir, "python" + os.path.basename(exe)[7:]
                            )
                        else:
                            cmd = exe
                        py = os.path.normpath(
                            os.path.join(
                                pydir, "..", appname + "-eeColor-to-madVR-converter.py"
                            )
                        )
                        if os.path.exists(py):
                            # Running from source or 0install
                            # If parent is running from 0install, the child
                            # will inherit the correct environment (PYTHONPATH)
                            # so no need to run child through 0install
                            # Need to run unbuffered so we can grab
                            # progress
                            interp_args.append("-u")
                            interp_args.append(py)
                        else:
                            # Regular install
                            # Need to run unbuffered so we can grab
                            # progress
                            interp_args.append("-u")
                            if sys.platform in ("win32", "darwin"):
                                interp_args.append(
                                    get_data_path(
                                        os.path.join(
                                            "scripts",
                                            appname.lower()
                                            + "-eecolor-to-madvr-converter",
                                        )
                                    )
                                )
                            else:
                                # Linux
                                interp_args.append(
                                    which(
                                        appname.lower() + "-eecolor-to-madvr-converter"
                                    )
                                )
                    elif isapp:
                        cmd = os.path.join(exedir, "python")
                        interp_args.extend(
                            [
                                "-c",
                                "import sys;sys.path.insert(0, %r);execfile(%r)"
                                % (
                                    os.path.join(
                                        pydir.encode(fs_enc),
                                        "lib",
                                        "python%s%s" % sys.version_info[:2],
                                        "site-packages.zip",
                                    ),
                                    os.path.join(
                                        pydir.encode(fs_enc),
                                        appname.lower() + "-eecolor-to-madvr-converter",
                                    ),
                                ),
                            ]
                        )
                    else:
                        cmd = os.path.join(
                            pydir, appname + "-eeColor-to-madVR-converter" + exe_ext
                        )
                    if in_colors:
                        interp_args.append(
                            "--colorspace=" + ",".join([str(v) for v in in_colors])
                        )
                    interp_args.append("--hdr=%i" % (smpte2084 + hdr_display))
                    interp_args.append("--convert-video-rgb-to-clut65")
                    interp_args.append("--append-linear-cal")
                    interp_args.append("--batch")
                    interp_args.append(link_filename)
                    result = self.exec_cmd(
                        cmd,
                        interp_args,
                        capture_output=True,
                        skip_scripts=True,
                        use_pty=True,
                    )
                    if debug:
                        h3d = madvr.H3DLUT(os.path.join(cwd, name + ".3dlut"))
                        h3d.write_devicelink(filename + ".3dlut" + profile_ext)

            if result and not isinstance(result, Exception):
                if format == "madVR" and is_argyll_lut_format:
                    # We need to update Input_Primaries, otherwise the
                    # madVR 3D LUT won't work correctly! (collink fills
                    # Input_Primaries from a lookup through the input
                    # profile, which won't work correctly if the input
                    # profile is cLUT-based. Also, we want to use a D65
                    # white as madVR can only deal correctly with D65
                    h3d = madvr.H3DLUT(os.path.join(cwd, name + ".3dlut"))
                    input_primaries = h3d.parametersData.get("Input_Primaries")
                    if input_primaries:
                        if in_colors:
                            h3d.parametersData["Input_Primaries"] = in_colors
                        if smpte2084:
                            h3d.parametersData["Input_Transfer_Function"] = "PQ"
                            if hdr_display:
                                h3d.parametersData["Output_Transfer_Function"] = "PQ"
                        h3d.write()
                    else:
                        raise Error("madVR 3D LUT doesn't contain " "Input_Primaries")

                if hdr or not use_collink_bt1886 or XYZwp:
                    if not hdr and XYZwp != profile_in_wtpt_XYZ:
                        # Update profile description
                        profile_in.setDescription(
                            profile_in.getDescription()
                            + " %sx %sy"
                            % tuple(
                                stripzeros("%.4f" % v)
                                for v in colormath.XYZ2xyY(*XYZwp)[:2]
                            )
                        )
                    # Save source profile
                    in_name, in_ext = os.path.splitext(profile_in_basename)
                    profile_in.fileName = os.path.join(
                        os.path.dirname(path),
                        self.lut3d_get_filename(profile_in_basename, False, False)
                        + in_ext,
                    )
                    profile_in.write()
                    if isinstance(profile_in.tags.get("A2B0"), ICCP.LUT16Type):
                        # Write diagnostic PNG
                        profile_in.tags.A2B0.clut_writepng(
                            os.path.splitext(profile_in.fileName)[0] + ".A2B0.CLUT.png"
                        )
                    if isinstance(profile_in.tags.get("DBG0"), ICCP.LUT16Type):
                        # HDR RGB
                        profile_in.tags.DBG0.clut_writepng(
                            os.path.splitext(profile_in.fileName)[0] + ".DBG0.CLUT.png"
                        )
                    if isinstance(profile_in.tags.get("DBG1"), ICCP.LUT16Type):
                        # Display RGB
                        profile_in.tags.DBG1.clut_writepng(
                            os.path.splitext(profile_in.fileName)[0] + ".DBG1.CLUT.png"
                        )
                    if isinstance(profile_in.tags.get("DBG2"), ICCP.LUT16Type):
                        # Display XYZ
                        profile_in.tags.DBG2.clut_writepng(
                            os.path.splitext(profile_in.fileName)[0] + ".DBG2.CLUT.png"
                        )

            if is_argyll_lut_format or (use_xicclu and format == "madVR"):
                # Collink has already written the 3DLUT for us,
                # or we have written the madVR 3D LUT
                if format == "cube":
                    if maxval is None:
                        maxval = 1.0
                    # Strip any leading whitespace from each line (although
                    # leading/trailing spaces are allowed according to the spec).
                    # Also, Argyll does not write (optional) DOMAIN_MIN/MAX
                    # keywords. Add them after the fact.
                    cube_filename = os.path.join(cwd, f"{name}.cube")
                    if os.path.isfile(cube_filename):
                        add_domain = True
                        cube_data = []
                        with open(cube_filename, "rb") as cube_file:
                            for line in cube_file:
                                # Strip any leading whitespace
                                line = line.lstrip()
                                if line.startswith(b"DOMAIN_"):
                                    # Account for the possibility that a
                                    # future Argyll version might write
                                    # DOMAIN_MIN/MAX keywords.
                                    add_domain = False
                                elif line.startswith(b"0.") and add_domain:
                                    # 1st cube data entry marks end of keywords.
                                    # Add DOMAIN_MIN/MAX keywords
                                    cube_data.append(b"DOMAIN_MIN 0.0 0.0 0.0\n")
                                    fp_offset = str(maxval).find(".")
                                    domain_max = b"DOMAIN_MAX %s %s %s\n" % (
                                        (b"%%.%if" % len(str(maxval)[fp_offset + 1 :]),)
                                        * 3
                                    )
                                    cube_data.append(domain_max % ((maxval,) * 3))
                                    cube_data.append(b"\n")
                                    add_domain = False
                                cube_data.append(line)
                        # Write updated cube
                        with open(cube_filename, "wb") as cube_file:
                            cube_file.write(b"".join(cube_data))
                result2 = self.wrapup(
                    not isinstance(result, UnloggedInfo) and result,
                    dst_path=path,
                    ext_filter=[".3dlut", ".cube", ".log", ".png", ".txt", ".wrl"],
                )
                if not result:
                    result = UnloggedError(lang.getstr("aborted"))
                if isinstance(result2, Exception):
                    if isinstance(result, Exception):
                        result = Error(str(result) + "\n\n" + str(result2))
                    else:
                        result = result2
                if not isinstance(result, Exception):
                    return

            if isinstance(result, Exception):
                raise result
            elif not result:
                raise UnloggedError(lang.getstr("aborted"))

        # We have to create the 3DLUT ourselves
        logfiles.write("Generating %s 3D LUT...\n" % format)

        # Create input RGB values
        RGB_oin = []
        RGB_in = []
        RGB_indexes = []
        seen = {}
        if format == "eeColor":
            # Fixed size
            size = 65
        elif format == "ReShade":
            format = "png"
        if format == "3dl":
            if maxval is None:
                maxval = 1023
            if output_bits is None:
                output_bits = math.log(maxval + 1) / math.log(2)
            if input_bits is None:
                input_bits = output_bits
            # Note: We only round up for the input values, output values
            # are rounded to nearest integer
            quantizer = lambda v: int(math.ceil(v * (2**input_bits - 1)))
            scale = quantizer(1.0)
        else:
            quantizer = lambda v: v
            scale = 1.0
        step = 1.0 / (size - 1)
        RGB_triplet = [0.0, 0.0, 0.0]
        RGB_index = [0, 0, 0]
        # Set the fastest and slowest changing columns, from right to left
        if format in ("3dl", "mga", "spi3d") or (
            format == "png" and getcfg("3dlut.image.order") == "bgr"
        ):
            columns = (0, 1, 2)
        elif format == "eeColor":
            columns = (2, 0, 1)
        else:
            columns = (2, 1, 0)
        for i in range(0, size):
            # Red
            if format == "eeColor" and not eecolor65 and i == size - 1:
                # Last cLUT entry is fixed to 1.0 for eeColor and unchangeable
                continue
            RGB_triplet[columns[0]] = quantizer(step * i)
            RGB_index[columns[0]] = i
            for j in range(0, size):
                # Green
                if format == "eeColor" and not eecolor65 and j == size - 1:
                    # Last cLUT entry is fixed to 1.0 for eeColor and unchangeable
                    continue
                RGB_triplet[columns[1]] = quantizer(step * j)
                RGB_index[columns[1]] = j
                for k in range(0, size):
                    # Blue
                    if self.thread_abort:
                        raise Info(lang.getstr("aborted"))
                    if format == "eeColor" and not eecolor65 and k == size - 1:
                        # Last cLUT entry is fixed to 1.0 for eeColor and unchangeable
                        continue
                    RGB_triplet[columns[2]] = quantizer(step * k)
                    RGB_oin.append(list(RGB_triplet))
                    RGB_copy = list(RGB_triplet)
                    if format == "eeColor":
                        for l in range(3):
                            RGB_copy[l] = eeColor_to_VidRGB(RGB_copy[l])
                            if input_encoding in ("t", "T"):
                                RGB_copy[l] = VidRGB_to_cLUT65(RGB_copy[l])
                    RGB_index[columns[2]] = k
                    RGB_in.append(RGB_copy)
                    RGB_indexes.append(list(RGB_index))

        # Lookup RGB -> RGB values through devicelink profile using icclu
        # (Using icclu instead of xicclu because xicclu in versions
        # prior to Argyll CMS 1.6.0 could not deal with devicelink profiles)
        RGB_out = self.xicclu(
            link_filename, RGB_in, scale=scale, use_icclu=True, logfile=logfiles
        )

        if format == "eeColor" and output_encoding == "n":
            RGBw = self.xicclu(link_filename, [[1, 1, 1]], use_icclu=True)[0]

        # Remove temporary files, move log file
        result2 = self.wrapup(dst_path=path, ext_filter=[".log"])

        if isinstance(result, Exception):
            raise result

        valsep = " "
        if format not in ("dcl", "png"):
            lut = [["# Created with %s %s" % (appname, version)]]
            linesep = "\n"
        if format in ("3dl", "dcl"):
            maxval = math.pow(2, output_bits) - 1
            if format == "3dl":
                lut.append(["# INPUT RANGE: %i" % input_bits])
                lut.append(["# OUTPUT RANGE: %i" % output_bits])
                lut.append([])
                for i in range(0, size):
                    lut[-1].append("%i" % quantizer(i * step))
            else:
                # dcl
                lut = [["# DeviceControl-LG 3D"]]
                linesep = "\r\n"
            for RGB_triplet in RGB_out:
                lut.append([])
                for component in (0, 1, 2):
                    lut[-1].append(
                        "%i" % int(round(RGB_triplet[component] / scale * maxval))
                    )
        elif format == "cube":
            if maxval is None:
                maxval = 1.0
            lut.append(["LUT_3D_SIZE %i" % size])
            lut.append(["DOMAIN_MIN 0.0 0.0 0.0"])
            fp_offset = str(maxval).find(".")
            domain_max = "DOMAIN_MAX %s %s %s" % (
                ("%%.%if" % len(str(maxval)[fp_offset + 1 :]),) * 3
            )
            lut.append([domain_max % ((maxval,) * 3)])
            lut.append([])
            for RGB_triplet in RGB_out:
                lut.append([])
                for component in (0, 1, 2):
                    lut[-1].append("%.6f" % (RGB_triplet[component] * maxval))
        elif format == "spi3d":
            if maxval is None:
                maxval = 1.0
            lut = [["SPILUT 1.0"]]
            lut.append(["3 3"])
            lut.append(["%i %i %i" % ((size,) * 3)])
            for i, RGB_triplet in enumerate(RGB_out):
                lut.append([str(index) for index in RGB_indexes[i]])
                for component in (0, 1, 2):
                    lut[-1].append("%.6f" % (RGB_triplet[component] * maxval))
        elif format == "eeColor":
            if maxval is None:
                maxval = 1.0
            lut = []
            for i, RGB_triplet in enumerate(RGB_out):
                lut.append(["%.6f" % (component * maxval) for component in RGB_oin[i]])
                for component in (0, 1, 2):
                    v = RGB_triplet[component] * maxval
                    if output_encoding == "n":
                        # For eeColor and full range RGB, make sure that the cLUT
                        # output maps to 1.0
                        # The output curve will correct this
                        v /= RGBw[component]
                        v = min(v, 1)
                    v = VidRGB_to_eeColor(v)
                    lut[-1].append("%.6f" % v)
            linesep = "\r\n"
        elif format == "mga":
            lut = [
                ["#HEADER"],
                ["#filename: %s" % os.path.basename(path)],
                ["#type: 3D cube file"],
                ["#format: 1.00"],
                ["#created: %s" % strftime("%d %B %Y")],
                ["#owner: %s" % getpass.getuser()],
                ["#title: %s" % os.path.splitext(os.path.basename(path))[0]],
                ["#END"],
            ]
            lut.append([])
            lut.append(["channel 3d"])
            lut.append(["in %i" % (size**3)])
            maxval = 2**output_bits - 1
            lut.append(["out %i" % (maxval + 1)])
            lut.append([""])
            lut.append(["format lut"])
            lut.append([""])
            lut.append(["values\tred\tgreen\tblue"])
            for i, RGB_triplet in enumerate(RGB_out):
                lut.append(["%i" % i])
                for component in (0, 1, 2):
                    lut[-1].append(("%i" % int(round(RGB_triplet[component] * maxval))))
            valsep = "\t"
        elif format == "png":
            lut = [[]]
            if output_bits > 8:
                # PNG only supports 8 and 16 bit
                output_bits = 16
            maxval = 2**output_bits - 1
            for RGB_triplet in RGB_out:
                if len(lut[-1]) == size:
                    # Append new scanline
                    lut.append([])
                lut[-1].append([int(round(v * maxval)) for v in RGB_triplet])
            # Current layout is vertical
            if getcfg("3dlut.image.layout") == "h":
                # Change layout to horizontal
                lutv = lut
                lut = [[]]
                for i in range(size):
                    if len(lut[-1]) == size**2:
                        # Append new scanline
                        lut.append([])
                    for j in range(size):
                        lut[-1].extend(lutv[i + size * j])

        if format != "png":
            lut.append([])
            for i, line in enumerate(lut):
                lut[i] = valsep.join(line)
            result = linesep.join(lut)

        # Write 3DLUT
        lut_file = open(path, "wb")
        if format != "png":
            lut_file.write(result.encode())
        else:
            im = imfile.Image(lut, output_bits)
            im.write(lut_file)
        lut_file.close()

        if format == "eeColor":
            # Write eeColor 1D LUTs
            for i, color in enumerate(["red", "green", "blue"]):
                for count, inout in [(1024, "first"), (8192, "second")]:
                    with open(
                        filename + "-" + inout + "1d" + color + ".txt", "wb"
                    ) as lut1d:
                        for j in range(count):
                            v = j / (count - 1.0)
                            if inout == "second" and output_encoding == "n":
                                # For eeColor and Full range RGB, unmap the
                                # cLUT output maps from 1.0
                                v *= RGBw[i]
                            n_v = "%.6f\n" % v
                            lut1d.write(n_v.encode())

        if isinstance(result2, Exception):
            raise result2

    def enumerate_displays_and_ports(
        self,
        silent=False,
        check_lut_access=True,
        enumerate_ports=True,
        include_network_devices=True,
    ):
        """Enumerate the available displays and ports.

        Also sets Argyll version number, availability of certain options
        like black point rate, and checks LUT access for each display.

        """
        if (silent and check_argyll_bin()) or (not silent and check_set_argyll_bin()):
            displays = []
            xrandr_names = {}
            lut_access = []
            if verbose >= 1:
                print(lang.getstr("enumerating_displays_and_comports"))
            instruments = []
            current_display_name = config.get_display_name()
            cfg_instruments = getcfg("instruments")
            current_instrument = config.get_instrument_name()
            if enumerate_ports:
                cmd = get_argyll_util("dispcal")
            else:
                cmd = get_argyll_util("dispwin")
                for instrument in cfg_instruments:
                    # Names are canonical from 1.1.4.7 onwards, but we may have
                    # verbose names from an old configuration
                    instrument = get_canonical_instrument_name(instrument)
                    if instrument.strip():
                        instruments.append(instrument)
            args = []
            if include_network_devices:
                args.append("-dcc:?")
            args.append("-?")
            argyll_bin_dir = os.path.dirname(cmd)
            if argyll_bin_dir != self.argyll_bin_dir:
                self.argyll_bin_dir = argyll_bin_dir
                print(self.argyll_bin_dir)
            result = self.exec_cmd(
                cmd,
                args,
                capture_output=True,
                skip_scripts=True,
                silent=True,
                log_output=False,
            )
            if isinstance(result, Exception):
                print(result)
            arg = None
            defaults["calibration.black_point_hack"] = 0
            defaults["calibration.black_point_rate.enabled"] = 0
            defaults["patterngenerator.prisma.argyll"] = 0
            n = -1
            self.display_rects = []
            non_standard_display_args = ("-dweb[:port]", "-dmadvr")
            if test:
                # Add dummy Chromecasts
                self.output.append(" -dcc[:n]")
                self.output.append("    100 = '\xd4\xc7\xf3 Test A'")
                self.output.append("    101 = '\xd4\xc7\xf3 Test B'")
            argyll_version_string = None
            self.reset_argyll_enum()
            for line in self.output:
                if isinstance(line, str):
                    n += 1
                    line = line.strip()
                    if argyll_version_string is None and "version" in line.lower():
                        argyll_version_string = line[line.lower().find("version") + 8 :]
                        if argyll_version_string != self.argyll_version_string:
                            self.set_argyll_version_from_string(argyll_version_string)
                        print(f"ArgyllCMS {self.argyll_version_string}")
                        defaults["copyright"] = (
                            f"No copyright. Created with {appname} {version} and "
                            f"Argyll CMS {argyll_version_string}"
                        )

                        if self.argyll_version > [1, 0, 4]:
                            # Rate of blending from neutral to black point.
                            defaults["calibration.black_point_rate.enabled"] = 1

                        if (
                            self.argyll_version >= [1, 7]
                            and "Beta" not in self.argyll_version_string
                        ):
                            # Forced black point hack available
                            # (Argyll CMS 1.7)
                            defaults["calibration.black_point_hack"] = 1

                        if self.argyll_version >= [1, 9, 4]:
                            # Add CIE 2012 observers
                            valid_observers = natsort(observers + ["2012_2", "2012_10"])
                        else:
                            valid_observers = observers
                        for key in [
                            "%s",
                            "colorimeter_correction.%s",
                            "colorimeter_correction.%s.reference",
                        ]:
                            key %= "observer"
                            config.valid_values[key] = valid_observers
                        continue
                    line = line.split(None, 1)
                    if len(line) and line[0][0] == "-":
                        arg = line[0]
                        value = line[-1].split(None, 1)[0]
                        if arg == "-d" and not value.startswith("n"):
                            # Argyll 2.0.2 started listing -d madvr and -d dummy
                            # instead of -dmadvr and -ddummy
                            # Use the non-space-delimited as the canonical form
                            arg += value
                        if arg == "-A":
                            # Rate of blending from neutral to black point.
                            defaults["calibration.black_point_rate.enabled"] = 1
                        elif arg in non_standard_display_args:
                            displays.append(arg)
                        elif arg == "-b" and not line[-1].startswith("bright"):
                            # Forced black point hack available
                            # (Argyll CMS 1.7b 2014-12-22)
                            defaults["calibration.black_point_hack"] = 1
                        elif arg == "-dprisma[:host]":
                            defaults["patterngenerator.prisma.argyll"] = 1
                        elif arg in ("-dvirtual", "-ddummy"):
                            # Custom modified Argyll V2.0.2 (-dvirtual)
                            # or Argyll >= 2.0.2 (-d dummy)
                            self.argyll_virtual_display = arg[2:]
                            print("Argyll has virtual display support")
                    elif len(line) > 1 and line[1][0] == "=":
                        value = line[1].strip(" ='")
                        if arg == "-d":
                            # Standard displays
                            match = re.findall(
                                r"(.+?),? at (-?\d+), (-?\d+), width (\d+), height (\d+)",
                                value,
                            )
                            if len(match):
                                xrandr_name = re.search(r", Output (.+)", match[0][0])
                                if xrandr_name:
                                    xrandr_names[len(displays)] = xrandr_name.group(1)
                                display = "%s @ %s, %s, %sx%s" % match[0]
                                if " ".join(value.split()[-2:]) == "(Primary Display)":
                                    display += " [PRIMARY]"
                                displays.append(display)
                                self.display_rects.append(
                                    wx.Rect(*[int(item) for item in match[0][1:]])
                                )
                        elif arg == "-dcc[:n]":
                            # Chromecast
                            if value:
                                # Note the Chromecast name may be mangled due
                                # to being UTF-8 encoded, but commandline output
                                # will always be decoded to Unicode using the
                                # stdout encoding, which may not be UTF-8
                                # (e.g. under Windows). We can recover characters
                                # valid in both UTF-8 and stdout encoding
                                # by a re-encode/decode step
                                displays.append(
                                    "Chromecast %s: %s"
                                    % (line[0], safe_str(value, enc))
                                )
                        elif arg == "-dprisma[:host]":
                            # Prisma (via Argyll CMS)
                            # <serial no>: <name> @ <ip>
                            # 141550000000: prisma-0000 @ 172.31.31.162
                            match = re.findall(r".+?: (.+) @ (.+)", value)
                            if len(match):
                                displays.append(
                                    "Prisma %s: %s @ %s"
                                    % (
                                        line[0],
                                        safe_str(match[0][0], enc),
                                        match[0][1],
                                    )
                                )
                        elif arg == "-c" and enumerate_ports:
                            if (
                                re.match(r"/dev(?:/[\w.\-]+)*$", value)
                                or re.match(r"COM\d+$", value)
                            ) and getcfg("skip_legacy_serial_ports"):
                                # Skip all legacy serial ports (this means we
                                # deliberately don't support DTP92 and
                                # Spectrolino, although they may work when
                                # used with a serial to USB adaptor)
                                continue
                            value = value.split(None, 1)
                            if len(value) > 1:
                                value = value[1].split("'", 1)[0].strip("()")
                            else:
                                value = value[0]
                            value = get_canonical_instrument_name(value)
                            instruments.append(value)
            if test:
                inames = list(all_instruments.keys())
                inames.sort()
                for iname in inames:
                    iname = get_canonical_instrument_name(iname)
                    if iname not in instruments:
                        instruments.append(iname)
            if verbose >= 1:
                print(lang.getstr("success"))
            if instruments != self.instruments:
                self.instruments = instruments
                setcfg("instruments", instruments)
                if (
                    current_instrument != self.get_instrument_name()
                    and current_instrument in instruments
                ):
                    setcfg("comport.number", instruments.index(current_instrument) + 1)
            if displays != self._displays:
                self._displays = list(displays)
                setcfg("displays", displays)
                if RDSMM:
                    # Sync with Argyll - needed under Linux to map EDID
                    RDSMM.enumerate_displays()
                displays = [
                    display
                    for display in displays
                    if display not in non_standard_display_args
                ]
                self.display_edid = []
                self.display_manufacturers = []
                self.display_names = []
                if sys.platform == "win32":
                    # The ordering will work as long
                    # as Argyll continues using
                    # EnumDisplayMonitors
                    try:
                        monitors = util_win.get_real_display_devices_info()
                    except Exception as exception:
                        if not isinstance(exception, pywintypes.error):
                            print(traceback.format_exc())
                        monitors = []
                for i, display in enumerate(displays):
                    if display.startswith("Chromecast ") or display.startswith(
                        "Prisma "
                    ):
                        self.display_edid.append({})
                        if display.startswith("Prisma "):
                            display_manufacturer = "Q, Inc"
                        else:
                            display_manufacturer = "Google"
                        self.display_manufacturers.append(display_manufacturer)
                        self.display_names.append(display.split(":", 1)[1].strip())
                        continue
                    display_name = split_display_name(display)
                    # Make sure we have nice descriptions
                    desc = []
                    if sys.platform == "win32" and i < len(monitors):
                        # Get monitor description using win32api
                        device = util_win.get_active_display_device(
                            monitors[i]["Device"]
                        )
                        if device:
                            desc.append(device.DeviceString)
                        # Deal with HiDPI - update monitor rect
                        m_left, m_top, m_right, m_bottom = monitors[i]["Monitor"]
                        m_width = m_right - m_left
                        m_height = m_bottom - m_top
                        self.display_rects[i] = wx.Rect(
                            m_left, m_top, m_width, m_height
                        )
                        is_primary = " [PRIMARY]" in display
                        display = " @ ".join(
                            [
                                display_name,
                                "%i, %i, %ix%i" % (m_left, m_top, m_width, m_height),
                            ]
                        )
                        if is_primary:
                            display += " [PRIMARY]"
                    # Get monitor descriptions from EDID
                    try:
                        # Important: display_name must be given for get_edid
                        # under Mac OS X, but it doesn't hurt to always
                        # include it
                        edid = get_edid(i, display_name)
                    except Exception as exception:
                        suppress_errors = (SystemError, TypeError, ValueError, WMIError)
                        if sys.platform == "win32":
                            suppress_errors += (pywintypes.error,)
                        if isinstance(exception, EnvironmentError):
                            print(exception)
                        elif not isinstance(exception, suppress_errors):
                            print(traceback.format_exc())
                        edid = {}
                    self.display_edid.append(edid)
                    if edid:
                        manufacturer = edid.get("manufacturer", "").split()
                        monitor = edid.get(
                            "monitor_name",
                            edid.get("ascii", str(edid["product_id"] or "")),
                        )
                        if (
                            monitor in ("Color LCD", "iMac")
                            and edid["manufacturer_id"] == "APP"
                            and sys.platform == "darwin"
                        ):
                            # Get mac model if internal display
                            model_id = get_model_id()
                            if model_id:
                                # Override monitor name
                                monitor = model_id
                                # Override EDID
                                edid["monitor_name"] = monitor
                        if monitor and monitor not in "".join(desc):
                            desc = [monitor]
                    else:
                        manufacturer = []
                    if desc and desc[-1] not in display:
                        # Only replace the description if it not already
                        # contains the monitor model
                        display = " @".join([" ".join(desc), display.split("@")[-1]])
                    displays[i] = display
                    self.display_manufacturers.append(" ".join(manufacturer))
                    self.display_names.append(split_display_name(display))
                if self.argyll_version >= [1, 4, 0]:
                    displays.append("Web @ localhost")
                    self.display_edid.append({})
                    self.display_manufacturers.append("")
                    self.display_names.append("Web")
                if self.argyll_version >= [1, 6, 0]:
                    displays.append("madVR")
                    self.display_edid.append({})
                    self.display_manufacturers.append("")
                    self.display_names.append("madVR")
                # Prisma (via DisplayCAL)
                displays.append("Prisma")
                self.display_edid.append({})
                self.display_manufacturers.append("Q, Inc")
                self.display_names.append("Prisma")
                # Resolve
                displays.append("Resolve")
                self.display_edid.append({})
                self.display_manufacturers.append("DaVinci")
                self.display_names.append("Resolve")
                # Untethered
                displays.append("Untethered")
                self.display_edid.append({})
                self.display_manufacturers.append("")
                self.display_names.append("Untethered")
                #
                self.displays = displays
                setcfg("displays", displays)
                if (
                    current_display_name != config.get_display_name()
                    and current_display_name in self.display_names
                ):
                    setcfg(
                        "display.number",
                        self.display_names.index(current_display_name) + 1,
                    )
                # Filter out Prisma (via DisplayCAL), Resolve and Untethered
                # IMPORTANT: Also make changes to display filtering in
                # worker.Worker.has_separate_lut_access
                displays = displays[:-3]
                if self.argyll_version >= [1, 6, 0]:
                    # Filter out madVR
                    displays = displays[:-1]
                if self.argyll_version >= [1, 4, 0]:
                    # Filter out Web @ localhost
                    displays = displays[:-1]
                if check_lut_access:
                    dispwin = get_argyll_util("dispwin")
                    test_cal = get_data_path("test.cal")
                    if not test_cal:
                        print(lang.getstr("file.missing", "test.cal"))
                    tmp = self.create_tempdir()
                    if isinstance(tmp, Exception):
                        print(tmp)
                        tmp = None
                    for i, disp in enumerate(displays):
                        if (
                            disp.startswith("Chromecast ")
                            or disp.startswith("Prisma ")
                            or not test_cal
                        ):
                            lut_access.append(None)
                            continue
                        if sys.platform == "darwin":
                            # There's no easy way to check LUT access under
                            # Mac OS X because loading a LUT isn't persistent
                            # unless you run as root. Just assume we have
                            # access to all displays.
                            lut_access.append(True)
                            continue
                        if verbose >= 1:
                            print(lang.getstr("checking_lut_access", (i + 1)))
                        # Save current calibration?
                        if tmp:
                            current_cal = os.path.join(tmp, "current.cal")
                            tmp_cal = current_cal
                            result = self.save_current_video_lut(
                                i + 1, current_cal, silent=True
                            )
                        # Load test.cal
                        result = self.exec_cmd(
                            dispwin,
                            ["-d%s" % (i + 1), "-c", test_cal],
                            capture_output=True,
                            skip_scripts=True,
                            silent=True,
                        )
                        if isinstance(result, Exception):
                            print(result)
                        elif result is None:
                            lut_access.append(None)
                            continue
                        # Check if LUT == test.cal
                        result = self.exec_cmd(
                            dispwin,
                            ["-d%s" % (i + 1), "-V", test_cal],
                            capture_output=True,
                            skip_scripts=True,
                            silent=True,
                        )
                        if isinstance(result, Exception):
                            print(result)
                        elif result is None:
                            lut_access.append(None)
                            continue
                        retcode = -1
                        for line in self.output:
                            if line.find("IS loaded") >= 0:
                                retcode = 0
                                break
                        # Reset LUT & (re-)load previous cal (if any)
                        if not tmp or not os.path.isfile(current_cal):
                            current_cal = self.get_dispwin_display_profile_argument(i)
                        result = self.exec_cmd(
                            dispwin,
                            ["-d%s" % (i + 1), "-c", current_cal],
                            capture_output=True,
                            skip_scripts=True,
                            silent=True,
                        )
                        if isinstance(result, Exception):
                            print(result)
                        if tmp and os.path.isfile(tmp_cal):
                            try:
                                os.remove(tmp_cal)
                            except EnvironmentError as exception:
                                print(exception)
                        lut_access.append(retcode == 0)
                        if verbose >= 1:
                            if retcode == 0:
                                print(lang.getstr("success"))
                            else:
                                print(lang.getstr("failure"))
                else:
                    lut_access.extend([None] * len(displays))
                if self.argyll_version >= [1, 4, 0]:
                    # Web @ localhost
                    lut_access.append(False)
                if self.argyll_version >= [1, 6, 0]:
                    # madVR
                    lut_access.append(True)
                # Prisma (via DisplayCAL)
                lut_access.append(False)
                # Resolve
                lut_access.append(False)
                # Untethered
                lut_access.append(False)
                self.lut_access = lut_access
        elif silent or not check_argyll_bin():
            self.clear_argyll_info()

    def exec_cmd(
        self,
        cmd,
        args=None,
        capture_output=False,
        display_output=False,
        low_contrast=True,
        skip_scripts=False,
        silent=False,
        parent=None,
        asroot=False,
        log_output=True,
        title=appname,
        shell=False,
        working_dir=None,
        dry_run=None,
        sessionlogfile=None,
        use_pty=False,
    ):
        """Execute a command.

        Return value is either True (succeed), False (failed), None (canceled)
        or an exception.

        Args:
            cmd (str): the full path of the command.
            args (List[str]): The arguments, if any.
            capture_output (bool): If True, swallows any output from the
                command and sets the 'output' and 'errors' properties of the
                Worker instance.
            display_output (bool): Shows the log after the command.
            low_contrast (bool): If True sets low contrast shell colors while
                the command is run.
            skip_scripts (bool): If True, skips the creation of shell scripts
                that allow re-running the command. Note that this is also
                controlled by a global config option and scripts will only be
                created if it evaluates to False.
            silent (bool): If True, skips most output and also most error
                dialogs (except unexpected failures).
            parent (): Sets the parent window for auth dialog (if asroot is
                True).
            asroot (bool): If True, on Linux runs the command using sudo.
            log_output (bool): If True, logs any output if capture_output is
                also set.
            title (str): Title for auth dialog (if asroot is True).
            working_dir (str): Working directory. If None, will be determined
                from absulte path of last argument and last argument will be
                set to only the basename. If False, no working dir will be used
                and file arguments not changed.
        """
        if args is None:
            args = []

        # convert all args to str if any are bytes
        for i, arg in enumerate(args):
            if isinstance(arg, bytes):
                args[i] = arg.decode("utf-8")

        # If dry_run is explicitly set to False, ignore dry_run config value
        dry_run = dry_run is not False and (dry_run or getcfg("dry_run"))
        if not capture_output:
            capture_output = False
            if sys.stdout and hasattr(sys.stdout, "isatty") and not sys.stdout.isatty():
                capture_output = True

        self.clear_cmd_output()
        if None in [cmd, args]:
            if verbose >= 1 and not silent:
                print(lang.getstr("aborted"))
            return False
        self.cmd = cmd
        cmdname = os.path.splitext(os.path.basename(cmd))[0]
        self.cmdname = cmdname
        if "-?" not in args and cmdname == get_argyll_utilname("dispwin"):
            if "-I" in args or "-U" in args:
                if "-Sl" in args or "-Sn" in args:
                    # Root is required if installing a profile to a system
                    # location
                    asroot = True
            elif "-s" not in args and not self.calibration_loading_generally_supported:
                # Loading/clearing calibration not supported
                # Don't actually do it, pretend we were successful
                if "-V" in args:
                    self.output.append("IS loaded")
                self.retcode = 0
                return True
        if asroot:
            silent = False
        measure_cmds = (
            get_argyll_utilname("dispcal"),
            get_argyll_utilname("dispread"),
            get_argyll_utilname("spotread"),
        )
        process_cmds = (
            get_argyll_utilname("collink"),
            get_argyll_utilname("colprof"),
            get_argyll_utilname("targen"),
        )
        # Run commands through wexpect.spawn instead of subprocess.Popen if
        # any of these conditions apply
        use_pty = (
            args
            and "-?" not in args
            and (use_pty or cmdname in measure_cmds + process_cmds)
        )
        self.measure_cmd = "-?" not in args and cmdname in measure_cmds
        report_current_cal = cmdname == get_argyll_utilname("dispcal") and (
            "-r" in args or "-z" in args
        )
        if self.measure_cmd and not dry_run and sys.platform not in ("darwin", "win32"):
            # Inhibit session to prevent screensaver/powersaving etc.
            # Useful commands to figure out list of DBus interfaces:
            # dbus-send [--session|--system] \
            #   --dest=org.freedesktop.DBus  \
            #   --type=method_call           \
            #   --print-reply                \
            #   /org/freedesktop/DBus        \
            #   org.freedesktop.DBus.ListNames
            if dbus_session:
                desktop = os.getenv("XDG_CURRENT_DESKTOP", "").split(":")
                inhibit_reason = "Display device measurements"
                gnome_sm = "org.gnome.SessionManager"
                gnome_sm_xid = 0
                # GNOME SessionManager.Inhibit flags:
                # 1 Inhibit logging out
                # 2 Inhibit user switching
                # 4 Inhibit suspending
                # 8 Inhibit idle
                gnome_sm_flags = 1 | 2 | 4 | 8
                ifaces = getattr(self, "dbus_ifaces", None)
                if not ifaces:
                    ifaces = dict(
                        [
                            (
                                gnome_sm,
                                {
                                    "args": (
                                        gnome_sm_xid,
                                        inhibit_reason,
                                        gnome_sm_flags,
                                    ),
                                    "uninhibit": "uninhibit",
                                },
                            ),
                            ("org.freedesktop.ScreenSaver", {"precedence": [gnome_sm]}),
                            (
                                "org.freedesktop.PowerManagement.Inhibit",
                                {"precedence": [gnome_sm]},
                            ),
                        ]
                    )
                    self.dbus_ifaces = ifaces
                for bus_name in ifaces:
                    iface_dict = ifaces[bus_name]
                    if bus_name.startswith("org.freedesktop."):
                        skip = False
                        for precedence in iface_dict.get("precedence", []):
                            if ifaces[precedence].get("cookie"):
                                # Already took care of inhibit
                                skip = True
                                break
                        if skip:
                            continue
                    else:
                        iface_domain = bus_name.split(".")[1]
                        if iface_domain.upper() not in desktop:
                            # Not current desktop environment
                            continue
                    object_path = "/" + bus_name.replace(".", "/")
                    other_path = iface_dict.get("path")
                    if other_path:
                        if other_path.startswith("/"):
                            object_path = other_path
                        else:
                            object_path += "/" + other_path
                    if not iface_dict.get("cookie"):
                        try:
                            iface = iface_dict.get("iface")
                            if not iface:
                                iface = DBusObject(
                                    BUSTYPE_SESSION, bus_name, object_path
                                )
                            cookie = iface.inhibit(
                                appname, *iface_dict.get("args", (inhibit_reason,))
                            )
                        except DBusException as exception:
                            self.log(exception)
                        else:
                            iface_dict["iface"] = iface
                            iface_dict["cookie"] = cookie
                            self.log(appname + ": Inhibited " + bus_name)
            else:
                self.log(
                    appname + ": Warning - no D-Bus session bus - "
                    "cannot inhibit session, screensaver/powersaving may "
                    "still be active!"
                )
        profiling_inhibit = False
        display_profile = None
        if (
            sys.platform not in ("darwin", "win32")
            and self.measure_cmd
            and self._use_patternwindow
            and not dry_run
            and not report_current_cal
        ):
            # Preliminary Wayland support. This still needs a lot
            # of work as Argyll doesn't support Wayland natively yet,
            # so we use virtual display to drive our own patch window.
            # We need to make sure videoLUT is linear. Only way to
            # achieve this currently under Wayland is by using colord.

            # Inhibit display device to reset videoLUT to linear and profile
            # to none
            device_id = self.get_device_id(query=True)
            object_path = None
            if device_id:
                try:
                    object_path = colord.get_object_path(device_id, "device")
                except colord.CDError as exception:
                    self.log(exception)
            else:
                self.log(
                    appname + ": Warning - couldn't get display device ID - "
                    "cannot inhibit display device!"
                )
            if dbus_system and object_path:
                # Use DBus interface to call ProfilingInhibit()
                try:
                    cd_device = colord.Device(object_path)
                    cd_device.profiling_inhibit()
                except (colord.CDError, DBusException) as exception:
                    self.log(exception)
                else:
                    profiling_inhibit = True
                    self.log(appname + ": Inhibited display device", object_path)
            elif object_path:
                self.log(
                    appname + ": Warning - no D-Bus system bus - "
                    "cannot inhibit display device!"
                )
            if not profiling_inhibit:
                # Fallback - install linear cal sRGB profile
                self.log(appname + ": Temporarily installing sRGB profile...")
                display_profile = config.get_display_profile()
                self.srgb = srgb = ICCP.ICCProfile.from_named_rgb_space("sRGB")
                # Date should not change so the ID stays the same.
                srgb.dateTime = datetime.datetime(2003, 0o1, 23, 0, 0, 0)
                srgb.tags.vcgt = ICCP.VideoCardGammaTableType("", "vcgt")
                srgb.tags.vcgt.update(
                    {
                        "channels": 3,
                        "entryCount": 256,
                        "entrySize": 1,
                        "data": [
                            list(range(0, 256)),
                            list(range(0, 256)),
                            list(range(0, 256)),
                        ],
                    }
                )
                srgb.setDescription(appname + " Linear Calibration sRGB Profile")
                srgb.calculateID()
                srgb.write(
                    os.path.join(
                        self.tempdir, appname + " Linear Calibration sRGB Profile.icc"
                    )
                )
                cdinstall = self._attempt_install_profile_colord(srgb)
                if not cdinstall:
                    return Error(lang.getstr("calibration.reset_error"))
                elif isinstance(cdinstall, Exception):
                    return UnloggedError(safe_str(cdinstall))
                self.log(appname + ": Successfully assigned sRGB profile")
        self.use_patterngenerator = (
            self.measure_cmd
            and cmdname != get_argyll_utilname("spotread")
            and (
                config.get_display_name() == "Resolve"
                or (
                    config.get_display_name() == "Prisma"
                    and not defaults["patterngenerator.prisma.argyll"]
                )
                or self._use_patternwindow
            )
        )
        use_3dlut_override = (
            (
                (
                    self.use_patterngenerator
                    and config.get_display_name(None, True) == "Prisma"
                )
                or (
                    config.get_display_name(None, True) == "madVR"
                    and (sys.platform != "win32" or not getcfg("madtpg.native"))
                )
            )
            and cmdname == get_argyll_utilname("dispread")
            and "-V" in args
        )
        if use_3dlut_override:
            args.remove("-V")
        working_basename = None
        if args and args[-1].find(os.path.sep) > -1:
            working_basename = os.path.basename(args[-1])
            if cmdname not in (
                get_argyll_utilname("dispcal"),
                get_argyll_utilname("dispread"),
                get_argyll_utilname("colprof"),
                get_argyll_utilname("targen"),
                get_argyll_utilname("txt2ti3"),
            ):
                # Last arg is with extension
                working_basename = os.path.splitext(working_basename)[0]
            if working_dir is None:
                working_dir = os.path.dirname(args[-1])
        if working_dir is None:
            if self.use_patterngenerator:
                working_dir = self.create_tempdir()
            else:
                working_dir = self.tempdir
        if working_dir and not os.path.isdir(working_dir):
            working_dir = None
        if working_dir and working_dir == self.tempdir:
            # Get a list of files in the temp directory and their modification
            # times so we can determine later if anything has changed and we
            # should keep the files in case of errors
            for filename in os.listdir(working_dir):
                self.tmpfiles[filename] = os.stat(
                    os.path.join(working_dir, filename)
                ).st_mtime
        if (
            working_basename
            and working_dir == self.tempdir
            and not silent
            and log_output
            and not dry_run
        ):
            self.set_sessionlogfile(sessionlogfile, working_basename, working_dir)
        if not silent or verbose >= 3:
            self.log("-" * 80)
            if self.sessionlogfile:
                print("Session log:", self.sessionlogfile.filename)
                print("")
        use_madvr = (
            cmdname
            in (
                get_argyll_utilname("dispcal"),
                get_argyll_utilname("dispread"),
                get_argyll_utilname("dispwin"),
            )
            and get_arg("-dmadvr", args)
            and madvr
        )
        self.use_madvr = use_madvr
        madvr_use_virtual_display = (
            use_madvr
            and self.argyll_virtual_display
            and (sys.platform != "win32" or getcfg("patterngenerator.ffp_insertion"))
        )
        if use_madvr:
            # Try to connect to running madTPG or launch a new instance
            try:
                if self.madtpg_connect():
                    # Connected
                    if (
                        isinstance(self.madtpg, madvr.MadTPG_Net)
                        or madvr_use_virtual_display
                    ):
                        # Need to handle calibration clearing/loading/saving
                        # for madVR net-protocol pure python implementation
                        cal = None
                        calfilename = None
                        profile = None
                        ramp = False
                        if cmdname == get_argyll_utilname("dispwin"):
                            if "-c" in args:
                                # Clear calibration
                                self.log("MadTPG_Net clear calibration")
                                ramp = None
                            if "-L" in args:
                                # NOTE: Hmm, profile will be None. It's not
                                # functionality we currently use though.
                                profile = config.get_display_profile()
                            if "-s" in args:
                                # Save calibration. Get from madTPG
                                self.log("MadTPG_Net save calibration:", args[-1])
                                ramp = self.madtpg.get_device_gamma_ramp()
                                if not ramp:
                                    self.madtpg_disconnect(False)
                                    return Error("madVR_GetDeviceGammaRamp failed")
                                cal = """CAL

KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "DISPLAY"
KEYWORD "COLOR_REP"
COLOR_REP "RGB"
BEGIN_DATA_FORMAT
RGB_I RGB_R RGB_G RGB_B
END_DATA_FORMAT
NUMBER_OF_SETS 256
BEGIN_DATA
"""
                                # Convert ushort_Array_256_Array_3 to dictionary
                                RGB = {}
                                for j in range(3):
                                    for i in range(256):
                                        if i not in RGB:
                                            RGB[i] = []
                                        RGB[i].append(ramp[j][i] / 65535.0)
                                # Get RGB from dictionary
                                for i in RGB:
                                    R, G, B = RGB[i]
                                    cal += "%f %f %f %f\n" % (i / 255.0, R, G, B)
                                cal += "END_DATA"
                                # Write out .cal file
                                try:
                                    with open(args[-1], "w") as calfile:
                                        calfile.write(cal)
                                except OSError as exception:
                                    self.madtpg_disconnect(False)
                                    return exception
                                cal = None
                                ramp = False
                            elif working_basename:
                                # .cal/.icc/.icm file to load
                                calfilename = args[-1]
                        elif cmdname == get_argyll_utilname("dispread"):
                            # Check for .cal file to load
                            # NOTE this isn't normally used as we use -K
                            # for madTPG, but is overridable by the user
                            k_arg = get_arg("-k", args, True)
                            if k_arg:
                                calfilename = args[k_arg[0] + 1]
                            else:
                                ramp = None
                        else:
                            # dispcal
                            ramp = None
                        if calfilename:
                            # Load calibration from cal file or ICC profile
                            self.log("MadTPG_Net load calibration:", calfilename)
                            result = check_file_isfile(calfilename)
                            if isinstance(result, Exception):
                                self.madtpg_disconnect(False)
                                return result
                            if calfilename.lower().endswith(".cal"):
                                # .cal file
                                try:
                                    cal = CGATS.CGATS(calfilename)
                                except (IOError, CGATS.CGATSError) as exception:
                                    self.madtpg_disconnect(False)
                                    return exception
                            else:
                                # ICC profile
                                try:
                                    profile = ICCP.ICCProfile(calfilename)
                                except (
                                    IOError,
                                    ICCP.ICCProfileInvalidError,
                                ) as exception:
                                    self.madtpg_disconnect(False)
                                    return exception
                        if profile:
                            # Load calibration from ICC profile (if present)
                            cal = extract_cal_from_profile(profile, None, False)
                            if not cal:
                                # Linear
                                ramp = None
                        if cal:
                            # Check calibration we're going to load
                            try:
                                cal = verify_cgats(cal, ("RGB_R", "RGB_G", "RGB_B"))
                                if len(cal.DATA) != 256:
                                    # Needs to have 256 entries
                                    raise CGATS.CGATSError(
                                        "%s: %s != 256"
                                        % (
                                            lang.getstr("calibration"),
                                            lang.getstr("number_of_entries"),
                                        )
                                    )
                            except CGATS.CGATSError as exception:
                                self.madtpg_disconnect(False)
                                return exception
                            # Convert calibration to ushort_Array_256_Array_3
                            ramp = ((ctypes.c_ushort * 256) * 3)()
                            for i in range(256):
                                for j, channel in enumerate("RGB"):
                                    ramp[j][i] = int(
                                        round(cal.DATA[i]["RGB_" + channel] * 65535)
                                    )
                    else:
                        ramp = None
                    if ramp is not False and not self.madtpg.set_device_gamma_ramp(
                        ramp
                    ):
                        self.madtpg_disconnect(False)
                        return Error("madVR_SetDeviceGammaRamp failed")
                    if (
                        isinstance(self.madtpg, madvr.MadTPG_Net)
                        or madvr_use_virtual_display
                    ) and cmdname == get_argyll_utilname("dispwin"):
                        # For madVR net-protocol pure python implementation
                        # we are now done
                        if "-s" not in args:
                            # Only disconnect if we didn't save calibration (as
                            # part of a follow-up measurement)
                            self.madtpg_disconnect(False)
                        return True
                    if "-V" not in args and not use_3dlut_override:
                        endis = "disable"
                    else:
                        endis = "enable"
                    if not getattr(self.madtpg, endis + "_3dlut")():
                        self.madtpg_disconnect(False)
                        return Error("madVR_%s3dlut failed" % endis.capitalize())
                    fullscreen = self.madtpg.is_use_fullscreen_button_pressed()
                    if sys.platform == "win32":
                        # Make sure interactive display adjustment window isn't
                        # concealed by temporarily disabling fullscreen if
                        # needed. This is only a problem in single display
                        # configurations.
                        if self.single_real_display():
                            # We only have one "real" display connected
                            if cmdname == get_argyll_utilname("dispcal") or (
                                self.dispread_after_dispcal
                                and cmdname == get_argyll_utilname("dispread")
                                and self._detecting_video_levels
                            ):
                                if (
                                    getcfg("calibration.interactive_display_adjustment")
                                    and not getcfg("calibration.update")
                                    and fullscreen
                                ):
                                    # Disable fullscreen
                                    if self.madtpg.set_use_fullscreen_button(False):
                                        self.log(
                                            "Temporarily leaving madTPG " "fullscreen"
                                        )
                                        self.madtpg_previous_fullscreen = fullscreen
                                    else:
                                        self.log(
                                            "Warning - couldn't "
                                            "temporarily leave madTPG "
                                            "fullscreen"
                                        )
                            elif (
                                getattr(self, "madtpg_previous_fullscreen", None)
                                and cmdname == get_argyll_utilname("dispread")
                                and self.dispread_after_dispcal
                            ):
                                # Restore fullscreen
                                if self.madtpg.set_use_fullscreen_button(True):
                                    self.log("Restored madTPG fullscreen")
                                    self.madtpg_previous_fullscreen = None
                                else:
                                    self.log(
                                        "Warning - couldn't restore "
                                        "madTPG fullscreen"
                                    )
                    self.madtpg_fullscreen = (
                        self.madtpg.is_use_fullscreen_button_pressed()
                    )
                    # IMPORTANT: When making changes to the instrument on screen
                    # detection, also apply them to appropriate part in
                    # Worker.check_instrument_place_on_screen
                    if (
                        (
                            not (
                                cmdname == get_argyll_utilname("dispwin")
                                or self.dispread_after_dispcal
                            )
                            or (
                                cmdname == get_argyll_utilname("dispcal")
                                and ("-m" in args or "-u" in args)
                            )
                            or self._detecting_video_levels
                        )
                        and self.madtpg_fullscreen
                        and not self.instrument_on_screen
                    ):
                        # Show place instrument on screen message with countdown
                        countdown = 15
                        # We need to show the progress bar to make OSD visible
                        if not self.madtpg.show_progress_bar(countdown):
                            self.madtpg_disconnect()
                            return Error("madVR_ShowProgressBar failed")
                        self.madtpg_osd = (
                            not self.madtpg.is_disable_osd_button_pressed()
                        )
                        if not self.madtpg_osd:
                            # Enable OSD if disabled
                            if self.madtpg.set_disable_osd_button(False):
                                self.log(
                                    "Temporarily enabled madTPG OSD for "
                                    "instrument placement countdown"
                                )
                            else:
                                self.log(
                                    "Warning - couldn't temporarily "
                                    "enable madTPG OSD"
                                )
                        for i in range(countdown):
                            if self.subprocess_abort:
                                break
                            if not self.madtpg.set_osd_text(
                                lang.getstr(
                                    "instrument.place_on_screen.madvr",
                                    (countdown - i, self.get_instrument_name()),
                                )
                            ):
                                self.madtpg_disconnect()
                                return Error("madVR_SetOsdText failed")
                            ts = time()
                            if i % 2 == 0:
                                # Flash test area red
                                self.madtpg.show_rgb(0.25, 0.10, 0.10)
                            else:
                                self.madtpg.show_rgb(0.15, 0.15, 0.15)
                            delay = time() - ts
                            if delay < 1:
                                sleep(1 - delay)
                        self.instrument_on_screen = True
                        if not self.madtpg_osd:
                            # Disable OSD
                            if self.madtpg.set_disable_osd_button(True):
                                self.log(
                                    "Restored madTPG 'Disable OSD' button " "state"
                                )
                                self.madtpg_osd = None
                            else:
                                self.log(
                                    "Warning - could not restore madTPG "
                                    "'Disable OSD' button state"
                                )
                        self.madtpg.set_osd_text("\u25b6")  # "Play" symbol
                        self.madtpg.show_rgb(0.5, 0.5, 0.5)
                    # Get black and white level
                    self.madtpg_bw_lvl = self.madtpg.get_black_and_white_level()
                    if not self.madtpg_bw_lvl:
                        self.log("madVR_GetBlackAndWhiteLevel failed")
                    else:
                        self.log("Output levels: %s-%s" % self.madtpg_bw_lvl)
                    # Get pattern config
                    patternconfig = self.madtpg.get_pattern_config()
                    if (
                        not patternconfig
                        or not isinstance(patternconfig, tuple)
                        or len(patternconfig) != 4
                    ):
                        self.madtpg_disconnect()
                        return Error("madVR_GetPatternConfig failed")
                    self.log("Pattern area: %i%%" % patternconfig[0])
                    self.log("Background level: %i%%" % patternconfig[1])
                    self.log(
                        "Background mode: %s"
                        % {0: "Constant", 1: "APL gamma", 2: "APL linear"}.get(
                            patternconfig[2], patternconfig[2]
                        )
                    )
                    self.log("Border width: %i pixels" % patternconfig[3])
                    if (
                        isinstance(self.madtpg, madvr.MadTPG_Net)
                        or madvr_use_virtual_display
                    ):
                        dindex = args.index("-dmadvr")
                        args.remove("-dmadvr")
                        if madvr_use_virtual_display:
                            args.insert(dindex, "-d%s" % self.argyll_virtual_display)
                        else:
                            args.insert(0, "-P1,1,0.01")
                    else:
                        # Only if using native madTPG implementation!
                        if not get_arg("-P", args):
                            # Setup patch size to match pattern config
                            args.insert(0, "-P0.5,0.5,%f" % math.sqrt(patternconfig[0]))
                        if not patternconfig[1] and self.argyll_version >= [1, 7]:
                            # Setup black background if background level is zero.
                            # Only do this for Argyll >= 1.7 to prevent messing
                            # with pattern area when Argyll 1.6.x is used
                            args.insert(0, "-F")
                    self.log("")
                else:
                    return Error(lang.getstr("madtpg.launch.failure"))
            except Exception as exception:
                if isinstance(getattr(self, "madtpg", None), madvr.MadTPG_Net) or (
                    getattr(self, "madtpg", None) and madvr_use_virtual_display
                ):
                    self.madtpg_disconnect()
                return exception
        # Use mad* net protocol pure python implementation
        use_madnet = use_madvr and (
            isinstance(self.madtpg, madvr.MadTPG_Net) or madvr_use_virtual_display
        )
        # Use mad* net protocol pure python implementation as pattern generator
        self.use_madnet_tpg = use_madnet and cmdname != get_argyll_utilname("dispwin")
        if self.use_patterngenerator or self.use_madnet_tpg:
            # Run a dummy command so we can grab the RGB numbers for
            # the pattern generator from the output
            carg = get_arg("-C", args, True)
            if carg:
                index = min(carg[0] + 1, len(args) - 1)
                args[index] += " && "
            else:
                args.insert(0, "-C")
                args.insert(1, "")
                index = 1
            python, pythonpath = get_python_and_pythonpath()
            script_dir = working_dir
            pythonscript = WAIT_FILE_TEMPLATE.format(script_dir=script_dir)
            waitfilename = os.path.join(script_dir, ".wait")
            if sys.platform == "win32":
                # Avoid problems with encoding
                python = win32api.GetShortPathName(python)
                for i, path in enumerate(pythonpath):
                    if os.path.exists(path):
                        pythonpath[i] = win32api.GetShortPathName(path)
                # Write out .wait.py file
                scriptfilename = f"{waitfilename}.py"
                with open(scriptfilename, "w", encoding="utf-8") as scriptfile:
                    scriptfile.write(pythonscript)
                scriptfilename = win32api.GetShortPathName(scriptfilename)
                # Write out .wait.cmd file
                with open(f"{waitfilename}.cmd", "w", encoding="utf-8") as waitfile:
                    waitfile.write("@echo off\n")
                    waitfile.write("echo.\n")
                    waitfile.write("echo Current RGB %*\n")
                    waitfile.write(
                        'set "PYTHONPATH=%s"\n'
                        % safe_str(os.pathsep.join(pythonpath), enc)
                    )
                    waitfile.write(
                        '"%s" -S "%s" %%*\n'
                        % (safe_str(python, enc), safe_str(scriptfilename, enc))
                    )
                args[index] += waitfilename
            else:
                # Write out .wait file
                with open(waitfilename, "w") as waitfile:
                    waitfile.write(f"#!/usr/bin/env python3\n{pythonscript}")
                os.chmod(waitfilename, 0o755)
                args[index] += "%s ./%s" % (
                    strtr(safe_str(python), {'"': r"\"", "$": r"\$"}),
                    os.path.basename(waitfilename),
                )
        if verbose >= 1 or not silent:
            if not silent or verbose >= 3:
                if not silent and dry_run and not self.cmdrun:
                    print(lang.getstr("dry_run"))
                    print("")
                    self.cmdrun = True
                if working_dir:
                    self.log(lang.getstr("working_dir"))
                    indent = "  "
                    for name in working_dir.split(os.path.sep):
                        self.log(
                            textwrap.fill(
                                name + os.path.sep,
                                80,
                                expand_tabs=False,
                                replace_whitespace=False,
                                initial_indent=indent,
                                subsequent_indent=indent,
                            )
                        )
                        indent += " "
                    self.log("")
                self.log(lang.getstr("commandline"))
                printcmdline(cmd, args, fn=self.log, cwd=working_dir)
                self.log("")
                if not silent and dry_run:
                    if not self.lastcmdname or self.lastcmdname == cmdname:
                        print(lang.getstr("dry_run.end"))
                    if self.owner and hasattr(self.owner, "infoframe_toggle_handler"):
                        wx.CallAfter(self.owner.infoframe_toggle_handler, show=True)
                    if use_madnet:
                        self.madtpg_disconnect()
                    return UnloggedInfo(lang.getstr("dry_run.info"))
        cmdline = [cmd] + args
        for i, item in enumerate(cmdline):
            if i > 0 and item.find(os.path.sep) > -1:
                if sys.platform == "win32":
                    item = make_win32_compatible_long_path(item)
                    if (
                        re.search(r"[^\x20-\x7e]", os.path.basename(item))
                        and os.path.exists(item)
                        and i < len(cmdline) - 1
                    ):
                        # Avoid problems with encoding under Windows by using
                        # GetShortPathName, but be careful with the last
                        # parameter which may be used as the basename for the
                        # output file
                        item = win32api.GetShortPathName(item)
                if working_dir and os.path.dirname(cmdline[i]) == working_dir:
                    # Strip the path from all items in the working dir
                    item = os.path.basename(item)
                if item != cmdline[i]:
                    cmdline[i] = item
        if (
            working_dir
            and sys.platform == "win32"
            and re.search(r"[^\x20-\x7e]", working_dir)
            and os.path.exists(working_dir)
        ):
            # Avoid problems with encoding
            working_dir = win32api.GetShortPathName(working_dir)
        sudo = None
        if asroot and (
            (sys.platform != "win32" and os.geteuid() != 0)
            or (sys.platform == "win32" and sys.getwindowsversion() >= (6,))
        ):
            if sys.platform == "win32":
                # Vista and later
                pass
            else:
                if not self.auth_timestamp:
                    if hasattr(self, "thread") and self.thread.is_alive():
                        # Careful: We can only show the auth dialog if running
                        # in the main GUI thread!
                        if use_madnet:
                            self.madtpg_disconnect()
                        return Error("Authentication requested in non-GUI thread")
                    result = self.authenticate(cmd, title, parent)
                    if result is False:
                        if use_madnet:
                            self.madtpg_disconnect()
                        return None
                    elif isinstance(result, Exception):
                        if use_madnet:
                            self.madtpg_disconnect()
                        return result
                sudo = str(self.sudo)
        if sudo:
            if not use_pty:
                # Sudo may need a tty depending on configuration
                use_pty = True
            cmdline.insert(0, sudo)
            if (
                cmdname == get_argyll_utilname("dispwin")
                and sys.platform != "darwin"
                and self.sudo.availoptions.get("E")
                and getcfg("sudo.preserve_environment")
            ):
                # Preserve environment so $DISPLAY is set
                cmdline.insert(1, "-E")
            if not use_pty:
                cmdline.insert(1, "-S")
                # Set empty string as password prompt to hide it from stderr
                cmdline.insert(1, "")
                cmdline.insert(1, "-p")
            else:
                # Use a designated prompt
                cmdline.insert(1, "Password:")
                cmdline.insert(1, "-p")
        if (
            working_dir
            and working_basename
            and not skip_scripts
            and not getcfg("skip_scripts")
        ):
            try:
                cmdfilename = os.path.join(
                    working_dir, working_basename + "." + cmdname + script_ext
                )
                allfilename = os.path.join(
                    working_dir, working_basename + ".all" + script_ext
                )
                first = not os.path.exists(allfilename)
                last = cmdname == get_argyll_utilname("dispwin")
                cmdfile = open(cmdfilename, "w")
                allfile = open(allfilename, "a")
                cmdfiles = Files((cmdfile, allfile))
                if first:
                    context = cmdfiles
                else:
                    context = cmdfile
                if sys.platform == "win32":
                    context.write("@echo off\n")
                    context.write(
                        ("PATH %s;%%PATH%%\n" % os.path.dirname(cmd)).encode(
                            enc, "safe_asciize"
                        )
                    )
                    cmdfiles.write('pushd "%~dp0"\n'.encode(enc, "safe_asciize"))
                    if cmdname in (
                        get_argyll_utilname("dispcal"),
                        get_argyll_utilname("dispread"),
                    ):
                        cmdfiles.write("color 07\n")
                else:
                    context.write(
                        ("PATH=%s:$PATH\n" % os.path.dirname(cmd)).encode(
                            enc, "safe_asciize"
                        )
                    )
                    if sys.platform == "darwin" and config.mac_create_app:
                        cmdfiles.write('pushd "`dirname ' '\\"$0\\"`/../../.."\n')
                    else:
                        cmdfiles.write('pushd "`dirname \\"$0\\"`"\n')
                    if (
                        cmdname
                        in (
                            get_argyll_utilname("dispcal"),
                            get_argyll_utilname("dispread"),
                        )
                        and sys.platform != "darwin"
                    ):
                        cmdfiles.write('echo -e "\\033[40;2;37m" && clear\n')
                    os.chmod(cmdfilename, 0o755)
                    os.chmod(allfilename, 0o755)
                cmdfiles.write(
                    " ".join(quote_args(cmdline))
                    .replace(cmd, cmdname)
                    .encode(enc, "safe_asciize")
                    + "\n".encode()
                )
                if sys.platform == "win32":
                    cmdfiles.write("set exitcode=%errorlevel%\n")
                    if cmdname in (
                        get_argyll_utilname("dispcal"),
                        get_argyll_utilname("dispread"),
                    ):
                        # Reset to default commandline shell colors
                        cmdfiles.write("color\n")
                    cmdfiles.write("popd\n")
                    cmdfiles.write("if not %exitcode%==0 exit /B %exitcode%\n")
                else:
                    cmdfiles.write("exitcode=$?\n")
                    if (
                        cmdname
                        in (
                            get_argyll_utilname("dispcal"),
                            get_argyll_utilname("dispread"),
                        )
                        and sys.platform != "darwin"
                    ):
                        # reset to default commandline shell colors
                        cmdfiles.write('echo -e "\\033[0m" && clear\n')
                    cmdfiles.write("popd\n")
                    cmdfiles.write(
                        "if [ $exitcode -ne 0 ]; " "then exit $exitcode; fi\n"
                    )
                cmdfiles.close()
                if sys.platform == "darwin":
                    if config.mac_create_app:
                        # Could also use .command file directly, but using
                        # applescript allows giving focus to the terminal
                        # window automatically after a delay
                        script = (
                            mac_terminal_do_script()
                            + mac_terminal_set_colors(do=False)
                            + [
                                "-e",
                                "set shellscript to quoted form of "
                                "(POSIX path of (path to resource "
                                '"main.command"))',
                                "-e",
                                'tell app "Terminal"',
                                "-e",
                                "do script shellscript " "in first window",
                                "-e",
                                "delay 3",
                                "-e",
                                "activate",
                                "-e",
                                "end tell",
                                "-o",
                            ]
                        )
                        # Part 1: "cmdfile"
                        appfilename = os.path.join(
                            working_dir, working_basename + "." + cmdname + ".app"
                        )
                        cmdargs = ["osacompile"] + script + [appfilename.decode()]
                        p = sp.Popen(
                            cmdargs, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE
                        )
                        p.communicate()
                        shutil.move(
                            cmdfilename,
                            appfilename + "/Contents/Resources/main.command",
                        )
                        os.chmod(
                            appfilename + "/Contents/Resources/main.command", 0o755
                        )
                        # Part 2: "allfile"
                        appfilename = os.path.join(
                            working_dir, working_basename + ".all.app"
                        )
                        cmdargs = ["osacompile"] + script + [appfilename]
                        p = sp.Popen(
                            cmdargs, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE
                        )
                        p.communicate()
                        shutil.copyfile(
                            allfilename,
                            appfilename + "/Contents/Resources/main.command",
                        )
                        os.chmod(
                            appfilename + "/Contents/Resources/main.command", 0o755
                        )
                        if last:
                            os.remove(allfilename)
            except Exception as exception:
                self.log(
                    "Warning - error during shell script creation:", str(exception)
                )
        cmdline = [safe_str(arg, fs_enc) for arg in cmdline]
        working_dir = None if not working_dir else working_dir
        try:
            if not self.measure_cmd and self.argyll_version >= [1, 2]:
                # Argyll tools will no longer respond to keys
                if debug:
                    self.log("[D] Setting ARGYLL_NOT_INTERACTIVE 1")
                os.environ["ARGYLL_NOT_INTERACTIVE"] = "1"
            elif "ARGYLL_NOT_INTERACTIVE" in os.environ:
                del os.environ["ARGYLL_NOT_INTERACTIVE"]
            if debug:
                self.log("[D] argyll_version", self.argyll_version)
                self.log(
                    "[D] ARGYLL_NOT_INTERACTIVE",
                    os.environ.get("ARGYLL_NOT_INTERACTIVE"),
                )
            if self.measure_cmd:
                if isinstance(self.measurement_sound, audio.DummySound):
                    self._init_sounds(dummy=False)
                for name, version in (
                    ("MIN_DISPLAY_UPDATE_DELAY_MS", [1, 5]),
                    ("DISPLAY_SETTLE_TIME_MULT", [1, 7]),
                ):
                    backup = os.getenv(f"ARGYLL_{name}_BACKUP")
                    value = None
                    if (
                        getcfg(f"measure.override_{name.lower()}")
                        and self.argyll_version >= version
                    ):
                        if backup is None:
                            # Backup current value if any
                            current = os.getenv(f"ARGYLL_{name}", "")
                            os.environ[f"ARGYLL_{name}_BACKUP"] = current
                        else:
                            current = backup
                        if current:
                            self.log(f"{appname}: Overriding ARGYLL_{name} {current}")
                        # Override
                        value = str(getcfg(f"measure.{name.lower()}"))
                        self.log(f"{appname}: Setting ARGYLL_{name} {value}")
                    elif backup is not None:
                        value = backup
                        del os.environ[f"ARGYLL_{name}_BACKUP"]
                        if value:
                            self.log(f"{appname}: Restoring ARGYLL_{name} {value}")
                        elif f"ARGYLL_{name}" in os.environ:
                            del os.environ[f"ARGYLL_{name}"]
                    elif f"ARGYLL_{name}" in os.environ:
                        self.log(
                            f"{appname}: ARGYLL_{name}",
                            os.getenv(f"ARGYLL_{name}"),
                        )
                    if value:
                        os.environ[f"ARGYLL_{name}"] = value
            elif cmdname in (
                get_argyll_utilname("iccgamut"),
                get_argyll_utilname("tiffgamut"),
                get_argyll_utilname("viewgam"),
                get_argyll_utilname("colprof"),
                get_argyll_utilname("collink"),
            ):
                os.environ["ARGYLL_3D_DISP_FORMAT"] = "VRML"
            if sys.platform not in ("darwin", "win32"):
                os.environ["ENABLE_COLORHUG"] = "1"
            if sys.platform == "win32":
                startupinfo = sp.STARTUPINFO()
                startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = sp.SW_HIDE
            else:
                startupinfo = None
            if not use_pty:
                data_encoding = enc
                if silent:
                    stderr = sp.STDOUT
                else:
                    stderr = tempfile.SpooledTemporaryFile()
                if capture_output:
                    stdout = tempfile.SpooledTemporaryFile()
                elif (
                    sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
                ):
                    stdout = sys.stdout
                else:
                    stdout = sp.PIPE
                if sudo:
                    stdin = tempfile.SpooledTemporaryFile()
                    stdin.write(self.pwd.encode(enc, "replace") + os.linesep)
                    stdin.seek(0)
                else:
                    stdin = sp.PIPE
            else:
                data_encoding = self.pty_encoding
                kwargs = dict(timeout=20, cwd=working_dir, env=os.environ)
                if sys.platform == "win32":
                    # FIX: stdio cp1252 vs utf-8 (cp65001) issue under Windows 10/11+
                    # os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "1"
                    kwargs["codepage"] = windll.kernel32.GetACP()
                    # As Windows' console always hard wraps at the
                    # rightmost column, increase the buffer width
                    kwargs["columns"] = 160
                stderr = None
                stdout = EncodedWriter(StringIO(), None, data_encoding)
                logfiles = []
                if (
                    hasattr(self, "thread")
                    and self.thread.is_alive()
                    and self.interactive
                    and getattr(self, "terminal", None)
                ):
                    logfiles.append(
                        FilteredStream(
                            self.terminal, discard="", triggers=self.triggers
                        )
                    )
                if log_output:
                    linebuffered_logfiles = []
                    if (
                        sys.stdout
                        and hasattr(sys.stdout, "isatty")
                        and sys.stdout.isatty()
                    ):
                        linebuffered_logfiles.append(print)
                    else:
                        linebuffered_logfiles.append(log)
                    if self.sessionlogfile:
                        linebuffered_logfiles.append(self.sessionlogfile)
                    logfiles.append(
                        LineBufferedStream(
                            FilteredStream(
                                Files(linebuffered_logfiles),
                                data_encoding,
                                discard="",
                                linesep_in="\n",
                                triggers=[],
                            )
                        )
                    )
                logfiles.append(stdout)
                if hasattr(self, "thread") and self.thread.is_alive():
                    logfiles.extend([self.recent, self.lastmsg, self])
                logfiles = Files(logfiles)
                if self.use_patterngenerator:
                    pgname = config.get_display_name()
                    self.setup_patterngenerator(logfiles)
                    if not hasattr(self.patterngenerator, "conn") and hasattr(
                        self.patterngenerator, "wait"
                    ):
                        # Wait for connection - blocking
                        self.patterngenerator.wait()
                        if hasattr(self.patterngenerator, "conn"):
                            self.patterngenerator_send(
                                (0.5,) * 3, increase_sent_count=False
                            )
                        else:
                            # User aborted before connection was established
                            return False
                    if pgname == "Prisma":
                        x, y, w, h, size = get_pattern_geometry()
                        if use_3dlut_override:
                            self.patterngenerator.enable_processing(size=size * 100)
                        else:
                            self.patterngenerator.disable_processing(size=size * 100)
            tries = 1
            while tries > 0:
                if self.subprocess_abort:
                    break
                if use_pty:
                    if (
                        self.argyll_version >= [1, 2]
                        and USE_WPOPEN
                        and os.environ.get("ARGYLL_NOT_INTERACTIVE")
                    ):
                        self.subprocess = WPopen(
                            cmdline,
                            stdin=sp.PIPE,
                            stdout=tempfile.SpooledTemporaryFile(),
                            stderr=sp.STDOUT,
                            shell=shell,
                            cwd=working_dir,
                            startupinfo=startupinfo,
                        )
                    else:
                        # Minimum Windows version: XP or Server 2003
                        if sys.platform == "win32" and sys.getwindowsversion() < (5, 1):
                            raise Error(lang.getstr("windows.version.unsupported"))

                        try:
                            self.subprocess = wexpect.spawn(
                                cmdline[0], cmdline[1:], **kwargs
                            )
                        except wexpect.ExceptionPexpect as exception:
                            self.retcode = -1
                            raise Error(str(exception))

                        if sys.platform == "darwin" and self.measure_cmd:
                            # Caffeinate (prevent sleep/screensaver)
                            caffeinate = which("caffeinate")
                            if caffeinate:
                                wait_pid = str(self.subprocess.pid)
                                try:
                                    # -d prevent idle display sleep
                                    # -i prevent idle system sleep
                                    # -w wait for process <pid> to exit
                                    caffeinated = sp.Popen(
                                        [caffeinate, "-d", "-i", "-w", wait_pid],
                                        stdin=sp.PIPE,
                                        stdout=sp.PIPE,
                                        stderr=sp.PIPE,
                                    )
                                except Exception as exception:
                                    self.log(
                                        appname + ": caffeinate could not "
                                        "be started - screensaver and "
                                        "display/system sleep may still "
                                        "occur!"
                                    )
                                    self.log(exception)
                                else:
                                    self.log(
                                        appname + ": caffeinate started, "
                                        "preventing screensaver and "
                                        "display/system sleep - waiting "
                                        "for %s (PID %s) to exit" % (cmdname, wait_pid)
                                    )

                                    def caffeinate_wait():
                                        caffeinated.wait()
                                        self.log(
                                            appname + ": caffeinate exited "
                                            "with code %s" % caffeinated.returncode
                                        )

                                    wait_thread = threading.Thread(
                                        target=caffeinate_wait
                                    )
                                    wait_thread.daemon = True
                                    wait_thread.start()
                            else:
                                self.log(
                                    appname + ": caffeinate not found - "
                                    "screensaver and display/system sleep "
                                    "may still occur!"
                                )
                        if debug >= 9 or (test and "-?" not in args):
                            self.subprocess.interact()
                    self.subprocess.logfile_read = logfiles
                    if self.measure_cmd:
                        keyhit_strs = [" or Q to ", r"8\) Exit"]
                        patterns = keyhit_strs + ["Current", r" \d+ of \d+"]
                        self.log(f"{appname}: Starting interaction with subprocess")
                    else:
                        patterns = []
                        self.log(f"{appname}: Waiting for EOF")
                    loop = 0
                    pwdsent = False
                    authfailed = False
                    eof = False
                    while 1:
                        if loop < 1 and sudo:
                            curpatterns = ["Password:"] + patterns
                        else:
                            curpatterns = patterns
                        # NOTE: Using a timeout of None can block indefinitely
                        # and prevent expect() from ever returning!
                        self.subprocess.expect(
                            curpatterns + [wexpect.EOF, wexpect.TIMEOUT], timeout=1
                        )
                        if self.subprocess.after is wexpect.EOF:
                            self.log(f"{appname}: Reached EOF (OK)")
                            break
                        elif self.subprocess.after is wexpect.TIMEOUT:
                            if not self.subprocess.isalive():
                                self.log(
                                    f"{appname}: Subprocess no longer alive (timeout)"
                                )
                                if eof:
                                    break
                                eof = True
                            continue
                        elif self.subprocess.after == "Password:" and loop < 1 and sudo:
                            if pwdsent:
                                self.subprocess.sendcontrol("C")
                                authfailed = True
                                self.auth_timestamp = 0
                            else:
                                self._safe_send(
                                    self.pwd + os.linesep,
                                    obfuscate=True,
                                )
                                pwdsent = True
                            if not self.subprocess.isalive():
                                break
                            continue
                        elif self.measure_cmd:
                            if [
                                keyhit_str
                                for keyhit_str in keyhit_strs
                                if re.search(keyhit_str, self.subprocess.after)
                            ]:
                                # Wait for the keypress
                                self.log(f"{appname}: Waiting for send buffer")
                                while not self.send_buffer:
                                    if not self.subprocess.isalive():
                                        self.log(
                                            f"{appname}: Subprocess no longer alive (unknown reason)"
                                        )
                                        break
                                    sleep(0.05)
                                self.log(
                                    f"{appname}: Send buffer received: {self.send_buffer}"
                                )
                            if (
                                self.send_buffer is not None
                                and self.subprocess.isalive()
                            ):
                                if (
                                    self.send_buffer == "7"
                                    and use_madvr
                                    and cmdname == get_argyll_utilname("dispcal")
                                ):
                                    # Restore madTPG OSD and fullscreen
                                    self.madtpg_restore_settings(False)
                                self.log(
                                    f"{appname}: Sending buffer: {self.send_buffer}"
                                )
                                self._safe_send(self.send_buffer)
                                self.send_buffer = None
                        if not self.subprocess.isalive():
                            break
                        loop += 1
                    # We need to call isalive() to set the exitstatus.
                    # We can't use wait() because it might block in the
                    # case of a timeout
                    if self.subprocess.isalive():
                        self.log(f"{appname}: Checking subprocess status")
                        while self.subprocess.isalive():
                            sleep(0.1)
                        self.log(f"{appname}: Subprocess no longer alive (OK)")
                    self.retcode = self.subprocess.exitstatus
                    if authfailed:
                        raise Error(lang.getstr("auth.failed"))
                else:
                    try:
                        if (
                            asroot
                            and sys.platform == "win32"
                            and sys.getwindowsversion() >= (6,)
                        ):
                            p = run_as_admin(cmd, args, close_process=False, show=False)
                            while not self.subprocess_abort:
                                # Wait for subprocess to exit
                                self.retcode = win32event.WaitForSingleObject(
                                    p["hProcess"], 50
                                )
                                if not self.retcode:
                                    break
                            p["hProcess"].Close()
                            return self.retcode == 0
                        else:
                            self.subprocess = sp.Popen(
                                cmdline,
                                stdin=stdin,
                                stdout=stdout,
                                stderr=stderr,
                                shell=shell,
                                cwd=working_dir,
                                startupinfo=startupinfo,
                            )
                    except Exception as exception:
                        self.retcode = -1
                        raise Error(str(exception))
                    self.retcode = self.subprocess.wait()
                    if stdin != sp.PIPE and not getattr(stdin, "closed", True):
                        stdin.close()
                if self.is_working() and self.subprocess_abort and self.retcode == 0:
                    self.retcode = -1
                self.subprocess = None
                tries -= 1
                if not silent and stderr:
                    stderr.seek(0)
                    errors = stderr.readlines()
                    if not capture_output or stderr is not stdout:
                        stderr.close()
                    if len(errors):
                        for line in errors:
                            if isinstance(line, bytes):
                                line = line.decode()
                            line = line.strip()
                            if (
                                "Instrument Access Failed" in line
                                and "-N" in cmdline[:-1]
                            ):
                                cmdline.remove("-N")
                                tries = 1
                                break
                            if (
                                line.find("User Aborted") < 0
                                and line.find(
                                    "XRandR 1.2 is faulty - falling back "
                                    "to older extensions"
                                )
                                < 0
                            ):
                                self.errors.append(line)
                    if tries > 0 and not use_pty:
                        stderr = tempfile.SpooledTemporaryFile()
                if capture_output or use_pty:
                    stdout.seek(0)
                    stdout_readlines = stdout.readlines()
                    self.output = []
                    for line in stdout_readlines:
                        if isinstance(line, bytes):
                            line = line.decode()
                        line = line.strip()
                        line = re.sub(r"^\.{4,}\s*$", "", line).strip()
                        self.output.append(line)
                    stdout.close()
                    if len(self.output) and log_output:
                        if not use_pty:
                            self.log("".join(self.output).strip())
                        if (
                            display_output
                            and self.owner
                            and hasattr(self.owner, "infoframe_toggle_handler")
                        ):
                            wx.CallAfter(self.owner.infoframe_toggle_handler, show=True)
                    if tries > 0 and not use_pty:
                        stdout = tempfile.SpooledTemporaryFile()
                if not silent and len(self.errors):
                    errstr = "".join(self.errors).strip()
                    self.log(errstr)
        except (Error, socket.error, EnvironmentError, RuntimeError) as exception:
            return exception
        except Exception:
            if debug:
                self.log("[D] working_dir:", working_dir)

            # TODO: Fix this in the source of the problem, not here!!!
            new_cmdline = []
            for item in cmdline:
                if isinstance(item, bytes):
                    item = item.decode()
                new_cmdline.append(item)
            cmdline = new_cmdline

            errmsg = " ".join(cmdline) + "\n" + str(traceback.format_exc())
            self.retcode = -1
            return Error(errmsg)
        finally:
            if (
                sudo
                and cmdname not in ("chown", get_argyll_utilname("dispwin"))
                and working_dir
                and working_dir == self.tempdir
                and os.listdir(working_dir)
            ):
                # We need to take ownership of any files created by commands
                # run via sudo otherwise we cannot move or remove them from
                # the temporary directory!
                errors = self.errors
                output = self.output
                retcode = self.retcode
                self.exec_cmd(
                    "chown",
                    ["-R", getpass.getuser().decode(fs_enc), working_dir],
                    capture_output=capture_output,
                    skip_scripts=True,
                    asroot=True,
                )
                self.errors = errors
                self.output = output
                self.retcode = retcode
            finished = (
                (self.cmdname == "dispcal" and not self.dispread_after_dispcal)
                or (self.cmdname == "dispread" and not self._detecting_video_levels)
                or self.retcode
            )
            if self.patterngenerator:
                if hasattr(self.patterngenerator, "conn"):
                    try:
                        if config.get_display_name() == "Resolve":
                            # Send fullscreen black to prevent burn-in
                            if finished:
                                try:
                                    self.patterngenerator.send(
                                        (0,) * 3, x=0, y=0, w=1, h=1
                                    )
                                except socket.error:
                                    pass
                        else:
                            self.patterngenerator.disconnect_client()
                    except Exception as exception:
                        self.log(exception)
            if hasattr(self, "madtpg") and finished:
                self.madtpg_disconnect()
            if (
                sys.platform not in ("darwin", "win32")
                and self.measure_cmd
                and self._use_patternwindow
                and (profiling_inhibit or display_profile)
                and not report_current_cal
            ):
                # Preliminary Wayland support. This still needs a lot
                # of work as Argyll doesn't support Wayland natively yet,
                # so we use virtual display to drive our own patch window.

                # We need to restore the display profile.
                if profiling_inhibit:
                    # Use DBus interface to call ProfilingInhibit()
                    try:
                        cd_device.profiling_uninhibit()
                    except Exception as cd_exception:
                        self.log(cd_exception)
                        profiling_inhibit = False
                    else:
                        self.log(f"{appname}: Uninhibited display device")
                if not profiling_inhibit:
                    # Fallback - restore display profile
                    self.log(f"{appname}: Re-assigning display profile...")
                    cdinstall = self._attempt_install_profile_colord(display_profile)
                    if cdinstall is True:
                        self.log(f"{appname}: Successfully re-assigned display profile")
                    elif not cdinstall:
                        self.log(lang.getstr("calibration.load_error"))
                    # Remove temp sRGB profile
                    try:
                        os.remove(
                            os.path.join(
                                xdg_data_home,
                                "icc",
                                os.path.basename(self.srgb.fileName),
                            )
                        )
                    except Exception as exception:
                        self.log(exception)
        if not silent:
            self.log(cmdname, "exitcode:", self.retcode)
        if self.retcode != 0:
            if use_pty and verbose >= 1 and not silent:
                self.log(lang.getstr("aborted"))
            if use_pty and len(self.output):
                errmsg = None
                for i, line in enumerate(self.output):
                    if (
                        "Calibrate failed with 'User hit Abort Key' (No device error)"
                        in line
                    ):
                        break
                    if (
                        (
                            ": Error" in line
                            and "failed with 'User Aborted'" not in line
                            and "returned error code 1" not in line
                        )
                        or (
                            line.startswith("Failed to")
                            and "Failed to meet target" not in line
                        )
                        or (
                            "Requested ambient light capability" in line
                            and len(self.output) == i + 2
                        )
                        or (
                            "Diagnostic:" in line
                            and (
                                len(self.output) == i + 1
                                or self.output[i + 1].startswith("usage:")
                            )
                        )
                        or "communications failure" in line.lower()
                    ):
                        # "returned error code 1" == user aborted
                        if (
                            sys.platform == "win32"
                            and (
                                "config 1 failed (Operation not supported or "
                                "unimplemented on this platform) (Permissions ?)"
                            )
                            in line
                        ):
                            self.output.insert(
                                i,
                                lang.getstr("argyll.instrument.driver.missing")
                                + "\n\n"
                                + lang.getstr("argyll.error.detail")
                                + " ",
                            )
                        if "Diagnostic:" in line:
                            errmsg = line
                        else:
                            errmsg = "".join(self.output[i:])
                        startpos = errmsg.find(": Error")
                        if startpos > -1:
                            errmsg = errmsg[startpos + 2 :]
                if errmsg:
                    return UnloggedError(errmsg.strip())
        if self.exec_cmd_returnvalue is not None:
            return self.exec_cmd_returnvalue
        return self.retcode == 0

    def flush(self):
        pass

    def _generic_consumer(
        self, delayedResult, consumer, continue_next, *args, **kwargs
    ):
        # consumer must accept result as first arg
        result = None
        try:
            result = delayedResult.get()
        except Exception as exception:
            if (
                exception.__class__ is Exception
                and exception.args
                and exception.args[0] == "aborted"
            ):
                # Special case - aborted
                result = False
            elif isinstance(exception, (UntracedError, Info)):
                result = exception
            else:
                if hasattr(exception, "originalTraceback"):
                    self.log(exception.originalTraceback)
                else:
                    self.log(traceback.format_exc())
                result = UnloggedError(safe_str(exception))
        if self.progress_start_timer.IsRunning():
            self.progress_start_timer.Stop()
        self.finished = True
        if not continue_next or isinstance(result, Exception) or not result:
            self.stop_progress()
        self.subprocess_abort = False
        self.thread_abort = False
        self.recent.clear()
        self.lastmsg.clear()
        if self.thread.is_alive():
            # Consumer may check if thread is still alive. Technically
            # it shouldn't be at that point when using CallAfter, but e.g. on
            # OS X there seems to be overlap with the thread counting as
            # 'alive' even though it already exited
            self.thread.join()
        wx.CallAfter(consumer, result, *args, **kwargs)

    def generate_A2B0(self, profile, clutres=None, logfile=None):

        # Lab cLUT is currently not implemented and should NOT be used!
        if profile.connectionColorSpace != b"XYZ":
            raise Error(
                lang.getstr(
                    "profile.unsupported",
                    (profile.connectionColorSpace, profile.connectionColorSpace),
                )
            )

        if logfile:
            print("-" * 80)
            logfile.write("Creating perceptual A2B0 table\n")
            logfile.write("\n")
        # Make new A2B0
        A2B0 = ICCP.LUT16Type(None, "A2B0", profile)
        # Matrix (identity)
        A2B0.matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        # Input / output curves (linear)
        A2B0.input = []
        A2B0.output = []
        channel = []
        for j in range(256):
            channel.append(j * 257)
        for table in (A2B0.input, A2B0.output):
            for i in range(3):
                table.append(channel)
        # cLUT
        if logfile:
            logfile.write("Generating A2B0 table lookup input values...\n")
        A2B0.clut = []
        if not clutres:
            clutres = len(profile.tags.A2B0.clut[0])
        if logfile:
            logfile.write("cLUT grid res: %i\n" % clutres)
        vrange = range(clutres)
        step = 1.0 / (clutres - 1.0)
        idata = []
        for R in vrange:
            for G in vrange:
                for B in vrange:
                    idata.append([v * step for v in (R, G, B)])
        if logfile:
            logfile.write("Looking up input values through A2B0 table...\n")
        odata = self.xicclu(profile, idata, pcs="x", logfile=logfile)
        numrows = len(odata)
        if numrows != clutres**3:
            raise ValueError(
                "Number of cLUT entries (%s) exceeds cLUT res "
                "maximum (%s^3 = %s)" % (numrows, clutres, clutres**3)
            )
        XYZbp = list(odata[0])
        XYZwp = list(odata[-1])
        if logfile:
            logfile.write("Filling cLUT...\n")
        for i, (X, Y, Z) in enumerate(odata):
            if i % clutres == 0:
                if self.thread_abort:
                    raise Info(lang.getstr("aborted"))
                A2B0.clut.append([])
                if logfile:
                    logfile.write("\r%i%%" % round(i / (numrows - 1.0) * 100))
            # Apply black point compensation
            XYZ = colormath.blend_blackpoint(X, Y, Z, XYZbp)
            XYZ = [v / XYZwp[1] for v in XYZ]
            A2B0.clut[-1].append([max(v * 32768, 0) for v in XYZ])
        if logfile:
            logfile.write("\n")
        profile.tags.A2B0 = A2B0
        return True

    def generate_B2A_from_inverse_table(
        self,
        profile,
        clutres=None,
        source="A2B",
        tableno=None,
        bpc=False,
        smooth=True,
        rgb_space=None,
        logfile=None,
        filename=None,
        only_input_curves=False,
    ):
        """Generate a profile's B2A table by inverting the A2B table
        (default A2B1 or A2B0)

        It is also possible to re-generate a B2A table by interpolating
        the B2A table itself.
        """

        if tableno is None:
            if "A2B1" in profile.tags:
                tableno = 1
            else:
                tableno = 0
        if not clutres:
            if "B2A%i" % tableno in profile.tags:
                tablename = "B2A%i" % tableno
            else:
                tablename = "A2B%i" % tableno
            clutres = len(profile.tags[tablename].clut[0])

        if source == "B2A" and clutres > 23:
            # B2A interpolation is smoothest when used with a lower cLUT res
            clutres = 23

        if logfile:
            if source == "A2B":
                msg = "Generating B2A%i table by inverting A2B%i table\n" % (
                    tableno,
                    tableno,
                )
            else:
                msg = "Re-generating B2A%i table by interpolation\n" % tableno
            logfile.write(msg)
            logfile.write("\n")

        cat = profile.guess_cat() or "Bradford"
        self.log("Using chromatic adaptation transform matrix:", cat)

        # Note that intent 0 will be colorimetric if no other tables are
        # present
        intent = {0: "p", 1: "r", 2: "s"}[tableno]

        # Lookup RGB -> XYZ for primaries, black- and white point
        idata = [[0, 0, 0], [1, 1, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1]]

        direction = {"A2B": "f", "B2A": "ib"}[source]
        odata = self.xicclu(profile, idata, intent, direction, pcs="x")

        # Scale to Y = 1
        XYZwp_abs = odata[1]
        XYZwpY = odata[1][1]
        odata = [[n / XYZwpY for n in v] for v in odata]

        XYZbp = odata[0]
        XYZwp = odata[1]
        XYZr = odata[2]
        XYZg = odata[3]
        XYZb = odata[4]

        # Sanity check whitepoint
        if (
            round(XYZwp[0], 3) != 0.964
            or round(XYZwp[1], 3) != 1
            or round(XYZwp[2], 3) != 0.825
        ):
            raise Error(
                "Argyll CMS xicclu: Invalid white XYZ: "
                "%.4f %.4f %.4f" % tuple(XYZwp_abs)
            )

        # Get the primaries
        XYZrgb = [XYZr, XYZg, XYZb]

        # Sanity check primaries:
        # Red Y, Z shall not be higher than X
        # Green X, Z shall not be higher than Y
        # Blue X, Y shall not be higher than Z
        for i, XYZ in enumerate(XYZrgb):
            for j, v in enumerate(XYZ):
                if v > XYZ[i]:
                    raise Error(
                        "xicclu: Invalid primary %s XYZ: "
                        "%.4f %.4f %.4f" % (("RGB"[i],) + tuple(XYZ))
                    )

        if logfile:
            logfile.write("Black XYZ: %.4f %.4f %.4f\n" % tuple(XYZbp))
            logfile.write("White XYZ: %.4f %.4f %.4f\n" % tuple(XYZwp))
            for i in range(3):
                logfile.write(
                    "%s XYZ: %.4f %.4f %.4f\n" % (("RGB"[i],) + tuple(XYZrgb[i]))
                )

        # Prepare input PCS values
        if logfile:
            logfile.write("Generating input curve PCS values...\n")
        idata = []
        numentries = 4096
        maxval = numentries - 1.0
        vrange = range(numentries)
        Lbp, abp, bbp = colormath.XYZ2Lab(*[v * 100 for v in XYZbp])
        # Method to determine device <-> PCS neutral axis relationship
        # 0: L* (a*=b*=0) -> RGB
        # 1: As method 0, but blend a* b* to blackpoint hue
        # 2: R=G=B -> PCS
        # 3: As method 0, but blend a* b* to blackpoint hue in XYZ (BPC)
        method = 2
        if method != 2:
            for i in vrange:
                L, a, b = i / maxval * 100, 0, 0
                if method in (1, 3) and not bpc and XYZbp != [0, 0, 0]:
                    # Blend to blackpoint hue
                    if method == 1:
                        vv = (L - Lbp) / (100.0 - Lbp)  # 0 at bp, 1 at wp
                        vv = 1.0 - vv
                        if vv < 0.0:
                            vv = 0.0
                        elif vv > 1.0:
                            vv = 1.0
                        vv = math.pow(vv, 40.0)
                        a += vv * abp
                        b += vv * bbp
                    else:
                        X, Y, Z = colormath.Lab2XYZ(L, a, b)
                        XYZ = colormath.blend_blackpoint(X, Y, Z, None, XYZbp)
                        a, b = colormath.XYZ2Lab(*[v * 100 for v in XYZ])[1:]
                idata.append((L, a, b))

        pcs = profile.connectionColorSpace[0:1].lower().decode("utf-8")
        if source == "B2A":
            # NOTE:
            # Argyll's B2A tables are slightly inaccurate:
            # 0 0 0 PCS -> RGB may give RGB levels > 0 (it should clip
            # instead). Inversely, 0 0 0 RGB -> PCS (through inverted B2A)
            # will return PCS values that are too low or zero (ie. not the
            # black point as expected)

            # TODO: How to deal with this?
            # TODO: Erkan Ozgur Yilmaz, please do a research for this issue.
            pass

        if method == 2:
            # lookup RGB -> XYZ values through profile using xicclu to get TRC
            odata = []
            if not bpc:
                numentries -= 1
                maxval -= 1
            for i in range(numentries):
                odata.append([i / maxval] * 3)
            idata = self.xicclu(
                profile, odata, intent, {"A2B": "f", "B2A": "ib"}[source], pcs="x"
            )
            wY = idata[-1][1]
            idata = [[v[1] / wY * n for n in XYZwp] for v in idata]
            # Input curve maps neutral (except near black) XYZ -> RGB
            idata = [
                list(
                    colormath.blend_blackpoint(
                        *v, bp_in=idata[0], bp_out=XYZbp, wp=XYZwp
                    )
                )
                for v in idata
            ]
            if not bpc:
                numentries += 1
                maxval += 1
                idata.insert(0, [0, 0, 0])
                odata.insert(0, [0, 0, 0])
            oXYZ = idata
            D50 = colormath.get_whitepoint("D50")
            fpL = [colormath.XYZ2Lab(*v + [D50])[0] for v in oXYZ]
        else:
            oXYZ = [colormath.Lab2XYZ(*v) for v in idata]
            fpL = [v[0] for v in idata]
        fpX = [v[0] for v in oXYZ]
        fpY = [v[1] for v in oXYZ]
        fpZ = [v[2] for v in oXYZ]

        if method != 2 and bpc and XYZbp != [0, 0, 0]:
            if logfile:
                logfile.write("Applying BPC to input curve PCS values...\n")
            for i, (L, a, b) in enumerate(idata):
                X, Y, Z = colormath.Lab2XYZ(L, a, b)
                X, Y, Z = colormath.blend_blackpoint(X, Y, Z, None, XYZbp)
                idata[i] = colormath.XYZ2Lab(X * 100, Y * 100, Z * 100)

        if logfile:
            logfile.write("Looking up input curve RGB values...\n")

        direction = {"A2B": "if", "B2A": "b"}[source]

        if method != 2:
            # Lookup Lab -> RGB values through profile using xicclu to get TRC
            odata = self.xicclu(
                profile, idata, intent, direction, pcs="l", get_clip=True
            )

            # Deal with values that got clipped (below black as well as white)
            do_low_clip = True
            for i, values in enumerate(odata):
                if values[3] is True or i == 0:
                    if do_low_clip and (i / maxval * 100 < Lbp or i == 0):
                        # Set to black
                        self.log(
                            "Setting curve entry #%i (%.6f %.6f %.6f) to "
                            "black because it got clipped" % ((i,) + tuple(values[:3]))
                        )
                        values[:] = [0.0, 0.0, 0.0]
                    elif i == maxval and [round(v, 4) for v in values[:3]] == [1, 1, 1]:
                        # Set to white
                        self.log(
                            "Setting curve entry #%i (%.6f %.6f %.6f) to "
                            "white because it got clipped" % ((i,) + tuple(values[:3]))
                        )
                        values[:] = [1.0, 1.0, 1.0]
                else:
                    # First non-clipping value disables low clipping
                    do_low_clip = False
                if len(values) > 3:
                    values.pop()

            # Sanity check white
            if (
                round(odata[-1][0], 3) != 1
                or round(odata[-1][1], 3) != 1
                or round(odata[-1][2], 3) != 1
            ):
                wrgb_warning = (
                    "Warning: xicclu: Suspicious white "
                    "RGB: %.4f %.4f %.4f\n" % tuple(odata[-1])
                )
                if logfile:
                    logfile.write(wrgb_warning)
                else:
                    print(wrgb_warning)

        xpR = [v[0] for v in odata]
        xpG = [v[1] for v in odata]
        xpB = [v[2] for v in odata]

        # Initialize B2A
        if only_input_curves:
            # Use existing B2A table
            itable = profile.tags["B2A%i" % tableno]
        else:
            # Create new B2A table
            itable = ICCP.LUT16Type(None, "B2A%i" % tableno, profile)

        use_cam_clipping = True

        # Setup matrix
        scale = 1 + (32767 / 32768.0)
        m3 = colormath.Matrix3x3(((scale, 0, 0), (0, scale, 0), (0, 0, scale)))

        matrices = []

        if profile.connectionColorSpace == b"Lab":
            # L*a*b* LUT
            # Use identity matrix for Lab as mandated by ICC spec
            itable.matrix = colormath.Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
            m2 = None
        elif only_input_curves:
            # Use existing matrix
            m2 = itable.matrix * m3.inverted()

            # Scale for BPC
            XYZbp_relcol = self.xicclu(profile, [[0, 0, 0]], pcs="x")[0]
            XYZbp_relcol_D50 = [v * XYZbp_relcol[1] for v in XYZwp]
            m2i = m2.inverted()
            XYZrgb = [m2i * (1, 0, 0), m2i * (0, 1, 0), m2i * (0, 0, 1)]
            for i, XYZ in enumerate(XYZrgb):
                XYZrgb[i] = colormath.apply_bpc(
                    *XYZ, bp_in=(0, 0, 0), bp_out=XYZbp_relcol_D50, wp_out=XYZwp
                )
        else:
            # Use a matrix that scales the profile colorspace into the XYZ
            # encoding range, to make optimal use of the cLUT grid points

            xyYrgb = [colormath.XYZ2xyY(*XYZ) for XYZ in XYZrgb]
            area1 = 0.5 * abs(
                sum(
                    x0 * y1 - x1 * y0
                    for ((x0, y0, Y0), (x1, y1, Y1)) in zip(
                        xyYrgb, xyYrgb[1:] + [xyYrgb[0]]
                    )
                )
            )

            if logfile:
                logfile.write("Setting up matrix\n")

            # RGB spaces used as PCS candidates.
            # Six synthetic RGB spaces that are large enough to encompass
            # display gamuts (except the LaserVue one) found on
            # http://www.tftcentral.co.uk/articles/pointers_gamut.htm
            # aswell as a selection of around two dozen profiles from openSUSE
            # ICC Profile Taxi database aswell as other user contributions
            rgb_spaces = []

            rgb = [
                ("R", (1.0, 0.0, 0.0)),
                ("G", (0.0, 1.0, 0.0)),
                ("B", (0.0, 0.0, 1.0)),
            ]

            # Add matrix from just white + 50% gray + black + primaries
            # as first entry
            # outname = os.path.splitext(profile.fileName)[0]
            # if not os.path.isfile(outname + ".ti3"):
            # if isinstance(profile.tags.get("targ"), ICCP.Text):
            # with open(outname + ".ti3", "wb") as ti3:
            # ti3.write(profile.tags.targ)
            # else:
            # ti1name = "ti1/d3-e4-s2-g28-m0-b0-f0.ti1"
            # ti1 = get_data_path(ti1name)
            # if not ti1:
            # raise Error(lang.getstr("file.missing", ti1name))
            # ti1, ti3, gray = self.ti1_lookup_to_ti3(ti1, profile,
            # intent="a",
            # white_patches=1)
            # outname += "." + ti1name
            # ti3.write(outname + ".ti3")
            # result = self._create_matrix_profile(outname, omit="TRC")
            result = True
            if isinstance(result, Exception) or not result:
                if logfile:
                    logfile.write("Warning - could not compute RGBW matrix")
                    if result:
                        logfile.write(": " + str(result))
                    else:
                        logfile.write("\n")
            else:
                comp_rgb_space = [2.2, "D50"]
                # Oversaturate primaries to add headroom
                wx, wy = colormath.XYZ2xyY(*XYZwp)[:2]
                # Determine saturation factor by looking at distance between
                # Rec. 2020 blue and actual blue primary
                bx, by, bY = colormath.XYZ2xyY(
                    *colormath.adapt(
                        *colormath.RGB2XYZ(0, 0, 1, "Rec. 2020"),
                        whitepoint_source="D65",
                        cat=cat,
                    )
                )
                bx2, by2, bY2 = xyYrgb[2]
                bu, bv = colormath.xyY2Lu_v_(bx, by, bY)[1:]
                bu2, bv2 = colormath.xyY2Lu_v_(bx2, by2, bY2)[1:]
                dist = math.sqrt((bx - bx2) ** 2 + (by - by2) ** 2)
                sat = 1 + math.ceil(dist * 100) / 100.0
                if logfile:
                    logfile.write(
                        "Increasing saturation of actual "
                        "primaries for PCS candidate to "
                        "%i%%...\n" % round(sat * 100)
                    )
                for i, channel in enumerate("rgb"):
                    # x, y, Y = result.tags[channel + "XYZ"].pcs.xyY
                    x, y, Y = xyYrgb[i]
                    if logfile:
                        logfile.write(channel.upper() + " xy %.6f %.6f -> " % (x, y))
                    x, y, Y = colormath.xyYsaturation(x, y, Y, wx, wy, sat)
                    if logfile:
                        logfile.write("%.6f %.6f\n" % (x, y))
                    xyYrgb[i] = x, y, Y
                (rx, ry, rY), (gx, gy, gY), (bx, by, bY) = xyYrgb
                mtx = colormath.rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, XYZwp)
                for i, (channel, components) in enumerate(rgb):
                    X, Y, Z = mtx * components
                    comp_rgb_space.append(colormath.XYZ2xyY(X, Y, Z))
                comp_rgb_space.append("PCS candidate based on actual " "primaries")
                rgb_spaces.append(comp_rgb_space)

            # A colorspace that encompasses Rec709. Uses Rec. 2020 blue.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.68280181011, 0.315096403371, 0.224182128906],
                    [0.310096375087, 0.631250246526, 0.73258972168],
                    [0.129244796433, 0.0471357502953, 0.0432281494141],
                    "Rec709-encompassing, variant 1",
                ]
            )

            # A colorspace that encompasses Rec709. Uses slightly different
            # primaries (based on WLED and B+RG LED) than variant 1.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.664580313612, 0.329336320112, 0.228820800781],
                    [0.318985161632, 0.644740328564, 0.742568969727],
                    [0.143284983488, 0.0303535582465, 0.0286102294922],
                    "Rec709-encompassing, variant 2",
                ]
            )

            # A colorspace that encompasses Rec709 with imaginary red and blue
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.672053135694, 0.331936091367, 0.250122070312],
                    [0.319028093312, 0.644705491217, 0.710144042969],
                    [0.113899645442, 0.0424325604954, 0.0396270751953],
                    "Rec709-encompassing, variant 3",
                ]
            )

            # A colorspace that encompasses Rec709. Uses red and blue from
            # variant 2, but a slightly different green primary.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.664627993657, 0.329338357942, 0.244033813477],
                    [0.300155771607, 0.640946446796, 0.728302001953],
                    [0.143304213944, 0.0303410650333, 0.0276641845703],
                    "Rec709-encompassing, variant 4",
                ]
            )

            # A colorspace with Plasma-like primaries. Uses Rec. 2020 blue.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.692947816539, 0.30857396028, 0.244430541992],
                    [0.284461719244, 0.70017174365, 0.709167480469],
                    [0.129234824405, 0.0471509419335, 0.0464019775391],
                    "SMPTE-431-2/DCI-P3-encompassing, variant 1",
                ]
            )

            # A colorspace that encompasses both AdobeRGB and NTSC1953. Uses
            # Rec. 2020 blue.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.680082575358, 0.319746686121, 0.314331054688],
                    [0.200003470174, 0.730003123156, 0.641983032227],
                    [0.129238369699, 0.0471305063812, 0.0436706542969],
                    "AdobeRGB-NTSC1953-hybrid, variant 1",
                ]
            )

            # A colorspace with Plasma-like primaries. Uses Rec. 2020 blue.
            # More saturated green primary than variant 1.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.692943297796, 0.308579731457, 0.268966674805],
                    [0.249088838269, 0.730263586072, 0.684844970703],
                    [0.129230721306, 0.047147329564, 0.0461883544922],
                    "SMPTE-431-2/DCI-P3-encompassing, variant 2",
                ]
            )

            # A colorspace that encompasses both AdobeRGB and NTSC1953.
            # Different, more saturated primaries than variant 1.
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.700603882817, 0.299296301842, 0.274520874023],
                    [0.200006562972, 0.75, 0.697494506836],
                    [0.143956453416, 0.0296952711131, 0.0279693603516],
                    "AdobeRGB-NTSC1953-hybrid, variant 2",
                ]
            )

            # A colorspace that encompasses DCI P3 with imaginary red and blue
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.699964323939, 0.312334528794, 0.253814697266],
                    [0.284337791321, 0.68212854805, 0.73779296875],
                    [0.098165262763, 0.00937830372063, 0.00839233398438],
                    "SMPTE-431-2/DCI-P3-encompassing, variant 3",
                ]
            )

            # A colorspace that encompasses DCI P3 with imaginary red and blue
            # (red and blue are practically the same as Rec2020-encompassing)
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.717267960557, 0.29619267491, 0.231002807617],
                    [0.284277504105, 0.682088122605, 0.760604858398],
                    [0.0981978292034, 0.00940337224384, 0.00840759277344],
                    "SMPTE-431-2/DCI-P3-encompassing, variant 4",
                ]
            )

            # Rec. 2020
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.7084978651, 0.293540723619, 0.279037475586],
                    [0.190200063067, 0.775375775201, 0.675354003906],
                    [0.129244405192, 0.0471399056886, 0.0456085205078],
                    "Rec2020",
                ]
            )

            # A colorspace that encompasses Rec2020 with imaginary primaries
            rgb_spaces.append(
                [
                    2.2,
                    "D50",
                    [0.71715243505, 0.296225595183, 0.291244506836],
                    [0.191129060214, 0.795212673762, 0.700057983398],
                    [0.0981403936826, 0.00939694681658, 0.00869750976562],
                    "Rec2020-encompassing",
                ]
            )

            if rgb_space:
                rgb_space = list(rgb_space[:5])
                rgb_spaces = [rgb_space + ["Custom"]]

            # Find smallest candidate that encompasses space defined by actual
            # primaries
            if logfile:
                logfile.write("Checking for suitable PCS candidate...\n")
            pcs_candidate = None
            pcs_candidates = []
            XYZsrgb = []
            for channel, components in rgb:
                XYZsrgb.append(
                    colormath.adapt(
                        *colormath.RGB2XYZ(*components),
                        whitepoint_source="D65",
                        cat=cat,
                    )
                )
            XYZrgb_sequence = [XYZrgb, XYZsrgb]
            for rgb_space in rgb_spaces:
                if rgb_space[1] not in ("D50", colormath.get_whitepoint("D50")):
                    # Adapt to D50
                    for i in range(3):
                        X, Y, Z = colormath.xyY2XYZ(*rgb_space[2 + i])
                        X, Y, Z = colormath.adapt(X, Y, Z, rgb_space[1], cat=cat)
                        rgb_space[2 + i] = colormath.XYZ2xyY(X, Y, Z)
                    rgb_space[1] = "D50"

                extremes = []
                skip = False
                for XYZrgb in XYZrgb_sequence:
                    for i, color in enumerate(["red", "green", "blue"]):
                        RGB = colormath.XYZ2RGB(
                            XYZrgb[i][0],
                            XYZrgb[i][1],
                            XYZrgb[i][2],
                            rgb_space=rgb_space,
                            clamp=False,
                        )
                        maxima = max(RGB)
                        minima = min(RGB)
                        if minima < 0:
                            maxima += abs(minima)
                        if XYZrgb is XYZsrgb:
                            if maxima > 1 and color == "blue":
                                # We want our PCS candiate to contain Rec. 709
                                # blue, which may not be the case for our
                                # candidate based off the actual display
                                # primaries. Blue region is typically the one
                                # where the most artifacts would be visible in
                                # color conversions if the source blue is
                                # clipped
                                if logfile:
                                    logfile.write(
                                        "Skipping %s because it does "
                                        "not encompass Rec. 709 %s\n"
                                        % (rgb_space[-1], color)
                                    )
                                skip = True
                                break
                        else:
                            extremes.append(maxima)
                    if skip:
                        break
                if skip:
                    continue
                # Check area % (in xy for simplicity's sake)
                xyYrgb = rgb_space[2:5]
                area2 = 0.5 * abs(
                    sum(
                        x0 * y1 - x1 * y0
                        for ((x0, y0, Y0), (x1, y1, Y1)) in zip(
                            xyYrgb, xyYrgb[1:] + [xyYrgb[0]]
                        )
                    )
                )
                if logfile:
                    logfile.write(
                        "%s fit: %.2f (area: %.2f%%)\n"
                        % (
                            rgb_space[-1],
                            round(1.0 / max(extremes), 2),
                            area1 / area2 * 100,
                        )
                    )
                pcs_candidates.append((area1 / area2, 1.0 / max(extremes), rgb_space))
                # Check if tested RGB space contains actual primaries
                if round(max(extremes), 2) <= 1.0:
                    break

            XYZrgb = []
            if not pcs_candidate and False:  # NEVER?
                # Create quick medium quality shaper+matrix profile and use the
                # matrix from that
                if logfile:
                    logfile.write(
                        "No suitable PCS candidate. " "Computing best fit matrix...\n"
                    )
                # Lookup small testchart so profile computation finishes quickly
                ti1name = "ti1/d3-e4-s5-g52-m5-b0-f0.ti1"
                ti1 = get_data_path(ti1name)
                if not ti1:
                    raise Error(lang.getstr("file.missing", ti1name))
                ti1, ti3, gray = self.ti1_lookup_to_ti3(
                    ti1, profile, intent="a", white_patches=1
                )
                dirname, basename = os.path.split(profile.fileName)
                basepath = os.path.join(
                    dirname, "." + os.path.splitext(basename)[0] + "-MTX.tmp"
                )
                ti3.write(basepath + ".ti3")
                # Calculate profile
                cmd, args = get_argyll_util("colprof"), ["-v", "-qm", "-as", basepath]
                result = self.exec_cmd(
                    cmd,
                    args,
                    capture_output=True,
                    sessionlogfile=getattr(self, "sessionlogfile", None),
                )
                if isinstance(result, Exception):
                    raise result
                if result:
                    mtx = ICCP.ICCProfile(basepath + profile_ext)
                    for column in "rgb":
                        tag = mtx.tags.get(column + "XYZ")
                        if isinstance(tag, ICCP.XYZType):
                            XYZrgb.append(list(tag.values()))
                    # os.remove(basepath + ".ti3")
                    # os.remove(basepath + profile_ext)
                    if not XYZrgb:
                        raise Error(
                            lang.getstr(
                                "profile.required_tags_missing", "rXYZ/gXYZ/bXYZ"
                            )
                        )
                pcs_candidate = "BestFit"
            else:
                # If clutres is -1 (auto), set it depending on area coverage
                if clutres == -1:
                    if area1 / area2 <= 0.51:
                        clutres = 45
                    elif area1 / area2 <= 0.73:
                        clutres = 33

                # Use PCS candidate with best fit
                # (best fit is the smallest fit greater or equal 1 and
                # largest possible coverage)
                pcs_candidates.sort(key=lambda row_: (-row_[0], row_[1]))
                for coverage, fit, rgb_space in pcs_candidates:
                    if round(fit, 2) >= 1:
                        break
                if logfile:
                    logfile.write("Using primaries: %s\n" % rgb_space[-1])
                for channel, components in rgb:
                    XYZrgb.append(colormath.RGB2XYZ(*components, rgb_space=rgb_space))
                pcs_candidate = rgb_space[-1]

            for i in range(3):
                logfile.write(
                    "Using %s XYZ: %.4f %.4f %.4f\n" % (("RGB"[i],) + tuple(XYZrgb[i]))
                )

        if profile.connectionColorSpace == b"XYZ":
            # Construct the final matrix
            Xr, Yr, Zr = XYZrgb[0]
            Xg, Yg, Zg = XYZrgb[1]
            Xb, Yb, Zb = XYZrgb[2]
            if logfile:
                logfile.write(
                    "R+G+B XYZ: %.4f %.4f %.4f\n"
                    % (Xr + Xg + Xb, Yr + Yg + Yb, Zr + Zg + Zb)
                )
            m1 = colormath.Matrix3x3(
                ((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))
            ).inverted()
            matrices.append(m1)
            Sr, Sg, Sb = m1 * XYZwp
            if logfile:
                logfile.write("Correction factors: %.4f %.4f %.4f\n" % (Sr, Sg, Sb))
            m2 = colormath.Matrix3x3(
                (
                    (Sr * Xr, Sg * Xg, Sb * Xb),
                    (Sr * Yr, Sg * Yg, Sb * Yb),
                    (Sr * Zr, Sg * Zg, Sb * Zb),
                )
            ).inverted()
            matrices.append(m2)
            matrices.append(m3)

            for m, matrix in enumerate(matrices):
                if logfile:
                    logfile.write("Matrix %i:\n" % (m + 1))
                    for row in matrix:
                        logfile.write("%r\n" % row)

            itable.matrix = m2 * m3
            if logfile:
                logfile.write("Final matrix:\n")
                for row in itable.matrix:
                    logfile.write("%r\n" % row)

            if logfile:
                logfile.write("Applying matrix to input curve XYZ values...\n")
            # Apply matrix
            rX = []
            rY = []
            rZ = []
            for i in vrange:
                X, Y, Z = fpX[i], fpY[i], fpZ[i]
                X, Y, Z = m2 * (X, Y, Z)
                rX.append(X)
                rY.append(Y)
                rZ.append(Z)
            interp = (
                colormath.Interp(xpR, rX),
                colormath.Interp(xpG, rY),
                colormath.Interp(xpB, rZ),
            )
            rinterp = (
                colormath.Interp(rX, xpR),
                colormath.Interp(rY, xpG),
                colormath.Interp(rZ, xpB),
            )
            Linterp = None
        else:
            Lscale = 65280.0 / 65535.0
            oldmin = (xpR[0] + xpG[0] + xpB[0]) / 3.0
            oldmax = (xpR[-1] + xpG[-1] + xpB[-1]) / 3.0
            oldrange = oldmax - oldmin
            newmin = 0.0
            newmax = 100
            newrange = newmax - newmin
            xpL = []
            for i in vrange:
                v = (xpR[i] + xpG[i] + xpB[i]) / 3.0
                v = max((((v - oldmin) * newrange) / oldrange) + newmin, 0)
                xpL.append(v)
            Linterp = colormath.Interp(xpL, fpL)
            rLinterp = colormath.Interp(fpL, xpL)
            interp = None
        # Set input curves
        # Apply inverse TRC to input values to distribute them
        # optimally across cLUT grid points
        if logfile:
            logfile.write("Generating input curves...\n")
        itable.input = [[], [], []]
        for j in vrange:
            if self.thread_abort:
                raise Info(lang.getstr("aborted"))
            if profile.connectionColorSpace == b"XYZ":
                v = [rinterp[i](j / maxval) for i in range(3)]
            else:
                # CIELab PCS encoding
                v = [rLinterp(j / (maxval * Lscale) * 100) / 100.0]
                v.extend([j / maxval] * 2)
            for i in range(len(itable.input)):
                itable.input[i].append(min(v[i] * 65535, 65535))
            if logfile and j % math.floor(maxval / 100.0) == 0:
                logfile.write("\r%i%%" % round(j / maxval * 100))
        if logfile:
            logfile.write("\n")
        if False and method and not bpc:
            # Force the blackpoint - NEVER
            if logfile:
                logfile.write("Forcing B2A input curve blackpoint...\n")
            XYZbp_m = m2 * XYZbp
            for i in range(3):
                black_index = int(math.ceil(maxval * XYZbp_m[i]))
                if logfile:
                    logfile.write("Channel #%i\n" % i)
                for j in range(black_index + 1):
                    v = 0
                    if logfile:
                        logfile.write("#%i %i -> %i\n" % (j, itable.input[i][j], v))
                    itable.input[i][j] = v

        if only_input_curves:
            # We are done
            return True

        if clutres == -1:
            # Auto
            if pcs == "l" and smooth:
                # Counteract L*a*b* cLUT accuracy loss when smoothing.
                # With a res of 45, about the same accuracy as when using
                # colprof B2A with a res of 33 and no smoothing.
                # This is not necessary with XYZ cLUT as the accuracy is always
                # higher than colprof baseline due to restricting the XYZ space
                # with a matrix.
                clutres = 45
            else:
                clutres = 33
        step = 1.0 / (clutres - 1.0)
        do_lookup = True
        if do_lookup:
            # Generate inverse table lookup input values

            # Use slightly less than equal the amount of CPUs for workers
            # for best utilization (each worker has 2 xicclu sub-processes)
            num_cpus = cpu_count()
            num_workers = min(max(num_cpus, 1), clutres)
            if num_cpus > 2:
                num_workers = int(num_workers * 0.75)

            if logfile:
                logfile.write(
                    "Generating %s%i table lookup input values...\n" % (source, tableno)
                )
                logfile.write("cLUT grid res: %i\n" % clutres)
                logfile.write(
                    "Looking up input values through %s%i table (%i workers)...\n"
                    % (source, tableno, num_workers)
                )
                logfile.write(
                    "%s CAM Jab for clipping\n"
                    % (use_cam_clipping and "Using" or "Not using")
                )

            idata = []
            odata1 = []
            odata2 = []

            threshold = int((clutres - 1) * 0.75)
            threshold2 = int((clutres - 1) / 3)

            for slices in pool_slice(
                _mp_generate_B2A_clut,
                list(range(clutres)),
                (
                    profile.fileName,
                    intent,
                    direction,
                    pcs,
                    use_cam_clipping,
                    clutres,
                    step,
                    threshold,
                    threshold2,
                    interp,
                    Linterp,
                    m2,
                    XYZbp,
                    XYZwp,
                    bpc,
                    lang.getstr("aborted"),
                ),
                {},
                num_workers,
                self.thread_abort,
                logfile,
                num_batches=clutres // 9,
            ):
                for i, data in enumerate((idata, odata1, odata2)):
                    data.extend(slices[i])

            if logfile:
                logfile.write("\n")
            if logfile and (pcs == "x" or clutres // 2 != clutres / 2.0):
                if pcs == "x":
                    iXYZbp = idata[0]
                    iXYZwp = idata[-1]
                    logfile.write("Input black XYZ: %s\n" % iXYZbp)
                    logfile.write("Input white XYZ: %s\n" % iXYZwp)
                else:
                    iLabbp = idata[clutres * (clutres // 2) + clutres // 2]
                    iLabwp = idata[
                        (
                            clutres**2 * (clutres - 1)
                            + clutres * (clutres // 2)
                            + clutres // 2
                        )
                    ]
                    logfile.write("Input black L*a*b*: %s\n" % iLabbp)
                    logfile.write("Input white L*a*b*: %s\n" % iLabwp)

            if not use_cam_clipping:
                odata = odata1
            elif pcs == "l":
                odata = odata2
            else:
                # Linearly interpolate the crossover to CAM Jab clipping region
                cam_diag = False
                odata = []
                j, k = 0, 0
                r = float(threshold - threshold2)
                for a in range(clutres):
                    for b in range(clutres):
                        for c in range(clutres):
                            if a <= threshold and b <= threshold and c <= threshold:
                                v = odata1[j]
                                j += 1
                                if a > threshold2 or b > threshold2 or c > threshold2:
                                    d = max(a, b, c)
                                    if cam_diag:
                                        v = [100.0, 100.0, 0.0]
                                        v2 = [0.0, 100.0, 100.0]
                                    else:
                                        v2 = odata2[k]
                                    k += 1
                                    for i, n in enumerate(v):
                                        v[i] *= (threshold - d) / r
                                        v2[i] *= 1 - (threshold - d) / r
                                        v[i] += v2[i]
                            else:
                                if cam_diag:
                                    v = [100.0, 0.0, 100.0]
                                else:
                                    v = odata2[k]
                                k += 1
                            odata.append(v)
            numrows = len(odata)
            if numrows != clutres**3:
                raise ValueError(
                    "Number of cLUT entries (%s) exceeds cLUT res "
                    "maximum (%s^3 = %s)" % (numrows, clutres, clutres**3)
                )
            if logfile and (pcs == "x" or clutres // 2 != clutres / 2.0):
                if pcs == "x":
                    oRGBbp = odata[0]
                    oRGBwp = odata[-1]
                else:
                    oRGBbp = odata[clutres * (clutres // 2) + clutres // 2]
                    oRGBwp = odata[
                        (
                            clutres**2 * (clutres - 1)
                            + clutres * (clutres // 2)
                            + clutres // 2
                        )
                    ]
                logfile.write("Output black RGB: %.4f %.4f %.4f\n" % tuple(oRGBbp))
                logfile.write("Output white RGB: %.4f %.4f %.4f\n" % tuple(oRGBwp))
            odata = [[n / 100.0 for n in v] for v in odata]

        # Fill cCLUT
        itable.clut = []
        if logfile:
            logfile.write("Filling cLUT...\n")
        if not do_lookup:
            # Linearly scale RGB
            for R in range(clutres):
                if self.thread_abort:
                    raise Info(lang.getstr("aborted"))
                for G in range(clutres):
                    itable.clut.append([])
                    for B in range(clutres):
                        itable.clut[-1].append([v * step * 65535 for v in (R, G, B)])
                    if logfile:
                        logfile.write(
                            "\r%i%%" % round((R * G * B) / ((clutres - 1.0) ** 3) * 100)
                        )
        else:
            for i, RGB in enumerate(odata):
                if i % clutres == 0:
                    if self.thread_abort:
                        raise Info(lang.getstr("aborted"))
                    itable.clut.append([])
                    if logfile:
                        logfile.write("\r%i%%" % round(i / (numrows - 1.0) * 100))
                # Set RGB black and white explicitly
                if pcs == "x":
                    if i == 0:
                        RGB = 0, 0, 0
                    elif i == numrows - 1.0:
                        RGB = 1, 1, 1
                elif clutres // 2 != clutres / 2.0:
                    # For CIELab cLUT, white- and black point will only
                    # fall on a cLUT point if uneven cLUT res
                    if i == clutres * (clutres // 2) + clutres // 2:
                        # if raw_input("%i %r" % (i, RGB)):
                        RGB = 0, 0, 0
                    elif i == (
                        clutres**2 * (clutres - 1)
                        + clutres * (clutres // 2)
                        + clutres // 2
                    ):
                        # if raw_input("%i %r" % (i, RGB)):
                        RGB = 1, 1, 1
                itable.clut[-1].append([v * 65535 for v in RGB])
        if logfile:
            logfile.write("\n")

        if getcfg("profile.b2a.hires.diagpng") and filename:
            # Generate diagnostic images
            fname, ext = os.path.splitext(filename)
            for suffix, table in [
                ("pre", profile.tags.get("B2A%i" % tableno)),
                ("post", itable),
            ]:
                if table:
                    table.clut_writepng(
                        fname + ".B2A%i.%s.CLUT.png" % (tableno, suffix)
                    )

        # Update profile
        profile.tags["B2A%i" % tableno] = itable

        if method == 2:
            if logfile:
                logfile.write("Generating output curves...\n")
            # Output curve maps <clutres> RGB to <numentries> RGB
            # Lookup neutral (except near black) XYZ -> RGB
            oRGB = self.xicclu(
                profile,
                oXYZ,
                intent,
                {"A2B": "if", "B2A": "b"}[source],
                pcs="x",
                get_clip=True,
            )

            # Deal with values that got clipped (below black as well as white)
            do_low_clip = True
            for i, values in enumerate(oRGB):
                if values[3] is True or i == 0:
                    if do_low_clip:
                        # Set to black
                        self.log(
                            "Setting curve entry #%i (%.6f %.6f %.6f) to "
                            "black because it got clipped" % ((i,) + tuple(values[:3]))
                        )
                        values[:] = [0.0, 0.0, 0.0]
                    elif i == maxval and [round(v, 4) for v in values[:3]] == [1, 1, 1]:
                        # Set to white
                        self.log(
                            "Setting curve entry #%i (%.6f %.6f %.6f) to "
                            "white because it got clipped" % ((i,) + tuple(values[:3]))
                        )
                        values[:] = [1.0, 1.0, 1.0]
                else:
                    # First non-clipping value disables low clipping
                    do_low_clip = False
                if len(values) > 3:
                    values.pop()

            ocurves = [[], [], []]
            for i, RGB in enumerate(oRGB):
                for j, v in enumerate(RGB):
                    ocurves[j].append(v)
            ointerp = []
            for i, ocurve in enumerate(ocurves):
                olen = len(ocurve)
                ointerp_i = colormath.Interp(
                    [j / (olen - 1.0) for j in range(olen)], ocurve, use_numpy=True
                )
                ocurve_i = [ointerp_i(j / (clutres - 1.0)) for j in range(clutres)]
                ocurve_i = colormath.interp_resize(
                    ocurve_i, len(ocurve), use_numpy=True
                )
                ointerp_o = colormath.Interp(ocurve_i, ocurve, use_numpy=True)
                ointerp.append(ointerp_o)

        # Set output curves
        itable.output = [[], [], []]
        numentries = 256
        maxval = numentries - 1.0
        for i in range(len(itable.output)):
            for j in range(numentries):
                v = j / maxval
                if method == 2:
                    v = ointerp[i](v)
                itable.output[i].append(v * 65535)

        if smooth:
            self.smooth_B2A(
                profile, tableno, getcfg("profile.b2a.hires.diagpng"), filename, logfile
            )

        return True

    def smooth_B2A(self, profile, tableno, diagpng=2, filename=None, logfile=None):
        """Apply extra smoothing to the cLUT"""
        itable = profile.tags.get("B2A%i" % tableno)
        if not itable:
            return False
        itable.smooth2(diagpng, profile.connectionColorSpace, filename, logfile)
        return True

    def get_device_id(
        self,
        quirk=False,
        use_serial_32=True,
        truncate_edid_strings=False,
        omit_manufacturer=False,
        query=False,
    ):
        """Get org.freedesktop.ColorManager device key"""
        if not self.display_edid or config.is_virtual_display():
            return None
        display_no = max(0, min(len(self.displays) - 1, getcfg("display.number") - 1))
        edid = self.display_edid[display_no]
        if not edid:
            # Fall back to XrandR name
            if not (
                not quirk
                and use_serial_32
                and not truncate_edid_strings
                and not omit_manufacturer
            ):
                return
            if RDSMM:
                display = RDSMM.get_display(display_no)
                if display:
                    xrandr_name = display.get("xrandr_name")
                    if xrandr_name:
                        edid = {"monitor_name": xrandr_name}
                    elif os.getenv("XDG_SESSION_TYPE") == "wayland":
                        # Preliminary Wayland support under non-GNOME desktops.
                        # This still needs a lot of work.
                        device_ids = colord.get_display_device_ids()
                        if device_ids and display_no < len(device_ids):
                            return device_ids[display_no]
        return colord.device_id_from_edid(
            edid,
            quirk=quirk,
            use_serial_32=use_serial_32,
            truncate_edid_strings=truncate_edid_strings,
            omit_manufacturer=omit_manufacturer,
            query=query,
        )

    def get_display(self):
        """Get the currently configured display.

        Returned is the Argyll CMS dispcal/dispread -d argument
        """
        display_name = config.get_display_name(None, True)
        if display_name == "Web @ localhost":
            return "web:%i" % getcfg("webserver.portnumber")
        if display_name == "madVR":
            return "madvr"
        if display_name == "Untethered":
            return "0"
        if display_name == "Resolve":
            if (
                self.argyll_virtual_display
                # and os.getenv("XDG_SESSION_TYPE") == "wayland"
            ):
                return self.argyll_virtual_display
            else:
                return "1"
        if display_name == "Prisma" and not defaults["patterngenerator.prisma.argyll"]:
            if self.argyll_virtual_display:
                return self.argyll_virtual_display
            else:
                return "1"
        if display_name == "Prisma":
            host = getcfg("patterngenerator.prisma.host")
            try:
                host = socket.gethostbyname(host)
            except socket.error:
                pass
            return "prisma:%s" % host
        if display_name.startswith("Chromecast "):
            return "cc:%s" % display_name.split(":")[0].split(None, 1)[1].strip()
        if display_name.startswith("Prisma "):
            return "prisma:%s" % display_name.split("@")[-1].strip()
        if self._use_patternwindow:
            # Preliminary Wayland support. This still needs a lot
            # of work as Argyll doesn't support Wayland natively,
            # so we use virtual display to drive our own patch window.
            return self.argyll_virtual_display
        display_no = min(len(self.displays), getcfg("display.number")) - 1
        display = str(display_no + 1)
        if (
            (sys.platform not in ("darwin", "win32") or test)
            and (self.has_separate_lut_access() or getcfg("use_separate_lut_access"))
            and (
                not getcfg("display_lut.link")
                or (display_no > -1 and not self.lut_access[display_no])
            )
        ):
            display_lut_no = min(len(self.displays), getcfg("display_lut.number")) - 1
            if display_lut_no > -1 and not self.lut_access[display_lut_no]:
                for display_lut_no, disp in enumerate(self.lut_access):
                    if disp:
                        break
            display += "," + str(display_lut_no + 1)
        return display

    def get_display_edid(self):
        """Return EDID of currently configured display"""
        n = getcfg("display.number") - 1
        if 0 <= n < len(self.display_edid):
            return self.display_edid[n]
        return {}

    def get_display_name(
        self, prepend_manufacturer=False, prefer_edid=False, remove_manufacturer=True
    ):
        """Return name of currently configured display"""
        n = getcfg("display.number") - 1
        if 0 <= n < len(self.display_names):
            display = []
            manufacturer = None
            display_name = None
            if prefer_edid:
                edid = self.get_display_edid()
                manufacturer = edid.get("manufacturer")
                display_name = edid.get(
                    "monitor_name", edid.get("ascii", str(edid.get("product_id") or ""))
                )
            if not manufacturer:
                manufacturer = self.display_manufacturers[n]
            if not display_name:
                display_name = self.display_names[n]
            if manufacturer:
                manufacturer = colord.quirk_manufacturer(manufacturer)
                if prepend_manufacturer:
                    if manufacturer.lower() not in display_name.lower():
                        display.append(manufacturer)
                elif remove_manufacturer:
                    start = display_name.lower().find(manufacturer.lower())
                    if start > -1:
                        display_name = (
                            display_name[:start]
                            + display_name[start + len(manufacturer) :]
                        ).lstrip()
                        display_name = re.sub(r"^[^([{\w]+", "", display_name)
            display.append(display_name)
            return " ".join(display)
        return ""

    def get_display_name_short(self, prepend_manufacturer=False, prefer_edid=False):
        """Return shortened name of configured display (if possible)

        If name can't be shortened (e.g. because it's already 10 characters
        or less), return full string
        """
        display_name = self.get_display_name(prepend_manufacturer, prefer_edid)
        if len(display_name) > 10:
            maxweight = 0
            for part in re.findall(
                r"[^\s_]+(?:\s*\d+)?", re.sub(r"\([^)]+\)", "", display_name)
            ):
                digits = re.search(r"\d+", part)
                if digits:
                    # Weigh parts with digits higher than those without
                    chars = re.sub(r"\d+", "", part)
                    weight = len(chars) + len(digits.group()) * 5
                else:
                    # Weigh parts with uppercase letters higher than those without
                    chars = ""
                    for char in part:
                        if char.lower() != char:
                            chars += char
                    weight = len(chars)
                if chars and weight >= maxweight:
                    # Weigh parts further to the right higher
                    display_name = re.sub(r"^[^([{\w]+", "", part)
                    maxweight = weight

        # Shortname should not contain any spaces.
        display_name = re.sub(r"[\s]+", "_", display_name)
        return display_name

    def get_dispwin_display_profile_argument(self, display_no=0):
        """Return argument corresponding to the display profile for use with dispwin.

        Will either return '-L' (use current profile) or a filename.
        """
        arg = "-L"
        try:
            profile = ICCP.get_display_profile(display_no)
        except Exception as exception:
            print(exception)
            return arg
        else:
            if not profile:
                return arg
            if profile.fileName:
                prefix = os.path.basename(profile.fileName)
            else:
                prefix = (
                    make_filename_safe(profile.getDescription(), concat=False)
                    + profile_ext
                )
            prefix += "-"
        if profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
            print(
                "\n".join(
                    [lang.getstr("profile.iccv4.unsupported"), profile.getDescription()]
                )
            )
        elif not profile.fileName:
            fd, profile.fileName = tempfile.mkstemp("", prefix)
            stream = os.fdopen(fd, "wb")
            profile.write(stream)
            stream.close()
            atexit.register(os.remove, profile.fileName)
        return profile.fileName or arg

    def update_display_name_manufacturer(
        self, ti3, display_name=None, display_manufacturer=None, write=True
    ):
        """Update display name and manufacturer in colprof arguments
        embedded in 'ARGYLL_COLPROF_ARGS' section in a TI3 file."""
        options_colprof = []
        if not display_name and not display_manufacturer:
            # Note: Do not mix'n'match display name and manufacturer from
            # different sources
            try:
                ti3_options_colprof = get_options_from_ti3(ti3)[1]
            except (
                IOError,
                CGATS.CGATSInvalidError,
                CGATS.CGATSInvalidOperationError,
                CGATS.CGATSKeyError,
                CGATS.CGATSTypeError,
                CGATS.CGATSValueError,
            ) as exception:
                print(exception)
                ti3_options_colprof = []
            for option in ti3_options_colprof:
                if option[0] == "M":
                    display_name = option.split(None, 1)[-1][1:-1]
                elif option[0] == "A":
                    display_manufacturer = option.split(None, 1)[-1][1:-1]
        if not display_name and not display_manufacturer:
            # Note: Do not mix'n'match display name and manufacturer from
            # different sources
            edid = self.display_edid[
                max(0, min(len(self.displays), getcfg("display.number")) - 1)
            ]
            display_name = edid.get(
                "monitor_name", edid.get("ascii", str(edid.get("product_id") or ""))
            )
            display_manufacturer = edid.get("manufacturer")
        if not display_name and not display_manufacturer:
            # Note: Do not mix'n'match display name and manufacturer from
            # different sources
            display_name = self.get_display_name()
        if display_name:
            options_colprof.append("-M")
            options_colprof.append(display_name)
        if display_manufacturer:
            options_colprof.append("-A")
            options_colprof.append(display_manufacturer)
        if write:
            # Add dispcal and colprof arguments to ti3
            if is_ccxx_testchart():
                options_dispcal = []
            else:
                options_dispcal = self.options_dispcal
            ti3 = add_options_to_ti3(ti3, options_dispcal, options_colprof)
            if ti3:
                ti3.write()
        return options_colprof

    def get_instrument_features(self, instrument_name=None):
        """Return features of currently configured instrument"""
        features = all_instruments.get(
            instrument_name or self.get_instrument_name(), {}
        )
        if test_require_sensor_cal:
            features["sensor_cal"] = True
            features["skip_sensor_cal"] = False
        return features

    def get_instrument_measurement_modes(
        self, instrument_id=None, skip_ccxx_modes=True
    ):
        """Enumerate measurement modes supported by the instrument"""
        if not instrument_id:
            features = self.get_instrument_features()
            instrument_id = features.get("id", self.get_instrument_name())
        if instrument_id:
            measurement_modes = self.measurement_modes.get(instrument_id, dict())
            if not measurement_modes:
                result = self.exec_cmd(
                    get_argyll_util("spotread"),
                    ["-?"],
                    capture_output=True,
                    skip_scripts=True,
                    silent=True,
                    log_output=False,
                )
                if isinstance(result, Exception):
                    print(result)
                # Need to get and remember output of spotread because calling
                # self.get_technology_strings() will overwrite self.output
                output = self.output
                if test:
                    output.extend(
                        """Measure spot values, Version 1.7.0_beta
Author: Graeme W. Gill, licensed under the GPL Version 2 or later
Diagnostic: Usage requested
usage: spotread [-options] [logfile]
 -v                   Verbose mode
 -s                   Print spectrum for each reading
 -S                   Plot spectrum for each reading
 -c listno            Set communication port from the following list (default 1)
    1 = 'COM13 (Klein K-10)'
    2 = 'COM1'
    3 = 'COM3'
    4 = 'COM4'
 -t                   Use transmission measurement mode
 -e                   Use emissive measurement mode (absolute results)
 -eb                  Use display white brightness relative measurement mode
 -ew                  Use display white point relative chromatically adjusted mode
 -p                   Use telephoto measurement mode (absolute results)
 -pb                  Use projector white brightness relative measurement mode
 -pw                  Use projector white point relative chromatically adjusted mode
 -a                   Use ambient measurement mode (absolute results)
 -f                   Use ambient flash measurement mode (absolute results)
 -y F                  K-10: Factory Default [Default,CB1]
    c                  K-10: Default CRT File
    P                  K-10: Klein DLP Lux
    E                  K-10: Klein SMPTE C
    b                  K-10: TVL XVM245
    d                  K-10: Klein LED Bk LCD
    m                  K-10: Klein Plasma
    p                  K-10: DLP Screen
    o                  K-10: TVL LEM150
    O                  K-10: Sony EL OLED
    z                  K-10: Eizo CG LCD
    L                  K-10: FSI 2461W
    h                  K-10: HP DreamColor 2
    1                  K-10: LCD CCFL Wide Gamut IPS (LCD2690WUXi)
    l|c                Other: l = LCD, c = CRT
 -I illum             Set simulated instrument illumination using FWA (def -i illum):
                       M0, M1, M2, A, C, D50, D50M2, D65, F5, F8, F10 or file.sp]
 -i illum             Choose illuminant for computation of CIE XYZ from spectral data & FWA:
                       A, C, D50 (def.), D50M2, D65, F5, F8, F10 or file.sp
 -Q observ            Choose CIE Observer for spectral data or CCSS instrument:
                      1931_2 (def), 1964_10, S&B 1955_2, shaw, J&V 1978_2
                      (Choose FWA during operation)
 -F filter            Set filter configuration (if aplicable):
    n                  None
    p                  Polarising filter
    6                  D65
    u                  U.V. Cut
 -E extrafilterfile   Apply extra filter compensation file
 -x                   Display Yxy instead of Lab
 -h                   Display LCh instead of Lab
 -V                   Show running average and std. devation from ref.
 -T                   Display correlated color temperatures and CRI
 -N                   Disable auto calibration of instrument
 -O                   Do one cal. or measure and exit
 -H                   Start in high resolution spectrum mode (if available)
 -X file.ccmx         Apply Colorimeter Correction Matrix
 -Y r|n               Override refresh, non-refresh display mode
 -Y R:rate            Override measured refresh rate with rate Hz
 -Y A                 Use non-adaptive integration time mode (if available).
 -W n|h|x             Override serial port flow control: n = none, h = HW, x = Xon/Xoff
 -D [level]           Print debug diagnostics to stderr
 logfile              Optional file to save reading results as text""".splitlines()
                    )
                measurement_modes_follow = False
                technology_strings = self.get_technology_strings()
                for line in output:
                    line = line.strip()
                    if line.startswith("-y "):
                        line = line.lstrip("-y ")
                        measurement_modes_follow = True
                    elif line.startswith("-"):
                        measurement_modes_follow = False
                    parts = [v.strip() for v in line.split(None, 1)]
                    if measurement_modes_follow and len(parts) == 2:
                        measurement_mode, desc = parts
                        if measurement_mode not in (
                            string.digits[1:] + string.ascii_letters
                        ):
                            # Ran out of selectors
                            continue
                        measurement_mode_instrument_id, desc = desc.split(":", 1)
                        desc = desc.strip()
                        if measurement_mode_instrument_id == instrument_id:
                            # Found a mode for our instrument
                            if (
                                re.sub(r"\s*\(.*?\)?$", "", desc)
                                in list(technology_strings.values()) + [""]
                                and skip_ccxx_modes
                            ):
                                # This mode is supplied via CCMX/CCSS, skip
                                continue
                            desc = re.sub(r"\s*(?:File|\[[^\]]*\])", "", desc)
                            measurement_modes[measurement_mode] = desc
                self.measurement_modes[instrument_id] = measurement_modes
            return measurement_modes
        return {}

    def get_instrument_name(self):
        """Return name of currently configured instrument"""
        try:
            return self.instruments[getcfg("comport.number") - 1]
        except IndexError:
            return ""

    def get_real_displays(self):
        """Get real (nonvirtual) displays"""
        real_displays = []
        for display_no in range(len(self.displays)):
            if not config.is_virtual_display(display_no):
                real_displays.append(display_no)
        return real_displays

    def get_technology_strings(self):
        """Return technology strings mapping (from ccxxmake -??)"""
        if self.argyll_version < [1, 7]:
            # Argyll ccxxmake before V1.7 didn't have the ability to list
            # dtechs with -??
            # Argyll V1.7 had different keys (we still want to use those for
            # V1.7) with some duplicates
            # Use Argyll V1.7.1 mapping (which has no duplicate keys) for
            # Argyll before V1.7
            return dict(
                [
                    ("c", "CRT"),
                    ("m", "Plasma"),
                    ("l", "LCD"),
                    ("1", "LCD CCFL"),
                    ("2", "LCD CCFL IPS"),
                    ("3", "LCD CCFL VPA"),
                    ("4", "LCD CCFL TFT"),
                    ("L", "LCD CCFL Wide Gamut"),
                    ("5", "LCD CCFL Wide Gamut IPS"),
                    ("6", "LCD CCFL Wide Gamut VPA"),
                    ("7", "LCD CCFL Wide Gamut TFT"),
                    ("e", "LCD White LED"),
                    ("8", "LCD White LED IPS"),
                    ("9", "LCD White LED VPA"),
                    ("d", "LCD White LED TFT"),
                    ("b", "LCD RGB LED"),
                    ("f", "LCD RGB LED IPS"),
                    ("g", "LCD RGB LED VPA"),
                    ("i", "LCD RGB LED TFT"),
                    ("h", "LCD RG Phosphor"),
                    ("j", "LCD RG Phosphor IPS"),
                    ("k", "LCD RG Phosphor VPA"),
                    ("n", "LCD RG Phosphor TFT"),
                    ("o", "LED OLED"),
                    ("a", "LED AMOLED"),
                    ("p", "DLP Projector"),
                    ("q", "DLP Projector RGB Filter Wheel"),
                    ("r", "DPL Projector RGBW Filter Wheel"),
                    ("s", "DLP Projector RGBCMY Filter Wheel"),
                    ("u", "Unknown"),
                ]
            )
        result = self.exec_cmd(
            get_argyll_util("ccxxmake"),
            ["-??"],
            capture_output=True,
            skip_scripts=True,
            silent=True,
            log_output=False,
        )
        if isinstance(result, Exception):
            traceback.print_exc()
            print(result)
            return dict()
        technology_strings = dict()
        in_tech = False
        for line in self.output:
            parts = line.strip().split(None, 1)
            if parts:
                arg = parts.pop(0)
                if arg == "-t":
                    parts = parts[0].split(None, 1)
                    if len(parts) == 2:
                        arg = parts.pop(0)
                        in_tech = True
                elif arg.startswith("-"):
                    in_tech = False
                if in_tech and parts:
                    technology_strings[arg] = parts[0]
        return technology_strings

    def has_lut_access(self):
        display_no = min(len(self.lut_access), getcfg("display.number")) - 1
        return display_no > -1 and bool(self.lut_access[display_no])

    def has_separate_lut_access(self):
        """Return True if separate LUT access is possible and needed."""
        # Filter out Prisma, Resolve and Untethered
        # IMPORTANT: Also make changes to display filtering in
        # worker.Worker.enumerate_displays_and_ports
        lut_access = self.lut_access[:-3]
        if self.argyll_version >= [1, 6, 0]:
            # Filter out madVR
            lut_access = lut_access[:-1]
        if self.argyll_version >= [1, 4, 0]:
            # Filter out Web @ localhost
            lut_access = lut_access[:-1]
        return len(self.displays) > 1 and False in lut_access and True in lut_access

    def import_colorimeter_corrections(self, cmd, args=None, asroot=False):
        """Import colorimeter corrections. cmd can be 'i1d3ccss', 'spyd4en'
        or 'oeminst'"""
        if not args:
            args = []
        if (is_superuser() or asroot) and "-Sl" not in args:
            # If we are root or need root privs anyway, install to local
            # system scope
            args.insert(0, "-Sl")
        return self.exec_cmd(
            cmd,
            ["-v"] + args,
            capture_output=True,
            skip_scripts=True,
            silent=False,
            asroot=asroot,
        )

    def import_edr(self, args=None, asroot=False):
        """Import X-Rite .edr files"""
        return self.import_colorimeter_corrections(
            get_argyll_util("i1d3ccss"), args, asroot
        )

    def import_spyd4cal(self, args=None, asroot=False):
        """Import Spyder4/5 calibrations to spy4cal.bin"""
        return self.import_colorimeter_corrections(
            get_argyll_util("spyd4en"), args, asroot
        )

    def install_3dlut(self, path, filename=None):
        if getcfg("3dlut.format") == "madVR" and madvr:
            # Install (load) 3D LUT using madTPG
            print(path)
            hdr_to_sdr = not getcfg("3dlut.hdr_display")
            # Get parameters from actual 3D LUT file
            h3dlut = madvr.H3DLUT(path)
            xy = h3dlut.parametersData.get("Input_Primaries", [])
            smpte2084 = h3dlut.parametersData.get("Input_Transfer_Function") == "PQ"
            if len(xy) < 6:
                # Should never happen
                return Error("madVR 3D LUT doesn't contain " "Input_Primaries")
            slot, rgb_space_name = h3dlut.source_colorspace
            if slot is not None:
                print("Input primaries match", rgb_space_name)
            else:
                return Error(
                    lang.getstr(
                        "3dlut.madvr.colorspace.unsupported",
                        [rgb_space_name or lang.getstr("unknown")] + list(xy[:6]),
                    )
                )
            args = [path, True, slot]
            if smpte2084:
                methodname = "load_hdr_3dlut_file"
                args.append(hdr_to_sdr)
                lut3d_section = "HDR"
                if hdr_to_sdr:
                    lut3d_section += " to SDR"
            else:
                methodname = "load_3dlut_file"
                lut3d_section = "calibration"
            print(
                "Installing madVR 3D LUT for %s slot %i (%s)..."
                % (lut3d_section, slot, rgb_space_name)
            )
            try:
                # Connect & load 3D LUT
                if self.madtpg_connect() and getattr(self.madtpg, methodname)(*args):
                    raise Info(lang.getstr("3dlut.install.success"))
                else:
                    raise Error(lang.getstr("3dlut.install.failure"))
            except Exception as exception:
                return exception
        elif config.get_display_name(None, True) == "Prisma":
            try:
                # Use Prisma HTTP REST interface to upload 3D LUT
                if not self.patterngenerator:
                    self.setup_patterngenerator()
                self.patterngenerator.connect()
                # Check preset. If it has a custom LUT assigned, we delete the
                # currently assigned LUT before uploading, unless its filename
                # is the same as the LUT to be uploaded, in which case it will
                # be simply overwritten, and unless the custom LUT is still
                # assigned to another preset as well.
                presetname = getcfg("patterngenerator.prisma.preset")
                if False:
                    # NEVER?
                    # Check all presets for currently assigned LUT
                    # Check the preset we're going to use for the upload last
                    presetnames = [
                        name
                        for name in config.valid_values[
                            "patterngenerator.prisma.preset"
                        ]
                        if name != presetname
                    ]
                else:
                    # Check only the preset we're going to use for the upload
                    presetnames = []
                presetnames.append(presetname)
                assigned_luts = {}
                for presetname in presetnames:
                    self.log("Loading Prisma preset", presetname)
                    preset = self.patterngenerator.load_preset(presetname)
                    assigned_lut = preset["v"].get("cube", "")
                    if assigned_lut not in assigned_luts:
                        assigned_luts[assigned_lut] = 0
                    assigned_luts[assigned_lut] += 1
                # Only remove the currently assigned custom LUT if it's not
                # assigned to another preset
                if (
                    assigned_lut.lower().endswith(".3dl")
                    and assigned_luts[assigned_lut] == 1
                ):
                    remove = preset["v"]["cube"]
                else:
                    remove = False
                # Check total size of installed 3D LUTs. The Prisma has 1 MB of
                # custom LUT storage, which is enough for 15 67 KB LUTs.
                maxsize = 1024 * 67 * 15
                installed = self.patterngenerator.get_installed_3dluts()
                rawlen = len(installed["raw"])
                size = 0
                numinstalled = 0
                for table in installed["v"]["tables"]:
                    if table.get("n") != remove:
                        size += table.get("s", 0)
                        numinstalled += 1
                    else:
                        rawlen -= len(
                            '{"n":"%s", "s":%i},' % (table["n"], table.get("s", 0))
                        )
                filesize = os.stat(path).st_size
                size_exceeded = size + filesize > maxsize
                # NOTE that the total number of 3D LUT slots seems to be limited
                # to 32, which includes built-in LUTs.
                maxluts = 32
                luts_exceeded = numinstalled >= maxluts
                if size_exceeded or luts_exceeded:
                    if size_exceeded:
                        missing = size + filesize - maxsize
                    elif luts_exceeded:
                        missing = filesize * (numinstalled + 1 - maxluts)
                    else:
                        missing = size + filesize - 1024 * 67 * 2
                    raise Error(
                        lang.getstr(
                            "3dlut.holder.out_of_memory",
                            (
                                getcfg("patterngenerator.prisma.host"),
                                round(missing / 1024.0),
                                getcfg("patterngenerator.prisma.host"),
                                "Prisma",
                            ),
                        )
                    )
                if remove and remove != filename:
                    self.log("Removing currently assigned LUT", remove)
                    self.patterngenerator.remove_3dlut(remove)
                self.log("Uploading LUT", path, "as", filename)
                self.patterngenerator.load_3dlut_file(path, filename)
                self.log("Setting LUT", filename)
                self.patterngenerator.set_3dlut(filename)
                self.log("Setting PrismaVue to zero")
                self.patterngenerator.set_prismavue(0)
            except Exception as exception:
                return exception
            return Info(lang.getstr("3dlut.install.success"))
        else:
            return Error(lang.getstr("3dlut.install.unsupported"))

    def install_profile(
        self, profile_path, capture_output=True, skip_scripts=False, silent=False
    ):
        """Install a profile by copying it to an appropriate location and
        registering it with the system"""
        colord_install = None
        oy_install = None
        argyll_install = self._install_profile_argyll(
            profile_path, capture_output, skip_scripts, silent
        )
        if isinstance(argyll_install, str):
            # The installed name may be different due to escaping non-ASCII
            # chars (see prepare_dispwin), so get the profile path
            profile_path = argyll_install
            argyll_install = True
            if sys.platform == "win32":
                # Assign profile to active display
                display_no = min(len(self.displays), getcfg("display.number")) - 1
                monitors = util_win.get_real_display_devices_info()
                moninfo = monitors[display_no]
                displays = util_win.get_display_devices(moninfo["Device"])
                active_display = util_win.get_active_display_device(None, displays)
                if not active_display:
                    self.log(appname + ": Warning - no active display device!")
                    if not displays:
                        self.log(
                            appname + ": Warning - could not enumerate "
                            "display devices for %s!" % moninfo["Device"]
                        )
                elif active_display.DeviceKey != displays[0].DeviceKey:
                    self.log(appname + ": Setting profile for active display device...")
                    try:
                        ICCP.set_display_profile(
                            os.path.basename(profile_path),
                            devicekey=active_display.DeviceKey,
                        )
                    except Exception as exception:
                        # Not a critical error. Only log the exception.
                        if (
                            isinstance(exception, EnvironmentError)
                            and not exception.filename
                            and not os.path.isfile(profile_path)
                        ):
                            exception.filename = profile_path
                        self.log(
                            appname + ": Warning - could not set profile for "
                            "active display device:",
                            exception,
                        )
                    else:
                        self.log(appname + ": ...ok")
        loader_install = None
        profile = None
        try:
            profile = ICCP.ICCProfile(profile_path)
        except (IOError, ICCP.ICCProfileInvalidError) as exception:
            return exception
        device_id = self.get_device_id(quirk=False, query=True)
        if (
            sys.platform not in ("darwin", "win32")
            and not getcfg("dry_run")
            and (
                argyll_install is not True
                or self.argyll_version < [1, 6]
                or not os.getenv("ARGYLL_USE_COLORD")
                or not dlopen("libcolordcompat.so")
            )
            and which("colormgr")
        ):
            if device_id:
                result = self._attempt_install_profile_colord(profile, device_id)
                colord_install = result
            if not device_id or result is not True:
                gcm_import = bool(which("gcm-import"))
                if gcm_import:
                    self._install_profile_gcm(profile)
                    # gcm-import doesn't seem to return a useful exit code or
                    # stderr output, so check for our profile
                    profilename = os.path.basename(profile.fileName)
                    for dirname in iccprofiles_home:
                        profile_install_path = os.path.join(dirname, profilename)
                        if os.path.isfile(profile_install_path):
                            colord_install = Warn(lang.getstr("profile.import.success"))
                            break
        if which("oyranos-monitor") and self.check_display_conf_oy_compat(
            getcfg("display.number")
        ):
            if device_id:
                profile_name = re.sub(r"[- ]", "_", device_id.lower()) + ".icc"
            else:
                profile_name = None
            result = self._install_profile_oy(
                profile_path, profile_name, capture_output, skip_scripts, silent
            )
            oy_install = result
        if argyll_install is not True and (
            (colord_install and not isinstance(colord_install, colord.CDError))
            or oy_install is True
        ):
            # Ignore Argyll install errors if colord or Oyranos install was
            # succesful
            argyll_install = None
        # Check if atleast one of our profile install methods did return a
        # result that is not an error
        for result in (argyll_install, colord_install, oy_install):
            check = result is True or isinstance(result, Warning)
            if check:
                break
        # Only go on to create profile loader if profile loading on login
        # isn't disabled in the config file, and we are not under Mac OS X
        # (no loader required  there), and if atleast one of our profile
        # install methods did return a result that is not an error
        if getcfg("profile.load_on_login") and sys.platform != "darwin" and check:
            # Create profile loader. Failing to create it is a critical error
            # under Windows if calibration loading isn't handled by the OS
            # (this is checked), and also under Linux if colord profile install
            # failed (colord handles loading otherwise)
            check = sys.platform == "win32" or (
                not colord_install or isinstance(colord_install, colord.CDError)
            )
            if getcfg("profile.install_scope") == "l" and sys.platform != "win32":
                # We need a system-wide config file to store the path to
                # the Argyll binaries for the profile loader
                if not config.makecfgdir("system", self) or (
                    not config.writecfg("system", self) and check
                ):
                    # If the system-wide config dir could not be created,
                    # or the system-wide config file could not be written,
                    # error out if under Linux and colord profile install failed
                    return Error(lang.getstr("error.autostart_system"))
            if sys.platform == "win32":
                loader_install = self._install_profile_loader_win32(silent)
            else:
                loader_install = self._install_profile_loader_xdg(silent)
            if loader_install is not True and check:
                return loader_install
        # Check if atleast one of our profile install methods returned a result
        for result in (argyll_install, colord_install, oy_install):
            if result is not None:
                return argyll_install, colord_install, oy_install, loader_install
        if not result:
            # This should never happen
            result = Error(lang.getstr("profile.install.error"))
        return result

    def install_argyll_instrument_conf(self, uninstall=False, filenames=None):
        """(Un-)install Argyll CMS instrument configuration under Linux"""
        udevrules = "/etc/udev/rules.d"
        hotplug = "/etc/hotplug"
        if not os.path.isdir(udevrules) and not os.path.isdir(hotplug):
            return Error(lang.getstr("udev_hotplug.unavailable"))
        if not filenames:
            filenames = self.get_argyll_instrument_conf(
                "installed" if uninstall else None
            )
        if not filenames:
            return Error(
                "\n".join(
                    lang.getstr("file.missing", filename)
                    for filename in self.get_argyll_instrument_conf("expected")
                )
            )
        if uninstall:
            backupbase = os.path.join(
                config.datahome, "backup", strftime("%Y%m%dT%H%M%S")
            )
        for filename in filenames:
            if filename.endswith(".rules"):
                dst = udevrules
            else:
                dst = hotplug
            if uninstall:
                # Move file to backup location
                backupdir = "".join([backupbase, os.path.dirname(filename)])
                if not os.path.isdir(backupdir):
                    os.makedirs(backupdir)
                cmd, args = "mv", [filename, "".join([backupbase, filename])]
            else:
                cmd, args = "cp", ["--remove-destination", filename]
                args.append(os.path.join(dst, os.path.basename(filename)))
            result = self.exec_cmd(
                cmd, args, capture_output=True, skip_scripts=True, asroot=True
            )
            if result is not True:
                break
            elif not uninstall:
                self.exec_cmd(
                    "chmod",
                    ["0644", args[-1]],
                    capture_output=True,
                    skip_scripts=True,
                    asroot=True,
                )
        install_result = result
        paths = ["/sbin", "/usr/sbin"]
        paths.extend(getenvu("PATH", os.defpath).split(os.pathsep))
        if not uninstall:
            if not isinstance(result, Exception) and result:
                # Add colord group if it does not exist
                if "colord" not in [g.gr_name for g in grp.getgrall()]:
                    groupadd = which("groupadd", paths)
                    if groupadd:
                        result = self.exec_cmd(
                            groupadd,
                            ["colord"],
                            capture_output=True,
                            skip_scripts=True,
                            asroot=True,
                        )
            if not isinstance(result, Exception) and result:
                # Add user to colord group if not yet a member
                if "colord" not in getgroups(getpass.getuser(), True):
                    usermod = which("usermod", paths)
                    if usermod:
                        result = self.exec_cmd(
                            usermod,
                            ["-a", "-G", "colord", getpass.getuser()],
                            capture_output=True,
                            skip_scripts=True,
                            asroot=True,
                        )
        if install_result is True and dst == udevrules:
            # Reload udev rules
            udevadm = which("udevadm", paths)
            if udevadm:
                result = self.exec_cmd(
                    udevadm,
                    ["control", "--reload-rules"],
                    capture_output=True,
                    skip_scripts=True,
                    asroot=True,
                )
        return result

    def install_argyll_instrument_drivers(self, uninstall=False, launch_devman=False):
        """(Un-)install the Argyll CMS instrument drivers under Windows"""
        winxp = sys.getwindowsversion() < (6,)
        if launch_devman:
            if winxp:
                cmd = "start"
                args = ["mmc", "devmgmt.msc"]
            else:
                cmd = "mmc"
                args = ["devmgmt.msc"]
            self.exec_cmd(
                cmd,
                args,
                capture_output=True,
                skip_scripts=True,
                asroot=not winxp,
                shell=winxp,
                working_dir=False,
            )
        if uninstall:
            if not winxp:
                # Windows Vista and newer
                with win64_disable_file_system_redirection():
                    pnputil = which("PnPutil.exe")
                    if not pnputil:
                        return Error(lang.getstr("file.missing", "PnPutil.exe"))
                    result = self.exec_cmd(
                        pnputil,
                        ["-e"],
                        capture_output=True,
                        log_output=False,
                        silent=True,
                        skip_scripts=True,
                    )
                    if not result:
                        return Error(
                            lang.getstr("argyll.instrument.drivers.uninstall.failure")
                        )
                    elif isinstance(result, Exception):
                        return result
                    output = universal_newlines("".join(self.output))
                    for entry in output.split("\n\n"):
                        entry = [
                            line.split(":", 1)[-1].strip() for line in entry.split("\n")
                        ]
                        for value in entry:
                            if value == "ArgyllCMS":
                                result = self.exec_cmd(
                                    pnputil,
                                    ["-f", "-d", entry[0]],
                                    capture_output=True,
                                    skip_scripts=True,
                                    asroot=True,
                                )
            else:
                # Windows XP
                # Uninstallation not supported
                pass
        else:
            # Install driver using modified 'zadic' command line tool from
            # https://github.com/fhoech/libwdi

            result = None

            # Get Argyll version
            argyll_version_string = self.argyll_version_string
            if argyll_version_string == "0.0.0":
                # Download version info
                resp = http_request(
                    None,
                    DOMAIN,
                    "GET",
                    "/Argyll/VERSION",
                    failure_msg=lang.getstr("update_check.fail"),
                    silent=True,
                )
                if resp:
                    argyll_version_string = resp.read().strip()

            installer_basename = (
                "Argyll_V%s_USB_driver_installer.exe" % argyll_version_string
            )

            download_dir = os.path.join(config.datahome, "dl")
            installer = os.path.join(download_dir, installer_basename)

            if not os.path.isfile(installer):
                installer_zip = self.download(
                    f"https://{DOMAIN}/Argyll/{installer_basename}.zip"
                )
                if isinstance(installer_zip, Exception):
                    return installer_zip
                elif not installer_zip:
                    # Cancelled
                    return

                installer = os.path.splitext(installer_zip)[0]
                # Open installer ZIP archive
                try:
                    with zipfile.ZipFile(installer_zip) as z:
                        # Extract installer if it does not exist or if the existing
                        # file is different from the one in the archive
                        if os.path.isfile(installer):
                            with open(installer, "rb") as f:
                                crc = zlib.crc32(f.read())
                        else:
                            crc = None
                        if (
                            not os.path.isfile(installer)
                            or crc != z.getinfo(installer_basename).CRC
                        ):
                            z.extract(
                                installer_basename, os.path.dirname(installer_zip)
                            )
                except Exception as exception:
                    return exception

            # Get supported instruments USB device IDs
            usb_ids = {}
            for instrument_name in all_instruments:
                instrument = all_instruments[instrument_name]
                if instrument.get("usb_ids"):
                    for entry in instrument.get("usb_ids"):
                        usb_id = (entry["vid"], entry["pid"])
                        if entry.get("hid"):
                            # Skip HID devices
                            continue
                        else:
                            usb_ids[usb_id] = usb_ids.get(usb_id, [instrument_name])
                            usb_ids[usb_id].append(instrument_name)

            # Check connected USB devices for supported instruments
            not_main_thread = currentThread().__class__.__name__ != "_MainThread"
            if not_main_thread:
                # If running in a thread, need to call pythoncom.CoInitialize
                pythoncom.CoInitialize()
            try:
                if not wmi:
                    raise NotImplementedError("WMI not available")
                wmi_connection = wmi.WMI()
                query = "Select * From Win32_USBControllerDevice"
                for item in wmi_connection.query(query):
                    try:
                        device_id = item.Dependent.DeviceID
                    except wmi.x_wmi as exception:
                        self.log(exception)
                        continue
                    for usb_id in usb_ids:
                        instrument_names = usb_ids[usb_id]
                        hardware_id = r"USB\VID_%04X&PID_%04X" % usb_id
                        if device_id.startswith(hardware_id):
                            # Found supported instrument
                            try:
                                self.log(item.Dependent.Caption)
                            except wmi.x_wmi:
                                self.log(", ".join(instrument_names))
                            # Install driver for specific device
                            result = self.exec_cmd(
                                installer,
                                [
                                    "--noprompt",
                                    "--usealldevices",
                                    "--vid",
                                    hex(usb_id[0]),
                                    "--pid",
                                    hex(usb_id[1]),
                                ],
                                capture_output=True,
                                skip_scripts=True,
                                asroot=True,
                            )
                            output = universal_newlines("".join(self.output))
                            if isinstance(result, Exception):
                                return result
                            elif not result or "Failed to install driver" in output:
                                return Error(
                                    lang.getstr(
                                        "argyll.instrument.drivers.install.failure"
                                    )
                                )
            except Exception as exception:
                self.log(exception)
            finally:
                if not_main_thread:
                    # If running in a thread, need to call pythoncom.CoUninitialize
                    pythoncom.CoUninitialize()

            if not result:
                # No matching device found. Install driver anyway, doesn't
                # matter for which specific device as the .inf contains entries
                # for all supported ones, thus instruments that are connected
                # later should be recognized
                usb_id, instrument_names = usb_ids.popitem()
                result = self.exec_cmd(
                    installer,
                    [
                        "--noprompt",
                        "--vid",
                        hex(usb_id[0]),
                        "--pid",
                        hex(usb_id[1]),
                        "--create",
                        "%s (Argyll)" % instrument_names[-1],
                    ],
                    capture_output=True,
                    skip_scripts=True,
                    asroot=True,
                )
                output = universal_newlines("".join(self.output))
                if not result or "Failed to install driver" in output:
                    return Error(
                        lang.getstr("argyll.instrument.drivers.install.failure")
                    )

        return result

    def _install_profile_argyll(
        self, profile_path, capture_output=False, skip_scripts=False, silent=False
    ):
        """Install profile using dispwin.

        Return the profile path, an error or False

        """
        if sys.platform == "darwin" and False:  # NEVER
            # Alternate way of 'installing' the profile under OS X by just
            # copying it
            profiles = os.path.join("Library", "ColorSync", "Profiles")
            profile_install_path = os.path.join(
                profiles, os.path.basename(profile_path)
            )
            network = os.path.join(os.path.sep, "Network", profiles)
            if getcfg("profile.install_scope") == "l":
                profile_install_path = os.path.join(os.path.sep, profile_install_path)
            elif getcfg("profile.install_scope") == "n" and os.path.isdir(network):
                profile_install_path = os.path.join(network, profile_install_path)
            else:
                profile_install_path = os.path.join(
                    os.path.expanduser("~"), profile_install_path
                )
            cmd, args = "cp", ["-f", profile_path, profile_install_path]
            result = self.exec_cmd(
                cmd,
                args,
                capture_output,
                low_contrast=False,
                skip_scripts=skip_scripts,
                silent=silent,
                asroot=getcfg("profile.install_scope") in ("l", "n"),
                title=lang.getstr("profile.install"),
            )
            if not isinstance(result, Exception) and result:
                self.output = ["Installed"]
        else:
            cmd, args = self.prepare_dispwin(None, profile_path, True)
            if not isinstance(cmd, Exception):
                profile_path = args[-1]
                if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
                    # Set/unset per-user profiles under Vista / Windows 7
                    idx = getcfg("display.number") - 1
                    try:
                        device0 = util_win.get_display_device(idx, exception_cls=None)
                        devicea = util_win.get_display_device(idx, True)
                    except Exception as exception:
                        self.log("util_win.get_display_device(%s):" % idx, exception)
                    else:
                        per_user = "-Sl" not in args
                        for i, device in enumerate((device0, devicea)):
                            if not device:
                                self.log(
                                    "Warning: There is no %s display "
                                    "device to %s per-user profiles"
                                    % (
                                        "1st" if i == 0 else "active",
                                        "enable" if per_user else "disable",
                                    )
                                )
                                continue
                            try:
                                util_win.enable_per_user_profiles(
                                    per_user, devicekey=device.DeviceKey
                                )
                            except Exception as exception:
                                self.log(
                                    "util_win.enable_per_user_profiles(%s, devicekey=%r): %s"
                                    % (per_user, device.DeviceKey, exception)
                                )
                if "-Sl" in args and (
                    sys.platform != "darwin"
                    or intlist(mac_ver()[0].split(".")) >= [10, 6]
                ):
                    # If a 'system' install is requested under Linux,
                    # Mac OS X >= 10.6 or Windows,
                    # install in 'user' scope first because a system-wide install
                    # doesn't also set it as current user profile on those systems
                    # (on Mac OS X < 10.6, we can use ColorSyncScripting to set it).
                    # It has the small drawback under Linux and OS X 10.6 that
                    # it will copy the profile to both the user and system-wide
                    # locations, though, which is not a problem under Windows as
                    # they are the same.
                    args.remove("-Sl")
                    result = self.exec_cmd(
                        cmd,
                        args,
                        capture_output,
                        low_contrast=False,
                        skip_scripts=skip_scripts,
                        silent=silent,
                        title=lang.getstr("profile.install"),
                    )
                    output = list(self.output)
                    args.insert(0, "-Sl")
                else:
                    output = None
                    result = True
                if not isinstance(result, Exception) and result:
                    result = self.exec_cmd(
                        cmd,
                        args,
                        capture_output,
                        low_contrast=False,
                        skip_scripts=skip_scripts,
                        silent=silent,
                        title=lang.getstr("profile.install"),
                    )
            else:
                result = cmd
        if not isinstance(result, Exception) and result is not None:
            result = False
            for line in output or self.output:
                if "Installed" in line:
                    if (
                        sys.platform == "darwin"
                        and "-Sl" in args
                        and intlist(mac_ver()[0].split(".")) < [10, 6]
                    ):
                        # The profile has been installed, but we need a little
                        # help from AppleScript to actually make it the default
                        # for the current user. Only works under Mac OS < 10.6
                        n = getcfg("display.number")
                        path = os.path.join(
                            os.path.sep,
                            "Library",
                            "ColorSync",
                            "Profiles",
                            os.path.basename(args[-1]),
                        )
                        applescript = [
                            'tell app "ColorSyncScripting"',
                            'set displayProfile to POSIX file "%s" as alias' % path,
                            "set display profile of display %i to displayProfile" % n,
                            "end tell",
                        ]
                        try:
                            retcode, output, errors = osascript(applescript)
                        except Exception as exception:
                            self.log(exception)
                        else:
                            if errors.strip():
                                self.log("osascript error: %s" % errors)
                            else:
                                result = True
                        break
                    elif sys.platform == "darwin" and False:  # NEVER
                        # After 'installing' a profile under Mac OS X by just
                        # copying it, show system preferences
                        applescript = [
                            'tell application "System Preferences"',
                            "activate",
                            'set current pane to pane id "com.apple.preference.displays"',
                            'reveal (first anchor of current pane whose name is "displaysColorTab")',
                            # This needs access for assistive devices enabled
                            # 'tell application "System Events"',
                            # 'tell process "System Preferences"',
                            # 'select row 2 of table 1 of scroll area 1 of group 1 of tab group 1 of window "<Display name from EDID here>"',
                            # 'end tell',
                            # 'end tell',
                            "end tell",
                        ]
                        try:
                            retcode, output, errors = osascript(applescript)
                        except Exception as exception:
                            self.log(exception)
                        else:
                            if errors.strip():
                                self.log("osascript error: %s" % errors)
                            else:
                                result = True
                    else:
                        result = True
                    break
            if not result and self.errors:
                result = Error("".join(self.errors).strip())
            else:
                result = profile_path
        # DO NOT call wrapup() here, it'll remove the profile in the temp
        # directory before dispwin can get a hold of it when running with UAC
        # under Windows, because that makes the call to dispwin run in a
        # separate thread. DisplayCAL.MainFrame.profile_finish_consumer calls
        # DisplayCAL.MainFrame.start_timers(True) after displaying the result
        # message which takes care of cleanup.
        return result

    def _install_profile_colord(self, profile, device_id):
        """Install profile using colord"""
        self.log("%s: Trying device ID %r" % (appname, device_id))
        try:
            colord.install_profile(device_id, profile, logfn=self.log)
        except Exception as exception:
            self.log(exception)
            return exception
        return True

    def _attempt_install_profile_colord(self, profile, device_id=None):
        if not device_id:
            device_id = self.get_device_id(quirk=False, query=True)
        if device_id:
            result = False
            # Try a range of possible device IDs
            device_ids = [
                device_id,
                self.get_device_id(quirk=True, truncate_edid_strings=True),
                self.get_device_id(quirk=True, use_serial_32=False),
                self.get_device_id(
                    quirk=True, use_serial_32=False, truncate_edid_strings=True
                ),
                self.get_device_id(quirk=True),
                self.get_device_id(quirk=False, truncate_edid_strings=True),
                self.get_device_id(quirk=False, use_serial_32=False),
                self.get_device_id(
                    quirk=False, use_serial_32=False, truncate_edid_strings=True
                ),
                # Try with manufacturer omitted
                self.get_device_id(omit_manufacturer=True),
                self.get_device_id(truncate_edid_strings=True, omit_manufacturer=True),
                self.get_device_id(use_serial_32=False, omit_manufacturer=True),
                self.get_device_id(
                    use_serial_32=False,
                    truncate_edid_strings=True,
                    omit_manufacturer=True,
                ),
            ]
            for device_id in dict.fromkeys(device_ids).keys():
                if device_id:
                    # NOTE: This can block
                    result = self._install_profile_colord(profile, device_id)
                    if isinstance(result, colord.CDObjectQueryError):
                        # Device ID was not found, try next one
                        continue
                    else:
                        # Either returned ok or there was another error
                        break
            return result

    def _install_profile_gcm(self, profile):
        """Install profile using gcm-import"""
        if which("colormgr"):
            # Check if profile already exists in database
            try:
                colord.get_object_path("icc-" + hexlify(profile.ID).decode(), "profile")
            except colord.CDObjectQueryError:
                # Profile not in database
                pass
            except colord.CDError as exception:
                self.log(exception)
            else:
                # Profile already in database, nothing to do
                return None
        # gcm-import will check if the profile is already in the database
        # (based on profile ID), but will fail to overwrite a profile with the
        # same name. We need to remove those profiles so gcm-import can work.
        profilename = os.path.basename(profile.fileName)
        for dirname in iccprofiles_home:
            profile_install_path = os.path.join(dirname, profilename)
            if (
                os.path.isfile(profile_install_path)
                and profile_install_path != profile.fileName
            ):
                try:
                    send2trash([profile_install_path])
                except OSError as exc:
                    self.log(exc)
                else:
                    # Give colord time to recognize that the profile was
                    # removed, otherwise gcm-import may complain if it's
                    # a profile that was already in the database
                    sleep(3)
        if self._progress_wnd and not getattr(self._progress_wnd, "dlg", None):
            self._progress_wnd.dlg = DummyDialog()
        # Run gcm-import
        cmd, args = which("gcm-import"), [profile.fileName]
        # gcm-import does not seem to return a useful exit code (it's always 1)
        # or stderr output
        self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)

    def _install_profile_oy(
        self,
        profile_path,
        profile_name=None,
        capture_output=False,
        skip_scripts=False,
        silent=False,
    ):
        """Install profile using oyranos-monitor"""
        display = self.displays[
            max(0, min(len(self.displays) - 1, getcfg("display.number") - 1))
        ]
        x, y = [pos.strip() for pos in display.split("@")[-1].split(",")[0:2]]
        if getcfg("profile.install_scope") == "l":
            # If system-wide install, copy profile to
            # /var/lib/color/icc/devices/display
            var_icc = "/var/lib/color/icc/devices/display"
            if not profile_name:
                profile_name = os.path.basename(profile_path)
            profile_install_path = os.path.join(var_icc, profile_name)
            result = self.exec_cmd(
                "mkdir",
                ["-p", os.path.dirname(profile_install_path)],
                capture_output=True,
                low_contrast=False,
                skip_scripts=True,
                silent=True,
                asroot=True,
            )
            if not isinstance(result, Exception) and result:
                result = self.exec_cmd(
                    "cp",
                    ["-f", profile_path, profile_install_path],
                    capture_output=True,
                    low_contrast=False,
                    skip_scripts=True,
                    silent=True,
                    asroot=True,
                )
        else:
            result = True
            dirname = None
            for dirname in iccprofiles_display_home:
                if os.path.isdir(dirname):
                    # Use the first one that exists
                    break
                else:
                    dirname = None
            if not dirname:
                # Create the first one in the list
                dirname = iccprofiles_display_home[0]
                try:
                    os.makedirs(dirname)
                except Exception as exception:
                    self.log(exception)
                    result = False
            if result is not False:
                profile_install_path = os.path.join(
                    dirname, os.path.basename(profile_path)
                )
                try:
                    shutil.copyfile(profile_path, profile_install_path)
                except Exception as exception:
                    self.log(exception)
                    result = False
        if not isinstance(result, Exception) and result is not False:
            cmd = which("oyranos-monitor")
            args = ["-x", x, "-y", y, profile_install_path]
            result = self.exec_cmd(
                cmd,
                args,
                capture_output,
                low_contrast=False,
                skip_scripts=skip_scripts,
                silent=silent,
                working_dir=False,
            )
        # if getcfg("profile.install_scope") == "l":
        # result = self.exec_cmd(cmd, args,
        # capture_output,
        # low_contrast=False,
        # skip_scripts=skip_scripts,
        # silent=silent,
        # asroot=True,
        # working_dir=False)
        if not result and self.errors:
            result = Error("".join(self.errors).strip())
        return result

    def _install_profile_loader_win32(self, silent=False):
        """Install profile loader"""
        if (
            sys.platform == "win32"
            and sys.getwindowsversion() >= (6, 1)
            and util_win.calibration_management_isenabled()
        ):
            self._uninstall_profile_loader_win32()
            return True
        # Must return either True on success or an Exception object on error
        result = True
        # Remove outdated (pre-0.5.5.9) profile loaders
        display_no = self.get_display()
        name = "%s Calibration Loader (Display %s)" % (appname, display_no)
        if autostart_home:
            loader_v01b = os.path.join(
                autostart_home, ("dispwin-d%s-c-L" % display_no) + ".lnk"
            )
            if os.path.exists(loader_v01b):
                try:
                    # delete v0.1b loader
                    os.remove(loader_v01b)
                except Exception as exception:
                    self.log(
                        "Warning - could not remove old "
                        "v0.1b calibration loader '%s': %s"
                        % tuple(str(s) for s in (loader_v01b, exception))
                    )
            loader_v02b = os.path.join(autostart_home, name + ".lnk")
            if os.path.exists(loader_v02b):
                try:
                    # delete v02.b/v0.2.1b loader
                    os.remove(loader_v02b)
                except Exception as exception:
                    self.log(
                        "Warning - could not remove old "
                        "v0.2b calibration loader '%s': %s"
                        % tuple(str(s) for s in (loader_v02b, exception))
                    )
            loader_v0558 = os.path.join(autostart_home, name + ".lnk")
            if os.path.exists(loader_v0558):
                try:
                    # delete v0.5.5.8 user loader
                    os.remove(loader_v0558)
                except Exception as exception:
                    self.log(
                        "Warning - could not remove old "
                        "v0.2b calibration loader '%s': %s"
                        % tuple(str(s) for s in (loader_v02b, exception))
                    )
        if autostart:
            loader_v0558 = os.path.join(autostart, name + ".lnk")
            if os.path.exists(loader_v0558):
                try:
                    # delete v0.5.5.8 system loader
                    os.remove(loader_v0558)
                except Exception as exception:
                    self.log(
                        "Warning - could not remove old "
                        "v0.2b calibration loader '%s': %s"
                        % tuple(str(s) for s in (loader_v02b, exception))
                    )
        # Create unified loader
        name = appname + " Profile Loader"
        if autostart:
            autostart_lnkname = os.path.join(autostart, name + ".lnk")
        if autostart_home:
            autostart_home_lnkname = os.path.join(autostart_home, name + ".lnk")
        loader_args = []
        if os.path.basename(exe).lower() in ("python.exe", "pythonw.exe"):
            cmd = os.path.join(exedir, "pythonw.exe")
            pyw = os.path.normpath(
                os.path.join(pydir, "..", appname + "-apply-profiles.pyw")
            )
            if os.path.exists(pyw):
                # Running from source or 0install
                # Check if this is a 0install implementation, in which
                # case we want to call 0launch with the appropriate
                # command
                if re.match(
                    r"sha\d+(?:new)?", os.path.basename(os.path.dirname(pydir))
                ):
                    cmd = which("0install-win.exe") or "0install-win.exe"
                    loader_args.extend(
                        [
                            "run",
                            "--batch",
                            "--no-wait",
                            "--offline",
                            "--command=run-apply-profiles",
                            f"http://{DOMAIN}/0install/{appname}.xml",
                        ]
                    )
                else:
                    # Running from source
                    loader_args.append(pyw)
            else:
                # Regular install
                loader_args.append(
                    get_data_path(os.path.join("scripts", appname + "-apply-profiles"))
                )
        else:
            cmd = os.path.join(pydir, appname + "-apply-profiles.exe")

        not_main_thread = currentThread().__class__.__name__ != "_MainThread"
        if not_main_thread:
            # If running in a thread, need to call pythoncom.CoInitialize
            pythoncom.CoInitialize()

        from DisplayCAL import taskscheduler

        try:
            ts = taskscheduler.TaskScheduler()
        except Exception as exception:
            print("Warning - could not access task scheduler:", exception)
            ts = None
            task = None
        else:
            task = ts.query_task(appname + " Profile Loader Launcher")

        elevate = getcfg(
            "profile.install_scope"
        ) == "l" and sys.getwindowsversion() >= (6,)

        loader_lockfile = os.path.join(
            config.confighome, appbasename + "-apply-profiles.lock"
        )
        loader_running = os.path.isfile(loader_lockfile)

        if not loader_running or (not task and elevate):
            # Launch profile loader if not yet running, or restart if no task
            # and going to elevate (launching profile loader with elevated
            # privileges will try to create scheduled task so we can run
            # elevated at login without UAC prompt)
            errmsg = "Warning - could not launch profile loader"
            if elevate:
                errmsg += " with elevated privileges"
            try:
                shell_exec(
                    cmd,
                    loader_args + ["--skip"],
                    operation="runas" if elevate else "open",
                    wait_for_idle=True,
                )
            except pywintypes.error as exception:
                if exception.args[0] == winerror.ERROR_CANCELLED:
                    errmsg += " (user cancelled)"
                else:
                    errmsg += " " + safe_str(exception)
                print(errmsg)

        if task or (ts and ts.query_task(appname + " Profile Loader Launcher")):
            if not_main_thread:
                pythoncom.CoUninitialize()
            return True

        try:
            scut = pythoncom.CoCreateInstance(
                win32com_shell.CLSID_ShellLink,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                win32com_shell.IID_IShellLink,
            )
            scut.SetPath(cmd)
            if len(loader_args) == 1:
                scut.SetWorkingDirectory(pydir)
            if os.path.basename(cmd) == appname + "-apply-profiles.exe":
                scut.SetIconLocation(cmd, 0)
            else:
                scut.SetIconLocation(
                    get_data_path(
                        os.path.join("theme", "icons", appname + "-apply-profiles.ico")
                    ),
                    0,
                )
            scut.SetArguments(sp.list2cmdline(loader_args))
            scut.SetShowCmd(win32con.SW_SHOWDEFAULT)
            if is_superuser():
                if autostart:
                    try:
                        scut.QueryInterface(pythoncom.IID_IPersistFile).Save(
                            autostart_lnkname, 0
                        )
                    except Exception as exception:
                        if not silent:
                            result = Warning(
                                lang.getstr("error.autostart_creation", autostart)
                                + "\n"
                                + str(exception)
                            )
                    # Now try user scope
                else:
                    if not silent:
                        result = Warning(lang.getstr("error.autostart_system"))
            if autostart_home:
                if autostart and os.path.isfile(autostart_lnkname):
                    # Remove existing user loader
                    if os.path.isfile(autostart_home_lnkname):
                        os.remove(autostart_home_lnkname)
                else:
                    # Only create user loader if no system loader
                    try:
                        scut.QueryInterface(pythoncom.IID_IPersistFile).Save(
                            autostart_home_lnkname, 0
                        )
                    except Exception as exception:
                        if not silent:
                            result = Warning(
                                lang.getstr("error.autostart_creation", autostart_home)
                                + "\n"
                                + str(exception)
                            )
            else:
                if not silent:
                    result = Warning(lang.getstr("error.autostart_user"))
        except Exception as exception:
            if not silent:
                result = Warning(
                    lang.getstr("error.autostart_creation", autostart_home)
                    + "\n"
                    + str(exception)
                )
        finally:
            if not_main_thread:
                # If running in a thread, need to call pythoncom.CoUninitialize
                pythoncom.CoUninitialize()
        return result

    def _uninstall_profile_loader_win32(self):
        """Uninstall profile loader"""
        name = appname + " Profile Loader"
        if autostart and is_superuser():
            autostart_lnkname = os.path.join(autostart, name + ".lnk")
            if os.path.exists(autostart_lnkname):
                try:
                    os.remove(autostart_lnkname)
                except Exception as exception:
                    self.log(autostart_lnkname, exception)
        if autostart_home:
            autostart_home_lnkname = os.path.join(autostart_home, name + ".lnk")
            if os.path.exists(autostart_home_lnkname):
                try:
                    os.remove(autostart_home_lnkname)
                except Exception as exception:
                    self.log(autostart_home_lnkname, exception)
        return True

    def _install_profile_loader_xdg(self, silent=False):
        """Install profile loader"""
        # See http://standards.freedesktop.org/autostart-spec
        # Must return either True on success or an Exception object on error
        result = True
        # Remove wrong-cased entry potentially created by DisplayCAL < 3.1.6
        name = f"z-{appname}-apply-profiles"
        desktop_file_path = os.path.join(autostart_home, f"{name}.desktop")
        if os.path.exists(desktop_file_path):
            try:
                os.remove(desktop_file_path)
            except Exception as exception:
                result = Warning(
                    lang.getstr("error.autostart_remove_old", desktop_file_path)
                )
        # Create unified loader
        # Prepend 'z' so our loader hopefully loads after
        # possible nvidia-settings entry (which resets gamma table)
        name = "z-%s-apply-profiles" % appname.lower()
        desktop_file_path = os.path.join(autostart_home, f"{name}.desktop")
        system_desktop_file_path = os.path.join(autostart, f"{name}.desktop")
        try:
            # Create user loader, even if we later try to
            # move it to the system-wide location so that at least
            # the user loader is present if the move to the system
            # dir fails
            if not os.path.exists(autostart_home):
                os.makedirs(autostart_home)

            desktop_file_buffer = []
            desktop_file_buffer.append("[Desktop Entry]")
            desktop_file_buffer.append("Version=1.0")
            desktop_file_buffer.append("Encoding=UTF-8")
            desktop_file_buffer.append("Type=Application")
            desktop_file_buffer.append(f"Name={appname} ICC Profile Loader")
            desktop_file_buffer.append(
                "Comment={}".format(
                    lang.getstr("calibrationloader.description", lcode="en")
                )
            )
            if lang.getcode() != "en":
                desktop_file_buffer.append(
                    (
                        "Comment[%s]=%s".format(
                            lang.getcode(), lang.getstr("calibrationloader.description")
                        )
                    )
                )
            pyw = os.path.normpath(
                os.path.join(pydir, "..", f"{appname}-apply-profiles.pyw")
            )
            icon = f"{appname.lower()}-apply-profiles"
            if os.path.exists(pyw):
                # Running from source, or 0install/installer install
                # Check if this is a 0install implementation, in which
                # case we want to call 0launch with the appropriate
                # command
                if re.match(
                    r"sha\d+(?:new)?", os.path.basename(os.path.dirname(pydir))
                ):
                    executable = (
                        "0launch --console --offline "
                        "--command=run-apply-profiles "
                        f"http://{DOMAIN}/0install/{appname}.xml"
                    )
                else:
                    icon = os.path.join(
                        pydir,
                        "theme",
                        "icons",
                        "256x256",
                        f"{appname.lower()}-apply-profiles.png",
                    )
                    executable = pyw
            else:
                # Regular install
                executable = f"{appname.lower()}-apply-profiles"
            desktop_file_buffer.append(f"Icon={icon}")
            desktop_file_buffer.append(f"Exec={executable}")
            desktop_file_buffer.append("Terminal=false")
            with open(desktop_file_path, "w") as desktop_file:
                desktop_file.write("\n".join(desktop_file_buffer))
        except Exception as exception:
            if not silent:
                result = Warning(
                    lang.getstr("error.autostart_creation", desktop_file_path)
                    + "\n"
                    + str(exception)
                )
        else:
            if getcfg("profile.install_scope") == "l" and autostart:
                # Move system-wide loader
                if (
                    self.exec_cmd(
                        "mkdir",
                        ["-p", autostart],
                        capture_output=True,
                        low_contrast=False,
                        skip_scripts=True,
                        silent=True,
                        asroot=True,
                    )
                    is not True
                    or self.exec_cmd(
                        "mv",
                        ["-f", desktop_file_path, system_desktop_file_path],
                        capture_output=True,
                        low_contrast=False,
                        skip_scripts=True,
                        silent=True,
                        asroot=True,
                    )
                    is not True
                ) and not silent:
                    result = Warning(
                        lang.getstr(
                            "error.autostart_creation", system_desktop_file_path
                        )
                    )
        return result

    def instrument_supports_ccss(self, instrument_name=None):
        """Return whether instrument supports CCSS files or not"""
        if not instrument_name:
            instrument_name = self.get_instrument_name()
        return self.get_instrument_features(instrument_name).get("spectral_cal")

    def create_ccxx(self, args=None, working_dir=None):
        """Create CCMX or CCSS"""
        if not args:
            args = []
        cmd = get_argyll_util("ccxxmake")
        if "-I" not in args:
            # Display manufacturer & name
            name = self.get_display_name(True)
            if name:
                args.insert(0, "-I")
                args.insert(1, name)
            elif "-T" not in args:
                # Display technology
                args.insert(0, "-T")
                displaytech = ["LCD" if getcfg("measurement_mode") == "l" else "CRT"]
                if self.get_instrument_features().get("projector_mode") and getcfg(
                    "measurement_mode.projector"
                ):
                    displaytech.append("Projector")
                args.insert(1, " ".join(displaytech))
        if not getcfg("ccmx.use_four_color_matrix_method"):
            args.insert(0, "-v")
        return self.exec_cmd(
            cmd,
            args,
            capture_output=True,
            skip_scripts=True,
            silent=False,
            working_dir=working_dir,
        )

    def create_gamut_views(self, profile_path):
        """Generate gamut views (VRML files) and show progress in current
        progress dialog"""
        if getcfg("profile.create_gamut_views"):
            self.log("-" * 80)
            self.log(lang.getstr("gamut.view.create"))
            self.lastmsg.clear()
            self.recent.clear()
            self.recent.write(lang.getstr("gamut.view.create"))
            sleep(0.75)  # Allow time for progress window to update
            return self.calculate_gamut(profile_path)
        else:
            return None, None

    def create_profile(
        self,
        dst_path=None,
        skip_scripts=False,
        display_name=None,
        display_manufacturer=None,
        tags=None,
    ):
        """Create an ICC profile and process the generated file"""
        print(lang.getstr("create_profile"))
        if dst_path is None:
            dst_path = os.path.join(
                getcfg("profile.save_path"),
                getcfg("profile.name.expanded"),
                getcfg("profile.name.expanded") + profile_ext,
            )
        cmd, args = self.prepare_colprof(
            os.path.basename(os.path.splitext(dst_path)[0]),
            display_name,
            display_manufacturer,
            tags,
        )
        if isinstance(cmd, Exception):
            result = cmd
        else:
            result = True
            profile = None
            profile_path = args[-1] + profile_ext
            if "-aX" in args:
                # If profile type is X (XYZ cLUT + matrix), only create the
                # cLUT, then add the matrix tags later from a forward lookup of
                # a smaller testchart (faster computation!)
                args.insert(args.index("-aX"), "-ax")
                args.remove("-aX")
            check_for_ti1_match = False
            is_regular_grid = False
            is_primaries_only = False
            ti3 = CGATS.CGATS(args[-1] + ".ti3")
            XYZbp = None
            try:
                (
                    ti3_extracted,
                    ti3_RGB_XYZ,
                    ti3_remaining,
                ) = extract_device_gray_primaries(ti3, logfn=self.log)
            except Error as exception:
                self.log(exception)
            else:
                if getcfg("profile.type") in ("X", "x", "S", "s"):
                    # Check if TI3 RGB matches one of our regular grid or
                    # primaries + gray charts
                    check_for_ti1_match = True
                if ti3_RGB_XYZ[(0, 0, 0)] != (0, 0, 0):
                    # Note: Setting black chroma to zero fixes smoothness
                    # issues on devices with not very neutral black.
                    bpcorr = getcfg("profile.black_point_correction")
                    if False:  # getcfg("profile.black_point_compensation"):
                        XYZbp = (0, 0, 0)
                        Labbp = (0, 0, 0)
                    else:
                        # Correct black point a* b* and make neutral hues near
                        # black blend over to the new blackpoint. The correction
                        # factor determines the amount of the measured black hue
                        # that should be retained.
                        # It makes the profile slightly less accurate near
                        # black, but the effect is negligible and the visual
                        # benefit is of greater importance (allows for
                        # calibration blackpoint hue correction to have desired
                        # effect, and makes relcol with BPC visually match
                        # perceptual in Photoshop).
                        XYZwp = ti3_RGB_XYZ[(100, 100, 100)]
                        Labbp = colormath.XYZ2Lab(
                            *ti3_RGB_XYZ[(0, 0, 0)], whitepoint=XYZwp
                        )
                        Labbp = (Labbp[0], Labbp[1] * bpcorr, Labbp[2] * bpcorr)
                        XYZbp = colormath.Lab2XYZ(
                            *Labbp, whitepoint=[v / XYZwp[1] for v in XYZwp]
                        )
                    if XYZbp and bpcorr < 1:
                        ti3.write(args[-1] + ".ti3.backup")
                        if False:  # getcfg("profile.black_point_compensation"):
                            logmsg = "Applying black point compensation"
                        else:
                            logmsg = "Applying %i%% black point " "correction" % (
                                bpcorr * 100
                            )
                        self.log("%s to TI3" % logmsg)
                        ti3[0].apply_bpc(XYZbp)
                        ti3.write()
            if check_for_ti1_match:
                for ti1_name in (
                    "ti1/d3-e4-s2-g28-m0-b0-f0",  # Primaries + gray
                    "ti1/d3-e4-s3-g52-m3-b0-f0",  # 3^3 grid
                    "ti1/d3-e4-s4-g52-m4-b0-f0",  # 4^3 grid
                    "ti1/d3-e4-s5-g52-m5-b0-f0",  # 5^3 grid
                    "ti1/d3-e4-s9-g52-m9-b0-f0",  # 9^3 grid
                    "ti1/d3-e4-s17-g52-m17-b0-f0",
                ):  # 17^3 grid
                    ti1_filename = "%s.ti1" % ti1_name
                    ti1_path = get_data_path(ti1_filename)
                    if not ti1_path:
                        if ti1_name in (
                            "ti1/d3-e4-s2-g28-m0-b0-f0",
                            "ti1/d3-e4-s3-g52-m3-b0-f0",
                            "ti1/d3-e4-s4-g52-m4-b0-f0",
                            "ti1/d3-e4-s5-g52-m5-b0-f0",
                        ):
                            return Error(lang.getstr("file.missing", ti1_filename))
                        else:
                            continue
                    ti1 = CGATS.CGATS(ti1_path)
                    (
                        ti1_extracted,
                        ti1_RGB_XYZ,
                        ti1_remaining,
                    ) = extract_device_gray_primaries(ti1)
                    # Quantize to 8 bit for comparison
                    # XXX Note that round(50 * 2.55) = 127, but
                    # round(50 / 100 * 255) = 128 (the latter is what we want)!
                    if sorted(
                        tuple(round(v / 100.0 * 255) for v in RGB)
                        for RGB in list(ti3_remaining.keys())
                    ) == sorted(
                        tuple(round(v / 100.0 * 255) for v in RGB)
                        for RGB in list(ti1_remaining.keys())
                    ):
                        if ti1_name == "ti1/d3-e4-s2-g28-m0-b0-f0":
                            is_primaries_only = True
                            if getcfg("profile.type") not in ("S", "s"):
                                options_dispcal = get_options_from_ti3(ti3)[0]
                                setcfg(
                                    "profile.type",
                                    "S" if get_arg("q", options_dispcal) else "s",
                                )
                        elif getcfg("profile.type") in ("X", "x"):
                            is_regular_grid = True
                        break
            if not display_name:
                arg = get_arg("-M", args, True)
                if arg and len(args) - 1 > arg[0]:
                    display_name = args[arg[0] + 1]
            if not display_manufacturer:
                arg = get_arg("-A", args, True)
                if arg and len(args) - 1 > arg[0]:
                    display_manufacturer = args[arg[0] + 1]
            if is_regular_grid:
                # Use our own forward profile code
                profile = self.create_RGB_XYZ_cLUT_fwd_profile(
                    ti3,
                    os.path.basename(args[-1]),
                    getcfg("copyright"),
                    display_manufacturer,
                    display_name,
                    self.log,
                )
                if getcfg("profile.type") == "x" and (
                    self.argyll_version < [2, 1, 0] or "-aY" in args
                ):
                    # Swapped matrix - need to create it ourselves
                    # Start with sRGB
                    sRGB = profile.from_named_rgb_space("sRGB")
                    for channel in "rgb":
                        tagname = channel + "TRC"
                        profile.tags[tagname] = sRGB.tags[tagname]
                    # Swap RGB -> BRG
                    profile.tags.rXYZ = sRGB.tags.bXYZ
                    profile.tags.gXYZ = sRGB.tags.rXYZ
                    profile.tags.bXYZ = sRGB.tags.gXYZ
            elif not is_primaries_only:
                # Use colprof to create profile
                result = self.exec_cmd(
                    cmd, args, low_contrast=False, skip_scripts=skip_scripts
                )
                if not isinstance(result, Exception) and result:
                    try:
                        profile = ICCP.ICCProfile(profile_path)
                    except (IOError, ICCP.ICCProfileInvalidError):
                        result = Error(
                            lang.getstr("profile.invalid") + "\n" + profile_path
                        )
        if not isinstance(result, Exception) and result:
            if getcfg("profile.type") == "X" or is_primaries_only:
                # Use our own accurate matrix
                cat = "Bradford"
                if not is_primaries_only:
                    cat = profile.guess_cat() or cat
                mtx = self._create_simple_matrix_profile(
                    ti3_RGB_XYZ,
                    ti3_remaining,
                    os.path.basename(args[-1]),
                    getcfg("copyright"),
                    display_manufacturer,
                    display_name,
                    (
                        getcfg("profile.type") in ("X", "x")
                        and getcfg("profile.b2a.hires")
                    )
                    or getcfg("profile.black_point_compensation"),
                    cat,
                )
                if is_primaries_only:
                    # Use matrix profile
                    profile = mtx

                    # Add luminance tag
                    luminance_XYZ_cdm2 = ti3.queryv1("LUMINANCE_XYZ_CDM2")
                    if luminance_XYZ_cdm2:
                        profile.tags.lumi = ICCP.XYZType(profile=profile)
                        profile.tags.lumi.Y = float(luminance_XYZ_cdm2.split()[1])

                    # Add blackpoint tag
                    profile.tags.bkpt = ICCP.XYZType(profile=profile)
                    if XYZbp:
                        black_XYZ = XYZbp
                    else:
                        black_XYZ = (0, 0, 0)
                    (
                        profile.tags.bkpt.X,
                        profile.tags.bkpt.Y,
                        profile.tags.bkpt.Z,
                    ) = black_XYZ

                    # Check if we have calibration, if so, add vcgt
                    for cgats in ti3.values():
                        if cgats.type == b"CAL":
                            profile.tags.vcgt = cal_to_vcgt(cgats)
                else:
                    # Add matrix tags to cLUT profile
                    for tagcls in ("XYZ", "TRC"):
                        for channel in "rgb":
                            tagname = channel + tagcls
                            profile.tags[tagname] = mtx.tags[tagname]
            if is_regular_grid or is_primaries_only:
                # Write profile
                profile.write(profile_path)
            if os.path.isfile(args[-1] + ".chrm"):
                # Get ChromaticityType tag
                with open(args[-1] + ".chrm", "rb") as blob:
                    chrm = ICCP.ChromaticityType(blob.read())
            else:
                chrm = None

            if XYZbp:
                Ybp = XYZbp[1]
                XYZbp = colormath.adapt(
                    *XYZbp,
                    whitepoint_source=[v / XYZwp[1] for v in XYZwp],
                    cat=profile.guess_cat() or "Bradford",
                )
                XYZbp = tuple(XYZbp)

        bpc_applied = False
        profchanged = False
        if not isinstance(result, Exception) and result:
            errors = self.errors
            output = self.output
            retcode = self.retcode
            try:
                if not profile:
                    profile = ICCP.ICCProfile(profile_path)
            except (IOError, ICCP.ICCProfileInvalidError):
                result = Error(lang.getstr("profile.invalid") + "\n" + profile_path)
            else:
                # Do we have a B2A0 table?
                has_B2A = "B2A0" in profile.tags
                # Hires CIECAM02 gamut mapping - perceptual and saturation
                # tables, also colorimetric table for non-RGB profiles
                # Use collink for smoother result.
                # Only for XYZ LUT and if source profile is a simple matrix
                # profile, otherwise CIECAM02 tables will already have been
                # created by colprof
                gamap = (
                    getcfg("gamap_perceptual") or getcfg("gamap_saturation")
                ) and getcfg("gamap_profile")
                collink = None
                if (
                    "A2B0" in profile.tags
                    and profile.connectionColorSpace == b"XYZ"
                    and (gamap or profile.colorSpace != b"RGB")
                    and getcfg("profile.b2a.hires")
                ):
                    collink = get_argyll_util("collink")
                    if not collink:
                        self.log(lang.getstr("argyll.util.not_found", "collink"))
                gamap_profiles = []
                gamap_profile = None
                if gamap and collink:
                    gamap_profile_filename = getcfg("gamap_profile")
                    try:
                        gamap_profile = ICCP.ICCProfile(gamap_profile_filename)
                    except (IOError, ICCProfileInvalidError) as exception:
                        self.log(exception)
                    else:
                        if (
                            not "A2B0" in gamap_profile.tags
                            and "rXYZ" in gamap_profile.tags
                            and "gXYZ" in gamap_profile.tags
                            and "bXYZ" in gamap_profile.tags
                            and "rTRC" in gamap_profile.tags
                            and "gTRC" in gamap_profile.tags
                            and "bTRC" in gamap_profile.tags
                        ):
                            # Simple matrix source profile
                            if gamap_profile.convert_iccv4_tags_to_iccv2():
                                # Write to temp file
                                fd, gamap_profile.fileName = mkstemp_bypath(
                                    gamap_profile_filename, dir=self.tempdir
                                )
                                stream = os.fdopen(fd, "wb")
                                gamap_profile.write(stream)
                                stream.close()
                                gamap_profiles.append(gamap_profile)
                            if profile.colorSpace == b"RGB" and has_B2A:
                                # Only table 0 (colorimetric) in display profile.
                                # Assign it to table 1 as per ICC spec to prepare
                                # for adding table 0 (perceptual) and 2 (saturation)
                                profile.tags.B2A1 = profile.tags.B2A0
                        else:
                            gamap_profile = None
                tables = []
                if gamap_profile or (collink and profile.colorSpace != b"RGB"):
                    self.log("-" * 80)
                    self.log("Creating CIECAM02 gamut mapping using collink")
                    size = getcfg("profile.b2a.hires.size")
                    # Make sure to map 'auto' value (-1) to an actual size
                    size = {-1: 33}.get(size, size)
                    collink_args = [
                        "-v",
                        "-q" + getcfg("profile.quality"),
                        "-G",
                        "-r%i" % size,
                    ]
                    if is_regular_grid:
                        # Do not preserve output shaper curves in devicelink
                        collink_args.append("-no")
                    if profile.colorSpace == b"RGB" and self.argyll_version >= [1, 7]:
                        # Use RGB->RGB forced black point hack
                        collink_args.append("-b")
                    if gamap_profile:
                        for tableno, cfgname in [
                            (0, "gamap_perceptual"),
                            (2, "gamap_saturation"),
                        ]:
                            if getcfg(cfgname):
                                tables.append((tableno, getcfg(cfgname + "_intent")))
                    if profile.colorSpace != b"RGB":
                        # Create colorimetric table for non-RGB profile
                        tables.insert(0, (1, "r"))
                        if not gamap_profile:
                            # Create perceptual table with
                            # luminance matched appearance rendering
                            # (similar to rel. col. + BPC)
                            tables.append((0, "la"))
                        # Get inking rules from colprof extra args
                        extra_args = getcfg("extra_args.colprof")
                        inking = re.findall(
                            r"-[Kk](?:[zhxr]|p[0-9.\s]+)|-[Ll][0-9.\s]+",
                            extra_args,
                        )
                        if inking:
                            collink_args.extend(parse_argument_string(" ".join(inking)))
                        # Get rid of lores B2A tables - they affect
                        # collink even in inverse forward lookup mode
                        # (probably because collink tries to determine inking
                        # rules by looking at B2A?)
                        for tableno in range(3):
                            tablename = "B2A%i" % tableno
                            if tablename in profile.tags:
                                del profile.tags[tablename]
                                profchanged = True
                        if profchanged:
                            # Need to write updated profile for xicclu/collink
                            profile.write()
                        # Input curve clipping.
                        # Setting to True makes rel. col. + BPC produce a
                        # smoother result, but reduces accuracy of the
                        # colorimetric table
                        input_curve_clipping = False
                        # Determine profile blackpoint
                        if input_curve_clipping:
                            # Figure out profile blackpoint by looking up
                            # neutral values from L* = 0 to L* = 50,
                            # in 0.1 increments
                            idata = []
                            for i in range(501):
                                idata.append((i / 10.0, 0, 0))
                            odata = self.xicclu(
                                profile,
                                idata,
                                intent="r",
                                direction="if",
                                pcs="l",
                                use_cam_clipping=True,
                                get_clip=True,
                            )
                            Labbp = (0, 0, 0)
                            for i, values in enumerate(odata):
                                if not values[-1]:
                                    # Not clipped
                                    Labbp = idata[i]
                                    break
                    ogamap_profile = gamap_profile
                    for tableno, intent in tables:
                        # Create device link(s)
                        gamap_args = []
                        if tableno == 1:
                            # Use PhotoPrintRGB as PCS if creating colorimetric
                            # table for non-RGB profile.
                            # PhotoPrintRGB is a synthetic L* TRC space
                            # with the Rec2020 red and blue adapted to D50
                            # and a green of x 0.1292 (same as blue x) y 0.8185
                            # It almost completely encompasses PhotoGamutRGB
                            pcs = get_data_path("ref/PhotoPrintRGB_Lstar.icc")
                            if pcs:
                                try:
                                    gamap_profile = ICCP.ICCProfile(pcs)
                                except (IOError, ICCProfileInvalidError) as exception:
                                    self.log(exception)
                            else:
                                missing = lang.getstr(
                                    "file.missing", "ref/PhotoPrintRGB_Lstar.icc"
                                )
                                if gamap_profile:
                                    self.log(missing)
                                else:
                                    result = Error(missing)
                                    break
                            if pcs and input_curve_clipping and Labbp:
                                self.log(
                                    "Applying black offset L*a*b* %.2f %.2f %.2f to %s..."
                                    % (Labbp + (gamap_profile.getDescription(),))
                                )
                                XYZbp = colormath.Lab2XYZ(*Labbp)
                                gamap_profile.apply_black_offset(XYZbp)
                                # Write to temp file because file changed
                                fd, gamap_profile.fileName = mkstemp_bypath(
                                    gamap_profile.fileName, dir=self.tempdir
                                )
                                stream = os.fdopen(fd, "wb")
                                gamap_profile.write(stream)
                                stream.close()
                                gamap_profiles.append(gamap_profile)
                        elif gamap:
                            gamap_profile = ogamap_profile
                            if getcfg("gamap_src_viewcond"):
                                gamap_args.append("-c" + getcfg("gamap_src_viewcond"))
                            if getcfg("gamap_out_viewcond"):
                                gamap_args.append("-d" + getcfg("gamap_out_viewcond"))
                        # Preserve input curves in resulting devicelink?
                        preserve_input_curves = True
                        if gamap_profile and not preserve_input_curves:
                            for channel in "rgb":
                                trc = gamap_profile.tags[channel + "TRC"]
                                trc_len = len(trc)
                                # Do not preserve input shaper curves if nonlinear
                                if trc_len > 1 or trc[0] != 1.0:
                                    if trc_len > 1:
                                        # Check if nonlinear (10 bit precision)
                                        values = [
                                            round(v / 65535.0 * 1023) for v in trc
                                        ]
                                        ivalues = [
                                            round(v / (trc_len - 1.0) * 1023)
                                            for v in range(trc_len)
                                        ]
                                        ni = values != ivalues
                                    else:
                                        # Single gamma != 1.0 (nonlinear)
                                        ni = True
                                    if ni and "-ni" not in collink_args:
                                        # Do not preserve input shaper curves in
                                        # devicelink
                                        collink_args.append("-ni")
                                        break
                                    elif not ni and "-ni" in collink_args:
                                        # Preserve input shaper curves in
                                        # devicelink
                                        collink_args.remove("-ni")
                                        break
                        link_profile = tempfile.mktemp(profile_ext, dir=self.tempdir)
                        result = self.exec_cmd(
                            collink,
                            collink_args
                            + gamap_args
                            + [
                                "-i" + intent,
                                gamap_profile.fileName,
                                profile_path,
                                link_profile,
                            ],
                            sessionlogfile=self.sessionlogfile,
                        )
                        if not isinstance(result, Exception) and result:
                            try:
                                link_profile = ICCP.ICCProfile(link_profile)
                            except (IOError, ICCP.ICCProfileInvalidError) as exception:
                                self.log(exception)
                                continue
                            table = "B2A%i" % tableno
                            profile.tags[table] = link_profile.tags.A2B0
                            if gamap_profile:
                                # Map B2A input curves to inverse source
                                # profile TRC
                                for i, channel in enumerate("rgb"):
                                    curve = profile.tags[table].input[i]
                                    trc = gamap_profile.tags[channel + "TRC"]
                                    if len(trc) == 1:
                                        trc.set_trc(trc[0], len(curve))
                                    elif len(trc) != len(curve):
                                        trc = colormath.interp_resize(
                                            trc, len(curve), use_numpy=True
                                        )
                                    interp = colormath.Interp(
                                        trc, curve, use_numpy=True
                                    )
                                    profile.tags[table].input[i] = icurve = []
                                    for j in range(4096):
                                        icurve.append(interp(j / 4095.0 * 65535))
                            # Remove temporary link profile
                            os.remove(link_profile.fileName)
                            # Update B2A matrix with source profile matrix
                            matrix = colormath.Matrix3x3(
                                [
                                    [
                                        gamap_profile.tags.rXYZ.X,
                                        gamap_profile.tags.gXYZ.X,
                                        gamap_profile.tags.bXYZ.X,
                                    ],
                                    [
                                        gamap_profile.tags.rXYZ.Y,
                                        gamap_profile.tags.gXYZ.Y,
                                        gamap_profile.tags.bXYZ.Y,
                                    ],
                                    [
                                        gamap_profile.tags.rXYZ.Z,
                                        gamap_profile.tags.gXYZ.Z,
                                        gamap_profile.tags.bXYZ.Z,
                                    ],
                                ]
                            )
                            matrix.invert()
                            scale = 1 + (32767 / 32768.0)
                            matrix *= colormath.Matrix3x3(
                                ((scale, 0, 0), (0, scale, 0), (0, 0, scale))
                            )
                            profile.tags[table].matrix = matrix
                            profchanged = True
                        else:
                            break
                elif (
                    getcfg("profile.b2a.hires")
                    and getcfg("profile.b2a.hires.smooth")
                    and gamap
                ):
                    # Smooth existing B2A tables
                    linebuffered_logfiles = []
                    if (
                        sys.stdout
                        and hasattr(sys.stdout, "isatty")
                        and sys.stdout.isatty()
                    ):
                        linebuffered_logfiles.append(print)
                    else:
                        linebuffered_logfiles.append(log)
                    if self.sessionlogfile:
                        linebuffered_logfiles.append(self.sessionlogfile)
                    logfiles = Files(
                        [
                            LineBufferedStream(
                                FilteredStream(
                                    Files(linebuffered_logfiles),
                                    enc,
                                    discard="",
                                    linesep_in="\n",
                                    triggers=[],
                                )
                            ),
                            self.recent,
                            self.lastmsg,
                        ]
                    )
                    smooth_tables = []
                    for tableno in (0, 2):
                        table = profile.tags.get("B2A%i" % tableno)
                        if table in smooth_tables:
                            continue
                        if self.smooth_B2A(
                            profile,
                            tableno,
                            getcfg("profile.b2a.hires.diagpng") and 2,
                            logfile=logfiles,
                        ):
                            smooth_tables.append(table)
                            profchanged = True
            self.errors = errors
            self.output = output
            self.retcode = retcode
            if not isinstance(result, Exception) and result:
                for gamap_profile in gamap_profiles:
                    if (
                        gamap_profile
                        and os.path.dirname(gamap_profile.fileName) == self.tempdir
                    ):
                        # Remove temporary source profile
                        os.remove(gamap_profile.fileName)
                if profchanged and tables:
                    # Make sure we match Argyll colprof i.e. have a complete
                    # set of tables
                    if "A2B1" not in profile.tags:
                        profile.tags.A2B1 = profile.tags.A2B0
                    if "A2B2" not in profile.tags:
                        profile.tags.A2B2 = profile.tags.A2B0

                if (
                    profile.colorSpace == b"RGB"
                    and profile.connectionColorSpace in (b"XYZ", b"Lab")
                    and "A2B0" in profile.tags
                    and (getcfg("profile.b2a.hires") or "B2A1" in profile.tags)
                ):
                    # Apply BPC to A2B0/A2B2 to match B2A0/B2A2 black

                    if profchanged:
                        # We need to write the changed profile
                        try:
                            profile.write()
                        except Exception as exception:
                            return exception

                    if "A2B1" not in profile.tags:
                        self.log("Generating A2B1 by copying A2B0")
                        profile.tags.A2B1 = profile.tags.A2B0
                    A2B1 = profile.tags.get("A2B1")
                    a2b_tables = [0]
                    if profile.tags.get("B2A2"):
                        a2b_tables.append(2)

                    D50 = colormath.get_whitepoint("D50")

                    XYZrgb = self.xicclu(
                        profile, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], pcs="x"
                    )
                    Xr, Yr, Zr = XYZrgb[0]
                    Xg, Yg, Zg = XYZrgb[1]
                    Xb, Yb, Zb = XYZrgb[2]
                    m1 = colormath.Matrix3x3(
                        ((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))
                    ).inverted()
                    Sr, Sg, Sb = m1 * D50
                    m2 = colormath.Matrix3x3(
                        (
                            (Sr * Xr, Sg * Xg, Sb * Xb),
                            (Sr * Yr, Sg * Yg, Sb * Yb),
                            (Sr * Zr, Sg * Zg, Sb * Zb),
                        )
                    ).inverted()

                    for tableno in a2b_tables:
                        tablename = "A2B%i" % tableno
                        table = profile.tags.get(tablename)
                        if not table:
                            continue
                        if tables:
                            # Get inverse B2A0/B2A2 black
                            XYZbp_B2A = self.xicclu(
                                profile,
                                [[0, 0, 0]],
                                intent="prs"[tableno],
                                direction="ib",
                                pcs="x",
                            )[0]
                            XYZbp_B2A = tuple(XYZbp_B2A)
                        else:
                            XYZbp_B2A = (0, 0, 0)
                        Labbp_B2A = colormath.XYZ2Lab(*XYZbp_B2A, scale=1)
                        if XYZbp and (0, 0, 0) not in (XYZbp, XYZbp_B2A):
                            # Make it same hue as relcol black
                            self.log(
                                "Inverse B2A%i" % tableno,
                                "blackpoint L*a*b* "
                                "%.6f %.6f %.6f" % tuple(Labbp_B2A),
                            )
                            if XYZbp_B2A != (0, 0, 0):
                                # Always...
                                continue
                            Labbp_B2A = (Labbp_B2A[0], Labbp[1], Labbp[2])
                            self.log(
                                "Adjusted",
                                tablename,
                                "blackpoint L*a*b* "
                                "%.6f %.6f %.6f" % tuple(Labbp_B2A),
                            )
                            XYZbp_B2A = colormath.Lab2XYZ(*Labbp_B2A)
                        if XYZbp_B2A == XYZbp:
                            continue
                        if table is A2B1 and not getcfg(
                            "profile.black_point_compensation"
                        ):
                            # Make A2B0/A2B2 a distinct table
                            self.log("Making distinct", tablename)
                            table = ICCP.LUT16Type(None, tablename, profile)
                            table.matrix = []
                            for row in A2B1.matrix:
                                table.matrix.append(list(row))
                            table.input = []
                            table.output = []
                            for curves in ("input", "output"):
                                for channel in getattr(A2B1, curves):
                                    getattr(table, curves).append(list(channel))
                            table.clut = []
                            for block in A2B1.clut:
                                table.clut.append([])
                                for row in block:
                                    table.clut[-1].append(list(row))
                            profile.tags[tablename] = table
                        else:
                            table = profile.tags[tablename]
                        # Apply BPC to A2B0/A2B2
                        self.log(
                            "Applying black point compensation to %s:" % tablename,
                            "L*a*b* %.6f %.6f %.6f" % tuple(Labbp_B2A),
                        )
                        table.apply_black_offset(
                            XYZbp_B2A, None, self.thread_abort, lang.getstr("aborted")
                        )
                        profchanged = True
                        if XYZbp:
                            # Adjust for BPC
                            if XYZbp_B2A != (0, 0, 0):
                                XYZbp_A2B = XYZbp_B2A
                            else:
                                XYZbp_A2B = [v * Ybp for v in D50]
                            XYZtmp = list(XYZrgb)
                            for i, XYZ in enumerate(XYZtmp):
                                XYZtmp[i] = colormath.blend_blackpoint(
                                    *XYZ, bp_in=(0, 0, 0), bp_out=XYZbp_A2B
                                )
                            Xr, Yr, Zr = XYZtmp[0]
                            Xg, Yg, Zg = XYZtmp[1]
                            Xb, Yb, Zb = XYZtmp[2]
                            m3 = colormath.Matrix3x3(
                                ((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))
                            ).inverted()
                            Sr, Sg, Sb = m3 * D50
                            m4 = colormath.Matrix3x3(
                                (
                                    (Sr * Xr, Sg * Xg, Sb * Xb),
                                    (Sr * Yr, Sg * Yg, Sb * Yb),
                                    (Sr * Zr, Sg * Zg, Sb * Zb),
                                )
                            )

                            if debug:
                                for i in range(3):
                                    self.log(
                                        colormath.XYZ2xyY(*XYZrgb[i]),
                                        colormath.XYZ2xyY(*XYZtmp[i]),
                                        colormath.XYZ2xyY(*m4 * (m2 * XYZrgb[i])),
                                    )
                            interp = []
                            rinterp = []
                            osize = len(table.output[0])
                            omaxv = osize - 1.0
                            orange = [i / omaxv * 65535 for i in range(osize)]
                            for i in range(3):
                                interp.append(colormath.Interp(orange, table.output[i]))
                                rinterp.append(
                                    colormath.Interp(table.output[i], orange)
                                )
                            if len(table.clut[0]) < 33:
                                num_workers = 1
                            else:
                                num_workers = None
                            table.clut = sum(
                                pool_slice(
                                    ICCP._mp_apply,
                                    table.clut,
                                    (
                                        profile.connectionColorSpace,
                                        colormath.matmul,
                                        (m4, m2),
                                        D50,
                                        interp,
                                        rinterp,
                                        lang.getstr("aborted"),
                                    ),
                                    {},
                                    num_workers,
                                    self.thread_abort,
                                ),
                                [],
                            )

                # A2B processing
                process_A2B = (
                    "A2B0" in profile.tags
                    and profile.colorSpace == b"RGB"
                    and profile.connectionColorSpace in (b"XYZ", b"Lab")
                    and (
                        getcfg("profile.b2a.hires")
                        or getcfg("profile.quality.b2a") in ("l", "n")
                        or not has_B2A
                    )
                )
                if process_A2B:
                    if getcfg("profile.b2a.hires") or not has_B2A:
                        if profchanged:
                            # We need to write the changed profile before
                            # enhancing B2A resolution!
                            try:
                                profile.write()
                            except Exception as exception:
                                return exception
                        result = self.update_profile_B2A(profile)
                        if not isinstance(result, Exception) and result:
                            profchanged = True

            # All table processing done

            if not isinstance(result, Exception) and result:
                if profchanged and tables:
                    # Make sure we match Argyll colprof i.e. have a complete
                    # set of tables
                    if profile.colorSpace != b"RGB":
                        if len(tables) == 1:
                            # We only created a colorimetric table, the
                            # others are still low quality. Assign
                            # colorimetric table
                            profile.tags.B2A0 = profile.tags.B2A1
                        if len(tables) < 3:
                            # We only created colorimetric and/or perceptual
                            # tables, saturation table is still low quality.
                            # Assign perceptual table
                            profile.tags.B2A2 = profile.tags.B2A0
                    if "B2A2" not in profile.tags:
                        profile.tags.B2A2 = profile.tags.B2A0
                apply_bpc = (
                    getcfg("profile.black_point_compensation")
                    and "A2B0" not in profile.tags
                ) or (process_A2B and (getcfg("profile.b2a.hires") or not has_B2A))
                # If profile type is X (XYZ cLUT + matrix) add the matrix tags
                # from a lookup of a smaller testchart or A2B/B2A (faster
                # computation!). If profile is a shaper+matrix profile,
                # re-generate shaper curves from testchart with only
                # gray+primaries (better curve smoothness and neutrality)
                # Make sure we do this *after* all changes on the A2B/B2A tables
                # are done, because we may end up using them for lookup!
                if (
                    getcfg("profile.type") in ("X", "s", "S")
                    and profile.colorSpace == b"RGB"
                ):
                    if getcfg("profile.type") == "X":
                        if (
                            not isinstance(
                                profile.tags.get("vcgt"), ICCP.VideoCardGammaType
                            )
                            or profile.tags.vcgt.is_linear()
                        ):
                            # Use matrix from 3x shaper curves profile if vcgt
                            # is linear
                            ptype = "s"
                            if profchanged:
                                # We need to write the changed profile before
                                # creating TRC tags because we will be using
                                # lookup through A2B/B2A table!
                                try:
                                    profile.write()
                                except Exception as exception:
                                    return exception
                        else:
                            # Use matrix from single shaper curve profile if
                            # vcgt is nonlinear
                            ptype = "S"
                    else:
                        ptype = getcfg("profile.type")
                    result = self._create_matrix_profile(
                        args[-1], profile, ptype, "XYZ", apply_bpc
                    )
                    if isinstance(result, ICCP.ICCProfile):
                        result = True
                        profchanged = True
            if not isinstance(result, Exception) and result:
                if (
                    "rTRC" in profile.tags
                    and "gTRC" in profile.tags
                    and "bTRC" in profile.tags
                    and isinstance(profile.tags.rTRC, ICCP.CurveType)
                    and isinstance(profile.tags.gTRC, ICCP.CurveType)
                    and isinstance(profile.tags.bTRC, ICCP.CurveType)
                    and apply_bpc
                    and len(profile.tags.rTRC) > 1
                    and len(profile.tags.gTRC) > 1
                    and len(profile.tags.bTRC) > 1
                    and (
                        profile.tags.rTRC[0] != 0
                        or profile.tags.gTRC[0] != 0
                        or profile.tags.bTRC[0] != 0
                    )
                ):
                    self.log("-" * 80)
                    for component in ("r", "g", "b"):
                        self.log(
                            "Applying black point compensation to " "%sTRC" % component
                        )
                    profile.apply_black_offset(
                        (0, 0, 0), include_A2B=False, set_blackpoint=False
                    )
                    if getcfg("profile.black_point_compensation"):
                        bpc_applied = True
                    profchanged = True
            if profchanged and not isinstance(result, Exception) and result:
                if "bkpt" in profile.tags and bpc_applied:
                    # We need to update the blackpoint tag
                    try:
                        odata = self.xicclu(profile, (0, 0, 0), intent="a", pcs="x")
                        if len(odata) != 1 or len(odata[0]) != 3:
                            raise ValueError("Blackpoint is invalid: %s" % odata)
                    except Exception as exception:
                        self.log(exception)
                    else:
                        (
                            profile.tags.bkpt.X,
                            profile.tags.bkpt.Y,
                            profile.tags.bkpt.Z,
                        ) = odata[0]
                # We need to write the changed profile
                try:
                    profile.write()
                except Exception as exception:
                    return exception
            if os.path.isfile(args[-1] + ".ti3.backup") and os.path.isfile(
                args[-1] + ".ti3"
            ):
                # Restore backed up TI3
                os.rename(args[-1] + ".ti3", args[-1] + ".bpc.ti3")
                os.rename(args[-1] + ".ti3.backup", args[-1] + ".ti3")
                ti3_file = open(args[-1] + ".ti3", "rb")
                ti3 = ti3_file.read()
                ti3_file.close()
            elif not is_regular_grid and not is_primaries_only:
                ti3 = None
            if not isinstance(result, Exception) and result:
                # Always explicitly do profile self check
                self.exec_cmd(
                    get_argyll_util("profcheck"),
                    [args[-1] + ".ti3", args[-1] + profile_ext],
                    capture_output=True,
                    skip_scripts=True,
                )
        # Get profile max and avg err to be later added to metadata
        # Argyll outputs the following:
        # Profile check complete, peak err = x.xxxxxx, avg err = x.xxxxxx, RMS = x.xxxxxx
        peak = None
        avg = None
        rms = None
        for line in self.output:
            if line.startswith("Profile check complete"):
                peak = re.search(r"(?:peak err|max\.) = (\d+(?:\.\d+))", line)
                avg = re.search(r"avg(?: err|\.) = (\d+(?:\.\d+))", line)
                rms = re.search(r"RMS = (\d+(?:\.\d+))", line)
                if peak:
                    peak = peak.groups()[0]
                if avg:
                    avg = avg.groups()[0]
                if rms:
                    rms = rms.groups()[0]
                break
        if not isinstance(result, Exception) and result:
            (gamut_volume, gamut_coverage) = self.create_gamut_views(profile_path)
        self.log("-" * 80)
        if not isinstance(result, Exception) and result:
            result = self.update_profile(
                profile,
                ti3,
                chrm,
                tags,
                avg,
                peak,
                rms,
                gamut_volume,
                gamut_coverage,
                quality=getcfg("profile.quality"),
            )
        result2 = self.wrapup(
            not isinstance(result, UnloggedInfo) and result, dst_path=dst_path
        )
        if isinstance(result2, Exception):
            if isinstance(result, Exception):
                result = Error(str(result) + "\n\n" + str(result2))
            else:
                result = result2
        elif not isinstance(result, Exception) and result:
            setcfg("last_cal_or_icc_path", dst_path)
            setcfg("last_icc_path", dst_path)
        return result

    def create_RGB_XYZ_cLUT_fwd_profile(
        self,
        ti3,
        description,
        copyright,
        manufacturer,
        model,
        logfn=None,
        clutres=33,
        cat="Bradford",
    ):
        """Create a RGB to XYZ forward profile"""
        # Extract grays and remaining colors
        (ti3_extracted, RGB_XYZ, remaining) = extract_device_gray_primaries(
            ti3, True, logfn
        )
        bwd_matrix = colormath.Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]])

        # Check if we have calibration, if so, add vcgt
        vcgt = False
        options_dispcal = []
        is_hq_cal = False
        for cgats in ti3.values():
            if cgats.type == b"CAL":
                vcgt = cal_to_vcgt(cgats)
                options_dispcal = get_options_from_cal(cgats)[0]
                is_hq_cal = "qh" in options_dispcal

        dEs = []
        RGB_XYZ = dict_sort(RGB_XYZ)
        for X, Y, Z in RGB_XYZ.values():
            if Y >= 1:
                X, Y, Z = colormath.adapt(X, Y, Z, RGB_XYZ[(100, 100, 100)], cat=cat)
                L, a, b = colormath.XYZ2Lab(X, Y, Z)
                dE = colormath.delta(L, 0, 0, L, a, b, "00")["E"]
                dEs.append(dE)
                if debug or verbose > 1:
                    self.log("L* %5.2f a* %5.2f b* %5.2f dE*00 %4.2f" % (L, a, b, dE))
        dE_avg = sum(dEs) / len(dEs)
        dE_max = max(dEs)
        self.log("R=G=B (>= 1% luminance) dE*00 avg", dE_avg, "peak", dE_max)

        # Create profile
        profile = ICCP.ICCProfile()
        profile.version = 2.2  # Match ArgyllCMS
        profile.setDescription(description)
        profile.setCopyright(copyright)
        if manufacturer:
            profile.setDeviceManufacturerDescription(manufacturer)
        if model:
            profile.setDeviceModelDescription(model)
        luminance_XYZ_cdm2 = ti3.queryv1("LUMINANCE_XYZ_CDM2")
        if luminance_XYZ_cdm2:
            profile.tags.lumi = ICCP.XYZType(profile=profile)
            profile.tags.lumi.Y = float(luminance_XYZ_cdm2.split()[1])
        profile.tags.wtpt = ICCP.XYZType(profile=profile)
        white_XYZ = [v / 100.0 for v in RGB_XYZ[(100, 100, 100)]]
        (profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z) = white_XYZ
        profile.tags.bkpt = ICCP.XYZType(profile=profile)
        black_XYZ = [v / 100.0 for v in RGB_XYZ[(0, 0, 0)]]
        (profile.tags.bkpt.X, profile.tags.bkpt.Y, profile.tags.bkpt.Z) = black_XYZ
        profile.tags.arts = ICCP.chromaticAdaptionTag()
        profile.tags.arts.update(colormath.get_cat_matrix(cat))

        # Check if we have calibration, if so, add vcgt
        if vcgt:
            profile.tags.vcgt = vcgt

        # Interpolate shaper curves from grays - returned curves are adapted
        # to D50
        self.single_curve = round(dE_max, 2) <= 1.25 and round(dE_avg, 2) <= 0.5
        if self.single_curve:
            self.log(
                "Got high quality calibration, using single device to PCS "
                "shaper curve for cLUT"
            )

        gray = create_shaper_curves(
            RGB_XYZ,
            bwd_matrix,
            self.single_curve,
            getcfg("profile.black_point_compensation"),
            logfn,
            profile=profile,
            options_dispcal=options_dispcal,
            optimize=self.single_curve,
            cat=cat,
        )

        curves = [curve[:] for curve in gray]

        # Add black back in
        XYZbp = [
            v / 100.0
            for v in colormath.adapt(
                *RGB_XYZ[(0, 0, 0)], whitepoint_source=RGB_XYZ[(100, 100, 100)], cat=cat
            )
        ]
        for i in range(len(gray[0])):
            (gray[0][i], gray[1][i], gray[2][i]) = colormath.apply_bpc(
                *(curve[i] for curve in gray), bp_in=(0, 0, 0), bp_out=XYZbp
            )

        grayinterp = [
            colormath.Interp(list(range(len(curve))), curve, use_numpy=True)
            for curve in gray
        ]

        def get_XYZ_from_curves(n, m):
            # Curves are adapted to D50
            return [interp((len(interp.xp) - 1.0) / m * n) for interp in grayinterp]

        # Quantize RGB to make lookup easier
        # XXX Note that round(50 * 2.55) = 127, but
        # round(50 / 100 * 255) = 128 (the latter is what we want)!
        remaining = dict(
            [
                (tuple(round(k / 100.0 * 255) for k in RGB), XYZ)
                for RGB, XYZ in remaining.items()
            ]
        )

        # Need to sort so columns increase (fastest to slowest) B G R
        remaining = dict_sort(remaining)

        # Build initial cLUT
        # Try to fill a 5x5x5 or 3x3x3 cLUT
        clut_actual = 0
        for iclutres in (17, 9, 5, 4, 3, 2):
            clut = []
            step = 100 / (iclutres - 1.0)
            for a in range(iclutres):
                for b in range(iclutres):
                    clut.append([])
                    for c in range(iclutres):
                        # XXX Note that round(50 * 2.55) = 127, but
                        # round(50 / 100 * 255) = 128 (the latter is what we want)!
                        RGB = tuple(round((k * step) / 100.0 * 255) for k in (a, b, c))
                        # Prefer actual measurements over interpolated values
                        XYZ = remaining.get(RGB)
                        if not XYZ:
                            if a == b == c:
                                # Fall back to interpolated values for gray
                                # (already black scaled)
                                XYZ = get_XYZ_from_curves(a, iclutres - 1)
                                # Range 0..1
                                clut[-1].append(XYZ)
                            elif iclutres > 2:
                                # Try next smaller cLUT res
                                break
                            else:
                                raise ValueError(
                                    "Measurement data is missing "
                                    "RGB %.4f %.4f %.4f" % RGB
                                )
                        else:
                            clut_actual += 1
                            X, Y, Z = (v / 100.0 for v in XYZ)
                            # # Need to black scale actual measurements
                            # X, Y, Z = colormath.blend_blackpoint(X, Y, Z,
                            # black_XYZ, None, white_XYZ)
                            # Range 0..1
                            clut[-1].append(
                                colormath.adapt(X, Y, Z, white_XYZ, cat=cat)
                            )
                    if c < iclutres - 1:
                        break
                if b < iclutres - 1:
                    break
            if a == iclutres - 1:
                break
        self.log("Initial cLUT resolution %ix%ix%i" % ((iclutres,) * 3))

        profile.tags.A2B0 = ICCP.create_RGB_A2B_XYZ(curves, clut, self.log)

        # Interpolate to higher cLUT resolution
        quality = getcfg("profile.quality")
        clutres = {"m": 17, "l": 9}.get(quality, clutres)
        # XXX: Need to implement proper 3D interpolation

        if clutres > iclutres:

            # Lookup input RGB to interpolated XYZ
            RGB_in = []
            step = 100 / (clutres - 1.0)
            for a in range(clutres):
                for b in range(clutres):
                    for c in range(clutres):
                        RGB_in.append([a * step, b * step, c * step])
            XYZ_out = self.xicclu(profile, RGB_in, "a", pcs="X", scale=100)
            profile.fileName = None

            # Create new cLUT
            clut = []
            i = -1
            actual = 0
            interpolated = 0
            for a in range(clutres):
                for b in range(clutres):
                    clut.append([])
                    for c in range(clutres):
                        # XXX Note that round(50 * 2.55) = 127, but
                        # round(50 / 100 * 255) = 128 (the latter is what we want)!
                        RGB = tuple(round((k * step) / 100.0 * 255) for k in (a, b, c))
                        # Prefer actual measurements over interpolated values
                        prev_actual = actual
                        XYZ = remaining.get(RGB)
                        i += 1
                        if not XYZ:
                            # Fall back to interpolated values
                            # (already black scaled)
                            if a == b == c:
                                XYZ = get_XYZ_from_curves(a, clutres - 1)
                                # Range 0..1
                                clut[-1].append(XYZ)
                                continue
                            else:
                                XYZ = XYZ_out[i]
                            interpolated += 1
                        else:
                            actual += 1
                        X, Y, Z = (v / 100.0 for v in XYZ)
                        # if actual > prev_actual:
                        # # Need to black scale actual measurements
                        # X, Y, Z = colormath.blend_blackpoint(X, Y, Z,
                        # black_XYZ, None, white_XYZ)
                        # Range 0..1
                        clut[-1].append(colormath.adapt(X, Y, Z, white_XYZ, cat=cat))
            if actual > clut_actual:
                # Did we get any additional actual measured cLUT points?
                self.log(
                    "cLUT resolution %ix%ix%i: Got %i "
                    "additional values from actual measurements"
                    % (clutres, clutres, clutres, actual - clut_actual)
                )

            profile.tags.A2B0 = ICCP.create_RGB_A2B_XYZ(curves, clut, self.log)
            clut_actual = actual

        self.log(
            "Final interpolated cLUT resolution %ix%ix%i"
            % ((len(profile.tags.A2B0.clut[0]),) * 3)
        )

        profile.tags.A2B0.profile = profile

        # # Add black back in
        # black_XYZ_D50 = colormath.adapt(*black_XYZ, whitepoint_source=white_XYZ, cat=cat)
        # profile.tags.A2B0.apply_black_offset(black_XYZ_D50)

        return profile

    def _create_simple_matrix_profile(
        self,
        ti3_RGB_XYZ,
        ti3_remaining,
        desc,
        copyright="No copyright",
        display_manufacturer=None,
        display_name=None,
        bpc=False,
        cat="Bradford",
    ):
        self.log("-" * 80)
        self.log("Creating matrix from primaries")
        xy = []
        XYZbp = ti3_RGB_XYZ[(0, 0, 0)]
        XYZwp = ti3_RGB_XYZ[(100, 100, 100)]
        for R, G, B in [(100, 0, 0), (0, 100, 0), (0, 0, 100), (100, 100, 100)]:
            if R == G == B:
                RGB_XYZ = ti3_RGB_XYZ
            else:
                RGB_XYZ = ti3_remaining
            X, Y, Z = RGB_XYZ[(R, G, B)]
            if XYZbp != (0, 0, 0) and not bpc:
                # Adjust for black offset
                X, Y, Z = colormath.blend_blackpoint(X, Y, Z, XYZbp, (0, 0, 0), XYZwp)
            xy.append(colormath.XYZ2xyY(*(v / 100 for v in (X, Y, Z)))[:2])
        self.log("Using chromatic adaptation transform matrix:", cat)
        mtx = ICCP.ICCProfile.from_chromaticities(
            xy[0][0],
            xy[0][1],
            xy[1][0],
            xy[1][1],
            xy[2][0],
            xy[2][1],
            xy[3][0],
            xy[3][1],
            2.2,  # Will be replaced
            desc,
            copyright,
            display_manufacturer,
            display_name,
            cat=cat,
        )
        return mtx

    def _create_matrix_profile(
        self, outname, profile=None, ptype="s", omit=None, bpc=False, cat="Bradford"
    ):
        """Create matrix profile from lookup through ti3

        <outname>.ti3 has to exist.
        If <profile> is given, it has to be an ICCProfile instance, and the
        matrix tags will be added to this profile.
        <ptype> should be the type of profile, i.e. one of g, G, s or S.
        <omit> if given should be the tag to omit, either 'TRC' or 'XYZ'.

        We use a testchart with only gray + primaries for TRC,
        and larger testchart for the matrix. This should give the smoothest
        overall result.

        Returns an ICCProfile with fileName set to <outname>.ic[cm].

        """
        if profile:
            cat = profile.guess_cat() or cat
        if omit == "XYZ":
            tags = "shaper"
        else:
            tags = "shaper+matrix"
        self.log("-" * 80)
        self.log("Creating %s tags in separate step" % tags)
        self.log("Using chromatic adaptation transform matrix:", cat)
        fakeread = get_argyll_util("fakeread")
        if not fakeread:
            return Error(lang.getstr("argyll.util.not_found", "fakeread"))
        colprof = get_argyll_util("colprof")
        if not colprof:
            return Error(lang.getstr("argyll.util.not_found", "colprof"))
        # Strip potential CAL from Ti3
        try:
            oti3 = CGATS.CGATS(outname + ".ti3")
        except (IOError, CGATS.CGATSError) as exception:
            return exception
        else:
            if 0 in oti3:
                ti3 = oti3[0]
                ti3.filename = oti3.filename  # So we can log the name
                ti3.fix_zero_measurements(logfile=self.get_logfiles(False))
            else:
                return Error(
                    lang.getstr("error.measurement.file_invalid", outname + ".ti3")
                )
        for ti1name, tagcls in [("d3-e4-s3-g52-m3-b0-f0", "XYZ"), (None, "TRC")]:
            if tagcls == omit:
                continue
            elif (
                tagcls == "TRC" and profile and "A2B0" in profile.tags and ptype == "s"
            ):
                # Create TRC from forward lookup through A2B
                numentries = 256
                maxval = numentries - 1.0
                RGBin = []
                for i in range(numentries):
                    RGBin.append((i / maxval,) * 3)
                if "B2A0" in profile.tags:
                    # Inverse backward
                    direction = "ib"
                else:
                    # Forward
                    direction = "f"
                try:
                    XYZout = self.xicclu(profile, RGBin, "p", direction, pcs="x")
                except Info as exception:
                    return exception
                # Get RGB space from already added matrix column tags
                rgb_space = colormath.get_rgb_space(profile.get_rgb_space("pcs", 1))
                mtx = rgb_space[-1].inverted()
                self.log("-" * 80)
                for channel in "rgb":
                    tagname = channel + tagcls
                    self.log(
                        "Adding %s from %s lookup to %s"
                        % (
                            tagname,
                            {"f": "forward A2B0", "ib": "inverse backward B2A0"}.get(
                                direction
                            ),
                            profile.getDescription(),
                        )
                    )
                    profile.tags[tagname] = ICCP.CurveType()
                for XYZ in XYZout:
                    RGB = mtx * XYZ
                    for i, channel in enumerate("rgb"):
                        tagname = channel + tagcls
                        profile.tags[tagname].append(min(max(RGB[i], 0), 1) * 65535)
                break
            if not ti1name:
                # Extract gray+primaries into new TI3
                (ti3, RGB_XYZ, remaining) = extract_device_gray_primaries(
                    ti3, tagcls == "TRC", self.log
                )
                ti3.sort_by_RGB()
                self.log(ti3.DATA)
                if tagcls == "TRC" and profile:
                    rgb_space = colormath.get_rgb_space(profile.get_rgb_space("pcs", 1))
                    fwd_mtx = rgb_space[-1]
                    bwd_mtx = fwd_mtx.inverted()

                    self.log("-" * 80)

                    options_dispcal = get_options_from_ti3(oti3)[0]

                    curves = create_shaper_curves(
                        RGB_XYZ,
                        bwd_mtx,
                        ptype == "S",
                        bpc,
                        self.log,
                        profile=profile,
                        options_dispcal=options_dispcal,
                        optimize=ptype == "S",
                        cat=cat,
                    )

                    for i, channel in enumerate("rgb"):
                        tagname = channel + tagcls
                        self.log(
                            "Adding %s from interpolation to %s"
                            % (tagname, profile.getDescription())
                        )
                        profile.tags[tagname] = trc = ICCP.CurveType(profile=profile)
                        # Slope limit for 16-bit encoding
                        trc[:] = [
                            max(v, j / 65535.0) * 65535 for j, v in enumerate(curves[i])
                        ]

                    if not bpc:
                        XYZbp = None
                        for R, G, B in RGB_XYZ:
                            X, Y, Z = RGB_XYZ[(R, G, B)]
                            if R == G == B == 0:
                                XYZbp = [v / 100 for v in (X, Y, Z)]
                                XYZbp = colormath.adapt(
                                    *XYZbp,
                                    whitepoint_source=RGB_XYZ[(100, 100, 100)],
                                    cat=cat,
                                )
                        if XYZbp:
                            # Add black back in
                            profile.apply_black_offset(XYZbp, include_A2B=False)
                    if ptype == "S":
                        # Single curve
                        profile.tags["rTRC"][:] = profile.tags["gTRC"][:]
                        profile.tags["bTRC"][:] = profile.tags["gTRC"][:]

                    break
            ti3.write(f"{outname}.0.ti3")
            if ti1name:
                ti1 = get_data_path(f"ti1/{ti1name}.ti1")
                if not ti1:
                    return Error(lang.getstr("file.missing", f"ti1/{ti1name}.ti1"))
                fakeout = f"{outname }.{ti1name}"
                try:
                    shutil.copyfile(ti1, f"{fakeout}.ti1")
                except EnvironmentError as exception:
                    return exception
                # Lookup ti1 through ti3
                result = self.exec_cmd(
                    fakeread,
                    [f"{outname}.0.ti3", fakeout],
                    capture_output=True,
                    skip_scripts=True,
                    sessionlogfile=self.sessionlogfile,
                )
                try:
                    os.remove(f"{fakeout}.ti1")
                except EnvironmentError as exception:
                    self.log(exception)
                if not result:
                    return UnloggedError("\n".join(self.errors))
                elif isinstance(result, Exception):
                    return result
                try:
                    os.remove(f"{outname}.0.ti3")
                except EnvironmentError as exception:
                    self.log(exception)
            else:
                # Use gray+primaries from existing ti3
                fakeout = f"{outname}.0"
            result = self.exec_cmd(
                colprof,
                ["-v", "-q" + getcfg("profile.quality"), "-a" + ptype, fakeout],
                sessionlogfile=self.sessionlogfile,
            )
            try:
                os.remove(f"{fakeout}.ti3")
            except EnvironmentError as exception:
                self.log(exception)
            if isinstance(result, Exception) or not result:
                return result
            try:
                matrix_profile = ICCP.ICCProfile(fakeout + profile_ext)
            except (IOError, ICCP.ICCProfileInvalidError):
                return Error(
                    lang.getstr("profile.invalid") + "\n" + fakeout + profile_ext
                )
            if profile:
                self.log("-" * 80)
                for channel in "rgb":
                    tagname = channel + tagcls
                    tag = matrix_profile.tags.get(tagname)
                    if tag:
                        self.log(
                            "Adding %s from matrix profile to %s"
                            % (tagname, profile.getDescription())
                        )
                        profile.tags[tagname] = tag
                    else:
                        self.log(lang.getstr("profile.required_tags_missing", tagname))
            else:
                profile = matrix_profile
                profile.fileName = outname + profile_ext
            try:
                os.remove(fakeout + profile_ext)
            except EnvironmentError as exception:
                self.log(exception)
        return profile

    def update_profile(
        self,
        profile,
        ti3=None,
        chrm=None,
        tags=None,
        avg=None,
        peak=None,
        rms=None,
        gamut_volume=None,
        gamut_coverage=None,
        quality=None,
    ):
        """Update profile tags and metadata"""
        if isinstance(profile, str):
            profile_path = profile
            try:
                profile = ICCP.ICCProfile(profile_path)
            except (IOError, ICCP.ICCProfileInvalidError):
                return Error(lang.getstr("profile.invalid") + "\n" + profile_path)
        else:
            profile_path = profile.fileName
        if (
            profile.profileClass == b"mntr"
            and profile.colorSpace == b"RGB"
            and not (self.tempdir and profile_path.startswith(self.tempdir))
        ):
            setcfg("last_cal_or_icc_path", profile_path)
            setcfg("last_icc_path", profile_path)
        if ti3:
            # Embed original TI3
            profile.tags.targ = profile.tags.DevD = profile.tags.CIED = ICCP.TextType(
                b"text\0\0\0\0" + bytes(ti3) + b"\0", b"targ"
            )
        if chrm:
            # Add ChromaticityType tag
            profile.tags.chrm = chrm
        # Fixup desc tags - ASCII needs to be 7-bit
        # also add Unicode strings if different from ASCII
        if "desc" in profile.tags and isinstance(
            profile.tags.desc, ICCP.TextDescriptionType
        ):
            profile.setDescription(profile.getDescription())
        if "dmdd" in profile.tags and isinstance(
            profile.tags.dmdd, ICCP.TextDescriptionType
        ):
            profile.setDeviceModelDescription(profile.getDeviceModelDescription())
        if "dmnd" in profile.tags and isinstance(
            profile.tags.dmnd, ICCP.TextDescriptionType
        ):
            profile.setDeviceManufacturerDescription(
                profile.getDeviceManufacturerDescription()
            )
        if tags and tags is not True:
            # Add custom tags
            for tagname in tags:
                tag = tags[tagname]
                if tagname == "mmod":
                    profile.device["manufacturer"] = (
                        b"\0\0" + tag["manufacturer"][1] + tag["manufacturer"][0]
                    )
                    profile.device["model"] = (
                        b"\0\0" + tag["model"][0] + tag["model"][1]
                    )
                profile.tags[tagname] = tag
        elif tags is True:
            edid = self.get_display_edid()
            if edid:
                profile.device["manufacturer"] = (
                    b"\0\0" + edid["edid"][9:10] + edid["edid"][8:9]
                )
                profile.device["model"] = (
                    b"\0\0" + edid["edid"][11:12] + edid["edid"][10:11]
                )
                # Add Apple-specific 'mmod' tag (TODO: need full spec)
                mmod = (
                    b"mmod"
                    + (b"\x00" * 6)
                    + edid["edid"][8:10]
                    + (b"\x00" * 2)
                    + edid["edid"][11:12]
                    + edid["edid"][10:11]
                    + (b"\x00" * 4)
                    + (b"\x00" * 20)
                )
                profile.tags.mmod = ICCP.ICCProfileTag(mmod, "mmod")
                # Add new meta information based on EDID
                profile.set_edid_metadata(edid)
            elif "meta" not in profile.tags:
                # Make sure meta tag exists
                profile.tags.meta = ICCP.DictType()
        if tags is True or (tags and "meta" in tags):
            profile.tags.meta.update(
                {"CMF_product": appname, "CMF_binary": appname, "CMF_version": version}
            )
            # Set license
            profile.tags.meta["License"] = getcfg("profile.license")
            # Set profile quality
            quality = {"v": "very low", "l": "low", "m": "medium", "h": "high"}.get(
                quality
            )
            if quality:
                profile.tags.meta["Quality"] = quality
            spec_prefixes = "CMF_"
        if tags is True:
            # Set OPENICC_automatic_generated to "0"
            profile.tags.meta["OPENICC_automatic_generated"] = "0"
            # Set GCM DATA_source to "calib"
            profile.tags.meta["DATA_source"] = "calib"
            # Add instrument
            profile.tags.meta["MEASUREMENT_device"] = self.get_instrument_name().lower()
            spec_prefixes = "CMF_,DATA_,MEASUREMENT_,OPENICC_"
            # Add screen brightness if applicable
            if sys.platform not in ("darwin", "win32") and dbus_session:
                try:
                    iface = DBusObject(
                        BUSTYPE_SESSION,
                        "org.gnome.SettingsDaemon.Power",
                        "/org/gnome/SettingsDaemon/Power",
                        "Screen",
                    )
                    brightness = iface.get_percentage()
                except DBusException:
                    pass
                else:
                    profile.tags.meta["SCREEN_brightness"] = str(brightness)
                    spec_prefixes += ",SCREEN_"
            # Set device ID
            device_id = self.get_device_id(quirk=False, query=True)
            if device_id:
                profile.tags.meta["MAPPING_device_id"] = device_id
                spec_prefixes += ",MAPPING_"
        if tags is True or (tags and "meta" in tags):
            prefixes = (
                profile.tags.meta.getvalue("prefix", "", None) or spec_prefixes
            ).split(",")
            for prefix in spec_prefixes.split(","):
                if prefix not in prefixes:
                    prefixes.append(prefix)
            profile.tags.meta["prefix"] = ",".join(prefixes)
        if (avg, peak, rms) != (None,) * 3:
            # Make sure meta tag exists
            if "meta" not in profile.tags:
                profile.tags.meta = ICCP.DictType()
            # Update meta prefix
            prefixes = (
                profile.tags.meta.getvalue("prefix", "", None) or "ACCURACY_"
            ).split(",")
            if "ACCURACY_" not in prefixes:
                prefixes.append("ACCURACY_")
                profile.tags.meta["prefix"] = ",".join(prefixes)
            # Add error info
            if avg is not None:
                profile.tags.meta["ACCURACY_dE76_avg"] = avg
            if peak is not None:
                profile.tags.meta["ACCURACY_dE76_max"] = peak
            if rms is not None:
                profile.tags.meta["ACCURACY_dE76_rms"] = rms
        profile.set_gamut_metadata(gamut_volume, gamut_coverage)
        # Set default rendering intent
        if "B2A0" in profile.tags and (
            "B2A1" in profile.tags or "B2A2" in profile.tags
        ):
            profile.intent = {"p": 0, "r": 1, "s": 2, "a": 3}[
                getcfg("gamap_default_intent")
            ]
        # Check if we need to video scale vcgt
        if isinstance(profile.tags.get("vcgt"), ICCP.VideoCardGammaType):
            try:
                cal = extract_cal_from_profile(profile, None, False, prefer_cal=True)
            except Exception as exception:
                self.log(exception)
            else:
                white = False
                if cal:
                    if cal.queryv1("TV_OUTPUT_ENCODING") == "YES":
                        black, white = (16, 235)
                    else:
                        output_enc = cal.queryv1("OUTPUT_ENCODING")
                        if output_enc:
                            try:
                                black, white = (float(v) for v in output_enc.split())
                            except (TypeError, ValueError):
                                white = False
                if white and (black, white) != (0, 255):
                    self.log(
                        "Need to scale vcgt to video levels (%s..%s)" % (black, white)
                    )
                    # Need to create videoscaled vcgt from calibration
                    data = cal.queryv1("DATA")
                    if data:
                        self.log(
                            "Scaling vcgt to video levels (%s..%s)" % (black, white)
                        )
                        for entry in data.values():
                            for column in "RGB":
                                v_old = entry["RGB_" + column]
                                # For video encoding the extra bits of
                                # precision are created by bit shifting rather
                                # than scaling, so we need to scale the fp
                                # value to account for this
                                newmin = (black / 256.0) * (65536 / 65535.0)
                                newmax = (white / 256.0) * (65536 / 65535.0)
                                v_new = colormath.convert_range(
                                    v_old, 0, 1, newmin, newmax
                                )
                                entry["RGB_" + column] = v_new
                        profile.tags.vcgt = cal_to_vcgt(cal)
                    else:
                        self.log(
                            "Warning - no scaling applied - no " "calibration data!"
                        )
        # Calculate profile ID
        profile.calculateID()
        try:
            profile.write()
        except Exception as exception:
            return exception
        return True

    def get_logfiles(self, include_progress_buffers=True):
        linebuffered_logfiles = []
        if sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            linebuffered_logfiles.append(print)
        else:
            linebuffered_logfiles.append(log)
        if self.sessionlogfile:
            linebuffered_logfiles.append(self.sessionlogfile)
        logfiles = LineBufferedStream(
            FilteredStream(
                Files(linebuffered_logfiles),
                enc,
                discard="",
                linesep_in="\n",
                triggers=[],
            )
        )
        if include_progress_buffers:
            logfiles = Files([logfiles, self.recent, self.lastmsg])
        return logfiles

    def update_profile_B2A(
        self,
        profile,
        generate_perceptual_table=True,
        clutres=None,
        smooth=None,
        rgb_space=None,
    ):
        # Use reverse A2B interpolation to generate B2A table
        if not clutres:
            if getcfg("profile.b2a.hires"):
                # Chosen resolution
                clutres = getcfg("profile.b2a.hires.size")
            elif getcfg("profile.quality.b2a") in "ln":
                # Low quality/resolution
                clutres = 9
            else:
                # Medium quality/resolution
                clutres = 17
        if smooth is None:
            smooth = getcfg("profile.b2a.hires.smooth")
        logfiles = self.get_logfiles()
        tables = [1]
        self.log("-" * 80)
        # Add perceptual tables if not present
        if "A2B0" in profile.tags and "A2B1" not in profile.tags:
            if not isinstance(profile.tags.A2B0, ICCP.LUT16Type):
                self.log("%s: Can't process non-LUT16Type A2B0 table" % appname)
                return []
            try:
                # Copy A2B0
                logfiles.write("Generating A2B1 by copying A2B0\n")
                profile.tags.A2B1 = profile.tags.A2B0
                if "B2A0" in profile.tags:
                    # Copy B2A0
                    B2A0 = profile.tags.B2A0
                    profile.tags.B2A1 = B2A1 = ICCP.LUT16Type(None, "B2A1", profile)
                    B2A1.matrix = []
                    for row in B2A0.matrix:
                        B2A1.matrix.append(list(row))
                    B2A1.input = []
                    B2A1.output = []
                    for table in ("input", "output"):
                        for channel in getattr(B2A0, table):
                            getattr(B2A1, table).append(list(channel))
                    B2A1.clut = []
                    for block in B2A0.clut:
                        B2A1.clut.append([])
                        for row in block:
                            B2A1.clut[-1].append(list(row))
            except Exception as exception:
                return exception
        if "A2B2" not in profile.tags and generate_perceptual_table:
            # Argyll always creates a complete set of A2B / B2A tables if
            # colprof -s (perceptual) or -S (perceptual and saturation) is used,
            # so we can assume that if A2B2 is not present then it is safe to
            # re-generate B2A0 because it was not created by Argyll CMS.
            tables.append(0)
        # Invert A2B tables if present. Always invert colorimetric A2B table.
        rtables = []
        filename = profile.fileName
        for tableno in tables:
            if "A2B%i" % tableno in profile.tags:
                if (
                    "B2A%i" % tableno in profile.tags
                    and profile.tags["B2A%i" % tableno] in rtables
                ):
                    continue
                if not isinstance(profile.tags["A2B%i" % tableno], ICCP.LUT16Type):
                    self.log(
                        "%s: Can't process non-LUT16Type A2B%i table"
                        % (appname, tableno)
                    )
                    continue
                # Check if we want to apply BPC
                bpc = tableno != 1
                if bpc and (
                    profile.tags["A2B1"].clut[0][0] != [0, 0, 0]
                    or profile.tags["A2B1"].input[0][0] != 0
                    or profile.tags["A2B1"].input[1][0] != 0
                    or profile.tags["A2B1"].input[2][0] != 0
                    or profile.tags["A2B1"].output[0][0] != 0
                    or profile.tags["A2B1"].output[1][0] != 0
                    or profile.tags["A2B1"].output[2][0] != 0
                ):
                    # Need to apply BPC
                    table = ICCP.LUT16Type(profile=profile)
                    # Copy existing B2A1 table matrix, cLUT and output curves
                    table.matrix = rtables[0].matrix
                    table.clut = rtables[0].clut
                    table.output = rtables[0].output
                    profile.tags["B2A%i" % tableno] = table
                elif bpc:
                    # BPC not needed, copy existing B2A
                    profile.tags["B2A%i" % tableno] = rtables[0]
                    return rtables
                if not filename or not os.path.isfile(filename) or bpc:
                    # Write profile to temp dir
                    tempdir = self.create_tempdir()
                    if isinstance(tempdir, Exception):
                        return tempdir
                    fd, profile.fileName = tempfile.mkstemp(profile_ext, dir=tempdir)
                    stream = os.fdopen(fd, "wb")
                    profile.write(stream)
                    stream.close()
                    temp = True
                else:
                    temp = False
                # Invert A2B
                try:
                    result = self.generate_B2A_from_inverse_table(
                        profile,
                        clutres,
                        "A2B",
                        tableno,
                        bpc,
                        smooth,
                        rgb_space,
                        logfiles,
                        filename,
                        bpc,
                    )
                except (Error, Info) as exception:
                    return exception
                except Exception as exception:
                    self.log(traceback.format_exc())
                    return exception
                else:
                    if result:
                        rtables.append(profile.tags["B2A%i" % tableno])
                    else:
                        return False
                finally:
                    if temp:
                        os.remove(profile.fileName)
                        profile.fileName = filename
        return rtables

    def is_working(self):
        """Check if any Worker instance is busy. Return True or False."""
        for worker in workers:
            if not getattr(worker, "finished", True):
                return True
        return False

    def start_measurement(
        self,
        consumer,
        apply_calibration=True,
        progress_msg="",
        resume=False,
        continue_next=False,
    ):
        """Start a measurement and use a progress dialog for progress
        information"""
        self.start(
            consumer,
            self.measure,
            wkwargs={"apply_calibration": apply_calibration},
            progress_msg=progress_msg,
            resume=resume,
            continue_next=continue_next,
            pauseable=True,
        )

    def start_calibration(
        self, consumer, remove=False, progress_msg="", resume=False, continue_next=False
    ):
        """Start a calibration and use a progress dialog for progress
        information"""
        self.start(
            consumer,
            self.calibrate,
            wkwargs={"remove": remove},
            progress_msg=progress_msg,
            resume=resume,
            continue_next=continue_next,
            interactive_frame="adjust",
            pauseable=True,
        )

    def madtpg_init(self):
        if not hasattr(self, "madtpg"):
            if sys.platform == "win32" and getcfg("madtpg.native"):
                # Using native implementation (madHcNet32.dll)
                self.madtpg = madvr.MadTPG()
            else:
                # Using madVR net-protocol pure python implementation
                self.madtpg = madvr.MadTPG_Net()
                self.madtpg.debug = verbose

    def madtpg_connect(self):
        self.madtpg_init()
        self.patterngenerator = self.madtpg
        if self.madtpg.connect(method3=madvr.CM_StartLocalInstance, timeout3=3000):
            # Check madVR version
            madvr_version = self.madtpg.get_version()
            if not madvr_version or madvr_version < madvr.min_version:
                self.madtpg_disconnect(False)
                raise Error(lang.getstr("madvr.outdated", madvr.min_version))
            self.log(
                "Connected to madVR version %i.%i.%i.%i (%s)"
                % (madvr_version + (self.madtpg.uri,))
            )
            self.madtpg.set_osd_text("\u25b6")  # "Play" symbol
            return True
        return False

    def madtpg_disconnect(self, restore_settings=True):
        """Restore madVR settings and disconnect"""
        if restore_settings:
            self.madtpg_restore_settings()
        if self.madtpg.disconnect():
            self.log("Successfully disconnected from madTPG")

    def madtpg_restore_settings(
        self, reconnect=True, restore_fullscreen=None, restore_osd=None
    ):
        if restore_fullscreen is None:
            restore_fullscreen = getattr(self, "madtpg_previous_fullscreen", None)
        if restore_osd is None:
            restore_osd = getattr(self, "madtpg_osd", None) is False
        if restore_fullscreen or restore_osd:
            check = not reconnect or self.madtpg.get_version()
            if not check and reconnect:
                check = self.madtpg_connect()
            if check:
                if restore_fullscreen:
                    # Restore fullscreen
                    if self.madtpg.set_use_fullscreen_button(True):
                        self.log(
                            appname + ": Restored madTPG 'use fullscreen' "
                            "button state"
                        )
                        self.madtpg_previous_fullscreen = None
                    else:
                        self.log(
                            appname + ": Warning - couldn't restore madTPG "
                            "'use fullscreen' button state"
                        )
                    if not reconnect:
                        if self.madtpg.is_fse_mode_enabled():
                            # Allow three seconds for automatic switch to FSE
                            sleep(3)
                        # Allow three seconds for fullscreen to settle
                        sleep(3)
                if restore_osd:
                    # Restore disable OSD
                    if self.madtpg.set_disable_osd_button(True):
                        self.log(
                            appname + ": Restored madTPG 'disable OSD' " "button state"
                        )
                        self.madtpg_osd = None
                    else:
                        self.log(
                            appname + ": Warning - couldn't restore madTPG "
                            "'disable OSD' button state"
                        )
            else:
                buttons = []
                if restore_fullscreen:
                    buttons.append("'use fullscreen'")
                if restore_osd:
                    buttons.append("'disable OSD'")
                self.log(
                    appname + ": Warning - couldn't re-connect to madTPG "
                    "to restore %s button states" % "/".join(buttons)
                )

    def madtpg_show_osd(self, msg=None, leave_fullscreen=False):
        """Show madTPG OSD, optionally with message and leaving fullscreen"""
        if self.madtpg.is_fullscreen() and leave_fullscreen:
            self.madtpg_previous_fullscreen = True
            self.madtpg.set_use_fullscreen_button(False)
        self.madtpg_osd = not self.madtpg.is_disable_osd_button_pressed()
        if not self.madtpg_osd:
            self.madtpg.set_disable_osd_button(False)
        if msg:
            self.madtpg.set_osd_text(msg)
            if self.cmdname == "dispcal":
                self.madtpg.show_progress_bar(6)

    def measure(self, apply_calibration=True):
        """Measure the configured testchart"""
        result = self.detect_video_levels()
        if isinstance(result, Exception) or not result:
            return result
        precond_ti1 = None
        precond_ti3 = None
        testchart_file = getcfg("testchart.file")
        auto = getcfg("testchart.auto_optimize") or 7
        if testchart_file == "auto" and auto > 4:
            # Testchart auto-optimization
            # Create optimized testchart on-the-fly. To do this, create a
            # simple profile for preconditioning
            if config.get_display_name() == "Untethered":
                return Error(
                    lang.getstr("testchart.auto_optimize.untethered.unsupported")
                )
            # Use small testchart for grayscale+primaries (34 patches)
            precond_ti1_path = get_data_path("ti1/d3-e4-s2-g28-m0-b0-f0.ti1")
            precond_ti1 = CGATS.CGATS(precond_ti1_path)
            setcfg("testchart.file", precond_ti1_path)
            cmd, args = self.prepare_dispread(apply_calibration)
            setcfg("testchart.file", "auto")
            if not isinstance(cmd, Exception):
                # Measure testchart
                result = self.exec_cmd(cmd, args)
                if not isinstance(result, Exception) and result:
                    # Create preconditioning profile
                    self.pauseable = False
                    basename = args[-1]
                    precond_ti3 = CGATS.CGATS(basename + ".ti3")
                    precond_ti3.fix_zero_measurements(logfile=self.get_logfiles(False))
                    precond_ti3.write()
                    # Extract grays and remaining colors
                    (
                        ti3_extracted,
                        ti3_RGB_XYZ,
                        ti3_remaining,
                    ) = extract_device_gray_primaries(precond_ti3, True, self.log)
                    profile = self._create_simple_matrix_profile(
                        ti3_RGB_XYZ, ti3_remaining, os.path.basename(basename)
                    )
                    result = self._create_matrix_profile(basename, profile, omit="XYZ")
                    if not isinstance(result, Exception) and result:
                        # Write matrix profile
                        result.write(basename + profile_ext)
                        # Create optimized testchart
                        if getcfg("use_fancy_progress"):
                            # Fade out animation/sound
                            self.cmdname = get_argyll_utilname("targen")
                            # Allow time for fade out
                            sleep(4)
                        s = min(auto, 11) * 4 - 3
                        g = s * 3 - 2
                        f = get_total_patches(4, 4, s, g, auto, auto, 0)
                        f += 120
                        cmd, args = (
                            get_argyll_util("targen"),
                            [
                                "-v",
                                "-d3",
                                "-e4",
                                "-s%i" % s,
                                "-g%i" % g,
                                "-m0",
                                "-f%i" % f,
                                "-A1.0",
                            ],
                        )
                        if self.argyll_version >= [1, 1]:
                            args.append("-G")
                        if self.argyll_version >= [1, 3, 3]:
                            args.append("-N0.5")
                        if self.argyll_version >= [1, 6]:
                            args.extend(["-B4", "-b0"])
                        if self.argyll_version >= [1, 6, 2]:
                            args.append("-V1.6")
                        args.extend(["-c", basename + profile_ext, basename])
                        result = self.exec_cmd(cmd, args)
                        self.pauseable = True
            else:
                result = cmd
        else:
            result = True
            if testchart_file == "auto" and auto < 5:
                # Use pre-baked testchart
                if auto == 1:
                    testchart = "ti1/d3-e4-s2-g28-m0-b0-f0.ti1"
                elif auto == 2:
                    testchart = "ti1/d3-e4-s3-g52-m3-b0-f0.ti1"
                elif auto == 3:
                    testchart = "ti1/d3-e4-s4-g52-m4-b0-f0.ti1"
                else:
                    testchart = "ti1/d3-e4-s5-g52-m5-b0-f0.ti1"
                testchart_path = get_data_path(testchart)
                if testchart_path:
                    setcfg("testchart.file", testchart_path)
                else:
                    result = Error(lang.getstr("not_found", testchart))
        if not isinstance(result, Exception) and result:
            cmd, args = self.prepare_dispread(apply_calibration)
            if testchart_file == "auto":
                # Restore "auto" setting
                setcfg("testchart.file", "auto")
        else:
            cmd = result
        if not isinstance(cmd, Exception) and cmd:
            if config.get_display_name() == "Untethered":
                cmd, args2 = get_argyll_util("spotread"), ["-v", "-e"]
                if getcfg("extra_args.spotread").strip():
                    args2 += parse_argument_string(getcfg("extra_args.spotread"))
                result = self.add_measurement_features(
                    args2, False, allow_nondefault_observer=is_ccxx_testchart()
                )
                if isinstance(result, Exception):
                    return result
            else:
                args2 = args
            result = self.exec_cmd(cmd, args2)
            if not isinstance(result, Exception) and result:
                self.update_display_name_manufacturer(args[-1] + ".ti3")
                ti3 = args[-1] + ".ti3"
                if precond_ti3:
                    # Add patches from preconditioning measurements
                    ti3 = insert_ti_patches_omitting_RGB_duplicates(
                        precond_ti3, ti3, self.log
                    )
                options = {
                    "OBSERVER": get_cfg_option_from_args("observer", "-Q", args[:-1])
                }
                ti3 = add_keywords_to_cgats(ti3, options)
                if 1 in ti3:
                    # Add video level encoding flag if needed
                    black_white = False
                    if "-E" in args2:
                        black_white = (16, 235)
                    elif config.get_display_name() == "madVR":
                        # Get output encoding from madVR
                        # Note: 'tags' will only be True if creating profile
                        # directly after measurements, and only in that case will
                        # we want to query madVR
                        black_white = self.madtpg_bw_lvl
                    if black_white == (16, 235):
                        ti3[1].add_keyword("TV_OUTPUT_ENCODING", "YES")
                    elif black_white == (0, 255):
                        ti3[1].add_keyword("TV_OUTPUT_ENCODING", "NO")
                    elif black_white and black_white != (0, 255):
                        ti3[1].add_keyword(
                            "OUTPUT_ENCODING", " ".join(str(v) for v in black_white)
                        )
                ti3.write()
                # Restore original TI1
                ti1_orig = args[-1] + ".original.ti1"
                ti1 = args[-1] + ".ti1"
                if os.path.isfile(ti1_orig):
                    try:
                        if os.path.isfile(ti1):
                            # Should always exist
                            os.remove(ti1)
                        os.rename(ti1_orig, ti1)
                    except Exception as exception:
                        self.log(
                            "Warning - could not restore "
                            "backup of original TI1 file %s:" % str(ti1_orig),
                            exception,
                        )
                    else:
                        self.log("Restored backup of original TI1 file")
                if precond_ti1 and os.path.isfile(ti1):
                    # Need to add precond TI1 patches to TI1.
                    # Do this AFTER the measurements because we don't want to
                    # measure precond patches twice.
                    ti1 = insert_ti_patches_omitting_RGB_duplicates(
                        precond_ti1, ti1, self.log
                    )
                    ti1.write()
        else:
            result = cmd
        result2 = self.wrapup(
            not isinstance(result, UnloggedInfo) and result,
            isinstance(result, Exception) or not result,
        )
        if isinstance(result2, Exception):
            if isinstance(result, Exception):
                result = Error(str(result) + "\n\n" + str(result2))
            else:
                result = result2
        return result

    def ensure_patch_sequence(self, ti1, write=True):
        """Ensure correct patch sequence of TI1 file

        Return either the changed CGATS object or the original path/TI1

        """
        patch_sequence = getcfg("testchart.patch_sequence")
        if patch_sequence != "optimize_display_response_delay":
            # Need to re-order patches
            if not isinstance(ti1, CGATS.CGATS):
                try:
                    ti1 = CGATS.CGATS(ti1)
                except Exception as exception:
                    self.log(
                        "Warning - could not process TI1 file %s:" % str(ti1), exception
                    )
                    return ti1
            self.log(
                "Changing patch sequence:", lang.getstr("testchart." + patch_sequence)
            )
            if patch_sequence == "maximize_lightness_difference":
                result = ti1.checkerboard(sort1=CGATS.stable_sort_by_L)
            elif patch_sequence == "maximize_rec709_luma_difference":
                result = ti1.checkerboard(CGATS.sort_by_rec709_luma)
            elif patch_sequence == "maximize_RGB_difference":
                result = ti1.checkerboard(CGATS.sort_by_RGB_sum)
            elif patch_sequence == "vary_RGB_difference":
                result = ti1.checkerboard(
                    CGATS.sort_by_RGB, None, split_grays=True, shift=True
                )
            if not result:
                self.log("Warning - patch sequence was not changed")
            elif write:
                # Make a copy
                try:
                    shutil.copyfile(
                        ti1.filename,
                        os.path.splitext(ti1.filename)[0] + ".original.ti1",
                    )
                except Exception as exception:
                    self.log(
                        "Warning - could not make backup of TI1 file %s:"
                        % str(ti1.filename),
                        exception,
                    )
                # Write new TI1 to original filename
                try:
                    ti1.write()
                except Exception as exception:
                    self.log(
                        "Warning - could not write TI1 file %s:" % str(ti1.filename),
                        exception,
                    )
        return ti1

    def parse(self, txt):
        if not txt:
            return
        self.logger.info("%s" % txt)
        self.check_instrument_calibration(txt)
        self.check_instrument_place_on_screen(txt)
        self.check_instrument_sensor_position(txt)
        self.check_retry_measurement(txt)
        self.check_is_single_measurement(txt)
        self.check_spotread_result(txt)

    def audio_visual_feedback(self, txt):
        if isinstance(txt, bytes):
            txt = txt.decode()

        if self.cmdname in (
            get_argyll_utilname("dispcal"),
            get_argyll_utilname("dispread"),
            get_argyll_utilname("spotread"),
        ):
            if (
                self.cmdname == get_argyll_utilname("dispcal")
                and ", repeat" in txt.lower()
            ):
                self.repeat = True
            elif ", ok" in txt.lower():
                self.repeat = False
            if (
                re.search(r"Patch [2-9]\d* of ", txt, re.I)
                or (
                    re.search(
                        r"Patch \d+ of |The instrument can be removed from the screen",
                        txt,
                        re.I,
                    )
                    and self.patch_count > 1
                )
                or (
                    "Result is XYZ:" in txt
                    and not isinstance(self.progress_wnd, UntetheredFrame)
                )
            ):
                if self.cmdname == get_argyll_utilname("dispcal") and self.repeat:
                    if getcfg("measurement.play_sound") and hasattr(
                        self.progress_wnd, "sound_on_off_btn"
                    ):
                        self.measurement_sound.safe_play()
                else:
                    if getcfg("measurement.play_sound") and (
                        hasattr(self.progress_wnd, "sound_on_off_btn")
                        or isinstance(self.progress_wnd, DisplayUniformityFrame)
                        or getattr(self.progress_wnd, "Name", None)
                        == "VisualWhitepointEditor"
                    ):
                        self.commit_sound.safe_play()
                    if hasattr(self.progress_wnd, "animbmp"):
                        self.progress_wnd.animbmp.frame = 0

    def setup_patterngenerator(self, logfile=None):
        pgname = config.get_display_name(None, True)
        if self.patterngenerator:
            # Use existing pattern generator instance
            self.patterngenerator.logfile = logfile
            self.patterngenerator.use_video_levels = getcfg(
                "patterngenerator.use_video_levels"
            )
            if hasattr(self.patterngenerator, "conn"):
                # Try to use existing connection
                try:
                    self.patterngenerator_send(
                        (0.5,) * 3, raise_exceptions=True, increase_sent_count=False
                    )
                except (socket.error, http.client.HTTPException) as exception:
                    self.log(exception)
                    self.patterngenerator.disconnect_client()
        elif pgname == "Prisma":
            patterngenerator = PrismaPatternGeneratorClient
            self.patterngenerator = patterngenerator(
                host=getcfg("patterngenerator.prisma.host"),
                port=getcfg("patterngenerator.prisma.port"),
                use_video_levels=getcfg("patterngenerator.use_video_levels"),
                logfile=logfile,
            )
        elif pgname == "Web @ localhost":
            patterngenerator = WebWinHTTPPatternGeneratorServer
            self.patterngenerator = patterngenerator(
                port=getcfg("webserver.portnumber"), logfile=logfile
            )
        elif pgname.startswith("Chromecast "):
            from DisplayCAL.chromecast_patterngenerator import (
                ChromeCastPatternGenerator,
            )

            self.patterngenerator = ChromeCastPatternGenerator(
                name=self.get_display_name(), logfile=logfile
            )
        elif pgname == "Resolve":
            # Resolve
            if getcfg("patterngenerator.resolve") == "LS":
                patterngenerator = ResolveLSPatternGeneratorServer
            else:
                patterngenerator = ResolveCMPatternGeneratorServer
            self.patterngenerator = patterngenerator(
                port=getcfg("patterngenerator.resolve.port"),
                use_video_levels=getcfg("patterngenerator.use_video_levels"),
                logfile=logfile,
            )

    @property
    def patterngenerator(self):
        pgname = config.get_display_name()
        return self._patterngenerators.get(pgname)

    @patterngenerator.setter
    def patterngenerator(self, patterngenerator):
        pgname = config.get_display_name()
        self._patterngenerators[pgname] = patterngenerator

    @property
    def patterngenerators(self):
        return self._patterngenerators

    def patterngenerator_send(
        self, rgb, bgrgb=None, raise_exceptions=False, increase_sent_count=True
    ):
        """Send RGB color to pattern generator"""
        if getattr(self, "abort_requested", False):
            return
        x, y, w, h, size = get_pattern_geometry()
        if bgrgb is not None:
            pass
        elif getcfg("measure.darken_background"):
            bgrgb = (0, 0, 0)
        elif size == 1.0:
            bgrgb = list(rgb)
        else:
            # Constant APL (matches madTPG 'gamma light')
            desired_apl = getcfg("patterngenerator.apl")
            bgrgb = [min(max(desired_apl - v * size, 0) / (1.0 - size), 1) for v in rgb]
            bgrgb_apl = sum(bgrgb) / 3.0 * (1 - size)
            rgb_apl = sum(rgb) / 3.0 * size
            needed_bgrgb_apl = max(desired_apl - rgb_apl, 0)
            if bgrgb_apl > needed_bgrgb_apl:
                f = needed_bgrgb_apl / bgrgb_apl
                bgrgb = [v * f for v in bgrgb]
        self.log(
            f"{appname}: Sending RGB {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f}, "
            f"background RGB {bgrgb[0]:.3f} {bgrgb[1]:.3f} {bgrgb[2]:.3f}, "
            f"x {x:.4f}, y {y:.4f}, w {w:.4f}, h {h:.4f}"
        )
        if self._use_patternwindow:
            # Preliminary Wayland support. This still needs a lot
            # of work as Argyll doesn't support Wayland natively yet,
            # so we use virtual display to drive our own patch window.
            self._patterngenerator_wait = True
            wx.CallAfter(self.owner.measureframe.show_rgb, rgb)
            # Wait for call to return
            while self._patterngenerator_wait and not self.subprocess_abort:
                sleep(0.001)
        else:
            try:
                self.patterngenerator.send(rgb, bgrgb, x=x, y=y, w=w, h=h)
            except Exception as exception:
                if raise_exceptions:
                    raise
                else:
                    self.exec_cmd_returnvalue = exception
                    self.abort_subprocess()
                return
        if increase_sent_count:
            self.patterngenerator_sent_count += 1
            self.log(
                "%s: Patterngenerator sent count: %i"
                % (appname, self.patterngenerator_sent_count)
            )

    @property
    def pauseable(self):
        return self._pauseable

    @pauseable.setter
    def pauseable(self, pauseable):
        self._pauseable = pauseable
        self.pauseable_now = False

    def pause_continue(self):
        if not self.pauseable or not self.pauseable_now:
            return
        if getattr(self.progress_wnd, "paused", False) and not getattr(
            self, "paused", False
        ):
            self.paused = True
            self.log("%s: Pausing..." % appname)
            self.safe_send("\x1b")
            if self.use_madnet_tpg:
                self.madtpg.set_osd_text("\u23f8")  # "Pause" symbol
        elif not getattr(self.progress_wnd, "paused", False) and getattr(
            self, "paused", False
        ):
            self.paused = False
            self.log("%s: Continuing..." % appname)
            self.safe_send(" ")
            if self.use_madnet_tpg:
                self.madtpg.set_osd_text("\u25b6")  # "Play" symbol

    def prepare_colprof(
        self, profile_name=None, display_name=None, display_manufacturer=None, tags=None
    ):
        """Prepare a colprof commandline.

        All options are read from the user configuration.
        Profile name and display name can be overridden by passing thecorresponding arguments.
        """
        if profile_name is None:
            profile_name = getcfg("profile.name.expanded")
        in_out_file = self.setup_inout(profile_name)
        if not in_out_file or isinstance(in_out_file, Exception):
            return in_out_file, None
        if not os.path.exists(f"{in_out_file}.ti3"):
            return (
                Error(
                    lang.getstr("error.measurement.file_missing", f"{in_out_file}.ti3")
                ),
                None,
            )
        if not os.path.isfile(f"{in_out_file}.ti3"):
            return Error(lang.getstr("file_notfile", f"{in_out_file}.ti3")), None

        cmd = get_argyll_util("colprof")
        args = ["-v", f"-q{getcfg('profile.quality')}", f"-a{getcfg('profile.type')}"]
        gamap_args = args
        if getcfg("profile.type") in ["l", "x", "X"]:
            if getcfg("gamap_saturation"):
                gamap = "S"
            elif getcfg("gamap_perceptual"):
                gamap = "s"
            else:
                gamap = None
            gamap_profile = None
            if gamap and getcfg("gamap_profile"):
                # CIECAM02 gamut mapping - perceptual and saturation tables
                # Only for L*a*b* LUT or if source profile is not a simple matrix
                # profile, otherwise create hires CIECAM02 tables with collink
                try:
                    gamap_profile = ICCP.ICCProfile(getcfg("gamap_profile"))
                except ICCP.ICCProfileInvalidError as exception:
                    self.log(exception)
                    return Error(
                        lang.getstr("profile.invalid") + "\n" + getcfg("gamap_profile")
                    )
                except IOError as exception:
                    return exception
                if (
                    getcfg("profile.type") != "l"
                    and getcfg("profile.b2a.hires")
                    and "A2B0" not in gamap_profile.tags
                    and "rXYZ" in gamap_profile.tags
                    and "gXYZ" in gamap_profile.tags
                    and "bXYZ" in gamap_profile.tags
                    and "rTRC" in gamap_profile.tags
                    and "gTRC" in gamap_profile.tags
                    and "bTRC" in gamap_profile.tags
                ):
                    self.log("Delegating CIECAM02 gamut mapping to collink")
                    # Make a copy, so we can store options without adding them
                    # to actual colprof arguments
                    gamap_args = []
                    gamap_profile = None
                gamap_args.append(f"-{gamap}")
                gamap_args.append(getcfg("gamap_profile"))
                gamap_args.append(f"-t{getcfg('gamap_perceptual_intent')}")
                if gamap == "S":
                    gamap_args.append(f"-T{getcfg('gamap_saturation_intent')}")
                if getcfg("gamap_src_viewcond"):
                    gamap_args.append(f"-c{getcfg('gamap_src_viewcond')}")
                if getcfg("gamap_out_viewcond"):
                    gamap_args.append(f"-d{getcfg('gamap_out_viewcond')}")
            b2a_q = getcfg("profile.quality.b2a")
            if (
                getcfg("profile.b2a.hires")
                and getcfg("profile.type") in ("l", "x", "X")
                and not (gamap and gamap_profile)
            ):
                rgb = False
                is_lab_clut_ptype = getcfg("profile.type") == "l"
                if is_lab_clut_ptype:
                    with open(f"{in_out_file}.ti3", "rb") as ti3_file:
                        for line in ti3_file:
                            if line.startswith(b"COLOR_REP"):
                                if b"RGB_XYZ" in line:
                                    rgb = True
                                break
                if rgb or not is_lab_clut_ptype:
                    # Disable B2A creation in colprof, B2A is handled
                    # by A2B inversion code (only for cLUT profiles)
                    b2a_q = "n"
            if b2a_q and b2a_q != getcfg("profile.quality"):
                args.append(f"-b{b2a_q}")
        args.append("-C")
        args.append(getcfg("copyright").encode("ASCII", "asciize").decode("utf-8"))
        if getcfg("extra_args.colprof").strip():
            args += parse_argument_string(getcfg("extra_args.colprof"))
        options_dispcal = []
        if "-d3" in self.options_targen:
            # only add display desc and dispcal options if creating RGB profile
            options_dispcal = self.options_dispcal
            if len(self.displays):
                args.extend(
                    self.update_display_name_manufacturer(
                        f"{in_out_file}.ti3",
                        display_name,
                        display_manufacturer,
                        write=False,
                    )
                )
        self.options_colprof = list(args)
        if gamap_args is not args:
            self.options_colprof.extend(gamap_args)
        args.append("-D")
        args.append(profile_name)
        args.append(in_out_file)
        # Add dispcal and colprof arguments to ti3
        ti3 = add_options_to_ti3(
            f"{in_out_file}.ti3", options_dispcal, self.options_colprof
        )
        if ti3:
            color_rep = (ti3.queryv1("COLOR_REP").decode("utf-8") or "").split("_")
            # Prepare ChromaticityType tag
            self.log("Preparing ChromaticityType tag from TI3 colorants")
            colorants = ti3.get_colorants()
            if colorants and None not in colorants:
                chrm = ICCP.ChromaticityType()
                chrm.type = 0
                for colorant in colorants:
                    if color_rep[1] == "LAB":
                        XYZ = colormath.Lab2XYZ(
                            colorant["LAB_L"], colorant["LAB_A"], colorant["LAB_B"]
                        )
                    else:
                        XYZ = (colorant["XYZ_X"], colorant["XYZ_Y"], colorant["XYZ_Z"])
                    chrm.channels.append(colormath.XYZ2xyY(*XYZ)[:-1])
                with open(in_out_file + ".chrm", "wb") as blob:
                    blob.write(chrm.tagData)
            self.log("Storing settings in TI3")
            # Black point compensation
            ti3[0].add_keyword(
                "USE_BLACK_POINT_COMPENSATION",
                "YES" if getcfg("profile.black_point_compensation") else "NO",
            )
            # Black point correction
            # NOTE that profile black point correction is not the same as
            # calibration black point correction!
            # See Worker.create_profile
            ti3[0].add_keyword(
                "BLACK_POINT_CORRECTION", getcfg("profile.black_point_correction")
            )
            # Hires B2A with optional smoothing
            ti3[0].add_keyword(
                "HIRES_B2A", "YES" if getcfg("profile.b2a.hires") else "NO"
            )
            ti3[0].add_keyword("HIRES_B2A_SIZE", getcfg("profile.b2a.hires.size"))
            ti3[0].add_keyword(
                "SMOOTH_B2A", "YES" if getcfg("profile.b2a.hires.smooth") else "NO"
            )
            # Display update delay
            if getcfg("measure.override_min_display_update_delay_ms"):
                ti3[0].add_keyword(
                    "MIN_DISPLAY_UPDATE_DELAY_MS",
                    getcfg("measure.min_display_update_delay_ms"),
                )
            # Display settle time multiplier
            if getcfg("measure.override_display_settle_time_mult"):
                ti3[0].add_keyword(
                    "DISPLAY_SETTLE_TIME_MULT",
                    getcfg("measure.display_settle_time_mult"),
                )
            # FFP
            if getcfg("patterngenerator.ffp_insertion"):
                for keyword in ("INTERVAL", "DURATION", "LEVEL"):
                    ti3[0].add_keyword(
                        "FFP_INSERTION_%s" % keyword,
                        getcfg("patterngenerator.ffp_insertion.%s" % keyword.lower()),
                    )
            # Remove AUTO_OPTIMIZE
            if ti3[0].queryv1("AUTO_OPTIMIZE"):
                ti3[0].remove_keyword("AUTO_OPTIMIZE")
            # Patch sequence
            ti3[0].add_keyword(
                "PATCH_SEQUENCE", getcfg("testchart.patch_sequence").upper()
            )
            # Add 3D LUT options if set, else remove them
            for keyword, cfgname in {
                "3DLUT_SOURCE_PROFILE": "3dlut.input.profile",
                "3DLUT_TRC": "3dlut.trc",
                "3DLUT_HDR_PEAK_LUMINANCE": "3dlut.hdr_peak_luminance",
                "3DLUT_HDR_SAT": "3dlut.hdr_sat",
                "3DLUT_HDR_HUE": "3dlut.hdr_hue",
                "3DLUT_HDR_MAXMLL": "3dlut.hdr_maxmll",
                "3DLUT_HDR_MAXMLL_ALT_CLIP": "3dlut.hdr_maxmll_alt_clip",
                "3DLUT_HDR_MINMLL": "3dlut.hdr_minmll",
                "3DLUT_HDR_AMBIENT_LUMINANCE": "3dlut.hdr_ambient_luminance",
                "3DLUT_HDR_DISPLAY": "3dlut.hdr_display",
                "3DLUT_GAMMA": "3dlut.trc_gamma",
                "3DLUT_DEGREE_OF_BLACK_OUTPUT_OFFSET": "3dlut.trc_output_offset",
                "3DLUT_INPUT_ENCODING": "3dlut.encoding.input",
                "3DLUT_OUTPUT_ENCODING": "3dlut.encoding.output",
                "3DLUT_GAMUT_MAPPING_MODE": "3dlut.gamap.use_b2a",
                "3DLUT_RENDERING_INTENT": "3dlut.rendering_intent",
                "3DLUT_FORMAT": "3dlut.format",
                "3DLUT_SIZE": "3dlut.size",
                "3DLUT_INPUT_BITDEPTH": "3dlut.bitdepth.input",
                "3DLUT_OUTPUT_BITDEPTH": "3dlut.bitdepth.output",
                "3DLUT_APPLY_CAL": "3dlut.output.profile.apply_cal",
                "SIMULATION_PROFILE": "measurement_report.simulation_profile",
            }.items():
                if getcfg("3dlut.create"):
                    value = getcfg(cfgname)
                    if cfgname == "3dlut.gamap.use_b2a":
                        if value:
                            value = "g"
                        else:
                            value = "G"
                    elif cfgname == "3dlut.trc_gamma":
                        if getcfg("3dlut.trc_gamma_type") == "B":
                            value = -value
                    elif (
                        cfgname == "3dlut.input.profile"
                        and os.path.basename(os.path.dirname(value)) == "ref"
                        and get_data_path("ref/" + os.path.basename(value)) == value
                    ):
                        # Store relative path instead of absolute path if
                        # ref file
                        value = "ref/" + os.path.basename(value)
                    elif cfgname == "measurement_report.simulation_profile":
                        if (
                            getcfg("3dlut.trc").startswith("smpte2084")
                            or getcfg("3dlut.trc") == "hlg"
                        ):
                            # Use 3D LUT profile
                            value = getcfg("3dlut.input.profile")
                            # Add 3D LUT HDR parameters and store only filename
                            # (file will be copied to profile dir)
                            fn, ext = os.path.splitext(os.path.basename(value))
                            lut3d_fn = self.lut3d_get_filename(fn, False, False)
                            value = lut3d_fn + ext
                        else:
                            value = None
                else:
                    value = None
                if value is not None:
                    ti3[0].add_keyword(keyword, safe_str(value, "utf-8"))
                elif keyword in ti3[0]:
                    ti3[0].remove_keyword(keyword)
            # 3D LUT content color space (currently only used for HDR)
            for color in ("white", "red", "green", "blue"):
                for coord in "xy":
                    keyword = "3DLUT_CONTENT_COLORSPACE_{}_{}".format(
                        color.upper(),
                        coord.upper(),
                    )
                    if getcfg("3dlut.create"):
                        value = getcfg(
                            "3dlut.content.colorspace.{}.{}".format(color, coord)
                        )
                        ti3[0].add_keyword(keyword, safe_str(value, "utf-8"))
                    elif keyword in ti3[0]:
                        ti3[0].remove_keyword(keyword)
            ti3[0].fix_zero_measurements(logfile=self.get_logfiles(False))
            ti3.write()
        return cmd, args

    def prepare_dispcal(self, calibrate=True, verify=False, dry_run=False):
        """Prepare a dispcal commandline.

        All options are read from the user configuration.
        You can choose if you want to calibrate and/or verify by passing
        the corresponding arguments.
        """
        cmd = get_argyll_util("dispcal")
        args = ["-v2"]
        if getcfg("argyll.debug"):
            args.append("-D8")
        result = self.add_measurement_features(args, allow_nondefault_observer=True)
        if isinstance(result, Exception):
            return result, None
        if calibrate:
            if getcfg("trc"):
                args.append("-q" + getcfg("calibration.quality"))
            inoutfile = self.setup_inout()
            if not inoutfile or isinstance(inoutfile, Exception):
                return inoutfile, None
            if getcfg("profile.update") or self.dispcal_create_fast_matrix_shaper:
                args.append("-o")
            if getcfg("calibration.update") and not dry_run:
                cal = getcfg("calibration.file", False)
                calcopy = os.path.join(f"{inoutfile}.cal")
                filename, ext = os.path.splitext(cal)
                ext = ".cal"
                cal = f"{filename}{ext}"
                if ext.lower() == ".cal":
                    result = check_cal_isfile(cal)
                    if isinstance(result, Exception):
                        return result, None
                    if not result:
                        return None, None
                    if not os.path.exists(calcopy):
                        try:
                            # Copy cal to profile dir
                            shutil.copyfile(cal, calcopy)
                        except Exception as exception:
                            return (
                                Error(
                                    lang.getstr("error.copy_failed", (cal, calcopy))
                                    + "\n\n"
                                    + str(exception)
                                ),
                                None,
                            )
                        result = check_cal_isfile(calcopy)
                        if isinstance(result, Exception):
                            return result, None
                        if not result:
                            return None, None
                        cal = calcopy
                else:
                    rslt = extract_fix_copy_cal(cal, calcopy)
                    if isinstance(rslt, ICCP.ICCProfileInvalidError):
                        return Error(lang.getstr("profile.invalid") + "\n" + cal), None
                    elif isinstance(rslt, Exception):
                        traceback.print_exc()
                        return (
                            Error(
                                lang.getstr("cal_extraction_failed")
                                + "\n"
                                + cal
                                + "\n\n"
                                + rslt
                            ),
                            None,
                        )
                    if not isinstance(rslt, list):
                        return None, None
                if getcfg("profile.update"):
                    profile_path = (
                        os.path.splitext(getcfg("calibration.file", False))[0]
                        + profile_ext
                    )
                    result = check_profile_isfile(profile_path)
                    if isinstance(result, Exception):
                        return result, None
                    if not result:
                        return None, None
                    profilecopy = os.path.join(inoutfile + profile_ext)
                    if not os.path.exists(profilecopy):
                        try:
                            # Copy profile to profile dir
                            shutil.copyfile(profile_path, profilecopy)
                        except Exception as exception:
                            return (
                                Error(
                                    lang.getstr(
                                        "error.copy_failed", (profile_path, profilecopy)
                                    )
                                    + "\n\n"
                                    + str(exception)
                                ),
                                None,
                            )
                        result = check_profile_isfile(profilecopy)
                        if isinstance(result, Exception):
                            return result, None
                        if not result:
                            return None, None
                args.append("-u")
        if calibrate or verify:
            if calibrate and not getcfg("calibration.interactive_display_adjustment"):
                # Skip interactive display adjustment
                args.append("-m")
            whitepoint_colortemp = getcfg("whitepoint.colortemp", False)
            whitepoint_x = getcfg("whitepoint.x", False)
            whitepoint_y = getcfg("whitepoint.y", False)
            if whitepoint_colortemp or None in (whitepoint_x, whitepoint_y):
                whitepoint = getcfg("whitepoint.colortemp.locus")
                if whitepoint_colortemp:
                    whitepoint += str(whitepoint_colortemp)
                args.append("-" + whitepoint)
            else:
                args.append("-w%s,%s" % (whitepoint_x, whitepoint_y))
            luminance = getcfg("calibration.luminance", False)
            self.log(f"{appname}: luminance: {luminance}")
            if luminance is not None:
                args.append(f"-b{luminance}")
            if getcfg("trc"):
                args.append("-" + getcfg("trc.type") + str(getcfg("trc")))
                args.append("-f%s" % getcfg("calibration.black_output_offset"))
                if bool(int(getcfg("calibration.ambient_viewcond_adjust"))):
                    # Argyll dispcal uses 20% of ambient (in lux,
                    # fixed steradiant of 3.1415) as adapting
                    # luminance, but we assume it already *is*
                    # the adapting luminance. To correct for this,
                    # scale so that dispcal gets the correct value.
                    ambient = getcfg("calibration.ambient_viewcond_adjust.lux")
                    args.append("-a%s" % (ambient * 5))
                if not getcfg("calibration.black_point_correction.auto"):
                    args.append("-k%s" % getcfg("calibration.black_point_correction"))
                if (
                    defaults["calibration.black_point_rate.enabled"]
                    and float(getcfg("calibration.black_point_correction")) < 1
                ):
                    black_point_rate = getcfg("calibration.black_point_rate")
                    if black_point_rate:
                        args.append("-A%s" % black_point_rate)
            black_luminance = getcfg("calibration.black_luminance", False)
            if black_luminance:
                args.append("-B%f" % black_luminance)
            elif (
                not (
                    getcfg("calibration.black_point_correction.auto")
                    or getcfg("calibration.black_point_correction")
                )
                and defaults["calibration.black_point_hack"]
            ):
                # Forced black point hack
                # (Argyll CMS 1.7b 2014-12-22)
                # Always use this if no black luminance or black point hue
                # correction specified. The rationale is that a reasonably good
                # quality digitally driven display should have no "dead zone"
                # above zero device input if set up correctly. Using this option
                # with a display that is not well behaved may result in a loss
                # of shadow detail.
                self.log("skipping -b parameter")
                # args.append("-b")
                pass
            if verify:
                if calibrate and type(verify) == int:
                    args.append("-e%s" % verify)  # Verify final computed curves
                elif self.argyll_version >= [1, 6]:
                    args.append("-z")  # Verify current curves
                else:
                    args.append("-E")  # Verify current curves
        if getcfg("extra_args.dispcal").strip():
            args += parse_argument_string(getcfg("extra_args.dispcal"))
        if config.get_display_name() == "Resolve" or (
            config.get_display_name() == "Prisma"
            and not defaults["patterngenerator.prisma.argyll"]
        ):
            # Substitute actual measurement frame dimensions
            self.options_dispcal = [
                re.sub(
                    r"^-[Pp]1,1,0.01$", "-P" + getcfg("dimensions.measureframe"), arg
                )
                for arg in args
            ]
            # Re-add -F (darken background) so it can be set when loading settings
            if getcfg("measure.darken_background"):
                self.options_dispcal.append("-F")
        else:
            self.options_dispcal = list(args)
        if calibrate:
            args.append(inoutfile)
        return cmd, args

    def prepare_dispread(self, apply_calibration=True):
        """Prepare a dispread commandline.

        All options are read from the user configuration.
        You can choose if you want to apply the current calibration,
        either the previously by dispcal created one by passing in True, by
        passing in a valid path to a .cal file, or by passing in None
        (current video card gamma table).
        """
        self.lastcmdname = get_argyll_utilname("dispread")
        inoutfile = self.setup_inout()
        if not inoutfile or isinstance(inoutfile, Exception):
            return inoutfile, None
        if not os.path.exists(f"{inoutfile}.ti1"):
            filename, ext = os.path.splitext(getcfg("testchart.file"))
            result = check_file_isfile(filename + ext)
            if isinstance(result, Exception):
                return result, None
            try:
                if ext.lower() in (".icc", ".icm"):
                    try:
                        profile = ICCP.ICCProfile(filename + ext)
                    except (IOError, ICCP.ICCProfileInvalidError):
                        return (
                            Error(
                                lang.getstr(
                                    "error.testchart.read", getcfg("testchart.file")
                                )
                            ),
                            None,
                        )
                    ti3 = BytesIO(
                        profile.tags.get("CIED", b"") or profile.tags.get("targ", b"")
                    )
                elif ext.lower() == ".ti1":
                    shutil.copyfile(filename + ext, f"{inoutfile}.ti1")
                else:  # ti3
                    try:
                        ti3 = open(filename + ext, "rb")
                    except Exception:
                        return (
                            Error(
                                lang.getstr(
                                    "error.testchart.read", getcfg("testchart.file")
                                )
                            ),
                            None,
                        )
                if ext.lower() != ".ti1":
                    ti3_lines = [line.strip() for line in ti3]
                    ti3.close()
                    if b"CTI3" not in ti3_lines:
                        return (
                            Error(
                                lang.getstr(
                                    "error.testchart.invalid", getcfg("testchart.file")
                                )
                            ),
                            None,
                        )

                    with open(f"{inoutfile}.ti1", "wb") as ti1:
                        ti1.write(ti3_to_ti1(ti3_lines))
            except Exception as exception:
                localized_error_message = lang.getstr(
                    "error.testchart.creation_failed", f"{inoutfile}.ti1"
                )
                return (
                    Error(f"{localized_error_message}\n\n{exception}"),
                    None,
                )
        if apply_calibration is not False:
            if apply_calibration is True:
                # Always a .cal file in that case
                cal = (
                    os.path.join(
                        getcfg("profile.save_path"),
                        getcfg("profile.name.expanded"),
                        getcfg("profile.name.expanded"),
                    )
                    + ".cal"
                )
            elif apply_calibration is None:
                # Use current videoLUT
                cal = inoutfile + ".cal"
                result = self.save_current_video_lut(self.get_display(), cal)
                if isinstance(result, Exception) and not isinstance(
                    result, UnloggedInfo
                ):
                    return result, None
            else:
                cal = apply_calibration  # can be .cal or .icc / .icm
            calcopy = inoutfile + ".cal"
            filename, ext = os.path.splitext(cal)
            if getcfg("dry_run"):
                options_dispcal = []
            elif ext.lower() == ".cal":
                result = check_cal_isfile(cal)
                if isinstance(result, Exception):
                    return result, None
                if not result:
                    return None, None
                # Get dispcal options if present
                try:
                    options_dispcal = get_options_from_cal(cal)[0]
                except (
                    IOError,
                    CGATS.CGATSInvalidError,
                    CGATS.CGATSInvalidOperationError,
                    CGATS.CGATSKeyError,
                    CGATS.CGATSTypeError,
                    CGATS.CGATSValueError,
                ) as exception:
                    return exception, None
                if not os.path.exists(calcopy):
                    try:
                        # Copy cal to temp dir
                        shutil.copyfile(cal, calcopy)
                    except Exception as exception:
                        return (
                            Error(
                                lang.getstr("error.copy_failed", (cal, calcopy))
                                + "\n\n"
                                + str(exception)
                            ),
                            None,
                        )
                    result = check_cal_isfile(calcopy)
                    if isinstance(result, Exception):
                        return result, None
                    if not result:
                        return None, None
            else:
                # .icc / .icm
                result = check_profile_isfile(cal)
                if isinstance(result, Exception):
                    return result, None
                if not result:
                    return None, None
                try:
                    profile = ICCP.ICCProfile(filename + ext)
                except (IOError, ICCP.ICCProfileInvalidError):
                    profile = None
                if profile:
                    ti3 = StringIO(
                        profile.tags.get("CIED", "") or profile.tags.get("targ", "")
                    )
                    # Get dispcal options if present
                    options_dispcal = get_options_from_profile(profile)[0]
                else:
                    ti3 = StringIO("")
                ti3_lines = [line.strip() for line in ti3]
                ti3.close()
                if "CTI3" not in ti3_lines:
                    return Error(lang.getstr("error.cal_extraction", (cal))), None
                try:
                    tmpcal = open(calcopy, "w")
                    tmpcal.write(extract_cal_from_ti3(ti3_lines))
                    tmpcal.close()
                except Exception as exception:
                    return (
                        Error(
                            lang.getstr("error.cal_extraction", (cal))
                            + "\n\n"
                            + str(exception)
                        ),
                        None,
                    )
            cal = calcopy
            if options_dispcal:
                self.options_dispcal = ["-" + arg for arg in options_dispcal]
        #
        # Make sure any measurement options are present
        if not self.options_dispcal:
            self.prepare_dispcal(dry_run=True)
        # Special case -X because it can have a separate filename argument
        if "-X" in self.options_dispcal:
            index = self.options_dispcal.index("-X")
            if (
                len(self.options_dispcal) > index + 1
                and self.options_dispcal[index + 1][0] != "-"
            ):
                self.options_dispcal = (
                    self.options_dispcal[:index] + self.options_dispcal[index + 2 :]
                )
        # Strip options we may override (basically all the stuff which can be
        # added by add_measurement_features. -X is repeated because it can
        # have a number instead of explicit filename argument, e.g. -X1)
        dispcal_override_args = (
            "-F",
            "-H",
            "-I",
            "-P",
            "-V",
            "-X",
            "-d",
            "-c",
            "-p",
            "-y",
        )
        self.options_dispcal = [
            arg for arg in self.options_dispcal if arg[:2] not in dispcal_override_args
        ]
        # Only add the dispcal extra args which may override measurement features
        dispcal_extra_args = parse_argument_string(getcfg("extra_args.dispcal"))
        for i, arg in enumerate(dispcal_extra_args):
            if not arg.startswith("-") and i > 0:
                # Assume option to previous arg
                arg = dispcal_extra_args[i - 1]
            if arg[:2] in dispcal_override_args:
                self.options_dispcal.append(dispcal_extra_args[i])
        result = self.add_measurement_features(
            self.options_dispcal, ignore_display_name=True
        )
        if isinstance(result, Exception):
            return result, None
        cmd = get_argyll_util("dispread")
        args = []
        args.append("-v")  # verbose
        if getcfg("argyll.debug"):
            args.append("-D8")
        result = self.add_measurement_features(
            args, allow_nondefault_observer=is_ccxx_testchart(), quantize=True
        )
        if isinstance(result, Exception):
            return result, None
        if apply_calibration is not False:
            if (
                self.argyll_version >= [1, 3, 3]
                and (
                    not self.has_lut_access() or not getcfg("calibration.use_video_lut")
                )
                # Only use -K if we don't use -d n,m (Linux X11)
                and len(get_arg("-d", args)[1].split(",")) == 1
            ):
                # Apply calibration to test values directly instead of via
                # videoLUT
                args.append("-K")
            else:
                # Apply calibration via videoLUT (in special case of madVR,
                # always applied to test values directly instead)
                args.append("-k")
            args.append(cal)
        if self.get_instrument_features().get("spectral"):
            args.append("-s")
        if getcfg("extra_args.dispread").strip():
            args += parse_argument_string(getcfg("extra_args.dispread"))
        self.options_dispread = list(args)
        cgats = self.ensure_patch_sequence(inoutfile + ".ti1")
        if getattr(self, "terminal", None) and isinstance(
            self.terminal, UntetheredFrame
        ):
            result = self.set_terminal_cgats(cgats)
            if isinstance(result, Exception):
                return result, None
        return cmd, self.options_dispread + [inoutfile]

    def prepare_dispwin(self, cal=None, profile_path=None, install=True):
        """Prepare a dispwin commandline.

        All options are read from the user configuration.
        If you pass in cal as True, it will try to load the current
        display profile's calibration. If cal is a path, it'll use
        that instead. If cal is False, it'll clear the current calibration.
        If cal is None, it'll try to load the calibration from a profile
        specified by profile_path.

        """
        cmd = get_argyll_util("dispwin")
        args = []
        args.append("-v")
        if getcfg("argyll.debug"):
            if self.argyll_version >= [1, 3, 1]:
                args.append("-D8")
            else:
                args.append("-E8")
        args.append("-d" + self.get_display())
        if sys.platform != "darwin" or cal is False:
            # Mac OS X 10.7 Lion needs root privileges when clearing
            # calibration
            args.append("-c")
        if cal is True:
            args.append(
                self.get_dispwin_display_profile_argument(
                    max(0, min(len(self.displays), getcfg("display.number")) - 1)
                )
            )
        elif cal:
            result = check_cal_isfile(cal)
            if isinstance(result, Exception):
                return result, None
            if not result:
                return None, None
            args.append(cal)
        else:
            if cal is None:
                if not profile_path:
                    profile_save_path = os.path.join(
                        getcfg("profile.save_path"), getcfg("profile.name.expanded")
                    )
                    profile_path = os.path.join(
                        profile_save_path, getcfg("profile.name.expanded") + profile_ext
                    )
                result = check_profile_isfile(profile_path)
                if isinstance(result, Exception):
                    return result, None
                if not result:
                    return None, None
                try:
                    profile = ICCP.ICCProfile(profile_path)
                except (IOError, ICCP.ICCProfileInvalidError):
                    return (
                        Error(lang.getstr("profile.invalid") + "\n" + profile_path),
                        None,
                    )
                if profile.profileClass != b"mntr" or profile.colorSpace != b"RGB":
                    return (
                        Error(
                            lang.getstr(
                                "profile.unsupported",
                                (profile.profileClass, profile.colorSpace),
                            )
                            + "\n"
                            + profile_path
                        ),
                        None,
                    )
                if install:
                    if getcfg("profile.install_scope") != "u" and (
                        (
                            (
                                sys.platform == "darwin"
                                or (
                                    sys.platform != "win32"
                                    and self.argyll_version >= [1, 1, 0]
                                )
                            )
                            and (os.geteuid() == 0 or which("sudo"))
                        )
                        or (
                            sys.platform == "win32"
                            and sys.getwindowsversion() >= (6,)
                            and self.argyll_version > [1, 1, 1]
                        )
                    ):
                        # -S option is broken on Linux with current Argyll
                        # releases
                        args.append("-S" + getcfg("profile.install_scope"))
                    else:
                        # Make sure user profile dir exists
                        # (e.g. on Mac OS X 10.9 Mavericks, it does not by
                        # default)
                        for profile_dir in reversed(iccprofiles_home):
                            if os.path.isdir(profile_dir):
                                break
                        if not os.path.isdir(profile_dir):
                            try:
                                os.makedirs(profile_dir)
                            except OSError as exception:
                                return exception, None
                    args.append("-I")
                    # Always copy to temp dir so if a user accidentally tries
                    # to install a profile from the location where it's already
                    # installed (e.g. system32/spool/drivers/color) it doesn't
                    # get nuked by dispwin
                    tmp_dir = self.create_tempdir()
                    if not tmp_dir or isinstance(tmp_dir, Exception):
                        return tmp_dir, None
                    # Check directory and in/output file(s)
                    result = check_create_dir(tmp_dir)
                    if isinstance(result, Exception):
                        return result, None
                    profile_name = os.path.basename(profile_path)
                    if (
                        sys.platform in ("win32", "darwin")
                        or fs_enc.upper() not in ("UTF8", "UTF-8")
                    ) and re.search(r"[^\x20-\x7e]", profile_name):
                        # Copy to temp dir and give ASCII-only name to
                        # avoid profile install issues
                        profile_tmp_path = os.path.join(
                            tmp_dir,
                            safe_asciize(profile_name).decode("utf-8", "ignore"),
                        )
                    else:
                        profile_tmp_path = os.path.join(tmp_dir, profile_name)
                    shutil.copyfile(profile_path, profile_tmp_path)
                    profile_path = profile_tmp_path
                args.append(profile_path)
        return cmd, args

    def prepare_targen(self):
        """Prepare a targen commandline.

        All options are read from the user configuration.

        """
        path = self.create_tempdir()
        if not path or isinstance(path, Exception):
            return path, None
        # Check directory and in/output file(s)
        result = check_create_dir(path)
        if isinstance(result, Exception):
            return result, None
        inoutfile = os.path.join(path, "temp")
        cmd = get_argyll_util("targen")
        args = []
        args.append("-v")
        args.append("-d3")
        args.append("-e%s" % getcfg("tc_white_patches"))
        if self.argyll_version >= [1, 6]:
            args.append("-B%s" % getcfg("tc_black_patches"))
        args.append("-s%s" % getcfg("tc_single_channel_patches"))
        args.append("-g%s" % getcfg("tc_gray_patches"))
        args.append("-m%s" % getcfg("tc_multi_steps"))
        if self.argyll_version >= [1, 6, 0]:
            args.append("-b%s" % getcfg("tc_multi_bcc_steps"))
        tc_algo = getcfg("tc_algo")
        if getcfg("tc_fullspread_patches") > 0:
            args.append("-f%s" % config.get_total_patches())
            if tc_algo:
                args.append("-" + tc_algo)
            if tc_algo in ("i", "I"):
                args.append("-a%s" % getcfg("tc_angle"))
            if tc_algo == "":
                args.append("-A%s" % getcfg("tc_adaption"))
            if self.argyll_version >= [1, 3, 3]:
                args.append("-N%s" % getcfg("tc_neutral_axis_emphasis"))
            if self.argyll_version == [1, 1, "RC1"] or self.argyll_version >= [1, 1]:
                args.append("-G")
        else:
            args.append("-f0")
        if getcfg("tc_precond") and getcfg("tc_precond_profile"):
            args.append("-c")
            args.append(getcfg("tc_precond_profile"))
        if getcfg("tc_filter"):
            args.append(
                "-F%s,%s,%s,%s"
                % (
                    getcfg("tc_filter_L"),
                    getcfg("tc_filter_a"),
                    getcfg("tc_filter_b"),
                    getcfg("tc_filter_rad"),
                )
            )
        if self.argyll_version >= [1, 6, 2] and (
            "-c" in args or self.argyll_version >= [1, 6, 3]
        ):
            args.append("-V%s" % (1 + getcfg("tc_dark_emphasis") * 3))
        if self.argyll_version == [1, 1, "RC2"] or self.argyll_version >= [1, 1]:
            args.append("-p%s" % getcfg("tc_gamma"))
        if getcfg("extra_args.targen").strip():
            # Disallow -d and -D as the testchart editor only supports
            # video RGB (-d3)
            args += [
                arg
                for arg in parse_argument_string(getcfg("extra_args.targen"))
                if not arg.lower().startswith("-d")
            ]
        self.options_targen = list(args)
        args.append(inoutfile)
        return cmd, args

    def progress_handler(self, event):
        """Handle progress dialog updates and react to Argyll CMS command output"""
        if getattr(self, "subprocess_abort", False) or getattr(
            self, "thread_abort", False
        ):
            self.progress_wnd.Pulse(lang.getstr("aborting"))
            return
        percentage = None
        msg = self.recent.read(FilteredStream.triggers)
        lastmsg = self.lastmsg.read(FilteredStream.triggers).strip()
        warning = r"\D+: Warning -.*"
        msg = re.sub(warning, "", msg)
        lastmsg = re.sub(warning, "", lastmsg)
        # Filter for '=' so that 1% reading during calibration check
        # measurements doesn't trigger swapping from the interactive adjustment
        # to the progress window
        if re.match(r"\s*\d+%\s*(?:[^=]+)?$", lastmsg):
            # colprof, download progress
            try:
                percentage = int(self.lastmsg.read().split("%")[0])
            except ValueError:
                pass
        elif re.match(r"Patch \d+ of \d+", lastmsg, re.I):
            # dispcal/dispread
            components = lastmsg.split()
            try:
                start = float(components[1])
                end = float(components[3])
            except ValueError:
                pass
            else:
                percentage = max(start - 1, 0) / end * 100
        elif re.match(r"Added \d+/\d+", lastmsg, re.I):
            # targen
            components = lastmsg.lower().replace("added ", "").split("/")
            try:
                start = float(components[0])
                end = float(components[1])
            except ValueError:
                pass
            else:
                percentage = start / end * 100
        else:
            iteration = re.search(r"It (\d+):", msg)
            if iteration:
                # targen
                try:
                    start = float(iteration.groups()[0])
                except ValueError:
                    pass
                else:
                    end = 20
                    percentage = min(start, 20.0) / end * 100
                    lastmsg = ""
        if (
            percentage is not None
            and time() > self.starttime + 3
            and self.progress_wnd is getattr(self, "terminal", None)
            and not self._detecting_video_levels
        ):
            # We no longer need keyboard interaction, switch over to
            # progress dialog
            wx.CallAfter(self.swap_progress_wnds)
        self.set_progress_type()
        if (
            getattr(self.progress_wnd, "original_msg", None)
            and msg != self.progress_wnd.original_msg
        ):
            # UGLY HACK: This 'print' call fixes a GTK assertion and
            # segfault under Arch Linux when setting the window title.
            # This has a chance of throwing a IOError: [Errno 9] Bad file
            # descriptor under Windows, so check for wxGTK
            if "__WXGTK__" in wx.PlatformInfo:
                print("")
            self.progress_wnd.SetTitle(self.progress_wnd.original_msg)
            self.progress_wnd.original_msg = None
        if percentage is not None:
            if (
                "Setting up the instrument" in msg
                or "Commencing device calibration" in msg
                or "Commencing display calibration" in msg
                or "Calibration complete" in msg
            ):
                self.recent.clear()
                msg = ""
            keepGoing, skip = self.progress_wnd.UpdateProgress(
                max(min(percentage, 100), 0), msg + "\n" + lastmsg
            )
        elif re.match(r"\d+(?:\.\d+)? (?:[KM]iB)", lastmsg, re.I):
            keepGoing, skip = self.progress_wnd.Pulse("\n".join([msg, lastmsg]))
        else:
            if getattr(self.progress_wnd, "lastmsg", "") == msg or not msg:
                keepGoing, skip = self.progress_wnd.Pulse()
            else:
                if "Setting up the instrument" in lastmsg:
                    msg = lang.getstr("instrument.initializing")
                elif "Created web server at" in msg:
                    webserver = re.search(r"(http\:\/\/[^']+)", msg)
                    if webserver:
                        msg = (
                            lang.getstr("webserver.waiting")
                            + " "
                            + webserver.groups()[0]
                        )
                keepGoing, skip = self.progress_wnd.Pulse(msg)
        self.pause_continue()
        if hasattr(self.progress_wnd, "pause_continue"):
            if "read stopped at user request!" in lastmsg:
                self.progress_wnd.pause_continue.Enable()
            if self.progress_wnd.pause_continue.IsShown() != self.pauseable:
                self.progress_wnd.pause_continue.Show(self.pauseable)
                self.progress_wnd.Layout()
        if not keepGoing and not getattr(self, "abort_requested", False):
            # Only confirm abort if we are not currently doing interactive
            # display adjustment
            self.abort_subprocess(
                not isinstance(self._progress_wnd, DisplayAdjustmentFrame)
            )
        if self.finished is True:
            return
        if (
            self.progress_wnd.IsShownOnScreen()
            and not self.progress_wnd.IsActive()
            and (
                not getattr(self.progress_wnd, "dlg", None)
                or not self.progress_wnd.dlg.IsShownOnScreen()
            )
            and wx.GetApp().GetTopWindow()
            and wx.GetApp().GetTopWindow().IsShownOnScreen()
            and (
                wx.GetApp().IsActive()
                or (sys.platform == "darwin" and not self.activated)
            )
        ):
            for window in wx.GetTopLevelWindows():
                if (
                    window
                    and window is not self.progress_wnd
                    and isinstance(window, wx.Dialog)
                    and window.IsShownOnScreen()
                ):
                    return
            self.activated = True
            self.progress_wnd.Raise()

    def progress_dlg_start(
        self, progress_title="", progress_msg="", parent=None, resume=False, fancy=True
    ):
        """Start a progress dialog, replacing existing one if present"""
        if self._progress_wnd and self.progress_wnd is getattr(self, "terminal", None):
            self.terminal.stop_timer()
            self.terminal.Hide()
        if self.finished is True:
            return
        fancy = fancy and getcfg("use_fancy_progress")
        if (
            resume
            and self._progress_wnd
            and self._progress_wnd in list(self._progress_dlgs.values())
        ):
            progress_wnd = self._progress_wnd
        else:
            key = (
                self.show_remaining_time,
                self.cancelable,
                fancy,
                parent,
                parent and parent.IsShownOnScreen(),
            )
            progress_wnd = self._progress_dlgs.get(key)
        if progress_wnd:
            if self._progress_wnd is not progress_wnd:
                self.progress_wnd = progress_wnd
            # UGLY HACK: This 'print' call fixes a GTK assertion and
            # segfault under Arch Linux when setting the window title
            # This has a chance of throwing a IOError: [Errno 9] Bad file
            # descriptor under Windows, so check for wxGTK
            if "__WXGTK__" in wx.PlatformInfo:
                print("")
            self.progress_wnd.SetTitle(progress_title)
            if not resume or not self.progress_wnd.IsShown():
                self.progress_wnd.reset()
            self.progress_wnd.Pulse(progress_msg)
            if hasattr(self.progress_wnd, "pause_continue"):
                self.progress_wnd.pause_continue.Show(self.pauseable)
                self.progress_wnd.Layout()
            self.progress_wnd.Resume()
            if not self.progress_wnd.IsShownOnScreen():
                self.progress_wnd.place()
                self.progress_wnd.Show()
        else:
            style = wx.PD_SMOOTH | wx.PD_ELAPSED_TIME
            if self.show_remaining_time:
                style |= wx.PD_REMAINING_TIME
            if self.cancelable:
                style |= wx.PD_CAN_ABORT
            # Set maximum to 101 to prevent the 'cancel' changing to 'close'
            # when 100 is reached
            self._progress_dlgs[key] = ProgressDialog(
                progress_title,
                progress_msg,
                maximum=101,
                parent=parent,
                handler=self.progress_handler,
                keyhandler=self.terminal_key_handler,
                pauseable=self.pauseable,
                style=style,
                start_timer=False,
                fancy=fancy,
            )
            self.progress_wnd = self._progress_dlgs[key]
        self.set_progress_type()
        if not self.progress_wnd.timer.IsRunning():
            self.progress_wnd.start_timer()
        self.progress_wnd.original_msg = progress_msg

    def set_progress_type(self):
        """Set progress type for fancy progress dialog"""
        if hasattr(self.progress_wnd, "progress_type"):
            if self.pauseable or getattr(self, "interactive_frame", "") in (
                "ambient",
                "luminance",
            ):
                # If pauseable, we assume it's a measurement
                progress_type = 1  # Measuring
            elif self.cmdname == get_argyll_utilname("targen"):
                progress_type = 2  # Generating test patches
            else:
                progress_type = 0  # Processing
            if self.progress_wnd.progress_type != progress_type:
                if self.progress_wnd.timer.IsRunning():
                    # Fade-out current progress type, fade-in new one
                    self.progress_wnd.set_progress_type(progress_type)
                else:
                    # Not yet running, just set initial progress type
                    self.progress_wnd.progress_type = progress_type

    def quit_terminate_cmd(self):
        """Forcefully abort the current subprocess.

        Try to gracefully exit first by sending common Argyll CMS abort
        keystrokes (ESC), forcefully terminate the subprocess if not
        reacting

        """
        # If running wexpect.spawn in a thread under Windows, writing to
        # sys.stdout from another thread can fail sporadically with IOError 9
        # 'Bad file descriptor', so don't use sys.stdout
        # Careful: Python 2.5 Producer objects don't have a name attribute
        if (
            hasattr(self, "thread")
            and self.thread.is_alive()
            and (
                not hasattr(currentThread(), "name")
                or currentThread().name != self.thread.name
            )
        ):
            logfn = log
        else:
            logfn = print
        subprocess = getattr(self, "subprocess", None)
        if self.isalive(subprocess):
            try:
                if self.measure_cmd and hasattr(subprocess, "send"):
                    self.log(
                        "%s: Trying to end subprocess gracefully..." % appname, fn=logfn
                    )
                    try:
                        if subprocess.after == "Current":
                            # Stop measurement
                            self.safe_send(" ")
                            sleep(1)
                        ts = time()
                        while (
                            self.isalive(subprocess) and self.subprocess == subprocess
                        ):
                            self.safe_send("\x1b")
                            if time() > ts + 20:
                                break
                            sleep(0.5)
                    except Exception as exception:
                        self.log(traceback.format_exc(), fn=logfn)
                        self.log(
                            "%s: Exception in quit_terminate_command: %s"
                            % (appname, exception),
                            fn=logfn,
                        )
                elif hasattr(subprocess, "sendintr"):
                    self.log("%s: Sending CTRL+C to subprocess..." % appname, fn=logfn)
                    try:
                        subprocess.sendintr()
                    except Exception as exception:
                        self.log(traceback.format_exc(), fn=logfn)
                        self.log(
                            "%s: Exception in quit_terminate_command: %s"
                            % (appname, exception),
                            fn=logfn,
                        )
                    ts = time()
                    while self.isalive(subprocess):
                        if time() > ts + 20:
                            break
                        sleep(0.25)
                if self.isalive(subprocess):
                    self.log(
                        "%s: Trying to terminate subprocess..." % appname, fn=logfn
                    )
                    subprocess.terminate()
                    ts = time()
                    while self.isalive(subprocess):
                        if time() > ts + 3:
                            break
                        sleep(0.25)
                    if sys.platform != "win32" and self.isalive(subprocess):
                        self.log(
                            "%s: Trying to terminate subprocess forcefully..."
                            % appname,
                            fn=logfn,
                        )
                        if isinstance(subprocess, sp.Popen):
                            subprocess.kill()
                        else:
                            subprocess.terminate(force=True)
                        ts = time()
                        while self.isalive(subprocess):
                            if time() > ts + 3:
                                break
                            sleep(0.25)
                    if self.isalive(subprocess):
                        self.log("...warning: couldn't terminate subprocess.", fn=logfn)
                    else:
                        self.log("...subprocess terminated.", fn=logfn)
            except Exception as exception:
                self.log(traceback.format_exc(), fn=logfn)
                self.log(
                    "%s: Exception in quit_terminate_command: %s"
                    % (appname, exception),
                    fn=logfn,
                )
        subprocess_isalive = self.isalive(subprocess)
        if subprocess_isalive or (
            hasattr(self, "thread") and not self.thread.is_alive()
        ):
            # We don't normally need this as closing of the progress window is
            # handled by _generic_consumer(), but there are two cases where it
            # is desirable to have this 'safety net':
            # 1. The user aborted a running task, but we couldn't terminate the
            #    associated subprocess. In that case, we have a lingering
            #    subprocess which is problematic but we can't do anything about
            #    it. Atleast we need to give control back to the user by closing
            #    the progress window so he can interact with the application
            #    and doesn't have to resort to forecfully terminate it.
            # 2. We started a thread with continue_next=True, which then exited
            #    without returning an error, yet not the result we were looking
            #    for, so we never started the next thread with resume=True, but
            #    we forgot to call stop_progress() exlicitly. This should never
            #    happen if we design our result consumer correctly to handle
            #    this particular case, but we need to make sure the user can
            #    close the progress window in case we mess up.
            if hasattr(self, "thread") and not self.thread.is_alive():
                wx.CallAfter(self.stop_progress)
            if subprocess_isalive:
                wx.CallAfter(
                    show_result_dialog,
                    Warning(
                        "Couldn't terminate %s. Please try to end "
                        "it manually before continuing to use %s. "
                        "If you can not terminate %s, restarting "
                        "%s may also help. Apologies for the "
                        "inconvenience." % (self.cmd, appname, self.cmd, appname)
                    ),
                    self.owner,
                )
        if self.patterngenerator:
            self.patterngenerator.listening = False
        return not subprocess_isalive

    def report(self, report_calibrated=True):
        """Report on calibrated or uncalibrated display device response"""
        result = self.detect_video_levels()
        if isinstance(result, Exception) or not result:
            return result
        cmd, args = self.prepare_dispcal(calibrate=False)
        if isinstance(cmd, Exception):
            return cmd
        if args:
            if report_calibrated:
                args.append("-r")
            else:
                args.append("-R")
        return self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)

    def reset_cal(self):
        cmd, args = self.prepare_dispwin(False)
        result = self.exec_cmd(
            cmd, args, capture_output=True, skip_scripts=True, silent=False
        )
        return result

    def safe_send(self, bytes_):
        self.send_buffer = bytes_
        return True

    def _safe_send(self, bytes_, retry=3, obfuscate=False):
        """Safely send a keystroke to the current subprocess."""
        for i in range(0, retry):
            if obfuscate:
                logbytes = "***"
            else:
                logbytes = bytes_
            self.logger.info("Sending key(s) %r (%i)" % (logbytes, i + 1))
            try:
                if sys.platform == "win32":
                    # directly send the bytes_ without encoding to anything
                    self.subprocess.send(bytes_)
                else:
                    # for Linux and MacOS encode to bytes
                    self.subprocess.send(bytes_.encode())
            except Exception as exception:
                self.logger.exception("Exception: %s" % str(exception))
            else:
                return True
            sleep(0.25)
        return False

    def save_current_video_lut(
        self, display_no, outfilename, interpolate_to_256=True, silent=False
    ):
        """Save current videoLUT, optionally interpolating to n entries"""
        result = None
        if self.argyll_version[0:3] > [1, 1, 0] or (
            self.argyll_version[0:3] == [1, 1, 0]
            and "Beta" not in self.argyll_version_string
        ):
            cmd, args = (
                get_argyll_util("dispwin"),
                ["-d%s" % display_no, "-s", outfilename],
            )
            result = self.exec_cmd(
                cmd, args, capture_output=True, skip_scripts=True, silent=silent
            )
            if isinstance(result, Exception) and not isinstance(result, UnloggedInfo):
                return result
        if not result:
            return Error(lang.getstr("calibration.load_error"))
        # Make sure there are 256 entries in the .cal file, otherwise dispwin
        # will complain and not be able to load it back in.
        # Under Windows, the GetDeviceGammaRamp API seems to enforce 256 entries
        # regardless of graphics card, but under Linux and Mac OS X there may be
        # more than 256 entries if the graphics card has greater than 8 bit
        # videoLUTs (e.g. Quadro and newer consumer cards)
        cgats = CGATS.CGATS(outfilename)
        data = cgats.queryv1("DATA")
        if data and len(data) != 256:
            print("VideoLUT has %i entries, interpolating to 256" % len(data))
            rgb = {"I": [], "R": [], "G": [], "B": []}
            for entry in data.values():
                for column in ("I", "R", "G", "B"):
                    rgb[column].append(entry["RGB_" + column])
            interp = {}
            for column in ("R", "G", "B"):
                interp[column] = colormath.Interp(rgb["I"], rgb[column])
            resized = CGATS.CGATS()
            data.parent.DATA = resized
            resized.key = "DATA"
            resized.parent = data.parent
            resized.root = cgats
            resized.type = b"DATA"
            for i in range(256):
                entry = {"RGB_I": i / 255.0}
                for column in ("R", "G", "B"):
                    entry["RGB_" + column] = interp[column](entry["RGB_I"])
                resized.add_data(entry)
            cgats.write()
        return result

    def set_argyll_version(self, name, silent=False, cfg=False):
        self.set_argyll_version_from_string(
            get_argyll_version_string(name, silent), cfg
        )

    def set_argyll_version_from_string(self, argyll_version_string, cfg=True):
        self.argyll_version_string = argyll_version_string
        if cfg:
            setcfg("argyll.version", argyll_version_string)
            # Always write cfg directly after setting Argyll version so
            # subprocesses that read the configuration will use the right
            # version
            writecfg()
        self.argyll_version = parse_argyll_version_string(argyll_version_string)

    def set_sessionlogfile(self, sessionlogfile, basename, dirname):
        if sessionlogfile:
            self.sessionlogfile = sessionlogfile
        else:
            self.sessionlogfile = LogFile(basename, dirname)
        self.sessionlogfiles[basename] = self.sessionlogfile

    def set_terminal_cgats(self, cgats):
        if not isinstance(cgats, CGATS.CGATS):
            try:
                cgats = CGATS.CGATS(cgats)
            except (
                IOError,
                CGATS.CGATSInvalidError,
                CGATS.CGATSInvalidOperationError,
                CGATS.CGATSKeyError,
                CGATS.CGATSTypeError,
                CGATS.CGATSValueError,
            ) as exception:
                return exception
        self.terminal.cgats = cgats

    def setup_inout(self, basename=None):
        """Setup in/outfile basename and session logfile."""
        dirname = self.create_tempdir()
        if not dirname or isinstance(dirname, Exception):
            return dirname
        # Check directory and in/output file(s)
        result = check_create_dir(dirname)
        if isinstance(result, Exception):
            return result
        if basename is None:
            basename = getcfg("profile.name.expanded")
        basename = make_argyll_compatible_path(basename)
        self.set_sessionlogfile(None, basename, dirname)
        return os.path.join(dirname, basename)

    def single_real_display(self):
        return len(self.get_real_displays()) == 1

    def argyll_support_file_exists(self, name, scope=None):
        """Check if named file exists in any of the known Argyll support
        locations valid for the chosen Argyll CMS version.

        Scope can be 'u' (user), 'l' (local system) or None (both)

        """
        paths = []
        if sys.platform != "darwin":
            if not scope or scope == "u":
                paths.append(defaultpaths.appdata)
            if not scope or scope == "l":
                paths += defaultpaths.commonappdata
        else:
            if not scope or scope == "u":
                paths.append(defaultpaths.library_home)
            if not scope or scope == "l":
                paths.append(defaultpaths.library)
        searchpaths = []
        if self.argyll_version >= [1, 5, 0]:
            if sys.platform != "darwin":
                searchpaths.extend(
                    os.path.join(dir_, "ArgyllCMS", name) for dir_ in paths
                )
            else:
                paths2 = []
                if not scope or scope == "u":
                    paths2.append(defaultpaths.appdata)
                if not scope or scope == "l":
                    paths2.append(defaultpaths.library)
                if [1, 9] <= self.argyll_version <= [1, 9, 1]:
                    # Argyll CMS 1.9 and 1.9.1 use *nix locations due to a
                    # configuration problem
                    paths2.extend(
                        [
                            os.path.join(defaultpaths.home, ".local", "share"),
                            "/usr/local/share",
                        ]
                    )
                searchpaths.extend(
                    os.path.join(dir_, "ArgyllCMS", name) for dir_ in paths2
                )
        searchpaths.extend(os.path.join(dir_, "color", name) for dir_ in paths)
        for searchpath in searchpaths:
            if os.path.isfile(searchpath):
                return True
        return False

    def spyder2_firmware_exists(self, scope=None):
        """Check if the Spyder 2 firmware file exists in any of the known
        locations valid for the chosen Argyll CMS version.

        Scope can be 'u' (user), 'l' (local system) or None (both)

        """
        if self.argyll_version < [1, 2, 0]:
            spyd2en = get_argyll_util("spyd2en")
            if not spyd2en:
                return False
            return os.path.isfile(
                os.path.join(os.path.dirname(spyd2en), "spyd2PLD.bin")
            )
        else:
            return self.argyll_support_file_exists("spyd2PLD.bin", scope=scope)

    def spyder4_cal_exists(self):
        """Check if the Spyder4/5 calibration file exists in any of the known
        locations valid for the chosen Argyll CMS version."""
        if self.argyll_version < [1, 3, 6]:
            # We couldn't use it even if it exists
            return False
        return self.argyll_support_file_exists("spyd4cal.bin")

    def start(
        self,
        consumer,
        producer,
        cargs=(),
        ckwargs=None,
        wargs=(),
        wkwargs=None,
        progress_title=appname,
        progress_msg="",
        parent=None,
        progress_start=100,
        resume=False,
        continue_next=False,
        stop_timers=True,
        interactive_frame="",
        pauseable=False,
        cancelable=True,
        show_remaining_time=True,
        fancy=True,
    ):
        # The following statement is super hacky, I didn't want to use it but the
        # original developer wanted to add the ``appname`` into the docstring
        # programmatically. So, I think this is the best but hacky way to do it.
        self.start.__func__.__doc__ = f"""Start a worker process.

        Also show a progress dialog while the process is running.

        consumer            consumer function.
        producer            producer function.
        cargs               consumer arguments.
        ckwargs             consumer keyword arguments.
        wargs               producer arguments.
        wkwargs             producer keyword arguments.
        progress_title      progress dialog title. Defaults to '{appname}'.
        progress_msg        progress dialog message. Defaults to ''.
        progress_start      show progress dialog after delay (ms).
        resume              resume previous progress dialog (elapsed time etc).
        continue_next       do not hide progress dialog after producer finishes.
        stop_timers         stop the timers on the owner window if True
        interactive_frame   "" or "uniformity" (selects the type of
                            interactive window)
        pauseable           Is the operation pauseable? (show pause button on
                            progress dialog)
        cancelable          Is the operation cancelable? (show cancel button on
                            progress dialog)
        fancy               Use fancy progress dialog with animated throbber &
                            sound fx
        """
        if ckwargs is None:
            ckwargs = {}
        if wkwargs is None:
            wkwargs = {}
        while self.is_working():
            sleep(0.25)  # wait until previous worker thread finishes
        if hasattr(self.owner, "stop_timers") and stop_timers:
            self.owner.stop_timers()
        if not parent:
            parent = self.owner
        if progress_start < 1:
            # Can't be zero!
            progress_start = 1
        self.activated = False
        self.cmdname = None
        self.cmdrun = False
        self.finished = False
        self.instrument_calibration_complete = False
        if not resume:
            self.instrument_on_screen = False
        self.instrument_place_on_screen_msg = False
        self.instrument_sensor_position_msg = False
        self.interactive_frame = interactive_frame
        self.is_single_measurement = (
            interactive_frame == "ambient"
            or interactive_frame == "luminance"
            or (
                isinstance(interactive_frame, wx.TopLevelWindow)
                and interactive_frame.Name == "VisualWhitepointEditor"
            )
        )
        self.is_ambient_measurement = interactive_frame == "ambient"
        self.lastcmdname = None
        self.pauseable = pauseable
        self.paused = False
        self.cancelable = cancelable
        self.show_remaining_time = show_remaining_time
        self.fancy = fancy
        self.resume = resume
        self.subprocess_abort = False
        self.abort_requested = False
        self.starttime = time()
        self.thread_abort = False
        if (
            fancy
            and (
                not self.interactive
                or interactive_frame not in ("uniformity", "untethered")
            )
            and not isinstance(interactive_frame, wx.TopLevelWindow)
        ):
            # Pre-init progress dialog bitmaps
            ProgressDialog.get_bitmaps(0)
            ProgressDialog.get_bitmaps(1)
        if self.interactive:
            self.progress_start_timer = wx.Timer()
            if progress_msg and progress_title == appname:
                progress_title = progress_msg
            if (
                config.get_display_name() == "Untethered"
                and interactive_frame != "uniformity"
            ):
                interactive_frame = "untethered"
            if interactive_frame == "adjust":
                windowclass = DisplayAdjustmentFrame
            elif interactive_frame == "uniformity":
                windowclass = DisplayUniformityFrame
            elif interactive_frame == "untethered":
                windowclass = UntetheredFrame
            else:
                windowclass = SimpleTerminal
            if getattr(self, "terminal", None) and isinstance(
                self.terminal, windowclass
            ):
                self.progress_wnd = self.terminal
                if not resume:
                    if isinstance(self.progress_wnd, SimpleTerminal):
                        self.progress_wnd.console.SetValue("")
                    elif (
                        isinstance(self.progress_wnd, DisplayAdjustmentFrame)
                        or isinstance(self.progress_wnd, DisplayUniformityFrame)
                        or isinstance(self.progress_wnd, UntetheredFrame)
                    ):
                        self.progress_wnd.reset()
                self.progress_wnd.stop_timer()
                self.progress_wnd.Resume()
                self.progress_wnd.start_timer()
                # UGLY HACK: This 'print' call fixes a GTK assertion and
                # segfault under Arch Linux when setting the window title
                print("")
                if isinstance(self.progress_wnd, SimpleTerminal):
                    self.progress_wnd.SetTitle(progress_title)
                self.progress_wnd.Show()
                if resume and isinstance(self.progress_wnd, SimpleTerminal):
                    self.progress_wnd.console.ScrollLines(
                        self.progress_wnd.console.GetNumberOfLines()
                    )
            else:
                if getattr(self, "terminal", None):
                    # Destroy the wx object so the decref'd python object can
                    # be garbage collected
                    self.terminal.Destroy()
                if interactive_frame == "adjust":
                    self.terminal = DisplayAdjustmentFrame(
                        parent,
                        handler=self.progress_handler,
                        keyhandler=self.terminal_key_handler,
                    )
                elif interactive_frame == "uniformity":
                    self.terminal = DisplayUniformityFrame(
                        parent,
                        handler=self.progress_handler,
                        keyhandler=self.terminal_key_handler,
                    )
                elif interactive_frame == "untethered":
                    self.terminal = UntetheredFrame(
                        parent,
                        handler=self.progress_handler,
                        keyhandler=self.terminal_key_handler,
                    )
                elif isinstance(interactive_frame, wx.TopLevelWindow):
                    self.terminal = interactive_frame
                else:
                    self.terminal = SimpleTerminal(
                        parent,
                        title=progress_title,
                        handler=self.progress_handler,
                        keyhandler=self.terminal_key_handler,
                    )
                if getattr(self.terminal, "worker", self) is not self:
                    print(
                        "DEBUG: In worker.Worker.start: worker.Worker()."
                        "terminal.worker is not self! This is probably a"
                        "bug."
                    )
                self.terminal.worker = self
                self.progress_wnd = self.terminal
        else:
            if not progress_msg:
                progress_msg = lang.getstr("please_wait")
            # Show the progress dialog after a delay
            self.progress_start_timer = BetterCallLater(
                progress_start,
                self.progress_dlg_start,
                progress_title,
                progress_msg,
                parent,
                resume,
                fancy,
            )
        if not hasattr(self, "_disabler"):
            skip = self.progress_wnds
            if self.owner and hasattr(self.owner, "measureframe"):
                skip.append(self.owner.measureframe)
            self._disabler = BetterWindowDisabler(skip)
        # Can't use startWorker because we may need access to self.thread from
        # within thread, and startWorker does not return before the actual
        # thread starts running
        jobID = None
        sender = delayedresult.SenderCallAfter(
            self._generic_consumer,
            jobID,
            args=[consumer, continue_next] + list(cargs),
            kwargs=ckwargs,
        )
        self.thread = delayedresult.Producer(
            sender,
            Producer(self, producer, continue_next),
            args=wargs,
            kwargs=wkwargs,
            name=jobID,
            group=None,
            daemon=False,
            senderArg=None,
            sendReturn=True,
        )

        self.thread.start()
        return True

    def stop_progress(self):
        if hasattr(self, "_disabler"):
            del self._disabler
        if getattr(self, "progress_wnd", False):
            if getattr(self.progress_wnd, "dlg", None):
                if self.progress_wnd.dlg.IsShownOnScreen():
                    self.progress_wnd.dlg.EndModal(wx.ID_CANCEL)
                self.progress_wnd.dlg = None
            self.progress_wnd.stop_timer()
            if getattr(self.progress_wnd, "Name", None) == "VisualWhitepointEditor":
                self.progress_wnd.Close()
            else:
                self.progress_wnd.Hide()
            self.subprocess_abort = False
            self.thread_abort = False
            self.interactive = False
        self.resume = False
        self._detected_output_levels = False

        # Uninhibit session if needed
        if hasattr(self, "dbus_ifaces"):
            for bus_name in self.dbus_ifaces:
                iface_dict = self.dbus_ifaces[bus_name]
                cookie = iface_dict.get("cookie")
                if cookie:
                    # Uninhibit. Note that if (e.g.) screensaver timeout has
                    # occured during the time the session was inhibited, that
                    # may now kick in immediately after uninhibiting
                    uninhibit = iface_dict.get("uninhibit", "un_inhibit")
                    try:
                        getattr(iface_dict["iface"], uninhibit)(cookie)
                    except DBusException as exception:
                        self.log(exception)
                    else:
                        iface_dict["cookie"] = None
                        self.log(appname + ": Uninhibited " + bus_name)

    def swap_progress_wnds(self):
        """Swap the current interactive window with a progress dialog"""
        parent = self.terminal.GetParent()
        if isinstance(self.terminal, DisplayAdjustmentFrame):
            title = lang.getstr("calibration")
        else:
            title = self.terminal.GetTitle()
        self.progress_dlg_start(title, "", parent, self.resume, self.fancy)

    def terminal_key_handler(self, event):
        """Key handler for the interactive window or progress dialog."""
        keycode = None
        if event.GetEventType() in (wx.EVT_CHAR_HOOK.typeId, wx.EVT_KEY_DOWN.typeId):
            keycode = event.GetKeyCode()
        elif event.GetEventType() == wx.EVT_MENU.typeId:
            keycode = self.progress_wnd.id_to_keycode.get(event.GetId())
        if (
            keycode is not None
            and getattr(self, "subprocess", None)
            and hasattr(self.subprocess, "send")
        ):
            keycode = keycodes.get(keycode, keycode)
            if keycode in (ord("\x1b"), ord("8"), ord("Q"), ord("q")):
                # exit
                self.abort_subprocess(True)
                return
            try:
                self.safe_send(chr(keycode))
            except Exception:
                pass

    def calculate_gamut(
        self,
        profile_path,
        intent="r",
        direction="f",
        order="n",
        compare_standard_gamuts=True,
    ):
        """Calculate gamut, volume, and coverage % against sRGB and Adobe RGB.

        Return gamut volume (int, scaled to sRGB = 1.0) and
        coverage (dict) as tuple.

        """
        if isinstance(profile_path, list):
            profile_paths = profile_path
        else:
            profile_paths = [profile_path]
        outname = os.path.splitext(profile_paths[0])[0]
        mods = []
        if intent != "r":
            mods.append(intent)
        if direction != "f":
            mods.append(direction)
        if order != "n":
            mods.append(order)
        if mods:
            outname += " " + "".join(["[%s]" % mod.upper() for mod in mods])
        gamut_volume = None
        gamut_coverage = {}
        # Create profile gamut and vrml
        det = getcfg("iccgamut.surface_detail")
        for i, profile_path in enumerate(profile_paths):
            if not profile_path:
                self.log("Warning: calculate_gamut(): No profile path %i" % i)
                continue
            result = self.exec_cmd(
                get_argyll_util("iccgamut"),
                [
                    "-v",
                    "-w",
                    "-i" + intent,
                    "-f" + direction,
                    "-o" + order,
                    "-d%.2f" % det,
                    profile_path,
                ],
                capture_output=True,
                skip_scripts=True,
            )
            if not isinstance(result, Exception) and result:
                # iccgamut output looks like this:
                # Header:
                #  <...>
                #
                # Total volume of gamut is xxxxxx.xxxxxx cubic colorspace units
                for line in self.output:
                    match = re.search(
                        r"(\d+(?:\.\d+)?)\s+cubic\s+colorspace\s+units", line
                    )
                    if match:
                        gamut_volume = float(match.groups()[0]) / ICCP.GAMUT_VOLUME_SRGB
                        break
            else:
                break
        name = os.path.splitext(profile_paths[0])[0]
        gamfilename = name + ".gam"
        wrlfilename = name + ".wrl"
        tmpfilenames = [gamfilename, wrlfilename]
        if compare_standard_gamuts:
            comparison_gamuts = [
                ("srgb", "sRGB"),
                ("adobe-rgb", "ClayRGB1998"),
                ("dci-p3", "SMPTE431_P3"),
            ]
        else:
            comparison_gamuts = []
        for profile_path in profile_paths[1:]:
            filename, ext = os.path.splitext(profile_path)
            comparison_gamuts.append(
                (filename.lower().replace(" ", "-"), filename + ".gam")
            )
        threads = []
        viewgam = get_argyll_util("viewgam")
        for key, src in comparison_gamuts:
            if not isinstance(result, Exception) and result:
                # Create gamut view and intersection
                if os.path.isabs(src):
                    src_path = src
                    src = os.path.splitext(os.path.basename(src))[0]
                else:
                    if mods:
                        src += " " + "".join([f"[{mod.upper()}]" for mod in mods])
                    src_path = get_data_path(f"ref/{src}.gam")
                if not src_path:
                    continue
                outfilename = outname + " vs " + src
                if mods:
                    outfilename += " " + "".join([f"[{mod.upper()}]" for mod in mods])
                outfilename += ".wrl"
                tmpfilenames.append(outfilename)
                # Multi-threaded gamut view calculation
                worker = Worker()
                args = [
                    "-cw",
                    "-t0",
                    "-w",
                    src_path,
                    "-cn",
                    "-t.3",
                    "-s",
                    gamfilename,
                    "-i",
                    outfilename,
                ]
                thread = threading.Thread(
                    target=self.create_gamut_view_worker,
                    name="CreateGamutViewWorker",
                    args=(worker, viewgam, args, key, src, gamut_coverage),
                )
                threads.append((thread, worker, args))
                thread.start()
        # Wait for threads to finish
        for thread, worker, args in threads:
            thread.join()
            self.log("-" * 80)
            self.log(lang.getstr("commandline"))
            printcmdline(viewgam, args, fn=self.log, cwd=os.path.dirname(args[-1]))
            self.log("")
            self.log("".join(worker.output))

        if not isinstance(result, Exception) and result:
            for tmpfilename in tmpfilenames:
                if tmpfilename == gamfilename and tmpfilename != f"{outname}.gam":
                    # Use the original file name
                    filename = f"{outname}.gam"
                elif tmpfilename == wrlfilename and tmpfilename != f"{outname}.wrl":
                    # Use the original file name
                    filename = f"{outname}.wrl"
                else:
                    filename = tmpfilename

                try:

                    def tweak_vrml(vrml):
                        # Set viewpoint further away
                        vrml = re.sub(
                            rb"(Viewpoint\s*\{)[^}]+\}", rb"\1 position 0 0 340 }", vrml
                        )
                        # Fix label color for -a* axis
                        label = re.search(
                            rb'Transform\s*\{\s*translation\s+[+\-0-9.]+\s*[+\-0-9.]+\s*[+\-0-9.]+\s+children\s*\[\s*Shape\s*\{\s*geometry\s+Text\s*\{\s*string\s*\["-a\*"\]\s*fontStyle\s+FontStyle\s*\{[^}]*\}\s*\}\s*appearance\s+Appearance\s*\{\s*material\s+Material\s*{[^}]*\}\s*\}\s*\}\s*\]\s*\}',
                            vrml,
                        )
                        if label:
                            label = label.group()
                            vrml = vrml.replace(
                                label,
                                re.sub(
                                    rb"(diffuseColor)\s+[+\-0-9.]+\s+[+\-0-9.]+\s+[+\-0-9.]+",
                                    rb"\1 0.0 1.0 0.0",
                                    label,
                                ),
                            )
                        # Add range to axes
                        vrml = re.sub(
                            rb'(string\s*\[")(\+?)(L\*)("\])',
                            rb'\1\3", b"\2\0$\4',
                            vrml,
                        )
                        vrml = re.sub(
                            rb'(string\s*\[")([+\-]?)(a\*)("\])',
                            rb'\1\3", b"\2\0$\4',
                            vrml,
                        )
                        vrml = re.sub(
                            rb'(string\s*\[")([+\-]?)(b\*)("\])', rb"\1\3 \2\0$\4", vrml
                        )
                        vrml = vrml.replace(b"\0$", b"100")
                        return vrml

                    gzfilename = f"{filename}.gz"
                    if sys.platform == "win32":
                        filename = make_win32_compatible_long_path(filename)
                        gzfilename = make_win32_compatible_long_path(gzfilename)
                        tmpfilename = make_win32_compatible_long_path(tmpfilename)
                    if getcfg("vrml.compress"):
                        # Compress gam and wrl files using gzip
                        with GzipFileProper(gzfilename, "wb") as gz:
                            # Always use original filename with '.gz' extension,
                            # that way the filename in the header will be correct
                            with open(tmpfilename, "rb") as infile:
                                gz.write(tweak_vrml(infile.read()))
                        # Remove uncompressed file
                        os.remove(tmpfilename)
                        tmpfilename = gzfilename
                    else:
                        with open(tmpfilename, "rb") as infile:
                            vrml = infile.read().decode()
                        with open(tmpfilename, "wb") as outfile:
                            outfile.write(tweak_vrml(vrml).encode())
                    if filename.endswith(".wrl"):
                        filename = filename[:-4] + ".wrz"
                    else:
                        filename = gzfilename
                    if tmpfilename != filename:
                        # Rename the file if filename is different
                        if os.path.exists(filename):
                            os.remove(filename)
                        os.rename(tmpfilename, filename)
                except Exception as exception:
                    self.log(exception)
        elif result:
            # Exception
            self.log(result)
        return gamut_volume, gamut_coverage

    @staticmethod
    def create_gamut_view_worker(worker, viewgam, args, key, src, gamut_coverage):
        """Gamut view creation producer"""
        try:
            result = worker.exec_cmd(
                viewgam,
                args,
                capture_output=True,
                skip_scripts=True,
                silent=True,
                log_output=False,
            )
            if not isinstance(result, Exception) and result:
                # viewgam output looks like this:
                # Intersecting volume = xxx.x cubic units
                # 'path/to/1.gam' volume = xxx.x cubic units, intersect = xx.xx%
                # 'path/to/2.gam' volume = xxx.x cubic units, intersect = xx.xx%
                for line in worker.output:
                    match = re.search(
                        r"[\/]%s.gam'\s+volume\s*=\s*"
                        r"\d+(?:\.\d+)?\s+cubic\s+units,?"
                        r"\s+intersect\s*=\s*"
                        r"(\d+(?:\.\d+)?)" % re.escape(src),
                        line,
                    )
                    if match:
                        gamut_coverage[key] = float(match.groups()[0]) / 100.0
                        break
        except Exception:
            traceback.print_exc()
            worker.log(traceback.format_exc())

    def calibrate(self, remove=False):
        """Calibrate the screen and process the generated file(s)."""
        result = self.detect_video_levels()
        if isinstance(result, Exception) or not result:
            return result
        capture_output = False
        if sys.stdout and hasattr(sys.stdout, "isatty") and not sys.stdout.isatty():
            capture_output = True
        cmd, args = self.prepare_dispcal()
        if not isinstance(cmd, Exception):
            print(f"cmd: {cmd}")
            print(f"args: {args}")
            result = self.exec_cmd(cmd, args, capture_output=capture_output)
            print(f"result: {result}")
        else:
            result = cmd
        if not isinstance(result, Exception) and result and getcfg("trc"):
            dst_pathname = os.path.join(
                getcfg("profile.save_path"),
                getcfg("profile.name.expanded"),
                getcfg("profile.name.expanded"),
            )
            print(f"dst_pathname: {dst_pathname}")
            cal = args[-1] + ".cal"
            print(f"cal         : {cal}")
            result = check_cal_isfile(
                cal, lang.getstr("error.calibration.file_not_created")
            )
            print(f"result      : {result}")
            if not isinstance(result, Exception) and result:
                cal_cgats = add_dispcal_options_to_cal(cal, self.options_dispcal)
                if cal_cgats:
                    cal_cgats.write()
                if getcfg("profile.update") or self.dispcal_create_fast_matrix_shaper:
                    profile_path = args[-1] + profile_ext
                    result = check_profile_isfile(
                        profile_path, lang.getstr("error.profile.file_not_created")
                    )
                    if not isinstance(result, Exception) and result:
                        try:
                            profile = ICCP.ICCProfile(profile_path)
                        except (IOError, ICCP.ICCProfileInvalidError):
                            result = Error(
                                lang.getstr("profile.invalid") + "\n" + profile_path
                            )
                    if not isinstance(result, Exception) and result:
                        if not getcfg("profile.update"):
                            # Created fast matrix shaper profile
                            # we need to set cprt, targ and a few other things
                            profile.setCopyright(getcfg("copyright"))
                            # Fast matrix shaper profiles currently don't
                            # contain TI3 data, but look for it anyways
                            # to be future-proof
                            ti3 = add_options_to_ti3(
                                profile.tags.get("targ", profile.tags.get("CIED", "")),
                                self.options_dispcal,
                            )
                            if not ti3:
                                ti3 = CGATS.CGATS("TI3\n")
                                ti3[1] = cal_cgats
                            edid = self.get_display_edid()
                            display_name = edid.get(
                                "monitor_name",
                                edid.get("ascii", str(edid.get("product_id") or "")),
                            )
                            display_manufacturer = edid.get("manufacturer")
                            profile.setDeviceModelDescription(display_name)
                            if display_manufacturer:
                                profile.setDeviceManufacturerDescription(
                                    display_manufacturer
                                )
                            (gamut_volume, gamut_coverage) = self.create_gamut_views(
                                profile_path
                            )
                            self.update_profile(
                                profile,
                                ti3=str(ti3),
                                chrm=None,
                                tags=True,
                                avg=None,
                                peak=None,
                                rms=None,
                                gamut_volume=gamut_volume,
                                gamut_coverage=gamut_coverage,
                                quality=getcfg("calibration.quality"),
                            )
                        else:
                            # Update desc tag - ASCII needs to be 7-bit
                            # also add Unicode string if different from ASCII
                            if "desc" in profile.tags and isinstance(
                                profile.tags.desc, ICCP.TextDescriptionType
                            ):
                                profile.setDescription(getcfg("profile.name.expanded"))
                            # Calculate profile ID
                            profile.calculateID()
                            try:
                                profile.write()
                            except Exception as exception:
                                self.log(exception)
        result2 = self.wrapup(
            not isinstance(result, UnloggedInfo) and result,
            remove or isinstance(result, Exception) or not result,
        )
        if isinstance(result2, Exception):
            if isinstance(result, Exception):
                result = Error(str(result) + "\n\n" + str(result2))
            else:
                result = result2
        elif not isinstance(result, Exception) and result and getcfg("trc"):
            setcfg("last_cal_path", dst_pathname + ".cal")
            setcfg("calibration.file.previous", getcfg("calibration.file", False))
            if getcfg("profile.update") or self.dispcal_create_fast_matrix_shaper:
                setcfg("last_cal_or_icc_path", dst_pathname + profile_ext)
                setcfg("last_icc_path", dst_pathname + profile_ext)
                setcfg("calibration.file", dst_pathname + profile_ext)
            else:
                setcfg("calibration.file", dst_pathname + ".cal")
                setcfg("last_cal_or_icc_path", dst_pathname + ".cal")
        return result

    @property
    def calibration_loading_generally_supported(self):
        # Loading/clearing calibration seems to have undesirable side-effects
        # on Mac OS X 10.6 and newer
        # Wayland does not support videoLUT access (only by installing a
        # profile via colord)
        return (
            sys.platform != "darwin" or intlist(mac_ver()[0].split(".")) < [10, 6]
        ) and os.getenv("XDG_SESSION_TYPE") != "wayland"

    @property
    def calibration_loading_supported(self):
        # Loading/clearing calibration seems to have undesirable side-effects
        # on Mac OS X 10.6 and newer
        return (
            self.calibration_loading_generally_supported
            and not config.is_virtual_display()
        )

    def change_display_profile_cal_whitepoint(
        self, profile, x, y, outfilename, calibration_only=False, use_collink=False
    ):
        """Change display profile (and calibration) whitepoint.

        Do it in an colorimetrically accurate manner (as far as possible).

        """
        XYZw = colormath.xyY2XYZ(x, y)
        xicclu = get_argyll_util("xicclu")
        if not xicclu:
            return Error(lang.getstr("argyll.util.not_found", "xicclu"))
        tempdir = self.create_tempdir()
        if isinstance(tempdir, Exception):
            return tempdir
        outpathname = os.path.splitext(outfilename)[0]
        outname = os.path.basename(outpathname)
        logfiles = Files([self.recent, self.lastmsg, LineBufferedStream(print)])
        ofilename = profile.fileName
        temppathname = os.path.join(tempdir, outname)
        if ofilename and os.path.isfile(ofilename):
            # Profile comes from a file
            temp = False
            temporig = ofilename
        else:
            # Profile not associated to a file, write to temp dir
            temp = True
            profile.fileName = temporig = temppathname + ".orig.icc"
            profile.write(temporig)
        # Remember original white XYZ
        origXYZ = profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z
        # Make a copy of the profile with changed whitepoint
        profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = XYZw
        tempcopy = temppathname + ".copy.icc"
        profile.write(tempcopy)
        # Generate updated calibration with changed whitepoint
        if use_collink:
            collink = get_argyll_util("collink")
            if not collink:
                profile.fileName = ofilename
                self.wrapup(False)
                return Error(lang.getstr("argyll.util.not_found", "collink"))
            linkpath = temppathname + ".link.icc"
            result = self.exec_cmd(
                collink,
                ["-v", "-n", "-G", "-iaw", "-b", tempcopy, temporig, linkpath],
                capture_output=True,
            )
            if not result or isinstance(result, Exception):
                profile.fileName = ofilename
                self.wrapup(False)
                return result
            link = ICCP.ICCProfile(linkpath)
            RGBscaled = []
            for i in range(256):
                RGBscaled.append([i / 255.0] * 3)
            RGBscaled = self.xicclu(link, RGBscaled)
            logfiles.write("RGB white %6.4f %6.4f %6.4f\n" % tuple(RGBscaled[-1]))
            # Restore original white XYZ
            profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = origXYZ
            # Get white RGB
            XYZwscaled = self.xicclu(profile, RGBscaled[-1], "a", pcs="x")[0]
            logfiles.write(
                "XYZ white %6.4f %6.4f %6.4f, CCT %i\n"
                % tuple(XYZwscaled + [colormath.XYZ2CCT(*XYZwscaled)])
            )
        else:
            # Lookup scaled down white XYZ
            logfiles.write("Looking for solution...\n")
            XYZscaled = []
            for i in range(2000):
                XYZscaled.append([v * (1 - i / 1999.0) for v in XYZw])
            RGBscaled = self.xicclu(
                profile, XYZscaled, "a", "if", pcs="x", get_clip=True
            )
            # Set filename to copy (used by worker.xicclu to get profile path)
            profile.fileName = tempcopy
            # Find point at which it no longer clips
            for i, RGBclip in enumerate(RGBscaled):
                if RGBclip[3] is True:
                    # Clipped, skip
                    continue
                # Found
                XYZwscaled = XYZscaled[i]
                logfiles.write(
                    "Solution found at index %i (step size %f)\n" % (i, 1 / 1999.0)
                )
                logfiles.write("RGB white %6.4f %6.4f %6.4f\n" % tuple(RGBclip[:3]))
                logfiles.write(
                    "XYZ white %6.4f %6.4f %6.4f, CCT %i\n"
                    % tuple(XYZscaled[i] + [colormath.XYZ2CCT(*XYZscaled[i])])
                )
                break
            else:
                profile.fileName = ofilename
                self.wrapup(False)
                return Error("No solution found in %i steps" % i)
            # Generate RGB input values
            # Reduce interpolation res as target whitepoint moves farther away
            # from profile whitepoint in RGB
            res = max(int(round((min(RGBclip[:3]) / 1.0) * 33)), 9)
            logfiles.write("Interpolation res %i\n" % res)
            RGBscaled = []
            for i in range(res):
                RGBscaled.append([v * (i / (res - 1.0)) for v in (1, 1, 1)])
            # Lookup RGB -> XYZ through whitepoint adjusted profile
            RGBscaled2XYZ = self.xicclu(profile, RGBscaled, "a", pcs="x")
            # Restore original XYZ
            profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = origXYZ
            # Restore original filename (used by worker.xicclu to get profile path)
            profile.fileName = temporig
            # Get original black point
            XYZk = self.xicclu(profile, [0, 0, 0], "a", pcs="x")[0]
            logfiles.write("XYZ black %6.4f %6.4f %6.4f\n" % tuple(XYZk))
            logfiles.write(
                "XYZ white after forward lookup %6.4f %6.4f %6.4f\n"
                % tuple(RGBscaled2XYZ[-1])
            )
            # Scale down XYZ
            XYZscaled = []
            for i in range(res):
                XYZ = [v * XYZwscaled[1] for v in RGBscaled2XYZ[i]]
                if i == 0:
                    bp_in = XYZ
                XYZ = colormath.apply_bpc(
                    *XYZ, bp_in=bp_in, bp_out=XYZk, wp_out=XYZwscaled, weight=True
                )
                XYZscaled.append(XYZ)
            logfiles.write(
                "XYZ white after scale down %6.4f %6.4f %6.4f\n" % tuple(XYZscaled[-1])
            )
            # Lookup XYZ -> RGB through original profile
            RGBscaled = self.xicclu(
                profile, XYZscaled, "a", "if", pcs="x", use_cam_clipping=True
            )
            logfiles.write(
                "RGB black after inverse forward lookup %6.4f %6.4f %6.4f\n"
                % tuple(RGBscaled[0])
            )
            logfiles.write(
                "RGB white after inverse forward lookup %6.4f %6.4f %6.4f\n"
                % tuple(RGBscaled[-1])
            )
            if res != 256:
                # Interpolate
                R = []
                G = []
                B = []
                for i, RGB in enumerate(RGBscaled):
                    R.append(RGB[0])
                    G.append(RGB[1])
                    B.append(RGB[2])
                if res > 2:
                    # Catmull-Rom spline interpolation
                    Ri = ICCP.CRInterpolation(R)
                    Gi = ICCP.CRInterpolation(G)
                    Bi = ICCP.CRInterpolation(B)
                else:
                    # Linear interpolation
                    Ri = colormath.Interp(list(range(res)), R)
                    Gi = colormath.Interp(list(range(res)), G)
                    Bi = colormath.Interp(list(range(res)), B)
                RGBscaled = []
                step = (res - 1) / 255.0
                for i in range(256):
                    RGB = [Ri(i * step), Gi(i * step), Bi(i * step)]
                    RGBscaled.append(RGB)
                logfiles.write(
                    "RGB black after interpolation %6.4f %6.4f %6.4f\n"
                    % tuple(RGBscaled[0])
                )
                logfiles.write(
                    "RGB white after interpolation %6.4f %6.4f %6.4f\n"
                    % tuple(RGBscaled[-1])
                )
        has_nonlinear_vcgt = (
            isinstance(profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
            and not profile.tags.vcgt.is_linear()
        )
        if has_nonlinear_vcgt:
            # Apply cal
            ocal = extract_cal_from_profile(profile)
            bp_out = list(ocal.queryv1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0}).values())
            ocalpath = temppathname + ".cal"
            ocal.filename = ocalpath
            RGBscaled = self.xicclu(ocal, RGBscaled)
            logfiles.write(
                "RGB black after cal %6.4f %6.4f %6.4f\n" % tuple(RGBscaled[0])
            )
            logfiles.write(
                "RGB white after cal %6.4f %6.4f %6.4f\n" % tuple(RGBscaled[-1])
            )
        else:
            bp_out = (0, 0, 0)
        cal = """CAL

KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "DISPLAY"
KEYWORD "COLOR_REP"
COLOR_REP "RGB"
BEGIN_DATA_FORMAT
RGB_I RGB_R RGB_G RGB_B
END_DATA_FORMAT
NUMBER_OF_SETS 256
BEGIN_DATA
"""
        for i, RGB in enumerate(RGBscaled):
            R, G, B = colormath.apply_bpc(
                *RGB,
                bp_in=RGBscaled[0],
                bp_out=bp_out,
                wp_out=RGBscaled[-1],
                weight=True,
            )
            cal += "%f %f %f %f\n" % (i / 255.0, R, G, B)
        cal += "END_DATA"
        cal = CGATS.CGATS(cal)
        cal.filename = outpathname + ".cal"
        cal.write()
        if calibration_only:
            # Only update calibration
            profile.setDescription(outname)
            profile.tags.vcgt = cal_to_fake_profile(cal).tags.vcgt
            profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = XYZw
            profile.calculateID()
            profile.write(outfilename)
            self.wrapup(False)
            return True
        else:
            # Re-create profile
            cti3 = None
            if isinstance(profile.tags.get("targ"), ICCP.Text):
                # Get measurement data
                try:
                    cti3 = CGATS.CGATS(profile.tags.targ)
                except (IOError, CGATS.CGATSError):
                    pass
                else:
                    if 0 not in cti3 or cti3[0].type.strip() != b"CTI3":
                        # Not Argyll measurement data
                        cti3 = None
            if not cti3:
                # Use fakeread
                fakeread = get_argyll_util("fakeread")
                if not fakeread:
                    profile.fileName = ofilename
                    self.wrapup(False)
                    return Error(lang.getstr("argyll.util.not_found", "fakeread"))
                shutil.copyfile(defaults["testchart.file"], temppathname + ".ti1")
                result = self.exec_cmd(fakeread, [temporig, temppathname])
                if not result or isinstance(result, Exception):
                    profile.fileName = ofilename
                    self.wrapup(False)
                    return result
                cti3 = CGATS.CGATS(temppathname + ".ti3")
            # Get RGB from measurement data
            RGBorig = []
            for i, sample in cti3[0].DATA.items():
                RGB = []
                for j, component in enumerate("RGB"):
                    RGB.append(sample["RGB_" + component])
                RGBorig.append(RGB)
            # Lookup RGB -> scaled RGB through calibration
            RGBscaled = self.xicclu(cal, RGBorig, scale=100)
            if has_nonlinear_vcgt:
                # Undo original calibration
                RGBscaled = self.xicclu(ocal, RGBscaled, direction="b", scale=100)
            # Update CAL in ti3 file
            if 1 in cti3 and cti3[1].type.strip() == b"CAL":
                cti3[1].DATA = cal[0].DATA
            else:
                cti3[1] = cal[0]
            # Lookup scaled RGB -> XYZ through profile
            RGBscaled2XYZ = self.xicclu(profile, RGBscaled, "a", pcs="x", scale=100)
            # Update measurement data
            if "LUMINANCE_XYZ_CDM2" in cti3[0]:
                XYZa = [
                    float(v) * XYZwscaled[i]
                    for i, v in enumerate(cti3[0].LUMINANCE_XYZ_CDM2.split())
                ]
                cti3[0].add_keyword(
                    "LUMINANCE_XYZ_CDM2", " ".join([str(v) for v in XYZa])
                )
            for i, sample in cti3[0].DATA.items():
                for j, component in enumerate("XYZ"):
                    sample["XYZ_" + component] = (
                        RGBscaled2XYZ[i][j] / XYZwscaled[1] * 100
                    )
            cti3.write(temppathname + ".ti3")
            # Preserve custom tags
            display_name = profile.getDeviceModelDescription()
            display_manufacturer = profile.getDeviceManufacturerDescription()
            tags = {}
            for tagname in ("mmod", "meta"):
                if tagname in profile.tags:
                    tags[tagname] = profile.tags[tagname]
            if temp:
                os.remove(temporig)
            os.remove(tempcopy)
            # Compute profile
            self.options_targen = ["-d3"]
            return self.create_profile(
                outfilename, True, display_name, display_manufacturer, tags
            )

    def chart_lookup(
        self,
        cgats,
        profile,
        as_ti3=False,
        fields=None,
        check_missing_fields=False,
        function="f",
        pcs="l",
        intent="r",
        bt1886=None,
        white_patches=4,
        white_patches_total=True,
        raise_exceptions=False,
    ):
        """Lookup CIE or device values through profile"""
        if profile.colorSpace == b"RGB":
            labels = ("RGB_R", "RGB_G", "RGB_B")
        else:
            labels = ("CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K")
        ti1 = None
        ti3_ref = None
        gray = None
        try:
            if not isinstance(cgats, CGATS.CGATS):
                cgats = CGATS.CGATS(cgats, True)
            else:
                # Always make a copy and do not alter a passed in CGATS instance!
                cgats_filename = cgats.filename
                cgats = CGATS.CGATS(bytes(cgats))
                cgats.filename = cgats_filename
            if 0 in cgats:
                # only look at the first section
                cgats[0].filename = cgats.filename
                cgats = cgats[0]
            primaries = cgats.queryi(labels)
            if primaries and not as_ti3:
                primaries.fix_device_values_scaling(profile.colorSpace)
                cgats.type = b"CTI1"
                cgats.COLOR_REP = profile.colorSpace
                ti1, ti3_ref, gray = self.ti1_lookup_to_ti3(
                    cgats,
                    profile,
                    function,
                    pcs,
                    "r",
                    white_patches,
                    white_patches_total,
                )
                if bt1886 or intent == "a":
                    cat = profile.guess_cat() or "Bradford"
                    for item in ti3_ref.DATA.values():
                        if pcs == "l":
                            X, Y, Z = colormath.Lab2XYZ(
                                item["LAB_L"], item["LAB_A"], item["LAB_B"]
                            )
                        else:
                            X, Y, Z = (
                                v / 100.0
                                for v in (item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"])
                            )
                        if bt1886:
                            X, Y, Z = bt1886.apply(X, Y, Z)
                        if intent == "a":
                            X, Y, Z = colormath.adapt(
                                X,
                                Y,
                                Z,
                                "D50",
                                list(profile.tags.wtpt.values()),
                                cat=cat,
                            )
                        X, Y, Z = [v * 100 for v in (X, Y, Z)]
                        if pcs == "l":
                            (
                                item["LAB_L"],
                                item["LAB_A"],
                                item["LAB_B"],
                            ) = colormath.XYZ2Lab(X, Y, Z)
                        else:
                            item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"] = X, Y, Z
            else:
                if not primaries and check_missing_fields:
                    raise ValueError(
                        lang.getstr(
                            "error.testchart.missing_fields",
                            (cgats.filename, ", ".join(labels)),
                        )
                    )
                ti1, ti3_ref = self.ti3_lookup_to_ti1(
                    cgats, profile, fields, intent, white_patches
                )
        except Exception as exception:
            traceback.print_exc()
            if raise_exceptions:
                raise exception
            if not isinstance(exception, (TypeError, ValueError)) or isinstance(
                exception, UnicodeError
            ):
                handle_error(exception, self.owner)
            else:
                show_result_dialog(exception, self.owner)
        return ti1, ti3_ref, gray

    def ti1_lookup_to_ti3(
        self,
        ti1,
        profile,
        function="f",
        pcs=None,
        intent="r",
        white_patches=4,
        white_patches_total=True,
    ):
        """Read TI1 (filename or CGATS instance), lookup device->pcs values
        colorimetrically through profile using Argyll's xicclu
        utility and return TI3 (CGATS instance)

        """
        # ti1
        if isinstance(ti1, str):
            ti1 = CGATS.CGATS(ti1)
        if not isinstance(ti1, CGATS.CGATS):
            raise TypeError("Wrong type for ti1, needs to be CGATS.CGATS " "instance")

        # profile
        if isinstance(profile, str):
            profile = ICCP.ICCProfile(profile)
        if not isinstance(profile, ICCP.ICCProfile):
            raise TypeError(
                "Wrong type for profile, needs to be " "ICCP.ICCProfile instance"
            )

        # determine pcs for lookup
        color_rep = profile.connectionColorSpace.upper()
        if color_rep == b"RGB":
            pcs = None
        elif not pcs:
            if color_rep == b"LAB":
                pcs = "l"
            elif color_rep == b"XYZ":
                pcs = "x"
            else:
                raise ValueError("Unknown CIE color representation " + color_rep)
        else:
            if pcs == "l":
                color_rep = b"LAB"
            elif pcs == "x":
                color_rep = b"XYZ"

        # get profile color space
        colorspace = profile.colorSpace

        # required fields for ti1
        if colorspace == b"CMYK":
            required = ("CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K")
        else:
            required = ("RGB_R", "RGB_G", "RGB_B")
        ti1_filename = ti1.filename
        try:
            ti1 = verify_cgats(ti1, required, True)
        except CGATS.CGATSInvalidError:
            raise ValueError(lang.getstr("error.testchart.invalid", ti1_filename))
        except CGATS.CGATSKeyError:
            raise ValueError(
                lang.getstr(
                    "error.testchart.missing_fields",
                    (ti1_filename, ", ".join(required)),
                )
            )

        # read device values from ti1
        data = ti1.queryv1("DATA")
        if not data:
            raise ValueError(lang.getstr("error.testchart.invalid", ti1_filename))
        device_data = data.queryv(required)
        if not device_data:
            raise ValueError(
                lang.getstr(
                    "error.testchart.missing_fields",
                    (ti1_filename, ", ".join(required)),
                )
            )

        if colorspace == b"RGB" and white_patches:
            # make sure the first four patches are white so the whitepoint can be
            # averaged
            white_rgb = {"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}
            white = dict(white_rgb)
            wp = ti1.queryv1("APPROX_WHITE_POINT")
            if wp:
                wp = [float(v) for v in wp.split()]
                wp = [CGATS.rpad((v / wp[1]) * 100.0, data.vmaxlen) for v in wp]
            else:
                wp = colormath.get_standard_illuminant("D65", scale=100)
            for label in list(data.parent.DATA_FORMAT.values()):
                label = label.decode("utf-8")
                if label not in white:
                    if label.upper() == "LAB_L":
                        value = 100
                    elif label.upper() in ("LAB_A", "LAB_B"):
                        value = 0
                    elif label.upper() == "XYZ_X":
                        value = wp[0]
                    elif label.upper() == "XYZ_Y":
                        value = 100
                    elif label.upper() == "XYZ_Z":
                        value = wp[2]
                    else:
                        value = b"0"
                    white.update({label: value})
            white_added_count = 0
            if profile.profileClass != b"link":
                if white_patches_total:
                    # Ensure total of n white patches
                    while len(data.queryi(white_rgb)) < white_patches:
                        data.insert(0, white)
                        white_added_count += 1
                else:
                    # Add exactly n white patches
                    while white_added_count < white_patches:
                        data.insert(0, white)
                        white_added_count += 1
                print("Added %i white patch(es)" % white_added_count)

        idata = []
        for primaries in list(device_data.values()):
            idata.append(list(primaries.values()))

        if debug:
            print("ti1_lookup_to_ti3 %s -> %s idata" % (profile.colorSpace, color_rep))
            for v in idata:
                print(" ".join(("%3.4f",) * len(v)) % tuple(v))

        # lookup device->cie values through profile using (x)icclu
        if pcs or self.argyll_version >= [1, 6]:
            use_icclu = False
        else:
            # DeviceLink profile, we have to use icclu under older Argyll CMS
            # versions because older xicclu cannot handle devicelink
            use_icclu = True

        input_encoding = None
        output_encoding = None
        if not pcs:
            # Try to determine input/output encoding for devicelink
            if isinstance(profile.tags.get("meta"), ICCP.DictType):
                input_encoding = profile.tags.meta.getvalue("encoding.input")
                output_encoding = profile.tags.meta.getvalue("encoding.output")
                if input_encoding == "T":
                    # 'T' (clip wtw on input) not supported for xicclu
                    input_encoding = "t"
            # Fall back to configured 3D LUT encoding
            if (
                not input_encoding
                or input_encoding not in config.valid_values["3dlut.encoding.input"]
            ):
                input_encoding = getcfg("3dlut.encoding.input")
                if input_encoding == "T":
                    # 'T' (clip wtw on input) not supported for xicclu
                    input_encoding = "t"
            if (
                not output_encoding
                or output_encoding not in config.valid_values["3dlut.encoding.output"]
            ):
                output_encoding = getcfg("3dlut.encoding.output")
            if self.argyll_version < [1, 6] and not (
                input_encoding == output_encoding == "n"
            ):
                # Fail if encoding is not n (data levels)
                raise ValueError(
                    "The used version of ArgyllCMS only"
                    "supports full range RGB encoding."
                )

        odata = self.xicclu(
            profile,
            idata,
            intent,
            function,
            pcs=pcs,
            scale=100,
            use_icclu=use_icclu,
            input_encoding=input_encoding,
            output_encoding=output_encoding,
        )

        gray = []
        igray = []
        igray_idx = []
        if colorspace == b"RGB":
            # treat r=g=b specially: set expected a=b=0
            for i, cie in enumerate(odata):
                r, g, b = idata[i]
                if r == g == b < 100:
                    # if grayscale and not white
                    if pcs == "x":
                        # Need to scale XYZ coming from xicclu
                        # Lab is already scaled
                        cie = colormath.XYZ2Lab(*[n * 100.0 for n in cie])
                    cie = (cie[0], 0, 0)  # set a=b=0
                    igray.append("%s %s %s" % cie)
                    igray_idx.append(i)
                    if pcs == "x":
                        cie = colormath.Lab2XYZ(*cie)
                        luminance = cie[1]
                    else:
                        luminance = colormath.Lab2XYZ(*cie)[1]
                    if luminance * 100.0 >= 1:
                        # only add if luminance is greater or equal 1% because
                        # dark tones fluctuate too much
                        gray.append((r, g, b))
                    if False:  # NEVER?
                        # set cie in odata to a=b=0
                        odata[i] = cie

        if igray and False:  # NEVER?
            # lookup cie->device values for grays through profile using xicclu
            gray = []
            ogray = self.xicclu(profile, igray, "r", "b", pcs="l", scale=100)
            for i, rgb in enumerate(ogray):
                cie = idata[i]
                if colormath.Lab2XYZ(cie[0], 0, 0)[1] * 100.0 >= 1:
                    # only add if luminance is greater or equal 1% because
                    # dark tones fluctuate too much
                    gray.append(rgb)
                # update values in ti1 and data for ti3
                for n, channel in enumerate(("R", "G", "B")):
                    data[igray_idx[i] + white_added_count]["RGB_" + channel] = rgb[n]
                odata[igray_idx[i]] = cie

        # write output ti3
        ofile = BytesIO()
        if pcs:
            ofile.write(b"CTI3   \n")
            ofile.write(
                b'\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n'
            )
        else:
            ofile.write(b"CTI1   \n")
            ofile.write(
                b'\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
            )
        ofile.write(b'KEYWORD "DEVICE_CLASS"\n')
        ofile.write(
            b'DEVICE_CLASS "'
            + (b"DISPLAY" if colorspace == b"RGB" else b"OUTPUT")
            + b'"\n'
        )
        include_sample_name = False
        for i, cie in enumerate(odata):
            if i == 0:
                icolor = profile.colorSpace
                if icolor == b"RGB":
                    olabel = b"RGB_R RGB_G RGB_B"
                elif icolor == b"CMYK":
                    olabel = b"CMYK_C CMYK_M CMYK_Y CMYK_K"
                else:
                    raise ValueError("Unknown color representation " + icolor)
                if color_rep == b"LAB":
                    ilabel = b"LAB_L LAB_A LAB_B"
                elif color_rep in (b"XYZ", b"RGB"):
                    ilabel = b"XYZ_X XYZ_Y XYZ_Z"
                else:
                    raise ValueError("Unknown CIE color representation " + color_rep)
                ofile.write(b'KEYWORD "COLOR_REP"\n')
                if icolor == color_rep:
                    ofile.write(b'COLOR_REP "' + icolor + b'"\n')
                else:
                    ofile.write(b'COLOR_REP "' + icolor + b"_" + color_rep + b'"\n')

                ofile.write(b"\n")
                ofile.write(b"NUMBER_OF_FIELDS ")
                if include_sample_name:
                    ofile.write(
                        bytes(str(2 + len(icolor) + len(color_rep)), "utf-8") + b"\n"
                    )
                else:
                    ofile.write(
                        bytes(str(1 + len(icolor) + len(color_rep)), "utf-8") + b"\n"
                    )
                ofile.write(b"BEGIN_DATA_FORMAT\n")
                ofile.write(b"SAMPLE_ID ")
                if include_sample_name:
                    ofile.write(b"SAMPLE_NAME " + olabel + b" " + ilabel + b"\n")
                else:
                    ofile.write(olabel + b" " + ilabel + b"\n")
                ofile.write(b"END_DATA_FORMAT\n")
                ofile.write(b"\n")
                ofile.write(
                    b"NUMBER_OF_SETS " + bytes(str(len(odata)), "utf-8") + b"\n"
                )
                ofile.write(b"BEGIN_DATA\n")
            if pcs == "x":
                # Need to scale XYZ coming from xicclu, Lab is already scaled
                cie = [round(n * 100.0, 5 - len(str(int(abs(n * 100.0))))) for n in cie]
            elif not pcs:
                # Actually CIE = RGB because Devicelink
                idata[i] = cie
                cie = [
                    round(n * 100.0, 5 - len(str(int(abs(n * 100.0)))))
                    for n in colormath.RGB2XYZ(*[n / 100.0 for n in cie])
                ]
            device = [bytes(str(n), "utf-8") for n in idata[i]]
            cie = [bytes(str(n), "utf-8") for n in cie]
            if include_sample_name:
                ofile.write(
                    bytes(str(i), "utf-8")
                    + b" "
                    + data[i - 1][1].strip(b'"')
                    + b" "
                    + b" ".join(device)
                    + b" "
                    + b" ".join(cie)
                    + b"\n"
                )
            else:
                ofile.write(
                    bytes(str(i), "utf-8")
                    + b" "
                    + b" ".join(device)
                    + b" "
                    + b" ".join(cie)
                    + b"\n"
                )
        ofile.write(b"END_DATA\n")
        ofile.seek(0)
        ti3 = CGATS.CGATS(ofile)[0]

        if colorspace == b"RGB" and white_patches and profile.profileClass == b"link":
            if white_patches_total:
                # Ensure total of n white patches
                while len(ti3.DATA.queryi(white_rgb)) < white_patches:
                    ti3.DATA.insert(0, white)
                    white_added_count += 1
            else:
                # Add exactly n white patches
                while white_added_count < white_patches:
                    ti3.DATA.insert(0, white)
                    white_added_count += 1
            print("Added %i white patch(es)" % white_added_count)

        if debug:
            print(f"ti3: {ti3}")
        return ti1, ti3, list(map(list, gray))

    def ti3_lookup_to_ti1(
        self, ti3, profile, fields=None, intent="r", add_white_patches=4
    ):
        """Read TI3 (filename or CGATS instance), lookup cie->device values
        colorimetrically through profile using Argyll's xicclu
        utility and return TI1 and compatible TI3 (CGATS instances)
        """
        # ti3
        copy = True
        if isinstance(ti3, (str, bytes)):
            copy = False
            ti3 = CGATS.CGATS(ti3)
        if not isinstance(ti3, CGATS.CGATS):
            raise TypeError("Wrong type for ti3, needs to be CGATS.CGATS " "instance")
        ti3_filename = ti3.filename
        if copy:
            # Make a copy and do not alter a passed in CGATS instance!
            ti3 = CGATS.CGATS(bytes(ti3))

        if fields == "XYZ":
            labels = ("XYZ_X", "XYZ_Y", "XYZ_Z")
        else:
            labels = ("LAB_L", "LAB_A", "LAB_B")

        try:
            ti3v = verify_cgats(ti3, labels, True)
        except CGATS.CGATSInvalidError as exception:
            raise ValueError(
                lang.getstr("error.testchart.invalid", ti3_filename)
                + "\n"
                + lang.getstr(str(exception))
            )
        except CGATS.CGATSKeyError:
            try:
                if fields:
                    raise
                else:
                    labels = ("XYZ_X", "XYZ_Y", "XYZ_Z")
                ti3v = verify_cgats(ti3, labels, True)
            except CGATS.CGATSKeyError:
                missing = ", ".join(labels)
                if not fields:
                    missing += " " + lang.getstr("or") + " LAB_L, LAB_A, LAB_B"
                raise ValueError(
                    lang.getstr(
                        "error.testchart.missing_fields", (ti3_filename, missing)
                    )
                )
            else:
                color_rep = "XYZ"
        else:
            color_rep = fields or "LAB"

        # profile
        if isinstance(profile, str):
            profile = ICCP.ICCProfile(profile)
        if not isinstance(profile, ICCP.ICCProfile):
            raise TypeError(
                "Wrong type for profile, needs to be ICCP.ICCProfile instance"
            )

        # determine pcs for lookup
        if color_rep == "LAB":
            pcs = "l"
            required = ("LAB_L", "LAB_A", "LAB_B")
        elif color_rep == "XYZ":
            pcs = "x"
            required = ("XYZ_X", "XYZ_Y", "XYZ_Z")
        else:
            raise ValueError("Unknown CIE color representation " + color_rep)

        # get profile color space
        colorspace = profile.colorSpace

        # read cie values from ti3
        data = ti3v.queryv1("DATA")
        if not data:
            raise ValueError(lang.getstr("error.testchart.invalid", ti3_filename))
        cie_data = data.queryv(required)
        if not cie_data:
            raise ValueError(
                lang.getstr(
                    "error.testchart.missing_fields",
                    (ti3_filename, ", ".join(required)),
                )
            )
        idata = []
        if colorspace == "RGB" and add_white_patches:
            # make sure the first four patches are white so the whitepoint can be
            # averaged
            wp = [n * 100.0 for n in list(profile.tags.wtpt.values())]
            if color_rep == "LAB":
                wp = colormath.XYZ2Lab(*wp)
                wp = dict((("L", wp[0]), ("a", wp[1]), ("b", wp[2])))
            else:
                wp = dict((("X", wp[0]), ("Y", wp[1]), ("Z", wp[2])))
            wp = [wp] * int(add_white_patches)
            print("Added %i white patches" % add_white_patches)
        else:
            wp = []

        for cie in wp + list(cie_data.values()):
            cie = list(cie.values())
            if color_rep == "XYZ":
                # assume scale 0...100 in ti3, we need to convert to 0...1
                cie = [n / 100.0 for n in cie]
            idata.append(cie)

        if debug:
            print("ti3_lookup_to_ti1 %s -> %s idata" % (color_rep, profile.colorSpace))
            for v in idata:
                print(" ".join(("%3.4f",) * len(v)) % tuple(v))

        # lookup cie->device values through profile.icc using xicclu
        odata = self.xicclu(profile, idata, intent, "b", pcs=pcs, scale=100)

        # write output ti1/ti3
        ti1out = BytesIO()
        ti1out.write(b"CTI1\n")
        ti1out.write(b"\n")
        ti1out.write(b'DESCRIPTOR "Argyll Calibration Target chart information 1"\n')
        include_sample_name = False
        for i, device in enumerate(odata):
            if i == 0:
                if color_rep == "LAB":
                    ilabel = b"LAB_L LAB_A LAB_B"
                elif color_rep == "XYZ":
                    ilabel = b"XYZ_X XYZ_Y XYZ_Z"
                else:
                    raise ValueError(f"Unknown CIE color representation {color_rep}")
                ocolor = profile.colorSpace.upper()
                if ocolor == b"RGB":
                    olabel = b"RGB_R RGB_G RGB_B"
                elif ocolor == b"CMYK":
                    olabel = b"CMYK_C CMYK_M CMYK_Y CMYK_K"
                else:
                    raise ValueError(f"Unknown color representation {ocolor}")
                olabels = olabel.split()
                # add device fields to DATA_FORMAT if not yet present
                if (
                    olabels[0] not in list(ti3v.DATA_FORMAT.values())
                    and olabels[1] not in list(ti3v.DATA_FORMAT.values())
                    and not olabels[2] in list(ti3v.DATA_FORMAT.values())
                    and (
                        ocolor == b"RGB"
                        or (
                            ocolor == b"CMYK"
                            and not olabels[3] in list(ti3v.DATA_FORMAT.values())
                        )
                    )
                ):
                    ti3v.DATA_FORMAT.add_data(olabels)
                # add required fields to DATA_FORMAT if not yet present
                if (
                    not bytes(required[0], "utf-8") in list(ti3v.DATA_FORMAT.values())
                    and not bytes(required[1], "utf-8")
                    in list(ti3v.DATA_FORMAT.values())
                    and not bytes(required[2], "utf-8")
                    in list(ti3v.DATA_FORMAT.values())
                ):
                    ti3v.DATA_FORMAT.add_data(required)
                ti1out.write(b'KEYWORD "COLOR_REP"\n')
                ti1out.write(b'COLOR_REP "%s"\n' % ocolor)
                ti1out.write(b"\n")
                ti1out.write(b"NUMBER_OF_FIELDS ")
                if include_sample_name:
                    ti1out.write(
                        bytes(str(2 + len(color_rep) + len(ocolor)), "utf-8") + b"\n"
                    )
                else:
                    ti1out.write(
                        bytes(str(1 + len(color_rep) + len(ocolor)), "utf-8") + b"\n"
                    )
                ti1out.write(b"BEGIN_DATA_FORMAT\n")
                ti1out.write(b"SAMPLE_ID ")
                if include_sample_name:
                    ti1out.write(b"SAMPLE_NAME %s %s\n" % (olabel, ilabel))
                else:
                    ti1out.write(b"%s %s\n" % (olabel, ilabel))
                ti1out.write(b"END_DATA_FORMAT\n")
                ti1out.write(b"\n")
                ti1out.write(b"NUMBER_OF_SETS %s\n" % bytes(str(len(odata)), "utf-8"))
                ti1out.write(b"BEGIN_DATA\n")
            if i < len(wp):
                if ocolor == b"RGB":
                    device = [100.00, 100.00, 100.00]
                else:
                    device = [0, 0, 0, 0]
            # Make sure device values do not exceed valid range of 0..100
            device = [bytes(str(max(0, min(v, 100))), "utf-8") for v in device]
            cie = list((wp + list(cie_data.values()))[i].values())
            cie = [bytes(str(n), "utf-8") for n in cie]
            if include_sample_name:
                cie_ = "%s %s %s %s\n" % (
                    str(i + 1),
                    data[i][1].strip('"'),
                    " ".join(device),
                    " ".join(cie),
                )
                ti1out.write(cie_.encode("utf-8"))
            else:
                cie_ = b"%s %s %s\n" % (
                    bytes(str(i + 1), "utf-8"),
                    b" ".join(device),
                    b" ".join(cie),
                )
                ti1out.write(cie_)
            if i > len(wp) - 1:  # don't include whitepoint patches in ti3
                # set device values in ti3
                for n, v in enumerate(olabels):
                    # Assuming 0..100, 4 decimal digits is
                    # enough for roughly 19 bits integer
                    # device values
                    ti3v.DATA[i - len(wp)][v.decode("utf-8")] = round(
                        float(device[n]), 4
                    )
                # set PCS values in ti3
                for n, v in enumerate(cie):
                    ti3v.DATA[i - len(wp)][required[n]] = float(v)
        ti1out.write(b"END_DATA\n")
        ti1out.seek(0)
        ti1 = CGATS.CGATS(ti1out)
        if debug:
            print(ti1)
        return ti1, ti3v

    def download(self, uri, force=False, download_dir=None):
        # Set timeout to a sane value
        default_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(20)  # 20 seconds
        try:
            return self._download(uri, force=force, download_dir=download_dir)
        finally:
            socket.setdefaulttimeout(default_timeout)

    def _download(self, uri, force=False, download_dir=None):
        if test_badssl:
            uri = f"https://{test_badssl}.badssl.com/"
        orig_uri = uri
        total_size = None
        filename = os.path.basename(uri)
        if not download_dir:
            download_dir = os.path.join(config.datahome, "dl")
        download_path = os.path.join(download_dir, filename)
        response = None
        hashes = None
        is_main_dl = uri.startswith(f"https://{DOMAIN}/download/")
        if is_main_dl:
            # Always force connection to server even if local file exists for
            # displaycal.net/downloads/* and displaycal.net/Argyll/*
            # to force a hash check
            force = True
        if force or not os.path.isfile(download_path):
            cafile = None
            try:
                import ssl
                from ssl import CertificateError, SSLError
            except ImportError:
                CertificateError = ValueError
                SSLError = socket.error
            else:
                if hasattr(ssl, "get_default_verify_paths"):
                    cafile = ssl.get_default_verify_paths().cafile
                    if cafile:
                        print("Using CA file", cafile)
            components = urllib.parse.urlparse(uri)
            # Don't use socket.getservbyname, as it apparently can fail with
            # socket.error under Windows 10 (although why remains a mystery,
            # we're only dealing with HTTP and HTTPS protocols...)
            scheme2port = {"http": 80, "https": 443}
            print(
                lang.getstr(
                    "connecting.to",
                    (
                        "%s://%s" % (components.scheme, components.hostname),
                        components.port or scheme2port.get(components.scheme, "?"),
                    ),
                )
            )
            LoggingHTTPRedirectHandler.newurl = uri
            opener = urllib.request.build_opener(LoggingHTTPRedirectHandler)
            opener.addheaders = list(get_default_headers().items())
            try:
                response = opener.open(uri)
                if always_fail_download or test_badssl:
                    raise urllib.error.URLError("")
                newurl = getattr(LoggingHTTPRedirectHandler, "newurl", uri)
                if is_main_dl or not newurl.startswith(f"https://{DOMAIN}/"):
                    # Get SHA-256 hashes so we can verify the downloaded file.
                    # Only do this for 3rd party hosts/mirrors (no sense
                    # doing it for files downloaded securely directly from
                    # displaycal.net when that is also the source of our hashes
                    # file, unless we are verifying an existing local app setup
                    # or portable archive)
                    noredir = urllib.request.build_opener(NoHTTPRedirectHandler)
                    noredir.addheaders = list(get_default_headers().items())
                    hashes = noredir.open(f"https://{DOMAIN}/sha256sums.txt")
            except (
                socket.error,
                urllib.error.URLError,
                http.client.HTTPException,
                CertificateError,
                SSLError,
            ) as exception:
                if response:
                    response.close()
                if "CERTIFICATE_VERIFY_FAILED" in safe_str(exception):
                    ekey = "ssl.certificate_verify_failed"
                    if not cafile and isapp:
                        ekey += ".root_ca_missing"
                    print(lang.getstr(ekey))
                elif "SSLV3_ALERT_HANDSHAKE_FAILURE" in safe_str(exception):
                    print(lang.getstr("ssl.handshake_failure"))
                elif "SSL:" not in safe_str(exception):
                    return exception
                else:
                    print(exception)
                if getattr(LoggingHTTPRedirectHandler, "newurl", uri) != uri:
                    uri = LoggingHTTPRedirectHandler.newurl
                return DownloadError(
                    lang.getstr("download.fail")
                    + " "
                    + lang.getstr("connection.fail", uri),
                    orig_uri,
                )
            uri = response.geturl()
            filename = Path(Path(uri).name)
            actualhash = sha256()
            if hashes and False:  # skip this for now
                # Read max. 64 KB hashes
                hashesdata = hashes.read(1024 * 64)
                hashes.close()
                hashesdict = {}
                for line in hashesdata.splitlines():
                    if not line.strip():
                        continue
                    name_hash = [value.strip() for value in line.split(None, 1)]
                    if len(name_hash) != 2 or "" in name_hash:
                        response.close()
                        return DownloadError(
                            lang.getstr("file.hash.malformed", filename), orig_uri
                        )
                    else:
                        hashesdict[Path(name_hash[1].decode().lstrip("*"))] = name_hash[0]
                    expectedhash_hex = hashesdict[filename]
                if not expectedhash_hex:
                    response.close()
                    return DownloadError(
                        lang.getstr("file.hash.missing", filename), orig_uri
                    )
            total_size = response.info().get("Content-Length")
            if total_size is not None:
                try:
                    total_size = int(total_size)
                except (TypeError, ValueError):
                    return DownloadError(
                        lang.getstr(
                            "download.fail.wrong_size",
                            ("<%s>" % lang.getstr("unknown"),) * 2,
                        ),
                        orig_uri,
                    )
                else:
                    if not total_size:
                        total_size = None
            contentdispo = response.info().get("Content-Disposition")
            if contentdispo:
                filename = re.search(r'filename="([^"]+)"', contentdispo)
                if filename:
                    filename = filename.groups()[0]
            if not filename:
                filename = make_filename_safe(uri.rstrip("/"), concat=False)
                content_type = response.info().get("Content-Type")
                if content_type:
                    content_type = content_type.split(";", 1)[0]
                ext = mimetypes.guess_extension(content_type or "", False)
                filename += ext or ".html"
            download_path = os.path.join(download_dir, filename)
        if not os.path.isfile(download_path) or (
            total_size is not None and os.stat(download_path).st_size != total_size
        ):

            if not os.path.isdir(download_dir):
                os.makedirs(download_dir)

            # Acquire files safely so no-one but us can mess with them
            fd = tmp_fd = tmp_download_path = None
            try:
                fd, download_path = mksfile(download_path)
                tmp_fd, tmp_download_path = mksfile(download_path + ".download")
            except EnvironmentError as mksfile_exception:
                response.close()
                for fd, pth in [(fd, download_path), (tmp_fd, tmp_download_path)]:
                    if fd:
                        os.close(fd)
                        try:
                            os.remove(download_path)
                        except EnvironmentError as exception:
                            print(exception)
                return mksfile_exception
            print(lang.getstr("downloading"), uri, "\u2192", download_path)
            self.recent.write(lang.getstr(f"downloading {filename}\n"))
            min_chunk_size = 1024 * 8
            chunk_size = min_chunk_size
            bytes_so_far = 0
            prev_bytes_so_far = 0
            unit = "Bytes"
            unit_size = 1.0
            if total_size > 1048576:
                unit = "MiB"
                unit_size = 1048576.0
            elif total_size > 1024:
                unit = "KiB"
                unit_size = 1024.0

            ts = time()
            bps = 0

            prev_percent = -1
            update_ts = time()
            fps = 20
            frametime = 1.0 / fps

            download_file = None
            download_file_exception = None
            try:
                with os.fdopen(tmp_fd, "rb+") as tmp_download_file:
                    while True:
                        if self.thread_abort:
                            print(lang.getstr("aborted"))
                            return False
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        bytes_read = len(chunk)
                        bytes_so_far += bytes_read
                        tmp_download_file.write(chunk)

                        # Determine data rate
                        tdiff = time() - ts
                        if tdiff >= 1:
                            bps = (bytes_so_far - prev_bytes_so_far) / tdiff
                            prev_bytes_so_far = bytes_so_far
                            ts = time()
                        elif not bps:
                            if tdiff:
                                bps = bytes_so_far / tdiff
                            else:
                                bps = bytes_read
                        bps_unit = "Bytes"
                        bps_unit_size = 1.0
                        if bps > 1048576:
                            bps_unit = "MiB"
                            bps_unit_size = 1048576.0
                        elif bps > 1024:
                            bps_unit = "KiB"
                            bps_unit_size = 1024.0

                        if total_size:
                            percent = math.floor(float(bytes_so_far) / total_size * 100)
                            if (
                                percent > prev_percent
                                or time() >= update_ts + frametime
                            ):
                                self.lastmsg.write(
                                    "\r%i%% (%.1f / %.1f %s, %.2f %s/s)"
                                    % (
                                        percent,
                                        bytes_so_far / unit_size,
                                        total_size / unit_size,
                                        unit,
                                        round(bps / bps_unit_size, 2),
                                        bps_unit,
                                    )
                                )
                                prev_percent = percent
                                update_ts = time()
                        elif time() >= update_ts + frametime:
                            if bytes_so_far > 1048576 > unit_size:
                                unit = "MiB"
                                unit_size = 1048576.0
                            elif bytes_so_far > 1024 > unit_size:
                                unit = "KiB"
                                unit_size = 1024.0
                            self.lastmsg.write(
                                "\r%.1f %s (%.2f %s/s)"
                                % (
                                    bytes_so_far / unit_size,
                                    unit,
                                    round(bps / bps_unit_size, 2),
                                    bps_unit,
                                )
                            )
                            update_ts = time()

                        # Adjust chunk size based on DL rate
                        if int(bps / fps) > chunk_size or min_chunk_size <= int(
                            bps / fps
                        ) < int(chunk_size * 0.75):
                            if debug or test or verbose > 1:
                                print(
                                    "Download buffer size changed from %i KB to %i KB"
                                    % (chunk_size / 1024.0, bps / fps / 1024)
                                )
                            chunk_size = int(bps / fps)

                    if not bytes_so_far:
                        return DownloadError(
                            lang.getstr("download.fail.empty_response", uri), orig_uri
                        )
                    if total_size is not None and bytes_so_far != total_size:
                        return DownloadError(
                            lang.getstr(
                                "download.fail.wrong_size", (total_size, bytes_so_far)
                            ),
                            orig_uri,
                        )
                    if total_size is None or bytes_so_far == total_size:
                        # Succesful download, write to destination
                        tmp_download_file.seek(0)
                        try:
                            with os.fdopen(fd, "wb") as download_file:
                                while True:
                                    chunk = tmp_download_file.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    download_file.write(chunk)
                                    if hashes:
                                        actualhash.update(chunk)
                        except EnvironmentError as download_file_exception:
                            return download_file_exception
                        print(lang.getstr("success"))
            finally:
                response.close()
                if not download_file_exception:
                    # Remove temporary download file unless there was an error
                    # writing destination
                    try:
                        os.remove(tmp_download_path)
                    except EnvironmentError as exception:
                        print(exception)
                if self.thread_abort or download_file_exception:
                    # Remove destination file if download aborted or error
                    # writing destination \
                    if not download_file:
                        # Need to close file descriptor first
                        os.close(fd)
                    try:
                        os.remove(download_path)
                    except EnvironmentError as exception:
                        print(exception)
        else:
            # File already exists
            if response:
                response.close()
            if hashes:
                # Verify hash. Get hash of existing file
                with open(download_path, "rb") as download_file:
                    while True:
                        chunk = download_file.read(1024 * 1024)
                        if not chunk:
                            break
                        actualhash.update(chunk)
        if hashes and False:  # skip this for now
            # Verify hash. Compare to expected hash
            actualhash_hex = actualhash.hexdigest()
            if actualhash_hex != expectedhash_hex.decode():
                return Error(
                    lang.getstr(
                        "file.hash.verification.fail",
                        (
                            download_path,
                            f"SHA-256= {expectedhash_hex.decode()}",
                            f"SHA-256= {actualhash_hex}",
                        ),
                    )
                )
            else:
                print(f"Verified hash SHA-256= {actualhash_hex}")
        return download_path

    def process_argyll_download(self, result, exit=False):
        if isinstance(result, Exception):
            show_result_dialog(result, self.owner)
        elif result:
            if result.lower().endswith(".zip") or result.lower().endswith(".tgz"):
                self.start(
                    self.set_argyll_bin,
                    self.extract_archive,
                    cargs=(result,),
                    wargs=(result,),
                    progress_msg=lang.getstr("please_wait"),
                    fancy=False,
                )
            else:
                show_result_dialog(
                    lang.getstr("error.file_type_unsupported") + "\n" + result,
                    self.owner,
                )

    def extract_archive(self, filename):
        extracted = []
        if filename.lower().endswith(".zip"):
            cls = zipfile.ZipFile
            mode = "r"
        elif filename.lower().endswith(".tgz"):
            cls = TarFileProper.open  # classmethod
            mode = "r:gz"
        else:
            return extracted
        with cls(filename, mode) as z:
            outdir = os.path.realpath(os.path.dirname(filename))
            if cls is not zipfile.ZipFile:
                method = z.getnames
            else:
                method = z.namelist

            try:
                names = method()
            except EOFError as e:
                # probably didn't download properly,
                # delete the file and let the user download again
                print(f"Got EOFError, deleting the current downloaded file: {filename}")
                os.remove(filename)
                raise e
            names.sort()
            extracted = [os.path.join(outdir, os.path.normpath(name)) for name in names]
            if names:
                name0 = os.path.normpath(names[0])
            for outpath in extracted:
                if not os.path.realpath(outpath).startswith(
                    os.path.join(outdir, name0)
                ):
                    return Error(lang.getstr("file.invalid") + "\n" + filename)
            if cls is not zipfile.ZipFile:
                z.extractall(outdir)
            else:
                for name in names:
                    # If the ZIP file was created with Unicode names stored
                    # in the file, 'name' will already be Unicode.
                    # Otherwise, it'll either be 7-bit ASCII or (legacy)
                    # cp437 encoding
                    outname = name
                    outpath = os.path.join(outdir, os.path.normpath(outname))
                    if outname.endswith("/"):
                        if not os.path.isdir(outpath):
                            os.makedirs(outpath)
                    elif not os.path.isfile(outpath):
                        with open(outpath, "wb") as outfile:
                            outfile.write(z.read(name))
        return extracted

    def set_argyll_bin(self, result, filename):
        if isinstance(result, Exception):
            show_result_dialog(result, self.owner)
        elif result and os.path.isdir(result[0]):
            setcfg("argyll.dir", os.path.join(result[0], "bin"))
            # Always write cfg directly after setting Argyll directory so
            # subprocesses that read the configuration will use the right
            # executables
            writecfg()
            from DisplayCAL.display_cal import check_donation

            snapshot = VERSION > VERSION_BASE
            self.owner.set_argyll_bin_handler(
                None,
                True,
                self.owner.check_instrument_setup,
                (check_donation, (self.owner, snapshot)),
            )
        else:
            show_result_dialog(
                lang.getstr("error.no_files_extracted_from_archive", filename),
                self.owner,
            )

    def process_download(self, result, exit=False):
        if isinstance(result, Exception):
            show_result_dialog(result, self.owner)
        elif result:
            if exit:
                if self.owner:
                    self.owner.Close()
                else:
                    wx.GetApp().ExitMainLoop()
            launch_file(result)

    def verify_calibration(self):
        """Verify the current calibration"""
        result = self.detect_video_levels()
        if isinstance(result, Exception) or not result:
            return result
        cmd, args = self.prepare_dispcal(calibrate=False, verify=True)
        if not isinstance(cmd, Exception):
            result = self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)
        else:
            result = cmd
        return result

    def measure_ti1(
        self, ti1_path, cal_path=None, colormanaged=False, allow_video_levels=True
    ):
        """Measure a TI1 testchart file"""
        if allow_video_levels:
            result = self.detect_video_levels()
            if isinstance(result, Exception) or not result:
                return result
        if config.get_display_name() == "Untethered":
            cmd, args = get_argyll_util("spotread"), ["-v", "-e"]
            if getcfg("extra_args.spotread").strip():
                args += parse_argument_string(getcfg("extra_args.spotread"))
            result = self.set_terminal_cgats(ti1_path)
            if isinstance(result, Exception):
                return result
        else:
            cmd = get_argyll_util("dispread")
            args = ["-v"]
            if getcfg("argyll.debug"):
                args.append("-D8")
            if config.get_display_name() in ("madVR", "Prisma") and colormanaged:
                args.append("-V")
            if cal_path:
                if self.argyll_version >= [1, 3, 3] and (
                    not self.has_lut_access() or not getcfg("calibration.use_video_lut")
                ):
                    args.append("-K")
                else:
                    args.append("-k")
                args.append(cal_path)
            if getcfg("extra_args.dispread").strip():
                args += parse_argument_string(getcfg("extra_args.dispread"))
        result = self.add_measurement_features(
            quote_args(args) if sys.platform == "win32" else args,
            cmd == get_argyll_util("dispread"),
            allow_nondefault_observer=is_ccxx_testchart(),
            allow_video_levels=allow_video_levels,
            quantize=True,
        )
        if isinstance(result, Exception):
            return result
        self.options_dispread = list(args)
        if config.get_display_name() != "Untethered":
            args.append(os.path.splitext(ti1_path)[0])
        return self.exec_cmd(cmd, args, skip_scripts=True)

    def wrapup(self, copy=True, remove=True, dst_path=None, ext_filter=None):
        """Wrap up - copy and/or clean temporary file(s)."""
        if debug:
            print("[D] wrapup(copy=%s, remove=%s)" % (copy, remove))
        if not self.tempdir or not os.path.isdir(self.tempdir):
            return  # nothing to do
        if (
            isinstance(copy, Exception)
            and not isinstance(copy, (UnloggedError, UnloggedInfo, UnloggedWarning))
            and self.sessionlogfile
        ):
            # This is an incomplete run, log exception to session logfile
            self.sessionlogfile.write(safe_basestring(copy))
        while self.sessionlogfiles:
            self.sessionlogfiles.popitem()[1].close()
        self.sessionlogfile = None
        if isinstance(copy, Exception):
            # This is an incomplete run, check if any files have been added or
            # modified (except log files and 'hidden' temporary files)
            changes = False
            for filename in os.listdir(self.tempdir):
                if filename.endswith(".log") or filename in (
                    ".abort",
                    ".ok",
                    ".wait",
                    ".wait.cmd",
                    ".wait.py",
                ):
                    # Skip log files and 'hidden' temporary files
                    continue
                if (
                    filename not in self.tmpfiles
                    or os.stat(os.path.join(self.tempdir, filename)).st_mtime
                    != self.tmpfiles[filename]
                ):
                    changes = True
                    break
            if not changes:
                copy = False
        result = True
        if copy:
            try:
                src_listdir = os.listdir(self.tempdir)
            except Exception as exception:
                result = exception
                remove = False
            if not isinstance(result, Exception) and src_listdir:
                if not ext_filter:
                    ext_filter = [
                        ".app",
                        ".cal",
                        ".ccmx",
                        ".ccss",
                        ".cmd",
                        ".command",
                        ".gam",
                        ".gz",
                        ".icc",
                        ".icm",
                        ".log",
                        ".png",
                        ".sh",
                        ".ti1",
                        ".ti3",
                        ".wrl",
                        ".wrz",
                    ]
                save_path = getcfg("profile.save_path")
                if dst_path is None:
                    dst_path = os.path.join(
                        save_path,
                        getcfg("profile.name.expanded"),
                        getcfg("profile.name.expanded") + ".ext",
                    )
                if isinstance(copy, Exception):
                    # This is an incomplete run
                    parts = os.path.normpath(dst_path).split(os.sep)
                    # DON'T use os.path.join due to how it works under Windows:
                    # os.path.join("c:", "foo") represents a path relative to
                    # the current directory on drive C: (c:foo), not c:\foo.

                    # Save incomplete runs to different directory
                    parts = [config.datahome, "incomplete"] + parts[-2:]
                    dst_path = os.sep.join(parts)
                result = check_create_dir(os.path.dirname(dst_path))
                if isinstance(result, Exception):
                    remove = False
                else:
                    if isinstance(copy, Exception):
                        print(
                            "Moving files of incomplete run to",
                            os.path.dirname(dst_path),
                        )
                    for basename in src_listdir:
                        name, ext = os.path.splitext(basename)
                        if ext_filter is None or ext.lower() in ext_filter:
                            src = os.path.join(self.tempdir, basename)
                            dst = os.path.join(os.path.dirname(dst_path), basename)
                            if sys.platform == "win32":
                                dst = make_win32_compatible_long_path(dst)
                            if os.path.exists(dst):
                                if os.path.isdir(dst):
                                    if verbose >= 2:
                                        print(
                                            appname + ": Removing existing "
                                            "destination directory tree",
                                            dst,
                                        )
                                    try:
                                        shutil.rmtree(dst, True)
                                    except Exception as exception:
                                        print(
                                            "Warning - directory '%s' "
                                            "could not be removed: %s"
                                            % tuple(str(s) for s in (dst, exception))
                                        )
                                else:
                                    if verbose >= 2:
                                        print(
                                            appname + ": Removing existing "
                                            "destination file",
                                            dst,
                                        )
                                    try:
                                        os.remove(dst)
                                    except Exception as exception:
                                        print(
                                            "Warning - file '%s' could "
                                            "not be removed: %s"
                                            % tuple(str(s) for s in (dst, exception))
                                        )
                            if remove:
                                if verbose >= 2:
                                    print(
                                        appname + ": Moving temporary "
                                        "object %s to %s" % (src, dst)
                                    )
                                try:
                                    shutil.move(src, dst)
                                except Exception as exception:
                                    print(
                                        "Warning - temporary object "
                                        "'%s' could not be moved to "
                                        "'%s': %s"
                                        % tuple(str(s) for s in (src, dst, exception))
                                    )
                                    try:
                                        shutil.copyfile(src, dst)
                                    except Exception as exception:
                                        result2 = Error(
                                            lang.getstr("error.copy_failed", (src, dst))
                                            + "\n"
                                            + str(exception)
                                        )
                                        if isinstance(result, Exception):
                                            result = "\n".join(
                                                str(error)
                                                for error in (result, result2)
                                            )
                                        else:
                                            result = result2
                                        remove = False
                            else:
                                if os.path.isdir(src):
                                    if verbose >= 2:
                                        print(
                                            appname + ": Copying temporary "
                                            "directory tree %s to %s" % (src, dst)
                                        )
                                    try:
                                        shutil.copytree(src, dst)
                                    except Exception as exception:
                                        print(
                                            "Warning - temporary "
                                            "directory '%s' could not "
                                            "be copied to '%s': %s"
                                            % tuple(
                                                str(s) for s in (src, dst, exception)
                                            )
                                        )
                                else:
                                    if verbose >= 2:
                                        print(
                                            appname + ": Copying temporary "
                                            "file %s to %s" % (src, dst)
                                        )
                                    try:
                                        shutil.copyfile(src, dst)
                                    except Exception as exception:
                                        print(
                                            "Warning - temporary file "
                                            "'%s' could not be copied "
                                            "to '%s': %s"
                                            % tuple(
                                                str(s) for s in (src, dst, exception)
                                            )
                                        )
        if remove:
            try:
                src_listdir = os.listdir(self.tempdir)
            except Exception as exception:
                print(
                    "Error - directory '%s' listing failed: %s"
                    % tuple(str(s) for s in (self.tempdir, exception))
                )
            else:
                for basename in src_listdir:
                    name, ext = os.path.splitext(basename)
                    if ext_filter is None or ext.lower() not in ext_filter:
                        src = os.path.join(self.tempdir, basename)
                        isdir = os.path.isdir(src)
                        if isdir:
                            if verbose >= 2:
                                print(
                                    appname + ": Removing temporary " "directory tree",
                                    src,
                                )
                            try:
                                shutil.rmtree(src, True)
                            except Exception as exception:
                                print(
                                    "Warning - temporary directory "
                                    "'%s' could not be removed: %s"
                                    % tuple(str(s) for s in (src, exception))
                                )
                        else:
                            if verbose >= 2:
                                print(f"{appname}: Removing temporary file", src)
                            try:
                                os.remove(src)
                            except Exception as exception:
                                print(
                                    "Warning - temporary file "
                                    "'%s' could not be removed: %s"
                                    % tuple(str(s) for s in (src, exception))
                                )
            try:
                src_listdir = os.listdir(self.tempdir)
            except Exception as exception:
                print(
                    "Error - directory '%s' listing failed: %s"
                    % tuple(str(s) for s in (self.tempdir, exception))
                )
            else:
                if not src_listdir:
                    if verbose >= 2:
                        print(
                            appname + ": Removing empty temporary directory",
                            self.tempdir,
                        )
                    try:
                        shutil.rmtree(self.tempdir, True)
                    except Exception as exception:
                        print(
                            "Warning - temporary directory '%s' could "
                            "not be removed: %s"
                            % tuple(str(s) for s in (self.tempdir, exception))
                        )
        if isinstance(result, Exception):
            result = Error(
                str(result)
                + "\n\n"
                + lang.getstr("tempdir_should_still_contain_files", self.tempdir)
            )
        return result

    def write(self, txt):
        if True:
            # Don't buffer
            self._write(txt)
            return
        # NEVER - Use line buffer
        self.buffer.append(txt)
        self.buffer = [line for line in StringIO("".join(self.buffer))]
        for line in self.buffer:
            if not (
                line.endswith("\n")
                or line.rstrip().endswith(":")
                or line.rstrip().endswith(",")
                or line.rstrip().endswith(".")
            ):
                break
            self._write(line)
            self.buffer = self.buffer[1:]

    def _write(self, txt):

        if isinstance(txt, bytes):
            txt = txt.decode()

        wx.CallAfter(self.audio_visual_feedback, txt)
        if getattr(self, "measure_cmd", None):
            # i1 Pro, Spyders: Instrument Type
            # i1D3: Product Name
            # K10: Model
            # specbos: Identification
            instrument = re.search(
                r"(?:Instrument Type|Product Name|Model|Identificaton):\s+([^\r\n]+)",
                txt,
                re.I,
            )
            if instrument:
                self._detected_instrument = instrument.group(1)
            serial = re.search(r"(?:Serial Number):\s+([^\r\n]+)", txt, re.I)
            if serial:
                self._detected_instrument_serial = serial.group(1)
        if re.search(r"press 1|space when done|patch 1 of ", txt, re.I):
            # There are some intial measurements which we can't check for
            # unless -D (debug) is used for Argyll tools
            if "patch 1 of " not in txt.lower() or not self.patch_sequence:
                if "patch 1 of " in txt.lower():
                    self.patch_sequence = True
                self.patch_count = 0
                self.patterngenerator_sent_count = 0
        update = re.search(
            r"[/\\] current|patch \d+ of |the instrument can be removed from the screen",
            txt,
            re.I,
        )
        # Send colors to pattern generator
        use_patterngenerator = (
            self.use_patterngenerator
            and self.patterngenerator
            and hasattr(self.patterngenerator, "conn")
        )
        if use_patterngenerator or self.use_madnet_tpg or self._use_patternwindow:
            # sometimes the data is not fully received
            if self.partial_data != "":
                # combine the partial data with the currently received one
                self.log(f"Combining previous data of: {self.partial_data}")
                self.log(f"with                      : {txt}")
                txt = self.partial_data + txt
                self.log(f"to                        : {txt}")

            rgb = re.search(r"Current RGB(?:\s+\d+){3}((?:\s+\d+(?:\.\d+)){3})", txt)
            # Check if the data is partial
            if "Current RGB" in txt and rgb is None:
                self.log(f"Data is not fully received, storing partial data: {txt}")
                self.partial_data = txt

            if rgb:
                # reset the partial data storage, as we fully received the data
                self.partial_data = ""
                update_ffp_insertion_ts = False
                if (
                    getcfg("patterngenerator.ffp_insertion")
                    and self.patterngenerator_sent_count > 1
                ):
                    # Frame insertion
                    frq = getcfg("patterngenerator.ffp_insertion.interval")
                    if time() - getattr(self, "_ffp_insertion_ts", 0) > frq:
                        dur = getcfg("patterngenerator.ffp_insertion.duration")
                        lvl = getcfg("patterngenerator.ffp_insertion.level")
                        self.log(
                            "%s: Frame insertion duration %is, level = %i%%"
                            % (appname, dur, lvl * 100)
                        )
                        ts = time()
                        patternconfig = []
                        if self.use_madnet_tpg:
                            patternconfig = self.madtpg.get_pattern_config()
                            self.madtpg.set_pattern_config(
                                patternconfig[0], int(lvl * 100), 0, 0
                            )
                            self.madtpg.show_rgb(lvl, lvl, lvl)
                            self.madtpg.set_pattern_config(100, 0, 0, 0)
                        else:
                            self.patterngenerator_send((lvl, lvl, lvl), (lvl, lvl, lvl))
                        while time() - ts < dur and not (
                            self.subprocess_abort or self.thread_abort
                        ):
                            sleep(0.05)
                        if self.use_madnet_tpg:
                            self.madtpg.set_pattern_config(*patternconfig)
                        update_ffp_insertion_ts = True
                    if (
                        not hasattr(self, "_ffp_insertion_ts")
                        or update_ffp_insertion_ts
                    ):
                        self._ffp_insertion_ts = time()
                rgb = [float(v) for v in rgb.groups()[0].strip().split()]
                if self.use_madnet_tpg:
                    if self.madtpg.show_rgb(*rgb):
                        self.patterngenerator_sent_count += 1
                        self.log(
                            f"{appname}: MadTPG_Net sent count: "
                            f"{self.patterngenerator_sent_count}"
                        )
                    else:
                        self.exec_cmd_returnvalue = Error(
                            lang.getstr("patterngenerator.sync_lost")
                        )
                        self.abort_subprocess()
                else:
                    self.patterngenerator_send(rgb)
                if getcfg("patterngenerator.ffp_insertion") and update_ffp_insertion_ts:
                    # Delay to allow patch update and settle time after
                    # frame insertion. If display update delay is bigger,
                    # do not use extra delay. Otherwise, subtract display
                    # update delay from fixed delay.
                    if getcfg("measure.override_min_display_update_delay_ms"):
                        dur = getcfg("measure.min_display_update_delay_ms") / 1000.0
                    else:
                        dur = 0
                    ts = time()
                    while time() - ts < max(0.8 - dur, 0) and not (
                        self.subprocess_abort or self.thread_abort
                    ):
                        sleep(0.05)
                # Create .ok file which will be picked up by .wait script
                okfilename = os.path.join(self.tempdir, ".ok")
                open(okfilename, "w").close()
            if update:
                # Check if patch count is higher than patterngenerator sent count
                if (
                    self.patch_count > self.patterngenerator_sent_count
                    and self.exec_cmd_returnvalue is None
                ):
                    # XXX: This can happen when pausing/unpausing?
                    # Need to investigate
                    self.log("Warning - did we loose sync with the pattern generator?")
                # self.exec_cmd_returnvalue = Error(lang.getstr("patterngenerator.sync_lost"))
                # self.abort_subprocess()
        if update and not (
            self.subprocess_abort
            or self.thread_abort
            or "the instrument can be removed from the screen" in txt.lower()
        ):
            self.patch_count += 1
            if use_patterngenerator or self.use_madnet_tpg:
                self.log("%s: Patch update count: %i" % (appname, self.patch_count))
        if self.use_madnet_tpg:
            progress = re.search(
                r"(?:Patch (\d+) of|Number of patches =) (\d+)", txt, re.I
            )
            if progress:
                # Set madTPG progress bar
                try:
                    start = int(progress.group(1) or 0)
                    end = int(progress.group(2))
                except ValueError:
                    pass
                else:
                    self.madtpg.set_progress_bar_pos(start, end)
        # Parse
        wx.CallAfter(self.parse, txt)

    @property
    def _use_patternwindow(self):
        # Preliminary Wayland support. This still needs a lot
        # of work as Argyll doesn't support Wayland natively yet,
        # so we use virtual display to drive our own patch window.
        return (
            not config.is_virtual_display()
            and (
                # os.getenv("XDG_SESSION_TYPE") == "wayland"
                getcfg("patterngenerator.use_pattern_window")
            )
            and self.argyll_virtual_display
        )
