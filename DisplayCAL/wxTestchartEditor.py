# -*- coding: utf-8 -*-


import csv
import math
import os
import re
import shutil
import sys
import time

if sys.platform == "win32":
    import win32file

from DisplayCAL import CGATS
from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import colormath
from DisplayCAL import config
from DisplayCAL import imfile
from DisplayCAL import localization as lang
from DisplayCAL.argyll_RGB2XYZ import (
    RGB2XYZ as argyll_RGB2XYZ,
    XYZ2RGB as argyll_XYZ2RGB,
)
from DisplayCAL.argyll_cgats import ti3_to_ti1, verify_cgats
from DisplayCAL.config import (
    defaults,
    getbitmap,
    getcfg,
    geticon,
    get_current_profile,
    get_display_name,
    get_data_path,
    get_total_patches,
    get_verified_path,
    hascfg,
    profile_ext,
    setcfg,
    writecfg,
)
from DisplayCAL.debughelpers import handle_error
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug, tc_use_alternate_preview, test, verbose
from DisplayCAL.util_os import expanduseru, is_superuser, launch_file, waccess
from DisplayCAL.worker import (
    Error,
    Worker,
    check_file_isfile,
    check_set_argyll_bin,
    get_argyll_util,
    get_current_profile_path,
    show_result_dialog,
)
from DisplayCAL.wxaddons import CustomEvent, CustomGridCellEvent, wx
from DisplayCAL.wxwindows import (
    BaseApp,
    BaseFrame,
    CustomGrid,
    ConfirmDialog,
    FileBrowseBitmapButtonWithChoiceHistory,
    FileDrop,
    InfoDialog,
    get_gradient_panel,
)
from DisplayCAL.wxfixes import GenBitmapButton as BitmapButton
from DisplayCAL import floatspin
from DisplayCAL.wxMeasureFrame import get_default_size


def swap_dict_keys_values(mydict):
    return dict([(v, k) for (k, v) in mydict.items()])


class TestchartEditor(BaseFrame):
    def __init__(
        self,
        parent=None,
        id=-1,
        path=None,
        cfg="testchart.file",
        parent_set_chart_methodname="set_testchart",
        setup=True,
    ):
        BaseFrame.__init__(
            self, parent, id, lang.getstr("testchart.edit"), name="tcgen"
        )
        self.SetIcons(
            config.get_icon_bundle([256, 48, 32, 16], appname + "-testchart-editor")
        )
        self.Bind(wx.EVT_CLOSE, self.tc_close_handler)

        self.tc_algos_ab = {
            "": lang.getstr("tc.ofp"),
            "t": lang.getstr("tc.t"),
            "r": lang.getstr("tc.r"),
            "R": lang.getstr("tc.R"),
            "q": lang.getstr("tc.q"),
            "i": lang.getstr("tc.i"),
            "I": lang.getstr("tc.I"),
        }

        self.cfg = cfg
        self.parent_set_chart_methodname = parent_set_chart_methodname

        if setup:
            self.setup(path)

    def setup(self, path=None):
        self.worker = Worker(self)
        self.worker.set_argyll_version("targen")

        if self.worker.argyll_version >= [1, 1, 0]:
            self.tc_algos_ab["Q"] = lang.getstr("tc.Q")

        self.tc_algos_ba = swap_dict_keys_values(self.tc_algos_ab)

        self.label_b2a = {
            "R %": "RGB_R",
            "G %": "RGB_G",
            "B %": "RGB_B",
            "X": "XYZ_X",
            "Y": "XYZ_Y",
            "Z": "XYZ_Z",
        }

        self.droptarget = FileDrop(self)
        self.droptarget.drophandlers = {
            ".cgats": self.ti1_drop_handler,
            ".cie": self.tc_drop_ti3_handler,
            ".csv": self.csv_drop_handler,
            ".gam": self.tc_drop_ti3_handler,
            ".icc": self.ti1_drop_handler,
            ".icm": self.ti1_drop_handler,
            ".jpg": self.tc_drop_ti3_handler,
            ".jpeg": self.tc_drop_ti3_handler,
            ".png": self.tc_drop_ti3_handler,
            ".tif": self.tc_drop_ti3_handler,
            ".tiff": self.tc_drop_ti3_handler,
            ".ti1": self.ti1_drop_handler,
            ".ti3": self.ti1_drop_handler,
            ".txt": self.ti1_drop_handler,
        }

        scale = getcfg("app.dpi") / config.get_default_dpi()
        if scale < 1:
            scale = 1

        if tc_use_alternate_preview:
            # splitter
            splitter = self.splitter = wx.SplitterWindow(
                self, -1, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH
            )
            if wx.VERSION < (2, 9):
                self.Bind(
                    wx.EVT_SPLITTER_SASH_POS_CHANGED, self.tc_sash_handler, splitter
                )
                self.Bind(
                    wx.EVT_SPLITTER_SASH_POS_CHANGING, self.tc_sash_handler, splitter
                )

            p1 = wx.Panel(splitter)
            p1.sizer = wx.BoxSizer(wx.VERTICAL)
            p1.SetSizer(p1.sizer)

            p2 = wx.Panel(splitter)
            # Setting a droptarget seems to cause crash when destroying
            # p2.SetDropTarget(self.droptarget)
            p2.sizer = wx.BoxSizer(wx.VERTICAL)
            p2.SetSizer(p2.sizer)

            splitter.SetMinimumPaneSize(23)
            # splitter end

            panel = self.panel = p1
        else:
            panel = self.panel = wx.Panel(self)
        panel.SetDropTarget(self.droptarget)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(self.sizer)

        border = 4

        sizer = wx.FlexGridSizer(0, 4, 0, 0)
        self.sizer.Add(sizer, flag=(wx.ALL & ~wx.BOTTOM), border=12)

        # white patches
        sizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.white")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_white_patches = wx.SpinCtrl(
            panel, -1, size=(100 * scale, -1), min=0, name="tc_white_patches"
        )
        self.Bind(
            wx.EVT_TEXT, self.tc_white_patches_handler, id=self.tc_white_patches.GetId()
        )
        sizer.Add(
            self.tc_white_patches, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        # single channel patches
        sizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.single")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT,
            border=border,
        )
        self.tc_single_channel_patches = wx.SpinCtrl(
            panel,
            -1,
            size=(100 * scale, -1),
            min=0,
            max=256,
            name="tc_single_channel_patches",
        )
        self.tc_single_channel_patches.Bind(
            wx.EVT_KILL_FOCUS, self.tc_single_channel_patches_handler
        )
        self.Bind(
            wx.EVT_SPINCTRL,
            self.tc_single_channel_patches_handler,
            id=self.tc_single_channel_patches.GetId(),
        )
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(hsizer)
        hsizer.Add(
            self.tc_single_channel_patches,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        hsizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.single.perchannel")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        # black patches
        if self.worker.argyll_version >= [1, 6]:
            hsizer.Add(
                wx.StaticText(panel, -1, lang.getstr("tc.black")),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
            self.tc_black_patches = wx.SpinCtrl(
                panel, -1, size=(100 * scale, -1), min=0, name="tc_black_patches"
            )
            self.Bind(
                wx.EVT_TEXT,
                self.tc_black_patches_handler,
                id=self.tc_black_patches.GetId(),
            )
            hsizer.Add(
                self.tc_black_patches,
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )

        # gray axis patches
        sizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.gray")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_gray_patches = wx.SpinCtrl(
            panel, -1, size=(100 * scale, -1), min=0, max=256, name="tc_gray_patches"
        )
        self.tc_gray_patches.Bind(wx.EVT_KILL_FOCUS, self.tc_gray_handler)
        self.Bind(
            wx.EVT_SPINCTRL, self.tc_gray_handler, id=self.tc_gray_patches.GetId()
        )
        sizer.Add(
            self.tc_gray_patches, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        # multidim steps
        sizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.multidim")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT,
            border=border,
        )
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(hsizer)
        self.tc_multi_steps = wx.SpinCtrl(
            panel, -1, size=(100 * scale, -1), min=0, max=21, name="tc_multi_steps"
        )  # 16 multi dim steps = 4096 patches
        self.tc_multi_steps.Bind(wx.EVT_KILL_FOCUS, self.tc_multi_steps_handler)
        self.Bind(
            wx.EVT_SPINCTRL, self.tc_multi_steps_handler, id=self.tc_multi_steps.GetId()
        )
        hsizer.Add(
            self.tc_multi_steps, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        if self.worker.argyll_version >= [1, 6, 0]:
            self.tc_multi_bcc_cb = wx.CheckBox(panel, -1, lang.getstr("centered"))
            self.tc_multi_bcc_cb.Bind(wx.EVT_CHECKBOX, self.tc_multi_bcc_cb_handler)
            hsizer.Add(
                self.tc_multi_bcc_cb,
                flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
        self.tc_multi_patches = wx.StaticText(panel, -1, "", name="tc_multi_patches")
        hsizer.Add(
            self.tc_multi_patches, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        # full spread patches
        sizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.fullspread")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_fullspread_patches = wx.SpinCtrl(
            panel,
            -1,
            size=(100 * scale, -1),
            min=0,
            max=9999,
            name="tc_fullspread_patches",
        )
        self.Bind(
            wx.EVT_TEXT,
            self.tc_fullspread_handler,
            id=self.tc_fullspread_patches.GetId(),
        )
        sizer.Add(
            self.tc_fullspread_patches,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        # algo
        algos = list(self.tc_algos_ab.values())
        algos.sort()
        sizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.algo")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT,
            border=border,
        )
        self.tc_algo = wx.Choice(panel, -1, choices=algos, name="tc_algo")
        self.tc_algo.Disable()
        self.Bind(wx.EVT_CHOICE, self.tc_algo_handler, id=self.tc_algo.GetId())
        sizer.Add(self.tc_algo, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border)

        # adaption
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(hsizer, 1, flag=wx.EXPAND)
        hsizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.adaption")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_adaption_slider = wx.Slider(
            panel, -1, 0, 0, 100, size=(64 * scale, -1), name="tc_adaption_slider"
        )
        self.tc_adaption_slider.Disable()
        self.Bind(
            wx.EVT_SLIDER, self.tc_adaption_handler, id=self.tc_adaption_slider.GetId()
        )
        hsizer.Add(self.tc_adaption_slider, flag=wx.ALIGN_CENTER_VERTICAL)
        self.tc_adaption_intctrl = wx.SpinCtrl(
            panel,
            -1,
            size=(100 * scale, -1),
            min=0,
            max=100,
            name="tc_adaption_intctrl",
        )
        self.tc_adaption_intctrl.Disable()
        self.Bind(
            wx.EVT_TEXT, self.tc_adaption_handler, id=self.tc_adaption_intctrl.GetId()
        )
        sizer.Add(
            self.tc_adaption_intctrl,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        hsizer = wx.GridSizer(0, 2, 0, 0)
        sizer.Add(hsizer, 1, flag=wx.EXPAND)
        hsizer.Add(
            wx.StaticText(panel, -1, "%"),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        hsizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.angle")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT,
            border=border,
        )

        # angle
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(hsizer, 1, flag=wx.EXPAND)
        self.tc_angle_slider = wx.Slider(
            panel, -1, 0, 0, 5000, size=(128 * scale, -1), name="tc_angle_slider"
        )
        self.tc_angle_slider.Disable()
        self.Bind(wx.EVT_SLIDER, self.tc_angle_handler, id=self.tc_angle_slider.GetId())
        hsizer.Add(self.tc_angle_slider, flag=wx.ALIGN_CENTER_VERTICAL)
        self.tc_angle_intctrl = wx.SpinCtrl(
            panel, -1, size=(110 * scale, -1), min=0, max=5000, name="tc_angle_intctrl"
        )
        self.tc_angle_intctrl.Disable()
        self.Bind(wx.EVT_TEXT, self.tc_angle_handler, id=self.tc_angle_intctrl.GetId())
        hsizer.Add(
            self.tc_angle_intctrl, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        # gamma
        if self.worker.argyll_version == [
            1,
            1,
            "RC2",
        ] or self.worker.argyll_version >= [1, 1]:
            sizer.Add(
                wx.StaticText(panel, -1, lang.getstr("trc.gamma")),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
            self.tc_gamma_floatctrl = floatspin.FloatSpin(
                panel,
                -1,
                size=(100 * scale, -1),
                min_val=0.0,
                max_val=9.9,
                increment=0.05,
                digits=2,
                name="tc_gamma_floatctrl",
            )
            self.Bind(
                floatspin.EVT_FLOATSPIN,
                self.tc_gamma_handler,
                id=self.tc_gamma_floatctrl.GetId(),
            )
            sizer.Add(
                self.tc_gamma_floatctrl,
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )

        # neutral axis emphasis
        if self.worker.argyll_version >= [1, 3, 3]:
            sizer.Add(
                wx.StaticText(panel, -1, lang.getstr("tc.neutral_axis_emphasis")),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT,
                border=border,
            )
            hsizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(hsizer, 1, flag=wx.EXPAND)
            self.tc_neutral_axis_emphasis_slider = wx.Slider(
                panel,
                -1,
                0,
                0,
                100,
                size=(64 * scale, -1),
                name="tc_neutral_axis_emphasis_slider",
            )
            self.tc_neutral_axis_emphasis_slider.Disable()
            self.Bind(
                wx.EVT_SLIDER,
                self.tc_neutral_axis_emphasis_handler,
                id=self.tc_neutral_axis_emphasis_slider.GetId(),
            )
            hsizer.Add(
                self.tc_neutral_axis_emphasis_slider, flag=wx.ALIGN_CENTER_VERTICAL
            )
            self.tc_neutral_axis_emphasis_intctrl = wx.SpinCtrl(
                panel,
                -1,
                size=(100 * scale, -1),
                min=0,
                max=100,
                name="tc_neutral_axis_emphasis_intctrl",
            )
            self.tc_neutral_axis_emphasis_intctrl.Disable()
            self.Bind(
                wx.EVT_TEXT,
                self.tc_neutral_axis_emphasis_handler,
                id=self.tc_neutral_axis_emphasis_intctrl.GetId(),
            )
            hsizer.Add(
                self.tc_neutral_axis_emphasis_intctrl,
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
            hsizer.Add(
                wx.StaticText(panel, -1, "%"),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )

        # dark patch emphasis
        if self.worker.argyll_version >= [1, 6, 2]:
            hsizer.Add(
                wx.StaticText(panel, -1, lang.getstr("tc.dark_emphasis")),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
            self.tc_dark_emphasis_slider = wx.Slider(
                panel,
                -1,
                0,
                0,
                100,
                size=(64 * scale, -1),
                name="tc_dark_emphasis_slider",
            )
            self.tc_dark_emphasis_slider.Disable()
            self.Bind(
                wx.EVT_SLIDER,
                self.tc_dark_emphasis_handler,
                id=self.tc_dark_emphasis_slider.GetId(),
            )
            hsizer.Add(self.tc_dark_emphasis_slider, flag=wx.ALIGN_CENTER_VERTICAL)
            self.tc_dark_emphasis_intctrl = wx.SpinCtrl(
                panel,
                -1,
                size=(100 * scale, -1),
                min=0,
                max=100,
                name="tc_dark_emphasis_intctrl",
            )
            self.tc_dark_emphasis_intctrl.Disable()
            self.Bind(
                wx.EVT_TEXT,
                self.tc_dark_emphasis_handler,
                id=self.tc_dark_emphasis_intctrl.GetId(),
            )
            hsizer.Add(
                self.tc_dark_emphasis_intctrl,
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
            hsizer.Add(
                wx.StaticText(panel, -1, "%"),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )

        # precond profile
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(
            hsizer, flag=wx.ALL & ~(wx.BOTTOM | wx.TOP) | wx.EXPAND, border=12
        )
        self.tc_precond = wx.CheckBox(
            panel, -1, lang.getstr("tc.precond"), name="tc_precond"
        )
        self.tc_precond.Disable()
        self.Bind(wx.EVT_CHECKBOX, self.tc_precond_handler, id=self.tc_precond.GetId())
        hsizer.Add(
            self.tc_precond, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        self.tc_precond_profile = FileBrowseBitmapButtonWithChoiceHistory(
            panel,
            -1,
            toolTip=lang.getstr("tc.precond"),
            dialogTitle=lang.getstr("tc.precond"),
            fileMask=lang.getstr("filetype.icc_mpp") + "|*.icc;*.icm;*.mpp",
            changeCallback=self.tc_precond_profile_handler,
            history=get_data_path("ref", r"\.(icm|icc)$"),
        )
        self.tc_precond_profile.SetMaxFontSize(11)
        hsizer.Add(
            self.tc_precond_profile,
            1,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        self.tc_precond_profile_current_btn = wx.Button(
            panel, -1, lang.getstr("profile.current"), name="tc_precond_profile_current"
        )
        self.Bind(
            wx.EVT_BUTTON,
            self.tc_precond_profile_current_ctrl_handler,
            id=self.tc_precond_profile_current_btn.GetId(),
        )
        hsizer.Add(
            self.tc_precond_profile_current_btn,
            0,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.precond_droptarget = FileDrop(self)
        self.precond_droptarget.drophandlers = {
            ".icc": self.precond_profile_drop_handler,
            ".icm": self.precond_profile_drop_handler,
        }
        self.tc_precond_profile.SetDropTarget(self.precond_droptarget)

        # limit samples to lab sphere
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(hsizer, flag=wx.ALL & ~(wx.BOTTOM | wx.TOP), border=12)
        self.tc_filter = wx.CheckBox(
            panel, -1, lang.getstr("tc.limit.sphere"), name="tc_filter"
        )
        self.Bind(wx.EVT_CHECKBOX, self.tc_filter_handler, id=self.tc_filter.GetId())
        hsizer.Add(
            self.tc_filter, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        # L
        hsizer.Add(
            wx.StaticText(panel, -1, "L"),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_filter_L = wx.SpinCtrl(
            panel,
            -1,
            initial=50,
            size=(100 * scale, -1),
            min=0,
            max=100,
            name="tc_filter_L",
        )
        self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id=self.tc_filter_L.GetId())
        hsizer.Add(
            self.tc_filter_L, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        # a
        hsizer.Add(
            wx.StaticText(panel, -1, "a"),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_filter_a = wx.SpinCtrl(
            panel,
            -1,
            initial=0,
            size=(100 * scale, -1),
            min=-128,
            max=127,
            name="tc_filter_a",
        )
        self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id=self.tc_filter_a.GetId())
        hsizer.Add(
            self.tc_filter_a, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        # b
        hsizer.Add(
            wx.StaticText(panel, -1, "b"),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_filter_b = wx.SpinCtrl(
            panel,
            -1,
            initial=0,
            size=(100 * scale, -1),
            min=-128,
            max=127,
            name="tc_filter_b",
        )
        self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id=self.tc_filter_b.GetId())
        hsizer.Add(
            self.tc_filter_b, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        # radius
        hsizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.limit.sphere_radius")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_filter_rad = wx.SpinCtrl(
            panel,
            -1,
            initial=255,
            size=(100 * scale, -1),
            min=1,
            max=255,
            name="tc_filter_rad",
        )
        self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id=self.tc_filter_rad.GetId())
        hsizer.Add(
            self.tc_filter_rad, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        # diagnostic VRML files
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(hsizer, flag=wx.ALL & ~(wx.BOTTOM | wx.TOP), border=12 + border)

        self.vrml_save_as_btn = wx.BitmapButton(panel, -1, geticon(16, "3D"))
        if sys.platform == "darwin":
            # Work-around bitmap cutoff on left and right side
            w = self.vrml_save_as_btn.Size[0] + 4
        else:
            w = -1
        self.vrml_save_as_btn.MinSize = (w, -1)
        self.vrml_save_as_btn.SetToolTipString(lang.getstr("tc.3d"))
        self.vrml_save_as_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.tc_view_3d, id=self.vrml_save_as_btn.GetId())
        self.vrml_save_as_btn.Bind(wx.EVT_CONTEXT_MENU, self.view_3d_format_popup)
        hsizer.Add(
            self.vrml_save_as_btn,
            flag=wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL,
            border=border * 2,
        )
        hsizer.Add((1, 1))
        self.view_3d_format_btn = wx.BitmapButton(
            panel, -1, getbitmap("theme/dropdown-arrow")
        )
        if sys.platform == "darwin":
            # Work-around bitmap cutoff on left and right side
            w = self.view_3d_format_btn.Size[0] + 4
        else:
            w = -1
        self.view_3d_format_btn.MinSize = (w, self.vrml_save_as_btn.Size[1])
        self.view_3d_format_btn.Bind(wx.EVT_BUTTON, self.view_3d_format_popup)
        self.view_3d_format_btn.Bind(wx.EVT_CONTEXT_MENU, self.view_3d_format_popup)
        self.view_3d_format_btn.SetToolTipString(lang.getstr("tc.3d"))
        self.view_3d_format_btn.Disable()
        hsizer.Add(
            self.view_3d_format_btn,
            flag=(wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL,
            border=border * 2,
        )
        self.tc_vrml_cie = wx.CheckBox(
            panel, -1, "", name="tc_vrml_cie", style=wx.RB_GROUP
        )
        self.tc_vrml_cie.SetToolTipString(lang.getstr("tc.3d"))
        self.Bind(wx.EVT_CHECKBOX, self.tc_vrml_handler, id=self.tc_vrml_cie.GetId())
        hsizer.Add(
            self.tc_vrml_cie,
            flag=(wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL,
            border=border * 2,
        )
        self.tc_vrml_cie_colorspace_ctrl = wx.Choice(
            panel, -1, choices=config.valid_values["tc_vrml_cie_colorspace"]
        )
        self.tc_vrml_cie_colorspace_ctrl.SetToolTipString(lang.getstr("tc.3d"))
        self.Bind(
            wx.EVT_CHOICE,
            self.tc_vrml_handler,
            id=self.tc_vrml_cie_colorspace_ctrl.GetId(),
        )
        hsizer.Add(
            self.tc_vrml_cie_colorspace_ctrl,
            flag=(wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL,
            border=border * 2,
        )
        self.tc_vrml_device = wx.CheckBox(panel, -1, "", name="tc_vrml_device")
        self.tc_vrml_device.SetToolTipString(lang.getstr("tc.3d"))
        self.Bind(wx.EVT_CHECKBOX, self.tc_vrml_handler, id=self.tc_vrml_device.GetId())
        hsizer.Add(
            self.tc_vrml_device,
            flag=(wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL,
            border=border * 2,
        )
        self.tc_vrml_device_colorspace_ctrl = wx.Choice(
            panel, -1, choices=config.valid_values["tc_vrml_device_colorspace"]
        )
        self.tc_vrml_device_colorspace_ctrl.SetToolTipString(lang.getstr("tc.3d"))
        self.Bind(
            wx.EVT_CHOICE,
            self.tc_vrml_handler,
            id=self.tc_vrml_device_colorspace_ctrl.GetId(),
        )
        hsizer.Add(
            self.tc_vrml_device_colorspace_ctrl,
            flag=(wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL,
            border=border * 2,
        )

        hsizer.Add(
            wx.StaticText(panel, -1, lang.getstr("tc.vrml.black_offset")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_vrml_black_offset_intctrl = wx.SpinCtrl(
            panel,
            -1,
            size=(90 * scale, -1),
            min=0,
            max=40,
            name="tc_vrml_black_offset_intctrl",
        )
        self.Bind(
            wx.EVT_TEXT,
            self.tc_vrml_black_offset_ctrl_handler,
            id=self.tc_vrml_black_offset_intctrl.GetId(),
        )
        hsizer.Add(
            self.tc_vrml_black_offset_intctrl,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_vrml_use_D50_cb = wx.CheckBox(
            panel, -1, lang.getstr("tc.vrml.use_D50"), name="tc_vrml_use_D50_cb"
        )
        self.Bind(
            wx.EVT_CHECKBOX,
            self.tc_vrml_use_D50_handler,
            id=self.tc_vrml_use_D50_cb.GetId(),
        )
        hsizer.Add(
            self.tc_vrml_use_D50_cb,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.tc_vrml_compress_cb = wx.CheckBox(
            panel, -1, lang.getstr("compression.gzip"), name="tc_vrml_compress_cb"
        )
        self.Bind(
            wx.EVT_CHECKBOX,
            self.tc_vrml_compress_handler,
            id=self.tc_vrml_compress_cb.GetId(),
        )
        hsizer.Add(
            self.tc_vrml_compress_cb,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        # buttons
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(hsizer, flag=(wx.ALL & ~wx.BOTTOM) | wx.ALIGN_CENTER, border=12)

        self.preview_btn = wx.Button(
            panel, -1, lang.getstr("testchart.create"), name="tc_create"
        )
        self.Bind(wx.EVT_BUTTON, self.tc_preview_handler, id=self.preview_btn.GetId())
        hsizer.Add(
            self.preview_btn, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        self.save_btn = wx.Button(panel, -1, lang.getstr("save"))
        self.save_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.tc_save_handler, id=self.save_btn.GetId())
        hsizer.Add(self.save_btn, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border)

        self.save_as_btn = wx.Button(panel, -1, lang.getstr("save_as"))
        self.save_as_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.tc_save_as_handler, id=self.save_as_btn.GetId())
        hsizer.Add(
            self.save_as_btn, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        self.export_btn = wx.Button(panel, -1, lang.getstr("export"), name="tc_export")
        self.export_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.tc_export_handler, id=self.export_btn.GetId())
        hsizer.Add(
            self.export_btn, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        self.clear_btn = wx.Button(
            panel, -1, lang.getstr("testchart.discard"), name="tc_clear"
        )
        self.clear_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.tc_clear_handler, id=self.clear_btn.GetId())
        hsizer.Add(
            self.clear_btn, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )

        # buttons row 2
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(hsizer, flag=wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border=12)

        hsizer.Add(
            wx.StaticText(panel, -1, lang.getstr("testchart.add_saturation_sweeps")),
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        self.saturation_sweeps_intctrl = wx.SpinCtrl(
            panel,
            -1,
            size=(95 * scale, -1),
            initial=getcfg("tc.saturation_sweeps"),
            min=2,
            max=255,
        )
        self.saturation_sweeps_intctrl.Disable()
        hsizer.Add(
            self.saturation_sweeps_intctrl,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        for color in ("R", "G", "B", "C", "M", "Y"):
            name = "saturation_sweeps_%s_btn" % color
            setattr(self, name, wx.Button(panel, -1, color, size=(45 * scale, -1)))
            getattr(self, "saturation_sweeps_%s_btn" % color).Disable()
            self.Bind(
                wx.EVT_BUTTON,
                self.tc_add_saturation_sweeps_handler,
                id=getattr(self, name).GetId(),
            )
            hsizer.Add(
                getattr(self, name),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )

        self.saturation_sweeps_custom_btn = wx.Button(
            panel, -1, "=", size=(45 * scale, -1)
        )
        self.saturation_sweeps_custom_btn.Disable()
        self.Bind(
            wx.EVT_BUTTON,
            self.tc_add_saturation_sweeps_handler,
            id=self.saturation_sweeps_custom_btn.GetId(),
        )
        hsizer.Add(
            self.saturation_sweeps_custom_btn,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        for component in ("R", "G", "B"):
            hsizer.Add(
                wx.StaticText(panel, -1, component),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )
            name = "saturation_sweeps_custom_%s_ctrl" % component
            setattr(
                self,
                name,
                floatspin.FloatSpin(
                    panel,
                    -1,
                    size=(100 * scale, -1),
                    value=getcfg("tc.saturation_sweeps.custom.%s" % component),
                    min_val=0,
                    max_val=100,
                    increment=100.0 / 255,
                    digits=2,
                ),
            )
            getattr(self, "saturation_sweeps_custom_%s_ctrl" % component).Disable()
            self.Bind(
                floatspin.EVT_FLOATSPIN,
                self.tc_algo_handler,
                id=getattr(self, name).GetId(),
            )
            hsizer.Add(
                getattr(self, name),
                flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
                border=border,
            )

        # buttons row 3
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(hsizer, flag=wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border=12)

        self.add_ti3_btn = wx.Button(
            panel, -1, lang.getstr("testchart.add_ti3_patches")
        )
        self.add_ti3_btn.Disable()
        self.Bind(wx.EVT_BUTTON, self.tc_add_ti3_handler, id=self.add_ti3_btn.GetId())
        hsizer.Add(
            self.add_ti3_btn, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=border
        )
        self.add_ti3_relative_cb = wx.CheckBox(
            panel, -1, lang.getstr("whitepoint.simulate.relative")
        )
        self.add_ti3_relative_cb.Disable()
        self.Bind(
            wx.EVT_CHECKBOX,
            self.tc_add_ti3_relative_handler,
            id=self.add_ti3_relative_cb.GetId(),
        )
        hsizer.Add(
            self.add_ti3_relative_cb,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )
        hsizer.Add((50, 1))

        patch_order_choices = []
        for lstr in (
            "testchart.sort_RGB_gray_to_top",
            "testchart.sort_RGB_white_to_top",
            "testchart.sort_RGB_red_to_top",
            "testchart.sort_RGB_green_to_top",
            "testchart.sort_RGB_blue_to_top",
            "testchart.sort_RGB_cyan_to_top",
            "testchart.sort_RGB_magenta_to_top",
            "testchart.sort_RGB_yellow_to_top",
            "testchart.sort_by_HSI",
            "testchart.sort_by_HSL",
            "testchart.sort_by_HSV",
            "testchart.sort_by_L",
            "testchart.sort_by_rec709_luma",
            "testchart.sort_by_RGB",
            "testchart.sort_by_RGB_sum",
            "testchart.sort_by_BGR",
            "testchart.optimize_display_response_delay",
            "testchart.interleave",
            "testchart.shift_interleave",
            "testchart.maximize_lightness_difference",
            "testchart.maximize_rec709_luma_difference",
            "testchart.maximize_RGB_difference",
            "testchart.vary_RGB_difference",
        ):
            patch_order_choices.append(lang.getstr(lstr))
        self.change_patch_order_ctrl = wx.Choice(panel, -1, choices=patch_order_choices)
        self.change_patch_order_ctrl.SetSelection(0)
        self.change_patch_order_ctrl.SetToolTipString(
            lang.getstr("testchart.change_patch_order")
        )
        hsizer.Add(
            self.change_patch_order_ctrl,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        self.change_patch_order_btn = wx.Button(panel, -1, lang.getstr("apply"))
        self.Bind(
            wx.EVT_BUTTON, self.tc_sort_handler, id=self.change_patch_order_btn.GetId()
        )
        hsizer.Add(
            self.change_patch_order_btn,
            flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL,
            border=border,
        )

        # grid
        self.sizer.Add((-1, 12))
        self.grid = CustomGrid(panel, -1, size=(-1, 100))
        self.grid.DisableDragColSize()
        self.grid.EnableGridLines(False)
        self.grid.SetCellHighlightPenWidth(0)
        self.grid.SetCellHighlightROPenWidth(0)
        self.grid.SetColLabelSize(self.grid.GetDefaultRowSize())
        self.grid.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
        self.grid.SetScrollRate(0, 5)
        self.grid.draw_horizontal_grid_lines = False
        self.grid.draw_vertical_grid_lines = False
        self.sizer.Add(self.grid, 1, flag=wx.EXPAND)
        self.grid.CreateGrid(0, 0)
        font = self.grid.GetDefaultCellFont()
        if font.PointSize > 11:
            font.PointSize = 11
            self.grid.SetDefaultCellFont(font)
        self.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.tc_grid_cell_change_handler)
        self.grid.Bind(
            wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.tc_grid_label_left_click_handler
        )
        self.grid.Bind(
            wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.tc_grid_label_left_dclick_handler
        )
        self.grid.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.tc_grid_range_select_handler)
        self.grid.DisableDragRowSize()
        if tc_use_alternate_preview:
            separator_color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
            separator = wx.Panel(panel, size=(-1, 1))
            separator.BackgroundColour = separator_color
            self.sizer.Add(separator, flag=wx.EXPAND)

        # preview area
        if tc_use_alternate_preview:
            self.sizer.SetSizeHints(self)
            self.sizer.Layout()
            self.sizer.SetMinSize((self.sizer.MinSize[0], self.sizer.MinSize[1] + 1))
            p1.SetMinSize(self.sizer.MinSize)
            splitter.SplitHorizontally(p1, p2, self.sizer.GetMinSize()[1])
            hsizer = wx.BoxSizer(wx.VERTICAL)
            gradientpanel = get_gradient_panel(p2, lang.getstr("preview"))
            gradientpanel.MinSize = (-1, 23 * scale)
            p2.sizer.Add(gradientpanel, flag=wx.EXPAND)
            p2.sizer.Add(hsizer, 1, flag=wx.EXPAND)
            p2.BackgroundColour = "#333333"
            preview = CustomGrid(p2, -1, size=(-1, 100))
            preview.DisableDragColSize()
            preview.DisableDragRowSize()
            preview.EnableEditing(False)
            preview.EnableGridLines(False)
            preview.SetCellHighlightPenWidth(0)
            preview.SetCellHighlightROPenWidth(0)
            preview.SetColLabelSize(self.grid.GetDefaultRowSize())
            preview.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
            preview.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
            preview.SetLabelTextColour("#CCCCCC")
            preview.SetScrollRate(0, 5)
            preview._default_col_label_renderer.bgcolor = "#333333"
            preview._default_row_label_renderer.bgcolor = "#333333"
            preview.alternate_cell_background_color = False
            preview.alternate_row_label_background_color = False
            preview.draw_horizontal_grid_lines = False
            preview.draw_vertical_grid_lines = False
            preview.rendernative = False
            preview.style = ""
            preview.CreateGrid(0, 0)
            font = preview.GetDefaultCellFont()
            if font.PointSize > 11:
                font.PointSize = 11
                preview.SetDefaultCellFont(font)
            preview.SetLabelFont(font)
            preview.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.tc_mouseclick_handler)
            self.preview = preview
            preview.SetDefaultCellBackgroundColour("#333333")
            preview.SetLabelBackgroundColour("#333333")
            hsizer.Add(preview, 1, wx.EXPAND)

            panel = p2

        if sys.platform not in ("darwin", "win32"):
            separator_color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
            separator = wx.Panel(panel, size=(-1, 1))
            separator.BackgroundColour = separator_color
            panel.Sizer.Add(separator, flag=wx.EXPAND)

        # status
        status = wx.StatusBar(self, -1)
        status.SetStatusStyles([wx.SB_FLAT])
        self.SetStatusBar(status)

        # layout
        if tc_use_alternate_preview:
            self.SetMinSize(
                (
                    self.GetMinSize()[0],
                    self.GetMinSize()[1] + splitter.SashSize + p2.sizer.MinSize[1],
                )
            )
        else:
            self.sizer.SetSizeHints(self)
            self.sizer.Layout()

        defaults.update(
            {
                "position.tcgen.x": self.GetDisplay().ClientArea[0] + 40,
                "position.tcgen.y": self.GetDisplay().ClientArea[1] + 60,
                "size.tcgen.w": self.ClientSize[0],
                "size.tcgen.h": self.ClientSize[1],
            }
        )

        if (
            hascfg("position.tcgen.x")
            and hascfg("position.tcgen.y")
            and hascfg("size.tcgen.w")
            and hascfg("size.tcgen.h")
        ):
            self.SetSaneGeometry(
                int(getcfg("position.tcgen.x")),
                int(getcfg("position.tcgen.y")),
                int(getcfg("size.tcgen.w")),
                int(getcfg("size.tcgen.h")),
            )
        else:
            self.Center()

        self.tc_size_handler()

        children = self.GetAllChildren()

        for child in children:
            if hasattr(child, "SetFont"):
                child.SetMaxFontSize(11)
            child.Bind(wx.EVT_KEY_DOWN, self.tc_key_handler)
            if (
                sys.platform == "win32"
                and sys.getwindowsversion() >= (6,)
                and isinstance(child, wx.Panel)
            ):
                # No need to enable double buffering under Linux and Mac OS X.
                # Under Windows, enabling double buffering on the panel seems
                # to work best to reduce flicker.
                child.SetDoubleBuffered(True)
        self.Bind(wx.EVT_MOVE, self.tc_move_handler)
        self.Bind(wx.EVT_SIZE, self.tc_size_handler, self)
        self.Bind(wx.EVT_MAXIMIZE, self.tc_size_handler, self)

        self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.tc_destroy_handler)

        self.tc_update_controls()
        self.tc_check()
        if path is not False:
            wx.CallAfter(self.tc_load_cfg_from_ti1, None, path)

    def csv_drop_handler(self, path):
        if self.worker.is_working():
            return
        if not self.tc_check_save_ti1():
            return
        self.worker.start(
            self.csv_convert_finish,
            self.csv_convert,
            wargs=(path,),
            progress_msg=lang.getstr("testchart.read"),
            parent=self,
            progress_start=500,
            cancelable=False,
            continue_next=True,
            show_remaining_time=False,
            fancy=False,
        )

    def csv_convert(self, path):
        # Read CSV file and get rows
        rows = []
        maxval = 100.0
        try:
            with open(path, "rb") as csvfile:
                sniffer = csv.Sniffer()
                rawcsv = csvfile.read()
                dialect = sniffer.sniff(rawcsv, delimiters=",;\t")
                has_header = sniffer.has_header(rawcsv)
                csvfile.seek(0)
                for i, row in enumerate(csv.reader(csvfile, dialect=dialect)):
                    if has_header:
                        continue
                    if len(row) == 3 or len(row) == 6:
                        # Add row number before first column
                        row.insert(0, i)
                    if len(row) not in (4, 7):
                        raise ValueError(lang.getstr("error.testchart.invalid", path))
                    row = [int(row[0])] + [float(v) for v in row[1:]]
                    for v in row[1:]:
                        if v > maxval:
                            maxval = v
                    rows.append(row)
        except Exception as exception:
            result = exception
        else:
            # Scale to 0..100 if actual value range is different
            if maxval > 100:
                for i, row in enumerate(rows):
                    rows[i][1:] = [v / maxval * 100 for v in row[1:]]
            # Create temporary TI1
            ti1 = CGATS.CGATS(
                """CTI1
KEYWORD "COLOR_REP"
COLOR_REP "RGB"
NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 4
BEGIN_DATA
END_DATA"""
            )
            # Add rows to TI1
            data = ti1[0].DATA
            for row in rows:
                if len(row) < 7:
                    # Missing XYZ, add via simple sRGB-like model
                    row.extend(
                        v * 100 for v in argyll_RGB2XYZ(*[v / 100.0 for v in row[1:]])
                    )
                data.add_data(row)
            # Create temp dir
            result = tmp = self.worker.create_tempdir()
        if not isinstance(result, Exception):
            # Write out temporary TI1
            ti1.filename = os.path.join(
                tmp, os.path.splitext(os.path.basename(path))[0] + ".ti1"
            )
            ti1.write()
            result = ti1
        return result

    def csv_convert_finish(self, result):
        if isinstance(result, Exception):
            show_result_dialog(result, self)
        else:
            self.tc_load_cfg_from_ti1(None, result.filename, resume=True)

    def precond_profile_drop_handler(self, path):
        self.tc_precond_profile.SetPath(path)
        self.tc_precond_profile_handler()

    def get_commands(self):
        return self.get_common_commands() + [
            "testchart-editor [filename | create filename]",
            "load <filename>",
        ]

    def process_data(self, data):
        if (
            data[0] == "testchart-editor"
            and (len(data) < 3 or (len(data) == 3 and data[1] == "create"))
        ) or (data[0] == "load" and len(data) == 2):
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
            elif len(data) == 3:
                # Create testchart
                wx.CallAfter(self.tc_preview_handler, path=data[2])
            return "ok"
        return "invalid"

    def ti1_drop_handler(self, path):
        self.tc_load_cfg_from_ti1(None, path)

    def resize_grid(self):
        num_cols = self.grid.GetNumberCols()
        if not num_cols or num_cols == 1:
            return
        grid_w = (
            self.grid.GetSize()[0]
            - self.grid.GetRowLabelSize()
            - self.grid.GetDefaultRowSize()
        )
        col_w = round(grid_w / (num_cols - 1))
        last_col_w = grid_w - col_w * (num_cols - 2)
        for i in range(num_cols):
            if i == 3:
                w = self.grid.GetDefaultRowSize()
            elif i == num_cols - 2:
                w = last_col_w - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
            else:
                w = col_w
            self.grid.SetColSize(i, w)
        self.grid.SetMargins(0 - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X), 0)
        self.grid.ForceRefresh()
        if hasattr(self, "preview"):
            num_cols = self.preview.GetNumberCols()
            if not num_cols:
                return
            grid_w = (
                self.preview.GetSize()[0]
                - self.preview.GetRowLabelSize()
                - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
            )
            col_w = round(grid_w / num_cols)
            for i in range(num_cols):
                self.preview.SetColSize(i, col_w)
            self.preview.SetMargins(
                0 - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X), 0
            )
            self.preview.ForceRefresh()

    def tc_grid_range_select_handler(self, event):
        if debug:
            print("[D] tc_grid_range_select_handler")
        if not self.grid.GetBatchCount():
            wx.CallAfter(self.tc_set_default_status)
        event.Skip()

    def tc_grid_label_left_click_handler(self, event):
        wx.CallAfter(self.tc_set_default_status)
        event.Skip()

    def tc_grid_label_left_dclick_handler(self, event):
        row, col = event.GetRow(), event.GetCol()
        if col == -1:  # row label clicked
            data = self.ti1.queryv1("DATA")
            wp = self.ti1.queryv1("APPROX_WHITE_POINT")
            if wp:
                wp = [float(v) for v in wp.split()]
                wp = [(v / wp[1]) * 100.0 for v in wp]
            else:
                wp = colormath.get_standard_illuminant("D65", scale=100)
            newdata = {
                "SAMPLE_ID": row + 2,
                "RGB_R": 100.0,
                "RGB_G": 100.0,
                "RGB_B": 100.0,
                "XYZ_X": wp[0],
                "XYZ_Y": 100.0,
                "XYZ_Z": wp[2],
            }
            self.tc_add_data(row, [newdata])
        event.Skip()

    def tc_key_handler(self, event):
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
        if debug:
            print(
                "[D] event.KeyCode",
                event.GetKeyCode(),
                "event.RawKeyCode",
                event.GetRawKeyCode(),
                "event.UniChar",
                event.GetUniChar(),
                "event.UnicodeKey",
                event.GetUnicodeKey(),
                "CTRL/CMD:",
                event.ControlDown() or event.CmdDown(),
                "ALT:",
                event.AltDown(),
                "SHIFT:",
                event.ShiftDown(),
            )
        if (
            event.ControlDown() or event.CmdDown()
        ):  # CTRL (Linux/Mac/Windows) / CMD (Mac)
            key = event.GetKeyCode()
            focus = self.FindFocus()
            if focus and self.grid in (
                focus,
                focus.GetParent(),
                focus.GetGrandParent(),
            ):
                if key in (8, 127):  # BACKSPACE / DEL
                    rows = self.grid.GetSelectionRows()
                    if (
                        rows
                        and len(rows)
                        and min(rows) >= 0
                        and max(rows) + 1 <= self.grid.GetNumberRows()
                    ):
                        if len(rows) == self.grid.GetNumberRows():
                            self.tc_check_save_ti1()
                        else:
                            self.tc_delete_rows(rows)
                        return
                elif key == 86 and self.grid.IsEditable():
                    # V
                    wx.CallAfter(self.tc_save_check)
            if key == 83:  # S
                if hasattr(self, "ti1"):
                    if (
                        event.ShiftDown()
                        or event.AltDown()
                        or not self.ti1.filename
                        or not os.path.exists(self.ti1.filename)
                    ):
                        self.tc_save_as_handler()
                    elif self.ti1.modified:
                        self.tc_save_handler(True)
                return
            else:
                event.Skip()
        else:
            event.Skip()

    def tc_sash_handler(self, event):
        if event.GetSashPosition() < self.sizer.GetMinSize()[1]:
            self.splitter.SetSashPosition(self.sizer.GetMinSize()[1])
        event.Skip()

    def tc_size_handler(self, event=None):
        wx.CallAfter(self.resize_grid)
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            w, h = self.ClientSize
            setcfg("size.tcgen.w", w)
            setcfg("size.tcgen.h", h)
        if event:
            event.Skip()

    def tc_sort_handler(self, event):
        idx = self.change_patch_order_ctrl.GetSelection()
        if idx == 0:
            self.ti1.sort_RGB_gray_to_top()
        elif idx == 1:
            self.ti1.sort_RGB_white_to_top()
        elif idx == 2:
            self.ti1.sort_RGB_to_top(1, 0, 0)  # Red
        elif idx == 3:
            self.ti1.sort_RGB_to_top(0, 1, 0)  # Green
        elif idx == 4:
            self.ti1.sort_RGB_to_top(0, 0, 1)  # Blue
        elif idx == 5:
            self.ti1.sort_RGB_to_top(0, 1, 1)  # Cyan
        elif idx == 6:
            self.ti1.sort_RGB_to_top(1, 0, 1)  # Magenta
        elif idx == 7:
            self.ti1.sort_RGB_to_top(1, 1, 0)  # Yellow
        elif idx == 8:
            self.ti1.sort_by_HSI()
        elif idx == 9:
            self.ti1.sort_by_HSL()
        elif idx == 10:
            self.ti1.sort_by_HSV()
        elif idx == 11:
            self.ti1.sort_by_L()
        elif idx == 12:
            self.ti1.sort_by_rec709_luma()
        elif idx == 13:
            self.ti1.sort_by_RGB()
        elif idx == 14:
            self.ti1.sort_by_RGB_sum()
        elif idx == 15:
            self.ti1.sort_by_BGR()
        elif idx == 16:
            # Minimize display response delay
            self.ti1.sort_by_BGR()
            self.ti1.sort_RGB_gray_to_top()
            self.ti1.sort_RGB_white_to_top()
        elif idx == 17:
            # Interleave
            self.ti1.checkerboard(None, None)
        elif idx == 18:
            # Shift & interleave
            self.ti1.checkerboard(None, None, split_grays=True, shift=True)
        elif idx == 19:
            # Maximize L* difference
            self.ti1.checkerboard(sort1=CGATS.stable_sort_by_L)
        elif idx == 20:
            # Maximize Rec. 709 luma difference
            self.ti1.checkerboard(CGATS.sort_by_rec709_luma)
        elif idx == 21:
            # Maximize RGB difference
            self.ti1.checkerboard(CGATS.sort_by_RGB_sum)
        elif idx == 22:
            # Vary RGB difference
            self.ti1.checkerboard(CGATS.sort_by_RGB, None, split_grays=True, shift=True)
        self.tc_clear(False)
        self.tc_preview(True)

    def tc_enable_sort_controls(self):
        enable = hasattr(self, "ti1")
        self.change_patch_order_ctrl.Enable(enable)
        self.change_patch_order_btn.Enable(enable)

    def tc_grid_cell_change_handler(self, event, save_check=True):
        data = self.ti1[0]["DATA"]
        sample = data[event.GetRow()]
        label = self.label_b2a.get(self.grid.GetColLabelValue(event.GetCol()))
        strval = "0" + self.grid.GetCellValue(event.GetRow(), event.GetCol()).replace(
            ",", "."
        )
        value_set = False
        try:
            value = float(strval)
            if value > 100:
                raise ValueError("RGB value %r%% is invalid" % value)
            elif value < 0:
                raise ValueError("Negative RGB value %r%% is invalid" % value)
        except ValueError:
            if not self.grid.GetBatchCount():
                wx.Bell()
            if label in list(self.ti1[0]["DATA_FORMAT"].values()):
                strval = str(sample[label])
                if "." in strval:
                    strval = strval.rstrip("0").rstrip(".")
            else:
                strval = ""
        else:
            if label in ("RGB_R", "RGB_G", "RGB_B"):
                sample[label] = value
                # If the same RGB combo is already in the ti1, use its XYZ
                # TODO: Implement proper lookup when using precond profile
                # This costs too much performance when updating multiple cells!
                # (e.g. paste operation from spreadsheet)
                # ref = data.queryi({"RGB_R": sample["RGB_R"],
                # "RGB_G": sample["RGB_G"],
                # "RGB_B": sample["RGB_B"]})
                # if ref:
                # for i in ref:
                # if ref[i] != sample:
                # ref = ref[i]
                # break
                # if "XYZ_X" in ref:
                # XYZ = [component / 100.0 for component in (ref["XYZ_X"], ref["XYZ_Y"], ref["XYZ_Z"])]
                # else:
                # Fall back to default D65-ish values
                XYZ = argyll_RGB2XYZ(
                    *[
                        component / 100.0
                        for component in (
                            sample["RGB_R"],
                            sample["RGB_G"],
                            sample["RGB_B"],
                        )
                    ]
                )
                sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"] = [
                    component * 100.0 for component in XYZ
                ]
                # FIXME: Should this be removed? There are no XYZ fields in the editor
                # for label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
                # for col in range(self.grid.GetNumberCols()):
                # if self.label_b2a.get(self.grid.GetColLabelValue(col)) == label:
                # self.grid.SetCellValue(event.GetRow(), col, str(round(sample[label], 4)))
                # value_set = True
            elif label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
                # FIXME: Should this be removed? There are no XYZ fields in the editor
                if value < 0:
                    value = 0.0
                sample[label] = value
                RGB = argyll_XYZ2RGB(
                    *[
                        component / 100.0
                        for component in (
                            sample["XYZ_X"],
                            sample["XYZ_Y"],
                            sample["XYZ_Z"],
                        )
                    ]
                )
                sample["RGB_R"], sample["RGB_G"], sample["RGB_B"] = [
                    component * 100.0 for component in RGB
                ]
                for label in ("RGB_R", "RGB_G", "RGB_B"):
                    for col in range(self.grid.GetNumberCols()):
                        if self.label_b2a.get(self.grid.GetColLabelValue(col)) == label:
                            self.grid.SetCellValue(
                                event.GetRow(), col, str(round(sample[label], 4))
                            )
                            value_set = True
            self.tc_grid_setcolorlabel(event.GetRow(), data)
            if not self.grid.GetBatchCount() and save_check:
                self.tc_save_check()
        if not value_set:
            self.grid.SetCellValue(
                event.GetRow(), event.GetCol(), re.sub(r"^0+(?!\.)", "", strval) or "0"
            )

    def tc_white_patches_handler(self, event=None):
        setcfg("tc_white_patches", self.tc_white_patches.GetValue())
        self.tc_check()
        if event:
            event.Skip()

    def tc_black_patches_handler(self, event=None):
        setcfg("tc_black_patches", self.tc_black_patches.GetValue())
        self.tc_check()
        if event:
            event.Skip()

    def tc_single_channel_patches_handler(self, event=None):
        if event:
            event.Skip()
            event = CustomEvent(event.GetEventType(), event.GetEventObject())
        if event and event.GetEventType() == wx.EVT_TEXT.evtType[0]:
            wx.CallLater(
                3000, self.tc_single_channel_patches_handler2, event
            )  # 3 seconds delay to allow user to finish keying in a value before it is validated
        else:
            wx.CallAfter(self.tc_single_channel_patches_handler2, event)

    def tc_single_channel_patches_handler2(self, event=None):
        if self.tc_single_channel_patches.GetValue() == 1:
            if (
                event
                and event.GetEventType() in (0, wx.EVT_SPINCTRL.evtType[0])
                and getcfg("tc_single_channel_patches") == 2
            ):  # decrease
                self.tc_single_channel_patches.SetValue(0)
            else:  # increase
                self.tc_single_channel_patches.SetValue(2)
        setcfg("tc_single_channel_patches", self.tc_single_channel_patches.GetValue())
        self.tc_check()

    def tc_gray_handler(self, event=None):
        if event:
            event.Skip()
            event = CustomEvent(event.GetEventType(), event.GetEventObject())
        if event and event.GetEventType() == wx.EVT_TEXT.evtType[0]:
            wx.CallLater(
                3000, self.tc_gray_handler2, event
            )  # 3 seconds delay to allow user to finish keying in a value before it is validated
        else:
            wx.CallAfter(self.tc_gray_handler2, event)

    def tc_gray_handler2(self, event=None):
        if self.tc_gray_patches.GetValue() == 1:
            if (
                event
                and event.GetEventType() in (0, wx.EVT_SPINCTRL.evtType[0])
                and getcfg("tc_gray_patches") == 2
            ):  # decrease
                self.tc_gray_patches.SetValue(0)
            else:  # increase
                self.tc_gray_patches.SetValue(2)
        setcfg("tc_gray_patches", self.tc_gray_patches.GetValue())
        self.tc_check()

    def tc_fullspread_handler(self, event=None):
        setcfg("tc_fullspread_patches", self.tc_fullspread_patches.GetValue())
        self.tc_algo_handler()
        self.tc_check()

    def tc_gamma_handler(self, event):
        setcfg("tc_gamma", self.tc_gamma_floatctrl.GetValue())

    def tc_get_total_patches(
        self,
        white_patches=None,
        black_patches=None,
        single_channel_patches=None,
        gray_patches=None,
        multi_steps=None,
        multi_bcc_steps=None,
        fullspread_patches=None,
    ):
        if (
            hasattr(self, "ti1")
            and [
                white_patches,
                black_patches,
                single_channel_patches,
                gray_patches,
                multi_steps,
                multi_bcc_steps,
                fullspread_patches,
            ]
            == [None] * 7
        ):
            return self.ti1.queryv1("NUMBER_OF_SETS")
        if white_patches is None:
            white_patches = self.tc_white_patches.GetValue()
        if black_patches is None:
            if self.worker.argyll_version >= [1, 6]:
                black_patches = self.tc_black_patches.GetValue()
            elif hasattr(self, "ti1"):
                black_patches = self.ti1.queryv1("BLACK_COLOR_PATCHES")
        if single_channel_patches is None:
            single_channel_patches = self.tc_single_channel_patches.GetValue()
        single_channel_patches_total = single_channel_patches * 3
        if gray_patches is None:
            gray_patches = self.tc_gray_patches.GetValue()
        if (
            gray_patches == 0
            and (single_channel_patches > 0 or black_patches > 0)
            and white_patches > 0
        ):
            gray_patches = 2
        if multi_steps is None:
            multi_steps = self.tc_multi_steps.GetValue()
        if (
            multi_bcc_steps is None
            and getcfg("tc_multi_bcc")
            and self.worker.argyll_version >= [1, 6]
        ):
            multi_bcc_steps = self.tc_multi_steps.GetValue()
        if fullspread_patches is None:
            fullspread_patches = self.tc_fullspread_patches.GetValue()
        return get_total_patches(
            white_patches,
            black_patches,
            single_channel_patches,
            gray_patches,
            multi_steps,
            multi_bcc_steps,
            fullspread_patches,
        )

    def tc_get_black_patches(self):
        if self.worker.argyll_version >= [1, 6]:
            black_patches = self.tc_black_patches.GetValue()
        else:
            black_patches = 0
        single_channel_patches = self.tc_single_channel_patches.GetValue()
        gray_patches = self.tc_gray_patches.GetValue()
        if gray_patches == 0 and single_channel_patches > 0 and black_patches > 0:
            gray_patches = 2
        multi_steps = self.tc_multi_steps.GetValue()
        if (
            multi_steps > 1 or gray_patches > 1
        ):  # black always in multi channel or gray patches
            black_patches -= 1
        return max(0, black_patches)

    def tc_get_white_patches(self):
        white_patches = self.tc_white_patches.GetValue()
        single_channel_patches = self.tc_single_channel_patches.GetValue()
        gray_patches = self.tc_gray_patches.GetValue()
        if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
            gray_patches = 2
        multi_steps = self.tc_multi_steps.GetValue()
        if (
            multi_steps > 1 or gray_patches > 1
        ):  # white always in multi channel or gray patches
            white_patches -= 1
        return max(0, white_patches)

    def tc_multi_steps_handler(self, event=None):
        if event:
            event.Skip()
            event = CustomEvent(event.GetEventType(), event.GetEventObject())
        if event and event.GetEventType() == wx.EVT_TEXT.evtType[0]:
            wx.CallLater(
                3000, self.tc_multi_steps_handler2, event
            )  # 3 seconds delay to allow user to finish keying in a value before it is validated
        else:
            wx.CallAfter(self.tc_multi_steps_handler2, event)

    def tc_multi_steps_handler2(self, event=None):
        if self.tc_multi_steps.GetValue() == 1:
            if (
                event
                and event.GetEventType() in (0, wx.EVT_SPINCTRL.evtType[0])
                and getcfg("tc_multi_steps") == 2
            ):  # decrease
                self.tc_multi_steps.SetValue(0)
            else:  # increase
                self.tc_multi_steps.SetValue(2)
        multi_steps = self.tc_multi_steps.GetValue()
        multi_patches = int(math.pow(multi_steps, 3))
        if getcfg("tc_multi_bcc") and self.worker.argyll_version >= [1, 6]:
            pref = "tc_multi_bcc_steps"
            if multi_steps:
                multi_patches += int(math.pow(multi_steps - 1, 3))
                multi_steps += multi_steps - 1
            setcfg("tc_multi_steps", self.tc_multi_steps.GetValue())
        else:
            pref = "tc_multi_steps"
            setcfg("tc_multi_bcc_steps", 0)
        self.tc_multi_patches.SetLabel(
            lang.getstr("tc.multidim.patches", (multi_patches, multi_steps))
        )
        setcfg(pref, self.tc_multi_steps.GetValue())
        self.tc_check()

    def tc_neutral_axis_emphasis_handler(self, event=None):
        if event.GetId() == self.tc_neutral_axis_emphasis_slider.GetId():
            self.tc_neutral_axis_emphasis_intctrl.SetValue(
                self.tc_neutral_axis_emphasis_slider.GetValue()
            )
        else:
            self.tc_neutral_axis_emphasis_slider.SetValue(
                self.tc_neutral_axis_emphasis_intctrl.GetValue()
            )
        setcfg(
            "tc_neutral_axis_emphasis",
            self.tc_neutral_axis_emphasis_intctrl.GetValue() / 100.0,
        )
        self.tc_algo_handler()

    def tc_dark_emphasis_handler(self, event=None):
        if event.GetId() == self.tc_dark_emphasis_slider.GetId():
            self.tc_dark_emphasis_intctrl.SetValue(
                self.tc_dark_emphasis_slider.GetValue()
            )
        else:
            self.tc_dark_emphasis_slider.SetValue(
                self.tc_dark_emphasis_intctrl.GetValue()
            )
        setcfg("tc_dark_emphasis", self.tc_dark_emphasis_intctrl.GetValue() / 100.0)
        self.tc_algo_handler()

    def tc_algo_handler(self, event=None):
        tc_algo_enable = self.tc_fullspread_patches.GetValue() > 0
        self.tc_algo.Enable(tc_algo_enable)
        tc_algo = self.tc_algos_ba[self.tc_algo.GetStringSelection()]
        self.tc_adaption_slider.Enable(tc_algo_enable and tc_algo == "")
        self.tc_adaption_intctrl.Enable(tc_algo_enable and tc_algo == "")
        tc_precond_enable = tc_algo in ("I", "Q", "R", "t") or (
            tc_algo == "" and self.tc_adaption_slider.GetValue() > 0
        )
        if self.worker.argyll_version >= [1, 3, 3]:
            self.tc_neutral_axis_emphasis_slider.Enable(
                tc_algo_enable and tc_precond_enable
            )
            self.tc_neutral_axis_emphasis_intctrl.Enable(
                tc_algo_enable and tc_precond_enable
            )
        self.tc_precond.Enable(bool(getcfg("tc_precond_profile")))
        if not getcfg("tc_precond_profile"):
            self.tc_precond.SetValue(False)
        else:
            self.tc_precond.SetValue(bool(int(getcfg("tc_precond"))))
        if self.worker.argyll_version >= [1, 6, 2]:
            tc_dark_emphasis_enable = self.worker.argyll_version >= [1, 6, 3] or (
                tc_precond_enable
                and bool(int(getcfg("tc_precond")))
                and bool(getcfg("tc_precond_profile"))
            )
            self.tc_dark_emphasis_slider.Enable(tc_dark_emphasis_enable)
            self.tc_dark_emphasis_intctrl.Enable(tc_dark_emphasis_enable)
        self.tc_angle_slider.Enable(tc_algo_enable and tc_algo in ("i", "I"))
        self.tc_angle_intctrl.Enable(tc_algo_enable and tc_algo in ("i", "I"))
        setcfg("tc_algo", tc_algo)
        self.tc_enable_add_precond_controls()

    def tc_enable_add_precond_controls(self):
        tc_algo = getcfg("tc_algo")
        add_preconditioned_enable = hasattr(self, "ti1") and bool(
            getcfg("tc_precond_profile")
        )
        self.saturation_sweeps_intctrl.Enable(add_preconditioned_enable)
        for color in ("R", "G", "B", "C", "M", "Y"):
            getattr(self, "saturation_sweeps_%s_btn" % color).Enable(
                add_preconditioned_enable
            )
        RGB = {}
        for component in ("R", "G", "B"):
            ctrl = getattr(self, "saturation_sweeps_custom_%s_ctrl" % component)
            ctrl.Enable(add_preconditioned_enable)
            RGB[component] = ctrl.GetValue()
        self.saturation_sweeps_custom_btn.Enable(
            add_preconditioned_enable and not (RGB["R"] == RGB["G"] == RGB["B"])
        )
        self.add_ti3_btn.Enable(add_preconditioned_enable)
        self.add_ti3_relative_cb.Enable(add_preconditioned_enable)

    def tc_adaption_handler(self, event=None):
        if event.GetId() == self.tc_adaption_slider.GetId():
            self.tc_adaption_intctrl.SetValue(self.tc_adaption_slider.GetValue())
        else:
            self.tc_adaption_slider.SetValue(self.tc_adaption_intctrl.GetValue())
        setcfg("tc_adaption", self.tc_adaption_intctrl.GetValue() / 100.0)
        self.tc_algo_handler()

    def tc_add_saturation_sweeps_handler(self, event):
        try:
            profile = ICCP.ICCProfile(getcfg("tc_precond_profile"))
        except (IOError, ICCP.ICCProfileInvalidError) as exception:
            show_result_dialog(exception, self)
        else:
            rgb_space = profile.get_rgb_space()
            if not rgb_space:
                show_result_dialog(
                    Error(
                        lang.getstr(
                            "profile.required_tags_missing",
                            lang.getstr("profile.type.shaper_matrix"),
                        )
                    ),
                    self,
                )
                return
            R, G, B = {
                self.saturation_sweeps_R_btn.GetId(): (1, 0, 0),
                self.saturation_sweeps_G_btn.GetId(): (0, 1, 0),
                self.saturation_sweeps_B_btn.GetId(): (0, 0, 1),
                self.saturation_sweeps_C_btn.GetId(): (0, 1, 1),
                self.saturation_sweeps_M_btn.GetId(): (1, 0, 1),
                self.saturation_sweeps_Y_btn.GetId(): (1, 1, 0),
                self.saturation_sweeps_custom_btn.GetId(): (
                    self.saturation_sweeps_custom_R_ctrl.GetValue() / 100.0,
                    self.saturation_sweeps_custom_G_ctrl.GetValue() / 100.0,
                    self.saturation_sweeps_custom_B_ctrl.GetValue() / 100.0,
                ),
            }[event.GetId()]
            maxv = self.saturation_sweeps_intctrl.GetValue()
            newdata = []
            rows = self.grid.GetSelectionRows()
            if rows:
                row = rows[-1]
            else:
                row = self.grid.GetNumberRows() - 1
            for i in range(maxv):
                saturation = 1.0 / (maxv - 1) * i
                RGB, xyY = colormath.RGBsaturation(
                    R, G, B, 1.0 / (maxv - 1) * i, rgb_space
                )
                X, Y, Z = colormath.xyY2XYZ(*xyY)
                newdata.append(
                    {
                        "SAMPLE_ID": row + 2,
                        "RGB_R": round(RGB[0] * 100, 4),
                        "RGB_G": round(RGB[1] * 100, 4),
                        "RGB_B": round(RGB[2] * 100, 4),
                        "XYZ_X": X * 100,
                        "XYZ_Y": Y * 100,
                        "XYZ_Z": Z * 100,
                    }
                )
            self.tc_add_data(row, newdata)
            self.grid.select_row(row + len(newdata))

    def tc_drop_ti3_handler(self, path):
        if not hasattr(self, "ti1"):
            wx.Bell()
        elif getcfg("tc_precond_profile"):
            self.tc_add_ti3_handler(None, path)
        else:
            show_result_dialog(lang.getstr("tc.precond.notset"), self)

    def tc_add_ti3_handler(self, event, chart=None):
        try:
            profile = ICCP.ICCProfile(getcfg("tc_precond_profile"))
        except (IOError, ICCP.ICCProfileInvalidError) as exception:
            show_result_dialog(exception, self)
            return

        if not chart:
            defaultDir, defaultFile = get_verified_path("testchart.reference")
            dlg = wx.FileDialog(
                self,
                lang.getstr("testchart_or_reference"),
                defaultDir=defaultDir,
                defaultFile=defaultFile,
                wildcard=(
                    lang.getstr("filetype.ti1_ti3_txt")
                    + "|*.cgats;*.cie;*.gam;*.icc;*.icm;*.jpg;*.jpeg;*.png;*.ti1;*.ti2;*.ti3;*.tif;*.tiff;*.txt"
                ),
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            dlg.Center(wx.BOTH)
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                chart = dlg.GetPath()
                setcfg("testchart.reference", chart)
            dlg.Destroy()
            if result != wx.ID_OK:
                return

        use_gamut = False

        # Determine if this is an image
        filename, ext = os.path.splitext(chart)
        if ext.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            llevel = wx.Log.GetLogLevel()
            wx.Log.SetLogLevel(0)  # Suppress TIFF library related message popups
            try:
                img = wx.Image(chart, wx.BITMAP_TYPE_ANY)
                if not img.IsOk():
                    raise Error(lang.getstr("error.file_type_unsupported"))
            except Exception as exception:
                show_result_dialog(exception, self)
                return
            finally:
                wx.Log.SetLogLevel(llevel)
            if test:
                dlg = ConfirmDialog(
                    self,
                    title=lang.getstr("testchart.add_ti3_patches"),
                    msg=lang.getstr("gamut"),
                    ok="L*a*b*",
                    alt="RGB",
                    bitmap=geticon(32, appname + "-testchart-editor"),
                )
                result = dlg.ShowModal()
                if result == wx.ID_CANCEL:
                    return
                use_gamut = result == wx.ID_OK
        else:
            img = None
            if ext.lower() in (".icc", ".icm"):
                try:
                    nclprof = ICCP.ICCProfile(chart)
                    if (
                        nclprof.profileClass != "nmcl"
                        or "ncl2" not in nclprof.tags
                        or not isinstance(nclprof.tags.ncl2, ICCP.NamedColor2Type)
                        or nclprof.connectionColorSpace not in ("Lab", "XYZ")
                    ):
                        raise Error(lang.getstr("profile.only_named_color"))
                except Exception as exception:
                    show_result_dialog(exception, self)
                    return
                if nclprof.connectionColorSpace == "Lab":
                    data_format = "LAB_L LAB_A LAB_B"
                else:
                    data_format = " XYZ_X XYZ_Y XYZ_Z"
                chart = [
                    "GAMUT  ",
                    "BEGIN_DATA_FORMAT",
                    data_format,
                    "END_DATA_FORMAT",
                    "BEGIN_DATA",
                    "END_DATA",
                ]
                if "wtpt" in nclprof.tags:
                    chart.insert(1, 'KEYWORD "APPROX_WHITE_POINT"')
                    chart.insert(
                        2,
                        'APPROX_WHITE_POINT "%.4f %.4f %.4f"'
                        % tuple(v * 100 for v in list(nclprof.tags.wtpt.ir.values())),
                    )
                for k in nclprof.tags.ncl2:
                    v = nclprof.tags.ncl2[k]
                    chart.insert(-1, "%.4f %.4f %.4f" % tuple(v.pcs.values()))
                chart = "\n".join(chart)

        self.worker.start(
            self.tc_add_ti3_consumer,
            self.tc_add_ti3,
            cargs=(profile,),
            wargs=(chart, img, use_gamut, profile),
            wkwargs={},
            progress_msg=lang.getstr("testchart.add_ti3_patches"),
            parent=self,
            progress_start=500,
            fancy=False,
        )

    def tc_add_ti3_consumer(self, result, profile=None):
        if isinstance(result, Exception):
            show_result_dialog(result, self)
        else:
            chart = result
            data_format = list(chart.queryv1("DATA_FORMAT").values())
            if getcfg("tc_add_ti3_relative"):
                intent = "r"
            else:
                intent = "a"
            if not (
                chart[0].type.strip() == "GAMUT"
                and "RGB_R" in data_format
                and "RGB_G" in data_format
                and "RGB_B" in data_format
            ):
                as_ti3 = (
                    "LAB_L" in data_format
                    and "LAB_A" in data_format
                    and "LAB_B" in data_format
                ) or (
                    "XYZ_X" in data_format
                    and "XYZ_Y" in data_format
                    and "XYZ_Z" in data_format
                )
                if getcfg("tc_add_ti3_relative"):
                    adapted = chart.adapt()
                ti1, ti3, void = self.worker.chart_lookup(
                    chart, profile, as_ti3, intent=intent, white_patches=False
                )
                if not ti1 or not ti3:
                    return
                if as_ti3:
                    chart = ti1
                else:
                    chart = ti3
            dataset = chart.queryi1("DATA")
            data_format = list(dataset.queryv1("DATA_FORMAT").values())
            # Returned CIE values are always either XYZ or Lab
            if (
                "LAB_L" in data_format
                and "LAB_A" in data_format
                and "LAB_B" in data_format
            ):
                cie = "Lab"
            else:
                cie = "XYZ"
            newdata = []
            rows = self.grid.GetSelectionRows()
            if rows:
                row = rows[-1]
            else:
                row = self.grid.GetNumberRows() - 1
            for i in dataset.DATA:
                if cie == "Lab":
                    (
                        dataset.DATA[i]["XYZ_X"],
                        dataset.DATA[i]["XYZ_Y"],
                        dataset.DATA[i]["XYZ_Z"],
                    ) = colormath.Lab2XYZ(
                        dataset.DATA[i]["LAB_L"],
                        dataset.DATA[i]["LAB_A"],
                        dataset.DATA[i]["LAB_B"],
                        scale=100,
                    )
                if intent == "r":
                    (
                        dataset.DATA[i]["XYZ_X"],
                        dataset.DATA[i]["XYZ_Y"],
                        dataset.DATA[i]["XYZ_Z"],
                    ) = colormath.adapt(
                        dataset.DATA[i]["XYZ_X"],
                        dataset.DATA[i]["XYZ_Y"],
                        dataset.DATA[i]["XYZ_Z"],
                        "D50",
                        list(profile.tags.wtpt.values()),
                    )
                entry = {"SAMPLE_ID": row + 2 + i}
                for label in ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"):
                    entry[label] = round(dataset.DATA[i][label], 4)
                newdata.append(entry)
            self.tc_add_data(row, newdata)
            self.grid.select_row(row + len(newdata))

    def tc_add_ti3(self, chart, img=None, use_gamut=True, profile=None):
        if img:
            cwd = self.worker.create_tempdir()
            if isinstance(cwd, Exception):
                return cwd
            size = 70.0
            scale = math.sqrt((img.Width * img.Height) / (size * size))
            w, h = int(round(img.Width / scale)), int(round(img.Height / scale))
            loresimg = img.Scale(w, h, wx.IMAGE_QUALITY_NORMAL)
            if loresimg.CountColours() < img.CountColours(size * size):
                # Assume a photo
                quality = wx.IMAGE_QUALITY_HIGH
            else:
                # Assume a target
                quality = wx.IMAGE_QUALITY_NORMAL
            ext = os.path.splitext(chart)[1]
            if ext.lower() in (".tif", ".tiff") or (
                self.worker.argyll_version >= [1, 4]
                and ext.lower() in (".jpeg", ".jpg")
            ):
                imgpath = chart
            else:
                imgpath = os.path.join(cwd, "image.tif")
                img.SaveFile(imgpath, wx.BITMAP_TYPE_TIF)
            outpath = os.path.join(cwd, "imageout.tif")
            # Process image to get colors
            # Two ways to do this: Convert image using cctiff
            # or use tiffgamut
            # In both cases, a profile embedded in the image will be used
            # with the preconditioning profile as fallback if there is no
            # image profile
            if not use_gamut:
                # Use cctiff
                cmdname = "cctiff"
            else:
                # Use tiffgamut
                cmdname = "tiffgamut"
                gam = os.path.join(cwd, "image.gam")
            cmd = get_argyll_util(cmdname)
            if cmd:
                ppath = getcfg("tc_precond_profile")
                intent = "r" if getcfg("tc_add_ti3_relative") else "a"
                for n in range(2 if ppath else 1):
                    if use_gamut:
                        res = 10 if imgpath == chart else 1
                        args = ["-d%s" % res, "-O", gam]
                    # if self.worker.argyll_version >= [1, 0, 4]:
                    # args.append("-f100")
                    else:
                        args = ["-a"]
                        if self.worker.argyll_version >= [1, 4]:
                            # Always save as TIFF
                            args.append("-fT")
                        elif self.worker.argyll_version >= [1, 1]:
                            # TIFF photometric encoding 1..n
                            args.append("-t1")
                        else:
                            # TIFF photometric encoding 1..n
                            args.append("-e1")
                    args.append("-i%s" % intent)
                    if n == 0:
                        # Try to use embedded profile
                        args.append(imgpath)
                        if not use_gamut:
                            # Target
                            args.append("-i%s" % intent)
                            args.append(ppath)
                    else:
                        # Fall back to preconditioning profile
                        args.append(ppath)
                    args.append(imgpath)
                    if not use_gamut:
                        args.append(outpath)
                    result = self.worker.exec_cmd(
                        cmd, ["-v"] + args, capture_output=True, skip_scripts=True
                    )
                    if not result:
                        errors = "".join(self.worker.errors)
                        if (
                            "Error - Can't open profile in file" in errors
                            or "Error - Can't read profile" in errors
                        ):
                            # Try again?
                            continue
                    break
                if isinstance(result, Exception) or not result:
                    self.worker.wrapup(False)
                if isinstance(result, Exception):
                    return result
                elif result:
                    if use_gamut:
                        chart = gam
                    else:
                        last_output_space = None
                        for line in self.worker.output:
                            if line.startswith("Output space ="):
                                last_output_space = line.split("=")[1].strip()
                        if last_output_space == "RGB":
                            chart = outpath
                        else:
                            chart = imgpath
                else:
                    return Error("\n".join(self.worker.errors or self.worker.output))
            else:
                return Error(lang.getstr("argyll.util.not_found", cmdname))

            if not use_gamut:
                llevel = wx.Log.GetLogLevel()
                wx.Log.SetLogLevel(0)  # Suppress TIFF library related message popups
                try:
                    img = wx.Image(chart, wx.BITMAP_TYPE_ANY)
                    if not img.IsOk():
                        raise Error(lang.getstr("error.file_type_unsupported"))
                except Exception as exception:
                    return exception
                finally:
                    wx.Log.SetLogLevel(llevel)
                    self.worker.wrapup(False)
                if img.Width != w or img.Height != h:
                    img.Rescale(w, h, quality)
                # Select RGB colors and fill chart
                chart = [
                    "TI1    ",
                    "BEGIN_DATA_FORMAT",
                    "RGB_R RGB_G RGB_B",
                    "END_DATA_FORMAT",
                    "BEGIN_DATA",
                    "END_DATA",
                ]
                for y in range(h):
                    for x in range(w):
                        R, G, B = (
                            img.GetRed(x, y) / 2.55,
                            img.GetGreen(x, y) / 2.55,
                            img.GetBlue(x, y) / 2.55,
                        )
                        chart.insert(-1, "%.4f %.4f %.4f" % (R, G, B))
                chart = "\n".join(chart)

        try:
            chart = CGATS.CGATS(chart)
            if not chart.queryv1("DATA_FORMAT"):
                raise CGATS.CGATSError(
                    lang.getstr(
                        "error.testchart.missing_fields",
                        (chart.filename, "DATA_FORMAT"),
                    )
                )
        except (IOError, CGATS.CGATSError) as exception:
            return exception
        finally:
            path = None
            if isinstance(chart, CGATS.CGATS):
                if chart.filename:
                    path = chart.filename
            elif os.path.isfile(chart):
                path = chart
            if path and os.path.dirname(path) == self.worker.tempdir:
                self.worker.wrapup(False)
        if img:
            if use_gamut:
                threshold = 2
            else:
                threshold = 4
                try:
                    void, ti3, void = self.worker.chart_lookup(
                        chart,
                        profile,
                        intent=intent,
                        white_patches=False,
                        raise_exceptions=True,
                    )
                except Exception as exception:
                    return exception
                if ti3:
                    chart = ti3
                else:
                    return Error(
                        lang.getstr("error.generic", (-1, lang.getstr("unknown")))
                    )
            colorsets = dict()
            weights = {}
            demph = getcfg("tc_dark_emphasis")
            # Select Lab color
            data = chart.queryv1("DATA")
            for sample in data.values():
                if not use_gamut:
                    RGB = sample["RGB_R"], sample["RGB_G"], sample["RGB_B"]
                L, a, b = (sample["LAB_L"], sample["LAB_A"], sample["LAB_B"])
                color = round(L / 10), round(a / 15), round(b / 15)
                if color not in colorsets:
                    weights[color] = 0
                    colorsets[color] = []
                if L >= 50:
                    weights[color] += L / 50 - demph
                else:
                    weights[color] += L / 50 + demph
                colorsets[color].append((L, a, b))
                if not use_gamut:
                    colorsets[color][-1] += RGB
            # Fill chart
            data_format = "LAB_L LAB_A LAB_B"
            if not use_gamut:
                data_format += " RGB_R RGB_G RGB_B"
            chart = [
                "GAMUT  ",
                "BEGIN_DATA_FORMAT",
                data_format,
                "END_DATA_FORMAT",
                "BEGIN_DATA",
                "END_DATA",
            ]
            weight = bool(
                [
                    color
                    for color in iter(colorsets.keys())
                    if weights[color] >= threshold
                ]
            )
            for color in colorsets:
                colors = colorsets[color]
                if weight and weights[color] < threshold:
                    continue
                L, a, b = 0, 0, 0
                R, G, B = 0, 0, 0
                for v in colors:
                    L += v[0]
                    a += v[1]
                    b += v[2]
                    if len(v) == 6:
                        R += v[3]
                        G += v[4]
                        B += v[5]
                L /= len(colors)
                a /= len(colors)
                b /= len(colors)
                R /= len(colors)
                G /= len(colors)
                B /= len(colors)
                chart.insert(-1, "%.4f %.4f %.4f" % (L, a, b))
                if not use_gamut:
                    chart[-2] += " %.4f %.4f %.4f" % (R, G, B)

            chart = CGATS.CGATS("\n".join(chart))
        else:
            chart.fix_device_values_scaling()

        return chart

    def tc_add_ti3_relative_handler(self, event):
        setcfg("tc_add_ti3_relative", int(self.add_ti3_relative_cb.GetValue()))

    def tc_angle_handler(self, event=None):
        if event.GetId() == self.tc_angle_slider.GetId():
            self.tc_angle_intctrl.SetValue(self.tc_angle_slider.GetValue())
        else:
            self.tc_angle_slider.SetValue(self.tc_angle_intctrl.GetValue())
        setcfg("tc_angle", self.tc_angle_intctrl.GetValue() / 10000.0)

    def tc_multi_bcc_cb_handler(self, event=None):
        setcfg("tc_multi_bcc", int(self.tc_multi_bcc_cb.GetValue()))
        self.tc_multi_steps_handler2()

    def tc_precond_handler(self, event=None):
        setcfg("tc_precond", int(self.tc_precond.GetValue()))
        self.tc_adaption_slider.SetValue(
            int((1 if getcfg("tc_precond") else defaults["tc_adaption"]) * 100)
        )
        self.tc_adaption_handler(self.tc_adaption_slider)
        self.tc_algo_handler()

    def tc_precond_profile_handler(self, event=None):
        tc_precond_enable = bool(self.tc_precond_profile.GetPath())
        self.tc_precond.Enable(tc_precond_enable)
        setcfg("tc_precond_profile", self.tc_precond_profile.GetPath())
        self.tc_algo_handler()

    def tc_precond_profile_current_ctrl_handler(self, event):
        profile_path = get_current_profile_path(True, True)
        if profile_path:
            self.tc_precond_profile.SetPath(profile_path)
            self.tc_precond_profile_handler()
        else:
            show_result_dialog(
                Error(
                    lang.getstr(
                        "display_profile.not_detected", get_display_name(None, True)
                    )
                ),
                self,
            )

    def tc_filter_handler(self, event=None):
        setcfg("tc_filter", int(self.tc_filter.GetValue()))
        setcfg("tc_filter_L", self.tc_filter_L.GetValue())
        setcfg("tc_filter_a", self.tc_filter_a.GetValue())
        setcfg("tc_filter_b", self.tc_filter_b.GetValue())
        setcfg("tc_filter_rad", self.tc_filter_rad.GetValue())

    def tc_vrml_black_offset_ctrl_handler(self, event):
        setcfg("tc_vrml_black_offset", self.tc_vrml_black_offset_intctrl.GetValue())

    def tc_vrml_compress_handler(self, event):
        setcfg("vrml.compress", int(self.tc_vrml_compress_cb.GetValue()))

    def tc_vrml_handler(self, event=None):
        d = self.tc_vrml_device.GetValue()
        l = self.tc_vrml_cie.GetValue()
        if event:
            setcfg("tc_vrml_device", int(d))
            setcfg("tc_vrml_cie", int(l))
            setcfg(
                "tc_vrml_cie_colorspace",
                self.tc_vrml_cie_colorspace_ctrl.GetStringSelection(),
            )
            setcfg(
                "tc_vrml_device_colorspace",
                self.tc_vrml_device_colorspace_ctrl.GetStringSelection(),
            )
        self.vrml_save_as_btn.Enable(hasattr(self, "ti1") and (d or l))
        self.view_3d_format_btn.Enable(hasattr(self, "ti1") and (d or l))

    def tc_vrml_use_D50_handler(self, event):
        setcfg("tc_vrml_use_D50", int(self.tc_vrml_use_D50_cb.GetValue()))

    def tc_update_controls(self):
        self.tc_algo.SetStringSelection(
            self.tc_algos_ab.get(
                getcfg("tc_algo"), self.tc_algos_ab.get(defaults["tc_algo"])
            )
        )
        self.tc_white_patches.SetValue(getcfg("tc_white_patches"))
        if self.worker.argyll_version >= [1, 6]:
            self.tc_black_patches.SetValue(getcfg("tc_black_patches"))
        self.tc_single_channel_patches.SetValue(getcfg("tc_single_channel_patches"))
        self.tc_gray_patches.SetValue(getcfg("tc_gray_patches"))
        if getcfg("tc_multi_bcc_steps"):
            setcfg("tc_multi_bcc", 1)
            self.tc_multi_steps.SetValue(getcfg("tc_multi_bcc_steps"))
        else:
            setcfg("tc_multi_bcc", 0)
            self.tc_multi_steps.SetValue(getcfg("tc_multi_steps"))
        if hasattr(self, "tc_multi_bcc_cb"):
            self.tc_multi_bcc_cb.SetValue(bool(getcfg("tc_multi_bcc")))
        self.tc_multi_steps_handler2()
        self.tc_fullspread_patches.SetValue(getcfg("tc_fullspread_patches"))
        self.tc_angle_slider.SetValue(int(getcfg("tc_angle") * 10000))
        self.tc_angle_handler(self.tc_angle_slider)
        self.tc_adaption_slider.SetValue(int(getcfg("tc_adaption") * 100))
        self.tc_adaption_handler(self.tc_adaption_slider)
        if self.worker.argyll_version == [
            1,
            1,
            "RC2",
        ] or self.worker.argyll_version >= [1, 1]:
            self.tc_gamma_floatctrl.SetValue(getcfg("tc_gamma"))
        if self.worker.argyll_version >= [1, 3, 3]:
            self.tc_neutral_axis_emphasis_slider.SetValue(
                int(getcfg("tc_neutral_axis_emphasis") * 100)
            )
            self.tc_neutral_axis_emphasis_handler(self.tc_neutral_axis_emphasis_slider)
        if self.worker.argyll_version >= [1, 6, 2]:
            self.tc_dark_emphasis_slider.SetValue(int(getcfg("tc_dark_emphasis") * 100))
            self.tc_dark_emphasis_handler(self.tc_dark_emphasis_slider)
        self.tc_precond_profile.SetPath(getcfg("tc_precond_profile"))
        self.tc_filter.SetValue(bool(int(getcfg("tc_filter"))))
        self.tc_filter_L.SetValue(getcfg("tc_filter_L"))
        self.tc_filter_a.SetValue(getcfg("tc_filter_a"))
        self.tc_filter_b.SetValue(getcfg("tc_filter_b"))
        self.tc_filter_rad.SetValue(getcfg("tc_filter_rad"))
        self.tc_vrml_cie.SetValue(bool(int(getcfg("tc_vrml_cie"))))
        self.tc_vrml_cie_colorspace_ctrl.SetSelection(
            config.valid_values["tc_vrml_cie_colorspace"].index(
                getcfg("tc_vrml_cie_colorspace")
            )
        )
        self.tc_vrml_device_colorspace_ctrl.SetSelection(
            config.valid_values["tc_vrml_device_colorspace"].index(
                getcfg("tc_vrml_device_colorspace")
            )
        )
        self.tc_vrml_device.SetValue(bool(int(getcfg("tc_vrml_device"))))
        self.tc_vrml_black_offset_intctrl.SetValue(getcfg("tc_vrml_black_offset"))
        self.tc_vrml_use_D50_cb.SetValue(bool(getcfg("tc_vrml_use_D50")))
        self.tc_vrml_handler()
        self.tc_vrml_compress_cb.SetValue(bool(getcfg("vrml.compress")))
        self.add_ti3_relative_cb.SetValue(bool(getcfg("tc_add_ti3_relative")))
        self.tc_enable_sort_controls()

    def tc_check(self, event=None):
        white_patches = self.tc_white_patches.GetValue()
        self.tc_amount = self.tc_get_total_patches(white_patches)
        self.preview_btn.Enable(
            self.tc_amount
            - max(0, self.tc_get_white_patches())
            - max(0, self.tc_get_black_patches())
            >= 8
        )
        self.clear_btn.Enable(hasattr(self, "ti1"))
        self.tc_save_check()
        self.save_as_btn.Enable(hasattr(self, "ti1"))
        self.export_btn.Enable(hasattr(self, "ti1"))
        self.tc_vrml_handler()
        self.tc_enable_add_precond_controls()
        self.tc_enable_sort_controls()
        self.tc_set_default_status()

    def tc_save_check(self):
        self.save_btn.Enable(
            hasattr(self, "ti1")
            and self.ti1.modified
            and bool(self.ti1.filename)
            and os.path.exists(self.ti1.filename)
            and get_data_path(os.path.join("ref", os.path.basename(self.ti1.filename)))
            != self.ti1.filename
            and get_data_path(os.path.join("ti1", os.path.basename(self.ti1.filename)))
            != self.ti1.filename
        )

    def tc_save_cfg(self):
        setcfg("tc_white_patches", self.tc_white_patches.GetValue())
        if self.worker.argyll_version >= [1, 6]:
            setcfg("tc_black_patches", self.tc_black_patches.GetValue())
        setcfg("tc_single_channel_patches", self.tc_single_channel_patches.GetValue())
        setcfg("tc_gray_patches", self.tc_gray_patches.GetValue())
        setcfg("tc_multi_steps", self.tc_multi_steps.GetValue())
        setcfg("tc_fullspread_patches", self.tc_fullspread_patches.GetValue())
        tc_algo = self.tc_algos_ba[self.tc_algo.GetStringSelection()]
        setcfg("tc_algo", tc_algo)
        setcfg("tc_angle", self.tc_angle_intctrl.GetValue() / 10000.0)
        setcfg("tc_adaption", self.tc_adaption_intctrl.GetValue() / 100.0)
        tc_precond_enable = tc_algo in ("I", "Q", "R", "t") or (
            tc_algo == "" and self.tc_adaption_slider.GetValue() > 0
        )
        if tc_precond_enable:
            setcfg("tc_precond", int(self.tc_precond.GetValue()))
        setcfg("tc_precond_profile", self.tc_precond_profile.GetPath())
        setcfg("tc_filter", int(self.tc_filter.GetValue()))
        setcfg("tc_filter_L", self.tc_filter_L.GetValue())
        setcfg("tc_filter_a", self.tc_filter_a.GetValue())
        setcfg("tc_filter_b", self.tc_filter_b.GetValue())
        setcfg("tc_filter_rad", self.tc_filter_rad.GetValue())
        setcfg("tc_vrml_cie", int(self.tc_vrml_cie.GetValue()))
        setcfg("tc_vrml_device", int(self.tc_vrml_device.GetValue()))

    def tc_preview_handler(self, event=None, path=None):
        if self.worker.is_working():
            return

        fullspread_patches = getcfg("tc_fullspread_patches")
        single_patches = getcfg("tc_single_channel_patches")
        gray_patches = getcfg("tc_gray_patches")
        multidim_patches = getcfg("tc_multi_steps")
        multidim_bcc_patches = getcfg("tc_multi_bcc_steps")
        wkwargs = {}
        if (
            fullspread_patches
            and (
                single_patches > 2
                or gray_patches > 2
                or multidim_patches > 2
                or multidim_bcc_patches
            )
            and wx.GetKeyState(wx.WXK_SHIFT)
        ):
            dlg = ConfirmDialog(
                self,
                -1,
                lang.getstr("testchart.create"),
                lang.getstr("testchart.separate_fixed_points"),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                bitmap=geticon(32, appname + "-testchart-editor"),
            )
            dlg.sizer3.Add((1, 4))
            for name in ("single", "gray", "multidim"):
                if locals()[name + "_patches"] > 2 or (
                    name == "multidim" and multidim_bcc_patches
                ):
                    setattr(dlg, name, wx.CheckBox(dlg, -1, lang.getstr("tc." + name)))
                    dlg.sizer3.Add(getattr(dlg, name), 1, flag=wx.TOP, border=4)
                    getattr(dlg, name).Value = True
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()
            choice = dlg.ShowModal()
            for name in ("single", "gray", "multidim"):
                if hasattr(dlg, name):
                    wkwargs[name] = getattr(dlg, name).Value
            dlg.Destroy()
            if choice == wx.ID_CANCEL:
                return

        if not self.tc_check_save_ti1():
            return
        if not check_set_argyll_bin():
            return

        print("-" * 80)
        print(lang.getstr("testchart.create"))
        self.worker.interactive = False
        self.worker.start(
            self.tc_preview,
            self.tc_create,
            cargs=(path,),
            wargs=(),
            wkwargs=wkwargs,
            progress_msg=lang.getstr("testchart.create"),
            parent=self,
            progress_start=500,
        )

    def tc_preview_update(self, startindex):
        if not hasattr(self, "preview"):
            return
        numcols = self.preview.GetNumberCols()
        startrow = startindex / numcols
        startcol = startindex % numcols
        i = 0
        row = startrow
        numrows = self.preview.GetNumberRows()
        neededrows = math.ceil(float(self.grid.GetNumberRows()) / numcols) - numrows
        if neededrows > 0:
            self.preview.AppendRows(neededrows)
        while True:
            if row == startrow:
                cols = range(startcol, numcols)
            else:
                cols = range(numcols)
            for col in cols:
                if startindex + i < self.grid.GetNumberRows():
                    color = self.grid.GetCellBackgroundColour(startindex + i, 3)
                    textcolor = self.grid.GetCellTextColour(startindex + i, 3)
                    value = self.grid.GetCellValue(startindex + i, 3)
                else:
                    color = self.preview.GetDefaultCellBackgroundColour()
                    textcolor = self.preview.GetDefaultCellTextColour()
                    value = ""
                self.preview.SetCellBackgroundColour(row, col, color)
                self.preview.SetCellTextColour(row, col, textcolor)
                self.preview.SetCellValue(row, col, value)
                i += 1
            row += 1
            if startindex + i >= self.grid.GetNumberRows():
                break
        if row < self.preview.GetNumberRows():
            self.preview.DeleteRows(row, self.preview.GetNumberRows() - row)

    def tc_clear_handler(self, event):
        self.tc_check_save_ti1()

    def tc_clear(self, clear_ti1=True):
        grid = self.grid
        if grid.GetNumberRows() > 0:
            grid.DeleteRows(0, grid.GetNumberRows())
        if grid.GetNumberCols() > 0:
            grid.DeleteCols(0, grid.GetNumberCols())
        grid.Refresh()
        self.separator.Hide()
        self.sizer.Layout()
        if hasattr(self, "preview"):
            if self.preview.GetNumberRows() > 0:
                self.preview.DeleteRows(0, self.preview.GetNumberRows())
            if self.preview.GetNumberCols() > 0:
                self.preview.DeleteCols(0, self.preview.GetNumberCols())
            self.preview.Refresh()
        if clear_ti1:
            if hasattr(self, "ti1"):
                del self.ti1
            self.tc_update_controls()
            self.tc_check()
            # UGLY HACK: This 'print' call fixes a GTK assertion and
            # segfault under Arch Linux when setting the window title
            print("")
            self.SetTitle(lang.getstr("testchart.edit"))

    def tc_export_handler(self, event):
        if not hasattr(self, "ti1"):
            return
        path = None
        (defaultDir, defaultFile) = (
            get_verified_path("last_testchart_export_path")[0],
            os.path.basename(
                os.path.splitext(
                    self.ti1.filename or defaults["last_testchart_export_path"]
                )[0]
            ),
        )
        dlg = wx.FileDialog(
            self,
            lang.getstr("export"),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            # Disable JPEG as it introduces slight color errors
            wildcard=lang.getstr(  # lang.getstr("filetype.jpg") + "|*.jpg|" +
                "filetype.png"
            )
            + " (8-bit)|*.png|"
            + lang.getstr("filetype.png")
            + " (16-bit)|*.png|"
            + lang.getstr("filetype.tif")
            + " (8-bit)|*.tif|"
            + lang.getstr("filetype.tif")
            + " (16-bit)|*.tif|"
            + "DPX|*.dpx|"
            + "CSV (0.0..100.0)|*.csv|"
            + "CSV (0..255)|*.csv|"
            + "CSV (0..1023)|*.csv",
            style=wx.SAVE | wx.OVERWRITE_PROMPT,
        )
        dlg.Center(wx.BOTH)
        if dlg.ShowModal() == wx.ID_OK:
            filter_index = dlg.GetFilterIndex()
            path = dlg.GetPath()
        dlg.Destroy()
        if path:
            if not waccess(path, os.W_OK):
                show_result_dialog(
                    Error(lang.getstr("error.access_denied.write", path)), self
                )
                return
            setcfg("last_testchart_export_path", path)
            self.writecfg()
        else:
            return
        if filter_index < 5:
            # Image format
            scale = getcfg("app.dpi") / config.get_default_dpi()
            if scale < 1:
                scale = 1
            dlg = ConfirmDialog(
                self,
                title=lang.getstr("export"),
                msg=lang.getstr("testchart.export.repeat_patch"),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                bitmap=geticon(32, appname + "-testchart-editor"),
            )
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            dlg.sizer3.Add(sizer, 0, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
            intctrl = wx.SpinCtrl(
                dlg,
                -1,
                size=(95 * scale, -1),
                min=config.valid_ranges["tc_export_repeat_patch_max"][0],
                max=config.valid_ranges["tc_export_repeat_patch_max"][1],
                value=str(getcfg("tc_export_repeat_patch_max")),
            )
            sizer.Add(intctrl, 0, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=4)
            sizer.Add(
                wx.StaticText(dlg, -1, "× " + lang.getstr("max")),
                0,
                flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                border=12,
            )
            intctrl2 = wx.SpinCtrl(
                dlg,
                -1,
                size=(95 * scale, -1),
                min=config.valid_ranges["tc_export_repeat_patch_min"][0],
                max=config.valid_ranges["tc_export_repeat_patch_min"][1],
                value=str(getcfg("tc_export_repeat_patch_min")),
            )
            sizer.Add(intctrl2, 0, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=4)
            sizer.Add(
                wx.StaticText(dlg, -1, "× " + lang.getstr("min")),
                0,
                flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL,
                border=12,
            )
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()
            result = dlg.ShowModal()
            repeatmax = intctrl.GetValue()
            repeatmin = intctrl2.GetValue()
            dlg.Destroy()
            if result != wx.ID_OK:
                return
            setcfg("tc_export_repeat_patch_max", repeatmax)
            setcfg("tc_export_repeat_patch_min", repeatmin)
            self.writecfg()
            defaults["size.measureframe"] = get_default_size()
            self.display_size = wx.DisplaySize()
        if path:
            self.worker.start(
                lambda result: None,
                self.tc_export,
                wargs=(path, filter_index),
                wkwargs={},
                progress_msg=lang.getstr("export"),
                parent=self,
                progress_start=500,
                fancy=False,
            )

    def tc_export(self, path, filter_index):
        if filter_index < 5:
            # Image format
            self.tc_export_subroutine(path, filter_index)
        else:
            # CSV
            with open(path, "w") as csvfile:
                self.tc_export_subroutine(csv.writer(csvfile), filter_index)

    def tc_export_subroutine(self, target, filter_index, allow_gaps=False):
        maxlen = len(self.ti1[0].DATA)
        if filter_index < 5:
            # Image format
            name, ext = (
                os.path.splitext(target)[0],
                {0: ".png", 1: ".png", 2: ".tif", 3: ".tif", 4: ".dpx"}[filter_index],
            )
            format = {".dpx": "DPX", ".png": "PNG", ".tif": "TIFF"}[ext]
            bitdepth = {0: 8, 1: 16, 2: 8, 3: 16, 4: 10}[filter_index]
            vscale = 2**bitdepth - 1
            repeatmax = getcfg("tc_export_repeat_patch_max")
            repeatmin = getcfg("tc_export_repeat_patch_min")
            maxcount = maxlen * repeatmax
            filenameformat = "%%s-%%0%id%%s" % len(str(maxcount))
            count = 0
            secs = 0
            # Scale from screen dimensions to fixed 1080p viewport
            sw, sh = 1920, 1080
            x, y, size = [
                float(v) for v in getcfg("dimensions.measureframe").split(",")
            ]
            size *= defaults["size.measureframe"]
            displays = getcfg("displays")
            match = None
            display_no = getcfg("display.number") - 1
            if display_no in range(len(displays)):
                match = re.search(r"@ -?\d+, -?\d+, (\d+)x(\d+)", displays[display_no])
            if match:
                display_size = [int(item) for item in match.groups()]
            else:
                display_size = self.display_size
            w, h = [min(size / v, 1.0) for v in display_size]
            x = (display_size[0] - size) * x / display_size[0]
            y = (display_size[1] - size) * y / display_size[1]
            x, y, w, h = [max(v, 0) for v in (x, y, w, h)]
            x, w = [int(round(v * sw)) for v in (x, w)]
            y, h = [int(round(v * sh)) for v in (y, h)]
            dimensions = w, h
        else:
            # CSV
            vscale = {5: 100, 6: 255, 7: 1023}[filter_index]
        is_winnt6 = sys.platform == "win32" and sys.getwindowsversion() >= (6,)
        use_winnt6_symlinks = is_winnt6 and is_superuser()
        for i in range(maxlen):
            if self.worker.thread_abort:
                break
            self.worker.lastmsg.write("%d%%\n" % (100.0 / maxlen * (i + 1)))
            R, G, B = (
                self.ti1[0].DATA[i]["RGB_R"],
                self.ti1[0].DATA[i]["RGB_G"],
                self.ti1[0].DATA[i]["RGB_B"],
            )
            if not filter_index < 5:
                # CSV
                if vscale != 100:
                    # XXX: Careful when rounding floats!
                    # Incorrect: int(round(50 * 2.55)) = 127 (127.499999)
                    # Correct: int(round(50 / 100.0 * 255)) = 128 (127.5)
                    R, G, B = [int(round(v / 100.0 * vscale)) for v in [R, G, B]]
                target.writerow([str(v) for v in [i, R, G, B]])
                continue
            # Image format
            X, Y, Z = colormath.RGB2XYZ(R / 100.0, G / 100.0, B / 100.0, scale=100.0)
            L, a, b = colormath.XYZ2Lab(X, Y, Z)
            # XXX: Careful when rounding floats!
            # Incorrect: int(round(50 * 2.55)) = 127 (127.499999)
            # Correct: int(round(50 / 100.0 * 255)) = 128 (127.5)
            color = (
                int(round(R / 100.0 * vscale)),
                int(round(G / 100.0 * vscale)),
                int(round(B / 100.0 * vscale)),
            )
            count += 1
            filename = filenameformat % (name, count, ext)
            repeat = int(
                round(repeatmin + ((repeatmax - repeatmin) / 100.0 * (100 - L)))
            )
            imfile.write(
                [[color]],
                filename,
                bitdepth,
                format,
                dimensions,
                {
                    "original_width": sw,
                    "original_height": sh,
                    "offset_x": x,
                    "offset_y": y,
                    "frame_position": count,
                    "frame_rate": 1,
                    "held_count": repeat if allow_gaps else 1,
                    "timecode": [
                        int(v)
                        for v in time.strftime("%H:%M:%S:00", time.gmtime(secs)).split(
                            ":"
                        )
                    ],
                },
            )
            secs += 1
            # print("RGB", R, G, B, "L* %.2f" % L, "repeat", repeat)
            if repeat > 1:
                if allow_gaps:
                    count += repeat - 1
                    secs += repeat - 1
                    continue
                for j in range(repeat - 1):
                    count += 1
                    filecopyname = filenameformat % (name, count, ext)
                    if format == "DPX":
                        imfile.write(
                            [[color]],
                            filecopyname,
                            bitdepth,
                            format,
                            dimensions,
                            {
                                "original_width": sw,
                                "original_height": sh,
                                "offset_x": x,
                                "offset_y": y,
                                "frame_position": count,
                                "frame_rate": 1,
                                "timecode": [
                                    int(v)
                                    for v in time.strftime(
                                        "%H:%M:%S:00", time.gmtime(secs)
                                    ).split(":")
                                ],
                            },
                        )
                    secs += 1
                    if format == "DPX":
                        continue
                    if os.path.isfile(filecopyname):
                        os.unlink(filecopyname)
                    if is_winnt6:
                        if use_winnt6_symlinks:
                            win32file.CreateSymbolicLink(
                                filecopyname, os.path.basename(filename), 0
                            )
                        else:
                            shutil.copyfile(filename, filecopyname)
                    else:
                        os.symlink(os.path.basename(filename), filecopyname)

    def tc_save_handler(self, event=None):
        self.tc_save_as_handler(event, path=self.ti1.filename)

    def tc_save_as_handler(self, event=None, path=None):
        checkoverwrite = True
        if path is None or (event and not os.path.isfile(path)):
            path = None
            defaultDir = get_verified_path("last_ti1_path")[0]
            if hasattr(self, "ti1") and self.ti1.filename:
                if os.path.isfile(self.ti1.filename):
                    defaultDir = os.path.dirname(self.ti1.filename)
                defaultFile = os.path.basename(self.ti1.filename)
            else:
                defaultFile = os.path.basename(config.defaults["last_ti1_path"])
            dlg = wx.FileDialog(
                self,
                lang.getstr("save_as"),
                defaultDir=defaultDir,
                defaultFile=defaultFile,
                wildcard=lang.getstr("filetype.ti1") + "|*.ti1",
                style=wx.SAVE | wx.OVERWRITE_PROMPT,
            )
            dlg.Center(wx.BOTH)
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
            dlg.Destroy()
            if path:
                filename, ext = os.path.splitext(path)
                if ext.lower() != ".ti1":
                    path += ".ti1"
                else:
                    checkoverwrite = False
        if path:
            if not waccess(path, os.W_OK):
                show_result_dialog(
                    Error(lang.getstr("error.access_denied.write", path)), self
                )
                return
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
            setcfg("last_ti1_path", path)
            try:
                file_ = open(path, "wb")
                file_.write(bytes(self.ti1))
                file_.close()
                self.ti1.filename = path
                self.ti1.root.setmodified(False)
                if not self.IsBeingDeleted():
                    # UGLY HACK: This 'print' call fixes a GTK assertion and
                    # segfault under Arch Linux when setting the window title
                    print("")
                    self.SetTitle(
                        lang.getstr("testchart.edit").rstrip(".")
                        + ": "
                        + os.path.basename(path)
                    )
            except Exception as exception:
                handle_error(
                    Error("Error - testchart could not be saved: %s" % str(exception)),
                    parent=self,
                )
            else:
                if self.Parent:
                    if path != getcfg(self.cfg) and self.parent_set_chart_methodname:
                        dlg = ConfirmDialog(
                            self,
                            msg=lang.getstr("testchart.confirm_select"),
                            ok=lang.getstr("testchart.select"),
                            cancel=lang.getstr("testchart.dont_select"),
                            bitmap=geticon(32, "dialog-question"),
                        )
                        result = dlg.ShowModal()
                        dlg.Destroy()
                        if result == wx.ID_OK:
                            setcfg(self.cfg, path)
                            self.writecfg()
                    if path == getcfg(self.cfg) and self.parent_set_chart_methodname:
                        getattr(self.Parent, self.parent_set_chart_methodname)(path)
                if not self.IsBeingDeleted():
                    self.save_btn.Disable()
                return True
        return False

    def tc_view_3d(self, event):
        if (
            self.ti1.filename
            and not (
                self.worker.tempdir
                and self.ti1.filename.startswith(self.worker.tempdir)
            )
            and waccess(os.path.dirname(self.ti1.filename), os.W_OK)
        ):
            regenerate = self.ti1.modified
            paths = self.tc_save_3d(
                os.path.splitext(self.ti1.filename)[0], regenerate=regenerate
            )
            if not regenerate and os.path.isfile(self.ti1.filename):
                # Check if the testchart is newer than the 3D file(s)
                ti1_mtime = os.stat(self.ti1.filename).st_mtime
                for path in paths:
                    if os.stat(path).st_mtime < ti1_mtime:
                        regenerate = True
                        break
                if regenerate:
                    paths = self.tc_save_3d(
                        os.path.splitext(self.ti1.filename)[0], regenerate=True
                    )
        else:
            paths = self.tc_save_3d_as_handler(None)
        for path in paths:
            launch_file(path)

    def tc_save_3d_as_handler(self, event):
        path = None
        paths = []
        if (
            hasattr(self, "ti1")
            and self.ti1.filename
            and os.path.isfile(self.ti1.filename)
        ):
            defaultDir = os.path.dirname(self.ti1.filename)
            defaultFile = self.ti1.filename
        else:
            defaultDir = get_verified_path("last_vrml_path")[0]
            defaultFile = defaults["last_vrml_path"]
        view_3d_format = getcfg("3d.format")
        if view_3d_format == "HTML":
            formatext = ".html"
        elif view_3d_format == "VRML":
            if getcfg("vrml.compress"):
                formatext = ".wrz"
            else:
                formatext = ".wrl"
        else:
            formatext = ".x3d"
        defaultFile = os.path.splitext(os.path.basename(defaultFile))[0] + formatext
        dlg = wx.FileDialog(
            self,
            lang.getstr("save_as"),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            wildcard=lang.getstr("view.3d") + "|*" + formatext,
            style=wx.SAVE | wx.OVERWRITE_PROMPT,
        )
        dlg.Center(wx.BOTH)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        dlg.Destroy()
        if path:
            if not waccess(path, os.W_OK):
                show_result_dialog(
                    Error(lang.getstr("error.access_denied.write", path)), self
                )
                return []
            filename, ext = os.path.splitext(path)
            if ext.lower() != formatext:
                path += formatext
            setcfg("last_vrml_path", path)
            paths = self.tc_save_3d(filename)
        return paths

    def tc_save_3d(self, filename, regenerate=True):
        paths = []
        view_3d_format = getcfg("3d.format")
        if view_3d_format == "VRML":
            if getcfg("vrml.compress"):
                formatext = ".wrz"
            else:
                formatext = ".wrl"
        else:
            formatext = ".x3d"
            if view_3d_format == "HTML":
                formatext += ".html"
        if getcfg("tc_vrml_device") or getcfg("tc_vrml_cie"):
            colorspaces = []
            if getcfg("tc_vrml_device"):
                colorspaces.append(getcfg("tc_vrml_device_colorspace"))
            if getcfg("tc_vrml_cie"):
                colorspaces.append(getcfg("tc_vrml_cie_colorspace"))
            for colorspace in colorspaces:
                path = filename + " " + colorspace + formatext
                if os.path.exists(path):
                    if regenerate:
                        dlg = ConfirmDialog(
                            self,
                            msg=lang.getstr("dialog.confirm_overwrite", (path)),
                            ok=lang.getstr("overwrite"),
                            cancel=lang.getstr("cancel"),
                            bitmap=geticon(32, "dialog-warning"),
                        )
                        result = dlg.ShowModal()
                        dlg.Destroy()
                    else:
                        result = wx.ID_CANCEL
                    if result != wx.ID_OK:
                        paths.append(path)
                        continue
                try:
                    self.ti1[0].export_3d(
                        path,
                        colorspace,
                        RGB_black_offset=getcfg("tc_vrml_black_offset"),
                        normalize_RGB_white=getcfg("tc_vrml_use_D50"),
                        compress=formatext == ".wrz",
                        format=view_3d_format,
                    )
                except Exception as exception:
                    handle_error(
                        UserWarning(
                            "Warning - 3D file could not be " "saved: " + str(exception)
                        ),
                        parent=self,
                    )
                else:
                    paths.append(path)
        return paths

    def tc_check_save_ti1(self, clear=True):
        if hasattr(self, "ti1"):
            if (
                self.ti1.root.modified
                or not self.ti1.filename
                or not os.path.exists(self.ti1.filename)
            ):
                if self.save_btn.Enabled:
                    ok = lang.getstr("save")
                else:
                    ok = lang.getstr("save_as")
                dlg = ConfirmDialog(
                    self,
                    msg=lang.getstr("testchart.save_or_discard"),
                    ok=ok,
                    cancel=lang.getstr("cancel"),
                    bitmap=geticon(32, "dialog-warning"),
                )
                if self.IsBeingDeleted():
                    dlg.buttonpanel.Hide(0)
                if self.save_btn.Enabled:
                    dlg.save_as = wx.Button(dlg.buttonpanel, -1, lang.getstr("save_as"))
                    ID_SAVE_AS = dlg.save_as.GetId()
                    dlg.Bind(wx.EVT_BUTTON, dlg.OnClose, id=ID_SAVE_AS)
                    dlg.sizer2.Add((12, 12))
                    dlg.sizer2.Add(dlg.save_as)
                else:
                    ID_SAVE_AS = wx.ID_OK
                dlg.discard = wx.Button(
                    dlg.buttonpanel, -1, lang.getstr("testchart.discard")
                )
                ID_DISCARD = dlg.discard.GetId()
                dlg.Bind(wx.EVT_BUTTON, dlg.OnClose, id=ID_DISCARD)
                dlg.sizer2.Add((12, 12))
                dlg.sizer2.Add(dlg.discard)
                dlg.buttonpanel.Layout()
                dlg.sizer0.SetSizeHints(dlg)
                dlg.sizer0.Layout()
                result = dlg.ShowModal()
                dlg.Destroy()
                if result in (wx.ID_OK, ID_SAVE_AS):
                    if result == ID_SAVE_AS:
                        path = None
                    else:
                        path = self.ti1.filename
                    if not self.tc_save_as_handler(True, path):
                        return False
                elif result == wx.ID_CANCEL:
                    return False
                clear = True
            if clear and not self.IsBeingDeleted():
                self.tc_clear()
        return True

    def tc_close_handler(self, event=None):
        if getattr(self.worker, "thread", None) and self.worker.thread.is_alive():
            self.worker.abort_subprocess(True)
            return
        if (not event or self.IsShownOnScreen()) and self.tc_check_save_ti1(False):
            setcfg("tc.saturation_sweeps", self.saturation_sweeps_intctrl.GetValue())
            for component in ("R", "G", "B"):
                setcfg(
                    "tc.saturation_sweeps.custom.%s" % component,
                    getattr(
                        self, "saturation_sweeps_custom_%s_ctrl" % component
                    ).GetValue(),
                )
            self.worker.wrapup(False)
            # Hide first (looks nicer)
            self.Hide()
            if self.Parent:
                setcfg("tc.show", 0)
                return True
            else:
                self.writecfg()
                # Need to use CallAfter to prevent hang under Windows if minimized
                wx.CallAfter(self.Destroy)
        elif isinstance(event, wx.CloseEvent) and event.CanVeto():
            event.Veto()

    def tc_move_handler(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            setcfg("position.tcgen.x", x)
            setcfg("position.tcgen.y", y)
        if event:
            event.Skip()

    def tc_destroy_handler(self, event):
        event.Skip()

    def tc_load_cfg_from_ti1(
        self,
        event=None,
        path=None,
        cfg=None,
        parent_set_chart_methodname=None,
        resume=False,
    ):
        if self.worker.is_working():
            return

        if cfg:
            self.cfg = cfg
        if path is None:
            path = getcfg(self.cfg)
        if path == "auto":
            return
        if parent_set_chart_methodname:
            self.parent_set_chart_methodname = parent_set_chart_methodname

        if not self.tc_check_save_ti1():
            return

        print(lang.getstr("testchart.read"))
        self.worker.interactive = False
        self.worker.start(
            self.tc_load_cfg_from_ti1_finish,
            self.tc_load_cfg_from_ti1_worker,
            wargs=(path,),
            wkwargs={},
            progress_title=lang.getstr("testchart.read"),
            progress_msg=lang.getstr("testchart.read"),
            parent=self,
            progress_start=500,
            cancelable=False,
            resume=resume,
            show_remaining_time=False,
            fancy=False,
        )

    def tc_load_cfg_from_ti1_worker(self, path):
        path = str(path)
        try:
            filename, ext = os.path.splitext(path)
            if ext.lower() not in (".icc", ".icm"):
                if ext.lower() == ".ti3":
                    with open(path, "rb") as f:
                        ti3_data = f.read()
                    ti1 = CGATS.CGATS(ti3_to_ti1(ti3_data))
                    ti1.filename = filename + ".ti1"
                else:
                    ti1 = CGATS.CGATS(path)
                    ti1.filename = path
            else:  # icc or icm profile
                profile = ICCP.ICCProfile(path)
                ti1 = CGATS.CGATS(
                    ti3_to_ti1(
                        profile.tags.get("CIED", "") or profile.tags.get("targ", "")
                    )
                )
                ti1.filename = filename + ".ti1"
            ti1.fix_device_values_scaling()
            try:
                ti1_1 = verify_cgats(ti1, ("RGB_R", "RGB_B", "RGB_G"))
            except CGATS.CGATSError as exception:
                msg = {
                    CGATS.CGATSKeyError: lang.getstr(
                        "error.testchart.missing_fields", (path, "RGB_R, RGB_G, RGB_B")
                    )
                }.get(
                    exception.__class__,
                    lang.getstr("error.testchart.invalid", path)
                    + "\n"
                    + lang.getstr(str(exception)),
                )
                return Error(msg)
            else:
                try:
                    verify_cgats(ti1, ("XYZ_X", "XYZ_Y", "XYZ_Z"))
                except CGATS.CGATSKeyError:
                    # Missing XYZ, add via simple sRGB-like model
                    data = ti1_1.queryv1("DATA")
                    data.parent.DATA_FORMAT.add_data(("XYZ_X", "XYZ_Y", "XYZ_Z"))
                    for sample in data.values():
                        XYZ = argyll_RGB2XYZ(
                            *[sample["RGB_" + channel] / 100.0 for channel in "RGB"]
                        )
                        for i, component in enumerate("XYZ"):
                            sample["XYZ_" + component] = XYZ[i] * 100
                else:
                    if ext.lower() not in (".ti1", ".ti2") and ti1_1:
                        ti1_1.add_keyword("ACCURATE_EXPECTED_VALUES", "true")
                ti1.root.setmodified(False)
                self.ti1 = ti1
        except Exception as exception:
            return Error(
                "%s\n\n%s" % (lang.getstr("error.testchart.read", path), str(exception))
            )

        white_patches = self.ti1.queryv1("WHITE_COLOR_PATCHES") or None
        black_patches = self.ti1.queryv1("BLACK_COLOR_PATCHES") or None
        single_channel_patches = self.ti1.queryv1("SINGLE_DIM_STEPS") or None
        gray_patches = self.ti1.queryv1("COMP_GREY_STEPS") or None
        multi_bcc_steps = self.ti1.queryv1("MULTI_DIM_BCC_STEPS") or 0
        multi_steps = self.ti1.queryv1("MULTI_DIM_STEPS") or multi_bcc_steps
        fullspread_patches = self.ti1.queryv1("NUMBER_OF_SETS")
        gamma = self.ti1.queryv1("EXTRA_DEV_POW") or 1.0
        dark_emphasis = ((self.ti1.queryv1("DARK_REGION_EMPHASIS") or 1.0) - 1.0) / 3.0

        if None in (white_patches, single_channel_patches, gray_patches, multi_steps):
            if None in (single_channel_patches, gray_patches, multi_steps):
                white_patches = 0
                black_patches = 0
                R = []
                G = []
                B = []
                gray_channel = [0]
                data = self.ti1.queryv1("DATA")
                multi = {"R": [], "G": [], "B": []}
                if multi_steps is None:
                    multi_steps = 0
                uniqueRGB = []
                vmaxlen = 4
                for i in data:
                    if self.worker.thread_abort:
                        return False
                    # XXX Note that round(50 * 2.55) = 127, but
                    # round(50 / 100 * 255) = 128 (the latter is what we want)!
                    patch = [
                        round(v / 100.0 * 255, vmaxlen)
                        for v in (data[i]["RGB_R"], data[i]["RGB_G"], data[i]["RGB_B"])
                    ]  # normalize to 0...255 range
                    strpatch = [str(int(round(round(v, 1)))) for v in patch]
                    if patch[0] == patch[1] == patch[2] == 255:  # white
                        white_patches += 1
                        if 255 not in gray_channel:
                            gray_channel.append(255)
                    elif patch[0] == patch[1] == patch[2] == 0:  # black
                        black_patches += 1
                        if 0 not in R and 0 not in G and 0 not in B:
                            R.append(0)
                            G.append(0)
                            B.append(0)
                        if 0 not in gray_channel:
                            gray_channel.append(0)
                    elif patch[2] == patch[1] == 0 and patch[0] not in R:  # red
                        R.append(patch[0])
                    elif patch[0] == patch[2] == 0 and patch[1] not in G:  # green
                        G.append(patch[1])
                    elif patch[0] == patch[1] == 0 and patch[2] not in B:  # blue
                        B.append(patch[2])
                    elif patch[0] == patch[1] == patch[2]:  # gray
                        if patch[0] not in gray_channel:
                            gray_channel.append(patch[0])
                    elif multi_steps == 0:
                        multi_steps = None
                    if debug >= 9:
                        print("[D]", strpatch)
                    if strpatch not in uniqueRGB:
                        uniqueRGB.append(strpatch)
                        if patch[0] not in multi["R"]:
                            multi["R"].append(patch[0])
                        if patch[1] not in multi["G"]:
                            multi["G"].append(patch[1])
                        if patch[2] not in multi["B"]:
                            multi["B"].append(patch[2])

                if single_channel_patches is None:
                    single_channel_patches = min(len(R), len(G), len(B))
                if gray_patches is None:
                    gray_patches = len(gray_channel)
                if multi_steps is None:
                    multi_steps = 0

                if single_channel_patches is None:
                    # NEVER (old code, needs work for demphasis/gamma, remove?)
                    R_inc = self.tc_get_increments(R, vmaxlen)
                    G_inc = self.tc_get_increments(G, vmaxlen)
                    B_inc = self.tc_get_increments(B, vmaxlen)
                    if debug:
                        print("[D] R_inc:")
                        for i in R_inc:
                            if self.worker.thread_abort:
                                return False
                            print("[D] %s: x%s" % (i, R_inc[i]))
                        print("[D] G_inc:")
                        for i in G_inc:
                            if self.worker.thread_abort:
                                return False
                            print("[D] %s: x%s" % (i, G_inc[i]))
                        print("[D] B_inc:")
                        for i in B_inc:
                            if self.worker.thread_abort:
                                return False
                            print("[D] %s: x%s" % (i, B_inc[i]))
                    RGB_inc = {"0": 0}
                    for inc in R_inc:
                        if self.worker.thread_abort:
                            return False
                        if (
                            inc in G_inc
                            and inc in B_inc
                            and R_inc[inc] == G_inc[inc] == B_inc[inc]
                        ):
                            RGB_inc[inc] = R_inc[inc]
                    for inc in G_inc:
                        if self.worker.thread_abort:
                            return False
                        if (
                            inc in R_inc
                            and inc in B_inc
                            and R_inc[inc] == G_inc[inc] == B_inc[inc]
                        ):
                            RGB_inc[inc] = G_inc[inc]
                    for inc in B_inc:
                        if self.worker.thread_abort:
                            return False
                        if (
                            inc in R_inc
                            and inc in G_inc
                            and R_inc[inc] == G_inc[inc] == B_inc[inc]
                        ):
                            RGB_inc[inc] = B_inc[inc]
                    if False:
                        RGB_inc_max = max(RGB_inc.values())
                        if RGB_inc_max > 0:
                            single_channel_patches = RGB_inc_max + 1
                        else:
                            single_channel_patches = 0
                    else:
                        single_inc = {"0": 0}
                        for inc in RGB_inc:
                            if self.worker.thread_abort:
                                return False
                            if inc != "0":
                                finc = float(inc)
                                n = int(round(float(str(255.0 / finc))))
                                finc = 255.0 / n
                                n += 1
                                if debug >= 9:
                                    print("[D] inc:", inc)
                                    print("[D] n:", n)
                                for i in range(n):
                                    if self.worker.thread_abort:
                                        return False
                                    v = str(int(round(float(str(i * finc)))))
                                    if debug >= 9:
                                        print("[D] Searching for", v)
                                    if (
                                        [v, "0", "0"] in uniqueRGB
                                        and ["0", v, "0"] in uniqueRGB
                                        and ["0", "0", v] in uniqueRGB
                                    ):
                                        if inc not in single_inc:
                                            single_inc[inc] = 0
                                        single_inc[inc] += 1
                                    else:
                                        if debug >= 9:
                                            print("[D] Not found!")
                                        break
                        single_channel_patches = max(single_inc.values())
                    if debug:
                        print("[D] single_channel_patches:", single_channel_patches)
                    if 0 in R + G + B:
                        fullspread_patches += 3  # black in single channel patches
                elif single_channel_patches >= 2:
                    fullspread_patches += 3  # black always in SINGLE_DIM_STEPS

                if gray_patches is None:
                    # NEVER (old code, needs work for demphasis/gamma, remove?)
                    RGB_inc = self.tc_get_increments(gray_channel, vmaxlen)
                    if debug:
                        print("[D] RGB_inc:")
                        for i in RGB_inc:
                            if self.worker.thread_abort:
                                return False
                            print("[D] %s: x%s" % (i, RGB_inc[i]))
                    if False:
                        RGB_inc_max = max(RGB_inc.values())
                        if RGB_inc_max > 0:
                            gray_patches = RGB_inc_max + 1
                        else:
                            gray_patches = 0
                    else:
                        gray_inc = {"0": 0}
                        for inc in RGB_inc:
                            if self.worker.thread_abort:
                                return False
                            if inc != "0":
                                finc = float(inc)
                                n = int(round(float(str(255.0 / finc))))
                                finc = 255.0 / n
                                n += 1
                                if debug >= 9:
                                    print("[D] inc:", inc)
                                    print("[D] n:", n)
                                for i in range(n):
                                    if self.worker.thread_abort:
                                        return False
                                    v = str(int(round(float(str(i * finc)))))
                                    if debug >= 9:
                                        print("[D] Searching for", v)
                                    if [v, v, v] in uniqueRGB:
                                        if inc not in gray_inc:
                                            gray_inc[inc] = 0
                                        gray_inc[inc] += 1
                                    else:
                                        if debug >= 9:
                                            print("[D] Not found!")
                                        break
                        gray_patches = max(gray_inc.values())
                    if debug:
                        print("[D] gray_patches:", gray_patches)
                    if 0 in gray_channel:
                        fullspread_patches += 1  # black in gray patches
                    if 255 in gray_channel:
                        fullspread_patches += 1  # white in gray patches
                elif gray_patches >= 2:
                    fullspread_patches += 2  # black and white always in COMP_GREY_STEPS

                if multi_steps is None:
                    # NEVER (old code, needs work for demphasis/gamma, remove?)
                    R_inc = self.tc_get_increments(multi["R"], vmaxlen)
                    G_inc = self.tc_get_increments(multi["G"], vmaxlen)
                    B_inc = self.tc_get_increments(multi["B"], vmaxlen)
                    RGB_inc = {"0": 0}
                    for inc in R_inc:
                        if self.worker.thread_abort:
                            return False
                        if (
                            inc in G_inc
                            and inc in B_inc
                            and R_inc[inc] == G_inc[inc] == B_inc[inc]
                        ):
                            RGB_inc[inc] = R_inc[inc]
                    for inc in G_inc:
                        if self.worker.thread_abort:
                            return False
                        if (
                            inc in R_inc
                            and inc in B_inc
                            and R_inc[inc] == G_inc[inc] == B_inc[inc]
                        ):
                            RGB_inc[inc] = G_inc[inc]
                    for inc in B_inc:
                        if self.worker.thread_abort:
                            return False
                        if (
                            inc in R_inc
                            and inc in G_inc
                            and R_inc[inc] == G_inc[inc] == B_inc[inc]
                        ):
                            RGB_inc[inc] = B_inc[inc]
                    if debug:
                        print("[D] RGB_inc:")
                        for i in RGB_inc:
                            if self.worker.thread_abort:
                                return False
                            print("[D] %s: x%s" % (i, RGB_inc[i]))
                    multi_inc = {"0": 0}
                    for inc in RGB_inc:
                        if self.worker.thread_abort:
                            return False
                        if inc != "0":
                            finc = float(inc)
                            n = int(round(float(str(255.0 / finc))))
                            finc = 255.0 / n
                            n += 1
                            if debug >= 9:
                                print("[D] inc:", inc)
                                print("[D] n:", n)
                            for i in range(n):
                                if self.worker.thread_abort:
                                    return False
                                r = str(int(round(float(str(i * finc)))))
                                for j in range(n):
                                    if self.worker.thread_abort:
                                        return False
                                    g = str(int(round(float(str(j * finc)))))
                                    for k in range(n):
                                        if self.worker.thread_abort:
                                            return False
                                        b = str(int(round(float(str(k * finc)))))
                                        if debug >= 9:
                                            print(
                                                "[D] Searching for", i, j, k, [r, g, b]
                                            )
                                        if [r, g, b] in uniqueRGB:
                                            if inc not in multi_inc:
                                                multi_inc[inc] = 0
                                            multi_inc[inc] += 1
                                        else:
                                            if debug >= 9:
                                                print("[D] Not found! (b loop)")
                                            break
                                    if [r, g, b] not in uniqueRGB:
                                        if debug >= 9:
                                            print("[D] Not found! (g loop)")
                                        break
                                if [r, g, b] not in uniqueRGB:
                                    if debug >= 9:
                                        print("[D] Not found! (r loop)")
                                    break
                    multi_patches = max(multi_inc.values())
                    multi_steps = int(float(str(math.pow(multi_patches, 1 / 3.0))))
                    if debug:
                        print("[D] multi_patches:", multi_patches)
                        print("[D] multi_steps:", multi_steps)
                elif multi_steps >= 2:
                    fullspread_patches += 2  # black and white always in MULTI_DIM_STEPS
            else:
                white_patches = len(
                    self.ti1[0].queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
                )
                black_patches = len(
                    self.ti1[0].queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
                )
                if single_channel_patches >= 2:
                    fullspread_patches += 3  # black always in SINGLE_DIM_STEPS
                if gray_patches >= 2:
                    fullspread_patches += 2  # black and white always in COMP_GREY_STEPS
                if multi_steps >= 2:
                    fullspread_patches += 2  # black and white always in MULTI_DIM_STEPS
            fullspread_patches -= white_patches
            if self.worker.argyll_version >= [1, 6]:
                fullspread_patches -= black_patches
            fullspread_patches -= single_channel_patches * 3
            fullspread_patches -= gray_patches
            fullspread_patches -= (
                int(float(str(math.pow(multi_steps, 3)))) - single_channel_patches * 3
            )

        return (
            white_patches,
            black_patches,
            single_channel_patches,
            gray_patches,
            multi_steps,
            multi_bcc_steps,
            fullspread_patches,
            gamma,
            dark_emphasis,
        )

    def tc_load_cfg_from_ti1_finish(self, result):
        self.worker.wrapup(False)
        if isinstance(result, tuple):
            # UGLY HACK: This 'print' call fixes a GTK assertion and
            # segfault under Arch Linux when setting the window title
            print("")
            self.SetTitle(
                lang.getstr("testchart.edit").rstrip(".")
                + ": "
                + os.path.basename(self.ti1.filename)
            )

            print(lang.getstr("success"))
            (
                white_patches,
                black_patches,
                single_channel_patches,
                gray_patches,
                multi_steps,
                multi_bcc_steps,
                fullspread_patches,
                gamma,
                dark_emphasis,
            ) = result

            fullspread_ba = {
                "ERROR_OPTIMISED_PATCHES": "",  # OFPS in older Argyll CMS versions
                # "ERROR_OPTIMISED_PATCHES": "R",  # Perc. space random - same keyword as OFPS in older Argyll CMS versions, don't use
                "IFP_PATCHES": "t",  # Inc. far point
                "INC_FAR_PATCHES": "t",  # Inc. far point in older Argyll CMS versions
                "OFPS_PATCHES": "",  # OFPS
                "RANDOM_DEVICE_PATCHES": "r",  # Dev. space random
                "RANDOM_PATCHES": "r",  # Dev. space random in older Argyll CMS versions
                "RANDOM_PERCEPTUAL_PATCHES": "R",  # Perc. space random
                # "RANDOM_PERCEPTUAL_PATCHES": "Q",  # Perc. space filling quasi-random - same keyword as perc. space random, don't use
                "SIMPLEX_DEVICE_PATCHES": "i",  # Dev. space body centered cubic grid
                "SIMPLEX_PERCEPTUAL_PATCHES": "I",  # Perc. space body centered cubic grid
                "SPACEFILING_RANDOM_PATCHES": "q",  # Device space filling quasi-random, typo in older Argyll CMS versions
                "SPACEFILLING_RANDOM_PATCHES": "q",  # Device space filling quasi-random
            }

            algo = None

            for key in list(fullspread_ba.keys()):
                queryv_ = self.ti1.queryv1(key)
                if queryv_ is not None and queryv_ > 0:
                    algo = fullspread_ba[key]
                    break

            if white_patches is not None:
                setcfg("tc_white_patches", white_patches)
            if black_patches is not None:
                setcfg("tc_black_patches", black_patches)
            if single_channel_patches is not None:
                setcfg("tc_single_channel_patches", single_channel_patches)
            if gray_patches is not None:
                setcfg("tc_gray_patches", gray_patches)
            if multi_steps is not None:
                setcfg("tc_multi_steps", multi_steps)
            if multi_bcc_steps is not None:
                setcfg("tc_multi_bcc_steps", multi_bcc_steps)
            setcfg(
                "tc_fullspread_patches",
                self.ti1.queryv1("NUMBER_OF_SETS")
                - self.tc_get_total_patches(
                    white_patches,
                    black_patches,
                    single_channel_patches,
                    gray_patches,
                    multi_steps,
                    multi_bcc_steps,
                    0,
                ),
            )
            if gamma is not None:
                setcfg("tc_gamma", gamma)
            if dark_emphasis is not None:
                setcfg("tc_dark_emphasis", dark_emphasis)
            if algo is not None:
                setcfg("tc_algo", algo)
            self.writecfg()

            self.tc_update_controls()
            self.tc_preview(True)
            return True
        else:
            print(lang.getstr("aborted"))
            if self.Parent and hasattr(self.Parent, "start_timers"):
                self.Parent.start_timers()
            if isinstance(result, Exception):
                show_result_dialog(result, self)

    def tc_get_increments(self, channel, vmaxlen=4):
        channel.sort()
        increments = {"0": 0}
        for i, v in enumerate(channel):
            for j in reversed(range(i, len(channel))):
                inc = round(float(str(channel[j] - v)), vmaxlen)
                if inc > 0:
                    inc = str(inc)
                    if inc not in increments:
                        increments[inc] = 0
                    increments[inc] += 1
        return increments

    def tc_create(self, gray=False, multidim=False, single=False):
        """Create testchart using targen.

        Setting gray, multidim or single to True will ad those patches
        in a separate step if any number of iterative patches are to be
        generated as well.

        """
        self.writecfg()
        fullspread_patches = getcfg("tc_fullspread_patches")
        white_patches = getcfg("tc_white_patches")
        black_patches = getcfg("tc_black_patches")
        single_patches = getcfg("tc_single_channel_patches")
        gray_patches = getcfg("tc_gray_patches")
        multidim_patches = getcfg("tc_multi_steps")
        multidim_bcc_patches = getcfg("tc_multi_bcc_steps")
        extra_args = getcfg("extra_args.targen")
        result = True
        fixed_ti1 = None
        if fullspread_patches > 0 and (gray or multidim or single):
            # Generate fixed points first so they don't punch "holes" into the
            # OFPS distribution
            setcfg("tc_white_patches", 0)
            setcfg("tc_black_patches", 0)
            if not single:
                setcfg("tc_single_channel_patches", 0)
            if not gray:
                setcfg("tc_gray_patches", 0)
            if not multidim:
                setcfg("tc_multi_steps", 0)
                setcfg("tc_multi_bcc_steps", 0)
            setcfg("tc_fullspread_patches", 0)
            setcfg("extra_args.targen", "")
            result = self.tc_create_ti1()
        if fullspread_patches > 0 and (gray or multidim or single):
            setcfg("tc_white_patches", white_patches)
            setcfg("tc_black_patches", black_patches)
            if single:
                setcfg("tc_single_channel_patches", 2)
            else:
                setcfg("tc_single_channel_patches", single_patches)
            if gray:
                setcfg("tc_gray_patches", 2)
            else:
                setcfg("tc_gray_patches", gray_patches)
            if multidim:
                setcfg("tc_multi_steps", 2)
                setcfg("tc_multi_bcc_steps", 0)
            else:
                setcfg("tc_multi_steps", multidim_patches)
                setcfg("tc_multi_bcc_steps", multidim_bcc_patches)
            setcfg("tc_fullspread_patches", fullspread_patches)
            setcfg("extra_args.targen", extra_args)
            fixed_ti1 = result
        if not isinstance(result, Exception) and result:
            result = self.tc_create_ti1()
            if isinstance(result, CGATS.CGATS):
                if fixed_ti1:
                    if gray:
                        result[0].add_keyword("COMP_GREY_STEPS", gray_patches)
                    if multidim:
                        result[0].add_keyword("MULTI_DIM_STEPS", multidim_patches)
                        if multidim_bcc_patches:
                            result[0].add_keyword(
                                "MULTI_DIM_BCC_STEPS", multidim_bcc_patches
                            )
                    if single:
                        result[0].add_keyword("SINGLE_DIM_STEPS", single_patches)
                    fixed_data = fixed_ti1.queryv1("DATA")
                    data = result.queryv1("DATA")
                    data_format = result.queryv1("DATA_FORMAT")
                    # Get only RGB data
                    data.parent.DATA_FORMAT = CGATS.CGATS()
                    data.parent.DATA_FORMAT.key = "DATA_FORMAT"
                    data.parent.DATA_FORMAT.parent = data
                    data.parent.DATA_FORMAT.root = data.root
                    data.parent.DATA_FORMAT.type = "DATA_FORMAT"
                    for i, label in enumerate(("RGB_R", "RGB_G", "RGB_B")):
                        data.parent.DATA_FORMAT[i] = label
                    fixed_data.parent.DATA_FORMAT = data.parent.DATA_FORMAT
                    rgbdata = str(data)
                    # Restore DATA_FORMAT
                    data.parent.DATA_FORMAT = data_format
                    # Collect all fixed point datasets not in data
                    fixed_data.vmaxlen = data.vmaxlen
                    fixed_datasets = []
                    for i in fixed_data:
                        dataset = fixed_data[i]
                        if not str(dataset) in rgbdata:
                            fixed_datasets.append(dataset)
                    if fixed_datasets:
                        # Insert fixed point datasets after first patch
                        data.moveby1(1, len(fixed_datasets))
                        for i, dataset in enumerate(fixed_datasets):
                            dataset.key = i + 1
                            dataset.parent = data
                            dataset.root = data.root
                            data[dataset.key] = dataset
                self.ti1 = result
        setcfg("tc_single_channel_patches", single_patches)
        setcfg("tc_gray_patches", gray_patches)
        setcfg("tc_multi_steps", multidim_patches)
        setcfg("tc_multi_bcc_steps", multidim_bcc_patches)
        return result

    def tc_create_ti1(self):
        cmd, args = self.worker.prepare_targen()
        if not isinstance(cmd, Exception):
            result = self.worker.exec_cmd(
                cmd,
                args,
                low_contrast=False,
                skip_scripts=True,
                silent=False,
                parent=self,
            )
        else:
            result = cmd
        if not isinstance(result, Exception) and result:
            if not isinstance(result, Exception):
                path = os.path.join(self.worker.tempdir, "temp.ti1")
                result = check_file_isfile(path, silent=False)
                if not isinstance(result, Exception) and result:
                    try:
                        result = CGATS.CGATS(path)
                        print(lang.getstr("success"))
                    except Exception as exception:
                        result = Error(
                            "Error - testchart file could not be read: %s "
                            % str(exception)
                        )
                    else:
                        result.filename = None
        self.worker.wrapup(False)
        return result

    def tc_preview(self, result, path=None):
        self.tc_check()
        if isinstance(result, Exception):
            show_result_dialog(result, self)
        elif result:
            if not hasattr(self, "separator"):
                # We add this here because of a wxGTK 2.8 quirk where the
                # vertical scrollbar otherwise has a 1px horizontal
                # line at the top otherwise.
                separator_color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
                self.separator = wx.Panel(self.panel, size=(-1, 1))
                self.separator.BackgroundColour = separator_color
                index = len(self.sizer.Children) - 1
                if sys.platform not in ("darwin", "win32") or tc_use_alternate_preview:
                    index -= 1
                self.sizer.Insert(index, self.separator, flag=wx.EXPAND)
            else:
                self.separator.Show()
            self.sizer.Layout()
            if verbose >= 1:
                print(lang.getstr("tc.preview.create"))
            data = self.ti1.queryv1("DATA")
            vmaxlen = 6

            if hasattr(self, "preview"):
                self.preview.BeginBatch()
                w = self.grid.GetDefaultRowSize()
                numcols = (
                    self.sizer.Size[0] - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
                ) / w
                self.preview.AppendCols(numcols)
                for i in range(numcols):
                    self.preview.SetColLabelValue(i, str(i + 1))

            grid = self.grid
            grid.BeginBatch()
            data_format = self.ti1.queryv1("DATA_FORMAT")
            for i in data_format:
                data_format_str_value = data_format[i].decode("utf-8")
                if data_format_str_value in ("RGB_R", "RGB_G", "RGB_B"):
                    grid.AppendCols(1)
                    grid.SetColLabelValue(
                        grid.GetNumberCols() - 1,
                        data_format_str_value.split("_")[-1] + " %",
                    )
            grid.AppendCols(1)
            grid.SetColLabelValue(grid.GetNumberCols() - 1, "")
            grid.SetColSize(grid.GetNumberCols() - 1, self.grid.GetDefaultRowSize())
            self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
            grid.AppendRows(self.tc_amount)
            dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
            dc.SetFont(grid.GetLabelFont())
            w, h = dc.GetTextExtent("99%s" % self.ti1.queryv1("NUMBER_OF_SETS"))
            grid.SetRowLabelSize(max(w, grid.GetDefaultRowSize()))
            attr = wx.grid.GridCellAttr()
            attr.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
            attr.SetReadOnly()
            grid.SetColAttr(grid.GetNumberCols() - 1, attr)

            for i in data:
                sample = data[i]
                for j in range(grid.GetNumberCols()):
                    label = self.label_b2a.get(grid.GetColLabelValue(j))
                    if label in ("RGB_R", "RGB_G", "RGB_B"):
                        grid.SetCellValue(
                            i,
                            j,
                            CGATS.rpad(
                                sample[label], vmaxlen + (1 if sample[label] < 0 else 0)
                            ),
                        )
                self.tc_grid_setcolorlabel(i, data)
            self.tc_preview_update(0)

            if hasattr(self, "preview"):
                w, h = dc.GetTextExtent("99%s" % self.preview.GetNumberRows())
                self.preview.SetRowLabelSize(max(w, grid.GetDefaultRowSize()))
                self.preview.EndBatch()

            self.tc_set_default_status()
            if verbose >= 1:
                print(lang.getstr("success"))
            self.resize_grid()
            grid.EndBatch()
            if path:
                wx.CallAfter(self.tc_save_as_handler, path=path)
        if self.Parent and hasattr(self.Parent, "start_timers"):
            self.Parent.start_timers()

    def tc_add_data(self, row, newdata):
        self.grid.BeginBatch()
        self.grid.InsertRows(row + 1, len(newdata))
        data = self.ti1.queryv1("DATA")
        if hasattr(self, "preview"):
            self.preview.BeginBatch()
        data_format = self.ti1.queryv1("DATA_FORMAT")
        data.moveby1(row + 1, len(newdata))
        for i in range(len(newdata)):
            dataset = CGATS.CGATS()
            for label in data_format.values():
                label = label.decode("utf-8")
                if label not in newdata[i]:
                    newdata[i][label] = 0.0
                dataset[label] = newdata[i][label]
            dataset.key = row + 1 + i
            dataset.parent = data
            dataset.root = data.root
            dataset.type = b"SAMPLE"
            data[dataset.key] = dataset
            for label in ("RGB_R", "RGB_G", "RGB_B"):
                for col in range(self.grid.GetNumberCols()):
                    if self.label_b2a.get(self.grid.GetColLabelValue(col)) == label:
                        sample = newdata[i]
                        self.grid.SetCellValue(
                            row + 1 + i,
                            col,
                            CGATS.rpad(
                                sample[label],
                                data.vmaxlen + (1 if sample[label] < 0 else 0),
                            ),
                        )
            self.tc_grid_setcolorlabel(row + 1 + i, data)
        self.tc_preview_update(row + 1)
        self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
        dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
        dc.SetFont(self.grid.GetLabelFont())
        w, h = dc.GetTextExtent("99%s" % self.tc_amount)
        self.grid.SetRowLabelSize(max(w, self.grid.GetDefaultRowSize()))
        self.resize_grid()
        self.grid.EndBatch()
        self.tc_set_default_status()
        self.tc_save_check()
        if hasattr(self, "preview"):
            self.preview.EndBatch()

    def tc_grid_setcolorlabel(self, row, data=None):
        grid = self.grid
        col = grid.GetNumberCols() - 1
        if data is None:
            data = self.ti1.queryv1("DATA")
        sample = data[row]
        style, colour, labeltext, labelcolour = self.tc_getcolorlabel(sample)
        grid.SetCellBackgroundColour(row, col, colour)
        grid.SetCellValue(row, col, labeltext)
        if labelcolour:
            grid.SetCellTextColour(row, col, labelcolour)
        self.grid.Refresh()
        if hasattr(self, "preview"):
            style, colour, labeltext, labelcolour = self.tc_getcolorlabel(sample)
            numcols = self.preview.GetNumberCols()
            row = sample.key / numcols
            col = sample.key % numcols
            if row > self.preview.GetNumberRows() - 1:
                self.preview.AppendRows(1)
            self.preview.SetCellBackgroundColour(row, col, colour)
            self.preview.SetCellValue(row, col, labeltext)
            if labelcolour:
                self.preview.SetCellTextColour(row, col, labelcolour)
            self.preview.Refresh()

    def tc_getcolorlabel(self, sample):
        colour = wx.Colour(
            *[
                int(round(value / 100.0 * 255))
                for value in (sample.RGB_R, sample.RGB_G, sample.RGB_B)
            ]
        )
        # mark patches:
        # W = white (R/G/B == 100)
        # K = black (R/G/B == 0)
        # k = light black (R == G == B > 0)
        # R = red
        # r = light red (R == 100 and G/B > 0)
        # G = green
        # g = light green (G == 100 and R/B > 0)
        # B = blue
        # b = light blue (B == 100 and R/G > 0)
        # C = cyan
        # c = light cyan (G/B == 100 and R > 0)
        # M = magenta
        # m = light magenta (R/B == 100 and G > 0)
        # Y = yellow
        # y = light yellow (R/G == 100 and B > 0)
        # border = 50% value
        style = wx.NO_BORDER
        if sample.RGB_R == sample.RGB_G == sample.RGB_B:  # Neutral / black / white
            if sample.RGB_R < 50:
                labelcolour = wx.Colour(255, 255, 255)
            else:
                if sample.RGB_R == 50:
                    style = wx.SIMPLE_BORDER
                labelcolour = wx.Colour(0, 0, 0)
            if sample.RGB_R <= 50:
                labeltext = "K"
            elif sample.RGB_R == 100:
                labeltext = "W"
            else:
                labeltext = "k"
        elif (sample.RGB_G == 0 and sample.RGB_B == 0) or (
            sample.RGB_R == 100 and sample.RGB_G == sample.RGB_B
        ):  # Red
            if sample.RGB_R > 75:
                labelcolour = wx.Colour(0, 0, 0)
            else:
                labelcolour = wx.Colour(255, 255, 255)
                if sample.RGB_R == 50:
                    style = wx.SIMPLE_BORDER
            if sample.RGB_R == 100 and sample.RGB_G > 0:
                labeltext = "r"
            else:
                labeltext = "R"
        elif (sample.RGB_R == 0 and sample.RGB_B == 0) or (
            sample.RGB_G == 100 and sample.RGB_R == sample.RGB_B
        ):  # Green
            if sample.RGB_G > 75:
                labelcolour = wx.Colour(0, 0, 0)
            else:
                labelcolour = wx.Colour(255, 255, 255)
                if sample.RGB_G == 50:
                    style = wx.SIMPLE_BORDER
            if sample.RGB_G == 100 and sample.RGB_R > 0:
                labeltext = "g"
            else:
                labeltext = "G"
        elif (sample.RGB_R == 0 and sample.RGB_G == 0) or (
            sample.RGB_B == 100 and sample.RGB_R == sample.RGB_G
        ):  # Blue
            if sample.RGB_R > 25:
                labelcolour = wx.Colour(0, 0, 0)
            else:
                labelcolour = wx.Colour(255, 255, 255)
                if sample.RGB_B == 50:
                    style = wx.SIMPLE_BORDER
            if sample.RGB_B == 100 and sample.RGB_R > 0:
                labeltext = "b"
            else:
                labeltext = "B"
        elif (
            sample.RGB_R == 0 or sample.RGB_B == 100
        ) and sample.RGB_G == sample.RGB_B:  # Cyan
            if sample.RGB_G > 75:
                labelcolour = wx.Colour(0, 0, 0)
            else:
                labelcolour = wx.Colour(255, 255, 255)
                if sample.RGB_G == 50:
                    style = wx.SIMPLE_BORDER
            if sample.RGB_G == 100 and sample.RGB_R > 0:
                labeltext = "c"
            else:
                labeltext = "C"
        elif (
            sample.RGB_G == 0 or sample.RGB_R == 100
        ) and sample.RGB_R == sample.RGB_B:  # Magenta
            if sample.RGB_R > 75:
                labelcolour = wx.Colour(0, 0, 0)
            else:
                labelcolour = wx.Colour(255, 255, 255)
                if sample.RGB_R == 50:
                    style = wx.SIMPLE_BORDER
            if sample.RGB_R == 100 and sample.RGB_G > 0:
                labeltext = "m"
            else:
                labeltext = "M"
        elif (
            sample.RGB_B == 0 or sample.RGB_G == 100
        ) and sample.RGB_R == sample.RGB_G:  # Yellow
            if sample.RGB_G > 75:
                labelcolour = wx.Colour(0, 0, 0)
            else:
                labelcolour = wx.Colour(255, 255, 255)
                if sample.RGB_R == 100 and sample.RGB_G == 50:
                    style = wx.SIMPLE_BORDER
            if sample.RGB_B > 0:
                labeltext = "y"
            else:
                labeltext = "Y"
        else:
            labeltext = ""
            labelcolour = None
        return style, colour, labeltext, labelcolour

    def tc_set_default_status(self, event=None):
        if hasattr(self, "tc_amount"):
            statustxt = "%s: %s" % (lang.getstr("tc.patches.total"), self.tc_amount)
            sel = self.grid.GetSelectionRows()
            if sel:
                statustxt += " / %s: %s" % (
                    lang.getstr("tc.patches.selected"),
                    len(sel),
                )
                index = self.grid.GetGridCursorRow()
                if index > -1:
                    colour = self.grid.GetCellBackgroundColour(index, 3)
                    patchinfo = " \u2014 %s %s: R=%s G=%s B=%s" % (
                        lang.getstr("tc.patch"),
                        index + 1,
                        colour[0],
                        colour[1],
                        colour[2],
                    )
                    statustxt += patchinfo
            self.SetStatusText(statustxt)

    def tc_mouseclick_handler(self, event):
        if not getattr(self, "ti1", None):
            return
        index = event.Row * self.preview.GetNumberCols() + event.Col
        if index > self.ti1.queryv1("NUMBER_OF_SETS") - 1:
            return
        self.grid.select_row(
            index, event.ShiftDown(), event.ControlDown() or event.CmdDown()
        )
        return

    def tc_delete_rows(self, rows):
        self.grid.BeginBatch()
        if hasattr(self, "preview"):
            self.preview.BeginBatch()
        rows.sort()
        rows.reverse()
        data = self.ti1.queryv1("DATA")
        # Optimization: Delete consecutive rows in least number of operations
        consecutive = []
        rows.append(-1)
        for row in rows:
            if row == -1 or (consecutive and consecutive[-1] != row + 1):
                self.grid.DeleteRows(consecutive[-1], len(consecutive))
                if consecutive[0] != len(data) - 1:
                    data.moveby1(consecutive[-1] + len(consecutive), -len(consecutive))
                for crow in consecutive:
                    dict.pop(data, len(data) - 1)
                consecutive = []
            consecutive.append(row)
        rows.pop()
        if hasattr(self, "preview"):
            self.tc_preview_update(rows[-1])
        data.setmodified()
        self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
        row = min(rows[-1], self.grid.GetNumberRows() - 1)
        self.grid.SelectRow(row)
        self.grid.SetGridCursor(row, 0)
        self.grid.MakeCellVisible(row, 0)
        self.grid.EndBatch()
        self.tc_save_check()
        if hasattr(self, "preview"):
            self.preview.EndBatch()
        self.tc_set_default_status()

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

        self.tc_view_3d(None)

    def writecfg(self):
        if self.Parent:
            writecfg()
        else:
            writecfg(
                module="testchart-editor",
                options=(
                    "3d_format",
                    "last_ti1_path",
                    "last_testchart_export_path",
                    "last_vrml_path",
                    "position.tcgen",
                    "size.tcgen",
                    "tc.",
                    "tc_",
                ),
            )


def main():
    config.initcfg("testchart-editor")
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = TestchartEditor(setup=False)
    if sys.platform == "darwin":
        app.TopWindow.init_menubar()
    wx.CallLater(1, _main, app)
    app.MainLoop()


def _main(app):
    app.TopWindow.listen()
    app.TopWindow.setup(path=False)
    app.process_argv(1) or app.TopWindow.tc_load_cfg_from_ti1()
    app.TopWindow.Show()


if __name__ == "__main__":
    main()
