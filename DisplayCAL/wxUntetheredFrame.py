# -*- coding: UTF-8 -*-
"""
Interactive display calibration UI
"""

import os
import re
import sys
import time

from DisplayCAL.cgats import CGATS
from DisplayCAL.config import (
    getbitmap,
    getcfg,
    geticon,
    get_data_path,
    get_icon_bundle,
    setcfg,
)
from DisplayCAL.log import get_file_logger
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug, test, verbose
from DisplayCAL.wxaddons import wx
from DisplayCAL.wxwindows import (
    BaseApp,
    BaseFrame,
    BitmapBackgroundPanel,
    CustomCheckBox,
    CustomGrid,
    FlatShadedButton,
    numpad_keycodes,
    nav_keycodes,
    processing_keycodes,
    wx_Panel,
)
from DisplayCAL import audio
from DisplayCAL import colormath
from DisplayCAL import config
from DisplayCAL import localization as lang

BGCOLOUR = wx.Colour(0x33, 0x33, 0x33)
FGCOLOUR = wx.Colour(0x99, 0x99, 0x99)


class UntetheredFrame(BaseFrame):
    def __init__(self, parent=None, handler=None, keyhandler=None, start_timer=True):
        # BaseFrame.__init__(self, parent, wx.ID_ANY,
        #                    lang.getstr("measurement.untethered"),
        #                    style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
        #                    name="untetheredframe")
        BaseFrame.__init__(
            self,
            parent,
            wx.ID_ANY,
            lang.getstr("measurement.untethered"),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
            name="untetheredframe",
        )
        self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))
        self.sizer = wx.FlexGridSizer(2, 1, 0, 0)
        self.sizer.AddGrowableCol(0)
        self.sizer.AddGrowableRow(0)
        self.sizer.AddGrowableRow(1)
        self.panel = wx_Panel(self)
        self.SetSizer(self.sizer)
        self.sizer.Add(self.panel, 1, wx.EXPAND)
        self.panel.SetBackgroundColour(BGCOLOUR)
        panelsizer = wx.FlexGridSizer(3, 2, 8, 8)
        panelsizer.AddGrowableCol(0)
        panelsizer.AddGrowableCol(1)
        panelsizer.AddGrowableRow(1)
        self.panel.SetSizer(panelsizer)
        self.label_RGB = wx.StaticText(self.panel, wx.ID_ANY, " ")
        self.label_RGB.SetForegroundColour(FGCOLOUR)
        panelsizer.Add(self.label_RGB, 0, wx.TOP | wx.LEFT | wx.EXPAND, border=8)
        self.label_XYZ = wx.StaticText(self.panel, wx.ID_ANY, " ")
        self.label_XYZ.SetForegroundColour(FGCOLOUR)
        panelsizer.Add(self.label_XYZ, 0, wx.TOP | wx.RIGHT | wx.EXPAND, border=8)
        if sys.platform == "darwin":
            style = wx.BORDER_THEME
        else:
            style = wx.BORDER_SIMPLE
        self.panel_RGB = BitmapBackgroundPanel(self.panel, size=(256, 256), style=style)
        self.panel_RGB.scalebitmap = (True, True)
        self.panel_RGB.SetBitmap(getbitmap("theme/checkerboard-32x32x5-333-444"))
        panelsizer.Add(self.panel_RGB, 1, wx.LEFT | wx.EXPAND, border=8)
        self.panel_XYZ = BitmapBackgroundPanel(self.panel, size=(256, 256), style=style)
        self.panel_XYZ.scalebitmap = (True, True)
        self.panel_XYZ.SetBitmap(getbitmap("theme/checkerboard-32x32x5-333-444"))
        panelsizer.Add(self.panel_XYZ, 1, wx.RIGHT | wx.EXPAND, border=8)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.back_btn = FlatShadedButton(
            self.panel, bitmap=geticon(10, "back"), label="", fgcolour=FGCOLOUR
        )
        self.back_btn.Bind(wx.EVT_BUTTON, self.back_btn_handler)
        sizer.Add(self.back_btn, 0, wx.LEFT | wx.RIGHT, border=8)
        self.label_index = wx.StaticText(self.panel, wx.ID_ANY, " ")
        self.label_index.SetForegroundColour(FGCOLOUR)
        sizer.Add(self.label_index, 0, wx.ALIGN_CENTER_VERTICAL)
        self.next_btn = FlatShadedButton(
            self.panel, bitmap=geticon(10, "play"), label="", fgcolour=FGCOLOUR
        )
        self.next_btn.Bind(wx.EVT_BUTTON, self.next_btn_handler)
        sizer.Add(self.next_btn, 0, wx.LEFT, border=8)
        sizer.Add((12, 1), 1)
        self.measure_auto_cb = CustomCheckBox(
            self.panel, wx.ID_ANY, lang.getstr("auto")
        )
        self.measure_auto_cb.SetForegroundColour(FGCOLOUR)
        self.measure_auto_cb.Bind(wx.EVT_CHECKBOX, self.measure_auto_ctrl_handler)
        # only vertical alignment flags can be used with a horizontal sizer
        sizer.Add(self.measure_auto_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        panelsizer.Add(sizer, 0, wx.BOTTOM | wx.EXPAND, border=8)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.measure_btn = FlatShadedButton(
            self.panel,
            bitmap=geticon(10, "play"),
            label=lang.getstr("measure"),
            fgcolour=FGCOLOUR,
        )
        self.measure_btn.Bind(wx.EVT_BUTTON, self.measure_btn_handler)
        sizer.Add(self.measure_btn, 0, wx.RIGHT, border=6)
        # Sound when measuring
        # Needs to be stereo!
        self.measurement_sound = audio.Sound(get_data_path("beep.wav"))
        self.commit_sound = audio.Sound(get_data_path("camera_shutter.wav"))
        bitmap = self.get_sound_on_off_btn_bitmap()
        self.sound_on_off_btn = FlatShadedButton(
            self.panel, bitmap=bitmap, fgcolour=FGCOLOUR
        )
        self.sound_on_off_btn.SetToolTipString(lang.getstr("measurement.play_sound"))
        self.sound_on_off_btn.Bind(wx.EVT_BUTTON, self.measurement_play_sound_handler)
        sizer.Add(self.sound_on_off_btn, 0)
        sizer.Add((12, 1), 1)
        self.finish_btn = FlatShadedButton(
            self.panel, label=lang.getstr("finish"), fgcolour=FGCOLOUR
        )
        self.finish_btn.Bind(wx.EVT_BUTTON, self.finish_btn_handler)
        sizer.Add(self.finish_btn, 0, wx.RIGHT, border=8)
        panelsizer.Add(sizer, 0, wx.BOTTOM | wx.EXPAND, border=8)

        self.grid = CustomGrid(self, -1, size=(536, 256))
        self.grid.DisableDragColSize()
        self.grid.DisableDragRowSize()
        self.grid.SetScrollRate(0, 5)
        self.grid.SetCellHighlightROPenWidth(0)
        self.grid.SetColLabelSize(self.grid.GetDefaultRowSize())
        self.grid.SetDefaultCellAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
        self.grid.draw_horizontal_grid_lines = False
        self.grid.draw_vertical_grid_lines = False
        self.grid.style = ""
        self.grid.CreateGrid(0, 9)
        self.grid.SetRowLabelSize(62)
        for i in range(9):
            if i in (3, 4):
                size = self.grid.GetDefaultRowSize()
                if i == 4:
                    attr = wx.grid.GridCellAttr()
                    attr.SetBackgroundColour(wx.Colour(0, 0, 0, 0))
                    self.grid.SetColAttr(i, attr)
            else:
                size = 62
            self.grid.SetColSize(i, size)
        for i, label in enumerate(["R", "G", "B", "", "", "L*", "a*", "b*", ""]):
            self.grid.SetColLabelValue(i, label)
        self.grid.SetCellHighlightPenWidth(0)
        self.grid.SetDefaultCellBackgroundColour(self.grid.GetLabelBackgroundColour())
        font = self.grid.GetDefaultCellFont()
        if font.PointSize > 11:
            font.PointSize = 11
            self.grid.SetDefaultCellFont(font)
        self.grid.SetSelectionMode(wx.grid.Grid.wxGridSelectRows)
        self.grid.EnableEditing(False)
        self.grid.EnableGridLines(False)
        self.grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.grid_left_click_handler)
        self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.grid_left_click_handler)
        self.sizer.Add(self.grid, 1, wx.EXPAND)

        self.Fit()
        self.SetMinSize(self.GetSize())

        self.keyhandler = keyhandler
        self.id_to_keycode = {}
        if sys.platform == "darwin":
            # Use an accelerator table for tab, space, 0-9, A-Z, numpad,
            # navigation keys and processing keys
            keycodes = [wx.WXK_TAB, wx.WXK_SPACE]
            keycodes.extend(list(range(ord("0"), ord("9"))))
            keycodes.extend(list(range(ord("A"), ord("Z"))))
            keycodes.extend(numpad_keycodes)
            keycodes.extend(nav_keycodes)
            keycodes.extend(processing_keycodes)
            for keycode in keycodes:
                self.id_to_keycode[wx.Window.NewControlId()] = keycode
            accels = []
            for id_ in self.id_to_keycode:
                keycode = self.id_to_keycode[id_]
                self.Bind(wx.EVT_MENU, self.key_handler, id=id_)
                accels.append((wx.ACCEL_NORMAL, keycode, id_))
                if keycode == wx.WXK_TAB:
                    accels.append((wx.ACCEL_SHIFT, keycode, id_))
            self.SetAcceleratorTable(wx.AcceleratorTable(accels))
        else:
            self.Bind(wx.EVT_CHAR_HOOK, self.key_handler)

        self.Bind(wx.EVT_KEY_DOWN, self.key_handler)

        # Event handlers
        self.Bind(wx.EVT_CLOSE, self.OnClose, self)
        self.Bind(wx.EVT_MOVE, self.OnMove, self)
        self.Bind(wx.EVT_SIZE, self.OnResize, self)
        self.timer = wx.Timer(self)
        if handler:
            self.Bind(wx.EVT_TIMER, handler, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)

        # Final initialization steps
        for child in list(self.GetAllChildren()):
            if (
                sys.platform == "win32"
                and sys.getwindowsversion() >= (6,)
                and isinstance(child, wx.Panel)
            ):
                # No need to enable double buffering under Linux and Mac OS X.
                # Under Windows, enabling double buffering on the panel seems
                # to work best to reduce flicker.
                child.SetDoubleBuffered(True)
        self.logger = get_file_logger("untethered")
        self._setup()

        self.Show()

        if start_timer:
            self.start_timer()

    def EndModal(self, returncode=wx.ID_OK):
        return returncode

    def MakeModal(self, makemodal=False):
        pass

    def OnClose(self, event):
        config.writecfg()
        if not self.timer.IsRunning():
            self.Destroy()
        else:
            self.keepGoing = False

    def OnDestroy(self, event):
        self.stop_timer()
        del self.timer
        if not hasattr(wx.Window, "UnreserveControlId"):
            return 0

        for id in self.id_to_keycode.keys():
            if id >= 0:
                continue
            try:
                wx.Window.UnreserveControlId(id)
            except wx.wxAssertionError as exception:
                print(exception)

        return 0


    def OnMove(self, event):
        if (
            self.IsShownOnScreen()
            and not self.IsIconized()
            and (not self.GetParent() or not self.GetParent().IsShownOnScreen())
        ):
            prev_x = getcfg("position.progress.x")
            prev_y = getcfg("position.progress.y")
            x, y = self.GetScreenPosition()
            if x != prev_x or y != prev_y:
                setcfg("position.progress.x", x)
                setcfg("position.progress.y", y)

    def OnResize(self, event):
        wx.CallAfter(self.resize_grid)
        event.Skip()

    def Pulse(self, msg=""):
        if msg == lang.getstr("instrument.initializing"):
            self.label_RGB.SetLabel(msg)
        return self.keepGoing, False

    def Resume(self):
        self.keepGoing = True
        self.set_sound_on_off_btn_bitmap()

    def UpdateProgress(self, value, msg=""):
        return self.Pulse(msg)

    def UpdatePulse(self, msg=""):
        return self.Pulse(msg)

    def back_btn_handler(self, event):
        if self.index > 0:
            self.update(self.index - 1)

    def enable_btns(self, enable=True, enable_measure_button=False):
        self.is_measuring = not enable and enable_measure_button
        self.back_btn.Enable(enable and self.index > 0)
        self.next_btn.Enable(enable and self.index < self.index_max)
        self.measure_btn._bitmap = geticon(
            10, {True: "play", False: "pause"}.get(enable)
        )
        self.measure_btn.Enable(enable or enable_measure_button)
        self.measure_btn.SetDefault()
        if self.measure_btn.Enabled and not isinstance(
            self.FindFocus(), (wx.Control, CustomGrid)
        ):
            self.measure_btn.SetFocus()

    def finish_btn_handler(self, event):
        self.finish_btn.Disable()
        self.cgats[0].type = b"CTI3"
        self.cgats[0].add_keyword("COLOR_REP", "RGB_XYZ")
        if self.white_XYZ[1] > 0:
            # Normalize to Y = 100
            query = self.cgats[0].DATA
            for i in query:
                XYZ = query[i]["XYZ_X"], query[i]["XYZ_Y"], query[i]["XYZ_Z"]
                XYZ = [v / self.white_XYZ[1] * 100 for v in XYZ]
                query[i]["XYZ_X"], query[i]["XYZ_Y"], query[i]["XYZ_Z"] = XYZ
            normalized = "YES"
        else:
            normalized = "NO"
        self.cgats[0].add_keyword("NORMALIZED_TO_Y_100", normalized)
        self.cgats[0].add_keyword("DEVICE_CLASS", "DISPLAY")
        self.cgats[0].add_keyword("INSTRUMENT_TYPE_SPECTRAL", "NO")
        if hasattr(self.cgats[0], "APPROX_WHITE_POINT"):
            self.cgats[0].remove_keyword("APPROX_WHITE_POINT")
        # Remove L*a*b* from DATA_FORMAT if present
        for i, label in reversed(list(self.cgats[0].DATA_FORMAT.items())):
            if label.startswith(b"LAB_"):
                self.cgats[0].DATA_FORMAT.pop(i)
        # Add XYZ to DATA_FORMAT if not yet present
        for label in (b"XYZ_X", b"XYZ_Y", b"XYZ_Z"):
            if label not in list(self.cgats[0].DATA_FORMAT.values()):
                self.cgats[0].DATA_FORMAT.add_data((label,))
        self.cgats[0].write(os.path.splitext(self.cgats.filename)[0] + ".ti3")
        self.safe_send("Q")
        time.sleep(0.5)
        self.safe_send("Q")

    def flush(self):
        pass

    def get_Lab_RGB(self):
        row = self.cgats[0].DATA[self.index]
        XYZ = row["XYZ_X"], row["XYZ_Y"], row["XYZ_Z"]
        self.last_XYZ = XYZ
        Lab = colormath.XYZ2Lab(*XYZ)
        if self.white_XYZ[1] > 0:
            XYZ = [v / self.white_XYZ[1] * 100 for v in XYZ]
            white_XYZ_Y100 = [v / self.white_XYZ[1] * 100 for v in self.white_XYZ]
            white_CCT = colormath.XYZ2CCT(*white_XYZ_Y100)
            if white_CCT:
                DXYZ = colormath.CIEDCCT2XYZ(white_CCT, scale=100.0)
                if DXYZ:
                    white_CIEDCCT_Lab = colormath.XYZ2Lab(*DXYZ)
                PXYZ = colormath.planckianCT2XYZ(white_CCT, scale=100.0)
                if PXYZ:
                    white_planckianCCT_Lab = colormath.XYZ2Lab(*PXYZ)
                white_Lab = colormath.XYZ2Lab(*white_XYZ_Y100)
                if (
                    DXYZ
                    and PXYZ
                    and (
                        colormath.delta(*white_CIEDCCT_Lab + white_Lab)["E"] < 6
                        or colormath.delta(*white_planckianCCT_Lab + white_Lab)["E"] < 6
                    )
                ):
                    # Is white close enough to daylight or planckian locus?
                    XYZ = colormath.adapt(XYZ[0], XYZ[1], XYZ[2], white_XYZ_Y100, "D65")
        X, Y, Z = [v / 100.0 for v in XYZ]
        color = [int(round(v)) for v in colormath.XYZ2RGB(X, Y, Z, scale=255)]
        return Lab, color

    def grid_left_click_handler(self, event):
        if not self.is_measuring:
            row, col = event.GetRow(), event.GetCol()
            if row == -1 and col > -1:  # col label clicked
                pass
            elif row > -1:  # row clicked
                if not (event.CmdDown() or event.ControlDown() or event.ShiftDown()):
                    self.update(row)
                event.Skip()

    def has_worker_subprocess(self):
        return bool(
            getattr(self, "worker", None) and getattr(self.worker, "subprocess", None)
        )

    def isatty(self):
        return True

    def key_handler(self, event):
        keycode = None
        is_key_event = event.GetEventType() in (
            wx.EVT_CHAR.typeId,
            wx.EVT_CHAR_HOOK.typeId,
            wx.EVT_KEY_DOWN.typeId,
        )
        if is_key_event:
            keycode = event.GetKeyCode()
        elif event.GetEventType() == wx.EVT_MENU.typeId:
            keycode = self.id_to_keycode.get(event.GetId())
        if keycode == wx.WXK_TAB:
            self.global_navigate() or event.Skip()
        elif keycode >= 0:
            if keycode in (wx.WXK_UP, wx.WXK_NUMPAD_UP):
                self.back_btn_handler(None)
            elif keycode in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
                self.next_btn_handler(None)
            elif keycode in (wx.WXK_HOME, wx.WXK_NUMPAD_HOME):
                if self.index > -1:
                    self.update(0)
            elif keycode in (wx.WXK_END, wx.WXK_NUMPAD_END):
                if self.index_max > -1:
                    self.update(self.index_max)
            elif keycode in (wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEDOWN):
                if self.index > -1:
                    self.grid.MovePageDown()
                    self.update(self.grid.GetGridCursorRow())
            elif keycode in (wx.WXK_PAGEUP, wx.WXK_NUMPAD_PAGEUP):
                if self.index > -1:
                    self.grid.MovePageUp()
                    self.update(self.grid.GetGridCursorRow())
            elif is_key_event and (event.ControlDown() or event.CmdDown()):
                event.Skip()
            elif self.has_worker_subprocess() and keycode < 256:
                if keycode == wx.WXK_ESCAPE or chr(keycode) == "Q":
                    # ESC or Q
                    self.worker.abort_subprocess()
                elif (
                    not isinstance(self.FindFocus(), wx.Control)
                    or keycode != wx.WXK_SPACE
                ):
                    # Any other key
                    self.measure_btn_handler(None)
                else:
                    event.Skip()
            else:
                event.Skip()
        else:
            event.Skip()

    def measure(self, event=None):
        self.enable_btns(False, True)
        # Use a delay to allow for TFT lag
        wx.CallLater(200, self.safe_send, " ")

    def measure_auto_ctrl_handler(self, event):
        auto = self.measure_auto_cb.GetValue()
        setcfg("untethered.measure.auto", int(auto))

    def measure_btn_handler(self, event):
        if self.is_measuring:
            self.is_measuring = False
        else:
            self.last_XYZ = (-1, -1, -1)
            self.measure_count = 1
            self.measure()

    def measurement_play_sound_handler(self, event):
        setcfg(
            "measurement.play_sound", int(not (bool(getcfg("measurement.play_sound"))))
        )
        self.set_sound_on_off_btn_bitmap()

    def get_sound_on_off_btn_bitmap(self):
        if getcfg("measurement.play_sound"):
            bitmap = geticon(16, "sound_volume_full")
        else:
            bitmap = geticon(16, "sound_off")
        return bitmap

    def set_sound_on_off_btn_bitmap(self):
        bitmap = self.get_sound_on_off_btn_bitmap()
        self.sound_on_off_btn._bitmap = bitmap

    def next_btn_handler(self, event):
        if self.index < self.index_max:
            self.update(self.index + 1)

    def parse_txt(self, txt):
        if not txt:
            return
        self.logger.info("%r" % txt)
        data_len = len(self.cgats[0].DATA)
        if self.grid.GetNumberRows() < data_len:
            self.index = 0
            self.index_max = data_len - 1
            self.grid.AppendRows(data_len - self.grid.GetNumberRows())
            for i in self.cgats[0].DATA:
                self.grid.SetRowLabelValue(i, "%i" % (i + 1))
                row = self.cgats[0].DATA[i]
                RGB = []
                for j, label in enumerate("RGB"):
                    value = int(round(row["RGB_%s" % label] / 100.0 * 255))
                    self.grid.SetCellValue(row.SAMPLE_ID - 1, j, "%i" % value)
                    RGB.append(value)
                self.grid.SetCellBackgroundColour(row.SAMPLE_ID - 1, 3, wx.Colour(*RGB))
        if "Connecting to the instrument" in txt:
            self.Pulse(lang.getstr("instrument.initializing"))
        if "Spot read needs a calibration" in txt:
            self.is_measuring = False
        if "Spot read failed" in txt:
            self.last_error = txt
        if "Result is XYZ:" in txt:
            self.last_error = None
            if getcfg("measurement.play_sound"):
                self.measurement_sound.safe_play()
            # Result is XYZ: d.dddddd d.dddddd d.dddddd, D50 Lab: d.dddddd d.dddddd d.dddddd
            XYZ = re.search(
                r"XYZ:\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", txt
            )
            if not XYZ:
                return

            def is_white(r):
                return r["RGB_R"] == 100 and r["RGB_G"] == 100 and r["RGB_B"] == 100

            XYZ = [float(v) for v in XYZ.groups()]
            row = self.cgats[0].DATA[self.index]
            if is_white(row):
                if XYZ[1] > 0:
                    self.cgats[0].add_keyword(
                        "LUMINANCE_XYZ_CDM2", "%.6f %.6f %.6f" % tuple(XYZ)
                    )
                    self.white_XYZ = XYZ
            Lab1 = colormath.XYZ2Lab(*self.last_XYZ)
            Lab2 = colormath.XYZ2Lab(*XYZ)
            delta = colormath.delta(*Lab1 + Lab2)
            if debug or test or verbose > 1:
                print("Last recorded Lab: %.4f %.4f %.4f" % Lab1)
                print("Current Lab: %.4f %.4f %.4f" % Lab2)
                print("Delta E to last recorded Lab: %.4f" % delta["E"])
                print("Abs. delta L to last recorded Lab: %.4f" % abs(delta["L"]))
                print("Abs. delta C to last recorded Lab: %.4f" % abs(delta["C"]))
            consecutive_white_patch = (
                self.index
                and is_white(row)
                and is_white(self.cgats[0].DATA[self.index - 1])
            )
            measurement_exceeds_delta = delta["E"] > getcfg("untethered.min_delta") or (
                abs(delta["L"]) > getcfg("untethered.min_delta.lightness")
                and abs(delta["C"]) < getcfg("untethered.max_delta.chroma")
            )
            if consecutive_white_patch or measurement_exceeds_delta:
                self.measure_count += 1
                if self.measure_count == 2:
                    if getcfg("measurement.play_sound"):
                        self.commit_sound.safe_play()
                    self.measure_count = 0
                    # Reset row label
                    self.grid.SetRowLabelValue(self.index, "%i" % (self.index + 1))
                    # Update CGATS
                    query = self.cgats[0].queryi1(
                        {
                            "RGB_R": row["RGB_R"],
                            "RGB_G": row["RGB_G"],
                            "RGB_B": row["RGB_B"],
                            "SAMPLE_ID": row["SAMPLE_ID"],
                        }
                    )
                    if query:
                        index = query.SAMPLE_ID - 1
                        if index not in self.measured:
                            self.measured.append(index)
                        query["XYZ_X"], query["XYZ_Y"], query["XYZ_Z"] = XYZ
                    if getcfg("untethered.measure.auto"):
                        self.show_RGB(False, False)
                    self.show_XYZ()
                    Lab, color = self.get_Lab_RGB()
                    self.grid.SetCellBackgroundColour(
                        query.SAMPLE_ID - 1, 4, wx.Colour(*color)
                    )
                    for j in range(3):
                        self.grid.SetCellValue(
                            query.SAMPLE_ID - 1, 5 + j, "%.2f" % Lab[j]
                        )
                    self.grid.MakeCellVisible(self.index, 0)
                    self.grid.ForceRefresh()
                    if len(self.measured) == data_len:
                        self.finished = True
                        self.finish_btn.Enable()
                    else:
                        # Jump to the next or previous unmeasured patch, if any
                        index = self.index
                        for i in range(self.index + 1, data_len):
                            if (
                                getcfg("untethered.measure.auto")
                                or i not in self.measured
                            ):
                                self.index = i
                                break
                        if self.index == index:
                            for i in range(self.index - 1, -1, -1):
                                if i not in self.measured:
                                    self.index = i
                                    break
                        if self.index != index:
                            # Mark the row containing the next/previous patch
                            self.grid.SetRowLabelValue(
                                self.index, "\u25ba %i" % (self.index + 1)
                            )
                            self.grid.MakeCellVisible(self.index, 0)
        if "key to take a reading" in txt and not self.last_error:
            if getcfg("untethered.measure.auto") and self.is_measuring:
                if not self.finished and self.keepGoing:
                    self.measure()
                else:
                    self.enable_btns()
            else:
                show_XYZ = self.index in self.measured
                delay = getcfg("untethered.measure.manual.delay") * 1000
                wx.CallLater(delay, self.show_RGB, not show_XYZ)
                if show_XYZ:
                    wx.CallLater(delay, self.show_XYZ)
                wx.CallLater(delay, self.enable_btns)

    def pause_continue_handler(self, event=None):
        if not event:
            self.parse_txt(self.worker.lastmsg.read())

    @property
    def paused(self):
        return False

    def reset(self):
        self._setup()

    def resize_grid(self):
        num_cols = self.grid.GetNumberCols()
        if not num_cols:
            return
        grid_w = self.grid.GetSize()[0] - self.grid.GetDefaultRowSize() * 2
        col_w = round(grid_w / (num_cols - 1))
        last_col_w = grid_w - col_w * (num_cols - 2)
        self.grid.SetRowLabelSize(col_w)
        for i in range(num_cols):
            if i in (3, 4):
                w = self.grid.GetDefaultRowSize()
            elif i == num_cols - 1:
                w = last_col_w - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
            else:
                w = col_w
            self.grid.SetColSize(i, w)
        self.grid.SetMargins(0 - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X), 0)
        self.grid.ForceRefresh()

    def _setup(self):
        self.logger.info("-" * 80)
        self.is_measuring = False
        self.keepGoing = True
        self.last_error = None
        self.index = -1
        self.index_max = -1
        self.last_XYZ = (-1, -1, -1)
        self.white_XYZ = (-1, -1, -1)
        self.measure_count = 0
        self.measured = []
        self.finished = False
        self.label_RGB.SetLabel(" ")
        self.label_XYZ.SetLabel(" ")
        self.panel_RGB.SetBackgroundColour(BGCOLOUR)
        self.panel_RGB.Refresh()
        self.panel_RGB.Update()
        self.panel_XYZ.SetBackgroundColour(BGCOLOUR)
        self.panel_XYZ.Refresh()
        self.panel_XYZ.Update()
        self.label_index.SetLabel(" ")
        self.enable_btns(False)
        self.measure_auto_cb.SetValue(bool(getcfg("untethered.measure.auto")))
        self.finish_btn.Disable()

        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())

        # Set position
        x = getcfg("position.progress.x")
        y = getcfg("position.progress.y")
        self.SetSaneGeometry(x, y)

    def safe_send(self, bytes):
        if self.has_worker_subprocess() and not self.worker.subprocess_abort:
            self.worker.safe_send(bytes)

    def show_RGB(self, clear_XYZ=True, mark_current_row=True):
        row = self.cgats[0].DATA[self.index]
        self.label_RGB.SetLabel(
            "RGB %i %i %i"
            % (
                round(row["RGB_R"] / 100.0 * 255),
                round(row["RGB_G"] / 100.0 * 255),
                round(row["RGB_B"] / 100.0 * 255),
            )
        )
        color = [
            int(round(v / 100.0 * 255))
            for v in (row["RGB_R"], row["RGB_G"], row["RGB_B"])
        ]
        self.panel_RGB.SetBackgroundColour(wx.Colour(*color))
        self.panel_RGB.SetBitmap(None)
        self.panel_RGB.Refresh()
        self.panel_RGB.Update()
        if clear_XYZ:
            self.label_XYZ.SetLabel(" ")
            self.panel_XYZ.SetBackgroundColour(BGCOLOUR)
            self.panel_XYZ.SetBitmap(getbitmap("theme/checkerboard-32x32x5-333-444"))
            self.panel_XYZ.Refresh()
            self.panel_XYZ.Update()
        if mark_current_row:
            self.grid.SetRowLabelValue(self.index, "\u25ba %i" % (self.index + 1))
            self.grid.MakeCellVisible(self.index, 0)
        if self.index not in self.grid.GetSelectedRows():
            self.grid.SelectRow(self.index)
            self.grid.SetGridCursor(self.index, 0)
        self.label_index.SetLabel("%i/%i" % (self.index + 1, len(self.cgats[0].DATA)))
        self.label_index.GetContainingSizer().Layout()

    def show_XYZ(self):
        Lab, color = self.get_Lab_RGB()
        self.label_XYZ.SetLabel("L*a*b* %.2f %.2f %.2f" % Lab)
        self.panel_XYZ.SetBackgroundColour(wx.Colour(*color))
        self.panel_XYZ.SetBitmap(None)
        self.panel_XYZ.Refresh()
        self.panel_XYZ.Update()

    def start_timer(self, ms=50):
        self.timer.Start(ms)

    def stop_timer(self):
        self.timer.Stop()

    def update(self, index):
        # Reset row label
        self.grid.SetRowLabelValue(self.index, "%i" % (self.index + 1))

        self.index = index
        show_XYZ = self.index in self.measured
        self.show_RGB(not show_XYZ)
        if show_XYZ:
            self.show_XYZ()
        self.enable_btns()

    def write(self, txt):
        wx.CallAfter(self.parse_txt, txt)


if __name__ == "__main__":
    from _thread import start_new_thread
    from time import sleep
    import random
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL.util_io import Files
    from DisplayCAL import worker

    class Subprocess:
        def send(self, bytes_):
            start_new_thread(test, (bytes_,))

    class Worker(worker.Worker):
        def __init__(self):
            worker.Worker.__init__(self)
            self.finished = False
            self.instrument_calibration_complete = False
            self.instrument_place_on_screen_msg = False
            self.instrument_sensor_position_msg = False
            self.is_ambient_measuring = False
            self.subprocess = Subprocess()
            self.subprocess_abort = False

        def abort_subprocess(self):
            self.safe_send("Q")

        def safe_send(self, bytes_):
            print("*** Sending %r" % bytes_)
            self.subprocess.send(bytes_)
            return True

    config.initcfg()
    print("untethered.min_delta", getcfg("untethered.min_delta"))
    print("untethered.min_delta.lightness", getcfg("untethered.min_delta.lightness"))
    print("untethered.max_delta.chroma", getcfg("untethered.max_delta.chroma"))
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = UntetheredFrame(start_timer=False)
    testchart = getcfg("testchart.file")
    if os.path.splitext(testchart)[1].lower() in (".icc", ".icm"):
        try:
            testchart = ICCProfile(testchart).tags.targ
        except Exception:
            pass
    try:
        app.TopWindow.cgats = CGATS(testchart)
    except Exception:
        app.TopWindow.cgats = CGATS(
            """TI1
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
BEGIN_DATA
1 0 0 0 0 0 0
END_DATA
"""
        )
    app.TopWindow.worker = Worker()
    app.TopWindow.worker.progress_wnd = app.TopWindow
    app.TopWindow.Show()
    files = Files([app.TopWindow.worker, app.TopWindow])

    def test(bytes_=None):
        print("*** Received %r" % bytes_)
        menu = r"""Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:"""
        if not bytes_:
            txt = menu
        elif bytes_ == " ":
            i = app.TopWindow.index
            row = app.TopWindow.cgats[0].DATA[i]
            txt = [
                """
 Result is XYZ: %.6f %.6f %.6f

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:"""
                % (row.XYZ_X, row.XYZ_Y, row.XYZ_Z),
                """"
Result is XYZ: %.6f %.6f %.6f

Spot read needs a calibration before continuing
Place cap on the instrument, or place on a dark surface,
or place on the white calibration reference,
and then hit any key to continue,
or hit Esc or Q to abort:"""
                % (row.XYZ_X, row.XYZ_Y, row.XYZ_Z),
            ][random.choice([0, 1])]
        elif bytes_ in ("Q", "q"):
            wx.CallAfter(app.TopWindow.Close)
            return
        else:
            return
        for line in txt.split("\n"):
            sleep(0.03125)
            if app.TopWindow:
                wx.CallAfter(files.write, line)
                print(line)

    start_new_thread(test, tuple())
    app.MainLoop()
