# -*- coding: utf-8 -*-

import math
import os
import sys
import time
import warnings

from DisplayCAL import (
    config,
    localization as lang,
)
from DisplayCAL.config import (
    defaults,
    enc,
    get_argyll_display_number,
    get_default_dpi,
    get_display_number,
    get_display_rects,
    getcfg,
    geticon,
    scale_adjustment_factor,
    setcfg,
    writecfg,
)
from DisplayCAL.debughelpers import handle_error
from DisplayCAL.meta import (
    name as appname,
)
from DisplayCAL.options import debug
from DisplayCAL.util_list import floatlist, strlist
from DisplayCAL.wxaddons import wx
from DisplayCAL.wxfixes import (
    GenBitmapButton as BitmapButton,
)
from DisplayCAL.wxwindows import (
    BaseApp,
    BitmapBackgroundPanel,
    ConfirmDialog,
    InfoDialog,
    InvincibleFrame,
)

try:
    from DisplayCAL import RealDisplaySizeMM as RDSMM
except ImportError as exception:
    RDSMM = None
    warnings.warn(str(exception), Warning)


def get_default_size():
    """Get and return the default size for the window in pixels.

    The default size is always equivalent to 100 x 100 mm according
    to the display's size as returned by the RealDisplaySizeMM function,
    which uses the same code as Argyll to determine that size.

    This function is used internally.
    """
    display_sizes = []
    display_sizes_mm = []
    for display_no in range(len(getcfg("displays"))):
        display_no = get_display_number(display_no)
        display_size = wx.Display(display_no).Geometry[2:]
        display_size_mm = []
        if RDSMM:
            try:
                display_size_mm = RDSMM.RealDisplaySizeMM(display_no)
            except Exception as exception:
                handle_error(
                    "Error - RealDisplaySizeMM() failed: %s" % exception, silent=True
                )
            else:
                display_size_mm = floatlist(display_size_mm)
        if debug:
            print("[D]  display_size_mm:", display_size_mm)
        if not len(display_size_mm) or 0 in display_size_mm:
            ppi_def = get_default_dpi()
            method = 1
            if method == 0:
                # use configurable screen diagonal
                inch = 20.0
                mm = inch * 25.4
                f = mm / math.sqrt(
                    math.pow(display_size[0], 2) + math.pow(display_size[1], 2)
                )
                w_mm = math.sqrt(math.pow(mm, 2) - math.pow(display_size[1] * f, 2))
                h_mm = math.sqrt(math.pow(mm, 2) - math.pow(display_size[0] * f, 2))
                display_size_mm = w_mm, h_mm
            elif method == 1:
                # use the first display
                display_size_1st = wx.DisplaySize()
                display_size_mm = floatlist(wx.DisplaySizeMM())
                if 0 in display_size_mm:
                    # bogus
                    display_size_mm = [
                        float(display_size_1st[0]) / ppi_def * 25.4,
                        float(display_size_1st[1]) / ppi_def * 25.4,
                    ]
                if display_no > 0:
                    display_size_mm[0] = float(display_size[0]) / (
                        display_size_1st[0] / display_size_mm[0]
                    )
                    display_size_mm[1] = float(display_size[1]) / (
                        display_size_1st[1] / display_size_mm[1]
                    )
            else:
                # use assumed ppi
                display_size_mm = (
                    float(display_size[0]) / ppi_def * 25.4,
                    float(display_size[1]) / ppi_def * 25.4,
                )
        display_sizes.append(display_size)
        display_sizes_mm.append(display_size_mm)
    if (
        sum(mm[0] for mm in display_sizes_mm) / len(display_sizes_mm)
        == display_sizes_mm[0][0]
        and sum(mm[1] for mm in display_sizes_mm) / len(display_sizes_mm)
        == display_sizes_mm[0][1]
    ):
        # display_size_mm is the same for all screens, use the 1st one
        display_size = display_sizes[0]
        display_size_mm = display_sizes_mm[0]
    else:
        if getcfg("display_lut.link"):
            display_no = getcfg("display.number") - 1
        else:
            display_no = getcfg("display_lut.number") - 1
        display_size = display_sizes[display_no]
        display_size_mm = display_sizes_mm[display_no]
    px_per_mm = (
        display_size[0] / display_size_mm[0],
        display_size[1] / display_size_mm[1],
    )
    if debug:
        print("[D]  H px_per_mm:", px_per_mm[0])
        print("[D]  V px_per_mm:", px_per_mm[1])
    return round(100.0 * max(px_per_mm))


class MeasureFrame(InvincibleFrame):
    """A rectangular window to set the measure area size for dispcal/dispread."""

    exitcode = 1

    def __init__(self, parent=None, id=-1):
        style = wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        if os.getenv("XDG_SESSION_TYPE") != "wayland" and getcfg(
            "patterngenerator.use_pattern_window"
        ):
            style |= wx.STAY_ON_TOP
        InvincibleFrame.__init__(
            self,
            parent,
            id,
            lang.getstr("measureframe.title"),
            style=style,
            name="measureframe",
        )
        self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
        self.Bind(wx.EVT_CLOSE, self.close_handler, self)
        if os.getenv("XDG_SESSION_TYPE") != "wayland":
            self.Bind(wx.EVT_MOVE, self.move_handler, self)
        self.Bind(wx.EVT_SHOW, self.show_handler)
        self.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
        self.Bind(wx.EVT_SET_FOCUS, self.focus_handler)
        self.panel = BitmapBackgroundPanel(self)
        self.panel.scalebitmap = (False, False)

        if os.getenv("XDG_SESSION_TYPE") == "wayland":
            self.sizer = wx.FlexGridSizer(3, 1, 0, 0)
            self.sizer.AddGrowableCol(0)
            self.sizer.AddGrowableRow(1)
        else:
            self.sizer = wx.GridSizer(3, 1, 0, 0)
        self.panel.SetSizer(self.sizer)

        self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.hsizer, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_TOP)

        self.zoommaxbutton = BitmapButton(
            self.panel,
            -1,
            geticon(16, "zoom-best-fit"),
            style=wx.NO_BORDER,
            name="zoommaxbutton",
        )
        self.zoommaxbutton.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
        self.Bind(wx.EVT_BUTTON, self.zoommax_handler, self.zoommaxbutton)
        self.hsizer.Add(
            self.zoommaxbutton,
            flag=wx.ALIGN_CENTER | wx.LEFT | wx.TOP | wx.BOTTOM,
            border=10,
        )
        self.zoommaxbutton.SetToolTipString(lang.getstr("measureframe.zoommax"))

        self.hsizer.Add((8, 0))

        self.zoominbutton = BitmapButton(
            self.panel,
            -1,
            geticon(16, "zoom-in"),
            style=wx.NO_BORDER,
            name="zoominbutton",
        )
        self.zoominbutton.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
        self.Bind(wx.EVT_BUTTON, self.zoomin_handler, self.zoominbutton)
        self.hsizer.Add(
            self.zoominbutton, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10
        )
        self.zoominbutton.SetToolTipString(lang.getstr("measureframe.zoomin"))

        self.hsizer.Add((8, 0))

        self.zoomnormalbutton = BitmapButton(
            self.panel,
            -1,
            geticon(16, "zoom-original"),
            style=wx.NO_BORDER,
            name="zoomnormalbutton",
        )
        self.zoomnormalbutton.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
        self.Bind(wx.EVT_BUTTON, self.zoomnormal_handler, self.zoomnormalbutton)
        self.hsizer.Add(
            self.zoomnormalbutton, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10
        )
        self.zoomnormalbutton.SetToolTipString(
            lang.getstr("measureframe." "zoomnormal")
        )

        self.hsizer.Add((8, 0))

        self.zoomoutbutton = BitmapButton(
            self.panel,
            -1,
            geticon(16, "zoom-out"),
            style=wx.NO_BORDER,
            name="zoomoutbutton",
        )
        self.zoomoutbutton.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
        self.Bind(wx.EVT_BUTTON, self.zoomout_handler, self.zoomoutbutton)
        self.hsizer.Add(
            self.zoomoutbutton,
            flag=wx.ALIGN_CENTER | wx.RIGHT | wx.TOP | wx.BOTTOM,
            border=10,
        )
        self.zoomoutbutton.SetToolTipString(lang.getstr("measureframe.zoomout"))

        if os.getenv("XDG_SESSION_TYPE") == "wayland":
            # No manual centering under Wayland...
            self.centermsg = wx.StaticText(
                self.panel,
                -1,
                lang.getstr("measureframe.center.manual"),
                style=wx.ALIGN_CENTER_HORIZONTAL,
            )
            self.centermsg.Wrap(self.hsizer.MinSize[0] - 20)
            self.sizer.Add(
                self.centermsg, flag=wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border=10
            )
        else:
            self.centerbutton = BitmapButton(
                self.panel,
                -1,
                geticon(16, "window-center"),
                style=wx.NO_BORDER,
                name="centerbutton",
            )
            self.centerbutton.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
            self.Bind(wx.EVT_BUTTON, self.center_handler, self.centerbutton)
            self.sizer.Add(
                self.centerbutton, flag=wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border=10
            )
            self.centerbutton.SetToolTipString(lang.getstr("measureframe.center"))

        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.vsizer, flag=wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL)

        if os.getenv("XDG_SESSION_TYPE") != "wayland" or config.is_virtual_display():
            self.measure_darken_background_cb = wx.CheckBox(
                self.panel, -1, lang.getstr("measure.darken_background")
            )
            self.measure_darken_background_cb.SetValue(
                bool(int(getcfg("measure.darken_background")))
            )
            self.measure_darken_background_cb.Bind(
                wx.EVT_KILL_FOCUS, self.focus_lost_handler
            )
            self.Bind(
                wx.EVT_CHECKBOX,
                self.measure_darken_background_ctrl_handler,
                id=self.measure_darken_background_cb.GetId(),
            )
            self.vsizer.Add(
                self.measure_darken_background_cb,
                # flag=wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT | wx.TOP,
                flag=wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT,
                border=10,
            )
        else:
            self.vsizer.Add((10, 10))

        self.measurebutton = wx.Button(
            self.panel,
            -1,
            lang.getstr("measureframe.measurebutton"),
            name="measurebutton",
        )
        self.measurebutton.Bind(wx.EVT_KILL_FOCUS, self.focus_lost_handler)
        self.Bind(wx.EVT_BUTTON, self.measure_handler, self.measurebutton)
        self.vsizer.Add(
            self.measurebutton,
            # flag=wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL,
            flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL,
            border=10,
        )
        self.measurebutton.SetMaxFontSize(11)
        self.measurebutton.SetDefault()
        self.last_focused = self.measurebutton

        self.display_no = wx.Display.GetFromWindow(self)
        self.display_rects = get_display_rects()

        self.sizer.SetSizeHints(self)

    def measure_darken_background_ctrl_handler(self, event):
        if self.measure_darken_background_cb.GetValue() and getcfg(
            "measure.darken_background.show_warning"
        ):
            dlg = ConfirmDialog(
                self,
                msg=lang.getstr("measure.darken_background.warning"),
                ok=lang.getstr("ok"),
                cancel=lang.getstr("cancel"),
                bitmap=geticon(32, "dialog-warning"),
            )
            chk = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
            dlg.Bind(
                wx.EVT_CHECKBOX,
                self.measure_darken_background_warning_handler,
                id=chk.GetId(),
            )
            dlg.sizer3.Add(chk, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
            dlg.sizer0.SetSizeHints(dlg)
            dlg.sizer0.Layout()
            rslt = dlg.ShowModal()
            if rslt == wx.ID_CANCEL:
                self.measure_darken_background_cb.SetValue(False)
        setcfg(
            "measure.darken_background",
            int(self.measure_darken_background_cb.GetValue()),
        )

    def measure_darken_background_warning_handler(self, event):
        setcfg(
            "measure.darken_background.show_warning",
            int(not event.GetEventObject().GetValue()),
        )

    def info_handler(self, event):
        InfoDialog(
            self,
            msg=lang.getstr("measureframe.info"),
            ok=lang.getstr("ok"),
            bitmap=geticon(32, "dialog-information"),
            log=False,
        )

    def measure_handler(self, event):
        if self.Parent and hasattr(self.Parent, "call_pending_function"):
            self.Parent.call_pending_function()
        else:
            MeasureFrame.exitcode = 255
            self.Close()

    def Show(self, show=True):
        if show:
            self.show_controls()
            if hasattr(self, "measure_darken_background_cb"):
                self.measure_darken_background_cb.SetValue(
                    bool(int(getcfg("measure.darken_background")))
                )
            if self.Parent and hasattr(self.Parent, "display_ctrl"):
                display_no = self.Parent.display_ctrl.GetSelection()
            else:
                display_no = getcfg("display.number") - 1
            if display_no < 0 or display_no > wx.Display.GetCount() - 1:
                display_no = 0
            else:
                display_no = get_display_number(display_no)
            x, y = wx.Display(display_no).Geometry[:2]
            self.SetPosition((x, y))  # place measure frame on correct display
            self.place_n_zoom(*floatlist(getcfg("dimensions.measureframe").split(",")))
            self.display_no = wx.Display.GetFromWindow(self)
        elif self.IsShownOnScreen():
            setcfg("dimensions.measureframe", self.get_dimensions())
            if self.Parent and hasattr(self.Parent, "get_set_display"):
                self.Parent.get_set_display()
        if isinstance(self, wx.Dialog):
            if show:
                self.ShowModal()
            else:
                if self.IsModal():
                    self.EndModal(wx.ID_OK)
                else:
                    wx.Dialog.Hide(self)
        else:
            wx.Frame.Show(self, show)

    def Hide(self):
        self.Show(False)

    def place_n_zoom(self, x=None, y=None, scale=None):
        """Place and scale the window.

        x, y and scale need to be in Argyll coordinates (0.0...1.0)
        if given. Without arguments, they are read from the user
        configuration.

        """
        if debug:
            print("[D] measureframe.place_n_zoom")
        if None in (x, y, scale):
            cur_x, cur_y, cur_scale = floatlist(self.get_dimensions().split(","))
            if x is None:
                x = cur_x
            if y is None:
                y = cur_y
            if scale is None:
                scale = cur_scale
        scale = min(scale, 50.0)  # Argyll max
        if debug:
            print("[D]  x:", x)
            print("[D]  y:", y)
            print("[D]  scale:", scale)
            print("[D]  scale_adjustment_factor:", scale_adjustment_factor)
        scale /= float(scale_adjustment_factor)
        if debug:
            print("[D]  scale / scale_adjustment_factor:", scale)
        display = self.get_display(getcfg("display.number") - 1)
        display_client_rect = display[2]
        display_client_size = display_client_rect[2:]
        if debug:
            print("[D]  display_client_rect:", display_client_rect)
            print("[D]  display_client_size:", display_client_size)
        measureframe_min_size = [max(self.sizer.GetMinSize())] * 2
        if debug:
            print("[D]  measureframe_min_size:", measureframe_min_size)
        default_measureframe_size = get_default_size()
        defaults["size.measureframe"] = default_measureframe_size
        size = [
            min(display_client_size[0], default_measureframe_size * scale),
            min(display_client_size[1], default_measureframe_size * scale),
        ]
        if measureframe_min_size[0] > size[0]:
            size = measureframe_min_size
        if size[0] > display_client_size[0]:
            size[0] = display_client_size[0]
        if size[1] > display_client_size[1]:
            size[1] = display_client_size[1]
        if max(size) >= max(display_client_size):
            scale = 50
        if debug:
            print("[D]  measureframe_size:", size)
        size[0] = size[1] = int(max(size))
        if (
            sys.platform not in ("darwin", "win32")
            and os.getenv("XDG_SESSION_TYPE") != "wayland"
            and not os.getenv("XDG_CURRENT_DESKTOP", "").startswith("KDE")
            and hasattr(self, "MaxClientSize")
        ):
            self.SetMaxClientSize((-1, -1))
            self.SetMinClientSize(size)
            self.SetClientSize(size)
            self.SetMaxClientSize(size)
        else:
            self.SetMaxSize((-1, -1))
            self.SetMinSize(size)
            self.SetSize(size)
            self.SetMaxSize(size)
        display_rect = display[1]
        if debug:
            print("[D]  display_rect:", display_rect)
        display_size = display_rect[2:]
        if debug:
            print("[D]  display_size:", display_size)
        if sys.platform in ("darwin", "win32"):
            titlebar = 0  # size already includes window decorations
        else:
            titlebar = 25  # assume titlebar height of 25px
        measureframe_pos = [
            display_rect[0] + round((display_size[0] - size[0]) * x),
            display_rect[1] + round((display_size[1] - size[1]) * y) - titlebar,
        ]
        if measureframe_pos[0] < display_client_rect[0]:
            measureframe_pos[0] = display_client_rect[0]
        if measureframe_pos[1] < display_client_rect[1]:
            measureframe_pos[1] = display_client_rect[1]
        if debug:
            print("[D]  measureframe_pos:", measureframe_pos)
        setcfg("dimensions.measureframe", ",".join(strlist((x, y, scale))))
        self.SetPosition(measureframe_pos)

    def zoomin_handler(self, event):
        if debug:
            print("[D] measureframe_zoomin_handler")
        # We can't use self.get_dimensions() here because if we are near
        # fullscreen, next magnification step will be larger than normal
        display_size = self.get_display()[1][2:]
        default_measureframe_size = float(get_default_size())
        size = floatlist(self.GetSize())
        x, y = None, None
        scale = (float(display_size[0]) / default_measureframe_size) / (
            float(display_size[0]) / size[0]
        ) + 0.125
        self.place_n_zoom(
            x,
            y,
            scale=scale,
        )

    def zoomout_handler(self, event):
        if debug:
            print("[D] measureframe_zoomout_handler")
        # We can't use self.get_dimensions() here because if we are
        # fullscreen, scale will be 50, thus changes won't be visible quickly
        display_size = self.get_display()[1][2:]
        default_measureframe_size = float(get_default_size())
        size = floatlist(self.GetSize())
        x, y = None, None
        scale = (float(display_size[0]) / default_measureframe_size) / (
            float(display_size[0]) / size[0]
        ) - 0.125
        self.place_n_zoom(
            x,
            y,
            scale=scale,
        )

    def zoomnormal_handler(self, event):
        if debug:
            print("[D] measureframe_zoomnormal_handler")
        x, y = None, None
        scale = floatlist(defaults["dimensions.measureframe"].split(","))[2]
        self.place_n_zoom(x, y, scale=scale)

    def zoommax_handler(self, event):
        if debug:
            print("[D] measureframe_zoommax_handler")
        display_client_rect = self.get_display()[2]
        if debug:
            print("[D]  display_client_rect:", display_client_rect)
        display_client_size = display_client_rect[2:]
        if debug:
            print("[D]  display_client_size:", display_client_size)
        size = self.GetSize()
        if debug:
            print(" size:", size)
        if max(size) >= max(display_client_size) - 50:
            dim = getcfg("dimensions.measureframe.unzoomed")
            self.place_n_zoom(*floatlist(dim.split(",")))
        else:
            setcfg("dimensions.measureframe.unzoomed", self.get_dimensions())
            self.place_n_zoom(x=0.5, y=0.5, scale=50.0)

    def center_handler(self, event):
        if debug:
            print("[D] measureframe_center_handler")
        x, y = floatlist(defaults["dimensions.measureframe"].split(","))[:2]
        self.place_n_zoom(x, y)

    def close_handler(self, event):
        if debug:
            print("[D] measureframe_close_handler")
        if self.Parent:
            if self.Parent.worker.is_working():
                self.Parent.worker.abort_subprocess(confirm=True)
                return
            self.Hide()
            self.Parent.Show()
            if getattr(self.Parent, "restore_measurement_mode"):
                self.Parent.restore_measurement_mode()
            if getattr(self.Parent, "restore_testchart"):
                self.Parent.restore_testchart()
        else:
            self.Hide()
            writecfg()
            self.Destroy()
            if MeasureFrame.exitcode != 255:
                MeasureFrame.exitcode = 0

    def get_display(self, display_no=None):
        """Get the display number, geometry and client area, taking into
        account separate X screens, TwinView and similar

        """
        if wx.Display.GetCount() == 1 and len(self.display_rects) > 1:
            # Separate X screens, TwinView or similar
            display = wx.Display(0)
            geometry = display.Geometry
            union = wx.Rect()
            xy = []
            for rect in self.display_rects:
                if rect[:2] in xy or rect[2:] == geometry[2:]:
                    # Overlapping x y coordinates or screen filling whole
                    # reported geometry, so assume separate X screens
                    union = None
                    break
                xy.append(rect[:2])
                union = union.Union(rect)
            if union == geometry:
                # Assume TwinView or similar where Argyll enumerates 1+n
                # displays but wx only 'sees' one that is the union of them
                framerect = self.Rect
                if display_no is not None:
                    geometry = self.display_rects[display_no]
                else:
                    display_no = 0
                    for i, coord in enumerate(framerect[:2]):
                        if coord < 0:
                            framerect[i] = 0
                        elif coord > geometry[i + 2]:
                            framerect[i] = geometry[i]
                    for i, display_rect in enumerate(self.display_rects):
                        if display_rect.Contains(framerect[:2]):
                            display_no = i
                            geometry = display_rect
                            break
            elif display_no is None:
                # Assume separate X screens
                display_no = 0
            client_rect = wx.Rect(*tuple(geometry)).Intersect(
                display.GetRealClientArea()
            )
        else:
            display_no = wx.Display.GetFromWindow(self)
            display = self.GetDisplay()
            geometry = display.Geometry
            client_rect = display.GetRealClientArea()
        return display_no, geometry, client_rect

    def move_handler(self, event):
        if not self.IsShownOnScreen():
            return
        display_no, geometry, client_area = self.get_display()
        if display_no != self.display_no:
            self.display_no = display_no
            if config.is_virtual_display():
                return
            # Translate from wx display index to Argyll display index
            n = get_argyll_display_number(geometry)
            if n is not None:
                # Save Argyll display index to configuration
                setcfg("display.number", n + 1)

    def focus_handler(self, event=None):
        event.Skip()
        if debug:
            print("SET_FOCUS", event.EventObject.Name)
        if event.EventObject is self and getattr(self, "last_focused", None) not in (
            None,
            self,
        ):
            self.last_focused.SetFocus()
            if debug:
                print(self.last_focused.Name + ".SetFocus()")

    def focus_lost_handler(self, e):
        e.Skip()
        if debug:
            print("KILL_FOCUS", e.EventObject.Name)
        if e.EventObject is not self:
            self.last_focused = e.EventObject
            if debug and self.last_focused:
                print("last_focused", self.last_focused.Name)

    def show_handler(self, e):
        e.Skip()
        if getattr(e, "IsShown", getattr(e, "GetShow", bool))():
            self.measurebutton.SetFocus()

    def show_controls(self, show=True):
        self.panel.Freeze()
        for ctrl in self.panel.Children:
            ctrl.Show(show)
        if show:
            self.panel.SetBitmap(None)
            self.panel.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        else:
            self.panel.SetCursor(wx.StockCursor(wx.CURSOR_BLANK))
        self.panel.Layout()
        self.panel.Thaw()

    def show_rgb(self, rgb):
        if getcfg("patterngenerator.use_video_levels"):
            minv = 16
            maxv = 235
        else:
            minv = 0
            maxv = 255
        rgb = tuple(minv + v * (maxv - minv) for v in rgb)
        floor = tuple(int(math.floor(v)) for v in rgb)
        ceil = tuple(int(math.ceil(v)) for v in rgb)
        if floor != ceil:
            # Dither using simple ordered pattern
            print(
                "Dither 8 bit %.6f %.6f %.6f -> %i %i %i | %i %i %i"
                % (rgb + floor + ceil)
            )
            img = wx.EmptyImage(*self.ClientSize, clear=False)
            buf = img.GetDataBuffer()
            buflen = len(buf)
            # Intervals in pixels per each R, G and B
            intervals = tuple(
                (buflen / (buflen * (rgb[i] - floor[i])) if rgb[i] - floor[i] else 0)
                for i in range(3)
            )
            print("Intervals %.6f %.6f %.6f" % intervals)
            floorbytes = tuple(chr(v) for v in floor)
            ceilbytes = tuple(chr(v) for v in ceil)
            n = 0
            # XXX: Generating the dithered image can take nontrivial amounts
            # of time if the image is large
            ts = time.time()
            for i, _byte in enumerate(buf):
                m = intervals[i % 3]
                if m and n % m < 1:
                    color = ceilbytes
                else:
                    color = floorbytes
                buf[i] = color[i % 3]
                if i % 3 == 2:
                    n += 1
            print("Generating dithered image took %.3fs" % (time.time() - ts))
            bmp = img.ConvertToBitmap()
        else:
            # Exact
            print("Exact 8 bit %.6f %.6f %.6f" % rgb)
            bmp = wx.EmptyBitmapRGBA(*tuple(self.ClientSize) + floor, alpha=255)
        self.panel.SetBitmap(bmp)
        self.panel.Refresh()
        if self.Parent:
            self.Parent.worker._patterngenerator_wait = False

    def get_dimensions(self):
        """Calculate and return the relative dimensions from the pixel values.

        Returns x, y and scale in Argyll coordinates (0.0...1.0).
        """
        if debug:
            print("[D] measureframe.get_dimensions")
        display = self.get_display()
        display_rect = display[1]
        display_size = display_rect[2:]
        display_client_rect = display[2]
        display_client_size = display_client_rect[2:]
        if debug:
            print("[D]  display_size:", display_size)
            print("[D]  display_client_size:", display_client_size)
        default_measureframe_size = float(get_default_size())
        if debug:
            print("[D]  default_measureframe_size:", default_measureframe_size)
        measureframe_pos = floatlist(self.GetScreenPosition())
        measureframe_pos[0] -= display_rect[0]
        measureframe_pos[1] -= display_rect[1]
        if debug:
            print("[D]  measureframe_pos:", measureframe_pos)
        size = floatlist(self.GetSize())
        if debug:
            print(" size:", size)
        if max(size) >= max(display_client_size) - 50:
            # Fullscreen?
            scale = 50.0  # Argyll max is 50
            measureframe_pos = [0.5, 0.5]
        else:
            scale = (float(display_size[0]) / default_measureframe_size) / (
                float(display_size[0]) / size[0]
            )
            if debug:
                print("[D]  scale:", scale)
                print("[D]  scale_adjustment_factor:", scale_adjustment_factor)
            scale *= float(scale_adjustment_factor)
            if size[0] >= display_client_size[0]:
                measureframe_pos[0] = 0.5
            elif measureframe_pos[0] != 0:
                if display_size[0] - size[0] < measureframe_pos[0]:
                    measureframe_pos[0] = display_size[0] - size[0]
                measureframe_pos[0] = 1.0 / (
                    (float(display_size[0]) - size[0]) / (measureframe_pos[0])
                )
            if size[1] >= display_client_size[1]:
                measureframe_pos[1] = 0.5
            elif measureframe_pos[1] != 0:
                if display_size[1] - size[1] < measureframe_pos[1]:
                    measureframe_pos[1] = display_size[1] - size[1]
                if sys.platform in ("darwin", "win32"):
                    titlebar = 0  # size already includes window decorations
                else:
                    titlebar = 25  # assume titlebar height of 25px
                measureframe_pos[1] = 1.0 / (
                    (float(display_size[1] - size[1]))
                    / (float(measureframe_pos[1] + titlebar))
                )
        if debug:
            print("[D]  scale:", scale)
        if debug:
            print("[D]  measureframe_pos:", measureframe_pos)
        measureframe_dimensions = ",".join(
            str(max(0, n)) for n in measureframe_pos + [scale]
        )
        if debug:
            print("[D]  measureframe_dimensions:", measureframe_dimensions)
        return measureframe_dimensions


def test():
    import time

    for rgb in [
        (0.079291, 1 / 51.0, 1 / 51.0),
        (0.079291, 0.089572, 0.094845),
        (0.032927, 0.028376, 0.027248),
        (0.037647, 0.037095, 0.036181),
        (51.2 / 255, 153.7 / 255, 127.4 / 255),
    ]:
        wx.CallAfter(wx.GetApp().TopWindow.show_rgb, rgb)
        time.sleep(0.05)
        input("Press RETURN to continue\n")
        if not wx.GetApp().TopWindow:
            break


def main():
    config.initcfg()
    lang.init()
    app = BaseApp(0)
    app.TopWindow = MeasureFrame()
    app.TopWindow.Show()
    if "--test-dither" in sys.argv[1:]:
        import threading

        t = threading.Thread(target=test)
        app.TopWindow.show_controls(False)
        t.start()
    app.MainLoop()


if __name__ == "__main__":
    main()
    sys.exit(MeasureFrame.exitcode)
