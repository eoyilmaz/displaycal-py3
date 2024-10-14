# -*- coding: utf-8 -*-

import math
import os
import re
import sys

from DisplayCAL import (
    ICCProfile as ICCP,
    colormath,
    config,
    localization as lang,
    wxenhancedplot as plot,
)
from DisplayCAL.argyll_cgats import cal_to_fake_profile, vcgt_to_cal
from DisplayCAL.config import (
    fs_enc,
    get_argyll_display_number,
    get_data_path,
    get_display_profile,
    get_display_rects,
    get_verified_path,
    getcfg,
    geticon,
    setcfg,
)
from DisplayCAL.meta import (
    name as appname,
)
from DisplayCAL.options import debug
from DisplayCAL.util_decimal import float2dec
from DisplayCAL.util_os import waccess
from DisplayCAL.worker import (
    Error,
    UnloggedError,
    Worker,
    make_argyll_compatible_path,
    show_result_dialog,
)
from DisplayCAL.wxMeasureFrame import MeasureFrame
from DisplayCAL.wxaddons import get_platform_window_decoration_size, wx
from DisplayCAL.wxfixes import (
    GenBitmapButton as BitmapButton,
    wx_Panel,
)
from DisplayCAL.wxwindows import (
    BaseApp,
    BaseFrame,
    BitmapBackgroundPanelText,
    BitmapBackgroundPanelTextGamut,
    CustomCheckBox,
    FileDrop,
    InfoDialog,
    TooltipWindow,
)

import numpy

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#444444"

if sys.platform == "darwin":
    FONTSIZE_LARGE = 11
    FONTSIZE_SMALL = 10
else:
    FONTSIZE_LARGE = 9
    FONTSIZE_SMALL = 8


class CoordinateType(list):
    """List of coordinates.

    [(Y, x)] where Y is in the range 0..100 and x in the range 0..255

    """

    def __init__(self, profile=None):
        super(CoordinateType, self).__init__()
        self.profile = profile
        self._transfer_function = {}

    def get_gamma(
        self, use_vmin_vmax=False, average=True, least_squares=False, slice=(0.01, 0.99)
    ):
        """Return average or least squares gamma or a list of gamma values"""
        if len(self):
            start = slice[0] * 100
            end = slice[1] * 100
            values = []
            for i, (y, x) in enumerate(self):
                n = colormath.XYZ2Lab(0, y, 0)[0]
                if start <= n <= end:
                    values.append((x / 255.0 * 100, y))
        else:
            # Identity
            if average or least_squares:
                return 1.0
            return [1.0]
        vmin = 0
        vmax = 100.0
        if use_vmin_vmax:
            if len(self) > 2:
                vmin = self[0][0]
                vmax = self[-1][0]
        return colormath.get_gamma(values, 100.0, vmin, vmax, average, least_squares)

    def get_transfer_function(self, best=True, slice=(0.05, 0.95), outoffset=None):
        """Return transfer function name, exponent and match percentage"""
        transfer_function = self._transfer_function.get((best, slice))
        if transfer_function:
            return transfer_function
        xp = []
        fp = []
        for y, x in self:
            xp.append(x)
            fp.append(y)
        interp = colormath.Interp(xp, fp, use_numpy=True)
        otrc = ICCP.CurveType(profile=self.profile)
        for i in range(len(self)):
            otrc.append(interp(i / (len(self) - 1.0) * 255) / 100 * 65535)
        match = otrc.get_transfer_function(best, slice, outoffset=outoffset)
        self._transfer_function[(best, slice)] = match
        return match

    def set_trc(self, power=2.2, values=(), vmin=0, vmax=100):
        """Set the response to a certain function.

        Positive power, or -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
        -601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
        identical)

        """
        self[:] = [[y, x] for y, x in values]
        for i in range(len(self)):
            self[i][0] = vmin + colormath.specialpow(self[i][1] / 255.0, power) * (
                vmax - vmin
            )


class PolyBox(plot.PolyLine):
    def __init__(self, x, y, w, h, **attr):
        plot.PolyLine.__init__(
            self, [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], **attr
        )


class LUTCanvas(plot.PlotCanvas):
    def __init__(self, *args, **kwargs):
        self.colors = {
            "RGB_R": "red",
            "RGB_G": "#00FF00",
            "RGB_B": "#0080FF",
            "CMYK_C": "cyan",
            "CMYK_M": "magenta",
            "CMYK_Y": "yellow",
            "CMYK_K": "black",
            "nCLR_0": "cyan",
            "nCLR_1": "magenta",
            "nCLR_2": "yellow",
            "nCLR_3": "black",
            "nCLR_4": "red",
            "nCLR_5": "#00FF00",
            "nCLR_6": "blue",
            "nCLR_7": "#FF8000",
            "nCLR_8": "#80FF00",
            "nCLR_9": "#00FF80",
            "XYZ_X": "red",
            "XYZ_Y": "#00FF00",
            "XYZ_Z": "#0080FF",
            "Lab_L*": "#CCCCCC",
            "Lab_a*": "#FF0080",
            "Lab_a*-": "#00CC80",
            "Lab_b*": "#FFEE00",
            "Lab_b*-": "#0080FF",
        }
        plot.PlotCanvas.__init__(self, *args, **kwargs)
        self.Unbind(wx.EVT_SCROLL_THUMBTRACK)
        self.Unbind(wx.EVT_SCROLL_PAGEUP)
        self.Unbind(wx.EVT_SCROLL_PAGEDOWN)
        self.Unbind(wx.EVT_SCROLL_LINEUP)
        self.Unbind(wx.EVT_SCROLL_LINEDOWN)
        self.HandCursor = wx.StockCursor(wx.CURSOR_CROSS)
        self.GrabHandCursor = wx.StockCursor(wx.CURSOR_SIZING)
        self.SetBackgroundColour(BGCOLOUR)
        self.SetEnableAntiAliasing(True)
        self.SetEnableHiRes(True)
        self.SetEnableCenterLines(True)
        self.SetEnableDiagonals("Bottomleft-Topright")
        self.SetEnableDrag(True)
        self.SetEnableGrid(False)
        self.SetEnablePointLabel(True)
        self.SetEnableTitle(False)
        self.SetForegroundColour(FGCOLOUR)
        self.SetFontSizeAxis(FONTSIZE_SMALL)
        self.SetFontSizeLegend(FONTSIZE_SMALL)
        self.SetFontSizeTitle(FONTSIZE_LARGE)
        self.SetGridColour(GRIDCOLOUR)
        self.setLogScale((False, False))
        self.SetPointLabelFunc(self.DrawPointLabel)
        self.canvas.BackgroundColour = BGCOLOUR
        if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
            # Enable/disable double buffering on-the-fly to make pointlabel work
            self.canvas.Bind(wx.EVT_ENTER_WINDOW, self._disabledoublebuffer)
            self.canvas.Bind(wx.EVT_LEAVE_WINDOW, self._enabledoublebuffer)
        self.worker = Worker(self.TopLevelParent)
        self.errors = []
        self.resetzoom()

    def DrawLUT(
        self,
        vcgt=None,
        title=None,
        xLabel=None,
        yLabel=None,
        channels=None,
        colorspace=b"RGB",
        connection_colorspace=b"RGB",
    ):
        if not title:
            title = ""
        if not xLabel:
            xLabel = ""
        if not yLabel:
            yLabel = ""

        detect_increments = False
        Plot = plot.PolyLine
        Plot._attributes["width"] = 1

        maxv = 4095
        linear_points = []

        if colorspace in (b"YCbr", b"RGB", b"GRAY", b"HSV", b"HLS"):
            axis_y = 255.0
            if connection_colorspace in (b"Lab", b"XYZ"):
                axis_x = 100.0
            else:
                axis_x = 255.0
        else:
            axis_y = 100.0
            axis_x = 100.0
        if getattr(self, "axis_x", None) != (0, axis_x) or getattr(
            self, "axis_y", None
        ) != (0, axis_y):
            self.resetzoom()
            wx.CallAfter(self.center)
        self.axis_x, self.axis_y = (0, axis_x), (0, axis_y)
        if not self.last_draw:
            self.center_x = axis_x / 2.0
            self.center_y = axis_y / 2.0
        self.proportional = False
        self.spec_x = self.spec_y = 5

        lines = [PolyBox(0, 0, axis_x, axis_y, colour=GRIDCOLOUR, width=1)]

        # Use a point grid, so we can get the whole set of output values for
        # each channel for any single given input value.
        # The point grid keys are quantized to 12 bits to avoid floating point
        # inaccuracy
        self.point_grid = {}
        points = {}
        if not channels:
            channels = {}
        for channel in channels:
            channel_name = channels[channel]
            if channel_name:
                self.point_grid[channel] = {}
                points[channel] = []

        if not vcgt:
            irange = list(range(0, 256))
        elif "data" in vcgt:  # table
            data = list(vcgt["data"])
            while len(data) < len(channels):
                data.append(data[0])
            if not isinstance(vcgt, ICCP.VideoCardGammaTableType) and not isinstance(
                data[0], ICCP.CurveType
            ):
                # Coordinate list
                irange = list(range(0, len(data[0])))
                set_linear_points = True
                for channel in range(len(data)):
                    if channel in points:
                        for n, y in data[channel]:
                            if not detect_increments and set_linear_points:
                                linear_points.append([n, n])
                            if connection_colorspace == b"Lab":
                                n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (
                                    axis_x / 100.0
                                )
                            points[channel].append([n, y])
                            idx = int(round(n / 255.0 * 4095))
                            self.point_grid[channel][idx] = y
                        set_linear_points = False
            else:
                irange = list(range(0, vcgt["entryCount"]))
                maxv = math.pow(256, vcgt["entrySize"]) - 1
                for i in irange:
                    j = i * (axis_y / (vcgt["entryCount"] - 1))
                    if not detect_increments:
                        linear_points.append([j, j])
                    for channel in points:
                        values = points[channel]
                        n = float(data[channel][i]) / maxv * axis_x
                        if (
                            not detect_increments
                            or not values
                            or i == vcgt["entryCount"] - 1
                            or n != i
                        ):
                            if (
                                detect_increments
                                and n != i
                                and len(values) == 1
                                and i > 1
                                and values[-1][0] == values[-1][1]
                            ):
                                values.append([i - 1, i - 1])
                            if connection_colorspace == b"Lab":
                                n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (
                                    axis_x / 100.0
                                )
                            if connection_colorspace in (b"Lab", b"XYZ"):
                                values.append([n, j])
                                idx = int(round(n / 255.0 * 4095))
                                self.point_grid[channel][idx] = j
                            else:
                                values.append([j, n])
                                idx = int(round(j / 255.0 * 4095))
                                self.point_grid[channel][idx] = n
        else:  # formula
            irange = list(range(0, 256))
            step = 100.0 / axis_y
            for i in irange:
                # float2dec(v) fixes miniscule deviations in the calculated gamma
                # n = float2dec(n, 8)
                if not detect_increments:
                    linear_points.append([i, i])
                for channel, color in enumerate(("red", "green", "blue")):
                    if channel not in points:
                        continue
                    vmin = float2dec(vcgt[f"{color}Min"] * axis_x)
                    v = float2dec(math.pow(step * i / 100.0, vcgt[f"{color}Gamma"]))
                    vmax = float2dec(vcgt[f"{color}Max"] * axis_x)
                    n = vmin + v * (vmax - vmin)
                    if connection_colorspace == b"Lab":
                        n = colormath.XYZ2Lab(0, float(n) / axis_x * 100, 0)[0] * (
                            axis_x / 100.0
                        )
                    if connection_colorspace in (b"Lab", b"XYZ"):
                        points[channel].append([n, i])
                        idx = int(round(float(n) / 255.0 * 4095))
                        self.point_grid[channel][idx] = i
                    else:
                        points[channel].append([i, n])
                        idx = int(round(i / 255.0 * 4095))
                        self.point_grid[channel][idx] = float(n)

        # for n in sorted(self.point_grid[0].keys()):
        # print n, self.point_grid[0].get(n), self.point_grid[1].get(n), self.point_grid[2].get(n)

        self.entryCount = irange[-1] + 1

        linear = [[0, 0], [irange[-1], irange[-1]]]

        if not vcgt:
            for values in points.values():
                if detect_increments:
                    values[:] = linear
                else:
                    values[:] = linear_points

        # Note: We need to make sure each point is a float because it
        # might be a decimal.Decimal, which can't be divided by floats!
        self.unique = {}
        for channel in points:
            values = points[channel]
            self.unique[channel] = len(
                set(round(float(y) / axis_y * irange[-1]) for x, y in values)
            )

        legend = []
        color = "white"

        if len(points) > 1:
            values0 = list(points.values())[0]
            # identical = all(values == values0
            # for values in points.itervalues())
            identical = all(
                all(
                    x == values0[i][0] and abs(y - values0[i][1]) < 0.005
                    for i, (x, y) in enumerate(values)
                )
                for values in points.values()
            )
        else:
            identical = False

        if identical:
            channels_label = "".join(list(channels.values()))
            color = self.get_color(channels_label, color)
        for channel_name in list(channels.values()):
            if channel_name:
                legend.append(channel_name)
        linear_points = [(i, int(round(v / axis_y * maxv))) for i, v in linear_points]
        seen_values = []
        seen_labels = []
        for channel in points:
            values = points[channel]
            channel_label = channels[channel]
            if not identical:
                color = self.colors.get(
                    f"{colorspace.decode('utf-8')}_{channel_label}", "white"
                )
            # Note: We need to make sure each point is a float because it
            # might be a decimal.Decimal, which can't be divided by floats!
            points_quantized = [
                (i, int(round(float(v) / axis_y * maxv))) for i, v in values
            ]
            line2 = None
            if identical:
                label = "=".join(legend)
                suffix = (
                    (", {}".format(lang.getstr("linear").capitalize()))
                    if points_quantized
                    == (linear if detect_increments else linear_points)
                    else ""
                )
            else:
                label = channel_label
                suffix = ""
                if channel_label in ("a*", "b*") and len(values) > 1:
                    half = len(values) / 2
                    values2 = values[:half]
                    values = values[half:]
                    center_x = (values[0][0] + values2[-1][0]) / 2.0
                    center_y = (values[0][1] + values2[-1][1]) / 2.0
                    center = [center_x, center_y]
                    if values[0] != center:
                        values.insert(0, center)
                    if values2[-1] != center:
                        values2.append(center)
                    idx = int(round(center_x / 255.0 * 4095))
                    self.point_grid[channel][idx] = center_y
                    color2 = self.colors["Lab_%s-" % channel_label]
                    line2 = Plot(values2, legend=label + suffix, colour=color2)
                elif seen_values:
                    # Check if same line (+- 0.005 tolerance) has been seen
                    for idx, seen in enumerate(seen_values):
                        match = True
                        for i, (x, y) in enumerate(seen):
                            if x != values[i][0] or abs(y - values[i][1]) > 0.005:
                                match = False
                                break
                        if match:
                            break
                    else:
                        match = False
                    if match:
                        seen_label = seen_labels[idx]
                        lines[idx + 1].attributes["colour"] = self.get_color(
                            seen_label + channel_label
                        )
                        continue
            line = Plot(values, legend=label + suffix, colour=color)
            if (colorspace == "CMYK" and label == "K") or (
                colorspace == "Lab" and label in ("a*", "b*")
            ):
                # CMYK -> KCMY, Lab -> baL for better visibilty
                lines.insert(1, line)
                seen_values.insert(0, values)
                seen_labels.insert(0, label)
                if line2:
                    lines.insert(1, line2)
            else:
                lines.append(line)
                seen_values.append(values)
                seen_labels.append(label)
                if line2:
                    lines.append(line2)
            if identical:
                break

        self._DrawCanvas(
            plot.PlotGraphics(
                lines,
                title,
                " ".join([xLabel, lang.getstr("in")]),
                " ".join([yLabel, lang.getstr("out")]),
            )
        )

    def get_color(self, channels_label, default="white"):
        if channels_label in ("RGB", "CMYK", "XYZ"):
            return "white"
        elif channels_label in ("RG", "XY"):
            return "yellow"
        elif channels_label in ("RB", "XZ"):
            return "magenta"
        elif channels_label in ("GB", "YZ"):
            return "cyan"
        elif channels_label == "CM":
            return "#0080FF"
        elif channels_label == "CY":
            return "#00FF00"
        elif channels_label == "MY":
            return "red"
        return default

    def DrawPointLabel(self, dc, mDataDict):
        """Draw point labels.

        dc - DC that will be passed
        mDataDict - Dictionary of data that you want to use for the pointLabel

        """
        if not self.last_draw:
            return
        graphics, xAxis, yAxis = self.last_draw
        # sizes axis to axis type, create lower left and upper right corners of plot
        if xAxis is None or yAxis is None:
            # One or both axis not specified in Draw
            p1, p2 = graphics.boundingBox()  # min, max points of graphics
            if xAxis is None:
                xAxis = self._axisInterval(self._xSpec, p1[0], p2[0])  # in user units
            if yAxis is None:
                yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
            # Adjust bounding box for axis spec
            p1[0], p1[1] = (
                xAxis[0],
                yAxis[0],
            )  # lower left corner user scale (xmin,ymin)
            p2[0], p2[1] = (
                xAxis[1],
                yAxis[1],
            )  # upper right corner user scale (xmax,ymax)
        else:
            # Both axis specified in Draw
            p1 = numpy.array(
                [xAxis[0], yAxis[0]]
            )  # lower left corner user scale (xmin,ymin)
            p2 = numpy.array(
                [xAxis[1], yAxis[1]]
            )  # upper right corner user scale (xmax,ymax)
        ptx, pty, rectWidth, rectHeight = self._point2ClientCoord(p1, p2)
        # allow graph to overlap axis lines by adding units to width and height
        dc.SetClippingRegion(
            int(ptx), int(pty), int(rectWidth + 2), int(rectHeight + 2)
        )

        dc.SetPen(wx.Pen(wx.WHITE, 1, wx.DOT))
        dc.SetBrush(wx.Brush(wx.WHITE, wx.SOLID))

        sx, sy = mDataDict["scaledXY"]  # Scaled x, y of closest point
        dc.DrawLine(0, int(sy), int(ptx + rectWidth + 2), int(sy))
        dc.DrawLine(int(sx), 0, int(sx), int(pty + rectHeight + 2))

    def GetClosestPoints(self, pntXY, pointScaled=True):
        """Returns list with
        [curveNumber, legend, index of closest point, pointXY, scaledXY, distance]
        list for each curve.
        Returns [] if no curves are being plotted.

        x, y in user coords
        if pointScaled == True based on screen coords
        if pointScaled == False based on user coords
        """
        if self.last_draw is None:
            # no graph available
            return []
        graphics, xAxis, yAxis = self.last_draw
        l = []
        for curveNum, obj in enumerate(graphics):
            # check there are points in the curve
            if len(obj.points) == 0 or isinstance(obj, PolyBox):
                continue  # go to next obj
            # [curveNumber, legend, index of closest point, pointXY, scaledXY, distance]
            cn = (
                [curveNum] + [obj.getLegend()] + obj.getClosestPoint(pntXY, pointScaled)
            )
            l.append(cn)
        return l

    def _disabledoublebuffer(self, event):
        window = self
        while window:
            if not isinstance(window, wx.TopLevelWindow):
                window.SetDoubleBuffered(False)
            window = window.Parent
        event.Skip()

    def _enabledoublebuffer(self, event):
        window = self
        while window:
            if not isinstance(window, wx.TopLevelWindow):
                window.SetDoubleBuffered(True)
            window = window.Parent
        event.Skip()

    def OnMouseDoubleClick(self, event):
        if self.last_draw:
            boundingbox = self.last_draw[0].boundingBox()
        else:
            boundingbox = None
        self.resetzoom(boundingbox=boundingbox)
        if self.last_draw:
            self.center()

    def OnMouseLeftDown(self, event):
        self.erase_pointlabel()
        self._zoomCorner1[0], self._zoomCorner1[1] = self._getXY(event)
        self._screenCoordinates = numpy.array(event.GetPosition())
        if self._dragEnabled:
            self.SetCursor(self.GrabHandCursor)
            self.canvas.CaptureMouse()

    def OnMouseLeftUp(self, event):
        if self._dragEnabled:
            self.SetCursor(self.HandCursor)
            if self.canvas.HasCapture():
                self.canvas.ReleaseMouse()
                self._set_center()
        if hasattr(self.TopLevelParent, "OnMotion"):
            self.TopLevelParent.OnMotion(event)

    def _DrawCanvas(self, graphics):
        """Draw proportionally correct, center and zoom"""
        w = float(self.GetSize()[0] or 1)
        h = float(self.GetSize()[1] or 1)
        if w > 45:
            w -= 45
        if h > 20:
            h -= 20
        ratio = [w / h, h / w]
        axis_x, axis_y = self.axis_x, self.axis_y
        spec_x = self.spec_x
        spec_y = self.spec_y
        if self._zoomfactor < 1:
            while spec_x * self._zoomfactor < self.spec_x / 2.0:
                spec_x *= 2
            while spec_y * self._zoomfactor < self.spec_y / 2.0:
                spec_y *= 2
        else:
            while spec_x * self._zoomfactor > self.spec_x * 2:
                spec_x /= 2
            while spec_y * self._zoomfactor > self.spec_y * 2:
                spec_y /= 2
        if self.proportional:
            if ratio[0] > ratio[1]:
                self.SetXSpec(spec_x * self._zoomfactor * ratio[0])
            else:
                self.SetXSpec(spec_x * self._zoomfactor)
            if ratio[0] > 1:
                axis_x = tuple([v * ratio[0] for v in axis_x])
            if ratio[1] > ratio[0]:
                self.SetYSpec(spec_y * self._zoomfactor * ratio[1])
            else:
                self.SetYSpec(spec_y * self._zoomfactor)
            if ratio[1] > 1:
                axis_y = tuple([v * ratio[1] for v in axis_y])
        else:
            self.SetXSpec(spec_x * self._zoomfactor)
            self.SetYSpec(spec_y * self._zoomfactor)
        x, y = self.center_x, self.center_y
        w = (axis_x[1] - axis_x[0]) * self._zoomfactor
        h = (axis_y[1] - axis_y[0]) * self._zoomfactor
        axis_x = (x - w / 2, x + w / 2)
        axis_y = (y - h / 2, y + h / 2)
        self.Draw(graphics, axis_x, axis_y)

    def _set_center(self):
        """Set center position from current X and Y axis"""
        if not self.last_draw:
            return
        axis_x = self.GetXCurrentRange()
        axis_y = self.GetYCurrentRange()
        if axis_x[0] < 0:
            if axis_x[1] < 0:
                x = axis_x[0] + (abs(axis_x[0]) - abs(axis_x[1])) / 2.0
            else:
                x = axis_x[0] + (abs(axis_x[1]) + abs(axis_x[0])) / 2.0
        else:
            x = axis_x[0] + (abs(axis_x[1]) - abs(axis_x[0])) / 2.0
        if axis_y[0] < 0:
            if axis_y[1] < 0:
                y = axis_y[0] + (abs(axis_y[0]) - abs(axis_y[1])) / 2.0
            else:
                y = axis_y[0] + (abs(axis_y[1]) + abs(axis_y[0])) / 2.0
        else:
            y = axis_y[0] + (abs(axis_y[1]) - abs(axis_y[0])) / 2.0
        self.center_x, self.center_y = x, y

    def center(self, boundingbox=None):
        """Center the current graphic"""
        if boundingbox:
            # Min, max points of graphics
            p1, p2 = boundingbox
            # In user units
            min_x, max_x = self._axisInterval(self._xSpec, p1[0], p2[0])
            min_y, max_y = self._axisInterval(self._ySpec, p1[1], p2[1])
        else:
            min_x, max_x = self.GetXMaxRange()
            min_y, max_y = self.GetYMaxRange()
        self.center_x = 0 + sum((min_x, max_x)) / 2.0
        self.center_y = 0 + sum((min_y, max_y)) / 2.0
        if not boundingbox:
            self.erase_pointlabel()
            self._DrawCanvas(self.last_draw[0])

    def erase_pointlabel(self):
        if self.GetEnablePointLabel() and self.last_PointLabel:
            # Erase point label
            self._drawPointLabel(self.last_PointLabel)
            self.last_PointLabel = None

    def resetzoom(self, boundingbox=None):
        self.center_x = 0
        self.center_y = 0
        self._zoomfactor = 1.0
        if boundingbox:
            # Min, max points of graphics
            p1, p2 = boundingbox
            # In user units
            min_x, max_x = self._axisInterval(self._xSpec, p1[0], p2[0])
            min_y, max_y = self._axisInterval(self._ySpec, p1[1], p2[1])
            max_abs_x = abs(min_x) + max_x
            max_abs_y = abs(min_y) + max_y
            max_abs_axis_x = abs(self.axis_x[0]) + self.axis_x[1]
            max_abs_axis_y = abs(self.axis_y[0]) + self.axis_y[1]
            w = float(self.GetSize()[0] or 1)
            h = float(self.GetSize()[1] or 1)
            if w > 45:
                w -= 45
            if h > 20:
                h -= 20
            ratio = [w / h, h / w]
            if ratio[0] > 1:
                max_abs_axis_x *= ratio[0]
            if ratio[1] > 1:
                max_abs_axis_y *= ratio[1]
            if max_abs_x / max_abs_y > max_abs_axis_x / max_abs_axis_y:
                self._zoomfactor = max_abs_x / max_abs_axis_x
            else:
                self._zoomfactor = max_abs_y / max_abs_axis_y

    def zoom(self, direction=1.0):
        _zoomfactor = 0.025 * direction
        if 0 < self._zoomfactor + _zoomfactor <= 5:
            self._zoomfactor += _zoomfactor
            self._set_center()
            self.erase_pointlabel()
            self._DrawCanvas(self.last_draw[0])


class LUTFrame(BaseFrame):
    """LUTFrame."""

    def __init__(self, *args, **kwargs):
        if len(args) < 3 and "title" not in kwargs:
            kwargs["title"] = lang.getstr("calibration.lut_viewer.title")
        if "name" not in kwargs:
            kwargs["name"] = "lut_viewer"

        BaseFrame.__init__(self, *args, **kwargs)

        self.SetIcons(
            config.get_icon_bundle([256, 48, 32, 16], f"{appname}-curve-viewer")
        )

        self.profile = None
        self.xLabel = lang.getstr("in")
        self.yLabel = lang.getstr("out")

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

        panel = wx_Panel(self)
        panel.SetBackgroundColour(BGCOLOUR)
        self.sizer.Add(panel, flag=wx.EXPAND)
        panel.SetSizer(wx.FlexGridSizer(0, 5, 0, 8))
        panel.Sizer.AddGrowableCol(0)
        panel.Sizer.AddGrowableCol(4)

        panel.Sizer.Add((1, 1))
        panel.Sizer.Add((1, 12))
        panel.Sizer.Add((1, 12))
        panel.Sizer.Add((1, 12))
        panel.Sizer.Add((1, 1))

        panel.Sizer.Add((1, 1))

        self.plot_mode_select = wx.Choice(panel, -1, size=(-1, -1), choices=[])
        panel.Sizer.Add(self.plot_mode_select, flag=wx.ALIGN_CENTER_VERTICAL)
        self.Bind(
            wx.EVT_CHOICE,
            self.plot_mode_select_handler,
            id=self.plot_mode_select.GetId(),
        )

        self.tooltip_btn = BitmapButton(
            panel, -1, geticon(16, "question-inverted"), style=wx.NO_BORDER
        )
        self.tooltip_btn.SetBackgroundColour(BGCOLOUR)
        self.tooltip_btn.Bind(wx.EVT_BUTTON, self.tooltip_handler)
        self.tooltip_btn.SetToolTipString(lang.getstr("gamut_plot.tooltip"))
        panel.Sizer.Add(self.tooltip_btn, flag=wx.ALIGN_CENTER_VERTICAL)

        self.save_plot_btn = BitmapButton(
            panel, -1, geticon(16, "image-x-generic-inverted"), style=wx.NO_BORDER
        )
        self.save_plot_btn.SetBackgroundColour(BGCOLOUR)
        panel.Sizer.Add(self.save_plot_btn, flag=wx.ALIGN_CENTER_VERTICAL)
        self.save_plot_btn.Bind(wx.EVT_BUTTON, self.SaveFile)
        self.save_plot_btn.SetToolTipString(
            f"{lang.getstr('save_as')} (*.bmp, *.xbm, *.xpm, *.jpg, *.png)"
        )
        self.save_plot_btn.Disable()

        panel.Sizer.Add((1, 1))

        panel.Sizer.Add((1, 1))
        panel.Sizer.Add((1, 4))
        panel.Sizer.Add((1, 4))
        panel.Sizer.Add((1, 4))
        panel.Sizer.Add((1, 1))

        self.client = LUTCanvas(self)
        self.sizer.Add(self.client, 1, wx.EXPAND)

        self.box_panel = wx_Panel(self)
        self.box_panel.SetBackgroundColour(BGCOLOUR)
        self.sizer.Add(self.box_panel, flag=wx.EXPAND)

        self.status = BitmapBackgroundPanelText(self, name="statuspanel")
        self.gamut_status = BitmapBackgroundPanelTextGamut(self, name="statuspanel")
        self.status.SetMaxFontSize(11)
        self.status.label_y = 8
        self.status.textshadow = False
        self.status.SetBackgroundColour(BGCOLOUR)
        self.status.SetForegroundColour(FGCOLOUR)
        h = self.status.GetTextExtent("Ig")[1]
        self.status.SetMinSize((0, h * 2 + 18))
        self.sizer.Add(self.status, flag=wx.EXPAND)

        self.box_sizer = wx.FlexGridSizer(0, 3, 4, 4)
        self.box_sizer.AddGrowableCol(0)
        self.box_sizer.AddGrowableCol(2)
        self.box_panel.SetSizer(self.box_sizer)

        self.box_sizer.Add((0, 0))

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.box_sizer.Add(
            hsizer,
            # flag=wx.ALIGN_CENTER | wx.BOTTOM | wx.TOP, border=4)
            flag=wx.BOTTOM | wx.TOP,
            border=4,
        )

        self.rendering_intent_select = wx.Choice(
            self.box_panel,
            -1,
            choices=[
                lang.getstr("gamap.intents.a"),
                lang.getstr("gamap.intents.r"),
                lang.getstr("gamap.intents.p"),
                lang.getstr("gamap.intents.s"),
            ],
        )
        hsizer.Add((10, self.rendering_intent_select.Size[1]))
        hsizer.Add(self.rendering_intent_select, flag=wx.ALIGN_CENTER_VERTICAL)
        self.rendering_intent_select.Bind(
            wx.EVT_CHOICE, self.rendering_intent_select_handler
        )
        self.rendering_intent_select.SetSelection(1)

        self.direction_select = wx.Choice(
            self.box_panel,
            -1,
            choices=[
                lang.getstr("direction.backward"),
                lang.getstr("direction.forward.inverted"),
            ],
        )
        hsizer.Add(
            self.direction_select, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10
        )
        self.direction_select.Bind(wx.EVT_CHOICE, self.direction_select_handler)
        self.direction_select.SetSelection(0)

        self.show_actual_lut_cb = CustomCheckBox(
            self.box_panel, -1, lang.getstr("calibration.show_actual_lut")
        )
        self.show_actual_lut_cb.SetForegroundColour(FGCOLOUR)
        self.show_actual_lut_cb.SetMaxFontSize(11)
        hsizer.Add(
            self.show_actual_lut_cb,
            # flag=wx.ALIGN_CENTER |
            flag=wx.ALIGN_CENTER_VERTICAL,
        )
        self.show_actual_lut_cb.Bind(wx.EVT_CHECKBOX, self.show_actual_lut_handler)

        self.box_sizer.Add((0, 0))

        self.box_sizer.Add((0, 0))

        self.cbox_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.box_sizer.Add(
            self.cbox_sizer,
            # flag=wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL | wx.TOP,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP,
            border=4,
        )

        self.box_sizer.Add((0, 0))

        self.cbox_sizer.Add((10, 0))

        self.reload_vcgt_btn = BitmapButton(
            self.box_panel,
            -1,
            geticon(16, "stock_refresh-inverted"),
            style=wx.NO_BORDER,
        )
        self.reload_vcgt_btn.SetBackgroundColour(BGCOLOUR)
        self.cbox_sizer.Add(
            self.reload_vcgt_btn,
            # flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            flag=wx.ALIGN_CENTER_VERTICAL,
            border=8,
        )
        self.reload_vcgt_btn.Bind(wx.EVT_BUTTON, self.reload_vcgt_handler)
        self.reload_vcgt_btn.SetToolTipString(
            lang.getstr("calibration.load_from_display_profile")
        )
        self.reload_vcgt_btn.Disable()

        self.apply_bpc_btn = BitmapButton(
            self.box_panel, -1, geticon(16, "color-inverted"), style=wx.NO_BORDER
        )
        self.apply_bpc_btn.SetBackgroundColour(BGCOLOUR)
        self.cbox_sizer.Add(
            self.apply_bpc_btn,
            # flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            flag=wx.ALIGN_CENTER_VERTICAL,
            border=8,
        )
        self.apply_bpc_btn.Bind(wx.EVT_BUTTON, self.apply_bpc_handler)
        self.apply_bpc_btn.SetToolTipString(lang.getstr("black_point_compensation"))
        self.apply_bpc_btn.Disable()

        self.install_vcgt_btn = BitmapButton(
            self.box_panel, -1, geticon(16, "install-inverted"), style=wx.NO_BORDER
        )
        self.install_vcgt_btn.SetBackgroundColour(BGCOLOUR)
        self.cbox_sizer.Add(
            self.install_vcgt_btn,
            # flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            flag=wx.ALIGN_CENTER_VERTICAL,
            border=8,
        )
        self.install_vcgt_btn.Bind(wx.EVT_BUTTON, self.install_vcgt_handler)
        self.install_vcgt_btn.SetToolTipString(lang.getstr("apply_cal"))
        self.install_vcgt_btn.Disable()

        self.save_vcgt_btn = BitmapButton(
            self.box_panel,
            -1,
            geticon(16, "document-save-as-inverted"),
            style=wx.NO_BORDER,
        )
        self.save_vcgt_btn.SetBackgroundColour(BGCOLOUR)
        self.cbox_sizer.Add(
            self.save_vcgt_btn,
            # flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            flag=wx.ALIGN_CENTER_VERTICAL,
            border=20,
        )
        self.save_vcgt_btn.Bind(wx.EVT_BUTTON, self.SaveFile)
        self.save_vcgt_btn.SetToolTipString(f"{lang.getstr('save_as')} (*.cal)")
        self.save_vcgt_btn.Disable()

        self.show_as_L = CustomCheckBox(self.box_panel, -1, "L* \u2192")
        self.show_as_L.SetForegroundColour(FGCOLOUR)
        self.show_as_L.SetMaxFontSize(11)
        self.show_as_L.SetValue(True)
        self.cbox_sizer.Add(
            self.show_as_L,
            # flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            flag=wx.ALIGN_CENTER_VERTICAL,
            border=4,
        )
        self.show_as_L.Bind(wx.EVT_CHECKBOX, self.DrawLUT)

        self.add_toggles(self.box_panel, self.cbox_sizer)

        self.toggle_clut = CustomCheckBox(self.box_panel, -1, "LUT")
        self.toggle_clut.SetForegroundColour(FGCOLOUR)
        self.toggle_clut.SetMaxFontSize(11)
        self.cbox_sizer.Add(
            self.toggle_clut,
            # flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            flag=wx.ALIGN_CENTER_VERTICAL,
            border=16,
        )
        self.toggle_clut.Bind(wx.EVT_CHECKBOX, self.toggle_clut_handler)

        self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)

        self.droptarget = FileDrop(self)
        self.droptarget.drophandlers = {
            ".cal": self.drop_handler,
            ".icc": self.drop_handler,
            ".icm": self.drop_handler,
        }
        self.client.SetDropTarget(self.droptarget)

        border, titlebar = get_platform_window_decoration_size()
        self.MinSize = (
            config.defaults["size.lut_viewer.w"] + border * 2,
            config.defaults["size.lut_viewer.h"] + titlebar + border,
        )
        self.SetSaneGeometry(
            getcfg("position.lut_viewer.x"),
            getcfg("position.lut_viewer.y"),
            getcfg("size.lut_viewer.w"),
            getcfg("size.lut_viewer.h"),
        )

        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        children = self.GetAllChildren()

        self.Bind(wx.EVT_KEY_DOWN, self.key_handler)
        for child in children:
            if isinstance(child, wx.Choice):
                child.SetMaxFontSize(11)
            child.Bind(wx.EVT_KEY_DOWN, self.key_handler)
            child.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
            if (
                sys.platform == "win32"
                and sys.getwindowsversion() >= (6,)
                and isinstance(child, wx.Panel)
            ):
                # No need to enable double buffering under Linux and Mac OS X.
                # Under Windows, enabling double buffering on the panel seems
                # to work best to reduce flicker.
                child.SetDoubleBuffered(True)

        self.display_no = -1
        self.display_rects = get_display_rects()

    def apply_bpc_handler(self, event):
        cal = vcgt_to_cal(self.profile)
        cal.filename = self.profile.fileName or ""
        cal.apply_bpc(weight=True)
        self.LoadProfile(cal_to_fake_profile(cal))

    def drop_handler(self, path):
        """Drag'n'drop handler for .cal/.icc/.icm files."""
        filename, ext = os.path.splitext(path)
        if ext.lower() not in (".icc", ".icm"):
            profile = cal_to_fake_profile(path)
            if not profile:
                InfoDialog(
                    self,
                    msg=lang.getstr("error.file.open", path),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
                profile = None
        else:
            try:
                profile = ICCP.ICCProfile(path)
            except (IOError, ICCP.ICCProfileInvalidError):
                InfoDialog(
                    self,
                    msg=f"{lang.getstr('profile.invalid')}\n{path}",
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
                profile = None
        self.show_actual_lut_cb.SetValue(False)
        self.current_cal = profile
        self.LoadProfile(profile)

    get_display = MeasureFrame.__dict__["get_display"]

    def handle_errors(self):
        if self.client.errors:
            show_result_dialog(
                Error(
                    "\n\n".join(
                        [
                            "{}".format(e)
                            for e in set(self.client.errors)
                            if e is not None
                        ]
                    )
                ),
                self,
            )
            self.client.errors = []

    def install_vcgt_handler(self, event):
        cwd = self.worker.create_tempdir()
        if isinstance(cwd, Exception):
            show_result_dialog(cwd, self)
        else:
            cal = os.path.join(
                cwd,
                re.sub(
                    r"[\\/:*?\"<>|]+",
                    "",
                    make_argyll_compatible_path(
                        self.profile.getDescription() or "Video LUT"
                    ),
                ),
            )
            vcgt_to_cal(self.profile).write(cal)
            cmd, args = self.worker.prepare_dispwin(cal)
            if isinstance(cmd, Exception):
                show_result_dialog(cmd, self)
            elif cmd:
                result = self.worker.exec_cmd(
                    cmd, args, capture_output=True, skip_scripts=True
                )
                if isinstance(result, Exception):
                    show_result_dialog(result, self)
                elif not result:
                    show_result_dialog(Error("".join(self.worker.errors)), self)
            # Important:
            # Make sure to only delete the temporary cal file we created
            try:
                os.remove(cal)
            except Exception as exception:
                print(
                    "Warning - temporary file '%s' could not be removed: %s"
                    % (cal, exception)
                )

    def key_handler(self, event):
        # AltDown
        # CmdDown
        # ControlDown
        # GetKeyCode
        # GetModifiers
        # GetPosition
        # GetRawKeyCode
        # GetRawKeyFlags
        # GetUniChar
        # GetUnicodeKey
        # GetX
        # GetY
        # HasModifiers
        # KeyCode
        # MetaDown
        # Modifiers
        # Position
        # RawKeyCode
        # RawKeyFlags
        # ShiftDown
        # UnicodeKey
        # X
        # Y
        key = event.GetKeyCode()
        if (
            event.ControlDown() or event.CmdDown()
        ):  # CTRL (Linux/Mac/Windows) / CMD (Mac)
            if key == 83 and self.profile:  # S
                self.SaveFile()
                return
            else:
                event.Skip()
        elif key in (43, wx.WXK_NUMPAD_ADD):
            # + key zoom in
            self.client.zoom(-1)
        elif key in (45, wx.WXK_NUMPAD_SUBTRACT):
            # - key zoom out
            self.client.zoom(1)
        else:
            event.Skip()

    def direction_select_handler(self, event):
        self.toggle_clut_handler(event)

    def rendering_intent_select_handler(self, event):
        self.toggle_clut_handler(event)

    def toggle_clut_handler(self, event):
        try:
            self.lookup_tone_response_curves()
        except Exception as exception:
            import traceback

            print(traceback.format_exc())
            show_result_dialog(exception, self)
        else:
            self.trc = None
            self.DrawLUT()
            self.handle_errors()

    def tooltip_handler(self, event):
        if not hasattr(self, "tooltip_window"):
            self.tooltip_window = TooltipWindow(
                self,
                msg=event.EventObject.ToolTip.Tip,
                title=event.EventObject.TopLevelParent.Title,
                bitmap=geticon(32, "dialog-information"),
            )
        else:
            self.tooltip_window.Show()
            self.tooltip_window.Raise()

    def show_actual_lut_handler(self, event):
        setcfg("lut_viewer.show_actual_lut", int(self.show_actual_lut_cb.GetValue()))
        if hasattr(self, "current_cal"):
            profile = self.current_cal
        else:
            profile = None
        self.load_lut(profile=profile)

    def load_lut(self, profile=None):
        self.current_cal = profile
        if (
            getcfg("lut_viewer.show_actual_lut")
            and (
                self.worker.argyll_version[0:3] > [1, 1, 0]
                or (
                    self.worker.argyll_version[0:3] == [1, 1, 0]
                    and "Beta" not in self.worker.argyll_version_string
                )
            )
            and not config.is_untethered_display()
        ):
            tmp = self.worker.create_tempdir()
            if isinstance(tmp, Exception):
                show_result_dialog(tmp, self)
                return
            outfilename = os.path.join(
                tmp,
                re.sub(
                    r"[\\/:*?\"<>|]+",
                    "",
                    make_argyll_compatible_path(
                        config.get_display_name(include_geometry=True) or "Video LUT"
                    ),
                ),
            )
            result = self.worker.save_current_video_lut(
                self.worker.get_display(),
                outfilename,
                silent=not __name__ == "__main__",
            )
            if not isinstance(result, Exception) and result:
                profile = cal_to_fake_profile(outfilename)
            else:
                if isinstance(result, Exception):
                    print(result)
            # Important: lut_viewer_load_lut is called after measurements,
            # so make sure to only delete the temporary cal file we created
            try:
                os.remove(outfilename)
            except Exception as exception:
                print(
                    "Warning - temporary file '%s' could not be removed: %s"
                    % (outfilename, exception)
                )
        if profile and (
            profile.is_loaded
            or not profile.fileName
            or os.path.isfile(profile.fileName)
        ):
            if (
                not self.profile
                or self.profile.fileName != profile.fileName
                or not self.profile.isSame(profile)
            ):
                self.LoadProfile(profile)
        else:
            self.LoadProfile(None)

    def lookup_tone_response_curves(self, intent="r"):
        """Lookup Y -> RGB tone values through TRC tags or LUT"""

        profile = self.profile

        # Final number of coordinates
        if profile.connectionColorSpace == b"RGB":
            size = 256
        elif profile.connectionColorSpace == b"Lab":
            size = 1001
        else:
            size = 1024

        if hasattr(self, "rendering_intent_select"):
            intent = {0: "a", 1: "r", 2: "p", 3: "s"}.get(
                self.rendering_intent_select.GetSelection()
            )

        use_trc_tags = (
            intent == "r"
            and (
                not ("B2A0" in self.profile.tags or "A2B0" in self.profile.tags)
                or not self.toggle_clut.GetValue()
            )
            and isinstance(self.rTRC, ICCP.CurveType)
            and isinstance(self.gTRC, ICCP.CurveType)
            and isinstance(self.bTRC, ICCP.CurveType)
            and len(self.rTRC) == len(self.gTRC) == len(self.bTRC)
        )
        has_same_trc = self.rTRC == self.gTRC == self.bTRC

        if profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
            self.client.errors.append(
                Error(
                    "\n".join(
                        [
                            lang.getstr("profile.iccv4.unsupported"),
                            profile.getDescription(),
                        ]
                    )
                )
            )
            return

        if profile.colorSpace not in (
            b"RGB",
            b"GRAY",
            b"CMYK",
        ) or profile.connectionColorSpace not in (b"Lab", b"XYZ", b"RGB"):
            if profile.colorSpace not in (b"RGB", b"GRAY", b"CMYK"):
                unsupported_colorspace = profile.colorSpace
            else:
                unsupported_colorspace = profile.connectionColorSpace
            self.client.errors.append(
                Error(
                    lang.getstr(
                        "profile.unsupported",
                        (profile.profileClass, unsupported_colorspace),
                    )
                )
            )
            return

        if profile.colorSpace == b"GRAY":
            direction = "b"
        elif profile.connectionColorSpace == b"RGB":
            direction = "f"
        elif "B2A0" in profile.tags:
            direction = {0: "b", 1: "if", 2: "f", 3: "ib"}.get(
                self.direction_select.GetSelection()
            )
        else:
            direction = "if"

        # Prepare input Lab values
        XYZ_triplets = []
        Lab_triplets = []
        devicevalues = []
        for i in range(0, size):
            if direction in ("b", "if"):
                if intent == "a":
                    # For display profiles, identical to relcol
                    # For print profiles, makes max L* match paper white
                    XYZwp_ir = list(profile.tags.wtpt.ir.values())
                    Labwp_ir = profile.tags.wtpt.ir.Lab
                    XYZwp_D50 = colormath.Lab2XYZ(Labwp_ir[0], 0, 0)
                    X, Y, Z = colormath.Lab2XYZ(
                        min(i * (100.0 / (size - 1)), Labwp_ir[0]), 0, 0
                    )
                    L, a, b = colormath.XYZ2Lab(
                        *[
                            v * 100
                            for v in colormath.adapt(X, Y, Z, XYZwp_D50, XYZwp_ir)
                        ]
                    )
                else:
                    L = i * (100.0 / (size - 1))
                    a = b = 0
                Lab_triplets.append([L, a, b])
            else:
                devicevalues.append([i * (1.0 / (size - 1))] * len(profile.colorSpace))
        if profile.colorSpace == "GRAY":
            use_icclu = True
            pcs = "x"
            for Lab in Lab_triplets:
                XYZ_triplets.append(colormath.Lab2XYZ(*Lab))
        elif profile.connectionColorSpace == b"RGB":
            use_icclu = False
            pcs = None
            intent = None
        else:
            use_icclu = False
            pcs = "l"
        if direction in ("b", "if"):
            if pcs == "l":
                idata = Lab_triplets
            else:
                idata = XYZ_triplets
        else:
            idata = devicevalues

        order = {True: "n", False: "r"}.get(
            ("B2A0" in self.profile.tags or "A2B0" in self.profile.tags)
            and self.toggle_clut.GetValue()
        )

        # Lookup values through 'input' profile using xicclu
        try:
            odata = self.worker.xicclu(
                profile,
                idata,
                intent,
                direction,
                order,
                pcs,
                use_icclu=use_icclu,
                get_clip=direction == "if",
            )
        except Exception as exception:
            self.client.errors.append(Error(exception))

        if self.client.errors:
            return

        if direction in ("b", "if") or profile.connectionColorSpace == b"RGB":
            if direction == "if" and profile.colorSpace == b"RGB":
                Lbp = self.worker.xicclu(
                    profile, [[0, 0, 0]], intent, "f", order, "l", use_icclu=use_icclu
                )[0][0]
                maxval = size - 1.0

                # Deal with values that got clipped (below black as well as white)
                # XXX: We should not clip these when plotting, because our input
                # values are all a = b = 0
                do_low_clip = False
                make_mono = True
                # Keep the max amount of useful information from Lbp onwards
                mono_end = 0
                for i, values in enumerate(odata):
                    if values[3] is True or i == 0:
                        if (do_low_clip and (i / maxval * 100 < Lbp or i == 0)) or (
                            make_mono and i == 0
                        ):
                            # Set to black
                            values[:] = [0.0, 0.0, 0.0]
                        elif i == maxval and [round(v, 4) for v in values[:3]] == [
                            1,
                            1,
                            1,
                        ]:
                            # Set to white
                            values[:] = [1.0, 1.0, 1.0]
                        elif i / maxval * 100 < Lbp:
                            mono_end = i + 2
                    else:
                        # First non-clipping value disables low clipping
                        do_low_clip = False
                    if len(values) > 3:
                        values.pop()

                if mono_end and mono_end < len(odata):
                    # Make segment from first non-zero value to Lbp
                    # monotonically increasing
                    mono = [[], [], []]
                    for i, values in enumerate(odata):
                        for j in range(3):
                            mono[j].append(values[j])
                    for j, values in enumerate(mono):
                        for i, v in enumerate(values):
                            if v:
                                break
                        if i:
                            i -= 1
                        if i + 2 < mono_end:
                            mono[j][i:mono_end] = (
                                colormath.make_monotonically_increasing(
                                    values[i:mono_end]
                                )
                            )
                    odata = []
                    for i in range(len(mono[0])):
                        values = []
                        for j in range(3):
                            values.append(mono[j][i])
                        odata.append(values)

            devicevalues = odata
        else:
            Lab_triplets = odata

        if profile.colorSpace in (b"RGB", b"GRAY"):
            maxv = 255
        else:
            maxv = 100
        self.rTRC = CoordinateType(self.profile)
        self.gTRC = CoordinateType(self.profile)
        self.bTRC = CoordinateType(self.profile)
        self.kTRC = CoordinateType(self.profile)
        for j, sample in enumerate(devicevalues):
            for i, v in enumerate(sample):
                v = min(v, 1.0)
                if (
                    not v
                    and j < len(devicevalues) - 1
                    and not min(devicevalues[j + 1][i], 1.0)
                ):
                    continue
                v *= maxv
                if profile.connectionColorSpace == b"RGB":
                    x = j / (size - 1.0) * maxv
                    if i == 0:
                        self.rTRC.append([x, v])
                    elif i == 1:
                        self.gTRC.append([x, v])
                    elif i == 2:
                        self.bTRC.append([x, v])
                else:
                    X, Y, Z = colormath.Lab2XYZ(*Lab_triplets[j], **{"scale": 100})
                    if direction in ("b", "if"):
                        X = Z = Y
                    elif intent == "a":
                        wp = list(profile.tags.wtpt.ir.values())
                        X, Y, Z = colormath.adapt(X, Y, Z, wp, (1, 1, 1))
                    elif intent != "a":
                        wp = list(profile.tags.wtpt.ir.values())
                        X, Y, Z = colormath.adapt(X, Y, Z, "D50", (1, 1, 1))
                    if i == 0:
                        self.rTRC.append([X, v])
                    elif i == 1:
                        self.gTRC.append([Y, v])
                    elif i == 2:
                        self.bTRC.append([Z, v])
                    elif i == 3:
                        self.kTRC.append([Y, v])
        if profile.connectionColorSpace == b"RGB":
            return
        if use_trc_tags:
            if has_same_trc:
                self.bTRC = self.gTRC = self.rTRC
            return
        # Generate interpolated TRCs for transfer function detection
        prev = None
        for sig in ("rTRC", "gTRC", "bTRC", "kTRC"):
            x, xp, y, yp = [], [], [], []
            # First, get actual values
            for i, (Y, v) in enumerate(getattr(self, sig)):
                # if not i or Y >= trc[sig][i - 1]:
                xp.append(v)
                yp.append(Y)
            setattr(self, f"tf_{sig}", CoordinateType(self.profile))
            if not xp or not yp:
                if prev:
                    getattr(self, f"tf_{sig}")[:] = prev
                continue
            # Second, interpolate to given size and use the same y axis
            # for all channels
            for i in range(size):
                x.append(i / (size - 1.0) * maxv)
                y.append(colormath.Lab2XYZ(i / (size - 1.0) * 100, 0, 0)[1] * 100)
            xi = numpy.interp(y, yp, xp)
            yi = numpy.interp(x, xi, y)
            prev = getattr(self, f"tf_{sig}")
            for Y, v in zip(yi, x):
                if Y <= yp[0]:
                    Y = yp[0]
                prev.append([Y, v])

    def move_handler(self, event):
        if not self.IsShownOnScreen():
            return
        display_no, geometry, client_area = self.get_display()
        if display_no != self.display_no:
            self.display_no = display_no
            # Translate from wx display index to Argyll display index
            n = get_argyll_display_number(geometry)
            if n is not None:
                # Save Argyll display index to configuration
                setcfg("display.number", n + 1)
                # Load profile
                self.load_lut(get_display_profile(n))
        event.Skip()

    def plot_mode_select_handler(self, event):
        # self.client.resetzoom()
        self.DrawLUT()

    def get_commands(self):
        return self.get_common_commands() + [
            "curve-viewer [filename]",
            "load <filename>",
        ]

    def process_data(self, data):
        if (data[0] == "curve-viewer" and len(data) < 3) or (
            data[0] == "load" and len(data) == 2
        ):
            if self.IsIconized():
                self.Restore()
            self.Raise()
            if len(data) == 2:
                path = data[1]
                if not os.path.isfile(path) and not os.path.isabs(path):
                    path = get_data_path(path)
                if not path:
                    return "fail"
                else:
                    self.droptarget.OnDropFiles(0, 0, [path])
            return "ok"
        return "invalid"

    def reload_vcgt_handler(self, event):
        cmd, args = self.worker.prepare_dispwin(True)
        if isinstance(cmd, Exception):
            show_result_dialog(cmd, self)
        elif cmd:
            result = self.worker.exec_cmd(
                cmd, args, capture_output=True, skip_scripts=True
            )
            if isinstance(result, Exception):
                show_result_dialog(result, self)
            elif not result:
                show_result_dialog(UnloggedError("".join(self.worker.errors)), self)
            else:
                self.load_lut(get_display_profile())

    def LoadProfile(self, profile):
        if profile and not isinstance(profile, ICCP.ICCProfile):
            try:
                profile = ICCP.ICCProfile(profile)
            except (IOError, ICCP.ICCProfileInvalidError) as exception:
                show_result_dialog(
                    Error(f"{lang.getstr('profile.invalid')}\n{profile}"), self
                )
                profile = None
        if not profile:
            profile = ICCP.ICCProfile()
            profile._data = "\0" * 128
            profile._tags.desc = ICCP.TextDescriptionType(b"", "desc")
            profile.size = len(profile.data)
            profile.is_loaded = True
        center = False
        if (
            getattr(self, "profile", None)
            and self.profile.colorSpace != profile.colorSpace
        ):
            center = True
        if profile.getDescription():
            title = " \u2014 ".join(
                [lang.getstr("calibration.lut_viewer.title"), profile.getDescription()]
            )
        else:
            title = lang.getstr("calibration.lut_viewer.title")
        self.SetTitle(title)
        self.profile = profile
        for channel in "rgb":
            trc = profile.tags.get(f"{channel}TRC", profile.tags.get("kTRC"))
            if isinstance(trc, ICCP.ParametricCurveType):
                trc = trc.get_trc()
            setattr(self, f"{channel}TRC", trc)
            setattr(self, f"tf_{channel}TRC", trc)
        self.trc = None
        curves = []
        if (
            "vcgt" in profile.tags
            or "MS00" in profile.tags
            or self.__class__ is LUTFrame
        ):
            curves.append(lang.getstr("vcgt"))
        self.client.errors = []
        self.toggle_clut.SetValue("B2A0" in profile.tags or "A2B0" in profile.tags)
        if (self.rTRC and self.gTRC and self.bTRC) or (
            self.toggle_clut.GetValue()
            and profile.colorSpace in (b"RGB", b"GRAY", b"CMYK")
        ):
            try:
                self.lookup_tone_response_curves()
            except Exception as exception:
                wx.CallAfter(show_result_dialog, exception, self)
            else:
                curves.append(lang.getstr("[rgb]TRC"))
        curves = self.add_shaper_curves(curves)
        selection = self.plot_mode_select.GetStringSelection()
        self.plot_mode_select.SetItems(curves)
        self.plot_mode_select.Enable(len(curves) > 1)
        if curves and not self.plot_mode_select.SetStringSelection(selection):
            self.plot_mode_select.SetSelection(0)
            center = True
        self.plot_mode_select.ContainingSizer.Layout()
        self.cbox_sizer.Layout()
        self.box_sizer.Layout()
        self.DrawLUT()
        if center:
            wx.CallAfter(self.client.center)
        wx.CallAfter(self.handle_errors)

    def add_shaper_curves(self, curves):
        if getcfg("show_advanced_options"):
            if isinstance(self.profile.tags.get("A2B0"), ICCP.LUT16Type):
                curves.append(lang.getstr("profile.tags.A2B0.shaper_curves.input"))
                curves.append(lang.getstr("profile.tags.A2B0.shaper_curves.output"))
            if isinstance(self.profile.tags.get("A2B1"), ICCP.LUT16Type):
                curves.append(lang.getstr("profile.tags.A2B1.shaper_curves.input"))
                curves.append(lang.getstr("profile.tags.A2B1.shaper_curves.output"))
            if isinstance(self.profile.tags.get("A2B2"), ICCP.LUT16Type):
                curves.append(lang.getstr("profile.tags.A2B2.shaper_curves.input"))
                curves.append(lang.getstr("profile.tags.A2B2.shaper_curves.output"))
            if isinstance(self.profile.tags.get("B2A0"), ICCP.LUT16Type):
                curves.append(lang.getstr("profile.tags.B2A0.shaper_curves.input"))
                curves.append(lang.getstr("profile.tags.B2A0.shaper_curves.output"))
            if isinstance(self.profile.tags.get("B2A1"), ICCP.LUT16Type):
                curves.append(lang.getstr("profile.tags.B2A1.shaper_curves.input"))
                curves.append(lang.getstr("profile.tags.B2A1.shaper_curves.output"))
            if isinstance(self.profile.tags.get("B2A2"), ICCP.LUT16Type):
                curves.append(lang.getstr("profile.tags.B2A2.shaper_curves.input"))
                curves.append(lang.getstr("profile.tags.B2A2.shaper_curves.output"))
        return curves

    def add_toggles(self, parent, sizer):
        # Add toggle checkboxes for up to 16 channels
        self.toggles = []
        for i in range(16):
            toggle = CustomCheckBox(parent, -1, "", name="toggle_channel_%i" % i)
            toggle.SetForegroundColour(FGCOLOUR)
            toggle.SetMaxFontSize(11)
            toggle.SetValue(True)
            sizer.Add(
                toggle,
                flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
                border=4 if i < 15 else 0,
            )
            toggle.Bind(wx.EVT_CHECKBOX, self.DrawLUT)
            self.toggles.append(toggle)
            toggle.Hide()

    def add_tone_values(self, legend):
        if not self.profile:
            return
        colorants = legend[0]
        if (
            self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
            and "vcgt" in self.profile.tags
        ):
            if "R" in colorants or "G" in colorants or "B" in colorants:
                legend.append(lang.getstr("tone_values"))
                if "=" in colorants and 0:  # NEVER
                    unique = []
                    if 0 in self.client.unique:  # Red
                        unique.append(self.client.unique[0])
                    if 1 in self.client.unique:  # Green
                        unique.append(self.client.unique[1])
                    if 2 in self.client.unique:  # Blue
                        unique.append(self.client.unique[2])
                    unique = min(unique)
                    legend[-1] += " %.1f%% (%i/%i)" % (
                        unique / (self.client.entryCount / 100.0),
                        unique,
                        self.client.entryCount,
                    )
                else:
                    if 0 in self.client.unique:  # Red
                        legend[-1] += " %.1f%% (%i/%i)" % (
                            self.client.unique[0] / (self.client.entryCount / 100.0),
                            self.client.unique[0],
                            self.client.entryCount,
                        )
                    if 1 in self.client.unique:  # Green
                        legend[-1] += " %.1f%% (%i/%i)" % (
                            self.client.unique[1] / (self.client.entryCount / 100.0),
                            self.client.unique[1],
                            self.client.entryCount,
                        )
                    if 2 in self.client.unique:  # Blue
                        legend[-1] += " %.1f%% (%i/%i)" % (
                            self.client.unique[2] / (self.client.entryCount / 100.0),
                            self.client.unique[2],
                            self.client.entryCount,
                        )
                unique = list(self.client.unique.values())
                if 0 not in unique and "R=G=B" not in colorants:
                    unique = min(unique)
                    legend[-1] += ", %s %.1f%% (%i/%i)" % (
                        lang.getstr("grayscale"),
                        unique / (self.client.entryCount / 100.0),
                        unique,
                        self.client.entryCount,
                    )
        elif (
            self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC")
            and isinstance(self.tf_rTRC, (ICCP.CurveType, CoordinateType))
            and len(self.tf_rTRC) > 1
            and isinstance(self.tf_gTRC, (ICCP.CurveType, CoordinateType))
            and len(self.tf_gTRC) > 1
            and isinstance(self.tf_bTRC, (ICCP.CurveType, CoordinateType))
            and len(self.tf_bTRC) > 1
        ):
            transfer_function = None
            if not getattr(self, "trc", None) and len(self.tf_rTRC) == len(
                self.tf_gTRC
            ) == len(self.tf_bTRC):
                if isinstance(self.tf_rTRC, ICCP.CurveType):
                    self.trc = ICCP.CurveType(profile=self.profile)
                    for i in range(len(self.tf_rTRC)):
                        self.trc.append(
                            (self.tf_rTRC[i] + self.tf_gTRC[i] + self.tf_bTRC[i]) / 3.0
                        )
                else:
                    self.trc = CoordinateType(self.profile)
                    for i in range(len(self.tf_rTRC)):
                        self.trc.append(
                            [
                                (
                                    self.tf_rTRC[i][0]
                                    + self.tf_gTRC[i][0]
                                    + self.tf_bTRC[i][0]
                                )
                                / 3.0,
                                (
                                    self.tf_rTRC[i][1]
                                    + self.tf_gTRC[i][1]
                                    + self.tf_bTRC[i][1]
                                )
                                / 3.0,
                            ]
                        )
            if getattr(self, "trc", None):
                transfer_function = self.trc.get_transfer_function(
                    slice=(0.00, 1.00), outoffset=1.0
                )
            # if "R" in colorants and "G" in colorants and "B" in colorants:
            # if self.profile.tags.rTRC == self.profile.tags.gTRC == self.profile.tags.bTRC:
            # transfer_function = self.profile.tags.rTRC.get_transfer_function()
            # elif ("R" in colorants and
            # (not "G" in colorants or
            # self.profile.tags.rTRC == self.profile.tags.gTRC) and
            # (not "B" in colorants or
            # self.profile.tags.rTRC == self.profile.tags.bTRC)):
            # transfer_function = self.profile.tags.rTRC.get_transfer_function()
            # elif ("G" in colorants and
            # (not "R" in colorants or
            # self.profile.tags.gTRC == self.profile.tags.rTRC) and
            # (not "B" in colorants or
            # self.profile.tags.gTRC == self.profile.tags.bTRC)):
            # transfer_function = self.profile.tags.gTRC.get_transfer_function()
            # elif ("B" in colorants and
            # (not "G" in colorants or
            # self.profile.tags.bTRC == self.profile.tags.gTRC) and
            # (not "R" in colorants or
            # self.profile.tags.bTRC == self.profile.tags.rTRC)):
            # transfer_function = self.profile.tags.bTRC.get_transfer_function()
            if transfer_function and transfer_function[1] >= 0.95:
                if self.tf_rTRC == self.tf_gTRC == self.tf_bTRC:
                    label = lang.getstr("rgb.trc")
                else:
                    label = lang.getstr("rgb.trc.averaged")
                if round(transfer_function[1], 2) == 1.0:
                    value = "%s" % (transfer_function[0][0])
                else:
                    value = "≈ %s (Δ %.2f%%)" % (
                        transfer_function[0][0],
                        100 - transfer_function[1] * 100,
                    )
                legend.append(" ".join([label, value]))

    def DrawLUT(self, event=None):
        self.SetStatusText("")
        self.Freeze()
        curves = None
        curves_colorspace = self.profile.colorSpace
        connection_colorspace = b"RGB"
        if self.profile and self.plot_mode_select.Items:
            if self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt"):
                # Convert calibration information from embedded WCS profile
                # (if present) to VideCardFormulaType if the latter is not present
                if (
                    isinstance(self.profile.tags.get("MS00"), ICCP.WcsProfilesTagType)
                    and "vcgt" not in self.profile.tags
                ):
                    vcgt = self.profile.tags["MS00"].get_vcgt()
                    if vcgt:
                        self.profile.tags["vcgt"] = vcgt
                if "vcgt" in self.profile.tags:
                    curves = self.profile.tags["vcgt"]
                else:
                    curves = None
            elif self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC"):
                if not (
                    isinstance(self.rTRC, (ICCP.CurveType, CoordinateType))
                    and isinstance(self.gTRC, (ICCP.CurveType, CoordinateType))
                    and isinstance(self.bTRC, (ICCP.CurveType, CoordinateType))
                ):
                    curves = None
                elif (
                    len(self.rTRC) == 1 and len(self.gTRC) == 1 and len(self.bTRC) == 1
                ):
                    # gamma
                    curves = {
                        "redMin": 0.0,
                        "redGamma": self.rTRC[0],
                        "redMax": 1.0,
                        "greenMin": 0.0,
                        "greenGamma": self.gTRC[0],
                        "greenMax": 1.0,
                        "blueMin": 0.0,
                        "blueGamma": self.bTRC[0],
                        "blueMax": 1.0,
                    }
                else:
                    # curves
                    data = [self.rTRC, self.gTRC, self.bTRC]
                    if hasattr(self, "kTRC"):
                        data.append(self.kTRC)
                    curves = {
                        "data": data,
                        "entryCount": len(self.rTRC),
                        "entrySize": 2,
                    }
            elif self.plot_mode_select.GetStringSelection() != lang.getstr("gamut"):
                to_pcs = False
                if self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.A2B0.shaper_curves.input"
                ):
                    tables = self.profile.tags.A2B0.input
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.A2B0.shaper_curves.output"
                ):
                    tables = self.profile.tags.A2B0.output
                    curves_colorspace = self.profile.connectionColorSpace
                    to_pcs = True
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.A2B1.shaper_curves.input"
                ):
                    tables = self.profile.tags.A2B1.input
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.A2B1.shaper_curves.output"
                ):
                    tables = self.profile.tags.A2B1.output
                    curves_colorspace = self.profile.connectionColorSpace
                    to_pcs = True
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.A2B2.shaper_curves.input"
                ):
                    tables = self.profile.tags.A2B2.input
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.A2B2.shaper_curves.output"
                ):
                    tables = self.profile.tags.A2B2.output
                    curves_colorspace = self.profile.connectionColorSpace
                    to_pcs = True
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.B2A0.shaper_curves.input"
                ):
                    tables = self.profile.tags.B2A0.input
                    curves_colorspace = self.profile.connectionColorSpace
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.B2A0.shaper_curves.output"
                ):
                    tables = self.profile.tags.B2A0.output
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.B2A1.shaper_curves.input"
                ):
                    tables = self.profile.tags.B2A1.input
                    curves_colorspace = self.profile.connectionColorSpace
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.B2A1.shaper_curves.output"
                ):
                    tables = self.profile.tags.B2A1.output
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.B2A2.shaper_curves.input"
                ):
                    tables = self.profile.tags.B2A2.input
                    curves_colorspace = self.profile.connectionColorSpace
                elif self.plot_mode_select.GetStringSelection() == lang.getstr(
                    "profile.tags.B2A2.shaper_curves.output"
                ):
                    tables = self.profile.tags.B2A2.output
                entry_count = len(tables[0])
                if curves_colorspace != b"RGB":
                    maxv = 100
                else:
                    maxv = 255
                lin = [v / (entry_count - 1.0) * maxv for v in range(entry_count)]
                data = []
                for i, table in enumerate(tables):
                    xp = lin
                    if curves_colorspace == b"Lab" and i == 0:
                        if to_pcs:
                            table = [v / 65280.0 * 65535.0 for v in table]
                        else:
                            xp = [
                                min(
                                    v / (entry_count - 1.0) * (100 + 25500 / 65280.0),
                                    maxv,
                                )
                                for v in range(entry_count)
                            ]
                    yp = [v / 65535.0 * maxv for v in table]
                    if curves_colorspace == b"Lab" and i == 0:
                        # Interpolate to given size and use the same y axis
                        # for all channels
                        xi = numpy.interp(lin, yp, xp)
                        yi = numpy.interp(lin, xi, lin)
                    else:
                        yi = yp
                    xy = []
                    for Y, v in zip(yi, lin):
                        if Y <= yp[0]:
                            Y = yp[0]
                        xy.append([v, Y])
                    data.append(xy)
                curves = {"data": data, "entryCount": entry_count, "entrySize": 2}
        yLabel = []
        numchannels = {
            b"XYZ": 3,
            b"Lab": 3,
            b"Luv": 3,
            b"YCbr": 3,
            b"Yxy": 3,
            b"RGB": 3,
            b"GRAY": 1,
            b"HSV": 3,
            b"HLS": 3,
            b"CMYK": 4,
            b"CMY": 3,
            b"2CLR": 2,
            b"3CLR": 3,
            b"4CLR": 4,
            b"5CLR": 5,
            b"6CLR": 6,
            b"7CLR": 7,
            b"8CLR": 8,
            b"9CLR": 9,
            b"ACLR": 10,
            b"BCLR": 11,
            b"CCLR": 12,
            b"DCLR": 13,
            b"ECLR": 14,
            b"FCLR": 15,
        }.get(curves_colorspace, 3)
        is_ktrc = (
            self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC")
            and curves_colorspace != b"RGB"
            and False
        )
        if is_ktrc:
            curves_colorspace = b"GRAY"
            numchannels = 1
        for channel, toggle in enumerate(self.toggles):
            toggle.Show(channel < numchannels)
            if channel < numchannels:
                if curves_colorspace == b"GRAY":
                    toggle.Label = "R=G=B"
                elif curves_colorspace == b"YCbr":
                    toggle.Label = ("Y", "Cb", "Cr")[channel]
                elif curves_colorspace.endswith(b"CLR"):
                    curves_colorspace = b"nCLR"
                    toggle.Label = "%i" % channel
                elif curves_colorspace == b"Lab":
                    toggle.Label = ("L*", "a*", "b*")[channel]
                else:
                    toggle.Label = curves_colorspace[channel : channel + 1].decode(
                        "utf-8"
                    )
                if toggle.GetValue():
                    yLabel.append(toggle.Label)
            toggle.Enable(bool(curves))
        if self.plot_mode_select.GetStringSelection() not in (
            lang.getstr("[rgb]TRC"),
            lang.getstr("gamut"),
        ) or (self.profile and self.profile.connectionColorSpace == b"RGB"):
            self.xLabel = "".join(yLabel)
        else:
            if self.show_as_L.GetValue():
                connection_colorspace = b"Lab"
                self.xLabel = "L*"
            else:
                connection_colorspace = b"XYZ"
                self.xLabel = "Y"
        self.yLabel = "".join(yLabel)

        self.show_as_L.Enable(bool(curves))
        self.show_as_L.Show(
            self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC")
            and self.profile.connectionColorSpace != b"RGB"
        )
        self.toggle_clut.Show(
            self.profile.colorSpace == b"RGB"
            and self.profile.connectionColorSpace != b"RGB"
            and self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC")
            and ("B2A0" in self.profile.tags or b"A2B0" in self.profile.tags)
        )
        self.toggle_clut.Enable(
            self.profile.connectionColorSpace != b"RGB"
            and self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC")
            and isinstance(self.profile.tags.get("rTRC"), ICCP.CurveType)
            and isinstance(self.profile.tags.get("gTRC"), ICCP.CurveType)
            and isinstance(self.profile.tags.get("bTRC"), ICCP.CurveType)
        )
        self.save_plot_btn.Enable(bool(curves))
        if hasattr(self, "reload_vcgt_btn"):
            self.reload_vcgt_btn.Enable(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
                and bool(self.profile)
            )
            self.reload_vcgt_btn.Show(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
            )
        if hasattr(self, "apply_bpc_btn"):
            enable_bpc = (
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
                and bool(self.profile)
                and isinstance(self.profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
            )
            if enable_bpc:
                values = self.profile.tags.vcgt.getNormalizedValues()
            self.apply_bpc_btn.Enable(enable_bpc and values[0] != (0, 0, 0))
            self.apply_bpc_btn.Show(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
            )
        if hasattr(self, "install_vcgt_btn"):
            self.install_vcgt_btn.Enable(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
                and bool(self.profile)
                and isinstance(self.profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
            )
            self.install_vcgt_btn.Show(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
            )
        if hasattr(self, "save_vcgt_btn"):
            self.save_vcgt_btn.Enable(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
                and bool(self.profile)
                and isinstance(self.profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
            )
            self.save_vcgt_btn.Show(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
            )
        if hasattr(self, "show_actual_lut_cb"):
            self.show_actual_lut_cb.Show(
                self.plot_mode_select.GetStringSelection() == lang.getstr("vcgt")
            )
        if hasattr(self, "rendering_intent_select"):
            self.rendering_intent_select.Show(
                self.plot_mode_select.GetStringSelection() == lang.getstr("[rgb]TRC")
                and self.profile.connectionColorSpace != b"RGB"
            )
        if hasattr(self, "direction_select"):
            self.direction_select.Show(
                self.rendering_intent_select.IsShown()
                and "B2A0" in self.profile.tags
                and "A2B0" in self.profile.tags
            )
        self.show_as_L.GetContainingSizer().Layout()
        if hasattr(self, "cbox_sizer"):
            self.cbox_sizer.Layout()
        if hasattr(self, "box_sizer"):
            self.box_sizer.Layout()
        if self.client.last_PointLabel is not None:
            self.client._drawPointLabel(self.client.last_PointLabel)  # erase old
            self.client.last_PointLabel = None
        channels = dict()
        for channel, toggle in enumerate(self.toggles):
            channels[channel] = (
                toggle.IsShown() and toggle.GetValue() and toggle.Label or ""
            )
        wx.CallAfter(
            self.client.DrawLUT,
            curves,
            xLabel=self.xLabel,
            yLabel=self.yLabel,
            channels=channels,
            colorspace=curves_colorspace,
            connection_colorspace=connection_colorspace,
        )
        self.Thaw()

    def OnClose(self, event):
        self.listening = False
        if self.worker.tempdir and os.path.isdir(self.worker.tempdir):
            self.worker.wrapup(False)
        config.writecfg(
            module="curve-viewer",
            options=("display.number", "position.lut_viewer", "size.lut_viewer"),
        )
        # Hide first (looks nicer)
        self.Hide()
        # Need to use CallAfter to prevent hang under Windows if minimized
        wx.CallAfter(self.Destroy)

    def OnMotion(self, event):
        if isinstance(event, wx.MouseEvent):
            if not event.LeftIsDown():
                self.UpdatePointLabel(self.client._getXY(event))
            else:
                self.client.erase_pointlabel()
            event.Skip()  # Go to next handler

    def OnMove(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            setcfg("position.lut_viewer.x", x)
            setcfg("position.lut_viewer.y", y)
        if event:
            event.Skip()

    def OnSize(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            w, h = self.ClientSize
            setcfg("size.lut_viewer.w", w)
            setcfg("size.lut_viewer.h", h)
        if event:
            event.Skip()
            if sys.platform == "win32":
                # Needed under Windows when using double buffering
                self.Refresh()

    def OnWheel(self, event):
        xy = wx.GetMousePosition()
        if self.client.last_draw:
            if event.WheelRotation < 0:
                direction = 1.0
            else:
                direction = -1.0
            self.client.zoom(direction)

    def SaveFile(self, event=None):
        """Saves the file to the type specified in the extension. If no file
        name is specified a dialog box is provided.  Returns True if sucessful,
        otherwise False.

        .bmp  Save a Windows bitmap file.
        .xbm  Save an X bitmap file.
        .xpm  Save an XPM bitmap file.
        .png  Save a Portable Network Graphics file.
        .jpg  Save a Joint Photographic Experts Group file.
        """
        fileName = " ".join(
            [
                self.plot_mode_select.GetStringSelection(),
                os.path.basename(
                    os.path.splitext(self.profile.fileName or lang.getstr("unnamed"))[0]
                ),
            ]
        )
        if (
            event
            and hasattr(self, "save_vcgt_btn")
            and event.GetId() == self.save_vcgt_btn.GetId()
        ):
            extensions = {"cal": 1}
            defType = "cal"
        else:
            extensions = {
                "bmp": wx.BITMAP_TYPE_BMP,  # Save a Windows bitmap file.
                "xbm": wx.BITMAP_TYPE_XBM,  # Save an X bitmap file.
                "xpm": wx.BITMAP_TYPE_XPM,  # Save an XPM bitmap file.
                "jpg": wx.BITMAP_TYPE_JPEG,  # Save a JPG file.
                "png": wx.BITMAP_TYPE_PNG,  # Save a PNG file.
            }
            defType = "png"

        fileName = f"{fileName}.{defType}"

        fType = None
        dlg1 = None
        while fType not in extensions:

            if dlg1:  # FileDialog exists: Check for extension
                InfoDialog(
                    self,
                    msg=lang.getstr("error.file_type_unsupported"),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
            else:  # FileDialog doesn't exist: just check one
                dlg1 = wx.FileDialog(
                    self,
                    lang.getstr("save_as"),
                    get_verified_path("last_filedialog_path")[0],
                    fileName,
                    "|".join(
                        [
                            "%s (*.%s)|*.%s" % (ext.upper(), ext, ext)
                            for ext in sorted(extensions.keys())
                        ]
                    ),
                    wx.SAVE | wx.OVERWRITE_PROMPT,
                )
                dlg1.SetFilterIndex(sorted(extensions.keys()).index(defType))

            if dlg1.ShowModal() == wx.ID_OK:
                fileName = dlg1.GetPath()
                if not waccess(fileName, os.W_OK):
                    show_result_dialog(
                        Error(lang.getstr("error.access_denied.write", fileName)), self
                    )
                    return
                fType = fileName[-3:].lower()
                setcfg("last_filedialog_path", fileName)
            else:  # exit without saving
                dlg1.Destroy()
                return False

        if dlg1:
            dlg1.Destroy()

        # Save Bitmap
        if (
            event
            and hasattr(self, "save_vcgt_btn")
            and event.GetId() == self.save_vcgt_btn.GetId()
        ):
            res = vcgt_to_cal(self.profile)
            res.write(fileName)
        else:
            res = self.client._Buffer.SaveFile(fileName, extensions.get(fType, ".png"))
        return res

    def SetStatusText(self, text):
        self.status.Label = text
        self.status.Refresh()

    def SetGamutStatusText(self, text):
        self.gamut_status.Label = text
        self.status.Refresh()

    def UpdatePointLabel(self, xy):
        if self.client.GetEnablePointLabel():
            # Show closest point (when enbled)
            # Make up dict with info for the point label
            dlst = self.client.GetClosestPoint(xy, pointScaled=True)
            if dlst != [] and hasattr(self.client, "point_grid"):
                curveNum, legend, pIndex, pointXY, scaledXY, distance = dlst
                legend = legend.split(", ")
                channels = {}
                value = []
                for channel in self.client.point_grid:
                    toggle = self.toggles[channel]
                    channels[channel] = toggle.Label or ""
                    x = int(round(pointXY[0] / 255.0 * 4095))
                    v = self.client.point_grid[channel].get(x, 0)
                    if toggle.Label in ("a*", "b*"):
                        v = -128 + v / 100.0 * (255 + 255 / 256.0)
                    value.append((toggle.Label, v))
                identical = len(value) > 1 and all(v[1] == value[0][1] for v in value)
                if 1:
                    joiner = " \u2192 "
                    label = [_f for _f in list(channels.values()) if _f]
                    if (
                        self.plot_mode_select.GetStringSelection()
                        == lang.getstr("[rgb]TRC")
                        and self.profile.connectionColorSpace != b"RGB"
                    ):
                        if self.show_as_L.GetValue():
                            format_ = "L* %.2f", "%s %.2f"
                        else:
                            format_ = "Y %.4f", "%s %.2f"
                        axis_y = 100.0
                    elif "L*" in label and ("a*" in label or "b*" in label):
                        a = b = -128 + pointXY[0] / 100.0 * (255 + 255 / 256.0)
                        if label == ["L*", "a*", "b*"]:
                            format_ = "L* %%.2f a* %.2f b* %.2f" % (a, b), "%s %.2f"
                        elif label == ["L*", "a*"]:
                            format_ = "L* %%.2f a* %.2f" % a, "%s %.2f"
                        elif label == ["L*", "b*"]:
                            format_ = "L* %%.2f b* %.2f" % b, "%s %.2f"
                        axis_y = self.client.axis_y[1]
                    else:
                        format_ = "%s %%.2f" % "=".join(label), "%s %.2f"
                        axis_y = self.client.axis_y[1]
                    if identical:
                        # if value[0][1] is None:
                        vout = pointXY[1]
                        if "L*" not in label and ("a*" in label or "b*" in label):
                            vout = -128 + vout / 100.0 * (255 + 255 / 256.0)
                        RGB = " ".join(["=".join(label), "%.2f" % vout])
                    # else:
                    # RGB = "R=G=B %.2f" % value[0][1]
                    else:
                        RGB = " ".join(
                            [
                                format_[1] % (v, s)
                                for v, s in [v for v in value if v[1] is not None]
                            ]
                        )
                    vin = pointXY[0]
                    if "L*" not in label and ("a*" in label or "b*" in label):
                        vin = -128 + pointXY[0] / 100.0 * (255 + 255 / 256.0)
                    legend[0] = joiner.join([format_[0] % vin, RGB])
                    if (
                        self.plot_mode_select.GetStringSelection()
                        == lang.getstr("[rgb]TRC")
                        and self.profile.connectionColorSpace != b"RGB"
                    ):
                        pointXY = pointXY[1], pointXY[0]
                else:
                    joiner = " \u2192 "
                    format_ = "%.2f", "%.2f"
                    axis_y = self.client.axis_y[1]
                    legend[0] = "{} {}".format(
                        legend[0],
                        joiner.join(
                            [format_[i] % point for i, point in enumerate(pointXY)]
                        ),
                    )
                if len(legend) == 1:
                    # Calculate gamma
                    axis_x = self.client.axis_y[1]
                    gamma = []
                    for label, v in value:
                        if v is None or label in ("a*", "b*"):
                            continue
                        if (
                            self.plot_mode_select.GetStringSelection()
                            == lang.getstr("[rgb]TRC")
                            and self.profile.connectionColorSpace != b"RGB"
                        ):
                            x = v
                            y = pointXY[1]
                            if self.show_as_L.GetValue():
                                y = colormath.Lab2XYZ(y, 0, 0)[1] * 100
                        else:
                            x = pointXY[0]
                            y = v
                        if x <= 0 or x >= axis_x or y <= 0 or y >= axis_y:
                            continue
                        if identical:
                            label = "=".join(
                                [
                                    "%s" % s
                                    for s, v in [
                                        s_v for s_v in value if s_v[1] is not None
                                    ]
                                ]
                            )
                        # Note: We need to make sure each point is a float because it
                        # might be a decimal.Decimal, which can't be divided by floats!
                        gamma.append(
                            "{} {:.2f}".format(
                                label,
                                round(
                                    math.log(float(y) / axis_y) / math.log(x / axis_x),
                                    2,
                                ),
                            )
                        )
                        if "=" in label:
                            break
                    if gamma:
                        legend.append("Gamma {}".format(" ".join(gamma)))
                if self.profile.connectionColorSpace != b"RGB":
                    self.add_tone_values(legend)
                legend = [", ".join(legend[:-1])] + [legend[-1]]
                self.SetStatusText("\n".join(legend))
                # Make up dictionary to pass to DrawPointLabel
                mDataDict = {
                    "curveNum": curveNum,
                    "legend": legend,
                    "pIndex": pIndex,
                    "pointXY": pointXY,
                    "scaledXY": scaledXY,
                }
                # Pass dict to update the point label
                self.client.UpdatePointLabel(mDataDict)

    def update_controls(self):
        self.show_actual_lut_cb.Enable(
            (
                self.worker.argyll_version[0:3] > [1, 1, 0]
                or (
                    self.worker.argyll_version[0:3] == [1, 1, 0]
                    and "Beta" not in self.worker.argyll_version_string
                )
            )
            and not config.is_untethered_display()
        )
        self.show_actual_lut_cb.SetValue(
            bool(getcfg("lut_viewer.show_actual_lut"))
            and not config.is_untethered_display()
        )

    @property
    def worker(self):
        return self.client.worker

    def display_changed(self, event):
        self.worker.enumerate_displays_and_ports(
            check_lut_access=False, enumerate_ports=False, include_network_devices=False
        )


def main():
    config.initcfg("curve-viewer")
    # Backup display config
    cfg_display = getcfg("display.number")
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = LUTFrame(None, -1)
    app.TopWindow.Bind(wx.EVT_CLOSE, app.TopWindow.OnClose, app.TopWindow)
    if sys.platform == "darwin":
        app.TopWindow.init_menubar()
    wx.CallLater(1, _main, app)
    app.MainLoop()


def _main(app):
    app.TopWindow.listen()
    app.TopWindow.display_changed(None)
    app.TopWindow.Bind(wx.EVT_DISPLAY_CHANGED, app.TopWindow.display_changed)
    app.TopWindow.display_no, geometry, client_area = app.TopWindow.get_display()
    app.TopWindow.Bind(wx.EVT_MOVE, app.TopWindow.move_handler, app.TopWindow)
    display_no = get_argyll_display_number(geometry)
    if display_no is not None:
        setcfg("display.number", display_no + 1)
    app.TopWindow.update_controls()
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            app.TopWindow.drop_handler(os.path.abspath(arg))
            break
    else:
        app.TopWindow.load_lut(get_display_profile(display_no))
    app.TopWindow.Show()


if __name__ == "__main__":
    main()
