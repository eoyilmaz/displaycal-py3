#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import ICCProfile as ICCP, colormath, config, worker


config.initcfg()
srgb = config.get_data_path("ref/sRGB.icm")
if not srgb:
    raise OSError("File not found: ref/sRGB.icm")
ref = ICCP.ICCProfile(srgb)
print("sRGB:", ref.fileName)


def update_preset(name):
    print("Preset name:", name)
    pth = config.get_data_path("presets/%s.icc" % name)
    if not pth:
        print("ERROR: Preset not found")
        return False
    print("Path:", pth)
    with open(
        os.path.join(os.path.dirname(__file__), "..", "misc", "ti3", "%s.ti3" % name),
        "rb",
    ) as f:
        ti3 = f.read()
    prof = ICCP.ICCProfile(pth)
    if prof.tags.targ != ti3:
        print("Updating 'targ'...")
        prof.tags.targ = ICCP.TextType(b"text\0\0\0\0%s\0" % ti3, b"targ")
    options_dispcal, options_colprof = worker.get_options_from_profile(prof)
    trc_a2b = {"240": -240, "709": -709, "l": -3, "s": -2.4}
    t_a2b = {"t": colormath.CIEDCCT2XYZ, "T": colormath.planckianCT2XYZ}
    trc = None
    for option in options_dispcal:
        if option[0] in ("g", "G"):
            trc = trc_a2b.get(option[1:])
            if not trc:
                try:
                    trc = float(option[1:])
                except ValueError:
                    trc = False
                    print("Invalid dispcal -g parameter:", option[1:])
            if trc:
                print("dispcal -%s parameter:" % option[0], option[1:])
                print("Updating tone response curves...")
                for chan in ("r", "g", "b"):
                    prof.tags["%sTRC" % chan].set_trc(trc, 256)
                print(
                    "Transfer function:",
                    prof.tags["%sTRC" % chan].get_transfer_function()[0][0],
                )
        elif option[0] in ("t", "T") and option[1:]:
            print("dispcal -t parameter:", option[1:])
            print("Updating white point...")
            (prof.tags.wtpt.X, prof.tags.wtpt.Y, prof.tags.wtpt.Z) = t_a2b[option[0]](
                float(option[1:])
            )
        elif option[0] == "w":
            print("dispcal -w parameter:", option[1:])
            x, y = [float(v) for v in option[1:].split(",")]
            print("Updating white point...")
            (prof.tags.wtpt.X, prof.tags.wtpt.Y, prof.tags.wtpt.Z) = colormath.xyY2XYZ(
                x, y
            )
        elif option[0] in ("t", "T"):
            print("Updating white point...")
            (
                prof.tags.wtpt.X,
                prof.tags.wtpt.Y,
                prof.tags.wtpt.Z,
            ) = colormath.get_whitepoint("D65")
    for option in options_colprof:
        if option[0] == "M":
            print("Updating device model description...")
            prof.setDeviceModelDescription(option[2:].strip('"'))
    if "CIED" in prof.tags:
        print("Removing 'CIED'...")
        del prof.tags["CIED"]
    if "DevD" in prof.tags:
        print("Removing 'DevD'...")
        del prof.tags["DevD"]
    if "clrt" in prof.tags:
        print("Removing 'clrt'...")
        del prof.tags["clrt"]
    print("Setting RGB matrix column tags to reference values...")
    prof.tags.rXYZ = ref.tags.rXYZ
    prof.tags.gXYZ = ref.tags.gXYZ
    prof.tags.bXYZ = ref.tags.bXYZ
    print("Updating profile ID...")
    prof.calculateID()
    prof.write()
    print("")
    return True


def update_presets():
    presets = config.get_data_path("presets", r"\.icc$")
    for fn in presets:
        update_preset(os.path.splitext(os.path.basename(fn))[0])


if __name__ == "__main__":
    if "--help" in sys.argv[1:]:
        print("Usage: %s [ preset_name [ preset_name ] ... ]" % __file__)
    elif sys.argv[1:]:
        for name in sys.argv[1:]:
            update_preset(name)
    else:
        update_presets()
