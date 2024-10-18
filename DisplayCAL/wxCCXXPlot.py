# -*- coding: utf-8 -*-

import math
import os
import sys

from DisplayCAL import (
    CGATS,
    ICCProfile as ICCP,
    colormath,
    config,
    localization as lang,
    wxenhancedplot as plot,
)
from DisplayCAL.argyll_instruments import get_canonical_instrument_name, instruments
from DisplayCAL.config import getcfg
from DisplayCAL.debughelpers import UnloggedError
from DisplayCAL.meta import (
    name as appname,
)
from DisplayCAL.util_str import make_filename_safe
from DisplayCAL.worker_base import get_argyll_util
from DisplayCAL.wxLUTViewer import LUTCanvas
from DisplayCAL.wxaddons import wx
from DisplayCAL.wxwindows import FlatShadedButton, show_result_dialog

BGCOLOUR = "#101010"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#202020"

if sys.platform == "darwin":
    FONTSIZE_LARGE = 11
    FONTSIZE_SMALL = 10
else:
    FONTSIZE_LARGE = 9
    FONTSIZE_SMALL = 8

NTICK = 10


# Graph labeling functions
# See Argyll plot/plot.c


def expt(a, n):
    return math.pow(a, n)


def nicenum(x, do_round):
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
    else:
        if f < 1.0:
            nf = 1.0
        elif f < 2.0:
            nf = 2.0
        elif f < 5.0:
            nf = 5.0
        else:
            nf = 10.0
    return nf * expt(10.0, ex)


class CCXXPlot(wx.Frame):
    """CCMX/CCSS plot and information"""

    def __init__(self, parent, cgats, worker=None):
        """Init new CCXPlot window.

        parent   Parent window (only used for error dialogs)
        cgats    A CCMX/CCSS CGATS instance
        worker   Worker instance

        """
        self.is_ccss = cgats[0].type == b"CCSS"

        desc = cgats.get_descriptor()

        if cgats.filename:
            fn, ext = os.path.splitext(os.path.basename(cgats.filename))
        else:
            fn = desc
            if self.is_ccss:
                ext = ".ccss"
            else:
                ext = ".ccmx"

        if isinstance(fn, bytes):
            fn = fn.decode("utf-8")

        desc = lang.getstr(f"{ext[1:]}.{fn}", default=desc)

        if self.is_ccss:
            ccxx_type = "spectral"
        else:
            ccxx_type = "matrix"

        title = "%s: %s" % (
            lang.getstr(ccxx_type),
            desc if isinstance(desc, str) else desc.decode("utf-8"),
        )

        if self.is_ccss:
            # Convert to TI3 so we can get XYZ from spectra for coloring

            temp = worker.create_tempdir()
            if isinstance(temp, Exception):
                show_result_dialog(temp, parent)
            else:
                basename = make_filename_safe(desc)
                if isinstance(basename, bytes):
                    basename = basename.decode("utf-8")
                temp_path = os.path.join(temp, basename + ".ti3")

                cgats[0].type = b"CTI3"
                cgats[0].DEVICE_CLASS = b"DISPLAY"
                cgats.write(temp_path)

                temp_out_path = os.path.join(temp, basename + ".CIE.ti3")

                result = worker.exec_cmd(
                    get_argyll_util("spec2cie"),
                    [temp_path, temp_out_path],
                    capture_output=True,
                )
                if isinstance(result, Exception) or not result:
                    show_result_dialog(
                        UnloggedError(result or "".join(worker.errors)), parent
                    )
                    worker.wrapup(False)
                else:
                    try:
                        cgats = CGATS.CGATS(temp_out_path)
                    except Exception as exception:
                        show_result_dialog(exception, parent)
                    finally:
                        worker.wrapup(False)

        data_format = cgats.queryv1("DATA_FORMAT")
        data = cgats.queryv1("DATA")

        XYZ_max = 0
        self.samples = []

        if self.is_ccss:
            x_min = cgats.queryv1("SPECTRAL_START_NM")
            x_max = cgats.queryv1("SPECTRAL_END_NM")
            bands = cgats.queryv1("SPECTRAL_BANDS")
            lores = bands <= 40
            if lores:
                # Interpolate if lores
                # 1nm intervals
                steps = int(x_max - x_min) + 1
                print("Up-interpolating", bands, "spectral bands to", steps)
                step = (x_max - x_min) / (steps - 1.0)
            else:
                step = (x_max - x_min) / (bands - 1.0)
            y_min = 0
            y_max = 1

            Y_max = 0
            for i in data:
                sample = data[i]
                # Get nm and spectral power
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
                    # Interpolate if lores. Use Catmull-Rom instead of
                    # PolySpline as we want curves to go through points exactly
                    numvalues = len(values)
                    interp = ICCP.CRInterpolation(values)
                    values = []
                    for i in range(steps):
                        values.append(
                            (x, interp(i / (steps - 1.0) * (numvalues - 1.0)))
                        )
                        x += step
                # Get XYZ for colorization
                XYZ = []
                for component in "XYZ":
                    label = "XYZ_" + component
                    if label in sample:
                        v = sample[label]
                        XYZ_max = max(XYZ_max, v)
                        if label == "XYZ_Y":
                            Y_max = max(Y_max, v)
                        XYZ.append(v)
                self.samples.append((XYZ, values, {}))

            Plot = plot.PolyLine
            Plot._attributes["width"] = 1
        else:
            # CCMX
            cube_size = 2
            x_min = 0
            y_min = 0

            mtx = colormath.Matrix3x3(
                [
                    [sample[k.decode("utf-8")] for k in data_format.values()]
                    for sample in data.values()
                ]
            )
            imtx = mtx.inverted()

            # Get XYZ that colorimeter would measure without matrix (sRGB ref,
            # so not accurate, but useful for visual representation which is all
            # we care about here)
            if cube_size == 2:
                scale = 1
                x_max = 100 * scale
                y_max = x_max * (74.6 / 67.4)
                if sys.platform != "win32":
                    x_center = x_max / 2.0
                else:
                    x_center = x_max / 2.0 - 2.5
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
            else:
                x_max = 100
                y_max = 100
                y = -5
                pos2rgb = []
                for R in range(cube_size):
                    for G in range(cube_size):
                        x = -5
                        y += 10
                        for B in range(cube_size):
                            x += 10
                            pos2rgb.append(
                                ((x, y), (v / (cube_size - 1.0) for v in (R, G, B)))
                            )
                attrs_c = {"marker": "square", "size": 10}
                attrs_r = {"marker": "square", "size": 5}
            Y_max = (imtx * colormath.get_whitepoint("D65"))[1]
            for _i, ((x, y), (R, G, B)) in enumerate(pos2rgb):
                XYZ = list(colormath.RGB2XYZ(R, G, B))
                X, Y, Z = imtx * XYZ
                XYZ_max = max(XYZ_max, X, Y, Z)
                self.samples.append(([X, Y, Z], [(x, y)], attrs_c))
                self.samples.append((XYZ, [(x, y)], attrs_r))

            Plot = plot.PolyMarker

        if self.is_ccss:
            # Protect against division by zero when range is zero
            if not x_max - x_min:
                x_min = 350.0
                x_max = 750.0
            if not y_max - y_min:
                y_min = 0.0
                y_max = 10.0

            y_zero = 0

            self.ccxx_axis_x = (
                math.floor(x_min / 50.0) * 50,
                math.ceil(x_max / 50.0) * 50,
            )
            self.spec_x = (self.ccxx_axis_x[1] - self.ccxx_axis_x[0]) / 50.0
            graph_range = nicenum(y_max - y_zero, False)
            d = nicenum(graph_range / (NTICK - 1.0), True)
            self.spec_y = math.ceil(y_max / d)
            self.ccxx_axis_y = (math.floor(y_zero / d) * d, self.spec_y * d)
        else:
            self.ccxx_axis_x = (
                math.floor(x_min / 20.0) * 20,
                math.ceil(x_max / 20.0) * 20,
            )
            self.ccxx_axis_y = (math.floor(y_min), math.ceil(y_max))

        self.gfx = []
        for XYZ, values, attrs in self.samples:
            if len(XYZ) == 3:
                # Got XYZ
                if attrs.get("size", 0) > 11.25:
                    # Colorimeter XYZ
                    if Y_max > 1:
                        # Colorimeter brighter than ref
                        XYZ[:] = [v / Y_max for v in XYZ]
                    else:
                        # Colorimeter dimmer than ref
                        XYZ[:] = [v * Y_max for v in XYZ]
                else:
                    # Ref XYZ
                    if Y_max > 1:
                        # Colorimeter brighter than ref
                        XYZ[:] = [v / Y_max for v in XYZ]
                RGB = tuple(
                    int(v) for v in colormath.XYZ2RGB(*XYZ, scale=255, round_=True)
                )
            else:
                RGB = (153, 153, 153)
            self.gfx.append(Plot(values, colour=wx.Colour(*RGB), **attrs))
        if self.is_ccss:
            # Add a few points at the extremes to define a bounding box
            self.gfx.append(
                plot.PolyLine(
                    [
                        (self.ccxx_axis_x[0], self.ccxx_axis_y[0]),
                        (self.ccxx_axis_x[1], self.ccxx_axis_y[1] - y_min),
                    ],
                    colour=wx.Colour(0, 0, 0, 0),
                )
            )

        ref = cgats.queryv1("REFERENCE")
        if ref:
            ref = get_canonical_instrument_name(ref).decode("utf-8")

        if not self.is_ccss:
            observers_ab = {}
            for observer in config.valid_values["observer"]:
                observers_ab[observer] = lang.getstr("observer." + observer)
            x_label = [lang.getstr("matrix")]
            x_label.extend(["%9.6f %9.6f %9.6f" % tuple(row) for row in mtx])
            if ref:
                ref_observer = cgats.queryv1("REFERENCE_OBSERVER")
                if ref_observer:
                    # If the .ccmx does not contain this value,
                    # the graph will still draw
                    ref_observer = ref_observer.decode("utf-8")
                    ref += ", " + observers_ab.get(ref_observer, ref_observer)
                x_label.append("")
                x_label.append(ref)
            fit_method = cgats.queryv1("FIT_METHOD")
            if fit_method == b"xy":
                # If the .ccmx does not contain this value,
                # the graph will still draw
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
                    "ΔE*00 %s %.4f"
                    % (lang.getstr("profile.self_check.avg"), fit_de00_avg)
                )
            if fit_de00_max:
                fit_de00.append(
                    "ΔE*00 %s %.4f"
                    % (lang.getstr("profile.self_check.max"), fit_de00_max)
                )
            if fit_de00:
                x_label.append("\n".join(fit_de00))
            x_label = "\n".join(x_label)
        else:
            x_label = ""
            if ref:
                x_label += ref + ", "
            x_label += "%.1fnm, %i-%inm" % (
                (x_max - x_min) / (bands - 1.0),
                x_min,
                x_max,
            )

        scale = max(getcfg("app.dpi") / config.get_default_dpi(), 1)

        style = wx.DEFAULT_FRAME_STYLE

        wx.Frame.__init__(self, None, -1, title, style=style)
        self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
        self.SetBackgroundColour(BGCOLOUR)
        self.Sizer = wx.GridSizer(1, 1, 0, 0)
        bg = wx.Panel(self)
        bg.SetBackgroundColour(BGCOLOUR)
        bg.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.canvas = canvas = LUTCanvas(bg)
        if self.is_ccss:
            bg.MinSize = (int(513 * scale), int(557 * scale))
            btnsizer = wx.BoxSizer(wx.HORIZONTAL)
            bg.Sizer.Add(
                btnsizer,
                flag=wx.EXPAND | wx.TOP,
                border=16,
            )
            self.toggle_btn = FlatShadedButton(bg, -1, label=lang.getstr("spectral"))
            btnsizer.Add(self.toggle_btn, 1)
            self.Sizer.Add(bg, 1, flag=wx.EXPAND)
            bg.Sizer.Add(canvas, 1, flag=wx.EXPAND)
        else:
            bg.MinSize = (int(400 * scale), int(400 * scale))
            self.Sizer.Add(bg, flag=wx.ALIGN_CENTER)
            canvas_w = int(240 * scale)
            canvas.MinSize = (int(canvas_w), int(canvas_w * (74.6 / 67.4)))
            bg.Sizer.Add(canvas, flag=wx.ALIGN_CENTER)
        label = wx.StaticText(
            bg, -1, x_label.replace("&", "&&"), style=wx.ALIGN_CENTRE_HORIZONTAL
        )
        label.SetForegroundColour(FGCOLOUR)
        label.SetMaxFontSize(11)
        bg.Sizer.Add(label, flag=wx.ALIGN_CENTER | wx.ALL & ~wx.TOP, border=16 * scale)
        canvas.SetBackgroundColour(BGCOLOUR)
        canvas.SetEnableCenterLines(False)
        canvas.SetEnableDiagonals(False)
        canvas.SetEnableGrid(True)
        canvas.enableTicks = (True, True)
        canvas.tickPen = wx.Pen(GRIDCOLOUR, int(canvas._pointSize[0]))
        canvas.SetEnablePointLabel(False)
        canvas.SetEnableTitle(True)
        canvas.SetForegroundColour(FGCOLOUR)
        canvas.SetGridColour(GRIDCOLOUR)
        canvas.canvas.BackgroundColour = BGCOLOUR
        if self.is_ccss:
            canvas.HandCursor = wx.StockCursor(wx.CURSOR_SIZING)
            canvas.SetCursor(canvas.HandCursor)
        else:
            canvas.canvas.Unbind(wx.EVT_LEFT_DCLICK)
            canvas.SetEnableDrag(False)
            canvas.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
            canvas.SetXSpec("none")
            canvas.SetYSpec("none")

        # CallAfter is needed under GTK as usual
        wx.CallAfter(self.draw_ccxx)

        if self.is_ccss:
            self.Bind(wx.EVT_KEY_DOWN, self.key_handler)
            for child in self.GetAllChildren():
                child.Bind(wx.EVT_KEY_DOWN, self.key_handler)
                child.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)

            self.toggle_btn.Bind(wx.EVT_BUTTON, self.toggle_draw)

            self.Bind(wx.EVT_SIZE, self.OnSize)
        else:
            bg.Sizer.Add((0, 16))
        self.Sizer.SetSizeHints(self)
        self.Sizer.Layout()

    def OnSize(self, event):
        if self.canvas.last_draw:
            wx.CallAfter(self.canvas._DrawCanvas, self.canvas.last_draw[0])
        event.Skip()

    def OnWheel(self, event):
        """Mousewheel zoom"""
        if event.WheelRotation < 0:
            direction = 1.0
        else:
            direction = -1.0
        self.canvas.zoom(direction)

    def key_handler(self, event):
        """Keyboard zoom"""
        key = event.GetKeyCode()
        if key in (43, wx.WXK_NUMPAD_ADD):
            # + key zoom in
            self.canvas.zoom(-1)
        elif key in (45, wx.WXK_NUMPAD_SUBTRACT):
            # - key zoom out
            self.canvas.zoom(1)
        else:
            event.Skip()

    def draw(self, objects, title="", xlabel=" ", ylabel=" "):
        """Draw objects to plot"""
        graphics = plot.PlotGraphics(objects, title, xlabel, ylabel)
        self.canvas.Draw(graphics, self.canvas.axis_x, self.canvas.axis_y)
        if self.is_ccss:
            self.canvas.OnMouseDoubleClick(None)

    def draw_ccxx(self):
        """Spectra or matrix 'flower' plot"""
        self.canvas.SetEnableLegend(False)
        self.canvas.proportional = not self.is_ccss
        self.canvas.axis_x = self.ccxx_axis_x
        self.canvas.axis_y = self.ccxx_axis_y
        if self.is_ccss:
            self.canvas.spec_x = self.spec_x
            self.canvas.spec_y = self.spec_y
            self.canvas.SetXSpec(self.spec_x)
            self.canvas.SetYSpec(self.spec_y)
        self.draw(self.gfx, " ")

    def draw_cie(self):
        """CIE 1931 2° xy plot"""
        self.canvas.SetEnableLegend(True)
        self.canvas.proportional = True
        gfx = []
        # Add a few points at the extremes to define a bounding box
        gfx.append(plot.PolyLine([(0, -0.025), (1, 1)], colour=wx.Colour(0, 0, 0, 0)))
        # Add CIE 1931 outline
        gfx.append(
            plot.PolySpline(
                colormath.cie1931_2_xy, colour=wx.Colour(102, 102, 102, 153), width=1.75
            )
        )
        gfx.append(
            plot.PolyLine(
                [colormath.cie1931_2_xy[0], colormath.cie1931_2_xy[-1]],
                colour=wx.Colour(102, 102, 102, 153),
                width=1.75,
            )
        )
        # Add comparison gamuts
        for rgb_space, pen_style in [
            ("Rec. 2020", wx.SOLID),
            ("Adobe RGB (1998)", wx.SHORT_DASH),
            ("DCI P3", wx.DOT_DASH),
            ("Rec. 709", wx.DOT),
        ]:
            values = []
            for R, G, B in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
                values.append(colormath.RGB2xyY(R, G, B, rgb_space)[:2])
            values.append(values[0])
            gfx.append(
                plot.PolyLine(
                    values,
                    colour=wx.Colour(102, 102, 102, 255),
                    legend=rgb_space.replace(" (1998)", ""),
                    width=2,
                    style=pen_style,
                )
            )
        # Add points
        for i, (XYZ, _values, _attrs) in enumerate(self.samples):
            if len(XYZ) != 3:
                continue
            xy = colormath.XYZ2xyY(*XYZ)[:2]
            gfx.append(
                plot.PolyMarker(
                    [colormath.XYZ2xyY(*XYZ)[:2]],
                    colour=wx.Colour(*self.gfx[i].attributes["colour"]),
                    size=2,
                    width=1.75,
                    marker="plus",
                    legend="%.4f\u2009x\u2002%.4f\u2009y" % xy,
                )
            )
        self.canvas.axis_x = 0, 1
        self.canvas.axis_y = 0, 1
        self.canvas.spec_x = 10
        self.canvas.spec_y = 10
        self.canvas.SetXSpec(10)
        self.canvas.SetYSpec(10)
        self.draw(gfx, " ", "x", "y")

    def toggle_draw(self, event):
        """Toggle between spectral and CIE plot"""
        if self.canvas.GetEnableLegend():
            self.draw_ccxx()
            self.toggle_btn.SetLabel(lang.getstr("spectral"))
        else:
            self.draw_cie()
            self.toggle_btn.SetLabel(lang.getstr("whitepoint.xy"))
