#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from time import strftime
import binascii
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from DisplayCAL import colormath
from DisplayCAL.icc_profile import ICCProfile, get_display_profile, XYZType


def prettyprint(iterable, level=1):
    for key in iterable:
        value = iterable[key]
        if hasattr(value, "items"):
            print(" " * 4 * level, "%s:" % key.capitalize())
            prettyprint(value, level + 1)
        else:
            print(" " * 4 * level, "%s:" % key.capitalize(), value)


def profileinfo(profile):
    if not isinstance(profile, ICCProfile):
        profile = ICCProfile(profile)
    # Attributes
    print("Size:", profile.size, "Bytes (%.1f KB)" % (profile.size / 1024.0))
    print("Preferred CMM:", profile.preferredCMM)
    print("ICC version:", profile.version)
    print("Class:", profile.profileClass)
    print("Colorspace:", profile.colorSpace)
    print("PCS:", profile.connectionColorSpace)
    print("Date/Time:", strftime("%Y-%m-%d %H:%M:%S", profile.dateTime + (0, 0, -1)))
    print("Platform:", profile.platform)
    print("Embedded:", profile.embedded)
    print("Independent:", profile.independent)
    print("Device:")
    for key in ("manufacturer", "model"):
        profile.device[key] = binascii.hexlify(profile.device[key]).upper()
    prettyprint(profile.device)
    print("Rendering Intent:", profile.intent)
    print("Illuminant:", " ".join(str(n * 100) for n in profile.illuminant.values()))
    print("Creator:", profile.creator)
    print("ID:", binascii.hexlify(profile.ID).upper())
    # Tags
    print("Description:", profile.getDescription())
    print("Copyright:", profile.getCopyright())
    if "dmnd" in profile.tags:
        print(
            "Device Manufacturer Description:",
        )
        print(profile.getDeviceManufacturerDescription())
    if "dmdd" in profile.tags:
        print("Device Model Description:", profile.getDeviceModelDescription())
    if "vued" in profile.tags:
        print(
            "Viewing Conditions Description:",
        )
        print(profile.getViewingConditionsDescription())
    wtpt_profile_norm = tuple(n * 100 for n in profile.tags.wtpt.values())
    if "chad" in profile.tags:
        # undo chromatic adaption of profile whitepoint
        X, Y, Z = wtpt_profile_norm
        M = colormath.Matrix3x3(profile.tags.chad).inverted()
        XR = X * M[0][0] + Y * M[0][1] + Z * M[0][2]
        YR = X * M[1][0] + Y * M[1][1] + Z * M[1][2]
        ZR = X * M[2][0] + Y * M[2][1] + Z * M[2][2]
        wtpt_profile_norm = tuple((n / YR) * 100.0 for n in (XR, YR, ZR))
    if "lumi" in profile.tags and isinstance(profile.tags.lumi, XYZType):
        print("Luminance:", profile.tags.lumi.Y)
    print("Actual Whitepoint XYZ:", " ".join(str(n) for n in wtpt_profile_norm))
    print("Correlated Color Temperature:", colormath.XYZ2CCT(*wtpt_profile_norm))


if __name__ == "__main__":
    for arg in sys.argv[1:] or [get_display_profile()]:
        profileinfo(arg)
