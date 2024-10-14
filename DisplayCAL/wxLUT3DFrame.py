# -*- coding: utf-8 -*-

import os
import re
import shutil
import sys
import traceback

from DisplayCAL import (
    ICCProfile as ICCP,
    colormath,
    config,
    floatspin,
    localization as lang,
    madvr,
    worker,
    xh_bitmapctrls,
    xh_filebrowsebutton,
    xh_floatspin,
)
from DisplayCAL.argyll_cgats import cal_to_fake_profile
from DisplayCAL.argyll_names import video_encodings
from DisplayCAL.config import (
    defaults,
    get_data_path,
    get_verified_path,
    getcfg,
    geticon,
    hascfg,
    profile_ext,
    setcfg,
)
from DisplayCAL.meta import (
    name as appname,
    version,
)
from DisplayCAL.options import debug
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_os import islink, readlink, safe_glob, waccess
from DisplayCAL.util_str import strtr
from DisplayCAL.worker import (
    Error,
    Info,
    UnloggedInfo,
    UnloggedWarning,
    check_set_argyll_bin,
    get_current_profile_path,
    get_options_from_profile,
    show_result_dialog,
)
from DisplayCAL.wxaddons import CustomEvent
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

if sys.platform == "win32":
    import win32api


class LUT3DMixin(object):
    """Mixin class that adds some ``lut3d_`` functions to the mixed-in class."""

    def lut3d_bind_event_handlers(self):
        # Shared with main window
        self.lut3d_apply_cal_cb.Bind(wx.EVT_CHECKBOX, self.lut3d_apply_cal_ctrl_handler)
        self.lut3d_create_btn.Bind(wx.EVT_BUTTON, self.lut3d_create_handler)
        self.lut3d_hdr_peak_luminance_ctrl.Bind(
            floatspin.EVT_FLOATSPIN, self.lut3d_hdr_peak_luminance_handler
        )
        self.lut3d_hdr_display_ctrl.Bind(wx.EVT_CHOICE, self.lut3d_hdr_display_handler)
        self.lut3d_bind_trc_handlers()
        self.lut3d_bind_hdr_trc_handlers()
        self.lut3d_bind_content_colorspace_handlers()
        self.lut3d_bind_common_handlers()

    def lut3d_bind_trc_handlers(self):
        self.lut3d_trc_ctrl.Bind(wx.EVT_CHOICE, self.lut3d_trc_ctrl_handler)
        self.lut3d_trc_gamma_ctrl.Bind(
            wx.EVT_COMBOBOX, self.lut3d_trc_gamma_ctrl_handler
        )
        self.lut3d_trc_gamma_ctrl.Bind(
            wx.EVT_KILL_FOCUS, self.lut3d_trc_gamma_ctrl_handler
        )
        self.lut3d_trc_gamma_type_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_trc_gamma_type_ctrl_handler
        )
        self.lut3d_trc_black_output_offset_ctrl.Bind(
            wx.EVT_SLIDER, self.lut3d_trc_black_output_offset_ctrl_handler
        )
        self.lut3d_trc_black_output_offset_intctrl.Bind(
            wx.EVT_TEXT, self.lut3d_trc_black_output_offset_ctrl_handler
        )

    def lut3d_bind_hdr_trc_handlers(self):
        self.lut3d_hdr_ambient_luminance_ctrl.Bind(
            floatspin.EVT_FLOATSPIN, self.lut3d_hdr_ambient_luminance_handler
        )
        self.lut3d_hdr_minmll_ctrl.Bind(
            floatspin.EVT_FLOATSPIN, self.lut3d_hdr_minmll_handler
        )
        self.lut3d_hdr_maxmll_ctrl.Bind(
            floatspin.EVT_FLOATSPIN, self.lut3d_hdr_maxmll_handler
        )
        self.lut3d_hdr_maxmll_alt_clip_cb.Bind(
            wx.EVT_CHECKBOX, self.lut3d_hdr_maxmll_alt_clip_handler
        )
        self.lut3d_hdr_sat_ctrl.Bind(wx.EVT_SLIDER, self.lut3d_hdr_sat_ctrl_handler)
        self.lut3d_hdr_hue_ctrl.Bind(wx.EVT_SLIDER, self.lut3d_hdr_hue_ctrl_handler)
        self.lut3d_hdr_hue_intctrl.Bind(wx.EVT_TEXT, self.lut3d_hdr_hue_ctrl_handler)

    def lut3d_bind_content_colorspace_handlers(self):
        self.lut3d_content_colorspace_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_content_colorspace_handler
        )
        for color in ("white", "red", "green", "blue"):
            for coord in "xy":
                v = self.getcfg("3dlut.content.colorspace.%s.%s" % (color, coord))
                getattr(self, "lut3d_content_colorspace_%s_%s" % (color, coord)).Bind(
                    floatspin.EVT_FLOATSPIN, self.lut3d_content_colorspace_xy_handler
                )

    def lut3d_bind_common_handlers(self):
        self.encoding_input_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_encoding_input_ctrl_handler
        )
        self.encoding_output_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_encoding_output_ctrl_handler
        )
        self.gamut_mapping_inverse_a2b.Bind(
            wx.EVT_RADIOBUTTON, self.lut3d_gamut_mapping_mode_handler
        )
        self.gamut_mapping_b2a.Bind(
            wx.EVT_RADIOBUTTON, self.lut3d_gamut_mapping_mode_handler
        )
        self.lut3d_rendering_intent_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_rendering_intent_ctrl_handler
        )
        self.lut3d_format_ctrl.Bind(wx.EVT_CHOICE, self.lut3d_format_ctrl_handler)
        self.lut3d_size_ctrl.Bind(wx.EVT_CHOICE, self.lut3d_size_ctrl_handler)
        self.lut3d_bitdepth_input_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_bitdepth_input_ctrl_handler
        )
        self.lut3d_bitdepth_output_ctrl.Bind(
            wx.EVT_CHOICE, self.lut3d_bitdepth_output_ctrl_handler
        )

    def lut3d_trc_apply_ctrl_handler(self, event=None):
        v = self.lut3d_trc_apply_ctrl.GetValue()
        self.lut3d_trc_ctrl.Enable(v)
        self.lut3d_trc_gamma_label.Enable(v)
        self.lut3d_trc_gamma_ctrl.Enable(v)
        self.lut3d_trc_gamma_type_ctrl.Enable(v)
        if event:
            self.setcfg("3dlut.apply_trc", int(v))
            self.setcfg(
                "3dlut.apply_black_offset",
                int(self.lut3d_trc_apply_black_offset_ctrl.GetValue()),
            )
        self.lut3d_hdr_peak_luminance_label.Enable(v)
        self.lut3d_hdr_peak_luminance_ctrl.Enable(v)
        self.lut3d_hdr_peak_luminance_ctrl_label.Enable(v)
        self.lut3d_hdr_minmll_label.Enable(v)
        self.lut3d_hdr_minmll_ctrl.Enable(v)
        self.lut3d_hdr_minmll_ctrl_label.Enable(v)
        self.lut3d_hdr_maxmll_label.Enable(v)
        self.lut3d_hdr_maxmll_ctrl.Enable(v)
        self.lut3d_hdr_maxmll_ctrl_label.Enable(v)
        self.lut3d_hdr_diffuse_white_label.Enable(v)
        self.lut3d_hdr_diffuse_white_txt.Enable(v)
        self.lut3d_hdr_diffuse_white_txt_label.Enable(v)
        self.lut3d_hdr_ambient_luminance_label.Enable(v)
        self.lut3d_hdr_ambient_luminance_ctrl.Enable(v)
        self.lut3d_hdr_ambient_luminance_ctrl_label.Enable(v)
        self.lut3d_hdr_system_gamma_label.Enable(v)
        self.lut3d_hdr_system_gamma_txt.Enable(v)
        self.lut3d_content_colorspace_label.Enable(v)
        self.lut3d_content_colorspace_ctrl.Enable(v)
        for color in ("white", "red", "green", "blue"):
            for coord in "xy":
                getattr(self, "lut3d_content_colorspace_%s_label" % color[0]).Enable(v)
                getattr(self, "lut3d_content_colorspace_%s_%s" % (color, coord)).Enable(
                    v
                )
                getattr(
                    self, "lut3d_content_colorspace_%s_%s_label" % (color, coord)
                ).Enable(v)
        self.lut3d_trc_black_output_offset_label.Enable(v)
        self.lut3d_trc_black_output_offset_ctrl.Enable(v)
        self.lut3d_trc_black_output_offset_intctrl.Enable(v)
        self.lut3d_trc_black_output_offset_intctrl_label.Enable(v)
        self.lut3d_show_input_value_clipping_warning(event)
        self.lut3d_show_hdr_display_control()

    def lut3d_show_input_value_clipping_warning(self, layout):
        self.panel.Freeze()
        show = (
            self.lut3d_trc_apply_none_ctrl.GetValue()
            and self.XYZbpout > self.XYZbpin
            and self.getcfg("3dlut.rendering_intent")
            not in ("la", "p", "pa", "ms", "s", "lp")
        )
        self.lut3d_input_value_clipping_bmp.Show(show)
        self.lut3d_input_value_clipping_label.Show(show)
        if layout:
            self.panel.Sizer.Layout()
            self.update_layout()
        self.panel.Thaw()

    def lut3d_hdr_maxmll_alt_clip_handler(self, event):
        self.lut3d_set_option(
            "3dlut.hdr_maxmll_alt_clip",
            int(not self.lut3d_hdr_maxmll_alt_clip_cb.GetValue()),
        )
        self.lut3d_hdr_update_diffuse_white()

    def lut3d_apply_cal_ctrl_handler(self, event):
        self.setcfg(
            "3dlut.output.profile.apply_cal", int(self.lut3d_apply_cal_cb.GetValue())
        )

    def lut3d_hdr_display_handler(self, event):
        if self.lut3d_hdr_display_ctrl.GetSelection() and not self.getcfg(
            "3dlut.hdr_display"
        ):
            if not show_result_dialog(
                UnloggedInfo(lang.getstr("3dlut.format.madVR.hdr.confirm")),
                self,
                confirm=lang.getstr("ok"),
            ):
                self.lut3d_hdr_display_ctrl.SetSelection(0)
                return
        self.lut3d_set_option(
            "3dlut.hdr_display", self.lut3d_hdr_display_ctrl.GetSelection()
        )

    def lut3d_hdr_peak_luminance_handler(self, event):
        target_peak = self.lut3d_hdr_peak_luminance_ctrl.GetValue()
        maxmll = self.lut3d_hdr_maxmll_ctrl.GetValue()
        if maxmll < target_peak:
            self.setcfg("3dlut.hdr_maxmll", target_peak)
        self.lut3d_hdr_maxmll_ctrl.SetRange(target_peak, 10000)
        self.lut3d_set_option(
            "3dlut.hdr_peak_luminance", self.lut3d_hdr_peak_luminance_ctrl.GetValue()
        )

    def lut3d_hdr_ambient_luminance_handler(self, event):
        self.lut3d_set_option(
            "3dlut.hdr_ambient_luminance",
            self.lut3d_hdr_ambient_luminance_ctrl.GetValue(),
        )

    def lut3d_hdr_minmll_handler(self, event):
        self.lut3d_set_option("3dlut.hdr_minmll", self.lut3d_hdr_minmll_ctrl.GetValue())

    def lut3d_hdr_maxmll_handler(self, event):
        self.lut3d_set_option("3dlut.hdr_maxmll", self.lut3d_hdr_maxmll_ctrl.GetValue())

    def lut3d_hdr_sat_ctrl_handler(self, event):
        self.lut3d_set_option(
            "3dlut.hdr_sat", self.lut3d_hdr_sat_ctrl.GetValue() / 100.0
        )
        self.lut3d_hdr_update_sat_val()

    def lut3d_hdr_hue_ctrl_handler(self, event):
        if event.GetId() == self.lut3d_hdr_hue_intctrl.GetId():
            self.lut3d_hdr_hue_ctrl.SetValue(self.lut3d_hdr_hue_intctrl.GetValue())
        else:
            self.lut3d_hdr_hue_intctrl.SetValue(self.lut3d_hdr_hue_ctrl.GetValue())
        v = self.lut3d_hdr_hue_ctrl.GetValue() / 100.0
        if v != self.getcfg("3dlut.hdr_hue"):
            self.lut3d_set_option("3dlut.hdr_hue", v)

    def lut3d_trc_black_output_offset_ctrl_handler(self, event):
        if event.GetId() == self.lut3d_trc_black_output_offset_intctrl.GetId():
            self.lut3d_trc_black_output_offset_ctrl.SetValue(
                self.lut3d_trc_black_output_offset_intctrl.GetValue()
            )
        else:
            self.lut3d_trc_black_output_offset_intctrl.SetValue(
                self.lut3d_trc_black_output_offset_ctrl.GetValue()
            )
        v = self.lut3d_trc_black_output_offset_ctrl.GetValue() / 100.0
        if v != self.getcfg("3dlut.trc_output_offset"):
            self.lut3d_set_option("3dlut.trc_output_offset", v)
            self.lut3d_update_trc_control()
        # self.lut3d_show_trc_controls()

    def lut3d_trc_gamma_ctrl_handler(self, event):
        try:
            v = float(self.lut3d_trc_gamma_ctrl.GetValue().replace(",", "."))
            if (
                v < config.valid_ranges["3dlut.trc_gamma"][0]
                or v > config.valid_ranges["3dlut.trc_gamma"][1]
            ):
                raise ValueError()
        except ValueError:
            wx.Bell()
            self.lut3d_trc_gamma_ctrl.SetValue(str(self.getcfg("3dlut.trc_gamma")))
        else:
            if str(v) != self.lut3d_trc_gamma_ctrl.GetValue():
                self.lut3d_trc_gamma_ctrl.SetValue(str(v))
            if v != self.getcfg("3dlut.trc_gamma"):
                self.lut3d_set_option("3dlut.trc_gamma", v)
                self.lut3d_update_trc_control()
            # self.lut3d_show_trc_controls()
        event.Skip()

    def lut3d_trc_ctrl_handler(self, event):
        self.Freeze()
        if self.lut3d_trc_ctrl.GetSelection() == 1:
            # BT.1886
            self.lut3d_set_option("3dlut.trc_gamma", 2.4)
            self.lut3d_set_option("3dlut.trc_gamma_type", "B")
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "bt1886"
        elif self.lut3d_trc_ctrl.GetSelection() == 0:
            # Pure power gamma 2.2
            self.lut3d_set_option("3dlut.trc_gamma", 2.2)
            self.lut3d_set_option("3dlut.trc_gamma_type", "b")
            self.lut3d_set_option("3dlut.trc_output_offset", 1.0)
            trc = "gamma2.2"
        elif self.lut3d_trc_ctrl.GetSelection() == 2:  # SMPTE 2084, hard clip
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "smpte2084.hardclip"
            self.lut3d_set_option("3dlut.hdr_maxmll", 10000)
        elif self.lut3d_trc_ctrl.GetSelection() == 3:  # SMPTE 2084, roll-off clip
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "smpte2084.rolloffclip"
            self.lut3d_set_option("3dlut.hdr_maxmll", 10000)
        elif self.lut3d_trc_ctrl.GetSelection() == 4:  # HLG
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "hlg"
        else:
            trc = "customgamma"
            # Have to use CallAfter, otherwise only part of the text will
            # be selected (wxPython bug?)
            wx.CallAfter(self.lut3d_trc_gamma_ctrl.SetFocus)
            wx.CallLater(1, self.lut3d_trc_gamma_ctrl.SelectAll)
        self.lut3d_set_option("3dlut.trc", trc)
        if trc != "customgamma":
            self.lut3d_update_trc_controls()
        self.lut3d_show_trc_controls()
        self.Thaw()

    def lut3d_trc_gamma_type_ctrl_handler(self, event):
        v = self.trc_gamma_types_ab[self.lut3d_trc_gamma_type_ctrl.GetSelection()]
        if v != self.getcfg("3dlut.trc_gamma_type"):
            self.lut3d_set_option("3dlut.trc_gamma_type", v)
            self.lut3d_update_trc_control()
            self.lut3d_show_trc_controls()

    def lut3d_encoding_input_ctrl_handler(self, event):
        encoding = self.encoding_input_ab[self.encoding_input_ctrl.GetSelection()]
        self.lut3d_set_option("3dlut.encoding.input", encoding)
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.lut3d_update_encoding_controls()
        elif self.Parent:
            self.Parent.lut3d_update_encoding_controls()

    def lut3d_encoding_output_ctrl_handler(self, event):
        encoding = self.encoding_output_ab[self.encoding_output_ctrl.GetSelection()]
        if self.getcfg("3dlut.format") == "madVR" and encoding != "t":
            profile = getattr(self, "output_profile", None)
            if (
                profile
                and "meta" in profile.tags
                and isinstance(profile.tags.meta, ICCP.DictType)
                and "EDID_model" in profile.tags.meta
            ):
                devicename = profile.tags.meta["EDID_model"]
            else:
                devicename = None
            dlg = ConfirmDialog(
                self,
                msg=lang.getstr(
                    "3dlut.encoding.output.warning.madvr",
                    devicename or lang.getstr("device.name.placeholder"),
                ),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                bitmap=geticon(32, "dialog-warning"),
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_OK:
                self.encoding_output_ctrl.SetSelection(
                    self.encoding_output_ba[self.getcfg("3dlut.encoding.output")]
                )
                return False
        self.lut3d_set_option("3dlut.encoding.output", encoding)
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.lut3d_update_encoding_controls()
        elif self.Parent:
            self.Parent.lut3d_update_encoding_controls()

    def lut3d_bitdepth_input_ctrl_handler(self, event):
        self.lut3d_set_option(
            "3dlut.bitdepth.input",
            self.lut3d_bitdepth_ab[self.lut3d_bitdepth_input_ctrl.GetSelection()],
        )
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.lut3d_update_shared_controls()
        elif self.Parent:
            self.Parent.lut3d_update_shared_controls()

    def lut3d_bitdepth_output_ctrl_handler(self, event):
        if self.getcfg("3dlut.format") in ("png", "ReShade") and self.lut3d_bitdepth_ab[
            self.lut3d_bitdepth_output_ctrl.GetSelection()
        ] not in (8, 16):
            wx.Bell()
            self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[8])
        self.lut3d_set_option(
            "3dlut.bitdepth.output",
            self.lut3d_bitdepth_ab[self.lut3d_bitdepth_output_ctrl.GetSelection()],
        )
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.lut3d_update_shared_controls()
        elif self.Parent:
            self.Parent.lut3d_update_shared_controls()

    def lut3d_content_colorspace_handler(self, event):
        sel = self.lut3d_content_colorspace_ctrl.Selection
        try:
            rgb_space = self.lut3d_content_colorspace_names[sel]
        except IndexError:
            # Custom
            rgb_space = None
        else:
            rgb_space = colormath.get_rgb_space(rgb_space)
            for i, color in enumerate(("white", "red", "green", "blue")):
                if i == 0:
                    xyY = colormath.XYZ2xyY(*rgb_space[1])
                else:
                    xyY = rgb_space[2:][i - 1]
                for j, coord in enumerate("xy"):
                    v = round(xyY[j], 4)
                    self.lut3d_set_option(
                        "3dlut.content.colorspace.%s.%s" % (color, coord), v
                    )
            self.lut3d_update_trc_controls()
        self.panel.Freeze()
        sizer = self.lut3d_content_colorspace_red_x.ContainingSizer
        sizer.ShowItems(not rgb_space)
        self.panel.Layout()
        self.panel.Thaw()
        if isinstance(self, LUT3DFrame):
            self.update_layout()

    def lut3d_content_colorspace_xy_handler(self, event):
        option = event.GetEventObject().Name.replace("_", ".")[5:]
        self.lut3d_set_option("3dlut" + option, event.GetEventObject().GetValue())
        self.lut3d_update_trc_controls()

    def lut3d_create_consumer(self, result=None):
        if isinstance(result, Exception):
            show_result_dialog(result, self)
        # Remove temporary files
        self.worker.wrapup(False)
        if not isinstance(result, Exception) and result:
            if not isinstance(self, LUT3DFrame) and getattr(self, "lut3d_path", None):
                # 3D LUT tab is part of main window
                if self.getcfg("3dlut.create"):
                    # 3D LUT was created automatically after profiling, show
                    # usual profile summary window
                    self.profile_finish(
                        True,
                        self.getcfg("calibration.file", False),
                        lang.getstr("calibration_profiling.complete"),
                        lang.getstr("profiling.incomplete"),
                        install_3dlut=True,
                    )
                else:
                    # 3D LUT was created manually
                    self.profile_finish(
                        True,
                        self.getcfg("calibration.file", False),
                        "",
                        lang.getstr("profiling.incomplete"),
                        install_3dlut=True,
                    )

    def lut3d_create_handler(self, event, path=None, copy_from_path=None):
        if sys.platform == "darwin" or debug:
            self.focus_handler(event)
        if not check_set_argyll_bin():
            return
        if isinstance(self, LUT3DFrame):
            profile_in = self.set_profile("input")
            if self.getcfg("3dlut.use_abstract_profile"):
                profile_abst = self.set_profile("abstract")
            else:
                profile_abst = None
            profile_out = self.set_profile("output")
        else:
            profile_abst = None
            profile_in_path = self.getcfg("3dlut.input.profile")
            if not profile_in_path or not os.path.isfile(profile_in_path):
                show_result_dialog(
                    Error(
                        lang.getstr(
                            "error.profile.file_missing",
                            self.getcfg("3dlut.input.profile", raw=True),
                        )
                    ),
                    parent=self,
                )
                return

            try:
                profile_in = ICCP.ICCProfile(profile_in_path)
            except (IOError, ICCP.ICCProfileInvalidError):
                show_result_dialog(
                    Error(lang.getstr("profile.invalid") + "\n" + profile_in_path),
                    parent=self,
                )
                return
            profile_out = config.get_current_profile()
            if not profile_out:
                show_result_dialog(
                    Error(
                        lang.getstr("profile.invalid")
                        + "\n%s" % self.getcfg("calibration.file", False)
                    ),
                    parent=self,
                )
                return
            if path:
                # Called from script client
                self.lut3d_path = None
            elif not copy_from_path:
                self.lut3d_set_path()
                path = self.lut3d_path
        if None not in (profile_in, profile_out) or (
            profile_in and profile_in.profileClass == "link"
        ):
            if profile_out and profile_in.isSame(profile_out, force_calculation=True):
                if not show_result_dialog(
                    Warning(lang.getstr("error.source_dest_same")),
                    self,
                    confirm=lang.getstr("continue"),
                ):
                    return
            checkoverwrite = True
            remember_last_3dlut_path = False
            if not path:
                defaultDir, defaultFile = get_verified_path("last_3dlut_path")
                if copy_from_path:
                    defaultFile = os.path.basename(copy_from_path)
                # Only remember last used path if it was a deliberate user
                # choice via the filedialog
                remember_last_3dlut_path = True
                if copy_from_path and config.get_display_name() == "Resolve":
                    # Find path to Resolve LUT folder
                    if sys.platform == "win32":
                        drives = win32api.GetLogicalDriveStrings()
                        for drive in drives.split("\0")[:-1]:
                            lut_dir = os.path.join(
                                drive,
                                "ProgramData",
                                "Blackmagic Design",
                                "DaVinci Resolve",
                                "Support",
                                "LUT",
                            )
                            if os.path.isdir(lut_dir):
                                defaultDir = lut_dir
                                remember_last_3dlut_path = False
                                break
                    else:
                        # Assume OS X
                        volumes = ["/"] + safe_glob("/Volumes/*")
                        for volume in volumes:
                            lut_dir = os.path.join(
                                volume,
                                "Library",
                                "Application Support",
                                "Blackmagic Design",
                                "DaVinci Resolve",
                                "LUT",
                            )
                            if os.path.isdir(lut_dir):
                                defaultDir = lut_dir
                                remember_last_3dlut_path = False
                                break
                ext = self.getcfg("3dlut.format")
                if (
                    ext != "madVR"
                    and not isinstance(self, LUT3DFrame)
                    and self.getcfg("3dlut.output.profile.apply_cal")
                ):
                    # Check if there's a clash between current videoLUT
                    # and 3D LUT (do both contain non-linear calibration?)
                    profile_display_name = profile_out.getDeviceModelDescription()
                    tempdir = self.worker.create_tempdir()
                    if isinstance(tempdir, Exception):
                        show_result_dialog(tempdir, self)
                        return
                    tempcal = os.path.join(tempdir, "temp.cal")
                    cancel = False
                    real_displays_count = 0
                    show_nonlinear_videolut_warning = False
                    for i, display_name in enumerate(self.worker.display_names):
                        if (
                            display_name == profile_display_name
                            and display_name != "madVR"
                            and self.worker.lut_access[i]
                            and self.worker.save_current_video_lut(
                                i + 1, tempcal, silent=True
                            )
                            is True
                            and not cal_to_fake_profile(tempcal).tags.vcgt.is_linear()
                        ):
                            show_nonlinear_videolut_warning = True
                            break
                        if not config.is_virtual_display(i):
                            real_displays_count += 1
                    if show_nonlinear_videolut_warning or real_displays_count == 1:
                        if copy_from_path:
                            confirm = lang.getstr("3dlut.save_as")
                        else:
                            confirm = lang.getstr("3dlut.install")
                        if not show_result_dialog(
                            UnloggedWarning(
                                lang.getstr("3dlut.1dlut.videolut.nonlinear")
                            ),
                            self,
                            confirm=confirm,
                        ):
                            cancel = True
                    if os.path.isfile(tempcal):
                        os.remove(tempcal)
                    if cancel:
                        return
                if ext == "ReShade":
                    dlg = wx.DirDialog(
                        self, lang.getstr("3dlut.install"), defaultPath=defaultDir
                    )
                else:
                    if ext == "eeColor":
                        ext = "txt"
                    elif ext == "madVR":
                        ext = "3dlut"
                    elif ext == "icc":
                        ext = profile_ext[1:]
                    defaultFile = (
                        os.path.splitext(
                            defaultFile
                            or os.path.basename(config.defaults.get("last_3dlut_path"))
                        )[0]
                        + "."
                        + ext
                    )
                    dlg = wx.FileDialog(
                        self,
                        lang.getstr("3dlut.save_as"),
                        defaultDir=defaultDir,
                        defaultFile=defaultFile,
                        wildcard="*." + ext,
                        style=wx.SAVE | wx.FD_OVERWRITE_PROMPT,
                    )
                dlg.Center(wx.BOTH)
                if dlg.ShowModal() == wx.ID_OK:
                    path = dlg.GetPath()
                    if ext == "ReShade":
                        path = os.path.join(
                            path.rstrip(os.path.sep), "ColorLookupTable.png"
                        )
                dlg.Destroy()
                checkoverwrite = False
            if path:
                if not waccess(path, os.W_OK):
                    show_result_dialog(
                        Error(lang.getstr("error.access_denied.write", path)), self
                    )
                    return
                if remember_last_3dlut_path:
                    self.setcfg("last_3dlut_path", path)
                if checkoverwrite and os.path.isfile(path):
                    dlg = ConfirmDialog(
                        self,
                        msg=lang.getstr("dialog.confirm_overwrite", (path)),
                        ok=lang.getstr("overwrite"),
                        cancel=lang.getstr("cancel"),
                        bitmap=geticon(32, "dialog-warning"),
                    )
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result != wx.ID_OK:
                        return
                if self.Parent:
                    config.writecfg()
                elif isinstance(self, LUT3DFrame):
                    config.writecfg(
                        module="3DLUT-maker",
                        options=(
                            "3dlut.",
                            "last_3dlut_path",
                            "position.lut3dframe",
                            "size.lut3dframe",
                        ),
                    )
                if copy_from_path:
                    # Instead of creating a 3D LUT, copy existing one
                    src_name = os.path.splitext(copy_from_path)[0]
                    dst_name = os.path.splitext(path)[0]
                    src_paths = [copy_from_path]
                    dst_paths = [path]
                    if self.getcfg("3dlut.format") == "eeColor":
                        # eeColor: 3D LUT + 6x 1D LUT
                        for part in ("first", "second"):
                            for channel in ("blue", "green", "red"):
                                src_path = "%s-%s1d%s.txt" % (src_name, part, channel)
                                if os.path.isfile(src_path):
                                    src_paths.append(src_path)
                                    dst_paths.append(
                                        "%s-%s1d%s.txt" % (dst_name, part, channel)
                                    )
                    elif self.getcfg("3dlut.format") == "ReShade":
                        dst_dir = os.path.dirname(path)
                        # Check if MasterEffect is installed
                        me_header_path = os.path.join(dst_dir, "MasterEffect.h")
                        use_mclut3d = False
                        if (
                            use_mclut3d
                            and os.path.isfile(me_header_path)
                            and os.path.isdir(os.path.join(dst_dir, "MasterEffect"))
                        ):
                            dst_paths = [
                                os.path.join(dst_dir, "MasterEffect", "mclut3d.png")
                            ]
                            # Alter existing MasterEffect.h
                            with open(me_header_path, "rb") as me_header_file:
                                me_header = me_header_file.read()
                            # Enable LUT
                            me_header = re.sub(
                                r"#define\s+USE_LUT\s+0", "#define USE_LUT 1", me_header
                            )
                            # iLookupTableMode 2 = use mclut3d.png
                            me_header = re.sub(
                                r"#define\s+iLookupTableMode\s+\d+",
                                "#define iLookupTableMode 2",
                                me_header,
                            )
                            # Amount of color change by lookup table.
                            # 1.0 means full effect.
                            me_header = re.sub(
                                r"#define\s+fLookupTableMix\s+\d+(?:\.\d+)",
                                "#define fLookupTableMix 1.0",
                                me_header,
                            )
                            with open(me_header_path, "wb") as me_header_file:
                                me_header_file.write(me_header)
                        else:
                            # Write out our own shader
                            clut_fx_path = get_data_path("ColorLookupTable.fx")
                            if not clut_fx_path:
                                show_result_dialog(
                                    Error(
                                        lang.getstr(
                                            "file.missing", "ColorLookupTable.fx"
                                        )
                                    ),
                                    self,
                                )
                                return
                            with open(clut_fx_path, "rb") as clut_fx_file:
                                clut_fx = clut_fx_file.read()
                            clut_size = self.getcfg("3dlut.size")
                            clut_fx = strtr(
                                clut_fx,
                                {
                                    "${VERSION}": version,
                                    "${WIDTH}": str(clut_size**2),
                                    "${HEIGHT}": str(clut_size),
                                    "${FORMAT}": "RGBA%i"
                                    % self.getcfg("3dlut.bitdepth.output"),
                                },
                            )
                            reshade_shaders = os.path.join(dst_dir, "reshade-shaders")
                            if os.path.isdir(reshade_shaders):
                                # ReShade >= 3.x with default shaders
                                path = os.path.join(
                                    reshade_shaders, "Textures", os.path.basename(path)
                                )
                                dst_paths = [path]
                                dst_dir = os.path.join(reshade_shaders, "Shaders")
                            else:
                                reshade_fx_path = os.path.join(dst_dir, "ReShade.fx")
                                # Adjust path for correct installation if ReShade.fx
                                # is a symlink.
                                if islink(reshade_fx_path):
                                    # ReShade < 3.0
                                    reshade_fx_path = readlink(reshade_fx_path)
                                    dst_dir = os.path.dirname(reshade_fx_path)
                                    path = os.path.join(dst_dir, os.path.basename(path))
                                    dst_paths = [path]
                                if os.path.isfile(reshade_fx_path):
                                    # ReShade < 3.0
                                    # Alter existing ReShade.fx
                                    with open(reshade_fx_path, "rb") as reshade_fx_file:
                                        reshade_fx = reshade_fx_file.read()
                                    # Remove existing shader include
                                    reshade_fx = re.sub(
                                        r"[ \t]*//\s*Automatically\s+\S+\s+by\s+%s\s+.+[ \t]*\r?\n?"
                                        % appname,
                                        "",
                                        reshade_fx,
                                    )
                                    reshade_fx = re.sub(
                                        r'[ \t]*#include\s+"ColorLookupTable.fx"[ \t]*\r?\n?',
                                        "",
                                        reshade_fx,
                                    ).rstrip("\r\n")
                                    reshade_fx += (
                                        "%s// Automatically added by %s %s%s"
                                        % (os.linesep * 2, appname, version, os.linesep)
                                    )
                                    reshade_fx += (
                                        '#include "ColorLookupTable.fx"' + os.linesep
                                    )
                                    with open(reshade_fx_path, "wb") as reshade_fx_file:
                                        reshade_fx_file.write(reshade_fx)
                            clut_fx_path = os.path.join(dst_dir, "ColorLookupTable.fx")
                            with open(clut_fx_path, "wb") as clut_fx_file:
                                clut_fx_file.write(clut_fx)
                    for src_path, dst_path in zip(src_paths, dst_paths):
                        shutil.copyfile(src_path, dst_path)
                    return
                self.worker.interactive = False
                self.worker.start(
                    self.lut3d_create_consumer,
                    self.lut3d_create_producer,
                    wargs=(profile_in, profile_abst, profile_out, path),
                    progress_msg=lang.getstr("3dlut.create"),
                    resume=not isinstance(self, LUT3DFrame)
                    and self.getcfg("3dlut.create"),
                )

    def lut3d_create_producer(self, profile_in, profile_abst, profile_out, path):
        apply_cal = (
            profile_out
            and isinstance(profile_out.tags.get("vcgt"), ICCP.VideoCardGammaType)
            and (
                self.getcfg("3dlut.output.profile.apply_cal")
                or not hasattr(self, "lut3d_apply_cal_cb")
            )
        )
        input_encoding = self.getcfg("3dlut.encoding.input")
        output_encoding = self.getcfg("3dlut.encoding.output")
        if self.getcfg("3dlut.apply_trc") or not hasattr(
            self, "lut3d_trc_apply_none_ctrl"
        ):
            if (
                self.getcfg("3dlut.trc").startswith("smpte2084")
                or self.getcfg("3dlut.trc") == "hlg"  # SMPTE ST.2084 (PQ)
            ):  # Hybrid Log-Gamma (HLG)
                trc_gamma = self.getcfg("3dlut.trc")
            else:
                trc_gamma = self.getcfg("3dlut.trc_gamma")
        else:
            trc_gamma = None
        XYZwp = None
        if not isinstance(self, LUT3DFrame):
            x = self.getcfg("3dlut.whitepoint.x", False)
            y = self.getcfg("3dlut.whitepoint.y", False)
            if x and y:
                XYZwp = colormath.xyY2XYZ(x, y)
        trc_gamma_type = self.getcfg("3dlut.trc_gamma_type")
        outoffset = self.getcfg("3dlut.trc_output_offset")
        intent = self.getcfg("3dlut.rendering_intent")
        format = self.getcfg("3dlut.format")
        size = self.getcfg("3dlut.size")
        input_bits = self.getcfg("3dlut.bitdepth.input")
        output_bits = self.getcfg("3dlut.bitdepth.output")
        apply_black_offset = self.getcfg("3dlut.apply_black_offset")
        use_b2a = self.getcfg("3dlut.gamap.use_b2a")
        white_cdm2 = self.getcfg("3dlut.hdr_peak_luminance")
        minmll = self.getcfg("3dlut.hdr_minmll")
        maxmll = self.getcfg("3dlut.hdr_maxmll")
        ambient_cdm2 = self.getcfg("3dlut.hdr_ambient_luminance")
        content_rgb_space = [1.0, [], [], [], []]
        for i, color in enumerate(("white", "red", "green", "blue")):
            for coord in "xy":
                v = self.getcfg("3dlut.content.colorspace.%s.%s" % (color, coord))
                content_rgb_space[i + 1].append(v)
            # Dummy Y value, not used for primaries but needs to be present
            content_rgb_space[i + 1].append(1.0)
        content_rgb_space[1] = colormath.xyY2XYZ(*content_rgb_space[1])
        content_rgb_space = colormath.get_rgb_space(content_rgb_space)
        try:
            # We need to make sure the link between the original profile object
            # and the one we're eventually going to change is broken
            profile_in = ICCP.ICCProfile(profile_in.fileName)
            self.worker.create_3dlut(
                profile_in,
                path,
                profile_abst,
                profile_out,
                apply_cal=apply_cal,
                intent=intent,
                format=format,
                size=size,
                input_bits=input_bits,
                output_bits=output_bits,
                input_encoding=input_encoding,
                output_encoding=output_encoding,
                trc_gamma=trc_gamma,
                trc_gamma_type=trc_gamma_type,
                trc_output_offset=outoffset,
                apply_black_offset=apply_black_offset,
                use_b2a=use_b2a,
                white_cdm2=white_cdm2,
                minmll=minmll,
                maxmll=maxmll,
                use_alternate_master_white_clip=self.getcfg(
                    "3dlut.hdr_maxmll_alt_clip"
                ),
                hdr_sat=self.getcfg("3dlut.hdr_sat"),
                hdr_hue=self.getcfg("3dlut.hdr_hue"),
                ambient_cdm2=ambient_cdm2,
                content_rgb_space=content_rgb_space,
                hdr_display=self.getcfg("3dlut.hdr_display"),
                XYZwp=XYZwp,
            )
        except Exception as exception:
            # if exception.__class__.__name__ in dir(exceptions):
            #     raise
            if debug:
                messages = traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
                print("[D] Worker raised exception: \n" + "\n".join(messages))
            return exception
        return True

    def lut3d_format_ctrl_handler(self, event):
        # Get selected format
        format = self.lut3d_formats_ab[self.lut3d_format_ctrl.GetSelection()]
        encoding_overrides = ("dcl", "eeColor", "madVR", "ReShade")
        size_overrides = ("dcl", "eeColor", "madVR", "mga", "ReShade")
        if (
            self.getcfg("3dlut.format") in encoding_overrides
            and format not in encoding_overrides
        ):
            # If previous format forced specific encoding, restore encoding
            self.setcfg(
                "3dlut.encoding.input", self.getcfg("3dlut.encoding.input.backup")
            )
            self.setcfg(
                "3dlut.encoding.output", self.getcfg("3dlut.encoding.output.backup")
            )
        if self.getcfg("3dlut.format") in size_overrides:
            # If previous format forced specific size, restore size
            self.setcfg("3dlut.size", self.getcfg("3dlut.size.backup"))
        if (
            self.getcfg("3dlut.format") not in encoding_overrides
            and format in encoding_overrides
        ):
            # If selected format forces specific encoding, backup current encoding
            self.setcfg(
                "3dlut.encoding.input.backup", self.getcfg("3dlut.encoding.input")
            )
            self.setcfg(
                "3dlut.encoding.output.backup", self.getcfg("3dlut.encoding.output")
            )
        # Set selected format
        self.lut3d_set_option("3dlut.format", format)
        if format in size_overrides:
            # If selected format forces specific size, backup current size
            self.setcfg("3dlut.size.backup", self.getcfg("3dlut.size"))
        if format == "eeColor":
            # -et -Et for eeColor
            if self.getcfg("3dlut.encoding.input") not in ("t", "T"):
                self.lut3d_set_option("3dlut.encoding.input", "t")
            self.lut3d_set_option("3dlut.encoding.output", "t")
            # eeColor uses a fixed size of 65x65x65
            self.lut3d_set_option("3dlut.size", 65)
        elif format == "mga":
            # Pandora uses a fixed bitdepth of 16
            self.lut3d_set_option("3dlut.bitdepth.output", 16)
            self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[16])
        elif format == "madVR":
            # -et -Et for madVR
            if self.getcfg("3dlut.encoding.input") not in ("t", "T"):
                self.lut3d_set_option("3dlut.encoding.input", "t")
            self.lut3d_set_option("3dlut.encoding.output", "t")
            # collink says madVR works best with 65
            self.lut3d_set_option("3dlut.size", 65)
        elif format in ("png", "ReShade"):
            if format == "ReShade":
                self.lut3d_set_option("3dlut.encoding.input", "n")
                self.lut3d_set_option("3dlut.encoding.output", "n")
                self.lut3d_set_option("3dlut.bitdepth.output", 8)
            elif self.getcfg("3dlut.bitdepth.output") not in (8, 16):
                self.lut3d_set_option("3dlut.bitdepth.output", 8)
            self.lut3d_bitdepth_output_ctrl.SetSelection(
                self.lut3d_bitdepth_ba[self.getcfg("3dlut.bitdepth.output")]
            )
        elif format == "dcl":
            self.lut3d_set_option("3dlut.encoding.input", "n")
            self.lut3d_set_option("3dlut.encoding.output", "n")
            self.lut3d_set_option("3dlut.size", 33)
            self.lut3d_set_option("3dlut.bitdepth.output", 12)
            self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[12])
        size = self.getcfg("3dlut.size")
        snap_size = self.lut3d_snap_size(size)
        if snap_size != size:
            self.lut3d_set_option("3dlut.size", snap_size)
        self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[self.getcfg("3dlut.size")])
        self.lut3d_update_encoding_controls()
        self.lut3d_enable_size_controls()
        self.lut3d_show_bitdepth_controls()
        if not isinstance(self, LUT3DFrame):
            self.panel.Freeze()
            self.lut3d_show_controls()
            self.calpanel.Layout()
            self.update_main_controls()
            self.panel.Thaw()
            if getattr(self, "lut3dframe", None):
                self.lut3dframe.lut3d_update_shared_controls()
            return
        else:
            self.panel.Freeze()
            self.lut3d_show_hdr_display_control()
            self.panel.Layout()
            self.panel.Thaw()
            self.update_layout()
            if self.Parent:
                self.Parent.lut3d_update_shared_controls()
        self.lut3d_create_btn.Enable(
            format != "madVR" or self.output_profile_ctrl.IsShown()
        )

    def lut3d_size_ctrl_handler(self, event):
        size = self.lut3d_size_ab[self.lut3d_size_ctrl.GetSelection()]
        snap_size = self.lut3d_snap_size(size)
        if snap_size != size:
            wx.Bell()
            self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[snap_size])
        self.lut3d_set_option("3dlut.size", snap_size)
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.lut3d_update_shared_controls()
        elif self.Parent:
            self.Parent.lut3d_update_shared_controls()

    def lut3d_snap_size(self, size):
        if self.getcfg("3dlut.format") == "mga" and size not in (17, 33):
            if size < 33:
                size = 17
            else:
                size = 33
        elif self.getcfg("3dlut.format") == "ReShade" and size not in (16, 32, 64):
            if size < 32:
                size = 16
            elif size < 64:
                size = 32
            else:
                size = 64
        return size

    def lut3d_gamut_mapping_mode_handler(self, event):
        self.lut3d_set_option(
            "3dlut.gamap.use_b2a", int(self.gamut_mapping_b2a.GetValue())
        )
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.update_controls()
        elif self.Parent:
            self.Parent.lut3d_update_b2a_controls()

    def lut3d_rendering_intent_ctrl_handler(self, event):
        self.lut3d_set_option(
            "3dlut.rendering_intent",
            self.rendering_intents_ab[self.lut3d_rendering_intent_ctrl.GetSelection()],
        )
        if getattr(self, "lut3dframe", None):
            self.lut3dframe.lut3d_update_shared_controls()
        else:
            if isinstance(self, LUT3DFrame):
                self.lut3d_show_input_value_clipping_warning(True)
            if self.Parent:
                self.Parent.lut3d_update_shared_controls()

    def lut3d_setup_language(self):
        # Shared with main window
        items = []
        for item in (
            "Gamma 2.2",
            "trc.rec1886",
            "trc.smpte2084.hardclip",
            "trc.smpte2084.rolloffclip",
            "trc.hlg",
            "custom",
        ):
            items.append(lang.getstr(item))
        self.lut3d_trc_ctrl.SetItems(items)

        self.trc_gamma_types_ab = {0: "b", 1: "B"}
        self.trc_gamma_types_ba = {"b": 0, "B": 1}
        self.lut3d_trc_gamma_type_ctrl.SetItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )

        self.lut3d_content_colorspace_names = ["Rec. 2020", "DCI P3 D65", "Rec. 709"]
        self.lut3d_content_colorspace_ctrl.SetItems(
            self.lut3d_content_colorspace_names + [lang.getstr("custom")]
        )

        self.rendering_intents_ab = {}
        self.rendering_intents_ba = {}
        self.lut3d_rendering_intent_ctrl.Clear()
        intents = list(config.valid_values["3dlut.rendering_intent"])
        if self.worker.argyll_version < [1, 8, 3]:
            intents.remove("lp")
        for i, ri in enumerate(intents):
            self.lut3d_rendering_intent_ctrl.Append(lang.getstr("gamap.intents." + ri))
            self.rendering_intents_ab[i] = ri
            self.rendering_intents_ba[ri] = i

        self.lut3d_formats_ab = {}
        self.lut3d_formats_ba = {}
        self.lut3d_format_ctrl.Clear()
        i = 0
        for format in config.valid_values["3dlut.format"]:
            if format != "madVR" or self.worker.argyll_version >= [1, 6]:
                self.lut3d_format_ctrl.Append(lang.getstr("3dlut.format.%s" % format))
                self.lut3d_formats_ab[i] = format
                self.lut3d_formats_ba[format] = i
                i += 1

        self.lut3d_hdr_display_ctrl.SetItems(
            [
                lang.getstr(item)
                for item in ("3dlut.format.madVR.hdr_to_sdr", "3dlut.format.madVR.hdr")
            ]
        )

        self.lut3d_size_ab = {}
        self.lut3d_size_ba = {}
        self.lut3d_size_ctrl.Clear()
        for i, size in enumerate(config.valid_values["3dlut.size"]):
            self.lut3d_size_ctrl.Append("%sx%sx%s" % ((size,) * 3))
            self.lut3d_size_ab[i] = size
            self.lut3d_size_ba[size] = i

        self.lut3d_bitdepth_ab = {}
        self.lut3d_bitdepth_ba = {}
        self.lut3d_bitdepth_input_ctrl.Clear()
        self.lut3d_bitdepth_output_ctrl.Clear()
        for i, bitdepth in enumerate(config.valid_values["3dlut.bitdepth.input"]):
            self.lut3d_bitdepth_input_ctrl.Append(str(bitdepth))
            self.lut3d_bitdepth_output_ctrl.Append(str(bitdepth))
            self.lut3d_bitdepth_ab[i] = bitdepth
            self.lut3d_bitdepth_ba[bitdepth] = i

    def lut3d_setup_encoding_ctrl(self):
        format = self.getcfg("3dlut.format")
        # Shared with amin window
        if format == "madVR":
            encodings = ["t"]
            config.defaults["3dlut.encoding.input"] = "t"
            config.defaults["3dlut.encoding.output"] = "t"
        else:
            if format == "dcl":
                encodings = ["n"]
            else:
                encodings = list(video_encodings)
            config.defaults["3dlut.encoding.input"] = "n"
            config.defaults["3dlut.encoding.output"] = "n"
        if (
            self.worker.argyll_version >= [1, 7]
            and self.worker.argyll_version != [1, 7, 0, "_beta"]
            and format != "dcl"
        ):
            # Argyll 1.7 beta 3 (2015-04-02) added clip WTW on input TV encoding
            encodings.insert(2, "T")
        config.valid_values["3dlut.encoding.input"] = encodings
        # collink: xvYCC output encoding is not supported
        config.valid_values["3dlut.encoding.output"] = [
            v for v in encodings if v not in ("T", "x", "X")
        ]
        self.encoding_input_ab = {}
        self.encoding_input_ba = {}
        self.encoding_output_ab = {}
        self.encoding_output_ba = {}
        self.encoding_input_ctrl.Freeze()
        self.encoding_input_ctrl.Clear()
        self.encoding_output_ctrl.Freeze()
        self.encoding_output_ctrl.Clear()
        for i, encoding in enumerate(config.valid_values["3dlut.encoding.input"]):
            lstr = lang.getstr("3dlut.encoding.type_%s" % encoding)
            self.encoding_input_ctrl.Append(lstr)
            self.encoding_input_ab[i] = encoding
            self.encoding_input_ba[encoding] = i
        for o, encoding in enumerate(config.valid_values["3dlut.encoding.output"]):
            lstr = lang.getstr("3dlut.encoding.type_%s" % encoding)
            self.encoding_output_ctrl.Append(lstr)
            self.encoding_output_ab[o] = encoding
            self.encoding_output_ba[encoding] = o
        self.encoding_input_ctrl.Thaw()
        self.encoding_output_ctrl.Thaw()

    def lut3d_set_option(self, option, v, set_changed=True):
        """Set option to value and update settings state"""
        if (
            hasattr(self, "profile_settings_changed")
            and set_changed
            and self.getcfg("3dlut.create")
            and v != self.getcfg(option)
        ):
            self.profile_settings_changed()
        self.setcfg(option, v)
        if option in (
            "3dlut.hdr_peak_luminance",
            "3dlut.hdr_minmll",
            "3dlut.hdr_maxmll",
        ):
            self.lut3d_show_hdr_maxmll_alt_clip_ctrl()
            self.lut3d_hdr_update_diffuse_white()
        elif option == "3dlut.hdr_ambient_luminance":
            self.lut3d_hdr_update_system_gamma()

    def lut3d_hdr_update_diffuse_white(self):
        # Update knee start info for BT.2390-3 roll-off
        bt2390 = colormath.BT2390(
            0,
            self.getcfg("3dlut.hdr_peak_luminance"),
            self.getcfg("3dlut.hdr_minmll"),
            self.getcfg("3dlut.hdr_maxmll"),
            self.getcfg("3dlut.hdr_maxmll_alt_clip"),
        )
        diffuse_ref_cdm2 = 94.37844
        diffuse_PQ = colormath.specialpow(diffuse_ref_cdm2 / 10000, 1.0 / -2084)
        # Determine white cd/m2 after roll-off
        diffuse_tgt_cdm2 = colormath.specialpow(bt2390.apply(diffuse_PQ), -2084) * 10000
        if diffuse_tgt_cdm2 < diffuse_ref_cdm2:
            signalcolor = "#CC0000"
        else:
            signalcolor = "#008000"
        self.lut3d_hdr_diffuse_white_txt.ForegroundColour = signalcolor
        self.lut3d_hdr_diffuse_white_txt.Label = "%.2f" % diffuse_tgt_cdm2
        self.lut3d_hdr_diffuse_white_txt_label.ForegroundColour = signalcolor
        self.lut3d_hdr_diffuse_white_txt.ContainingSizer.Layout()

    def lut3d_hdr_update_sat_val(self):
        v = self.getcfg("3dlut.hdr_sat") * 100
        self.lut3d_hdr_sat_ctrl_lum_val.Label = "%i%%" % (100 - v)
        self.lut3d_hdr_sat_ctrl_sat_val.Label = "%i%%" % v

    def lut3d_hdr_update_system_gamma(self):
        # Update system gamma for HLG based on ambient luminance (BT.2390-3)
        hlg = colormath.HLG(ambient_cdm2=self.getcfg("3dlut.hdr_ambient_luminance"))
        self.lut3d_hdr_system_gamma_txt.Label = str(stripzeros("%.4f" % hlg.gamma))

    def lut3d_update_shared_controls(self):
        # Shared with main window
        self.lut3d_update_trc_controls()
        self.lut3d_rendering_intent_ctrl.SetSelection(
            self.rendering_intents_ba[self.getcfg("3dlut.rendering_intent")]
        )
        # MadVR only available with Argyll 1.6+, fall back to default
        self.lut3d_format_ctrl.SetSelection(
            self.lut3d_formats_ba.get(
                self.getcfg("3dlut.format"),
                self.lut3d_formats_ba[defaults["3dlut.format"]],
            )
        )
        self.lut3d_hdr_display_ctrl.SetSelection(self.getcfg("3dlut.hdr_display"))
        self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[self.getcfg("3dlut.size")])
        self.lut3d_enable_size_controls()
        self.lut3d_bitdepth_input_ctrl.SetSelection(
            self.lut3d_bitdepth_ba[self.getcfg("3dlut.bitdepth.input")]
        )
        self.lut3d_bitdepth_output_ctrl.SetSelection(
            self.lut3d_bitdepth_ba[self.getcfg("3dlut.bitdepth.output")]
        )
        self.lut3d_show_bitdepth_controls()
        if self.Parent:
            self.Parent.lut3d_update_shared_controls()

    def lut3d_update_trc_control(self):
        if self.getcfg("3dlut.trc").startswith("smpte2084"):  # SMPTE 2084
            if self.getcfg("3dlut.trc") == "smpte2084.hardclip":
                sel = 2
            else:
                sel = 3
            self.lut3d_trc_ctrl.SetSelection(sel)
        elif self.getcfg("3dlut.trc") == "hlg":  # Hybrid Log-Gamma (HLG)
            self.lut3d_trc_ctrl.SetSelection(4)
        elif (
            self.getcfg("3dlut.trc_gamma_type") == "B"
            and self.getcfg("3dlut.trc_output_offset") == 0
            and self.getcfg("3dlut.trc_gamma") == 2.4
        ):
            self.lut3d_trc_ctrl.SetSelection(1)  # BT.1886
            self.setcfg("3dlut.trc", "bt1886")
        elif (
            self.getcfg("3dlut.trc_gamma_type") == "b"
            and self.getcfg("3dlut.trc_output_offset") == 1
            and self.getcfg("3dlut.trc_gamma") == 2.2
        ):
            self.lut3d_trc_ctrl.SetSelection(0)  # Pure power gamma 2.2
            self.setcfg("3dlut.trc", "gamma2.2")
        else:
            self.lut3d_trc_ctrl.SetSelection(5)  # Custom
            self.setcfg("3dlut.trc", "customgamma")

    def lut3d_update_trc_controls(self):
        self.lut3d_update_trc_control()
        self.lut3d_trc_gamma_ctrl.SetValue(str(self.getcfg("3dlut.trc_gamma")))
        self.lut3d_trc_gamma_type_ctrl.SetSelection(
            self.trc_gamma_types_ba[self.getcfg("3dlut.trc_gamma_type")]
        )
        outoffset = int(self.getcfg("3dlut.trc_output_offset") * 100)
        self.lut3d_trc_black_output_offset_ctrl.SetValue(outoffset)
        self.lut3d_trc_black_output_offset_intctrl.SetValue(outoffset)
        target_peak = self.getcfg("3dlut.hdr_peak_luminance")
        maxmll = self.getcfg("3dlut.hdr_maxmll")
        # Don't allow maxmll < target peak. Technically this restriction does
        # not exist, but practically maxmll < target peak doesn't make sense.
        if maxmll < target_peak:
            maxmll = target_peak
            self.setcfg("3dlut.hdr_maxmll", maxmll)
        self.lut3d_hdr_maxmll_ctrl.SetRange(target_peak, 10000)
        self.lut3d_hdr_peak_luminance_ctrl.SetValue(target_peak)
        self.lut3d_hdr_minmll_ctrl.SetValue(self.getcfg("3dlut.hdr_minmll"))
        self.lut3d_hdr_maxmll_ctrl.SetValue(maxmll)
        self.lut3d_hdr_maxmll_alt_clip_cb.SetValue(
            not bool(self.getcfg("3dlut.hdr_maxmll_alt_clip"))
        )
        self.lut3d_hdr_update_diffuse_white()
        self.lut3d_hdr_ambient_luminance_ctrl.SetValue(
            self.getcfg("3dlut.hdr_ambient_luminance")
        )
        self.lut3d_hdr_update_system_gamma()
        # Content colorspace (currently only used for SMPTE 2084)
        content_colors = []
        for color in ("red", "green", "blue", "white"):
            for coord in "xy":
                v = self.getcfg("3dlut.content.colorspace.%s.%s" % (color, coord))
                getattr(
                    self, "lut3d_content_colorspace_%s_%s" % (color, coord)
                ).SetValue(v)
                content_colors.append(round(v, 4))
        rgb_space_name = colormath.find_primaries_wp_xy_rgb_space_name(
            content_colors, self.lut3d_content_colorspace_names
        )
        if rgb_space_name:
            i = self.lut3d_content_colorspace_names.index(rgb_space_name)
        else:
            i = self.lut3d_content_colorspace_ctrl.Count - 1
        self.lut3d_content_colorspace_ctrl.SetSelection(i)
        self.lut3d_hdr_sat_ctrl.SetValue(int(round(self.getcfg("3dlut.hdr_sat") * 100)))
        self.lut3d_hdr_update_sat_val()
        hue = int(round(self.getcfg("3dlut.hdr_hue") * 100))
        self.lut3d_hdr_hue_ctrl.SetValue(hue)
        self.lut3d_hdr_hue_intctrl.SetValue(hue)

    def lut3d_show_bitdepth_controls(self):
        frozen = self.IsFrozen()
        if not frozen:
            self.Freeze()
        show = True
        input_show = show and self.getcfg("3dlut.format") == "3dl"
        self.lut3d_bitdepth_input_label.Show(input_show)
        self.lut3d_bitdepth_input_ctrl.Show(input_show)
        output_show = show and self.getcfg("3dlut.format") in ("3dl", "png")
        self.lut3d_bitdepth_output_label.Show(output_show)
        self.lut3d_bitdepth_output_ctrl.Show(output_show)
        if isinstance(self, LUT3DFrame):
            self.panel.GetSizer().Layout()
            self.update_layout()
        else:
            self.update_scrollbars()
        if not frozen:
            self.Thaw()

    def lut3d_show_hdr_display_control(self):
        self.lut3d_hdr_display_ctrl.Show(
            (
                self.getcfg("3dlut.apply_trc")
                or not hasattr(self, "lut3d_trc_apply_none_ctrl")
            )
            and self.getcfg("3dlut.trc").startswith("smpte2084")
            and self.getcfg("3dlut.format") == "madVR"
        )

    def lut3d_show_hdr_maxmll_alt_clip_ctrl(self):
        self.panel.Freeze()
        show = self.lut3d_hdr_maxmll_ctrl.IsShown()  # BT.2390 (roll-off)
        self.lut3d_hdr_maxmll_alt_clip_cb.Show(
            show and self.getcfg("3dlut.hdr_maxmll") < 10000
        )
        self.panel.Layout()
        self.panel.Thaw()

    def lut3d_show_trc_controls(self, show=True):
        self.panel.Freeze()
        show = show and self.worker.argyll_version >= [1, 6]
        if hasattr(self, "lut3d_trc_apply_ctrl"):
            self.lut3d_trc_apply_ctrl.Show(show)
        self.lut3d_trc_ctrl.Show(show)
        smpte2084 = self.getcfg("3dlut.trc").startswith("smpte2084")
        hlg = self.getcfg("3dlut.trc") == "hlg"
        hdr = smpte2084 or hlg
        show = show and (
            self.getcfg("3dlut.trc") == "customgamma"
            or (isinstance(self, LUT3DFrame) or self.getcfg("show_advanced_options"))
        )
        self.lut3d_trc_gamma_label.Show(show and not hdr)
        self.lut3d_trc_gamma_ctrl.Show(show and not hdr)
        smpte2084r = self.getcfg("3dlut.trc") == "smpte2084.rolloffclip"
        # Show items in this order so we end up with the correct controls shown
        showcc = (smpte2084r or hlg) and (
            isinstance(self, LUT3DFrame) or self.getcfg("show_advanced_options")
        )
        self.lut3d_content_colorspace_label.ContainingSizer.ShowItems(showcc)
        sel = self.lut3d_content_colorspace_ctrl.Selection
        lastsel = self.lut3d_content_colorspace_ctrl.Count - 1
        sizer = self.lut3d_content_colorspace_red_x.ContainingSizer
        sizer.ShowItems(showcc and sel == lastsel)
        self.lut3d_hdr_minmll_label.Show(show and smpte2084)
        self.lut3d_hdr_minmll_ctrl.Show(show and smpte2084)
        self.lut3d_hdr_minmll_ctrl_label.Show(show and smpte2084)
        self.lut3d_hdr_maxmll_label.Show(show and smpte2084r)
        self.lut3d_hdr_maxmll_ctrl.Show(show and smpte2084r)
        self.lut3d_hdr_maxmll_ctrl_label.Show(show and smpte2084r)
        self.lut3d_show_hdr_maxmll_alt_clip_ctrl()
        self.lut3d_hdr_diffuse_white_label.Show(show and smpte2084r)
        self.lut3d_hdr_diffuse_white_txt.Show(show and smpte2084r)
        self.lut3d_hdr_diffuse_white_txt_label.Show(show and smpte2084r)
        self.lut3d_hdr_ambient_luminance_label.Show(show and hlg)
        self.lut3d_hdr_ambient_luminance_ctrl.Show(show and hlg)
        self.lut3d_hdr_ambient_luminance_ctrl_label.Show(show and hlg)
        self.lut3d_hdr_system_gamma_label.Show(show and hlg)
        self.lut3d_hdr_system_gamma_txt.Show(show and hlg)
        sizer = self.lut3d_hdr_sat_ctrl.ContainingSizer
        sizer.ShowItems(show and smpte2084r)
        sizer = self.lut3d_hdr_hue_ctrl.ContainingSizer
        sizer.ShowItems(show and smpte2084r)
        show = (show or smpte2084) and not hlg
        show = show and (
            (hasattr(self, "lut3d_create_cb") and self.getcfg("3dlut.create"))
            or self.XYZbpout > [0, 0, 0]
        )
        self.lut3d_trc_gamma_type_ctrl.Show(show and not hdr)
        self.lut3d_trc_black_output_offset_label.Show(show)
        self.lut3d_trc_black_output_offset_ctrl.Show(show)
        self.lut3d_trc_black_output_offset_intctrl.Show(show)
        self.lut3d_trc_black_output_offset_intctrl_label.Show(show)
        self.lut3d_hdr_peak_luminance_label.Show(smpte2084)
        self.lut3d_hdr_peak_luminance_ctrl.Show(smpte2084)
        self.lut3d_hdr_peak_luminance_ctrl_label.Show(smpte2084)
        self.lut3d_show_hdr_display_control()
        self.panel.Layout()
        self.panel.Thaw()
        if isinstance(self, LUT3DFrame):
            self.update_layout()

    def lut3d_show_encoding_controls(self, show=True):
        show = show and (
            (
                self.worker.argyll_version >= [1, 7]
                and self.worker.argyll_version != [1, 7, 0, "_beta"]
            )
            or self.worker.argyll_version >= [1, 6]
        )
        # Argyll 1.7 beta 3 (2015-04-02) added clip WTW on input TV encoding
        self.encoding_input_label.Show(show)
        self.encoding_input_ctrl.Show(show)
        show = show and self.worker.argyll_version >= [1, 6]
        self.encoding_output_label.Show(show)
        self.encoding_output_ctrl.Show(show)

    def lut3d_update_encoding_controls(self):
        self.lut3d_setup_encoding_ctrl()
        self.encoding_input_ctrl.SetSelection(
            self.encoding_input_ba[self.getcfg("3dlut.encoding.input")]
        )
        self.encoding_input_ctrl.Enable(self.encoding_input_ctrl.Count > 1)
        self.encoding_output_ctrl.SetSelection(
            self.encoding_output_ba[self.getcfg("3dlut.encoding.output")]
        )
        self.encoding_output_ctrl.Enable(
            self.getcfg("3dlut.format") not in ("dcl", "madVR")
        )

    def lut3d_enable_size_controls(self):
        self.lut3d_size_ctrl.Enable(
            self.getcfg("3dlut.format") not in ("eeColor", "madVR")
        )


class LUT3DFrame(BaseFrame, LUT3DMixin):
    """3D LUT creation window"""

    def __init__(self, parent=None, setup=True):
        self.input_profile = None
        self.res = TempXmlResource(get_data_path(os.path.join("xrc", "3dlut.xrc")))
        self.res.InsertHandler(
            xh_filebrowsebutton.FileBrowseButtonWithHistoryXmlHandler()
        )
        self.res.InsertHandler(xh_floatspin.FloatSpinCtrlXmlHandler())
        self.res.InsertHandler(xh_bitmapctrls.BitmapButton())
        self.res.InsertHandler(xh_bitmapctrls.StaticBitmap())
        if hasattr(wx, "PreFrame"):
            # Classic
            pre = wx.PreFrame()
            self.res.LoadOnFrame(pre, parent, "lut3dframe")
            self.PostCreate(pre)
        else:
            # Phoenix
            wx.Frame.__init__(self)
            self.res.LoadFrame(self, parent, "lut3dframe")
        self.init()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        if sys.platform == "win32":
            self.Bind(wx.EVT_SIZE, self.OnSize)

        self.SetIcons(
            config.get_icon_bundle([256, 48, 32, 16], appname + "-3DLUT-maker")
        )

        self.set_child_ctrls_as_attrs(self)

        self.panel = xrc.XRCCTRL(self, "panel")

        if setup:
            self.setup()

    def OnSize(self, event):
        event.Skip()
        self.Refresh()  # Prevents distorted drawing under Windows

    def setup(self):
        self.worker = worker.Worker(self)
        self.worker.set_argyll_version("collink")

        for which in ("input", "abstract", "output"):
            ctrl = xrc.XRCCTRL(self, "%s_profile_ctrl" % which)
            setattr(self, "%s_profile_ctrl" % which, ctrl)
            ctrl.changeCallback = getattr(self, "%s_profile_ctrl_handler" % which)
            if which not in ("abstract", "output"):
                ctrl.SetHistory(get_data_path("ref", r"\.(icc|icm)$"))
            ctrl.SetMaxFontSize(11)
            # Drop targets
            droptarget = FileDrop(
                self,
                {
                    ".icc": getattr(self, "%s_drop_handler" % which),
                    ".icm": getattr(self, "%s_drop_handler" % which),
                },
            )
            ctrl.SetDropTarget(droptarget)

        # Bind event handlers
        self.abstract_profile_cb.Bind(
            wx.EVT_CHECKBOX, self.use_abstract_profile_ctrl_handler
        )
        self.output_profile_current_btn.Bind(
            wx.EVT_BUTTON, self.output_profile_current_ctrl_handler
        )
        self.lut3d_trc_apply_none_ctrl.Bind(
            wx.EVT_RADIOBUTTON, self.lut3d_trc_apply_ctrl_handler
        )
        self.lut3d_trc_apply_black_offset_ctrl.Bind(
            wx.EVT_RADIOBUTTON, self.lut3d_trc_apply_ctrl_handler
        )
        self.lut3d_trc_apply_ctrl.Bind(
            wx.EVT_RADIOBUTTON, self.lut3d_trc_apply_ctrl_handler
        )
        self.lut3d_bind_event_handlers()

        self.lut3d_create_btn.SetDefault()

        self.setup_language()
        self.XYZbpin = [0, 0, 0]
        # XYZbpout will be set to the blackpoint of the selected profile. This
        # is used to determine if lack output offset controls should be shown.
        # Set a initial value slightly above zero so output offset controls are
        # shown if the selected profile doesn't exist.
        self.XYZbpout = [0.001, 0.001, 0.001]
        self.update_controls()
        self.update_layout()
        if self.panel.VirtualSize[0] > self.panel.Size[0]:
            scrollrate_x = 2
        else:
            scrollrate_x = 0
        self.panel.SetScrollRate(scrollrate_x, 2)

        config.defaults.update(
            {
                "position.lut3dframe.x": self.GetDisplay().ClientArea[0] + 40,
                "position.lut3dframe.y": self.GetDisplay().ClientArea[1] + 60,
                "size.lut3dframe.w": self.ClientSize[0],
                "size.lut3dframe.h": self.ClientSize[1],
            }
        )

        if (
            self.hascfg("position.lut3dframe.x")
            and self.hascfg("position.lut3dframe.y")
            and self.hascfg("size.lut3dframe.w")
            and self.hascfg("size.lut3dframe.h")
        ):
            self.SetSaneGeometry(
                int(self.getcfg("position.lut3dframe.x")),
                int(self.getcfg("position.lut3dframe.y")),
                int(self.getcfg("size.lut3dframe.w")),
                int(self.getcfg("size.lut3dframe.h")),
            )
        else:
            self.Center()

    def OnClose(self, event=None):
        if getattr(self.worker, "thread", None) and self.worker.thread.is_alive():
            self.worker.abort_subprocess(True)
            return
        if sys.platform == "darwin" or debug:
            self.focus_handler(event)
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            self.setcfg("position.lut3dframe.x", x)
            self.setcfg("position.lut3dframe.y", y)
            self.setcfg("size.lut3dframe.w", self.ClientSize[0])
            self.setcfg("size.lut3dframe.h", self.ClientSize[1])
        if self.Parent:
            config.writecfg()
        else:
            config.writecfg(
                module="3DLUT-maker",
                options=(
                    "3dlut.",
                    "last_3dlut_path",
                    "position.lut3dframe",
                    "size.lut3dframe",
                ),
            )
        if event:
            # Hide first (looks nicer)
            self.Hide()
            # Need to use CallAfter to prevent hang under Windows if minimized
            wx.CallAfter(self.Destroy)

    def use_abstract_profile_ctrl_handler(self, event):
        self.setcfg(
            "3dlut.use_abstract_profile", int(self.abstract_profile_cb.GetValue())
        )
        enable = bool(self.getcfg("3dlut.use_abstract_profile"))
        self.abstract_profile_ctrl.Enable(enable)

    def abstract_drop_handler(self, path):
        if not self.worker.is_working():
            self.abstract_profile_ctrl.SetPath(path)
            self.set_profile("abstract")

    def input_drop_handler(self, path):
        if not self.worker.is_working():
            self.input_profile_ctrl.SetPath(path)
            self.set_profile("input")

    def output_drop_handler(self, path):
        if not self.worker.is_working():
            self.output_profile_ctrl.SetPath(path)
            self.set_profile("output")

    def abstract_profile_ctrl_handler(self, event):
        self.set_profile("abstract", silent=not event)

    def input_profile_ctrl_handler(self, event):
        self.set_profile("input", silent=not event)
        if self.Parent:
            self.Parent.lut3d_init_input_profiles()
            self.Parent.lut3d_update_controls()

    def output_profile_ctrl_handler(self, event):
        self.set_profile("output", silent=not event)

    def output_profile_current_ctrl_handler(self, event):
        profile_path = get_current_profile_path(True, True)
        if profile_path and os.path.isfile(profile_path):
            self.output_profile_ctrl.SetPath(profile_path)
            self.set_profile("output", profile_path or False, silent=not event)

    def get_commands(self):
        return self.get_common_commands() + ["3DLUT-maker [create <filename>]"]

    def process_data(self, data):
        if data[0] == "3DLUT-maker" and (
            len(data) == 1 or (len(data) == 3 and data[1] == "create")
        ):
            if self.IsIconized():
                self.Restore()
            self.Raise()
            if len(data) == 3:
                wx.CallAfter(
                    self.lut3d_create_handler,
                    CustomEvent(wx.EVT_BUTTON.evtType[0], self.lut3d_create_btn),
                    path=data[2],
                )
            return "ok"
        return "invalid"

    def set_profile(self, which, profile_path=None, silent=False):
        path = getattr(self, "%s_profile_ctrl" % which).GetPath()
        if which == "output":
            if profile_path is None:
                profile_path = get_current_profile_path(True, True)
            self.output_profile_current_btn.Enable(
                self.output_profile_ctrl.IsShown()
                and bool(profile_path)
                and os.path.isfile(profile_path)
                and profile_path != path
            )
        if path:
            if not os.path.isfile(path):
                if not silent:
                    show_result_dialog(
                        Error(lang.getstr("file.missing", path)), parent=self
                    )
                return
            try:
                profile = ICCP.ICCProfile(path)
            except (IOError, ICCP.ICCProfileInvalidError):
                if not silent:
                    show_result_dialog(
                        Error(lang.getstr("profile.invalid") + "\n" + path), parent=self
                    )
            except IOError as exception:
                if not silent:
                    show_result_dialog(exception, parent=self)
            else:
                if (
                    which in ("input", "output")
                    and (
                        profile.profileClass not in (b"mntr", b"link", b"scnr", b"spac")
                        or profile.colorSpace != b"RGB"
                    )
                ) or (
                    which == "abstract"
                    and (
                        profile.profileClass != b"abst"
                        or profile.colorSpace not in (b"Lab", b"XYZ")
                    )
                ):
                    show_result_dialog(
                        Error(
                            lang.getstr(
                                "profile.unsupported",
                                (profile.profileClass, profile.colorSpace),
                            )
                        ),
                        parent=self,
                    )
                else:
                    if profile.profileClass == b"link":
                        if which == "output":
                            self.input_profile_ctrl.SetPath(path)
                            if self.getcfg("3dlut.output.profile") == path:
                                # The original file was probably overwritten
                                # by the device link. Reset.
                                self.setcfg("3dlut.output.profile", None)
                            self.output_profile_ctrl.SetPath(
                                self.getcfg("3dlut.output.profile")
                            )
                            self.set_profile("input", silent=silent)
                            return
                        else:
                            self.Freeze()
                            self.abstract_profile_cb.SetValue(False)
                            self.abstract_profile_cb.Hide()
                            self.abstract_profile_ctrl.Hide()
                            self.output_profile_label.Hide()
                            self.output_profile_ctrl.Hide()
                            self.output_profile_current_btn.Hide()
                            self.lut3d_apply_cal_cb.Hide()
                            self.lut3d_trc_label.Hide()
                            self.lut3d_trc_apply_none_ctrl.Hide()
                            self.lut3d_input_value_clipping_bmp.Hide()
                            self.lut3d_input_value_clipping_label.Hide()
                            self.lut3d_trc_apply_black_offset_ctrl.Hide()
                            self.gamut_mapping_mode.Hide()
                            self.gamut_mapping_inverse_a2b.Hide()
                            self.gamut_mapping_b2a.Hide()
                            self.lut3d_show_encoding_controls(False)
                            self.lut3d_show_trc_controls(False)
                            self.lut3d_rendering_intent_label.Hide()
                            self.lut3d_rendering_intent_ctrl.Hide()
                            self.panel.GetSizer().Layout()
                            self.update_layout()
                            self.Thaw()
                    else:
                        if which == "input":
                            if (
                                not hasattr(self, which + "_profile")
                                or self.getcfg("3dlut.%s.profile" % which)
                                != profile.fileName
                            ):
                                # Get profile blackpoint so we can check if it makes
                                # sense to show TRC type and output offset controls
                                try:
                                    odata = self.worker.xicclu(
                                        profile, (0, 0, 0), pcs="x"
                                    )
                                except Exception as exception:
                                    show_result_dialog(exception, self)
                                    self.set_profile_ctrl_path(which)
                                    return
                                else:
                                    if len(odata) != 1 or len(odata[0]) != 3:
                                        show_result_dialog(
                                            "Blackpoint is invalid: %s" % odata, self
                                        )
                                        self.set_profile_ctrl_path(which)
                                        return
                                    self.XYZbpin = odata[0]
                            self.Freeze()
                            self.lut3d_trc_label.Show()
                            self.lut3d_trc_apply_none_ctrl.Show()
                            self.lut3d_trc_apply_black_offset_ctrl.Show()
                            self.gamut_mapping_mode.Show()
                            self.gamut_mapping_inverse_a2b.Show()
                            self.gamut_mapping_b2a.Show()
                            enable = bool(self.getcfg("3dlut.use_abstract_profile"))
                            self.abstract_profile_cb.SetValue(enable)
                            self.abstract_profile_cb.Show()
                            self.abstract_profile_ctrl.Enable(enable)
                            self.abstract_profile_ctrl.Show()
                            self.output_profile_label.Show()
                            self.output_profile_ctrl.Show()
                            self.output_profile_current_btn.Show()
                            self.lut3d_apply_cal_cb.Show()
                            self.lut3d_show_encoding_controls()
                            self.lut3d_update_encoding_controls()
                            # Update controls related to output profile
                            self.input_profile = profile
                            if not self.set_profile("output", silent=silent):
                                self.update_linking_controls()
                                self.lut3d_trc_apply_ctrl_handler()
                        elif which == "output":
                            if (
                                not hasattr(self, which + "_profile")
                                or self.getcfg("3dlut.%s.profile" % which)
                                != profile.fileName
                            ):
                                # Get profile blackpoint so we can check if input
                                # values would be clipped
                                try:
                                    odata = self.worker.xicclu(
                                        profile, (0, 0, 0), pcs="x"
                                    )
                                except Exception as exception:
                                    show_result_dialog(exception, self)
                                    self.set_profile_ctrl_path(which)
                                    return
                                else:
                                    if len(odata) != 1 or len(odata[0]) != 3:
                                        show_result_dialog(
                                            "Blackpoint is invalid: %s" % odata, self
                                        )
                                        self.set_profile_ctrl_path(which)
                                        return
                                    if odata[0][1]:
                                        # Got above zero blackpoint from lookup
                                        self.XYZbpout = odata[0]
                                    else:
                                        # Got zero blackpoint from lookup.
                                        # Try chardata instead.
                                        XYZbp = profile.get_chardata_bkpt()
                                        if XYZbp:
                                            self.XYZbpout = XYZbp
                                        else:
                                            self.XYZbpout = [0, 0, 0]
                            self.Freeze()
                            enable_apply_cal = isinstance(
                                profile.tags.get("vcgt"), ICCP.VideoCardGammaType
                            )
                            self.lut3d_apply_cal_cb.SetValue(
                                enable_apply_cal
                                and bool(self.getcfg("3dlut.output.profile.apply_cal"))
                            )
                            self.lut3d_apply_cal_cb.Enable(enable_apply_cal)
                            self.gamut_mapping_inverse_a2b.Enable()
                            allow_b2a_gamap = (
                                "B2A0" in profile.tags
                                and isinstance(profile.tags.B2A0, ICCP.LUT16Type)
                                and profile.tags.B2A0.clut_grid_steps >= 17
                            )
                            # Allow using B2A instead of inverse A2B?
                            self.gamut_mapping_b2a.Enable(allow_b2a_gamap)
                            if not allow_b2a_gamap:
                                self.setcfg("3dlut.gamap.use_b2a", 0)
                            self.update_linking_controls()
                            self.lut3d_trc_apply_ctrl_handler()
                            self.lut3d_rendering_intent_label.Show()
                            self.lut3d_rendering_intent_ctrl.Show()
                        self.panel.GetSizer().Layout()
                        self.update_layout()
                        if which != "abstract":
                            self.Thaw()
                    setattr(self, "%s_profile" % which, profile)
                    if which == "output" and not self.output_profile_ctrl.IsShown():
                        return
                    self.setcfg("3dlut.%s.profile" % which, profile.fileName)
                    self.lut3d_create_btn.Enable(
                        bool(self.getcfg("3dlut.input.profile"))
                        and os.path.isfile(self.getcfg("3dlut.input.profile"))
                        and (
                            (
                                bool(self.getcfg("3dlut.output.profile"))
                                and os.path.isfile(self.getcfg("3dlut.output.profile"))
                            )
                            or profile.profileClass == b"link"
                        )
                        and (
                            self.getcfg("3dlut.format") != "madVR"
                            or self.output_profile_ctrl.IsShown()
                        )
                    )
                    return profile
            self.set_profile_ctrl_path(which)
        else:
            if which == "input":
                self.set_profile_ctrl_path(which)
                self.lut3d_update_encoding_controls()
            else:
                if not silent:
                    setattr(self, "%s_profile" % which, None)
                    self.setcfg("3dlut.%s.profile" % which, None)
                    if which == "output":
                        self.lut3d_apply_cal_cb.Disable()
                        self.lut3d_create_btn.Disable()

    def set_profile_ctrl_path(self, which):
        getattr(self, "%s_profile_ctrl" % which).SetPath(
            self.getcfg("3dlut.%s.profile" % which)
        )

    def setup_language(self):
        BaseFrame.setup_language(self)

        for which in ("input", "abstract", "output"):
            msg = {
                "input": lang.getstr("3dlut.input.profile"),
                "abstract": lang.getstr("3dlut.use_abstract_profile"),
                "output": lang.getstr("output.profile"),
            }[which]
            kwargs = dict(
                toolTip=msg.rstrip(":"),
                dialogTitle=msg,
                fileMask=lang.getstr("filetype.icc") + "|*.icc;*.icm",
            )
            ctrl = getattr(self, "%s_profile_ctrl" % which)
            for name in kwargs:
                value = kwargs[name]
                setattr(ctrl, name, value)

        self.lut3d_setup_language()

    def update_controls(self):
        """Update controls with values from the configuration"""
        self.panel.Freeze()
        self.lut3d_create_btn.Disable()
        self.input_profile_ctrl.SetPath(self.getcfg("3dlut.input.profile"))
        self.output_profile_ctrl.SetPath(self.getcfg("3dlut.output.profile"))
        self.input_profile_ctrl_handler(None)
        enable = bool(self.getcfg("3dlut.use_abstract_profile"))
        self.abstract_profile_cb.SetValue(enable)
        self.abstract_profile_ctrl.SetPath(self.getcfg("3dlut.abstract.profile"))
        self.abstract_profile_ctrl_handler(None)
        self.output_profile_ctrl_handler(None)
        self.lut3d_update_shared_controls()
        self.panel.Thaw()

    def update_linking_controls(self):
        self.gamut_mapping_inverse_a2b.SetValue(not self.getcfg("3dlut.gamap.use_b2a"))
        self.gamut_mapping_b2a.SetValue(bool(self.getcfg("3dlut.gamap.use_b2a")))
        if (
            hasattr(self, "input_profile")
            and "rTRC" in self.input_profile.tags
            and "gTRC" in self.input_profile.tags
            and "bTRC" in self.input_profile.tags
            and self.input_profile.tags.rTRC
            == self.input_profile.tags.gTRC
            == self.input_profile.tags.bTRC
            and isinstance(self.input_profile.tags.rTRC, ICCP.CurveType)
        ):
            tf = self.input_profile.tags.rTRC.get_transfer_function(outoffset=1.0)
            if self.getcfg("3dlut.input.profile") != self.input_profile.fileName:
                # Use BT.1886 gamma mapping for SMPTE 240M /
                # Rec. 709 TRC
                self.setcfg(
                    "3dlut.apply_trc",
                    int(
                        tf[0][1] in (-240, -709)
                        or (tf[0][0].startswith("Gamma") and tf[1] >= 0.95)
                    ),
                )
                # Use only BT.1886 black output offset
                self.setcfg(
                    "3dlut.apply_black_offset",
                    int(
                        tf[0][1] not in (-240, -709)
                        and (not tf[0][0].startswith("Gamma") or tf[1] < 0.95)
                        and self.XYZbpin != self.XYZbpout
                    ),
                )
                # Set gamma to profile gamma if single gamma
                # profile
                if tf[0][0].startswith("Gamma") and tf[1] >= 0.95:
                    if not self.getcfg("3dlut.trc_gamma.backup", False):
                        # Backup current gamma
                        self.setcfg(
                            "3dlut.trc_gamma.backup", self.getcfg("3dlut.trc_gamma")
                        )
                    self.setcfg("3dlut.trc_gamma", round(tf[0][1], 2))
                # Restore previous gamma if not single gamma
                # profile
                elif self.getcfg("3dlut.trc_gamma.backup", False):
                    self.setcfg(
                        "3dlut.trc_gamma", self.getcfg("3dlut.trc_gamma.backup")
                    )
                    self.setcfg("3dlut.trc_gamma.backup", None)
            self.lut3d_trc_apply_black_offset_ctrl.Enable(
                tf[0][1] not in (-240, -709) and self.XYZbpin != self.XYZbpout
            )
            self.lut3d_update_trc_controls()
        elif (
            hasattr(self, "input_profile")
            and isinstance(self.input_profile.tags.get("A2B0"), ICCP.LUT16Type)
            and isinstance(
                self.input_profile.tags.get("A2B1", ICCP.LUT16Type()), ICCP.LUT16Type
            )
            and isinstance(
                self.input_profile.tags.get("A2B2", ICCP.LUT16Type()), ICCP.LUT16Type
            )
        ):
            self.lut3d_trc_apply_black_offset_ctrl.Enable(self.XYZbpin != self.XYZbpout)
            if self.XYZbpin == self.XYZbpout:
                self.setcfg("3dlut.apply_black_offset", 0)
        else:
            self.lut3d_trc_apply_black_offset_ctrl.Disable()
            self.setcfg("3dlut.apply_black_offset", 0)
        if self.getcfg("3dlut.apply_black_offset"):
            self.lut3d_trc_apply_black_offset_ctrl.SetValue(True)
        elif self.getcfg("3dlut.apply_trc"):
            self.lut3d_trc_apply_ctrl.SetValue(True)
        else:
            self.lut3d_trc_apply_none_ctrl.SetValue(True)
        self.lut3d_show_trc_controls()


def main():
    config.initcfg("3DLUT-maker")
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = LUT3DFrame(setup=False)
    if sys.platform == "darwin":
        app.TopWindow.init_menubar()
    wx.CallLater(1, _main, app)
    app.MainLoop()


def _main(app):
    app.TopWindow.listen()
    app.TopWindow.setup()
    app.TopWindow.Show()


if __name__ == "__main__":
    main()
