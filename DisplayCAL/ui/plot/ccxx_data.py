"""Compute CCMX/CCSS plot data for the "ccxx" and CIE 1931 xy views.

Binding-agnostic backend extracted from ``wx_ccxx_plot.CCXXPlot.__init__``
(and its ``draw_cie`` method): parses a CCMX/CCSS ``CGATS`` instance into
either spectral power-distribution curves (CCSS) or a matrix "flower" plot of
colorimeter-simulated vs. reference colour patches (CCMX), plus the
correction's CIE 1931 chromaticity points. Colour resolution (XYZ -> display
RGB) happens here so :class:`DisplayCAL.ui.plot.ccxx.CCXXPlotWidget` only
needs to render already-resolved points.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from DisplayCAL import colormath, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll_instruments import get_canonical_instrument_name
from DisplayCAL.cgats import CGATS
from DisplayCAL.icc_profile import CRInterpolation
from DisplayCAL.util_str import make_filename_safe
from DisplayCAL.worker_base import get_argyll_util

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker

#: Number of tick intervals used when rounding the CCSS y-axis max to a
#: "nice" number (matches ``wx_ccxx_plot.NTICK``).
NTICK = 10


def expt(a: float, n: float) -> float:
    """Return ``a**n``.

    Args:
        a (float): Base.
        n (float): Exponent.

    Returns:
        float: ``a`` raised to the power ``n``.
    """
    return math.pow(a, n)


def nicenum(x: float, do_round: bool) -> float:
    """Return a "nice" number close to ``x`` for axis labeling.

    Ported from Argyll's ``plot/plot.c``.

    Args:
        x (float): The value to round.
        do_round (bool): Round to the nearest nice number if True, otherwise
            round up.

    Returns:
        float: The nice number.
    """
    if x < 0.0:
        x = -x
    ex = math.floor(math.log10(x))
    f = x / expt(10.0, ex)
    if do_round:
        if f < 1.5:
            nf = 1.0
        elif f < 3.0:
            nf = 2.0
        elif f < 7.0:
            nf = 5.0
        else:
            nf = 10.0
    elif f < 1.0:
        nf = 1.0
    elif f < 2.0:
        nf = 2.0
    elif f < 5.0:
        nf = 5.0
    else:
        nf = 10.0
    return nf * expt(10.0, ex)


@dataclass(frozen=True)
class CCXXCurve:
    """One drawable element of the "ccxx" (spectral / flower) view.

    Attributes:
        points (list[tuple[float, float]]): The curve's vertices (a
            multi-point polyline for CCSS, a single point for CCMX).
        color (tuple[int, int, int]): Display RGB.
        marker (str | None): ``None`` for a line (CCSS), or a pyqtgraph
            scatter symbol name for a CCMX flower-plot marker.
        size (float): Marker size (CCMX only).
    """

    points: list[tuple[float, float]]
    color: tuple[int, int, int]
    marker: str | None = None
    size: float = 0.0


@dataclass(frozen=True)
class CCXXPoint:
    """One point usable in the CIE 1931 xy view.

    Attributes:
        xyz (list[float]): The linear-XYZ triplet.
        color (tuple[int, int, int]): Display RGB (matches the corresponding
            :class:`CCXXCurve`'s colour).
    """

    xyz: list[float]
    color: tuple[int, int, int]


@dataclass(frozen=True)
class CCXXPlotData:
    """Precomputed, toolkit-neutral CCMX/CCSS plot data.

    Attributes:
        is_ccss (bool): True for a CCSS (spectral), False for a CCMX (matrix)
            correction.
        title (str): Window title (correction type + description).
        x_label (str): Multi-line caption drawn under the "ccxx" plot.
        axis_x (tuple[float, float]): "ccxx" view X-axis range.
        axis_y (tuple[float, float]): "ccxx" view Y-axis range.
        curves (list[CCXXCurve]): Drawable elements for the "ccxx" view.
        points (list[CCXXPoint]): Points usable in the CIE 1931 xy view (only
            entries with a complete XYZ triplet).
    """

    is_ccss: bool
    title: str
    x_label: str
    axis_x: tuple[float, float]
    axis_y: tuple[float, float]
    curves: list[CCXXCurve] = field(default_factory=list)
    points: list[CCXXPoint] = field(default_factory=list)


def _resolve_rgb(
    xyz: list[float], y_max: float, size: float = 0.0
) -> tuple[int, int, int]:
    """Return the display RGB for one sample's XYZ, normalized by ``y_max``.

    Args:
        xyz (list[float]): The sample's XYZ triplet (mutated in place, as in
            the wx original).
        y_max (float): The reference whitepoint's Y (or matrix-derived
            equivalent), used to bring the sample into displayable range.
        size (float): The sample's marker size, if any. Mirrors the wx
            original's ``attrs.get("size", 0) > 11.25`` split between
            "colorimeter" and "reference" XYZ normalization.

    Returns:
        tuple[int, int, int]: The clamped, rounded display RGB.
    """
    if len(xyz) != 3:
        return (153, 153, 153)
    if size > 11.25:
        if y_max > 1:
            xyz[:] = [v / y_max for v in xyz]
        else:
            xyz[:] = [v * y_max for v in xyz]
    elif y_max > 1:
        xyz[:] = [v / y_max for v in xyz]
    return tuple(int(v) for v in colormath.XYZ2RGB(*xyz, scale=255, round_=True))


def compute_ccxx_plot_data(cgats: CGATS, worker: Worker | None = None) -> CCXXPlotData:
    """Compute plot data for a CCMX/CCSS ``CGATS`` instance.

    Args:
        cgats (CGATS): A CCMX/CCSS CGATS instance.
        worker (Worker | None): Worker used to run Argyll's ``spec2cie`` when
            ``cgats`` is a CCSS (spectral) correction.

    Returns:
        CCXXPlotData: The computed plot data.

    Raises:
        Exception: Whatever ``worker.create_tempdir()``/``exec_cmd()`` or
            ``CGATS()`` parsing raises when converting a CCSS to TI3.
    """
    is_ccss = cgats[0].type == b"CCSS"

    desc = cgats.get_descriptor()
    if cgats.filename:
        fn, ext = os.path.splitext(os.path.basename(cgats.filename))
    else:
        fn = desc
        ext = ".ccss" if is_ccss else ".ccmx"
    if isinstance(fn, bytes):
        fn = fn.decode("utf-8")
    desc = lang.getstr(f"{ext[1:]}.{fn}", default=desc)
    ccxx_type = "spectral" if is_ccss else "matrix"
    title = "{}: {}".format(
        lang.getstr(ccxx_type),
        desc if isinstance(desc, str) else desc.decode("utf-8"),
    )

    if is_ccss:
        temp = worker.create_tempdir()
        if isinstance(temp, Exception):
            raise temp
        basename = make_filename_safe(desc)
        if isinstance(basename, bytes):
            basename = basename.decode("utf-8")
        temp_path = os.path.join(temp, basename + ".ti3")

        cgats[0].type = b"CTI3"
        cgats[0].DEVICE_CLASS = b"DISPLAY"
        cgats.write(temp_path)

        temp_out_path = os.path.join(temp, basename + ".CIE.ti3")

        try:
            result = worker.exec_cmd(
                get_argyll_util("spec2cie"),
                [temp_path, temp_out_path],
                capture_output=True,
            )
            if isinstance(result, Exception) or not result:
                raise RuntimeError(result or "".join(worker.errors))
            cgats = CGATS(temp_out_path)
        finally:
            worker.wrapup(False)

    data_format = cgats.queryv1("DATA_FORMAT")
    data = cgats.queryv1("DATA")

    XYZ_max = 0
    samples: list[tuple[list[float], list[tuple[float, float]], dict]] = []

    if is_ccss:
        x_min = cgats.queryv1("SPECTRAL_START_NM")
        x_max = cgats.queryv1("SPECTRAL_END_NM")
        bands = cgats.queryv1("SPECTRAL_BANDS")
        lores = bands <= 40
        if lores:
            steps = int(x_max - x_min) + 1
            step = (x_max - x_min) / (steps - 1.0)
        else:
            step = (x_max - x_min) / (bands - 1.0)
        y_min = 0
        y_max = 1

        Y_max = 0
        for i in data:
            sample = data[i]
            values = []
            x = x_min
            for k in data_format.values():
                if k.startswith(b"SPEC_"):
                    y = sample[k.decode("utf-8")]
                    y_min = min(y, y_min)
                    y_max = max(y, y_max)
                    if lores:
                        values.append(y)
                    else:
                        values.append((x, y))
                        x += step
            if lores:
                numvalues = len(values)
                interp = CRInterpolation(values)
                values = []
                x = x_min
                for step_i in range(steps):
                    values.append(
                        (x, interp(step_i / (steps - 1.0) * (numvalues - 1.0)))
                    )
                    x += step
            XYZ = []
            for component in "XYZ":
                label = "XYZ_" + component
                if label in sample:
                    v = sample[label]
                    XYZ_max = max(XYZ_max, v)
                    if label == "XYZ_Y":
                        Y_max = max(Y_max, v)
                    XYZ.append(v)
            samples.append((XYZ, values, {}))
    else:
        x_min = 0
        y_min = 0

        mtx = colormath.Matrix3x3(
            [
                [sample[k.decode("utf-8")] for k in data_format.values()]
                for sample in data.values()
            ]
        )
        imtx = mtx.inverted()

        scale = 1
        x_max = 100 * scale
        y_max = x_max * (74.6 / 67.4)
        x_center = x_max / 2.0
        y_center = y_max / 2.0
        x_center *= scale
        y_center *= scale
        pos2rgb = [
            ((x_center - 23.7, y_center - 13.7), (0, 0, 1)),
            ((x_center, y_center + 27.3), (0, 1, 0)),
            ((x_center + 23.7, y_center - 13.7), (1, 0, 0)),
            ((x_center - 23.7, y_center + 13.7), (0, 1, 1)),
            ((x_center, y_center - 27.3), (1, 0, 1)),
            ((x_center + 23.7, y_center + 13.7), (1, 1, 0)),
            ((x_center, y_center), (1, 1, 1)),
        ]
        attrs_c = {"size": 10}
        attrs_r = {"size": 5}

        Y_max = (imtx * colormath.get_whitepoint("D65"))[1]
        for (x, y), (R, G, B) in pos2rgb:
            XYZ = list(colormath.RGB2XYZ(R, G, B))
            X, Y, Z = imtx * XYZ
            XYZ_max = max(XYZ_max, X, Y, Z)
            samples.append(([X, Y, Z], [(x, y)], attrs_c))
            samples.append((XYZ, [(x, y)], attrs_r))

    if is_ccss:
        if not x_max - x_min:
            x_min = 350.0
            x_max = 750.0
        if not y_max - y_min:
            y_min = 0.0
            y_max = 10.0
        y_zero = 0
        ccxx_axis_x = (
            math.floor(x_min / 50.0) * 50,
            math.ceil(x_max / 50.0) * 50,
        )
        graph_range = nicenum(y_max - y_zero, False)
        d = nicenum(graph_range / (NTICK - 1.0), True)
        spec_y = math.ceil(y_max / d)
        ccxx_axis_y = (math.floor(y_zero / d) * d, spec_y * d)
    else:
        ccxx_axis_x = (
            math.floor(x_min / 20.0) * 20,
            math.ceil(x_max / 20.0) * 20,
        )
        ccxx_axis_y = (math.floor(y_min), math.ceil(y_max))

    curves: list[CCXXCurve] = []
    points: list[CCXXPoint] = []
    for xyz, values, attrs in samples:
        rgb = _resolve_rgb(xyz, Y_max, attrs.get("size", 0.0))
        curves.append(
            CCXXCurve(
                points=values,
                color=rgb,
                marker="s" if "size" in attrs else None,
                size=attrs.get("size", 0.0),
            )
        )
        if len(xyz) == 3:
            points.append(CCXXPoint(xyz=xyz, color=rgb))

    ref = cgats.queryv1("REFERENCE")
    if ref:
        ref = get_canonical_instrument_name(ref)
        if isinstance(ref, bytes):
            ref = ref.decode("utf-8")

    if not is_ccss:
        observers_ab = {}
        for observer in config.VALID_VALUES["observer"]:
            observers_ab[observer] = lang.getstr("observer." + observer)
        x_label = [lang.getstr("matrix")]
        x_label.extend(["{:9.6f} {:9.6f} {:9.6f}".format(*tuple(row)) for row in mtx])
        if ref:
            ref_observer = cgats.queryv1("REFERENCE_OBSERVER")
            if ref_observer:
                if isinstance(ref_observer, bytes):
                    ref_observer = ref_observer.decode("utf-8")
                ref += ", " + observers_ab.get(ref_observer, ref_observer)
            x_label.append("")
            x_label.append(ref)
        fit_method = cgats.queryv1("FIT_METHOD")
        if fit_method == b"xy":
            fit_method = lang.getstr("ccmx.use_four_color_matrix_method")
        elif fit_method:
            fit_method = lang.getstr("perceptual")
        fit_de00_avg = cgats.queryv1("FIT_AVG_DE00")
        if not isinstance(fit_de00_avg, float):
            fit_de00_avg = None
        fit_de00_max = cgats.queryv1("FIT_MAX_DE00")
        if not isinstance(fit_de00_max, float):
            fit_de00_max = None
        if fit_method:
            x_label.append(fit_method)
        fit_de00 = []
        if fit_de00_avg:
            fit_de00.append(
                f"ΔE*00 {lang.getstr('profile.self_check.avg')} {fit_de00_avg:.4f}"
            )
        if fit_de00_max:
            fit_de00.append(
                f"ΔE*00 {lang.getstr('profile.self_check.max')} {fit_de00_max:.4f}"
            )
        if fit_de00:
            x_label.append("\n".join(fit_de00))
        x_label = "\n".join(x_label)
    else:
        x_label = ""
        if ref:
            x_label += ref + ", "
        x_label += f"{(x_max - x_min) / (bands - 1.0):.1f}nm, {x_min}-{x_max}nm"

    return CCXXPlotData(
        is_ccss=is_ccss,
        title=title,
        x_label=x_label,
        axis_x=ccxx_axis_x,
        axis_y=ccxx_axis_y,
        curves=curves,
        points=points,
    )


#: Comparison RGB gamuts drawn as triangles in the CIE 1931 xy view, paired
#: with a dash style name (mirrors ``wx_ccxx_plot.CCXXPlot.draw_cie``).
COMPARISON_GAMUTS: tuple[tuple[str, str], ...] = (
    ("Rec. 2020", "solid"),
    ("Adobe RGB (1998)", "dash"),
    ("DCI P3", "dashdot"),
    ("Rec. 709", "dot"),
)


def comparison_gamut_triangle(rgb_space: str) -> list[tuple[float, float]]:
    """Return the closed xy triangle for one comparison RGB colorspace.

    Args:
        rgb_space (str): A :mod:`DisplayCAL.colormath` RGB colorspace name.

    Returns:
        list[tuple[float, float]]: The R, G, B primaries' xy coordinates,
        closed back to the first point.
    """
    values = [
        colormath.RGB2xyY(*rgb, rgb_space=rgb_space)[:2]
        for rgb in ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    ]
    values.append(values[0])
    return values
