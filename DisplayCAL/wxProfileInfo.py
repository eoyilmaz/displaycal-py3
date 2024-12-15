# -*- coding: utf-8 -*-
import re
import os
import sys

import traceback

from DisplayCAL.config import (
    defaults,
    fs_enc,
    get_argyll_display_number,
    get_data_path,
    get_display_profile,
    get_display_rects,
    getbitmap,
    getcfg,
    geticon,
    get_verified_path,
    profile_ext,
    setcfg,
    writecfg,
)
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug
from DisplayCAL.util_dict import dict_slice, dict_sort
from DisplayCAL.util_io import GzipFileProper
from DisplayCAL.util_list import intlist
from DisplayCAL.util_os import launch_file, make_win32_compatible_long_path, waccess
from DisplayCAL.util_str import strtr, universal_newlines, wrap
from DisplayCAL.worker import (
    Error,
    UnloggedError,
    check_set_argyll_bin,
    get_argyll_util,
    make_argyll_compatible_path,
    show_result_dialog,
)
from DisplayCAL.wxaddons import get_platform_window_decoration_size, wx
from DisplayCAL.wxLUTViewer import LUTCanvas, LUTFrame
from DisplayCAL.wxVRML2X3D import vrmlfile2x3dfile
from DisplayCAL.wxwindows import (
    BaseApp,
    BaseFrame,
    BitmapBackgroundPanelText,
    BitmapBackgroundPanelTextGamut,
    CustomCheckBox,
    CustomGrid,
    CustomRowLabelRenderer,
    FileDrop,
    SimpleBook,
    TwoWaySplitter,
)
from DisplayCAL.wxfixes import GenBitmapButton as BitmapButton, wx_Panel, set_maxsize
from DisplayCAL import colormath
from DisplayCAL import config
from DisplayCAL import wxenhancedplot as plot
from DisplayCAL import localization as lang
from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import x3dom

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
TEXTCOLOUR = "#333333"

if sys.platform == "darwin":
    FONTSIZE_SMALL = 10
else:
    FONTSIZE_SMALL = 8


class GamutCanvas(LUTCanvas):
    def __init__(self, *args, **kwargs):
        LUTCanvas.__init__(self, *args, **kwargs)
        self.SetEnableTitle(False)
        self.SetFontSizeAxis(FONTSIZE_SMALL)
        self.SetFontSizeLegend(FONTSIZE_SMALL)
        self.pcs_data = []
        self.profiles = {}
        self.colorspace = "a*b*"
        self.intent = ""
        self.direction = ""
        self.order = ""
        self.reset()
        self.resetzoom()

    def DrawCanvas(
        self,
        title=None,
        colorspace=None,
        whitepoint=None,
        center=False,
        show_outline=True,
    ):
        if not title:
            title = ""
        if colorspace:
            self.colorspace = colorspace

        # Defaults
        poly = plot.PolyLine
        poly._attributes["width"] = 3
        polys = []

        # L*a*b*
        optimalcolors = colormath.optimalcolors_Lab

        # CIE 1931 2-deg chromaticity coordinates
        # http://www.cvrl.org/offercsvccs.php
        xy = colormath.cie1931_2_xy

        if self.colorspace == "xy":
            label_x = "x"
            label_y = "y"
            if show_outline:
                polys.append(
                    plot.PolySpline(
                        xy, colour=wx.Colour(102, 102, 102, 153), width=1.75
                    )
                )
                polys.append(
                    plot.PolyLine(
                        [xy[0], xy[-1]],
                        colour=wx.Colour(102, 102, 102, 153),
                        width=1.75,
                    )
                )
            max_x = 0.75
            max_y = 0.85
            min_x = -0.05
            min_y = -0.05
            step = 0.1
        elif self.colorspace == "u'v'":
            label_x = "u'"
            label_y = "v'"
            if show_outline:
                uv = [colormath.xyY2Lu_v_(x, y, 100)[1:] for x, y in xy]
                polys.append(
                    plot.PolySpline(
                        uv, colour=wx.Colour(102, 102, 102, 153), width=1.75
                    )
                )
                polys.append(
                    plot.PolyLine(
                        [uv[0], uv[-1]],
                        colour=wx.Colour(102, 102, 102, 153),
                        width=1.75,
                    )
                )
            max_x = 0.625
            max_y = 0.6
            min_x = -0.025
            min_y = -0.025
            step = 0.1
        elif self.colorspace == "u*v*":
            # Hard to present gamut projection appropriately in 2D
            # because blue tones 'cave in' towards the center
            label_x = "u*"
            label_y = "v*"
            max_x = 150.0
            max_y = 150.0
            min_x = -150.0
            min_y = -150.0
            step = 50
        elif self.colorspace == "DIN99":
            label_x = "a99"
            label_y = "b99"
            max_x = 50.0
            max_y = 50.0
            min_x = -50.0
            min_y = -50.0
            step = 25
        elif self.colorspace in ("DIN99b", "DIN99c", "DIN99d"):
            label_x = f"a{self.colorspace[3:]}"
            label_y = f"b{self.colorspace[3:]}"
            max_x = 65.0
            max_y = 65.0
            min_x = -65.0
            min_y = -65.0
            step = 25
        elif self.colorspace == "ICtCp":
            label_x = "Ct"
            label_y = "Cp"
            max_x = 0.4
            max_y = 0.5
            min_x = -0.5
            min_y = -0.4
            step = 0.1
        elif self.colorspace == "IPT":
            label_x = "P"
            label_y = "T"
            max_x = 1.0
            max_y = 1.0
            min_x = -1.0
            min_y = -1.0
            step = 0.25
        else:
            if self.colorspace == "Lpt":
                label_x = "p"
                label_y = "t"
            else:
                label_x = "a*"
                label_y = "b*"
            max_x = 150.0
            max_y = 150.0
            min_x = -150.0
            min_y = -150.0
            step = 50

        convert2coords = {
            "a*b*": lambda X, Y, Z: colormath.XYZ2Lab(*[v * 100 for v in (X, Y, Z)])[
                1:
            ],
            "xy": lambda X, Y, Z: colormath.XYZ2xyY(X, Y, Z)[:2],
            "u*v*": lambda X, Y, Z: colormath.XYZ2Luv(*[v * 100 for v in (X, Y, Z)])[
                1:
            ],
            "u'v'": lambda X, Y, Z: colormath.XYZ2Lu_v_(X, Y, Z)[1:],
            "DIN99": lambda X, Y, Z: colormath.XYZ2DIN99(*[v * 100 for v in (X, Y, Z)])[
                1:
            ],
            "DIN99b": lambda X, Y, Z: colormath.XYZ2DIN99b(
                *[v * 100 for v in (X, Y, Z)]
            )[1:],
            "DIN99c": lambda X, Y, Z: colormath.XYZ2DIN99c(
                *[v * 100 for v in (X, Y, Z)]
            )[1:],
            "DIN99d": lambda X, Y, Z: colormath.XYZ2DIN99d(
                *[v * 100 for v in (X, Y, Z)]
            )[1:],
            "ICtCp": lambda X, Y, Z: colormath.XYZ2ICtCp(X, Y, Z, clamp=False)[1:],
            "IPT": lambda X, Y, Z: colormath.XYZ2IPT(X, Y, Z)[1:],
            "Lpt": lambda X, Y, Z: colormath.XYZ2Lpt(*[v * 100 for v in (X, Y, Z)])[1:],
        }[self.colorspace]

        if show_outline and (
            self.colorspace == "a*b*" or self.colorspace.startswith("DIN99")
        ):
            if self.colorspace == "a*b*":
                optimalcolors = [Lab[1:] for Lab in optimalcolors]
            else:
                optimalcolors = [
                    convert2coords(*colormath.Lab2XYZ(L, a, b))
                    for L, a, b in optimalcolors
                ]
            polys.append(
                plot.PolySpline(
                    optimalcolors, colour=wx.Colour(102, 102, 102, 153), width=1.75
                )
            )

        # Add color temp graph
        if whitepoint == 1:
            colortemps = []
            for kelvin in range(4000, 25001, 40):
                colortemps.append(convert2coords(*colormath.CIEDCCT2XYZ(kelvin)))
            polys.append(
                plot.PolyLine(
                    colortemps, colour=wx.Colour(255, 255, 255, 204), width=1.5
                )
            )
        elif whitepoint == 2:
            colortemps = []
            # Stepsize 38 = endpoint 24999
            for kelvin in range(1667, 25001, 38):
                colortemps.append(convert2coords(*colormath.planckianCT2XYZ(kelvin)))
            polys.append(
                plot.PolyLine(
                    colortemps, colour=wx.Colour(255, 255, 255, 204), width=1.5
                )
            )

        kwargs = {"scale": 255}

        amount = len(self.pcs_data)

        for i, pcs_triplets in enumerate(reversed(self.pcs_data)):
            if not pcs_triplets or len(pcs_triplets) == 1:
                amount -= 1
                continue

            # Convert xicclu output to coordinates
            coords = []
            for pcs_triplet in pcs_triplets:
                coords.append(convert2coords(*pcs_triplet))

            profile = self.profiles.get(len(self.pcs_data) - 1 - i)
            if (
                profile
                and profile.profileClass == b"nmcl"
                and "ncl2" in profile.tags
                and isinstance(profile.tags.ncl2, ICCP.NamedColor2Type)
                and profile.connectionColorSpace in (b"Lab", b"XYZ")
            ):
                # Named color profile
                for j, (x, y) in enumerate(coords):
                    RGBA = colormath.XYZ2RGB(*pcs_triplets[j], **kwargs)
                    polys.append(
                        plot.PolyMarker(
                            [(x, y)],
                            colour=wx.Colour(*intlist(RGBA)),
                            size=2,
                            marker="plus",
                            width=1.75,
                        )
                    )
            else:
                xy = []
                for x, y in coords[:-1]:
                    xy.append((x, y))
                    if i == 0 or amount == 1:
                        if x > max_x:
                            max_x = x
                        if y > max_y:
                            max_y = y
                        if x < min_x:
                            min_x = x
                        if y < min_y:
                            min_y = y

                xy2 = []
                for j, (x, y) in enumerate(xy):
                    xy2.append((x, y))
                    if len(xy2) == self.size:
                        xy3 = []
                        for k, (x, y) in enumerate(xy2):
                            xy3.append((x, y))
                            if len(xy3) == 2:
                                if i == 1:
                                    # Draw comparison profile with grey outline
                                    RGBA = 102, 102, 102, 255
                                    w = 2
                                else:
                                    RGBA = colormath.XYZ2RGB(
                                        *pcs_triplets[j - len(xy2) + k], **kwargs
                                    )
                                    w = 3
                                polys.append(
                                    poly(
                                        list(xy3),
                                        colour=wx.Colour(*intlist(RGBA)),
                                        width=w,
                                    )
                                )
                                if i == 1:
                                    xy3 = []
                                else:
                                    xy3 = xy3[1:]
                        xy2 = xy2[self.size :]

            # Add whitepoint
            x, y = coords[-1]
            if i == 1:
                # Draw comparison profile with grey outline
                RGBA = 204, 204, 204, 102
                marker = "cross"
                s = 1.5
                w = 1.75
            else:
                RGBA = colormath.XYZ2RGB(*pcs_triplets[-1], **kwargs)
                marker = "plus"
                s = 2
                w = 1.75
            polys.append(
                plot.PolyMarker(
                    [(x, y)],
                    colour=wx.Colour(*intlist(RGBA)),
                    size=s,
                    marker=marker,
                    width=w,
                )
            )

        xy_range = max(abs(min_x), abs(min_y)) + max(max_x, max_y)
        if center or not self.last_draw:
            self.axis_x = self.axis_y = (min(min_x, min_y), max(max_x, max_y))
            self.spec_x = xy_range / step
            self.spec_y = xy_range / step

        if polys:
            graphics = plot.PlotGraphics(polys, title, label_x, label_y)
            p1, p2 = graphics.boundingBox()
            spacer = plot.PolyMarker(
                [
                    (p1[0] - xy_range / 20.0, p1[1] - xy_range / 20.0),
                    (p2[0] + xy_range / 20.0, p2[1] + xy_range / 20.0),
                ],
                colour=wx.Colour(0x33, 0x33, 0x33),
                size=0,
            )
            graphics.objects.append(spacer)
            if center or not self.last_draw:
                boundingbox = spacer.boundingBox()
                self.resetzoom(boundingbox)
                self.center(boundingbox)
            self._DrawCanvas(graphics)

    def reset(self):
        self.axis_x = self.axis_y = -128, 128

    def set_pcs_data(self, i):
        if len(self.pcs_data) < i + 1:
            self.pcs_data.append([])
        else:
            self.pcs_data[i] = []

    def setup(
        self, profiles=None, profile_no=None, intent="a", direction="f", order="n"
    ):
        # Number of segments from one primary to the next secondary color
        self.size = 40

        if not check_set_argyll_bin():
            return

        # Setup xicclu
        xicclu = get_argyll_util("xicclu")
        if not xicclu:
            return

        cwd = self.worker.create_tempdir()
        if isinstance(cwd, Exception):
            raise cwd

        if not profiles:
            profiles = [
                ICCP.ICCProfile(get_data_path("ref/sRGB.icm")),
                get_display_profile(),
            ]

        for i, profile in enumerate(profiles):
            if profile_no is not None and i != profile_no:
                continue

            if (
                not profile
                or profile.profileClass == b"link"
                or profile.connectionColorSpace not in (b"Lab", b"XYZ")
            ):
                self.set_pcs_data(i)
                self.profiles[i] = None
                continue

            check = self.profiles.get(i)
            if (
                check
                and check.fileName == profile.fileName
                and check.ID == profile.calculateID(False)
                and intent == self.intent
                and direction == self.direction
                and order == self.order
            ):
                continue

            self.profiles[i] = profile

            self.set_pcs_data(i)

            pcs_triplets = []
            if (
                profile.profileClass == b"nmcl"
                and "ncl2" in profile.tags
                and isinstance(profile.tags.ncl2, ICCP.NamedColor2Type)
                and profile.connectionColorSpace in (b"Lab", b"XYZ")
            ):
                for k in profile.tags.ncl2:
                    v = profile.tags.ncl2[k]
                    color = list(v.pcs.values())
                    if profile.connectionColorSpace == b"Lab":
                        # Need to convert to XYZ
                        color = colormath.Lab2XYZ(*color)
                    if intent == "a" and "wtpt" in profile.tags:
                        color = colormath.adapt(
                            color[0],
                            color[1],
                            color[2],
                            whitepoint_destination=list(profile.tags.wtpt.ir.values()),
                        )
                    pcs_triplets.append(color)
                pcs_triplets.sort()
            elif profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
                self.profiles[i] = None
                self.errors.append(
                    Error(
                        "\n".join(
                            [
                                lang.getstr("profile.iccv4.unsupported"),
                                profile.getDescription(),
                            ]
                        )
                    )
                )
                continue
            else:
                channels = {
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
                }.get(profile.colorSpace)

                if not channels:
                    self.errors.append(
                        Error(
                            lang.getstr(
                                "profile.unsupported",
                                (profile.profileClass, profile.colorSpace),
                            )
                        )
                    )
                    continue

                # Create input values
                device_values = []
                if profile.colorSpace in (b"Lab", b"Luv", b"XYZ", b"Yxy"):
                    # Use ICC PCSXYZ encoding range
                    minv = 0.0
                    maxv = 0xFFFF / 32768.0
                else:
                    minv = 0.0
                    maxv = 1.0
                step = (maxv - minv) / (self.size - 1)
                for j in range(min(3, channels)):
                    for k in range(min(3, channels)):
                        device_value = [0.0] * channels
                        device_value[j] = maxv
                        if j != k or channels == 1:
                            for l in range(self.size):
                                device_value[k] = minv + step * l
                                device_values.append(list(device_value))
                if profile.colorSpace in (
                    b"HLS",
                    b"HSV",
                    b"Lab",
                    b"Luv",
                    b"YCbr",
                    b"Yxy",
                ):
                    # Convert to actual color space
                    # TODO: Handle HLS and YCbr
                    tmp = list(device_values)
                    device_values = []
                    for j, values in enumerate(tmp):
                        if profile.colorSpace == b"HSV":
                            HSV = list(colormath.RGB2HSV(*values))
                            device_values.append(HSV)
                        elif profile.colorSpace == b"Lab":
                            Lab = list(colormath.XYZ2Lab(*[v * 100 for v in values]))
                            device_values.append(Lab)
                        elif profile.colorSpace == b"Luv":
                            Luv = list(colormath.XYZ2Luv(*[v * 100 for v in values]))
                            device_values.append(Luv)
                        elif profile.colorSpace == b"Yxy":
                            xyY = list(colormath.XYZ2xyY(*values))
                            device_values.append(xyY)

                # Add white
                if profile.colorSpace == b"RGB":
                    device_values.append([1.0] * channels)
                elif profile.colorSpace == b"HLS":
                    device_values.append([0, 1, 0])
                elif profile.colorSpace == b"HSV":
                    device_values.append([0, 0, 1])
                elif profile.colorSpace in (b"Lab", b"Luv", b"YCbr"):
                    if profile.colorSpace == b"YCbr":
                        device_values.append([1.0, 0.0, 0.0])
                    else:
                        device_values.append([100.0, 0.0, 0.0])
                elif profile.colorSpace in (b"XYZ", b"Yxy"):
                    if profile.colorSpace == b"XYZ":
                        device_values.append(list(profile.tags.wtpt.pcs.values()))
                    else:
                        device_values.append(profile.tags.wtpt.pcs.xyY)
                elif profile.colorSpace != b"GRAY":
                    device_values.append([0.0] * channels)

                if debug:
                    print("In:")
                    for v in device_values:
                        print(" ".join(("%3.4f",) * len(v)) % tuple(v))

                # Lookup device -> XYZ values through profile using xicclu
                if direction == "ib" and intent not in "ar":
                    fwd_intent = "r"
                else:
                    fwd_intent = intent
                try:
                    # Device -> PCS, fwd
                    odata = self.worker.xicclu(
                        profile, device_values, intent, "f", order
                    )
                    if direction == "ib":
                        # PCS -> device, bwd
                        odata = self.worker.xicclu(profile, odata, intent, "b", order)
                        # Device -> PCS, fwd
                        odata = self.worker.xicclu(
                            profile, odata, fwd_intent, "f", order
                        )
                except Exception as exception:
                    self.errors.append(Error(str(exception)))
                    continue

                if debug:
                    print("Out:")
                for pcs_triplet in odata:
                    if debug:
                        print(
                            " ".join(("%3.4f",) * len(pcs_triplet)) % tuple(pcs_triplet)
                        )
                    pcs_triplets.append(pcs_triplet)
                    if profile.connectionColorSpace == b"Lab":
                        pcs_triplets[-1] = list(colormath.Lab2XYZ(*pcs_triplets[-1]))

            if len(self.pcs_data) < i + 1:
                self.pcs_data.append(pcs_triplets)
            else:
                self.pcs_data[i] = pcs_triplets

        # Remove temporary files
        self.worker.wrapup(False)

        self.intent = intent
        self.direction = direction
        self.order = order


class GamutViewOptions(wx_Panel):
    def __init__(self, *args, **kwargs):
        scale = getcfg("app.dpi") / config.get_default_dpi()
        if scale < 1:
            scale = 1

        super(GamutViewOptions, self).__init__(*args, **kwargs)
        self.SetBackgroundColour(BGCOLOUR)
        self.sizer = wx.FlexGridSizer(0, 3, 4, 0)
        self.sizer.AddGrowableCol(0)
        self.sizer.AddGrowableCol(1)
        self.sizer.AddGrowableCol(2)
        self.SetSizer(self.sizer)

        self.sizer.Add((0, 0))
        legendsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(legendsizer)

        # Whitepoint legend
        legendsizer.Add(
            wx.StaticBitmap(self, -1, getbitmap("theme/cross-2px-12x12-fff")),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=2,
        )
        self.whitepoint_legend = wx.StaticText(self, -1, lang.getstr("whitepoint"))
        self.whitepoint_legend.SetMaxFontSize(11)
        self.whitepoint_legend.SetForegroundColour(FGCOLOUR)
        legendsizer.Add(
            self.whitepoint_legend, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=10
        )

        # Comparison profile whitepoint legend
        self.comparison_whitepoint_bmp = wx.StaticBitmap(
            self, -1, getbitmap("theme/x-2px-12x12-999")
        )
        legendsizer.Add(
            self.comparison_whitepoint_bmp,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=20,
        )
        self.comparison_whitepoint_legend = wx.StaticText(
            self,
            -1,
            "{} ({})".format(
                lang.getstr("whitepoint"), lang.getstr("comparison_profile")
            ),
        )
        self.comparison_whitepoint_legend.SetMaxFontSize(11)
        self.comparison_whitepoint_legend.SetForegroundColour(FGCOLOUR)
        legendsizer.Add(
            self.comparison_whitepoint_legend,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=8,
        )
        self.sizer.Add((0, 0))

        # Empty 'row'
        self.sizer.Add((0, 0))
        self.sizer.Add((0, 0))
        self.sizer.Add((0, 0))

        self.sizer.Add((0, 0))
        self.options_sizer = wx.FlexGridSizer(0, 3, 4, 8)
        self.options_sizer.AddGrowableCol(2)
        self.sizer.Add(self.options_sizer, flag=wx.EXPAND)

        # Colorspace select
        self.colorspace_outline_bmp = wx.StaticBitmap(
            self, -1, getbitmap("theme/solid-16x2-666")
        )
        self.options_sizer.Add(
            self.colorspace_outline_bmp, flag=wx.ALIGN_CENTER_VERTICAL
        )
        self.colorspace_label = wx.StaticText(self, -1, lang.getstr("colorspace"))
        self.colorspace_label.SetMaxFontSize(11)
        self.colorspace_label.SetForegroundColour(FGCOLOUR)
        self.options_sizer.Add(self.colorspace_label, flag=wx.ALIGN_CENTER_VERTICAL)
        self.colorspace_select = wx.Choice(
            parent=self,
            id=-1,
            size=(150 * scale, -1),
            choices=[
                "CIE a*b*",
                "CIE u*v*",
                "CIE u'v'",
                "CIE xy",
                "DIN99",
                "DIN99b",
                "DIN99c",
                "DIN99d",
                "ICtCp",
                "IPT",
                "Lpt",
            ],
        )
        self.options_sizer.Add(
            self.colorspace_select, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND
        )
        self.colorspace_select.Bind(wx.EVT_CHOICE, self.generic_select_handler)
        self.colorspace_select.SetSelection(0)

        # Colorspace outline
        self.options_sizer.Add((0, 0))
        self.options_sizer.Add((0, 0))
        self.draw_gamut_outline_cb = CustomCheckBox(
            parent=self, id=-1, label=lang.getstr("colorspace.show_outline")
        )
        self.draw_gamut_outline_cb.Bind(
            wx.EVT_CHECKBOX, self.draw_gamut_outline_handler
        )
        self.draw_gamut_outline_cb.SetMaxFontSize(11)
        self.draw_gamut_outline_cb.SetForegroundColour(FGCOLOUR)
        self.draw_gamut_outline_cb.SetValue(True)
        self.options_sizer.Add(
            self.draw_gamut_outline_cb,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=4,
        )

        # Colortemperature curve select
        self.whitepoint_bmp = wx.StaticBitmap(
            self, -1, getbitmap("theme/solid-16x1-fff")
        )
        self.options_sizer.Add(self.whitepoint_bmp, flag=wx.ALIGN_CENTER_VERTICAL)
        self.whitepoint_label = wx.StaticText(
            self, -1, lang.getstr("whitepoint.colortemp.locus.curve")
        )
        self.whitepoint_label.SetMaxFontSize(11)
        self.whitepoint_label.SetForegroundColour(FGCOLOUR)
        self.options_sizer.Add(self.whitepoint_label, flag=wx.ALIGN_CENTER_VERTICAL)
        self.whitepoint_select = wx.Choice(
            self,
            -1,
            size=(150 * scale, -1),
            choices=[
                lang.getstr("calibration.file.none"),
                lang.getstr("whitepoint.colortemp.locus.daylight"),
                lang.getstr("whitepoint.colortemp.locus.blackbody"),
            ],
        )
        self.options_sizer.Add(
            self.whitepoint_select, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND
        )
        self.whitepoint_select.Bind(wx.EVT_CHOICE, self.generic_select_handler)
        self.whitepoint_select.SetSelection(0)
        self.whitepoint_bmp.Hide()

        # Comparison profile select
        self.comparison_profile_bmp = wx.StaticBitmap(
            self, -1, getbitmap("theme/dashed-16x2-666")
        )
        self.options_sizer.Add(
            self.comparison_profile_bmp, flag=wx.ALIGN_CENTER_VERTICAL
        )
        self.comparison_profile_label = wx.StaticText(
            self, -1, lang.getstr("comparison_profile")
        )
        self.comparison_profile_label.SetMaxFontSize(11)
        self.comparison_profile_label.SetForegroundColour(FGCOLOUR)
        self.options_sizer.Add(
            self.comparison_profile_label, flag=wx.ALIGN_CENTER_VERTICAL
        )
        self.comparison_profiles = dict([(lang.getstr("calibration.file.none"), None)])
        srgb = None
        try:
            srgb = ICCP.ICCProfile(get_data_path("ref/sRGB.icm"))
        except EnvironmentError:
            pass
        except Exception as exception:
            print(exception)
        if srgb:
            self.comparison_profiles[srgb.getDescription()] = srgb
        for profile in config.get_standard_profiles():
            desc = profile.getDescription()
            if desc not in self.comparison_profiles:
                self.comparison_profiles[desc] = profile
        self.comparison_profile_select = wx.Choice(
            parent=self, id=-1, size=(150 * scale, -1), choices=[]
        )
        self.comparison_profiles_sort()
        self.options_sizer.Add(
            self.comparison_profile_select, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND
        )
        self.comparison_profile_select.Bind(
            wx.EVT_CHOICE, self.comparison_profile_select_handler
        )
        droptarget = FileDrop(
            self.TopLevelParent,
            {
                ".icc": self.comparison_profile_drop_handler,
                ".icm": self.comparison_profile_drop_handler,
            },
        )
        self.comparison_profile_select.SetDropTarget(droptarget)
        if srgb:
            self.comparison_profile_select.SetSelection(1)
            self.comparison_profile_select.SetToolTipString(srgb.fileName)

        # Rendering intent select
        self.options_sizer.Add((0, 0))
        self.rendering_intent_label = wx.StaticText(
            self, -1, lang.getstr("rendering_intent")
        )
        self.rendering_intent_label.SetMaxFontSize(11)
        self.rendering_intent_label.SetForegroundColour(FGCOLOUR)
        self.options_sizer.Add(
            self.rendering_intent_label, flag=wx.ALIGN_CENTER_VERTICAL
        )
        self.rendering_intent_select = wx.Choice(
            self,
            -1,
            size=(150 * scale, -1),
            choices=[
                lang.getstr("gamap.intents.a"),
                lang.getstr("gamap.intents.r"),
                lang.getstr("gamap.intents.p"),
                lang.getstr("gamap.intents.s"),
            ],
        )
        self.options_sizer.Add(
            self.rendering_intent_select, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND
        )
        self.rendering_intent_select.Bind(
            wx.EVT_CHOICE, self.rendering_intent_select_handler
        )
        self.rendering_intent_select.SetSelection(0)

        self.options_sizer.Add((0, 0))

        # LUT toggle
        self.toggle_clut = CustomCheckBox(self, -1, "LUT")
        self.toggle_clut.SetForegroundColour(FGCOLOUR)
        self.toggle_clut.SetMaxFontSize(11)
        self.options_sizer.Add(self.toggle_clut, flag=wx.ALIGN_CENTER_VERTICAL)
        self.toggle_clut.Bind(wx.EVT_CHECKBOX, self.toggle_clut_handler)
        self.toggle_clut.Hide()

        # Direction selection
        self.direction_select = wx.Choice(
            self,
            -1,
            size=(150 * scale, -1),
            choices=[
                lang.getstr("direction.forward"),
                lang.getstr("direction.backward.inverted"),
            ],
        )
        self.options_sizer.Add(
            self.direction_select, flag=wx.ALIGN_CENTER_VERTICAL | wx.EXPAND
        )
        self.direction_select.Bind(wx.EVT_CHOICE, self.direction_select_handler)
        self.direction_select.SetSelection(0)

        self.sizer.Add((0, 0))

    def DrawCanvas(self, profile_no=None, reset=True):
        # Gamut plot
        parent = self.TopLevelParent
        parent.client.SetEnableCenterLines(False)
        parent.client.SetEnableDiagonals(False)
        parent.client.SetEnableGrid(True)
        parent.client.SetEnablePointLabel(False)
        try:
            parent.client.setup(
                [self.comparison_profile, parent.profile],
                profile_no,
                intent=self.intent,
                direction=self.direction,
                order=self.order,
            )
        except Exception as exception:
            show_result_dialog(exception, parent)
        if reset:
            parent.client.reset()
            parent.client.resetzoom()
        wx.CallAfter(self.draw, center=reset)
        wx.CallAfter(parent.handle_errors)

    @property
    def colorspace(self):
        return self.get_colorspace()

    @property
    def comparison_profile(self) -> str:
        """Return the currently selected comparison profile name.

        Returns:
            str: The current comparison profile name.
        """
        index = self.comparison_profile_select.GetSelection()
        if index == -1:  # Fix for #67
            index = 0
            self.comparison_profile_select.SetSelection(index)
        return list(self.comparison_profiles.values())[index]

    def comparison_profile_drop_handler(self, path):
        try:
            profile = ICCP.ICCProfile(path)
        except Exception as exception:
            show_result_dialog(exception, self.TopLevelParent)
        else:
            desc = profile.getDescription()
            self.comparison_profiles[desc] = profile
            self.comparison_profiles_sort()
            self.comparison_profile_select.SetSelection(
                list(self.comparison_profiles.keys()).index(desc)
            )
            self.comparison_profile_select_handler(None)

    def comparison_profile_select_handler(self, event):
        index = self.comparison_profile_select.GetSelection()
        if index > 0:
            self.comparison_profile_select.SetToolTipString(
                self.comparison_profile.fileName
            )
        else:
            self.comparison_profile_select.SetToolTip(None)
        self.comparison_whitepoint_bmp.Show(index > 0)
        self.comparison_whitepoint_legend.Show(index > 0)
        self.comparison_profile_bmp.Show(index > 0)
        self.DrawCanvas(0, reset=False)

    def comparison_profiles_sort(self):
        comparison_profiles = dict_slice(self.comparison_profiles, 2)
        comparison_profiles = dict_sort(comparison_profiles, key=lambda s: s.lower())
        self.comparison_profiles = dict_slice(self.comparison_profiles, None, 2)
        self.comparison_profiles.update(comparison_profiles)
        self.comparison_profile_select.SetItems(list(self.comparison_profiles.keys()))

    @property
    def direction(self):
        index = self.direction_select.GetSelection()
        if index == -1:  # Fix for #67
            index = 0
            self.direction_select.SetSelection(index)
        if self.direction_select.IsShown():
            return {0: "f", 1: "ib"}.get(self.direction_select.GetSelection())
        else:
            return "f"

    def draw(self, center=False):
        index = self.whitepoint_select.GetSelection()
        if index == -1:  # Fix for #67
            index = 0
            self.whitepoint_select.SetSelection(index)
        colorspace = self.colorspace
        parent = self.TopLevelParent
        parent.client.proportional = True
        parent.client.DrawCanvas(
            f"{colorspace} {lang.getstr('colorspace')}",
            colorspace,
            whitepoint=index,
            center=center,
            show_outline=self.draw_gamut_outline_cb.GetValue(),
        )

    def draw_gamut_outline_handler(self, event):
        self.colorspace_outline_bmp.Show(self.draw_gamut_outline_cb.GetValue())
        self.draw()

    def generic_select_handler(self, event):
        self.whitepoint_bmp.Show(self.whitepoint_select.GetSelection() > 0)
        parent = self.TopLevelParent
        if parent.client.profiles:
            self.draw(center=event.GetId() == self.colorspace_select.GetId())
        else:
            self.DrawCanvas()

    def get_colorspace(self, dimensions: int = 2) -> str:
        """Return currently selected colorspace name.

        Args:
            dimensions (int): The dimensions, default is 2.

        Returns:
            str: The name of the currently selected colorspace.
        """
        index = self.colorspace_select.GetSelection()
        if index == -1:  # Fix for #67
            index = 0
            self.colorspace_select.SetSelection(index)
        return {
            0: "a*b*" if dimensions == 2 else "Lab",
            1: "u*v*" if dimensions == 2 else "Luv",
            2: "u'v'" if dimensions == 2 else "Lu'v'",
            3: "xy" if dimensions == 2 else "xyY",
            4: "DIN99",
            5: "DIN99b",
            6: "DIN99c",
            7: "DIN99d",
            8: "ICtCp",
            9: "IPT",
            10: "Lpt",
        }.get(index, "a*b*" if dimensions == 2 else "Lab")

    @property
    def intent(self) -> str:
        """Return rendering intent.

        Returns:
            str: The single letter rendering intent.
        """
        index = self.rendering_intent_select.GetSelection()
        if index == -1:  # Fix for #67
            index = 0
            self.rendering_intent_select.SetSelection(index)
        return {0: "a", 1: "r", 2: "p", 3: "s"}.get(index)

    @property
    def order(self):
        parent = self.TopLevelParent
        return {True: "n", False: "r"}.get(
            bool(parent.profile)
            and not ("B2A0" in parent.profile.tags or "A2B0" in parent.profile.tags)
            or self.toggle_clut.GetValue()
        )

    def rendering_intent_select_handler(self, event):
        self.DrawCanvas(reset=False)

    def direction_select_handler(self, event):
        self.DrawCanvas(reset=False)

    def toggle_clut_handler(self, event):
        parent = self.TopLevelParent
        self.Freeze()
        self.direction_select.Enable(
            bool(parent.profile)
            and "B2A0" in parent.profile.tags
            and "A2B0" in parent.profile.tags
            and self.toggle_clut.GetValue()
        )
        self.DrawCanvas(reset=False)
        self.Thaw()


class PIFrame_2WaySplitter(TwoWaySplitter):
    def OnLeftDClick(self, event):
        if not self.IsEnabled():
            return

        pt = event.GetPosition()

        if self.GetMode(pt):

            barSize = self._GetSashSize()

            winborder, titlebar = get_platform_window_decoration_size()

            win0w = self.GetTopLeft().Size[0]

            self.Freeze()
            TwoWaySplitter.OnLeftDClick(self, event)
            if self._expanded < 0:
                self.Parent.SetMinSize(
                    (
                        defaults["size.profile_info.split.w"] + winborder * 2,
                        self.Parent.GetMinSize()[1],
                    )
                )
                if (
                    not self.Parent.IsMaximized()
                    and self.Parent.ClientSize[0] < self.GetSplitSize()[0]
                ):
                    self.Parent.ClientSize = (
                        self.GetSplitSize()[0],
                        self.Parent.ClientSize[1],
                    )
            else:
                self.Parent.SetMinSize(
                    (
                        defaults["size.profile_info.w"] + winborder * 2,
                        self.Parent.GetMinSize()[1],
                    )
                )
                w = max(self.GetExpandedSize()[0], self._splitx)
                if not self.Parent.IsMaximized() and self.Parent.ClientSize[0] > w:
                    self.Parent.ClientSize = (w, self.Parent.ClientSize[1])
            if os.getenv("XDG_SESSION_TYPE") == "wayland":
                self.Parent.MaxSize = self.Parent.Size
                wx.CallAfter(set_maxsize, self.Parent, (-1, -1))
            if self.GetTopLeft().Size[0] != win0w:
                self.Parent.redraw()
            self.Parent.resize_grid()
            self.Thaw()


class ProfileInfoFrame(LUTFrame):
    def __init__(self, *args, **kwargs):

        if len(args) < 3 and "title" not in kwargs:
            kwargs["title"] = lang.getstr("profile.info")
        if "name" not in kwargs:
            kwargs["name"] = "profile_info"

        BaseFrame.__init__(self, *args, **kwargs)

        self.SetIcons(
            config.get_icon_bundle([256, 48, 32, 16], f"{appname}-profile-info")
        )

        self.profile = None
        self.xLabel = lang.getstr("in")
        self.yLabel = lang.getstr("out")

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

        self.splitter = PIFrame_2WaySplitter(
            self, -1, agwStyle=wx.SP_LIVE_UPDATE | wx.SP_NOSASH
        )
        self.sizer.Add(self.splitter, 1, flag=wx.EXPAND)

        p1 = wx_Panel(self.splitter, name="canvaspanel")
        p1.SetBackgroundColour(BGCOLOUR)
        p1.sizer = wx.BoxSizer(wx.VERTICAL)
        p1.SetSizer(p1.sizer)
        self.splitter.AppendWindow(p1)

        self.plot_mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        p1.sizer.Add(self.plot_mode_sizer, flag=wx.ALIGN_CENTER | wx.TOP, border=12)

        # The order of the choice items is significant for compatibility
        # with LUTFrame:
        # 0 = vcgt,
        # 1 = [rgb]TRC
        # 2 = gamut
        self.plot_mode_select = wx.Choice(
            p1,
            -1,
            choices=[
                lang.getstr("vcgt"),
                lang.getstr("[rgb]TRC"),
                lang.getstr("gamut"),
            ],
        )
        self.plot_mode_sizer.Add(self.plot_mode_select, flag=wx.ALIGN_CENTER_VERTICAL)
        self.plot_mode_select.Bind(wx.EVT_CHOICE, self.plot_mode_select_handler)
        self.plot_mode_select.Disable()

        self.tooltip_btn = BitmapButton(
            p1, -1, geticon(16, "question-inverted"), style=wx.NO_BORDER
        )
        self.tooltip_btn.SetBackgroundColour(BGCOLOUR)
        self.tooltip_btn.Bind(wx.EVT_BUTTON, self.tooltip_handler)
        self.tooltip_btn.SetToolTipString(lang.getstr("gamut_plot.tooltip"))
        self.plot_mode_sizer.Add(
            self.tooltip_btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8
        )

        self.save_plot_btn = BitmapButton(
            p1, -1, geticon(16, "image-x-generic-inverted"), style=wx.NO_BORDER
        )
        self.save_plot_btn.SetBackgroundColour(BGCOLOUR)
        self.save_plot_btn.Bind(wx.EVT_BUTTON, self.SaveFile)
        self.save_plot_btn.SetToolTipString(
            f"{lang.getstr('save_as')} (*.bmp, *.xbm, *.xpm, *.jpg, *.png)"
        )
        self.save_plot_btn.Disable()
        self.plot_mode_sizer.Add(
            self.save_plot_btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8
        )

        self.view_3d_btn = BitmapButton(p1, -1, geticon(16, "3D"), style=wx.NO_BORDER)
        self.view_3d_btn.SetBackgroundColour(BGCOLOUR)
        self.view_3d_btn.Bind(wx.EVT_BUTTON, self.view_3d)
        self.view_3d_btn.Bind(wx.EVT_CONTEXT_MENU, self.view_3d_format_popup)
        self.view_3d_btn.SetToolTipString(lang.getstr("view.3d"))
        self.view_3d_btn.Disable()
        self.plot_mode_sizer.Add(
            self.view_3d_btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=12
        )
        self.view_3d_format_btn = BitmapButton(
            p1, -1, getbitmap("theme/dropdown-arrow"), style=wx.NO_BORDER
        )
        self.view_3d_format_btn.MinSize = (-1, self.view_3d_btn.Size[1])
        self.view_3d_format_btn.SetBackgroundColour(BGCOLOUR)
        self.view_3d_format_btn.Bind(wx.EVT_BUTTON, self.view_3d_format_popup)
        self.view_3d_format_btn.Bind(wx.EVT_CONTEXT_MENU, self.view_3d_format_popup)
        self.view_3d_format_btn.SetToolTipString(lang.getstr("view.3d"))
        self.view_3d_format_btn.Disable()
        self.plot_mode_sizer.Add(
            self.view_3d_format_btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=4
        )

        self.client = GamutCanvas(p1)
        p1.sizer.Add(
            self.client,
            1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
            border=4,
        )

        self.options_panel = SimpleBook(p1)
        self.options_panel.SetBackgroundColour(BGCOLOUR)
        p1.sizer.Add(self.options_panel, flag=wx.EXPAND | wx.BOTTOM, border=8)

        self.status = BitmapBackgroundPanelText(p1)
        self.status.SetMaxFontSize(11)
        self.status.label_y = 0
        self.status.textshadow = False
        self.status.SetBackgroundColour(BGCOLOUR)
        self.status.SetForegroundColour(FGCOLOUR)
        h = self.status.GetTextExtent("Ig")[1]
        self.status.SetMinSize((0, h * 2 + 10))
        p1.sizer.Add(self.status, flag=wx.EXPAND)

        self.gamut_status = BitmapBackgroundPanelTextGamut(p1)
        self.gamut_status.SetMaxFontSize(11)
        self.gamut_status.label_y = 0
        self.gamut_status.textshadow = False
        self.gamut_status.SetBackgroundColour(BGCOLOUR)
        self.gamut_status.SetForegroundColour(FGCOLOUR)
        h = self.gamut_status.GetTextExtent("Ig")[1]
        self.gamut_status.SetMinSize((0, h * 2 + 10))
        p1.sizer.Add(self.gamut_status, flag=wx.EXPAND)

        # Gamut view options
        self.gamut_view_options = GamutViewOptions(p1)
        self.options_panel.AddPage(self.gamut_view_options, "")

        # Curve view options
        self.lut_view_options = wx_Panel(p1, name="lut_view_options")
        self.lut_view_options.SetBackgroundColour(BGCOLOUR)
        self.lut_view_options_sizer = self.box_sizer = wx.FlexGridSizer(0, 3, 4, 4)
        self.lut_view_options_sizer.AddGrowableCol(0)
        self.lut_view_options_sizer.AddGrowableCol(2)
        self.lut_view_options.SetSizer(self.lut_view_options_sizer)
        self.options_panel.AddPage(self.lut_view_options, "")

        self.lut_view_options_sizer.Add((0, 0))

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.lut_view_options_sizer.Add(
            hsizer, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=8
        )

        self.rendering_intent_select = wx.Choice(
            self.lut_view_options,
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
            self.lut_view_options,
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

        self.lut_view_options_sizer.Add((0, 0))

        self.lut_view_options_sizer.Add((0, 0))

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.lut_view_options_sizer.Add(hsizer, flag=wx.ALIGN_CENTER)

        hsizer.Add((16, 0))

        self.show_as_L = CustomCheckBox(self.lut_view_options, -1, "L* \u2192")
        self.show_as_L.SetForegroundColour(FGCOLOUR)
        self.show_as_L.SetValue(True)
        hsizer.Add(self.show_as_L, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
        self.show_as_L.Bind(wx.EVT_CHECKBOX, self.DrawLUT)

        self.add_toggles(self.lut_view_options, hsizer)

        self.toggle_clut = CustomCheckBox(self.lut_view_options, -1, "LUT")
        self.toggle_clut.SetForegroundColour(FGCOLOUR)
        hsizer.Add(self.toggle_clut, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=16)
        self.toggle_clut.Bind(wx.EVT_CHECKBOX, self.toggle_clut_handler)

        self.lut_view_options_sizer.Add((0, 0))

        p2 = wx_Panel(self.splitter, name="gridpanel")
        p2.sizer = wx.BoxSizer(wx.VERTICAL)
        p2.SetSizer(p2.sizer)
        self.splitter.AppendWindow(p2)

        self.grid = CustomGrid(p2, -1)
        self.grid.alternate_row_label_background_color = wx.Colour(230, 230, 230)
        self.grid.alternate_cell_background_color = (
            self.grid.alternate_row_label_background_color
        )
        self.grid.draw_horizontal_grid_lines = False
        self.grid.draw_vertical_grid_lines = False
        self.grid.draw_row_labels = False
        self.grid.show_cursor_outline = False
        self.grid.style = ""
        self.grid.CreateGrid(0, 2)
        self.grid.SetCellHighlightPenWidth(0)
        self.grid.SetCellHighlightROPenWidth(0)
        self.grid.SetDefaultCellBackgroundColour(self.grid.GetLabelBackgroundColour())
        font = self.grid.GetDefaultCellFont()
        if font.PointSize > 11:
            font.PointSize = 11
            self.grid.SetDefaultCellFont(font)
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
        self.grid.SetRowLabelSize(self.grid.GetDefaultRowSize())
        self.grid.SetColLabelSize(0)
        self.grid.DisableDragRowSize()
        self.grid.EnableDragColSize()
        self.grid.EnableEditing(False)
        self.grid.EnableGridLines(False)
        self.grid.Bind(wx.grid.EVT_GRID_COL_SIZE, self.resize_grid)
        p2.sizer.Add(self.grid, 1, flag=wx.EXPAND)

        drophandlers = {".icc": self.drop_handler, ".icm": self.drop_handler}
        self.droptarget = FileDrop(self, drophandlers)
        self.client.SetDropTarget(self.droptarget)
        droptarget = FileDrop(self, drophandlers)
        self.grid.SetDropTarget(droptarget)

        min_w = max(
            self.options_panel.GetBestSize()[0] + 24,
            defaults["size.profile_info.w"] - self.splitter._GetSashSize(),
        )

        self.splitter.SetMinimumPaneSize(min_w)
        self.splitter.SetHSplit(0)

        border, titlebar = get_platform_window_decoration_size()
        self.SetSaneGeometry(
            getcfg("position.profile_info.x"),
            getcfg("position.profile_info.y"),
            defaults["size.profile_info.split.w"],
            getcfg("size.profile_info.h"),
        )
        self.SetMinSize(
            (min_w + border * 2, defaults["size.profile_info.h"] + titlebar + border)
        )
        self.splitter.SetSplitSize(
            (defaults["size.profile_info.split.w"], self.ClientSize[1])
        )
        self.splitter.SetExpandedSize(self.ClientSize)

        self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self.OnSashPosChanging)

        self.display_no = -1
        self.display_rects = get_display_rects()

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

    def DrawCanvas(self, profile_no=None, reset=True):
        self.SetStatusText("")
        if self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1:
            # Gamut plot
            self.plot_mode_sizer.Show(self.view_3d_btn)
            self.plot_mode_sizer.Show(self.view_3d_format_btn)
            self.options_panel.GetCurrentPage().DrawCanvas(reset=reset)
            self.save_plot_btn.Enable()
            self.view_3d_btn.Enable()
            self.view_3d_format_btn.Enable()
        else:
            # Curves plot
            self.plot_mode_sizer.Hide(self.view_3d_btn)
            self.plot_mode_sizer.Hide(self.view_3d_format_btn)
            self.client.SetEnableCenterLines(True)
            self.client.SetEnableDiagonals("Bottomleft-Topright")
            self.client.SetEnableGrid(False)
            self.client.SetEnablePointLabel(True)
            if (
                isinstance(self.profile.tags.get("vcgt"), ICCP.VideoCardGammaType)
                or (self.rTRC and self.gTRC and self.bTRC)
                or ("B2A0" in self.profile.tags or "A2B0" in self.profile.tags)
            ):
                self.DrawLUT()
                self.handle_errors()
            else:
                self.client.DrawLUT()
        self.splitter.GetTopLeft().sizer.Layout()
        self.splitter.GetTopLeft().Refresh()

    def LoadProfile(self, profile, reset=True):
        if not isinstance(profile, ICCP.ICCProfile):
            try:
                profile = ICCP.ICCProfile(profile)
            except (IOError, ICCP.ICCProfileInvalidError):
                show_result_dialog(
                    Error(f"{lang.getstr('profile.invalid')}\n{profile}"), self
                )
                self.DrawCanvas(reset=reset)
                return
        if (
            not reset
            and getattr(self, "profile", None)
            and self.profile.colorSpace != profile.colorSpace
        ):
            reset = True
        self.profile = profile
        cinfo = []
        vinfo = []
        if "meta" in profile.tags:
            for key in ("avg", "max", "rms"):
                try:
                    dE = float(profile.tags.meta.getvalue(f"ACCURACY_dE76_{key}"))
                except (TypeError, ValueError):
                    pass

            gamuts = (
                ("srgb", "sRGB", ICCP.GAMUT_VOLUME_SRGB),
                ("adobe-rgb", "Adobe RGB", ICCP.GAMUT_VOLUME_ADOBERGB),
                ("dci-p3", "DCI P3", ICCP.GAMUT_VOLUME_SMPTE431_P3),
            )
            for key, name, _volume in gamuts:
                try:
                    gamut_coverage = profile.tags.meta.getvalue(
                        f"GAMUT_coverage({key})"
                    )
                    gamut_coverage = (
                        float(gamut_coverage)
                        if gamut_coverage is not None
                        else gamut_coverage
                    )
                except (TypeError, ValueError):
                    traceback.print_exc()
                    gamut_coverage = None
                if gamut_coverage:
                    cinfo.append(f"{gamut_coverage * 100:.1f}% {name}")
            try:
                gamut_volume = float(profile.tags.meta.getvalue("GAMUT_volume"))
            except (TypeError, ValueError):
                traceback.print_exc()
                gamut_volume = None
            if gamut_volume:
                for _key, name, volume in gamuts:
                    vinfo.append(
                        f"{gamut_volume * ICCP.GAMUT_VOLUME_SRGB / volume * 100:.1f}% {name}"
                    )
                    if len(vinfo) == len(cinfo):
                        break

            if gamut_coverage and gamut_volume:
                gamut_cov_text = f"{cinfo[0]}    {cinfo[1]}    {cinfo[2]}"
                self.SetGamutStatusText(gamut_cov_text)

        for channel in "rgb":
            trc = profile.tags.get(f"{channel}TRC", profile.tags.get("kTRC"))
            if isinstance(trc, ICCP.ParametricCurveType):
                trc = trc.get_trc()
            setattr(self, f"{channel}TRC", trc)
            setattr(self, f"tf_{channel}TRC", trc)
        self.trc = None

        self.gamut_view_options.direction_select.Enable(
            "B2A0" in self.profile.tags and "A2B0" in self.profile.tags
        )
        if not self.gamut_view_options.direction_select.Enabled:
            self.gamut_view_options.direction_select.SetSelection(0)
        self.gamut_view_options.toggle_clut.SetValue(
            "B2A0" in profile.tags or "A2B0" in profile.tags
        )
        self.gamut_view_options.toggle_clut.Show(
            "B2A0" in profile.tags or "A2B0" in profile.tags
        )
        self.gamut_view_options.toggle_clut.Enable(
            isinstance(self.rTRC, ICCP.CurveType)
            and isinstance(self.gTRC, ICCP.CurveType)
            and isinstance(self.bTRC, ICCP.CurveType)
        )
        self.toggle_clut.SetValue("B2A0" in profile.tags or "A2B0" in profile.tags)

        plot_mode = self.plot_mode_select.GetStringSelection()
        choice = []
        info = profile.get_info()
        self.client.errors = []
        if (self.rTRC and self.gTRC and self.bTRC) or (
            self.toggle_clut.GetValue()
            and profile.colorSpace in (b"RGB", b"GRAY", b"CMYK")
        ):
            if "vcgt" in profile.tags or "MS00" in profile.tags:
                choice.append(lang.getstr("vcgt"))
            try:
                self.lookup_tone_response_curves()
            except Exception as exception:
                wx.CallAfter(show_result_dialog, exception, self)
            else:
                choice.append(lang.getstr("[rgb]TRC"))
        choice = self.add_shaper_curves(choice)
        choice.append(lang.getstr("gamut"))
        self.Freeze()
        self.plot_mode_select.SetItems(choice)
        if not self.plot_mode_select.SetStringSelection(plot_mode):
            self.plot_mode_select.SetSelection(self.plot_mode_select.GetCount() - 1)
            reset = True
        self.select_current_page()
        self.plot_mode_select.Enable()

        self.SetTitle(
            " \u2014 ".join([lang.getstr("profile.info"), profile.getDescription()])
        )

        rows = [("", "")]
        lines = []
        for label, value in info:
            label = label.replace("\0", "")
            if value is None:
                value = ""
            elif not isinstance(value, str):
                value = str(value, "ascii")
            value = (
                wrap(universal_newlines(value.strip()).replace("\t", "\n"), 52)
                .replace("\0", "")
                .split("\n")
            )
            linecount = len(value)
            for i, line in enumerate(value):
                value[i] = line.strip()
            label = universal_newlines(label).split("\n")
            while len(label) < linecount:
                label.append("")
            lines.extend(list(zip(label, value)))
        for i, line in enumerate(lines):
            line = list(line)
            indent = re.match(r"\s+", line[0])
            for j, v in enumerate(line):
                if v.endswith("_"):
                    continue
                key = re.sub(
                    r"[^0-9A-Za-z]+",
                    "_",
                    strtr(line[j], {"\u0394E": "Delta E"}).lower().strip(),
                    0,
                ).strip("_")
                val = lang.getstr(key)
                if key != val:
                    line[j] = val
            if indent:
                # if i + 1 < len(lines) and lines[i + 1][0].startswith(" "):
                # marker = u" ├  "
                # else:
                # marker = u" └  "
                line[0] = indent.group() + line[0].strip()
            elif line[0]:
                # if i + 1 < len(lines) and lines[i + 1][0].startswith(" "):
                # marker = u"▼ "
                # else:
                # marker = u"► "
                pass
            rows.append(line)

        rows.append(("", ""))

        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.grid.AppendRows(len(rows))
        labelcolor = self.grid.GetLabelTextColour()
        alpha = 102
        namedcolor = False
        for i, (label, value) in enumerate(rows):
            self.grid.SetCellValue(i, 0, f" {label}")
            bgcolor = self.grid.GetCellBackgroundColour(i, 0)
            bgblend = (255 - alpha) / 255.0
            blend = alpha / 255.0
            textcolor = wx.Colour(
                int(round(bgblend * bgcolor.Red() + blend * labelcolor.Red())),
                int(round(bgblend * bgcolor.Green() + blend * labelcolor.Green())),
                int(round(bgblend * bgcolor.Blue() + blend * labelcolor.Blue())),
            )
            if label == lang.getstr("named_colors"):
                namedcolor = True
            elif label.strip() and label.lstrip() == label:
                namedcolor = False
            if namedcolor:
                color = re.match(r"(Lab|XYZ)((?:\s+-?\d+(?:\.\d+)){3,})", value)
            else:
                color = None
            if color:
                if color.groups()[0] == "Lab":
                    color = colormath.Lab2RGB(
                        *[float(v) for v in color.groups()[1].strip().split()],
                        **dict(scale=255),
                    )
                else:
                    # XYZ
                    color = colormath.XYZ2RGB(
                        *[float(v) for v in color.groups()[1].strip().split()],
                        **dict(scale=255),
                    )
                labelbgcolor = wx.Colour(*[int(round(v)) for v in color])
                rowlabelrenderer = CustomRowLabelRenderer(labelbgcolor)
            else:
                rowlabelrenderer = None
            self.grid.SetRowLabelRenderer(i, rowlabelrenderer)
            self.grid.SetCellTextColour(i, 0, textcolor)
            self.grid.SetCellValue(i, 1, value)

        self.grid.AutoSizeColumn(0)
        self.resize_grid()
        self.grid.ClearSelection()
        self.Layout()
        self.DrawCanvas(reset=reset)
        self.Thaw()

    def OnClose(self, event):
        if getattr(self.worker, "thread", None) and self.worker.thread.is_alive():
            self.worker.abort_subprocess(True)
            return
        self.worker.wrapup(False)
        writecfg(
            module="profile-info",
            options=(
                "3d.format",
                "last_cal_or_icc_path",
                "last_icc_path",
                "position.profile_info",
                "size.profile_info",
            ),
        )
        # Hide first (looks nicer)
        self.Hide()
        # Need to use CallAfter to prevent hang under Windows if minimized
        wx.CallAfter(self.Destroy)

    def OnMotion(self, event):
        if isinstance(event, wx.MouseEvent):
            xy = self.client._getXY(event)
        else:
            xy = event
        if self.plot_mode_select.GetSelection() < self.plot_mode_select.GetCount() - 1:
            # Curves plot
            if isinstance(event, wx.MouseEvent):
                if not event.LeftIsDown():
                    self.UpdatePointLabel(xy)
                else:
                    self.client.erase_pointlabel()
        else:
            # Gamut plot
            page = self.options_panel.GetCurrentPage()
            if page.colorspace in ("a*b*", "u*v*") or page.colorspace.startswith(
                "DIN99"
            ):
                format_ = "%.2f %.2f"
            else:
                format_ = "%.4f %.4f"
            whitepoint_no = page.whitepoint_select.GetSelection()
            if whitepoint_no > 0:
                if page.colorspace == "a*b*":
                    x, y, Y = colormath.Lab2xyY(100.0, xy[0], xy[1])
                elif page.colorspace == "u*v*":
                    X, Y, Z = colormath.Luv2XYZ(100.0, xy[0], xy[1])
                    x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
                elif page.colorspace == "u'v'":
                    x, y = colormath.u_v_2xy(xy[0], xy[1])
                elif page.colorspace.startswith("DIN99"):
                    # DIN99
                    L99 = colormath.Lab2DIN99(100, 0, 0)[0]
                    if page.colorspace == "DIN99b":
                        # DIN99b
                        a, b = colormath.DIN99b2Lab(L99, xy[0], xy[1])[1:]
                    elif page.colorspace == "DIN99c":
                        # DIN99c
                        a, b = colormath.DIN99c2Lab(L99, xy[0], xy[1])[1:]
                    elif page.colorspace == "DIN99d":
                        # DIN99d
                        a, b = colormath.DIN99d2Lab(L99, xy[0], xy[1])[1:]
                    else:
                        # DIN99
                        a, b = colormath.DIN992Lab(L99, xy[0], xy[1])[1:]
                    x, y = colormath.Lab2xyY(100.0, a, b)[:2]
                elif page.colorspace == "ICtCp":
                    X, Y, Z = colormath.ICtCp2XYZ(1.0, xy[0], xy[1])
                    x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
                elif page.colorspace == "IPT":
                    X, Y, Z = colormath.IPT2XYZ(1.0, xy[0], xy[1])
                    x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
                elif page.colorspace == "Lpt":
                    X, Y, Z = colormath.Lpt2XYZ(100.0, xy[0], xy[1])
                    x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
                else:
                    # xy
                    x, y = xy
                cct, delta = colormath.xy_CCT_delta(x, y, daylight=whitepoint_no == 1)
                status = format_ % xy
                if cct:
                    if delta:
                        locus = {"Blackbody": "blackbody", "Daylight": "daylight"}.get(
                            page.whitepoint_select.GetStringSelection(),
                            page.whitepoint_select.GetStringSelection(),
                        )
                        status = "%s, CCT %i (%s %.2f)" % (
                            format_ % xy,
                            cct,
                            lang.getstr("delta_e_to_locus", locus),
                            delta["E"],
                        )
                    else:
                        status = "%s, CCT %i" % (format_ % xy, cct)
                self.SetStatusText(status)
            else:
                self.SetStatusText(format_ % xy)
        if isinstance(event, wx.MouseEvent):
            event.Skip()  # Go to next handler

    def OnMove(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            setcfg("position.profile_info.x", x)
            setcfg("position.profile_info.y", y)
        if event:
            event.Skip()

    def OnSashPosChanging(self, event):
        self.splitter.SetExpandedSize(
            (self.splitter._splitx + self.splitter._GetSashSize(), self.ClientSize[1])
        )
        setcfg(
            "size.profile_info.w", self.splitter._splitx + self.splitter._GetSashSize()
        )
        wx.CallAfter(self.redraw)
        wx.CallAfter(self.resize_grid)

    def OnSize(self, event=None):
        if (
            self.IsShownOnScreen()
            and self.IsMaximized()
            and self.splitter._expanded < 0
        ):
            self.splitter.AdjustLayout()
        self.splitter.Refresh()
        wx.CallAfter(self.redraw)
        wx.CallAfter(self.resize_grid)
        if self.IsShownOnScreen() and not self.IsIconized():
            wx.CallAfter(self._setsize)
        if event:
            event.Skip()

    def OnWheel(self, event):
        xy = wx.GetMousePosition()
        if not self.client.GetClientRect().Contains(self.client.ScreenToClient(xy)):
            if self.grid.GetClientRect().Contains(self.grid.ScreenToClient(xy)):
                self.grid.SetFocus()
            event.Skip()
        elif self.client.last_draw:
            if event.WheelRotation < 0:
                direction = 1.0
            else:
                direction = -1.0
            self.client.zoom(direction)

    def _setsize(self):
        if not self.IsMaximized():
            w, h = self.ClientSize
            if self.splitter._expanded < 0:
                self.splitter.SetExpandedSize(
                    (self.splitter._splitx + self.splitter._GetSashSize(), h)
                )
                self.splitter.SetSplitSize((w, h))
                setcfg(
                    "size.profile_info.w",
                    self.splitter._splitx + self.splitter._GetSashSize(),
                )
                setcfg("size.profile_info.split.w", w)
            else:
                self.splitter.SetExpandedSize((w, h))
                setcfg("size.profile_info.w", w)
            setcfg("size.profile_info.h", h)

    def drop_handler(self, path):
        """Drag'n'drop handler for .cal/.icc/.icm files."""
        reset = (
            self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1
        )
        self.LoadProfile(path, reset=reset)

    def get_platform_window_size(
        self, defaultwidth=None, defaultheight=None, split=False
    ):
        if split:
            name = ".split"
        else:
            name = ""
        if not defaultwidth:
            defaultwidth = defaults[f"size.profile_info{name}.w"]
        if not defaultheight:
            defaultheight = defaults["size.profile_info.h"]
        border, titlebar = get_platform_window_decoration_size()
        # return (max(max(getcfg("size.profile_info{name}.w"),
        # defaultwidth), self.GetMinSize()[0] - border * 2),
        # max(getcfg("size.profile_info.h"),
        # defaultheight))
        if split:
            w, h = self.splitter.GetSplitSize()
        else:
            w, h = self.splitter.GetExpandedSize()
        return (
            max(w, defaultwidth, self.GetMinSize()[0] - border * 2),
            max(h, defaultheight),
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
            focus = self.FindFocus()
            if focus and self.grid in (
                focus,
                focus.GetParent(),
                focus.GetGrandParent(),
            ):
                event.Skip()
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

    def plot_mode_select_handler(self, event):
        self.Freeze()
        self.select_current_page()
        reset = (
            self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1
        )
        self.DrawCanvas(reset=reset)
        self.Thaw()

    def get_commands(self):
        return self.get_common_commands() + [
            "profile-info [filename]",
            "load <filename>",
        ]

    def process_data(self, data):
        if (data[0] == "profile-info" and len(data) < 3) or (
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

    def redraw(self):
        if (
            self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1
            and self.client.last_draw
        ):
            # Update gamut plot
            self.client.Parent.Freeze()
            self.client._DrawCanvas(self.client.last_draw[0])
            self.client.Parent.Thaw()

    def resize_grid(self, event=None):
        self.grid.SetColSize(
            1,
            max(
                self.grid.GetSize()[0]
                - self.grid.GetRowLabelSize()
                - self.grid.GetColSize(0)
                - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
                0,
            ),
        )
        self.grid.SetMargins(
            0 - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
            0 - wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y),
        )
        self.grid.ForceRefresh()

    def select_current_page(self):
        if self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1:
            # Gamut plot
            self.options_panel.SetSelection(0)
        else:
            # Curves plot
            self.options_panel.SetSelection(1)
        self.splitter.GetTopLeft().Layout()

    def view_3d(self, event):
        profile = self.profile
        if not profile:
            defaultDir, defaultFile = get_verified_path("last_icc_path")
            dlg = wx.FileDialog(
                self,
                lang.getstr("profile.choose"),
                defaultDir=defaultDir,
                defaultFile=defaultFile,
                wildcard=f'{lang.getstr("filetype.icc")}|*.icc;*.icm',
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            dlg.Center(wx.BOTH)
            result = dlg.ShowModal()
            path = dlg.GetPath()
            dlg.Destroy()
            if result != wx.ID_OK:
                return
            try:
                profile = ICCP.ICCProfile(path)
            except (IOError, ICCP.ICCProfileInvalidError):
                show_result_dialog(
                    Error(f'{lang.getstr("profile.invalid")}\n{path}'), self
                )
            else:
                setcfg("last_icc_path", path)
                setcfg("last_cal_or_icc_path", path)
        if profile:
            view_3d_format = getcfg("3d.format")
            if view_3d_format == "HTML":
                x3d = True
                html = True
            elif view_3d_format == "X3D":
                x3d = True
                html = False
            else:
                x3d = False
                html = False
            profile_path = None
            if profile.fileName and os.path.isfile(profile.fileName):
                profile_path = profile.fileName
            if not profile_path or not waccess(os.path.dirname(profile_path), os.W_OK):
                result = self.worker.create_tempdir()
                if isinstance(result, Exception):
                    show_result_dialog(result, self)
                    return
                desc = profile.getDescription()
                profile_path = os.path.join(
                    self.worker.tempdir,
                    f"{make_argyll_compatible_path(desc) }{profile_ext}",
                )
                profile.write(profile_path)
            profile_mtime = os.stat(profile_path).st_mtime
            filename, ext = os.path.splitext(profile_path)
            comparison_profile = self.gamut_view_options.comparison_profile
            comparison_profile_path = None
            comparison_profile_mtime = 0
            if comparison_profile:
                comparison_profile_path = comparison_profile.fileName
                if comparison_profile_path and not waccess(
                    os.path.dirname(comparison_profile_path), os.W_OK
                ):
                    result = self.worker.create_tempdir()
                    if isinstance(result, Exception):
                        show_result_dialog(result, self)
                        return
                    comparison_profile_path = os.path.join(
                        self.worker.tempdir,
                        make_argyll_compatible_path(
                            os.path.basename(comparison_profile_path)
                        ),
                    )
                    comparison_profile.write(comparison_profile_path)
                comparison_profile_mtime = os.stat(comparison_profile_path).st_mtime
            mods = []
            intent = self.gamut_view_options.intent
            if intent != "r":
                mods.append(intent)
            direction = self.gamut_view_options.direction[-1]
            if direction != "f":
                mods.append(direction)
            order = self.gamut_view_options.order
            if order != "n":
                mods.append(order)
            if mods:
                filename = "{} {}".format(
                    filename, "".join(["[{}]".format(mod.upper() for mod in mods)])
                )
            if comparison_profile_path:
                filename += (
                    " vs "
                    + os.path.splitext(os.path.basename(comparison_profile_path))[0]
                )
                if mods:
                    filename = "{} {}".format(
                        filename, "".join([f"[{mod.upper()}]" for mod in mods])
                    )
            for vrmlext in (".vrml", ".vrml.gz", ".wrl", ".wrl.gz", ".wrz"):
                vrmlpath = filename + vrmlext
                if sys.platform == "win32":
                    vrmlpath = make_win32_compatible_long_path(vrmlpath)
                if os.path.isfile(vrmlpath):
                    break
            outfilename = filename
            colorspace = self.gamut_view_options.get_colorspace(3)
            if colorspace != "Lab":
                outfilename = f"{outfilename} {colorspace}"
            vrmloutpath = f"{outfilename}{vrmlext}"
            x3dpath = f"{outfilename}.x3d"
            if html:
                finalpath = f"{x3dpath}.html"
            elif x3d:
                finalpath = x3dpath
            else:
                finalpath = vrmloutpath
            if sys.platform == "win32":
                vrmloutpath = make_win32_compatible_long_path(vrmloutpath)
                x3dpath = make_win32_compatible_long_path(x3dpath)
                finalpath = make_win32_compatible_long_path(finalpath)
            for outpath in (finalpath, vrmloutpath, vrmlpath):
                if os.path.isfile(outpath):
                    mtime = os.stat(outpath).st_mtime
                    if profile_mtime > mtime or comparison_profile_mtime > mtime:
                        # Profile(s) have changed, delete existing 3D visualization
                        # so it will be re-generated
                        os.remove(outpath)
            if os.path.isfile(finalpath):
                launch_file(finalpath)
            else:
                if os.path.isfile(vrmloutpath):
                    self.view_3d_consumer(
                        True, None, None, vrmloutpath, x3d, x3dpath, html
                    )
                elif os.path.isfile(vrmlpath):
                    self.view_3d_consumer(
                        True, colorspace, None, vrmlpath, x3d, x3dpath, html
                    )
                else:
                    # Create VRML file
                    profile_paths = [profile_path]
                    if comparison_profile_path:
                        profile_paths.append(comparison_profile_path)
                    self.worker.start(
                        self.view_3d_consumer,
                        self.worker.calculate_gamut,
                        cargs=(colorspace, filename, None, x3d, x3dpath, html),
                        wargs=(profile_paths, intent, direction, order, False),
                        progress_msg=lang.getstr("gamut.view.create"),
                        continue_next=x3d,
                        fancy=False,
                    )

    def view_3d_consumer(
        self, result, colorspace, filename, vrmlpath, x3d, x3dpath, html
    ):
        if filename:
            if getcfg("vrml.compress"):
                vrmlpath = f"{filename}.wrz"
            else:
                vrmlpath = f"{filename}.wrl"
        if os.path.isfile(vrmlpath) and colorspace not in ("Lab", None):
            filename, ext = os.path.splitext(vrmlpath)
            if ext.lower() in (".gz", ".wrz"):
                cls = GzipFileProper
            else:
                cls = open
            with cls(vrmlpath, "rb") as vrmlfile:
                vrml = vrmlfile.read()
            vrml = x3dom.update_vrml(vrml, colorspace)
            vrmlpath = f"{filename} {colorspace}{ext}"
            with cls(vrmlpath, "wb") as vrmlfile:
                vrmlfile.write(vrml)
        if not os.path.isfile(vrmlpath):
            if self.worker.errors:
                result = UnloggedError("".join(self.worker.errors).strip())
            else:
                result = Error(lang.getstr("file.missing", vrmlpath))
        if isinstance(result, Exception):
            self.worker.stop_progress()
            show_result_dialog(result, self)
        elif x3d:
            vrmlfile2x3dfile(
                vrmlpath,
                x3dpath,
                embed=getcfg("x3dom.embed"),
                html=html,
                view=True,
                force=False,
                cache=getcfg("x3dom.cache"),
                worker=self.worker,
            )
        else:
            launch_file(vrmlpath)

    def view_3d_format_popup(self, event):
        menu = wx.Menu()

        item_selected = False
        for file_format in config.valid_values["3d.format"]:
            item = menu.AppendRadioItem(-1, file_format)
            item.Check(file_format == getcfg("3d.format"))
            self.Bind(wx.EVT_MENU, self.view_3d_format_handler, id=item.Id)

        self.PopupMenu(menu)
        for item in menu.MenuItems:
            self.Unbind(wx.EVT_MENU, id=item.Id)
        menu.Destroy()

    def view_3d_format_handler(self, event):
        for item in event.EventObject.MenuItems:
            if item.IsChecked():
                setcfg("3d.format", item.GetItemLabelText())

        self.view_3d(None)


def main():
    config.initcfg("profile-info")
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = ProfileInfoFrame(None, -1)
    if sys.platform == "darwin":
        app.TopWindow.init_menubar()
    wx.CallLater(1, _main, app)
    app.MainLoop()


def _main(app):
    app.TopWindow.listen()
    display_no = get_argyll_display_number(app.TopWindow.get_display()[1])
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            app.TopWindow.drop_handler(str(os.path.abspath(arg)))
            break
    else:
        app.TopWindow.LoadProfile(get_display_profile(display_no))
    app.TopWindow.Show()


if __name__ == "__main__":
    main()
