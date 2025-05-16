"""This module provides functions and data structures for color space
conversions between RGB and XYZ, including normalization and glare adjustments.
It defines ink tables, normalization factors, and channel mappings used in the
conversion process.
"""
import math

from DisplayCAL import colormath

# from xcolorants.c
ICX_INK_TABLE = {
    "C": [[0.12, 0.18, 0.48], [0.12, 0.18, 0.48]],
    "M": [[0.38, 0.19, 0.20], [0.38, 0.19, 0.20]],
    "Y": [[0.76, 0.81, 0.11], [0.76, 0.81, 0.11]],
    "K": [[0.01, 0.01, 0.01], [0.04, 0.04, 0.04]],
    "O": [[0.59, 0.41, 0.03], [0.59, 0.41, 0.05]],
    "R": [[0.412414, 0.212642, 0.019325], [0.40, 0.21, 0.05]],
    "G": [[0.357618, 0.715136, 0.119207], [0.11, 0.27, 0.21]],
    "B": [[0.180511, 0.072193, 0.950770], [0.11, 0.27, 0.47]],
    "W": [
        [0.950543, 1.0, 1.089303],  # D65 ?
        colormath.get_standard_illuminant("D50"),
    ],  # D50
    "LC": [[0.76, 0.89, 1.08], [0.76, 0.89, 1.08]],
    "LM": [[0.83, 0.74, 1.02], [0.83, 0.74, 1.02]],
    "LY": [[0.88, 0.97, 0.72], [0.88, 0.97, 0.72]],
    "LK": [[0.56, 0.60, 0.65], [0.56, 0.60, 0.65]],
    "MC": [[0.61, 0.81, 1.07], [0.61, 0.81, 1.07]],
    "MM": [[0.74, 0.53, 0.97], [0.74, 0.53, 0.97]],
    "MY": [[0.82, 0.93, 0.40], [0.82, 0.93, 0.40]],
    "MK": [[0.27, 0.29, 0.31], [0.27, 0.29, 0.31]],
    "LLK": [
        [0.76, 0.72, 0.65],  # Very rough - should substitute real numbers
        [0.76, 0.72, 0.65],
    ],
    "": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
}

NORMALISATION_FACTOR = {"Ynorm": 0.0}
IIX_CHANNEL_MAPPING = {"iix": {0: "R", 1: "G", 2: "B"}}

for e in range(3):
    NORMALISATION_FACTOR["Ynorm"] += ICX_INK_TABLE[IIX_CHANNEL_MAPPING["iix"][e]][0][1]
NORMALISATION_FACTOR["Ynorm"] = 1.0 / NORMALISATION_FACTOR["Ynorm"]


def XYZ_denormalize_remove_glare(X, Y, Z):
    XYZ = [X, Y, Z]
    # De-Normalise Y from 1.0, & remove black glare
    for j in range(3):
        XYZ[j] = (XYZ[j] - ICX_INK_TABLE["K"][0][j]) / (1.0 - ICX_INK_TABLE["K"][0][j])
        XYZ[j] /= NORMALISATION_FACTOR["Ynorm"]
    return tuple(XYZ)


def XYZ_normalize_add_glare(X, Y, Z):
    XYZ = [X, Y, Z]
    # Normalise Y to 1.0, & add black glare
    for j in range(3):
        XYZ[j] *= NORMALISATION_FACTOR["Ynorm"]
        XYZ[j] = XYZ[j] * (1.0 - ICX_INK_TABLE["K"][0][j]) + ICX_INK_TABLE["K"][0][j]
    return tuple(XYZ)


def RGB2XYZ(R, G, B):  # from xcolorants.c -> icxColorantLu_to_XYZ
    d = (R, G, B)
    # We assume a simple additive model with gamma
    XYZ = [0.0, 0.0, 0.0]
    for e in range(3):
        v = d[e]
        if v < 0.0:
            v = 0.0
        elif v > 1.0:
            v = 1.0
        if v <= 0.03928:
            v /= 12.92
        else:
            v = math.pow((0.055 + v) / 1.055, 2.4)  # Gamma
        for j in range(3):
            XYZ[j] += v * ICX_INK_TABLE[IIX_CHANNEL_MAPPING["iix"][e]][0][j]
    return XYZ_normalize_add_glare(*XYZ)


def XYZ2RGB(X, Y, Z):
    return colormath.XYZ2RGB(*XYZ_denormalize_remove_glare(X, Y, Z))
