"""Diverse color mathematical functions.

Note:

In most cases, unless otherwise stated RGB is R'G'B' (gamma-compressed)
"""

from __future__ import annotations

import colorsys
import functools
import logging
import math
import sys
import warnings
from typing import TYPE_CHECKING, Any, Callable, overload

import numpy

from DisplayCAL.debughelpers import DEBUG

if TYPE_CHECKING:
    from typing import Self


logger = logging.getLogger(__name__)
if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


def cache(f: Callable) -> Callable[..., Any]:
    """Decorator to convert list arguments to tuples and cache.

    Args:
        f (Callable): The function to wrap.
    """

    def wrapper(*args, **kwargs) -> Any:  # noqa: ANN401
        cache_hash = (
            ((tuple(arg) if isinstance(arg, (list, tuple)) else arg for arg in args)),
            (
                (key, tuple(kwargs[key]))
                if isinstance(kwargs[key], (list, tuple))
                else kwargs[key]
                for key in kwargs
            ),
        )
        if not hasattr(f, "cache"):
            f.cache = {}
        if cache_hash in f.cache:
            return f.cache[cache_hash]

        result = f(*args, **kwargs)
        f.cache[cache_hash] = result
        return result

    return wrapper


def get_transfer_function_phi(alpha: float, gamma: float) -> float:
    """Get transfer function phi.

    Args:
        alpha (float): Alpha value.
        gamma (float): Gamma value.

    Returns:
        float: Transfer function phi value.
    """
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


def special_pow(a: float, b: float, slope_limit: float = 0) -> float:
    """Wrapper for power, Rec. 601/709, SMPTE 240M, sRGB and L* functions.

    Positive b = power, -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
    -601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
    identical)

    Args:
        a (float): Input value.
        b (float): Exponent, transfer function or gamma.
        slope_limit (float, optional): Slope limit for power curve, defaults to
            0.

    Returns:
        float: Output value.
    """
    if b >= 0.0:
        # Power curve
        if a < 0.0:
            if slope_limit:
                return min(-math.pow(-a, b), a / slope_limit)
            return -math.pow(-a, b)
        if slope_limit:
            return max(math.pow(a, b), a / slope_limit)
        return math.pow(a, b)

    sign_scale = -1.0 if a < 0.0 else 1.0
    a = abs(a)

    v = {
        1.0 / -601:
        # XYZ -> RGB, Rec. 601/709 TRC
        (a * REC709_P)
        if (a < REC709_K0 / REC709_P)
        else (1.099 * math.pow(a, 0.45) - 0.099),
        1.0 / -709:
        # XYZ -> RGB, Rec. 601/709 TRC
        (a * REC709_P)
        if (a < REC709_K0 / REC709_P)
        else (1.099 * math.pow(a, 0.45) - 0.099),
        1.0 / -240:
        # XYZ -> RGB, SMPTE 240M TRC
        (a * SMPTE240M_P)
        if (a < SMPTE240M_K0 / SMPTE240M_P)
        else (1.1115 * math.pow(a, 0.45) - 0.1115),
        1.0 / -3.0:
        # XYZ -> RGB, L* TRC
        0.01 * a * LSTAR_K if a <= LSTAR_E else 1.16 * math.pow(a, 1.0 / 3.0) - 0.16,
        1.0 / -2.4:
        # XYZ -> RGB, sRGB TRC
        (a * SRGB_P)
        if (a <= SRGB_K0 / SRGB_P)
        else (1.055 * math.pow(a, 1.0 / 2.4) - 0.055),
        1.0 / -2084:
        # XYZ -> RGB, SMPTE 2084 (PQ)
        ((2413.0 * (a**SMPTE2084_M1) + 107) / (2392.0 * (a**SMPTE2084_M1) + 128))
        ** SMPTE2084_M2,
        -2.4:
        # RGB -> XYZ, sRGB TRC
        a / SRGB_P if a <= SRGB_K0 else math.pow((a + 0.055) / 1.055, 2.4),
        -3.0:
        # RGB -> XYZ, L* TRC
        # E * K * 0.01
        100.0 * a / LSTAR_K if a <= 0.08 else math.pow((a + 0.16) / 1.16, 3.0),
        -240:
        # RGB -> XYZ, SMPTE 240M TRC
        (
            a / SMPTE240M_P
            if a < SMPTE240M_K0
            else math.pow((0.1115 + a) / 1.1115, 1.0 / 0.45)
        ),
        -601:
        # RGB -> XYZ, Rec. 601/709 TRC
        a / REC709_P if a < REC709_K0 else math.pow((a + 0.099) / 1.099, 1.0 / 0.45),
        -709:
        # RGB -> XYZ, Rec. 601/709 TRC
        a / REC709_P if a < REC709_K0 else math.pow((a + 0.099) / 1.099, 1.0 / 0.45),
        -2084:
        # RGB -> XYZ, SMPTE 2084 (PQ)
        # See https://www.smpte.org/sites/default/files/2014-05-06-EOTF-Miller-1-2-handout.pdf
        (
            max(a ** (1.0 / SMPTE2084_M2) - SMPTE2084_C1, 0)
            / (SMPTE2084_C2 - SMPTE2084_C3 * a ** (1.0 / SMPTE2084_M2))
        )
        ** (1.0 / SMPTE2084_M1),
    }.get(b)
    if v is None:
        raise ValueError(f"Invalid gamma {b!r}")

    return v * sign_scale


def DICOM(j: float, inverse: bool = False) -> float:  # noqa: N802
    """DICOM TRC.

    Args:
        j (float): Input value.
        inverse (bool): If True, apply inverse DICOM TRC.

    Returns:
        float: Output value.
    """
    if inverse:
        log10y = math.log10(j)
        a = 71.498068
        b = 94.593053
        c = 41.912053
        d = 9.8247004
        e = 0.28175407
        f = -1.1878455
        g = -0.18014349
        h = 0.14710899
        i = -0.017046845
        return (
            a
            + b * log10y
            + c * math.pow(log10y, 2)
            + d * math.pow(log10y, 3)
            + e * math.pow(log10y, 4)
            + f * math.pow(log10y, 5)
            + g * math.pow(log10y, 6)
            + h * math.pow(log10y, 7)
            + i * math.pow(log10y, 8)
        )
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
    """Hybrid Log Gamma (HLG) as defined in Rec BT.2100 and BT.2390-4.

    Args:
        black_cdm2 (float): Black level in cd/m², defaults to 0.0.
        white_cdm2 (float): White level in cd/m², defaults to 1000.0.
        system_gamma (float): System gamma for nominal peak luminance and
            ambient, defaults to 1.2.
        ambient_cdm2 (float): Ambient luminance in cd/m², defaults to 5.
        rgb_space (str): RGB color space, defaults to "Rec. 2020".
    """

    def __init__(
        self,
        black_cdm2: float = 0.0,
        white_cdm2: float = 1000.0,
        system_gamma: float = 1.2,
        ambient_cdm2: float = 5,
        rgb_space: str = "Rec. 2020",
    ) -> None:
        self.black_cdm2 = black_cdm2
        self.white_cdm2 = white_cdm2
        self.rgb_space = get_rgb_space(rgb_space)
        self.system_gamma = system_gamma
        self.ambient_cdm2 = ambient_cdm2

    @property
    def gamma(self) -> float:
        """System gamma for nominal peak luminance and ambient.

        Returns:
            float: Adjusted system gamma based on peak luminance and ambient
                luminance.
        """
        # Adjust system gamma for peak luminance != 1000 cd/m2 (extended model
        # described in BT.2390-4)
        k = 1.111
        gamma = self.system_gamma * k ** math.log(self.white_cdm2 / 1000.0, 2)
        if self.ambient_cdm2 > 0:
            # Adjust system gamma for ambient surround != 5 cd/m2 (BT.2390-4)
            u = 0.98
            gamma *= u ** math.log(self.ambient_cdm2 / 5.0, 2)
        return gamma

    def oetf(self, v: float, inverse: bool = False) -> float:
        """Hybrid Log Gamma (HLG) OETF.

        Relative scene linear light to non-linear HLG signal, or inverse

        Input domain 0..1
        Output range 0..1

        Args:
            v (float): Relative scene linear light or non-linear HLG signal.
            inverse (bool): If True, apply inverse OETF.

        Returns:
            float: Non-linear HLG signal if inverse is False, or relative scene
                linear light if inverse is True.
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
            v = math.sqrt(3 * v) if 0 <= v <= 1 / 12.0 else a * math.log(12 * v - b) + c
        return v

    @overload
    def eotf(
        self,
        RGB: float,  # noqa: N803
        inverse: bool = False,
        apply_black_offset: bool = True,
    ) -> float: ...

    @overload
    def eotf(
        self,
        RGB: tuple[float, float, float],  # noqa: N803
        inverse: bool = False,
        apply_black_offset: bool = True,
    ) -> tuple[float, float, float]: ...

    def eotf(
        self,
        RGB: float | tuple[float, float, float],  # noqa: N803
        inverse: bool = False,
        apply_black_offset: bool = True,
    ) -> float | tuple[float, float, float]:
        """Hybrid Log Gamma (HLG) EOTF.

        Non-linear HLG signal to display light, or inverse

        Input domain 0..1
        Output range 0..1

        Args:
            RGB (float | tuple[float, float, float]): R, G, B components of the
                non-linear HLG signal or display light.
            inverse (bool): If True, apply inverse EOTF.
            apply_black_offset (bool): Whether to apply black offset, defaults
                to True.

        Returns:
            float | tuple[float, float, float]: G component of the display
                light if RGB is a float, or R, G, B components of the display
                light if RGB is a tuple.
        """
        if isinstance(RGB, (float, int)):
            r, g, b = (RGB,) * 3
        else:
            r, g, b = RGB
        if inverse:
            # Display light -> relative scene linear light -> HLG signal
            r, g, b = (
                self.oetf(v) for v in self.ootf((r, g, b), True, apply_black_offset)
            )
        else:
            # HLG signal -> relative scene linear light -> display light
            r, g, b = self.ootf(
                [self.oetf(v, True) for v in (r, g, b)], False, apply_black_offset
            )
        return g if isinstance(RGB, (float, int)) else (r, g, b)

    @overload
    def ootf(
        self,
        RGB: float,  # noqa: N803
        inverse: bool = False,
        apply_black_offset: bool = True,
    ) -> float: ...

    @overload
    def ootf(
        self,
        RGB: tuple[float, float, float],  # noqa: N803
        inverse: bool = False,
        apply_black_offset: bool = True,
    ) -> tuple[float, float, float]: ...

    def ootf(
        self,
        RGB: float | tuple[float, float, float],  # noqa: N803
        inverse: bool = False,
        apply_black_offset: bool = True,
    ) -> float | tuple[float, float, float]:
        """Hybrid Log Gamma (HLG) OOTF.

        Relative scene linear light to display light, or inverse

        Input domain 0..1
        Output range 0..1

        Args:
            RGB (float | tuple[float, float, float]): R, G, B components of the
                relative scene linear light or non-linear HLG signal.
            inverse (bool): If True, apply inverse OOTF.
            apply_black_offset (bool): Whether to apply black offset, defaults
                to True.

        Returns:
            float | tuple[float, float, float]: G component of the display
                light if RGB is a float, or R, G, B components of the display
                light if RGB is a tuple.
        """
        r, g, b = (RGB,) * 3 if isinstance(RGB, (float, int)) else RGB
        black_cdm2 = float(self.black_cdm2) if apply_black_offset else 0
        alpha = (self.white_cdm2 - black_cdm2) / self.white_cdm2
        beta = black_cdm2 / self.white_cdm2
        y = 0.2627 * r + 0.6780 * g + 0.0593 * b
        if inverse:
            if beta < y:
                r, g, b = (
                    ((y - beta) / alpha) ** ((1 - self.gamma) / self.gamma)
                    * ((v - beta) / alpha)
                    for v in (r, g, b)
                )
            else:
                r, g, b = 0, 0, 0
        else:
            if y:
                y **= self.gamma - 1
            r, g, b = (alpha * y * e + beta for e in (r, g, b))
        return g if isinstance(RGB, (float, int)) else (r, g, b)

    def RGB2XYZ(  # noqa: N802
        self,
        R: float,  # noqa: N803
        G: float,  # noqa: N803
        B: float,  # noqa: N803
        apply_black_offset: bool = True,
    ) -> tuple[float, float, float]:
        """Non-linear HLG signal to display XYZ.

        Args:
            R (float): R component of the non-linear HLG signal.
            G (float): G component of the non-linear HLG signal.
            B (float): B component of the non-linear HLG signal.
            apply_black_offset (bool): Whether to apply black offset, defaults
                to True.

        Returns:
            tuple[float, float, float]: X, Y, Z components of the display XYZ.
        """
        x, y, z = self.rgb_space[-1] * [self.oetf(v, True) for v in (R, G, B)]
        x, y, z = (max(v, 0) for v in (x, y, z))
        yy = self.ootf(y, apply_black_offset=False)
        if y:
            x, y, z = (v / y * yy for v in (x, y, z))
        else:
            x, y, z = (v * yy for v in self.rgb_space[1])
        if apply_black_offset:
            beta = self.ootf(0)
            bp_out = [v * beta for v in self.rgb_space[1]]
            x, y, z = apply_bpc(x, y, z, (0, 0, 0), bp_out, self.rgb_space[1])
        return x, y, z

    def XYZ2RGB(  # noqa: N802
        self,
        X: float,  # noqa: N803
        Y: float,  # noqa: N803
        Z: float,  # noqa: N803
        apply_black_offset: bool = True,
    ) -> tuple[float, float, float]:
        """Display XYZ to non-linear HLG signal.

        Args:
            X (float): X component of the XYZ color value.
            Y (float): Y component of the XYZ color value.
            Z (float): Z component of the XYZ color value.
            apply_black_offset (bool): Whether to apply black offset, defaults
                to True.

        Returns:
            tuple[float, float, float]: R, G, B components of the non-linear
                HLG signal.
        """
        if apply_black_offset:
            beta = self.ootf(0)
            bp_in = [v * beta for v in self.rgb_space[1]]
            X, Y, Z = apply_bpc(X, Y, Z, bp_in, (0, 0, 0), self.rgb_space[1])  # noqa: N806
        yy = self.ootf(Y, True, apply_black_offset=False)
        if Y:
            X, Y, Z = (v / Y * yy for v in (X, Y, Z))  # noqa: N806
        r, g, b = self.rgb_space[-1].inverted() * (X, Y, Z)
        r, g, b = (max(v, 0) for v in (r, g, b))
        r, g, b = [self.oetf(v) for v in (r, g, b)]
        return r, g, b


rgb_spaces = {
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
    # "DCDM X'Y'Z'": (
    #     2.6,
    #     "E",
    #     (1.0000, 0.0000, 0.000000),
    #     (0.0000, 1.0000, 1.000000),
    #     (0.0000, 0.0000, 0.000000)
    # ),
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
"""
http://brucelindbloom.com/WorkingSpaceInfo.html
ACES: https://github.com/ampas/aces-dev/blob/master/docs/ACES_1.0.1.pdf?raw=true
Adobe RGB: http://www.adobe.com/digitalimag/pdfs/AdobeRGB1998.pdf
DCI P3: http://www.hp.com/united-states/campaigns/workstations/pdfs/lp2480zx-dci--p3-emulation.pdf
        http://dcimovies.com/specification/DCI_DCSS_v12_with_errata_2012-1010.pdf
Rec. 2020: http://en.wikipedia.org/wiki/Rec._2020

name              gamma             white                     primaries
                                    point                     Rx      Ry      RY          Gx      Gy      GY          Bx      By      BY
"""  # noqa: E501


@cache
def get_cat_matrix(
    cat: str | bytes | list | tuple | Matrix3x3 = "Bradford",
) -> Matrix3x3:
    """Get chromatic adaption matrix.

    Args:
        cat (bytes | str | list | tuple | Matrix3x3): Chromatic adaption matrix
            name or instance. Defaults to "Bradford".

    Returns:
        Matrix3x3: Chromatic adaption matrix.
    """
    if isinstance(cat, str):
        cat = CAT_MATRICES[cat]
    elif isinstance(cat, bytes):
        cat = CAT_MATRICES[cat.decode()]
    if not isinstance(cat, Matrix3x3):
        cat = Matrix3x3(cat)
    return cat


def cbrt(x: float) -> float:
    """Cube root.

    Args:
        x (float): Input value.

    Returns:
        float: Cube root of x.
    """
    return math.pow(x, 1.0 / 3.0) if x >= 0 else -math.pow(-x, 1.0 / 3.0)


def var(a: list[float]) -> float:
    """Variance.

    Args:
        a (list[float]): List of numbers.

    Returns:
        float: Variance of the numbers in the list.
    """
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


def XYZ2LMS(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    cat: str = "Bradford",
) -> tuple[float, float, float]:
    """Convert from XYZ to cone response domain.

    Args:
        X (float):  X component of the XYZ color value.
        Y (float):  Y component of the XYZ color value.
        Z (float):  Z component of the XYZ color value.
        cat (str):  Chromatic adaptation transform, defaults to 'Bradford'.

    Returns:
        tuple[float, float, float]: L, M, S components of the LMS color value.
    """
    cat = get_cat_matrix(cat)
    p, y, b = cat * [X, Y, Z]
    return p, y, b


def LMS_wp_adaption_matrix(  # noqa: N802
    whitepoint_source: None | float | str | list | tuple = None,
    whitepoint_destination: None | float | str | list | tuple = None,
    cat: str = "Bradford",
) -> Matrix3x3:
    """Prepare a matrix to match the whitepoints in cone response domain.

    Args:
        whitepoint_source (None | float | str | list | tuple): Source white
            point, defaults to None.
        whitepoint_destination (None | float | str | list | tuple): Destination
            white point, defaults to None.
        cat (str): Chromatic adaptation transform, defaults to 'Bradford'.

    Returns:
        Matrix3x3: Matrix to adapt source whitepoint to destination in LMS.
    """
    # chromatic adaption
    # based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
    # cat = adaption matrix or predefined choice ('CAT02', 'Bradford',
    # 'Von Kries', 'XYZ Scaling', see CAT_MATRICES), defaults to 'Bradford'
    cat = get_cat_matrix(cat)
    xyz_ws = get_whitepoint(whitepoint_source)
    xyz_wd = get_whitepoint(whitepoint_destination)
    if xyz_ws[1] <= 1.0 < xyz_wd[1]:
        # make sure the scaling is identical
        xyz_wd = [v / xyz_wd[1] * xyz_ws[1] for v in xyz_wd]
    if xyz_wd[1] <= 1.0 < xyz_ws[1]:
        # make sure the scaling is identical
        xyz_ws = [v / xyz_ws[1] * xyz_wd[1] for v in xyz_ws]
    ls, ms, ss = XYZ2LMS(xyz_ws[0], xyz_ws[1], xyz_ws[2], cat)
    ld, md, dd = XYZ2LMS(xyz_wd[0], xyz_wd[1], xyz_wd[2], cat)
    return Matrix3x3([[ld / ls, 0, 0], [0, md / ms, 0], [0, 0, dd / ss]])


@cache
def wp_adaption_matrix(
    whitepoint_source: None | float | str | list | tuple = None,
    whitepoint_destination: None | float | str | list | tuple = None,
    cat: str = "Bradford",
) -> Matrix3x3:
    """Return matrix to adapt source whitepoint to destination in XYZ.

    Args:
        whitepoint_source (None | float | str | list | tuple): Source white
            point, defaults to None.
        whitepoint_destination (None | float | str | list | tuple): Destination
            white point, defaults to None.
        cat (str): Chromatic adaptation transform, defaults to 'Bradford'.

    Returns:
        Matrix3x3: Matrix to adapt source whitepoint to destination.
    """
    # chromatic adaption
    # based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
    # cat = adaption matrix or predefined choice ('CAT02', 'Bradford',
    # 'Von Kries', 'XYZ Scaling', see CAT_MATRICES), defaults to 'Bradford'
    cat = get_cat_matrix(cat)
    return (
        cat.inverted()
        * LMS_wp_adaption_matrix(whitepoint_source, whitepoint_destination, cat)
        * cat
    )


def adapt(
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint_source: None | float | str | list | tuple = None,
    whitepoint_destination: None | float | str | list | tuple = None,
    cat: str = "Bradford",
) -> tuple[float, float, float]:
    """Transform XYZ under source illuminant to XYZ under destination illuminant.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint_source (None | float | str | list | tuple): Source white
            point, defaults to None.
        whitepoint_destination (None | float | str | list | tuple): Destination
            white point, defaults to None.
        cat (str): Chromatic adaptation transform, defaults to 'Bradford'.

    Returns:
        tuple[float, float, float]: Adapted X, Y, Z values.
    """
    # chromatic adaption
    # based on formula http://brucelindbloom.com/Eqn_ChromAdapt.html
    # cat = adaption matrix or predefined choice ('CAT02', 'Bradford',
    # 'Von Kries', 'XYZ Scaling', see CAT_MATRICES), defaults to 'Bradford'
    return wp_adaption_matrix(whitepoint_source, whitepoint_destination, cat) * (
        X,
        Y,
        Z,
    )


def apply_bpc(
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    bp_in: None | tuple = None,
    bp_out: None | tuple = None,
    wp_out: None | float | str | list | tuple = "D50",
    weight: bool = False,
    pin_chromaticity: bool = False,
) -> tuple[float, float, float]:
    """Apply black point compensation.

    Args:
        X (float): X value
        Y (float): Y value
        Z (float): Z value
        bp_in (tuple): Input black point
        bp_out (tuple): Output black point
        wp_out (str or tuple): Output white point
        weight (bool): Whether to apply weight
        pin_chromaticity (bool): Whether to pin chromaticity

    Returns:
        tuple[float, float, float]: Adjusted X, Y, Z values.
    """
    if not bp_in:
        bp_in = (0, 0, 0)
    if not bp_out:
        bp_out = (0, 0, 0)
    wp_out = get_whitepoint(wp_out)
    if weight:
        l = XYZ2Lab(*[v * 100 for v in (X, Y, Z)])[0]
        bp_in_lab = XYZ2Lab(*[v * 100 for v in bp_in])
        bp_out_lab = XYZ2Lab(*[v * 100 for v in bp_out])
        vv = (l - bp_in_lab[0]) / (100.0 - bp_in_lab[0])  # 0 at bp, 1 at wp
        vv = 1.0 - vv
        if vv < 0.0:
            vv = 0.0
        elif vv > 1.0:
            vv = 1.0
        vv = math.pow(vv, min(40.0, 40.0 / (max(bp_in_lab[0], bp_out_lab[0]) or 1.0)))
        bp_in = Lab2XYZ(*[v * vv for v in bp_in_lab])
        bp_out = Lab2XYZ(*[v * vv for v in bp_out_lab])
    if pin_chromaticity:
        XYZ = [Y]  # noqa: N806
        x, y = XYZ2xyY(X, Y, Z, wp_out)[:2]
        bp_in = bp_in[1:2]
        bp_out = bp_out[1:2]
        wp_out = wp_out[1:2]
    else:
        XYZ = [X, Y, Z]  # noqa: N806
    for i, v in enumerate(XYZ):
        XYZ[i] = ((wp_out[i] - bp_out[i]) * v - wp_out[i] * (bp_in[i] - bp_out[i])) / (  # noqa: N806
            wp_out[i] - bp_in[i]
        )
    if pin_chromaticity:
        XYZ = xyY2XYZ(x, y, XYZ[0])  # noqa: N806
    return XYZ


def avg(*args: list[float]) -> float:
    """Average of a list of numbers.

    Args:
        *args (list[float]): A list of numbers.

    Returns:
        float: Average of the numbers.
    """
    return float(sum(args)) / len(args)


def blend_ab(
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    bp: tuple,
    wp: tuple,
    power: float = 40.0,
    signscale: float = 1,
) -> tuple[float, float, float]:
    """Blend to destination black as L approaches black.

    Args:
        X (float): X value
        Y (float): Y value
        Z (float): Z value
        bp (tuple): Black point
        wp (tuple): White point
        power (float): Power for blending
        signscale (int): Sign scale for blending

    Returns:
        tuple[float, float, float]: Blended X, Y, Z values
    """
    if Y < 0:
        return 0, 0, 0
    l, a, b = XYZ2Lab(X, Y, Z, whitepoint=wp)
    bpl, bpa, bpb = XYZ2Lab(*bp, whitepoint=wp)
    if bpl == 100:
        raise ValueError("Black L* is 100!")
    vv = (l - bpl) / (100.0 - bpl)  # 0 at bp, 1 at wp
    vv = 1.0 - vv  # 1 at bp, 0 at wp
    if vv < 0.0:
        vv = 0.0
    elif vv > 1.0:
        vv = 1.0
    vv = math.pow(vv, power) * signscale
    a += vv * bpa
    b += vv * bpb
    return Lab2XYZ(l, a, b, whitepoint=wp)


def blend_blackpoint(
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    bp_in: None | tuple = None,
    bp_out: None | tuple = None,
    wp: None | float | str | list | tuple = None,
    power: float = 40.0,
    pin_chromaticity: bool = False,
) -> tuple[float, float, float]:
    """Blend to destination black as L approaches black, with optional input black compensation.

    Args:
        X (float): X value
        Y (float): Y value
        Z (float): Z value
        bp_in (tuple): Input black point
        bp_out (tuple): Output black point
        wp (str or tuple): White point, defaults to "D50"
        power (float): Power for blending, defaults to 40.0
        pin_chromaticity (bool): Whether to pin chromaticity, defaults to False.

    Returns:
        tuple[float, float, float]: Adjusted X, Y, Z values.
    """  # noqa: E501
    wp = get_whitepoint(wp)

    for i, bp in enumerate((bp_in, bp_out)):
        if not bp or tuple(bp) == (0, 0, 0):
            continue
        bp_wp = tuple(v / wp[1] * bp[1] for v in wp)
        if i == 0:
            X, Y, Z = blend_ab(X, Y, Z, bp, wp, power, -1)  # noqa: N806
            X, Y, Z = apply_bpc(X, Y, Z, bp_wp, None, wp, pin_chromaticity)  # noqa: N806
        else:
            X, Y, Z = apply_bpc(X, Y, Z, None, bp_wp, wp, pin_chromaticity)  # noqa: N806
            X, Y, Z = blend_ab(X, Y, Z, bp, wp, power, 1)  # noqa: N806

    return X, Y, Z


def interp_old(
    x: float,
    xp: list,
    fp: list,
    left: None | float = None,
    right: None | float = None,
) -> float:
    """One-dimensional linear interpolation similar to numpy.interp.

    Values do NOT have to be monotonically increasing
    interp(0, [0, 0], [0, 1]) will return 0.

    Args:
        x (float): The x value to interpolate.
        xp (list): The x-coordinates of the data points.
        fp (list): The y-coordinates of the data points.
        left (float, optional): Value to return for x < xp[0]. Defaults to None.
        right (float, optional): Value to return for x > xp[-1]. Defaults to None.

    Returns:
        float: Interpolated value.
    """
    if not isinstance(x, (int, float, complex)):
        return [interp_old(n, xp, fp, left, right) for n in x]
    if x in xp:
        return fp[xp.index(x)]
    if x < xp[0]:
        return fp[0] if left is None else left
    if x > xp[-1]:
        return fp[-1] if right is None else right
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
def interp(
    x: float | list,
    xp: list,
    fp: list,
    left: None | float = None,
    right: None | float = None,
    period: None | float = None,
) -> float | list:
    """One-dimensional linear interpolation similar to numpy.interp.

    Values do NOT have to be monotonically increasing
    interp(0, [0, 0], [0, 1]) will return 0

    Args:
        x (float or list): The x value(s) to interpolate.
        xp (list): The x-coordinates of the data points.
        fp (list): The y-coordinates of the data points.
        left (float, optional): Value to return for x < xp[0]. Defaults to None.
        right (float, optional): Value to return for x > xp[-1]. Defaults to None.
        period (float, optional): Periodicity of the interpolation. Defaults to None.

    Returns:
        float | list: Interpolated value(s).
    """
    # TODO: This function overrides the class implementation (Interp) and forces to use
    #       numpy.interp all the time, and it is kind of rude in that manner.
    #       Please respect the previous implementation, but use nump.interp again.
    return numpy.interp(x, xp, fp, left, right, period)


def interp_resize(iterable: list, new_size: int, use_numpy: bool = False) -> list:
    """Change size of iterable through linear interpolation.

    Args:
        iterable (list): A list of float values.
        new_size (int): New size of the list
        use_numpy (bool): Use numpy for interpolation. Defaults to False.

    Returns:
        list: Interpolated values.
    """
    # interp = Interp(list(range(len(iterable))), iterable, use_numpy=use_numpy)
    return [
        interp(
            i / (new_size - 1.0) * (len(iterable) - 1.0),
            list(range(len(iterable))),
            iterable,
        )
        for i in range(new_size)
    ]


def interp_fill(xp: list, fp: list, new_size: int, use_numpy: bool = False) -> list:
    """Fill missing points by interpolation.

    Args:
        xp (list): X values
        fp (list): Y values
        new_size (int): New size of the list
        use_numpy (bool): Use numpy for interpolation. Defaults to False.

    Returns:
        list: Interpolated values.
    """
    # interp = Interp(xp, fp, use_numpy=use_numpy)
    return [interp(i / (new_size - 1.0) * xp[-1], xp, fp) for i in range(new_size)]


def smooth_avg_old(
    values: list,
    passes: int = 1,
    window: None | tuple | list = None,
    protect: None | list = None,
) -> list:
    """Smooth values (moving average).

    Args:
        values (list): A list of float values.
        passes (int): Number of passes
        window (tuple/list): Tuple or list containing weighting factors. Its length
            determines the size of the window to use. Defaults to (1.0, 1.0, 1.0)
        protect (list): A list of indices to protect. The values related to these
            indices will be protected.

    Returns:
        list: Smoothed values.
    """
    if not window or len(window) < 3 or len(window) % 2 != 1:
        if window:
            warnings.warn(
                f"Invalid window {window!r}, size {len(window)} "
                "- using default (1, 1, 1)",
                Warning,
                stacklevel=2,
            )
        window = (1.0, 1.0, 1.0)
    for _x in range(passes):
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
                    tmp_window = tmp_window[1:-1]
            data.append(v)
        values = data
    return values


def smooth_avg(
    values: list,
    passes: int = 1,
    window: None | tuple[float, float, float] | list = None,
    protect: None | list = None,
) -> list:
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

    Returns:
        list: Smoothed values.
    """
    if not window or len(window) < 3 or len(window) % 2 != 1:
        if window:
            warnings.warn(
                f"Invalid window {window!r}, size {len(window)} "
                "- using default (1, 1, 1)",
                Warning,
                stacklevel=2,
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

    for _ in range(passes):
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


def compute_bpc(
    bp_in: tuple[float, float, float],
    bp_out: tuple[float, float, float],
) -> tuple[Matrix3x3, list]:
    """Black point compensation. Implemented as a linear scaling in XYZ.

    Black points should come relative to the white point. Fills and
    returns a matrix/offset element.

    [matrix]*bp_in + offset = bp_out
    [matrix]*D50  + offset = D50

    Args:
        bp_in (tuple[float, float, float]): Input black point in XYZ.
        bp_out (tuple[float, float, float]): Output black point in XYZ.

    Returns:
        tuple[Matrix, list]: A tuple containing a Matrix3x3 and an offset list.
            The matrix is used to scale the input black point to the output
            black point, and the offset is used to adjust the output black
            point to the desired value.
    """
    # This is a linear scaling in the form ax+b, where
    # a = (bp_out - D50) / (bp_in - D50)
    # b = - D50* (bp_out - bp_in) / (bp_in - D50)

    d50 = get_standard_illuminant("D50")

    tx = bp_in[0] - d50[0]
    ty = bp_in[1] - d50[1]
    tz = bp_in[2] - d50[2]

    ax = (bp_out[0] - d50[0]) / tx
    ay = (bp_out[1] - d50[1]) / ty
    az = (bp_out[2] - d50[2]) / tz

    bx = -d50[0] * (bp_out[0] - bp_in[0]) / tx
    by = -d50[1] * (bp_out[1] - bp_in[1]) / ty
    bz = -d50[2] * (bp_out[2] - bp_in[2]) / tz

    matrix = Matrix3x3([[ax, 0, 0], [0, ay, 0], [0, 0, az]])
    offset = [bx, by, bz]
    return matrix, offset


def delta(
    L1: float,  # noqa: N803
    a1: float,
    b1: float,
    L2: float,  # noqa: N803
    a2: float,
    b2: float,
    method: str = "1976",
    p1: None | float = None,
    p2: None | float = None,
    p3: None | float = None,
    cie94_use_symmetric_chrominance: bool = True,
) -> dict:
    """Compute the delta of two samples.

    - CIE 1994 & CMC calculation code derived from formulas on
        www.brucelindbloom.com
    - CIE 1994 code uses some alterations seen on
        www.farbmetrik-gall.de/cielab/korrcielab/cie94.html
        (see notes in code below)
    - CIE 2000 calculation code derived from Excel spreadsheet available at
        www.ece.rochester.edu/~gsharma/ciede2000

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

    Args:
        L1 (float): Lightness of first sample
        a1 (float): a* value of first sample
        b1 (float): b* value of first sample
        L2 (float): Lightness of second sample
        a2 (float): a* value of second sample
        b2 (float): b* value of second sample
        method (str): Method to use for delta calculation.
            Can be "CIE94", "CMC", "CIE2K" or "CIE76". Defaults to "CIE76".
        p1 (float): Parameter 1
            - for CIE94, if not None, adjusts calculation for textiles,
              otherwise for graphics arts (default if p1 is not set)
            - for CMC, equals l (lightness) weighting factor (default if p1 is
                not set)
            - for CIE2K, equals kL (lightness) weighting factor (default if p1
                is not set)
        p2 (float): Parameter 2
            - for CIE94, not used (default if p2 is not set)
            - for CMC, equals c (chroma) weighting factor (default if p2 is not
                set)
            - for CIE2K, equals kC (chroma) weighting factor (default if p2 is
                not set)
        p3 (float): Parameter 3
            - for CIE94, not used (default if p3 is not set)
            - for CMC, not used (default if p3 is not set)
            - for CIE2K, equals kH (hue) weighting factor (default if p3 is not
                set)
        cie94_use_symmetric_chrominance (bool):
            If True, CIE94 will use symmetric chrominance calculation.
            If False, it will use asymmetric chrominance calculation.
            Defaults to True.

    Returns:
        dict: A dictionary containing the delta E value and the method used.
            The dictionary will have the following keys:
                - "E": The calculated delta E value.
                - "L": The difference in lightness between the two samples.
                - "C": The difference in chroma between the two samples.
                - "H": The difference in hue between the two samples.
                - "a": The a* value of the first sample.
                - "b": The b* value of the first sample.
                - "Lw": The lightness difference adjusted for the method used.
                - "Cw": The chroma difference adjusted for the method used.
                - "Hw": The hue difference adjusted for the method used.
    """
    method = method.lower() if isinstance(method, str) else str(int(method))
    if method in ("94", "1994", "cie94", "cie1994"):
        textiles = p1
        dl = L2 - L1
        c1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        c2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        dc = c2 - c1
        dh2 = math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dc, 2)
        dh = math.sqrt(dh2) if dh2 > 0 else 0
        sl = 1.0
        k1 = 0.048 if textiles else 0.045
        k2 = 0.014 if textiles else 0.015
        c_ = math.sqrt(c1 * c2) if cie94_use_symmetric_chrominance else c1
        sc = 1.0 + k1 * c_
        sh = 1.0 + k2 * c_
        kl = 2.0 if textiles else 1.0
        kc = 1.0
        kh = 1.0
        dlw, dcw, dhw = dl / (kl * sl), dc / (kc * sc), dh / (kh * sh)
        de = math.sqrt(math.pow(dlw, 2) + math.pow(dcw, 2) + math.pow(dhw, 2))
    elif method in ("cmc(2:1)", "cmc21", "cmc(1:1)", "cmc11", "cmc"):
        if method in ("cmc(2:1)", "cmc21"):
            p1 = 2.0
        l = p1 if isinstance(p1, (float, int)) else 1.0
        c = p2 if isinstance(p2, (float, int)) else 1.0
        dl = L2 - L1
        c1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        c2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        dc = c2 - c1
        dh2 = math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dc, 2)
        dh = math.sqrt(dh2) if dh2 > 0 else 0
        sl = 0.511 if L1 < 16 else (0.040975 * L1) / (1 + 0.01765 * L1)
        sc = (0.0638 * c1) / (1 + 0.0131 * c1) + 0.638
        f = math.sqrt(math.pow(c1, 4) / (math.pow(c1, 4) + 1900.0))
        h1 = math.degrees(math.atan2(b1, a1)) + (0 if b1 >= 0 else 360.0)
        t = (
            0.56 + abs(0.2 * math.cos(math.radians(h1 + 168.0)))
            if 164 <= h1 <= 345
            else 0.36 + abs(0.4 * math.cos(math.radians(h1 + 35)))
        )
        sh = sc * (f * t + 1 - f)
        dlw, dcw, dhw = dl / (l * sl), dc / (c * sc), dh / sh
        de = math.sqrt(math.pow(dlw, 2) + math.pow(dcw, 2) + math.pow(dhw, 2))
    elif method in ("00", "2k", "2000", "cie00", "cie2k", "cie2000"):
        pow25_7 = math.pow(25, 7)
        k_l = p1 if isinstance(p1, (float, int)) else 1.0
        k_c = p2 if isinstance(p2, (float, int)) else 1.0
        k_h = p3 if isinstance(p3, (float, int)) else 1.0
        c1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        c2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        c_avg = avg(c1, c2)
        g = 0.5 * (1 - math.sqrt(math.pow(c_avg, 7) / (math.pow(c_avg, 7) + pow25_7)))
        l1_ = L1
        a1_ = (1 + g) * a1
        b1_ = b1
        l2_ = L2
        a2_ = (1 + g) * a2
        b2_ = b2
        c1_ = math.sqrt(math.pow(a1_, 2) + math.pow(b1_, 2))
        c2_ = math.sqrt(math.pow(a2_, 2) + math.pow(b2_, 2))
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
        dl_ = l2_ - l1_
        dl = dl_
        dc_ = c2_ - c1_
        dc = dc_
        dhh_ = 2 * math.sqrt(c1_ * c2_) * math.sin(math.radians(dh_ / 2.0))
        dh = dhh_
        l__avg = avg(l1_, l2_)
        c__avg = avg(c1_, c2_)
        h__avg_cond = (
            3.0
            if c1_ * c2_ == 0
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
        ab = math.pow(l__avg - 50.0, 2)  # (L'_ave-50)^2
        s_l = 1 + 0.015 * ab / math.sqrt(20.0 + ab)
        s_c = 1 + 0.045 * c__avg
        t = (
            1
            - 0.17 * math.cos(math.radians(h__avg - 30.0))
            + 0.24 * math.cos(math.radians(2.0 * h__avg))
            + 0.32 * math.cos(math.radians(3.0 * h__avg + 6.0))
            - 0.2 * math.cos(math.radians(4 * h__avg - 63.0))
        )
        s_h = 1 + 0.015 * c__avg * t
        dtheta = 30.0 * math.exp(-1 * math.pow((h__avg - 275.0) / 25.0, 2))
        r_c = 2.0 * math.sqrt(math.pow(c__avg, 7) / (math.pow(c__avg, 7) + pow25_7))
        r_t = -math.sin(math.radians(2.0 * dtheta)) * r_c
        aj = dl_ / s_l / k_l  # dL' / k_L / S_L
        ak = dc_ / s_c / k_c  # dC' / k_C / S_C
        al = dhh_ / s_h / k_h  # dH' / k_H / S_H
        dlw, dcw, dhw = aj, ak, al
        de = math.sqrt(
            math.pow(aj, 2) + math.pow(ak, 2) + math.pow(al, 2) + r_t * ak * al
        )
    else:
        # dE 1976
        dl = L2 - L1
        c1 = math.sqrt(math.pow(a1, 2) + math.pow(b1, 2))
        c2 = math.sqrt(math.pow(a2, 2) + math.pow(b2, 2))
        dc = c2 - c1
        dh2 = math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2) - math.pow(dc, 2)
        dh = math.sqrt(dh2) if dh2 > 0 else 0
        dlw, dcw, dhw = dl, dc, dh
        de = math.sqrt(math.pow(dl, 2) + math.pow(a1 - a2, 2) + math.pow(b1 - b2, 2))

    return {
        "E": de,
        "L": dl,
        "C": dc,
        "H": dh,
        "a": a1 - a2,
        "b": b1 - b2,
        # Weighted
        "Lw": dlw,
        "Cw": dcw,
        "Hw": dhw,
    }


def XYZ2Lab_delta(  # noqa: N802
    X1: float,  # noqa: N803
    Y1: float,  # noqa: N803
    Z1: float,  # noqa: N803
    X2: float,  # noqa: N803
    Y2: float,  # noqa: N803
    Z2: float,  # noqa: N803
    method: str = "76",
    whitepoint1: None | float | str | list | tuple = "D50",
    whitepoint2: None | float | str | list | tuple = "D50",
    whitepoint_reference: None | float | str | tuple = "D50",
    cat: str = "Bradford",
) -> dict:
    """Compute the delta of two samples in XYZ space.

    Args:
        X1 (float): XYZ values of the first sample.
        Y1 (float): XYZ values of the first sample.
        Z1 (float): XYZ values of the first sample.
        X2 (float): XYZ values of the second sample.
        Y2 (float): XYZ values of the second sample.
        Z2 (float): XYZ values of the second sample.
        method (str): Method to use for delta calculation. Defaults to "76".
        whitepoint1 (None | float | str | list | tuple): Whitepoint of
            the first sample. Defaults to "D50".
        whitepoint2 (None | float | str | list | tuple): Whitepoint of
            the second sample. Defaults to "D50".
        whitepoint_reference (None | float | str | list | tuple): Reference
            whitepoint. Defaults to "D50".
        cat (str): Chromatic adaptation transform. Defaults to "Bradford".

    Returns:
        dict: Dictionary containing the delta values.
    """
    whitepoint1 = get_whitepoint(whitepoint1)
    whitepoint2 = get_whitepoint(whitepoint2)
    whitepoint_reference = get_whitepoint(whitepoint_reference)
    if whitepoint1 != whitepoint_reference:
        X1, Y1, Z1 = adapt(X1, Y1, Z1, whitepoint1, whitepoint_reference, cat)  # noqa: N806
    if whitepoint2 != whitepoint_reference:
        X2, Y2, Z2 = adapt(X2, Y2, Z2, whitepoint2, whitepoint_reference, cat)  # noqa: N806
    l1, a1, b1 = XYZ2Lab(X1, Y1, Z1, whitepoint_reference)
    l2, a2, b2 = XYZ2Lab(X2, Y2, Z2, whitepoint_reference)
    logger.debug(
        f"L*a*b*[1] {l1:.4f} {a1:.4f} {b1:.4f} L*a*b*[2] {l2:.4f} {a2:.4f} {b2:.4f}"
    )
    return delta(l1, a1, b1, l2, a2, b2, method)


def is_similar_matrix(
    matrix1: Matrix3x3, matrix2: Matrix3x3, digits: float = 3
) -> bool:
    """Check if two matrices are equal up to n decimal digits.

    Args:
        matrix1 (Matrix3x3): First matrix to compare.
        matrix2 (Matrix3x3): Second matrix to compare.
        digits (int): Number of decimal digits to consider for equality.
            Defaults to 3.

    Returns:
        bool: True if the matrices are equal up to the specified number of
            digits, False otherwise.
    """
    return matrix1.rounded(digits) == matrix2.rounded(digits)


def is_equal(
    values1: list[float],
    values2: list[float],
    quantizer: None | Callable = None,
) -> bool:
    """Check if two value sets are equal after quantization.

    Args:
        values1 (list): First list of float values.
        values2 (list): Second list of float values.
        quantizer (callable, optional): Function to quantize the values. If None,
            defaults to rounding to 4 decimal places.

    Returns:
        bool: True if the quantized values are equal, False otherwise.
    """
    if quantizer is None:

        def quantizer(v: float) -> float:
            """Default quantizer that rounds to 4 decimal places.

            Args:
                v (float): The value to quantize.

            Returns:
                float: The quantized value rounded to 4 decimal places.
            """
            return round(v, 4)

    return [quantizer(v) for v in values1] == [quantizer(v) for v in values2]


def four_color_matrix(
    xrr: float,  # noqa: N803
    yrr: float,  # noqa: N803
    zrr: float,  # noqa: N803
    xrg: float,  # noqa: N803
    yrg: float,  # noqa: N803
    zrg: float,  # noqa: N803
    xrb: float,  # noqa: N803
    yrb: float,  # noqa: N803
    zrb: float,  # noqa: N803
    xrw: float,  # noqa: N803
    yrw: float,  # noqa: N803
    zrw: float,  # noqa: N803
    xmr: float,  # noqa: N803
    ymr: float,  # noqa: N803
    zmr: float,  # noqa: N803
    xmg: float,  # noqa: N803
    ymg: float,  # noqa: N803
    zmg: float,  # noqa: N803
    xmb: float,  # noqa: N803
    ymb: float,  # noqa: N803
    zmb: float,  # noqa: N803
    xmw: float,  # noqa: N803
    ymw: float,  # noqa: N803
    zmw: float,  # noqa: N803
    y_correction: bool = True,  # noqa: N803
) -> Matrix3x3:
    """Four-Color Matrix Method for Correction of Tristimulus Colorimeters.

    Based on paper published in Proc., IS&T Fifth Color Imaging Conference,
    301-305 (1997) and IS&T Sixth Color Imaging Conference (1998).

    Args:
        xrr (float): Reference RGB values for red.
        yrr (float): Reference RGB values for red.
        zrr (float): Reference RGB values for red.
        xrg (float): Reference RGB values for green.
        yrg (float): Reference RGB values for green.
        zrg (float): Reference RGB values for green.
        xrb (float): Reference RGB values for blue.
        yrb (float): Reference RGB values for blue.
        zrb (float): Reference RGB values for blue.
        xrw (float): Reference RGB values for white.
        yrw (float): Reference RGB values for white.
        zrw (float): Reference RGB values for white.
        xmr (float): Measured RGB values for red.
        ymr (float): Measured RGB values for red.
        zmr (float): Measured RGB values for red.
        xmg (float): Measured RGB values for green.
        ymg (float): Measured RGB values for green.
        zmg (float): Measured RGB values for green.
        xmb (float): Measured RGB values for blue.
        ymb (float): Measured RGB values for blue.
        zmb (float): Measured RGB values for blue.
        xmw (float): Measured RGB values for white.
        ymw (float): Measured RGB values for white.
        zmw (float): Measured RGB values for white.
        y_correction (bool): If True, apply Y correction. Defaults to True.

    Returns:
        Matrix3x3: The four-color matrix.
    """
    components = {
        "XrR": xrr,
        "YrR": yrr,
        "ZrR": zrr,
        "XrG": xrg,
        "YrG": yrg,
        "ZrG": zrg,
        "XrB": xrb,
        "YrB": yrb,
        "ZrB": zrb,
        "XrW": xrw,
        "YrW": yrw,
        "ZrW": zrw,
        "XmR": xmr,
        "YmR": ymr,
        "ZmR": zmr,
        "XmG": xmg,
        "YmG": ymg,
        "ZmG": zmg,
        "XmB": xmb,
        "YmB": ymb,
        "ZmB": zmb,
        "XmW": xmw,
        "YmW": ymw,
        "ZmW": zmw,
    }
    xyz = {}
    m = {}
    k = {}
    for s in "mr":
        xyz[s] = {}
        for color in "RGBW":
            x, y, _ = XYZ2xyY(
                *(components[f"{component}{s}{color}"] for component in "XYZ")
            )
            xyz[s][color] = x, y, 1 - x - y
        m[s] = Matrix3x3([xyz[s][color] for color in "RGB"]).transposed()
        k[s] = m[s].inverted() * xyz[s]["W"]
        m[f"{s}RGB"] = m[s] * Matrix3x3(
            [[k[s][0], 0, 0], [0, k[s][1], 0], [0, 0, k[s][2]]]
        )
    r = m["rRGB"] * m["mRGB"].inverted()
    if y_correction:
        # The Y calibration factor kY is obtained as the ratio of the reference
        # luminance value to the matrix-corrected Y value, as defined in
        # Four-Color Matrix Method for Correction of Tristimulus Colorimeters -
        # Part 2
        mw = xmw, ymw, zmw
        ky = yrw / (r * mw)[1]
        r[:] = [[ky * v for v in row] for row in r]
    return r


def get_gamma(
    values: list | tuple,
    scale: float = 1.0,
    vmin: float = 0.0,
    vmax: float = 1.0,
    average: bool = True,
    least_squares: bool = False,
) -> float | list:
    """Return average or least squares gamma or a list of gamma values.

    Args:
        values (list): A list of tuples containing x and y values.
        scale (float): The scale factor. Defaults to 1.0.
        vmin (float): Minimum value. Defaults to 0.0.
        vmax (float): Maximum value. Defaults to 1.0.
        average (bool): If True, return the average gamma. Defaults to True.
        least_squares (bool): If True, return the least squares gamma. Defaults
            to False.

    Returns:
        float | list: The average or least squares gamma, or a list of gamma
            values.
    """
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
        if not gammas:
            return 0
        return sum(gammas) / len(gammas)
    return gammas


def guess_cat(
    chad: Matrix3x3,
    whitepoint_source: None | float | str | list | tuple = None,
    whitepoint_destination: None | float | str | list | tuple = None,
) -> None | str:
    """Guess the chromatic adaption transform used in a chromatic adaption matrix.

    ...as found in an ICC profile's 'chad' tag

    Args:
        chad (Matrix3x3): The chromatic adaption matrix.
        whitepoint_source (tuple): The source whitepoint.
        whitepoint_destination (tuple): The destination whitepoint.

    Returns:
        None | str: The guessed chromatic adaption transform.
    """
    if chad == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]:
        # Cannot figure out CAT from identity chad
        return None
    for cat in CAT_MATRICES:
        if is_similar_matrix(
            (
                chad
                * CAT_MATRICES[cat].inverted()
                * LMS_wp_adaption_matrix(whitepoint_destination, whitepoint_source, cat)
            ).inverted(),
            CAT_MATRICES[cat],
            2,
        ):
            return cat
    return None


def CIEDCCT2xyY(T: float, scale: float = 1.0) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from CIE correlated daylight temperature to xyY.

    Based on formula from http://brucelindbloom.com/Eqn_T_to_xy.html

    Args:
        T (float): The temperature in Kelvin.
        scale (float): The scale factor. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The xyY values.
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
        warnings.warn(
            "Daylight CCT is only accurate down to about 4000 K",
            Warning,
            stacklevel=2,
        )
    if T <= 7000:
        xd = (
            ((-4.607 * math.pow(10, 9)) / math.pow(T, 3))
            + ((2.9678 * math.pow(10, 6)) / math.pow(T, 2))
            + ((0.09911 * math.pow(10, 3)) / T)
            + 0.244063
        )
    else:
        xd = (
            ((-2.0064 * math.pow(10, 9)) / math.pow(T, 3))
            + ((1.9018 * math.pow(10, 6)) / math.pow(T, 2))
            + ((0.24748 * math.pow(10, 3)) / T)
            + 0.237040
        )
    yd = -3 * math.pow(xd, 2) + 2.87 * xd - 0.275
    return xd, yd, scale


def CIEDCCT2XYZ(T: float, scale: float = 1.0) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from CIE correlated daylight temperature to XYZ.

    Args:
        T (float): The temperature in Kelvin.
        scale (float): The scale factor. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The XYZ values.
    """
    xyY = CIEDCCT2xyY(T, scale)  # noqa: N806
    return xyY2XYZ(*xyY) if xyY else None  # noqa: N806


def cLUT65_to_VidRGB(v: float, size: int = 65) -> float:  # noqa: N802
    """cLUT65 to VidRGB conversion.

    cLUT Input value tweaks to make Video encoded black land on
    65 res grid nodes, which should help 33 and 17 res cLUTs too.

    Args:
        v (float): The value to convert.
        size (int): The size of the LUT. Defaults to 65.

    Returns:
        float: The converted value.
    """
    if v <= 236.0 / 256:
        # Scale up to near black point
        return v * 256.0 / 255
    return 1 - (1 - v) * (1 - 236.0 / 255) / (1 - 236.0 / 256)


def VidRGB_to_cLUT65(v: float, size: int = 65) -> float:  # noqa: N802
    """Convert from VidRGB to cLUT65.

    Args:
        v (float): The value to convert.
        size (int): The size of the LUT. Defaults to 65.

    Returns:
        float: The converted value.
    """
    if v <= 236.0 / 255.0:
        return v * 255.0 / 256
    return 1 - (1 - v) * (1 - 236.0 / 256) / (1 - 236.0 / 255)


def VidRGB_to_eeColor(v: float) -> float:  # noqa: N802
    """Convert from VidRGB to eeColor.

    Args:
        v (float): The value to convert.

    Returns:
        float: The converted value.
    """
    return v * 255.0 / 256.0


def eeColor_to_VidRGB(v: float) -> float:  # noqa: N802
    """Convert from eeColor to VidRGB.

    Args:
        v (float): The value to convert.

    Returns:
        float: The converted value.
    """
    return v * 256.0 / 255.0


def DIN992Lab(  # noqa: N802
    l99: float,
    a99: float,
    b99: float,
    kCH: float = 1.0,  # noqa: N803
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from DIN99 to Lab.

    Args:
        l99 (float): The L value of the color.
        a99 (float): The a value of the color.
        b99 (float): The b value of the color.
        kCH (float, optional): The kCH value of the color. Defaults to 1.0.
        kE (float, optional): The kE value of the color. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    c99, h99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        l99, c99, h99, 0, 105.51, 0.0158, 16, 0.7, 1 / (0.045 * kCH * kE), 0.045, kE, 0
    )


def DIN99b2Lab(l99: float, a99: float, b99: float) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from DIN99b to Lab.

    Args:
        l99 (float): The L value of the color.
        a99 (float): The a value of the color.
        b99 (float): The b value of the color.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    c99, h99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(l99, c99, h99, 0, 303.67, 0.0039, 26, 0.83, 23, 0.075)


def DIN99o2Lab(  # noqa: N802
    l99: float,
    a99: float,
    b99: float,
    kCH: float = 1.0,  # noqa: N803
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from DIN99o to Lab.

    Args:
        l99 (float): The L value of the color.
        a99 (float): The a value of the color.
        b99 (float): The b value of the color.
        kCH (float, optional): The kCH value of the color. Defaults to 1.0.
        kE (float, optional): The kE value of the color. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    c99, h99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        l99, c99, h99, 0, 303.67, 0.0039, 26, 0.83, 1 / (0.0435 * kCH * kE), 0.075, kE
    )


def DIN99bLCH2Lab(l99: float, c99: float, h99: float) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from DIN99bLCH to Lab.

    Args:
        l99 (float): The L value of the color.
        c99 (float): The C value of the color.
        h99 (float): The H value of the color.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    return DIN99familyLCH2Lab(l99, c99, h99, 0, 303.67, 0.0039, 26, 0.83, 23, 0.075)


def DIN99c2Lab(  # noqa: N802
    l99: float,  # noqa: N803
    a99: float,
    b99: float,
    whitepoint: None | float | str | list | tuple = None,
) -> tuple[float, float, float]:
    """Convert from DIN99c to Lab.

    Args:
        l99 (float): The L value of the color.
        a99 (float): The a value of the color.
        b99 (float): The b value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    c99, h99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        l99, c99, h99, 0.1, 317.651, 0.0037, 0, 0.94, 23, 0.066, whitepoint
    )


def DIN99d2Lab(  # noqa: N802
    l99: float,  # noqa: N803
    a99: float,
    b99: float,
    whitepoint: None | float | str | list | tuple = None,
) -> tuple[float, float, float]:
    """Convert from DIN99d to Lab.

    Args:
        l99 (float): The L value of the color.
        a99 (float): The a value of the color.
        b99 (float): The b value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    c99, h99 = DIN99familyab2DIN99CH(a99, b99)
    return DIN99familyLCH2Lab(
        l99, c99, h99, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint
    )


def DIN99dLCH2Lab(  # noqa: N802
    l99: float,  # noqa: N803
    c99: float,  # noqa: N803
    h99: float,  # noqa: N803
    whitepoint: None | float | str | list | tuple = None,
) -> tuple[float, float, float]:
    """Convert from DIN99dLCH to Lab.

    Args:
        l99 (float): The L value of the color.
        c99 (float): The C value of the color.
        h99 (float): The H value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    return DIN99familyLCH2Lab(
        l99, c99, h99, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint
    )


def DIN99familyLCH2Lab(  # noqa: N802
    l99: float,  # noqa: N803
    c99: float,  # noqa: N803
    h99: float,  # noqa: N803
    x: float,
    l1: float,
    l2: float,
    deg: float,
    f1: float,
    c1: float,
    c2: float,
    whitepoint: None | float | str | list | tuple = None,
    kE: float = 1.0,  # noqa: N803
    hdeg: None | float = None,
) -> tuple[float, float, float]:
    """Convert from DIN99LCH to Lab.

    Args:
        l99 (float): The L value of the color.
        c99 (float): The C value of the color.
        h99 (float): The H value of the color.
        x (float): The x value of the color.
        l1 (float): The l1 value of the color.
        l2 (float): The l2 value of the color.
        deg (float): The degree value of the color.
        f1 (float): The f1 value of the color.
        c1 (float): The c1 value of the color.
        c2 (float): The c2 value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.
        kE (float, optional): The kE value of the color. Defaults to 1.0.
        hdeg (None | float, optional): The hdeg value of the color. Defaults to
            None.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    g = (math.exp(c99 / c1) - 1) / c2
    if hdeg is None:
        hdeg = deg
    h99 -= hdeg
    l, a, b = DIN99familyLHCG2Lab(l99, h99, c99, g, kE, l1, l2, deg, f1)
    if x:
        whitepoint99d = XYZ2DIN99cdXYZ(*get_whitepoint(whitepoint, 100), x=x)
        X, Y, Z = Lab2XYZ(l, a, b, whitepoint99d, scale=100)  # noqa: N806
        X, Y, Z = DIN99cdXYZ2XYZ(X, Y, Z, x)  # noqa: N806
        l, a, b = XYZ2Lab(X, Y, Z, whitepoint)
    return l, a, b


def DIN99cdXYZ2XYZ(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    x: float,
) -> tuple[float, float, float]:
    """Convert from DIN99cdXYZ to XYZ.

    Args:
        X (float): The X value of the color.
        Y (float): The Y value of the color.
        Z (float): The Z value of the color.
        x (float): The x value of the color.

    Returns:
        tuple[float, float, float]: The X, Y, Z values.
    """
    X = (X + x * Z) / (1 + x)  # noqa: N806
    return X, Y, Z


def DIN99familyLHCG2Lab(  # noqa: N802
    l99: float,  # noqa: N803
    h99: float,  # noqa: N803
    c99: float,  # noqa: N803
    G: float,  # noqa: N803
    kE: float,  # noqa: N803
    l1: float,
    l2: float,
    deg: float,
    f1: float,
) -> tuple[float, float, float]:
    """Convert from DIN99LCH to Lab.

    Args:
        l99 (float): The L value of the color.
        h99 (float): The H value of the color.
        c99 (float): The C value of the color.
        G (float): The G value of the color.
        kE (float): The kE value of the color.
        l1 (float): The l1 value of the color.
        l2 (float): The l2 value of the color.
        deg (float): The degree value of the color.
        f1 (float): The f1 value of the color.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    l = (math.exp((l99 * kE) / l1) - 1) / l2
    h99ef = h99 * math.pi / 180
    e = G * math.cos(h99ef)
    f = G * math.sin(h99ef)
    rad = deg * math.pi / 180
    a = e * math.cos(rad) - (f / f1) * math.sin(rad)
    b = e * math.sin(rad) + (f / f1) * math.cos(rad)
    return l, a, b


def DIN99familyCH2DIN99ab(c99: float, h99: float) -> tuple[float, float]:  # noqa: N802, N803
    """Convert from DIN99CH to DIN99ab.

    Args:
        c99 (float): The C value of the color.
        h99 (float): The H value of the color.

    Returns:
        tuple[float, float]: The a99 and b99 values.
    """
    h99ef = h99 * math.pi / 180
    return c99 * math.cos(h99ef), c99 * math.sin(h99ef)


def DIN99familyab2DIN99CH(a99: float, b99: float) -> tuple[float, float]:  # noqa: N802
    """Convert from DIN99ab to DIN99CH.

    Args:
        a99 (float): The a value of the color.
        b99 (float): The b value of the color.

    Returns:
        tuple[float, float]: The c99 and h99 values.
    """
    c99 = math.sqrt(math.pow(a99, 2) + math.pow(b99, 2))
    if a99 > 0:
        h99ef = math.atan2(b99, a99) if b99 >= 0 else 2 * math.pi + math.atan2(b99, a99)
    elif a99 < 0:
        h99ef = math.atan2(b99, a99)
    elif b99 > 0:
        h99ef = math.pi / 2
    elif b99 < 0:
        h99ef = (3 * math.pi) / 2
    else:
        h99ef = 0.0
    h99 = h99ef * 180 / math.pi
    return c99, h99


def HSI2RGB(  # noqa: N802
    H: float,  # noqa: N803
    S: float,  # noqa: N803
    I: float,  # noqa: N803
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from HSI to RGB.

    Args:
        H (float): The hue value of the color.
        S (float): The saturation value of the color.
        I (float): The intensity value of the color.
        scale (float): The scale factor to apply to the RGB values.

    Returns:
        tuple[float, float, float]: The R, G, B values.
    """
    H *= 360  # noqa: N806

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
        r = a
        g = b
        b = c
    elif H <= 240:
        g = a
        b = b
        r = c
    else:
        b = a
        r = b
        g = c

    return tuple(v * scale for v in (r, g, b))


def HSL2RGB(  # noqa: N802
    H: float,  # noqa: N803
    S: float,  # noqa: N803
    L: float,  # noqa: N803
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from HSL to RGB.

    Args:
        H (float): The hue value of the color.
        S (float): The saturation value of the color.
        L (float): The lightness value of the color.
        scale (float): The scale factor to apply to the RGB values.

    Returns:
        tuple[float, float, float]: The R, G, B values.
    """
    return tuple(v * scale for v in colorsys.hls_to_rgb(H, L, S))


def HSV2RGB(  # noqa: N802
    H: float,  # noqa: N803
    S: float,  # noqa: N803
    V: float,  # noqa: N803
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from HSV to RGB.

    Args:
        H (float): The hue value of the color.
        S (float): The saturation value of the color.
        V (float): The value (brightness) of the color.
        scale (float): The scale factor to apply to the RGB values.

    Returns:
        tuple[float, float, float]: The R, G, B values.
    """
    return tuple(v * scale for v in colorsys.hsv_to_rgb(H, S, V))


def get_dbl_min() -> float:
    """Get the smallest positive normalized double value.

    Returns:
        float: The smallest positive normalized double value.
    """
    t = "0.0"
    i = 10
    n = 0
    dbl_min = 0.0
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
            dbl_min = float(t + str(i))
    return dbl_min


DBL_MIN = get_dbl_min()


def LCHab2Lab(L: float, C: float, H: float) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from LCHab to Lab.

    Args:
        L (float): The L value of the color.
        C (float): The C value of the color.
        H (float): The H value of the color.

    Returns:
        tuple[float, float, float]: The L, a, b values.
    """
    a = C * math.cos(H * math.pi / 180.0)
    b = C * math.sin(H * math.pi / 180.0)
    return L, a, b


def Lab2DIN99(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kCH: float = 1.0,  # noqa: N803
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kCH (float): The kCH value. Defaults to 1.0.
        kE (float): The kE value. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The l99, a99, b99 values.
    """
    l99, c99, h99 = Lab2DIN99LCH(L, a, b, kCH, kE)
    a99, b99 = DIN99familyCH2DIN99ab(c99, h99)
    return l99, a99, b99


def Lab2DIN99b(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99b.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kE (float): The kE value. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The l99, a99, b99 values.
    """
    l99, c99, h99 = Lab2DIN99bLCH(L, a, b, kE)
    a99, b99 = DIN99familyCH2DIN99ab(c99, h99)
    return l99, a99, b99


def Lab2DIN99o(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kCH: float = 1.0,  # noqa: N803
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99o.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kCH (float): The kCH value.
        kE (float): The kE value.

    Returns:
        tuple[float, float, float]: The l99, a99, b99 values.
    """
    l99, c99, h99 = Lab2DIN99oLCH(L, a, b, kCH, kE)
    a99, b99 = DIN99familyCH2DIN99ab(c99, h99)
    return l99, a99, b99


def Lab2DIN99c(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kE: float = 1.0,  # noqa: N803
    whitepoint: None | float | str | list | tuple = None,
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99c.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kE (float): The kE value. Defaults to 1.0. Unused, but kept for
            compatibility.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.

    Returns:
        tuple[float, float, float]: The l99, a99, b99 values.
    """
    return XYZ2DIN99c(*Lab2XYZ(L, a, b, whitepoint, scale=100), whitepoint)


def Lab2DIN99d(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kE: float = 1.0,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99d.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kE (float, optional): The kE value. Currently not used.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.

    Returns:
        tuple[float, float, float]: The l99, a99, b99 values.
    """
    return XYZ2DIN99d(*Lab2XYZ(L, a, b, whitepoint, scale=100), whitepoint)


def Lab2DIN99LCH(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kCH: float = 1.0,  # noqa: N803
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99 LCH.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kCH (float): The kCH value.
        kE (float): The kE value.

    Returns:
        tuple[float, float, float]: The l99, c99, h99 values.
    """
    return Lab2DIN99familyLCH(
        L, a, b, 105.51, 0.0158, 16, 0.7, 1 / (0.045 * kCH * kE), 0.045, kE, 0
    )


def Lab2DIN99bLCH(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99b LCH.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kE (float): The kE value. Unused, but kept for compatibility.

    Returns:
        tuple[float, float, float]: The l99, c99, h99 values.
    """
    return Lab2DIN99familyLCH(L, a, b, 303.67, 0.0039, 26, 0.83, 23, 0.075)


def Lab2DIN99oLCH(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kCH: float = 1.0,  # noqa: N803
    kE: float = 1.0,  # noqa: N803
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99o LCH.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kCH (float, optional): The kCH value. Defaults to 1.0.
        kE (float, optional): The kE value. Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The l99, c99, h99 values.
    """
    return Lab2DIN99familyLCH(
        L, a, b, 303.67, 0.0039, 26, 0.83, 1 / (0.0435 * kCH * kE), 0.075, kE
    )


def Lab2DIN99familyLCH(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    l1: float,
    l2: float,
    deg: float,
    f1: float,
    c1: float,
    c2: float,
    kE: float = 1.0,  # noqa: N803
    hdeg: None | float = None,
) -> tuple[float, float, float]:
    """Convert from Lab to DIN99 family LCH.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        l1 (float): The l1 value.
        l2 (float): The l2 value.
        deg (float): The degree value.
        f1 (float): The f1 value.
        c1 (float): The c1 value.
        c2 (float): The c2 value.
        kE (float): The kE value.
        hdeg (None | float): The hdeg value. Defaults to None.

    Returns:
        tuple[float, float, float]: The l99, c99, h99 values.
    """
    l99, g, h99ef, _ = Lab2DIN99familyLGhrad(L, a, b, kE, l1, l2, deg, f1)
    c99 = c1 * math.log(1 + c2 * g)
    if hdeg is None:
        hdeg = deg
    h99 = h99ef * 180 / math.pi + hdeg
    return l99, c99, h99


def Lab2DIN99familyLGhrad(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    kE: float,  # noqa: N803
    l1: float,
    l2: float,
    deg: float,
    f1: float,
) -> tuple[float, float, float, float]:
    """Convert from Lab to DIN99 family LCH.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        kE (float): The kE value.
        l1 (float): The l1 value.
        l2 (float): The l2 value.
        deg (float): The degree value.
        f1 (float): The f1 value.

    Returns:
        tuple[float, float, float, float]: The l99, G, h99ef values.
    """
    l99 = (1.0 / kE) * l1 * math.log(1 + l2 * L)
    rad = deg * math.pi / 180
    if rad != 0:
        ar = math.cos(rad)  # a rotation term
        br = math.sin(rad)  # b rotation term
        e = a * ar + b * br
        f = f1 * (b * ar - a * br)
    else:
        e = a
        f = f1 * b
    g = math.sqrt(math.pow(e, 2) + math.pow(f, 2))
    h99ef = math.atan2(f, e)
    return l99, g, h99ef, rad


def Lab2LCHab(L: float, a: float, b: float) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from Lab to LCHab.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.

    Returns:
        tuple[float, float, float]: The LCHab values.
    """
    c = math.sqrt(math.pow(a, 2) + math.pow(b, 2))
    h = 180.0 * math.atan2(b, a) / math.pi
    if h < 0.0:
        h += 360.0
    return L, c, h


def Lab2Luv(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    whitepoint: None | float | str | list | tuple = None,
    scale: float = 100,
) -> tuple[float, float, float]:
    """Convert from Lab to Luv.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.
        scale (float): The scale factor to apply to the output values.
            Defaults to 100.

    Returns:
        tuple[float, float, float]: The Luv values.
    """
    return XYZ2Luv(*Lab2XYZ(L, a, b, whitepoint, scale), whitepoint)


def Lab2RGB(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    rgb_space: None | str | list | tuple = None,
    scale: float = 1.0,
    round_: bool = False,
    clamp: bool = True,
    whitepoint: None | float | str | list | tuple = None,
    whitepoint_source: None | float | str | list | tuple = None,
    noadapt: bool = False,
    cat: str = "Bradford",
) -> list[float]:
    """Convert from Lab to RGB.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        rgb_space (str or tuple): The RGB space to use. Defaults to sRGB.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.
        round_ (bool): Whether to round the output values. Defaults to False.
        clamp (bool): Whether to clamp the output values. Defaults to True.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.
        whitepoint_source (None | float | str | list | tuple): The source
            whitepoint to use. Defaults to D50.
        noadapt (bool): Whether to skip chromatic adaptation. Defaults to False.
        cat (str): The chromatic adaptation transform to use. Defaults to
            "Bradford".

    Returns:
        list[float]: The RGB values.
    """
    x, y, z = Lab2XYZ(L, a, b, whitepoint)
    if not noadapt:
        rgb_space = get_rgb_space(rgb_space)
        x, y, z = adapt(x, y, z, whitepoint_source, rgb_space[1], cat)
    return XYZ2RGB(x, y, z, rgb_space, scale, round_, clamp)


def Lab2XYZ(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    whitepoint: None | float | str | list | tuple = None,
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from Lab to XYZ.

    The input L value needs to be in the nominal range [0.0, 100.0] and
    other input values scaled accordingly.
    The output XYZ values are in the nominal range [0.0, scale].

    whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or
    color temperature as float or int. Defaults to D50 if not set.

    Based on formula from http://brucelindbloom.com/Eqn_Lab_to_XYZ.html

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The XYZ values.
    """
    fy = (L + 16) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    if math.pow(fx, 3.0) > LSTAR_E:
        xr = math.pow(fx, 3.0)
    else:
        xr = (116.0 * fx - 16) / LSTAR_K

    yr = math.pow((L + 16) / 116.0, 3.0) if L > LSTAR_K * LSTAR_E else L / LSTAR_K
    zr = (
        math.pow(fz, 3.0)
        if math.pow(fz, 3.0) > LSTAR_E
        else (116.0 * fz - 16) / LSTAR_K
    )

    Xr, Yr, Zr = get_whitepoint(whitepoint, scale)  # noqa: N806
    return (xr * Xr), (yr * Yr), (zr * Zr)


def Lab2xyY(  # noqa: N802
    L: float,  # noqa: N803
    a: float,
    b: float,
    whitepoint: None | float | str | list | tuple = None,
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from Lab to xyY.

    Args:
        L (float): The L value of the color.
        a (float): The a value of the color.
        b (float): The b value of the color.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The xyY values.
    """
    return XYZ2xyY(*Lab2XYZ(L, a, b, whitepoint, scale), whitepoint)


def Luv2LCHuv(L: float, u: float, v: float) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from Luv to LCHuv.

    Args:
        L (float): The L value of the color.
        u (float): The u' value of the color.
        v (float): The v' value of the color.

    Returns:
        tuple[float, float, float]: The LCHuv values.
    """
    c = math.sqrt(math.pow(u, 2) + math.pow(v, 2))
    h = 180.0 * math.atan2(v, u) / math.pi
    if h < 0.0:
        h += 360.0
    return L, c, h


def Luv2RGB(  # noqa: N802
    L: float,  # noqa: N803
    u: float,
    v: float,
    rgb_space: None | str | list | tuple = None,
    scale: float = 1.0,
    round_: bool = False,
    clamp: bool = True,
    whitepoint: None | float | str | list | tuple = None,
) -> list[float]:
    """Convert from Luv to RGB.

    Args:
        L (float): The L value of the color.
        u (float): The u' value of the color.
        v (float): The v' value of the color.
        rgb_space (str or tuple): The RGB space to use. Defaults to sRGB.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.
        round_ (bool): Whether to round the output values. Defaults to False.
        clamp (bool): Whether to clamp the output values. Defaults to True.
        whitepoint (None | float | str | list | tuple): The whitepoint to
            use. Defaults to D50.

    Returns:
        tuple[float, float, float]: The RGB values.
    """
    return XYZ2RGB(*Luv2XYZ(L, u, v, whitepoint), rgb_space, scale, round_, clamp)


def u_v_2xy(u: float, v: float) -> tuple[float, float]:
    """Convert from u'v' to xy.

    Args:
        u (float): The u' value of the color.
        v (float): The v' value of the color.

    Returns:
        tuple[float, float]: The xy values.
    """
    x = (9.0 * u) / (6 * u - 16 * v + 12)
    y = (4 * v) / (6 * u - 16 * v + 12)

    return x, y


def Luv2XYZ(  # noqa: N802
    L: float,  # noqa: N803
    u: float,
    v: float,
    whitepoint: None | str | float | list | tuple = None,
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from Luv to XYZ.

    Args:
        L (float): The L value of the color.
        u (float): The u' value of the color.
        v (float): The v' value of the color.
        whitepoint (str or tuple): The whitepoint to use. Defaults to D50.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The XYZ values.
    """
    xr, yr, zr = get_whitepoint(whitepoint)

    y = math.pow((L + 16.0) / 116.0, 3) if L > LSTAR_K * LSTAR_E else L / LSTAR_K

    uo = (4.0 * xr) / (xr + 15.0 * yr + 3.0 * zr)
    vo = (9.0 * yr) / (xr + 15.0 * yr + 3.0 * zr)

    a = (1.0 / 3.0) * (((52.0 * L) / (u + 13 * L * uo)) - 1)
    b = -5.0 * y
    c = -(1.0 / 3.0)
    d = y * (((39.0 * L) / (v + 13 * L * vo)) - 5)

    x = (d - b) / (a - c)
    z = x * a + b

    return tuple([v * scale for v in (x, y, z)])


def RGB2HSI(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from RGB to HSI.

    The input RGB values need to be in the nominal range [0.0, 1.0] and
    the output HSI values are in the nominal range [0.0, scale].

    Args:
        R (float): The red value of the color.
        G (float): The green value of the color.
        B (float): The blue value of the color.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The HSI values.
    """
    i = (R + G + B) / 3.0
    s = 1 - min(R, G, B) / i if i else 0
    if not R == G == B:
        h = math.atan2(math.sqrt(3) * (G - B), 2 * R - G - B) / math.pi / 2
        if h < 0:
            h += 1.0
        if h > 1:
            h -= 1.0
    else:
        h = 0
    return h * scale, s * scale, i * scale


def RGB2HSL(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from RGB to HSL.

    The input RGB values need to be in the nominal range [0.0, 1.0] and
    the output HSL values are in the nominal range [0.0, scale].

    Args:
        R (float): The red value of the color.
        G (float): The green value of the color.
        B (float): The blue value of the color.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The HSL values.
    """
    h, l, s = colorsys.rgb_to_hls(R, G, B)
    return tuple(v * scale for v in (h, s, l))


def RGB2HSV(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Convert from RGB to HSV.

    The input RGB values need to be in the nominal range [0.0, 1.0] and
    the output HSV values are in the nominal range [0.0, scale].

    Args:
        R (float): The red value of the color.
        G (float): The green value of the color.
        B (float): The blue value of the color.
        scale (float): The scale factor to apply to the output values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: The HSV values.
    """
    return tuple(v * scale for v in colorsys.rgb_to_hsv(R, G, B))


def LinearRGB2ICtCp(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    oetf: None | Callable = None,
) -> tuple[float, float, float]:
    """Rec. 2020 linear RGB to non-linear ICtCp.

    http://www.dolby.com/us/en/technologies/dolby-vision/ICtCp-white-paper.pdf
    """
    if oetf is None:

        def oetf(FD: float) -> float:  # noqa: N803
            """Default OETF for Rec. 2020.

            Args:
                FD (float): The value to apply the OETF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(FD, 1.0 / -2084)

    lms = LinearRGB2LMS_matrix * (R, G, B)
    l_, m_, s_ = (oetf(FD) for FD in lms)
    i, ct, cp = L_M_S_2ICtCp_matrix * (l_, m_, s_)
    return i, ct, cp


def ICtCp2LinearRGB(  # noqa: N802
    I: float,  # noqa: N803
    Ct: float,  # noqa: N803
    Cp: float,  # noqa: N803
    eotf: None | Callable = None,
) -> tuple[float, float, float]:
    """Non-linear ICtCp to Rec. 2020 linear RGB.

    http://www.dolby.com/us/en/technologies/dolby-vision/ICtCp-white-paper.pdf

    Args:
        I (float): The I value of the color.
        Ct (float): The Ct value of the color.
        Cp (float): The Cp value of the color.
        eotf (function): The electro-optical transfer function to use.
            Defaults to the Rec. 2020 EOTF.
            This function should take a single argument and return a float.
            The default function is the Rec. 2020 OETF.
            See the `special_pow` function for more details.

    Returns:
        tuple[float, float, float]: The RGB values.
    """
    if eotf is None:

        def eotf(v: float) -> float:
            """Default EOTF for Rec. 2020.

            Args:
                v (float): The value to apply the EOTF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(v, -2084)

    l_m_s_ = ICtCp2L_M_S__matrix * (I, Ct, Cp)
    l, m, s = (eotf(v) for v in l_m_s_)
    return LMS2LinearRGB_matrix * (l, m, s)


def RGB2ICtCp(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    rgb_space: None | str | list | tuple = "Rec. 2020",
    eotf: None | Callable = None,
    clamp: bool = False,
    oetf: None | Callable = None,
) -> tuple[float, float, float]:
    """R'G'B' to ICtCp.

    Args:
        R (float): The R' value of the color.
        G (float): The G' value of the color.
        B (float): The B' value of the color.
        rgb_space (str): The RGB space to use for conversion. Defaults to
            "Rec. 2020".
        eotf (None | callable): The electro-optical transfer function to use.
            Defaults to the Rec. 2020 EOTF.
            This function should take a single argument and return a float.
            The default function is the inverse of the Rec. 2020 EOTF.
            See the `special_pow` function for more details.
        clamp (bool): If True, clamp the output values to [0, 1].
            Defaults to False.
        oetf (None | callable): The opto-electrical transfer function to use.
            Defaults to the Rec. 2020 OETF.
            This function should take a single argument and return a float.
            The default function is the Rec. 2020 OETF.
            See the `special_pow` function for more details.

    Returns:
        tuple[float, float, float]: The ICtCp values.
    """
    if eotf is None:

        def eotf(v: float) -> float:
            """Default EOTF for Rec. 2020.

            Args:
                v (float): The value to apply the EOTF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(v, -2084)

    if oetf is None:

        def oetf(E: float) -> float:  # noqa: N803
            """Default OETF for Rec. 2020.

            Args:
                E (float): The value to apply the OETF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(E, 1.0 / -2084)

    return XYZ2ICtCp(*RGB2XYZ(R, G, B, rgb_space, eotf=eotf), clamp, oetf)


def ICtCp2RGB(  # noqa: N802
    I: float,  # noqa: N803
    Ct: float,  # noqa: N803
    Cp: float,  # noqa: N803
    rgb_space: None | str | list | tuple = "Rec. 2020",
    eotf: None | Callable = None,
    clamp: bool = False,
    oetf: None | Callable = None,
) -> list[float]:
    """ICtCp to R'G'B'.

    Args:
        I (float): The I value of the color.
        Ct (float): The Ct value of the color.
        Cp (float): The Cp value of the color.
        rgb_space (str): The RGB space to use for conversion. Defaults to
            "Rec. 2020".
        eotf (None | callable): The electro-optical transfer function to use.
            Defaults to the Rec. 2020 EOTF.
            This function should take a single argument and return a float.
            The default function is the inverse of the Rec. 2020 EOTF.
            See the `special_pow` function for more details.
        clamp (bool): If True, clamp the output values to [0, 1].
            Defaults to False.
        oetf (None | callable): The opto-electrical transfer function to use.
            Defaults to the Rec. 2020 OETF.
            This function should take a single argument and return a float.
            The default function is the Rec. 2020 OETF.
            See the `special_pow` function for more details.

    Returns:
        tuple: The RGB values.
    """
    if eotf is None:

        def eotf(v: float) -> float:
            """Default EOTF for Rec. 2020.

            Args:
                v (float): The value to apply the EOTF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(v, -2084)

    if oetf is None:

        def oetf(E: float) -> float:  # noqa: N803
            """Default OETF for Rec. 2020.

            Args:
                E (float): The value to apply the OETF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(E, 1.0 / -2084)

    return XYZ2RGB(*ICtCp2XYZ(I, Ct, Cp, eotf), rgb_space, clamp=clamp, oetf=oetf)


def XYZ2ICtCp(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    clamp: bool = False,
    oetf: None | Callable = None,
) -> tuple[float, float, float]:
    """XYZ to ICtCp.

    Args:
        X (float): The X value of the color.
        Y (float): The Y value of the color.
        Z (float): The Z value of the color.
        clamp (bool): If True, clamp the output values to [0, 1].
            Defaults to False.
        oetf (function): The opto-electrical transfer function to use.
            Defaults to the Rec. 2020 OETF.
            This function should take a single argument and return a float.
            The default function is the Rec. 2020 OETF.
            See the `special_pow` function for more details.

    Returns:
        tuple: The ICtCp values.
    """
    if oetf is None:

        def oetf(E: float) -> float:  # noqa: N803
            """Default OETF for Rec. 2020.

            Args:
                E (float): The value to apply the OETF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(E, 1.0 / -2084)

    return LinearRGB2ICtCp(
        *XYZ2RGB(X, Y, Z, "Rec. 2020", clamp=clamp, oetf=lambda v: v), oetf
    )


def ICtCp2XYZ(I: float, Ct: float, Cp: float, eotf: None | Callable = None) -> tuple:  # noqa: N802, N803
    """ICtCp to XYZ.

    Args:
        I (float): The I value of the color.
        Ct (float): The Ct value of the color.
        Cp (float): The Cp value of the color.
        eotf (function): The electro-optical transfer function to use.
            Defaults to the Rec. 2020 EOTF.
            This function should take a single argument and return a float.
            The default function is the inverse of the Rec. 2020 EOTF.
            See the `special_pow` function for more details.

    Returns:
        tuple: The XYZ values.
    """
    if eotf is None:

        def eotf(v: float) -> float:
            """Default EOTF for Rec. 2020.

            Args:
                v (float): The value to apply the EOTF to.

            Returns:
                float: The transformed value.
            """
            return special_pow(v, -2084)

    return RGB2XYZ(*ICtCp2LinearRGB(I, Ct, Cp, eotf), "Rec. 2020", eotf=lambda v: v)


def RGB2Lab(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    rgb_space: None | str | list | tuple = None,
    whitepoint: None | float | str | list | tuple = None,
    noadapt: bool = False,
    cat: str = "Bradford",
) -> tuple[float, float, float]:
    """Convert from RGB to Lab.

    Args:
        R (float): The R' value of the color.
        G (float): The G' value of the color.
        B (float): The B' value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or
            int). The gamma should be a float. The RGB primaries red,
            green, blue should be lists or tuples of xyY coordinates
            (only x and y will be used, so Y can be zero or None).
        whitepoint (None | str | tuple): The whitepoint to use for conversion.
            If None, the whitepoint of the RGB space will be used.
            If a string is given, it must be a valid whitepoint name.
            If a tuple is given, it must be in the format (X, Y, Z).
            The whitepoint can also be a color temperature in degrees K
            (float or int).
        noadapt (bool): If True, no chromatic adaptation will be applied.
            Defaults to False.
        cat (str): The chromatic adaptation transform to use. Defaults to
            "Bradford". Other options include "VonKries" and "CAT02".
            See the `adapt` function for more details.

    Returns:
        tuple[float, float, float]: The Lab values.
    """
    x, y, z = RGB2XYZ(R, G, B, rgb_space, scale=100)
    if not noadapt:
        rgb_space = get_rgb_space(rgb_space)
        x, y, z = adapt(x, y, z, rgb_space[1], whitepoint, cat)
    return XYZ2Lab(x, y, z, whitepoint=whitepoint)


def RGB2XYZ(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    rgb_space: None | str | list | tuple = None,
    scale: float = 1.0,
    eotf: None | Callable = None,
) -> tuple[float, float, float]:
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

    Args:
        R (float): The R' value of the color.
        G (float): The G' value of the color.
        B (float): The B' value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or
            int). The gamma should be a float. The RGB primaries red,
            green, blue should be lists or tuples of xyY coordinates
            (only x and y will be used, so Y can be zero or None).
        scale (float): The scale factor for the output values. Defaults to 1.0.
        eotf (function): A function to apply to the RGB values before conversion.
            If not set, the RGB values will be treated as linear RGB values.
            This function should take a single argument and return a float.
            The default function is the inverse of the Rec. 2020 EOTF.
            See the `special_pow` function for more details.

    Returns:
        tuple[float, float, float]: The XYZ values.

    """
    trc, _, _, _, _, matrix = get_rgb_space(rgb_space)
    rgb = [R, G, B]
    is_trc = isinstance(trc, (list, tuple))
    for i, v in enumerate(rgb):
        gamma = trc[i] if is_trc else trc
        if eotf:
            rgb[i] = eotf(v)
        elif isinstance(gamma, (list, tuple)):
            rgb[i] = interp(
                v, [n / float(len(gamma) - 1) for n in range(len(gamma))], gamma
            )
        else:
            rgb[i] = special_pow(v, gamma)
    xyz = matrix * rgb
    return tuple(v * scale for v in xyz)


def RGB2xyY(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    rgb_space: None | str | list | tuple = None,
    scale: float = 1.0,
    eotf: None | Callable = None,
) -> tuple[float, float, float]:
    """Convert RGB to xyY.

    Args:
        R (float): The R' value of the color.
        G (float): The G' value of the color.
        B (float): The B' value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or
            int). The gamma should be a float. The RGB primaries red,
            green, blue should be lists or tuples of xyY coordinates
            (only x and y will be used, so Y can be zero or None).
        scale (float): The scale factor for the output values. Defaults to 1.0.
        eotf (function): A function to apply to the RGB values before conversion.

    Returns:
        tuple[float, float, float]: The xyY values.
    """
    return XYZ2xyY(
        *RGB2XYZ(R, G, B, rgb_space, scale, eotf),
        whitepoint=RGB2XYZ(1, 1, 1, rgb_space, scale, eotf),
    )


def RGB2YCbCr(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    rgb_space: None | str | list | tuple = "NTSC 1953",
    bits: int = 8,
    fullrange: bool = False,
) -> tuple[float, float, float]:
    """R'G'B' to Y'CbCr quantized to n bits.

    Args:
        R (float): The R' value of the color.
        G (float): The G' value of the color.
        B (float): The B' value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or
            int). The gamma should be a float. The RGB primaries red,
            green, blue should be lists or tuples of xyY coordinates
            (only x and y will be used, so Y can be zero or None).
        bits (int): The number of bits to quantize to. Defaults to 8.
        fullrange (bool): Whether to use full range or limited range. Defaults to False.

    Returns:
        tuple: The Y'CbCr values.
    """
    return YPbPr2YCbCr(*RGB2YPbPr(R, G, B, rgb_space), bits=bits, fullrange=fullrange)


def RGB2YPbPr(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    rgb_space: None | str | list | tuple = "NTSC 1953",
) -> tuple[float, float, float]:
    """R'G'B' to Y'PbPr.

    Args:
        R (float): The R' value of the color.
        G (float): The G' value of the color.
        B (float): The B' value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).

    Returns:
        tuple: The Y'PbPr values.
    """
    return RGB2YPbPr_matrix(rgb_space) * (R, G, B)


def RGB2YPbPr_matrix(rgb_space: None | str | list | tuple = "NTSC 1953") -> Matrix3x3:  # noqa: N802
    """Get the RGB to Y'PbPr matrix for the given RGB space.

    Args:
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).

    Returns:
        Matrix3x3: The RGB to Y'PbPr matrix.
    """
    matrix = get_rgb_space(rgb_space)[-1]
    ndigits = 3 if matrix == get_rgb_space("NTSC 1953")[-1] else 4
    kr = round((matrix * (1, 0, 0))[1], ndigits)
    kb = round((matrix * (0, 0, 1))[1], ndigits)
    kg = 1.0 - kr - kb
    pb_scale = (1 - kb) / 0.5
    pr_scale = (1 - kr) / 0.5
    return Matrix3x3(
        [
            [kr, kg, kb],
            [-kr / pb_scale, -kg / pb_scale, 0.5],
            [0.5, -kg / pr_scale, -kb / pr_scale],
        ]
    )


def YCbCr2YPbPr(  # noqa: N802
    Y: float,  # noqa: N803
    Cb: float,  # noqa: N803
    Cr: float,  # noqa: N803
    bits: int = 8,
    fullrange: bool = False,
) -> tuple[float, float, float]:
    """Y'CbCr to Y'PbPr.

    Args:
        Y (float): The Y value of the color.
        Cb (float): The Cb value of the color.
        Cr (float): The Cr value of the color.
        bits (int, optional): The number of bits to quantize to. Defaults to 8.
        fullrange (bool, optional): Whether to use full range or limited range.
            Defaults to False.

    Returns:
        tuple[float, float, float]: The Y'PbPr values.
    """
    bitlevels = 2**bits
    if not fullrange:
        yblack = 16
        ywhite = 235
        cmax = 240
    else:
        yblack = 0
        ywhite = 255
        cmax = 255
    yscale = (ywhite - yblack) / 256.0 * bitlevels
    Y -= yblack / 256.0 * bitlevels  # noqa: N806
    Y /= yscale  # noqa: N806
    cneutral = 128 / 256.0 * bitlevels
    cscale = (cmax - yblack) / 256.0 * bitlevels
    pb = Cb - cneutral
    pb /= cscale
    pr = Cr - cneutral
    pr /= cscale
    return Y, pb, pr


def YCbCr2RGB(  # noqa: N802
    Y: float,  # noqa: N803
    Cb: float,  # noqa: N803
    Cr: float,  # noqa: N803
    rgb_space: None | str | list | tuple = "NTSC 1953",
    bits: int = 8,
    fullrange: bool = False,
    scale: float = 1.0,
    round_: bool = False,
    clamp: bool = True,
) -> list[float]:
    """Y'CbCr to R'G'B'.

    Args:
        Y (float): The Y value of the color.
        Cb (float): The Cb value of the color.
        Cr (float): The Cr value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).
        bits (int): The number of bits to quantize to. Defaults to 8.
        fullrange (bool): Whether to use full range or limited range. Defaults to False.
        scale (float): The scale factor to apply to the output values.
        round_ (int | bool): The number of decimal places to round to.
            If False, no rounding is applied. Defaults to False.
        clamp (bool): Whether to clamp the output values to [0.0, 1.0].
            Defaults to True.

    Returns:
        list[float]: The R'G'B' values.
    """
    return YPbPr2RGB(
        *YCbCr2YPbPr(Y, Cb, Cr, bits, fullrange), rgb_space, scale, round_, clamp
    )


def YPbPr2RGB(  # noqa: N802
    Y: float,  # noqa: N803
    Pb: float,  # noqa: N803
    Pr: float,  # noqa: N803
    rgb_space: None | str | list | tuple = "NTSC 1953",
    scale: float = 1.0,
    round_: bool = False,
    clamp: bool = True,
) -> list[float]:
    """Y'PbPr to R'G'B'.

    Args:
        Y (float): The Y value of the color.
        Pb (float): The Pb value of the color.
        Pr (float): The Pr value of the color.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).
        scale (float): The scale factor to apply to the output values.
        round_ (int | bool): The number of decimal places to round to.
            If False, no rounding is applied. Defaults to False.
        clamp (bool): Whether to clamp the output values to [0.0, 1.0].
            Defaults to True.

    Returns:
        list[float]: The R'G'B' values.
    """
    rgb = RGB2YPbPr_matrix(rgb_space).inverted() * (Y, Pb, Pr)
    for i in range(3):
        if clamp:
            rgb[i] = min(1.0, max(0.0, rgb[i]))
        rgb[i] *= scale
        if round_ is not False:
            rgb[i] = round(rgb[i], round_)
    return rgb


def YPbPr2YCbCr(  # noqa: N802
    Y: float,  # noqa: N803
    Pb: float,  # noqa: N803
    Pr: float,  # noqa: N803
    bits: int = 8,
    fullrange: bool = False,
) -> tuple[float, float, float]:
    """Y'PbPr to Y'CbCr quantized to n bits.

    Args:
        Y (float): The Y value of the color.
        Pb (float): The Pb value of the color.
        Pr (float): The Pr value of the color.
        bits (int): The number of bits to quantize to. Defaults to 8.
        fullrange (bool): Whether to use full range or limited range. Defaults to False.

    Returns:
        tuple[float, float, float]: The Y'CbCr values.
    """
    bitlevels = 2**bits
    if not fullrange:
        yblack = 16
        ywhite = 235
        cmax = 240
    else:
        yblack = 0
        ywhite = 255
        cmax = 255
    yscale = (ywhite - yblack) / 256.0 * bitlevels
    Y = yblack / 256.0 * bitlevels + yscale * Y  # noqa: N806
    cneutral = 128 / 256.0 * bitlevels
    cscale = (cmax - yblack) / 256.0 * bitlevels
    cb = cneutral + cscale * Pb  # noqa: N806
    cr = cneutral + cscale * Pr  # noqa: N806
    # In fullrange mode, Cb and Cr can reach 255.5, so we need to clamp
    # Follow ITU-T Rec. T.871 (JPEG)
    return (min(max(round(v), 0), bitlevels - 1) for v in (Y, cb, cr))


def RGBsaturation(  # noqa: N802
    R: float,  # noqa: N803
    G: float,  # noqa: N803
    B: float,  # noqa: N803
    saturation: float,
    rgb_space: None | str | list | tuple = None,
) -> tuple[float, float, float]:
    """(De)saturate a RGB color in CIE xy and return the RGB and xyY values.

    Args:
        R (float): The red value of the color.
        G (float): The green value of the color.
        B (float): The blue value of the color.
        saturation (float): The saturation factor.
            0.0 = grayscale, 1.0 = original color, >1.0 = oversaturated.
            <0.0 = undersaturated.
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).

    Returns:
        tuple: The new RGB values after saturation adjustment.
        tuple: The new xyY values after saturation adjustment.
    """
    whitepoint = RGB2XYZ(1, 1, 1, rgb_space=rgb_space)
    X, Y, Z = RGB2XYZ(R, G, B, rgb_space=rgb_space)  # noqa: N806
    XYZ, xyY = XYZsaturation(X, Y, Z, saturation, whitepoint)  # noqa: N806
    return XYZ2RGB(*XYZ, rgb_space=rgb_space), xyY


def XYZsaturation(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    saturation: float,
    whitepoint: None | float | str | list | tuple = None,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """(De)saturate a XYZ color in CIE xy and return the RGB and xyY values.

    Args:
        X (float): The X value of the color.
        Y (float): The Y value of the color.
        Z (float): The Z value of the color.
        saturation (float): The saturation factor.
            0.0 = grayscale, 1.0 = original color, >1.0 = oversaturated.
            <0.0 = undersaturated.
        whitepoint (None | float | str | list | tuple): The white point
            to use for conversion. Defaults to D65 if not set.

    Returns:
        tuple[tuple[float, float, float], tuple[float, float, float]]: The new
            XYZ values after saturation adjustment.
    """
    wx, wy, wY = XYZ2xyY(*get_whitepoint(whitepoint))  # noqa: N806
    x, y, Y = XYZ2xyY(X, Y, Z)  # noqa: N806
    x, y, Y = xyYsaturation(x, y, Y, wx, wy, saturation)  # noqa: N806
    return xyY2XYZ(x, y, Y), (x, y, Y)


def xyYsaturation(  # noqa: N802
    x: float,
    y: float,
    Y: float,  # noqa: N803
    wx: float,
    wy: float,
    saturation: float,
) -> tuple[float, float, float]:
    """(De)saturate a color in CIE xy and return the RGB and xyY values.

    Args:
        x (float): The x coordinate of the color.
        y (float): The y coordinate of the color.
        Y (float): The Y value of the color.
        wx (float): The x coordinate of the white point.
        wy (float): The y coordinate of the white point.
        saturation (float): The saturation factor.
            0.0 = grayscale, 1.0 = original color, >1.0 = oversaturated.
            <0.0 = undersaturated.

    Returns:
        tuple[float, float, float]: The new x, y, and Y values after saturation
            adjustment.
    """
    return wx + (x - wx) * saturation, wy + (y - wy) * saturation, Y


def convert_range(
    v: float, oldmin: float = 0, oldmax: float = 1, newmin: float = 0, newmax: float = 1
) -> float:
    """Convert a value from one range to another.

    Args:
        v (float): The value to convert.
        oldmin (float): The minimum of the old range.
        oldmax (float): The maximum of the old range.
        newmin (float): The minimum of the new range.
        newmax (float): The maximum of the new range.

    Returns:
        float: The converted value in the new range.
    """
    oldrange = float(oldmax - oldmin)
    newrange = newmax - newmin
    return (((v - oldmin) * newrange) / oldrange) + newmin


def rgb_to_xyz_matrix(
    rx: float,
    ry: float,
    gx: float,
    gy: float,
    bx: float,
    by: float,
    whitepoint: None | float | str | list | tuple = None,
    scale: float = 1.0,
) -> Matrix3x3:
    """Create and return an RGB to XYZ matrix.

    Args:
        rx (float): The x coordinate of the red primary.
        ry (float): The y coordinate of the red primary.
        gx (float): The x coordinate of the green primary.
        gy (float): The y coordinate of the green primary.
        bx (float): The x coordinate of the blue primary.
        by (float): The y coordinate of the blue primary.
        whitepoint (None | float | str | list | tuple): The white point
            to use for conversion. If None, the default white point will be
            used.
        scale (float): The scale factor for the XYZ values. Defaults to 1.0.

    Returns:
        Matrix3x3: The RGB to XYZ matrix.
    """
    whitepoint = get_whitepoint(whitepoint, scale)
    Xr, Yr, Zr = xyY2XYZ(rx, ry, scale)  # noqa: N806
    Xg, Yg, Zg = xyY2XYZ(gx, gy, scale)  # noqa: N806
    Xb, Yb, Zb = xyY2XYZ(bx, by, scale)  # noqa: N806
    Sr, Sg, Sb = (  # noqa: N806
        Matrix3x3(((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))).inverted() * whitepoint
    )
    return Matrix3x3(
        (
            (Sr * Xr, Sg * Xg, Sb * Xb),
            (Sr * Yr, Sg * Yg, Sb * Yb),
            (Sr * Zr, Sg * Zg, Sb * Zb),
        )
    )


def find_primaries_wp_xy_rgb_space_name(
    xy: list | tuple, rgb_space_names: None | list | tuple = None, digits: int = 4
) -> None | str:
    """Find the RGB space name matching given primaries and whitepoint xy.

    Args:
        xy (list | tuple): The xy coordinates of the primaries and whitepoint.
        rgb_space_names (None | list | tuple): A list of RGB space names to
            search in. If None, all RGB spaces will be searched.
            Defaults to None.
        digits (int): The number of digits to round to. Defaults to 4.

    Returns:
        None | str: The name of the RGB space matching the given xy
            coordinates, or None if no match is found.
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
    return None


@cache
def get_rgb_space(
    rgb_space: None | str | list | tuple = None, scale: float = 1.0
) -> tuple[float,]:
    """Return gamma, whitepoint, primaries and RGB -> XYZ matrix.

    Args:
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).
        scale (float): Scale factor for the XYZ values. Defaults to 1.0.

    Returns:
        tuple: A tuple containing the gamma, whitepoint, red, green, blue
            primaries in xyY format, and the RGB to XYZ matrix.
    """
    if not rgb_space:
        rgb_space = "sRGB"
    if isinstance(rgb_space, str):
        rgb_space = rgb_spaces[rgb_space]
    gamma = rgb_space[0] or rgb_spaces["sRGB"][0]
    whitepoint = get_whitepoint(rgb_space[1] or rgb_spaces["sRGB"][1], scale)
    rx, ry, rY = rxyY = rgb_space[2] or rgb_spaces["sRGB"][2]  # noqa: N806
    gx, gy, gY = gxyY = rgb_space[3] or rgb_spaces["sRGB"][3]  # noqa: N806
    bx, by, bY = bxyY = rgb_space[4] or rgb_spaces["sRGB"][4]  # noqa: N806
    matrix = rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, whitepoint, scale)
    return gamma, whitepoint, rxyY, gxyY, bxyY, matrix


def get_rgb_space_primaries_wp_xy(
    rgb_space: None | str | list | tuple = None, digits: int = 4
) -> list:
    """Return primaries and whitepoint xy for a given RGB space, rounded to n digits.

    Args:
        rgb_space (None | str | list | tuple): The RGB space
            to use for conversion. Defaults to sRGB if not set.
            If a string is given, it must be a valid RGB space name.
            If a list or tuple is given, it must be in the format
            (gamma, whitepoint, red, green, blue).
            The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green,
            blue should be lists or tuples of xyY coordinates (only x and
            y will be used, so Y can be zero or None).
        digits (int): The number of digits to round to. Defaults to 4.

    Returns:
        list: A list of xy coordinates for the RGB primaries and whitepoint,
            rounded to the specified number of digits.
    """
    rgb_space = get_rgb_space(rgb_space)
    xy = []
    for i in range(3):
        xy.extend(rgb_space[2:][i][:2])
    xy.extend(XYZ2xyY(*get_whitepoint(rgb_space[1]))[:2])
    if digits:
        xy = [round(v, digits) for v in xy]
    return xy


@cache
def get_standard_illuminant(
    illuminant_name: str = "D50",
    priority: tuple = (
        "ISO 11664-2:2007",
        "ICC",
        "ASTM E308-01",
        "Wyszecki & Stiles",
        None,
    ),
    scale: float = 1.0,
) -> tuple[float, float, float]:
    """Return a standard illuminant as XYZ coordinates.

    Args:
        illuminant_name (str): The name of the standard illuminant to return.
            Defaults to "D50".
        priority (tuple): A tuple of standard names to search for the
            illuminant. The first one found will be returned.
            Defaults to ("ISO 11664-2:2007", "ICC", "ASTM E308-01",
            "Wyszecki & Stiles", None).
        scale (float): Scale factor for the XYZ values. Defaults to 1.0.

    Raises:
        ValueError: If the illuminant name is not recognized or if no
            illuminant is found in the given priority list.

    Returns:
        tuple[float, float, float]: A tuple of XYZ coordinates scaled by the
            given scale factor.
    """
    illuminant = None
    for standard_name in priority:
        if standard_name not in standard_illuminants:
            raise ValueError(f'Unrecognized standard "{standard_name}"')
        illuminant = standard_illuminants.get(standard_name).get(
            illuminant_name.upper(), None
        )
        if illuminant:
            return illuminant["X"] * scale, 1.0 * scale, illuminant["Z"] * scale
    raise ValueError(f'Unrecognized illuminant "{illuminant_name}"')


@overload
def get_whitepoint(
    whitepoint: list,
    scale: float = 1.0,
    planckian: bool = False,
) -> list[float]: ...


@overload
def get_whitepoint(
    whitepoint: None | float | str | tuple,
    scale: float = 1.0,
    planckian: bool = False,
) -> tuple[float, float, float]: ...


@cache
def get_whitepoint(
    whitepoint: None | float | str | list | tuple = None,
    scale: float = 1.0,
    planckian: bool = False,
) -> tuple[float, float, float]:
    """Return a whitepoint as XYZ coordinates.

    Args:
        whitepoint: A string (e.g. "D50"), a tuple of XYZ coordinates, or a
            color temperature in degrees K (float or int). Defaults to D50 if
            not set.
        scale: Scale factor for the XYZ values. Defaults to 1.0.
        planckian: If True, interpret the whitepoint as a Planckian color
            temperature. Defaults to False.

    Returns:
        tuple: A tuple of XYZ coordinates scaled by the given scale factor.
    """
    if isinstance(whitepoint, (list, tuple)):
        return whitepoint
    if not whitepoint:
        whitepoint = "D50"
    if isinstance(whitepoint, str):
        whitepoint = get_standard_illuminant(whitepoint)
    elif isinstance(whitepoint, (float, int)):
        cct = whitepoint
        if planckian:
            whitepoint = planckianCT2XYZ(cct)
            if not whitepoint:
                raise ValueError(
                    f"Planckian color temperature {cct} out of range (1667, 25000)"
                )
        else:
            whitepoint = CIEDCCT2XYZ(cct)
            if not whitepoint:
                raise ValueError(
                    f"Daylight color temperature {cct} out of range (2500, 25000)"
                )
    if scale > 1.0 and whitepoint[1] == 100:
        scale = 1.0
    return tuple(v * scale for v in whitepoint)


def make_monotonically_increasing(
    iterable: tuple | list | dict,
    passes: int = 0,
    window: None | int = None,
) -> list | dict:
    """Make values in iterable strictly monotonically increasing by linear interpolation.

    If iterable is a dict, keep the keys of the original.

    If passes is non-zero, apply moving average smoothing to the values
    before making them monotonically increasing.

    Args:
        iterable (tuple | list | dict): The input iterable or sequence.
        passes (int): The number of smoothing passes to apply.
            Defaults to 0 (no smoothing).
        window (int): The window size for smoothing. Defaults to None.
            If None, the window size is set to 3.
            If passes is 0, this argument is ignored.

    Returns:
        list: A list of tuples containing the original keys and the
            monotonically increasing values.
    """  # noqa: E501
    if isinstance(iterable, dict):
        keys = list(iterable.keys())
        values = list(iterable.values())
    else:
        values = list(iterable) if hasattr(iterable, "next") else iterable
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


def matmul(
    XYZ: tuple[float, float, float],  # noqa: N803
    m1: Matrix3x3,
    m2: Matrix3x3,
) -> tuple[float, float, float]:
    """Matrix multiplication of two matrices.

    Args:
        XYZ (tuple[float, float, float]): A tuple of XYZ coordinates (X, Y, Z).
        m1 (Matrix3x3): The first matrix.
        m2 (Matrix3x3): The second matrix.

    Returns:
        tuple[float, float, float]: A tuple of the resulting coordinates
            (X', Y', Z').
    """
    return m1 * (m2 * XYZ)


def planckianCT2XYZ(T: float, scale: float = 1.0) -> None | tuple[float, float, float]:  # noqa: N802, N803
    """Convert from planckian temperature to XYZ.

    T = temperature in Kelvin.

    Args:
        T (float): Temperature in Kelvin.
        scale (float): Scale factor for the XYZ values.
            Defaults to 1.0.

    Returns:
        None | tuple[float, float, float]: A tuple of XYZ coordinates (X, Y, Z)
            if xyY is not None, None otherwise.
    """
    xyY = planckianCT2xyY(T, scale)  # noqa: N806
    return xyY2XYZ(*xyY) if xyY else None


def planckianCT2xyY(T: float, scale: float = 1.0) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from planckian temperature to xyY.

    T = temperature in Kelvin.

    Formula from http://en.wikipedia.org/wiki/Planckian_locus

    Args:
        T (float): Temperature in Kelvin.
        scale (float, optional): Scale factor for the xyY values.
            Defaults to 1.0.

    Returns:
        tuple[float, float, float]: A tuple of xyY coordinates (x, y, Y).
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


def xyY2CCT(x: float, y: float, Y: float = 1.0) -> None | float:  # noqa: N802, N803
    """Convert from xyY to correlated color temperature.

    Args:
        x (float): x coordinate in xyY color space.
        y (float): y coordinate in xyY color space.
        Y (float, optional): Y coordinate in xyY color space.

    Returns:
        None | float: Correlated color temperature in Kelvin.
    """
    return XYZ2CCT(*xyY2XYZ(x, y, Y))


def xyY2Lab(  # noqa: N802
    x: float,
    y: float,
    Y: float = 1.0,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from xyY to Lab color space.

    Args:
        x (float): x coordinate in xyY color space.
        y (float): y coordinate in xyY color space.
        Y (float, optional): Y coordinate in xyY color space.
        whitepoint ( None | float | str | tuple | list): Whitepoint to
            use for conversion. Defaults to D50 if not set.

    Returns:
        tuple[float, float, float]: A tuple of Lab coordinates (L, a, b).
    """
    return XYZ2Lab(*xyY2XYZ(x, y, Y), whitepoint)


def xyY2Lu_v_(  # noqa: N802
    x: float,
    y: float,
    Y: float = 1.0,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from xyY to Lu'v' color space.

    Args:
        x (float): x coordinate in xyY color space.
        y (float): y coordinate in xyY color space.
        Y (float, optional): Y coordinate in xyY color space.
        whitepoint ( None | float | str | tuple | list): Whitepoint to
            use for conversion. Defaults to D50 if not set.

    Returns:
        tuple[float, float, float]: A tuple of Lu'v' coordinates (L, u', v').
    """
    return XYZ2Lu_v_(*xyY2XYZ(x, y, Y), whitepoint)


def xyY2RGB(  # noqa: N802
    x: float,  # noqa: N803
    y: float,  # noqa: N803
    Y: float,  # noqa: N803
    rgb_space: None | str | list | tuple = None,
    scale: float = 1.0,
    round_: bool = False,
    clamp: bool = True,
) -> tuple[float, float, float]:
    """Convert from xyY to RGB.

    Args:
        x (float): x coordinate in xyY color space.
        y (float): y coordinate in xyY color space.
        Y (float): Y coordinate in xyY color space.
        rgb_space (str | tuple): RGB color space to use for conversion.
        scale (float): Scale factor for the RGB values.
        round_ (bool): If True, round the RGB values to integers.
        clamp (bool): If True, clamp the RGB values to [0, 1].

    Returns:
        tuple: A tuple of RGB coordinates (R, G, B).
    """
    return XYZ2RGB(*xyY2XYZ(x, y, Y), rgb_space, scale, round_, clamp)


def xyY2XYZ(x: float, y: float, Y: float = 1.0) -> tuple[float, float, float]:  # noqa: N802, N803
    """Convert from xyY to XYZ.

    Based on formula from http://brucelindbloom.com/Eqn_xyY_to_XYZ.html

    Implementation Notes:
    1. Watch out for the case where y = 0. In that case, X = Y = Z = 0 is
       returned.
    2. The output XYZ values are in the nominal range [0.0, Y[xyY]].

    Args:
        x (float): x coordinate in xyY color space.
        y (float): y coordinate in xyY color space.
        Y (float, optional): Y coordinate in xyY color space. The default is 1.0.

    Returns:
        tuple[float, float, float]: A tuple of XYZ coordinates (X, Y, Z).
    """
    if y == 0:
        return 0, 0, 0
    return (float(x * Y) / y), Y, (float((1 - x - y) * Y) / y)


def LERP(a: float, b: float, c: float) -> float:  # noqa: N802
    """Linear interpolation macro.

    Is 'a' when c == 0.0 and 'b' when c == 1.0

    Args:
        a (float): Start value.
        b (float): End value.
        c (float): Interpolation factor (0.0 to 1.0).

    Returns:
        float: Interpolated value.
    """
    return (b - a) * c + a


def XYZ2CCT(X: float, Y: float, Z: float) -> None | float:  # noqa: N802, N803
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


    Args:
        X (float): X coordinate in XYZ color space.
        Y (float): Y coordinate in XYZ color space.
        Z (float): Z coordinate in XYZ color space.

    Returns:
        None | float: Correlated color temperature in Kelvin if successful,
            else None.
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
    return p  # noqa: RET504


def XYZ2DIN99(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99 values.
    """
    return Lab2DIN99(*XYZ2Lab(*(max(v, 0) for v in (X, Y, Z)), whitepoint))


def XYZ2DIN99b(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99b.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99b values.
    """
    return Lab2DIN99b(*XYZ2Lab(X, Y, Z, whitepoint))


def XYZ2DIN99o(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99o.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float]: DIN99o values.
    """
    return Lab2DIN99o(*XYZ2Lab(X, Y, Z, whitepoint))


def XYZ2DIN99bLCH(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99b LCH.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99b LCH values.
    """
    return Lab2DIN99bLCH(*XYZ2Lab(X, Y, Z, whitepoint))


def XYZ2DIN99oLCH(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99o LCH.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99o LCH values.
    """
    return Lab2DIN99oLCH(*XYZ2Lab(X, Y, Z, whitepoint))


def XYZ2DIN99c(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99c.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99c values.
    """
    return XYZ2DIN99cd(X, Y, Z, 0.1, 317.651, 0.0037, 0, 0.94, 23, 0.066, whitepoint)


def XYZ2DIN99cd(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    x: float,
    l1: float,
    l2: float,
    deg: float,
    f1: float,
    c1: float,
    c2: float,
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99cd.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        x (float): Chromatic adaptation factor.
        l1 (float): L1 parameter.
        l2 (float): L2 parameter.
        deg (float): Deg parameter.
        f1 (float): F1 parameter.
        c1 (float): C1 parameter.
        c2 (float): C2 parameter.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float]: DIN99cd values.
    """
    l99, c99, h99 = XYZ2DIN99cdLCH(X, Y, Z, x, l1, l2, deg, f1, c1, c2, whitepoint)
    a99, b99 = DIN99familyCH2DIN99ab(c99, h99)
    return l99, a99, b99


def XYZ2DIN99cdLCH(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    x: float,
    l1: float,
    l2: float,
    deg: float,
    f1: float,
    c1: float,
    c2: float,
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99cd LCH.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        x (float): Chromatic adaptation factor.
        l1 (float): L1 parameter.
        l2 (float): L2 parameter.
        deg (float): Deg parameter.
        f1 (float): F1 parameter.
        c1 (float): C1 parameter.
        c2 (float): C2 parameter.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99cd LCH values.
    """
    X, Y, Z = XYZ2DIN99cdXYZ(X, Y, Z, x)  # noqa: N806
    whitepoint99d = XYZ2DIN99cdXYZ(*get_whitepoint(whitepoint, 100), x=x)
    l, a, b = XYZ2Lab(X, Y, Z, whitepoint99d)
    return Lab2DIN99familyLCH(l, a, b, l1, l2, deg, f1, c1, c2)


def XYZ2DIN99cdXYZ(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    x: float,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99cd.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        x (float): Chromatic adaptation factor.

    Returns:
        tuple[float]: DIN99cd values.
    """
    X = (1 + x) * X - x * Z  # noqa: N806
    return X, Y, Z


def XYZ2DIN99d(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to DIN99d.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: DIN99d values.
    """
    return XYZ2DIN99cd(X, Y, Z, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint)


def XYZ2DIN99dLCH(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float]:
    """Convert from XYZ to DIN99d LCH.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float]: DIN99d LCH values.
    """
    return XYZ2DIN99cdLCH(
        X, Y, Z, 0.12, 325.221, 0.0036, 50, 1.14, 22.5, 0.06, whitepoint
    )


def XYZ2IPT(X: float, Y: float, Z: float) -> Matrix3x3:  # noqa: N802, N803
    """Convert from XYZ to IPT.

    The input Y value needs to be in the nominal range [0.0, 100.0] and
    other input values scaled accordingly.
    The output I value is in the nominal range [0.0, 100.0].

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.

    Returns:
        Matrix3x3: IPT values.
    """
    xyz2lms_matrix = get_cat_matrix("IPT")
    lms = xyz2lms_matrix * (X, Y, Z)
    for i, component in enumerate(lms):
        if component >= 0:
            lms[i] **= 0.43
        else:
            lms[i] = -((-component) ** 0.43)
    return LMS2IPT_matrix * lms


def IPT2XYZ(I: float, P: float, T: float) -> Matrix3x3:  # noqa: N802, N803
    """Convert from IPT to XYZ.

    Args:
        I (float): I value.
        P (float): P value.
        T (float): T value.

    Returns:
        Matrix3x3: XYZ values.
    """
    xyz2lms_matrix = get_cat_matrix("IPT")
    lms2xyz_matrix = xyz2lms_matrix.inverted()
    lms = IPT2LMS_matrix * (I, P, T)
    for i, component in enumerate(lms):
        if component >= 0:
            lms[i] **= 1 / 0.43
        else:
            lms[i] = -((-component) ** (1 / 0.43))
    return lms2xyz_matrix * lms


def XYZ2Lab(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
    scale: float = 100,
) -> tuple[float, float, float]:
    """Convert from XYZ to Lab.

    The input Y value needs to be in the nominal range [0.0, scale] and
    other input values scaled accordingly.
    The output L value is in the nominal range [0.0, 100.0].

    whitepoint can be string (e.g. "D50"), a tuple of XYZ coordinates or
    color temperature as float or int. Defaults to D50 if not set.

    Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_Lab.html

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.
        scale (float): Scale factor. Defaults to 100.

    Returns:
        tuple[float, float, float]: L, a, b values.
    """
    Xr, Yr, Zr = get_whitepoint(whitepoint, scale)  # noqa: N806

    xr = X / Xr
    yr = Y / Yr
    zr = Z / Zr
    fx = cbrt(xr) if xr > LSTAR_E else (LSTAR_K * xr + 16) / 116.0
    fy = cbrt(yr) if yr > LSTAR_E else (LSTAR_K * yr + 16) / 116.0
    fz = cbrt(zr) if zr > LSTAR_E else (LSTAR_K * zr + 16) / 116.0
    l = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)

    return l, a, b


@functools.cache
def _lpt_observer_name() -> str:
    """Return the CIE observer used for Lpt, caching the Argyll version lookup.

    ``get_argyll_version("dispwin")`` can spawn a subprocess; ``XYZ2Lpt`` /
    ``Lpt2XYZ`` call it on every invocation, which — applied per point in a
    gamut projection — froze the UI. The installed Argyll version can't change
    within a session, so the observer choice is resolved once and cached.

    Returns:
        str: ``"CIE2012_2"`` (Argyll < 3.4.0) or ``"CIE2015_2"``.
    """
    from DisplayCAL import argyll

    if argyll.get_argyll_version("dispwin") < [3, 4, 0]:
        return "CIE2012_2"
    return "CIE2015_2"


def XYZ2Lpt(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> Matrix3x3:
    """Convert from XYZ to Lpt.

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

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        Matrix3x3: Lpt values.
    """
    # Adapted from Argyll/icc/icc.c
    xyz2lms = get_cat_matrix(_lpt_observer_name())

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


def Lpt2XYZ(  # noqa: N802
    L: float,  # noqa: N803
    p: float,
    t: float,
    whitepoint: None | float | str | tuple | list = None,
    scale: float = 1.0,
) -> Matrix3x3:
    """Convert from Lpt to XYZ.

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

    Args:
        L (float): L* value.
        p (float): p value.
        t (float): t value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.
        scale (float): Scale factor for the XYZ values. Defaults to 1.0.

    Returns:
        Matrix3x3: XYZ values.
    """
    # Adapted from Argyll/icc/icc.c
    xyz2lms = get_cat_matrix(_lpt_observer_name())
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


def XYZ2Lu_v_(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to CIE Lu'v'.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint to
            use for conversion. Defaults to D50 if not set.

    Returns:
        tuple[float, float, float]: A tuple of Lu'v' coordinates (L, u', v').
    """
    if X + Y + Z == 0:
        # We can't check for X == Y == Z == 0 because they may actually add up
        # to 0, thus resulting in ZeroDivisionError later
        l, u_, v_ = XYZ2Lu_v_(*get_whitepoint(whitepoint))
        return 0.0, u_, v_

    Xr, Yr, Zr = get_whitepoint(whitepoint, 100)  # noqa: N806

    yr = Y / Yr

    l = 116.0 * cbrt(yr) - 16.0 if yr > LSTAR_E else LSTAR_K * yr

    u_ = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
    v_ = (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z)

    return l, u_, v_


def XYZ2Luv(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to Luv.

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint to use
            for conversion. Defaults to D50 if not set.

    Returns:
        tuple[float, float, float]: A tuple of Luv coordinates (L, u, v).
    """
    if X + Y + Z == 0:  # noqa: N806
        # We can't check for X == Y == Z == 0 because they may actually add up
        # to 0, thus resulting in ZeroDivisionError later
        l, u, v = XYZ2Luv(*get_whitepoint(whitepoint))
        return 0.0, u, v

    Xr, Yr, Zr = get_whitepoint(whitepoint, 100)  # noqa: N806

    yr = Y / Yr

    l = 116.0 * cbrt(yr) - 16.0 if yr > LSTAR_E else LSTAR_K * yr

    u_ = (4.0 * X) / (X + 15.0 * Y + 3.0 * Z)
    v_ = (9.0 * Y) / (X + 15.0 * Y + 3.0 * Z)

    u_r = (4.0 * Xr) / (Xr + 15.0 * Yr + 3.0 * Zr)
    v_r = (9.0 * Yr) / (Xr + 15.0 * Yr + 3.0 * Zr)

    u = 13.0 * l * (u_ - u_r)
    v = 13.0 * l * (v_ - v_r)

    return l, u, v


def XYZ2RGB(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    rgb_space: None | str | list | tuple = None,
    scale: float = 1.0,
    round_: bool = False,
    clamp: bool = True,
    oetf: None | Callable = None,
) -> list[float]:
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

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        rgb_space (None | str | list | tuple): RGB colorspace definition.
            Defaults to sRGB.
        scale (float): Scale factor for RGB output. Defaults to 1.0.
        round_ (int | bool): Number of decimal places to round the output to.
            If False, no rounding is applied. Defaults to False.
        clamp (bool): If True, clamps the RGB values to the range [0.0, 1.0].
            Defaults to True.
        oetf (None | callable): Optional opto-electronic transfer function
            to apply to the RGB values. If None, no OETF is applied.
            Defaults to None.

    Returns:
        list[float]: RGB values in the range [0.0, scale].
    """
    trc, _whitepoint, _rxyY, _gxyY, _bxyY, matrix = get_rgb_space(rgb_space)  # noqa: N806
    rgb = matrix.inverted() * [X, Y, Z]
    is_trc = isinstance(trc, (list, tuple))
    for i, v in enumerate(rgb):
        gamma = trc[i] if is_trc else trc
        if clamp:
            v = min(1.0, max(0.0, v))
        if oetf:
            rgb[i] = oetf(v)
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
            rgb[i] = ginterp(v)
        else:
            rgb[i] = special_pow(v, 1.0 / gamma)
        rgb[i] *= scale
        if round_ is not False:
            rgb[i] = round(rgb[i], round_)
    return rgb


XYZ2RGB.interp = {}


def XYZ2xyY(  # noqa: N802
    X: float,  # noqa: N803
    Y: float,  # noqa: N803
    Z: float,  # noqa: N803
    whitepoint: None | float | str | tuple | list = None,
) -> tuple[float, float, float]:
    """Convert from XYZ to xyY.

    Based on formula from http://brucelindbloom.com/Eqn_XYZ_to_xyY.html

    Implementation Notes:
    1. Watch out for black, where X = Y = Z = 0. In that case, x and y are set
       to the chromaticity coordinates of the reference whitepoint.
    2. The output Y value is in the nominal range [0.0, Y[XYZ]].

    Args:
        X (float): X value.
        Y (float): Y value.
        Z (float): Z value.
        whitepoint (None | float | str | tuple | list): Whitepoint.
            Defaults to D50.

    Returns:
        tuple[float, float, float]: x, y, Y values.
    """
    if X + Y + Z == 0:
        # We can't check for X == Y == Z == 0 because they may actually add up
        # to 0, thus resulting in ZeroDivisionError later
        x, y, Y = XYZ2xyY(*get_whitepoint(whitepoint))  # noqa: N806
        return x, y, 0.0
    x = X / float(X + Y + Z)
    y = Y / float(X + Y + Z)
    return x, y, Y


def xy_CCT_delta(  # noqa: N802
    x: float, y: float, daylight: bool = True, method: int = 2000
) -> tuple[float, float]:
    """Return CCT and delta to locus.

    Args:
        x (float):  x chromaticity coordinate
        y (float):  y chromaticity coordinate
        daylight (bool):  True for daylight locus, False for planckian locus
        method (int):  Method to use for delta calculation

    Returns:
        tuple[float, float]:  CCT and delta to locus.
    """
    cct = xyY2CCT(x, y)
    d = None
    if cct:
        locus = None
        if daylight:
            # Daylight locus
            if 2500 <= cct <= 25000:
                locus = CIEDCCT2XYZ(cct, 100.0)
        # Planckian locus
        elif 1667 <= cct <= 25000:
            locus = planckianCT2XYZ(cct, 100.0)
        if locus:
            l2, a2, b2 = xyY2Lab(x, y, 100.0, locus)
            d = delta(l2, 0, 0, l2, a2, b2, method)
    return cct, d


def dmatrixz(nrl: int, nrh: int, ncl: int, nch: int) -> dict:
    """Create a 2D matrix of dictionaries.

    Adapted from ArgyllCMS numlib/numsup.c

    Args:
        nrl (int):  Row low index
        nrh (int):  Row high index
        ncl (int):  Col low index
        nch (int):  Col high index

    Returns:
        dict: A dictionary containing the matrix.
    """
    m = {}

    nrh = max(nrh, nrl)  # Prevent failure for 0 dimension
    nch = max(nch, ncl)

    rows = nrh - nrl + 1
    cols = nch - ncl + 1

    for i in range(rows):
        m[i + nrl] = {}
        for j in range(cols):
            m[i][j + ncl] = 0

    return m


def dvector(nl: int, nh: int) -> dict:
    """Adapted from ArgyllCMS numlib/numsup.c.

    Args:
        nl:  Lowest index
        nh:  Highest index

    Returns:
        dict: Empty dictionary.
    """
    return {}


def gam_fit(gf: GammaFits, v: list[float]) -> float:
    """Gamma + input offset function handed to powell().

    Adapted from ArgyllCMS xicc/xicc.c

    Args:
        gf (GammaFits): Gamma fit object containing parameters.
        v (list[float]): List of gamma values to fit.

    Returns:
        float: Squared error value for the fit.
    """
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


def linmin(
    cp: list[float],
    xi: list[float],
    di: int,
    ftol: float,
    func: Callable,
    fdata: Any,  # noqa: ANN401
) -> float:
    """Line bracketing and minimisation routine.

    Return value at minimum.

    Adapted from ArgyllCMS numlib/powell.c

    Args:
        cp (list[float]): Start point, and returned value.
        xi (list[float]): Search vector.
        di (int): Dimensionality.
        ftol (float): Tolerance to stop on.
        func (callable): Error function to evaluate.
        fdata: Opaque data for func().

    Returns:
        float: Value at minimum.
    """
    # ax, xx, bx  # Search vector multipliers
    # af, xf, bf  # Function values at those points
    # xt  # Trial point

    xt = {} if di <= 10 else dvector(0, di - 1)  # Vector for trial point

    # --------------------------
    # First bracket the solution

    ax, xx, bx, af, xf, bf = _linmin_bracket_solution(cp, xi, xt, di, func, fdata)

    # ---------------------------------------
    # Now use brent minimiser bewteen a and b

    return _linmin_use_brent_minimiser(
        ax,
        xx,
        bx,
        af,
        xf,
        bf,
        cp,
        xi,
        di,
        ftol,
        func,
        fdata,
        xt,
    )


def _linmin_bracket_solution(  # noqa: C901
    cp: list[float],
    xi: list[float],
    xt: dict | list[float],  # Vector for trial point
    di: int,
    func: Callable,
    fdata: Any,  # noqa: ANN401
) -> tuple[float, float, float, float, float, float]:
    """Bracket the solution for the line minimisation.

    Args:
        cp (list[float]): Start point, and returned value.
        xi (list[float]): Search vector.
        xt (dict | list[float]): Vector for trial point.
        di (int): Dimensionality.
        func (callable): Error function to evaluate.
        fdata: Opaque data for func().

    Returns:
        tuple[float, float, float, float, float, float]: ax, xx, bx, af, xf,
            bf - Search vector multipliers and function values at those points.
    """
    powell_gold = 1.618034
    logger.debug("linmin: Bracketing solution")

    # The line is measured as startpoint + offset * search vector.
    # (Search isn't symetric, but it seems to depend on cp being
    # best current solution ?)
    ax = 0.0
    for i in range(di):
        xt[i] = cp[i] + ax * xi[i]
    af = func(fdata, xt)

    # xx being vector offset 0.618
    xx = 1.0 / powell_gold
    for i in range(di):
        xt[i] = cp[i] + xx * xi[i]
    xf = func(fdata, xt)

    logger.debug(f"linmin: Initial points a:{ax:f}:{af:f} -> b:{xx:f}:{xf:f}")

    # Fix it so that we are decreasing from point a -> x
    if xf > af:
        tt = ax
        ax = xx
        xx = tt
        tt = af
        af = xf
        xf = tt

    logger.debug(f"linmin: Ordered Initial points a:{ax:f}:{af:f} -> b:{xx:f}:{xf:f}")

    bx = xx + powell_gold * (xx - ax)  # Guess b beyond a -> x
    for i in range(di):
        xt[i] = cp[i] + bx * xi[i]
    bf = func(fdata, xt)

    logger.debug(
        f"linmin: Initial bracket a:{ax:f}:{af:f} x:{xx:f}:{xf:f} b:{bx:f}:{bf:f}"
    )

    # While not bracketed
    while xf > bf:
        logger.debug(f"linmin: Not bracketed because xf {xf:f} > bf {bf:f}")
        logger.debug(f"        ax = {ax:f}, xx = {xx:f}, bx = {bx:f}")

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
            if uf > xf:  # Minimum is between a and u
                bx = ux
                bf = uf
                break

            # Parabolic fit didn't work, look further out in direction of b
            ux = bx + powell_gold * (bx - xx)

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
            ux = bx + powell_gold * (bx - xx)  # Test beyond b

        elif (ux - ulim) * (ulim - bx) >= 0.0:  # u is beyond limit
            ux = ulim
        else:  # u is to left side of x ?
            ux = bx + powell_gold * (bx - xx)
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
    logger.debug(f"linmin: Got bracket a:{ax:f}:{af:f} x:{xx:f}:{xf:f} b:{bx:f}:{bf:f}")
    # Got bracketed minimum between a -> x -> b

    return ax, xx, bx, af, xf, bf  # noqa: N806


def _linmin_use_brent_minimiser(  # noqa: C901
    ax: float,
    xx: float,
    bx: float,
    af: float,
    xf: float,
    bf: float,
    cp: list[float],
    xi: list[float],
    di: int,
    ftol: float,
    func: Callable,
    fdata: Any,  # noqa: ANN401
    xt: dict | list[float],  # Vector for trial point
) -> float:
    """Use Brent's method to find the minimum between a and b.

    Adapted from ArgyllCMS numlib/powell.c

    Args:
        ax (float): Lower bound of the bracket.
        xx (float): Current best point.
        bx (float): Upper bound of the bracket.
        af (float): Function value at ax.
        xf (float): Function value at xx.
        bf (float): Function value at bx.
        cp (list[float]): Current point.
        xi (list[float]): Search vector.
        di (int): Dimensionality of the problem.
        ftol (float): Tolerance for convergence.
        func (Callable): Function to minimize.
        fdata (Any): Opaque data for func().
        xt (dict | list[float]): Vector for trial point.

    Returns:
        float: Value at minimum.
    """
    powell_cgold = 0.3819660
    powell_max_iterations = 100

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

    for _iter in range(1, powell_max_iterations + 1):
        mx = 0.5 * (ax + bx)  # m is center of bracket values
        # if ABSTOL:
        # tol1 = ftol  # Absolute tollerance
        # else:
        tol1 = ftol * abs(xx) + 1e-10
        tol2 = 2.0 * tol1

        logger.debug(
            f"linmin: Got bracket a:{ax:f}:{af:f} x:{xx:f}:{xf:f} b:{bx:f}:{bf:f}"
        )

        # See if we're done
        if abs(xx - mx) <= (tol2 - 0.5 * (bx - ax)):
            logger.debug(
                "linmin: We're done because "
                f"{abs(xx - mx):f} <= {tol2 - 0.5 * (bx - ax):f}"
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

            logger.debug("linmin: Trial parabolic fit")

            if abs(p) >= abs(0.5 * q * te) or p <= q * (ax - xx) or p >= q * (bx - xx):
                # Give up on the parabolic fit, and use the golden section search
                e = (
                    ax - xx if xx >= mx else bx - xx
                )  # Override previous distance moved */
                de = powell_cgold * e
                logger.debug("linmin: Moving to golden section search")
            else:  # Use parabolic fit
                de = p / q  # Change in xb
                ux = xx + de  # Trial point according to parabolic fit
                if (ux - ax) < tol2 or (bx - ux) < tol2:
                    # Don't use parabolic, use tol1 if (mx - xx) > 0.0: tol1 is +ve
                    de = tol1 if (mx - xx) > 0.0 else -tol1
                logger.debug("linmin: Using parabolic fit")
        else:  # Keep using the golden section search
            e = ax - xx if xx >= mx else bx - xx  # Override previous distance moved
            de = powell_cgold * e
            logger.debug("linmin: Continuing golden section search")

        if abs(de) >= tol1:  # If de moves as much as tol1 would
            ux = xx + de  # use it
            logger.debug(f"linmin: ux = {ux:f} = xx {xx:f} + de {de:f}")
        elif de > 0.0:
            ux = xx + tol1
            logger.debug(f"linmin: ux = {ux:f} = xx {xx:f} + tol1 {tol1:f}")
        else:
            ux = xx - tol1
            logger.debug(f"linmin: ux = {ux:f} = xx {xx:f} - tol1 {tol1:f}")

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
            logger.debug("linmin: found new best solution")
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
            elif uf <= vf or vx in [xx, wx]:  # New 3rd best, or equal 1st & 2nd
                vx = ux
                vf = uf  # New previous 2nd best from latest
            logger.debug("linmin: found new worse solution")
    # !!! should do something if iter > POWELL_MAXIT !!!!
    # Solution is at xx, xf

    # Compute solution vector
    for i in range(di):
        cp[i] += xx * xi[i]

    return xf  # Return value at minimum


def powell(  # noqa: C901
    di: int,
    cp: list[float],
    s: list[float],
    ftol: float,
    maxit: int,
    func: Callable,
    fdata: list,
    prog: None | Callable = None,
    pdata: None | list = None,
) -> bool:
    """Standard interface for powell function.

    Adapted from ArgyllCMS `powell.c`.

    Args:
        di (int): Dimensionality of the problem.
        cp (list[float]): Initial starting point, will be modified to the
            solution.
        s (list[float]): Size of initial search area, must be same length as
            cp.
        ftol (float): Tolerance of error change to stop on.
        maxit (int): Maximum iterations allowed.
        func (Callable): Error function to evaluate.
        fdata (list): Opaque data needed by function.
        prog (Callable | None): Optional progress percentage callback.
        pdata: Opaque data needed by prog().

    Returns:
        bool: True on sucess, False on failure due to excessive iterions, result
            will be in cp
    """
    if prog is None:

        def prog(*args, **kwargs) -> None:
            """Dummy progress function."""

    dbl_epsilon = 2.2204460492503131e-016
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

    # Report initial progress
    prog(pdata, pc)

    # Initial function evaluation
    retv = func(fdata, cp)

    # Iterate untill we converge on a solution, or give up.
    for iter_ in range(1, maxit):
        # lretv  # Last function return value
        ibig = 0  # Index of biggest delta
        del_ = 0.0  # Biggest function value decrease
        # pretv  # Previous function return value

        pretv = retv  # Save return value at top of iteration

        # Loop over all directions in the set
        for i in range(di):
            logger.debug(f"Looping over direction {i}")

            for j in range(di):  # Extract this direction to make search vector
                svec[j] = dmtx[j][i]

            # Minimize in that direction
            lretv = retv
            retv = linmin(cp, svec, di, ftol, func, fdata)

            # Record bigest function decrease, and dimension it occurred on
            if abs(lretv - retv) > del_:
                del_ = abs(lretv - retv)
                ibig = i

        # if ABSTOL:
        # stopth = ftol  # Absolute tollerance
        # else
        stopth = ftol * 0.5 * (abs(pretv) + abs(retv) + dbl_epsilon)
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
                # Report initial progress
                prog(pdata, pc)

        # If we have had at least one change of direction and
        # reached a suitable tollerance, then finish
        if iter_ > 1 and curdel <= stopth:
            logger.debug(
                f"Reached stop tollerance because curdel {curdel:f} <= stopth "
                f"{stopth:f}"
            )
            break
        logger.debug(f"Not stopping because curdel {curdel:f} > stopth {stopth:f}")

        for i in range(di):
            svec[i] = cp[i] - spt[i]  # Average direction moved after minimization round
            xpt[i] = cp[i] + svec[i]  # Extrapolated point after round of minimization
            spt[i] = cp[i]  # New start point for next round

        # Function value at extrapolated point
        lretv = func(fdata, xpt)

        if lretv >= pretv:  # If extrapolation is not an improvement
            continue
        t1 = pretv - retv - del_
        t2 = pretv - lretv
        t = 2.0 * (pretv - 2.0 * retv + lretv) * t1 * t1 - del_ * t2 * t2
        if t >= 0.0:
            continue
        # Move to the minimum of the new direction
        retv = linmin(cp, svec, di, ftol, func, fdata)

        for i in range(di):  # Save the new direction
            dmtx[i][ibig] = svec[i]  # by replacing best previous

    # Report final progress
    prog(pdata, 100)

    if iter_ < maxit:
        return True

    logger.debug("powell: returning False due to excessive iterations")
    return False  # Failed due to execessive iterations


def xicc_tech_gamma(
    egamma: float, input_offset: float, output_offset: float = 0.0
) -> float:
    """Compute technical gamma for correct 50% response.

    Adapted from ArgyllCMS xicc.c

    Args:
        egamma (float): The effective gamma.
        input_offset (float): The input offset.
        output_offset (float, optional): The output offset. Defaults to 0.0.

    Returns:
        float: The technical gamma.
    """
    gf = GammaFits()
    op = {}
    sa = {}

    if input_offset <= 0.0:
        return egamma

    # We set up targets without outo being added
    outo = input_offset * output_offset  # Offset acounted for in output
    gf.bp = input_offset - outo  # Black value for 0 % input
    gf.wp = 1.0 - outo  # White value for 100% input
    gf.thyr = math.pow(0.5, egamma) - outo  # Advetised 50% target

    op[0] = egamma
    sa[0] = 0.1

    if not powell(1, op, sa, 1e-6, 500, gam_fit, gf):
        logger.warning("Computing effective gamma and input offset is inaccurate!")

    return op[0]


class GammaFits:
    """Gamma fits class for xicc technical gamma computation.

    Adapted from ArgyllCMS xicc/xicc.c.

    Args:
        wp (float): 100% input target.
        thyr (float): 50% input target.
        bp (float): 0% input target.
    """

    def __init__(self, wp: float = 1.0, thyr: float = 0.2, bp: float = 0.0) -> None:
        self.wp = wp  # 100% input target
        self.thyr = thyr  # 50% input target
        self.bp = bp  # 0% input target


class Interp:
    """Interpolation class.

    Args:
        xp (list): x values for interpolation.
        fp (list): f(x) values for interpolation.
        left (float, optional): Value to return for x < min(xp). Defaults to
            None.
        right (float, optional): Value to return for x > max(xp). Defaults to
            None.
        use_numpy (bool, optional): Use numpy for speed. Defaults to False.
    """

    def __init__(
        self,
        xp: list[float],
        fp: list[float],
        left: None | float = None,
        right: None | float = None,
        use_numpy: bool = False,
    ) -> None:
        if use_numpy:
            # Use numpy for speed
            xp = numpy.array(xp)
            fp = numpy.array(fp)
        self.xp = xp
        self.fp = fp
        self.left = left
        self.right = right
        self.lookup = {}
        self.use_numpy = use_numpy

    def __call__(self, x: float) -> float:
        """Return the interpolated value for x.

        Args:
            x (float): The x value to interpolate.

        Returns:
            float: The interpolated value at x.
        """
        if x not in self.lookup:
            self.lookup[x] = self._interp(x)
        return self.lookup[x]

    def _interp(self, x: float) -> float:
        """Perform the interpolation.

        Args:
            x (float): The x value to interpolate.

        Returns:
            float: The interpolated value at x.
        """
        if self.use_numpy:
            return numpy.interp(x, self.xp, self.fp, self.left, self.right)
        return interp(x, self.xp, self.fp, self.left, self.right)


class BT1886:
    """BT.1886 like transfer function.

    Adapted from ArgyllCMS xicc/xicc.c

    Args:
        matrix (Matrix): Matrix to use for forward and backward transformations.
        XYZbp (tuple[float, float, float]): Black point in XYZ coordinates.
        outoffset (float): Output offset. Defaults to 0.0.
        gamma (float): Gamma value. Defaults to 2.4.
        apply_trc (bool): Whether to apply the transfer curve. Defaults to True.
    """

    def __init__(
        self,
        matrix: Matrix3x3,
        XYZbp: tuple[float, float, float],  # noqa: N803
        outoffset: float = 0.0,
        gamma: float = 2.4,
        apply_trc: bool = True,
    ) -> None:
        """Setup BT.1886 for the given target.

        If apply_trc is False, apply only the black point blending portion of
        BT.1886 mapping. Note that this will only work correctly for an output
        offset of 1.0

        """
        if not apply_trc and outoffset < 1:
            raise ValueError("Output offset must be 1.0 when not applying gamma")

        self.bwd_matrix = matrix.inverted()
        self.fwd_matrix = matrix
        self.gamma = gamma

        lab = XYZ2Lab(*[v * 100 for v in XYZbp])

        # For bp blend
        self.outL = lab[0]
        # a* b* correction needed
        self.tab = list(lab)
        self.tab[0] = 0  # 0 because bt1886 maps L to target

        if XYZbp[1] < 0:
            XYZbp = list(XYZbp)  # noqa: N806
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

    def apply(self, X: float, Y: float, Z: float) -> tuple[float, float, float]:  # noqa: N803
        """Apply BT.1886 black offset + gamma curve to the XYZ out of the input profile.

        Do this in the colorspace defined by the input profile matrix lookup,
        so it will be relative XYZ. We assume that BT.1886 does a Rec709 to gamma
        viewing adjustment, on top of any source profile transfer curve
        (i.e. BT.1886 viewing adjustment is assumed to be the mismatch between
        Rec709 curve and the output offset pure 2.4 gamma curve)

        Args:
            X (float): X value in XYZ
            Y (float): Y value in XYZ
            Z (float): Z value in XYZ

        Returns:
            tuple[float, float, float]: Adjusted XYZ values as a tuple (X, Y, Z).
        """
        logger.debug(f"bt1886 XYZ in {X:f} {Y:f} {Z:f}")

        out = self.bwd_matrix * (X, Y, Z)

        logger.debug(f"bt1886 RGB in {out[0]:f} {out[1]:f} {out[2]:f}")

        for j in range(3):
            vv = out[j]

            if self.apply_trc:
                # Convert linear light to Rec709 transfer curve
                vv = 4.5 * vv if vv < 0.018 else 1.099 * math.pow(vv, 0.45) - 0.099

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

        logger.debug(f"bt1886 RGB bt.1886 {out[0]:f} {out[1]:f} {out[2]:f}")

        out = list(XYZ2Lab(*[v * 100 for v in out]))

        logger.debug(f"bt1886 Lab after Y adj. {out[0]:f} {out[1]:f} {out[2]:f}")

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

        logger.debug(f"bt1886 Lab after wp adj. {out[0]:f} {out[1]:f} {out[2]:f}")
        out = Lab2XYZ(*out)
        logger.debug(f"bt1886 XYZ out {out[0]:f} {out[1]:f} {out[2]:f}")
        return out


class BT2390:
    """Roll-off for SMPTE 2084 (PQ) according to Report ITU-R BT.2390-2 HDR TV.

    Args:
        black_cdm2 (float): Black level in cd/m^2.
        white_cdm2 (float): White level in cd/m^2.
        master_black_cdm2 (float, optional): Mastering black level in cd/m^2.
            Defaults to 0.
        master_white_cdm2 (float, optional): Mastering white level in cd/m^2.
            Defaults to 10000.
        use_alternate_master_white_clip (bool, optional): If True, use an
            alternate method for mastering white clipping. Defaults to True.
    """

    def __init__(
        self,
        black_cdm2: float,
        white_cdm2: float,
        master_black_cdm2: float = 0,
        master_white_cdm2: float = 10000,
        use_alternate_master_white_clip: bool = True,
    ) -> None:
        """Master black and white level are used to tweak the roll-off and clip.

        If use_alternate_master_white_clip is True, do not follow BT.2390 for
        the mastering white adjustment (allows to preserve more detail in
        rolled-off highlights)

        Args:
            black_cdm2 (float): Black level in cd/m^2.
            white_cdm2 (float): White level in cd/m^2.
            master_black_cdm2 (float, optional): Mastering black level in
                cd/m^2. Defaults to 0.
            master_white_cdm2 (float, optional): Mastering white level in
                cd/m^2. Defaults to 10000.
            use_alternate_master_white_clip (bool, optional): If True, use an
                alternate method for mastering white clipping. Defaults to
                True.
        """
        self.black_cdm2 = black_cdm2
        self.white_cdm2 = white_cdm2
        self.master_black_cdm2 = master_black_cdm2
        self.master_white_cdm2 = master_white_cdm2

        self.ominv = black_cdm2 / 10000.0  # Lmin
        self.omini = special_pow(self.ominv, 1.0 / -2084)  # Original minLum
        self.omaxv = white_cdm2 / 10000.0  # Lmax
        self.omaxi = special_pow(self.omaxv, 1.0 / -2084)  # Original maxLum

        self.oKS = 1.5 * self.omaxi - 0.5

        # BT.2390-2
        self.mminv = master_black_cdm2 / 10000.0  # LB
        self.mmini = special_pow(self.mminv, 1.0 / -2084)
        self.mmaxv = master_white_cdm2 / 10000.0  # LW
        mmaxi = special_pow(self.mmaxv, 1.0 / -2084)
        if use_alternate_master_white_clip:
            self.maxci = (mmaxi - self.mmini) / (1 - self.mmini)
            self.mmaxi = 1.0
        else:
            self.maxci = 1.0
            self.mmaxi = mmaxi
        self.mini = (self.omini - self.mmini) / (
            self.mmaxi - self.mmini
        )  # Normalized minLum
        self.minv = special_pow(self.mini, -2084)
        self.maxi = (self.omaxi - self.mmini) / (
            self.mmaxi - self.mmini
        )  # Normalized maxLum
        self.maxv = special_pow(self.maxi, -2084)

        self.KS = 1.5 * self.maxi - 0.5

        if self.maxi <= self.maxci < 1:
            e2 = self.P(self.maxci, self.KS, self.maxi)
            diff = self.maxci - e2
            self.s = (self.maxci - self.maxi) / diff

    def P(self, B: float, KS: float, maxi: float, maxci: float = 1.0) -> float:  # noqa: N802, N803
        """Apply the roll-off function P(E1) to the input value E1.

        Args:
            B (float): Input value E1 to apply the roll-off to.
            KS (float): The KS value.
            maxi (float): The maximum input value.
            maxci (float, optional): The maximum clip input value. Defaults to
                1.0.

        Returns:
            float: The output value after applying the roll-off.
        """  # noqa: D402
        t = (B - KS) / (1 - KS)
        e2 = (
            (2 * t**3 - 3 * t**2 + 1) * KS
            + (t**3 - 2 * t**2 + t) * (1 - KS)
            + (-2 * t**3 + 3 * t**2) * maxi
        )
        if maxci < 1:
            # (Old) Clipping for better target display peak luminance usage
            # XXX: Only kept for backwards compatibility
            s = min(((B - KS) / (maxci - KS)) ** 4, 1)
            e2 = e2 * (1 - s) + maxi * s
        return e2

    def apply(
        self,
        v: float,
        KS: None | float = None,  # noqa: N803
        maxi: None | float = None,
        maxci: None | float = None,
        mini: None | float = None,
        mmaxi: None | float = None,
        mmini: None | float = None,
        bpc: bool = False,
        normalize: bool = True,
    ) -> float:
        """Apply roll-off (E' in, E' out) maxci if < 1.0 applies alterante clip.

        Args:
            v (float): Input value to apply roll-off to.
            KS (float, optional): The KS value. Defaults to self.KS.
            maxi (float, optional): The maximum input value. Defaults to
                self.maxi.
            maxci (float, optional): The maximum clip input value. Defaults to
                self.maxci.
            mini (float, optional): The minimum input value. Defaults to
                self.mini.
            mmaxi (float, optional): The mastering maximum input value.
                Defaults to self.mmaxi.
            mmini (float, optional): The mastering minimum input value.
                Defaults to self.mmini.
            bpc (bool, optional): If True, apply black point compensation.
                Defaults to False.
            normalize (bool, optional): If True, normalize PQ values based on
                mastering display black/white levels. Defaults to True.

        Returns:
            float: The output value after applying the roll-off.
        """
        KS = self.KS if KS is None else KS  # noqa: N806
        maxi = self.maxi if maxi is None else maxi
        mini = self.mini if mini is None else mini
        mmaxi = self.mmaxi if mmaxi is None else mmaxi
        mmini = self.mmini if mmini is None else mmini
        maxci = self.maxci if maxci is None else maxci
        if normalize and mmini is not None and mmaxi is not None:
            # Normalize PQ values based on mastering display black/white levels
            e1 = min(max((v - mmini) / (mmaxi - mmini), 0), 1.0)
        else:
            e1 = v
        # BT.2390-3 suggests P[E1] if KS <= E1 <=1, but this results in
        # division by zero if KS = 1. The correct way is to check for
        # KS < E1 <=1
        if KS < e1 <= 1:
            e2 = self.P(e1, KS, maxi)
            if maxi <= maxci < 1:
                # (New) Clipping for better target display peak luminance usage
                s = self.s
                diff = e1 - e2
                e2 = min(e1 - diff * s, maxi)
            elif maxci < 1:
                e2 = min(e1, maxci)
        else:
            e2 = e1
        # BT.2390-3 suggests 0 <= E2 <= 1, but this results in a discontinuity
        # if KS < 0 (high LB > Lmin, low Lmax, high LW). To avoid this, check
        # for E2 <= 1 instead
        if mini and e2 <= 1:
            # Apply black level lift
            min_lum = mini
            # maxLum = maxi
            b = min_lum
            # BT.2390-3 suggests E2 + b * (1 - E2) ** 4, but this clips, if
            # minLum > 0.25, due to a 'dip' in the function. The solution is to
            # adjust the exponent according to minLum. For minLum <= 0.25
            # (< 5.15 cd/m2), this will give the same result as 'pure' BT.2390-3
            # Only for positive b i.e. minLum >= LB if b >= 0,
            # otherwise for negative b i.e. minLum < LB
            p = min(1.0 / b, 4) if b >= 0 else 4
            e3 = e2 + b * (1 - e2) ** p
            # If maxLum < 1, and the input value reaches maxLum, the resulting
            # output value will be higher than maxLum after applying the black
            # level lift (note that this is *not* a side effect of the above
            # exponent adjustment). Undo this by re-scaling to the nominal output
            # range [minLum, maxLum].
            if maxi < 1:
                # Only re-scale if maxLum < 1. Note that maxLum can be > 1
                # if Lmax > LW despite E2 <= 1
                e3 = convert_range(e3, b, maxi + b * (1 - maxi) ** p, b, maxi)
        else:
            e3 = e2
        if bpc:
            e3 = convert_range(e3, mini, maxi, 0, maxi)
        if normalize and mmini is not None and mmaxi is not None:
            # Invert the normalization of the PQ values
            e3 = e3 * (mmaxi - mmini) + mmini
        return max(e3, 0)


class Matrix3x3(list):
    """Simple 3x3 matrix.

    Args:
        matrix (list tuple, optional): A 3x3 matrix to initialize with.
            Defaults to None.
    """

    def __init__(self, matrix: None | list | tuple = None) -> None:
        super().__init__()
        self._reset()

        # TODO: Matrix should initialize to identity matrix if None or empty.
        # if matrix is None or (isinstance(matrix, (list, tuple)) and len(matrix) == 0):
        #     matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        if matrix:
            self.update(matrix)

    def update(self, matrix: list | tuple) -> None:
        """Update the matrix with a new 3x3 matrix.

        Args:
            matrix (list | tuple): A 3x3 matrix to update with.

        Raises:
            ValueError: If the matrix is not 3x3.
            ValueError: If the rows or columns of the matrix are not of length 3.
        """
        if len(matrix) != 3:
            raise ValueError(f"Invalid number of rows for 3x3 matrix: {len(matrix)}")
        self._reset()
        while len(self):
            self.pop()
        for row in matrix:
            if len(row) != 3:
                raise ValueError(
                    f"Invalid number of columns for 3x3 matrix: {len(row)}"
                )
            self.append([])
            for column in row:
                self[-1].append(column)

    def _reset(self) -> None:
        self._inverted = None
        self._transposed = None
        self._rounded = {}
        self._applied = {}

    def __add__(self, matrix: list | tuple | Matrix3x3) -> Matrix3x3:
        """Matrix addition.

        Args:
            matrix (Matrix3x3 or list or tuple): The matrix to add.

        Returns:
            Matrix3x3: The result of the addition.
        """
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

    def __iadd__(self, matrix: list | tuple | Matrix3x3) -> Self:
        """Matrix addition in place."""
        # inplace
        self.update(self.__add__(matrix))
        return self

    @overload
    def __imul__(
        self, matrix: list[float, float, float]
    ) -> list[float, float, float]: ...

    @overload
    def __imul__(
        self, matrix: tuple[float, float, float]
    ) -> list[float, float, float]: ...

    @overload
    def __imul__(self, matrix: Matrix3x3) -> Self: ...

    def __imul__(self, matrix) -> Self:
        """Matrix multiplication.

        Args:
            matrix (Matrix3x3 or list or tuple): The matrix to multiply with.
        """
        # inplace
        self.update(self.__mul__(matrix))
        return self

    @overload
    def __mul__(
        self, matrix: list[float, float, float]
    ) -> list[float, float, float]: ...

    @overload
    def __mul__(
        self, matrix: tuple[float, float, float]
    ) -> list[float, float, float]: ...

    @overload
    def __mul__(self, matrix: Matrix3x3) -> Matrix3x3: ...

    def __mul__(self, matrix):
        """Matrix multiplication.

        Args:
            matrix (Matrix3x3 or list or tuple): The matrix to multiply with.
        """
        if not isinstance(matrix[0], (list, tuple)):
            return [
                self[0][0] * matrix[0]
                + self[0][1] * matrix[1]
                + self[0][2] * matrix[2],
                self[1][0] * matrix[0]
                + self[1][1] * matrix[1]
                + self[1][2] * matrix[2],
                self[2][0] * matrix[0]
                + self[2][1] * matrix[1]
                + self[2][2] * matrix[2],
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

    def adjoint(self) -> Matrix3x3:
        """Return adjoint matrix.

        Returns:
            Matrix3x3: Adjoint matrix.
        """
        return self.cofactors().transposed()

    def applied(self, fn: Callable) -> Matrix3x3:
        """Apply function to every element, return new matrix.

        Args:
            fn (callable): Function to apply to each element of the matrix.

        Returns:
            Matrix3x3: A new Matrix3x3 with the function applied to each element.
        """
        if fn in self._applied:
            return self._applied[fn]
        matrix = self.__class__()
        for row in self:
            matrix.append([])
            for column in row:
                matrix[-1].append(fn(column))
        self._applied[fn] = matrix
        return matrix

    def cofactors(self) -> Matrix3x3:
        """Return cofactor matrix.

        Returns:
            Matrix3x3: Cofactor matrix.
        """
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

    def determinant(self) -> float:
        """Return determinant of the matrix.

        Returns:
            float: Determinant of the matrix.
        """
        return (
            self[0][0] * self[1][1] * self[2][2]
            + self[1][0] * self[2][1] * self[0][2]
            + self[0][1] * self[1][2] * self[2][0]
        ) - (
            self[2][0] * self[1][1] * self[0][2]
            + self[1][0] * self[0][1] * self[2][2]
            + self[2][1] * self[1][2] * self[0][0]
        )

    def invert(self) -> None:
        """Invert the matrix in place."""
        # inplace
        self.update(self.inverted())

    def inverted(self) -> Matrix3x3:
        """Return inverted matrix.

        Returns:
            Matrix3x3: Inverted matrix.
        """
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

    def rounded(self, digits: int = 3) -> Matrix3x3:
        """Round each element of the matrix to the specified number of digits.

        Args:
            digits (int): Number of digits to round to. Default is 3.

        Returns:
            Matrix3x3: A new Matrix3x3 with each element rounded to the
                specified number of digits.
        """
        if digits in self._rounded:
            return self._rounded[digits]
        matrix = self.__class__()
        for row in self:
            matrix.append([])
            for column in row:
                matrix[-1].append(round(column, digits))
        self._rounded[digits] = matrix
        return matrix

    def transpose(self) -> None:
        """Transpose the matrix in place."""
        self.update(self.transposed())

    def transposed(self) -> Matrix3x3:
        """Return transposed matrix.

        Returns:
            Matrix3x3: Transposed matrix.
        """
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

    def __hash__(self) -> int:
        """Make the Matrix3x3 hashable."""
        return hash(
            f"{self[0][0]},{self[1][0]},{self[2][0]},"
            f"{self[0][1]},{self[1][1]},{self[2][1]},"
            f"{self[0][2]},{self[1][2]},{self[2][2]}"
        )

    def __eq__(self, other: list | tuple | Matrix3x3) -> bool:
        """Check if two matrices are equal.

        Args:
            other (Matrix3x3): The other matrix to compare with.

        Returns:
            bool: True if the matrices are equal, False otherwise.
        """
        if not isinstance(other, (list, tuple, Matrix3x3)):
            return False
        return (
            self[0][0] == other[0][0]
            and self[0][1] == other[0][1]
            and self[0][2] == other[0][2]
            and self[1][0] == other[1][0]
            and self[1][1] == other[1][1]
            and self[1][2] == other[1][2]
            and self[2][0] == other[2][0]
            and self[2][1] == other[2][1]
            and self[2][2] == other[2][2]
        )


class NumberTuple(tuple):
    """Simple tuple with a few extra methods."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a string representation of the tuple.

        Returns:
            str: String representation of the tuple.
        """
        return "({})".format(", ".join(str(value) for value in self))

    def round(self, digits: int = 4) -> NumberTuple:
        """Round each element of the tuple to the specified number of digits.

        Args:
            digits (int): Number of digits to round to. Default is 4.

        Returns:
            NumberTuple: A new NumberTuple with each element rounded to the
                specified number of digits.
        """
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
CAT_MATRICES = {
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
    # Inverse CIE 2015 2deg LMS to XYZ matrix from Argyll/icc/icc.c
    "CIE2015_2": Matrix3x3(
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

OPTIMAL_COLORS_LAB = [
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


def debug_caches() -> None:
    """Debug caches for duplicate entries."""
    for cache_name in (
        "XYZ2RGB.interp",
        "wp_adaption_matrix.cache",
        "get_rgb_space.cache",
        "get_standard_illuminant.cache",
        "get_whitepoint.cache",
    ):
        cn, ck = cache_name.split(".")
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
        print(cache_name, len(c), "entries", max(count - 1, 0), "duplicates")
        if count > 1:
            for k in c:
                v = c[k]
                print(k, v)


if "--debug-caches" in sys.argv[1:]:
    import atexit

    atexit.register(debug_caches)
