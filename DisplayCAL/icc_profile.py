# -*- coding: utf-8 -*-
import binascii
import contextlib
import ctypes
import datetime
import json
import math
import os
import pathlib
import re
import struct
import subprocess as sp
import sys
import warnings
from collections import UserString
from copy import copy
from hashlib import md5
from weakref import WeakValueDictionary

from DisplayCAL.util_dict import dict_sort

if sys.platform == "win32":
    import winreg
    try:
        import win32api
        import win32gui
    except ImportError:
        pass

try:
    from DisplayCAL import colord
except ImportError:

    class Colord:
        Colord = None

        def quirk_manufacturer(self, manufacturer):
            return manufacturer

        def which(self, executable, paths=None):
            return None

    colord = Colord()
from DisplayCAL import colormath
from DisplayCAL import edid
from DisplayCAL import imfile
from DisplayCAL.defaultpaths import iccprofiles, iccprofiles_home
from DisplayCAL.encoding import get_encodings
from DisplayCAL.options import test_input_curve_clipping
from DisplayCAL.util_list import intlist

if sys.platform not in ("darwin", "win32"):
    from DisplayCAL.defaultpaths import xdg_config_dirs, xdg_config_home
    from DisplayCAL.edid import get_edid
    from DisplayCAL.util_x import get_display

    try:
        from DisplayCAL import xrandr
    except ImportError:
        xrandr = None
    from DisplayCAL.util_os import dlopen, which
elif sys.platform == "win32":
    from DisplayCAL import util_win

    if sys.getwindowsversion() < (6,):
        # WCS only available under Vista and later
        mscms = None
    else:
        from DisplayCAL.win_handles import (
            get_process_handles,
            get_handle_name,
            get_handle_type,
        )

        mscms = util_win._get_mscms_windll()

        win_ver = util_win.win_ver()
        win10_1903 = (
            win_ver[0].startswith("Windows 10") and win_ver[2] >= "Version 1903"
        )

# Gamut volumes in cubic colorspace units (L*a*b*) as reported by Argyll's
# iccgamut
GAMUT_VOLUME_SRGB = 833675.435316  # rel. col.
GAMUT_VOLUME_ADOBERGB = 1209986.014983  # rel. col.%
GAMUT_VOLUME_SMPTE431_P3 = 1176953.485921  # rel. col.

# http://msdn.microsoft.com/en-us/library/dd371953%28v=vs.85%29.aspx
COLOR_PROFILE_SUBTYPE = {
    "NONE": 0x0000,
    "RGB_WORKING_SPACE": 0x0001,
    "PERCEPTUAL": 0x0002,
    "ABSOLUTE_COLORIMETRIC": 0x0004,
    "RELATIVE_COLORIMETRIC": 0x0008,
    "SATURATION": 0x0010,
    "CUSTOM_WORKING_SPACE": 0x0020,
}

# http://msdn.microsoft.com/en-us/library/dd371955%28v=vs.85%29.aspx (wrong)
# http://msdn.microsoft.com/en-us/library/windows/hardware/ff546018%28v=vs.85%29.aspx (ok)
COLOR_PROFILE_TYPE = {"ICC": 0, "DMP": 1, "CAMP": 2, "GMMP": 3}

WCS_PROFILE_MANAGEMENT_SCOPE = {"SYSTEM_WIDE": 0, "CURRENT_USER": 1}

ERROR_PROFILE_NOT_ASSOCIATED_WITH_DEVICE = 2015
ERROR_SUCCESS = 0

DEBUG = False

ENC, FS_ENC = get_encodings()

CMMS = {
    b"argl": "ArgyllCMS",
    b"ADBE": "Adobe",
    b"ACMS": "Agfa",
    b"Agfa": "Agfa",
    b"APPL": "Apple",
    b"appl": "Apple",
    b"CCMS": "ColorGear",
    b"UCCM": "ColorGear Lite",
    b"DL&C": "Digital Light & Color",
    b"EFI ": "EFI",
    b"FF  ": "Fuji Film",
    b"HCMM": "Harlequin RIP",
    b"LgoS": "LogoSync",
    b"HDM ": "Heidelberg",
    b"Lino": "Linotype",
    b"lino": "Linotype",
    b"lcms": "Little CMS",
    b"KCMS": "Kodak",
    b"MCML": "Konica Minolta",
    b"MSFT": "Microsoft",
    b"SIGN": "Mutoh",
    b"RGMS": "DeviceLink",
    b"SICC": "SampleICC",
    b"32BT": "the imaging factory",
    b"WTG ": "Ware to Go",
    b"zc00": "Zoran",
}

ENCODINGS = {
    "mac": {
        141: "africaans",
        36: "albanian",
        85: "amharic",
        12: "arabic",
        51: "armenian",
        68: "assamese",
        134: "aymara",
        49: "azerbaijani-cyrllic",
        50: "azerbaijani-arabic",
        129: "basque",
        67: "bengali",
        137: "dzongkha",
        142: "breton",
        44: "bulgarian",
        77: "burmese",
        46: "byelorussian",
        78: "khmer",
        130: "catalan",
        92: "chewa",
        33: "simpchinese",
        19: "tradchinese",
        18: "croatian",
        38: "czech",
        7: "danish",
        4: "dutch",
        0: "roman",
        94: "esperanto",
        27: "estonian",
        30: "faeroese",
        31: "farsi",
        13: "finnish",
        34: "flemish",
        1: "french",
        140: "galician",
        144: "scottishgaelic",
        145: "manxgaelic",
        52: "georgian",
        2: "german",
        14: "greek-monotonic",
        148: "greek-polytonic",
        133: "guarani",
        69: "gujarati",
        10: "hebrew",
        21: "hindi",
        26: "hungarian",
        15: "icelandic",
        81: "indonesian",
        143: "inuktitut",
        35: "irishgaelic",
        146: "irishgaelic-dotsabove",
        3: "italian",
        11: "japanese",
        138: "javaneserom",
        73: "kannada",
        61: "kashmiri",
        48: "kazakh",
        90: "kiryarwanda",
        54: "kirghiz",
        91: "rundi",
        23: "korean",
        60: "kurdish",
        79: "lao",
        131: "latin",
        28: "latvian",
        24: "lithuanian",
        43: "macedonian",
        93: "malagasy",
        83: "malayroman-latin",
        84: "malayroman-arabic",
        72: "malayalam",
        16: "maltese",
        66: "marathi",
        53: "moldavian",
        57: "mongolian",
        58: "mongolian-cyrillic",
        64: "nepali",
        9: "norwegian",
        71: "oriya",
        87: "oromo",
        59: "pashto",
        25: "polish",
        8: "portuguese",
        70: "punjabi",
        132: "quechua",
        37: "romanian",
        32: "russian",
        29: "sami",
        65: "sanskrit",
        42: "serbian",
        62: "sindhi",
        76: "sinhalese",
        39: "slovak",
        40: "slovenian",
        88: "somali",
        6: "spanish",
        139: "sundaneserom",
        89: "swahili",
        5: "swedish",
        82: "tagalog",
        55: "tajiki",
        74: "tamil",
        135: "tatar",
        75: "telugu",
        22: "thai",
        63: "tibetan",
        86: "tigrinya",
        147: "tongan",
        17: "turkish",
        56: "turkmen",
        136: "uighur",
        45: "ukrainian",
        20: "urdu",
        47: "uzbek",
        80: "vietnamese",
        128: "welsh",
        41: "yiddish",
    }
}

COLORANTS = {
    0: {"description": "unknown", "channels": ()},
    1: {
        "description": "ITU-R BT.709",
        "channels": ((0.64, 0.33), (0.3, 0.6), (0.15, 0.06)),
    },
    2: {
        "description": "SMPTE RP145-1994",
        "channels": ((0.63, 0.34), (0.31, 0.595), (0.155, 0.07)),
    },
    3: {
        "description": "EBU Tech.3213-E",
        "channels": ((0.64, 0.33), (0.29, 0.6), (0.15, 0.06)),
    },
    4: {
        "description": "P22",
        "channels": ((0.625, 0.34), (0.28, 0.605), (0.155, 0.07)),
    },
}

GEOMETRY = {0: "unknown", 1: "0/45 or 45/0", 2: "0/d or d/0"}

ILLUMINANTS = {
    0: "unknown",
    1: "D50",
    2: "D65",
    3: "D93",
    4: "F2",
    5: "D55",
    6: "A",
    7: "E",
    8: "F8",
}

OBSERVERS = {0: "unknown", 1: "CIE 1931", 2: "CIE 1964"}

MANUFACTURERS = {
    b"ADBE": "Adobe Systems Incorporated",
    b"APPL": "Apple Computer, Inc.",
    b"agfa": "Agfa Graphics N.V.",
    b"argl": "ArgyllCMS",  # Not registered
    b"DCAL": "DisplayCAL",  # Not registered
    b"bICC": "basICColor GmbH",
    b"DL&C": "Digital Light & Color",
    b"EPSO": "Seiko Epson Corporation",
    b"HDM ": "Heidelberger Druckmaschinen AG",
    b"HP  ": "Hewlett-Packard",
    b"KODA": "Kodak",
    b"lcms": "Little CMS",
    b"MONS": "Monaco Systems Inc.",
    b"MSFT": "Microsoft Corporation",
    b"qato": "QUATOGRAPHIC Technology GmbH",
    b"XRIT": "X-Rite",
}

PLATFORM = {
    b"APPL": "Apple",
    b"MSFT": "Microsoft",
    b"SGI ": "Silicon Graphics",
    b"SUNW": "Sun Microsystems",
}

PROFILE_CLASS = {
    b"scnr": "Input device profile",
    b"mntr": "Display device profile",
    b"prtr": "Output device profile",
    b"link": "DeviceLink profile",
    b"spac": "Color space Conversion profile",
    b"abst": "Abstract profile",
    b"nmcl": "Named color profile",
}

TAGS = {
    "A2B0": "Device to PCS: Intent 0",
    "A2B1": "Device to PCS: Intent 1",
    "A2B2": "Device to PCS: Intent 2",
    "B2A0": "PCS to device: Intent 0",
    "B2A1": "PCS to device: Intent 1",
    "B2A2": "PCS to device: Intent 2",
    "CIED": "Characterization measurement values",  # Non-standard
    "DevD": "Characterization device values",  # Non-standard
    "arts": "Absolute to media relative transform",  # Non-standard (Argyll)
    "bkpt": "Media black point",
    "bTRC": "Blue tone response curve",
    "bXYZ": "Blue matrix column",
    "chad": "Chromatic adaptation transform",
    "ciis": "Colorimetric intent image state",
    "clro": "Colorant order",
    "cprt": "Copyright",
    "desc": "Description",
    "dmnd": "Device manufacturer name",
    "dmdd": "Device model name",
    "gamt": "Out of gamut tag",
    "gTRC": "Green tone response curve",
    "gXYZ": "Green matrix column",
    "kTRC": "Gray tone response curve",
    "lumi": "Luminance",
    "meas": "Measurement type",
    "mmod": "Make and model",
    "ncl2": "Named colors",
    "pseq": "Profile sequence description",
    "rTRC": "Red tone response curve",
    "rXYZ": "Red matrix column",
    "targ": "Characterization target",
    "tech": "Technology",
    "vcgt": "Video card gamma table",
    "view": "Viewing conditions",
    "vued": "Viewing conditions description",
    "wtpt": "Media white point",
}

TECH = {
    "fscn": "Film scanner",
    "dcam": "Digital camera",
    "rscn": "Reflective scanner",
    "ijet": "Ink jet printer",
    "twax": "Thermal wax printer",
    "epho": "Electrophotographic printer",
    "esta": "Electrostatic printer",
    "dsub": "Dye sublimation printer",
    "rpho": "Photographic paper printer",
    "fprn": "Film writer",
    "vidm": "Video monitor",
    "vidc": "Video camera",
    "pjtv": "Projection television",
    "CRT ": "Cathode ray tube display",
    "PMD ": "Passive matrix display",
    "AMD ": "Active matrix display",
    "KPCD": "Photo CD",
    "imgs": "Photographic image setter",
    "grav": "Gravure",
    "offs": "Offset lithography",
    "silk": "Silkscreen",
    "flex": "Flexography",
    "mpfs": "Motion picture film scanner",
    "mpfr": "Motion picture film recorder",
    "dmpc": "Digital motion picture camera",
    "dcpj": "Digital cinema projector",
}

CIIS = {
    "scoe": "Scene colorimetry estimates",
    "sape": "Scene appearance estimates",
    "fpce": "Focal plane colorimetry estimates",
    "rhoc": "Reflection hardcopy original colorimetry",
    "rpoc": "Reflection print output colorimetry",
}


def legacy_PCSLab_dec_to_uInt16(L, a, b):
    # ICCv2 (legacy) PCS L*a*b* encoding
    # Only used by LUT16Type and namedColor2Type in ICCv4
    return [
        v * (652.80, 256, 256)[i] + (0, 32768, 32768)[i]
        for i, v in enumerate((L, a, b))
    ]


def legacy_PCSLab_uInt16_to_dec(L_uInt16, a_uInt16, b_uInt16):
    # ICCv2 (legacy) PCS L*a*b* encoding
    # Only used by LUT16Type and namedColor2Type in ICCv4
    return [
        (v - (0, 32768, 32768)[i]) / (65280.0, 32768.0, 32768.0)[i] * (100, 128, 128)[i]
        for i, v in enumerate((L_uInt16, a_uInt16, b_uInt16))
    ]


def create_RGB_A2B_XYZ(input_curves, clut, logfn=print):
    """Create RGB device A2B from input curve XYZ values and cLUT

    Note that input curves and cLUT should already be adapted to D50.
    """
    if len(input_curves) != 3:
        raise ValueError(f"Wrong number of input curves: {len(input_curves)}")

    white_XYZ = clut[-1][-1]

    clutres = len(clut[0])

    itable = LUT16Type(None, "A2B0")
    itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    # Input curve interpolation
    # Normlly the input curves would either be linear (= 1:1 mapping to
    # cLUT) or the respective tone response curve.
    # We use a overall linear curve that is 'bent' in <clutres> intervals
    # to accomodate the non-linear TRC. Thus, we can get away with much
    # fewer cLUT grid points.

    # Use higher interpolation size than actual number of curve entries
    steps = 2**15 + 1
    maxv = steps - 1.0

    fwd = []
    bwd = []
    for i, input_curve in enumerate(input_curves):
        if isinstance(input_curve, (tuple, list)):
            linear = [v / (len(input_curve) - 1.0) for v in range(len(input_curve))]
            fwd.append(colormath.Interp(linear, input_curve, use_numpy=True))
            bwd.append(colormath.Interp(input_curve, linear, use_numpy=True))
        else:
            # Gamma
            fwd.append(lambda v, p=input_curve: colormath.specialpow(v, p))
            bwd.append(lambda v, p=input_curve: colormath.specialpow(v, 1.0 / p))
        itable.input.append([])
        itable.output.append([0, 65535])

    logfn("cLUT input curve segments:", clutres)
    for i in range(3):
        maxi = bwd[i](white_XYZ[1])
        segment = 1.0 / (clutres - 1.0) * maxi
        iv = 0.0
        prevpow = fwd[i](0.0)
        nextpow = fwd[i](segment)
        prevv = 0
        pprevpow = 0
        clipped = nextpow <= prevpow
        xp = []
        for j in range(steps):
            v = (j / maxv) * maxi
            if v > iv + segment:
                iv += segment
                prevpow = nextpow
                nextpow = fwd[i](iv + segment)
                clipped = nextpow <= prevpow
                logfn(
                    "#{:d} {}".format(int(iv * (clutres - 1)), "XYZ"[i]),
                    f"prev {prevpow:.6f}",
                    f"next {nextpow:.6f}",
                    "clip",
                    clipped,
                )
            if not clipped:
                prevs = 1.0 - (v - iv) / segment
                nexts = (v - iv) / segment
                vv = prevs * prevpow + nexts * nextpow
                prevv = v
                pprevpow = prevpow
            else:
                # Linearly interpolate
                vv = colormath.convert_range(v, prevv, 1, prevpow, 1)
            out = bwd[i](vv)
            xp.append(out)
        # Fill input curves from interpolated values
        interp = colormath.Interp(xp, list(range(steps)), use_numpy=True)
        entries = 2049
        threshold = bwd[i](pprevpow)
        k = None
        for j in range(entries):
            n = j / (entries - 1.0)
            v = interp(n) / maxv
            if clipped and n + (1 / (entries - 1.0)) > threshold:
                # Linear interpolate shaper for last n cLUT steps to prevent
                # clipping in shaper
                if k is None:
                    k = j
                    ov = v
                v = min(ov + (1.0 - ov) * ((j - k) / (entries - k - 1.0)), 1.0)
            # Slope limit for 16-bit encoding
            itable.input[i].append(max(v, j / 65535.0) * 65535)

    # Fill cLUT
    clut = list(clut)
    itable.clut = []
    step = 1.0 / (clutres - 1.0)
    for R in range(clutres):
        for G in range(clutres):
            row = list(clut.pop(0))
            itable.clut.append([])
            for B in range(clutres):
                X, Y, Z = row.pop(0)
                itable.clut[-1].append(
                    [max(v / white_XYZ[1] * 32768, 0) for v in (X, Y, Z)]
                )

    return itable


def create_synthetic_clut_profile(
    rgb_space,
    description,
    XYZbp=None,
    white_Y=1.0,
    clutres=9,
    entries=2049,
    cat="Bradford",
):
    """Create a synthetic cLUT profile from a colorspace definition"""
    profile = ICCProfile()
    profile.version = 2.2  # Match ArgyllCMS

    profile.tags.desc = TextDescriptionType(b"", "desc")
    profile.tags.desc.ASCII = description
    profile.tags.cprt = TextType(b"text\0\0\0\0Public domain\0", "cprt")

    profile.tags.wtpt = XYZType(profile=profile)
    (
        profile.tags.wtpt.X,
        profile.tags.wtpt.Y,
        profile.tags.wtpt.Z,
    ) = colormath.get_whitepoint(rgb_space[1])

    profile.tags.arts = chromaticAdaptionTag()
    profile.tags.arts.update(colormath.get_cat_matrix(cat))

    itable = profile.tags.A2B0 = LUT16Type(None, "A2B0", profile)
    itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    otable = profile.tags.B2A0 = LUT16Type(None, "B2A0", profile)
    Xr, Yr, Zr = colormath.adapt(
        *colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space),
        whitepoint_source=rgb_space[1],
        cat=cat,
    )
    Xg, Yg, Zg = colormath.adapt(
        *colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space),
        whitepoint_source=rgb_space[1],
        cat=cat,
    )
    Xb, Yb, Zb = colormath.adapt(
        *colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space),
        whitepoint_source=rgb_space[1],
        cat=cat,
    )
    m1 = colormath.Matrix3x3(((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))).inverted()
    scale = 1 + (32767 / 32768.0)
    m3 = colormath.Matrix3x3(((scale, 0, 0), (0, scale, 0), (0, 0, scale)))
    otable.matrix = m1 * m3

    # Input curve interpolation
    # Normlly the input curves would either be linear (= 1:1 mapping to
    # cLUT) or the respective tone response curve.
    # We use a overall linear curve that is 'bent' in <clutres> intervals
    # to accomodate the non-linear TRC. Thus, we can get away with much
    # fewer cLUT grid points.

    # Use higher interpolation size than actual number of curve entries
    steps = 2**15 + 1
    maxv = steps - 1.0
    gammas = rgb_space[0]
    if not isinstance(gammas, (list, tuple)):
        gammas = [gammas]
    for i, gamma in enumerate(gammas):
        maxi = colormath.specialpow(white_Y, 1.0 / gamma)
        segment = 1.0 / (clutres - 1.0) * maxi
        iv = 0.0
        prevpow = 0.0
        nextpow = colormath.specialpow(segment, gamma)
        xp = []
        for j in range(steps):
            v = (j / maxv) * maxi
            if v > iv + segment:
                iv += segment
                prevpow = nextpow
                nextpow = colormath.specialpow(iv + segment, gamma)
            prevs = 1.0 - (v - iv) / segment
            nexts = (v - iv) / segment
            vv = prevs * prevpow + nexts * nextpow
            out = colormath.specialpow(vv, 1.0 / gamma)
            xp.append(out)
        interp = colormath.Interp(xp, list(range(steps)), use_numpy=True)

        # Create input curves
        itable.input.append([])
        otable.input.append([])
        for j in range(4096):
            otable.input[i].append(
                colormath.specialpow(j / 4095.0 * white_Y, 1.0 / gamma) * 65535
            )

        # Fill input curves from interpolated values
        for j in range(entries):
            v = j / (entries - 1.0)
            itable.input[i].append(interp(v) / maxv * 65535)

    # Fill remaining input curves from first input curve and create output curves
    for i in range(3):
        if len(itable.input) < 3:
            itable.input.append(itable.input[0])
            otable.input.append(otable.input[0])
        itable.output.append([0, 65535])
        otable.output.append([0, 65535])

    # Create and fill cLUT
    itable.clut = []
    step = 1.0 / (clutres - 1.0)
    for R in range(clutres):
        for G in range(clutres):
            itable.clut.append([])
            for B in range(clutres):
                X, Y, Z = colormath.adapt(
                    *colormath.RGB2XYZ(
                        *[v * step * maxi for v in (R, G, B)], rgb_space=rgb_space
                    ),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                X, Y, Z = colormath.blend_blackpoint(X, Y, Z, None, XYZbp)
                itable.clut[-1].append([max(v / white_Y * 32768, 0) for v in (X, Y, Z)])

    otable.clut = []
    for R in range(2):
        for G in range(2):
            otable.clut.append([])
            for B in range(2):
                otable.clut[-1].append([v * 65535 for v in (R, G, B)])

    return profile


def create_synthetic_smpte2084_clut_profile(
    rgb_space,
    description,
    black_cdm2=0,
    white_cdm2=400,
    master_black_cdm2=0,
    master_white_cdm2=10000,
    use_alternate_master_white_clip=True,
    content_rgb_space="DCI P3",
    rolloff=True,
    clutres=33,
    mode="HSV_ICtCp",
    sat=1.0,
    hue=0.5,
    forward_xicclu=None,
    backward_xicclu=None,
    generate_B2A=False,
    worker=None,
    logfile=None,
    cat="Bradford",
):
    """Create a synthetic cLUT profile with the SMPTE 2084 TRC from a colorspace
    definition

    mode:  The gamut mapping mode when rolling off. Valid values:
           "HSV_ICtCp" (default, recommended)
           "ICtCp"
           "XYZ" (not recommended, unpleasing hue shift)
           "HSV" (not recommended, saturation loss)
           "RGB" (not recommended, saturation loss, pleasing hue shift)

    The roll-off saturation and hue preservation can be controlled.

    sat:   Saturation preservation factor [0.0, 1.0]
           0.0 = Favor luminance preservation over saturation
           1.0 = Favor saturation preservation over luminance

    hue:   Selective hue preservation factor [0.0, 1.0]
           0.0 = Allow hue shift for redorange/orange/yellowgreen towards
                 yellow to preserve more saturation and detail
           1.0 = Preserve hue

    """

    if not rolloff:
        raise NotImplementedError("rolloff needs to be True")

    return create_synthetic_hdr_clut_profile(
        "PQ",
        rgb_space,
        description,
        black_cdm2,
        white_cdm2,
        master_black_cdm2,
        master_white_cdm2,
        use_alternate_master_white_clip,
        1.2,  # Not used for PQ
        5.0,  # Not used for PQ
        1.0,  # Not used for PQ
        content_rgb_space,
        clutres,
        mode,
        sat,
        hue,
        forward_xicclu,
        backward_xicclu,
        generate_B2A,
        worker,
        logfile,
        cat,
    )


def create_synthetic_hdr_clut_profile(
    hdr_format,
    rgb_space,
    description,
    black_cdm2=0,
    white_cdm2=400,
    master_black_cdm2=0,  # Not used for HLG
    master_white_cdm2=10000,  # Not used for HLG
    use_alternate_master_white_clip=True,  # Not used for HLG
    system_gamma=1.2,  # Not used for PQ
    ambient_cdm2=5,  # Not used for PQ
    maxsignal=1.0,  # Not used for PQ
    content_rgb_space="DCI P3",
    clutres=33,
    mode="HSV_ICtCp",  # Not used for HLG
    sat=1.0,  # Not used for HLG
    hue=0.5,  # Not used for HLG
    forward_xicclu=None,
    backward_xicclu=None,
    generate_B2A=False,
    worker=None,
    logfile=None,
    cat="Bradford",
):
    """Create a synthetic HDR cLUT profile from a colorspace definition"""

    rgb_space = colormath.get_rgb_space(rgb_space)
    content_rgb_space = colormath.get_rgb_space(content_rgb_space)

    if hdr_format == "PQ":
        bt2390 = colormath.BT2390(
            black_cdm2,
            white_cdm2,
            master_black_cdm2,
            master_white_cdm2,
            use_alternate_master_white_clip,
        )
        # Preserve detail in saturated colors if mastering display peak < 10K cd/m2
        # XXX: Effect is detrimental to contrast at low target peak, and looks
        # artificial for BT.2390-4. Don't use for now.
        preserve_saturated_detail = False  # master_white_cdm2 < 10000
        if preserve_saturated_detail:
            bt2390s = colormath.BT2390(black_cdm2, white_cdm2, master_black_cdm2, 10000)

        maxv = white_cdm2 / 10000.0
        eotf = lambda v: colormath.specialpow(v, -2084)
        oetf = eotf_inverse = lambda v: colormath.specialpow(v, 1.0 / -2084)
        eetf = bt2390.apply

        # Apply a slight power to the segments to optimize encoding
        encpow = min(max(bt2390.omaxi * (5 / 3.0), 1.0), 1.5)

        def encf(v):
            if v < bt2390.mmaxi:
                v = colormath.convert_range(v, 0, bt2390.mmaxi, 0, 1)
                v = colormath.specialpow(v, 1.0 / encpow, 2)
                return colormath.convert_range(v, 0, 1, 0, bt2390.mmaxi)
            else:
                return v

        def encf_inverse(v):
            if v < bt2390.mmaxi:
                v = colormath.convert_range(v, 0, bt2390.mmaxi, 0, 1)
                v = colormath.specialpow(v, encpow, 2)
                return colormath.convert_range(v, 0, 1, 0, bt2390.mmaxi)
            else:
                return v

    elif hdr_format == "HLG":
        # Note: Unlike the PQ black level lift, we apply HLG black offset as
        # separate final step, not as part of the HLG EOTF
        hlg = colormath.HLG(0, white_cdm2, system_gamma, ambient_cdm2, rgb_space)

        if maxsignal < 1:
            # Adjust EOTF so that EOTF[maxsignal] gives (approx) white_cdm2
            while hlg.eotf(maxsignal) * hlg.white_cdm2 < white_cdm2:
                hlg.white_cdm2 += 1

        lscale = 1.0 / hlg.oetf(1.0, True)
        hlg.white_cdm2 *= lscale
        if lscale < 1 and logfile:
            logfile.write(
                f"Nominal peak luminance after scaling = {hlg.white_cdm2:.2f}\n"
            )

        Ymax = hlg.eotf(maxsignal)

        maxv = 1.0
        eotf = hlg.eotf
        eotf_inverse = lambda v: hlg.eotf(v, True)
        oetf = hlg.oetf
        eetf = lambda v: v

        encf = lambda v: v
    else:
        raise NotImplementedError(f"Unknown HDR format {repr(hdr_format)}")

    tonemap = eetf(1) != 1

    profile = ICCProfile()
    profile.version = 2.2  # Match ArgyllCMS

    profile.tags.desc = TextDescriptionType(b"", "desc")
    profile.tags.desc.ASCII = description
    profile.tags.cprt = TextType(b"text\0\0\0\0Public domain\0", "cprt")

    profile.tags.wtpt = XYZType(profile=profile)
    (
        profile.tags.wtpt.X,
        profile.tags.wtpt.Y,
        profile.tags.wtpt.Z,
    ) = colormath.get_whitepoint(rgb_space[1])

    profile.tags.arts = chromaticAdaptionTag()
    profile.tags.arts.update(colormath.get_cat_matrix(cat))

    itable = profile.tags.A2B0 = LUT16Type(None, "A2B0", profile)
    itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    # HDR RGB
    debugtable0 = profile.tags.DBG0 = LUT16Type(None, "DBG0", profile)
    debugtable0.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    # Display RGB
    debugtable1 = profile.tags.DBG1 = LUT16Type(None, "DBG1", profile)
    debugtable1.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    # Display XYZ
    debugtable2 = profile.tags.DBG2 = LUT16Type(None, "DBG2", profile)
    debugtable2.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    if generate_B2A:
        otable = profile.tags.B2A0 = LUT16Type(None, "B2A0", profile)
        Xr, Yr, Zr = colormath.adapt(
            *colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space),
            whitepoint_source=rgb_space[1],
            cat=cat,
        )
        Xg, Yg, Zg = colormath.adapt(
            *colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space),
            whitepoint_source=rgb_space[1],
            cat=cat,
        )
        Xb, Yb, Zb = colormath.adapt(
            *colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space),
            whitepoint_source=rgb_space[1],
            cat=cat,
        )
        m1 = colormath.Matrix3x3(((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb)))
        m2 = m1.inverted()
        scale = 1 + (32767 / 32768.0)
        m3 = colormath.Matrix3x3(((scale, 0, 0), (0, scale, 0), (0, 0, scale)))
        otable.matrix = m2 * m3

    # Input curve interpolation
    # Normlly the input curves would either be linear (= 1:1 mapping to
    # cLUT) or the respective tone response curve.
    # We use a overall linear curve that is 'bent' in <clutres> intervals
    # to accomodate the non-linear TRC. Thus, we can get away with much
    # fewer cLUT grid points.

    # Use higher interpolation size than actual number of curve entries
    steps = 2**15 + 1
    maxstep = steps - 1.0
    segment = 1.0 / (clutres - 1.0)
    iv = 0.0
    prevpow = eotf(eetf(0))
    # Apply a slight power to segments to optimize encoding
    nextpow = eotf(eetf(encf(segment)))
    prevv = 0
    pprevpow = [0]
    clipped = False
    xp = []
    if generate_B2A:
        oxp = []
    for j in range(steps):
        v = j / maxstep
        if v > iv + segment:
            iv += segment
            prevpow = nextpow
            # Apply a slight power to segments to optimize encoding
            nextpow = eotf(eetf(encf(iv + segment)))
        if nextpow > prevpow or test_input_curve_clipping:
            prevs = 1.0 - (v - iv) / segment
            nexts = (v - iv) / segment
            vv = prevs * prevpow + nexts * nextpow
            prevv = v
            if prevpow > pprevpow[-1]:
                pprevpow.append(prevpow)
        else:
            clipped = True
            # Linearly interpolate
            vv = colormath.convert_range(v, prevv, 1, prevpow, 1)
        out = eotf_inverse(vv)
        xp.append(out)
        if generate_B2A:
            oxp.append(eotf(eetf(v)) / maxv)
    interp = colormath.Interp(xp, list(range(steps)), use_numpy=True)
    if generate_B2A:
        ointerp = colormath.Interp(oxp, list(range(steps)), use_numpy=True)

    # Save interpolation input values for diagnostic purposes
    profile.tags.kTRC = CurveType()
    interp_inverse = colormath.Interp(list(range(steps)), xp, use_numpy=True)
    profile.tags.kTRC[:] = [
        interp_inverse(colormath.convert_range(v, 0, 2048, 0, maxstep)) * 65535
        for v in range(2049)
    ]

    # Create input and output curves
    for _i in range(3):
        itable.input.append([])
        itable.output.append([0, 65535])
        debugtable0.input.append([0, 65535])
        debugtable0.output.append([0, 65535])
        debugtable1.input.append([0, 65535])
        debugtable1.output.append([0, 65535])
        debugtable2.input.append([0, 65535])
        debugtable2.output.append([0, 65535])
        if generate_B2A:
            otable.input.append([])
            otable.output.append([0, 65535])

    # Generate device-to-PCS shaper curves from interpolated values
    if logfile:
        logfile.write("Generating device-to-PCS shaper curves...\n")
    entries = 1025
    prevperc = 0
    if generate_B2A:
        endperc = 1
    else:
        endperc = 2
    threshold = eotf_inverse(pprevpow[-2])
    k = None
    end = eotf_inverse(pprevpow[-1])
    l = entries - 1
    if end > threshold:
        for j in range(entries):
            n = j / (entries - 1.0)
            if eetf(n) > end:
                l = j - 1
                break
    for j in range(entries):
        if worker and worker.thread_abort:
            if forward_xicclu:
                forward_xicclu.exit()
            if backward_xicclu:
                backward_xicclu.exit()
            raise Exception("aborted")
        n = j / (entries - 1.0)
        v = interp(eetf(n)) / maxstep
        if hdr_format == "PQ":
            # threshold = 1.0 - segment * math.ceil((1.0 - bt2390.mmaxi) *
            # (clutres - 1.0) + 1)
            # check = n >= threshold
            check = tonemap and eetf(n + (1 / (entries - 1.0))) > threshold
        elif hdr_format == "HLG":
            check = maxsignal < 1 and n >= maxsignal
        if check and not test_input_curve_clipping:
            # Linear interpolate shaper for last n cLUT steps to prevent
            # clipping in shaper
            if k is None:
                k = j
                ov = v
                ev = interp(eetf(l / (entries - 1.0))) / maxstep
            # v = min(ov + (1.0 - ov) * ((j - k) / (entries - k - 1.0)), 1.0)
            v = min(colormath.convert_range(j, k, l, ov, ev), n)
        for i in range(3):
            itable.input[i].append(v * 65535)
        perc = math.floor(n * endperc)
        if logfile and perc > prevperc:
            logfile.write(f"\r{perc:.0f}%")
            prevperc = perc
    startperc = perc

    if generate_B2A:
        # Generate PCS-to-device shaper curves from interpolated values
        if logfile:
            logfile.write("\rGenerating PCS-to-device shaper curves...\n")
            logfile.write(f"\r{perc:.0f}%")
        for j in range(4096):
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")
            n = j / 4095.0
            v = ointerp(n) / maxstep * 65535
            for i in range(3):
                otable.input[i].append(v)
            perc = startperc + math.floor(n)
            if logfile and perc > prevperc:
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
        startperc = perc

    # Scene RGB -> HDR tone mapping -> HDR XYZ -> backward lookup -> display RGB
    itable.clut = []
    debugtable0.clut = []
    debugtable1.clut = []
    debugtable2.clut = []
    clutmax = clutres - 1.0
    step = 1.0 / clutmax
    count = 0
    # Lpt is the preferred mode for chroma blending. Some preliminary visual
    # comparison has shown it does overall the best job preserving hue and
    # saturation (blue hues superior to IPT). DIN99d is the second best,
    # but vibrant red turns slightly orange when desaturated (DIN99d has best
    # blue saturation preservation though).
    blendmode = "Lpt"
    IPT_white_XYZ = colormath.get_cat_matrix("IPT").inverted() * (1, 1, 1)
    Cmode = ("all", "primaries_secondaries")[0]
    RGB_in = []
    HDR_ICtCp = []
    HDR_RGB = []
    HDR_XYZ = []
    HDR_min_I = []
    logmsg = "\rGenerating lookup table"
    if hdr_format == "PQ" and tonemap:
        logmsg += " and applying HDR tone mapping"
        endperc = 25
    else:
        endperc = 50
    if logfile:
        logfile.write(f"{logmsg}...\n")
        logfile.write(f"\r{perc:.0f}%")
    # Selective hue preservation for redorange/orange
    # (otherwise shift towards yellow to preserve more saturation and detail)
    # Hue angles (RGB):
    # red, yellow, yellow, green, red
    hinterp = colormath.Interp(
        [0, 0.166666, 0.166666, 1], [1, hue, 1, 1], use_numpy=True
    )
    # Saturation adjustment for yellow/green/cyan
    # Hue angles (RGB):
    # red, orange, yellow, green, cyan, cyan/blue, red
    sinterp = colormath.Interp(
        [0, 0.083333, 0.166666, 0.333333, 0.5, 0.583333, 1],
        [1, 1, 0.5, 0.5, 0.5, 1, 1],
        use_numpy=True,
    )
    for R in range(clutres):
        for G in range(clutres):
            for B in range(clutres):
                if worker and worker.thread_abort:
                    if forward_xicclu:
                        forward_xicclu.exit()
                    if backward_xicclu:
                        backward_xicclu.exit()
                    raise Exception("aborted")
                # Apply a slight power to the segments to optimize encoding
                RGB = [encf(v * step) for v in (R, G, B)]
                RGB_in.append(tuple(RGB))
                if DEBUG and R == G == B:
                    print("RGB {:5.3f} {:5.3f} {:5.3f}".format(*RGB), end=" ")
                # RGB_sum = sum(RGB)
                if hdr_format == "PQ" and mode in (
                    "HSV",
                    "HSV_ICtCp",
                    "ICtCp",
                    "RGB_ICtCp",
                ):
                    # Record original hue angle, saturation and value
                    H, S, V = colormath.RGB2HSV(*RGB)
                if hdr_format == "PQ" and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                    I1, Ct1, Cp1 = colormath.RGB2ICtCp(
                        *RGB, rgb_space=rgb_space, eotf=eotf, oetf=eotf_inverse
                    )
                    if DEBUG and R == G == B:
                        print(
                            f"-> ICtCp {I1:5.3f} {Ct1:5.3f} {Cp1:5.3f}",
                            end=" ",
                        )
                    I2 = eetf(I1)
                    if preserve_saturated_detail and S:
                        sf = S
                        I2 *= 1 - sf
                        I2 += bt2390s.apply(I1) * sf
                if hdr_format == "HLG":
                    X, Y, Z = hlg.RGB2XYZ(*RGB)
                    if Y:
                        Y1 = Y
                        I1 = hlg.eotf(Y, True)
                        I2 = min(I1, maxsignal)
                        Y2 = hlg.eotf(I2)
                        Y3 = Y2 / Ymax
                        X, Y, Z = (v / Y * Y3 if Y else v for v in (X, Y, Z))
                        if R == G == B and logfile and DEBUG:
                            logfile.write(
                                f"\rE {Y1:.4f} -> E' {I1:.4f} -> roll-off -> "
                                f"{I2:.4f} -> E {Y2:.4f} -> "
                                f"scale ({Y3 / Y2:.0%}) -> {Y3:.4f}\n"
                            )
                elif mode == "XYZ":
                    X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space, eotf=eotf)
                    if Y:
                        I1 = colormath.specialpow(Y, 1.0 / -2084)
                        I2 = eetf(I1)
                        Y2 = colormath.specialpow(I2, -2084)
                        X, Y, Z = (v / Y * Y2 for v in (X, Y, Z))
                    else:
                        I1 = I2 = 0
                elif mode in ("HSV", "HSV_ICtCp", "ICtCp", "RGB", "RGB_ICtCp"):
                    if mode in ("HSV", "RGB"):
                        I1 = max(RGB)
                    if mode in ("HSV", "HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                        # Allow hue shift based on hue angle
                        hf = hinterp(H)

                        # Saturation adjustment
                        cf = sinterp(H)
                    for i, v in enumerate(RGB):
                        RGB[i] = eetf(v)
                        if preserve_saturated_detail and S:
                            sf = S
                            RGB[i] *= 1 - sf
                            RGB[i] += bt2390s.apply(v) * sf
                    RGB_shifted = RGB  # Potentially hue shifted RGB
                    if mode in ("HSV", "HSV_ICtCp"):
                        HSV = list(colormath.RGB2HSV(*RGB_shifted))

                        if mode == "HSV":
                            # Allow hue shift based on hue angle
                            H = H * hf + HSV[0] * (1 - hf)

                        # Set hue angle
                        HSV[0] = H
                        RGB = colormath.HSV2RGB(*HSV)
                    if mode in ("HSV", "RGB"):
                        I2 = max(RGB)
                elif mode == "YRGB":
                    LinearRGB = [eotf(v) for v in RGB]
                    I1 = (
                        0.2627 * LinearRGB[0]
                        + 0.678 * LinearRGB[1]
                        + 0.0593 * LinearRGB[2]
                    )
                    I2 = eotf(eetf(eotf_inverse(I1)))
                    if I1:
                        min_I = I2 / I1
                    else:
                        min_I = 1
                    RGB = [eotf_inverse(min_I * v) for v in LinearRGB]
                if (
                    hdr_format == "PQ"
                    and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp", "XYZ")
                    and I1
                    and I2
                ):
                    if mode != "ICtCp" or (forward_xicclu and backward_xicclu):
                        # Don't desaturate colors which are lighter after
                        # roll-off if mode is not ICtCp or if doing
                        # display-based desaturation
                        dsat = 1.0
                    else:
                        # Desaturate colors which are lighter after roll-off
                        # if mode is ICtCp and not doing display-based
                        # desaturation
                        dsat = I1 / I2
                    min_I = min(dsat, I2 / I1)
                else:
                    min_I = 1
                if hdr_format == "PQ" and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                    if DEBUG and R == G == B:
                        print(f"* {min_I:5.3f}", "->", end=" ")
                    Ct2, Cp2 = (min_I * v for v in (Ct1, Cp1))
                    if DEBUG and R == G == B:
                        print(f"{I2:5.3f} {Ct2:5.3f} {Cp2:5.3f}", "->", end=" ")
                if hdr_format == "HLG":
                    pass
                elif mode == "XYZ":
                    X, Y, Z = colormath.XYZsaturation(X, Y, Z, min_I, rgb_space[1])[0]
                    RGB = colormath.XYZ2RGB(X, Y, Z, rgb_space, oetf=eotf_inverse)
                elif mode == "ICtCp":
                    X, Y, Z = colormath.ICtCp2XYZ(I2, Ct2, Cp2)
                    RGB = colormath.XYZ2RGB(
                        X, Y, Z, rgb_space, clamp=False, oetf=eotf_inverse
                    )
                if DEBUG and R == G == B:
                    print("RGB {:5.3f} {:5.3f} {:5.3f}".format(*RGB))
                HDR_RGB.append(RGB)
                if hdr_format == "HLG":
                    pass
                elif mode not in ("XYZ", "ICtCp"):
                    X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space, eotf=eotf)
                if hdr_format == "PQ" and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                    # Use hue and chroma from ICtCp
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)
                    L, C, H = colormath.Lab2LCHab(I * 100, Ct * 100, Cp * 100)
                    L2, C2, H2 = colormath.Lab2LCHab(I2 * 100, Ct2 * 100, Cp2 * 100)

                    # Allow hue shift based on hue angle
                    I3, Ct3, Cp3 = colormath.RGB2ICtCp(
                        *RGB_shifted, rgb_space=rgb_space, eotf=eotf, oetf=eotf_inverse
                    )
                    L3, C3, H3 = colormath.Lab2LCHab(I3 * 100, Ct3 * 100, Cp3 * 100)
                    L = L * hf + L3 * (1 - hf)
                    C = C * hf + C3 * (1 - hf)
                    H2 = H2 * hf + H3 * (1 - hf)

                    # Saturation adjustment
                    C = colormath.convert_range(I1, I2, 1, C2, min(C2, C) * cf)
                    I, Ct2, Cp2 = (v / 100.0 for v in colormath.LCHab2Lab(L, C, H2))
                    Ct, Cp = Ct2, Cp2
                    if I1 > I2:
                        f = colormath.convert_range(I1, I2, 1, 1, 0)
                        Ct2, Cp2 = (v * f for v in (Ct2, Cp2))
                    if mode in ("HSV_ICtCp", "RGB_ICtCp"):
                        f = colormath.convert_range(sum(RGB_in[-1]), 0, 3, 1, sat)
                        Ct2 = Ct * f + Ct2 * (1 - f)
                        Cp2 = Cp * f + Cp2 * (1 - f)
                        I2 = I * f + I2 * (1 - f)
                    X, Y, Z = colormath.ICtCp2XYZ(I2, Ct2, Cp2)
                    RGB_ICtCp_XYZ = list((X, Y, Z))
                else:
                    # RGB_ICtCp_XYZ = [v / maxv for v in (X, Y, Z)]
                    RGB_ICtCp_XYZ = [X, Y, Z]
                # X, Y, Z = (v / maxv for v in (X, Y, Z))
                HDR_XYZ.append((RGB_in[-1], [X, Y, Z], RGB_ICtCp_XYZ))
                HDR_min_I.append(min_I)
                count += 1
                perc = startperc + math.floor(
                    count / clutres**3.0 * (endperc - startperc)
                )
                if logfile and perc > prevperc:
                    logfile.write(f"\r{perc:.0f}%")
                    prevperc = perc

    if hdr_format == "PQ" and tonemap:
        from DisplayCAL.multiprocess import cpu_count, pool_slice

        num_cpus = cpu_count()
        num_workers = num_cpus
        if num_cpus > 2:
            num_workers -= 1
        num_batches = clutres // 6

        HDR_XYZ = sum(
            pool_slice(
                _mp_hdr_tonemap,
                HDR_XYZ,
                (rgb_space, maxv, sat, cat),
                {},
                num_workers,
                worker and worker.thread_abort,
                logfile,
                num_batches,
                perc,
            ),
            [],
        )
        prevperc = startperc = perc = 75
    else:
        prevperc = startperc = perc = 50

    for i, item in enumerate(HDR_XYZ):
        if not item:  # Aborted
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")
        (RGB, (X, Y, Z), RGB_ICtCp_XYZ) = item
        I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z, oetf=eotf_inverse)
        X, Y, Z = (v / maxv for v in (X, Y, Z))
        HDR_ICtCp.append((I, Ct, Cp))
        # Adapt to D50
        X, Y, Z = colormath.adapt(X, Y, Z, whitepoint_source=rgb_space[1], cat=cat)
        if max(X, Y, Z) * 32768 > 65535 or min(X, Y, Z) < 0 or round(Y, 6) > 1:
            # This should not happen
            print(
                f"#{i}",
                "RGB {:.3f} {:.3f} {:.3f}".format(*RGB),
                f"XYZ {X:.6f} {Y:.6f} {Z:.6f}",
                "not in range [0,1]",
            )
        HDR_XYZ[i] = (X, Y, Z)
        perc = startperc + math.floor(i / clutres**3.0 * (100 - startperc))
        if logfile and perc > prevperc:
            logfile.write(f"\r{perc:.0f}%")
            prevperc = perc
    prevperc = startperc = perc = 0

    if forward_xicclu and backward_xicclu and logfile:
        logfile.write("\rDoing backward lookup...\n")
        logfile.write(f"\r{perc:.0f}%")
    count = 0
    for _i, (X, Y, Z) in enumerate(HDR_XYZ):
        if worker and worker.thread_abort:
            if forward_xicclu:
                forward_xicclu.exit()
            if backward_xicclu:
                backward_xicclu.exit()
            raise Exception("aborted")
        if forward_xicclu and backward_xicclu and Cmode != "primaries_secondaries":
            # HDR XYZ -> backward lookup -> display RGB
            backward_xicclu((X, Y, Z))
            count += 1
            perc = startperc + math.floor(count / clutres**3.0 * (100 - startperc))
            if (
                logfile
                and perc > prevperc
                and backward_xicclu.__class__.__name__ == "Xicclu"
            ):
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
    prevperc = startperc = perc = 0

    Cdiff = []
    Cmax = {}
    Cdmax = {}
    if forward_xicclu and backward_xicclu:
        # Display RGB -> forward lookup -> display XYZ
        backward_xicclu.close()
        try:
            display_RGB = backward_xicclu.get()
        except Exception:
            if forward_xicclu:
                # Make sure resources are not held in use
                forward_xicclu.exit()
            raise
        finally:
            backward_xicclu.exit()
        if logfile:
            logfile.write("\rDoing forward lookup...\n")
            logfile.write(f"\r{perc:.0f}%")

        # Smooth
        row = 0
        for col_0 in range(clutres):
            for col_1 in range(clutres):
                debugtable1.clut.append([])
                for col_2 in range(clutres):
                    RGBdisp = display_RGB[row]
                    debugtable1.clut[-1].append(
                        [min(max(v * 65535, 0), 65535) for v in RGBdisp]
                    )
                    row += 1
        debugtable1.smooth()
        display_RGB = []
        for block in debugtable1.clut:
            for row in block:
                display_RGB.append([v / 65535.0 for v in row])

        for i, (R, G, B) in enumerate(display_RGB):
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")
            forward_xicclu((R, G, B))
            perc = startperc + math.floor((i + 1) / clutres**3.0 * (100 - startperc))
            if (
                logfile
                and perc > prevperc
                and forward_xicclu.__class__.__name__ == "Xicclu"
            ):
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
        prevperc = startperc = perc = 0

        if Cmode == "primaries_secondaries":
            # Compare to chroma of content primaries/secondaries to determine
            # general chroma compression factor
            forward_xicclu((0, 0, 1))
            forward_xicclu((0, 1, 0))
            forward_xicclu((1, 0, 0))
            forward_xicclu((0, 1, 1))
            forward_xicclu((1, 0, 1))
            forward_xicclu((1, 1, 0))
        forward_xicclu.close()
        display_XYZ = forward_xicclu.get()
        if Cmode == "primaries_secondaries":
            for i in range(6):
                if i == 0:
                    # Blue
                    j = clutres - 1
                elif i == 1:
                    # Green
                    j = clutres**2 - clutres
                elif i == 2:
                    # Red
                    j = clutres**3 - clutres**2
                elif i == 3:
                    # Cyan
                    j = clutres**2 - 1
                elif i == 4:
                    # Magenta
                    j = clutres**3 - clutres**2 + clutres - 1
                elif i == 5:
                    # Yellow
                    j = clutres**3 - clutres
                R, G, B = RGB_in[j]
                XYZsrc = HDR_XYZ[j]
                XYZdisp = display_XYZ[-(6 - i)]
                XYZc = colormath.RGB2XYZ(R, G, B, content_rgb_space, eotf=eotf)
                XYZc = colormath.adapt(
                    *XYZc, whitepoint_source=content_rgb_space[1], cat=cat
                )
                L, C, H = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZc))
                Ld, Cd, Hd = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZdisp))
                Cdmaxk = tuple(map(round, (Ld, Hd)))
                if C > Cmax.get(Cdmaxk, -1):
                    Cmax[Cdmaxk] = C
                Cdiff.append(min(Cd / C, 1.0))
                if Cd > Cdmax.get(Cdmaxk, -1):
                    Cdmax[Cdmaxk] = Cd
                print(f"RGB in {R:5.2f} {G:5.2f} {B:5.2f}")
                print(
                    "Content BT2020 XYZ (DIN99d) {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v * 100 for v in XYZc)
                    )
                )
                print(f"Content BT2020 LCH (DIN99d) {L:5.2f} {C:5.2f} {H:5.2f}")
                print(
                    "Display XYZ {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v * 100 for v in XYZdisp)
                    )
                )
                print(f"Display LCH (DIN99d) {Ld:5.2f} {Cd:5.2f} {Hd:5.2f}")
                if logfile:
                    logfile.write(
                        "\r{} chroma compression factor: {:6.4f}\n".format(
                            {0: "B", 1: "G", 2: "R", 3: "C", 4: "M", 5: "Y"}[i],
                            Cdiff[-1],
                        )
                    )
            # Tweak so that it gives roughly 0.91 for a Rec. 709 target
            general_compression_factor = (sum(Cdiff) / len(Cdiff)) * 0.99
    else:
        display_RGB = False
        display_XYZ = False

    display_LCH = []
    if Cmode != "primaries_secondaries" and display_XYZ:
        # Determine compression factor by comparing display to content
        # colorspace in BT.2020
        if logfile:
            logfile.write("\rDetermining chroma compression factors...\n")
            logfile.write(f"\r{perc:.0f}%")
        for i, XYZsrc in enumerate(HDR_XYZ):
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")
            if display_XYZ:
                XYZdisp = display_XYZ[i]
            # # Adjust luminance from destination to source
            # Ydisp = XYZdisp[1]
            # if Ydisp:
            #     XYZdisp = [v / Ydisp * XYZsrc[1] for v in XYZdisp]
            else:
                XYZdisp = XYZsrc
            X, Y, Z = (v * maxv for v in XYZsrc)
            X, Y, Z = colormath.adapt(
                X, Y, Z, whitepoint_destination=content_rgb_space[1], cat=cat
            )
            R, G, B = colormath.XYZ2RGB(X, Y, Z, content_rgb_space, oetf=eotf_inverse)
            XYZc = colormath.RGB2XYZ(R, G, B, content_rgb_space, eotf=eotf)
            XYZc = colormath.adapt(
                *XYZc,
                whitepoint_source=content_rgb_space[1],
                whitepoint_destination=rgb_space[1],
                cat=cat,
            )
            RGBc_r2020 = colormath.XYZ2RGB(
                *XYZc, rgb_space=rgb_space, oetf=eotf_inverse
            )
            XYZc_r2020 = colormath.RGB2XYZ(*RGBc_r2020, rgb_space=rgb_space, eotf=eotf)
            if blendmode == "ICtCp":
                I, Ct, Cp = colormath.XYZ2ICtCp(*XYZc_r2020, oetf=eotf_inverse)
                L, C, H = colormath.Lab2LCHab(I * 100, Cp * 100, Ct * 100)
                XYZdispa = colormath.adapt(
                    *XYZdisp, whitepoint_destination=rgb_space[1], cat=cat
                )
                Id, Ctd, Cpd = colormath.XYZ2ICtCp(
                    *(v * maxv for v in XYZdispa), oetf=eotf_inverse
                )
                Ld, Cd, Hd = colormath.Lab2LCHab(Id * 100, Cpd * 100, Ctd * 100)
            elif blendmode == "IPT":
                XYZc_r2020 = colormath.adapt(
                    *XYZc_r2020,
                    whitepoint_source=rgb_space[1],
                    whitepoint_destination=IPT_white_XYZ,
                    cat=cat,
                )
                I, CP, CT = colormath.XYZ2IPT(*XYZc_r2020)
                L, C, H = colormath.Lab2LCHab(I * 100, CP * 100, CT * 100)
                XYZdispa = colormath.adapt(
                    *XYZdisp, whitepoint_destination=IPT_white_XYZ, cat=cat
                )
                Id, Pd, Td = colormath.XYZ2IPT(*XYZdispa)
                Ld, Cd, Hd = colormath.Lab2LCHab(Id * 100, Pd * 100, Td * 100)
            elif blendmode == "Lpt":
                XYZc_r2020 = colormath.adapt(
                    *XYZc_r2020, whitepoint_source=rgb_space[1], cat=cat
                )
                L, p, t = colormath.XYZ2Lpt(*(v / maxv * 100 for v in XYZc_r2020))
                L, C, H = colormath.Lab2LCHab(L, p, t)
                Ld, pd, td = colormath.XYZ2Lpt(*(v * 100 for v in XYZdisp))
                Ld, Cd, Hd = colormath.Lab2LCHab(Ld, pd, td)
            elif blendmode == "XYZ":
                XYZc_r2020 = colormath.adapt(
                    *XYZc_r2020, whitepoint_source=rgb_space[1], cat=cat
                )
                wx, wy = colormath.XYZ2xyY(*colormath.get_whitepoint())[:2]
                x, y, Y = colormath.XYZ2xyY(*XYZc_r2020)
                x -= wx
                y -= wy
                L, C, H = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))
                x, y, Y = colormath.XYZ2xyY(*XYZdisp)
                x -= wx
                y -= wy
                Ld, Cd, Hd = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))
            else:
                # DIN99d
                XYZc_r202099 = colormath.adapt(
                    *XYZc_r2020, whitepoint_source=rgb_space[1], cat=cat
                )
                L, C, H = colormath.XYZ2DIN99dLCH(
                    *(v / maxv * 100 for v in XYZc_r202099)
                )
                Ld, Cd, Hd = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZdisp))
            Cdmaxk = tuple(map(round, (Ld, Hd), (2, 2)))
            if C > Cmax.get(Cdmaxk, -1):
                Cmax[Cdmaxk] = C
            if C:
                # print(f"{Cd:6.3f} {C:6.3f}")
                Cdiff.append(min(Cd / C, 1.0))
            # if Cdiff[-1] < 0.0001:
            #     raise RuntimeError(f"#{i} RGB {R:5.3f} {G:5.3f} {B:5.3f} Cdiff {Cdiff[-1]:5.3f}")
            else:
                Cdiff.append(1.0)
            display_LCH.append((Ld, Cd, Hd))
            if Cd > Cdmax.get(Cdmaxk, -1):
                Cdmax[Cdmaxk] = Cd
            if DEBUG:
                print("RGB in {:5.2f} {:5.2f} {:5.2f}".format(*RGB_in[i]))
                print(f"RGB out {R:5.2f} {G:5.2f} {B:5.2f}")
                print(
                    "Content BT2020 XYZ {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v / maxv * 100 for v in XYZc_r2020)
                    )
                )
                print(f"Content BT2020 LCH {L:5.2f} {C:5.2f} {H:5.2f}")
                print(
                    "Display XYZ {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v * 100 for v in XYZdisp)
                    )
                )
                print(f"Display LCH {Ld:5.2f} {Cd:5.2f} {Hd:5.2f}")
            perc = startperc + math.floor(i / clutres**3.0 * (80 - startperc))
            if logfile and perc > prevperc:
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
        startperc = perc

        general_compression_factor = sum(Cdiff) / len(Cdiff)

    if display_XYZ:
        Cmaxv = max(Cmax.values())
        Cdmaxv = max(Cdmax.values())

    if logfile and display_LCH and Cmode == "primaries_secondaries":
        logfile.write(
            f"\rChroma compression factor: {general_compression_factor:6.4f}\n"
        )

    # Chroma compress to display XYZ
    if logfile:
        if display_XYZ:
            logfile.write("\rApplying chroma compression and filling cLUT...\n")
        else:
            logfile.write("\rFilling cLUT...\n")
        logfile.write(f"\r{perc:.0f}%")
    row = 0
    oog_count = 0
    # if forward_xicclu:
    #     forward_xicclu.spawn()
    # if backward_xicclu:
    #     backward_xicclu.spawn()
    for col_0 in range(clutres):
        for col_1 in range(clutres):
            itable.clut.append([])
            debugtable0.clut.append([])
            if not display_RGB:
                debugtable1.clut.append([])
            debugtable2.clut.append([])
            for col_2 in range(clutres):
                if worker and worker.thread_abort:
                    if forward_xicclu:
                        forward_xicclu.exit()
                    if backward_xicclu:
                        backward_xicclu.exit()
                    raise Exception("aborted")
                R, G, B = HDR_RGB[row]
                I, Ct, Cp = HDR_ICtCp[row]
                X, Y, Z = HDR_XYZ[row]
                min_I = HDR_min_I[row]
                if not (col_0 == col_1 == col_2) and display_XYZ:
                    # Desaturate based on compression factor
                    if display_LCH:
                        blend = 1
                    else:
                        # Blending threshold: Don't desaturate dark colors
                        # (< 26 cd/m2). Preserves more "pop"
                        thresh_I = 0.381
                        blend = min_I * min(
                            max((I - thresh_I) / (0.5081 - thresh_I), 0), 1
                        )
                    if blend:
                        if blendmode == "XYZ":
                            wx, wy = colormath.XYZ2xyY(*colormath.get_whitepoint())[:2]
                            x, y, Y = colormath.XYZ2xyY(X, Y, Z)
                            x -= wx
                            y -= wy
                            L, C, H = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))
                        elif blendmode == "ICtCp":
                            L, C, H = colormath.Lab2LCHab(I * 100, Cp * 100, Ct * 100)
                        elif blendmode == "DIN99d":
                            XYZ = X, Y, Z
                            L, C, H = colormath.XYZ2DIN99dLCH(*[v * 100 for v in XYZ])
                        elif blendmode == "IPT":
                            XYZ = colormath.adapt(
                                X, Y, Z, whitepoint_destination=IPT_white_XYZ, cat=cat
                            )
                            I, CP, CT = colormath.XYZ2IPT(*XYZ)
                            L, C, H = colormath.Lab2LCHab(I * 100, CP * 100, CT * 100)
                        elif blendmode == "Lpt":
                            XYZ = X, Y, Z
                            L, p, t = colormath.XYZ2Lpt(*[v * 100 for v in XYZ])
                            L, C, H = colormath.Lab2LCHab(L, p, t)
                        if blendmode:
                            if display_LCH:
                                Ld, Cd, Hd = display_LCH[row]
                                # Cdmaxk = tuple(map(round, (Ld, Hd), (2, 2)))
                                # # Lookup HDR max chroma for given display
                                # # luminance and hue
                                # HCmax = Cmax[Cdmaxk]
                                # if C and HCmax:
                                #     # Lookup display max chroma for given display
                                #     # luminance and hue
                                #     HCdmax = Cdmax[Cdmaxk]
                                #     # Display max chroma in 0..1 range
                                #     maxCc = min(HCdmax / HCmax, 1.0)
                                #     KSCc = 1.5 * maxCc - 0.5
                                #     # HDR chroma in 0..1 range
                                #     Cc1 = min(C / HCmax, 1.0)
                                #     if Cc1 >= KSCc <= 1 and maxCc > KSCc >= 0:
                                #         # Roll-off chroma
                                #         Cc2 = bt2390.apply(
                                #             Cc1, KSCc, maxCc, 1.0, 0, normalize=False
                                #         )
                                #         C = HCmax * Cc2
                                #     else:
                                #         # Use display chroma as-is (clip)
                                #         if debug:
                                #             print(
                                #                 "CLUT grid point "
                                #                 f"{int(col_0):d} {int(col_1):d} {int(col_2):d}: "
                                #                 f"C {C:6.4f} Cd {Cd:6.4f} "
                                #                 f"HCmax {HCmax:6.4f} "
                                #                 f"maxCc {maxCc:6.4f} "
                                #                 f"KSCc {KSCc:6.4f} "
                                #                 f"Cc1 {Cc1:6.4f}"
                                #             )
                                #         C = Cd
                                if C:
                                    C *= min(Cd / C, 1.0)
                                    C *= min(Ld / L, 1.0)
                            else:
                                Cc = general_compression_factor
                                Cc **= C / Cmaxv
                                C = C * (1 - blend) + (C * Cc) * blend
                        if blendmode == "ICtCp":
                            I, Cp, Ct = [
                                v / 100.0 for v in colormath.LCHab2Lab(L, C, H)
                            ]
                            XYZ = colormath.ICtCp2XYZ(I, Ct, Cp, eotf=eotf)
                            X, Y, Z = (v / maxv for v in XYZ)
                            # Adapt to D50
                            X, Y, Z = colormath.adapt(
                                X, Y, Z, whitepoint_source=rgb_space[1], cat=cat
                            )
                        elif blendmode == "DIN99d":
                            L, a, b = colormath.DIN99dLCH2Lab(L, C, H)
                            X, Y, Z = colormath.Lab2XYZ(L, a, b)
                        elif blendmode == "IPT":
                            I, CP, CT = [
                                v / 100.0 for v in colormath.LCHab2Lab(L, C, H)
                            ]
                            X, Y, Z = colormath.IPT2XYZ(I, CP, CT)
                            # Adapt to D50
                            X, Y, Z = colormath.adapt(
                                X, Y, Z, whitepoint_source=IPT_white_XYZ, cat=cat
                            )
                        elif blendmode == "Lpt":
                            L, p, t = colormath.LCHab2Lab(L, C, H)
                            X, Y, Z = colormath.Lpt2XYZ(L, p, t)
                        elif blendmode == "XYZ":
                            Y, x, y = [v / 100.0 for v in colormath.LCHab2Lab(L, C, H)]
                            x += wx
                            y += wy
                            X, Y, Z = colormath.xyY2XYZ(x, y, Y)
                    else:
                        print(
                            f"CLUT grid point {int(col_0):d} {int(col_1):d} {int(col_2):d}: "
                            "blend = 0"
                        )
                # if backward_xicclu and forward_xicclu:
                #     backward_xicclu((X, Y, Z))
                # else:
                #     HDR_XYZ[row] = (X, Y, Z)
                #     row += 1
                #     perc = startperc + math.floor(row / clutres ** 3.0 *
                #     (90 - startperc))
                # if logfile and perc > prevperc:
                #     logfile.write(f"\r{perc:.0f}%")
                # prevperc = perc
                # startperc = perc

                # if backward_xicclu and forward_xicclu:
                # # Get XYZ clipped to display RGB
                # backward_xicclu.exit()
                # for R, G, B in backward_xicclu.get():
                # forward_xicclu((R, G, B))
                # forward_xicclu.exit()
                # display_XYZ = forward_xicclu.get()
                # else:
                # display_XYZ = HDR_XYZ
                # row = 0
                # for a in range(clutres):
                # for b in range(clutres):
                # itable.clut.append([])
                # debugtable0.clut.append([])
                # for c in range(clutres):
                # if worker and worker.thread_abort:
                # if forward_xicclu:
                # forward_xicclu.exit()
                # if backward_xicclu:
                # backward_xicclu.exit()
                # raise Exception("aborted")
                # X, Y, Z = display_XYZ[row]
                itable.clut[-1].append(
                    [min(max(v * 32768, 0), 65535) for v in (X, Y, Z)]
                )
                debugtable0.clut[-1].append(
                    [min(max(v * 65535, 0), 65535) for v in (R, G, B)]
                )
                if not display_RGB:
                    debugtable1.clut[-1].append([0, 0, 0])
                if display_XYZ:
                    XYZdisp = display_XYZ[row]
                else:
                    XYZdisp = [0, 0, 0]
                debugtable2.clut[-1].append(
                    [min(max(v * 65535, 0), 65535) for v in XYZdisp]
                )
                row += 1
                perc = startperc + math.floor(row / clutres**3.0 * (100 - startperc))
                if logfile and perc > prevperc:
                    logfile.write(f"\r{perc:.0f}%")
                    prevperc = perc
    prevperc = startperc = perc = 0

    if DEBUG:
        print("Num OOG:", oog_count)

    if generate_B2A:
        if logfile:
            logfile.write("\rGenerating PCS-to-device table...\n")

        otable.clut = []
        count = 0
        for R in range(clutres):
            for G in range(clutres):
                otable.clut.append([])
                for B in range(clutres):
                    RGB = [v * step for v in (R, G, B)]
                    X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space, eotf=eotf)
                    if hdr_format == "PQ":
                        I1, Ct1, Cp1 = colormath.XYZ2ICtCp(X, Y, Z)
                        I2 = eetf(I1)
                        Ct2, Cp2 = (min(I1 / I2, I2 / I1) * v for v in (Ct1, Cp1))
                        RGB = colormath.ICtCp2RGB(I1, Ct2, Cp2, rgb_space)
                    else:
                        RGB = hlg.XYZ2RGB(X, Y, Z)
                    if (
                        max(X, Y, Z) * 32768 > 65535
                        or min(X, Y, Z) < 0
                        or round(Y, 6) > 1
                        or max(RGB) > 1
                        or min(RGB) < 0
                    ):
                        print(
                            f"#{count:d}",
                            "RGB {:.3f} {:.3f} {:.3f}".format(*RGB),
                            f"XYZ {X:.6f} {Y:.6f} {Z:.6f}",
                            "not in range [0,1]",
                        )
                    otable.clut[-1].append([min(max(v, 0), 1) * 65535 for v in RGB])
                    count += 1

    if logfile:
        logfile.write("\n")

    if forward_xicclu:
        forward_xicclu.exit()
    if backward_xicclu:
        backward_xicclu.exit()

    if hdr_format == "HLG" and black_cdm2:
        # Apply black offset
        XYZbp = colormath.get_whitepoint(scale=black_cdm2 / float(white_cdm2))
        if logfile:
            logfile.write("Applying black offset...\n")
        profile.tags.A2B0.apply_black_offset(
            XYZbp, logfile=logfile, thread_abort=worker and worker.thread_abort
        )

    return profile


def create_synthetic_hlg_clut_profile(
    rgb_space,
    description,
    black_cdm2=0,
    white_cdm2=400,
    system_gamma=1.2,
    ambient_cdm2=5,
    maxsignal=1.0,
    content_rgb_space="DCI P3",
    rolloff=True,
    clutres=33,
    mode="HSV_ICtCp",
    forward_xicclu=None,
    backward_xicclu=None,
    generate_B2A=True,
    worker=None,
    logfile=None,
    cat="Bradford",
):
    """Create a synthetic cLUT profile with the HLG TRC from a colorspace
    definition

    mode:  The gamut mapping mode when rolling off. Valid values:
           "RGB_ICtCp" (default, recommended)
           "ICtCp"
           "XYZ" (not recommended, unpleasing hue shift)
           "HSV" (not recommended, saturation loss)
           "RGB" (not recommended, saturation loss, pleasing hue shift)

    """

    if not rolloff:
        raise NotImplementedError("rolloff needs to be True")

    return create_synthetic_hdr_clut_profile(
        "HLG",
        rgb_space,
        description,
        black_cdm2,
        white_cdm2,
        0,  # Not used for HLG
        10000,  # Not used for HLG
        True,  # Not used for HLG
        system_gamma,
        ambient_cdm2,
        maxsignal,
        content_rgb_space,
        clutres,
        mode,  # Not used for HLG
        1.0,  # Sat - Not used for HLG
        0.5,  # Hue - Not used for HLG
        forward_xicclu,
        backward_xicclu,
        generate_B2A,
        worker,
        logfile,
        cat,
    )


def _colord_get_display_profile(display_no=0, path_only=False, use_cache=True):
    """Use a brute force way of getting display profile."""
    edid_ = get_edid(display_no)
    device_ids = []
    if edid_:
        # Try a range of possible device IDs
        dife = colord.device_id_from_edid
        device_ids = [
            dife(edid_, quirk=False, query=True),
            dife(edid_, quirk=True, truncate_edid_strings=True),
            dife(edid_, quirk=True, use_serial_32=False),
            dife(edid_, quirk=True, use_serial_32=False, truncate_edid_strings=True),
            dife(edid_, quirk=True),
            dife(edid_, quirk=False, truncate_edid_strings=True),
            dife(edid_, quirk=False, use_serial_32=False),
            dife(edid_, quirk=False, use_serial_32=False, truncate_edid_strings=True),
            # Try with manufacturer omitted
            dife(edid_, omit_manufacturer=True),
            dife(edid_, truncate_edid_strings=True, omit_manufacturer=True),
            dife(edid_, use_serial_32=False, omit_manufacturer=True),
            dife(
                edid_,
                use_serial_32=False,
                truncate_edid_strings=True,
                omit_manufacturer=True,
            ),
        ]
    else:
        # Fall back to XrandR name
        try:
            from DisplayCAL import RealDisplaySizeMM as RDSMM
        except ImportError as exception:
            warnings.warn(str(exception), Warning)
            return
        display = RDSMM.get_display(display_no)
        if display:
            xrandr_name = display.get("xrandr_name")
            if xrandr_name:
                edid_ = {"monitor_name": xrandr_name}
                device_ids = [f"xrandr-{xrandr_name.decode()}"]
            elif os.getenv("XDG_SESSION_TYPE") == "wayland":
                # Preliminary Wayland support under non-GNOME desktops.
                # This still needs a lot of work.
                device_ids = colord.get_display_device_ids()
                if device_ids and display_no < len(device_ids):
                    edid_ = {
                        "monitor_name": device_ids[display_no].split("xrandr-", 1).pop()
                    }
                    device_ids = [device_ids[display_no]]
    if edid_:
        for device_id in dict.fromkeys(device_ids).keys():
            if device_id:
                try:
                    profile = colord.get_default_profile(device_id)
                    profile_path = profile.properties.get("Filename")
                except colord.CDObjectQueryError:
                    # Device ID was not found, try next one
                    continue
                except colord.CDError as exception:
                    warnings.warn(str(exception), Warning)
                except colord.DBusException as exception:
                    warnings.warn(str(exception), Warning)
                else:
                    if profile_path:
                        if "hash" in edid_:
                            colord.device_ids[edid_["hash"]] = device_id
                        if path_only:
                            print(
                                "Got profile from colord for display "
                                f"{int(display_no):d} ({device_id}):",
                                profile_path,
                            )
                            return profile_path
                        return ICCProfile(profile_path, use_cache=use_cache)
                break


def _ucmm_get_display_profile(display_no, name, path_only=False, use_cache=True):
    """Argyll UCMM."""
    search = []
    edid = get_edid(display_no)
    if edid:
        # Look for matching EDID entry first
        search.append((b"EDID", b"0x" + binascii.hexlify(edid["edid"]).upper()))
    # Fallback to X11 name
    search.append((b"NAME", name))
    for path in [xdg_config_home] + xdg_config_dirs:
        color_jcnf = os.path.join(path, "color.jcnf")
        if not os.path.isfile(color_jcnf):
            continue

        with open(color_jcnf) as f:
            data = json.load(f)
        displays = data.get("devices", {}).get("display")
        if not isinstance(displays, dict):
            continue

        # Look for matching entry
        for key, value in search:
            for item in displays.values():
                if not isinstance(item, dict):
                    continue
                if item.get(key) != value:
                    continue
                profile_path = item.get("ICC_PROFILE")
                if path_only:
                    print(
                        "Got profile from Argyll UCMM for display "
                        f"{int(display_no):d} ({key} {value}):",
                        profile_path,
                    )
                    return profile_path
                return ICCProfile(profile_path, use_cache=use_cache)


def _wcs_get_display_profile(
    devicekey,
    scope=WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
    profile_type=COLOR_PROFILE_TYPE["ICC"],
    profile_subtype=COLOR_PROFILE_SUBTYPE["NONE"],
    profile_id=0,
    path_only=False,
    use_cache=True,
):
    buf = ctypes.create_unicode_buffer(256)
    _win10_1903_take_process_handles_snapshot()
    retv = mscms.WcsGetDefaultColorProfile(
        scope,
        devicekey,
        profile_type,
        profile_subtype,
        profile_id,
        ctypes.sizeof(buf),  # Bytes
        ctypes.byref(buf),
    )
    _win10_1903_close_leaked_regkey_handles(devicekey)
    if not retv:
        raise util_win.get_windows_error(ctypes.windll.kernel32.GetLastError())
    if buf.value:
        if path_only:
            return os.path.join(iccprofiles[0], buf.value)
        return ICCProfile(buf.value, use_cache=use_cache)


def _win10_1903_take_process_handles_snapshot():
    global prev_handles
    prev_handles = []
    if win10_1903 and DEBUG:
        try:
            for handle in get_process_handles():
                prev_handles.append(handle.HandleValue)
        except WindowsError as exception:
            print("Couldn't get process handles:", exception)


def _win10_1903_close_leaked_regkey_handles(devicekey):
    global prev_handles
    if not win10_1903:
        return
    # Wcs* methods leak handles under Win10 1903. Get and close them.

    # Extract substring from devicekey for matching handle name, e.g.
    # Control\Class\{4d36e96e-e325-11ce-bfc1-08002be10318}
    substr = "\\".join(devicekey.split("\\")[-4:-1])
    try:
        handles = get_process_handles()
    except WindowsError as exception:
        print("Couldn't get process handles:", exception)
        return
    for handle in handles:
        try:
            handle_name = get_handle_name(handle)
        except WindowsError as exception:
            print(f"Couldn't get name of handle 0x{handle.HandleValue:x}:", exception)
            handle_name = None
        if DEBUG and handle.HandleValue not in prev_handles:
            try:
                handle_type = get_handle_type(handle)
            except WindowsError as exception:
                print(
                    f"Couldn't get typestring of handle 0x{handle.HandleValue:x}:",
                    exception,
                )
                handle_type = None
            print(
                "New handle",
                f"0x{handle.HandleValue:x}",
                f"type 0x{handle.ObjectTypeIndex:02x} {handle_type}",
                handle_name,
            )
        if handle_name and handle_name.endswith(substr):
            print(
                "Windows 10",
                win_ver[2].split(" ", 1)[-1],
                f"housekeeping: Closing leaked handle 0x{handle.HandleValue:x}",
                handle_name,
            )
            try:
                win32api.RegCloseKey(handle.HandleValue)
            except pywintypes.error as exception:
                print(f"Couldn't close handle 0x{handle.HandleValue:x}:", exception)


def _winreg_get_display_profile(
    monkey, current_user=False, path_only=False, use_cache=True
):
    filename = None
    filenames = _winreg_get_display_profiles(monkey, current_user)
    if filenames:
        # last existing file in the list is active
        filename = filenames.pop()
    if not filename and not current_user:
        # fall back to sRGB
        filename = os.path.join(iccprofiles[0], "sRGB Color Space Profile.icm")
    if filename:
        if path_only:
            return os.path.join(iccprofiles[0], filename)
        return ICCProfile(filename, use_cache=use_cache)
    return None


def _winreg_get_display_profiles(monkey, current_user=False):
    filenames = []
    try:
        if current_user and sys.getwindowsversion() >= (6,):
            # Vista / Windows 7 ONLY
            # User has to place a check in 'use my settings for this device'
            # in the color management control panel at least once to cause
            # this key to be created, otherwise it won't exist
            subkey = "\\".join(
                [
                    "Software",
                    "Microsoft",
                    "Windows NT",
                    "CurrentVersion",
                    "ICM",
                    "ProfileAssociations",
                    "Display",
                ]
                + monkey
            )
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
        else:
            subkey = "\\".join(
                ["SYSTEM", "CurrentControlSet", "Control", "Class"] + monkey
            )
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
        numsubkeys, numvalues, mtime = winreg.QueryInfoKey(key)
        for i in range(numvalues):
            name, value, type_ = winreg.EnumValue(key, i)
            if name not in ["ICMProfile", "ICMProfileAC"] or not value:
                continue

            if type_ == winreg.REG_BINARY:
                # Win2k/XP
                # convert to list of strings
                value = value.decode("utf-16").split("\0")
            elif type_ == winreg.REG_MULTI_SZ:
                # Vista / Windows 7
                # nothing to be done, _winreg returns a list of strings
                pass
            if not isinstance(value, list):
                value = [value]
            while "" in value:
                value.remove("")
            filenames.extend(value)
        winreg.CloseKey(key)
    except WindowsError as exception:
        if exception.args[0] == 2:
            # Key does not exist
            pass
        else:
            raise
    return [
        filename
        for filename in filenames
        if os.path.isfile(os.path.join(iccprofiles[0], filename))
    ]


def get_display_profile(
    display_no=0,
    x_hostname=None,
    x_display=None,
    x_screen=None,
    path_only=False,
    devicekey=None,
    use_active_display_device=True,
    use_registry=True,
):
    """Return ICC Profile for display n or None."""
    if sys.platform == "win32":
        return get_display_profile_windows(
            display_no, path_only, devicekey, use_active_display_device, use_registry
        )
    elif sys.platform == "darwin":
        return get_display_profile_macos(display_no, path_only)
    else:
        return get_display_profile_linux(
            display_no, x_hostname, x_display, x_screen, path_only
        )


def get_display_profile_windows(
    display_no=0,
    path_only=False,
    devicekey=None,
    use_active_display_device=True,
    use_registry=True,
):
    """Return ICC Profile for the given display under Windows."""
    profile = None
    if "win32api" not in sys.modules:
        raise ImportError("pywin32 not available")
    if not devicekey:
        # The ordering will work as long as Argyll continues using
        # EnumDisplayMonitors
        monitors = util_win.get_real_display_devices_info()
        moninfo = monitors[display_no]
    if not mscms and not devicekey:
        # Via GetICMProfile. Sucks royally in a multi-monitor setup
        # where one monitor is disabled, because it'll always get
        # the profile of the first monitor regardless if that is the active
        # one or not. Yuck. Also, in this case it does not reflect runtime
        # changes to profile assignments. Double yuck.
        buflen = ctypes.c_ulong(260)
        dc = win32gui.CreateDC(moninfo["Device"], None, None)
        try:
            buf = ctypes.create_unicode_buffer(buflen.value)
            if ctypes.windll.gdi32.GetICMProfileW(
                dc,
                ctypes.byref(buflen),
                ctypes.byref(buf),  # WCHARs
            ):
                if path_only:
                    profile = buf.value
                else:
                    profile = ICCProfile(buf.value, use_cache=True)
        finally:
            win32gui.DeleteDC(dc)
    else:
        if devicekey:
            device = None
        elif use_active_display_device:
            # This would be the correct way. Unfortunately that is not
            # what other apps (or Windows itself) do.
            device = util_win.get_active_display_device(moninfo["Device"])
        else:
            # This is wrong, but it's what other apps use. Matches
            # GetICMProfile sucky behavior i.e. should return the same
            # profile, but atleast reflects runtime changes to profile
            # assignments.
            device = util_win.get_first_display_device(moninfo["Device"])
        if device:
            devicekey = device.DeviceKey
    if devicekey:
        if mscms:
            # Via WCS
            if util_win.per_user_profiles_isenabled(devicekey=devicekey):
                scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
            else:
                scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
            if not use_registry:
                # NOTE: WcsGetDefaultColorProfile causes the whole system
                # to hitch if the profile of the active display device is
                # queried. Windows bug?
                return _wcs_get_display_profile(
                    str(devicekey), scope, path_only=path_only
                )
        else:
            scope = None
            # Via registry
        monkey = devicekey.split("\\")[-2:]  # pun totally intended
        # Current user scope
        current_user = scope == WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        if current_user:
            profile = _winreg_get_display_profile(monkey, True, path_only=path_only)
        else:
            # System scope
            profile = _winreg_get_display_profile(monkey, path_only=path_only)

    return profile


def get_display_profile_macos(display_no=0, path_only=False):
    """Return ICC Profile for the given display under macOS."""
    from platform import mac_ver
    from DisplayCAL.util_mac import osascript

    if intlist(mac_ver()[0].split(".")) >= [10, 6]:
        options = ["Image Events"]
    else:
        options = ["ColorSyncScripting"]

    for option in options:
        # applescript: one-based index
        applescript = [
            f'tell app "{option}"',
            "set displayProfile to location of display profile of "
            f"display {int(display_no + 1):d}",
            "return POSIX path of displayProfile",
            "end tell",
        ]
        retcode, output, errors = osascript(applescript)
        if retcode == 0 and output.strip():
            filename = output.strip("\n").decode(FS_ENC)
            if path_only:
                profile = filename
            else:
                profile = ICCProfile(filename, use_cache=True)
        elif errors.strip():
            raise IOError(errors.strip())

    return profile


def get_display_profile_linux(
    display_no=0,
    x_hostname=None,
    x_display=None,
    x_screen=None,
    path_only=False,
):
    """Return ICC Profile for the given display under Linux."""
    options = ["_ICC_PROFILE"]
    try:
        from DisplayCAL import RealDisplaySizeMM as RDSMM
    except ImportError as exception:
        warnings.warn(str(exception), Warning)
        display = get_display()
    else:
        display = RDSMM.get_x_display(display_no)
    if display:
        if x_hostname is None:
            x_hostname = display[0]
        if x_display is None:
            x_display = display[1]
        if x_screen is None:
            x_screen = display[2]
        x_display_name = f"{x_hostname}:{x_display}.{x_screen}"
    for option in options:
        # Linux
        # Try colord
        if colord.which("colormgr") and (
            profile := (_colord_get_display_profile(display_no, path_only=path_only))
        ):
            return profile
        if path_only:
            # No way to figure out the profile path from X atom, so use
            # Argyll's UCMM if libcolordcompat.so is not present
            if dlopen("libcolordcompat.so"):
                # UCMM configuration might be stale, ignore
                return
            profile = _ucmm_get_display_profile(display_no, x_display_name, path_only)
            return profile
            # Try XrandR
        if (
            xrandr
            and RDSMM
            and option == "_ICC_PROFILE"
            and None not in (x_hostname, x_display, x_screen)
        ):
            with xrandr.XDisplay(x_display_name) as display:
                if DEBUG:
                    print("Using XrandR")
                for i, atom_id in enumerate(
                    [
                        RDSMM.get_x_icc_profile_output_atom_id(display_no),
                        RDSMM.get_x_icc_profile_atom_id(display_no),
                    ]
                ):
                    if not atom_id:
                        continue
                    if i == 0:
                        meth = display.get_output_property
                        what = RDSMM.GetXRandROutputXID(display_no)
                    else:
                        meth = display.get_window_property
                        what = display.root_window(0)
                    try:
                        property = meth(what, atom_id)
                    except ValueError as exception:
                        warnings.warn(str(exception), Warning)
                    else:
                        if property and (
                            profile := ICCProfile(
                                b"".join(bytes(chr(n), "UTF-8") for n in property),
                                use_cache=True,
                            )
                        ):
                            return profile
                    if DEBUG:
                        if i == 0:
                            print("Couldn't get _ICC_PROFILE XrandR output property")
                            print("Using X11")
                        else:
                            print("Couldn't get _ICC_PROFILE X atom")
            return

        # Read up to 8 MB of any X properties
        if DEBUG:
            print("Using xprop")
        xprop = which("xprop")
        if not xprop:
            return
        atom = "{}{}".format(option, "" if display_no == 0 else f"_{display_no}")
        tgt_proc = sp.Popen(
            [
                xprop,
                "-display",
                f"{x_hostname}:{x_display}.{x_screen}",
                "-len",
                "8388608",
                "-root",
                "-notype",
                atom,
            ],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        stdout, stderr = [data.strip(b"\n") for data in tgt_proc.communicate()]
        if stdout:
            raw = [item.strip() for item in stdout.split("=")]
            if raw[0] == atom and len(raw) == 2:
                bin = "".join([chr(int(part)) for part in raw[1].split(", ")])
                profile = ICCProfile(bin, use_cache=True)
        elif stderr and tgt_proc.wait() != 0:
            raise IOError(stderr)
        if profile:
            break
    return profile


def _wcs_set_display_profile(
    devicekey, profile_name, scope=WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
):
    """Set the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.

    * 0..65535 will get mapped to 0..65280, which is a Windows bug

    """
    # We need to disassociate the profile first in case it's not the default
    # so we can make it the default again.
    # Note that disassociating the current default profile for a display will
    # also set its video card gamma ramps to linear if Windows calibration
    # management isn't enabled.
    _win10_1903_take_process_handles_snapshot()
    with contextlib.suppress(WindowsError):
        # Disassociate the profile from the device first
        mscms.WcsDisassociateColorProfileFromDevice(scope, profile_name, devicekey)
    try:
        # Associate the profile with the device
        retv = mscms.WcsAssociateColorProfileWithDevice(scope, profile_name, devicekey)
    except WindowsError:
        retv = None
    _win10_1903_close_leaked_regkey_handles(devicekey)
    if not retv:
        raise util_win.get_windows_error(ctypes.windll.kernel32.GetLastError())
    monkey = devicekey.split("\\")[-2:]
    current_user = scope == WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
    profiles = _winreg_get_display_profiles(monkey, current_user)
    if profile_name not in profiles:
        return False
    return True


def _wcs_unset_display_profile(
    devicekey, profile_name, scope=WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
):
    """Unset the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.

    * 0..65535 will get mapped to 0..65280, which is a Windows bug

    """
    # Disassociating a profile will always (regardless of whether or
    # not the profile was associated or even exists) result in Windows
    # error code 2015 ERROR_PROFILE_NOT_ASSOCIATED_WITH_DEVICE.
    # This is probably a Windows bug.
    # To have a meaningful return value, we thus check wether the profile that
    # should be removed is currently associated, and only fail if it is not,
    # or if disassociating it fails for some reason.
    monkey = devicekey.split("\\")[-2:]
    current_user = scope == WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
    profiles = _winreg_get_display_profiles(monkey, current_user)
    _win10_1903_take_process_handles_snapshot()
    try:
        # Disassociate the profile from the device
        retv = mscms.WcsDisassociateColorProfileFromDevice(scope, profile_name, devicekey)
    except WindowsError:
        retv = None
    _win10_1903_close_leaked_regkey_handles(devicekey)
    if not retv:
        errcode = ctypes.windll.kernel32.GetLastError()
        if (
            errcode in (ERROR_PROFILE_NOT_ASSOCIATED_WITH_DEVICE, ERROR_SUCCESS)
            and profile_name in profiles
        ):
            # Check if profile is still associated
            profiles = _winreg_get_display_profiles(monkey, current_user)
            if profile_name not in profiles:
                # Successfully disassociated
                return True
        raise util_win.get_windows_error(errcode)
    return True


def set_display_profile(
    profile_name, display_no=0, devicekey=None, use_active_display_device=True
):
    # Currently only implemented for Windows.
    # The profile to be assigned has to be already installed!
    if not devicekey:
        device = util_win.get_display_device(display_no, use_active_display_device)
        if not device:
            return False
        devicekey = device.DeviceKey
    if mscms:
        if util_win.per_user_profiles_isenabled(devicekey=devicekey):
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        else:
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
        return _wcs_set_display_profile(str(devicekey), profile_name, scope)
    else:
        # TODO: Implement for XP
        return False


def unset_display_profile(
    profile_name, display_no=0, devicekey=None, use_active_display_device=True
):
    # Currently only implemented for Windows.
    # The profile to be unassigned has to be already installed!
    if not devicekey:
        device = util_win.get_display_device(display_no, use_active_display_device)
        if not device:
            return False
        devicekey = device.DeviceKey
    if mscms:
        if util_win.per_user_profiles_isenabled(devicekey=devicekey):
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        else:
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
        return _wcs_unset_display_profile(str(devicekey), profile_name, scope)
    else:
        # TODO: Implement for XP
        return False


def _blend_blackpoint(row, bp_in, bp_out, wp=None, use_bpc=False, weight=False):
    X, Y, Z = row
    if use_bpc:
        X, Y, Z = colormath.apply_bpc(X, Y, Z, bp_in, bp_out, wp, weight=weight)
    else:
        X, Y, Z = colormath.blend_blackpoint(X, Y, Z, bp_in, bp_out, wp)
    return X, Y, Z


def _mp_apply(
    blocks,
    thread_abort_event,
    progress_queue,
    pcs,
    fn,
    args,
    D50,
    interp,
    rinterp,
    abortmessage="Aborted",
):
    """Worker for applying function to cLUT

    This should be spawned as a multiprocessing process

    """
    from DisplayCAL.debughelpers import Info

    for interp_tuple in (interp, rinterp):
        if interp_tuple:
            # Use numpy for speed
            interp_list = list(interp_tuple)
            for i, ointerp in enumerate(interp_list):
                interp_list[i] = colormath.Interp(
                    ointerp.xp, ointerp.fp, use_numpy=True
                )
                interp_list[i].lookup = ointerp.lookup
            if interp_tuple is interp:
                interp = interp_list
            else:
                rinterp = interp_list
    prevperc = 0
    count = 0
    numblocks = len(blocks)
    for block in blocks:
        if thread_abort_event and thread_abort_event.is_set():
            return Info(abortmessage)
        for i, row in enumerate(block):
            if interp:
                for column, value in enumerate(row):
                    row[column] = interp[column](value)
            if pcs == "Lab":
                L, a, b = legacy_PCSLab_uInt16_to_dec(*row)
                X, Y, Z = colormath.Lab2XYZ(L, a, b, D50)
            else:
                X, Y, Z = [v / 32768.0 for v in row]
            X, Y, Z = fn((X, Y, Z), *args)
            if pcs == "Lab":
                L, a, b = colormath.XYZ2Lab(X, Y, Z, D50)
                row = [
                    min(max(0, v), 65535) for v in legacy_PCSLab_dec_to_uInt16(L, a, b)
                ]
            else:
                row = [min(max(0, v) * 32768.0, 65535) for v in (X, Y, Z)]
            if rinterp:
                for column, value in enumerate(row):
                    row[column] = rinterp[column](value)
            block[i] = row
        count += 1.0
        perc = round(count / numblocks * 100)
        if progress_queue and perc > prevperc:
            progress_queue.put(perc - prevperc)
            prevperc = perc
    return blocks


def _mp_apply_black(
    blocks,
    thread_abort_event,
    progress_queue,
    pcs,
    bp,
    bp_out,
    wp,
    use_bpc,
    weight,
    D50,
    interp,
    rinterp,
    abortmessage="Aborted",
):
    """Worker for applying black point compensation or offset

    This should be spawned as a multiprocessing process

    """
    return _mp_apply(
        blocks,
        thread_abort_event,
        progress_queue,
        pcs,
        _blend_blackpoint,
        (bp, bp_out, wp if use_bpc else None, use_bpc, weight),
        D50,
        interp,
        rinterp,
        abortmessage,
    )


def _mp_hdr_tonemap(
    HDR_XYZ, thread_abort_event, progress_queue, rgb_space, maxv, sat, cat="Bradford"
):
    """Worker for HDR tonemapping

    This should be spawned as a multiprocessing process

    """
    prevperc = 0
    amount = len(HDR_XYZ)
    dI = 0
    dI_max = 0
    dC = 0
    dC_max = 0
    I_reduced_count = 0
    its_hi = 0  # Highest number pf iterations seen per color
    for i, (RGB_in, ICtCp_XYZ, RGB_ICtCp_XYZ) in enumerate(HDR_XYZ):
        if thread_abort_event and thread_abort_event.is_set():
            return [False]
        is_neutral = all(v == RGB_in[0] for v in RGB_in)
        for j, XYZ in enumerate((ICtCp_XYZ, RGB_ICtCp_XYZ)):
            if j == 0 and (sat == 1 or ICtCp_XYZ == RGB_ICtCp_XYZ):
                # Set ICtCp_XYZ to the same object as RGB_ICtCp_XYZ which we
                # are going to change in-place in the next iteration of the loop
                # so that at the end of this loop, both will point to the same
                # changed data
                ICtCp_XYZ = RGB_ICtCp_XYZ
                continue
            X, Y, Z = XYZ
            H = None
            its = 10000  # Remaining iterations (limit)
            while not is_neutral and its:
                X_D50, Y_D50, Z_D50 = colormath.adapt(
                    *(v / maxv for v in (X, Y, Z)),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                negative_clip = min(X_D50, Y_D50, Z_D50) < 0
                positive_clip = (
                    round(X_D50, 4) > 0.9642 or Y_D50 > 1 or round(Z_D50, 4) > 0.8249
                )
                if not (negative_clip or positive_clip):
                    break
                if H is None:
                    # Record hue angle
                    H = colormath.RGB2HSV(*RGB_in)[0]
                    # This is the initial intensity, and hue + saturation
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)
                    Io = I
                    Co = colormath.Lab2LCHab(I, Ct, Cp)[1]
                # Desaturate
                Ct *= 0.99
                Cp *= 0.99
                # Update XYZ
                X, Y, Z = colormath.ICtCp2XYZ(I, Ct, Cp)
                if Y > XYZ[1]:
                    # Desaturating CtCp increases Y!
                    # As we desaturate different amounts per color,
                    # restore initial Y if lower than adjusted Y
                    # to keep luminance relation
                    X, Y, Z = (v / Y * XYZ[1] for v in (X, Y, Z))
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)
                its -= 1
            if H is not None and round(Io - I, 4):
                # Intensity was reduced by >= 0.0001, gather statistics
                C = colormath.Lab2LCHab(I, Ct, Cp)[1]
                dI += Io - I
                dI_max = max(dI_max, Io - I)
                dC += Co - C
                dC_max = max(dC_max, Co - C)
                I_reduced_count += 1
            if not its:
                # Max iterations exceeded, print diagnostics
                # XXX: This should not happen (testing OK)
                oX_D50, oY_D50, oZ_D50 = colormath.adapt(
                    *(v / maxv for v in XYZ), whitepoint_source=rgb_space[1], cat=cat
                )
                X_D50, Y_D50, Z_D50 = colormath.adapt(
                    *(v / maxv for v in (X, Y, Z)),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                print(
                    "Reached iteration limit, XYZ "
                    f"{oX_D50:.4f} {oY_D50:.4f} {oZ_D50:.4f} -> "
                    f"{X_D50:.4f} {Y_D50:.4f} {Z_D50:.4f}"
                )
            its_hi = max(its_hi, 10000 - its)
            XYZ[:] = X, Y, Z
        HDR_XYZ[i] = (RGB_in, ICtCp_XYZ, RGB_ICtCp_XYZ)
        perc = round((i + 1.0) / amount * 50)
        if progress_queue and perc > prevperc:
            progress_queue.put(perc - prevperc)
            prevperc = perc
    if I_reduced_count:
        # Intensity was reduced, print informational statistics
        print(
            f"Max iterations {int(its_hi):d} "
            f"dI avg {dI / I_reduced_count:.4f} "
            f"max {dI_max:.4f} "
            f"dC avg {dC / I_reduced_count:.4f} "
            f"max {dC_max:.4f}"
        )
    elif its_hi:
        print("Max iterations", its_hi)
    return HDR_XYZ


def hexrepr(bytestring, mapping=None):
    """Generates hex representation of a bytes instance

    :param bytestring:
    :param mapping:
    :return:
    """
    hex_repr = (b"0x%s" % binascii.hexlify(bytestring).upper()).decode()
    ascii_repr = re.sub(b"[^\x20-\x7e]", b"", bytestring)
    if ascii_repr == bytestring:
        hex_repr += f" '{ascii_repr.decode()}'"
        if mapping:
            value = mapping.get(ascii_repr)
            if value:
                hex_repr = f"{hex_repr} {value}"
    return hex_repr


def dateTimeNumber(binary_string):
    """Byte
    Offset Content                                     Encoded as...
    0..1   number of the year (actual year, e.g. 1994) uInt16Number
    2..3   number of the month (1-12)                  uInt16Number
    4..5   number of the day of the month (1-31)       uInt16Number
    6..7   number of hours (0-23)                      uInt16Number
    8..9   number of minutes (0-59)                    uInt16Number
    10..11 number of seconds (0-59)                    uInt16Number

    :param binary_string: A 12 character long bytes value representing a datetime value.
    """
    Y, m, d, H, M, S = [
        uInt16Number(chunk)
        for chunk in (
            binary_string[:2],
            binary_string[2:4],
            binary_string[4:6],
            binary_string[6:8],
            binary_string[8:10],
            binary_string[10:12],
        )
    ]
    return datetime.datetime(*(Y, m, d, H, M, S))


def dateTimeNumber_tohex(dt):
    data = [uInt16Number_tohex(n) for n in dt.timetuple()[:6]]
    return b"".join(data)


def s15Fixed16Number(binaryString):
    return struct.unpack(">i", binaryString)[0] / 65536.0


def s15Fixed16Number_tohex(num):
    return struct.pack(">i", int(round(num * 65536)))


def s15f16_is_equal(
    a, b, quantizer=lambda v: s15Fixed16Number(s15Fixed16Number_tohex(v))
):
    return colormath.is_equal(a, b, quantizer)


def u16Fixed16Number(binaryString):
    return struct.unpack(">I", binaryString)[0] / 65536.0


def u16Fixed16Number_tohex(num):
    return struct.pack(">I", int(round(num * 65536)) & 0xFFFFFFFF)


def u8Fixed8Number(binaryString):
    return struct.unpack(">H", binaryString)[0] / 256.0


def u8Fixed8Number_tohex(num):
    return struct.pack(">H", int(round(num * 256)))


def uInt16Number(binaryString):
    return struct.unpack(">H", binaryString)[0]


def uInt16Number_tohex(num):
    return struct.pack(">H", int(round(num)))


def uInt32Number(binaryString):
    return struct.unpack(">I", binaryString)[0]


def uInt32Number_tohex(num):
    try:
        return struct.pack(">I", int(round(num)))
    except struct.error as e:
        print("num: {}".format(num))
        raise e


def uInt64Number(binaryString):
    return struct.unpack(">Q", binaryString)[0]


def uInt64Number_tohex(num):
    return struct.pack(">Q", int(round(num)))


def uInt8Number(binaryString):
    return struct.unpack(">H", b"\0" + binaryString)[0]


def uInt8Number_tohex(num):
    return struct.pack(">H", int(round(num)))[1:2]


def videoCardGamma(tagData, tagSignature):
    # reserved = uInt32Number(tagData[4:8])
    tagType = uInt32Number(tagData[8:12])
    if tagType == 0:  # table
        return VideoCardGammaTableType(tagData, tagSignature)
    elif tagType == 1:  # formula
        return VideoCardGammaFormulaType(tagData, tagSignature)


class CRInterpolation:
    """Catmull-Rom interpolation.
    Curve passes through the points exactly, with neighbouring points influencing curvature.
    points[] should be at least 3 points long.
    """

    def __init__(self, points):
        self.points = points

    def __call__(self, pos):
        lbound = int(math.floor(pos) - 1)
        ubound = int(math.ceil(pos) + 1)
        t = pos % 1.0
        if abs((lbound + 1) - pos) < 0.0001:
            # sitting on a datapoint, so just return that
            return self.points[lbound + 1]
        if lbound < 0:
            p = self.points[: ubound + 1]
            # extend to the left linearly
            while len(p) < 4:
                p.insert(0, p[0] - (p[1] - p[0]))
        else:
            p = self.points[lbound : ubound + 1]
            # extend to the right linearly
            while len(p) < 4:
                p.append(p[-1] - (p[-2] - p[-1]))
        t2 = t * t
        return 0.5 * (
            (2 * p[1])
            + (-p[0] + p[2]) * t
            + ((2 * p[0]) - (5 * p[1]) + (4 * p[2]) - p[3]) * t2
            + (-p[0] + (3 * p[1]) - (3 * p[2]) + p[3]) * (t2 * t)
        )


class ADict(dict):
    """Convenience class for dictionary key access via attributes.

    Instead of writing aodict[key], you can also write aodict.key
    """

    def __init__(self, *args, **kwargs):
        super(ADict, self).__init__(*args, **kwargs)

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            return self.__getattribute__(name)

    def __setattr__(self, name, value):
        self[name] = value


class AODict(ADict):
    def __init__(self, *args, **kwargs):
        super(AODict, self).__init__(*args, **kwargs)

    def __setattr__(self, name, value):
        if name == "_keys":
            object.__setattr__(self, name, value)
        else:
            self[name] = value


class LazyLoadTagAODict(AODict):
    """Lazy-load (and parse) tag data on access"""

    def __init__(self, profile, *args, **kwargs):
        self.profile = profile
        AODict.__init__(self)

    def __getitem__(self, key):
        tag = AODict.__getitem__(self, key)
        if isinstance(tag, ICCProfileTag):
            # Return already parsed tag
            return tag
        # Load and parse tag data
        tagSignature = key
        typeSignature, tagDataOffset, tagDataSize, tagData = tag
        try:
            if tagSignature in tagSignature2Tag:
                tag = tagSignature2Tag[tagSignature](tagData, tagSignature)
            elif typeSignature in typeSignature2Type:
                args = tagData, tagSignature
                if typeSignature in (b"clrt", b"ncl2"):
                    args += (self.profile.connectionColorSpace,)
                    if typeSignature == b"ncl2":
                        args += (self.profile.colorSpace,)
                elif typeSignature in (b"XYZ ", b"mft2", b"curv", b"MS10", b"pseq"):
                    args += (self.profile,)
                tag = typeSignature2Type[typeSignature](*args)
            else:
                tag = ICCProfileTag(tagData, tagSignature)
        except Exception as exception:
            raise ICCProfileInvalidError(
                f"Couldn't parse tag {repr(tagSignature)} "
                f"(type {repr(typeSignature)}, "
                f"offset {int(tagDataOffset):d}, "
                f"size {int(tagDataSize):d}): {repr(exception)}"
            )
        self[key] = tag
        return tag

    def __setattr__(self, name, value):
        if name == "profile":
            object.__setattr__(self, name, value)
        else:
            AODict.__setattr__(self, name, value)

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default


class ICCProfileTag:
    def __init__(self, tagData, tagSignature):
        self.tagData = tagData
        self.tagSignature = tagSignature

    def __setattr__(self, name, value):
        if not isinstance(self, dict) or name in ("_keys", "tagData", "tagSignature"):
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def __repr__(self):
        """t.__repr__() <==> repr(t)"""
        if isinstance(self, dict):
            return dict.__repr__(self)
        elif isinstance(self, UserString):
            return UserString.__repr__(self)
        elif isinstance(self, list):
            return list.__repr__(self)
        else:
            if not self:
                return "{}.{}()".format(
                    self.__class__.__module__, self.__class__.__name__
                )
            return "{}.{}({})".format(
                self.__class__.__module__,
                self.__class__.__name__,
                repr(self.tagData),
            )


class Text(ICCProfileTag, bytes):
    def __init__(self, seq):
        super(Text, self).__init__(tagData=seq, tagSignature=b"")
        self.data = seq

    def __str__(self):
        return self.data.decode(FS_ENC, errors="replace")


class Colorant:
    def __init__(self, binaryString=b"\0" * 4):
        self._type = uInt32Number(binaryString)
        self._channels = []

    def __getitem__(self, key):
        return self.__getattribute__(key)

    def __iter__(self):
        return iter(list(self.keys()))

    def __repr__(self):
        items = []
        for key, value in (("type", self.type), ("description", self.description)):
            items.append(f"{repr(key)}: {repr(value)}")
        channels = []
        for xy in self.channels:
            channels.append("[{}]".format(", ".join([str(v) for v in xy])))
        items.append("'channels': [{}]".format(", ".join(channels)))
        return "{{{}}}".format(", ".join(items))

    def __setitem__(self, key, value):
        object.__setattr__(self, key, value)

    @property
    def channels(self):
        if not self._channels and self._type and self._type in COLORANTS:
            return [list(xy) for xy in COLORANTS[self._type]["channels"]]
        return self._channels

    @channels.setter
    def channels(self, channels):
        self._channels = channels

    @property
    def description(self):
        return COLORANTS.get(self._type, COLORANTS[0])["description"]

    @description.setter
    def description(self, value):
        pass

    def get(self, key, default=None):
        return getattr(self, key, default)

    def items(self):
        return list(zip(list(self.keys()), list(self.values())))

    def iteritems(self):
        return zip(list(self.keys()), iter(self.values()))

    iterkeys = __iter__

    def itervalues(self):
        return map(self.get, list(self.keys()))

    def keys(self):
        return ["type", "description", "channels"]

    def round(self, digits=4):
        colorant = self.__class__()
        colorant.type = self.type
        for xy in self.channels:
            colorant._channels.append([round(value, digits) for value in xy])
        return colorant

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        if value and value != self._type and value in COLORANTS:
            self._channels = []
        self._type = value

    def update(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError(f"update expected at most 1 arguments, got {len(args):d}")
        for iterable in args + tuple(kwargs.items()):
            if hasattr(iterable, "items"):
                self.update(iter(iterable.items()))
            elif hasattr(iterable, "keys"):
                for key in list(iterable.keys()):
                    self[key] = iterable[key]
            else:
                for key, val in iterable:
                    self[key] = val

    def values(self):
        return list(map(self.get, list(self.keys())))


class Geometry(ADict):
    def __init__(self, binaryString):
        super(Geometry, self).__init__()
        self.type = uInt32Number(binaryString)
        self.description = GEOMETRY[self.type]


class Illuminant(ADict):
    def __init__(self, binaryString):
        super(Illuminant, self).__init__()
        self.type = uInt32Number(binaryString)
        self.description = ILLUMINANTS[self.type]


class LUT16Type(ICCProfileTag):
    def __init__(self, tagData=None, tagSignature=None, profile=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        self._matrix = None
        self._input = None
        self._clut = None
        self._output = None
        self._i = (tagData and uInt8Number(tagData[8:9])) or 0  # Input channel count
        self._o = (tagData and uInt8Number(tagData[9:10])) or 0  # Output channel count
        self._g = (tagData and uInt8Number(tagData[10:11])) or 0  # cLUT grid res
        self._n = (
            tagData and uInt16Number(tagData[48:50])
        ) or 0  # Input channel entries count
        self._m = (
            tagData and uInt16Number(tagData[50:52])
        ) or 0  # Output channel entries count

    def apply_black_offset(
        self, XYZbp, logfile=None, thread_abort=None, abortmessage="Aborted"
    ):
        # Apply only the black point blending portion of BT.1886 mapping
        self._apply_black(XYZbp, False, False, logfile, thread_abort, abortmessage)

    def apply_bpc(
        self,
        bp_out=(0, 0, 0),
        weight=False,
        logfile=None,
        thread_abort=None,
        abortmessage="Aborted",
    ):
        return self._apply_black(
            bp_out, True, weight, logfile, thread_abort, abortmessage
        )

    def _apply_black(
        self,
        bp_out,
        use_bpc=False,
        weight=False,
        logfile=None,
        thread_abort=None,
        abortmessage="Aborted",
    ):
        pcs = self.profile and self.profile.connectionColorSpace
        bp_row = list(self.clut[0][0])
        wp_row = list(self.clut[-1][-1])
        nonzero_bp = tuple(bp_out) != (0, 0, 0)
        interp = []
        rinterp = []
        if not use_bpc or nonzero_bp:
            osize = len(self.output[0])
            omaxv = osize - 1.0
            orange = [i / omaxv * 65535 for i in range(osize)]
            for i in range(3):
                interp.append(colormath.Interp(orange, self.output[i]))
                rinterp.append(colormath.Interp(self.output[i], orange))
            for row in (bp_row, wp_row):
                for column, value in enumerate(row):
                    row[column] = interp[column](value)
        if use_bpc:
            method = "apply_bpc"
        else:
            method = "apply_black_offset"
        if pcs == b"Lab":
            bp = colormath.Lab2XYZ(*legacy_PCSLab_uInt16_to_dec(*bp_row))
            wp = colormath.Lab2XYZ(*legacy_PCSLab_uInt16_to_dec(*wp_row))
        elif not pcs or pcs == b"XYZ":
            if not pcs:
                warnings.warn(
                    f"LUT16Type.{method}: PCS not specified, assuming XYZ", Warning
                )
            bp = [v / 32768.0 for v in bp_row]
            wp = [v / 32768.0 for v in wp_row]
        else:
            raise ValueError(f"LUT16Type.{method}: Unsupported PCS {repr(pcs)}")
        if [round(v * 32768) for v in bp] != [round(v * 32768) for v in bp_out]:
            D50 = colormath.get_whitepoint("D50")

            from DisplayCAL.multiprocess import pool_slice

            if len(self.clut[0]) < 33:
                num_workers = 1
            else:
                num_workers = None

            # if pcs != "Lab" and nonzero_bp:
            # bp_out_offset = bp_out
            # bp_out = (0, 0, 0)

            if bp != bp_out:
                self.clut = sum(
                    pool_slice(
                        _mp_apply_black,
                        self.clut,
                        (
                            pcs,
                            bp,
                            bp_out,
                            wp,
                            use_bpc,
                            weight,
                            D50,
                            interp,
                            rinterp,
                            abortmessage,
                        ),
                        {},
                        num_workers,
                        thread_abort,
                        logfile,
                    ),
                    [],
                )

        # if pcs != "Lab" and nonzero_bp:
        # # Apply black offset to output curves
        # out = [[], [], []]
        # for i in range(2049):
        # v = i / 2048.0
        # X, Y, Z = colormath.blend_blackpoint(v, v, v, (0, 0, 0),
        # bp_out_offset)
        # out[0].append(X * 2048 / 4095.0 * 65535)
        # out[1].append(Y * 2048 / 4095.0 * 65535)
        # out[2].append(Z * 2048 / 4095.0 * 65535)
        # for i in range(2049, 4096):
        # v = i / 4095.0
        # out[0].append(v * 65535)
        # out[1].append(v * 65535)
        # out[2].append(v * 65535)
        # self.output = out

    @property
    def clut(self):
        if self._clut is None:
            i, o, g, n = self._i, self._o, self._g, self._n
            tagData = self._tagData
            self._clut = [
                [
                    [
                        uInt16Number(
                            tagData[
                                52 + n * i * 2 + o * 2 * (g * x + y) + z * 2 : 54
                                + n * i * 2
                                + o * 2 * (g * x + y)
                                + z * 2
                            ]
                        )
                        for z in range(o)
                    ]
                    for y in range(g)
                ]
                for x in range(int(g**i / g))
            ]
        return self._clut

    @clut.setter
    def clut(self, value):
        self._clut = value

    def clut_writepng(self, stream_or_filename):
        """Write the cLUT as PNG image organized in <grid steps> * <grid steps>
        sized squares, ordered vertically"""
        if len(self.clut[0][0]) != 3:
            raise NotImplementedError("clut_writepng: output channels != 3")
        imfile.write(self.clut, stream_or_filename)

    def clut_writecgats(self, stream_or_filename):
        """Write the cLUT as CGATS"""
        # TODO:
        # Need to take into account input/output curves
        # Currently only supports RGB, A2B direction, and XYZ color space
        if len(self.clut[0][0]) != 3:
            raise NotImplementedError("clut_writecgats: output channels != 3")
        if isinstance(stream_or_filename, str):
            stream = open(stream_or_filename, "wb")
        else:
            stream = stream_or_filename
        with stream:
            stream.write(
                b"""CTI3
DEVICE_CLASS "DISPLAY"
COLOR_REP "RGB_XYZ"
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
BEGIN_DATA
"""
            )
            clutres = len(self.clut[0])
            block = 0
            i = 1
            if self.tagSignature and self.tagSignature.startswith("B2A"):
                interp = []
                for input in self.input:
                    interp.append(
                        colormath.Interp(input, list(range(len(input))), use_numpy=True)
                    )
            for a in range(clutres):
                for b in range(clutres):
                    for c in range(clutres):
                        R, G, B = [v / (clutres - 1.0) * 100 for v in (a, b, c)]
                        if self.tagSignature and self.tagSignature.startswith("B2A"):
                            linear_rgb = [
                                interp[i](v)
                                / (len(interp[i].xp) - 1.0)
                                * (1 + (32767 / 32768.0))
                                * 100
                                for i, v in enumerate(self.clut[block][c])
                            ]
                            X, Y, Z = self.matrix.inverted() * linear_rgb
                        else:
                            X, Y, Z = [v / 32768.0 * 100 for v in self.clut[block][c]]
                        stream.write(
                            b"%i %7.3f %7.3f %7.3f %10.6f %10.6f %10.6f\n"
                            % (i, R, G, B, X, Y, Z)
                        )
                        i += 1
                    block += 1
            stream.write(b"END_DATA\n")

    @property
    def clut_grid_steps(self):
        """Return number of grid points per dimension."""
        return self._g or len(self.clut[0])

    @property
    def input(self):
        if self._input is None:
            i, n = self._i, self._n
            tagData = self._tagData
            self._input = [
                [
                    uInt16Number(
                        tagData[52 + n * 2 * z + y * 2 : 54 + n * 2 * z + y * 2]
                    )
                    for y in range(n)
                ]
                for z in range(i)
            ]
        return self._input

    @input.setter
    def input(self, value):
        self._input = value

    @property
    def input_channels_count(self):
        """Return number of input channels."""
        return self._i or len(self.input)

    @property
    def input_entries_count(self):
        """Return number of entries per input channel."""
        return self._n or len(self.input[0])

    def invert(self):
        """Invert input and output tables."""
        # Invert input/output 1d LUTs
        for channel in (self.input, self.output):
            for e, entries in enumerate(channel):
                lut = dict()
                maxv = len(entries) - 1.0
                for i, entry in enumerate(entries):
                    lut[entry / 65535.0 * maxv] = i / maxv * 65535
                xp = list(lut.keys())
                fp = list(lut.values())
                for i in range(len(entries)):
                    if i not in lut:
                        lut[i] = colormath.interp(i, xp, fp)
                lut = dict_sort(lut)
                channel[e] = list(lut.values())

    def clut_row_apply_per_channel(
        self,
        indexes,
        fn,
        fnargs=None,
        fnkwargs=None,
        pcs=None,
        protect_gray_axis=True,
        protect_dark=False,
        protect_black=True,
        exclude=None,
    ):
        """Apply function to channel values of each cLUT row"""
        if fnargs is None:
            fnargs = ()

        if fnkwargs is None:
            fnkwargs = {}

        clutres = len(self.clut[0])
        block = -1
        for i, row in enumerate(self.clut):
            channels = {}
            for k in indexes:
                channels[k] = []
            if protect_gray_axis or protect_dark or protect_black or exclude:
                if i % clutres == 0:
                    block += 1
                    if pcs == "XYZ":
                        gray_col_i = block
                    else:
                        # L*a*b*
                        gray_col_i = clutres // 2
                    gray_row_i = i + gray_col_i
                fnkwargs["protect"] = []
            for j, column in enumerate(row):
                is_exclude = exclude and (i, j) in exclude
                if is_exclude or (
                    protect_gray_axis and (i == gray_row_i and j == gray_col_i)
                ):
                    if DEBUG:
                        print(
                            "protect", "exclude" if is_exclude else "gray", i, j, column
                        )
                    fnkwargs["protect"].append(j)
                elif (protect_dark and sum(column) < 65535 * 0.03125 * 3) or (
                    protect_black and min(column) == max(column) == 0
                ):
                    if DEBUG:
                        print("protect dark", i, j, column)
                    fnkwargs["protect"].append(j)
                for k in indexes:
                    channels[k].append(column[k])
            for k in channels:
                values = channels[k]
                channels[k] = fn(values, *fnargs, **fnkwargs)
            for j, column in enumerate(row):
                for k in indexes:
                    column[k] = channels[k][j]

    def clut_shift_columns(self, order=(1, 2, 0)):
        """Shift cLUT columns, altering slowest to fastest changing column"""
        if len(self.input) != 3:
            raise NotImplementedError("input channels != 3")
        steps = len(self.clut[0])
        clut = []
        coord = [0, 0, 0]
        for a in range(steps):
            coord[order[0]] = a
            for b in range(steps):
                coord[order[1]] = b
                clut.append([])
                for c in range(steps):
                    coord[order[2]] = c
                    z, y, x = coord
                    clut[-1].append(self.clut[z * steps + y][x])
        self.clut = clut

    @property
    def matrix(self):
        if self._matrix is None:
            tagData = self._tagData
            return colormath.Matrix3x3(
                [
                    (
                        s15Fixed16Number(tagData[12:16]),
                        s15Fixed16Number(tagData[16:20]),
                        s15Fixed16Number(tagData[20:24]),
                    ),
                    (
                        s15Fixed16Number(tagData[24:28]),
                        s15Fixed16Number(tagData[28:32]),
                        s15Fixed16Number(tagData[32:36]),
                    ),
                    (
                        s15Fixed16Number(tagData[36:40]),
                        s15Fixed16Number(tagData[40:44]),
                        s15Fixed16Number(tagData[44:48]),
                    ),
                ]
            )
        return self._matrix

    @matrix.setter
    def matrix(self, value):
        self._matrix = value

    @property
    def output(self):
        if self._output is None:
            i, o, g, n, m = self._i, self._o, self._g, self._n, self._m
            tagData = self._tagData
            self._output = [
                [
                    uInt16Number(
                        tagData[
                            52 + n * i * 2 + m * 2 * z + y * 2 + g**i * o * 2 : 54
                            + n * i * 2
                            + m * 2 * z
                            + y * 2
                            + g**i * o * 2
                        ]
                    )
                    for y in range(m)
                ]
                for z in range(o)
            ]
        return self._output

    @output.setter
    def output(self, value):
        self._output = value

    @property
    def output_channels_count(self):
        """Return number of output channels."""
        return self._o or len(self.output)

    @property
    def output_entries_count(self):
        """Return number of entries per output channel."""
        return self._m or len(self.output[0])

    def smooth(self, diagpng=2, pcs=None, filename=None, logfile=None, debug_=0):
        """Apply extra smoothing to the cLUT"""
        if not pcs:
            if self.profile:
                pcs = self.profile.connectionColorSpace
            else:
                raise TypeError("PCS not specified")

        if not filename and self.profile:
            filename = self.profile.fileName

        clutres = len(self.clut[0])

        sig = self.tagSignature or id(self)

        if diagpng and filename and len(self.output) == 3:
            # Generate diagnostic images
            fname, _ = os.path.splitext(filename)
            diag_fname = f"{fname}.{sig}.post.CLUT.png"
            if diagpng == 2 and not os.path.isfile(diag_fname):
                self.clut_writepng(diag_fname)
        else:
            diagpng = 0

        if logfile:
            logfile.write(f"Smoothing {sig}...\n")
        # Create a list of <clutres> number of 2D grids, each one with a
        # size of (width x height) <clutres> x <clutres>
        grids = []
        for i, block in enumerate(self.clut):
            if i % clutres == 0:
                grids.append([])
            grids[-1].append([])
            for RGB in block:
                grids[-1][-1].append(RGB)
        for i, grid in enumerate(grids):
            for y in range(clutres):
                for x in range(clutres):
                    is_dark = sum(grid[y][x]) < 65535 * 0.03125 * 3
                    if pcs == "XYZ":
                        is_gray = x == y == i
                    elif clutres // 2 != clutres / 2.0:
                        # For CIELab cLUT, gray will only
                        # fall on a cLUT point if uneven cLUT res
                        is_gray = x == y == clutres // 2
                    else:
                        is_gray = False
                    # print(
                    #     i, y, x,
                    #     "{:d} {:d} {:d}".format(*(int(v / 655.35 * 2.55) for v in grid[y][x])),
                    #     is_dark,
                    #     raw_input(is_gray) if is_gray else "",
                    # )
                    if is_dark or is_gray:
                        # Don't smooth dark colors and gray axis
                        continue
                    RGB = [[v] for v in grid[y][x]]
                    # Use either "plus"-shaped or box filter depending if one
                    # channel is fully saturated
                    if clutres - 1 in (y, x) or 0 in (x, y):
                        # Filter with a "plus" (+) shape
                        if pcs == "Lab" and i > clutres / 2.0:
                            # Smoothing factor for L*a*b* -> RGB cLUT above 50%
                            smooth = 0.25
                        else:
                            smooth = 0.5
                        for j, c in enumerate((x, y)):
                            # Omit corners and perpendicular axis
                            if 0 < c < clutres - 1:
                                for n in (-1, 1):
                                    yi, xi = (y, y + n)[j], (x + n, x)[j]
                                    if -1 < xi < clutres and -1 < yi < clutres:
                                        RGBn = grid[yi][xi]
                                        if debug_ == 2:
                                            if i < clutres - 1 or grid[y][x] != [
                                                16384,
                                                16384,
                                                16384,
                                            ]:
                                                grid[y][x] = [32768, 32768, 32768]
                                            if x == y == clutres - 2:
                                                RGBn[:] = [16384, 16384, 16384]
                                        for k in range(3):
                                            RGB[k].append(
                                                RGBn[k] * smooth
                                                + RGB[k][0] * (1 - smooth)
                                            )
                    else:
                        # Box filter, 3x3
                        # Center pixel weight = 1.0, surround = 2/3, corners = 1/3
                        if debug_ == 1:
                            grid[y][x] = [32768, 32768, 32768]
                        for j in (0, 1):
                            for n in (-1, 1):
                                for yi, xi in [
                                    ((y, y + n)[j], (x + n, x)[j]),
                                    (y - n, (x + n, x - n)[j]),
                                ]:
                                    if -1 < xi < clutres and -1 < yi < clutres:
                                        RGBn = grid[yi][xi]
                                        if yi != y and xi != x:
                                            smooth = 1 / 3.0
                                        else:
                                            smooth = 2 / 3.0
                                        if debug_ == 1 and x == y == clutres - 2:
                                            RGBn[:] = (v * (1 - smooth) for v in RGBn)
                                        for k in range(3):
                                            RGB[k].append(
                                                RGBn[k] * smooth
                                                + RGB[k][0] * (1 - smooth)
                                            )
                    if not debug_:
                        grid[y][x] = [sum(v) / float(len(v)) for v in RGB]
            for j, row in enumerate(grid):
                self.clut[i * clutres + j] = [
                    [min(v, 65535) for v in RGB] for RGB in row
                ]

        if diagpng and filename:
            self.clut_writepng(f"{fname}.{sig}.post.CLUT.smooth.png")

    def smooth2(
        self,
        diagpng=2,
        pcs=None,
        filename=None,
        logfile=None,
        window=(1 / 16.0, 1, 1 / 16.0),
    ):
        """Apply extra smoothing to the cLUT"""
        if not pcs:
            if self.profile:
                pcs = self.profile.connectionColorSpace
            else:
                raise TypeError("PCS not specified")

        if not filename and self.profile:
            filename = self.profile.fileName

        clutres = len(self.clut[0])

        sig = self.tagSignature or id(self)

        if diagpng and filename and len(self.output) == 3:
            # Generate diagnostic images
            fname, ext = os.path.splitext(filename)
            diag_fname = f"{fname}.{sig}.post.CLUT.png"
            if diagpng == 2 and not os.path.isfile(diag_fname):
                self.clut_writepng(diag_fname)
        else:
            diagpng = 0

        if logfile:
            logfile.write(f"Smoothing {sig}...\n")

        for i in range(3):
            state = ("original", "pass", "final")[i]
            if diagpng != 3 and i != 1:
                continue
            for j, (order, channels) in enumerate(
                [
                    (None, "BGR"),
                    ((1, 2, 0), "RBG"),
                    ((0, 2, 1), "BRG"),
                    ((2, 1, 0), "GRB"),
                    ((0, 2, 1), "RGB"),
                    ((2, 0, 1), "GBR"),
                    ((0, 2, 1), "BGR"),
                ]
            ):
                if order:
                    if DEBUG:
                        print("Shifting order to", channels)
                    self.clut_shift_columns(order)
                if i == 1 and j != 6:
                    if DEBUG:
                        print("Smoothing")
                    exclude = None
                    protect_gray_axis = True
                    if pcs == "Lab":
                        if clutres // 2 != clutres / 2.0:
                            # For CIELab cLUT, gray will only
                            # fall on a cLUT point if uneven cLUT res
                            if channels in ("RBG", "RGB"):
                                exclude = [
                                    ((clutres // 2 + 1) * (clutres - 1), col)
                                    for col in range(clutres)
                                ]
                                protect_gray_axis = False
                            elif channels in ("BRG", "GRB"):
                                exclude = [
                                    ((clutres // 2) * clutres + y, clutres // 2)
                                    for y in range(clutres)
                                ]
                                protect_gray_axis = False
                        else:
                            protect_gray_axis = False
                    self.clut_row_apply_per_channel(
                        (0, 1, 2),
                        colormath.smooth_avg,
                        (),
                        {"window": window},
                        pcs,
                        protect_gray_axis,
                        exclude=exclude,
                    )
                if diagpng == 3 and filename and j != 6:
                    if DEBUG:
                        print("Writing diagnostic PNG for", state, channels)
                    self.clut_writepng(
                        f"{fname}.{sig}.post.CLUT.{channels}.{state}.png"
                    )

        if diagpng and filename:
            self.clut_writepng(f"{fname}.{sig}.post.CLUT.smooth.png")

    @property
    def tagData(self):
        """Return raw tag data."""

        if (self._matrix, self._input, self._clut, self._output) == (None,) * 4:
            return self._tagData
        tagData = [
            b"mft2",
            b"\0" * 4,
            uInt8Number_tohex(len(self.input)),
            uInt8Number_tohex(len(self.output)),
            uInt8Number_tohex(len(self.clut and self.clut[0])),
            b"\0",
            s15Fixed16Number_tohex(self.matrix[0][0]),
            s15Fixed16Number_tohex(self.matrix[0][1]),
            s15Fixed16Number_tohex(self.matrix[0][2]),
            s15Fixed16Number_tohex(self.matrix[1][0]),
            s15Fixed16Number_tohex(self.matrix[1][1]),
            s15Fixed16Number_tohex(self.matrix[1][2]),
            s15Fixed16Number_tohex(self.matrix[2][0]),
            s15Fixed16Number_tohex(self.matrix[2][1]),
            s15Fixed16Number_tohex(self.matrix[2][2]),
            uInt16Number_tohex(len(self.input and self.input[0])),
            uInt16Number_tohex(len(self.output and self.output[0])),
        ]
        for entries in self.input:
            tagData.extend(uInt16Number_tohex(v) for v in entries)
        for block in self.clut:
            for entries in block:
                tagData.extend(uInt16Number_tohex(v) for v in entries)
        for entries in self.output:
            tagData.extend(uInt16Number_tohex(v) for v in entries)
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        self._tagData = tagData


class Observer(ADict):
    def __init__(self, bytes_data):
        super(ADict, self).__init__()
        self.type = uInt32Number(bytes_data)
        self.description = OBSERVERS[self.type]


class ChromaticityType(ICCProfileTag, Colorant):
    def __init__(self, tagData=None, tagSignature=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        if not tagData:
            Colorant.__init__(self, uInt32Number_tohex(1))
            return
        deviceChannelsCount = uInt16Number(tagData[8:10])
        Colorant.__init__(self, uInt32Number_tohex(uInt16Number(tagData[10:12])))
        channels = tagData[12:]
        for _count in range(deviceChannelsCount):
            self._channels.append(
                [u16Fixed16Number(channels[:4]), u16Fixed16Number(channels[4:8])]
            )
            channels = channels[8:]

    __repr__ = Colorant.__repr__

    @property
    def tagData(self):
        """Return raw tag data."""
        tagData = [b"chrm", b"\0" * 4, uInt16Number_tohex(len(self.channels))]
        tagData.append(uInt16Number_tohex(self.type))
        for channel in self.channels:
            for xy in channel:
                tagData.append(u16Fixed16Number_tohex(xy))
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass


class ColorantTableType(ICCProfileTag, AODict):
    def __init__(self, tagData=None, tagSignature=None, pcs=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        colorantCount = uInt32Number(tagData[8:12])
        data = tagData[12:]
        for _count in range(colorantCount):
            pcsvalues = [
                uInt16Number(data[32:34]),
                uInt16Number(data[34:36]),
                uInt16Number(data[36:38]),
            ]
            for i, pcsvalue in enumerate(pcsvalues):
                if pcs in (b"Lab", b"RGB", b"CMYK", b"YCbr"):
                    keys = ["L", "a", "b"]
                    if i == 0:
                        # L* range 0..100 + (25500 / 65280.0)
                        pcsvalues[i] = pcsvalue / 65536.0 * 256 / 255.0 * 100
                    else:
                        # a, b range -128..127 + (255 / 256.0)
                        pcsvalues[i] = -128 + (pcsvalue / 65536.0 * 256)
                elif pcs == b"XYZ":
                    # X, Y, Z range 0..100 + (32767 / 32768.0)
                    keys = ["X", "Y", "Z"]
                    pcsvalues[i] = pcsvalue / 32768.0 * 100
                else:
                    print(f"Warning: Non-standard profile connection space '{pcs}'")
                    return
            end = data[:32].find(b"\0")
            if end < 0:
                end = 32
            name = data[:end]
            self[name] = AODict(list(zip(keys, pcsvalues)))
            data = data[38:]


class CurveType(ICCProfileTag, list):
    def __init__(self, tagData=None, tagSignature=None, profile=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        self._reset()
        if not tagData:
            return
        curveEntriesCount = uInt32Number(tagData[8:12])
        curveEntries = tagData[12:]
        if curveEntriesCount == 1:
            # Gamma
            self.append(u8Fixed8Number(curveEntries[:2]))
        elif curveEntriesCount:
            # Curve
            for _count in range(curveEntriesCount):
                self.append(uInt16Number(curveEntries[:2]))
                curveEntries = curveEntries[2:]
        else:
            # Identity
            self.append(1.0)

    def __delitem__(self, y):
        list.__delitem__(self, y)
        self._reset()

    def __delslice__(self, i, j):
        list.__delslice__(self, i, j)
        self._reset()

    def __iadd__(self, y):
        list.__iadd__(self, y)
        self._reset()

    def __imul__(self, y):
        list.__imul__(self, y)
        self._reset()

    def __setitem__(self, i, y):
        list.__setitem__(self, i, y)
        self._reset()

    def __setslice__(self, i, j, y):
        list.__setslice__(self, i, j, y)
        self._reset()

    def _reset(self):
        self._transfer_function = {}
        self._bt1886 = {}

    def append(self, object):
        list.append(self, object)
        self._reset()

    def apply_bpc(self, black_Y_out=0, weight=False):
        if len(self) < 2:
            return
        D50_xyY = colormath.XYZ2xyY(*colormath.get_whitepoint("D50"))
        bp_in = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], self[0] / 65535.0)
        bp_out = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], black_Y_out)
        wp_out = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], self[-1] / 65535.0)
        for i, v in enumerate(self):
            X, Y, Z = colormath.xyY2XYZ(D50_xyY[0], D50_xyY[1], v / 65535.0)
            self[i] = (
                colormath.apply_bpc(X, Y, Z, bp_in, bp_out, wp_out, weight)[1] * 65535.0
            )

    def extend(self, iterable):
        list.extend(self, iterable)
        self._reset()

    def get_gamma(
        self,
        use_vmin_vmax=False,
        average=True,
        least_squares=False,
        slice=(0.01, 0.99),
        lstar_slice=True,
    ):
        """Return average or least squares gamma or a list of gamma values"""
        if len(self) <= 1:
            if len(self):
                values = self
            else:
                # Identity
                values = [1.0]
            if average or least_squares:
                return values[0]
            return [values[0]]
        if lstar_slice:
            start = slice[0] * 100
            end = slice[1] * 100
            values = []
            for i, y in enumerate(self):
                n = colormath.XYZ2Lab(0, y / 65535.0 * 100, 0)[0]
                if start <= n <= end:
                    values.append((i / (len(self) - 1.0) * 65535.0, y))
        else:
            maxv = len(self) - 1.0
            maxi = int(maxv)
            starti = int(round(slice[0] * maxi))
            endi = int(round(slice[1] * maxi)) + 1
            values = list(
                zip(
                    [(v / maxv) * 65535 for v in range(starti, endi)], self[starti:endi]
                )
            )
        vmin = 0
        vmax = 65535.0
        if use_vmin_vmax:
            if len(self) > 2:
                vmin = self[0]
                vmax = self[-1]
        return colormath.get_gamma(values, 65535.0, vmin, vmax, average, least_squares)

    def get_transfer_function(
        self, best=True, slice=(0.05, 0.95), black_Y=None, outoffset=None
    ):
        """Return transfer function name, exponent and match percentage."""
        if len(self) == 1:
            # Gamma
            return (f"Gamma {round(self[0], 2):.2f}", self[0], 1.0), 1.0
        if not len(self):
            # Identity
            return ("Gamma 1.0", 1.0, 1.0), 1.0
        transfer_function = self._transfer_function.get((best, slice))
        if transfer_function:
            return transfer_function
        trc = CurveType()
        match = {}
        otrc = CurveType()
        otrc[:] = self
        if otrc[0]:
            otrc.apply_bpc()
        vmin = otrc[0]
        vmax = otrc[-1]
        if self.profile and isinstance(self.profile.tags.get("lumi"), XYZType):
            white_cdm2 = self.profile.tags.lumi.Y
        else:
            white_cdm2 = 100.0
        if black_Y is None:
            black_Y = self[0] / 65535.0
        black_cdm2 = black_Y * white_cdm2
        maxv = len(otrc) - 1.0
        maxi = int(maxv)
        _starti = int(round(0.4 * maxi))
        _endi = int(round(0.6 * maxi))
        gamma = otrc.get_gamma(True, slice=(0.4, 0.6), lstar_slice=False)
        egamma = colormath.get_gamma([(0.5, 0.5**gamma)], vmin=-black_Y)
        outoffset_unspecified = outoffset is None
        if outoffset_unspecified:
            outoffset = 1.0
        tfs = [
            ("Rec. 709", -709, outoffset),
            ("Rec. 1886", -1886, 0),
            ("SMPTE 240M", -240, outoffset),
            ("SMPTE 2084", -2084, outoffset),
            ("DICOM", -1023, outoffset),
            ("HLG", -2, outoffset),
            ("L*", -3.0, outoffset),
            ("sRGB", -2.4, outoffset),
            (
                "Gamma {:.2f} {:.0%}".format(gamma, outoffset),
                gamma,
                outoffset,
            ),
        ]
        if outoffset_unspecified and black_Y:
            for i in range(100):
                tfs.append(
                    (
                        "Gamma {:.2f} {:d}%".format(gamma, i),
                        gamma,
                        i / 100.0,
                    )
                )
        for name, exp, outoffset in tfs:
            if name in ("DICOM", "Rec. 1886", "SMPTE 2084", "HLG"):
                try:
                    if name == "DICOM":
                        trc.set_dicom_trc(black_cdm2, white_cdm2, size=len(self))
                    elif name == "Rec. 1886":
                        trc.set_bt1886_trc(black_Y, size=len(self))
                    elif name == "SMPTE 2084":
                        trc.set_smpte2084_trc(black_cdm2, white_cdm2, size=len(self))
                    elif name == "HLG":
                        trc.set_hlg_trc(black_cdm2, white_cdm2, size=len(self))
                except ValueError:
                    continue
            elif exp > 0 and black_Y:
                trc.set_bt1886_trc(black_Y, outoffset, egamma, "b")
            else:
                trc.set_trc(exp, len(self), vmin, vmax)
            if trc[0] and trc[-1] - trc[0]:
                trc.apply_bpc()
            if otrc == trc:
                match[(name, exp, outoffset)] = 1.0
            else:
                match[(name, exp, outoffset)] = 0.0
                count = 0
                start = slice[0] * len(self)
                end = slice[1] * len(self)
                for i, n in enumerate(otrc):
                    # n = colormath.XYZ2Lab(0, n / 65535.0 * 100, 0)[0]
                    if start <= i <= end:
                        n = colormath.get_gamma(
                            [(i / (len(self) - 1.0) * 65535.0, n)],
                            65535.0,
                            vmin,
                            vmax,
                            False,
                        )
                        if n:
                            n = n[0]
                            # n2 = colormath.XYZ2Lab(0, trc[i] / 65535.0 * 100, 0)[0]
                            n2 = colormath.get_gamma(
                                [(i / (len(self) - 1.0) * 65535.0, trc[i])],
                                65535.0,
                                vmin,
                                vmax,
                                False,
                            )
                            if n2 and n2[0]:
                                n2 = n2[0]
                                match[(name, exp, outoffset)] += 1 - (
                                    max(n, n2) - min(n, n2)
                                ) / ((n + n2) / 2.0)
                                count += 1
                if count:
                    match[(name, exp, outoffset)] /= count
        if not best:
            self._transfer_function[(best, slice)] = match
            return match
        match, (name, exp, outoffset) = sorted(
            zip(list(match.values()), list(match.keys()))
        )[-1]
        self._transfer_function[(best, slice)] = (name, exp, outoffset), match
        return (name, exp, outoffset), match

    def insert(self, object):
        list.insert(self, object)
        self._reset()

    def pop(self, index):
        list.pop(self, index)
        self._reset()

    def remove(self, value):
        list.remove(self, value)
        self._reset()

    def reverse(self):
        list.reverse(self)
        self._reset()

    def set_bt1886_trc(
        self, black_Y=0, outoffset=0.0, gamma=2.4, gamma_type="B", size=None
    ):
        """Set the response to the BT. 1886 curve

        This response is special in that it depends on the actual black
        level of the display.

        """
        bt1886 = self._bt1886.get((gamma, black_Y, outoffset))
        if bt1886:
            return bt1886
        if gamma_type in ("b", "g"):
            # Get technical gamma needed to achieve effective gamma
            gamma = colormath.xicc_tech_gamma(gamma, black_Y, outoffset)
        rXYZ = colormath.RGB2XYZ(1.0, 0, 0)
        gXYZ = colormath.RGB2XYZ(0, 1.0, 0)
        bXYZ = colormath.RGB2XYZ(0, 0, 1.0)
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        wXYZ = colormath.RGB2XYZ(1.0, 1.0, 1.0)
        x, y = colormath.XYZ2xyY(*wXYZ)[:2]
        XYZbp = colormath.xyY2XYZ(x, y, black_Y)
        bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
        self._bt1886[(gamma, black_Y, outoffset)] = bt1886
        self.set_trc(-709, size)
        for i, v in enumerate(self):
            X, Y, Z = colormath.xyY2XYZ(x, y, v / 65535.0)
            self[i] = bt1886.apply(X, Y, Z)[1] * 65535.0

    def set_dicom_trc(self, black_cdm2=0.05, white_cdm2=100, size=None):
        """Set the response to the DICOM Grayscale Standard Display Function

        This response is special in that it depends on the actual black
        and white level of the display.

        """
        # See http://medical.nema.org/Dicom/2011/11_14pu.pdf
        # Luminance levels depend on the start level of 0.05 cd/m2
        # and end level of 4000 cd/m2
        black_cdm2 = round(black_cdm2, 6)
        if black_cdm2 < 0.05 or black_cdm2 >= white_cdm2:
            raise ValueError(
                f"The black level of {black_cdm2} cd/m2 is out of range "
                "for DICOM. Valid range begins at 0.05 cd/m2."
            )
        if white_cdm2 > 4000 or white_cdm2 <= black_cdm2:
            raise ValueError(
                f"The white level of {white_cdm2} cd/m2 is out of range "
                "for DICOM. Valid range is up to 4000 cd/m2."
            )
        black_jndi = colormath.DICOM(black_cdm2, True)
        white_jndi = colormath.DICOM(white_cdm2, True)
        white_dicomY = math.pow(10, colormath.DICOM(white_jndi))
        if not size:
            size = len(self)
        if size < 2:
            size = 1024
        self[:] = []
        for i in range(size):
            v = (
                math.pow(
                    10,
                    colormath.DICOM(
                        black_jndi + (float(i) / (size - 1)) * (white_jndi - black_jndi)
                    ),
                )
                / white_dicomY
            )
            self.append(v * 65535)

    def set_hlg_trc(
        self,
        black_cdm2=0,
        white_cdm2=100,
        system_gamma=1.2,
        ambient_cdm2=5,
        maxsignal=1.0,
        size=None,
        logfile=None,
    ):
        """Set the response to the Hybrid Log-Gamma (HLG) function

        This response is special in that it depends on the actual black
        and white level of the display, system gamma and ambient.

        XYZbp           Black point in absolute XYZ, Y range 0..white_cdm2
        maxsignal       Set clipping point (optional)
        size            Number of steps. Recommended >= 1024

        """
        if black_cdm2 < 0 or black_cdm2 >= white_cdm2:
            raise ValueError(
                f"The black level of {black_cdm2:f} cd/m2 is out of range "
                "for HLG. Valid range begins at 0 cd/m2."
            )
        values = []

        hlg = colormath.HLG(black_cdm2, white_cdm2, system_gamma, ambient_cdm2)

        if maxsignal < 1:
            # Adjust EOTF so that EOTF[maxsignal] gives (approx) white_cdm2
            while hlg.eotf(maxsignal) * hlg.white_cdm2 < white_cdm2:
                hlg.white_cdm2 += 1

        lscale = 1.0 / hlg.oetf(1.0, True)
        hlg.white_cdm2 *= lscale
        if lscale < 1 and logfile:
            logfile.write(
                f"Nominal peak luminance after scaling = {hlg.white_cdm2:.2f}\n"
            )

        maxv = hlg.eotf(maxsignal)
        if not size:
            size = len(self)
        if size < 2:
            size = 1024
        for i in range(size):
            n = i / (size - 1.0)
            v = hlg.eotf(min(n, maxsignal))
            values.append(min(v / maxv, 1.0))
        self[:] = [min(v * 65535, 65535) for v in values]

    def set_smpte2084_trc(
        self,
        black_cdm2=0,
        white_cdm2=100,
        master_black_cdm2=0,
        master_white_cdm2=0,
        use_alternate_master_white_clip=True,
        rolloff=False,
        size=None,
    ):
        """Set the response to the SMPTE 2084 perceptual quantizer (PQ) function

        This response is special in that it depends on the actual black
        and white level of the display.

        black_cdm2      Black point in absolute Y, range 0..white_cdm2
        master_black_cdm2  (Optional) Used to normalize PQ values
        master_white_cdm2  (Optional) Used to normalize PQ values
        rolloff         BT.2390
        size            Number of steps. Recommended >= 1024

        """
        # See https://www.smpte.org/sites/default/files/2014-05-06-EOTF-Miller-1-2-handout.pdf
        # Luminance levels depend on the end level of 10000 cd/m2
        if black_cdm2 < 0 or black_cdm2 >= white_cdm2:
            raise ValueError(
                f"The black level of {black_cdm2:f} cd/m2 is out of range "
                "for SMPTE 2084. Valid range begins at 0 cd/m2."
            )
        if max(white_cdm2, master_white_cdm2) > 10000:
            raise ValueError(
                f"The white level of {max(white_cdm2, master_white_cdm2):f} "
                "cd/m2 is out of range for SMPTE 2084. "
                "Valid range is up to 10000 cd/m2."
            )
        values = []
        maxv = white_cdm2 / 10000.0
        maxi = colormath.specialpow(maxv, 1.0 / -2084)
        if rolloff:
            # Rolloff as defined in ITU-R BT.2390
            if not master_white_cdm2:
                master_white_cdm2 = 10000
            bt2390 = colormath.BT2390(
                black_cdm2,
                white_cdm2,
                master_black_cdm2,
                master_white_cdm2,
                use_alternate_master_white_clip,
            )
            maxi_out = maxi
        else:
            if not master_white_cdm2:
                master_white_cdm2 = white_cdm2
            maxi_out = colormath.specialpow(master_white_cdm2 / 10000.0, 1.0 / -2084)
        if not size:
            size = len(self)
        if size < 2:
            size = 1024
        for i in range(size):
            n = i / (size - 1.0)
            if rolloff:
                n = bt2390.apply(n)
            v = colormath.specialpow(n * (maxi / maxi_out), -2084)
            values.append(min(v / maxv, 1.0))
        self[:] = [min(v * 65535, 65535) for v in values]
        if black_cdm2 and not rolloff:
            self.apply_bpc(black_cdm2 / white_cdm2)

    def set_trc(self, power=2.2, size=None, vmin=0, vmax=65535):
        """Set the response to a certain function.

        Positive power, or -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
        -601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
        identical)

        """
        if not size:
            size = len(self) or 1024
        if size == 1:
            if callable(power):
                power = colormath.get_gamma([(0.5, power(0.5))])
            if power >= 0.0 and not vmin:
                self[:] = [power]
                return
            else:
                size = 1024
        self[:] = []
        if not callable(power):
            exp = power

            def power(a):
                return colormath.specialpow(a, exp)

        for i in range(0, size):
            self.append(vmin + power(float(i) / (size - 1)) * (vmax - vmin))

    def smooth_cr(self, length=64):
        """Smooth curves (Catmull-Rom)."""
        raise NotImplementedError()

    def smooth_avg(self, passes=1, window=None):
        """Smooth curves (moving average).

        passses   Number of passes
        window    Tuple or list containing weighting factors. Its length
                  determines the size of the window to use.
                  Defaults to (1.0, 1.0, 1.0)

        """
        self[:] = colormath.smooth_avg(self, passes, window)

    def sort(self, cmp=None, key=None, reverse=False):
        list.sort(self, key=key, reverse=reverse)
        self._reset()

    @property
    def tagData(self):
        """Return raw tag data."""

        if len(self) == 1 and self[0] == 1.0:
            # Identity
            curveEntriesCount = 0
        else:
            curveEntriesCount = len(self)
        tagData = [b"curv", b"\0" * 4, uInt32Number_tohex(curveEntriesCount)]
        if curveEntriesCount == 1:
            # Gamma
            tagData.append(u8Fixed8Number_tohex(self[0]))
        elif curveEntriesCount:
            # Curve
            for curveEntry in self:
                tagData.append(uInt16Number_tohex(curveEntry))
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass


class ParametricCurveType(ICCProfileTag):
    def __init__(self, tagData=None, tagSignature=None, profile=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        self.params = {}
        if not tagData:
            return
        fntype = uInt16Number(tagData[8:10])
        numparams = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}.get(fntype)
        for i, param in enumerate("gabcdef"[:numparams]):
            self.params[param] = s15Fixed16Number(tagData[12 + i * 4 : 12 + i * 4 + 4])

    def __apply(self, v):
        if len(self.params) == 1:
            return v ** self.params["g"]
        elif len(self.params) == 3:
            # CIE 122-1966
            if v >= -self.params["b"] / self.params["a"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params["g"]
            else:
                return 0
        elif len(self.params) == 4:
            # IEC 61966-3
            if v >= -self.params["b"] / self.params["a"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params[
                    "g"
                ] + self.params["c"]
            else:
                return self.params["c"]
        elif len(self.params) == 5:
            # IEC 61966-2.1 (sRGB)
            if v >= self.params["d"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params["g"]
            else:
                return self.params["c"] * v
        elif len(self.params) == 7:
            if v >= self.params["d"]:
                return (self.params["a"] * v + self.params["b"]) ** self.params[
                    "g"
                ] + self.params["e"]
            else:
                return self.params["c"] * v + self.params["f"]
        else:
            raise NotImplementedError(
                f"Invalid number of parameters: {len(self.params):d}"
            )

    def apply(self, v):
        # clip result to [0, 1]
        return max(0, min(self.__apply(v), 1))

    def get_trc(self, size=1024):
        curv = CurveType(profile=self.profile)
        for i in range(size):
            curv.append(self.apply(i / (size - 1.0)) * 65535)
        return curv


class DateTimeType(ICCProfileTag, datetime.datetime):
    def __new__(cls, tagData, tagSignature):
        dt = dateTimeNumber(tagData[8:20])
        return datetime.datetime.__new__(
            cls, dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
        )


class DictList(list):
    def __getitem__(self, key):
        for item in self:
            if item[0] == key:
                return item
        raise KeyError(key)

    def __setitem__(self, key, value):
        if not isinstance(value, DictListItem):
            self.append(DictListItem((key, value)))


class DictListItem(list):
    def __iadd__(self, value):
        self[-1] += value
        return self


class DictType(ICCProfileTag, AODict):
    """ICC dictType Tag

    Implements all features of 'Dictionary Type and Metadata TAG Definition'
    (ICC spec revision 2010-02-25), including shared data (the latter will
    only be effective for mutable types, ie. MultiLocalizedUnicodeType)

    Examples:

    tag[key]   Returns the (non-localized) value
    tag.getname(key, locale='en_US') Returns the localized name if present
    tag.getvalue(key, locale='en_US') Returns the localized value if present
    tag[key] = value   Sets the (non-localized) value

    """

    def __init__(self, tagData=None, tagSignature=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        numrecords = uInt32Number(tagData[8:12])
        recordlen = uInt32Number(tagData[12:16])
        if recordlen not in (16, 24, 32):
            print(
                f"Error (non-critical): '{tagData[:4]}' invalid record length "
                f"(expected 16, 24 or 32, got {recordlen})"
            )
            return
        elements = {}
        for n in range(0, numrecords):
            record = tagData[16 + n * recordlen : 16 + (n + 1) * recordlen]
            if len(record) < recordlen:
                print(
                    f"Error (non-critical): '{tagData[:4]}' record {n} too short "
                    f"(expected {recordlen} bytes, got {len(record)} bytes)"
                )
                break
            for key, offsetpos in (
                ("name", 0),
                ("value", 8),
                ("display_name", 16),
                ("display_value", 24),
            ):
                if (
                    offsetpos in (0, 8)
                    or recordlen == offsetpos + 8
                    or recordlen == offsetpos + 16
                ):
                    # Required:
                    # Bytes 0..3, 4..7: Name offset and size
                    # Bytes 8..11, 12..15: Value offset and size
                    # Optional:
                    # Bytes 16..23, 24..23: Display name offset and size
                    # Bytes 24..27, 28..31: Display value offset and size
                    offset = uInt32Number(record[offsetpos : offsetpos + 4])
                    size = uInt32Number(record[offsetpos + 4 : offsetpos + 8])
                    if offset > 0:
                        if (offset, size) in elements:
                            # Use existing element if same offset and size
                            # This will really only make a difference for
                            # mutable types i.e. MultiLocalizedUnicodeType
                            data = elements[(offset, size)]
                        else:
                            data = tagData[offset : offset + size]
                            try:
                                if key.startswith("display_"):
                                    data = MultiLocalizedUnicodeType(data, "mluc")
                                else:
                                    data = data.decode("UTF-16-BE", "replace").rstrip(
                                        "\0"
                                    )
                            except Exception:
                                print(
                                    "Error (non-critical): could not decode "
                                    f"'{tagData[:4]}', offset {offset}, length {size}"
                                )
                            # Remember element by offset and size
                            elements[(offset, size)] = data
                        if key == "name":
                            name = data
                            self[name] = ""
                        else:
                            self.get(name)[key] = data

    def __getitem__(self, name):
        return self.get(name).value

    def __setitem__(self, name, value):
        AODict.__setitem__(self, name, ADict(value=value))

    @property
    def tagData(self):
        """Return raw tag data."""
        numrecords = len(self)
        recordlen = 16
        keys = ("name", "value")
        for value in self.values():
            if isinstance(value, dict):
                if "display_value" in value:
                    recordlen = 32
                    break
                elif "display_name" in value:
                    recordlen = 24
        if recordlen > 16:
            keys += ("display_name",)
        if recordlen > 24:
            keys += ("display_value",)
        tagData = [
            b"dict",
            b"\0" * 4,
            uInt32Number_tohex(numrecords),
            uInt32Number_tohex(recordlen),
        ]
        storage_offset = 16 + numrecords * recordlen
        storage = []
        elements = []
        offsets = []
        for item in self.items():
            for key in keys:
                if key == "name":
                    element = item[0]
                else:
                    if isinstance(item[1], dict):
                        element = item[1].get(key)
                    else:
                        element = item[1]
                if element is None:
                    offset = 0
                    size = 0
                else:
                    if element in elements:
                        # Use existing offset and size if same element
                        offset, size = offsets[elements.index(element)]
                    else:
                        offset = storage_offset + len(b"".join(storage))
                        if isinstance(element, MultiLocalizedUnicodeType):
                            data = element.tagData
                        else:
                            data = str(element).encode("UTF-16-BE")
                        size = len(data)
                        if isinstance(element, MultiLocalizedUnicodeType):
                            # Remember element, offset and size
                            elements.append(element)
                            offsets.append((offset, size))
                        # Pad all data with binary zeros so it lies on
                        # 4-byte boundaries
                        padding = int(math.ceil(size / 4.0)) * 4 - size
                        data += b"\0" * padding
                        storage.append(data)
                tagData.append(uInt32Number_tohex(offset))
                tagData.append(uInt32Number_tohex(size))
        tagData.extend(storage)
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass

    def getname(self, name, default=None, locale="en_US"):
        """Convenience function to get (localized) names"""
        item = self.get(name, default)
        if item is default:
            return default
        if locale and "display_name" in item:
            return item.display_name.get_localized_string(*locale.split("_"))
        else:
            return name

    def getvalue(self, name, default=None, locale="en_US"):
        """Convenience function to get (localized) values"""
        item = self.get(name, default)
        if item is default:
            return default
        if locale and "display_value" in item:
            return item.display_value.get_localized_string(*locale.split("_"))
        else:
            if isinstance(item, dict):
                return item.value
            else:
                return item

    def setitem(self, name, value, display_name=None, display_value=None):
        """Convenience function to set items

        display_name and display_value (if given) should be dict types with
        country -> language -> string mappings, e.g.:

        {"en": {"US": u"localized string"},
         "de": {"DE": u"localized string", "CH": u"localized string"}}

        """
        self[name] = value
        item = self.get(name)
        if display_name:
            item.display_name = MultiLocalizedUnicodeType()
            item.display_name.update(display_name)
        if display_value:
            item.display_value = MultiLocalizedUnicodeType()
            item.display_value.update(display_value)

    def to_json(self, encoding="UTF-8", errors="replace", locale="en_US"):
        """Return a JSON representation

        Display names/values are used if present.

        """
        return DictTypeJSONEncoder(locale=locale).encode(self)


class DictTypeJSONEncoder(json.JSONEncoder):
    """JSON Encoder for the DictType class."""

    def __init__(self, *args, **kwargs):
        self.locale = kwargs.pop("locale") or "en_US"
        super().__init__(*args, **kwargs)

    def default(self, obj):
        return_data = {}
        regex = re.compile(r"\\x([0-9a-f]{2})")
        repl_str = r"\\u00\1"
        for name in obj:
            value = obj.getvalue(name, None, self.locale)
            name = obj.getname(name, None, self.locale)
            value = '"{}"'.format(repr(str(value))[2:-1].replace('"', '\\"'))
            name = regex.sub(repl_str, name)
            value = regex.sub(repl_str, value)
            return_data[name] = value
        return return_data


class MakeAndModelType(ICCProfileTag, ADict):
    def __init__(self, tagData, tagSignature):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.update({"manufacturer": tagData[10:12], "model": tagData[14:16]})


class MeasurementType(ICCProfileTag, ADict):
    def __init__(self, tagData, tagSignature):
        ICCProfileTag.__init__(self, tagData, tagSignature)

        print(f"tagData[8:12]: {tagData[8:12]}")

        self.update(
            {
                "observer": Observer(tagData[8:12]),
                "backing": XYZNumber(tagData[12:24]),
                "geometry": Geometry(tagData[24:28]),
                "flare": u16Fixed16Number(tagData[28:32]),
                "illuminantType": Illuminant(tagData[32:36]),
            }
        )


class MultiLocalizedUnicodeType(ICCProfileTag, AODict):  # ICC v4
    def __init__(self, tagData=None, tagSignature=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        recordsCount = uInt32Number(tagData[8:12])
        recordSize = uInt32Number(tagData[12:16])  # 12
        if recordSize != 12:
            print(
                f"Warning (non-critical): '{tagData[:4]}' invalid record length "
                f"(expected 12, got {recordSize})"
            )
            if recordSize < 12:
                recordSize = 12
        records = tagData[16 : 16 + recordSize * recordsCount]
        for _count in range(recordsCount):
            record = records[:recordSize]
            if len(record) < 12:
                continue
            recordLanguageCode = record[:2]
            recordCountryCode = record[2:4]
            recordLength = uInt32Number(record[4:8])
            recordOffset = uInt32Number(record[8:12])
            self.add_localized_string(
                recordLanguageCode,
                recordCountryCode,
                str(
                    tagData[recordOffset : recordOffset + recordLength],
                    "utf-16-be",
                    "replace",
                ),
            )
            records = records[recordSize:]

    def __str__(self):
        """Return tag as string."""
        # TODO: Needs some work re locales
        # (currently if en-UK or en-US is not found, simply the first entry
        # is returned)
        if b"en" in self:
            for countryCode in (b"UK", b"US"):
                if countryCode in self[b"en"]:
                    return self[b"en"][countryCode]
            if self[b"en"]:
                return list(self[b"en"].values())[0]
            return ""
        elif len(self):
            return list(list(self.values())[0].values())[0]
        else:
            return ""

    def add_localized_string(self, languagecode, countrycode, localized_string):
        """Convenience function for adding localized strings"""
        if languagecode not in self:
            self[languagecode] = AODict()
        self[languagecode][countrycode] = localized_string.strip("\0")

    def get_localized_string(self, languagecode="en", countrycode="US"):
        """Convenience function for retrieving localized strings

        Falls back to first locale available if the requested one isn't

        """
        try:
            return self[languagecode][countrycode]
        except KeyError:
            return str(self)

    @property
    def tagData(self):
        """Return raw tag data."""
        tagData = [b"mluc", b"\0" * 4]
        recordsCount = 0
        for languageCode in self:
            for _countryCode in self[languageCode]:
                recordsCount += 1
        tagData.append(uInt32Number_tohex(recordsCount))
        recordSize = 12
        tagData.append(uInt32Number_tohex(recordSize))
        storage_offset = 16 + recordSize * recordsCount
        storage = []
        offsets = []
        for languageCode in self:
            for countryCode in self[languageCode]:
                tagData.append(languageCode + countryCode)
                data = self[languageCode][countryCode].encode("UTF-16-BE")
                if data in storage:
                    offset, recordLength = offsets[storage.index(data)]
                else:
                    recordLength = len(data)
                    offset = len("".join(storage))
                    offsets.append((offset, recordLength))
                    storage.append(data)
                tagData.append(uInt32Number_tohex(recordLength))
                tagData.append(uInt32Number_tohex(storage_offset + offset))
        tagData.append(
            b"".join(storage)
        )  # TODO: Are you sure that this needs to be bytes
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass


class ProfileSequenceDescType(ICCProfileTag, list):
    def __init__(self, tagData=None, tagSignature=None, profile=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        if tagData:
            count = uInt32Number(tagData[8:12])
            desc_data = tagData[12:]
            while count:
                # NOTE: Like in the profile header, the attributes are a 64 bit
                # value, but the least significant 32 bits (big-endian) are
                # reserved for the ICC.
                attributes = uInt32Number(desc_data[8:12])
                desc = {
                    "manufacturer": desc_data[0:4],
                    "model": desc_data[4:8],
                    "attributes": {
                        "reflective": attributes & 1 == 0,
                        "glossy": attributes & 2 == 0,
                        "positive": attributes & 4 == 0,
                        "color": attributes & 8 == 0,
                    },
                    "tech": desc_data[16:20],
                }
                desc_data = desc_data[20:]
                for desc_type in ("dmnd", "dmdd"):
                    tag_type = desc_data[0:4]
                    if tag_type == "desc":
                        cls = TextDescriptionType
                    elif tag_type == "mluc":
                        cls = MultiLocalizedUnicodeType
                    else:
                        print(
                            "Error (non-critical): could not fully decode 'pseq' - "
                            f"unknown {repr(desc_type)} tag type {repr(tag_type)}"
                        )
                        count = 1  # Skip remaining
                        break
                    desc[desc_type] = cls(desc_data)
                    desc_data = desc_data[len(desc[desc_type].tagData) :]
                self.append(desc)
                count -= 1

    def add(self, profile):
        """Add description structure of profile"""
        desc = {}
        desc.update(profile.device)
        desc["tech"] = profile.tags.get("tech", b"").ljust(4, b"\0")[:4]
        for desc_type in ("dmnd", "dmdd"):
            if self.profile.version >= 4:
                cls = MultiLocalizedUnicodeType
            else:
                cls = TextDescriptionType
            if self.profile.version < 4 and profile.version < 4:
                # Both profiles not v4
                tag = profile.tags.get(desc_type, cls())
            else:
                tag = cls()
                description = str(profile.tags.get(desc_type, ""))
                if self.profile.version < 4:
                    # Other profile is v4
                    tag.ASCII = description.encode("ASCII", "asciize")
                    if tag.ASCII != description:
                        tag.Unicode = description
                else:
                    # Other profile is v2
                    tag.add_localized_string("en", "US", description)
            desc[desc_type] = tag
        self.append(desc)

    @property
    def tagData(self):
        """Return raw tag data."""
        tag_data = [b"pseq", b"\0" * 4, uInt32Number_tohex(len(self))]
        for desc in self:
            tag_data.append(desc.get("manufacturer", b"").ljust(4, b"\0")[:4])
            tag_data.append(desc.get("model", b"").ljust(4, b"\0")[:4])
            attributes = 0
            for name, bit in {
                "reflective": 1,
                "glossy": 2,
                "positive": 4,
                "color": 8,
            }.items():
                if not desc.get("attributes", {}).get(name):
                    attributes |= bit
            tag_data.append(uInt32Number_tohex(attributes) + b"\0" * 4)
            tag_data.append(desc.get("tech", b"").ljust(4, b"\0")[:4])
            for desc_type in ("dmnd", "dmdd"):
                tag_data.append(desc.get(desc_type, b"").tagData)
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tag_data):
        pass


class s15Fixed16ArrayType(ICCProfileTag, list):
    def __init__(self, tagData=None, tagSignature=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        if tagData:
            data = tagData[8:]
            while data:
                self.append(s15Fixed16Number(data[0:4]))
                data = data[4:]

    @property
    def tagData(self):
        """Return raw tag data."""
        tag_data = [b"sf32", b"\0" * 4]
        for value in self:
            tag_data.append(s15Fixed16Number_tohex(value))
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tag_data):
        pass


def SignatureType(tagData, tagSignature):
    tag = Text(tagData[8:12].rstrip(b"\0"))
    tag.tagData = tagData
    tag.tagSignature = tagSignature
    return tag


class TextDescriptionType(ICCProfileTag, ADict):  # ICC v2
    def __init__(self, tagData=None, tagSignature=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.ASCII = b""
        if not tagData:
            return
        ASCIIDescriptionLength = uInt32Number(tagData[8:12])
        if ASCIIDescriptionLength:
            ASCIIDescription = tagData[12 : 12 + ASCIIDescriptionLength].strip(
                b"\0\n\r "
            )
            if ASCIIDescription:
                self.ASCII = ASCIIDescription
        unicodeOffset = 12 + ASCIIDescriptionLength
        self.unicodeLanguageCode = uInt32Number(
            tagData[unicodeOffset : unicodeOffset + 4]
        )
        unicodeDescriptionLength = uInt32Number(
            tagData[unicodeOffset + 4 : unicodeOffset + 8]
        )
        if unicodeDescriptionLength:
            if unicodeOffset + 8 + unicodeDescriptionLength * 2 > len(tagData):
                # Damn you MS. The Unicode character count should be the number of
                # double-byte characters (including trailing unicode NUL), not the
                # number of bytes as in the profiles created by Vista and later
                print(
                    f"Warning (non-critical): '{tagData[:4]}' Unicode part end points "
                    "past the tag data, assuming number of bytes instead "
                    "of number of characters for length"
                )
                unicodeDescriptionLength /= 2
            if (
                tagData[
                    unicodeOffset + 8 + unicodeDescriptionLength : unicodeOffset
                    + 8
                    + unicodeDescriptionLength
                    + 2
                ]
                == b"\0\0"
            ):
                print(
                    f"Warning (non-critical): '{tagData[:4]}' Unicode part "
                    "seems to be a single-byte string (double-byte "
                    "string expected)"
                )
                charBytes = 1  # fix for fubar'd desc
            else:
                charBytes = 2
            unicodeDescription = tagData[
                unicodeOffset + 8 : unicodeOffset
                + 8
                + (unicodeDescriptionLength) * charBytes
            ]
            try:
                if charBytes == 1:
                    unicodeDescription = str(unicodeDescription, errors="replace")
                else:
                    if unicodeDescription[:2] == b"\xfe\xff":
                        # UTF-16 Big Endian
                        if DEBUG:
                            print("UTF-16 Big endian")
                        unicodeDescription = unicodeDescription[2:]
                        if (
                            len(unicodeDescription.split(b" "))
                            == unicodeDescriptionLength - 1
                        ):
                            print(
                                f"Warning (non-critical): '{tagData[:4]}' "
                                "Unicode part starts with UTF-16 big "
                                "endian BOM, but actual contents seem "
                                "to be UTF-16 little endian"
                            )
                            # fix fubar'd desc
                            unicodeDescription = str(
                                b"\0".join(unicodeDescription.split(b" ")),
                                "utf-16-le",
                                errors="replace",
                            )
                        else:
                            unicodeDescription = str(
                                unicodeDescription, "utf-16-be", errors="replace"
                            )
                    elif unicodeDescription[:2] == b"\xff\xfe":
                        # UTF-16 Little Endian
                        if DEBUG:
                            print("UTF-16 Little endian")
                        unicodeDescription = unicodeDescription[2:]
                        if unicodeDescription[0] == b"\0":
                            print(
                                f"Warning (non-critical): '{tagData[:4]}' "
                                "Unicode part starts with UTF-16 "
                                "little endian BOM, but actual "
                                "contents seem to be UTF-16 big "
                                "endian"
                            )
                            # fix fubar'd desc
                            unicodeDescription = str(
                                unicodeDescription, "utf-16-be", errors="replace"
                            )
                        else:
                            unicodeDescription = str(
                                unicodeDescription, "utf-16-le", errors="replace"
                            )
                    else:
                        if DEBUG:
                            print("ASSUMED UTF-16 Big Endian")
                        unicodeDescription = str(
                            unicodeDescription, "utf-16-be", errors="replace"
                        )
                unicodeDescription = unicodeDescription.strip("\0\n\r ")
                if unicodeDescription:
                    if unicodeDescription.find("\0") < 0:
                        self.Unicode = unicodeDescription
                    else:
                        print(
                            "Error (non-critical): could not decode "
                            f"'{tagData[:4]}' Unicode part - null byte(s) "
                            "encountered"
                        )
            except UnicodeDecodeError:
                print(
                    "UnicodeDecodeError (non-critical): could not "
                    f"decode '{tagData[:4]}' Unicode part"
                )
        else:
            charBytes = 1
        macOffset = unicodeOffset + 8 + unicodeDescriptionLength * charBytes
        self.macScriptCode = 0
        if len(tagData) > macOffset + 2:
            self.macScriptCode = uInt16Number(tagData[macOffset : macOffset + 2])
            macDescriptionLength = ord(tagData[macOffset + 2 : macOffset + 3])
            if macDescriptionLength:
                try:
                    macDescription = str(
                        tagData[macOffset + 3 : macOffset + 3 + macDescriptionLength],
                        "mac-" + ENCODINGS["mac"][self.macScriptCode],
                        errors="replace",
                    ).strip("\0\n\r ")
                    if macDescription:
                        self.Macintosh = macDescription
                except KeyError:
                    print(
                        f"KeyError (non-critical): could not decode '{tagData[:4]}' "
                        f"Macintosh part (unsupported encoding {self.macScriptCode})"
                    )
                except LookupError:
                    print(
                        f"LookupError (non-critical): could not decode '{tagData[:4]}' "
                        "Macintosh part (unsupported encoding "
                        f"'{ENCODINGS['mac'][self.macScriptCode]}')"
                    )
                except UnicodeDecodeError:
                    print(
                        "UnicodeDecodeError (non-critical): could not decode "
                        f"'{tagData[:4]}' Macintosh part"
                    )

    @property
    def tagData(self):
        """Return raw tag data."""
        tagData = [
            b"desc",
            b"\0" * 4,
            uInt32Number_tohex(len(self.ASCII) + 1),  # count of ASCII chars + 1
            self.ASCII + b"\0",  # ASCII desc, \0 terminated
            uInt32Number_tohex(self.get("unicodeLanguageCode", 0)),
        ]
        if "Unicode" in self:
            tagData.extend(
                [
                    uInt32Number_tohex(
                        len(self.Unicode) + 2
                    ),  # count of Unicode chars + 2 (UTF-16-BE BOM + trailing UTF-16 NUL, 1 char = 2 byte)
                    b"\xfe\xff" + self.Unicode.encode("utf-16-be", "replace") + b"\0\0",
                ]
            )  # Unicode desc, \0\0 terminated
        else:
            tagData.append(uInt32Number_tohex(0))  # Unicode desc length = 0
        tagData.append(uInt16Number_tohex(self.get("macScriptCode", 0)))
        if "Macintosh" in self:
            macDescription = self.Macintosh[:66]
            tagData.extend(
                [
                    uInt8Number_tohex(
                        len(macDescription) + 1
                    ),  # count of Macintosh chars + 1
                    macDescription.encode(
                        "mac-" + ENCODINGS["mac"][self.get("macScriptCode", 0)],
                        "replace",
                    )
                    + (b"\0" * (67 - len(macDescription))),
                ]
            )
        else:
            tagData.extend([b"\0", b"\0" * 67])  # Mac desc length = 0
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass

    def __str__(self):
        if "Unicode" not in self and len(str(self.ASCII)) < 67:
            # Do not use Macintosh description if ASCII length >= 67
            localizedTypes = ("Macintosh", "ASCII")
        else:
            localizedTypes = ("Unicode", "ASCII")
        for localizedType in localizedTypes:
            if localizedType in self:
                value = self[localizedType]
                if not isinstance(value, str):
                    # Even ASCII description may contain non-ASCII chars, so
                    # assume system encoding and convert to unicode, replacing
                    # unknown chars
                    value = value.decode("utf-8", "replace")
                return value


def TextType(tagData, tagSignature):
    tag = Text(tagData[8:].rstrip(b"\0"))
    tag.tagData = tagData
    tag.tagSignature = tagSignature
    return tag


class VideoCardGammaType(ICCProfileTag, ADict):
    # Private tag
    # http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473

    def __init__(self, tagData, tagSignature):
        ICCProfileTag.__init__(self, tagData, tagSignature)

    def is_linear(self, r=True, g=True, b=True):
        r_points, g_points, b_points, linear_points = self.get_values()
        if (
            (r and g and b and r_points == g_points == b_points)
            or (r and g and r_points == g_points)
            or not (g or b)
        ):
            points = r_points
        elif (
            (r and b and r_points == b_points)
            or (g and b and g_points == b_points)
            or not (r or g)
        ):
            points = b_points
        elif g:
            points = g_points
        return points == linear_points

    def get_unique_values(self, r=True, g=True, b=True):
        r_points, g_points, b_points, linear_points = self.get_values()
        r_unique = set(round(y) for x, y in r_points)
        g_unique = set(round(y) for x, y in g_points)
        b_unique = set(round(y) for x, y in b_points)
        return r_unique, g_unique, b_unique

    def get_values(self, r=True, g=True, b=True):
        r_points = []
        g_points = []
        b_points = []
        linear_points = []
        vcgt = self
        if "data" in vcgt:  # table
            data = list(vcgt["data"])
            while len(data) < 3:
                data.append(data[0])
            irange = list(range(0, vcgt["entryCount"]))
            vmax = math.pow(256, vcgt["entrySize"]) - 1
            for i in irange:
                j = i * (255.0 / (vcgt["entryCount"] - 1))
                linear_points.append(
                    [j, int(round(i / float(vcgt["entryCount"] - 1) * 65535))]
                )
                if r:
                    n = int(round(float(data[0][i]) / vmax * 65535))
                    r_points.append([j, n])
                if g:
                    n = int(round(float(data[1][i]) / vmax * 65535))
                    g_points.append([j, n])
                if b:
                    n = int(round(float(data[2][i]) / vmax * 65535))
                    b_points.append([j, n])
        else:  # formula
            irange = list(range(0, 256))
            step = 100.0 / 255.0
            for i in irange:
                linear_points.append([i, i / 255.0 * 65535])
                if r:
                    vmin = vcgt["redMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["redGamma"])
                    vmax = vcgt["redMax"] * 65535
                    r_points.append([i, int(round(vmin + v * (vmax - vmin)))])
                if g:
                    vmin = vcgt["greenMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["greenGamma"])
                    vmax = vcgt["greenMax"] * 65535
                    g_points.append([i, int(round(vmin + v * (vmax - vmin)))])
                if b:
                    vmin = vcgt["blueMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["blueGamma"])
                    vmax = vcgt["blueMax"] * 65535
                    b_points.append([i, int(round(vmin + v * (vmax - vmin)))])
        return r_points, g_points, b_points, linear_points

    def printNormalizedValues(self, amount=None, digits=12):
        """Normalizes and prints all values in the vcgt (range of 0.0...1.0).

        For a 256-entry table with linear values from 0 to 65535:
        #   REF            C1             C2             C3
        001 0.000000000000 0.000000000000 0.000000000000 0.000000000000
        002 0.003921568627 0.003921568627 0.003921568627 0.003921568627
        003 0.007843137255 0.007843137255 0.007843137255 0.007843137255
        ...
        You can also specify the amount of values to print (where a value
        lesser than the entry count will leave out intermediate values)
        and the number of digits.

        """
        if amount is None:
            if hasattr(self, "entryCount"):
                amount = self.entryCount
            else:
                amount = 256  # common value
        values = self.getNormalizedValues(amount)
        entryCount = len(values)
        channels = len(values[0])
        header = ["REF"]
        for k in range(channels):
            header.append("C" + str(k + 1))
        header = [title.ljust(digits + 2) for title in header]
        print("#".ljust(len(str(amount)) + 1) + " ".join(header))
        for i, value in enumerate(values):
            formatted_values = [
                str(round(channel, digits)).ljust(digits + 2, "0") for channel in value
            ]
            print(
                str(i + 1).rjust(len(str(amount)), "0"),
                str(round(i / float(entryCount - 1), digits)).ljust(digits + 2, "0"),
                " ".join(formatted_values),
            )


class VideoCardGammaFormulaType(VideoCardGammaType):
    def __init__(self, tagData, tagSignature):
        VideoCardGammaType.__init__(self, tagData, tagSignature)
        data = tagData[12:]
        self.update(
            {
                "redGamma": u16Fixed16Number(data[0:4]),
                "redMin": u16Fixed16Number(data[4:8]),
                "redMax": u16Fixed16Number(data[8:12]),
                "greenGamma": u16Fixed16Number(data[12:16]),
                "greenMin": u16Fixed16Number(data[16:20]),
                "greenMax": u16Fixed16Number(data[20:24]),
                "blueGamma": u16Fixed16Number(data[24:28]),
                "blueMin": u16Fixed16Number(data[28:32]),
                "blueMax": u16Fixed16Number(data[32:36]),
            }
        )

    def getNormalizedValues(self, amount=None):
        if amount is None:
            amount = 256  # common value
        step = 1.0 / float(amount - 1)
        rgb = AODict([("red", []), ("green", []), ("blue", [])])
        for i in range(0, amount):
            for key in rgb:
                rgb[key].append(
                    float(self[key + "Min"])
                    + math.pow(step * i / 1.0, float(self[key + "Gamma"]))
                    * float(self[key + "Max"] - self[key + "Min"])
                )
        return list(zip(*list(rgb.values())))

    def getTableType(self, entryCount=256, entrySize=2, quantizer=round):
        """Return gamma as table type."""
        maxValue = math.pow(256, entrySize) - 1
        tagData = [
            self.tagData[:8],
            uInt32Number_tohex(0),  # type 0 = table
            uInt16Number_tohex(3),  # channels
            uInt16Number_tohex(entryCount),
            uInt16Number_tohex(entrySize),
        ]
        int2hex = {
            1: uInt8Number_tohex,
            2: uInt16Number_tohex,
            4: uInt32Number_tohex,
            8: uInt64Number_tohex,
        }
        for key in ("red", "green", "blue"):
            for i in range(0, entryCount):
                vmin = float(self[key + "Min"])
                vmax = float(self[key + "Max"])
                gamma = float(self[key + "Gamma"])
                v = vmin + math.pow(1.0 / (entryCount - 1) * i, gamma) * float(
                    vmax - vmin
                )
                tagData.append(int2hex[entrySize](quantizer(v * maxValue)))
        return VideoCardGammaTableType(b"".join(tagData), self.tagSignature)


class VideoCardGammaTableType(VideoCardGammaType):
    def __init__(self, tagData, tagSignature):
        VideoCardGammaType.__init__(self, tagData, tagSignature)
        if not tagData:
            self.update({"channels": 0, "entryCount": 0, "entrySize": 0, "data": []})
            return
        data = tagData[12:]
        channels = uInt16Number(data[0:2])
        entryCount = uInt16Number(data[2:4])
        entrySize = uInt16Number(data[4:6])
        self.update(
            {
                "channels": channels,
                "entryCount": entryCount,
                "entrySize": entrySize,
                "data": [],
            }
        )
        hex2int = {1: uInt8Number, 2: uInt16Number, 4: uInt32Number, 8: uInt64Number}
        if entrySize not in hex2int:
            raise ValueError(
                f"Invalid VideoCardGammaTableType entry size {int(entrySize):d}"
            )
        i = 0
        while i < channels:
            self.data.append([])
            j = 0
            while j < entryCount:
                index = 6 + i * entryCount * entrySize + j * entrySize
                self.data[i].append(hex2int[entrySize](data[index : index + entrySize]))
                j = j + 1
            i = i + 1

    def getNormalizedValues(self, amount=None):
        if amount is None:
            amount = self.entryCount
        maxValue = math.pow(256, self.entrySize) - 1
        values = list(
            zip(*[[entry / maxValue for entry in channel] for channel in self.data])
        )
        if amount <= self.entryCount:
            step = self.entryCount / float(amount - 1)
            all = values
            values = []
            for i, value in enumerate(all):
                if i == 0 or (i + 1) % step < 1 or i + 1 == self.entryCount:
                    values.append(value)
        return values

    def getFormulaType(self):
        """Return formula representing gamma value at 50% input."""
        maxValue = math.pow(256, self.entrySize) - 1
        tagData = [self.tagData[:8], uInt32Number_tohex(1)]  # type 1 = formula
        data = list(self.data)
        while len(data) < 3:
            data.append(data[0])
        for channel in data:
            channel_length = (len(channel) - 1) / 2.0
            floor = float(channel[int(math.floor(channel_length))])
            ceil = float(channel[int(math.ceil(channel_length))])
            vmin = channel[0] / maxValue
            vmax = channel[-1] / maxValue
            v = (vmin + ((floor + ceil) / 2.0) * (vmax - vmin)) / maxValue
            gamma = math.log(v) / math.log(0.5)
            print(vmin, gamma, vmax)
            tagData.append(u16Fixed16Number_tohex(gamma))
            tagData.append(u16Fixed16Number_tohex(vmin))
            tagData.append(u16Fixed16Number_tohex(vmax))
        return VideoCardGammaFormulaType(b"".join(tagData), self.tagSignature)

    def quantize(self, bits=16, quantizer=round):
        """Quantize to n bits of precision.

        Note that when the quantize bits are not 8, 16, 32 or 64, double
        quantization will occur: First from the table precision bits according
        to entrySize to the chosen quantization bits, and then back to the
        table precision bits.

        """
        oldmax = math.pow(256, self.entrySize) - 1
        if bits in (8, 16, 32, 64):
            self.entrySize = int(bits / 8)
        bitv = 2.0**bits
        newmax = math.pow(256, self.entrySize) - 1
        for _i, channel in enumerate(self.data):
            for j, value in enumerate(channel):
                channel[j] = int(quantizer(value / oldmax * bitv) / bitv * newmax)

    def resize(self, length=128):
        data = [[], [], []]
        for i, channel in enumerate(self.data):
            for j in range(0, length):
                j *= (len(channel) - 1) / float(length - 1)
                if int(j) != j:
                    floor = channel[int(math.floor(j))]
                    ceil = channel[min(int(math.ceil(j)), len(channel) - 1)]
                    interpolated = range(floor, ceil + 1)
                    fraction = j - int(j)
                    index = int(round(fraction * (ceil - floor)))
                    v = interpolated[index]
                else:
                    v = channel[int(j)]
                data[i].append(v)
        self.data = data
        self.entryCount = len(data[0])

    def resized(self, length=128):
        resized = self.__class__(self.tagData, self.tagSignature)
        resized.resize(length)
        return resized

    def smooth_cr(self, length=64):
        """Smooth video LUT curves (Catmull-Rom)."""
        resized = self.resized(length)
        for i in range(0, len(self.data)):
            step = float(length - 1) / (len(self.data[i]) - 1)
            interpolation = CRInterpolation(resized.data[i])
            for j in range(0, len(self.data[i])):
                self.data[i][j] = interpolation(j * step)

    def smooth_avg(self, passes=1, window=None):
        """Smooth video LUT curves (moving average).

        passses   Number of passes
        window    Tuple or list containing weighting factors. Its length
                  determines the size of the window to use.
                  Defaults to (1.0, 1.0, 1.0)

        """
        for i, channel in enumerate(self.data):
            self.data[i] = colormath.smooth_avg(channel, passes, window)
        self.entryCount = len(self.data[0])

    @property
    def tagData(self):
        """Return raw tag data."""
        tagData = [
            b"vcgt",
            b"\0" * 4,
            uInt32Number_tohex(0),  # type 0 = table
            uInt16Number_tohex(len(self.data)),  # channels
            uInt16Number_tohex(self.entryCount),
            uInt16Number_tohex(self.entrySize),
        ]
        int2hex = {
            1: uInt8Number_tohex,
            2: uInt16Number_tohex,
            4: uInt32Number_tohex,
            8: uInt64Number_tohex,
        }
        for channel in self.data:
            for i in range(0, self.entryCount):
                tagData.append(int2hex[self.entrySize](channel[i]))
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass


class ViewingConditionsType(ICCProfileTag, ADict):
    def __init__(self, tagData, tagSignature):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.update(
            {
                "illuminant": XYZNumber(tagData[8:20]),
                "surround": XYZNumber(tagData[20:32]),
                "illuminantType": Illuminant(tagData[32:36]),
            }
        )


class TagData:
    def __init__(self, tagData, offset, size):
        self.tagData = tagData
        self.offset = offset
        self.size = size

    def __contains__(self, item):
        return item in bytes(self)

    def __bytes__(self):
        return self.tagData[self.offset : self.offset + self.size]


class WcsProfilesTagType(ICCProfileTag, ADict):
    def __init__(self, tagData, tagSignature, profile):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        for i, modelname in enumerate(
            ["ColorDeviceModel", "ColorAppearanceModel", "GamutMapModel"]
        ):
            j = i * 8
            if len(tagData) < 16 + j:
                break
            offset = uInt32Number(tagData[8 + j : 12 + j])
            size = uInt32Number(tagData[12 + j : 16 + j])
            if offset and size:
                from io import StringIO
                from xml.etree import ElementTree

                it = ElementTree.iterparse(StringIO(tagData[offset : offset + size]))
                for _event, elem in it:
                    elem.tag = elem.tag.split("}", 1)[-1]  # Strip all namespaces
                self[modelname] = it.root

    def get_vcgt(self, quantize=False, quantizer=round):
        """Return calibration information (if present) as VideoCardGammaType

        If quantize is set, a table quantized to <quantize> bits is returned.

        Note that when the quantize bits are not 8, 16, 32 or 64, multiple
        quantizations will occur: For quantization bits below 32, first to 32
        bits, then to the chosen quantization bits, then back to 32 bits (which
        will be the final table precision bits).

        """
        if quantize and not isinstance(quantize, int):
            raise ValueError(f"Invalid quantization bits: {repr(quantize)}")
        if "ColorDeviceModel" in self:
            # Parse calibration information to VCGT
            cal = self.ColorDeviceModel.find("Calibration")
            if cal is None:
                return
            agammaconf = cal.find("AdapterGammaConfiguration")
            if agammaconf is None:
                return
            pcurves = agammaconf.find("ParameterizedCurves")
            if pcurves is None:
                return
            vcgtData = "vcgt"
            vcgtData += b"\0" * 4
            vcgtData += uInt32Number_tohex(1)  # Type 1 = formula
            for color in ("Red", "Green", "Blue"):
                trc = pcurves.find(color + "TRC")
                if trc is None:
                    trc = {}
                vcgtData += u16Fixed16Number_tohex(float(trc.get("Gamma", 1)))
                vcgtData += u16Fixed16Number_tohex(float(trc.get("Offset1", 0)))
                vcgtData += u16Fixed16Number_tohex(float(trc.get("Gain", 1)))
            vcgt = VideoCardGammaFormulaType(vcgtData, "vcgt")
            if quantize:
                if quantize in (8, 16, 32, 64):
                    entrySize = quantize / 8
                elif quantize < 32:
                    entrySize = 4
                else:
                    entrySize = 8
                vcgt = vcgt.getTableType(entrySize=entrySize, quantizer=quantizer)
                if quantize not in (8, 16, 32, 64):
                    vcgt.quantize(quantize, quantizer)
            return vcgt


class XYZNumber(AODict):
    """Byte
    Offset Content Encoded as...
    0..3   CIE X   s15Fixed16Number
    4..7   CIE Y   s15Fixed16Number
    8..11  CIE Z   s15Fixed16Number

    :param bytes binaryString:
    """

    def __init__(self, binaryString=b"\0" * 12):
        AODict.__init__(self)
        self.X, self.Y, self.Z = [
            s15Fixed16Number(chunk)
            for chunk in (binaryString[:4], binaryString[4:8], binaryString[8:12])
        ]

    def __repr__(self):
        XYZ = []
        for key in self:
            value = self[key]
            XYZ.append("({}, {})".format(repr(key), value))
        return "{}.{}([{}])".format(
            self.__class__.__module__,
            self.__class__.__name__,
            ", ".join(XYZ),
        )

    def adapt(
        self, whitepoint_source=None, whitepoint_destination=None, cat="Bradford"
    ):
        XYZ = self.__class__()
        XYZ.X, XYZ.Y, XYZ.Z = colormath.adapt(
            self.X, self.Y, self.Z, whitepoint_source, whitepoint_destination, cat
        )
        return XYZ

    def round(self, digits=4):
        XYZ = self.__class__()
        for key in self:
            XYZ[key] = round(self[key], digits)
        return XYZ

    def tohex(self):
        data = [s15Fixed16Number_tohex(n) for n in list(self.values())]
        return b"".join(data)

    @property
    def hex(self):
        return self.tohex()

    @property
    def Lab(self):
        return colormath.XYZ2Lab(*[v * 100 for v in list(self.values())])

    @property
    def xyY(self):
        return colormath.NumberTuple(colormath.XYZ2xyY(self.X, self.Y, self.Z))


class XYZType(ICCProfileTag, XYZNumber):
    def __init__(self, tagData=b"\0" * 20, tagSignature=None, profile=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        XYZNumber.__init__(self, tagData[8:20])
        self.profile = profile

    __repr__ = XYZNumber.__repr__

    def __setattr__(self, name, value):
        if name in ("_keys", "profile", "tagData", "tagSignature"):
            object.__setattr__(self, name, value)
        else:
            self[name] = value

    def adapt(self, whitepoint_source=None, whitepoint_destination=None, cat=None):
        if cat is None:
            if self.profile and isinstance(
                self.profile.tags.get("arts"), chromaticAdaptionTag
            ):
                cat = self.profile.tags.arts
            else:
                cat = "Bradford"
        XYZ = self.__class__(profile=self.profile)
        XYZ.X, XYZ.Y, XYZ.Z = colormath.adapt(
            self.X, self.Y, self.Z, whitepoint_source, whitepoint_destination, cat
        )
        return XYZ

    @property
    def ir(self):
        """Get illuminant-relative values"""
        pcs_illuminant = list(self.profile.illuminant.values())
        if b"chad" in self.profile.tags and self.profile.creator != b"appl":
            # Apple profiles have a bug where they contain a 'chad' tag,
            # but the media white is not under PCS illuminant
            if self is self.profile.tags.wtpt:
                XYZ = self.__class__(profile=self.profile)
                XYZ.X, XYZ.Y, XYZ.Z = list(self.values())
            else:
                # Go from XYZ mediawhite-relative under PCS illuminant to XYZ
                # under PCS illuminant
                if isinstance(self.profile.tags.get("arts"), chromaticAdaptionTag):
                    cat = self.profile.tags.arts
                else:
                    cat = "XYZ scaling"
                XYZ = self.adapt(
                    pcs_illuminant, list(self.profile.tags.wtpt.values()), cat=cat
                )
            # Go from XYZ under PCS illuminant to XYZ illuminant-relative
            XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad.inverted() * list(XYZ.values())
            return XYZ
        else:
            if self in (self.profile.tags.wtpt, self.profile.tags.get("bkpt")):
                # For profiles without 'chad' tag, the white/black point should
                # already be illuminant-relative
                return self
            elif "chad" in self.profile.tags:
                XYZ = self.__class__(profile=self.profile)
                # Go from XYZ under PCS illuminant to XYZ illuminant-relative
                XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad.inverted() * list(
                    self.values()
                )
                return XYZ
            else:
                # Go from XYZ under PCS illuminant to XYZ illuminant-relative
                return self.adapt(pcs_illuminant, list(self.profile.tags.wtpt.values()))

    @property
    def pcs(self):
        """Get PCS-relative values"""
        if self in (self.profile.tags.wtpt, self.profile.tags.get("bkpt")) and (
            "chad" not in self.profile.tags or self.profile.creator == b"appl"
        ):
            # Apple profiles have a bug where they contain a 'chad' tag,
            # but the media white is not under PCS illuminant
            if "chad" in self.profile.tags:
                XYZ = self.__class__(profile=self.profile)
                XYZ.X, XYZ.Y, XYZ.Z = self.profile.tags.chad * list(self.values())
                return XYZ
            pcs_illuminant = list(self.profile.illuminant.values())
            return self.adapt(list(self.profile.tags.wtpt.values()), pcs_illuminant)
        else:
            # Values should already be under PCS illuminant
            return self

    @property
    def tagData(self):
        """Return raw tag data."""
        tagData = [b"XYZ ", b"\0" * 4]
        tagData.append(self.tohex())
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass

    @property
    def xyY(self):
        if self is self.profile.tags.get("bkpt"):
            ref = self.profile.tags.bkpt
        else:
            ref = self.profile.tags.wtpt
        return colormath.NumberTuple(
            colormath.XYZ2xyY(self.X, self.Y, self.Z, (ref.X, ref.Y, ref.Z))
        )


class chromaticAdaptionTag(colormath.Matrix3x3, s15Fixed16ArrayType):
    def __init__(self, tagData=None, tagSignature=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        if tagData:
            data = tagData[8:]
            if data:
                matrix = []
                while data:
                    if len(matrix) == 0 or len(matrix[-1]) == 3:
                        matrix.append([])
                    matrix[-1].append(s15Fixed16Number(data[0:4]))
                    data = data[4:]
                self.update(matrix)
        else:
            self._reset()

    @property
    def tagData(self):
        """Return raw tag data."""

        tagData = [b"sf32", b"\0" * 4]
        for row in self:
            for column in row:
                tagData.append(s15Fixed16Number_tohex(column))
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass

    def get_cat(self):
        """Compare to known CAT matrices and return matching name (if any)"""

        def q(v):
            return s15Fixed16Number(s15Fixed16Number_tohex(v))

        for cat_name in colormath.cat_matrices:
            cat_matrix = colormath.cat_matrices[cat_name]
            if colormath.is_similar_matrix(self.applied(q), cat_matrix.applied(q), 4):
                return cat_name


class NamedColor2Value:
    def __init__(
        self, valueData=b"\0" * 38, deviceCoordCount=0, pcs="XYZ", device="RGB"
    ):
        self._pcsname = pcs
        self._devicename = device
        end = valueData[0:32].find(b"\0")
        if end < 0:
            end = 32
        self.rootName = valueData[0:end]
        self.pcsvalues = [
            uInt16Number(valueData[32:34]),
            uInt16Number(valueData[34:36]),
            uInt16Number(valueData[36:38]),
        ]

        self.pcs = AODict()
        for i, pcsvalue in enumerate(self.pcsvalues):
            if pcs == "Lab":
                if i == 0:
                    # L* range 0..100 + (25500 / 65280.0)
                    self.pcs[pcs[i]] = pcsvalue / 65536.0 * 256 / 255.0 * 100
                else:
                    # a, b range -128..127 + (255/256.0)
                    self.pcs[pcs[i]] = -128 + (pcsvalue / 65536.0 * 256)
            elif pcs == "XYZ":
                # X, Y, Z range 0..100 + (32767 / 32768.0)
                self.pcs[pcs[i]] = pcsvalue / 32768.0 * 100

        deviceCoords = []
        if deviceCoordCount > 0:
            for i in range(38, 38 + deviceCoordCount * 2, 2):
                deviceCoords.append(uInt16Number(valueData[i : i + 2]))
        self.devicevalues = deviceCoords
        if device == "Lab":
            # L* range 0..100 + (25500 / 65280.0)
            # a, b range range -128..127 + (255 / 256.0)
            self.device = tuple(
                (
                    v / 65536.0 * 256 / 255.0 * 100
                    if i == 0
                    else -128 + (v / 65536.0 * 256)
                )
                for i, v in enumerate(deviceCoords)
            )
        elif device == "XYZ":
            # X, Y, Z range 0..100 + (32767 / 32768.0)
            self.device = tuple(v / 32768.0 * 100 for v in deviceCoords)
        else:
            # Device range 0..100
            self.device = tuple(v / 65535.0 * 100 for v in deviceCoords)

    @property
    def name(self):
        return str(Text(self.rootName.strip(b"\0")), "latin-1")

    def __repr__(self):
        pcs = []
        dev = []
        for key in self.pcs:
            value = self.pcs[key]
            pcs.append(f"{key}={value}")
        for value in self.device:
            dev.append(f"{value}")
        return "{}({}, {{{}}}, [{}])".format(
            self.__class__.__name__,
            self.name,
            ", ".join(pcs),
            ", ".join(dev),
        )

    @property
    def tagData(self):
        """Return raw tag data."""
        valueData = []
        valueData.append(self.rootName.ljust(32, b"\0"))
        valueData.extend([uInt16Number_tohex(pcsval) for pcsval in self.pcsvalues])
        valueData.extend(
            [uInt16Number_tohex(deviceval) for deviceval in self.devicevalues]
        )
        return b"".join(valueData)

    @tagData.setter
    def tagData(self, tagData):
        pass


class NamedColor2ValueTuple(tuple):
    __slots__ = ()
    REPR_OUTPUT_SIZE = 10

    def __repr__(self):
        data = list(self[: self.REPR_OUTPUT_SIZE + 1])
        if len(data) > self.REPR_OUTPUT_SIZE:
            data[-1] = "...(remaining elements truncated)..."
        return repr(data)

    @property
    def tagData(self):
        """Return raw tag data."""
        return b"".join([val.tagData for val in self])

    @tagData.setter
    def tagData(self, tagData):
        pass


class NamedColor2Type(ICCProfileTag, AODict):
    REPR_OUTPUT_SIZE = 10

    def __init__(self, tagData=b"\0" * 84, tagSignature=None, pcs=None, device=None):
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)

        colorCount = uInt32Number(tagData[12:16])
        deviceCoordCount = uInt32Number(tagData[16:20])
        stride = 38 + 2 * deviceCoordCount

        self.vendorData = tagData[8:12]
        self.colorCount = colorCount
        self.deviceCoordCount = deviceCoordCount
        self._prefix = Text(tagData[20:52])
        self._suffix = Text(tagData[52:84])
        self._pcsname = pcs
        self._devicename = device

        keys = []
        values = []
        if colorCount > 0:
            start = 84
            end = start + (stride * colorCount)
            for i in range(start, end, stride):
                nc2 = NamedColor2Value(
                    tagData[i : i + stride], deviceCoordCount, pcs=pcs, device=device
                )
                keys.append(nc2.name)
                values.append(nc2)
        self.update(dict(list(zip(keys, values))))

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

    @property
    def prefix(self):
        return str(self._prefix.strip(b"\0"), "latin-1")

    @property
    def suffix(self):
        return str(self._suffix.strip(b"\0"), "latin-1")

    @property
    def colorValues(self):
        return NamedColor2ValueTuple(list(self.values()))

    def add_color(self, rootName, *deviceCoordinates, **pcsCoordinates):
        if self._pcsname == "Lab":
            keys = ["L", "a", "b"]
        elif self._pcsname == "XYZ":
            keys = ["X", "Y", "Z"]
        else:
            keys = ["X", "Y", "Z"]

        if not set(pcsCoordinates.keys()).issuperset(set(keys)):
            raise ICCProfileInvalidError(
                "Can't add namedColor2 without all 3 PCS coordinates: '{}'".format(
                    set(keys) - set(pcsCoordinates.keys())
                )
            )

        if len(deviceCoordinates) != self.deviceCoordCount:
            raise ICCProfileInvalidError(
                f"Can't add namedColor2 without all {self.deviceCoordCount} "
                f"device coordinates (called with {len(deviceCoordinates)})"
            )

        nc2value = NamedColor2Value()
        nc2value._pcsname = self._pcsname
        nc2value._devicename = self._devicename
        nc2value.rootName = rootName

        if rootName in list(self.keys()):
            raise ICCProfileInvalidError(
                f"Can't add namedColor2 with existant name: '{rootName}'"
            )

        nc2value.devicevalues = []
        nc2value.device = tuple(deviceCoordinates)
        nc2value.pcs = AODict(copy(pcsCoordinates))

        for idx, key in enumerate(keys):
            val = nc2value.pcs[key]
            if key == "L":
                nc2value.pcsvalues[idx] = val * 65536 / (256 / 255.0) / 100.0
            elif key in ("a", "b"):
                nc2value.pcsvalues[idx] = (val + 128) * 65536 / 256.0
            elif key in ("X", "Y", "Z"):
                nc2value.pcsvalues[idx] = val * 32768 / 100.0

        for idx, val in enumerate(nc2value.device):
            if self._devicename == "Lab":
                if idx == 0:
                    # L* range 0..100 + (25500 / 65280.0)
                    nc2value.devicevalues[idx] = val * 65536 / (256 / 255.0) / 100.0
                else:
                    # a, b range -128..127 + (255/256.0)
                    nc2value.devicevalues[idx] = (val + 128) * 65536 / 256.0
            elif self._devicename == "XYZ":
                # X, Y. Z range 0..100 + (32767 / 32768.0)
                nc2value.devicevalues[idx] = val * 32768 / 100.0
            else:
                # Device range 0..100
                nc2value.devicevalues[idx] = val * 65535 / 100.0

        self[nc2value.name] = nc2value

    def __repr__(self):
        data = list(self.items())[: self.REPR_OUTPUT_SIZE + 1]
        if len(data) > self.REPR_OUTPUT_SIZE:
            data[-1] = ("...", "(remaining elements truncated)")
        return repr(dict(data))

    @property
    def tagData(self):
        """Return raw tag data."""
        tagData = [
            b"ncl2",
            b"\0" * 4,
            self.vendorData,
            uInt32Number_tohex(len(list(self.items()))),
            uInt32Number_tohex(self.deviceCoordCount),
            self._prefix.ljust(32),
            self._suffix.ljust(32),
            self.colorValues.tagData,
        ]
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData):
        pass


tagSignature2Tag = {"arts": chromaticAdaptionTag, "chad": chromaticAdaptionTag}

typeSignature2Type = {
    b"chrm": ChromaticityType,
    b"clrt": ColorantTableType,
    b"curv": CurveType,
    b"desc": TextDescriptionType,  # ICC v2
    b"dict": DictType,  # ICC v2 + v4
    b"dtim": DateTimeType,
    b"meas": MeasurementType,
    b"mluc": MultiLocalizedUnicodeType,  # ICC v4
    b"mft2": LUT16Type,
    b"mmod": MakeAndModelType,  # Apple private tag
    b"ncl2": NamedColor2Type,
    b"para": ParametricCurveType,
    b"pseq": ProfileSequenceDescType,
    b"sf32": s15Fixed16ArrayType,
    b"sig ": SignatureType,
    b"text": TextType,
    b"vcgt": videoCardGamma,
    b"view": ViewingConditionsType,
    b"MS10": WcsProfilesTagType,
    b"XYZ ": XYZType,
}


class ICCProfileInvalidError(IOError):
    pass


_iccprofilecache = WeakValueDictionary()


class ICCProfile:
    """Returns a new ICCProfile object.

    Optionally initialized with a string containing binary profile data or
    a filename, or a file-like object. Also, if the 'load' keyword argument
    is False (default True), only the header will be read initially and
    loading of the tags will be deferred to when they are accessed the
    first time.
    """

    _recent = []

    def __new__(cls, profile=None, load=True, use_cache=False):
        key = None
        # the content of the profile should be passed as bytes in Python 3.
        if isinstance(profile, (str, pathlib.Path)):
            # Filename
            if not profile:
                raise ICCProfileInvalidError("Empty path given")

            if isinstance(profile, str):
                p = pathlib.Path(profile)
            else:
                p = profile

            if not p.is_file() and not p.is_absolute():
                search_paths = list(set(iccprofiles_home + iccprofiles))
                found_profile = False
                while search_paths and not found_profile:
                    search_path = pathlib.Path(search_paths.pop(0))
                    if search_path.is_dir():  # only look in to directories
                        for entry in search_path.glob(profile):
                            if entry.is_file():
                                profile = str(entry)
                                # TODO: update this to stay a Path instance after migration
                                #       to pathlib is completed
                                found_profile = True
                                break

            if use_cache:
                stat = os.stat(profile)
                key = (profile, stat.st_dev, stat.st_ino, stat.st_mtime, stat.st_size)
            else:
                key = ()
        elif isinstance(profile, bytes):
            # Binary string
            if use_cache:
                key = md5(profile).hexdigest()

        if use_cache:
            chk = _iccprofilecache.get(key)
            if chk:
                return chk

        if isinstance(key, tuple):
            # Filename
            profile = open(profile, "rb")

        self = super(ICCProfile, cls).__new__(cls)

        if use_cache and key:
            _iccprofilecache[key] = self

            # Make sure most recent three are not garbage collected
            if len(ICCProfile._recent) == 3:
                ICCProfile._recent.pop(0)
            ICCProfile._recent.append(self)

        self._key = key
        self.ID = b"\0" * 16
        self._data = b""
        self._file = None
        self._tagoffsets = []  # Original tag offsets
        self._tags = LazyLoadTagAODict(self)
        self.fileName = None
        self.is_loaded = False
        self.size = 0

        if profile is not None:
            if isinstance(profile, bytes):
                # Binary string
                data = profile
                self.is_loaded = True
            else:
                # File object
                self._file = profile
                self.fileName = self._file.name
                self._file.seek(0)
                data = self._file.read(128)
                self.close()

            if not data or len(data) < 128:
                raise ICCProfileInvalidError("Not enough data")

            if data[:5] == b"<?xml" or data[:10] == b"<\0?\0x\0m\0l\0":
                # Microsoft WCS profile
                from io import BytesIO
                from xml.etree import ElementTree

                self.fileName = None
                self._data = data
                self.load()
                data = self._data
                self._data = b""
                self.set_defaults()
                it = ElementTree.iterparse(BytesIO(data))
                try:
                    for _event, elem in it:
                        # Strip all namespaces
                        elem.tag = elem.tag.split("}", 1)[-1]
                except ElementTree.ParseError:
                    raise ICCProfileInvalidError("Invalid WCS profile")
                desc = it.root.find(b"Description")
                if desc is not None:
                    desc = desc.find(b"Text")
                    if desc is not None:
                        self.setDescription(str(desc.text, "UTF-8"))
                author = it.root.find(b"Author")
                if author is not None:
                    author = author.find(b"Text")
                    if author is not None:
                        self.setCopyright(str(author.text, "UTF-8"))
                device = it.root.find(b"RGBVirtualDevice")
                if device is not None:
                    measurement_data = device.find(b"MeasurementData")
                    if measurement_data is not None:
                        for color in (b"White", b"Red", b"Green", b"Blue", b"Black"):
                            prim = measurement_data.find(color + b"Primary")
                            if prim is None:
                                continue
                            XYZ = []
                            for component in b"XYZ":
                                try:
                                    XYZ.append(float(prim.get(component)) / 100.0)
                                except (TypeError, ValueError):
                                    raise ICCProfileInvalidError("Invalid WCS profile")
                            if color == b"White":
                                tag_name = "wtpt"
                            elif color == b"Black":
                                tag_name = "bkpt"
                            else:
                                XYZ = colormath.adapt(
                                    *XYZ,
                                    whitepoint_source=list(self.tags.wtpt.values()),
                                )
                                tag_name = color[0].lower().decode() + "XYZ"
                            tag = self.tags[tag_name] = XYZType(profile=self)
                            tag.X, tag.Y, tag.Z = XYZ
                        gamma = measurement_data.find(b"GammaOffsetGainLinearGain")
                        if gamma is None:
                            gamma = measurement_data.find(b"GammaOffsetGain")
                        if gamma is not None:
                            params = {
                                "Gamma": 1,
                                "Offset": 0,
                                "Gain": 1,
                                "LinearGain": 1,
                                "TransitionPoint": -1,
                            }
                            for att in list(params.keys()):
                                try:
                                    params[att] = float(gamma.get(att))
                                except (TypeError, ValueError):
                                    if (
                                        att not in ("LinearGain", "TransitionPoint")
                                        or gamma.tag != "GammaOffsetGain"
                                    ):
                                        raise ICCProfileInvalidError(
                                            "Invalid WCS profile"
                                        )

                            def power(a):
                                if a <= params["TransitionPoint"]:
                                    v = a / params["LinearGain"]
                                else:
                                    v = math.pow(
                                        (a + params["Offset"]) * params["Gain"],
                                        params["Gamma"],
                                    )
                                return v

                        else:
                            gamma = measurement_data.find("Gamma")
                            if gamma is not None:
                                try:
                                    power = float(gamma.get("value"))
                                except (TypeError, ValueError):
                                    raise ICCProfileInvalidError("Invalid WCS profile")
                        if gamma is not None:
                            self.set_trc_tags(True, power)
                if it.root.tag == "ColorDeviceModel":
                    ms00 = WcsProfilesTagType(b"", "MS00", self)
                    ms00["ColorDeviceModel"] = it.root
                    vcgt = ms00.get_vcgt()
                    if vcgt:
                        self.tags["vcgt"] = vcgt
                self.size = len(self.data)
                return self

            if data[36:40] != b"acsp":
                raise ICCProfileInvalidError(
                    "Profile signature mismatch - expected 'acsp', found '"
                    + data[36:40].decode("utf-8")
                    + "'"
                )

            # ICC profile
            header = data[:128]
            self.size = uInt32Number(header[0:4])
            self.preferredCMM = header[4:8]
            minorrev_bugfixrev = binascii.hexlify(header[8:12][1:2])
            self.version = float(
                "{}.{}".format(
                    header[8:12][0],
                    str(int(b"0x0" + minorrev_bugfixrev[0:1], 16))
                    + str(int(b"0x0" + minorrev_bugfixrev[1:2], 16)),
                )
            )
            self.profileClass = header[12:16]
            self.colorSpace = header[16:20].strip()
            self.connectionColorSpace = header[20:24].strip()
            try:
                self.dateTime = dateTimeNumber(header[24:36])
            except ValueError:
                raise ICCProfileInvalidError("Profile creation date/time invalid")
            self.platform = header[40:44]
            flags = uInt32Number(header[44:48])
            self.embedded = flags & 1 != 0
            self.independent = flags & 2 == 0
            deviceAttributes = uInt32Number(header[56:60])

            self.device = {
                "manufacturer": header[48:52],
                "model": header[52:56],
                "attributes": {
                    "reflective": deviceAttributes & 1 == 0,
                    "glossy": deviceAttributes & 2 == 0,
                    "positive": deviceAttributes & 4 == 0,
                    "color": deviceAttributes & 8 == 0,
                },
            }
            self.intent = uInt32Number(header[64:68])
            self.illuminant = XYZNumber(header[68:80])
            self.creator = header[80:84]
            if header[84:100] != b"\0" * 16:
                self.ID = header[84:100]

            self._data = data[: self.size]

            if load:
                _ = self.tags
        else:
            self.set_defaults()

        return self

    def set_defaults(self):
        if not hasattr(self, "version"):
            # Default to RGB display device profile
            self.preferredCMM = b"argl"
            self.version = 2.4
            self.profileClass = b"mntr"
            self.colorSpace = b"RGB"
            self.connectionColorSpace = b"XYZ"
            self.dateTime = datetime.datetime.now()
            if sys.platform == "win32":
                platform_id = b"MSFT"  # Microsoft
            elif sys.platform == "darwin":
                platform_id = b"APPL"  # Apple
            else:
                platform_id = b"*nix"
            self.platform = platform_id
            self.embedded = False
            self.independent = True
            self.device = {
                "manufacturer": b"",
                "model": b"",
                "attributes": {
                    "reflective": True,
                    "glossy": True,
                    "positive": True,
                    "color": True,
                },
            }
            self.intent = 0
            self.illuminant = XYZNumber(b"\0\0\xf6\xd6\0\x01\0\0\0\0\xd3-")  # D50
            self.creator = b"DCAL"  # DisplayCAL

    def __len__(self):
        """Return the number of tags.

        Can also be used in boolean comparisons (profiles with no tags
        evaluate to false)
        """
        return len(self.tags)

    @property
    def data(self):
        """Get raw binary profile data.

        This will re-assemble the various profile parts (header, tag table and data)
        on-the-fly.
        """
        # Assemble tag table and tag data
        tagCount = len(self.tags)
        tagTable = dict()
        tagTableSize = tagCount * 12
        tagsData = []
        tagsDataOffset = []
        tagDataOffset = 128 + 4 + tagTableSize
        tags = []
        # Order of tag table and actual tag data may be different.
        # Keep order of tags according to original offsets (if any).
        for _oOffset, tagSignature in sorted(self._tagoffsets):
            if tagSignature in self.tags:
                tags.append(tagSignature)

        # Keep tag table order
        for tagSignature in self.tags:
            tagTable[tagSignature] = tagSignature.encode()
            if tagSignature not in tags:
                tags.append(tagSignature)

        for tagSignature in tags:
            tag = AODict.__getitem__(self.tags, tagSignature)
            if isinstance(tag, ICCProfileTag):
                tagData = self.tags[tagSignature].tagData
            else:
                tagData = tag[3]
            tagDataSize = len(tagData)
            # Pad all data with binary zeros, so it lies on 4-byte boundaries
            padding = int(math.ceil(tagDataSize / 4.0)) * 4 - tagDataSize
            tagData += b"\0" * padding
            if (
                tagDataOffset,
                tagSignature,
            ) not in self._tagoffsets and tagData in tagsData:
                tagTable[tagSignature] += uInt32Number_tohex(
                    tagsDataOffset[tagsData.index(tagData)]
                )
            else:
                tagTable[tagSignature] += uInt32Number_tohex(tagDataOffset)
                tagsData.append(tagData)
                tagsDataOffset.append(tagDataOffset)
                tagDataOffset += tagDataSize + padding
            tagTable[tagSignature] += uInt32Number_tohex(tagDataSize)
        tagsData = b"".join(tagsData)
        header = self.header(tagTableSize, len(tagsData))
        data = b"".join(
            [
                header,
                uInt32Number_tohex(tagCount),
                b"".join(list(tagTable.values())),
                tagsData,
            ]
        )
        return data

    def header(self, tagTableSize, tagDataSize):
        """Profile Header"""
        # Profile size: 128 bytes header + 4 bytes tag count + tag table + data
        header = [
            uInt32Number_tohex(128 + 4 + tagTableSize + tagDataSize),
            self.preferredCMM[:4].ljust(4, b" ") if self.preferredCMM else b"\0" * 4,
            # Next three lines are ICC version
            chr(int(str(self.version).split(".")[0])).encode(),
            binascii.unhexlify((f"{self.version:.2f}").split(".")[1]),
            b"\0" * 2,
            self.profileClass[:4].ljust(4, b" "),
            self.colorSpace[:4].ljust(4, b" "),
            self.connectionColorSpace[:4].ljust(4, b" "),
            dateTimeNumber_tohex(self.dateTime),
            b"acsp",
            self.platform[:4].ljust(4, b" ") if self.platform else b"\0" * 4,
        ]

        flags = 0
        if self.embedded:
            flags += 1
        if not self.independent:
            flags += 2

        header.extend(
            [
                uInt32Number_tohex(flags),
                (
                    self.device["manufacturer"][:4].rjust(4, b"\0")
                    if self.device["manufacturer"]
                    else b"\0" * 4
                ),
                (
                    self.device["model"][:4].rjust(4, b"\0")
                    if self.device["model"]
                    else b"\0" * 4
                ),
            ]
        )
        deviceAttributes = 0
        for name, bit in {
            "reflective": 1,
            "glossy": 2,
            "positive": 4,
            "color": 8,
        }.items():
            if not self.device["attributes"][name]:
                deviceAttributes += bit
        if sys.platform == "darwin" and self.version < 4:
            # Dont't include ID under Mac OS X unless v4 profile
            # to stop pedantic ColorSync utility from complaining
            # about header padding not being null
            id = b""
        else:
            id = self.ID[:16]

        if isinstance(self._data, str):
            self._data = self._data.encode()

        header.extend(
            [
                uInt32Number_tohex(deviceAttributes) + b"\0" * 4,
                uInt32Number_tohex(self.intent),
                self.illuminant.tohex(),
                self.creator[:4].ljust(4, b" ") if self.creator else b"\0" * 4,
                id.ljust(16, b"\0"),
                self._data[100:128] if len(self._data[100:128]) == 28 else b"\0" * 28,
            ]
        )

        return b"".join(header)

    @property
    def tags(self):
        """Profile Tag Table"""
        if not self._tags:
            self.load()
            if self._data and len(self._data) > 131:
                # tag table and tagged element data
                tagCount = uInt32Number(self._data[128:132])
                if DEBUG:
                    print("tagCount:", tagCount)

                tagTable = self._data[132 : 132 + tagCount * 12]
                self._tagoffsets = []
                discard_len = 0
                tags = {}
                while tagTable:
                    tag = tagTable[:12]
                    if len(tag) < 12:
                        raise ICCProfileInvalidError("Tag table is truncated")

                    tagSignature = tag[:4].decode()
                    if DEBUG:
                        print("tagSignature:", tagSignature)

                    tagDataOffset = uInt32Number(tag[4:8])
                    self._tagoffsets.append((tagDataOffset, tagSignature))
                    if DEBUG:
                        print("    tagDataOffset:", tagDataOffset)

                    tagDataSize = uInt32Number(tag[8:12])
                    if DEBUG:
                        print("    tagDataSize:", tagDataSize)

                    if tagSignature in self._tags:
                        print(
                            f"Error (non-critical): Tag '{tagSignature}' "
                            "already encountered. Skipping..."
                        )
                    else:
                        if (tagDataOffset, tagDataSize) in tags:
                            if DEBUG:
                                print(
                                    "    tagDataOffset and tagDataSize indicate shared tag"
                                )
                        else:
                            start = tagDataOffset - discard_len
                            if DEBUG:
                                print("    tagData start:", start)

                            end = tagDataOffset - discard_len + tagDataSize
                            if DEBUG:
                                print("    tagData end:", end)

                            tagData = self._data[start:end]
                            if len(tagData) < tagDataSize:
                                print(
                                    f"Warning: Tag data for tag {repr(tagSignature)} "
                                    f"is truncated (offset {int(tagDataOffset):d}, "
                                    f"expected size {int(tagDataSize):d}, "
                                    f"actual size {len(tagData):d})"
                                )
                                tagDataSize = len(tagData)
                            typeSignature = tagData[:4]
                            if len(typeSignature) < 4:
                                print(
                                    "Warning: Tag type signature for tag "
                                    f"{repr(tagSignature)} is truncated "
                                    f"(offset {int(tagDataOffset):d}, "
                                    f"size {int(tagDataSize):d})"
                                )
                                typeSignature = typeSignature.ljust(4, b" ")
                            if DEBUG:
                                print("    typeSignature:", typeSignature)
                            tags[(tagDataOffset, tagDataSize)] = (
                                typeSignature,
                                tagDataOffset,
                                tagDataSize,
                                tagData,
                            )
                        self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)]
                    tagTable = tagTable[12:]

                self._data = self._data[:128]
        return self._tags

    def calculateID(self, setID=True):
        """Calculates, sets, and returns the profile's ID (checksum).

        Calling this function always recalculates the checksum on-the-fly,
        in contrast to just accessing the ID property.

        The entire profile, based on the size field in the header, is used
        to calculate the ID after the values in the Profile Flags field
        (bytes 44 to 47), Rendering Intent field (bytes 64 to 67) and
        Profile ID field (bytes 84 to 99) in the profile header have been
        temporarily replaced with zeros.
        """
        data = self.data
        data = (
            data[:44]
            + b"\0\0\0\0"
            + data[48:64]
            + b"\0\0\0\0"
            + data[68:84]
            + b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
            + data[100:]
        )
        ID = md5(data).digest()
        if setID:
            if ID != self.ID:
                # No longer reflects original profile
                self._delfromcache()
            self.ID = ID
        return ID

    def close(self):
        """Closes the associated file object (if any)."""
        if self._file and not self._file.closed:
            self._file.close()

    def convert_iccv4_tags_to_iccv2(self, version=2.4, undo_wtpt_chad=False):
        """Convert ICCv4 parametric curve tags to ICCv2-compatible curve tags

        If desired version after conversion is < 2.4 and undo_wtpt_chad is True,
        also set whitepoint to illuinant relative values, and remove any
        chromatic adaptation tag.

        If ICC profile version is < 4 or no [rgb]TRC tags or LUT16Type tags,
        return False.
        Otherwise, convert curve tags and return True.

        """
        if self.version < 4:
            return False
        # Fail if any LUT tag is not LUT16Type as we currently
        # have not implemented conversion (which may not even
        # be possible, depending on LUT contents)
        has_lut_tags = False
        for direction in ("A2B", "B2A"):
            for tableno in range(3):
                tag = self.tags.get(f"{direction}{tableno}")
                if tag:
                    if isinstance(tag, LUT16Type):
                        has_lut_tags = True
                    else:
                        return False
        if self.has_trc_tags():
            for channel in "rgb":
                tag = self.tags[channel + "TRC"]
                if isinstance(tag, ParametricCurveType):
                    # Convert to CurveType
                    self.tags[channel + "TRC"] = tag.get_trc()
        elif not has_lut_tags:
            return False
        # Set fileName to None because our profile no longer reflects the file
        # on disk and remove from cache
        self.fileName = None
        self._delfromcache()
        if version < 2.4 and undo_wtpt_chad:
            # Set whitepoint tag to illuminant relative and remove chromatic
            # adaptation tag afterwards(!)
            self.tags.wtpt = self.tags.wtpt.ir
            if "chad" in self.tags:
                del self.tags["chad"]
        # Get all multiLocalizedUnicodeType tags
        mluc = {}
        for tagname in self.tags:
            tag = self.tags[tagname]
            if isinstance(tag, MultiLocalizedUnicodeType):
                mluc[tagname] = str(tag)
        # Set profile version
        self.version = version
        # Convert to textDescriptionType/textType (after setting version to 2.x)
        for tagname in mluc:
            unistr = mluc[tagname]
            if tagname == "cprt":
                self.setCopyright(unistr)
            else:
                self.set_localizable_desc(tagname, unistr)
        return True

    def convert_iccv2_tags_to_iccv4(self):
        """Convert ICCv2 text description tags to ICCv4 multi-localized unicode

        Also sets whitepoint to D50, and stores illuminant-relative to D50
        matrix as chromatic adaptation tag.

        If ICC profile version is >= 4, return False.
        Otherwise, convert and return True.

        After conversion, the profile version is 4.3

        """
        if self.version >= 4:
            return False
        # Set fileName to None because our profile no longer reflects the file
        # on disk and remove from cache
        self.fileName = None
        self._delfromcache()
        wtpt = list(self.tags.wtpt.ir.values())
        # Set whitepoint tag to D50
        self.tags.wtpt = self.tags.wtpt.pcs
        if "chad" not in self.tags:
            # Set chromatic adaptation matrix
            self.tags["chad"] = chromaticAdaptionTag()
            wpam = colormath.wp_adaption_matrix(
                wtpt, cat=self.tags.get("arts", "Bradford")
            )
            self.tags["chad"].update(wpam)
        # Get all textDescriptionType tags
        text = {}
        for tagname in self.tags:
            tag = self.tags[tagname]
            if tagname == "cprt" or isinstance(tag, TextDescriptionType):
                text[tagname] = str(tag)
        # Set profile version to 4.3
        self.version = 4.3
        # Convert to multiLocalizedUnicodeType (after setting version to 4.x)
        for tagname in text:
            unistr = text[tagname]
            self.set_localizable_text(tagname, unistr)
        return True

    @staticmethod
    def from_named_rgb_space(
        rgb_space_name, iccv4=False, cat="Bradford", profile_class=b"mntr"
    ):
        rgb_space = colormath.get_rgb_space(rgb_space_name)
        return ICCProfile.from_rgb_space(
            rgb_space, rgb_space_name, iccv4, cat, profile_class
        )

    @staticmethod
    def from_rgb_space(
        rgb_space, description, iccv4=False, cat="Bradford", profile_class=b"mntr"
    ):
        rx, ry = rgb_space[2:][0][:2]
        gx, gy = rgb_space[2:][1][:2]
        bx, by = rgb_space[2:][2][:2]
        wx, wy = colormath.XYZ2xyY(*rgb_space[1])[:2]
        return ICCProfile.from_chromaticities(
            rx,
            ry,
            gx,
            gy,
            bx,
            by,
            wx,
            wy,
            rgb_space[0],
            description,
            "No copyright",
            iccv4=iccv4,
            cat=cat,
            profile_class=profile_class,
        )

    @staticmethod
    def from_edid(edid, iccv4=False, cat="Bradford"):
        """Create an ICC Profile from EDID data and return it

        You may override the gamma from EDID by setting it to a list of curve
        values.

        """
        description = edid.get(
            "monitor_name", edid.get("ascii", str(edid["product_id"] or edid["hash"]))
        )
        manufacturer = edid.get("manufacturer", b"")
        manufacturer_id = edid["edid"][8:10]
        model_name = description
        model_id = edid["edid"][10:12]
        copyright = "Created from EDID"
        # Get chromaticities of primaries0
        xy = {}
        for color in ("red", "green", "blue", "white"):
            x, y = edid.get(color + "_x", 0.0), edid.get(color + "_y", 0.0)
            xy[color[0] + "x"] = x
            xy[color[0] + "y"] = y
        gamma = edid.get("gamma", 2.2)
        profile = ICCProfile.from_chromaticities(
            xy["rx"],
            xy["ry"],
            xy["gx"],
            xy["gy"],
            xy["bx"],
            xy["by"],
            xy["wx"],
            xy["wy"],
            gamma,
            description,
            copyright,
            manufacturer,
            model_name,
            manufacturer_id,
            model_id,
            iccv4,
            cat,
        )
        profile.set_edid_metadata(edid)
        spec_prefixes = "DATA_,OPENICC_"
        prefix = profile.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or spec_prefixes).split(",")
        for prefix in spec_prefixes.split(","):
            if prefix not in prefixes:
                prefixes.append(prefix)
        profile.tags.meta["prefix"] = ",".join(prefixes)
        profile.tags.meta["OPENICC_automatic_generated"] = "1"
        profile.tags.meta["DATA_source"] = "edid"
        profile.calculateID()
        return profile

    @staticmethod
    def from_chromaticities(
        rx,
        ry,
        gx,
        gy,
        bx,
        by,
        wx,
        wy,
        gamma,
        description,
        copyright,
        manufacturer=None,
        model_name=None,
        manufacturer_id=b"\0\0",
        model_id=b"\0\0",
        iccv4=False,
        cat="Bradford",
        profile_class=b"mntr",
    ):
        """Create an ICC Profile from chromaticities and return it"""
        wXYZ = colormath.xyY2XYZ(wx, wy, 1.0)
        # Calculate RGB to XYZ matrix from chromaticities and white
        mtx = colormath.rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, wXYZ)
        rgb = {"r": (1.0, 0.0, 0.0), "g": (0.0, 1.0, 0.0), "b": (0.0, 0.0, 1.0)}
        XYZ = {}
        for color in "rgb":
            # Calculate XYZ for primaries
            XYZ[color] = mtx * rgb[color]

        profile = ICCProfile.from_XYZ(
            XYZ["r"],
            XYZ["g"],
            XYZ["b"],
            wXYZ,
            gamma,
            description,
            copyright,
            manufacturer,
            model_name,
            manufacturer_id,
            model_id,
            iccv4,
            cat,
            profile_class,
        )
        return profile

    @staticmethod
    def from_XYZ(
        rXYZ,
        gXYZ,
        bXYZ,
        wXYZ,
        gamma,
        description,
        copyright,
        manufacturer=None,
        model_name=None,
        manufacturer_id=b"\0\0",
        model_id=b"\0\0",
        iccv4=False,
        cat="Bradford",
        profile_class=b"mntr",
    ):
        """Create an ICC Profile from XYZ values and return it"""
        profile = ICCProfile()
        profile.profileClass = profile_class
        D50 = colormath.get_whitepoint("D50")
        if iccv4:
            profile.version = 4.3
        elif not s15f16_is_equal(wXYZ, D50) and (
            profile.profileClass not in (b"mntr", b"prtr")
            or colormath.is_similar_matrix(
                colormath.get_cat_matrix(cat), colormath.get_cat_matrix("Bradford")
            )
        ):
            profile.version = 2.2  # Match ArgyllCMS
        profile.setDescription(description)
        profile.setCopyright(copyright)
        if manufacturer:
            profile.setDeviceManufacturerDescription(manufacturer)
        if model_name:
            profile.setDeviceModelDescription(model_name)

        profile.device["manufacturer"] = (
            b"\0\0" + manufacturer_id[1:] + manufacturer_id[:1]
        )
        profile.device["model"] = b"\0\0" + model_id[1:] + model_id[:1]
        # Add Apple-specific 'mmod' tag (TODO: need full spec)
        if manufacturer_id != b"\0\0" or model_id != b"\0\0":
            mmod = (
                b"mmod"
                + (b"\x00" * 6)
                + manufacturer_id
                + (b"\x00" * 2)
                + model_id[1:]
                + model_id[:1]
                + (b"\x00" * 4)
                + (b"\x00" * 20)
            )
            profile.tags.mmod = ICCProfileTag(mmod, "mmod")
        profile.set_wtpt(wXYZ, cat)
        profile.tags.chrm = ChromaticityType()
        profile.tags.chrm.type = 0
        for color in "rgb":
            X, Y, Z = locals()[color + "XYZ"]
            # Get chromaticity of primary
            x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
            profile.tags.chrm.channels.append((x, y))
            # Write XYZ and TRC tags (don't forget to adapt to D50)
            tagname = color + "XYZ"
            profile.tags[tagname] = XYZType(profile=profile)
            (
                profile.tags[tagname].X,
                profile.tags[tagname].Y,
                profile.tags[tagname].Z,
            ) = colormath.adapt(X, Y, Z, wXYZ, D50, cat)
            tagname = color + "TRC"
            profile.tags[tagname] = CurveType(profile=profile)
            if isinstance(gamma, (list, tuple)):
                profile.tags[tagname].extend(gamma)
            else:
                profile.tags[tagname].set_trc(gamma, 1)
        profile.calculateID()
        return profile

    def set_wtpt(self, wXYZ, cat="Bradford"):
        """Set whitepoint, 'chad' tag (if >= v2.4 profile or CAT is not Bradford
        and wtpt is not D50)
        Add ArgyllCMS 'arts' tag
        """
        self.tags.wtpt = XYZType(profile=self)
        # Compatibility: ArgyllCMS will only read 'chad' if display or
        # output profile
        if self.profileClass in (b"mntr", b"prtr") and (
            self.version >= 2.4
            or not colormath.is_similar_matrix(
                colormath.get_cat_matrix(cat), colormath.get_cat_matrix("Bradford")
            )
        ):
            # Set wtpt to D50 and store actual white -> D50 transform in chad
            # if creating ICCv4 profile or CAT is not default Bradford
            D50 = colormath.get_whitepoint("D50")
            (self.tags.wtpt.X, self.tags.wtpt.Y, self.tags.wtpt.Z) = D50
            if not s15f16_is_equal(wXYZ, D50):
                # Only create chad if actual white is not D50
                self.tags.chad = chromaticAdaptionTag()
                matrix = colormath.wp_adaption_matrix(wXYZ, D50, cat)
                self.tags.chad.update(matrix)
        else:
            # Store actual white in wtpt
            (self.tags.wtpt.X, self.tags.wtpt.Y, self.tags.wtpt.Z) = wXYZ
        self.tags.arts = chromaticAdaptionTag()
        self.tags.arts.update(colormath.get_cat_matrix(cat))

    def has_trc_tags(self):
        """Return whether the profile has [rgb]TRC tags"""
        return False not in [channel + "TRC" in self.tags for channel in "rgb"]

    def set_blackpoint(self, XYZbp):
        if "chad" not in self.tags:
            cat = self.guess_cat() or "Bradford"
            XYZbp = colormath.adapt(
                *XYZbp, whitepoint_destination=list(self.tags.wtpt.ir.values()), cat=cat
            )
        self.tags.bkpt = XYZType(tagSignature="bkpt", profile=self)
        self.tags.bkpt.X, self.tags.bkpt.Y, self.tags.bkpt.Z = XYZbp

    def apply_black_offset(
        self,
        XYZbp,
        power=40.0,
        include_A2B=True,
        set_blackpoint=True,
        logfiles=None,
        thread_abort=None,
        abortmessage="Aborted",
        include_trc=True,
    ):
        # Apply only the black point blending portion of BT.1886 mapping
        if include_A2B:
            tables = []
            for i in range(3):
                a2b = self.tags.get(f"A2B{i}")
                if isinstance(a2b, LUT16Type) and a2b not in tables:
                    a2b.apply_black_offset(XYZbp, logfiles, thread_abort, abortmessage)
                    tables.append(a2b)
        if set_blackpoint:
            self.set_blackpoint(XYZbp)
        if not self.tags.get("rTRC") or not include_trc:
            return
        rXYZ = list(self.tags.rXYZ.values())
        gXYZ = list(self.tags.gXYZ.values())
        bXYZ = list(self.tags.bXYZ.values())
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        imtx = mtx.inverted()
        for channel in "rgb":
            tag = CurveType(profile=self)
            if len(self.tags[channel + "TRC"]) == 1:
                gamma = self.tags[channel + "TRC"].get_gamma()
                tag.set_trc(gamma, 1024)
            else:
                tag.extend(self.tags[channel + "TRC"])
            self.tags[channel + "TRC"] = tag
        rgbbp_in = []
        for channel in "rgb":
            rgbbp_in.append(self.tags[f"{channel}TRC"][0] / 65535.0)
        bp_in = mtx * rgbbp_in
        if tuple(bp_in) == tuple(XYZbp):
            return
        size = len(self.tags.rTRC)
        for i in range(size):
            rgb = []
            for channel in "rgb":
                rgb.append(self.tags[f"{channel}TRC"][i] / 65535.0)
            X, Y, Z = mtx * rgb
            XYZ = colormath.blend_blackpoint(X, Y, Z, bp_in, XYZbp, power=power)
            rgb = imtx * XYZ
            for j, channel in enumerate("rgb"):
                self.tags[f"{channel}TRC"][i] = min(max(rgb[j], 0), 1) * 65535

    def set_bt1886_trc(
        self, XYZbp, outoffset=0.0, gamma=2.4, gamma_type="B", size=None
    ):
        if gamma_type in ("b", "g"):
            # Get technical gamma needed to achieve effective gamma
            gamma = colormath.xicc_tech_gamma(gamma, XYZbp[1], outoffset)
        rXYZ = list(self.tags.rXYZ.values())
        gXYZ = list(self.tags.gXYZ.values())
        bXYZ = list(self.tags.bXYZ.values())
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
        values = dict()
        for _i, channel in enumerate(("r", "g", "b")):
            self.tags[channel + "TRC"] = CurveType(profile=self)
            self.tags[channel + "TRC"].set_trc(-709, size)
            for j, v in enumerate(self.tags[channel + "TRC"]):
                if not values.get(j):
                    values[j] = []
                values[j].append(v / 65535.0)
        for i in values:
            r, g, b = values[i]
            X, Y, Z = mtx * (r, g, b)
            values[i] = bt1886.apply(X, Y, Z)
        for i in values:
            XYZ = values[i]
            rgb = mtx.inverted() * XYZ
            for j, channel in enumerate(("r", "g", "b")):
                self.tags[channel + "TRC"][i] = max(min(rgb[j] * 65535, 65535), 0)
        self.set_blackpoint(XYZbp)

    def set_dicom_trc(self, XYZbp, white_cdm2=100, size=1024):
        """Set the response to the DICOM Grayscale Standard Display Function

        This response is special in that it depends on the actual black
        and white level of the display.

        XYZbp   Black point in absolute XYZ, Y range 0.05..white_cdm2

        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_dicom_trc(XYZbp[1], white_cdm2, size)
        self.apply_black_offset(
            [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 40.0)
        )

    def set_hlg_trc(
        self,
        XYZbp=(0, 0, 0),
        white_cdm2=100,
        system_gamma=1.2,
        ambient_cdm2=5,
        maxsignal=1.0,
        size=1024,
        blend_blackpoint=True,
    ):
        """Set the response to the Hybrid Log-Gamma (HLG) function

        This response is special in that it depends on the actual black
        and white level of the display, system gamma and ambient.

        XYZbp           Black point in absolute XYZ, Y range 0..white_cdm2
        maxsignal       Set clipping point (optional)
        size            Number of steps. Recommended >= 1024

        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_hlg_trc(
                XYZbp[1], white_cdm2, system_gamma, ambient_cdm2, maxsignal, size
            )
        if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
            self.apply_black_offset(
                [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 100.0)
            )

    def set_smpte2084_trc(
        self,
        XYZbp=(0, 0, 0),
        white_cdm2=100,
        master_black_cdm2=0,
        master_white_cdm2=10000,
        use_alternate_master_white_clip=True,
        rolloff=False,
        size=1024,
        blend_blackpoint=True,
    ):
        """Set the response to the SMPTE 2084 perceptual quantizer (PQ) function

        This response is special in that it depends on the actual black
        and white level of the display.

        XYZbp           Black point in absolute XYZ, Y range 0..white_cdm2
        master_black_cdm2  (Optional) Used to normalize PQ values
        master_white_cdm2  (Optional) Used to normalize PQ values
        rolloff         BT.2390
        size            Number of steps. Recommended >= 1024

        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_smpte2084_trc(
                XYZbp[1],
                white_cdm2,
                master_black_cdm2,
                master_white_cdm2,
                use_alternate_master_white_clip,
                rolloff,
                size,
            )
        if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
            self.apply_black_offset(
                [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 100.0)
            )

    def set_trc_tags(self, identical=False, power=None):
        for channel in "rgb":
            if identical and channel != "r":
                tag = self.tags.rTRC
            else:
                tag = CurveType(profile=self)
                if power:
                    tag.set_trc(
                        power, size=1 if not callable(power) and power >= 0 else 1024
                    )
            self.tags[f"{channel}TRC"] = tag

    def set_localizable_desc(
        self, tagname, description, languagecode="en", countrycode="US"
    ):
        # Handle ICCv2 <> v4 differences and encoding
        if self.version < 4:
            self.tags[tagname] = TextDescriptionType()
            if isinstance(description, str):
                asciidesc = description.encode("ASCII", "asciize")
            else:
                asciidesc = description
            self.tags[tagname].ASCII = asciidesc
            if asciidesc != description:
                self.tags[tagname].Unicode = description
        else:
            self.set_localizable_text(tagname, description, languagecode, countrycode)

    def set_localizable_text(self, tagname, text, languagecode="en", countrycode="US"):
        # Handle ICCv2 <> v4 differences and encoding
        if self.version < 4:
            if isinstance(text, str):
                text = text.encode("ASCII", "asciize")
            self.tags[tagname] = TextType(b"text\0\0\0\0%s\0" % text, tagname)
        else:
            self.tags[tagname] = MultiLocalizedUnicodeType()
            self.tags[tagname].add_localized_string(languagecode, countrycode, text)

    def setCopyright(self, copyright, languagecode="en", countrycode="US"):
        self.set_localizable_text("cprt", copyright, languagecode, countrycode)

    def setDescription(self, description, languagecode="en", countrycode="US"):
        self.set_localizable_desc("desc", description, languagecode, countrycode)

    def setDeviceManufacturerDescription(
        self, description, languagecode="en", countrycode="US"
    ):
        self.set_localizable_desc("dmnd", description, languagecode, countrycode)

    def setDeviceModelDescription(
        self, description, languagecode="en", countrycode="US"
    ):
        self.set_localizable_desc("dmdd", description, languagecode, countrycode)

    def getCopyright(self):
        """Return profile copyright."""
        return str(self.tags.get("cprt", ""))

    def getDescription(self):
        """Return profile description."""
        return str(self.tags.get("desc", ""))

    def getDeviceManufacturerDescription(self):
        """Return device manufacturer description."""
        return str(self.tags.get("dmnd", ""))

    def getDeviceModelDescription(self):
        """Return device model description."""
        return str(self.tags.get("dmdd", ""))

    def getViewingConditionsDescription(self):
        """Return viewing conditions description."""
        return str(self.tags.get("vued", ""))

    def guess_cat(self, matrix=True):
        """Get or guess chromatic adaptation transform.

        If 'matrix' is True, and 'arts' tag is present, return actual matrix
        instead of name if no match to known matrices.

        """
        illuminant = list(self.illuminant.values())
        if isinstance(self.tags.get("chad"), chromaticAdaptionTag):
            return colormath.guess_cat(
                self.tags.chad, self.tags.chad.inverted() * illuminant, illuminant
            )
        elif isinstance(self.tags.get("arts"), chromaticAdaptionTag):
            return self.tags.arts.get_cat() or (matrix and self.tags.arts)

    def isSame(self, profile, force_calculation=False):
        """Compare the ID of profiles.

        Returns a boolean indicating if the profiles have the same ID.

        profile can be a ICCProfile instance, a binary string
        containing profile data, a filename or a file object.

        """
        if not isinstance(profile, self.__class__):
            profile = self.__class__(profile)
        if force_calculation or self.ID == b"\0" * 16:
            id1 = self.calculateID(False)
        else:
            id1 = self.ID
        if force_calculation or profile.ID == b"\0" * 16:
            id2 = profile.calculateID(False)
        else:
            id2 = profile.ID
        return id1 == id2

    def load(self):
        """Load the profile from the file object.

        Normally, you don't need to call this method, since the ICCProfile
        class automatically loads the profile when necessary (load does
        nothing if the profile was passed in as a binary string).
        """
        if not self.is_loaded and self._file:
            if self._file.closed:
                self._file = open(self._file.name, "rb")
                self._file.seek(len(self._data))
            read_size = self.size - len(self._data)
            if read_size > 0:
                self._data += self._file.read(read_size)
            self._file.close()
            self.is_loaded = True

    def print_info(self):
        print("=" * 80)
        print("ICC profile information")
        print("-" * 80)
        print("File name:", os.path.basename(self.fileName or ""))
        for label, value in self.get_info():
            if not value:
                print(label)
            else:
                print(label + ":", value)

    @staticmethod
    def add_device_info(info, device, level=1):
        """Add a device structure (see profile header) to info dict"""
        indent = " " * 4 * level
        info[f"{indent}Manufacturer"] = "0x{}".format(
            binascii.hexlify(device.get("manufacturer", b"")).upper().decode()
        )
        if (
            len(device.get("manufacturer", b"")) == 4
            and device["manufacturer"][0:2] == b"\0\0"
            and device["manufacturer"][2:4] != b"\0\0"
        ):
            mnft_id = device["manufacturer"][3:4] + device["manufacturer"][2:3]
            mnft_id = edid.parse_manufacturer_id(mnft_id)
            manufacturer = edid.get_manufacturer_name(mnft_id)  # this is str
        else:
            manufacturer = (
                re.sub(b"[^\x20-\x7e]", b"", device.get("manufacturer", b""))
            ).decode()
            if manufacturer != device.get("manufacturer"):
                manufacturer = None
            else:
                manufacturer = f"'{manufacturer.decode()}'"
        if manufacturer is not None:
            info[f"{indent}Manufacturer"] += f" {manufacturer}"
        info[indent + "Model"] = hexrepr(device.get("model", ""))
        attributes = device.get("attributes", {})
        info[indent + "Media attributes"] = ", ".join(
            [
                {True: "Reflective"}.get(attributes.get("reflective"), "Transparency"),
                {True: "Glossy"}.get(attributes.get("glossy"), "Matte"),
                {True: "Positive"}.get(attributes.get("positive"), "Negative"),
                {True: "Color"}.get(attributes.get("color"), "Black & white"),
            ]
        )

    def get_info(self):
        info = DictList()
        info["Size"] = "{:d} Bytes ({:.2f} KiB)".format(int(self.size), self.size / 1024.0)
        info["Preferred CMM"] = hexrepr(self.preferredCMM, CMMS)
        info["ICC version"] = f"{self.version}"
        info["Profile class"] = PROFILE_CLASS.get(self.profileClass, self.profileClass)
        info["Color model"] = self.colorSpace.decode()
        info["Profile connection space (PCS)"] = self.connectionColorSpace.decode()
        info["Created"] = "{:%Y-%m-%d %H:%M:%S}".format(self.dateTime)
        info["Platform"] = PLATFORM.get(self.platform, hexrepr(self.platform))
        info["Is embedded"] = {True: "Yes"}.get(self.embedded, "No")
        info["Can be used independently"] = {True: "Yes"}.get(self.independent, "No")
        info["Device"] = ""
        ICCProfile.add_device_info(info, self.device)
        info["Default rendering intent"] = {
            0: "Perceptual",
            1: "Media-relative colorimetric",
            2: "Saturation",
            3: "ICC-absolute colorimetric",
        }.get(self.intent, "Unknown")
        info["PCS illuminant XYZ"] = " ".join(
            [
                " ".join([f"{v * 100:6.2f}" for v in list(self.illuminant.values())]),
                "(xy {},".format(
                    " ".join(f"{v:6.4f}" for v in self.illuminant.xyY[:2])
                ),
                "CCT {:d}K)".format(
                    int(colormath.XYZ2CCT(*list(self.illuminant.values()))) or 0
                ),
            ]
        )
        info["Creator"] = hexrepr(self.creator, MANUFACTURERS)
        info["Checksum"] = f"0x{binascii.hexlify(self.ID).upper().decode()}"
        calculated_id = self.calculateID(False)
        if self.ID != b"\0" * 16:
            info["    Checksum OK"] = {True: "Yes"}.get(self.ID == calculated_id, "No")
        if self.ID != calculated_id:
            info["    Calculated checksum"] = (
                f"0x{binascii.hexlify(calculated_id).upper().decode()}"
            )
        for sig in self.tags:
            tag = self.tags[sig]
            name = TAGS.get(sig, f"'{sig}'")
            if isinstance(tag, chromaticAdaptionTag):
                info[name] = self.guess_cat(False) or "Unknown"
                name = "    Matrix"
                for i, row in enumerate(tag):
                    if i > 0:
                        name = "    " * 2
                    info[name] = " ".join(f"{v:6.4f}" for v in row)
            elif isinstance(tag, ChromaticityType):
                info["Chromaticity (illuminant-relative)"] = ""
                for i, channel in enumerate(tag.channels):
                    if self.colorSpace.endswith(b"CLR"):
                        colorant_name = ""
                    else:
                        colorant_name = "({}) ".format(
                            self.colorSpace[i : i + 1].decode("utf-8")
                        )
                    info[f"    Channel {i + 1:d} {colorant_name}xy"] = " ".join(
                        f"{v:6.4f}" for v in channel
                    )
            elif isinstance(tag, ColorantTableType):
                info["Colorants (PCS-relative)"] = ""
                for colorant_name in tag:
                    colorant = tag[colorant_name]
                    values = list(colorant.values())
                    if "".join(list(colorant.keys())) == "Lab":
                        values = colormath.Lab2XYZ(*values)
                    else:
                        values = [v / 100.0 for v in values]
                    XYZxy = [" ".join(f"{v:6.2f}" for v in list(colorant.values()))]
                    if values != [0, 0, 0]:
                        XYZxy.append(
                            "(xy {})".format(
                                " ".join(
                                    f"{v:6.4f}" for v in colormath.XYZ2xyY(*values)[:2]
                                )
                            )
                        )
                    colorant_name = colorant_name.decode()
                    info[
                        "    {} {}".format(
                            colorant_name, "".join(list(colorant.keys()))
                        )
                    ] = " ".join(XYZxy)
            elif isinstance(tag, ParametricCurveType):
                params = "".join(sorted(tag.params.keys()))
                tag_params = dict(list(tag.params.items()))
                for key in tag_params:
                    value = tag_params[key]
                    if key == "g":
                        value = f"{value:3.2f}"
                    else:
                        value = f"{value:.6f}"
                    value = value.rstrip("0").rstrip(".")
                    if key == "g" and "." not in value:
                        value += ".0"
                    tag_params[key] = value
                tag_params["E"] = sig[0].upper()
                if params == "g":
                    info[name] = f"Gamma {tag_params['g']}"
                else:
                    info[name] = ""
                if params == "abg":
                    info["    if ({E} >= - {b} / {a}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g})".format(**tag_params)
                    )
                    info["    if ({E} <  - {b} / {a}):".format(**tag_params)] = "Y = 0"
                elif params == "abcg":
                    info["    if ({E} >= - {b} / {a}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g}) + {c}".format(**tag_params)
                    )
                    info["    if ({E} <  - {b} / {a}):".format(**tag_params)] = (
                        f"Y = {tag_params['c']}"
                    )
                elif params == "abcdg":
                    info["    if ({E} >= {d}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g})".format(**tag_params)
                    )
                    info["    if ({E} <  {d}):".format(**tag_params)] = (
                        "Y = {c} * {E}".format(**tag_params)
                    )
                elif params == "abcdefg":
                    info["    if ({E} >= {d}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g}) + {e}".format(**tag_params)
                    )
                    info["    if ({E} <  {d}):".format(**tag_params)] = (
                        "Y = {c} * {E} + {f}".format(**tag_params)
                    )
                if params != "g":
                    tag = tag.get_trc()
                    # info["    Average gamma"] = f"{tag.get_gamma():3.2f}"
                    transfer_function = tag.get_transfer_function(
                        slice=(0, 1.0), outoffset=1.0
                    )
                    if round(transfer_function[1], 2) == 1.0:
                        value = f"{transfer_function[0][0]}"
                    else:
                        if transfer_function[1] >= 0.95:
                            value = "≈ {} (Δ {:.2%})".format(
                                transfer_function[0][0],
                                1 - transfer_function[1],
                            )
                        else:
                            value = "Unknown"
                    info["    Transfer function"] = value
            elif isinstance(tag, CurveType):
                if len(tag) == 1:
                    value = (f"{tag[0]:3.2f}").rstrip("0").rstrip(".")
                    if "." not in value:
                        value = f"{value}.0"
                    info[name] = f"Gamma {value}"
                elif len(tag):
                    info[name] = ""
                    info["    Number of entries"] = f"{len(tag):d}"
                    # info["    Average gamma"] = f"{tag.get_gamma():3.2f}"
                    transfer_function = tag.get_transfer_function(
                        slice=(0, 1.0), outoffset=1.0
                    )
                    if round(transfer_function[1], 2) == 1.0:
                        value = f"{transfer_function[0][0]}"
                    else:
                        if transfer_function[1] >= 0.95:
                            value = "≈ {} (Δ {:.2%})".format(
                                transfer_function[0][0],
                                1 - transfer_function[1],
                            )
                        else:
                            value = "Unknown"
                    info["    Transfer function"] = value
                    info["    Minimum Y"] = "{:6.4f}".format(tag[0] / 65535.0 * 100)
                    info["    Maximum Y"] = "{:6.2f}".format(tag[-1] / 65535.0 * 100)
            elif isinstance(tag, DictType):
                if sig == "meta":
                    name = "Metadata"
                else:
                    name = "Generic name-value data"
                info[name] = ""
                for key in tag:
                    record = tag.get(key)
                    value = record.get("value")
                    if value and key == "prefix":
                        value = "\n".join(value.split(","))
                    info[f"    {key}"] = value
                    elements = dict()
                    for subkey in ("display_name", "display_value"):
                        entry = record.get(subkey)
                        if isinstance(entry, MultiLocalizedUnicodeType):
                            for language in entry:
                                countries = entry[language]
                                for country in countries:
                                    value = countries[country]
                                    if country.strip("\0 "):
                                        country = f"/{country}"
                                    loc = f"{language}{country}"
                                    if loc not in elements:
                                        elements[loc] = dict()
                                    elements[loc][subkey] = value
                    for loc in elements:
                        items = elements[loc]
                        if len(items) > 1:
                            value = "{} = {}".format(*items.values())
                        elif "display_name" in items:
                            value = "{}".format(items["display_name"])
                        else:
                            value = " = {}".format(items["display_value"])
                        info[f"        {loc}"] = value
            elif isinstance(tag, LUT16Type):
                info[name] = ""
                name = "    Matrix"
                for i, row in enumerate(tag.matrix):
                    if i > 0:
                        name = "    " * 2
                    info[name] = " ".join(f"{v:6.4f}" for v in row)
                info["    Input Table"] = ""
                info["        Channels"] = f"{int(tag.input_channels_count):d}"
                info["        Number of entries per channel"] = (
                    f"{int(tag.input_entries_count):d}"
                )
                info["    Color Look Up Table"] = ""
                info["        Grid Steps"] = f"{int(tag.clut_grid_steps):d}"
                info["        Entries"] = "{:d}".format(
                    int(tag.clut_grid_steps**tag.input_channels_count)
                )
                info["    Output Table"] = ""
                info["        Channels"] = f"{int(tag.output_channels_count):d}"
                info["        Number of entries per channel"] = (
                    f"{int(tag.output_entries_count):d}"
                )
            elif isinstance(tag, MakeAndModelType):
                info[name] = ""
                manufacturer_code = tag.manufacturer
                manufacturer_name = edid.get_manufacturer_name(
                    edid.parse_manufacturer_id(manufacturer_code.ljust(2, b"\0")[:2])
                )
                info["    Manufacturer"] = "0x{} {}".format(
                    binascii.hexlify(manufacturer_code).decode("utf-8").upper(),
                    manufacturer_name or "",
                )
                info["    Model"] = "0x{}".format(
                    binascii.hexlify(tag.model).decode("utf-8").upper()
                )
            elif isinstance(tag, MeasurementType):
                info[name] = ""
                info["    Observer"] = tag.observer.description
                info["    Backing XYZ"] = " ".join(
                    f"{v:6.2f}" for v in list(tag.backing.values())
                )
                info["    Geometry"] = tag.geometry.description
                info["    Flare"] = f"{tag.flare:.2%}"
                info["    Illuminant"] = tag.illuminantType.description
            elif isinstance(tag, MultiLocalizedUnicodeType):
                info[name] = ""
                for language in tag:
                    countries = tag[language]
                    for country in countries:
                        value = countries[country]
                        country = country.decode()
                        if country.strip("\0 "):
                            country = "/" + country
                        language = language.decode()
                        info[f"    {language}{country}"] = value
            elif isinstance(tag, NamedColor2Type):
                info[name] = ""
                info["    Device color components"] = f"{int(tag.deviceCoordCount):d}"
                info["    Colors (PCS-relative)"] = (
                    f"{int(tag.colorCount):d} ({len(tag.tagData):d} Bytes) "
                )
                i = 1
                for k in tag:
                    v = tag[k]
                    pcsout = []
                    devout = []
                    for _kk in v.pcs:
                        vv = v.pcs[_kk]
                        pcsout.append(f"{vv:03.2f}")
                    for vv in v.device:
                        devout.append(f"{vv:03.2f}")
                    formatstr = (
                        f"        {{:0{len(str(tag.colorCount)):d}}} {{}}{{}}{{}}"
                    )
                    key = formatstr.format(i, tag.prefix, k, tag.suffix)
                    info[key] = "{} {}".format(
                        "".join(list(v.pcs.keys())),
                        " ".join(pcsout),
                    )
                    if self.colorSpace != self.connectionColorSpace or " ".join(
                        pcsout
                    ) != " ".join(devout):
                        info[key] += " ({} {})".format(
                            self.colorSpace, " ".join(devout)
                        )
                    i += 1
            elif isinstance(tag, ProfileSequenceDescType):
                info[name] = ""
                for i, desc in enumerate(tag):
                    info[" " * 4 + f"{i + 1:d}"] = ""
                    ICCProfile.add_device_info(info, desc, 2)
                    for desc_type in ("dmnd", "dmdd"):
                        description = str(desc[desc_type])
                        if description:
                            info[" " * 8 + TAGS[desc_type]] = description
            elif isinstance(tag, Text):
                if sig == "cprt":
                    info[name] = str(tag)
                elif sig == "ciis":
                    info[name] = CIIS.get(tag, f"'{tag}'")
                elif sig == "tech":
                    print(f"tag: {tag}")
                    print(f"type(tag): {type(tag)}")
                    info[name] = TECH.get(tag, f"'{tag}'")
                elif tag.find(b"\n") > -1 or tag.find(b"\r") > -1:
                    info[name] = f"[{len(tag):d} Bytes]"
                else:
                    info[name] = tag[: 60 - len(name)] + (
                        b"...[%i more Bytes]" % (len(tag) - (60 - len(name)))
                        if len(tag) > 60 - len(name)
                        else b""
                    )
            elif isinstance(tag, TextDescriptionType):
                if not tag.get("Unicode") and not tag.get("Macintosh"):
                    info[f"{name} (ASCII)"] = tag.ASCII.decode("utf-8")
                else:
                    info[name] = ""
                    info["    ASCII"] = tag.ASCII.decode("utf-8")
                    if tag.get("Unicode"):
                        info["    Unicode"] = tag.Unicode
                    if tag.get("Macintosh"):
                        info["    Macintosh"] = tag.Macintosh
            elif isinstance(tag, VideoCardGammaFormulaType):
                info[name] = ""
                # linear = tag.is_linear()
                # info["    Is linear"] = {0: "No", 1: "Yes"}[linear]
                for key in ("red", "green", "blue"):
                    info[f"    {key.capitalize()} gamma"] = "{:.2f}".format(
                        tag[f"{key}Gamma"]
                    )
                    info[f"    {key.capitalize()} minimum"] = "{:.2f}".format(
                        tag[f"{key}Min"]
                    )
                    info[f"    {key.capitalize()} maximum"] = "{:.2f}".format(
                        tag[f"{key}Max"]
                    )
            elif isinstance(tag, VideoCardGammaTableType):
                info[name] = ""
                info["    Bitdepth"] = f"{int(tag.entrySize * 8):d}"
                info["    Channels"] = f"{int(tag.channels):d}"
                info["    Number of entries per channel"] = f"{int(tag.entryCount):d}"
                r_points, g_points, b_points, linear_points = tag.get_values()
                points = r_points, g_points, b_points
                # if r_points == g_points == b_points == linear_points:
                # info["    Is linear".format(i)] = {True: "Yes"}.get(points[i] == linear_points, "No")
                # else:
                if True:
                    unique = tag.get_unique_values()
                    for i, channel in enumerate(tag.data):
                        scale = math.pow(2, tag.entrySize * 8) - 1
                        vmin = 0
                        vmax = scale
                        gamma = colormath.get_gamma(
                            [
                                (
                                    (len(channel) / 2 - 1)
                                    / (len(channel) - 1.0)
                                    * scale,
                                    channel[int(len(channel) / 2 - 1)],
                                )
                            ],
                            scale,
                            vmin,
                            vmax,
                            False,
                            False,
                        )
                        if gamma:
                            info[f"    Channel {i + 1} gamma at 50% input"] = (
                                f"{gamma[0]:.2f}"
                            )
                        vmin = channel[0]
                        vmax = channel[-1]
                        info[f"    Channel {i + 1} minimum"] = f"{vmin / scale:6.4%}"
                        info[f"    Channel {i + 1} maximum"] = f"{vmax / scale:6.2%}"
                        info[f"    Channel {i + 1} unique values"] = (
                            f"{len(unique[i])} @ 8 Bit"
                        )
                        info[f"    Channel {i + 1} is linear"] = "Yes" if points[i] == linear_points else "No"
            elif isinstance(tag, ViewingConditionsType):
                info[name] = ""
                info["    Illuminant"] = tag.illuminantType.description
                info["    Illuminant XYZ"] = "{} (xy {})".format(
                    " ".join(f"{v:6.2f}" for v in list(tag.illuminant.values())),
                    " ".join(f"{v:6.4f}" for v in tag.illuminant.xyY[:2]),
                )
                XYZxy = [" ".join(f"{v:6.2f}" for v in list(tag.surround.values()))]
                if list(tag.surround.values()) != [0, 0, 0]:
                    XYZxy.append(
                        "(xy {})".format(
                            " ".join(f"{v:6.4f}" for v in tag.surround.xyY[:2])
                        )
                    )
                info["    Surround XYZ"] = " ".join(XYZxy)
            elif isinstance(tag, XYZType):
                if sig == "lumi":
                    info[name] = f"{self.tags.lumi.Y:.2f} cd/m²"
                elif sig in ("bkpt", "wtpt"):
                    format = {"bkpt": "{:6.4f}", "wtpt": "{:6.2f}"}[sig]
                    info[name] = ""
                    if self.profileClass == b"mntr" and sig == "wtpt":
                        info["    Is illuminant"] = "Yes"
                    if self.profileClass != b"prtr":
                        label = "Illuminant-relative"
                    else:
                        label = "PCS-relative"
                    # if self.connectionColorSpace == "Lab" and self.profileClass == "prtr":
                    if self.profileClass == b"prtr":
                        color = [" ".join([format.format(v) for v in tag.ir.Lab])]
                        info[f"    {label} Lab"] = " ".join(color)
                    else:
                        color = [
                            " ".join(format.format(v * 100) for v in list(tag.ir.values()))
                        ]
                        if list(tag.ir.values()) != [0, 0, 0]:
                            xy = " ".join(f"{v:6.4f}" for v in tag.ir.xyY[:2])
                            color.append(f"(xy {xy})")
                            cct, delta = colormath.xy_CCT_delta(*tag.ir.xyY[:2])
                        else:
                            cct = None
                        info[f"    {label} XYZ"] = " ".join(color)
                        if cct:
                            info[f"    {label} CCT"] = f"{int(cct):d}K"
                            if delta:
                                info["        ΔE 2000 to daylight locus"] = (
                                    f"{delta['E']:.2f}"
                                )
                            kwargs = {"daylight": False}
                            cct, delta = colormath.xy_CCT_delta(
                                *tag.ir.xyY[:2], **kwargs
                            )
                            if delta:
                                info["        ΔE 2000 to blackbody locus"] = (
                                    f"{delta['E']:.2f}"
                                )
                    if "chad" in self.tags:
                        color = [
                            " ".join(format.format(v * 100) for v in list(tag.pcs.values()))
                        ]
                        if list(tag.pcs.values()) != [0, 0, 0]:
                            xy = " ".join(f"{v:6.4f}" for v in tag.pcs.xyY[:2])
                            color.append(f"(xy {xy})")
                        info["    PCS-relative XYZ"] = " ".join(color)
                        cct, delta = colormath.xy_CCT_delta(*tag.pcs.xyY[:2])
                        if cct:
                            info["    PCS-relative CCT"] = f"{int(cct):d}K"
                        # if delta:
                        #     info[u"        ΔE 2000 to daylight locus"] = f"{delta['E']:.2f}"
                        # kwargs = {"daylight": False}
                        # cct, delta = colormath.xy_CCT_delta(*tag.pcs.xyY[:2], **kwargs)
                        # if delta:
                        #     info[u"        ΔE 2000 to blackbody locus"] = f"{delta['E']:.2f}"
                else:
                    info[name] = ""
                    info["    Illuminant-relative XYZ"] = " ".join(
                        [
                            " ".join(
                                f"{v * 100:6.2f}" for v in list(tag.ir.values())
                            ),
                            "(xy {})".format(" ".join(f"{v:6.4f}" for v in tag.ir.xyY[:2])),
                        ]
                    )
                    info["    PCS-relative XYZ"] = " ".join(
                        [
                            " ".join(f"{v * 100:6.2f}" for v in list(tag.values())),
                            "(xy {})".format(" ".join(f"{v:6.4f}" for v in tag.xyY[:2])),
                        ]
                    )
            elif isinstance(tag, ICCProfileTag):
                info[name] = "'{}' [{:d} Bytes]".format(
                    tag.tagData[:4].decode(),
                    len(tag.tagData),
                )
        return info

    def get_rgb_space(self, relation="ir", gamma=None):
        tags = self.tags
        if "wtpt" not in tags:
            return False
        rgb_space = [gamma or [], list(getattr(tags.wtpt, relation).values())]
        for component in ("r", "g", "b"):
            if "{component}XYZ" not in tags or (
                not gamma
                and (
                    f"{component}TRC" not in tags
                    or not isinstance(tags[f"{component}TRC"], CurveType)
                )
            ):
                return False
            rgb_space.append(getattr(tags[f"{component}XYZ"], relation).xyY)
            if not gamma:
                if len(tags[f"{component}TRC"]) > 1:
                    rgb_space[0].append(
                        [v / 65535.0 for v in tags[f"{component}TRC"]]
                    )
                else:
                    rgb_space[0].append(tags[f"{component}TRC"][0])
        return rgb_space

    def get_chardata_bkpt(self, illuminant_relative=False):
        """Get blackpoint from embeded characterization data ('targ' tag)"""
        if isinstance(self.tags.get("targ"), Text):
            from DisplayCAL.cgats import CGATS

            ti3 = CGATS(self.tags.targ)
            if 0 in ti3:
                black = ti3[0].queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
                # May be several samples for black. Average them.
                if black:
                    XYZbp = [0, 0, 0]
                    for sample in black.values():
                        for i, component in enumerate("XYZ"):
                            if "XYZ_" + component in sample:
                                XYZbp[i] += sample["XYZ_" + component] / 100.0
                    for i in range(3):
                        XYZbp[i] /= len(black)
                    if not illuminant_relative:
                        # Adapt to D50
                        white = ti3.get_white_cie()
                        if white:
                            XYZwp = [
                                v / 100.0
                                for v in (
                                    white["XYZ_X"],
                                    white["XYZ_Y"],
                                    white["XYZ_Z"],
                                )
                            ]
                        else:
                            XYZwp = list(self.tags.wtpt.ir.values())
                        cat = self.guess_cat() or "Bradford"
                        XYZbp = colormath.adapt(
                            *XYZbp, whitepoint_source=XYZwp, cat=cat
                        )
                    return XYZbp

    def optimize(self, return_bytes_saved=False, update_ID=True):
        """Optimize the tag data so that shared tags are only recorded once.

        Return whether or not optimization was performed (not necessarily
        indicative of a reduction in profile size).
        If return_bytes_saved is True, return number of bytes saved instead
        (this sets the 'size' property of the profile to the new size).

        If update_ID is True, a non-NULL profile ID will also be updated.

        Note that for profiles created by ICCProfile (and not read from disk),
        this will always be superfluous because they are optimized by default.

        """
        numoffsets = len(self._tagoffsets)
        offsets = [
            (-(numoffsets - i), tag_sig)
            for i, (offset, tag_sig) in enumerate(sorted(self._tagoffsets))
        ]
        if self._tagoffsets != offsets:
            if return_bytes_saved:
                oldsize = len(self.data)
            # Discard original offsets
            self._tagoffsets = offsets
            if update_ID and self.ID != b"\0" * 16:
                self.calculateID()
            else:
                # No longer reflects original profile
                self._delfromcache()
            if return_bytes_saved:
                self.size = len(self.data)
                return oldsize - self.size
            return True
        return 0 if return_bytes_saved else False

    def read(self, profile):
        """Read profile from binary string, filename or file object.
        Same as self.__init__(profile)
        """
        self.__init__(profile)

    def set_edid_metadata(self, edid):
        """Sets metadata from EDID

        Key names follow the ICC meta Tag for Monitor Profiles specification
        http://www.oyranos.org/wiki/index.php?title=ICC_meta_Tag_for_Monitor_Profiles_0.1
        and the GNOME Color Manager metadata specification
        http://gitorious.org/colord/master/blobs/master/doc/metadata-spec.txt

        """
        if "meta" not in self.tags:
            self.tags.meta = DictType()
        spec_prefixes = "EDID_"
        prefix = self.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or spec_prefixes).split(",")
        for prefix in spec_prefixes.split(","):
            if prefix not in prefixes:
                prefixes.append(prefix)
        # OpenICC keys (some shared with GCM)
        self.tags.meta.update(
            (
                ("prefix", ",".join(prefixes)),
                ("EDID_mnft", edid["manufacturer_id"]),
                ("EDID_mnft_id", struct.unpack(">H", edid["edid"][8:10])[0]),
                ("EDID_model_id", edid["product_id"]),
                (
                    "EDID_date",
                    "{:04d}-T{:d}".format(
                        int(edid["year_of_manufacture"]),
                        int(edid["week_of_manufacture"])
                    ),
                ),
                ("EDID_red_x", edid["red_x"]),
                ("EDID_red_y", edid["red_y"]),
                ("EDID_green_x", edid["green_x"]),
                ("EDID_green_y", edid["green_y"]),
                ("EDID_blue_x", edid["blue_x"]),
                ("EDID_blue_y", edid["blue_y"]),
                ("EDID_white_x", edid["white_x"]),
                ("EDID_white_y", edid["white_y"]),
            )
        )
        manufacturer = edid.get("manufacturer")
        if manufacturer:
            self.tags.meta["EDID_manufacturer"] = manufacturer
        if "gamma" in edid:
            self.tags.meta["EDID_gamma"] = edid["gamma"]
        monitor_name = edid.get("monitor_name", edid.get("ascii"))
        if monitor_name:
            self.tags.meta["EDID_model"] = monitor_name
        if edid.get("serial_ascii"):
            self.tags.meta["EDID_serial"] = edid["serial_ascii"]
        elif edid.get("serial_32"):
            # don't try to convert the following ``str`` to ``bytes``.
            # the edid["serial_32"] is a huge number and bytes({int}) is not working
            # like str({int}). What it tries is to create a b"\0" * {int}.
            self.tags.meta["EDID_serial"] = str(edid["serial_32"])
        # Gnome Color Management keys
        self.tags.meta["EDID_md5"] = edid["hash"]

    def set_gamut_metadata(self, gamut_volume=None, gamut_coverage=None):
        """Set gamut volume and coverage metadata keys."""
        if gamut_volume or gamut_coverage:
            if "meta" not in self.tags:
                self.tags.meta = DictType()
            # Update meta prefix
            prefix = self.tags.meta.getvalue("prefix", b"", None)
            if isinstance(prefix, bytes):
                prefix = prefix.decode("utf-8")
            prefixes = (prefix or "GAMUT_").split(",")
            if "GAMUT_" not in prefixes:
                prefixes.append("GAMUT_")
            self.tags.meta["prefix"] = ",".join(prefixes)
            if gamut_volume:
                # Set gamut size
                self.tags.meta["GAMUT_volume"] = gamut_volume
            if gamut_coverage:
                # Set gamut coverage
                for key in gamut_coverage:
                    factor = gamut_coverage[key]
                    self.tags.meta[f"GAMUT_coverage({key})"] = factor

    def write(self, stream_or_filename=None):
        """Write profile to stream.

        This will re-assemble the various profile parts (header,
        tag table and data) on-the-fly.
        """
        if not stream_or_filename:
            if self._file:
                if not self._file.closed:
                    self.close()
            stream_or_filename = self.fileName
        if isinstance(stream_or_filename, str):
            stream = open(stream_or_filename, "wb")
            if not self.fileName:
                self.fileName = stream_or_filename
        else:
            stream = stream_or_filename
        stream.write(self.data)
        if isinstance(stream_or_filename, str):
            stream.close()

    def __getattribute__(self, name):
        if name == "write" or name.startswith("set") or name.startswith("apply"):
            # No longer reflects original profile
            self._delfromcache()
        return object.__getattribute__(self, name)

    def _delfromcache(self):
        # Make double sure to remove ourselves from the cache
        if self._key and self._key in _iccprofilecache:
            try:
                del _iccprofilecache[self._key]
            except KeyError:
                # GC was faster
                pass
