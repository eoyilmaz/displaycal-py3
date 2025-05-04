#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from copy import deepcopy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL.colormath import (
    RGB2XYZ,
    convert_range,
    get_rgb_space,
    get_whitepoint,
    specialpow,
)
from DisplayCAL.icc_profile import (
    create_synthetic_clut_profile,
    ICCProfile,
    LUT16Type,
    XYZType,
)


def create_rendering_intent_test_profile(
    filename, add_fallback_matrix=True, generate_B2A_tables=True, swap=False
):
    desc = "Rendering Intent Test Profile"
    if not add_fallback_matrix:
        desc += " (cLUT only)"
    else:
        desc += " (cLUT + fallback matrix)"
    srgb = get_rgb_space("sRGB")
    if swap:
        rgb_space = list(srgb)
        rgb_space[2:5] = rgb_space[3], rgb_space[4], rgb_space[2]
        rgb_space = get_rgb_space(rgb_space)
    else:
        rgb_space = srgb
    clutres = 9  # Minimum 9 because we require f >= 2
    f = int(round((clutres - 1) / 4.0))
    p = create_synthetic_clut_profile(rgb_space, desc, clutres=clutres)
    tagnames = ["A2B"]
    if generate_B2A_tables:
        p.tags.B2A0.clut = []
        tagnames.append("B2A")
    else:
        del p.tags["B2A0"]
    for i in range(1, 3):
        for tagname in tagnames:
            tag0 = p.tags[tagname + "0"]
            tag = p.tags[tagname + "%i" % i] = LUT16Type()
            for component_name in ("matrix", "input", "clut", "output"):
                component = getattr(tag0, component_name)
                if component_name == "clut":
                    component = deepcopy(component)
                setattr(tag, component_name, component)
    for i in range(3):
        for tagname in tagnames:
            tag = p.tags[tagname + "%i" % i]
            if i == 0:
                # Perceptual
                RGB = (f, f, 0)
            elif i == 1:
                # Colorimetric
                RGB = (0, f, f)
            else:
                # Saturation
                RGB = (0, f, 0)
            block = 0
            for R in range(clutres):
                r = min(max(R, f), clutres - 2)
                b1 = min(max(R, f) + 1, clutres - 2)
                b2 = min(max(R - 1, f), clutres - 2)
                for G in range(clutres):
                    if tagname == "B2A":
                        tag.clut.append([])
                    for B in range(clutres):
                        if tagname == "B2A":
                            tag.clut[block].append(
                                [v / (clutres - 1.0) * 65535 for v in (R, G, B)]
                            )
                        # Everything should be good as long as primaries
                        # are sensible (otherwise, when embedded in a PNG,
                        # some programs like Firefox and XnView will ignore
                        # the profile. This doesn't happen when embedded in
                        # JPEG. Go figure...)
                        if (R, G, B) in (
                            (f, f, 0),
                            (0, f, f),
                            (0, f, 0),
                            # Magenta 64..223
                            (r, 0, r),
                            (r, 0, b1),
                            (r, 0, b2),
                            # Red 64..223
                            (r, 0, 0),
                            (r, 0, 1),
                            (r, 1, 0),
                            # CMY 255
                            (0, clutres - 1, clutres - 1),
                            (clutres - 1, 0, clutres - 1),
                            (clutres - 1, clutres - 1, 0),
                        ):
                            if (R, G, B) == (0, clutres - 1, clutres - 1):
                                # Map C -> R
                                if tagname == "B2A":
                                    triplet = (65535, 0, 0)
                                else:
                                    triplet = RGB2XYZ(1, 0, 0, scale=32768)
                            elif (R, G, B) == (clutres - 1, 0, clutres - 1):
                                # Map M -> G
                                if tagname == "B2A":
                                    triplet = (0, 65535, 0)
                                else:
                                    triplet = RGB2XYZ(0, 1, 0, scale=32768)
                            elif (R, G, B) == (clutres - 1, clutres - 1, 0):
                                # Map Y -> B
                                if tagname == "B2A":
                                    triplet = (0, 0, 65535)
                                else:
                                    triplet = RGB2XYZ(0, 0, 1, scale=32768)
                            elif (R, G, B) != RGB:
                                triplet = [0, 0, 0]
                            else:
                                if tagname == "B2A":
                                    # White RGB
                                    triplet = [65535] * 3
                                else:
                                    # White XYZ D50
                                    triplet = get_whitepoint("D50", 32768)
                            tag.clut[block][B] = triplet
                    block += 1
            tag.clut_writepng(filename[:-3] + tagname + "%i.CLUT.png" % i)
            if tagname == "A2B":
                tag.clut_writecgats(filename[:-3] + tagname + "%i.CLUT.ti3" % i)
    if add_fallback_matrix:
        srgb_icc = ICCProfile.from_rgb_space(srgb, "sRGB")
        p.tags.rTRC = srgb_icc.tags.rTRC
        p.tags.gTRC = srgb_icc.tags.gTRC
        p.tags.bTRC = srgb_icc.tags.bTRC
        # if False:  # NEVER
        #     # Don't really need this...?
        #     t = specialpow(1 / 3.0, -2.4)
        #     for i, v in enumerate(p.tags.gTRC[1:], 1):
        #         v /= 65535.0
        #         p.tags.rTRC[i] = p.tags.gTRC[i] = max(convert_range(v, t, 1, 0, 1), 0) * 65535
        #         p.tags.bTRC[i] = min(convert_range(v, 0, t, 0, 1), 1) * 65535
        p.tags.rXYZ = XYZType()  # Map red to black
        p.tags.gXYZ = XYZType()  # Map green to black
        p.tags.bXYZ = srgb_icc.tags.wtpt.pcs  # Map blue to white
    p.calculateID()
    p.write(filename)


if __name__ == "__main__":
    create_rendering_intent_test_profile(sys.argv[1], add_fallback_matrix=sys.argv[2:3])
