# -*- coding: utf-8 -*-

import math
import os
import sys

from DisplayCAL import (
    CGATS,
    ICCProfile as ICCP,
    colormath,
    config,
    floatspin,
    localization as lang,
    worker,
    xh_bitmapctrls,
    xh_floatspin,
)
from DisplayCAL.ICCProfile import ICCProfile
from DisplayCAL.argyll_cgats import extract_device_gray_primaries
from DisplayCAL.config import (
    enc,
    get_data_path,
    get_verified_path,
    getcfg,
    hascfg,
    profile_ext,
    setcfg,
)
from DisplayCAL.debughelpers import Error
from DisplayCAL.log import log
from DisplayCAL.meta import (
    name as appname,
)
from DisplayCAL.options import debug
from DisplayCAL.util_dict import dict_sort
from DisplayCAL.util_io import Files
from DisplayCAL.util_os import waccess
from DisplayCAL.util_str import safe_str
from DisplayCAL.worker import (
    Error,
    FilteredStream,
    LineBufferedStream,
    show_result_dialog,
)
from DisplayCAL.wxLUT3DFrame import LUT3DFrame, LUT3DMixin
from DisplayCAL.wxfixes import TempXmlResource
from DisplayCAL.wxwindows import (
    BaseApp,
    BaseFrame,
    ConfirmDialog,
    FileDrop,
    InfoDialog,
    wx,
)

from wx import xrc


class SynthICCFrame(BaseFrame, LUT3DMixin):
    """Synthetic ICC creation window"""

    cfg = config.cfg

    def __init__(self, parent=None):
        self.res = TempXmlResource(get_data_path(os.path.join("xrc", "synthicc.xrc")))
        self.res.InsertHandler(xh_floatspin.FloatSpinCtrlXmlHandler())
        self.res.InsertHandler(xh_bitmapctrls.BitmapButton())
        self.res.InsertHandler(xh_bitmapctrls.StaticBitmap())
        if hasattr(wx, "PreFrame"):
            # Classic
            pre = wx.PreFrame()
            self.res.LoadOnFrame(pre, parent, "synthiccframe")
            self.PostCreate(pre)
        else:
            # Phoenix
            wx.Frame.__init__(self)
            self.res.LoadFrame(self, parent, "synthiccframe")
        self.init()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        if sys.platform == "win32":
            self.Bind(wx.EVT_SIZE, self.OnSize)

        self.SetIcons(
            config.get_icon_bundle([256, 48, 32, 16], appname + "-synthprofile")
        )

        self.set_child_ctrls_as_attrs(self)

        self.panel = xrc.XRCCTRL(self, "panel")

        self._updating_ctrls = False

        # Presets
        presets = [""] + sorted(colormath.rgb_spaces.keys())
        self.preset_ctrl.SetItems(presets)

        self.set_default_cat()

        self.worker = worker.Worker(self)

        # Drop targets
        self.droptarget = FileDrop(self)
        self.droptarget.drophandlers = {
            ".icc": self.drop_handler,
            ".icm": self.drop_handler,
            ".ti3": self.drop_handler,
        }
        self.panel.SetDropTarget(self.droptarget)

        # Bind event handlers
        self.preset_ctrl.Bind(wx.EVT_CHOICE, self.preset_ctrl_handler)
        for color in ("red", "green", "blue", "white", "black"):
            for component in "XYZxy":
                if component in "xy":
                    handler = "xy"
                else:
                    handler = "XYZ"
                self.Bind(
                    floatspin.EVT_FLOATSPIN,
                    getattr(self, "%s_%s_ctrl_handler" % (color, handler)),
                    getattr(self, "%s_%s" % (color, component)),
                )
        self.black_point_cb.Bind(wx.EVT_CHECKBOX, self.black_point_enable_handler)
        self.chromatic_adaptation_btn.Bind(
            wx.EVT_BUTTON, self.chromatic_adaptation_btn_handler
        )
        self.trc_ctrl.Bind(wx.EVT_CHOICE, self.trc_ctrl_handler)
        self.trc_gamma_ctrl.Bind(wx.EVT_COMBOBOX, self.trc_gamma_ctrl_handler)
        self.trc_gamma_ctrl.Bind(wx.EVT_KILL_FOCUS, self.trc_gamma_ctrl_handler)
        self.trc_gamma_type_ctrl.Bind(wx.EVT_CHOICE, self.trc_gamma_type_ctrl_handler)
        self.lut3d_bind_hdr_trc_handlers()
        self.black_output_offset_ctrl.Bind(
            wx.EVT_SLIDER, self.black_output_offset_ctrl_handler
        )
        self.black_output_offset_intctrl.Bind(
            wx.EVT_TEXT, self.black_output_offset_ctrl_handler
        )
        self.colorspace_rgb_ctrl.Bind(wx.EVT_RADIOBUTTON, self.colorspace_ctrl_handler)
        self.colorspace_gray_ctrl.Bind(wx.EVT_RADIOBUTTON, self.colorspace_ctrl_handler)
        self.black_luminance_ctrl.Bind(
            floatspin.EVT_FLOATSPIN, self.black_luminance_ctrl_handler
        )
        self.luminance_ctrl.Bind(floatspin.EVT_FLOATSPIN, self.luminance_ctrl_handler)
        self.save_as_btn.Bind(wx.EVT_BUTTON, self.save_as_btn_handler)

        self.save_as_btn.SetDefault()

        self.setup_language()

        self.update_controls()
        self.update_layout()
        if self.panel.VirtualSize[0] > self.panel.Size[0]:
            scrollrate_x = 2
        else:
            scrollrate_x = 0
        self.panel.SetScrollRate(scrollrate_x, 2)

        self.save_btn.Hide()

        config.defaults.update(
            {
                "position.synthiccframe.x": self.GetDisplay().ClientArea[0] + 40,
                "position.synthiccframe.y": self.GetDisplay().ClientArea[1] + 60,
                "size.synthiccframe.w": self.ClientSize[0],
                "size.synthiccframe.h": self.ClientSize[1],
            }
        )

        if (
            self.hascfg("position.synthiccframe.x")
            and self.hascfg("position.synthiccframe.y")
            and self.hascfg("size.synthiccframe.w")
            and self.hascfg("size.synthiccframe.h")
        ):
            self.SetSaneGeometry(
                int(self.getcfg("position.synthiccframe.x")),
                int(self.getcfg("position.synthiccframe.y")),
                int(self.getcfg("size.synthiccframe.w")),
                int(self.getcfg("size.synthiccframe.h")),
            )
        else:
            self.Center()

    def OnSize(self, event):
        event.Skip()
        self.Refresh()  # Prevents distorted drawing under Windows

    def OnClose(self, event=None):
        if sys.platform == "darwin" or debug:
            self.focus_handler(event)
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            self.setcfg("position.synthiccframe.x", x)
            self.setcfg("position.synthiccframe.y", y)
            self.setcfg("size.synthiccframe.w", self.ClientSize[0])
            self.setcfg("size.synthiccframe.h", self.ClientSize[1])
        config.writecfg(
            module="synthprofile",
            options=(
                "synthprofile.",
                "last_icc_path",
                "position.synthiccframe",
                "size.synthiccframe",
                "3dlut.hdr_",
            ),
            cfg=self.cfg,
        )
        if event:
            # Hide first (looks nicer)
            self.Hide()
            # Need to use CallAfter to prevent hang under Windows if minimized
            if wx.GetApp().TopWindow is self:
                # XXX: Weird wxPython Phoenix bug under Windows: Destroying the
                # frame seems to affect subsequently loaded XRC resources
                # (wrong control classes used).
                # More investigation is needed, but it is clear this is a
                # Phoenix or wxWidgets bug because it does not happen with
                # wxPython classic (3.0.2).
                # Workaround: Only destroy the frame if running standalone.
                wx.CallAfter(self.Destroy)

    def black_luminance_ctrl_handler(self, event):
        v = self.black_luminance_ctrl.GetValue()
        white_Y = self.getcfg("synthprofile.luminance")
        if v >= white_Y * 0.9:
            if event:
                wx.Bell()
            v = white_Y * 0.9
        if event:
            min_Y = 0.000001  # (1 / 65535.0) * 100
            increment = 0.000001  # (1 / 65535.0) * white_Y
            if increment < min_Y:
                increment = min_Y * (white_Y / 100.0)
            min_inc = 1.0 / (10.0 ** self.black_luminance_ctrl.GetDigits())
            if increment < min_inc:
                increment = min_inc
            self.black_luminance_ctrl.SetIncrement(increment)
            fmt = "%%.%if" % self.black_luminance_ctrl.GetDigits()
            if fmt % 0 < fmt % v < fmt % increment:
                if event:
                    v = increment
                else:
                    v = 0
            elif fmt % v == fmt % 0:
                v = 0
            v = round(v / increment) * increment
        self.black_luminance_ctrl.SetValue(v)

        old = self.getcfg("synthprofile.black_luminance")
        self.setcfg("synthprofile.black_luminance", v)
        if event:
            self.black_xy_ctrl_handler(None)
        self.black_point_cb.Enable(v > 0)
        self.black_point_enable_handler(None)
        if (v != old and (old == 0 or v == 0)) or event is True:
            self.Freeze()
            i = self.trc_ctrl.GetSelection()
            self.trc_gamma_type_ctrl.Show(i in (0, 5) and bool(v))
            if not v:
                self.bpc_ctrl.SetValue(False)
            self.bpc_ctrl.Enable(bool(v))
            black_output_offset_show = i in (0, 5, 7, 8) and bool(v)
            self.black_output_offset_label.Show(black_output_offset_show)
            self.black_output_offset_ctrl.Show(black_output_offset_show)
            self.black_output_offset_intctrl.Show(black_output_offset_show)
            self.black_output_offset_intctrl_label.Show(black_output_offset_show)
            self.panel.GetSizer().Layout()
            self.update_layout()
            self.Thaw()

    def black_output_offset_ctrl_handler(self, event):
        if event.GetId() == self.black_output_offset_intctrl.GetId():
            self.black_output_offset_ctrl.SetValue(
                self.black_output_offset_intctrl.GetValue()
            )
        else:
            self.black_output_offset_intctrl.SetValue(
                self.black_output_offset_ctrl.GetValue()
            )
        v = self.black_output_offset_ctrl.GetValue() / 100.0
        self.setcfg("synthprofile.trc_output_offset", v)
        self.update_trc_control()

    def black_point_enable_handler(self, event):
        v = self.getcfg("synthprofile.black_luminance")
        for component in "XYZxy":
            getattr(self, "black_%s" % component).Enable(
                v > 0 and self.black_point_cb.Value
            )

    def black_XYZ_ctrl_handler(self, event):
        luminance = self.getcfg("synthprofile.luminance")
        XYZ = []
        for component in "XYZ":
            XYZ.append(getattr(self, "black_%s" % component).GetValue() / 100.0)
            if component == "Y":
                self.black_luminance_ctrl.SetValue(XYZ[-1] * luminance)
                self.black_luminance_ctrl_handler(None)
                if not XYZ[-1]:
                    XYZ = [0, 0, 0]
                    for i in range(3):
                        getattr(self, "black_%s" % "XYZ"[i]).SetValue(0)
                    break
        self.parse_XYZ("black")

    def black_xy_ctrl_handler(self, event):
        # Black Y scaled to 0..1 range
        Y = self.getcfg("synthprofile.black_luminance") / self.getcfg(
            "synthprofile.luminance"
        )
        xy = []
        for component in "xy":
            xy.append(getattr(self, "black_%s" % component).GetValue() or 1.0 / 3)
            getattr(self, "black_%s" % component).SetValue(xy[-1])
        for i, v in enumerate(colormath.xyY2XYZ(*xy + [Y])):
            getattr(self, "black_%s" % "XYZ"[i]).SetValue(v * 100)

    def blue_XYZ_ctrl_handler(self, event):
        self.parse_XYZ("blue")

    def blue_xy_ctrl_handler(self, event):
        self.parse_xy("blue")

    def chromatic_adaptation_btn_handler(self, event):
        scale = self.getcfg("app.dpi") / config.get_default_dpi()
        if scale < 1:
            scale = 1
        dlg = ConfirmDialog(
            self,
            title=lang.getstr("chromatic_adaptation"),
            msg=lang.getstr("whitepoint.xy"),
            ok=lang.getstr("apply"),
            cancel=lang.getstr("cancel"),
        )
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        dlg.sizer3.Add(sizer, 0, flag=wx.TOP | wx.ALIGN_LEFT, border=8)
        x_ctrl = floatspin.FloatSpin(
            dlg,
            -1,
            size=(75 * scale, -1),
            min_val=0.00001,
            max_val=1,
            increment=0.00001,
            value=self.white_x.GetValue(),
        )
        sizer.Add(x_ctrl, 0, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=4)
        sizer.Add(
            wx.StaticText(dlg, -1, "x"),
            0,
            flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
            border=12,
        )
        y_ctrl = floatspin.FloatSpin(
            dlg,
            -1,
            size=(75 * scale, -1),
            min_val=0.00001,
            max_val=1,
            increment=0.00001,
            value=self.white_y.GetValue(),
        )
        sizer.Add(y_ctrl, 0, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=4)
        sizer.Add(
            wx.StaticText(dlg, -1, "y"),
            0,
            flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
            border=12,
        )
        dlg.sizer3.Add(
            wx.StaticText(dlg, -1, lang.getstr("chromatic_adaptation_transform")),
            0,
            flag=wx.TOP | wx.ALIGN_LEFT,
            border=12,
        )
        if self.getcfg("show_advanced_options"):
            # Only offer those that seem suitable in an ICC workflow
            # (i.e. blue primary not too far from default Bradford to
            # prevent 'blue turns purple' problems)
            cat_choices = ["Bradford", "CAT02BS"]
        else:
            cat_choices = ["Bradford"]
        cat_choices_ab = dict(
            get_mapping(((k, k) for k in colormath.cat_matrices), cat_choices)
        )
        cat_choices_ba = dict((v, k) for k, v in cat_choices_ab.items())
        cat_ctrl = wx.Choice(dlg, -1, choices=list(cat_choices_ab.values()))
        cat_ctrl.SetStringSelection(cat_choices_ab[self.cat])
        dlg.sizer3.Add(cat_ctrl, 0, flag=wx.TOP | wx.ALIGN_LEFT, border=8)
        dlg.sizer0.SetSizeHints(dlg)
        dlg.sizer0.Layout()
        result = dlg.ShowModal()
        x = x_ctrl.GetValue()
        y = y_ctrl.GetValue()
        cat = cat_choices_ba[cat_ctrl.GetStringSelection()]
        dlg.Destroy()
        if result != wx.ID_OK:
            return
        wp_src = [getattr(self, "white_" + component).GetValue() for component in "XYZ"]
        wp_tgt = colormath.xyY2XYZ(x, y)
        self.cat = cat
        for color in ("red", "green", "blue", "white", "black"):
            ctrls = [getattr(self, "%s_%s" % (color, component)) for component in "XYZ"]
            X, Y, Z = (ctrl.GetValue() for ctrl in ctrls)
            XYZa = colormath.adapt(X, Y, Z, wp_src, wp_tgt, cat)
            for i, ctrl in enumerate(ctrls):
                ctrl.SetValue(XYZa[i])
            self.parse_XYZ(color, False)

    def colorspace_ctrl_handler(self, event):
        self.Freeze()
        show = bool(self.colorspace_rgb_ctrl.Value)
        for color in ("red", "green", "blue"):
            getattr(self, "label_%s" % color).Show(show)
            for component in "XYZxy":
                getattr(self, "%s_%s" % (color, component)).Show(show)
        self.enable_btns()
        self.update_layout()
        self.Thaw()

    def drop_handler(self, path):
        """File dropped"""
        fn, ext = os.path.splitext(path)
        if ext.lower() == ".ti3":
            self.ti3_drop_handler(path)
        else:
            self.icc_drop_handler(path)

    def icc_drop_handler(self, path):
        """ICC profile dropped"""
        try:
            profile = ICCP.ICCProfile(path)
        except (IOError, ICCP.ICCProfileInvalidError) as exception:
            show_result_dialog(
                Error(lang.getstr("profile.invalid") + "\n" + path), self
            )
        else:
            if profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
                show_result_dialog(
                    Error(lang.getstr("profile.iccv4.unsupported")), self
                )
                return
            if profile.colorSpace not in (
                b"RGB",
                b"GRAY",
            ) or profile.connectionColorSpace not in (b"Lab", b"XYZ"):
                show_result_dialog(
                    Error(
                        lang.getstr(
                            "profile.unsupported",
                            (profile.profileClass, profile.colorSpace),
                        )
                    ),
                    self,
                )
                return
            rgb = [(1, 1, 1), (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
            for i in range(256):
                rgb.append((1.0 / 255 * i, 1.0 / 255 * i, 1.0 / 255 * i))
            try:
                colors = self.worker.xicclu(profile, rgb, intent="a", pcs="x")
            except Exception as exception:
                show_result_dialog(exception, self)
            else:
                if "lumi" in profile.tags:
                    luminance = profile.tags.lumi.Y
                else:
                    luminance = 100
                if not colors[1][1] and isinstance(profile.tags.get("targ"), ICCP.Text):
                    # The profile may not reflect the actual black point.
                    # Get it from the embedded TI3 instead if zero from lookup.
                    XYZbp = profile.get_chardata_bkpt(True)
                    if XYZbp:
                        # Use wtpt chromaticity
                        colors[1] = [v * XYZbp[1] for v in colors[0]]
                self.set_colors(colors, luminance, profile.colorSpace)

    def set_colors(self, colors, luminance, colorspace):
        """Set controls according to args"""
        self.panel.Freeze()
        for ctrl, value in [
            (self.colorspace_rgb_ctrl, colorspace == "RGB"),
            (self.colorspace_gray_ctrl, colorspace == "GRAY"),
        ]:
            ctrl.SetValue(value)
        self.colorspace_ctrl_handler(None)
        self.setcfg("synthprofile.luminance", luminance)
        self.luminance_ctrl.SetValue(luminance)
        for i, color in enumerate(("white", "black")):
            for j, component in enumerate("XYZ"):
                getattr(self, "%s_%s" % (color, component)).SetValue(
                    colors[i][j] / colors[0][1] * 100
                )
            self.parse_XYZ(color)
        for i, color in enumerate(("red", "green", "blue")):
            xyY = colormath.XYZ2xyY(*colors[2 + i])
            for j, component in enumerate("xy"):
                getattr(self, "%s_%s" % (color, component)).SetValue(xyY[j])
        self.parse_xy(None)
        self.black_XYZ_ctrl_handler(None)
        if len(colors[5:]) > 2:
            trc = ICCP.CurveType()
            for XYZ in colors[5:]:
                trc.append(XYZ[1] / colors[0][1] * 65535)
            transfer_function = trc.get_transfer_function(outoffset=1.0)
            if transfer_function and transfer_function[1] >= 0.95:
                # Use detected transfer function
                gamma = transfer_function[0][1]
            else:
                # Use 50% gamma value
                gamma = math.log(colors[132][1]) / math.log(128.0 / 255)
            self.set_trc(round(gamma, 2))
            self.setcfg("synthprofile.trc_gamma_type", "g")
            self.trc_gamma_type_ctrl.SetSelection(self.trc_gamma_types_ba["g"])
        self.panel.Thaw()

    def ti3_drop_handler(self, path):
        """TI3 file dropped"""
        try:
            ti3 = CGATS.CGATS(path)
        except (IOError, CGATS.CGATSInvalidError) as exception:
            show_result_dialog(
                Error(lang.getstr("error.measurement.file_invalid", path)), self
            )
        else:
            ti3[0].normalize_to_y_100()
            rgb = [(100, 100, 100), (0, 0, 0), (100, 0, 0), (0, 100, 0), (0, 0, 100)]
            colors = []
            for R, G, B in rgb:
                result = ti3.queryi1({"RGB_R": R, "RGB_G": G, "RGB_B": B})
                if result:
                    color = []
                    for component in "XYZ":
                        label = "XYZ_" + component
                        if label in result:
                            color.append(result[label])
                if not result or len(color) < 3:
                    color = (0, 0, 0)
                colors.append(color)
            try:
                (
                    ti3_extracted,
                    RGB_XYZ_extracted,
                    RGB_XYZ_remaining,
                ) = extract_device_gray_primaries(ti3)
            except Error as exception:
                show_result_dialog(exception, self)
            else:
                RGB_XYZ_extracted = dict_sort(RGB_XYZ_extracted)
                colors.extend(list(RGB_XYZ_extracted.values()))
                luminance = ti3.queryv1("LUMINANCE_XYZ_CDM2")
                if luminance:
                    try:
                        luminance = float(luminance.split()[1])
                    except (TypeError, ValueError):
                        luminance = 100
                else:
                    luminance = 100
                self.set_colors(colors, luminance, "RGB")

    def enable_btns(self):
        enable = bool(self.get_XYZ())
        self.save_as_btn.Enable(enable)
        self.chromatic_adaptation_btn.Enable(enable)

    def get_XYZ(self):
        """Get XYZ in 0..1 range"""
        XYZ = {}
        black_Y = self.getcfg("synthprofile.black_luminance") / self.getcfg(
            "synthprofile.luminance"
        )
        for color in ("white", "red", "green", "blue", "black"):
            for component in "XYZ":
                v = getattr(self, "%s_%s" % (color, component)).GetValue() / 100.0
                if color == "black":
                    key = "k"
                    if not self.black_point_cb.Value:
                        v = XYZ["w%s" % component] * black_Y
                else:
                    key = color[0]
                XYZ[key + component] = v
        if (
            XYZ["wX"]
            and XYZ["wY"]
            and XYZ["wZ"]
            and (
                self.colorspace_gray_ctrl.Value
                or (XYZ["rX"] and XYZ["gY"] and XYZ["bZ"])
            )
        ):
            return XYZ

    def green_XYZ_ctrl_handler(self, event):
        self.parse_XYZ("green")

    def green_xy_ctrl_handler(self, event):
        self.parse_xy("green")

    def luminance_ctrl_handler(self, event):
        v = self.luminance_ctrl.GetValue()
        self.setcfg("synthprofile.luminance", v)
        target_peak = v
        maxmll = self.lut3d_hdr_maxmll_ctrl.GetValue()
        if maxmll < target_peak:
            self.setcfg("3dlut.hdr_maxmll", target_peak)
        self.lut3d_hdr_maxmll_ctrl.SetRange(target_peak, 10000)
        self.lut3d_set_option("3dlut.hdr_peak_luminance", v)
        self.black_luminance_ctrl_handler(event)

    def parse_XYZ(self, name, set_blackpoint=None):
        if set_blackpoint is None:
            set_blackpoint = not self.black_point_cb.Value
        if not self._updating_ctrls:
            self.preset_ctrl.SetSelection(0)
        XYZ = {}
        # Black Y scaled to 0..1 range
        black_Y = self.getcfg("synthprofile.black_luminance") / self.getcfg(
            "synthprofile.luminance"
        )
        for component in "XYZ":
            v = getattr(self, "%s_%s" % (name, component)).GetValue()
            XYZ[component] = v
            if name == "white" and set_blackpoint:
                getattr(self, "black_%s" % (component)).SetValue(v * black_Y)
        if "X" in XYZ and "Y" in XYZ and "Z" in XYZ:
            if XYZ["X"] + XYZ["Y"] + XYZ["Z"] == 0:
                # Set black chromaticity to white chromaticity if XYZ is 0
                xyY = []
                for i, component in enumerate("xy"):
                    xyY.append(getattr(self, "white_%s" % component).GetValue())
            else:
                xyY = colormath.XYZ2xyY(XYZ["X"], XYZ["Y"], XYZ["Z"])
            for i, component in enumerate("xy"):
                getattr(self, "%s_%s" % (name, component)).SetValue(xyY[i])
                if name == "white" and set_blackpoint:
                    getattr(self, "black_%s" % (component)).SetValue(xyY[i])
        self.enable_btns()

    def parse_xy(self, name=None, set_blackpoint=False):
        if not set_blackpoint:
            set_blackpoint = not self.black_point_cb.Value
        if not self._updating_ctrls:
            self.preset_ctrl.SetSelection(0)
        xy = {}
        for color in ("white", "red", "green", "blue"):
            for component in "xy":
                v = getattr(self, "%s_%s" % (color, component)).GetValue()
                xy[color[0] + component] = v
        if name == "white":
            wXYZ = colormath.xyY2XYZ(xy["wx"], xy["wy"], 1.0)
        else:
            wXYZ = []
            for component in "XYZ":
                wXYZ.append(getattr(self, "white_%s" % component).GetValue() / 100.0)
        if name == "white":
            # Black Y scaled to 0..1 range
            black_Y = self.getcfg("synthprofile.black_luminance") / self.getcfg(
                "synthprofile.luminance"
            )
            for i, component in enumerate("XYZ"):
                getattr(self, "white_%s" % component).SetValue(wXYZ[i] * 100)
                if set_blackpoint:
                    getattr(self, "black_%s" % component).SetValue(
                        wXYZ[i] * black_Y * 100
                    )
        has_rgb_xy = True
        # Calculate RGB to XYZ matrix from chromaticities and white
        try:
            mtx = colormath.rgb_to_xyz_matrix(
                xy["rx"], xy["ry"], xy["gx"], xy["gy"], xy["bx"], xy["by"], wXYZ
            )
        except ZeroDivisionError:
            # Singular matrix
            has_rgb_xy = False
        rgb = {"r": (1.0, 0.0, 0.0), "g": (0.0, 1.0, 0.0), "b": (0.0, 0.0, 1.0)}
        XYZ = {}
        for color in ("red", "green", "blue"):
            if has_rgb_xy:
                # Calculate XYZ for primaries
                v = mtx * rgb[color[0]]
            if not has_rgb_xy:
                v = (0, 0, 0)
            XYZ[color[0]] = v
            for i, component in enumerate("XYZ"):
                getattr(self, "%s_%s" % (color, component)).SetValue(
                    XYZ[color[0]][i] * 100
                )
        self.enable_btns()

    def preset_ctrl_handler(self, event):
        preset_name = self.preset_ctrl.GetStringSelection()
        if preset_name:
            self.set_default_cat()
            gamma, white, red, green, blue = colormath.rgb_spaces[preset_name]
            white = colormath.get_whitepoint(white)
            self._updating_ctrls = True
            self.panel.Freeze()
            if self.preset_ctrl.GetStringSelection() == "DCI P3":
                tech = self.tech["dcpj"]
            else:
                tech = self.tech[""]
            self.tech_ctrl.SetStringSelection(tech)
            for i, component in enumerate("XYZ"):
                getattr(self, "white_%s" % component).SetValue(white[i] * 100)
            self.parse_XYZ("white", True)
            for color in ("red", "green", "blue"):
                for i, component in enumerate("xy"):
                    getattr(self, "%s_%s" % (color, component)).SetValue(
                        locals()[color][i]
                    )
            self.parse_xy(None)
            self.set_trc(gamma)
            self.panel.Thaw()
            self._updating_ctrls = False

    def get_commands(self):
        return self.get_common_commands() + [
            "synthprofile [filename]",
            "load <filename>",
        ]

    def process_data(self, data):
        if (data[0] == "synthprofile" and len(data) < 3) or (
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

    def set_default_cat(self):
        self.cat = "Bradford"

    def set_trc(self, gamma):
        if gamma == -1023:
            # DICOM
            self.trc_ctrl.SetSelection(1)
        elif gamma == -2.0:
            # HLG
            self.trc_ctrl.SetSelection(2)
        elif gamma == -3.0:
            # L*
            self.trc_ctrl.SetSelection(3)
        elif gamma == -709:
            # Rec. 709
            self.trc_ctrl.SetSelection(4)
        elif gamma == -1886:
            # Rec. 1886
            self.trc_ctrl.SetSelection(5)
            self.trc_ctrl_handler()
        elif gamma == -240:
            # SMPTE 240M
            self.trc_ctrl.SetSelection(6)
        elif gamma == -2084:
            # SMPTE 2084, roll-off clip
            self.trc_ctrl.SetSelection(8)
        elif gamma == -2.4:
            # sRGB
            self.trc_ctrl.SetSelection(9)
        else:
            # Gamma
            self.trc_ctrl.SetSelection(0)
            self.setcfg("synthprofile.trc_gamma", gamma)
        self.update_trc_controls()

    def profile_name_ctrl_handler(self, event):
        self.enable_btns()

    def red_XYZ_ctrl_handler(self, event):
        self.parse_XYZ("red")

    def red_xy_ctrl_handler(self, event):
        self.parse_xy("red")

    def save_as_btn_handler(self, event):
        try:
            gamma = float(self.trc_gamma_ctrl.Value)
        except ValueError:
            wx.Bell()
            gamma = 2.2
            self.trc_gamma_ctrl.Value = str(gamma)

        defaultDir, defaultFile = get_verified_path("last_icc_path")
        defaultFile = lang.getstr("unnamed")
        path = None
        dlg = wx.FileDialog(
            self,
            lang.getstr("save_as"),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            wildcard=lang.getstr("filetype.icc") + "|*" + profile_ext,
            style=wx.SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        dlg.Center(wx.BOTH)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        dlg.Destroy()
        if path:
            if os.path.splitext(path)[1].lower() not in (".icc", ".icm"):
                path += profile_ext
            if not waccess(path, os.W_OK):
                show_result_dialog(
                    Error(lang.getstr("error.access_denied.write", path)), self
                )
                return
            self.setcfg("last_icc_path", path)
        else:
            return

        XYZ = self.get_XYZ()
        if self.trc_ctrl.GetSelection() in (0, 5):
            # 0 = Gamma
            # 5 = Rec. 1886 - trc set here is only used if black = 0
            trc = gamma
        elif self.trc_ctrl.GetSelection() == 1:
            # DICOM
            trc = -1
        elif self.trc_ctrl.GetSelection() == 2:
            # HLG
            trc = -2
        elif self.trc_ctrl.GetSelection() == 3:
            # L*
            trc = -3.0
        elif self.trc_ctrl.GetSelection() == 4:
            # Rec. 709
            trc = -709
        elif self.trc_ctrl.GetSelection() == 6:
            # SMPTE 240M
            trc = -240
        elif self.trc_ctrl.GetSelection() in (7, 8):
            # SMPTE 2084
            trc = -2084
        elif self.trc_ctrl.GetSelection() == 9:
            # sRGB
            trc = -2.4
        rolloff = self.trc_ctrl.GetSelection() == 8
        class_i = self.profile_class_ctrl.GetSelection()
        tech_i = self.tech_ctrl.GetSelection()
        ciis_i = self.ciis_ctrl.GetSelection()
        consumer = lambda result: (
            isinstance(result, Exception) and show_result_dialog(result, self)
        )
        wargs = (XYZ, trc, path)
        wkwargs = {
            "rgb": self.colorspace_rgb_ctrl.Value,
            "rolloff": rolloff,
            "bpc": self.bpc_ctrl.Value,
            "profile_class": list(self.profile_classes.keys())[class_i],
            "tech": list(self.tech.keys())[tech_i],
            "ciis": list(self.ciis.keys())[ciis_i],
        }
        if (trc == -2084 and rolloff) or trc == -2:
            if trc == -2084:
                msg = "smpte2084.rolloffclip"
            else:
                msg = "hlg"
            self.worker.recent.write(lang.getstr("trc." + msg) + "\n")
            self.worker.start(
                consumer,
                self.create_profile,
                wargs=(XYZ, trc, path),
                wkwargs=wkwargs,
                progress_msg=lang.getstr("synthicc.create"),
            )
        else:
            consumer(self.create_profile(*wargs, **wkwargs))

    def create_profile(
        self,
        XYZ,
        trc,
        path,
        rgb=True,
        rolloff=True,
        bpc=False,
        profile_class=b"mntr",
        tech=None,
        ciis=None,
    ):
        white = XYZ["wX"], XYZ["wY"], XYZ["wZ"]
        if rgb:
            # Color profile
            profile = ICCP.ICCProfile.from_XYZ(
                (XYZ["rX"], XYZ["rY"], XYZ["rZ"]),
                (XYZ["gX"], XYZ["gY"], XYZ["gZ"]),
                (XYZ["bX"], XYZ["bY"], XYZ["bZ"]),
                (XYZ["wX"], XYZ["wY"], XYZ["wZ"]),
                1.0,
                "",
                self.getcfg("copyright"),
                cat=self.cat,
                profile_class=profile_class,
            )
            black = colormath.adapt(XYZ["kX"], XYZ["kY"], XYZ["kZ"], white)
            profile.tags.rTRC = ICCP.CurveType(profile=profile)
            profile.tags.gTRC = ICCP.CurveType(profile=profile)
            profile.tags.bTRC = ICCP.CurveType(profile=profile)
            channels = "rgb"
        else:
            # Grayscale profile
            profile = ICCP.ICCProfile()
            # Profile class
            profile.profileClass = profile_class
            if not ICCP.s15f16_is_equal(
                (XYZ["wX"], XYZ["wY"], XYZ["wZ"]), colormath.get_whitepoint("D50")
            ) and (
                profile.profileClass not in (b"mntr", b"prtr")
                or colormath.is_similar_matrix(
                    colormath.get_cat_matrix(self.cat),
                    colormath.get_cat_matrix("Bradford"),
                )
            ):
                profile.version = 2.2  # Match ArgyllCMS
            profile.colorSpace = b"GRAY"
            profile.setCopyright(self.getcfg("copyright"))
            profile.set_wtpt((XYZ["wX"], XYZ["wY"], XYZ["wZ"]), self.cat)
            black = [
                XYZ["wY"]
                * (
                    self.getcfg("synthprofile.black_luminance")
                    / self.getcfg("synthprofile.luminance")
                )
            ] * 3
            profile.tags.kTRC = ICCP.CurveType(profile=profile)
            channels = "k"
        if trc == -2:
            # HLG
            outoffset = 1
        else:
            outoffset = self.getcfg("synthprofile.trc_output_offset")
        if trc == -1:
            # DICOM
            # Absolute luminance values!
            try:
                if rgb:
                    # Color profile
                    profile.set_dicom_trc(
                        [v * self.getcfg("synthprofile.luminance") for v in black],
                        self.getcfg("synthprofile.luminance"),
                    )
                else:
                    # Grayscale profile
                    profile.tags.kTRC.set_dicom_trc(
                        self.getcfg("synthprofile.black_luminance"),
                        self.getcfg("synthprofile.luminance"),
                    )
            except ValueError as exception:
                return exception
        elif trc > -1 and black != [0, 0, 0]:
            # Gamma with output offset or Rec. 1886-like
            if rgb:
                # Color profile
                profile.set_bt1886_trc(
                    black, outoffset, trc, self.getcfg("synthprofile.trc_gamma_type")
                )
            else:
                # Grayscale profile
                profile.tags.kTRC.set_bt1886_trc(
                    black[1], outoffset, trc, self.getcfg("synthprofile.trc_gamma_type")
                )
        elif trc == -2084 or trc == -2:
            # SMPTE 2084 or HLG
            if trc == -2084:
                hdr_format = "PQ"
            else:
                hdr_format = "HLG"
            minmll = self.getcfg("3dlut.hdr_minmll")
            if rolloff:
                maxmll = self.getcfg("3dlut.hdr_maxmll")
            else:
                maxmll = self.getcfg("synthprofile.luminance")
            if rgb:
                # Color profile
                if trc == -2084:
                    profile.set_smpte2084_trc(
                        [
                            v * self.getcfg("synthprofile.luminance") * (1 - outoffset)
                            for v in black
                        ],
                        self.getcfg("synthprofile.luminance"),
                        minmll,
                        maxmll,
                        self.getcfg("3dlut.hdr_maxmll_alt_clip"),
                        rolloff=True,
                        blend_blackpoint=False,
                    )
                else:
                    # HLG
                    profile.set_hlg_trc(
                        (0, 0, 0),
                        self.getcfg("synthprofile.luminance"),
                        1.2,
                        self.getcfg("3dlut.hdr_ambient_luminance"),
                        blend_blackpoint=False,
                    )
                if rolloff or trc == -2:
                    rgb_space = profile.get_rgb_space()
                    rgb_space[0] = 1.0  # Set gamma to 1.0 (not actually used)
                    rgb_space = colormath.get_rgb_space(rgb_space)
                    linebuffered_logfiles = []
                    if (
                        sys.stdout
                        and hasattr(sys.stdout, "isatty")
                        and sys.stdout.isatty()
                    ):
                        linebuffered_logfiles.append(print)
                    else:
                        linebuffered_logfiles.append(log)
                    logfiles = Files(
                        [
                            LineBufferedStream(
                                FilteredStream(
                                    Files(linebuffered_logfiles),
                                    enc,
                                    discard="",
                                    linesep_in="\n",
                                    triggers=[],
                                )
                            ),
                            self.worker.recent,
                            self.worker.lastmsg,
                        ]
                    )
                    quality = self.getcfg("profile.quality")
                    clutres = {"m": 17, "l": 9}.get(quality, 33)
                    hdr_clut_profile = ICCP.create_synthetic_hdr_clut_profile(
                        hdr_format,
                        rgb_space,
                        "",
                        self.getcfg("synthprofile.black_luminance") * (1 - outoffset),
                        self.getcfg("synthprofile.luminance"),
                        minmll,
                        maxmll,
                        self.getcfg("3dlut.hdr_maxmll_alt_clip"),
                        1.2,
                        self.getcfg("3dlut.hdr_ambient_luminance"),
                        clutres=clutres,
                        sat=self.getcfg("3dlut.hdr_sat"),
                        hue=self.getcfg("3dlut.hdr_hue"),
                        generate_B2A=trc == -2,
                        worker=self.worker,
                        logfile=logfiles,
                        cat=self.cat,
                    )
                    profile.tags.A2B0 = hdr_clut_profile.tags.A2B0
                    if trc == -2:
                        # HLG
                        profile.tags.B2A0 = hdr_clut_profile.tags.B2A0
                if black != [0, 0, 0] and outoffset and not bpc:
                    profile.apply_black_offset(black)
            else:
                # Grayscale profile
                if trc == -2084:
                    profile.tags.kTRC.set_smpte2084_trc(
                        self.getcfg("synthprofile.black_luminance") * (1 - outoffset),
                        self.getcfg("synthprofile.luminance"),
                        minmll,
                        maxmll,
                        self.getcfg("3dlut.hdr_maxmll_alt_clip"),
                        rolloff=True,
                    )
                else:
                    # HLG
                    profile.tags.kTRC.set_hlg_trc(
                        0,
                        self.getcfg("synthprofile.luminance"),
                        1.2,
                        self.getcfg("3dlut.hdr_ambient_luminance"),
                    )
                if black != [0, 0, 0] and outoffset and not bpc:
                    profile.tags.kTRC.apply_bpc(black[1])
        elif black != [0, 0, 0]:
            if rgb:
                # Color profile
                vmin = 0
            else:
                # Grayscale profile
                vmin = black[1]
            for i, channel in enumerate(channels):
                TRC = profile.tags["%sTRC" % channel]
                TRC.set_trc(trc, 1024, vmin=vmin * 65535)
            if rgb:
                profile.apply_black_offset(black)
        else:
            for channel in channels:
                profile.tags["%sTRC" % channel].set_trc(trc, 1)
        if black != [0, 0, 0] and bpc:
            if rgb:
                profile.apply_black_offset((0, 0, 0))
            else:
                profile.tags.kTRC.apply_bpc()
        for tagname in ("lumi", "bkpt"):
            if tagname == "lumi":
                # Absolute
                X, Y, Z = [
                    (v / XYZ["wY"]) * self.getcfg("synthprofile.luminance")
                    for v in (XYZ["wX"], XYZ["wY"], XYZ["wZ"])
                ]
            else:
                X, Y, Z = (XYZ["kX"], XYZ["kY"], XYZ["kZ"])
            profile.tags[tagname] = ICCP.XYZType()
            (
                profile.tags[tagname].X,
                profile.tags[tagname].Y,
                profile.tags[tagname].Z,
            ) = (X, Y, Z)
        # Technology type
        if tech:
            if not isinstance(tech, bytes):
                tech = tech.encode("utf-8")
            profile.tags.tech = ICCP.SignatureType(b"sig \0\0\0\0" + tech, "tech")
        # Colorimetric intent image state
        if ciis:
            if not isinstance(ciis, bytes):
                ciis = ciis.encode("utf-8")
            profile.tags.ciis = ICCP.SignatureType(b"sig \0\0\0\0" + ciis, "ciis")
        profile.setDescription(os.path.splitext(os.path.basename(path))[0])
        profile.calculateID()
        try:
            profile.write(path)
        except Exception as exception:
            return exception

    def setup_language(self):
        BaseFrame.setup_language(self)

        items = []
        for item in self.trc_ctrl.Items:
            items.append(lang.getstr(item))
        self.trc_ctrl.SetItems(items)
        self.trc_ctrl.SetSelection(0)

        self.trc_gamma_types_ab = {0: "g", 1: "G"}
        self.trc_gamma_types_ba = {"g": 0, "G": 1}
        self.trc_gamma_type_ctrl.SetItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )

        self.profile_classes = dict(
            get_mapping(list(ICCP.profileclass.items()), [b"mntr", b"scnr"])
        )
        self.profile_class_ctrl.SetItems(list(self.profile_classes.values()))
        self.profile_class_ctrl.SetSelection(0)

        self.tech = dict(
            get_mapping(
                [("", "unspecified")] + list(ICCP.tech.items()),
                [
                    "",
                    "fscn",
                    "dcam",
                    "rscn",
                    "vidm",
                    "vidc",
                    "pjtv",
                    "CRT ",
                    "PMD ",
                    "AMD ",
                    "mpfs",
                    "dmpc",
                    "dcpj",
                ],
            )
        )
        self.tech_ctrl.SetItems(list(self.tech.values()))
        self.tech_ctrl.SetSelection(0)

        self.ciis = dict(
            get_mapping(
                [("", "unspecified")] + list(ICCP.ciis.items()),
                ["", "scoe", "sape", "fpce"],
            )
        )
        self.ciis_ctrl.SetItems(list(self.ciis.values()))
        self.ciis_ctrl.SetSelection(0)

    def trc_ctrl_handler(self, event=None):
        if not self._updating_ctrls:
            self.preset_ctrl.SetSelection(0)
        i = self.trc_ctrl.GetSelection()
        if i == 5:
            # BT.1886
            self.setcfg("synthprofile.trc_gamma", 2.4)
            self.setcfg("synthprofile.trc_gamma_type", "G")
            self.setcfg("synthprofile.trc_output_offset", 0.0)
        if not self._updating_ctrls:
            self.update_trc_controls()

    def trc_gamma_type_ctrl_handler(self, event):
        self.setcfg(
            "synthprofile.trc_gamma_type",
            self.trc_gamma_types_ab[self.trc_gamma_type_ctrl.GetSelection()],
        )
        self.update_trc_control()

    def trc_gamma_ctrl_handler(self, event):
        if not self._updating_ctrls:
            try:
                v = float(self.trc_gamma_ctrl.GetValue().replace(",", "."))
                if (
                    v < config.valid_ranges["gamma"][0]
                    or v > config.valid_ranges["gamma"][1]
                ):
                    raise ValueError()
            except ValueError:
                wx.Bell()
                self.trc_gamma_ctrl.SetValue(str(self.getcfg("synthprofile.trc_gamma")))
            else:
                if str(v) != self.trc_gamma_ctrl.GetValue():
                    self.trc_gamma_ctrl.SetValue(str(v))
                self.setcfg(
                    "synthprofile.trc_gamma", float(self.trc_gamma_ctrl.GetValue())
                )
                self.preset_ctrl.SetSelection(0)
                self.update_trc_control()
        event.Skip()

    def update_controls(self):
        """Update controls with values from the configuration"""
        self.luminance_ctrl.SetValue(self.getcfg("synthprofile.luminance"))
        self.black_luminance_ctrl.SetValue(self.getcfg("synthprofile.black_luminance"))
        self.update_trc_control()
        self.update_trc_controls()

    def update_trc_control(self):
        if self.trc_ctrl.GetSelection() in (0, 5):
            if (
                self.getcfg("synthprofile.trc_gamma_type") == "G"
                and self.getcfg("synthprofile.trc_output_offset") == 0
                and self.getcfg("synthprofile.trc_gamma") == 2.4
            ):
                self.trc_ctrl.SetSelection(5)  # BT.1886
            else:
                self.trc_ctrl.SetSelection(0)  # Gamma

    def update_trc_controls(self):
        i = self.trc_ctrl.GetSelection()
        self.panel.Freeze()
        self.trc_gamma_label.Show(i in (0, 5))
        self.trc_gamma_ctrl.SetValue(str(self.getcfg("synthprofile.trc_gamma")))
        self.trc_gamma_ctrl.Show(i in (0, 5))
        self.trc_gamma_type_ctrl.SetSelection(
            self.trc_gamma_types_ba[self.getcfg("synthprofile.trc_gamma_type")]
        )
        if i in (0, 5, 7, 8):
            # Gamma, BT.1886, SMPTE 2084 (PQ)
            outoffset = int(self.getcfg("synthprofile.trc_output_offset") * 100)
        else:
            outoffset = 100
        self.black_output_offset_ctrl.SetValue(outoffset)
        self.black_output_offset_intctrl.SetValue(outoffset)
        target_peak = self.getcfg("synthprofile.luminance")
        maxmll = self.getcfg("3dlut.hdr_maxmll")
        # Don't allow maxmll < target peak. Technically this restriction does
        # not exist, but practically maxmll < target peak doesn't make sense.
        if maxmll < target_peak:
            maxmll = target_peak
            self.setcfg("3dlut.hdr_maxmll", maxmll)
        self.lut3d_hdr_maxmll_ctrl.SetRange(target_peak, 10000)
        self.luminance_ctrl.SetValue(target_peak)
        self.lut3d_hdr_minmll_ctrl.SetValue(self.getcfg("3dlut.hdr_minmll"))
        self.lut3d_hdr_maxmll_ctrl.SetValue(maxmll)
        self.lut3d_hdr_maxmll_alt_clip_cb.SetValue(
            not bool(self.getcfg("3dlut.hdr_maxmll_alt_clip"))
        )
        self.lut3d_hdr_sat_ctrl.SetValue(int(round(self.getcfg("3dlut.hdr_sat") * 100)))
        self.lut3d_hdr_update_sat_val()
        hue = int(round(self.getcfg("3dlut.hdr_sat") * 100))
        self.lut3d_hdr_hue_ctrl.SetValue(hue)
        self.lut3d_hdr_hue_intctrl.SetValue(hue)
        self.setcfg("3dlut.hdr_peak_luminance", self.getcfg("synthprofile.luminance"))
        self.lut3d_hdr_update_diffuse_white()
        self.lut3d_hdr_ambient_luminance_ctrl.SetValue(
            self.getcfg("3dlut.hdr_ambient_luminance")
        )
        self.lut3d_hdr_update_system_gamma()
        self.lut3d_hdr_minmll_label.Show(i in (7, 8))  # SMPTE 2084 (PQ)
        self.lut3d_hdr_minmll_ctrl.Show(i in (7, 8))  # SMPTE 2084 (PQ)
        self.lut3d_hdr_minmll_ctrl_label.Show(i in (7, 8))  # SMPTE 2084 (PQ)
        self.lut3d_hdr_maxmll_label.Show(i == 8)  # SMPTE 2084 (PQ)
        self.lut3d_hdr_maxmll_ctrl.Show(i == 8)  # SMPTE 2084 (PQ)
        self.lut3d_hdr_maxmll_ctrl_label.Show(i == 8)  # SMPTE 2084 (PQ)
        self.lut3d_show_hdr_maxmll_alt_clip_ctrl()
        self.lut3d_hdr_diffuse_white_label.Show(i == 8)  # SMPTE 2084 (PQ)
        self.lut3d_hdr_diffuse_white_txt.Show(i == 8)  # SMPTE 2084 (PQ)
        self.lut3d_hdr_diffuse_white_txt_label.Show(i == 8)  # SMPTE 2084 (PQ)
        sizer = self.lut3d_hdr_sat_ctrl.ContainingSizer
        sizer.ShowItems(i == 8)  # SMPTE 2084 (PQ)
        sizer = self.lut3d_hdr_hue_ctrl.ContainingSizer
        sizer.ShowItems(i == 8)  # SMPTE 2084 (PQ)
        self.lut3d_hdr_ambient_luminance_label.Show(i == 2)  # HLG
        self.lut3d_hdr_ambient_luminance_ctrl.Show(i == 2)  # HLG
        self.lut3d_hdr_ambient_luminance_ctrl_label.Show(i == 2)  # HLG
        self.lut3d_hdr_system_gamma_label.Show(i == 2)  # HLG
        self.lut3d_hdr_system_gamma_txt.Show(i == 2)  # HLG
        self.black_luminance_ctrl_handler(True)
        if i in (4, 6):
            # Rec 709 or SMPTE 240M
            # Match Adobe 'video' profiles
            self.profile_class_ctrl.SetStringSelection(self.profile_classes[b"scnr"])
            self.tech_ctrl.SetStringSelection(self.tech["vidc"])
            self.ciis_ctrl.SetStringSelection(self.ciis["fpce"])
        elif (
            self.profile_class_ctrl.GetStringSelection()
            == self.profile_classes[b"scnr"]
        ):
            # If 'input' profile, reset class/tech/colorimetric intent image state
            self.profile_class_ctrl.SetStringSelection(self.profile_classes[b"mntr"])
            self.tech_ctrl.SetStringSelection(self.tech[""])
            self.ciis_ctrl.SetStringSelection(self.ciis[""])
        self.panel.GetSizer().Layout()
        self.panel.Thaw()

    def white_XYZ_ctrl_handler(self, event):
        self.parse_XYZ("white")
        self.parse_xy()

    def white_xy_ctrl_handler(self, event):
        self.parse_xy("white")

    def getcfg(self, name, fallback=True, raw=False, cfg=None):
        if not cfg:
            cfg = self.cfg
        return getcfg(name, fallback, raw, cfg)

    def hascfg(self, name, fallback=True, cfg=None):
        if not cfg:
            cfg = self.cfg
        return hascfg(name, fallback, cfg)

    def setcfg(self, name, value, cfg=None):
        if not cfg:
            cfg = self.cfg
        setcfg(name, value, cfg)


def get_mapping(mapping, keys):
    return sorted(
        [
            (k, lang.getstr(v.lower().replace(" ", "_")))
            for k, v in [item for item in mapping if item[0] in keys]
        ],
        key=lambda item: item[0],
    )


def main():
    config.initcfg("synthprofile")
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = SynthICCFrame()
    if sys.platform == "darwin":
        app.TopWindow.init_menubar()
    wx.CallLater(1, _main, app)
    app.MainLoop()


def _main(app):
    app.TopWindow.listen()
    app.process_argv(1)
    app.TopWindow.Show()


if __name__ == "__main__":
    main()
