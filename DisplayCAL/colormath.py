# -*- coding: utf-8 -*-
"""
Diverse color mathematical functions.

Note:

In most cases, unless otherwise stated RGB is R'G'B' (gamma-compressed)

"""

import colorsys
import logging
import math
import sys
import warnings


def get_transfer_function_phi(alpha, gamma):
    return (math.pow(1 + alpha, gamma) * math.pow(gamma - 1, gamma - 1)) / (
        math.pow(alpha, gamma - 1) * math.pow(gamma, gamma)
    )


LSTAR_E = 216.0 / 24389.0  # Intent of CIE standard, actual CIE standard = 0.008856
LSTAR_K = 24389.0 / 27.0  # Intent of CIE standard, actual CIE standard = 903.3
REC709_K0 = 0.081  # 0.099 / (1.0 / 0.45 - 1)
REC709_P = 4.5  # get_transfer_function_phi(0.099, 1.0 / 0.45)
SMPTE240M_K0 = 0.0913  # 0.1115 / (1.0 / 0.45 - 1)
SMPTE240M_P = 4.0  # get_transfer_function_phi(0.1115, 1.0 / 0.45)
SMPTE2084_M1 = (2610.0 / 4096) * 0.25
SMPTE2084_M2 = (2523.0 / 4096) * 128
SMPTE2084_C1 = 3424.0 / 4096
SMPTE2084_C2 = (2413.0 / 4096) * 32
SMPTE2084_C3 = (2392.0 / 4096) * 32
SRGB_K0 = 0.04045  # 0.055 / (2.4 - 1)
SRGB_P = 12.92  # get_transfer_function_phi(0.055, 2.4)


def specialpow(a, b, slope_limit=0):
    """Wrapper for power, Rec. 601/709, SMPTE 240M, sRGB and L* functions

    Positive b = power, -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
    -601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
    identical)

    """
    if b >= 0.0:
        # Power curve
        if a < 0.0:
            if slope_limit:
                return min(-math.pow(-a, b), a / slope_limit)
            return -math.pow(-a, b)
        else:
            if slope_limit:
                return max(math.pow(a, b), a / slope_limit)
            return math.pow(a, b)
    if a < 0.0:
        signScale = -1.0
        a = -a
    else:
        signScale = 1.0
    if b in (1.0 / -601, 1.0 / -709):
        # XYZ -> RGB, Rec. 601/709 TRC
        if a < REC709_K0 / REC709_P:
            v = a * REC709_P
        else:
            v = 1.099 * math.pow(a, 0.45) - 0.099
    elif b == 1.0 / -240:
        # XYZ -> RGB, SMPTE 240M TRC
        if a < SMPTE240M_K0 / SMPTE240M_P:
            v = a * SMPTE240M_P
        else:
            v = 1.1115 * math.pow(a, 0.45) - 0.1115
    elif b == 1.0 / -3.0:
        # XYZ -> RGB, L* TRC
        if a <= LSTAR_E:
            v = 0.01 * a * LSTAR_K
        else:
            v = 1.16 * math.pow(a, 1.0 / 3.0) - 0.16
    elif b == 1.0 / -2.4:
        # XYZ -> RGB, sRGB TRC
        if a <= SRGB_K0 / SRGB_P:
            v = a * SRGB_P
        else:
            v = 1.055 * math.pow(a, 1.0 / 2.4) - 0.055
    elif b == 1.0 / -2084:
        # XYZ -> RGB, SMPTE 2084 (PQ)
        v = (
            (2413.0 * (a**SMPTE2084_M1) + 107) / (2392.0 * (a**SMPTE2084_M1) + 128)
        ) ** SMPTE2084_M2
    elif b == -2.4:
        # RGB -> XYZ, sRGB TRC
        if a <= SRGB_K0:
            v = a / SRGB_P
        else:
            v = math.pow((a + 0.055) / 1.055, 2.4)
    elif b == -3.0:
        # RGB -> XYZ, L* TRC
        if a <= 0.08:  # E * K * 0.01
            v = 100.0 * a / LSTAR_K
        else:
            v = math.pow((a + 0.16) / 1.16, 3.0)
    elif b == -240:
        # RGB -> XYZ, SMPTE 240M TRC
        if a < SMPTE240M_K0:
            v = a / SMPTE240M_P
        else:
            v = math.pow((0.1115 + a) / 1.1115, 1.0 / 0.45)
    elif b in (-601, -709):
        # RGB -> XYZ, Rec. 601/709 TRC
        if a < REC709_K0:
            v = a / REC709_P
        else:
            v = math.pow((a + 0.099) / 1.099, 1.0 / 0.45)
    elif b == -2084:
        # RGB -> XYZ, SMPTE 2084 (PQ)
        # See https://www.smpte.org/sites/default/files/2014-05-06-EOTF-Miller-1-2-handout.pdf
        v = (
            max(a ** (1.0 / SMPTE2084_M2) - SMPTE2084_C1, 0)
            / (SMPTE2084_C2 - SMPTE2084_C3 * a ** (1.0 / SMPTE2084_M2))
        ) ** (1.0 / SMPTE2084_M1)
    else:
        raise ValueError("Invalid gamma %r" % b)
    return v * signScale


def DICOM(j, inverse=False):
    if inverse:
        log10Y = math.log10(j)
        A = 71.498068
        B = 94.593053
        C = 41.912053
        D = 9.8247004
        E = 0.28175407
        F = -1.1878455
        G = -0.18014349
        H = 0.14710899
        I = -0.017046845
        return (
            A
            + B * log10Y
            + C * math.pow(log10Y, 2)
            + D * math.pow(log10Y, 3)
            + E * math.pow(log10Y, 4)
            + F * math.pow(log10Y, 5)
            + G * math.pow(log10Y, 6)
            + H * math.pow(log10Y, 7)
            + I * math.pow(log10Y, 8)
        )
    else:
        logj = math.log(j)
        a = -1.3011877
        b = -2.5840191e-2
        c = 8.0242636e-2
        d = -1.0320229e-1
        e = 1.3646699e-1
        f = 2.8745620e-2
        g = -2.5468404e-2
        h = -3.1978977e-3
        k = 1.2992634e-4
        m = 1.3635334e-3
        return (
            a
            + c * logj
            + e * math.pow(logj, 2)
            + g * math.pow(logj, 3)
            + m * math.pow(logj, 4)
        ) / (
            1
            + b * logj
            + d * math.pow(logj, 2)
            + f * math.pow(logj, 3)
            + h * math.pow(logj, 4)
            + k * math.pow(logj, 5)
        )


class HLG:
    """Hybrid Log Gamma (HLG) as defined in Rec BT.2100
    and BT.2390-4

    """

    def __init__(
        self,
        black_cdm2=0.0,
        white_cdm2=1000.0,
        system_gamma=1.2,
        ambient_cdm2=5,
        rgb_space="Rec. 2020",
    ):
        self.black_cdm2 = black_cdm2
        self.white_cdm2 = white_cdm2
        self.rgb_space = get_rgb_space(rgb_space)
        self.system_gamma = system_gamma
        self.ambient_cdm2 = ambient_cdm2

    @property
    def gamma(self):
        """System gamma for nominal peak luminance and ambient"""
        # Adjust system gamma for peak luminance != 1000 cd/m2 (extended model
        # described in BT.2390-4)
        K = 1.111
        gamma = self.system_gamma * K ** math.log(self.white_cdm2 / 1000.0, 2)
        if self.ambient_cdm2 > 0:
            # Adjust system gamma for ambient surround != 5 cd/m2 (BT.2390-4)
            u = 0.98
            gamma *= u ** math.log(self.ambient_cdm2 / 5.0, 2)
        return gamma

    def oetf(self, v, inverse=False):
        """Hybrid Log Gamma (HLG) OETF

        Relative scene linear light to non-linear HLG signal, or inverse

        Input domain 0..1
        Output range 0..1

        """
        if v == 1:
            return 1.0
        a = 0.17883277
        b = 1 - 4 * a
        c = 0.5 - a * math.log(4 * a)
        if inverse:
            # Non-linear HLG signal to relative scene linear light
            if 0 <= v <= 1 / 2.0:
                v = v**2 / 3.0
            else:
                v = (math.exp((v - c) / a) + b) / 12.0
        else:
            # Relative scene linear light to non-linear HLG signal
            if 0 <= v <= 1 / 12.0:
                v = math.sqrt(3 * v)
            else:
                v = a * math.log(12 * v - b) + c
        return v

    def eotf(self, RGB, inverse=False, apply_black_offset=True):
        """Hybrid Log Gamma (HLG) EOTF

        Non-linear HLG signal to display light, or inverse

        Input domain 0..1
        Output range 0..1

        """
        if isinstance(RGB, (float, int)):
            R, G, B = (RGB,) * 3
        else:
            R, G, B = RGB
        if inverse:
            # Display light -> relative scene linear light -> HLG signal
            R, G, B = (
                self.oetf(v) for v in self.ootf((R, G, B), True, apply_black_offset)
            )
        else:
            # HLG signal -> relative scene linear light -> display light
            R, G, B = self.ootf(
                [self.oetf(v, True) for v in (R, G, B)], False, apply_black_offset
            )
        return G if isinstance(RGB, (float, int)) else (R, G, B)

    def ootf(self, RGB, inverse=False, apply_black_offset=True):
        """Hybrid Log Gamma (HLG) OOTF

        Relative scene linear light to display light, or inverse

        Input domain 0..1
        Output range 0..1

        """
        if isinstance(RGB, (float, int)):
            R, G, B = (RGB,) * 3
        else:
            R, G, B = RGB
        if apply_black_offset:
            black_cdm2 = float(self.black_cdm2)
        else:
            black_cdm2 = 0
        alpha = (self.white_cdm2 - black_cdm2) / self.white_cdm2
        beta = black_cdm2 / self.white_cdm2
        Y = 0.2627 * R + 0.6780 * G + 0.0593 * B
        if inverse:
            if Y > beta:
                R, G, B = (
                    ((Y - beta) / alpha) ** ((1 - self.gamma) / self.gamma)
                    * ((v - beta) / alpha)
                    for v in (R, G, B)
                )
            else:
                R, G, B = 0, 0, 0
        else:
            if Y:
                Y **= self.gamma - 1
            R, G, B = (alpha * Y * E + beta for E in (R, G, B))
        return G if isinstance(RGB, (float, int)) else (R, G, B)

    def RGB2XYZ(self, R, G, B, apply_black_offset=True):
        """Non-linear HLG signal to display XYZ"""
        X, Y, Z = self.rgb_space[-1] * [self.oetf(v, True) for v in (R, G, B)]
        X, Y, Z = (max(v, 0) for v in (X, Y, Z))
        Yy = self.ootf(Y, apply_black_offset=False)
        if Y:
            X, Y, Z = (v / Y * Yy for v in (X, Y, Z))
        else:
            X, Y, Z = (v * Yy for v in self.rgb_space[1])
        if apply_black_offset:
            beta = self.ootf(0)
            bp_out = [v * beta for v in self.rgb_space[1]]
            X, Y, Z = apply_bpc(X, Y, Z, (0, 0, 0), bp_out, self.rgb_space[1])
        return X, Y, Z

    def XYZ2RGB(self, X, Y, Z, apply_black_offset=True):
        """Display XYZ to non-linear HLG signal"""
        if apply_black_offset:
            beta = self.ootf(0)
            bp_in = [v * beta for v in self.rgb_space[1]]
            X, Y, Z = apply_bpc(X, Y, Z, bp_in, (0, 0, 0), self.rgb_space[1])
        Yy = self.ootf(Y, True, apply_black_offset=False)
        if Y:
            X, Y, Z = (v / Y * Yy for v in (X, Y, Z))
        R, G, B = self.rgb_space[-1].inverted() * (X, Y, Z)
        R, G, B = (max(v, 0) for v in (R, G, B))
        R, G, B = [self.oetf(v) for v in (R, G, B)]
        return R, G, B


rgb_spaces = {
    # http://brucelindbloom.com/WorkingSpaceInfo.html
    # ACES: https://github.com/ampas/aces-dev/blob/master/docs/ACES_1.0.1.pdf?raw=true
    # Adobe RGB: http://www.adobe.com/digitalimag/pdfs/AdobeRGB1998.pdf
    # DCI P3: http://www.hp.com/united-states/campaigns/workstations/pdfs/lp2480zx-dci--p3-emulation.pdf
    #         http://dcimovies.com/specification/DCI_DCSS_v12_with_errata_2012-1010.pdf
    # Rec. 2020: http://en.wikipedia.org/wiki/Rec._2020
    #
    # name              gamma             white                     primaries
    #                                     point                     Rx      Ry      RY          Gx      Gy      GY          Bx      By      BY
    "ACES": (
        1.0,
        (0.95265, 1.0, 1.00883),
        (0.7347, 0.2653, 0.343961),
        (0.0000, 1.0000, 0.728164),
        (0.0001, -0.0770, -0.072125),
    ),
    "ACEScg": (
        1.0,
        (0.95265, 1.0, 1.00883),
        (0.7130, 0.2930, 0.272230),
        (0.1650, 0.8300, 0.674080),
        (0.1280, 0.0440, 0.053690),
    ),
    "Adobe RGB (1998)": (
        2 + 51 / 256.0,
        "D65",
        (0.6400, 0.3300, 0.297361),
        (0.2100, 0.7100, 0.627355),
        (0.1500, 0.0600, 0.075285),
    ),
    "Apple RGB": (
        1.8,
        "D65",
        (0.6250, 0.3400, 0.244634),
        (0.2800, 0.5950, 0.672034),
        (0.1550, 0.0700, 0.083332),
    ),
    "Best RGB": (
        2.2,
        "D50",
        (0.7347, 0.2653, 0.228457),
        (0.2150, 0.7750, 0.737352),
        (0.1300, 0.0350, 0.034191),
    ),
    "Beta RGB": (
        2.2,
        "D50",
        (0.6888, 0.3112, 0.303273),
        (0.1986, 0.7551, 0.663786),
        (0.1265, 0.0352, 0.032941),
    ),
    "Bruce RGB": (
        2.2,
        "D65",
        (0.6400, 0.3300, 0.240995),
        (0.2800, 0.6500, 0.683554),
        (0.1500, 0.0600, 0.075452),
    ),
    "CIE RGB": (
        2.2,
        "E",
        (0.7350, 0.2650, 0.176204),
        (0.2740, 0.7170, 0.812985),
        (0.1670, 0.0090, 0.010811),
    ),
    "ColorMatch RGB": (
        1.8,
        "D50",
        (0.6300, 0.3400, 0.274884),
        (0.2950, 0.6050, 0.658132),
        (0.1500, 0.0750, 0.066985),
    ),
    # "DCDM X'Y'Z'":      (2.6,             "E",                     (1.0000, 0.0000, 0.000000), (0.0000, 1.0000, 1.000000), (0.0000, 0.0000, 0.000000)),
    "DCI P3": (
        2.6,
        (0.89459, 1.0, 0.95442),
        (0.6800, 0.3200, 0.209475),
        (0.2650, 0.6900, 0.721592),
        (0.1500, 0.0600, 0.068903),
    ),
    "DCI P3 D65": (
        2.6,
        "D65",
        (0.6800, 0.3200, 0.209475),
        (0.2650, 0.6900, 0.721592),
        (0.1500, 0.0600, 0.068903),
    ),
    "Don RGB 4": (
        2.2,
        "D50",
        (0.6960, 0.3000, 0.278350),
        (0.2150, 0.7650, 0.687970),
        (0.1300, 0.0350, 0.033680),
    ),
    "ECI RGB": (
        1.8,
        "D50",
        (0.6700, 0.3300, 0.320250),
        (0.2100, 0.7100, 0.602071),
        (0.1400, 0.0800, 0.077679),
    ),
    "ECI RGB v2": (
        -3.0,
        "D50",
        (0.6700, 0.3300, 0.320250),
        (0.2100, 0.7100, 0.602071),
        (0.1400, 0.0800, 0.077679),
    ),
    "Ekta Space PS5": (
        2.2,
        "D50",
        (0.6950, 0.3050, 0.260629),
        (0.2600, 0.7000, 0.734946),
        (0.1100, 0.0050, 0.004425),
    ),
    "NTSC 1953": (
        2.2,
        "C",
        (0.6700, 0.3300, 0.298839),
        (0.2100, 0.7100, 0.586811),
        (0.1400, 0.0800, 0.114350),
    ),
    "PAL/SECAM": (
        2.2,
        "D65",
        (0.6400, 0.3300, 0.222021),
        (0.2900, 0.6000, 0.706645),
        (0.1500, 0.0600, 0.071334),
    ),
    "ProPhoto RGB": (
        1.8,
        "D50",
        (0.7347, 0.2653, 0.288040),
        (0.1596, 0.8404, 0.711874),
        (0.0366, 0.0001, 0.000086),
    ),
    "Rec. 709": (
        -709,
        "D65",
        (0.6400, 0.3300, 0.212656),
        (0.3000, 0.6000, 0.715158),
        (0.1500, 0.0600, 0.072186),
    ),
    "Rec. 2020": (
        -709,
        "D65",
        (0.7080, 0.2920, 0.262694),
        (0.1700, 0.7970, 0.678009),
        (0.1310, 0.0460, 0.059297),
    ),
    "SMPTE-C": (
        2.2,
        "D65",
        (0.6300, 0.3400, 0.212395),
        (0.3100, 0.5950, 0.701049),
        (0.1550, 0.0700, 0.086556),
    ),
    "SMPTE 240M": (
        -240,
        "D65",
        (0.6300, 0.3400, 0.212395),
        (0.3100, 0.5950, 0.701049),
        (0.1550, 0.0700, 0.086556),
    ),
    "sRGB": (
        -2.4,
        "D65",
        (0.6400, 0.3300, 0.212656),
        (0.3000, 0.6000, 0.715158),
        (0.1500, 0.0600, 0.072186),
    ),
    "Wide Gamut RGB": (
        2.2,
        "D50",
        (0.7350, 0.2650, 0.258187),
        (0.1150, 0.8260, 0.724938),
        (0.1570, 0.0180, 0.016875),
    ),
}


def get_cat_matrix(cat="Bradford"):
    if isinstance(cat, str):
        cat = cat_matrices[cat]
    elif isinstance(cat, bytes):
        cat = cat_matrices[cat.decode()]
    if not isinstance(cat, Matrix3x3):
        cat = Matrix3x3(cat)
    return cat


def cbrt(x):
    return math.pow(x, 1.0 / 3.0) if x >= 0 else -math.pow(-x, 1.0 / 3.0)


def var(a):
    """Variance"""
    s = 0.0
    l = len(a)
    while l:
        l -= 1
        s += a[l]
    l = len(a)
    m = s / l
    s = 0.0
    while l:
        l -= 1
        s += (a[l] - m) ** 2
    return s / len(a)


def XYZ2LMS(X, Y, Z, cat="Bradford"):
    """Convert from XYZ to cone response domain

    :param X:
    :param Y:
    :param Z:
    :param str, Matrix3x3 cat:
    """
    cat = get_cat_matrix(cat)
    p, y, b = cat * [X, Y, Z]
    return p, y, b


def LMS_wp_adaption_matrix(
    whitepoint_source=None, whitepoint_destination=None, cat="Bradford"
):
    """Prepare a matrix to match the whitepoints in cone response domain"""
    # chromatic adaption
    # based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
    # cat = adaption matrix or predefined choice ('CAT02', 'Bradford',
    # 'Von Kries', 'XYZ Scaling', see cat_matrices), defaults to 'Bradford'
    cat = get_cat_matrix(cat)
    XYZWS = get_whitepoint(whitepoint_source)
    XYZWD = get_whitepoint(whitepoint_destination)
    if XYZWS[1] <= 1.0 < XYZWD[1]:
        # make sure the scaling is identical
        XYZWD = [v / XYZWD[1] * XYZWS[1] for v in XYZWD]
    if XYZWD[1] <= 1.0 < XYZWS[1]:
        # make sure the scaling is identical
        XYZWS = [v / XYZWS[1] * XYZWD[1] for v in XYZWS]
    Ls, Ms, Ss = XYZ2LMS(XYZWS[0], XYZWS[1], XYZWS[2], cat)
    Ld, Md, Sd = XYZ2LMS(XYZWD[0], XYZWD[1], XYZWD[2], cat)
    return Matrix3x3([[Ld / Ls, 0, 0], [0, Md / Ms, 0], [0, 0, Sd / Ss]])


def wp_adaption_matrix(
    whitepoint_source=None, whitepoint_destination=None, cat="Bradford"
):
    """Prepare a matrix to match the whitepoints in cone response doamin and
    transform back to XYZ

    """
    # chromatic adaption
    # based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
    # cat = adaption matrix or predefined choice ('CAT02', 'Bradford',
    # 'Von Kries', 'XYZ Scaling', see cat_matrices), defaults to 'Bradford'
    cachehash = (
        (
            tuple(whitepoint_source)
            if isinstance(whitepoint_source, (list, tuple))
            else whitepoint_source
        ),
        (
            tuple(whitepoint_destination)
            if isinstance(whitepoint_destination, (list, tuple))
            else whitepoint_destination
        ),
        cat if isinstance(cat, str) else id(cat),
    )
    if cachehash in wp_adaption_matrix.cache:
        return wp_adaption_matrix.cache[cachehash]
    cat = get_cat_matrix(cat)
    wpam = (
        cat.inverted()
        * LMS_wp_adaption_matrix(whitepoint_source, whitepoint_destination, cat)
        * cat
    )
    wp_adaption_matrix.cache[cachehash] = wpam
    return wpam


wp_adaption_matrix.cache = {}


def adapt(X, Y, Z, whitepoint_source=None, whitepoint_destination=None, cat="Bradford"):
    """Transform XYZ under source illuminant to XYZ under destination illuminant"""
    # chromatic adaption
    # based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
    # cat = adaption matrix or predefined choice ('CAT02', 'Bradford',
    # 'Von Kries', 'XYZ Scaling', see cat_matrices), defaults to 'Bradford'
    return wp_adaption_matrix(whitepoint_source, whitepoint_destination, cat) * (
        X,
        Y,
        Z,
    )


def apply_bpc(
    X, Y, Z, bp_in=None, bp_out=None, wp_out="D50", weight=False, pin_chromaticity=False
):
    """Apply black point compensation"""
    if not bp_in:
        bp_in = (0, 0, 0)
    if not bp_out:
        bp_out = (0, 0, 0)
    wp_out = get_whitepoint(wp_out)
    if weight:
        L = XYZ2Lab(*[v * 100 for v in (X, Y, Z)])[0]
        bp_in_Lab = XYZ2Lab(*[v * 100 for v in bp_in])
        bp_out_Lab = XYZ2Lab(*[v * 100 for v in bp_out])
        vv = (L - bp_in_Lab[0]) / (100.0 - bp_in_Lab[0])  # 0 at bp, 1 at wp
        vv = 1.0 - vv
        if vv < 0.0:
            vv = 0.0
        elif vv > 1.0:
            vv = 1.0
        vv = math.pow(vv, min(40.0, 40.0 / (max(bp_in_Lab[0], bp_out_Lab[0]) or 1.0)))
        bp_in = Lab2XYZ(*[v * vv for v in bp_in_Lab])
        bp_out = Lab2XYZ(*[v * vv for v in bp_out_Lab])
    if pin_chromaticity:
        XYZ = [Y]
        x, y = XYZ2xyY(X, Y, Z, wp_out)[:2]
        bp_in = bp_in[1:2]
        bp_out = bp_out[1:2]
        wp_out = wp_out[1:2]
    else:
        XYZ = [X, Y, Z]
    for i, v in enumerate(XYZ):
        XYZ[i] = ((wp_out[i] - bp_out[i]) * v - wp_out[i] * (bp_in[i] - bp_out[i])) / (
            wp_out[i] - bp_in[i]
        )
    if pin_chromaticity:
        XYZ = xyY2XYZ(x, y, XYZ[0])
    return XYZ


def avg(*args):
    return float(sum(args)) / len(args)


def blend_ab(X, Y, Z, bp, wp, power=40.0, signscale=1):
    if Y < 0:
        return 0, 0, 0
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint=wp)
    bpL, bpa, bpb = XYZ2Lab(*bp, whitepoint=wp)
    if bpL == 100:
        raise ValueError("Black L* is 100!")
    vv = (L - bpL) / (100.0 - bpL)  # 0 at bp, 1 at wp
    vv = 1.0 - vv  # 1 at bp, 0 at wp
    if vv < 0.0:
        vv = 0.0
    elif vv > 1.0:
        vv = 1.0
    vv = math.pow(vv, power) * signscale
    a += vv * bpa
    b += vv * bpb
    return Lab2XYZ(L, a, b, whitepoint=wp)


def blend_blackpoint(
    X, Y, Z, bp_in=None, bp_out=None, wp=None, power=40.0, pin_chromaticity=False
):
    """Blend to destination black as L approaches black, optionally compensating
    for input black first

    """

    wp = get_whitepoint(wp)

    for i, bp in enumerate((bp_in, bp_out)):
        if not bp or tuple(bp) == (0, 0, 0):
            continue
        bp_wp = tuple(v / wp[1] * bp[1] for v in wp)
        if i == 0:
            X, Y, Z = blend_ab(X, Y, Z, bp, wp, power, -1)
            X, Y, Z = apply_bpc(X, Y, Z, bp_wp, None, wp, pin_chromaticity)
        else:
            X, Y, Z = apply_bpc(X, Y, Z, None, bp_wp, wp, pin_chromaticity)
            X, Y, Z = blend_ab(X, Y, Z, bp, wp, power, 1)

    return X, Y, Z


def interp_old(x, xp, fp, left=None, right=None):
    """One-dimensional linear interpolation similar to numpy.interp

    Values do NOT have to be monotonically increasing
    interp(0, [0, 0], [0, 1]) will return 0

    """
    if not isinstance(x, (int, float, complex)):
        yi = []
        for n in x:
            yi.append(interp_old(n, xp, fp, left, right))
        return yi
    if x in xp:
        return fp[xp.index(x)]
    elif x < xp[0]:
        return fp[0] if left is None else left
    elif x > xp[-1]:
        return fp[-1] if right is None else right
    else:
        # Interpolate
        lower = 0
        higher = len(fp) - 1
        for i, v in enumerate(xp):
            if v < x and i > lower:
                lower = i
            elif v > x and i < higher:
                higher = i
        step = float(x - xp[lower])
        steps = (xp[higher] - xp[lower]) / step
        return fp[lower] + (fp[higher] - fp[lower]) / steps


# This is much faster than the old implementation
def interp(x, xp, fp, left=None, right=None, period=None):
    """One-dimensional linear interpolation similar to numpy.interp

    Values do NOT have to be monotonically increasing
    interp(0, [0, 0], [0, 1]) will return 0

    """
    # TODO: This function overrides the class implementation (Interp) and forces to use
    #       numpy.interp all the time, and it is kind of rude in that manner.
    #       Please respect the previous implementation, but use nump.interp again.
    import numpy

    return numpy.interp(x, xp, fp, left, right, period)


def interp_resize(iterable, new_size, use_numpy=False):
    """Change size of iterable through linear interpolation"""
    result = []
    x_new = list(range(len(iterable)))
    # interp = Interp(x_new, iterable, use_numpy=use_numpy)
    for i in range(new_size):
        result.append(
            interp(
                i / (new_size - 1.0) * (len(iterable) - 1.0),
                x_new,
                iterable,
            )
        )
    return result


def interp_fill(xp, fp, new_size, use_numpy=False):
    """Fill missing points by interpolation"""
    result = []
    last = xp[-1]
    # interp = Interp(xp, fp, use_numpy=use_numpy)
    for i in range(new_size):
        result.append(interp(i / (new_size - 1.0) * last, xp, fp))
    return result


def smooth_avg_old(values, passes=1, window=None, protect=None):
    """Smooth values (moving average).

    Args:
        values (list): A list of float values.
        passes (int): Number of passes
        window (tuple/list): Tuple or list containing weighting factors. Its length
            determines the size of the window to use. Defaults to (1.0, 1.0, 1.0)
        protect (list): A list of indices to protect. The values related to these
            indices will be protected.
    """
    if not window or len(window) < 3 or len(window) % 2 != 1:
        if window:
            warnings.warn(
                "Invalid window %r, size %i - using default (1, 1, 1)"
                % (window, len(window)),
                Warning,
            )
        window = (1.0, 1.0, 1.0)
    for _x in range(0, passes):
        data = []
        for j, v in enumerate(values):
            tmp_window = window
            if not protect or j not in protect:
                while 0 < j < len(values) - 1 and len(tmp_window) >= 3:
                    tl = (len(tmp_window) - 1) / 2
                    # print j, tl, tmp_window
                    if tl > 0 and j - tl >= 0 and j + tl <= len(values) - 1:
                        windowslice = values[int(j - tl) : int(j + tl + 1)]
                        windowsize = 0
                        for k, weight in enumerate(tmp_window):
                            windowsize += float(weight) * windowslice[k]
                        v = windowsize / sum(tmp_window)
                        break
                    else:
                        tmp_window = tmp_window[1:-1]
            data.append(v)
        values = data
    return values


def smooth_avg(values, passes=1, window=None, protect=None):
    """Smooth values fast (moving average).

    This is (should be) the fast implementation of the ``smooth_avg``. Inputs are the
    same.

    Args:
        values (list): A list of float values.
        passes (int): Number of passes
        window (tuple/list): Tuple or list containing weighting factors. Its length
            determines the size of the window to use. Defaults to (1.0, 1.0, 1.0)
        protect (list): A list of indices to protect. The values related to these
            indices will be restored after each pass.
    """
    if not window or len(window) < 3 or len(window) % 2 != 1:
        if window:
            warnings.warn(
                "Invalid window %r, size %i - using default (1, 1, 1)"
                % (window, len(window)),
                Warning,
            )
        window = (1, 1, 1)
    # fix the window values
    window_length = float(len(window))
    window_weight = sum(window)
    window = tuple([i / window_weight for i in window])

    # extend the array by ceil(window_size / 2)
    extend_amount = math.ceil(window_length / 2)

    # protect start and end values by adding the first and last values by the half of
    # the window length
    values = values[0:1] * extend_amount + values + values[-1:] * extend_amount

    protection_extension = 1
    protected_start = values[: extend_amount + protection_extension]
    protected_end = values[-extend_amount - protection_extension :]

    protected_values = {}
    if protect is not None:
        for index in protect:
            # offset the values with ``extend_amount``
            protected_values[index + extend_amount] = values[index + extend_amount]

    import numpy

    for i in range(passes):
        values = list(numpy.convolve(values, window, mode="same"))
        # Protect start and end values
        values[: extend_amount + protection_extension] = protected_start
        values[-extend_amount - protection_extension :] = protected_end

        # restore protected values
        if protect is not None:
            for k in protected_values:
                v = protected_values[k]
                values[k] = v

    # return the non-extended portion
    return values[extend_amount:-extend_amount]


def compute_bpc(bp_in, bp_out):
    """Black point compensation. Implemented as a linear scaling in XYZ.

    Black points should come relative to the white point. Fills and
    returns a matrix/offset element.

    [matrix]*bp_in + offset = bp_out
    [matrix]*D50  + offset = D50

    """
    # This is a linear scaling in the form ax+b, where
    # a = (bp_out - D50) / (bp_in - D50)
    # b = - D50* (bp_out - bp_in) / (bp_in - D50)

    D50 = get_standard_illuminant("D50")

    tx = bp_in[0] - D50[0]
    ty = bp_in[1] - D50[1]
    tz = bp_in[2] - D50[2]

    ax = (bp_out[0] - D50[0]) / tx
    ay = (bp_out[1] - D50[1]) / ty
    az = (bp_out[2] - D50[2]) / tz

    bx = -D50[0] * (bp_out[0] - bp_in[0]) / tx
    by = -D50[1] * (bp_out[1] - bp_in[1]) / ty
    bz = -D50[2] * (bp_out[2] - bp_in[2]) / tz

    matrix = Matrix3x3([[ax, 0, 0], [0, ay, 0], [0, 0, az]])
    offset = [bx, by, bz]
    return matrix, offset


def delta(
    L1,
    a1,
    b1,
    L2,
    a2,
    b2,
    method="1976",
    p1=None,
    p2=None,
    p3=None,
    cie94_use_symmetric_chrominance=True,
):
    """Compute the delta of two samples

    CIE 1994 & CMC calculation code derived from formulas on
     www.brucelindbloom.com
    CIE 1994 code uses some alterations seen on
     www.farbmetrik-gall.de/cielab/korrcielab/cie94.html
     (see notes in code below)
    CIE 2000 calculation code derived from Excel spreadsheet available at
     www.ece.rochester.edu/~gsharma/ciede2000

    method: either "CIE94", "CMC", "CIE2K" or "CIE76"
     (default if method is not set)

    p1, p2, p3 arguments have different meaning for each calculation method:

        CIE 1994: If p1 is not None, calculation will be adjusted for
                  textiles, otherwise graphics arts (default if p1 is not set)
        CMC(l:c): p1 equals l (lightness) weighting factor and p2 equals c
                  (chroma) weighting factor.
                  Commonly used values are CMC(1:1) for perceptability
                  (default if p1 and p2 are not set) and CMC(2:1) for
                  acceptability
        CIE 2000: p1 becomes kL (lightness) weighting factor, p2 becomes
                  kC (chroma) weighting factor and p3 becomes kH (hue)
                  weighting factor (all three default to 1 if not set)

    """
    if isinstance(method, str):
        method = method.lower()
    else:
        method = str(int(method))
    if method in ("94", "1994", "cie94", "cie1994"):
        textiles = p1
        dL = L2 - L1
        C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        dC = C2 - C1
        dH2 = math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dC, 2)
        dH = math.sqrt(dH2) if dH2 > 0 else 0
        SL = 1.0
        K1 = 0.048 if textiles else 0.045
        K2 = 0.014 if textiles else 0.015
        if cie94_use_symmetric_chrominance:
            C_ = math.sqrt(C1 * C2)
        else:
            C_ = C1
        SC = 1.0 + K1 * C_
        SH = 1.0 + K2 * C_
        KL = 2.0 if textiles else 1.0
        KC = 1.0
        KH = 1.0
        dLw, dCw, dHw = dL / (KL * SL), dC / (KC * SC), dH / (KH * SH)
        dE = math.sqrt(math.pow(dLw, 2) + math.pow(dCw, 2) + math.pow(dHw, 2))
    elif method in ("cmc(2:1)", "cmc21", "cmc(1:1)", "cmc11", "cmc"):
        if method in ("cmc(2:1)", "cmc21"):
            p1 = 2.0
        l = p1 if isinstance(p1, (float, int)) else 1.0
        c = p2 if isinstance(p2, (float, int)) else 1.0
        dL = L2 - L1
        C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        dC = C2 - C1
        dH2 = math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dC, 2)
        dH = math.sqrt(dH2) if dH2 > 0 else 0
        SL = 0.511 if L1 < 16 else (0.040975 * L1) / (1 + 0.01765 * L1)
        SC = (0.0638 * C1) / (1 + 0.0131 * C1) + 0.638
        F = math.sqrt(math.pow(C1, 4) / (math.pow(C1, 4) + 1900.0))
        H1 = math.degrees(math.atan2(b1, a1)) + (0 if b1 >= 0 else 360.0)
        T = (
            0.56 + abs(0.2 * math.cos(math.radians(H1 + 168.0)))
            if 164 <= H1 <= 345
            else 0.36 + abs(0.4 * math.cos(math.radians(H1 + 35)))
        )
        SH = SC * (F * T + 1 - F)
        dLw, dCw, dHw = dL / (l * SL), dC / (c * SC), dH / SH
        dE = math.sqrt(math.pow(dLw, 2) + math.pow(dCw, 2) + math.pow(dHw, 2))
    elif method in ("00", "2k", "2000", "cie00", "cie2k", "cie2000"):
        pow25_7 = math.pow(25, 7)
        k_L = p1 if isinstance(p1, (float, int)) else 1.0
        k_C = p2 if isinstance(p2, (float, int)) else 1.0
        k_H = p3 if isinstance(p3, (float, int)) else 1.0
        C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        C_avg = avg(C1, C2)
        G = 0.5 * (1 - math.sqrt(math.pow(C_avg, 7) / (math.pow(C_avg, 7) + pow25_7)))
        L1_ = L1
        a1_ = (1 + G) * a1
        b1_ = b1
        L2_ = L2
        a2_ = (1 + G) * a2
        b2_ = b2
        C1_ = math.sqrt(math.pow(a1_, 2) + math.pow(b1_, 2))
        C2_ = math.sqrt(math.pow(a2_, 2) + math.pow(b2_, 2))
        h1_ = (
            0
            if a1_ == 0 and b1_ == 0
            else math.degrees(math.atan2(b1_, a1_)) + (0 if b1_ >= 0 else 360.0)
        )
        h2_ = (
            0
            if a2_ == 0 and b2_ == 0
            else math.degrees(math.atan2(b2_, a2_)) + (0 if b2_ >= 0 else 360.0)
        )
        dh_cond = 1.0 if h2_ - h1_ > 180 else (2.0 if h2_ - h1_ < -180 else 0)
        dh_ = (
            h2_ - h1_
            if dh_cond == 0
            else (h2_ - h1_ - 360.0 if dh_cond == 1 else h2_ + 360.0 - h1_)
        )
        dL_ = L2_ - L1_
        dL = dL_
        dC_ = C2_ - C1_
        dC = dC_
        dH_ = 2 * math.sqrt(C1_ * C2_) * math.sin(math.radians(dh_ / 2.0))
        dH = dH_
        L__avg = avg(L1_, L2_)
        C__avg = avg(C1_, C2_)
        h__avg_cond = (
            3.0
            if C1_ * C2_ == 0
            else (0 if abs(h2_ - h1_) <= 180 else (1.0 if h2_ + h1_ < 360 else 2.0))
        )
        h__avg = (
            h1_ + h2_
            if h__avg_cond == 3
            else (
                avg(h1_, h2_)
                if h__avg_cond == 0
                else (
                    avg(h1_, h2_) + 180.0 if h__avg_cond == 1 else avg(h1_, h2_) - 180.0
                )
            )
        )
        AB = math.pow(L__avg - 50.0, 2)  # (L'_ave-50)^2
        S_L = 1 + 0.015 * AB / math.sqrt(20.0 + AB)
        S_C = 1 + 0.045 * C__avg
        T = (
            1
            - 0.17 * math.cos(math.radians(h__avg - 30.0))
            + 0.24 * math.cos(math.radians(2.0 * h__avg))
            + 0.32 * math.cos(math.radians(3.0 * h__avg + 6.0))
            - 0.2 * math.cos(math.radians(4 * h__avg - 63.0))
        )
        S_H = 1 + 0.015 * C__avg * T
        dTheta = 30.0 * math.exp(-1 * math.pow((h__avg - 275.0) / 25.0, 2))
        R_C = 2.0 * math.sqrt(math.pow(C__avg, 7) / (math.pow(C__avg, 7) + pow25_7))
        R_T = -math.sin(math.radians(2.0 * dTheta)) * R_C
        AJ = dL_ / S_L / k_L  # dL' / k_L / S_L
        AK = dC_ / S_C / k_C  # dC' / k_C / S_C
        AL = dH_ / S_H / k_H  # dH' / k_H / S_H
        dLw, dCw, dHw = AJ, AK, AL
        dE = math.sqrt(
            math.pow(AJ, 2) + math.pow(AK, 2) + math.pow(AL, 2) + R_T * AK * AL
        )
    else:
        # dE 1976
        dL = L2 - L1
        C1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        C2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        dC = C2 - C1
        dH2 = math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dC, 2)
        dH = math.sqrt(dH2) if dH2 > 0 else 0
        dLw, dCw, dHw = dL, dC, dH
        dE = math.sqrt(math.pow(dL, 2) + math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2))

    return {
        "E": dE,
        "L": dL,
        "C": dC,
        "H": dH,
        "a": a1 - a2,
        "b": b1 - b2,
        # Weighted
        "Lw": dLw,
        "Cw": dCw,
        "Hw": dHw,
    }


def XYZ2Lab_delta(
    X1,
    Y1,
    Z1,
    X2,
    Y2,
    Z2,
    method="76",
    whitepoint1="D50",
    whitepoint2="D50",
    whitepoint_reference="D50",
    cat="Bradford",
):
    whitepoint1 = get_whitepoint(whitepoint1)
    whitepoint2 = get_whitepoint(whitepoint2)
    whitepoint_reference = get_whitepoint(whitepoint_reference)
    if whitepoint1 != whitepoint_reference:
        X1, Y1, Z1 = adapt(X1, Y1, Z1, whitepoint1, whitepoint_reference, cat)
    if whitepoint2 != whitepoint_reference:
        X2, Y2, Z2 = adapt(X2, Y2, Z2, whitepoint2, whitepoint_reference, cat)
    L1, a1, b1 = XYZ2Lab(X1, Y1, Z1, whitepoint_reference)
    L2, a2, b2 = XYZ2Lab(X2, Y2, Z2, whitepoint_reference)
    logging.debug(
        "L*a*b*[1] %.4f %.4f %.4f L*a*b*[2] %.4f %.4f %.4f" % (L1, a1, b1, L2, a2, b2)
    )
    return delta(L1, a1, b1, L2, a2, b2, method)


def is_similar_matrix(matrix1, matrix2, digits=3):
    """Compare two matrices and check if they are the same
    up to n digits after the decimal point"""
    return matrix1.rounded(digits) == matrix2.rounded(digits)


def is_equal(values1, values2, quantizer=lambda v: round(v, 4)):
    """Compare two sets of values and check if they are the same
    after applying quantization"""
    return [quantizer(v) for v in values1] == [quantizer(v) for v in values2]


def four_color_matrix(
    XrR,
    YrR,
    ZrR,
    XrG,
    YrG,
    ZrG,
    XrB,
    YrB,
    ZrB,
    XrW,
    YrW,
    ZrW,
    XmR,
    YmR,
    ZmR,
    XmG,
    YmG,
    ZmG,
    XmB,
    YmB,
    ZmB,
    XmW,
    YmW,
    ZmW,
    Y_correction=True,
):
    """Four-Color Matrix Method for Correction of Tristimulus Colorimeters

    Based on paper published in Proc., IS&T Fifth Color Imaging Conference,
    301-305 (1997) and IS&T Sixth Color Imaging Conference (1998).

    """
    XYZ = locals()
    xyz = {}
    M = {}
    k = {}
    for s in "mr":
        xyz[s] = {}
        for color in "RGBW":
            X, Y, Z = (XYZ[component + s + color] for component in "XYZ")
            x, y = XYZ2xyY(X, Y, Z)[:2]
            xyz[s][color] = x, y, 1 - x - y
        M[s] = Matrix3x3([xyz[s][color] for color in "RGB"]).transposed()
        k[s] = M[s].inverted() * xyz[s]["W"]
        M[s + "RGB"] = M[s] * Matrix3x3(
            [[k[s][0], 0, 0], [0, k[s][1], 0], [0, 0, k[s][2]]]
        )
    R = M["rRGB"] * M["mRGB"].inverted()
    if Y_correction:
        # The Y calibration factor kY is obtained as the ratio of the reference
        # luminance value to the matrix-corrected Y value, as defined in
        # Four-Color Matrix Method for Correction of Tristimulus Colorimeters –
        # Part 2
        MW = XmW, YmW, ZmW
        kY = YrW / (R * MW)[1]
        R[:] = [[kY * v for v in row] for row in R]
    return R


def get_gamma(values, scale=1.0, vmin=0.0, vmax=1.0, average=True, least_squares=False):
    """Return average or least squares gamma or a list of gamma values"""
    if least_squares:
        logxy = []
        logx2 = []
    else:
        gammas = []
    vmin /= scale
    vmax /= scale
    for x, y in values:
        x /= scale
        y = (y / scale - vmin) * (vmax + vmin)
        if 0 < x < 1 and y > 0:
            if least_squares:
                logxy.append(math.log(x) * math.log(y))
                logx2.append(math.pow(math.log(x), 2))
            else:
                gammas.append(math.log(y) / math.log(x))
    if average or least_squares:
        if least_squares:
            if not logxy or not logx2:
                return 0
            return sum(logxy) / sum(logx2)
        else:
            if not gammas:
                return 0
            return sum(gammas) / len(gammas)
    else:
        return gammas


def guess_cat(chad, whitepoint_source=None, whitepoint_destination=None):
    """Try and guess the chromatic adaption transform used in a chromatic
    adaption matrix as found in an ICC profile's 'chad' tag"""
    if chad == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]:
        # Cannot figure out CAT from identity chad
        return
    for cat in cat_matrices:
        if is_similar_matrix(
            (
                chad
                * cat_matrices[cat].inverted()
                * LMS_wp_adaption_matrix(whitepoint_destination, whitepoint_source, cat)
            ).inverted(),
            cat_matrices[cat],
            2,
        ):
            return cat


def CIEDCCT2xyY(T, scale=1.0):
    """Convert from CIE correlated daylight temperature to xyY.

    T = temperature in Kelvin.

    Based on formula from http://brucelindbloom.com/Eqn_T_to_xy.html

    """
    if isinstance(T, str):
        # Assume standard illuminant, e.g. "D50"
        return XYZ2xyY(*get_standard_illuminant(T, scale=scale))
    if not (2500 <= T <= 25000):
        # Lower limit of 2500 is consistent with Argyll xicc/xspect.c daylight_il
        # Actual usable lower limit lies at roughly 2244
        return None
    if T < 4000:
        # Only accurate down to about 4000
        warnings.warn("Daylight CCT is only accurate down to about 4000 K", Warning)
    if T <= 7000:
        xD = (
            ((-4.607 * math.pow(10, 9)) / math.pow(T, 3))
            + ((2.9678 * math.pow(10, 6)) / math.pow(T, 2))
            + ((0.09911 * math.pow(10, 3)) / T)
            + 0.244063
        )
    else:
        xD = (
            ((-2.0064 * math.pow(10, 9)) / math.pow(T, 3))
            + ((1.9018 * math.pow(10, 6)) / math.pow(T, 2))
            + ((0.24748 * math.pow(10, 3)) / T)
            + 0.237040
        )
    yD = -3 * math.pow(xD, 2) + 2.87 * xD - 0.275
    return xD, yD, scale


def CIEDCCT2XYZ(T, scale=1.0):
    """Convert from CIE correlated daylight temperature to XYZ.

    T = temperature in Kelvin.

    """
    xyY = CIEDCCT2xyY(T, scale)
    if xyY:
        return xyY2XYZ(*xyY)


# cLUT Input value tweaks to make Video encoded black land on
# 65 res grid nodes, which should help 33 and 17 res cLUTs too
def cLUT65_to_VidRGB(v, size=65):
    if v <= 236.0 / 256:
        # Scale up to near black point
        return v * 256.0 / 255
    else:
        return 1 - (1 - v) * (1 - 236.0 / 255) / (1 - 236.0 / 256)


def VidRGB_to_cLUT65(v, size=65):
    if v <= 236.0 / 255.0:
        return v * 255.0 / 256
    else:
        return 1 - (1 - v) * (1 - 236.0 / 256) / (1 - 236.0 / 255)


def VidRGB_to_eeColor(v):
    return v * 255.0 / 256.0


def eeColor_to_VidRGB(v):
    return v * 256.0 / 255.0


def DIN992Lab(L99, a99, b99, kCH=1.0, kE=1.0):
    C99, H99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        L99, C99, H99, 0, 105.51, 0.0158, 16, 0.7, 1 / (0.045 * kCH * kE), 0.045, kE, 0
    )


def DIN99b2Lab(L99, a99, b99):
    C99, H99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(L99, C99, H99, 0, 303.67, 0.0039, 26, 0.83, 23, 0.075)


def DIN99o2Lab(L99, a99, b99, kCH=1.0, kE=1.0):
    C99, H99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        L99, C99, H99, 0, 303.67, 0.0039, 26, 0.83, 1 / (0.0435 * kCH * kE), 0.075, kE
    )


def DIN99bLCH2Lab(L99, C99, H99):
    return DIN99familyLCH2Lab(L99, C99, H99, 0, 303.67, 0.0039, 26, 0.83, 23, 0.075)


def DIN99c2Lab(L99, a99, b99, whitepoint=None):
    C99, H99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        L99, C99, H99, 0.1, 317.651, 0.0037, 0, 0.94, 23, 0.066, whitepoint
    )


def DIN99d2Lab(L99, a99, b99, whitepoint=None):
    C99, H99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        L99, C99, H99, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint
    )


def DIN99dLCH2Lab(L99, C99, H99, whitepoint=None):
    return DIN99familyLCH2Lab(
        L99, C99, H99, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint
    )


def DIN99familyLCH2Lab(
    L99, C99, H99, x, l1, l2, deg, f1, c1, c2, whitepoint=None, kE=1.0, hdeg=None
):
    G = (math.exp(C99 / c1) - 1) / c2
    if hdeg is None:
        hdeg = deg
    H99 -= hdeg
    L, a, b = DIN99familyLHCG2Lab(L99, H99, C99, G, kE, l1, l2, deg, f1)
    if x:
        whitepoint99d = XYZ2DIN99cdXYZ(*get_whitepoint(whitepoint, 100), x=x)
        X, Y, Z = Lab2XYZ(L, a, b, whitepoint99d, scale=100)
        X, Y, Z = DIN99cdXYZ2XYZ(X, Y, Z, x)
        L, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return L, a, b


def DIN99cdXYZ2XYZ(X, Y, Z, x):
    X = (X + x * Z) / (1 + x)
    return X, Y, Z


def DIN99familyLHCG2Lab(L99, H99, C99, G, kE, l1, l2, deg, f1):
    L = (math.exp((L99 * kE) / l1) - 1) / l2
    h99ef = H99 * math.pi / 180
    e = G * math.cos(h99ef)
    f = G * math.sin(h99ef)
    rad = deg * math.pi / 180
    a = e * math.cos(rad) - (f / f1) * math.sin(rad)
    b = e * math.sin(rad) + (f / f1) * math.cos(rad)
    return L, a, b


def DIN99familyCH2DIN99ab(C99, H99):
    h99ef = H99 * math.pi / 180
    return C99 * math.cos(h99ef), C99 * math.sin(h99ef)


def DIN99familyab2DIN99CH(a99, b99):
    C99 = math.sqrt(math.pow(a99, 2) + math.pow(b99, 2))
    if a99 > 0:
        if b99 >= 0:
            h99ef = math.atan2(b99, a99)
        else:
            h99ef = 2 * math.pi + math.atan2(b99, a99)
    elif a99 < 0:
        h99ef = math.atan2(b99, a99)
    else:
        if b99 > 0:
            h99ef = math.pi / 2
        elif b99 < 0:
            h99ef = (3 * math.pi) / 2
        else:
            h99ef = 0.0
    H99 = h99ef * 180 / math.pi
    return C99, H99


def HSI2RGB(H, S, I, scale=1.0):
    H *= 360

    h = H
    if 120 < H <= 240:
        h -= 120
    elif 240 < H <= 360:
        h -= 240

    f = math.cos(math.radians(h)) / math.cos(math.radians(60 - h))
    a = I + I * S * f
    b = I + I * S * (1 - f)
    c = I - I * S

    if H <= 120:
        R = a
        G = b
        B = c
    elif H <= 240:
        G = a
        B = b
        R = c
    else:
        B = a
        R = b
        G = c

    return tuple(v * scale for v in (R, G, B))


def HSL2RGB(H, S, L, scale=1.0):
    return tuple(v * scale for v in colorsys.hls_to_rgb(H, L, S))


def HSV2RGB(H, S, V, scale=1.0):
    return tuple(v * scale for v in colorsys.hsv_to_rgb(H, S, V))


def get_DBL_MIN():
    t = "0.0"
    i = 10
    n = 0
    while True:
        if i > 1:
            i -= 1
        else:
            t += "0"
            i = 9
        if float(t + str(i)) == 0.0:
            if n > 1:
                break
            n += 1
            t += str(i)
            i = 10
        else:
            if n > 1:
                n -= 1
            DBL_MIN = float(t + str(i))
    return DBL_MIN


DBL_MIN = get_DBL_MIN()


def LCHab2Lab(L, C, H):
    a = C * math.cos(H * math.pi / 180.0)
    b = C * math.sin(H * math.pi / 180.0)
    return L, a, b


def Lab2DIN99(L, a, b, kCH=1.0, kE=1.0):
    L99, C99, H99 = Lab2DIN99LCH(L, a, b, kCH, kE)
    a99, b99 = DIN99familyCH2DIN99ab(C99, H99)
    return L99, a99, b99


def Lab2DIN99b(L, a, b, kE=1.0):
    L99, C99, H99 = Lab2DIN99bLCH(L, a, b, kE)
    a99, b99 = DIN99familyCH2DIN99ab(C99, H99)
    return L99, a99, b99


def Lab2DIN99o(L, a, b, kCH=1.0, kE=1.0):
    L99, C99, H99 = Lab2DIN99oLCH(L, a, b, kCH, kE)
    a99, b99 = DIN99familyCH2DIN99ab(C99, H99)
    return L99, a99, b99


def Lab2DIN99c(L, a, b, kE=1.0, whitepoint=None):
    X, Y, Z = Lab2XYZ(L, a, b, whitepoint, scale=100)
    return XYZ2DIN99c(X, Y, Z, whitepoint)


def Lab2DIN99d(L, a, b, kE=1.0, whitepoint=None):
    X, Y, Z = Lab2XYZ(L, a, b, whitepoint, scale=100)
    return XYZ2DIN99d(X, Y, Z, whitepoint)


def Lab2DIN99LCH(L, a, b, kCH=1.0, kE=1.0):
    return Lab2DIN99familyLCH(
        L, a, b, 105.51, 0.0158, 16, 0.7, 1 / (0.045 * kCH * kE), 0.045, kE, 0
    )


def Lab2DIN99bLCH(L, a, b, kE=1.0):
    return Lab2DIN99familyLCH(L, a, b, 303.67, 0.0039, 26, 0.83, 23, 0.075)


def Lab2DIN99oLCH(L, a, b, kCH=1.0, kE=1.0):
    return Lab2DIN99familyLCH(
        L, a, b, 303.67, 0.0039, 26, 0.83, 1 / (0.0435 * kCH * kE), 0.075, kE
    )


def Lab2DIN99familyLCH(L, a, b, l1, l2, deg, f1, c1, c2, kE=1.0, hdeg=None):
    L99, G, h99ef, rad = Lab2DIN99familyLGhrad(L, a, b, kE, l1, l2, deg, f1)
    C99 = c1 * math.log(1 + c2 * G)
    if hdeg is None:
        hdeg = deg
    H99 = h99ef * 180 / math.pi + hdeg
    return L99, C99, H99


def Lab2DIN99familyLGhrad(L, a, b, kE, l1, l2, deg, f1):
    L99 = (1.0 / kE) * l1 * math.log(1 + l2 * L)
    rad = deg * math.pi / 180
    if rad:
        ar = math.cos(rad)  # a rotation term
        br = math.sin(rad)  # b rotation term
        e = a * ar + b * br
        f = f1 * (b * ar - a * br)
    else:
        e = a
        f = f1 * b
    G = math.sqrt(math.pow(e, 2) + math.pow(f, 2))
    h99ef = math.atan2(f, e)
    return L99, G, h99ef, rad


def Lab2LCHab(L, a, b):
    C = math.sqrt(math.pow(a, 2) + math.pow(b, 2))
    H = 180.0 * math.atan2(b, a) / math.pi
    if H < 0.0:
        H += 360.0
    return L, C, H


def Lab2Luv(L, a, b, whitepoint=None, scale=100):
    X, Y, Z = Lab2XYZ(L, a, b, whitepoint, scale)
    return XYZ2Luv(X, Y, Z, whitepoint)


def Lab2RGB(
    L,
    a,
    b,
    rgb_space=None,
    scale=1.0,
    round_=False,
    clamp=True,
    whitepoint=None,
    whitepoint_source=None,
    noadapt=False,
    cat="Bradford",
):
    """Convert from Lab to RGB"""
    X, Y, Z = Lab2XYZ(L, a, b, whitepoint)
    if not noadapt:
        rgb_space = get_rgb_space(rgb_space)
        X, Y, Z = adapt(X, Y, Z, whitepoint_source, rgb_space[1], cat)
    return XYZ2RGB(X, Y, Z, rgb_space, scale, round_, clamp)


def Lab2XYZ(L, a, b, whitepoint=None, scale=1.0):
    """Convert from Lab to XYZ.

    The input L value needs to be in the nominal range [0.0, 100.0] and
    other input values scaled accordingly.
    The output XYZ values are in the nominal range [0.0, scale].

    whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or
    color temperature as float or int. Defaults to D50 if not set.

    Based on formula from http://brucelindbloom.com/Eqn_Lab_to_XYZ.html

    """
    fy = (L + 16) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    if math.pow(fx, 3.0) > LSTAR_E:
        xr = math.pow(fx, 3.0)
    else:
        xr = (116.0 * fx - 16) / LSTAR_K

    if L > LSTAR_K * LSTAR_E:
        yr = math.pow((L + 16) / 116.0, 3.0)
    else:
        yr = L / LSTAR_K

    if math.pow(fz, 3.0) > LSTAR_E:
        zr = math.pow(fz, 3.0)
    else:
        zr = (116.0 * fz - 16) / LSTAR_K

    Xr, Yr, Zr = get_whitepoint(whitepoint, scale)

    X = xr * Xr
    Y = yr * Yr
    Z = zr * Zr

    return X, Y, Z


def Lab2xyY(L, a, b, whitepoint=None, scale=1.0):
    X, Y, Z = Lab2XYZ(L, a, b, whitepoint, scale)
    return XYZ2xyY(X, Y, Z, whitepoint)


def Luv2LCHuv(L, u, v):
    C = math.sqrt(math.pow(u, 2) + math.pow(v, 2))
    H = 180.0 * math.atan2(v, u) / math.pi
    if H < 0.0:
        H += 360.0
    return L, C, H


def Luv2RGB(
    L, u, v, rgb_space=None, scale=1.0, round_=False, clamp=True, whitepoint=None
):
    """Convert from Luv to RGB"""
    X, Y, Z = Luv2XYZ(L, u, v, whitepoint)
    return XYZ2RGB(X, Y, Z, rgb_space, scale, round_, clamp)


def u_v_2xy(u, v):
    """Convert from u'v' to xy"""

    x = (9.0 * u) / (6 * u - 16 * v + 12)
    y = (4 * v) / (6 * u - 16 * v + 12)

    return x, y


def Luv2XYZ(L, u, v, whitepoint=None, scale=1.0):
    """Convert from Luv to XYZ"""

    Xr, Yr, Zr = get_whitepoint(whitepoint)

    Y = math.pow((L + 16.0) / 116.0, 3) if L > LSTAR_K * LSTAR_E else L / LSTAR_K

    uo = (4.0 * Xr) / (Xr + 15.0 * Yr + 3.0 * Zr)
    vo = (9.0 * Yr) / (Xr + 15.0 * Yr + 3.0 * Zr)

    a = (1.0 / 3.0) * (((52.0 * L) / (u + 13 * L * uo)) - 1)
    b = -5.0 * Y
    c = -(1.0 / 3.0)
    d = Y * (((39.0 * L) / (v + 13 * L * vo)) - 5)

    X = (d - b) / (a - c)
    Z = X * a + b

    return tuple([v * scale for v in (X, Y, Z)])


def RGB2HSI(R, G, B, scale=1.0):
    I = (R + G + B) / 3.0
    if I:
        S = 1 - min(R, G, B) / I
    else:
        S = 0
    if not R == G == B:
        H = math.atan2(math.sqrt(3) * (G - B), 2 * R - G - B) / math.pi / 2
        if H < 0:
            H += 1.0
        if H > 1:
            H -= 1.0
    else:
        H = 0
    return H * scale, S * scale, I * scale


def RGB2HSL(R, G, B, scale=1.0):
    H, L, S = colorsys.rgb_to_hls(R, G, B)
    return tuple(v * scale for v in (H, S, L))


def RGB2HSV(R, G, B, scale=1.0):
    return tuple(v * scale for v in colorsys.rgb_to_hsv(R, G, B))


def LinearRGB2ICtCp(R, G, B, oetf=lambda FD: specialpow(FD, 1.0 / -2084)):
    """Rec. 2020 linear RGB to non-linear ICtCp"""
    # http://www.dolby.com/us/en/technologies/dolby-vision/ICtCp-white-paper.pdf
    LMS = LinearRGB2LMS_matrix * (R, G, B)
    L_, M_, S_ = (oetf(FD) for FD in LMS)
    I, Ct, Cp = L_M_S_2ICtCp_matrix * (L_, M_, S_)
    return I, Ct, Cp


def ICtCp2LinearRGB(I, Ct, Cp, eotf=lambda v: specialpow(v, -2084)):
    """Non-linear ICtCp to Rec. 2020 linear RGB"""
    # http://www.dolby.com/us/en/technologies/dolby-vision/ICtCp-white-paper.pdf
    L_M_S_ = ICtCp2L_M_S__matrix * (I, Ct, Cp)
    L, M, S = (eotf(v) for v in L_M_S_)
    R, G, B = LMS2LinearRGB_matrix * (L, M, S)
    return R, G, B


def RGB2ICtCp(
    R,
    G,
    B,
    rgb_space="Rec. 2020",
    eotf=lambda v: specialpow(v, -2084),
    clamp=False,
    oetf=lambda E: specialpow(E, 1.0 / -2084),
):
    """R'G'B' to ICtCp"""
    X, Y, Z = RGB2XYZ(R, G, B, rgb_space, eotf=eotf)
    return XYZ2ICtCp(X, Y, Z, clamp, oetf)


def ICtCp2RGB(
    I,
    Ct,
    Cp,
    rgb_space="Rec. 2020",
    eotf=lambda v: specialpow(v, -2084),
    clamp=False,
    oetf=lambda E: specialpow(E, 1.0 / -2084),
):
    """ICtCp to R'G'B'"""
    X, Y, Z = ICtCp2XYZ(I, Ct, Cp, eotf)
    return XYZ2RGB(X, Y, Z, rgb_space, clamp=clamp, oetf=oetf)


def XYZ2ICtCp(X, Y, Z, clamp=False, oetf=lambda E: specialpow(E, 1.0 / -2084)):
    R, G, B = XYZ2RGB(X, Y, Z, "Rec. 2020", clamp=clamp, oetf=lambda v: v)
    return LinearRGB2ICtCp(R, G, B, oetf)


def ICtCp2XYZ(I, Ct, Cp, eotf=lambda v: specialpow(v, -2084)):
    R, G, B = ICtCp2LinearRGB(I, Ct, Cp, eotf)
    return RGB2XYZ(R, G, B, "Rec. 2020", eotf=lambda v: v)


def RGB2Lab(R, G, B, rgb_space=None, whitepoint=None, noadapt=False, cat="Bradford"):
    X, Y, Z = RGB2XYZ(R, G, B, rgb_space, scale=100)
    if not noadapt:
        rgb_space = get_rgb_space(rgb_space)
        X, Y, Z = adapt(X, Y, Z, rgb_space[1], whitepoint, cat)
    return XYZ2Lab(X, Y, Z, whitepoint=whitepoint)


def RGB2XYZ(R, G, B, rgb_space=None, scale=1.0, eotf=None):
    """Convert from RGB to XYZ.

    Use optional RGB colorspace definition, which can be a named colorspace
    (e.g. "CIE RGB") or must be a tuple in the following format:

    (gamma, whitepoint, red, green, blue)

    whitepoint can be a string (e.g. "D50"), a tuple of XYZ coordinates,
    or a color temperatur in degrees K (float or int). Gamma should be a float.
    The RGB primaries red, green, blue should be lists or tuples of xyY
    coordinates (only x and y will be used, so Y can be zero or None).

    If no colorspace is given, it defaults to sRGB.

    Based on formula from http://brucelindbloom.com/Eqn_RGB_to_XYZ.html

    Implementation Notes:
    1. The transformation matrix [M] is calculated from the RGB reference
       primaries as discussed here:
       http://brucelindbloom.com/Eqn_RGB_XYZ_Matrix.html
    2. The gamma values for many common RGB color spaces may be found here:
       http://brucelindbloom.com/WorkingSpaceInfo.html#Specifications
    3. Your input RGB values may need to be scaled before using the above.
       For example, if your values are in the range [0, 255], you must first
       divide each by 255.0.
    4. The output XYZ values are in the nominal range [0.0, scale].
    5. The XYZ values will be relative to the same reference white as the
       RGB system. If you want XYZ relative to a different reference white,
       you must apply a chromatic adaptation transform
       [http://brucelindbloom.com/Eqn_ChromAdapt.html] to the XYZ color to
       convert it from the reference white of the RGB system to the desired
       reference white.
    6. Sometimes the more complicated special case of sRGB shown above is
       replaced by a "simplified" version using a straight gamma function
       with gamma = 2.2.

    """
    trc, whitepoint, rxyY, gxyY, bxyY, matrix = get_rgb_space(rgb_space)
    RGB = [R, G, B]
    is_trc = isinstance(trc, (list, tuple))
    for i, v in enumerate(RGB):
        if is_trc:
            gamma = trc[i]
        else:
            gamma = trc
        if eotf:
            RGB[i] = eotf(v)
        elif isinstance(gamma, (list, tuple)):
            RGB[i] = interp(
                v, [n / float(len(gamma) - 1) for n in range(len(gamma))], gamma
            )
        else:
            RGB[i] = specialpow(v, gamma)
    XYZ = matrix * RGB
    return tuple(v * scale for v in XYZ)


def RGB2xyY(R, G, B, rgb_space=None, scale=1.0, eotf=None):
    """Convert RGB to xyY"""
    return XYZ2xyY(
        *RGB2XYZ(R, G, B, rgb_space, scale, eotf),
        whitepoint=RGB2XYZ(1, 1, 1, rgb_space, scale, eotf),
    )


def RGB2YCbCr(R, G, B, rgb_space="NTSC 1953", bits=8, fullrange=False):
    """R'G'B' to Y'CbCr quantized to n bits"""
    return YPbPr2YCbCr(*RGB2YPbPr(R, G, B, rgb_space), bits=bits, fullrange=fullrange)


def RGB2YPbPr(R, G, B, rgb_space="NTSC 1953"):
    """R'G'B' to Y'PbPr"""
    return RGB2YPbPr_matrix(rgb_space) * (R, G, B)


def RGB2YPbPr_matrix(rgb_space="NTSC 1953"):
    (trc, whitepoint, (rx, ry, rY), (gx, gy, gY), (bx, by, bY), matrix) = get_rgb_space(
        rgb_space
    )
    if matrix == get_rgb_space("NTSC 1953")[-1]:
        ndigits = 3
    else:
        ndigits = 4
    KR = round((matrix * (1, 0, 0))[1], ndigits)
    KB = round((matrix * (0, 0, 1))[1], ndigits)
    KG = 1.0 - KR - KB
    Pb_scale = (1 - KB) / 0.5
    Pr_scale = (1 - KR) / 0.5
    return Matrix3x3(
        [
            [KR, KG, KB],
            [-KR / Pb_scale, -KG / Pb_scale, 0.5],
            [0.5, -KG / Pr_scale, -KB / Pr_scale],
        ]
    )


def YCbCr2YPbPr(Y, Cb, Cr, bits=8, fullrange=False):
    """Y'CbCr to Y'PbPr"""
    bitlevels = 2**bits
    if not fullrange:
        Yblack = 16
        Ywhite = 235
        Cmax = 240
    else:
        Yblack = 0
        Ywhite = 255
        Cmax = 255
    Yscale = (Ywhite - Yblack) / 256.0 * bitlevels
    Y -= Yblack / 256.0 * bitlevels
    Y /= Yscale
    Cneutral = 128 / 256.0 * bitlevels
    Cscale = (Cmax - Yblack) / 256.0 * bitlevels
    Pb = Cb - Cneutral
    Pb /= Cscale
    Pr = Cr - Cneutral
    Pr /= Cscale
    return Y, Pb, Pr


def YCbCr2RGB(
    Y,
    Cb,
    Cr,
    rgb_space="NTSC 1953",
    bits=8,
    fullrange=False,
    scale=1.0,
    round_=False,
    clamp=True,
):
    """Y'CbCr to R'G'B'"""
    Y, Pb, Pr = YCbCr2YPbPr(Y, Cb, Cr, bits, fullrange)
    return YPbPr2RGB(Y, Pb, Pr, rgb_space, scale, round_, clamp)


def YPbPr2RGB(Y, Pb, Pr, rgb_space="NTSC 1953", scale=1.0, round_=False, clamp=True):
    """Y'PbPr to R'G'B'"""
    RGB = RGB2YPbPr_matrix(rgb_space).inverted() * (Y, Pb, Pr)
    for i in range(3):
        if clamp:
            RGB[i] = min(1.0, max(0.0, RGB[i]))
        RGB[i] *= scale
        if round_ is not False:
            RGB[i] = round(RGB[i], round_)
    return RGB


def YPbPr2YCbCr(Y, Pb, Pr, bits=8, fullrange=False):
    """Y'PbPr to Y'CbCr quantized to n bits"""
    bitlevels = 2**bits
    if not fullrange:
        Yblack = 16
        Ywhite = 235
        Cmax = 240
    else:
        Yblack = 0
        Ywhite = 255
        Cmax = 255
    Yscale = (Ywhite - Yblack) / 256.0 * bitlevels
    Y = Yblack / 256.0 * bitlevels + Yscale * Y
    Cneutral = 128 / 256.0 * bitlevels
    Cscale = (Cmax - Yblack) / 256.0 * bitlevels
    Cb = Cneutral + Cscale * Pb
    Cr = Cneutral + Cscale * Pr
    # In fullrange mode, Cb and Cr can reach 255.5, so we need to clamp
    # Follow ITU-T Rec. T.871 (JPEG)
    Y, Cb, Cr = (min(max(int(round(v)), 0), bitlevels - 1) for v in (Y, Cb, Cr))
    return Y, Cb, Cr


def RGBsaturation(R, G, B, saturation, rgb_space=None):
    """(De)saturate a RGB color in CIE xy and return the RGB and xyY values"""
    whitepoint = RGB2XYZ(1, 1, 1, rgb_space=rgb_space)
    X, Y, Z = RGB2XYZ(R, G, B, rgb_space=rgb_space)
    XYZ, xyY = XYZsaturation(X, Y, Z, saturation, whitepoint)
    return XYZ2RGB(*XYZ, rgb_space=rgb_space), xyY


def XYZsaturation(X, Y, Z, saturation, whitepoint=None):
    """(De)saturate a XYZ color in CIE xy and return the RGB and xyY values"""
    wx, wy, wY = XYZ2xyY(*get_whitepoint(whitepoint))
    x, y, Y = XYZ2xyY(X, Y, Z)
    x, y, Y = xyYsaturation(x, y, Y, wx, wy, saturation)
    return xyY2XYZ(x, y, Y), (x, y, Y)


def xyYsaturation(x, y, Y, wx, wy, saturation):
    """(De)saturate a color in CIE xy and return the RGB and xyY values"""
    return wx + (x - wx) * saturation, wy + (y - wy) * saturation, Y


def convert_range(v, oldmin=0, oldmax=1, newmin=0, newmax=1):
    oldrange = float(oldmax - oldmin)
    newrange = newmax - newmin
    return (((v - oldmin) * newrange) / oldrange) + newmin


def rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, whitepoint=None, scale=1.0):
    """Create and return an RGB to XYZ matrix."""
    whitepoint = get_whitepoint(whitepoint, scale)
    Xr, Yr, Zr = xyY2XYZ(rx, ry, scale)
    Xg, Yg, Zg = xyY2XYZ(gx, gy, scale)
    Xb, Yb, Zb = xyY2XYZ(bx, by, scale)
    Sr, Sg, Sb = (
        Matrix3x3(((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))).inverted() * whitepoint
    )
    return Matrix3x3(
        (
            (Sr * Xr, Sg * Xg, Sb * Xb),
            (Sr * Yr, Sg * Yg, Sb * Yb),
            (Sr * Zr, Sg * Zg, Sb * Zb),
        )
    )


def find_primaries_wp_xy_rgb_space_name(xy, rgb_space_names=None, digits=4):
    """Given primaries and whitepoint xy as list, find matching RGB space by
    comparing primaries and whitepoint (fuzzy match rounded to n digits) and
    return its name (or None if no match)
    """
    for _i, rgb_space_name in enumerate(rgb_space_names or iter(rgb_spaces.keys())):
        if not rgb_space_names and rgb_space_name in (
            "ECI RGB",
            "ECI RGB v2",
            "SMPTE 240M",
            "sRGB",
        ):
            # Skip in favor of base color space (i.e. NTSC 1953, SMPTE-C and
            # Rec. 709)
            continue
        if get_rgb_space_primaries_wp_xy(rgb_space_name, digits)[: len(xy)] == xy:
            return rgb_space_name


def get_rgb_space(rgb_space=None, scale=1.0):
    """Return gamma, whitepoint, primaries and RGB -> XYZ matrix"""
    if not rgb_space:
        rgb_space = "sRGB"
    if isinstance(rgb_space, str):
        rgb_space = rgb_spaces[rgb_space]
    cachehash = tuple(map(id, rgb_space[:5])), scale
    if cachehash in get_rgb_space.cache:
        return get_rgb_space.cache[cachehash]
    gamma = rgb_space[0] or rgb_spaces["sRGB"][0]
    whitepoint = get_whitepoint(rgb_space[1] or rgb_spaces["sRGB"][1], scale)
    rx, ry, rY = rxyY = rgb_space[2] or rgb_spaces["sRGB"][2]
    gx, gy, gY = gxyY = rgb_space[3] or rgb_spaces["sRGB"][3]
    bx, by, bY = bxyY = rgb_space[4] or rgb_spaces["sRGB"][4]
    matrix = rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, whitepoint, scale)
    rgb_space = gamma, whitepoint, rxyY, gxyY, bxyY, matrix
    get_rgb_space.cache[cachehash] = rgb_space
    return rgb_space


def get_rgb_space_primaries_wp_xy(rgb_space=None, digits=4):
    """Given RGB space, get primaries and whitepoint xy, optionally rounded to n
    digits (default 4)

    """
    rgb_space = get_rgb_space(rgb_space)
    xy = []
    for i in range(3):
        xy.extend(rgb_space[2:][i][:2])
    xy.extend(XYZ2xyY(*get_whitepoint(rgb_space[1]))[:2])
    if digits:
        xy = [round(v, digits) for v in xy]
    return xy


get_rgb_space.cache = {}


def get_standard_illuminant(
    illuminant_name="D50",
    priority=("ISO 11664-2:2007", "ICC", "ASTM E308-01", "Wyszecki & Stiles", None),
    scale=1.0,
):
    """Return a standard illuminant as XYZ coordinates."""
    cachehash = illuminant_name, tuple(priority), scale
    if cachehash in get_standard_illuminant.cache:
        return get_standard_illuminant.cache[cachehash]
    illuminant = None
    for standard_name in priority:
        if standard_name not in standard_illuminants:
            raise ValueError('Unrecognized standard "%s"' % standard_name)
        illuminant = standard_illuminants.get(standard_name).get(
            illuminant_name.upper(), None
        )
        if illuminant:
            illuminant = illuminant["X"] * scale, 1.0 * scale, illuminant["Z"] * scale
            get_standard_illuminant.cache[cachehash] = illuminant
            return illuminant
    raise ValueError('Unrecognized illuminant "%s"' % illuminant_name)


get_standard_illuminant.cache = {}


def get_whitepoint(whitepoint=None, scale=1.0, planckian=False):
    """Return a whitepoint as XYZ coordinates"""
    if isinstance(whitepoint, (list, tuple)):
        return whitepoint
    if not whitepoint:
        whitepoint = "D50"
    cachehash = whitepoint, scale, planckian
    if cachehash in get_whitepoint.cache:
        return get_whitepoint.cache[cachehash]
    if isinstance(whitepoint, str):
        whitepoint = get_standard_illuminant(whitepoint)
    elif isinstance(whitepoint, (float, int)):
        cct = whitepoint
        if planckian:
            whitepoint = planckianCT2XYZ(cct)
            if not whitepoint:
                raise ValueError(
                    "Planckian color temperature %s out of range (1667, 25000)" % cct
                )
        else:
            whitepoint = CIEDCCT2XYZ(cct)
            if not whitepoint:
                raise ValueError(
                    "Daylight color temperature %s out of range (2500, 25000)" % cct
                )
    if scale > 1.0 and whitepoint[1] == 100:
        scale = 1.0
    whitepoint = tuple(v * scale for v in whitepoint)
    get_whitepoint.cache[cachehash] = whitepoint
    return whitepoint


get_whitepoint.cache = {}


def make_monotonically_increasing(iterable, passes=0, window=None):
    """Given an iterable or sequence, make the values strictly monotonically
    increasing (no repeated successive values) by linear interpolation.

    If iterable is a dict, keep the keys of the original.

    If passes is non-zero, apply moving average smoothing to the values
    before making them monotonically increasing.

    """
    if isinstance(iterable, dict):
        keys = list(iterable.keys())
        values = list(iterable.values())
    else:
        if hasattr(iterable, "next"):
            values = list(iterable)
        else:
            values = iterable
        keys = range(len(values))
    if passes:
        values = smooth_avg(values, passes, window)
    sequence = list(zip(keys, values))
    numvalues = len(sequence)
    s_new = []
    y_min = sequence[0][1]
    while sequence:
        x, y = sequence.pop()
        if (not s_new or y < s_new[0][1]) and (y > y_min or not sequence):
            s_new.insert(0, (x, y))
    sequence = s_new
    # Interpolate to original size
    x_new = [item[0] for item in sequence]
    y = [item[1] for item in sequence]
    values = []
    for i in range(numvalues):
        values.append(interp(i, x_new, y))
    if isinstance(iterable, dict):
        # Add in original keys
        return iterable.__class__(list(zip(keys, values)))
    return values


def matmul(XYZ, m1, m2):
    XYZ = m1 * (m2 * XYZ)
    return XYZ


def planckianCT2XYZ(T, scale=1.0):
    """Convert from planckian temperature to XYZ.

    T = temperature in Kelvin.

    """
    xyY = planckianCT2xyY(T, scale)
    if xyY:
        return xyY2XYZ(*xyY)


def planckianCT2xyY(T, scale=1.0):
    """Convert from planckian temperature to xyY.

    T = temperature in Kelvin.

    Formula from http://en.wikipedia.org/wiki/Planckian_locus

    """
    if 1667 <= T <= 4000:
        x = (
            -0.2661239 * (math.pow(10, 9) / math.pow(T, 3))
            - 0.2343580 * (math.pow(10, 6) / math.pow(T, 2))
            + 0.8776956 * (math.pow(10, 3) / T)
            + 0.179910
        )
    elif 4000 <= T <= 25000:
        x = (
            -3.0258469 * (math.pow(10, 9) / math.pow(T, 3))
            + 2.1070379 * (math.pow(10, 6) / math.pow(T, 2))
            + 0.2226347 * (math.pow(10, 3) / T)
            + 0.24039
        )
    else:
        return None
    if 1667 <= T <= 2222:
        y = (
            -1.1063814 * math.pow(x, 3)
            - 1.34811020 * math.pow(x, 2)
            + 2.18555832 * x
            - 0.20219683
        )
    elif 2222 <= T <= 4000:
        y = (
            -0.9549476 * math.pow(x, 3)
            - 1.37418593 * math.pow(x, 2)
            + 2.09137015 * x
            - 0.16748867
        )
    elif 4000 <= T <= 25000:
        y = (
            3.0817580 * math.pow(x, 3)
            - 5.87338670 * math.pow(x, 2)
            + 3.75112997 * x
            - 0.37001483
        )
    return x, y, scale


def xyY2CCT(x, y, Y=1.0):
    """Convert from xyY to correlated color temperature."""
    return XYZ2CCT(*xyY2XYZ(x, y, Y))


def xyY2Lab(x, y, Y=1.0, whitepoint=None):
    X, Y, Z = xyY2XYZ(x, y, Y)
    return XYZ2Lab(X, Y, Z, whitepoint)


def xyY2Lu_v_(x, y, Y=1.0, whitepoint=None):
    X, Y, Z = xyY2XYZ(x, y, Y)
    return XYZ2Lu_v_(X, Y, Z, whitepoint)


def xyY2RGB(x, y, Y, rgb_space=None, scale=1.0, round_=False, clamp=True):
    """Convert from xyY to RGB"""
    X, Y, Z = xyY2XYZ(x, y, Y)
    return XYZ2RGB(X, Y, Z, rgb_space, scale, round_, clamp)


def xyY2XYZ(x, y, Y=1.0):
    """Convert from xyY to XYZ.

    Based on formula from http://brucelindbloom.com/Eqn_xyY_to_XYZ.html

    Implementation Notes:
    1. Watch out for the case where y = 0. In that case, X = Y = Z = 0 is
       returned.
    2. The output XYZ values are in the nominal range [0.0, Y[xyY]].

    """
    if y == 0:
        return 0, 0, 0
    X = float(x * Y) / y
    Z = float((1 - x - y) * Y) / y
    return X, Y, Z


def LERP(a, b, c):
    """LERP(a,b,c) = linear interpolation macro.

    Is 'a' when c == 0.0 and 'b' when c == 1.0

    """
    return (b - a) * c + a


def XYZ2CCT(X, Y, Z):
    """Convert from XYZ to correlated color temperature.

    Derived from ANSI C implementation by Bruce Lindbloom
    http://brucelindbloom.com/Eqn_XYZ_to_T.html

    Return: correlated color temperature if successful, else None.

    Description:
    This is an implementation of Robertson's method of computing the
    correlated color temperature of an XYZ color. It can compute correlated
    color temperatures in the range [1666.7K, infinity].

    Reference:
    "Color Science: Concepts and Methods, Quantitative Data and Formulae",
    Second Edition, Gunter Wyszecki and W. S. Stiles, John Wiley & Sons,
    1982, pp. 227, 228.

    """
    rt = [  # reciprocal temperature (K)
        DBL_MIN,
        10.0e-6,
        20.0e-6,
        30.0e-6,
        40.0e-6,
        50.0e-6,
        60.0e-6,
        70.0e-6,
        80.0e-6,
        90.0e-6,
        100.0e-6,
        125.0e-6,
        150.0e-6,
        175.0e-6,
        200.0e-6,
        225.0e-6,
        250.0e-6,
        275.0e-6,
        300.0e-6,
        325.0e-6,
        350.0e-6,
        375.0e-6,
        400.0e-6,
        425.0e-6,
        450.0e-6,
        475.0e-6,
        500.0e-6,
        525.0e-6,
        550.0e-6,
        575.0e-6,
        600.0e-6,
    ]
    uvt = [
        [0.18006, 0.26352, -0.24341],
        [0.18066, 0.26589, -0.25479],
        [0.18133, 0.26846, -0.26876],
        [0.18208, 0.27119, -0.28539],
        [0.18293, 0.27407, -0.30470],
        [0.18388, 0.27709, -0.32675],
        [0.18494, 0.28021, -0.35156],
        [0.18611, 0.28342, -0.37915],
        [0.18740, 0.28668, -0.40955],
        [0.18880, 0.28997, -0.44278],
        [0.19032, 0.29326, -0.47888],
        [0.19462, 0.30141, -0.58204],
        [0.19962, 0.30921, -0.70471],
        [0.20525, 0.31647, -0.84901],
        [0.21142, 0.32312, -1.0182],
        [0.21807, 0.32909, -1.2168],
        [0.22511, 0.33439, -1.4512],
        [0.23247, 0.33904, -1.7298],
        [0.24010, 0.34308, -2.0637],
        [0.24792, 0.34655, -2.4681],  # Note: 0.24792 is a corrected value
        # for the error found in W&S as 0.24702
        [0.25591, 0.34951, -2.9641],
        [0.26400, 0.35200, -3.5814],
        [0.27218, 0.35407, -4.3633],
        [0.28039, 0.35577, -5.3762],
        [0.28863, 0.35714, -6.7262],
        [0.29685, 0.35823, -8.5955],
        [0.30505, 0.35907, -11.324],
        [0.31320, 0.35968, -15.628],
        [0.32129, 0.36011, -23.325],
        [0.32931, 0.36038, -40.770],
        [0.33724, 0.36051, -116.45],
    ]
    if (X < 1.0e-20 and Y < 1.0e-20 and Z < 1.0e-20) or X + 15.0 * Y + 3.0 * Z == 0:
        return None  # protect against possible divide-by-zero failure
    us = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
    vs = (6.0 * Y) / (X + 15.0 * Y + 3.0 * Z)
    dm = 0.0
    i = 0
    while i < 31:
        di = (vs - uvt[i][1]) - uvt[i][2] * (us - uvt[i][0])
        if i > 0 and ((di < 0.0 <= dm) or (di >= 0.0 > dm)):
            break  # found lines bounding (us, vs) : i-1 and i
        dm = di
        i += 1
    if i == 31:
        # bad XYZ input, color temp would be less than minimum of 1666.7
        # degrees, or too far towards blue
        return None
    di = di / math.sqrt(1.0 + uvt[i][2] * uvt[i][2])
    dm = dm / math.sqrt(1.0 + uvt[i - 1][2] * uvt[i - 1][2])
    p = dm / (dm - di)  # p = interpolation parameter, 0.0 : i-1, 1.0 : i
    p = 1.0 / (LERP(rt[i - 1], rt[i], p))
    return p


def XYZ2DIN99(X, Y, Z, whitepoint=None):
    X, Y, Z = (max(v, 0) for v in (X, Y, Z))
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return Lab2DIN99(L, a, b)


def XYZ2DIN99b(X, Y, Z, whitepoint=None):
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return Lab2DIN99b(L, a, b)


def XYZ2DIN99o(X, Y, Z, whitepoint=None):
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return Lab2DIN99o(L, a, b)


def XYZ2DIN99bLCH(X, Y, Z, whitepoint=None):
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return Lab2DIN99bLCH(L, a, b)


def XYZ2DIN99oLCH(X, Y, Z, whitepoint=None):
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return Lab2DIN99oLCH(L, a, b)


def XYZ2DIN99c(X, Y, Z, whitepoint=None):
    return XYZ2DIN99cd(X, Y, Z, 0.1, 317.651, 0.0037, 0, 0.94, 23, 0.066, whitepoint)


def XYZ2DIN99cd(X, Y, Z, x, l1, l2, deg, f1, c1, c2, whitepoint=None):
    L99, C99, H99 = XYZ2DIN99cdLCH(X, Y, Z, x, l1, l2, deg, f1, c1, c2, whitepoint)
    a99, b99 = DIN99familyCH2DIN99ab(C99, H99)
    return L99, a99, b99


def XYZ2DIN99cdLCH(X, Y, Z, x, l1, l2, deg, f1, c1, c2, whitepoint=None):
    X, Y, Z = XYZ2DIN99cdXYZ(X, Y, Z, x)
    whitepoint99d = XYZ2DIN99cdXYZ(*get_whitepoint(whitepoint, 100), x=x)
    L, a, b = XYZ2Lab(X, Y, Z, whitepoint99d)
    return Lab2DIN99familyLCH(L, a, b, l1, l2, deg, f1, c1, c2)


def XYZ2DIN99cdXYZ(X, Y, Z, x):
    X = (1 + x) * X - x * Z
    return X, Y, Z


def XYZ2DIN99d(X, Y, Z, whitepoint=None):
    return XYZ2DIN99cd(X, Y, Z, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint)


def XYZ2DIN99dLCH(X, Y, Z, whitepoint=None):
    return XYZ2DIN99cdLCH(
        X, Y, Z, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint
    )


def XYZ2IPT(X, Y, Z):
    XYZ2LMS_matrix = get_cat_matrix("IPT")
    LMS = XYZ2LMS_matrix * (X, Y, Z)
    for i, component in enumerate(LMS):
        if component >= 0:
            LMS[i] **= 0.43
        else:
            LMS[i] = -((-component) ** 0.43)
    return LMS2IPT_matrix * LMS


def IPT2XYZ(I, P, T):
    XYZ2LMS_matrix = get_cat_matrix("IPT")
    LMS2XYZ_matrix = XYZ2LMS_matrix.inverted()
    LMS = IPT2LMS_matrix * (I, P, T)
    for i, component in enumerate(LMS):
        if component >= 0:
            LMS[i] **= 1 / 0.43
        else:
            LMS[i] = -((-component) ** (1 / 0.43))
    return LMS2XYZ_matrix * LMS


def XYZ2Lab(X, Y, Z, whitepoint=None, scale=100):
    """Convert from XYZ to Lab.

    The input Y value needs to be in the nominal range [0.0, scale] and
    other input values scaled accordingly.
    The output L value is in the nominal range [0.0, 100.0].

    whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or
    color temperature as float or int. Defaults to D50 if not set.

    Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_Lab.html

    """
    Xr, Yr, Zr = get_whitepoint(whitepoint, scale)

    xr = X / Xr
    yr = Y / Yr
    zr = Z / Zr
    fx = cbrt(xr) if xr > LSTAR_E else (LSTAR_K * xr + 16) / 116.0
    fy = cbrt(yr) if yr > LSTAR_E else (LSTAR_K * yr + 16) / 116.0
    fz = cbrt(zr) if zr > LSTAR_E else (LSTAR_K * zr + 16) / 116.0
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)

    return L, a, b


def XYZ2Lpt(X, Y, Z, whitepoint=None):
    """Convert from XYZ to Lpt

    This is a modern update to L*a*b*, based on IPT space.

    Differences to L*a*b* and IPT:
    - Using inverse CIE 2012 2degree LMS to XYZ matrix instead of
      Hunt-Pointer-Estevez Von Kries chromatic adapation in LMS space.
    - Using L* compression rather than IPT pure 0.43 power.
    - Tweaked LMS' to IPT matrix to account for change in XYZ to LMS matrix.
    - Output scaled to L*a*b* type ranges, to maintain 1 JND scale.
    - L* value is not a non-linear Y value.

    The input Y value needs to be in the nominal range [0.0, 100.0] and
    other input values scaled accordingly.
    The output L value is in the nominal range [0.0, 100.0].

    whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or
    color temperature as float or int. Defaults to D50 if not set.

    """
    # Adapted from Argyll/icc/icc.c
    from DisplayCAL import argyll

    if argyll.get_argyll_version("dispwin") < [3, 4, 0]:
        observer_name = "CIE2012_2"
    else:
        observer_name = "CIE2015_2"
    xyz2lms = get_cat_matrix(observer_name)

    wlms = xyz2lms * get_whitepoint(whitepoint, 100)

    lms = xyz2lms * (X, Y, Z)

    for j in range(3):
        lms[j] /= wlms[j]

        if lms[j] > 0.008856451586:
            lms[j] = pow(lms[j], 1.0 / 3.0)
        else:
            lms[j] = 7.787036979 * lms[j] + 16.0 / 116.0
        lms[j] = 116.0 * lms[j] - 16.0

    return LMS2Lpt_matrix * lms


def Lpt2XYZ(L, p, t, whitepoint=None, scale=1.0):
    """Convert from Lpt to XYZ

    This is a modern update to L*a*b*, based on IPT space.

    Differences to L*a*b* and IPT:
    - Using inverse CIE 2012 2degree LMS to XYZ matrix instead of
      Hunt-Pointer-Estevez Von Kries chromatic adapation in LMS space.
    - Using L* compression rather than IPT pure 0.43 power.
    - Tweaked LMS' to IPT matrix to account for change in XYZ to LMS matrix.
    - Output scaled to L*a*b* type ranges, to maintain 1 JND scale.
    - L* value is not a non-linear Y value.

    The input L* value needs to be in the nominal range [0.0, 100.0] and
    other input values scaled accordingly.
    The output XYZ values are in the nominal range [0.0, 1.0].

    whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or
    color temperature as float or int. Defaults to D50 if not set.

    """
    # Adapted from Argyll/icc/icc.c

    from DisplayCAL import argyll

    if argyll.get_argyll_version("dispwin") < [3, 4, 0]:
        observer_name = "CIE2012_2"
    else:
        observer_name = "CIE2015_2"

    xyz2lms = get_cat_matrix(observer_name)
    lms2xyz = xyz2lms.inverted()

    wlms = xyz2lms * get_whitepoint(whitepoint, scale)

    lms = Lpt2LMS_matrix * (L, p, t)

    for j in range(3):
        lms[j] = (lms[j] + 16.0) / 116.0

        if lms[j] > 24.0 / 116.0:
            lms[j] = pow(lms[j], 3.0)
        else:
            lms[j] = (lms[j] - 16.0 / 116.0) / 7.787036979

        lms[j] *= wlms[j]

    return lms2xyz * lms


def XYZ2Lu_v_(X, Y, Z, whitepoint=None):
    """Convert from XYZ to CIE Lu'v'"""

    if X + Y + Z == 0:
        # We can't check for X == Y == Z == 0 because they may actually add up
        # to 0, thus resulting in ZeroDivisionError later
        L, u_, v_ = XYZ2Lu_v_(*get_whitepoint(whitepoint))
        return 0.0, u_, v_

    Xr, Yr, Zr = get_whitepoint(whitepoint, 100)

    yr = Y / Yr

    L = 116.0 * cbrt(yr) - 16.0 if yr > LSTAR_E else LSTAR_K * yr

    u_ = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
    v_ = (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z)

    return L, u_, v_


def XYZ2Luv(X, Y, Z, whitepoint=None):
    """Convert from XYZ to Luv"""

    if X + Y + Z == 0:
        # We can't check for X == Y == Z == 0 because they may actually add up
        # to 0, thus resulting in ZeroDivisionError later
        L, u, v = XYZ2Luv(*get_whitepoint(whitepoint))
        return 0.0, u, v

    Xr, Yr, Zr = get_whitepoint(whitepoint, 100)

    yr = Y / Yr

    L = 116.0 * cbrt(yr) - 16.0 if yr > LSTAR_E else LSTAR_K * yr

    u_ = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
    v_ = (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z)

    u_r = (4.0 * Xr) / (Xr + 15.0 * Yr + 3.0 * Zr)
    v_r = (9.0 * Yr) / (Xr + 15.0 * Yr + 3.0 * Zr)

    u = 13.0 * L * (u_ - u_r)
    v = 13.0 * L * (v_ - v_r)

    return L, u, v


def XYZ2RGB(X, Y, Z, rgb_space=None, scale=1.0, round_=False, clamp=True, oetf=None):
    """Convert from XYZ to RGB.

    Use optional RGB colorspace definition, which can be a named colorspace
    (e.g. "CIE RGB") or must be a tuple in the following format:

    (gamma, whitepoint, red, green, blue)

    whitepoint can be a string (e.g. "D50"), a tuple of XYZ coordinates,
    or a color temperatur in degrees K (float or int). Gamma should be a float.
    The RGB primaries red, green, blue should be lists or tuples of xyY
    coordinates (only x and y will be used, so Y can be zero or None).

    If no colorspace is given, it defaults to sRGB.

    Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_RGB.html

    Implementation Notes:
    1. The transformation matrix [M] is calculated from the RGB reference
       primaries as discussed here:
       http://brucelindbloom.com/Eqn_RGB_XYZ_Matrix.html
    2. gamma is the gamma value of the RGB color system used. Many common ones
       may be found here:
       http://brucelindbloom.com/WorkingSpaceInfo.html#Specifications
    3. The output RGB values are in the nominal range [0.0, scale].
    4. If the input XYZ color is not relative to the same reference white as
       the RGB system, you must first apply a chromatic adaptation transform
       [http://brucelindbloom.com/Eqn_ChromAdapt.html] to the XYZ color to
       convert it from its own reference white to the reference white of the
       RGB system.
    5. Sometimes the more complicated special case of sRGB shown above is
       replaced by a "simplified" version using a straight gamma function with
       gamma = 2.2.

    """
    trc, whitepoint, rxyY, gxyY, bxyY, matrix = get_rgb_space(rgb_space)
    RGB = matrix.inverted() * [X, Y, Z]
    is_trc = isinstance(trc, (list, tuple))
    for i, v in enumerate(RGB):
        if is_trc:
            gamma = trc[i]
        else:
            gamma = trc
        if clamp:
            v = min(1.0, max(0.0, v))
        if oetf:
            RGB[i] = oetf(v)
        elif isinstance(gamma, (list, tuple)):
            key = id(gamma)
            if key not in XYZ2RGB.interp:
                ginterp = Interp(
                    gamma,
                    [n / float(len(gamma) - 1) for n in range(len(gamma))],
                    use_numpy=True,
                )
                XYZ2RGB.interp[key] = ginterp
            else:
                ginterp = XYZ2RGB.interp[key]
            RGB[i] = ginterp(v)
        else:
            RGB[i] = specialpow(v, 1.0 / gamma)
        RGB[i] *= scale
        if round_ is not False:
            RGB[i] = round(RGB[i], round_)
    return RGB


XYZ2RGB.interp = {}


def XYZ2xyY(X, Y, Z, whitepoint=None):
    """Convert from XYZ to xyY.

    Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_xyY.html

    Implementation Notes:
    1. Watch out for black, where X = Y = Z = 0. In that case, x and y are set
       to the chromaticity coordinates of the reference whitepoint.
    2. The output Y value is in the nominal range [0.0, Y[XYZ]].

    """
    if X + Y + Z == 0:
        # We can't check for X == Y == Z == 0 because they may actually add up
        # to 0, thus resulting in ZeroDivisionError later
        x, y, Y = XYZ2xyY(*get_whitepoint(whitepoint))
        return x, y, 0.0
    x = X / float(X + Y + Z)
    y = Y / float(X + Y + Z)
    return x, y, Y


def xy_CCT_delta(x, y, daylight=True, method=2000):
    """Return CCT and delta to locus"""
    cct = xyY2CCT(x, y)
    d = None
    if cct:
        locus = None
        if daylight:
            # Daylight locus
            if 2500 <= cct <= 25000:
                locus = CIEDCCT2XYZ(cct, 100.0)
        else:
            # Planckian locus
            if 1667 <= cct <= 25000:
                locus = planckianCT2XYZ(cct, 100.0)
        if locus:
            L2, a2, b2 = xyY2Lab(x, y, 100.0, locus)
            d = delta(L2, 0, 0, L2, a2, b2, method)
    return cct, d


def dmatrixz(nrl, nrh, ncl, nch):
    # Adapted from ArgyllCMS numlib/numsup.c

    # nrl  # Row low index
    # nrh  # Row high index
    # ncl  # Col low index
    # nch  # Col high index
    m = {}

    if nrh < nrl:  # Prevent failure for 0 dimension
        nrh = nrl
    if nch < ncl:
        nch = ncl

    rows = nrh - nrl + 1
    cols = nch - ncl + 1

    for i in range(rows):
        m[i + nrl] = {}
        for j in range(cols):
            m[i][j + ncl] = 0

    return m


def dvector(nl, nh):
    # Adapted from ArgyllCMS numlib/numsup.c

    # nl  # Lowest index
    # nh  # Highest index
    return {}


def gam_fit(gf, v):
    # Adapted from ArgyllCMS xicc/xicc.c
    """gamma + input offset function handed to powell()"""
    gamma = v[0]
    rv = 0.0

    if gamma < 0.0:
        rv += 100.0 * -gamma
        gamma = 1e-4

    t1 = math.pow(gf.bp, 1.0 / gamma)
    t2 = math.pow(gf.wp, 1.0 / gamma)
    b = t1 / (t2 - t1)  # Offset
    a = math.pow(t2 - t1, gamma)  # Gain

    # Comput 50% output for this technical gamma
    # (All values are without output offset being added in)
    t1 = a * math.pow(0.5 + b, gamma)
    t1 = t1 - gf.thyr
    rv += t1 * t1

    return rv


def linmin(cp, xi, di, ftol, func, fdata):
    # Adapted from ArgyllCMS numlib/powell.c

    """
    Line bracketing and minimisation routine.
    Return value at minimum.

    """
    POWELL_GOLD = 1.618034
    POWELL_CGOLD = 0.3819660
    POWELL_MAXIT = 100
    # cp  # Start point, and returned value
    # xi[]  # Search vector
    # di  # Dimensionality
    # ftol  # Tolerance to stop on
    # func  # Error function to evaluate
    # fdata  # Opaque data for func()
    # ax, xx, bx  # Search vector multipliers
    # af, xf, bf  # Function values at those points
    # xt, XT  # Trial point
    XT = {}

    if di <= 10:
        xt = XT
    else:
        xt = dvector(0, di - 1)  # Vector for trial point

    # --------------------------
    # First bracket the solution

    logging.debug("linmin: Bracketing solution")

    # The line is measured as startpoint + offset * search vector.
    # (Search isn't symetric, but it seems to depend on cp being
    # best current solution ?)
    ax = 0.0
    for i in range(di):
        xt[i] = cp[i] + ax * xi[i]
    af = func(fdata, xt)

    # xx being vector offset 0.618
    xx = 1.0 / POWELL_GOLD
    for i in range(di):
        xt[i] = cp[i] + xx * xi[i]
    xf = func(fdata, xt)

    logging.debug("linmin: Initial points a:%f:%f -> b:%f:%f" % (ax, af, xx, xf))

    # Fix it so that we are decreasing from point a -> x
    if xf > af:
        tt = ax
        ax = xx
        xx = tt
        tt = af
        af = xf
        xf = tt

    logging.debug(
        "linmin: Ordered Initial points a:%f:%f -> b:%f:%f" % (ax, af, xx, xf)
    )

    bx = xx + POWELL_GOLD * (xx - ax)  # Guess b beyond a -> x
    for i in range(di):
        xt[i] = cp[i] + bx * xi[i]
    bf = func(fdata, xt)

    logging.debug(
        "linmin: Initial bracket a:%f:%f x:%f:%f b:%f:%f" % (ax, af, xx, xf, bx, bf)
    )

    # While not bracketed
    while xf > bf:
        logging.debug("linmin: Not bracketed because xf %f > bf %f" % (xf, bf))
        logging.debug("        ax = %f, xx = %f, bx = %f" % (ax, xx, bx))

        # Compute ux by parabolic interpolation from a, x & b
        q = (xx - bx) * (xf - af)
        r = (xx - ax) * (xf - bf)
        tt = q - r
        if 0.0 <= tt < 1e-20:  # If +ve too small
            tt = 1e-20
        elif 0.0 >= tt > -1e-20:  # If -ve too small
            tt = -1e-20
        ux = xx - ((xx - bx) * q - (xx - ax) * r) / (2.0 * tt)
        ulim = xx + 100.0 * (bx - xx)  # Extrapolation limit

        if (xx - ux) * (ux - bx) > 0.0:  # u is between x and b
            for i in range(di):  # Evaluate u
                xt[i] = cp[i] + ux * xi[i]
            uf = func(fdata, xt)

            if uf < bf:  # Minimum is between x and b
                ax = xx
                af = xf
                xx = ux
                xf = uf
                break
            elif uf > xf:  # Minimum is between a and u
                bx = ux
                bf = uf
                break

            # Parabolic fit didn't work, look further out in direction of b
            ux = bx + POWELL_GOLD * (bx - xx)

        elif (bx - ux) * (ux - ulim) > 0.0:  # u is between b and limit
            for i in range(di):  # Evaluate u
                xt[i] = cp[i] + ux * xi[i]
            uf = func(fdata, xt)

            if uf > bf:  # Minimum is between x and u
                ax = xx
                af = xf
                xx = bx
                xf = bf
                bx = ux
                bf = uf
                break
            xx = bx
            xf = bf  # Continue looking
            bx = ux
            bf = uf
            ux = bx + POWELL_GOLD * (bx - xx)  # Test beyond b

        elif (ux - ulim) * (ulim - bx) >= 0.0:  # u is beyond limit
            ux = ulim
        else:  # u is to left side of x ?
            ux = bx + POWELL_GOLD * (bx - xx)
        # Evaluate u, and move into place at b
        for i in range(di):
            xt[i] = cp[i] + ux * xi[i]
        uf = func(fdata, xt)
        ax = xx
        af = xf
        xx = bx
        xf = bf
        bx = ux
        bf = uf
    logging.debug(
        "linmin: Got bracket a:%f:%f x:%f:%f b:%f:%f" % (ax, af, xx, xf, bx, bf)
    )
    # Got bracketed minimum between a -> x -> b

    # ---------------------------------------
    # Now use brent minimiser bewteen a and b
    if True:
        # a and b bracket solution
        # x is best function value so far
        # w is second best function value so far
        # v is previous second best, or third best
        # u is most recently tested point
        # wx, vx, ux  # Search vector multipliers
        # wf
        vf = 0.0
        # uf  # Function values at those points
        de = 0.0  # Distance moved on previous step
        e = 0.0  # Distance moved on 2nd previous step

        # Make sure a and b are in ascending order
        if ax > bx:
            tt = ax
            ax = bx
            bx = tt
            tt = af
            af = bf
            bf = tt

        wx = vx = xx  # Initial values of other center points
        wf = xf = xf

        for _iter in range(1, POWELL_MAXIT + 1):
            mx = 0.5 * (ax + bx)  # m is center of bracket values
            # if ABSTOL:
            # tol1 = ftol  # Absolute tollerance
            # else:
            tol1 = ftol * abs(xx) + 1e-10
            tol2 = 2.0 * tol1

            logging.debug(
                "linmin: Got bracket a:%f:%f x:%f:%f b:%f:%f" % (ax, af, xx, xf, bx, bf)
            )

            # See if we're done
            if abs(xx - mx) <= (tol2 - 0.5 * (bx - ax)):
                logging.debug(
                    "linmin: We're done because %f <= %f"
                    % (abs(xx - mx), tol2 - 0.5 * (bx - ax))
                )
                break

            if abs(e) > tol1:  # Do a trial parabolic fit
                r = (xx - wx) * (xf - vf)
                q = (xx - vx) * (xf - wf)
                p = (xx - vx) * q - (xx - wx) * r
                q = 2.0 * (q - r)
                if q > 0.0:
                    p = -p
                else:
                    q = -q
                te = e  # Save previous e value
                e = de  # Previous steps distance moved

                logging.debug("linmin: Trial parabolic fit")

                if (
                    abs(p) >= abs(0.5 * q * te)
                    or p <= q * (ax - xx)
                    or p >= q * (bx - xx)
                ):
                    # Give up on the parabolic fit, and use the golden section search
                    e = (
                        ax - xx if xx >= mx else bx - xx
                    )  # Override previous distance moved */
                    de = POWELL_CGOLD * e
                    logging.debug("linmin: Moving to golden section search")
                else:  # Use parabolic fit
                    de = p / q  # Change in xb
                    ux = xx + de  # Trial point according to parabolic fit
                    if (ux - ax) < tol2 or (bx - ux) < tol2:
                        if (mx - xx) > 0.0:  # Don't use parabolic, use tol1
                            de = tol1  # tol1 is +ve
                        else:
                            de = -tol1
                    logging.debug("linmin: Using parabolic fit")
            else:  # Keep using the golden section search
                e = ax - xx if xx >= mx else bx - xx  # Override previous distance moved
                de = POWELL_CGOLD * e
                logging.debug("linmin: Continuing golden section search")

            if abs(de) >= tol1:  # If de moves as much as tol1 would
                ux = xx + de  # use it
                logging.debug("linmin: ux = %f = xx %f + de %f" % (ux, xx, de))
            else:  # else move by tol1 in direction de
                if de > 0.0:
                    ux = xx + tol1
                    logging.debug("linmin: ux = %f = xx %f + tol1 %f" % (ux, xx, tol1))
                else:
                    ux = xx - tol1
                    logging.debug("linmin: ux = %f = xx %f - tol1 %f" % (ux, xx, tol1))

            # Evaluate function
            for i in range(di):
                xt[i] = cp[i] + ux * xi[i]
            uf = func(fdata, xt)

            if uf <= xf:  # Found new best solution
                if ux >= xx:
                    ax = xx
                    af = xf  # New lower bracket
                else:
                    bx = xx
                    bf = xf  # New upper bracket
                vx = wx
                vf = wf  # New previous 2nd best solution
                wx = xx
                wf = xf  # New 2nd best solution from previous best
                xx = ux
                xf = uf  # New best solution from latest
                logging.debug("linmin: found new best solution")
            else:  # Found a worse solution
                if ux < xx:
                    ax = ux
                    af = uf  # New lower bracket
                else:
                    bx = ux
                    bf = uf  # New upper bracket
                if uf <= wf or wx == xx:  # New 2nd best solution, or equal best
                    vx = wx
                    vf = wf  # New previous 2nd best solution
                    wx = ux
                    wf = uf  # New 2nd best from latest
                elif (
                    uf <= vf or vx == xx or vx == wx
                ):  # New 3rd best, or equal 1st & 2nd
                    vx = ux
                    vf = uf  # New previous 2nd best from latest
                logging.debug("linmin: found new worse solution")
        # !!! should do something if iter > POWELL_MAXIT !!!!
        # Solution is at xx, xf

        # Compute solution vector
        for i in range(di):
            cp[i] += xx * xi[i]

    return xf


def powell(di, cp, s, ftol, maxit, func, fdata, prog=None, pdata=None):
    # Adapted from ArgyllCMS powell.c

    """
    Standard interface for powell function
    return True on sucess, False on failure due to excessive iterions
    Result will be in cp

    """
    DBL_EPSILON = 2.2204460492503131e-016
    # di  # Dimentionality
    # cp  # Initial starting point
    # s  # Size of initial search area
    # ftol  # Tolerance of error change to stop on
    # maxit  # Maximum iterations allowed
    # func  # Error function to evaluate
    # fdata  # Opaque data needed by function
    # prog  # Optional progress percentage callback
    # pdata  # Opaque data needed by prog()

    # dmtx  # Direction vector
    # sp  # Sarting point before exploring all the directions
    # xpt  # Extrapolated point
    # svec  # Search vector
    # retv  # Returned function value at p
    # stopth  # Current stop threshold */
    startdel = -1.0  # Initial change in function value
    # curdel  # Current change in function value
    pc = 0  # Percentage complete

    dmtx = dmatrixz(0, di - 1, 0, di - 1)  # Zero filled
    spt = dvector(0, di - 1)
    xpt = dvector(0, di - 1)
    svec = dvector(0, di - 1)

    # Create initial direction matrix by
    # placing search start on diagonal
    for i in range(di):
        dmtx[i][i] = s[i]
        # Save the starting point
        spt[i] = cp[i]

    if prog:  # Report initial progress
        prog(pdata, pc)

    # Initial function evaluation
    retv = func(fdata, cp)

    # Iterate untill we converge on a solution, or give up.
    for iter in range(1, maxit):
        # lretv  # Last function return value
        ibig = 0  # Index of biggest delta
        del_ = 0.0  # Biggest function value decrease
        # pretv  # Previous function return value

        pretv = retv  # Save return value at top of iteration

        # Loop over all directions in the set
        for i in range(di):
            logging.debug("Looping over direction %d" % i)

            for j in range(di):  # Extract this direction to make search vector
                svec[j] = dmtx[j][i]

            # Minimize in that direction
            lretv = retv
            retv = linmin(cp, svec, di, ftol, func, fdata)

            # Record bigest function decrease, and dimension it occured on
            if abs(lretv - retv) > del_:
                del_ = abs(lretv - retv)
                ibig = i

        # if ABSTOL:
        # stopth = ftol  # Absolute tollerance
        # else
        stopth = ftol * 0.5 * (abs(pretv) + abs(retv) + DBL_EPSILON)
        curdel = abs(pretv - retv)
        if startdel < 0.0:
            startdel = curdel
        elif curdel > 0 and startdel > 0:
            tt = (
                100.0
                * math.pow(
                    (math.log(curdel) - math.log(startdel))
                    / (math.log(stopth) - math.log(startdel)),
                    4.0,
                )
                + 0.5
            )
            if pc < tt < 100:
                pc = tt
                if prog:  # Report initial progress
                    prog(pdata, pc)

        # If we have had at least one change of direction and
        # reached a suitable tollerance, then finish
        if iter > 1 and curdel <= stopth:
            logging.debug(
                "Reached stop tollerance because curdel %f <= stopth "
                "%f" % (curdel, stopth)
            )
            break
        logging.debug("Not stopping because curdel %f > stopth %f" % (curdel, stopth))

        for i in range(di):
            svec[i] = cp[i] - spt[i]  # Average direction moved after minimization round
            xpt[i] = cp[i] + svec[i]  # Extrapolated point after round of minimization
            spt[i] = cp[i]  # New start point for next round

        # Function value at extrapolated point
        lretv = func(fdata, xpt)

        if lretv < pretv:  # If extrapolation is an improvement
            t1 = pretv - retv - del_
            t2 = pretv - lretv
            t = 2.0 * (pretv - 2.0 * retv + lretv) * t1 * t1 - del_ * t2 * t2
            if t < 0.0:
                # Move to the minimum of the new direction
                retv = linmin(cp, svec, di, ftol, func, fdata)

                for i in range(di):  # Save the new direction
                    dmtx[i][ibig] = svec[i]  # by replacing best previous

    if prog:  # Report final progress
        prog(pdata, 100)

    if iter < maxit:
        return True

    logging.debug("powell: returning False due to excessive iterations")
    return False  # Failed due to execessive iterations


def xicc_tech_gamma(egamma, off, outoffset=0.0):
    # Adapted from ArgyllCMS xicc.c

    """
    Given the effective gamma and the output offset Y,
    return the technical gamma needed for the correct 50% response.

    """
    gf = gam_fits()
    op = {}
    sa = {}

    if off <= 0.0:
        return egamma

    # We set up targets without outo being added
    outo = off * outoffset  # Offset acounted for in output
    gf.bp = off - outo  # Black value for 0 % input
    gf.wp = 1.0 - outo  # White value for 100% input
    gf.thyr = math.pow(0.5, egamma) - outo  # Advetised 50% target

    op[0] = egamma
    sa[0] = 0.1

    if not powell(1, op, sa, 1e-6, 500, gam_fit, gf):
        logging.warning("Computing effective gamma and input offset is inaccurate")

    return op[0]


class gam_fits:
    # Adapted from ArgyllCMS xicc/xicc.c

    def __init__(self, wp=1.0, thyr=0.2, bp=0.0):
        self.wp = wp  # 100% input target
        self.thyr = thyr  # 50% input target
        self.bp = bp  # 0% input target


class Interp:
    def __init__(self, xp, fp, left=None, right=None, use_numpy=False):
        if use_numpy:
            # Use numpy for speed
            import numpy

            xp = numpy.array(xp)
            fp = numpy.array(fp)
            self.numpy = numpy
        self.xp = xp
        self.fp = fp
        self.left = left
        self.right = right
        self.lookup = {}
        self.use_numpy = use_numpy

    def __call__(self, x):
        if x not in self.lookup:
            self.lookup[x] = self._interp(x)
        return self.lookup[x]

    def _interp(self, x):
        if self.use_numpy:
            import numpy

            return self.numpy.interp(x, self.xp, self.fp, self.left, self.right)
        else:
            return interp(x, self.xp, self.fp, self.left, self.right)


class BT1886:
    # Adapted from ArgyllCMS xicc/xicc.c

    """BT.1886 like transfer function"""

    def __init__(self, matrix, XYZbp, outoffset=0.0, gamma=2.4, apply_trc=True):
        """Setup BT.1886 for the given target

        If apply_trc is False, apply only the black point blending portion of
        BT.1886 mapping. Note that this will only work correctly for an output
        offset of 1.0

        """
        if not apply_trc and outoffset < 1:
            raise ValueError("Output offset must be 1.0 when not applying gamma")

        self.bwd_matrix = matrix.inverted()
        self.fwd_matrix = matrix
        self.gamma = gamma

        Lab = XYZ2Lab(*[v * 100 for v in XYZbp])

        # For bp blend
        self.outL = Lab[0]
        # a* b* correction needed
        self.tab = list(Lab)
        self.tab[0] = 0  # 0 because bt1886 maps L to target

        if XYZbp[1] < 0:
            XYZbp = list(XYZbp)
            XYZbp[1] = 0.0

        # Offset acounted for in output
        self.outo = XYZbp[1] * outoffset
        # Balance of offset accounted for in input
        ino = XYZbp[1] - self.outo

        # Input offset black to 1/pow
        bkipow = math.pow(ino, 1.0 / self.gamma)
        # Input offset white to 1/pow
        wtipow = math.pow(1.0 - self.outo, 1.0 / self.gamma)
        # non-linear Y that makes input offset proportion of black point
        self.ingo = bkipow / (wtipow - bkipow)
        # Scale to make input of 1 map to 1.0 - self.outo
        self.outsc = pow(wtipow - bkipow, self.gamma)
        self.apply_trc = apply_trc

    def apply(self, X, Y, Z):
        """Apply BT.1886 black offset and gamma curve to the XYZ out of the input profile.
        Do this in the colorspace defined by the input profile matrix lookup,
        so it will be relative XYZ. We assume that BT.1886 does a Rec709 to gamma
        viewing adjustment, on top of any source profile transfer curve
        (i.e. BT.1886 viewing adjustment is assumed to be the mismatch between
        Rec709 curve and the output offset pure 2.4 gamma curve)

        """

        logging.debug("bt1886 XYZ in %f %f %f" % (X, Y, Z))

        out = self.bwd_matrix * (X, Y, Z)

        logging.debug("bt1886 RGB in %f %f %f" % (out[0], out[1], out[2]))

        for j in range(3):
            vv = out[j]

            if self.apply_trc:
                # Convert linear light to Rec709 transfer curve
                if vv < 0.018:
                    vv = 4.5 * vv
                else:
                    vv = 1.099 * math.pow(vv, 0.45) - 0.099

            # Apply input offset
            vv = vv + self.ingo

            # Apply power and scale
            if vv > 0.0:
                if self.apply_trc:
                    vv = self.outsc * math.pow(vv, self.gamma)
                else:
                    vv *= self.outsc

            # Apply output portion of offset
            vv += self.outo

            out[j] = vv

        out = self.fwd_matrix * out

        logging.debug("bt1886 RGB bt.1886 %f %f %f" % (out[0], out[1], out[2]))

        out = list(XYZ2Lab(*[v * 100 for v in out]))

        logging.debug("bt1886 Lab after Y adj. %f %f %f" % (out[0], out[1], out[2]))

        # Blend ab to required black point offset self.tab[] as L approaches black.
        vv = (out[0] - self.outL) / (100.0 - self.outL)  # 0 at bp, 1 at wp
        vv = 1.0 - vv

        if vv < 0.0:
            vv = 0.0
        elif vv > 1.0:
            vv = 1.0
        vv = math.pow(vv, 40.0)
        out[0] += vv * self.tab[0]
        out[1] += vv * self.tab[1]
        out[2] += vv * self.tab[2]

        logging.debug("bt1886 Lab after wp adj. %f %f %f" % (out[0], out[1], out[2]))

        out = Lab2XYZ(*out)

        logging.debug("bt1886 XYZ out %f %f %f" % (out[0], out[1], out[2]))

        return out


class BT2390:
    """Roll-off for SMPTE 2084 (PQ) according to Report ITU-R BT.2390-2 HDR TV"""

    def __init__(
        self,
        black_cdm2,
        white_cdm2,
        master_black_cdm2=0,
        master_white_cdm2=10000,
        use_alternate_master_white_clip=True,
    ):
        """Master black and white level are used to tweak the roll-off and clip.

        If use_alternate_master_white_clip is True, do not follow BT.2390 for
        the mastering white adjustment (allows to preserve more detail in
        rolled-off highlights)

        """

        self.black_cdm2 = black_cdm2
        self.white_cdm2 = white_cdm2
        self.master_black_cdm2 = master_black_cdm2
        self.master_white_cdm2 = master_white_cdm2

        self.ominv = black_cdm2 / 10000.0  # Lmin
        self.omini = specialpow(self.ominv, 1.0 / -2084)  # Original minLum
        self.omaxv = white_cdm2 / 10000.0  # Lmax
        self.omaxi = specialpow(self.omaxv, 1.0 / -2084)  # Original maxLum

        self.oKS = 1.5 * self.omaxi - 0.5

        # BT.2390-2
        self.mminv = master_black_cdm2 / 10000.0  # LB
        self.mmini = specialpow(self.mminv, 1.0 / -2084)
        self.mmaxv = master_white_cdm2 / 10000.0  # LW
        mmaxi = specialpow(self.mmaxv, 1.0 / -2084)
        if use_alternate_master_white_clip:
            self.maxci = (mmaxi - self.mmini) / (1 - self.mmini)
            self.mmaxi = 1.0
        else:
            self.maxci = 1.0
            self.mmaxi = mmaxi
        self.mini = (self.omini - self.mmini) / (
            self.mmaxi - self.mmini
        )  # Normalized minLum
        self.minv = specialpow(self.mini, -2084)
        self.maxi = (self.omaxi - self.mmini) / (
            self.mmaxi - self.mmini
        )  # Normalized maxLum
        self.maxv = specialpow(self.maxi, -2084)

        self.KS = 1.5 * self.maxi - 0.5

        if self.maxi <= self.maxci < 1:
            E2 = self.P(self.maxci, self.KS, self.maxi)
            diff = self.maxci - E2
            self.s = (self.maxci - self.maxi) / diff

    def P(self, B, KS, maxi, maxci=1.0):
        T = (B - KS) / (1 - KS)
        E2 = (
            (2 * T**3 - 3 * T**2 + 1) * KS
            + (T**3 - 2 * T**2 + T) * (1 - KS)
            + (-2 * T**3 + 3 * T**2) * maxi
        )
        if maxci < 1:
            # (Old) Clipping for better target display peak luminance usage
            # XXX: Only kept for backwards compatibility
            s = min(((B - KS) / (maxci - KS)) ** 4, 1)
            E2 = E2 * (1 - s) + maxi * s
        return E2

    def apply(
        self,
        v,
        KS=None,
        maxi=None,
        maxci=None,
        mini=None,
        mmaxi=None,
        mmini=None,
        bpc=False,
        normalize=True,
    ):
        """Apply roll-off (E' in, E' out)
        maxci if < 1.0 applies alterante clip.

        """
        if KS is None:
            KS = self.KS
        if maxi is None:
            maxi = self.maxi
        if mini is None:
            mini = self.mini
        if mmaxi is None:
            mmaxi = self.mmaxi
        if mmini is None:
            mmini = self.mmini
        if maxci is None:
            maxci = self.maxci
        if normalize and mmini is not None and mmaxi is not None:
            # Normalize PQ values based on mastering display black/white levels
            E1 = min(max((v - mmini) / (mmaxi - mmini), 0), 1.0)
        else:
            E1 = v
        # BT.2390-3 suggests P[E1] if KS <= E1 <=1, but this results in
        # division by zero if KS = 1. The correct way is to check for
        # KS < E1 <=1
        if KS < E1 <= 1:
            E2 = self.P(E1, KS, maxi)
            if maxi <= maxci < 1:
                # (New) Clipping for better target display peak luminance usage
                s = self.s
                diff = E1 - E2
                E2 = min(E1 - diff * s, maxi)
            elif maxci < 1:
                E2 = min(E1, maxci)
        else:
            E2 = E1
        # BT.2390-3 suggests 0 <= E2 <= 1, but this results in a discontinuity
        # if KS < 0 (high LB > Lmin, low Lmax, high LW). To avoid this, check
        # for E2 <= 1 instead
        if mini and E2 <= 1:
            # Apply black level lift
            minLum = mini
            # maxLum = maxi
            b = minLum
            # BT.2390-3 suggests E2 + b * (1 - E2) ** 4, but this clips, if
            # minLum > 0.25, due to a 'dip' in the function. The solution is to
            # adjust the exponent according to minLum. For minLum <= 0.25
            # (< 5.15 cd/m2), this will give the same result as 'pure' BT.2390-3
            if b >= 0:
                # Only for positive b i.e. minLum >= LB
                p = min(1.0 / b, 4)
            else:
                # For negative b i.e. minLum < LB
                p = 4
            E3 = E2 + b * (1 - E2) ** p
            # If maxLum < 1, and the input value reaches maxLum, the resulting
            # output value will be higher than maxLum after applying the black
            # level lift (note that this is *not* a side effect of the above
            # exponent adjustment). Undo this by re-scaling to the nominal output
            # range [minLum, maxLum].
            if maxi < 1:
                # Only re-scale if maxLum < 1. Note that maxLum can be > 1
                # if Lmax > LW despite E2 <= 1
                E3 = convert_range(E3, b, maxi + b * (1 - maxi) ** p, b, maxi)
        else:
            E3 = E2
        if bpc:
            E3 = convert_range(E3, mini, maxi, 0, maxi)
        if normalize and mmini is not None and mmaxi is not None:
            # Invert the normalization of the PQ values
            E3 = E3 * (mmaxi - mmini) + mmini
        return max(E3, 0)


class Matrix3x3(list):
    """Simple 3x3 matrix"""

    def __init__(self, matrix=None):
        super(Matrix3x3, self).__init__()
        if matrix:
            self.update(matrix)
        else:
            self._reset()

    def update(self, matrix):
        if len(matrix) != 3:
            raise ValueError("Invalid number of rows for 3x3 matrix: %i" % len(matrix))
        self._reset()
        while len(self):
            self.pop()
        for row in matrix:
            if len(row) != 3:
                raise ValueError(
                    "Invalid number of columns for 3x3 matrix: %i" % len(row)
                )
            self.append([])
            for column in row:
                self[-1].append(column)

    def _reset(self):
        self._inverted = None
        self._transposed = None
        self._rounded = {}
        self._applied = {}

    def __add__(self, matrix):
        instance = self.__class__()
        instance.update(
            [
                [
                    self[0][0] + matrix[0][0],
                    self[0][1] + matrix[0][1],
                    self[0][2] + matrix[0][2],
                ],
                [
                    self[1][0] + matrix[1][0],
                    self[1][1] + matrix[1][1],
                    self[1][2] + matrix[1][2],
                ],
                [
                    self[2][0] + matrix[2][0],
                    self[2][1] + matrix[2][1],
                    self[2][2] + matrix[2][2],
                ],
            ]
        )
        return instance

    def __iadd__(self, matrix):
        # inplace
        self.update(self.__add__(matrix))
        return self

    def __imul__(self, matrix):
        # inplace
        self.update(self.__mul__(matrix))
        return self

    def __mul__(self, matrix):
        if not isinstance(matrix[0], (list, tuple)):
            return [
                matrix[0] * self[0][0]
                + matrix[1] * self[0][1]
                + matrix[2] * self[0][2],
                matrix[0] * self[1][0]
                + matrix[1] * self[1][1]
                + matrix[2] * self[1][2],
                matrix[0] * self[2][0]
                + matrix[1] * self[2][1]
                + matrix[2] * self[2][2],
            ]
        instance = self.__class__()
        instance.update(
            [
                [
                    self[0][0] * matrix[0][0]
                    + self[0][1] * matrix[1][0]
                    + self[0][2] * matrix[2][0],
                    self[0][0] * matrix[0][1]
                    + self[0][1] * matrix[1][1]
                    + self[0][2] * matrix[2][1],
                    self[0][0] * matrix[0][2]
                    + self[0][1] * matrix[1][2]
                    + self[0][2] * matrix[2][2],
                ],
                [
                    self[1][0] * matrix[0][0]
                    + self[1][1] * matrix[1][0]
                    + self[1][2] * matrix[2][0],
                    self[1][0] * matrix[0][1]
                    + self[1][1] * matrix[1][1]
                    + self[1][2] * matrix[2][1],
                    self[1][0] * matrix[0][2]
                    + self[1][1] * matrix[1][2]
                    + self[1][2] * matrix[2][2],
                ],
                [
                    self[2][0] * matrix[0][0]
                    + self[2][1] * matrix[1][0]
                    + self[2][2] * matrix[2][0],
                    self[2][0] * matrix[0][1]
                    + self[2][1] * matrix[1][1]
                    + self[2][2] * matrix[2][1],
                    self[2][0] * matrix[0][2]
                    + self[2][1] * matrix[1][2]
                    + self[2][2] * matrix[2][2],
                ],
            ]
        )
        return instance

    def adjoint(self):
        return self.cofactors().transposed()

    def applied(self, fn):
        """Apply function to every element, return new matrix"""
        if fn in self._applied:
            return self._applied[fn]
        matrix = self.__class__()
        for row in self:
            matrix.append([])
            for column in row:
                matrix[-1].append(fn(column))
        self._applied[fn] = matrix
        return matrix

    def cofactors(self):
        instance = self.__class__()
        instance.update(
            [
                [
                    (self[1][1] * self[2][2] - self[1][2] * self[2][1]),
                    -1 * (self[1][0] * self[2][2] - self[1][2] * self[2][0]),
                    (self[1][0] * self[2][1] - self[1][1] * self[2][0]),
                ],
                [
                    -1 * (self[0][1] * self[2][2] - self[0][2] * self[2][1]),
                    (self[0][0] * self[2][2] - self[0][2] * self[2][0]),
                    -1 * (self[0][0] * self[2][1] - self[0][1] * self[2][0]),
                ],
                [
                    (self[0][1] * self[1][2] - self[0][2] * self[1][1]),
                    -1 * (self[0][0] * self[1][2] - self[1][0] * self[0][2]),
                    (self[0][0] * self[1][1] - self[0][1] * self[1][0]),
                ],
            ]
        )
        return instance

    def determinant(self):
        return (
            self[0][0] * self[1][1] * self[2][2]
            + self[1][0] * self[2][1] * self[0][2]
            + self[0][1] * self[1][2] * self[2][0]
        ) - (
            self[2][0] * self[1][1] * self[0][2]
            + self[1][0] * self[0][1] * self[2][2]
            + self[2][1] * self[1][2] * self[0][0]
        )

    def invert(self):
        # inplace
        self.update(self.inverted())

    def inverted(self):
        if self._inverted:
            return self._inverted
        determinant = self.determinant()
        matrix = self.adjoint()
        instance = self.__class__()
        instance.update(
            [
                [
                    matrix[0][0] / determinant,
                    matrix[0][1] / determinant,
                    matrix[0][2] / determinant,
                ],
                [
                    matrix[1][0] / determinant,
                    matrix[1][1] / determinant,
                    matrix[1][2] / determinant,
                ],
                [
                    matrix[2][0] / determinant,
                    matrix[2][1] / determinant,
                    matrix[2][2] / determinant,
                ],
            ]
        )
        self._inverted = instance
        return instance

    def rounded(self, digits=3):
        if digits in self._rounded:
            return self._rounded[digits]
        matrix = self.__class__()
        for row in self:
            matrix.append([])
            for column in row:
                matrix[-1].append(round(column, digits))
        self._rounded[digits] = matrix
        return matrix

    def transpose(self):
        self.update(self.transposed())

    def transposed(self):
        if self._transposed:
            return self._transposed
        instance = self.__class__()
        instance.update(
            [
                [self[0][0], self[1][0], self[2][0]],
                [self[0][1], self[1][1], self[2][1]],
                [self[0][2], self[1][2], self[2][2]],
            ]
        )
        self._transposed = instance
        return instance


class NumberTuple(tuple):
    def __repr__(self):
        return "(%s)" % ", ".join(str(value) for value in self)

    def round(self, digits=4):
        return self.__class__(round(value, digits) for value in self)


# Chromatic adaption transform matrices
# Bradford, von Kries (= HPE normalized to D65) from http://brucelindbloom.com/Eqn_ChromAdapt.html
# CAT02 from http://en.wikipedia.org/wiki/CIECAM02#CAT02
# HPE normalized to illuminant E, CAT97s from http://en.wikipedia.org/wiki/LMS_color_space#CAT97s
# CMCCAT2000, Sharp from 'Computational colour science using MATLAB'
# ISBN 0470845627, http://books.google.com/books?isbn=0470845627
# Cross-verification of the matrix numbers has been done using various sources,
# most notably 'Chromatic Adaptation Performance of Different RGB Sensors'
# http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.14.918&rep=rep1&type=pdf
cat_matrices = {
    "Bradford": Matrix3x3(
        [
            [0.89510, 0.26640, -0.16140],
            [-0.75020, 1.71350, 0.03670],
            [0.03890, -0.06850, 1.02960],
        ]
    ),
    "CAT02": Matrix3x3(
        [[0.7328, 0.4296, -0.1624], [-0.7036, 1.6975, 0.0061], [0.0030, 0.0136, 0.9834]]
    ),
    # Brill & Süsstrunk modification also found in ArgyllCMS
    "CAT02BS": Matrix3x3(
        [[0.7328, 0.4296, -0.1624], [-0.7036, 1.6975, 0.0061], [0.0000, 0.0000, 1.0000]]
    ),
    "CAT97s": Matrix3x3(
        [
            [0.8562, 0.3372, -0.1934],
            [-0.8360, 1.8327, 0.0033],
            [0.0357, -0.0469, 1.0112],
        ]
    ),
    "CMCCAT2000": Matrix3x3(
        [[0.7982, 0.3389, -0.1371], [-0.5918, 1.5512, 0.0406], [0.0008, 0.0239, 0.9753]]
    ),
    # Hunt-Pointer-Estevez, equal-energy illuminant
    "HPE E": Matrix3x3(
        [
            [0.38971, 0.68898, -0.07868],
            [-0.22981, 1.18340, 0.04641],
            [0.00000, 0.00000, 1.00000],
        ]
    ),
    # Süsstrunk et al.15 optimized spectrally sharpened matrix
    "Sharp": Matrix3x3(
        [
            [1.2694, -0.0988, -0.1706],
            [-0.8364, 1.8006, 0.0357],
            [0.0297, -0.0315, 1.0018],
        ]
    ),
    # 'Von Kries' as found on Bruce Lindbloom's site:
    # Hunt-Pointer-Estevez normalized to D65
    # (maybe I should call it that instead of 'Von Kries'
    # to avoid ambiguity?)
    "HPE D65": Matrix3x3(
        [
            [0.40024, 0.70760, -0.08081],
            [-0.22630, 1.16532, 0.04570],
            [0.00000, 0.00000, 0.91822],
        ]
    ),
    "XYZ scaling": Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
    "IPT": Matrix3x3(
        [[0.4002, 0.7075, -0.0807], [-0.2280, 1.1500, 0.0612], [0.0000, 0.0000, 0.9184]]
    ),
    # Inverse CIE 2012 2deg LMS to XYZ matrix from Argyll/icc/icc.c
    "CIE2012_2": Matrix3x3(
        [
            [0.2052445519046028, 0.8334486497310412, -0.0386932016356441],
            [-0.4972221301804286, 1.4034846060306130, 0.0937375241498157],
            [0.0000000000000000, 0.0000000000000000, 1.0000000000000000],
        ]
    ),
    # Bianco and Schettini (2010)
    "BS": Matrix3x3(
        [
            [0.8752, 0.2787, -0.1539],
            [-0.8904, 1.8709, 0.0195],
            [-0.0061, 0.0162, 0.9899],
        ]
    ),
    # Bianco and Schettini (2010) with positivity constraint
    "BS-PC": Matrix3x3(
        [
            [0.6489, 0.3915, -0.0404],
            [-0.3775, 1.3055, 0.0720],
            [-0.0271, 0.0888, 0.9383],
        ]
    ),
}

LMS2IPT_matrix = Matrix3x3(
    [[0.4000, 0.4000, 0.2000], [4.4550, -4.8510, 0.3960], [0.8056, 0.3572, -1.1628]]
)
IPT2LMS_matrix = LMS2IPT_matrix.inverted()

LinearRGB2LMS_matrix = Matrix3x3(
    [
        [1688 / 4096.0, 2146 / 4096.0, 262 / 4096.0],
        [683 / 4096.0, 2951 / 4096.0, 462 / 4096.0],
        [99 / 4096.0, 309 / 4096.0, 3688 / 4096.0],
    ]
)
LMS2LinearRGB_matrix = LinearRGB2LMS_matrix.inverted()
L_M_S_2ICtCp_matrix = Matrix3x3(
    [
        [0.5, 0.5, 0],
        [6610 / 4096.0, -13613 / 4096.0, 7003 / 4096.0],
        [17933 / 4096.0, -17390 / 4096.0, -543 / 4096.0],
    ]
)
ICtCp2L_M_S__matrix = L_M_S_2ICtCp_matrix.inverted()

# Tweaked LMS to IPT matrix to account for CIE 2012 2deg XYZ to LMS matrix
# From Argyll/icc/icc.c
LMS2Lpt_matrix = Matrix3x3(
    [
        [0.6585034777870502, 0.1424555300344579, 0.1990409921784920],
        [5.6413505933276049, -6.1697985811414187, 0.5284479878138138],
        [1.6370552576322106, 0.0192823194340315, -1.6563375770662419],
    ]
)
Lpt2LMS_matrix = LMS2Lpt_matrix.inverted()

standard_illuminants = {
    # 1st level is the standard name => illuminant definitions
    # 2nd level is the illuminant name => CIE XYZ coordinates
    # (Y should always assumed to be 1.0 and is not explicitly defined)
    None: {"E": {"X": 1.00000, "Z": 1.00000}},
    "ASTM E308-01": {
        "A": {"X": 1.09850, "Z": 0.35585},
        "C": {"X": 0.98074, "Z": 1.18232},
        "D50": {"X": 0.96422, "Z": 0.82521},
        "D55": {"X": 0.95682, "Z": 0.92149},
        "D65": {"X": 0.95047, "Z": 1.08883},
        "D75": {"X": 0.94972, "Z": 1.22638},
        "F2": {"X": 0.99186, "Z": 0.67393},
        "F7": {"X": 0.95041, "Z": 1.08747},
        "F11": {"X": 1.00962, "Z": 0.64350},
    },
    "ICC": {"D50": {"X": 0.9642, "Z": 0.8249}, "D65": {"X": 0.9505, "Z": 1.0890}},
    "ISO 11664-2:2007": {
        "D65": {"X": xyY2XYZ(0.3127, 0.329)[0], "Z": xyY2XYZ(0.3127, 0.329)[2]}
    },
    "Wyszecki & Stiles": {
        "A": {"X": 1.09828, "Z": 0.35547},
        "B": {"X": 0.99072, "Z": 0.85223},
        "C": {"X": 0.98041, "Z": 1.18103},
        "D55": {"X": 0.95642, "Z": 0.92085},
        "D65": {"X": 0.95017, "Z": 1.08813},
        "D75": {"X": 0.94939, "Z": 1.22558},
    },
}

# CIE 1931 2-deg chromaticity coordinates
# http://www.cvrl.org/offercsvccs.php
cie1931_2_xy = [
    (0.175560, 0.005294),
    (0.175161, 0.005256),
    (0.174821, 0.005221),
    (0.174510, 0.005182),
    (0.174112, 0.004964),
    (0.174008, 0.004981),
    (0.173801, 0.004915),
    (0.173560, 0.004923),
    (0.173337, 0.004797),
    (0.173021, 0.004775),
    (0.172577, 0.004799),
    (0.172087, 0.004833),
    (0.171407, 0.005102),
    (0.170301, 0.005789),
    (0.168878, 0.006900),
    (0.166895, 0.008556),
    (0.164412, 0.010858),
    (0.161105, 0.013793),
    (0.156641, 0.017705),
    (0.150985, 0.022740),
    (0.143960, 0.029703),
    (0.135503, 0.039879),
    (0.124118, 0.057803),
    (0.109594, 0.086843),
    (0.091294, 0.132702),
    (0.068706, 0.200723),
    (0.045391, 0.294976),
    (0.023460, 0.412703),
    (0.008168, 0.538423),
    (0.003859, 0.654823),
    (0.013870, 0.750186),
    (0.038852, 0.812016),
    (0.074302, 0.833803),
    (0.114161, 0.826207),
    (0.154722, 0.805864),
    (0.192876, 0.781629),
    (0.229620, 0.754329),
    (0.265775, 0.724324),
    (0.301604, 0.692308),
    (0.337363, 0.658848),
    (0.373102, 0.624451),
    (0.408736, 0.589607),
    (0.444062, 0.554714),
    (0.478775, 0.520202),
    (0.512486, 0.486591),
    (0.544787, 0.454434),
    (0.575151, 0.424232),
    (0.602933, 0.396497),
    (0.627037, 0.372491),
    (0.648233, 0.351395),
    (0.665764, 0.334011),
    (0.680079, 0.319747),
    (0.691504, 0.308342),
    (0.700606, 0.299301),
    (0.707918, 0.292027),
    (0.714032, 0.285929),
    (0.719033, 0.280935),
    (0.723032, 0.276948),
    (0.725992, 0.274008),
    (0.728272, 0.271728),
    (0.729969, 0.270031),
    (0.731089, 0.268911),
    (0.731993, 0.268007),
    (0.732719, 0.267281),
    (0.733417, 0.266583),
    (0.734047, 0.265953),
    (0.734390, 0.265610),
    (0.734592, 0.265408),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734548, 0.265452),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
    (0.734690, 0.265310),
]

optimalcolors_Lab = [
    (52.40, 95.40, 10.58),
    (52.33, 91.23, 38.56),
    (52.31, 89.09, 65.80),
    (52.30, 88.24, 89.93),
    (59.11, 84.13, 101.46),
    (66.02, 75.66, 113.09),
    (72.36, 64.33, 123.65),
    (78.27, 50.88, 132.94),
    (83.64, 36.33, 140.63),
    (88.22, 22.05, 145.02),
    (92.09, 8.49, 143.95),
    (90.38, -4.04, 141.05),
    (87.54, -23.02, 136.16),
    (85.18, -37.06, 132.16),
    (82.10, -52.65, 126.97),
    (85.53, -65.59, 122.51),
    (82.01, -81.46, 116.55),
    (77.35, -97.06, 108.72),
    (74.76, -122.57, 90.91),
    (68.33, -134.27, 80.11),
    (63.07, -152.99, 56.41),
    (54.57, -159.74, 42.75),
    (44.43, -162.58, 27.45),
    (46.92, -162.26, 13.87),
    (48.53, -144.04, -4.73),
    (49.50, -115.82, -25.38),
    (59.18, -85.50, -47.00),
    (59.33, -68.64, -58.79),
    (59.41, -52.73, -69.57),
    (50.80, -25.33, -84.08),
    (42.05, 8.67, -98.57),
    (33.79, 43.74, -111.63),
    (26.63, 74.31, -121.90),
    (20.61, 98.44, -128.77),
    (14.87, 117.34, -131.97),
    (9.74, 127.16, -129.59),
    (5.20, 125.79, -120.43),
    (7.59, 122.01, -116.33),
    (10.21, 117.89, -111.81),
    (26.35, 115.11, -100.95),
    (40.68, 115.59, -87.47),
    (39.37, 115.48, -78.51),
    (46.49, 114.84, -66.24),
    (53.49, 111.63, -54.17),
    (52.93, 107.54, -38.16),
    (52.58, 101.53, -16.45),
    (52.40, 95.40, 10.58),
]


def debug_caches():
    for cache in (
        "XYZ2RGB.interp",
        "wp_adaption_matrix.cache",
        "get_rgb_space.cache",
        "get_standard_illuminant.cache",
        "get_whitepoint.cache",
    ):
        cn, ck = cache.split(".")
        c = getattr(globals()[cn], ck)
        count = 0
        seen = {}
        for k in c:
            v = c[k]
            for kk in c:
                vv = c[kk]
                # Check for equality, not identity
                if k != kk and v == vv and kk not in seen:
                    count += 1
                    seen[kk] = True
        print(cache, len(c), "entries", max(count - 1, 0), "duplicates")
        if count > 1:
            for k in c:
                v = c[k]
                print(k, v)


if "--debug-caches" in sys.argv[1:]:
    import atexit

    atexit.register(debug_caches)


def test():
    for i in range(4):
        if i == 0:
            wp = "native"
        elif i == 1:
            wp = "D50"
            XYZ = get_standard_illuminant(wp)
        elif i == 2:
            wp = "D65"
            XYZ = get_standard_illuminant(wp)
        elif i == 3:
            XYZ = get_standard_illuminant("D65", ("ASTM E308-01",))
            wp = " ".join([str(v) for v in XYZ])
        print(
            (
                "RGB and corresponding XYZ (nominal range 0.0 - 1.0) with whitepoint %s"
                % wp
            )
        )
        for name in rgb_spaces:
            spc = rgb_spaces[name]
            if i == 0:
                XYZ = CIEDCCT2XYZ(spc[1])
            spc = spc[0], XYZ, spc[2], spc[3], spc[4]
            print(
                "%s 1.0, 1.0, 1.0 = XYZ" % name,
                [str(round(v, 4)) for v in RGB2XYZ(1.0, 1.0, 1.0, spc)],
            )
            print(
                "%s 1.0, 0.0, 0.0 = XYZ" % name,
                [str(round(v, 4)) for v in RGB2XYZ(1.0, 0.0, 0.0, spc)],
            )
            print(
                "%s 0.0, 1.0, 0.0 = XYZ" % name,
                [str(round(v, 4)) for v in RGB2XYZ(0.0, 1.0, 0.0, spc)],
            )
            print(
                "%s 0.0, 0.0, 1.0 = XYZ" % name,
                [str(round(v, 4)) for v in RGB2XYZ(0.0, 0.0, 1.0, spc)],
            )
        print("")


if __name__ == "__main__":
    test()
