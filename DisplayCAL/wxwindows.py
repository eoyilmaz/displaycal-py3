# -*- coding: utf-8 -*-


from datetime import datetime
import html
from html.parser import HTMLParser

htmlparser = HTMLParser()
from time import gmtime, sleep, strftime, time
import errno
import math
import os
import re
import signal
import socket
import string
import subprocess as sp
import sys
import tarfile
import textwrap
import threading
import warnings
import xml.parsers.expat
import zipfile

from DisplayCAL import demjson_compat as demjson

from DisplayCAL import ICCProfile as ICCP
from DisplayCAL import audio
from DisplayCAL import config
from DisplayCAL.config import (
    defaults,
    getbitmap,
    getcfg,
    geticon,
    get_data_path,
    get_default_dpi,
    get_verified_path,
    hascfg,
    pyname,
    setcfg,
    confighome,
    appbasename,
    logdir,
    set_default_app_dpi,
)
from DisplayCAL.debughelpers import (
    Error,
    DownloadError,
    Info,
    UnloggedError,
    UnloggedInfo,
    UnloggedWarning,
    Warn,
    getevtobjname,
    getevttype,
    handle_error,
)
from DisplayCAL.log import log as log_
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug
from DisplayCAL.network import ScriptingClientSocket, get_network_addr
from DisplayCAL.util_io import StringIOu as StringIO
from DisplayCAL.util_os import get_program_file, launch_file, waccess
from DisplayCAL.util_str import box, safe_str, wrap
from DisplayCAL.util_xml import dict2xml
from DisplayCAL.wxaddons import (
    CustomEvent,
    FileDrop as _FileDrop,
    gamma_encode,
    get_parent_frame,
    get_platform_window_decoration_size,
    wx,
    BetterWindowDisabler,
    BetterTimer,
    EVT_BETTERTIMER,
)
from DisplayCAL.wexpect import split_command_line

# from wexpect import split_command_line
from DisplayCAL.wxfixes import (
    GenBitmapButton,
    GenButton,
    GTKMenuItemGetFixedLabel,
    PlateButton,
    ThemedGenButton,
    adjust_font_size_for_gcdc,
    get_bitmap_disabled,
    get_dc_font_size,
    get_gcdc_font_size,
    platebtn,
    set_bitmap_labels,
    wx_Panel,
    get_dialogs,
    set_maxsize,
)
from DisplayCAL.lib.agw import labelbook, pygauge
from DisplayCAL.lib.agw.gradientbutton import GradientButton, CLICK, HOVER
from DisplayCAL.lib.agw.fourwaysplitter import (
    _TOLERANCE,
    FLAG_CHANGED,
    FLAG_PRESSED,
    NOWHERE,
    FourWaySplitter,
    FourWaySplitterEvent,
)
from DisplayCAL import localization as lang
from DisplayCAL import util_str
from DisplayCAL import floatspin

try:
    from wx.lib.agw import aui
    from wx.lib.agw.aui import AuiDefaultTabArt
except ImportError:
    from wx import aui
    from wx.aui import PyAuiTabArt as AuiDefaultTabArt
import wx.lib.filebrowsebutton as filebrowse
from wx.lib.agw import hyperlink
from wx.lib import fancytext
from wx.lib.statbmp import GenStaticBitmap
import wx.html
from wx._core import wxAssertionError

taskbar = None
if sys.platform == "win32" and sys.getwindowsversion() >= (6, 1):
    try:
        from DisplayCAL import taskbar
    except Exception as exception:
        print(exception)


numpad_keycodes = [
    wx.WXK_NUMPAD0,
    wx.WXK_NUMPAD1,
    wx.WXK_NUMPAD2,
    wx.WXK_NUMPAD3,
    wx.WXK_NUMPAD4,
    wx.WXK_NUMPAD5,
    wx.WXK_NUMPAD6,
    wx.WXK_NUMPAD7,
    wx.WXK_NUMPAD8,
    wx.WXK_NUMPAD9,
    wx.WXK_NUMPAD_ADD,
    wx.WXK_NUMPAD_DECIMAL,
    wx.WXK_NUMPAD_ENTER,
    wx.WXK_NUMPAD_EQUAL,
    wx.WXK_NUMPAD_DIVIDE,
    wx.WXK_NUMPAD_MULTIPLY,
    wx.WXK_NUMPAD_SEPARATOR,
    wx.WXK_NUMPAD_SUBTRACT,
]

nav_keycodes = [
    wx.WXK_DOWN,
    wx.WXK_END,
    wx.WXK_HOME,
    wx.WXK_LEFT,
    wx.WXK_PAGEDOWN,
    wx.WXK_PAGEUP,
    wx.WXK_RIGHT,
    wx.WXK_TAB,
    wx.WXK_UP,
    wx.WXK_NUMPAD_DOWN,
    wx.WXK_NUMPAD_END,
    wx.WXK_NUMPAD_HOME,
    wx.WXK_NUMPAD_LEFT,
    wx.WXK_NUMPAD_PAGEDOWN,
    wx.WXK_NUMPAD_PAGEUP,
    wx.WXK_NUMPAD_RIGHT,
    wx.WXK_NUMPAD_UP,
]

processing_keycodes = [
    wx.WXK_ESCAPE,
    wx.WXK_RETURN,
    wx.WXK_INSERT,
    wx.WXK_DELETE,
    wx.WXK_BACK,
]

modifier_keycodes = [wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_COMMAND]


class AboutDialog(wx.Dialog):
    def __init__(self, *args, **kwargs):
        kwargs["style"] = wx.DEFAULT_DIALOG_STYLE & ~(
            wx.RESIZE_BORDER | wx.MAXIMIZE_BOX
        )
        kwargs["name"] = "aboutdialog"
        wx.Dialog.__init__(self, *args, **kwargs)

        # Set an icon so text isn't crammed to the left of the titlebar under
        # Windows (other platforms?)
        self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))

        self.Sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.Sizer.Add(self.panel, 1, flag=wx.EXPAND)

        self.panel.Sizer = wx.BoxSizer(wx.VERTICAL)

        if "gtk3" in wx.PlatformInfo:
            # Fix background color not working for panels under GTK3
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    if "gtk3" in wx.PlatformInfo:
        OnEraseBackground = wx_Panel.__dict__["OnEraseBackground"]

    def OnClose(self, event):
        self.Hide()

    def Layout(self):
        self.Sizer.SetMinSize(480, 560)
        self.Sizer.SetSizeHints(self)
        self.panel.SetScrollRate(2, 2)
        self.Sizer.Layout()
        if wx.Platform == "__WXGTK__":
            for child in self.panel.Children:
                # Fix height of children
                child.MinSize = child.MinSize[0], child.Size[1]

    def add_items(self, items):
        self.line = wx.Panel(self, size=(-1, 1))
        self.line.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
        )
        self.Sizer.Add(self.line, flag=wx.EXPAND)
        self.btnpanel = wx.Panel(self)
        self.btnpanel.Sizer = wx.GridSizer(1, 1, 0, 0)
        self.Sizer.Add(self.btnpanel, flag=wx.EXPAND)
        self.ok = wx.Button(self.btnpanel, -1, lang.getstr("close"))
        self.btnpanel.Sizer.Add(self.ok, flag=wx.ALL | wx.ALIGN_CENTER, border=12)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.ok.GetId())
        for item in items:
            if (
                not isinstance(item, wx.Window)
                and hasattr(item, "__iter__")
                and [
                    subitem for subitem in item if not isinstance(subitem, (int, float))
                ]
            ):
                sizer = wx.BoxSizer(wx.HORIZONTAL)
                self.add_item(sizer, self.panel.Sizer)
                for subitem in item:
                    self.add_item(subitem, sizer)
            else:
                self.add_item(item, self.panel.Sizer)
        self.ok.SetDefault()
        self.ok.SetFocus()

    def add_item(self, item, sizer):
        if isinstance(item, (HyperLinkCtrl, ThemedGenButton)):
            item.BackgroundColour = self.panel.BackgroundColour
        if isinstance(item, wx.Window):
            pointsize = 10
            font = item.GetFont()
            if item.GetLabel() and font.GetPointSize() > pointsize:
                font.SetPointSize(pointsize)
                item.SetFont(font)
        flag = wx.ALIGN_NOT
        if isinstance(item, (wx.Panel, wx.PyPanel)):
            flag |= wx.EXPAND
        elif sizer is self.panel.Sizer:
            flag |= wx.LEFT | wx.RIGHT
        sizer.Add(item, 0, flag, 12)


class AnimatedBitmap(wx.PyControl):
    """Animated bitmap"""

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        bitmaps=None,
        range=(0, -1),
        loop=True,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.NO_BORDER,
    ):
        """Create animated bitmap

        bitmaps should be an array of bitmaps.
        range should be the indexes of the range of frames that should be looped.
        -1 means last frame.

        """
        self.dpiscale = getcfg("app.dpi") / get_default_dpi()
        if self.dpiscale > 1:
            size = tuple(int(round(v * self.dpiscale)) if v != -1 else v for v in size)
        wx.PyControl.__init__(self, parent, id, pos, size, style)
        self._minsize = size
        self.SetBitmaps(bitmaps or [], range, loop)
        # Avoid flickering under Windows
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self._timer = BetterTimer(self)
        self.Bind(EVT_BETTERTIMER, self.OnTimer, self._timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    def OnDestroy(self, event):
        self._timer.Stop()
        del self._timer

    def DoGetBestSize(self):
        return self._minsize

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.Parent.BackgroundColour))
        dc.Clear()
        if self._bitmaps:
            if self.frame > len(self._bitmaps) - 1:
                self.frame = len(self._bitmaps) - 1
            if self.dpiscale > 1:
                dc.SetUserScale(self.dpiscale, self.dpiscale)
            dc.DrawBitmap(self._bitmaps[self.frame], 0, 0, True)

    def OnTimer(self, event):
        first_frame, last_frame = self.range
        if first_frame < 0:
            first_frame += len(self._bitmaps)
        if last_frame < 0:
            last_frame += len(self._bitmaps)
        frame = self.frame
        if frame < last_frame:
            frame += 1
        elif self.loop:
            frame = first_frame
        if frame != self.frame:
            self.frame = frame
            self.Refresh()

    def Play(self, fps=24):
        self._timer.Start(int(1000.0 / fps))

    def Stop(self):
        self._timer.Stop()

    def SetBitmaps(self, bitmaps, range=(0, -1), loop=True):
        w, h = self._minsize
        for bitmap in bitmaps:
            w = max(bitmap.Size[0], w)
            h = max(bitmap.Size[0], h)
        self._minsize = w, h
        self._bitmaps = bitmaps
        self.loop = loop
        self.range = range
        self.frame = 0


class AuiBetterTabArt(AuiDefaultTabArt):
    def DrawTab(self, dc, wnd, page, in_rect, close_button_state, paint_control=False):
        """Draws a single tab.

        :param dc: a :class:`DC` device context;
        :param wnd: a :class:`Window` instance object;
        :param page: the tab control page associated with the tab;
        :param Rect `in_rect`: rectangle the tab should be confined to;
        :param integer `close_button_state`: the state of the close button on the tab;
        :param bool `paint_control`: whether to draw the control inside a tab (if any) on a :class:`MemoryDC`.
        """

        # if the caption is empty, measure some temporary text
        caption = page.caption
        if not caption:
            caption = "Xj"

        dc.SetFont(self._selected_font)
        if hasattr(dc, "GetFullMultiLineTextExtent"):
            # Phoenix
            selected_textx, selected_texty = dc.GetMultiLineTextExtent(caption)
        else:
            # Classic
            selected_textx, selected_texty, dummy = dc.GetMultiLineTextExtent(caption)

        dc.SetFont(self._normal_font)
        if hasattr(dc, "GetFullMultiLineTextExtent"):
            # Phoenix
            normal_textx, normal_texty = dc.GetMultiLineTextExtent(caption)
        else:
            # Classic
            normal_textx, normal_texty, dummy = dc.GetMultiLineTextExtent(caption)

        control = page.control

        # figure out the size of the tab
        tab_size, x_extent = self.GetTabSize(
            dc, wnd, page.caption, page.bitmap, page.active, close_button_state, control
        )

        tab_height = self._tab_ctrl_height - 3
        tab_width = tab_size[0]
        tab_x = in_rect.x
        tab_y = in_rect.y + in_rect.height - tab_height

        caption = page.caption

        # select pen, brush and font for the tab to be drawn

        if page.active:

            dc.SetFont(self._selected_font)
            textx, texty = selected_textx, selected_texty

        else:

            dc.SetFont(self._normal_font)
            textx, texty = normal_textx, normal_texty

        if not page.enabled:
            dc.SetTextForeground(self._tab_disabled_text_colour)
            pagebitmap = page.dis_bitmap
        else:
            dc.SetTextForeground(self._tab_text_colour(page))
            pagebitmap = page.bitmap

        # create points that will make the tab outline

        clip_width = tab_width
        if tab_x + clip_width > in_rect.x + in_rect.width:
            clip_width = in_rect.x + in_rect.width - tab_x

        # since the above code above doesn't play well with WXDFB or WXCOCOA,
        # we'll just use a rectangle for the clipping region for now --
        dc.SetClippingRegion(tab_x, tab_y, clip_width + 1, tab_height - 3)

        border_points = [wx.Point() for i in range(6)]
        agwFlags = self.GetAGWFlags()

        if agwFlags & aui.AUI_NB_BOTTOM:

            border_points[0] = wx.Point(tab_x, tab_y)
            border_points[1] = wx.Point(tab_x, tab_y + tab_height - 6)
            border_points[2] = wx.Point(tab_x + 2, tab_y + tab_height - 4)
            border_points[3] = wx.Point(tab_x + tab_width - 2, tab_y + tab_height - 4)
            border_points[4] = wx.Point(tab_x + tab_width, tab_y + tab_height - 6)
            border_points[5] = wx.Point(tab_x + tab_width, tab_y)

        else:  # if (agwFlags & aui.AUI_NB_TOP)

            border_points[0] = wx.Point(tab_x, tab_y + tab_height - 4)
            border_points[1] = wx.Point(tab_x, tab_y + 2)
            border_points[2] = wx.Point(tab_x + 2, tab_y)
            border_points[3] = wx.Point(tab_x + tab_width - 2, tab_y)
            border_points[4] = wx.Point(tab_x + tab_width, tab_y + 2)
            border_points[5] = wx.Point(tab_x + tab_width, tab_y + tab_height - 4)

        # TODO: else if (agwFlags & aui.AUI_NB_LEFT)
        # TODO: else if (agwFlags & aui.AUI_NB_RIGHT)

        drawn_tab_yoff = border_points[1].y
        drawn_tab_height = border_points[0].y - border_points[1].y

        if page.active:

            # draw active tab

            # draw base background colour
            r = wx.Rect(tab_x, tab_y, tab_width, tab_height)
            dc.SetPen(self._base_colour_pen)
            dc.SetBrush(self._base_colour_brush)
            dc.DrawRectangle(r.x + 1, r.y + 1, r.width - 1, r.height - 4)

            # this white helps fill out the gradient at the top of the tab
            dc.SetPen(wx.Pen(self._tab_gradient_highlight_colour))
            dc.SetBrush(wx.Brush(self._tab_gradient_highlight_colour))
            dc.DrawRectangle(r.x + 2, r.y + 1, r.width - 3, r.height - 4)

            # these two points help the rounded corners appear more antialiased
            dc.SetPen(self._base_colour_pen)
            dc.DrawPoint(r.x + 2, r.y + 1)
            dc.DrawPoint(r.x + r.width - 2, r.y + 1)

            # set rectangle down a bit for gradient drawing
            r.SetHeight(int(r.GetHeight() / 2))
            r.x += 2
            r.width -= 3
            r.y += r.height
            r.y -= 2

            # draw gradient background
            top_colour = self._tab_bottom_colour
            bottom_colour = self._tab_top_colour
            dc.GradientFillLinear(r, bottom_colour, top_colour, wx.NORTH)

        else:

            # draw inactive tab

            r = wx.Rect(tab_x, tab_y + 1, tab_width, tab_height - 3)

            # start the gradent up a bit and leave the inside border inset
            # by a pixel for a 3D look.  Only the top half of the inactive
            # tab will have a slight gradient
            r.x += 2
            r.y += 1
            r.width -= 3
            r.height = int(r.height / 2)

            # -- draw top gradient fill for glossy look
            top_colour = self._tab_inactive_top_colour
            bottom_colour = self._tab_inactive_bottom_colour
            dc.GradientFillLinear(r, bottom_colour, top_colour, wx.NORTH)

            r.y += r.height
            r.y -= 1

            # -- draw bottom fill for glossy look
            top_colour = self._tab_inactive_bottom_colour
            bottom_colour = self._tab_inactive_bottom_colour
            dc.GradientFillLinear(r, top_colour, bottom_colour, wx.SOUTH)

        # draw tab outline
        dc.SetPen(self._border_pen)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawPolygon(border_points)

        # there are two horizontal grey lines at the bottom of the tab control,
        # this gets rid of the top one of those lines in the tab control
        if page.active:

            if agwFlags & aui.AUI_NB_BOTTOM:
                dc.SetPen(wx.Pen(self._background_bottom_colour))

            # TODO: else if (agwFlags & aui.AUI_NB_LEFT)
            # TODO: else if (agwFlags & aui.AUI_NB_RIGHT)
            else:  # for aui.AUI_NB_TOP
                dc.SetPen(self._base_colour_pen)

            dc.DrawLine(
                border_points[0].x + 1,
                border_points[0].y,
                border_points[5].x,
                border_points[5].y,
            )

        text_offset = tab_x + 8
        close_button_width = 0

        if close_button_state != aui.AUI_BUTTON_STATE_HIDDEN:
            close_button_width = self._active_close_bmp.GetWidth()

            if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT:
                text_offset += close_button_width - 5

        bitmap_offset = 0

        if pagebitmap.IsOk():

            bitmap_offset = tab_x + 8
            if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT and close_button_width:
                bitmap_offset += close_button_width - 5

            # draw bitmap
            dc.DrawBitmap(
                pagebitmap,
                bitmap_offset,
                drawn_tab_yoff
                + int(drawn_tab_height / 2)
                - int(pagebitmap.GetHeight() / 2),
                True,
            )

            text_offset = bitmap_offset + pagebitmap.GetWidth()
            text_offset += 3  # bitmap padding

        else:

            if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT == 0 or not close_button_width:
                text_offset = tab_x + 8

        draw_text = aui.ChopText(
            dc, caption, tab_width - (text_offset - tab_x) - close_button_width
        )

        ypos = drawn_tab_yoff + int(drawn_tab_height / 2) - int(texty / 2) - 1

        offset_focus = text_offset

        if control is not None:
            try:
                if control.GetPosition() != wx.Point(text_offset + 1, ypos):
                    control.SetPosition(wx.Point(text_offset + 1, ypos))

                if not control.IsShown():
                    control.Show()

                if paint_control:
                    bmp = aui.TakeScreenShot(control.GetScreenRect())
                    dc.DrawBitmap(bmp, text_offset + 1, ypos, True)

                controlW, controlH = control.GetSize()
                text_offset += controlW + 4
                textx += controlW + 4
            except wx.PyDeadObjectError:
                pass

        # draw tab text
        if hasattr(dc, "GetFullMultiLineTextExtent"):
            # Phoenix
            rectx, recty = dc.GetMultiLineTextExtent(draw_text)
        else:
            # Classic
            rectx, recty, dummy = dc.GetMultiLineTextExtent(draw_text)
        textfg = dc.GetTextForeground()
        shadow = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
        dc.SetTextForeground(shadow)
        dc.DrawLabel(draw_text, wx.Rect(text_offset + 1, ypos + 1, rectx, recty))
        dc.SetTextForeground(textfg)
        dc.DrawLabel(draw_text, wx.Rect(text_offset, ypos, rectx, recty))

        # draw focus rectangle
        if (agwFlags & aui.AUI_NB_NO_TAB_FOCUS) == 0:
            self.DrawFocusRectangle(
                dc,
                page,
                wnd,
                draw_text,
                offset_focus,
                bitmap_offset,
                drawn_tab_yoff,
                drawn_tab_height,
                rectx,
                recty,
            )

        out_button_rect = wx.Rect()

        # draw close button if necessary
        if close_button_state != aui.AUI_BUTTON_STATE_HIDDEN:

            bmp = self._disabled_close_bmp

            if close_button_state == aui.AUI_BUTTON_STATE_HOVER:
                bmp = self._hover_close_bmp
            elif close_button_state == aui.AUI_BUTTON_STATE_PRESSED:
                bmp = self._pressed_close_bmp

            shift = (agwFlags & aui.AUI_NB_BOTTOM and [1] or [0])[0]

            if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT:
                rect = wx.Rect(
                    tab_x + 4,
                    tab_y + int((tab_height - bmp.GetHeight()) / 2 - shift),
                    close_button_width,
                    tab_height,
                )
            else:
                rect = wx.Rect(
                    tab_x + tab_width - close_button_width - 1,
                    tab_y + int((tab_height - bmp.GetHeight()) / 2 - shift),
                    close_button_width,
                    tab_height,
                )

            rect = aui.IndentPressedBitmap(rect, close_button_state)
            dc.DrawBitmap(bmp, rect.x, rect.y, True)

            out_button_rect = rect

        out_tab_rect = wx.Rect(tab_x, tab_y, tab_width, tab_height)

        dc.DestroyClippingRegion()

        return out_tab_rect, out_button_rect, x_extent

    def SetDefaultColours(self, base_colour=None):
        """Sets the default colours, which are calculated from the given base colour.

        :param base_colour: an instance of :class:`Colour`. If defaulted to ``None``, a colour
         is generated accordingly to the platform and theme.
        """

        if base_colour is None:
            base_colour = aui.GetBaseColour()

        self.SetBaseColour(base_colour)
        self._border_colour = aui.StepColour(base_colour, 75)
        self._border_pen = wx.Pen(self._border_colour)

        self._background_top_colour = aui.StepColour(self._base_colour, 90)
        self._background_bottom_colour = aui.StepColour(self._base_colour, 120)

        self._tab_top_colour = self._base_colour
        self._tab_bottom_colour = aui.StepColour(self._base_colour, 130)
        self._tab_gradient_highlight_colour = aui.StepColour(self._base_colour, 130)

        self._tab_inactive_top_colour = self._background_top_colour
        self._tab_inactive_bottom_colour = aui.StepColour(self._base_colour, 110)

        self._tab_text_colour = lambda page: page.text_colour
        self._tab_disabled_text_colour = wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_GRAYTEXT
        )


class AutocompleteComboBox(wx.ComboBox):
    def __init__(self, *args, **kwargs):
        wx.ComboBox.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_TEXT, self.OnText)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_COMBOBOX, self.OnComboBox)
        self._ignore_text_evt = False
        self._popup_shown = None
        if hasattr(wx, "EVT_COMBOBOX_DROPDOWN"):
            self.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.OnComboBoxDropDown)
        if hasattr(wx, "EVT_COMBOBOX_CLOSEUP"):
            self.Bind(wx.EVT_COMBOBOX_CLOSEUP, self.OnComboBoxCloseUp)

    def OnComboBox(self, event):
        self._ignore_text_evt = True
        event.Skip()

    def OnComboBoxDropDown(self, event):
        self._popup_shown = True
        event.Skip()

    def OnComboBoxCloseUp(self, event):
        self._popup_shown = False
        event.Skip()

    def OnChar(self, event):
        if event.GetKeyCode() == 8 or event.ControlDown():  # Backspace or modifier
            self._ignore_text_evt = True
        event.Skip()

    def OnText(self, event):
        if self._ignore_text_evt:
            self._ignore_text_evt = False
            return
        current_text = event.GetString().lower()
        found = False
        for i, choice in enumerate(self.Items):
            if choice.lower().startswith(current_text):
                self._ignore_text_evt = True
                if self._popup_shown is not None:
                    self.SetSelection(i)
                self.SetValue(choice)
                self.SetInsertionPoint(len(current_text))
                self.SetMark(len(current_text), len(choice))
                found = True
                break
        if not found:
            event.Skip()


class BaseApp(wx.App):
    """Application base class implementing common functionality."""

    _exithandlers = []
    _query_end_session = None

    def __init__(self, *args, **kwargs):
        # Fix sys.prefix for SetInstallPrefix used inside wx.App which does not
        # decode to Unicode when calling SetInstallPrefix. DisplayCAL when
        # bundled by Py2App can't be run from a path containing Unicode
        # characters under Mac OS X otherwise.
        prefix = sys.prefix
        sys.prefix = str(sys.prefix)

        wx.App.__init__(self, *args, **kwargs)

        # Restore prefix
        sys.prefix = prefix

        if not kwargs.get("clearSigInt", True) or len(args) == 4 and not args[3]:
            # Install our own SIGINT handler, so we can do cleanup on receiving
            # SIGINT
            print("Installing SIGINT handler")
            signal.signal(signal.SIGINT, self.signal_handler)
            # This timer allows processing of SIGINT / CTRL+C, because normally
            # with clearSigInt=False, SIGINT / CTRL+C are only processed during
            # UI events
            self._signal_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, lambda e: None, self._signal_timer)
            self._signal_timer.Start(100)

    def signal_handler(self, signum, frame):
        if signum == signal.SIGINT:
            print("Received SIGINT")
            print("Sending query to end session...")
            self.ProcessEvent(wx.CloseEvent(wx.EVT_QUERY_END_SESSION.evtType[0]))

    def OnInit(self):
        self.AppName = pyname
        set_default_app_dpi()
        # We use a lock so we can make sure the exit handlers are executed
        # properly before we actually exit when receiving OS
        # logout/reboot/shutdown events. This is needed because it is not
        # guaranteed that when we receive EVT_QUERY_END_SESSION and close
        # the main application window (which will normally exit the main event
        # loop unless BaseApp.ExitOnFrameDelete is False) that OnExit (which'll
        # execute the exit handlers) will run right away because normally it'll
        # run after the main event loop exits (i.e. in the next iteration of the
        # main loop after an implicit or explicit call of ExitMainLoop).
        # Also, we need to call OnExit explicitly when receiving EVT_END_SESSION
        # because there will be no next iteration of the event loop (the OS
        # simply kills the application after the handler is executed). If OnExit
        # was already called before as a result of receiving
        # EVT_QUERY_END_SESSION and exiting the main event loop (remember this
        # is not guaranteed because of the way the event loop works!) and did
        # already finish, this'll do nothing and we can just exit. If OnExit is
        # still executing the exit handlers and thus holds the lock, the lock
        # makes sure that we wait for OnExit to finish before we explicitly call
        # sys.exit(0) (which'll make sure exit handlers registered by atexit
        # will run) to finally exit for good before the OS tries to kill the
        # application.
        self._lock = threading.Lock()
        self.Bind(wx.EVT_QUERY_END_SESSION, self.query_end_session)
        self.Bind(wx.EVT_END_SESSION, self.end_session)
        if os.getenv("XDG_SESSION_TYPE") == "wayland":
            # Fix erroneous extra spacing around window contents under
            # Wayland. First frame will get size right, but not min size,
            # so create a 'dummy' frame, call Show() which is needed so
            # we can fix subsequently created windows, then instantly get
            # rid of it. Ugly.
            dummy = wx.Frame(None)
            # May not be needed, but we don't want to risk actually
            # showing our dummy frame
            dummy.SetTransparent(0)
            # Need to call Show() to 'fix' subsequently created windows
            dummy.Show()
            # Now we can get rid of it
            dummy.Close()
        return True

    def MacOpenFiles(self, paths):
        if self.TopWindow and isinstance(
            getattr(self.TopWindow, "droptarget", None), FileDrop
        ):
            self.TopWindow.droptarget.OnDropFiles(0, 0, paths)

    def MacReopenApp(self):
        if self.TopWindow and self.TopWindow.IsShownOnScreen():
            self.TopWindow.Raise()

    def process_argv(self, count=0):
        paths = []
        for arg in sys.argv[1:]:
            if os.path.isfile(arg):
                paths.append(str(arg))
                if len(paths) == count:
                    break
        if paths:
            self.MacOpenFiles(paths)
            return paths

    def OnExit(self):
        print("Executing BaseApp.OnExit()")
        with self._lock:
            if BaseApp._exithandlers:
                print("Running application exit handlers")
                BaseApp._run_exitfuncs()
        if hasattr(wx.App, "OnExit"):
            return wx.App.OnExit(self)
        else:
            return 0

    @staticmethod
    def _run_exitfuncs():
        """run any registered exit functions

        _exithandlers is traversed in reverse order so functions are executed
        last in, first out.
        """
        # Inspired by python's 'atexit' module.
        # It's important that the exit handlers run *before* the actual main
        # loop exits, otherwise they might not run at all if the app is closed
        # externally (e.g. if the OS asks the app to close on logout).
        # Using the 'atexit' module will NOT work!

        exc_info = None
        while BaseApp._exithandlers:
            func, args, kwargs = BaseApp._exithandlers.pop()
            try:
                func(*args, **kwargs)
            except SystemExit:
                exc_info = sys.exc_info()
            except Exception:
                import traceback

                print("Error in BaseApp._run_exitfuncs:")
                print(traceback.format_exc())

        if exc_info is not None:
            raise exc_info[0](exc_info[1]).with_traceback(exc_info[2])

    @staticmethod
    def register_exitfunc(func, *args, **kwargs):
        BaseApp._exithandlers.append((func, args, kwargs))

    def query_end_session(self, event):
        print("Received query to end session")
        if event.CanVeto():
            print("Can veto")
        else:
            print("Cannot veto")
        if self.TopWindow and self.TopWindow is not self._query_end_session:
            if not isinstance(self.TopWindow, wx.Dialog):
                print("Trying to close main top-level application window...")
                if self.TopWindow.Close(force=not event.CanVeto()):
                    self.TopWindow.listening = False
                    self._query_end_session = self.TopWindow
                    print("Main top-level application window processed close event")
                    return
                else:
                    print("Failed to close main top-level application window")
            if event.CanVeto():
                event.Veto()
                print("Vetoed query to end session")

    def end_session(self, event):
        print("Ending session")
        self.ExitMainLoop()
        # We may need to call OnExit() explicitly because there is not
        # guaranteed to be a next iteration of the main event loop
        try:
            self.OnExit()
        except Exception:
            # Yes, this can fail with a TypeError, amazingly enough :-(
            # Apparently sometimes, wx already shuts down the application
            # and OnExit will be None. We assume in this case that OnExit
            # already ran.
            pass
        # Calling sys.exit makes sure that exit handlers registered by atexit
        # will run
        print("Calling sys.exit(0)")
        sys.exit(0)


active_window = None
responseformats = {}


class BaseFrame(wx.Frame):
    """Main frame base class."""

    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        self.init()

    def FindWindowByName(self, name):
        """wxPython Phoenix FindWindowByName descends into the parent windows,
        we don't want that
        """
        for child in self.GetAllChildren():
            if hasattr(child, "Name") and child.Name == name:
                return child

    def __OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.listening = False
        event.Skip()

    def close_all(self):
        windows = list(wx.GetTopLevelWindows())
        while windows:
            win = windows.pop()
            if (
                isinstance(win, (AboutDialog, BaseInteractiveDialog, ProgressDialog))
                or win.__class__ is wx.Dialog
            ) and win.IsShown():
                if win.IsModal():
                    wx.CallAfter(win.EndModal, wx.ID_CANCEL)
                    print("Closed modal dialog", win)
                else:
                    wx.CallAfter(win.Close)
                    print("Closed dialog", win)
            elif isinstance(win, wx.Frame):
                wx.CallAfter(win.Close)
                print("Closed", win)

    def init(self):
        self.Bind(wx.EVT_ACTIVATE, self.activate_handler)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.__OnDestroy)

    def init_menubar(self):
        self.MenuBar = wx.MenuBar()
        filemenu = wx.Menu()
        quit = filemenu.Append(
            -1 if wx.VERSION < (2, 9) else wx.ID_EXIT,
            "&%s\tCtrl+Q" % lang.getstr("menuitem.quit"),
        )
        self.Bind(wx.EVT_MENU, lambda event: self.Close(), quit)
        if sys.platform != "darwin":
            self.MenuBar.Append(filemenu, "&%s" % lang.getstr("menu.file"))

    def activate_handler(self, event):
        global active_window
        active_window = self

    def listen(self):
        if isinstance(getattr(sys, "_appsocket", None), socket.socket):
            addr, port = sys._appsocket.getsockname()
            if addr == "0.0.0.0":
                try:
                    addr = get_network_addr()
                except socket.error:
                    pass
            print(lang.getstr("app.listening", (addr, port)))
            self.listening = True
            self.listener = threading.Thread(
                target=self.connection_handler, name="ScriptingHost.ConnectionHandler"
            )
            self.listener.start()

    def connect(self, ip, port):
        if getattr(self, "conn", None):
            self.conn.disconnect()
        conn = ScriptingClientSocket()
        conn.settimeout(3)
        try:
            conn.connect((ip, port))
        except socket.error as exception:
            del conn
            return exception
        return conn

    def connection_handler(self):
        """Handle socket connections"""
        self._msghandlercount = 0
        while self and getattr(self, "listening", False):
            try:
                # Wait for connection
                conn, addrport = sys._appsocket.accept()
            except socket.timeout:
                continue
            except socket.error as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                break
            if addrport[0] != "127.0.0.1" and not getcfg("app.allow_network_clients"):
                # Network client disallowed
                conn.close()
                print(lang.getstr("app.client.network.disallowed", addrport))
                sleep(0.2)
                continue
            try:
                conn.settimeout(0.2)
            except socket.error as exception:
                conn.close()
                print(lang.getstr("app.client.ignored", exception))
                sleep(0.2)
                continue
            print(lang.getstr("app.client.connect", addrport))
            self._msghandlercount += 1
            threading.Thread(
                target=self.message_handler,
                name="ScriptingHost.MessageHandler-%d" % self._msghandlercount,
                args=(conn, addrport),
            ).start()
        sys._appsocket.close()

    def message_handler(self, conn, addrport):
        """Handle messages sent via socket"""
        responseformats[conn] = "plain"
        buffer = ""
        while self and getattr(self, "listening", False):
            # Wait for incoming message
            try:
                incoming = conn.recv(4096)
                if isinstance(incoming, bytes):
                    incoming = incoming.decode("utf-8")
            except socket.timeout:
                continue
            except socket.error as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                break
            else:
                if not incoming:
                    break
                buffer += incoming
                while "\n" in buffer and self and getattr(self, "listening", False):
                    end = buffer.find("\n")
                    line = buffer[:end].strip()
                    buffer = buffer[end + 1 :]
                    if line:
                        command_timestamp = datetime.now().strftime(
                            "%Y-%m-%dTH:%M:%S.%f"
                        )
                        line = str(line)
                        print(lang.getstr("app.incoming_message", addrport + (line,)))
                        data = split_command_line(line)
                        response = None
                        # Non-UI commands
                        if data[0] == "getappname" and len(data) == 1:
                            response = pyname
                        elif data[0] == "getcfg" and len(data) < 3:
                            if len(data) == 2:
                                # Return cfg value
                                if data[1] in defaults:
                                    if responseformats[conn].startswith("xml"):
                                        response = {
                                            "name": data[1],
                                            "value": getcfg(data[1]),
                                        }
                                    else:
                                        response = {data[1]: getcfg(data[1])}
                                else:
                                    response = "invalid"
                            else:
                                # Return whole cfg
                                if responseformats[conn] != "plain":
                                    response = []
                                else:
                                    response = dict()
                                for name in sorted(defaults):
                                    value = getcfg(name, False)
                                    if value is not None:
                                        if responseformats[conn] != "plain":
                                            response.append(
                                                {"name": name, "value": value}
                                            )
                                        else:
                                            response[name] = value
                        elif data[0] == "getcommands" and len(data) == 1:
                            response = sorted(self.get_commands())
                        elif data[0] == "getdefault" and len(data) == 2:
                            if data[1] in defaults:
                                if responseformats[conn] != "plain":
                                    response = {
                                        "name": data[1],
                                        "value": defaults[data[1]],
                                    }
                                else:
                                    response = {data[1]: defaults[data[1]]}
                            else:
                                response = "invalid"
                        elif data[0] == "getdefaults" and len(data) == 1:
                            if responseformats[conn] != "plain":
                                response = []
                            else:
                                response = dict()
                            for name in sorted(defaults):
                                if responseformats[conn] != "plain":
                                    response.append(
                                        {"name": name, "value": defaults[name]}
                                    )
                                else:
                                    response[name] = defaults[name]
                        elif data[0] == "getvalid" and len(data) == 1:
                            if responseformats[conn] != "plain":
                                response = {}
                                for section, options in (
                                    ("ranges", config.valid_ranges),
                                    ("values", config.valid_values),
                                ):
                                    valid = response[section] = []
                                    for name in options:
                                        values = options[name]
                                        valid.append({"name": name, "values": values})
                            else:
                                response = {
                                    "ranges": config.valid_ranges,
                                    "values": config.valid_values,
                                }
                            if responseformats[conn] == "plain":
                                valid = []
                                for section in response:
                                    options = response[section]
                                    valid.append("[%s]" % section)
                                    for name in options:
                                        values = options[name]
                                        valid.append(
                                            "%s = %s"
                                            % (
                                                name,
                                                " ".join(
                                                    demjson.encode(value)
                                                    for value in values
                                                ),
                                            )
                                        )
                                response = valid
                        elif (
                            data[0] == "setresponseformat"
                            and len(data) == 2
                            and data[1]
                            in ("json", "json.pretty", "plain", "xml", "xml.pretty")
                        ):
                            responseformats[conn] = data[1]
                            response = "ok"
                        if response is not None:
                            self.send_response(response, data, conn, command_timestamp)
                            continue
                        # UI commands
                        wx.CallAfter(
                            self.finish_processing, data, conn, command_timestamp
                        )
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except socket.error as exception:
            if exception.errno != errno.ENOTCONN:
                print("Warning - could not shutdown connection:", exception)
        print(lang.getstr("app.client.disconnect", addrport))
        conn.close()
        responseformats.pop(conn)

    def get_app_state(self, format):
        win = self.get_top_window()
        if isinstance(win, wx.Dialog) and win.IsShown():
            if isinstance(win, (DirDialog, FileDialog)):
                response = format_ui_element(win, format)
                if format != "plain":
                    response.update({"message": win.Message, "path": win.Path})
                else:
                    response = [
                        response,
                        demjson.encode(win.Message),
                        "path",
                        demjson.encode(win.Path),
                    ]
            elif isinstance(win, (AboutDialog, BaseInteractiveDialog, ProgressDialog)):
                response = format_ui_element(win, format)
                if format == "plain":
                    response = [response]
                if hasattr(win, "message") and win.message:
                    if format != "plain":
                        response["message"] = win.message.Label
                    else:
                        response.append(demjson.encode(win.message.Label))
                # Ordering in tab order
                for child in win.GetAllChildren():
                    if (
                        child
                        and isinstance(child, (FlatShadedButton, GenButton, wx.Button))
                        and child.TopLevelParent is win
                        and child.IsShownOnScreen()
                        and child.IsEnabled()
                    ):
                        if format != "plain":
                            if "buttons" not in response:
                                response["buttons"] = []
                            response["buttons"].append(child.Label)
                        else:
                            if "buttons" not in response:
                                response.append("buttons")
                            response.append(demjson.encode(child.Label))
            elif win.__class__ is wx.Dialog:
                response = format_ui_element(win, format)
                if format == "plain":
                    response = [response]
            else:
                return "blocked"
            if format == "plain":
                response = " ".join(response)
            return response
        if hasattr(self, "worker") and self.worker.is_working():
            return "busy"
        return "idle"

    def get_commands(self):
        return self.get_common_commands()

    def get_common_commands(self):
        cmds = [
            "abort",
            "activate [window]",
            "alt",
            "cancel",
            "ok [filename]",
            "close [window]",
            "echo <string>",
            "exit [force]",
            "getactivewindow",
            "getappname",
            "getcellvalues [window] <grid>",
            "getcommands",
            "getcfg [option]",
            "getdefault <option>",
            "getdefaults",
            "getmenus",
            "getmenuitems [menu]",
            "getstate",
            "getuielement [window] <element>",
            "getuielements [window]",
            "getvalid",
            "getwindows",
            "interact [window] <element> [setvalue value]",
            "invokemenu <menu> <menuitem>",
            "restore-defaults [category...]",
            "setcfg <option> <value>",
            "setresponseformat <format>",
        ]
        if hasattr(self, "update_controls"):
            cmds.append("refresh")
            if hasattr(self, "panel"):
                cmds.append("setlanguage <languagecode>")
        return cmds

    def get_scripting_hosts(self):
        scripting_hosts = []
        lockfilebasenames = [appbasename]
        for module in [
            "3DLUT-maker",
            "curve-viewer",
            "profile-info",
            "scripting-client",
            "synthprofile",
            "testchart-editor",
            "VRML-to-X3D-converter",
            "apply-profiles",
        ]:
            lockfilebasenames.append("%s-%s" % (appbasename, module))
        for lockfilebasename in lockfilebasenames:
            lockfilename = os.path.join(confighome, "%s.lock" % lockfilebasename)
            if os.path.isfile(lockfilename):
                ports = []
                try:
                    with open(lockfilename) as lockfile:
                        for line in lockfile.read().splitlines():
                            if line:
                                if ":" in line:
                                    pid, port = line.split(":", 1)
                                else:
                                    port = line
                                if port:
                                    ports.append(port)
                except EnvironmentError as exception:
                    # This shouldn't happen
                    print(
                        "Warning - could not read lockfile %s:" % lockfilename,
                        exception,
                    )
                else:
                    for port in ports:
                        scripting_hosts.append(
                            "127.0.0.1:%s %s" % (port, lockfilebasename)
                        )
        scripting_hosts.sort()
        return scripting_hosts

    def get_top_window(self):
        windows = [active_window or self] + list(wx.GetTopLevelWindows())
        while windows:
            win = windows.pop()
            if win and isinstance(win, wx.Dialog) and win.IsShown():
                break
        return (win and win.IsShown() and win) or self

    def global_navigate(self):
        # We have wx.Window.Navigate, but it only works for siblings in the
        # same parent frame. Re-implement our own version.
        focus = self.FindFocus()
        if focus:
            children = self.GetAllChildren()
            if focus in children:
                start = i = children.index(focus)
                while True:
                    if wx.GetKeyState(wx.WXK_SHIFT):
                        i -= 1
                    else:
                        i += 1
                    if i < 0:
                        i = len(children) - 1
                    elif i > len(children) - 1:
                        i = 0
                    if i == start:
                        return False
                    focus = children[i]
                    if (
                        focus
                        and isinstance(focus, (wx.Control, wx.grid.Grid))
                        and focus.AcceptsFocus()
                        and not focus.HasFocus()
                    ):
                        focus.SetFocus()
                        return True
        return False

    def process_data(self, data):
        """Override this method in derived classes"""
        return "invalid"

    def finish_processing(self, data, conn, command_timestamp):
        if not responseformats.get(conn):
            # Client connection has broken down in the meantime
            return
        state = self.get_app_state("plain")
        dialog = isinstance(self.get_top_window(), wx.Dialog)
        if data[0] == "setcfg" and len(data) == 4 and data[-1] == "force":
            force_setcfg = data.pop()
        else:
            force_setcfg = False
        if (
            (state in ("blocked", "busy") or dialog)
            and data[0]
            not in (
                "abort",
                "activate",
                "alt",
                "cancel",
                "close",
                "exit",
                "getactivewindow",
                "getcellvalues",
                "getmenus",
                "getmenuitems",
                "getstate",
                "getuielement",
                "getuielements",
                "getwindows",
                "interact",
                "ok",
            )
            and not force_setcfg
        ):
            if dialog:
                state = "blocked"
            self.send_response(state, data, conn, command_timestamp)
            return
        win = None
        child = None
        response = "ok"
        if data[0] in ("abort", "close", "exit"):
            if (
                hasattr(self, "worker")
                and not self.worker.abort_all()
                and self.worker.is_working()
            ):
                response = "failed"
            elif data[0] in ("close", "exit"):
                if len(data) == 2:
                    if data[0] == "exit":
                        win = None
                    else:
                        win = get_toplevel_window(data[1])
                else:
                    win = self.get_top_window()
                if win:
                    state = self.get_app_state("plain")
                    if state == "blocked" or (state != "idle" and data[0] == "exit"):
                        response = state
                    elif (
                        state not in ("busy", "idle")
                        and win is not self.get_top_window()
                    ):
                        response = "blocked"
                    elif (
                        isinstance(
                            win, (AboutDialog, BaseInteractiveDialog, ProgressDialog)
                        )
                        or win.__class__ is wx.Dialog
                    ):
                        if win.IsModal():
                            wx.CallAfter(win.EndModal, wx.ID_CANCEL)
                        else:
                            wx.CallAfter(win.Close)
                    elif isinstance(win, wx.Frame):
                        wx.CallAfter(win.Close)
                    else:
                        response = "failed"
                else:
                    if data[0] == "exit" and len(data) == 2:
                        wx.CallAfter(self.close_all)
                    else:
                        response = "invalid"
            else:
                response = "invalid"
        elif data[0] == "activate" and len(data) < 3:
            response = "ok"
            if len(data) < 2:
                win = self.get_top_window()
            else:
                try:
                    id_name_label = int(data[1])
                except ValueError:
                    id_name_label = data[1]
                for win in reversed(wx.GetTopLevelWindows()):
                    if (
                        win.Id == id_name_label
                        or win.Name == id_name_label
                        or win.Label == id_name_label
                    ) and win.IsShown():
                        break
                else:
                    win = None
            if win and win.IsShown():
                if win.IsIconized():
                    win.Restore()
                win.Raise()
            else:
                response = "invalid"
        elif data[0] in ("alt", "cancel", "ok") and (
            len(data) == 1 or (data[0] == "ok" and len(data) == 2)
        ):
            response = "invalid"
            win = self.get_top_window()
            if isinstance(win, (DirDialog, FileDialog)):
                if data[0] in ("ok", "cancel"):
                    if len(data) > 1:
                        # Path
                        win.SetPath(data[1])
                    if win.IsModal():
                        wx.CallAfter(
                            win.EndModal,
                            {"ok": wx.ID_OK, "cancel": wx.ID_CANCEL}[data[0]],
                        )
                    elif data[0] == "cancel":
                        wx.CallAfter(win.Close)
                    response = "ok"
            elif isinstance(win, (AboutDialog, BaseInteractiveDialog, ProgressDialog)):
                if hasattr(win, data[0]):
                    ctrl = getattr(win, data[0])
                    if ctrl.IsEnabled():
                        if win.IsModal():
                            wx.CallAfter(win.EndModal, ctrl.Id)
                        elif isinstance(ctrl, (FlatShadedButton, GenButton, wx.Button)):
                            event = wx.CommandEvent(wx.EVT_BUTTON.typeId, ctrl.Id)
                            event.SetEventObject(ctrl)
                            wx.CallAfter(ctrl.ProcessEvent, event)
                        response = "ok"
                    else:
                        response = "forbidden"
        elif (
            data[0] == "echo"
            and "echo <string>" in self.get_common_commands()
            and len(data) > 1
        ):
            txt = " ".join(data[1:])
            print(txt)
        elif data[0] == "invokemenu" and len(data) == 3:
            if self.get_app_state("plain") == "idle":
                menubar = self.GetMenuBar()
                response = "invalid"
            else:
                menubar = None
                response = "forbidden"
            if menubar:
                try:
                    menu_pos = int(data[1])
                except ValueError:
                    menu_pos = menubar.FindMenu(data[1])
                if (
                    menu_pos not in (wx.NOT_FOUND, None)
                    and -1 < menu_pos < menubar.GetMenuCount()
                    and menubar.IsEnabledTop(menu_pos)
                ):
                    menu = menubar.GetMenu(menu_pos)
                    try:
                        menuitem_id = int(data[2])
                    except ValueError:
                        menuitem_id = menu.FindItem(data[2])
                    if menuitem_id not in (wx.NOT_FOUND, None):
                        menuitem = menu.FindItemById(menuitem_id)
                        if menuitem.IsEnabled():
                            event = wx.CommandEvent(wx.EVT_MENU.typeId, menuitem_id)
                            event.SetEventObject(menu)
                            wx.CallAfter(self.ProcessEvent, event)
                            response = "ok"
                        else:
                            response = "forbidden"
        elif data[0] == "getactivewindow" and len(data) == 1:
            win = self.get_top_window()
            response = format_ui_element(win, responseformats[conn])
            win = None
        elif data[0] == "getcellvalues" and len(data) in (2, 3):
            response = "invalid"
            if len(data) == 3:
                win = get_toplevel_window(data[1])
            else:
                win = self.get_top_window()
            if win:
                name = data[-1]
                child = get_widget(win, name)
                if (
                    child
                    and isinstance(child, wx.grid.Grid)
                    and child.IsShownOnScreen()
                ):
                    response = []
                    for row in range(child.GetNumberRows()):
                        values = []
                        for col in range(child.GetNumberCols()):
                            values.append(child.GetCellValue(row, col))
                        if responseformats[conn] == "plain":
                            values = (
                                demjson.encode(values).strip("[]").replace('","', '" "')
                            )
                        response.append(values)
                elif child is False:
                    response = "forbidden"
                child = None
        elif data[0] == "getmenus" and len(data) == 1:
            menus = []
            menubar = self.GetMenuBar()
            if menubar:
                for i, (menu, label) in enumerate(menubar.GetMenus()):
                    label = label.lstrip("&_")
                    if responseformats[conn] != "plain":
                        menus.append(
                            {
                                "label": label,
                                "position": i,
                                "enabled": menubar.IsEnabledTop(i),
                            }
                        )
                    else:
                        menus.append(
                            "%s %s %s"
                            % (
                                i,
                                demjson.encode(label),
                                "enabled" if menubar.IsEnabledTop(i) else "disabled",
                            )
                        )
            response = menus
        elif data[0] == "getmenuitems" and len(data) < 3:
            menuitems = []
            menulabels = []
            menus = []
            menubar = self.GetMenuBar()
            if menubar:
                if len(data) == 2:
                    try:
                        menu_pos_label = int(data[1])
                    except ValueError:
                        menu_pos_label = data[1]
                for i, (menu, label) in enumerate(menubar.GetMenus()):
                    label = label.lstrip("&_")
                    if (
                        len(data) == 2
                        and label != menu_pos_label
                        and i != menu_pos_label
                    ):
                        continue
                    if responseformats[conn] != "plain" and label not in menulabels:
                        menuitems = []
                        menulabels.append(label)
                        menus.append(
                            {
                                "label": label,
                                "position": i,
                                "enabled": menubar.IsEnabledTop(i),
                                "menuitems": menuitems,
                            }
                        )
                    for menuitem in menu.GetMenuItems():
                        if menuitem.IsSeparator():
                            continue
                        if responseformats[conn] != "plain":
                            menuitems.append(
                                {
                                    "label": menuitem.Label,
                                    "id": menuitem.Id,
                                    "enabled": menubar.IsEnabledTop(i)
                                    and menuitem.IsEnabled(),
                                    "checkable": menuitem.IsCheckable(),
                                    "checked": menuitem.IsChecked(),
                                }
                            )
                        else:
                            menuitems.append(
                                "%s %s %s %s %s%s%s"
                                % (
                                    i,
                                    demjson.encode(label),
                                    menuitem.Id,
                                    demjson.encode(menuitem.Label),
                                    (
                                        "enabled"
                                        if menubar.IsEnabledTop(i)
                                        and menuitem.IsEnabled()
                                        else "disabled"
                                    ),
                                    " checkable" if menuitem.IsCheckable() else "",
                                    " checked" if menuitem.IsChecked() else "",
                                )
                            )
            if responseformats[conn] != "plain":
                response = menus
            else:
                response = menuitems
        elif data[0] == "getstate" and len(data) == 1:
            response = self.get_app_state(responseformats[conn])
        elif data[0] == "getuielement" and len(data) in (2, 3):
            response = "invalid"
            if len(data) == 3:
                win = get_toplevel_window(data[1])
            else:
                win = self.get_top_window()
            if win:
                name = data[-1]
                child = get_widget(win, name)
                if child and child.IsShownOnScreen():
                    response = format_ui_element(child, responseformats[conn])
                elif child is False:
                    response = "forbidden"
                child = None
        elif data[0] == "getuielements" and len(data) < 3:
            uielements = []
            if len(data) == 2:
                win = get_toplevel_window(data[1])
            else:
                win = self.get_top_window()
            if win:
                # Ordering in tab order
                for child in win.GetAllChildren():
                    if is_scripting_allowed(win, child):
                        uielements.append(
                            format_ui_element(child, responseformats[conn])
                        )
                child = None
                response = uielements
            else:
                response = "invalid"
        elif data[0] == "getwindows" and len(data) == 1:
            windows = [win for win in wx.GetTopLevelWindows() if win.IsShown()]
            response = [
                format_ui_element(win, responseformats[conn]) for win in windows
            ]
            win = None
        elif data[0] == "interact" and 1 < len(data) < 6:
            response = "invalid"
            value = None
            args = data[1:]
            if len(args) > 2 and args[-2] == "setvalue":
                value = args.pop()
                args.pop()
            name = args.pop()
            state = self.get_app_state("plain")
            if state == "blocked":
                win = None
                response = state
            elif args:
                # Window name specified
                win = get_toplevel_window(args[0])
                if state not in ("busy", "idle") and win is not self.get_top_window():
                    win = None
                    response = "blocked"
            else:
                win = self.get_top_window()
            if win:
                child = get_widget(win, name)
                if child is False or (
                    child and (not child.IsShownOnScreen() or not child.IsEnabled())
                ):
                    response = "forbidden"
                elif child:
                    event = None
                    if value is not None:
                        # Set value
                        values = value.split(",", 2)
                        if isinstance(child, floatspin.FloatSpin):
                            try:
                                child.SetValue(float(value))
                            except Exception:
                                response = "failed"
                            else:
                                event = floatspin.EVT_FLOATSPIN
                        elif isinstance(
                            child, (CustomCheckBox, wx.CheckBox)
                        ) and value in ("0", "1", "false", "true"):
                            child.SetValue(bool(demjson.decode(value)))
                            event = wx.EVT_CHECKBOX
                        elif isinstance(child, wx.ComboBox):
                            child.SetValue(value)
                            event = wx.EVT_TEXT
                        elif isinstance(child, wx.Choice):
                            # NOTE: Check for wx.ComboBox first because it is a
                            # subclass of wx.Choice!
                            if value in child.Items:
                                child.SetStringSelection(value)
                                event = wx.EVT_CHOICE
                        elif isinstance(
                            child,
                            (aui.AuiNotebook, labelbook.FlatBookBase, wx.Notebook),
                        ):
                            for page_idx in range(child.GetPageCount()):
                                if child.GetPageText(page_idx) == value:
                                    child.SetSelection(page_idx)
                                    event = wx.EVT_NOTEBOOK_PAGE_CHANGED
                                    break
                        elif isinstance(child, wx.grid.Grid) and len(values) == 3:
                            try:
                                row, col = (int(v) for v in values[:2])
                            except ValueError:
                                row, col = -1, -1
                            if (
                                -1 < row < child.GetNumberRows()
                                and -1 < col < child.GetNumberCols()
                            ):
                                if child.IsEditable() and not child.IsReadOnly(
                                    row, col
                                ):
                                    child.SetCellValue(row, col, values[2])
                                    event = wx.grid.GridEvent(
                                        -1,
                                        wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
                                        child,
                                        row,
                                        col,
                                    )
                                else:
                                    response = "forbidden"
                        elif isinstance(child, wx.ListCtrl):
                            for row in range(child.GetItemCount()):
                                item = []
                                for col in range(child.GetColumnCount()):
                                    item.append(child.GetItem(row, col).GetText())
                                if " ".join(item) == value:
                                    state = child.GetItemState(
                                        row, wx.LIST_STATE_SELECTED
                                    )
                                    child.Select(
                                        row, not state & wx.LIST_STATE_SELECTED
                                    )
                                    if state & wx.LIST_STATE_SELECTED:
                                        event = wx.EVT_LIST_ITEM_DESELECTED
                                    else:
                                        event = wx.EVT_LIST_ITEM_SELECTED
                                    break
                        elif isinstance(child, wx.RadioButton) and value in (
                            "0",
                            "1",
                            "false",
                            "true",
                        ):
                            child.SetValue(bool(demjson.decode(value)))
                            event = wx.EVT_RADIOBUTTON
                        elif isinstance(child, wx.Slider):
                            try:
                                child.SetValue(int(value))
                            except Exception:
                                response = "failed"
                            else:
                                event = wx.EVT_SLIDER
                        elif isinstance(child, wx.SpinCtrl):
                            try:
                                child.SetValue(int(value))
                            except Exception:
                                response = "failed"
                            else:
                                event = wx.EVT_SPINCTRL
                        elif isinstance(child, wx.TextCtrl):
                            child.ChangeValue(value)
                            event = wx.EVT_TEXT
                    elif isinstance(child, (FlatShadedButton, GenButton, wx.Button)):
                        event = wx.EVT_BUTTON
                    if event:
                        if isinstance(child, CustomCheckBox):
                            ctrl = child._cb
                        else:
                            ctrl = child
                        events = [event]
                        if event is wx.EVT_SPINCTRL:
                            events.append(wx.EVT_TEXT)
                        elif event is wx.EVT_TEXT and win.FindFocus() != ctrl:
                            events.append(wx.EVT_KILL_FOCUS)
                        for event in events:
                            if not isinstance(event, wx.Event):
                                event = wx.CommandEvent(event.typeId, ctrl.Id)
                                if isinstance(
                                    child, (CustomCheckBox, wx.CheckBox, wx.RadioButton)
                                ):
                                    event.SetInt(int(ctrl.Value))
                                event.SetEventObject(ctrl)
                            if not isinstance(ctrl, wx.Notebook):
                                # Bus error under Mac OS X
                                wx.CallAfter(ctrl.ProcessEvent, event)
                        wx.CallLater(1, child.Refresh)
                        response = "ok"
        elif data[0] == "setcfg" and len(data) == 3:
            # Set configuration option
            if data[1] in defaults:
                value = data[2]
                if value == "null":
                    value = None
                elif value == "false":
                    value = 0
                elif value == "true":
                    value = 1
                elif defaults[data[1]] is not None:
                    try:
                        value = type(defaults[data[1]])(value)
                    except ValueError:
                        pass
                setcfg(data[1], value)
                if getcfg(data[1], False) != value:
                    response = "failed"
            else:
                response = "invalid"
        else:
            try:
                response = self.process_data(data)
            except Exception as exception:
                print(exception)
                if responseformats[conn] != "plain":
                    response = {
                        "class": exception.__class__.__name__,
                        "error": str(exception),
                    }
                else:
                    response = "error " + demjson.encode(str(exception))
            else:
                # Some commands can be overriden, check response
                if response == "invalid":
                    if (
                        data[0] == "refresh"
                        and len(data) == 1
                        and hasattr(self, "update_controls")
                    ):
                        self.update_controls()
                        self.update_layout()
                        response = "ok"
                    elif data[0] == "restore-defaults":
                        for name in defaults:
                            if len(data) > 1:
                                include = False
                                for category in data[1:]:
                                    if name.startswith(data[1]):
                                        include = True
                                        break
                                if not include:
                                    continue
                            setcfg(name, None)
                        response = "ok"
                    elif (
                        data[0] == "setlanguage"
                        and len(data) == 2
                        and hasattr(self, "panel")
                        and hasattr(self, "update_controls")
                    ):
                        setcfg("lang", data[1])
                        self.panel.Freeze()
                        self.setup_language()
                        self.update_controls()
                        self.update_layout()
                        self.panel.Thaw()
                        response = "ok"
        if (
            data[0].startswith("get")
            or data[0] in ("refresh", "restore-defaults", "setcfg")
            or response != "ok"
        ):
            # No interaction with UI
            relayfunc = lambda func, *args: func(*args)
        else:
            # Interaction with UI
            # Prevent actual file dialogs blocking the UI - need to restore
            # original values after processing
            wx.DirDialog = DirDialog
            wx.FileDialog = FileDialog
            # Use CallLater so GUI methods have a chance to run before we send
            # our response
            relayfunc = lambda func, *args: wx.CallLater(55, func, *args)
            relayfunc(restore_path_dialog_classes)
        relayfunc(
            self.send_response, response, data, conn, command_timestamp, child or win
        )

    def send_response(self, response, data, conn, command_timestamp, win=None):
        if not responseformats.get(conn):
            # Client connection has broken down in the meantime
            return
        if response == "invalid":
            print(lang.getstr("app.incoming_message.invalid"))
        if responseformats[conn] != "plain":
            if not isinstance(response, (str, list)):
                response = [response]
            command = {"name": data[0], "timestamp": command_timestamp}
            if data[1:]:
                command["arguments"] = data[1:]
            response = {
                "command": command,
                "result": response,
                "timestamp": datetime.now().strftime("%Y-%m-%dTH:%M:%S.%f"),
            }
            if win:
                response["object"] = format_ui_element(win, responseformats[conn])
        if responseformats[conn].startswith("json"):
            response = demjson.encode(
                response, compactly=responseformats[conn] == "json"
            )
        elif responseformats[conn].startswith("xml"):
            response = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                + (responseformats[conn] == "xml.pretty" and "\n" or "")
                + dict2xml(
                    response, "response", pretty=responseformats[conn] == "xml.pretty"
                )
            )
        else:
            if isinstance(response, dict):
                response = [
                    "%s = %s" % (name, value) for name, value in response.items()
                ]
            if isinstance(response, list):
                response = "\n".join(response)
        try:
            conn.sendall(("%s\4" % safe_str(response, "UTF-8")).encode("utf-8"))
        except socket.error as exception:
            print(exception)

    def send_command(self, scripting_host_name_suffix, command):
        lock_name = appbasename
        scripting_host = appname
        if scripting_host_name_suffix:
            lock_name += "-" + scripting_host_name_suffix
            scripting_host += "-" + scripting_host_name_suffix
        try:
            for host in self.get_scripting_hosts():
                ip_port, name = host.split(None, 1)
                if name == lock_name:
                    ip, port = ip_port.split(":", 1)
                    port = int(port)
                    conn = self.connect(ip, port)
                    if isinstance(conn, Exception):
                        raise conn
                    # Check if we're actually connected to the right
                    # application (if it terminated unexpectedly, something
                    # else may have grabbed the port)
                    conn.send_command("getappname")
                    response = conn.get_single_response()
                    if response == scripting_host:
                        conn.send_command(command)
                        response = conn.get_single_response()
                        print(f"{scripting_host} {command} returned", response)
                    else:
                        print(
                            f"Warning - {scripting_host} not running under expected port",
                            port,
                        )
                    del conn
                    return response
            else:
                print(f"Warning - {scripting_host} not running?")
        except Exception as exception:
            print(f"Warning - couldn't talk to {scripting_host}:", exception)
            return exception

    def focus_handler(self, event=None):
        # IMPORTANT: event can either be EVT_TEXT, EVT_SET_FOCUS, EVT_CLOSE,
        # EVT_MENU or EVT_BUTTON.
        # This means the available event methods will be different, e.g.
        # only EVT_SET_FOCUS will have a GetWindow method, and EVT_MENU's
        # GetEventObject method returns the menu item which doesn't have
        # most methods that controls would have.
        if not event:
            event = CustomEvent(wx.EVT_SET_FOCUS.evtType[0], self)
        if debug:
            if hasattr(event.GetEventObject(), "GetId"):
                print(
                    "[D] focus_handler called for ID %s %s %s, event type "
                    "%s %s"
                    % (
                        event.GetEventObject().GetId(),
                        getevtobjname(event, self),
                        event.GetEventObject().__class__,
                        event.GetEventType(),
                        getevttype(event),
                    )
                )
            else:
                print(
                    "[D] focus_handler called for %s %s, event type "
                    "%s %s"
                    % (
                        getevtobjname(event, self),
                        event.GetEventObject().__class__,
                        event.GetEventType(),
                        getevttype(event),
                    )
                )
            if (
                hasattr(event, "GetWindow")
                and event.GetWindow()
                and event.GetEventObject() != event.GetWindow()
            ):
                print(
                    "[D] Focus moving from control ID %s %s %s"
                    % (
                        event.GetWindow().GetId(),
                        event.GetWindow().GetName(),
                        event.GetWindow().__class__,
                    )
                )
            if getattr(self, "last_focused_ctrl", None):
                print(
                    "[D] Last focused control: ID %s %s %s"
                    % (
                        self.last_focused_ctrl.GetId(),
                        self.last_focused_ctrl.GetName(),
                        self.last_focused_ctrl.__class__,
                    )
                )
        if (
            getattr(self, "last_focused_ctrl", None)
            and isinstance(self.last_focused_ctrl, wx.ComboBox)
            and self.last_focused_ctrl != event.GetEventObject()
            and self.last_focused_ctrl.IsShownOnScreen()
            and event.GetEventObject()
            and (
                not hasattr(event.GetEventObject(), "IsShownOnScreen")
                or event.GetEventObject().IsShownOnScreen()
            )
        ):
            catchup_event = wx.FocusEvent(
                wx.EVT_KILL_FOCUS.evtType[0], self.last_focused_ctrl.GetId()
            )
            if debug:
                print(
                    "[D] Last focused control ID %s %s %s processing "
                    "catchup event type %s %s"
                    % (
                        self.last_focused_ctrl.GetId(),
                        self.last_focused_ctrl.GetName(),
                        self.last_focused_ctrl.__class__,
                        catchup_event.GetEventType(),
                        getevttype(catchup_event),
                    )
                )
            if self.last_focused_ctrl.ProcessEvent(catchup_event):
                if debug:
                    print("[D] Last focused control processed catchup " "event")
                self.last_focused_ctrl = None
        if (
            hasattr(event.GetEventObject(), "GetId")
            and callable(event.GetEventObject().GetId)
            and isinstance(event.GetEventObject(), wx.Control)
            and event.GetEventObject() != getattr(self, "last_focused_ctrl", None)
            and hasattr(event.GetEventObject(), "IsShownOnScreen")
            and event.GetEventObject().IsShownOnScreen()
        ):
            if debug:
                print(
                    "[D] Setting last focused control to ID %s %s %s"
                    % (
                        event.GetEventObject().GetId(),
                        getevtobjname(event, self),
                        event.GetEventObject().__class__,
                    )
                )
            self.last_focused_ctrl = event.GetEventObject()
        if isinstance(event, wx.FocusEvent) or isinstance(
            event.GetEventObject(), wx.ComboBox
        ):
            event.Skip()

    def setup_language(self):
        """Substitute translated strings for menus, controls, labels and tooltips."""
        if not hasattr(self, "_menulabels"):
            # Needed for Phoenix because custom attributes attached to menus
            # are not retained
            self._menulabels = {}
        if not hasattr(self, "_ctrllabels"):
            # Needed for Phoenix because custom attributes attached to controls
            # may not be retained
            self._ctrllabels = {}
        if not hasattr(self, "_tooltipstrings"):
            # Needed for Phoenix because custom attributes attached to controls
            # may not be retained
            self._tooltipstrings = {}

        # Title
        if not hasattr(self, "_Title"):
            # Backup un-translated label
            title = self._Title = self.Title
        else:
            # Restore un-translated label
            title = self._Title
        translated = lang.getstr(title)
        if translated != title:
            self.Title = translated

        # Menus
        menubar = self.menubar if hasattr(self, "menubar") else self.GetMenuBar()
        if menubar:
            for menu, label in menubar.GetMenus():
                menu_pos = menubar.FindMenu(label)
                if menu not in self._menulabels:
                    # Backup un-translated label
                    self._menulabels[menu] = label
                menubar.SetMenuLabel(
                    menu_pos,
                    "&" + lang.getstr(GTKMenuItemGetFixedLabel(self._menulabels[menu])),
                )
                self.setup_menu_language(menu)
            if sys.platform == "darwin":
                wx.GetApp().SetMacHelpMenuTitleName(lang.getstr("menu.help"))
            if isinstance(menubar, wx.MenuBar):
                self.SetMenuBar(menubar)

        # Controls and labels
        for child in self.GetAllChildren():
            if isinstance(
                child,
                (
                    wx.StaticText,
                    wx.Control,
                    BetterStaticFancyText,
                    BitmapBackgroundPanelText,
                ),
            ):
                if child not in self._ctrllabels:
                    # Backup un-translated label
                    label = self._ctrllabels[child] = child.Label
                else:
                    # Restore un-translated label
                    label = self._ctrllabels[child]
                translated = lang.getstr(label)
                if translated != label:
                    if isinstance(child, wx.Button):
                        translated = translated.replace("&", "&&")
                    elif isinstance(
                        child, BetterStaticFancyText
                    ) and child.Name.endswith("_info_text"):
                        if lang.getcode() == "ko":
                            # Korean text runs too wide on info panels with
                            # default wrap of 119
                            child.maxlen = 70
                        else:
                            child.maxlen = 119
                        if child.Name == "display_instrument_warmup_info_text":
                            # Fix spacing - exactly one blank line between
                            # warmup info and instrument/disptech info text
                            translated += "\n&#160;"
                    child.Label = translated
                if child.ToolTip:
                    if child not in self._tooltipstrings:
                        # Backup un-translated tooltip
                        tooltipstr = self._tooltipstrings[child] = child.ToolTip.Tip
                    else:
                        # Restore un-translated tooltip
                        tooltipstr = self._tooltipstrings[child]
                    translated = lang.getstr(tooltipstr)
                    if translated != tooltipstr:
                        child.SetToolTipString(translated)
            elif isinstance(child, FileBrowseBitmapButtonWithChoiceHistory):
                if child.history:
                    selection = child.textControl.GetSelection()
                    child.textControl.Clear()
                    for path in child.history:
                        child.textControl.Append(child.GetName(path))
                    child.textControl.SetSelection(selection)

    def setup_menu_language(self, menu):
        if not hasattr(self, "_menuitems"):
            self._menuitems = {}

        if menu not in self._menuitems:
            # Backup un-translated labels
            self._menuitems[menu] = []
            for item in menu.GetMenuItems():
                item_label = item.GetItemLabelText()
                self._menuitems[menu].append((item, item_label))

        for item, label in self._menuitems[menu]:
            item_label = item.GetItemLabelText()
            if item_label and item_label != "":
                label = GTKMenuItemGetFixedLabel(label)
                localized_label = lang.getstr(label)
                if item.Accel:
                    localized_label_text_with_accel = "{}\t{}".format(
                        localized_label, item.Accel.ToString()
                    )
                    # item.Text = localized_label_text_with_accel
                    item.SetItemLabel(localized_label_text_with_accel)
                else:
                    # item.Text = localized_label
                    item.SetItemLabel(localized_label)
            if item.SubMenu:
                self.setup_menu_language(item.SubMenu)

    def update_layout(self):
        """Update main window layout."""
        border_lr = self.Size[0] - self.ClientSize[0]
        border_tb = self.Size[1] - self.ClientSize[1]
        clientarea = self.GetDisplay().ClientArea
        sw = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
        if sys.platform not in ("darwin", "win32"):  # Linux
            if os.getenv("XDG_SESSION_TYPE") == "wayland":
                # Client-side decorations
                safety_margin = 0
            else:
                # Assume server-side decorations
                safety_margin = 40
        else:
            safety_margin = 20
        w, h = 0, 0
        for child in self.Children:
            if child.IsShown():
                if child.Sizer:
                    size = child.Sizer.CalcMin()
                else:
                    size = child.BestSize
                w = max(size[0], w)
                h += max(size[1], 0)
        minsize = (
            min(clientarea[2] - border_lr, w + sw),
            min(clientarea[3] - border_tb - safety_margin, h),
        )
        clientsize = (
            min(clientarea[2] - border_lr, self.ClientSize[0]),
            min(clientarea[3] - border_tb - safety_margin, self.ClientSize[1]),
        )
        if not self.IsIconized() and not self.IsMaximized():
            if os.getenv("XDG_SESSION_TYPE") == "wayland":
                self.MaxSize = (-1, -1)
            if (
                minsize[0] > clientsize[0]
                or minsize[1] != clientsize[1]
                or not getattr(self, "_layout", False)
            ):
                if not getattr(self, "_layout", False):
                    clientsize = minsize
                elif os.getenv("XDG_SESSION_TYPE") != "wayland":
                    # XXX this causes brief flickering to previous height on
                    # manual resize under Wayland
                    clientsize = clientsize[0], minsize[1]
                self.Sizer.SetMinSize(
                    (max(minsize[0], clientsize[0]), max(minsize[1], clientsize[1]))
                )
                self.GetSizer().SetSizeHints(self)
                self.GetSizer().Layout()
                self._layout = True
            else:
                self.Layout()
            if os.getenv("XDG_SESSION_TYPE") == "wayland":
                self.MaxSize = self.Size
                wx.CallAfter(set_maxsize, self, (-1, -1))
        self.Sizer.SetMinSize((minsize[0], minsize[1]))
        if hasattr(self, "MinClientSize"):
            # wxPython >= 2.9
            self.MinClientSize = minsize
        else:
            # wxPython < 2.9
            self.SetMinSize(self.ClientToWindowSize(minsize))

    def set_child_ctrls_as_attrs(self, parent=None):
        """Set child controls and labels as attributes of the frame.

        Will also set a maximum font size of 11 pt.
        parent is the window over which children will be iterated and
        defaults to self.

        """
        if not parent:
            parent = self
        scale = getcfg("app.dpi") / get_default_dpi()
        for child in parent.GetAllChildren():
            if debug:
                print(child.__class__, child.Name)
            if isinstance(
                child,
                (
                    wx.StaticText,
                    wx.Control,
                    filebrowse.FileBrowseButton,
                    floatspin.FloatSpin,
                ),
            ):
                if (
                    isinstance(child, wx.Choice)
                    and sys.platform not in ("darwin", "win32")
                    and child.MinSize[1] == -1
                ):
                    # wx.Choice can have varying height based on GTK theme if
                    # no initial items. Simply always set min height to that
                    # of a wx.Choice with items.
                    if not hasattr(BaseFrame, "_choiceheight"):
                        choice = wx.Choice(self, choices=["|"])
                        BaseFrame._choiceheight = choice.Size[1]
                        choice.Destroy()
                    child.MinSize = child.MinSize[0], BaseFrame._choiceheight
                elif isinstance(child, wx.BitmapButton):
                    if "gtk3" in wx.PlatformInfo:
                        # GTK3 doesn't respect NO_BORDER in hovered state when
                        # using wx.BitmapButton and looks ugly
                        orig_child = child
                        child = GenBitmapButton(
                            child.Parent,
                            -1,
                            child.BitmapLabel,
                            child.Position,
                            child.MinSize,
                            child.WindowStyle,
                            child.Validator or wx.DefaultValidator,
                            child.Name,
                        )
                        child.BackgroundColour = orig_child.Parent.BackgroundColour
                        child.Enabled = orig_child.Enabled
                        # wxPython Classic / Phoenix
                        for tt_attr in ("ToolTipString", "ToolTip"):
                            if hasattr(orig_child, tt_attr):
                                break
                        orig_tt = getattr(orig_child, tt_attr, None)
                        if orig_tt:
                            if isinstance(orig_tt, wx.ToolTip):
                                orig_tt = orig_tt.Tip
                            setattr(child, tt_attr, orig_tt)
                        orig_child.ContainingSizer.Replace(orig_child, child)
                        orig_child.Destroy()
                    else:
                        set_bitmap_labels(child)
                elif (
                    isinstance(child, wx._SpinCtrl)
                    and not hasattr(child, "_spinwidth")
                    and "gtk3" in wx.PlatformInfo
                ):
                    if not getattr(wx.SpinCtrl, "_spinwidth", 0):
                        spin = wx.SpinCtrl(self, -1)
                        text = wx.TextCtrl(self, -1)
                        wx.SpinCtrl._spinwidth = spin.Size[0] - text.Size[0] + 11
                        spin.Destroy()
                        text.Destroy()
                    child.MinSize = (
                        child.MinSize[0] + wx.SpinCtrl._spinwidth,
                        child.MinSize[1],
                    )
                elif isinstance(child, wx._StaticText) and "gtk3" in wx.PlatformInfo:
                    if (
                        child.__class__.SetLabel
                        is not wx.StaticText.__dict__["SetLabel"]
                    ):
                        child.__class__.SetLabel = wx.StaticText.__dict__["SetLabel"]
                    if child.__class__.Label is not wx.StaticText.__dict__["Label"]:
                        child.__class__.Label = property(
                            child.__class__.GetLabel, child.__class__.SetLabel
                        )
                elif isinstance(child, wx.ComboBox) and "gtk3" in wx.PlatformInfo:
                    # ComboBox is not wide enough to accomodate its text
                    # box under GTK3
                    child.MinSize = (
                        max(child.MinSize[0], int(170 * scale)),
                        child.MinSize[1],
                    )
                child.SetMaxFontSize(11)
                if sys.platform == "darwin":
                    # Work around ComboBox issues on Mac OS X
                    # (doesn't receive EVT_KILL_FOCUS)
                    if isinstance(child, wx.ComboBox):
                        if child.IsEditable():
                            if debug:
                                print(
                                    "[D]", child.Name, "binds EVT_TEXT to focus_handler"
                                )
                            child.Bind(wx.EVT_TEXT, self.focus_handler)
                    else:
                        child.Bind(wx.EVT_SET_FOCUS, self.focus_handler)
                if not hasattr(self, child.Name):
                    setattr(self, child.Name, child)
            if (
                sys.platform == "win32"
                and sys.getwindowsversion() >= (6,)
                and isinstance(child, wx.Panel)
            ):
                # No need to enable double buffering under Linux and Mac OS X.
                # Under Windows, enabling double buffering on the panel seems
                # to work best to reduce flicker.
                child.SetDoubleBuffered(True)
            if (
                sys.platform != "darwin"
                and isinstance(child, wx.Panel)
                and child.AcceptsFocus()
            ):
                # Has no children that can accept focus, so there is no reason
                # why this should be able to receive focus, ever.
                # Move focus to the next control.
                child.Bind(
                    wx.EVT_SET_FOCUS,
                    lambda event: event.EventObject.AcceptsFocus()
                    and event.EventObject.Navigate(
                        int(not wx.GetKeyState(wx.WXK_SHIFT))
                    )
                    or event.Skip(),
                )

    def getcfg(self, name, fallback=True, raw=False, cfg=config.cfg):
        return getcfg(name, fallback, raw, cfg)

    def hascfg(self, name, fallback=True, cfg=config.cfg):
        return hascfg(name, fallback, cfg)

    def setcfg(self, name, value, cfg=config.cfg):
        setcfg(name, value, cfg)


class BaseInteractiveDialog(wx.Dialog):
    """Base class for informational and confirmation dialogs"""

    def __init__(
        self,
        parent=None,
        id=-1,
        title=appname,
        msg="",
        ok=None,
        bitmap=None,
        pos=(-1, -1),
        size=(400, -1),
        show=True,
        log=True,
        style=wx.DEFAULT_DIALOG_STYLE,
        nowrap=False,
        wrap=70,
        name=wx.DialogNameStr,
        bitmap_margin=None,
    ):
        if not ok:
            ok = lang.getstr("ok")
        self._log = log
        self._msg = msg
        if parent:
            pos = list(pos)
            i = 0
            for coord in pos:
                if coord > -1:
                    pos[i] += parent.GetScreenPosition()[i]
                i += 1
            pos = tuple(pos)
            if title == appname:
                appid = get_appid_from_window_hierarchy(parent)
                base_appid = appname.lower()
                appid2title = {
                    base_appid + "-3dlut-maker": "3dlut.frame.title",
                    base_appid + "-curve-viewer": "calibration.lut_viewer.title",
                    base_appid + "-profile-info": "profile.info",
                    base_appid + "-scripting-client": "scripting-client",
                    base_appid + "-synthprofile": "synthicc.create",
                    base_appid + "-testchart-editor": "testchart.edit",
                    base_appid + "-vrml-to-x3d-converter": "vrml_to_x3d_converter",
                }
                title = lang.getstr(appid2title.get(appid, "window.title"))
        scale = int(getcfg("app.dpi") / get_default_dpi())
        if scale > 1 and size == (400, -1):
            size = size[0] * scale, size[1]
        wx.Dialog.__init__(self, parent, id, title, pos, size, style, name)
        self.taskbar = None
        if sys.platform == "win32":
            bgcolor = self.BackgroundColour
            self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
            if taskbar:
                if parent and parent.IsShownOnScreen():
                    taskbarframe = parent
                else:
                    taskbarframe = self
                if hasattr(taskbarframe, "taskbar"):
                    self.taskbar = taskbarframe.taskbar
                else:
                    self.taskbar = taskbar.Taskbar(taskbarframe)
        self.SetPosition(pos)  # yes, this is needed

        self.Bind(wx.EVT_SHOW, self.OnShow, self)

        margin = 12

        if bitmap_margin is None:
            bitmap_margin = margin

        self.sizer0 = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer0)
        if bitmap:
            self.sizer1 = wx.FlexGridSizer(1, 2, 0, 0)
        else:
            self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer3 = wx.FlexGridSizer(0, 1, 0, 0)
        self.sizer0.Add(self.sizer1, flag=wx.ALIGN_LEFT | wx.RIGHT, border=margin)
        self.buttonpanel = wx.Panel(self)
        self.buttonpanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.buttonpanel.Sizer.Add(
            self.sizer2, 1, flag=wx.ALL | wx.EXPAND, border=margin
        )
        if sys.platform == "win32":
            self.buttonpanel_line = wx.Panel(self, size=(-1, 1))
            self.buttonpanel_line.SetBackgroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
            )
            self.sizer0.Add(
                self.buttonpanel_line, flag=wx.TOP | wx.EXPAND, border=margin
            )
            self.buttonpanel.SetBackgroundColour(bgcolor)
        self.sizer0.Add(self.buttonpanel, flag=wx.EXPAND)

        if bitmap_margin:
            flags = wx.LEFT | wx.TOP
        else:
            flags = 0
        if bitmap:
            self.bitmap = wx.StaticBitmap(self, -1, bitmap)
            self.sizer1.Add(self.bitmap, flag=flags, border=margin)
            if self.taskbar:
                state = None
                if bitmap is geticon(32, "dialog-error"):
                    state = taskbar.TBPF_ERROR
                elif bitmap is geticon(32, "dialog-warning"):
                    state = taskbar.TBPF_PAUSED
                if state is not None:
                    if (
                        state == taskbar.TBPF_ERROR
                        or not isinstance(self.Parent, ProgressDialog)
                        or self.Parent.paused
                    ):
                        self.taskbar.set_progress_state(state)
                    if not isinstance(self.Parent, ProgressDialog):
                        self.taskbar.set_progress_value(self.taskbar.maxv)

        self.sizer1.Add(self.sizer3, flag=wx.ALIGN_LEFT | flags | wx.TOP, border=margin)
        msg = msg.replace("&", "&&")
        self.message = wx.StaticText(
            self, -1, msg if nowrap else util_str.wrap(msg, wrap)
        )
        if sys.platform == "win32":
            # Prevent text cutoff (wxWidgets bug)
            self.message.MinSize = (
                self.message.Size[0] + math.ceil(1 * scale),
                self.message.MinSize[1],
            )
        self.sizer3.Add(self.message)

        btnwidth = 80

        self.ok = wx.Button(self.buttonpanel, wx.ID_OK, ok)
        self.sizer2.Add((-1, 1), 1)
        self.sizer2.Add(self.ok)
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_OK)

        self.buttonpanel.Layout()
        self.sizer0.SetSizeHints(self)
        self.sizer0.Layout()
        self.pos = pos
        if show:
            self.ok.SetDefault()
            self.ShowModalThenDestroy()

    def ShowModalThenDestroy(self):
        result = self.ShowModal()
        self.Destroy()
        return result

    def OnShow(self, event):
        event.Skip()
        if not getattr(event, "IsShown", getattr(event, "GetShow", bool))():
            return
        if self._log:
            print(box(self._msg))
        app = wx.GetApp()
        # Make sure taskbar button flashes under Windows
        topwindow = app.GetTopWindow()
        topwindow_shown = topwindow and topwindow.IsShown()
        if topwindow_shown:
            window = topwindow
        else:
            window = self.Parent or self
        # Only request user attention if toplevel window has a non-empty title
        if (
            not app.IsActive()
            or (self.Parent and not topwindow_shown and getattr(topwindow, "Title", ""))
        ) and hasattr(window, "RequestUserAttention"):
            window.RequestUserAttention()
            if window != self:
                self.RequestUserAttention()

    def OnClose(self, event):
        if event.GetEventObject() == self:
            id = wx.ID_CANCEL
        else:
            id = event.GetId()
        if self._log and isinstance(self, ConfirmDialog):
            if hasattr(self, "FindWindow"):
                # wxPython 4
                ctrl = self.FindWindow(id)
            else:
                # wxPython 3
                ctrl = self.FindWindowById(id)
            if ctrl:
                print("->", ctrl.Label)
        self.EndModal(id)

    def EndModal(self, id):
        # Re-enable other windows
        if hasattr(self, "_disabler"):
            del self._disabler
        if self.IsModal():
            wx.Dialog.EndModal(self, id)
        else:
            # Process wx.WindowModalDialogEvent
            event = wx.WindowModalDialogEvent(
                wx.wxEVT_WINDOW_MODAL_DIALOG_CLOSED, self.Id
            )
            event.SetInt(id)
            self.ProcessEvent(event)
            self.Hide()

    def Show(self, show=True):
        if show:
            self.set_position()
        return wx.Dialog.Show(self, show)

    def ShowModal(self):
        self.set_position()
        result = wx.Dialog.ShowModal(self)
        if self:
            self.update_taskbar()
        return result

    def update_taskbar(self):
        if self and self.taskbar:
            state = None
            if (
                isinstance(self.Parent, ProgressDialog)
                and self.Parent.timer.IsRunning()
            ):
                if self.Parent.indeterminate:
                    state = taskbar.TBPF_INDETERMINATE
                elif not self.Parent.paused:
                    state = taskbar.TBPF_NORMAL
            else:
                state = taskbar.TBPF_NOPROGRESS
            if state is not None:
                self.taskbar.set_progress_state(state)

    def ShowWindowModal(self):
        self.set_position()
        self._disabler = BetterWindowDisabler(self, self.Parent)
        if hasattr(wx.Dialog, "ShowWindowModal") and sys.platform == "darwin":
            # wx 2.9+
            wx.Dialog.ShowWindowModal(self)
        else:
            self.Show()

    def ShowWindowModalBlocking(self):
        """Blocking ShoWindowModal implementation.

        Normally, ShowWindowModal is only implemented under macOS and doesn't
        block. This version blocks, while still allowing interaction with
        windows other than the parent (i.e. like ShowModal under platforms
        other than macOS).

        """
        result = {"dlg": None, "retcode": wx.ID_CANCEL}

        def OnCloseWindowModalDialog(event):
            result["dlg"] = event.GetDialog()
            result["retcode"] = event.GetReturnCode()

        self.Unbind(wx.EVT_WINDOW_MODAL_DIALOG_CLOSED)
        self.Bind(wx.EVT_WINDOW_MODAL_DIALOG_CLOSED, OnCloseWindowModalDialog)
        self.ShowWindowModal()
        while self and result["dlg"] is not self:
            wx.Yield()
            sleep(1.0 / 60)
        return result["retcode"]

    def set_position(self):
        if self.Parent and self.Parent.IsIconized():
            self.Parent.Restore()
        if not getattr(self, "pos", None) or self.pos == (-1, -1):
            self.Center(wx.BOTH)
        elif self.pos[0] == -1:
            self.Center(wx.HORIZONTAL)
        elif self.pos[1] == -1:
            self.Center(wx.VERTICAL)


if not hasattr(wx, "WindowModalDialogEvent") or sys.platform != "darwin":
    # Fake it or overwrite it, as we can't use GetDialog/GetReturnCode otherwise

    wx.wxEVT_WINDOW_MODAL_DIALOG_CLOSED = wx.NewEventType()
    wx.EVT_WINDOW_MODAL_DIALOG_CLOSED = wx.PyEventBinder(
        wx.wxEVT_WINDOW_MODAL_DIALOG_CLOSED, 1
    )

    class WindowModalDialogEvent(wx.PyCommandEvent):
        def __init__(self, commandType=wx.wxEVT_NULL, id=0):
            wx.PyCommandEvent.__init__(self, commandType, id)

        def GetDialog(self):
            return wx.FindWindowById(self.Id)

        def GetReturnCode(self):
            return self.GetInt()

    wx.WindowModalDialogEvent = WindowModalDialogEvent


class HtmlInfoDialog(BaseInteractiveDialog):
    def __init__(
        self,
        parent=None,
        id=-1,
        title=appname,
        msg="",
        html="",
        ok="OK",
        bitmap=None,
        pos=(-1, -1),
        size=(400, -1),
        show=True,
        log=True,
        bitmap_margin=None,
    ):
        BaseInteractiveDialog.__init__(
            self,
            parent,
            id,
            title,
            msg,
            ok,
            bitmap,
            pos,
            size,
            False,
            log,
            bitmap_margin=bitmap_margin,
        )

        scale = getcfg("app.dpi") / config.get_default_dpi()
        if scale < 1:
            scale = 1
        htmlwnd = HtmlWindow(
            self, -1, size=(332 * scale, 200 * scale), style=wx.BORDER_THEME
        )
        htmlwnd.SetPage(html)
        self.sizer3.Add(htmlwnd, 1, flag=wx.TOP | wx.ALIGN_LEFT | wx.EXPAND, border=12)
        self.sizer0.SetSizeHints(self)
        self.sizer0.Layout()
        if show:
            self.ok.SetDefault()
            self.ShowModalThenDestroy()


class HtmlWindow(wx.html.HtmlWindow):
    def __init__(self, *args, **kwargs):
        wx.html.HtmlWindow.__init__(self, *args, **kwargs)
        scale = max(getcfg("app.dpi") / config.get_default_dpi(), 1)
        if "gtk3" in wx.PlatformInfo:
            size = int(
                round(
                    wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT).PointSize * scale
                )
            )
        else:
            size = -1
        self.SetStandardFonts(size)
        self.Bind(
            wx.html.EVT_HTML_LINK_CLICKED,
            lambda event: launch_file(event.GetLinkInfo().Href),
        )

    def SetPage(self, source):
        """Set displayed page with system default colors"""
        html = str(source)
        bgcolor, text, linkcolor, vlinkcolor = get_html_colors()
        if "<body" not in html:
            html = "<body>%s</body>" % html
        html = re.sub(
            r"<body[^>]*",
            '<body bgcolor="%s" text="%s" link="%s" alink="%s" vlink="%s"'
            % (
                bgcolor.GetAsString(wx.C2S_HTML_SYNTAX),
                text.GetAsString(wx.C2S_HTML_SYNTAX),
                linkcolor.GetAsString(wx.C2S_HTML_SYNTAX),
                linkcolor.GetAsString(wx.C2S_HTML_SYNTAX),
                vlinkcolor.GetAsString(wx.C2S_HTML_SYNTAX),
            ),
            html,
        )
        wx.html.HtmlWindow.SetPage(self, html)


class BitmapBackgroundBitmapButton(wx.BitmapButton):
    """A BitmapButton that will use its parent bitmap background.

    The parent needs to have a GetBitmap() method.

    """

    def __init__(self, *args, **kwargs):
        wx.BitmapButton.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def OnPaint(self, dc):
        dc = wx.PaintDC(self)
        try:
            dc = wx.GCDC(dc)
        except Exception as exception:
            pass
        dc.DrawBitmap(self.Parent.GetBitmap(), 0, -self.GetPosition()[1])
        dc.DrawBitmap(self.GetBitmapLabel(), 0, 0)


bitmaps = {}


class BitmapBackgroundPanel(wx.PyPanel):
    """A panel with a background bitmap"""

    def __init__(self, *args, **kwargs):
        wx.PyPanel.__init__(self, *args, **kwargs)
        self._bitmap = None
        self.alpha = 1.0
        self.blend = False
        self.borderbtmcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
        self.bordertopcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
        self.drawborderbtm = False
        self.drawbordertop = False
        self.repeat_sub_bitmap_h = None
        self.scalebitmap = (True, False)
        self.scalequality = wx.IMAGE_QUALITY_NORMAL
        if "gtk3" in wx.PlatformInfo:
            # Fix background color not working for panels under GTK3
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        else:
            self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    if "gtk3" in wx.PlatformInfo:
        OnEraseBackground = wx_Panel.__dict__["OnEraseBackground"]

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False

    def GetBitmap(self):
        return self._bitmap

    def SetBitmap(self, bitmap):
        self._bitmap = bitmap

    def OnPaint(self, event):
        if sys.platform != "win32":
            # AutoBufferedPaintDCFactory is the magic needed for crisp text
            # rendering in HiDPI mode under OS X and Linux
            cls = wx.AutoBufferedPaintDCFactory
        else:
            cls = wx.BufferedPaintDC
        dc = cls(self)
        self._draw(dc)

    def OnSize(self, event):
        self.Refresh()
        event.Skip()

    def _draw(self, dc):
        bgcolor = self.BackgroundColour
        bbr = wx.Brush(bgcolor, wx.SOLID)
        dc.SetBackground(bbr)
        dc.SetBackgroundMode(wx.SOLID)
        dc.Clear()
        dc.SetTextForeground(self.GetForegroundColour())
        bmp = self._bitmap
        if bmp:
            if self.alpha < 1.0 or self.blend:
                key = (
                    id(bmp),
                    (bgcolor.Red(), bgcolor.Green(), bgcolor.Blue()),
                    self.alpha,
                )
                bmp = bitmaps.get(key)
                if not bmp:
                    bmp = self._bitmap
                    image = bmp.ConvertToImage()
                    if self.alpha < 1.0:
                        if not image.HasAlpha():
                            image.InitAlpha()
                        alphabuffer = image.GetAlphaBuffer()
                        for i, byte in enumerate(alphabuffer):
                            if byte > 0:
                                alphabuffer[i] = int(round(byte * self.alpha))
                    if self.blend:
                        databuffer = image.GetDataBuffer()
                        for i, byte in enumerate(databuffer):
                            if byte > 0:
                                databuffer[i] = int(
                                    round(byte * (bgcolor[i % 3] / 255.0))
                                )
                    bmp = image.ConvertToBitmap()
                    bitmaps[key] = bmp
            if True in self.scalebitmap:
                img = bmp.ConvertToImage()
                img.Rescale(
                    self.GetSize()[0] if self.scalebitmap[0] else img.GetSize()[0],
                    self.GetSize()[1] if self.scalebitmap[1] else img.GetSize()[1],
                    quality=self.scalequality,
                )
                bmp = img.ConvertToBitmap()
            dc.DrawBitmap(bmp, 0, 0)
            if (
                self.repeat_sub_bitmap_h
                and self.Size[0] > bmp.Size[0] >= self.repeat_sub_bitmap_h[0]
                and bmp.Size[1] >= self.repeat_sub_bitmap_h[1]
            ):
                sub_bmp = bmp.GetSubBitmap(self.repeat_sub_bitmap_h)
                sub_img = sub_bmp.ConvertToImage()
                sub_img.Rescale(
                    self.GetSize()[0] - bmp.GetSize()[0],
                    bmp.GetSize()[1] if self.scalebitmap[1] else sub_bmp.GetSize()[1],
                    quality=self.scalequality,
                )
                dc.DrawBitmap(sub_img.ConvertToBitmap(), bmp.GetSize()[0], 0)
        if self.drawbordertop:
            pen = wx.Pen(self.bordertopcolor, 1, wx.SOLID)
            pen.SetCap(wx.CAP_BUTT)
            dc.SetPen(pen)
            dc.DrawLine(0, 0, self.GetSize()[0], 0)
        if self.drawborderbtm:
            pen = wx.Pen(self.borderbtmcolor, 1, wx.SOLID)
            pen.SetCap(wx.CAP_BUTT)
            dc.SetPen(pen)
            dc.DrawLine(
                0, self.GetSize()[1] - 1, self.GetSize()[0], self.GetSize()[1] - 1
            )


class BitmapBackgroundPanelText(BitmapBackgroundPanel):
    """A panel with a background bitmap and text label"""

    def __init__(self, *args, **kwargs):
        BitmapBackgroundPanel.__init__(self, *args, **kwargs)
        self.label_x = None
        self.label_y = None
        self.textalpha = 1.0
        self.textshadow = True
        self.textshadowcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
        self.use_gcdc = False
        self._label = ""

    def _set_font(self, dc):
        font = self.GetFont()
        if self.use_gcdc:
            # NOTE: Drawing text to wx.GCDC has problems with unicode chars
            # being replaced with boxes under wxGTK
            try:
                dc = wx.GCDC(dc)
            except Exception as exception:
                pass
        font.SetPointSize(get_dc_font_size(font.GetPointSize(), dc))
        dc.SetFont(font)
        return dc

    def GetLabel(self):
        return self._label

    @property
    def Label(self):
        return self.GetLabel()

    @Label.setter
    def Label(self, label):
        self.SetLabel(label)

    def SetLabel(self, label):
        self._label = label

    def _draw(self, dc):
        BitmapBackgroundPanel._draw(self, dc)
        dc.SetBackgroundMode(wx.TRANSPARENT)
        dc = self._set_font(dc)
        label = self.Label.splitlines()
        for i, line in enumerate(label):
            w1, h1 = self.GetTextExtent(line)
            w2, h2 = dc.GetTextExtent(line)
            if self.label_x is None:
                w = (max(w1, w2) - min(w1, w2)) / 2.0 + min(w1, w2)
                x = self.GetSize()[0] / 2.0 - w / 2.0
            else:
                x = self.label_x
            h = (max(h1, h2) - min(h1, h2)) / 2.0 + min(h1, h2)
            if self.label_y is None:
                y = self.GetSize()[1] / 2.0 - h / 2.0
            else:
                y = self.label_y + h * i
            if self.textshadow:
                dc.SetTextForeground(self.textshadowcolor)
                dc.DrawText(line, x + 1, y + 1)
            color = self.GetForegroundColour()
            if self.textalpha < 1:
                bgcolor = self.BackgroundColour
                bgblend = 1.0 - self.textalpha
                blend = self.textalpha
                color = wx.Colour(
                    int(round(bgblend * bgcolor.Red() + blend * color.Red())),
                    int(round(bgblend * bgcolor.Green() + blend * color.Green())),
                    int(round(bgblend * bgcolor.Blue() + blend * color.Blue())),
                )
            dc.SetTextForeground(color)
            dc.DrawText(line, int(x), int(y))


class BitmapBackgroundPanelTextGamut(BitmapBackgroundPanelText):
    """A panel with a background bitmap and text label to display gamut"""

    def __init__(self, *args, **kwargs):
        BitmapBackgroundPanel.__init__(self, *args, **kwargs)
        self.title = lang.getstr("gamut.coverage")
        self.caption = lang.getstr("gamut.coverage")
        self.label_x = None
        self.label_y = None
        self.textalpha = 1.0
        self.textshadow = True
        self.textshadowcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
        self.use_gcdc = False
        self._label = ""


class ConfirmDialog(BaseInteractiveDialog):
    """Confirmation dialog with OK and Cancel buttons"""

    def __init__(
        self,
        parent=None,
        id=-1,
        title=appname,
        msg="",
        ok=None,
        cancel=None,
        bitmap=None,
        pos=(-1, -1),
        size=(400, -1),
        alt=None,
        log=False,
        style=wx.DEFAULT_DIALOG_STYLE,
        nowrap=False,
        wrap=70,
        name=wx.DialogNameStr,
        bitmap_margin=None,
    ):
        if not ok:
            ok = lang.getstr("ok")
        if not cancel:
            cancel = lang.getstr("cancel")
        BaseInteractiveDialog.__init__(
            self,
            parent,
            id,
            title,
            msg,
            ok,
            bitmap,
            pos,
            size,
            show=False,
            log=log,
            style=style,
            nowrap=nowrap,
            wrap=wrap,
            name=name,
            bitmap_margin=bitmap_margin,
        )

        self.Bind(wx.EVT_CLOSE, self.OnClose, self)

        margin = 12

        if alt:
            self.alt = wx.Button(self.buttonpanel, -1, alt)
            self.sizer2.Insert(1, (margin, margin))
            self.sizer2.Insert(1, self.alt)
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.alt.GetId())

        if ok != cancel:
            self.cancel = wx.Button(self.buttonpanel, wx.ID_CANCEL, cancel)
            self.sizer2.Insert(1, (margin, margin))
            self.sizer2.Insert(1, self.cancel)
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CANCEL)

        self.buttonpanel.Layout()
        self.sizer0.SetSizeHints(self)
        self.sizer0.Layout()


class FileBrowseBitmapButtonWithChoiceHistory(filebrowse.FileBrowseButtonWithHistory):
    def __init__(self, *arguments, **namedarguments):
        self.history = namedarguments.get("history") or []
        if "history" in namedarguments:
            del namedarguments["history"]

        self.historyCallBack = None
        if callable(self.history):
            self.historyCallBack = self.history
            self.history = []
        name = namedarguments.get("name", "fileBrowseButtonWithHistory")
        if "name" in namedarguments:
            del namedarguments["name"]
        filebrowse.FileBrowseButton.__init__(self, *arguments, **namedarguments)
        self.SetName(name)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        if "__WXGTK__" in wx.PlatformInfo and wx.VERSION < (2, 9):
            self.textControl.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
            self.browseButton.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def OnSetFocus(self, event):
        if event.EventObject is self:
            floatspin.focus_next_keyboard_focusable_control(self)
        event.Skip()

    def OnKeyDown(self, event):
        if event.KeyCode == wx.WXK_TAB:
            floatspin.focus_next_keyboard_focusable_control(event.EventObject)
        else:
            event.Skip()

    def Disable(self):
        self.Enable(False)

    def Enable(self, enable=True):
        self.textControl.Enable(enable and self.history != [""])
        self.browseButton.Enable(enable)

    def GetName(self, path):
        """Return a name for a path. Return value may be a translated string."""
        name = None
        if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
            try:
                profile = ICCP.ICCProfile(path)
            except (IOError, ICCP.ICCProfileInvalidError):
                pass
            else:
                name = profile.getDescription()
        if not name:
            name = os.path.basename(path)
        return lang.getstr(name)

    def GetValue(self):
        """retrieve current value of text control"""
        if self.textControl.GetSelection() > -1:
            return self.history[self.textControl.GetSelection()]
        return ""

    GetPath = GetValue

    def OnChanged(self, evt):
        self.textControl.SetToolTipString(self.history[self.textControl.GetSelection()])
        if self.callCallback and self.changeCallback:
            self.changeCallback(evt)

    def SetBackgroundColour(self, color):
        wx.Panel.SetBackgroundColour(self, color)

    def SetHistory(self, value=(), selectionIndex=None, control=None):
        """Set the current history list"""
        if control is None:
            control = self.textControl
        if self.history == value:
            return
        value = list(value)

        if os.getenv("XDG_SESSION_TYPE") == "wayland":
            # When the number of items in a dropdown popup menu exceeds
            # the available display client area height, the popup menu
            # gets shown at weird positions or not at all under Wayland.
            # Work-around this wx bug by truncating the choices. Yuck.

            # Text height multiplier of 1.6 matches default popup menu item
            # height under GNOME
            line_height = math.ceil(control.GetTextExtent("69Gg")[1] * 1.6)

            # Find smallest display client area height
            max_height = sys.maxsize
            for i in range(wx.Display.GetCount()):
                max_height = min(wx.Display(i).ClientArea[3], max_height)

            # Check if combined height of items exceeds available client area.
            # Account for possible current value which is not in list and
            # for GNOME top bar (assume item height for the latter).
            if line_height * len(value) + 2 > max_height:
                max_entries = int(max_height / line_height) - 2
                print(
                    "Discarding entries to work around wxGTK Wayland "
                    "dropdown popup menu bug:",
                    ", ".join(value[max_entries:]),
                )
                value = value[:max_entries]

        index = control.GetSelection()
        if self.history and index > -1:
            tempValue = self.history[index]
        else:
            tempValue = ""
        self.history = []
        control.Clear()
        for path in value + [tempValue]:
            if path:
                self.history.append(path)
                control.Append(self.GetName(path))
        self.setupControl(selectionIndex, control)

    def SetMaxFontSize(self, pointsize=11):
        self.textControl.SetMaxFontSize(pointsize)

    def SetValue(self, value, callBack=1, clear_on_empty_value=False):
        if not value:
            if clear_on_empty_value and self.history:
                index = self.textControl.GetSelection()
                if index > -1:
                    self.history.pop(index)
                    self.textControl.Delete(index)
        if value not in self.history:
            self.history.append(value)
            self.textControl.Append(self.GetName(value))
        self.setupControl(self.history.index(value))
        if callBack:
            self.changeCallback(CustomEvent(wx.EVT_CHOICE.typeId, self.textControl))

    def SetPath(self, path):
        self.SetValue(path, 0, clear_on_empty_value=True)

    def createBrowseButton(self):
        """Create the browse-button control"""
        button = GenBitmapButton(
            self, -1, geticon(16, "document-open"), style=wx.NO_BORDER
        )
        if sys.platform == "win32":
            button.BackgroundColour = self.BackgroundColour
        button.SetToolTipString(self.toolTip)
        button.Bind(wx.EVT_BUTTON, self.OnBrowse)
        return button

    def createDialog(self, parent, id, pos, size, style, name=None):
        """Setup the graphic representation of the dialog"""
        wx.Panel.__init__(self, parent, id, pos, size, style)
        self.SetMinSize(size)  # play nice with sizers
        if sys.platform == "win32":
            self.BackgroundColour = parent.BackgroundColour

        box = wx.BoxSizer(wx.HORIZONTAL)

        self.textControl = self.createTextControl()
        if sys.platform == "darwin" and wx.VERSION > (2, 9):
            # Prevent 1px cut-off at left-hand side
            box.Add((1, 1))
        box.Add(self.textControl, 1, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM, 4)

        self.browseButton = self.createBrowseButton()
        box.Add(self.browseButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        if self.history:
            history = self.history
            self.history = []
            self.SetHistory(history)

        self.SetAutoLayout(True)
        self.SetSizer(box)
        self.Layout()

    def createLabel(self):
        return (0, 0)

    def createTextControl(self):
        """Create the text control"""
        textControl = wx.Choice(self, -1)
        textControl.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        if self.changeCallback:
            textControl.Bind(wx.EVT_CHOICE, self.OnChanged)
        return textControl

    def setupControl(self, selectionIndex=None, control=None):
        if control is None:
            control = self.textControl
        if selectionIndex is None:
            selectionIndex = len(self.history) - 1
        control.SetSelection(selectionIndex)
        toolTip = self.history[selectionIndex] if selectionIndex > -1 else self.toolTip
        control.SetToolTipString(toolTip)
        control.Enable(self.browseButton.Enabled and self.history != [""])


class PathDialog(ConfirmDialog):
    def __init__(self, parent, msg="", name="pathdialog"):
        ConfirmDialog.__init__(
            self,
            parent,
            msg=msg,
            ok=lang.getstr("browse"),
            cancel=lang.getstr("cancel"),
            name=name,
        )
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.ok.Bind(wx.EVT_BUTTON, self.filedialog_handler)

    def OnDestroy(self, event):
        self.filedialog.Destroy()
        event.Skip()

    def __getattr__(self, name):
        return getattr(self.filedialog, name)

    def filedialog_handler(self, event):
        self.EndModal(self.filedialog.ShowModal())


_DirDialog = wx.DirDialog


class DirDialog(PathDialog):
    """wx.DirDialog cannot be interacted with programmatically after
    ShowModal(), a functionality we need for scripting."""

    def __init__(self, *args, **kwargs):
        PathDialog.__init__(self, *args[0:2], name="dirdialog")
        self.filedialog = _DirDialog(self, *args[1:], **kwargs)


_FileDialog = wx.FileDialog


class FileDialog(PathDialog):
    """wx.FileDialog cannot be interacted with programmatically after
    ShowModal(), a functionality we need for scripting."""

    def __init__(self, *args, **kwargs):
        PathDialog.__init__(self, *args[0:2], name="filedialog")
        self.filedialog = _FileDialog(self, *args[1:], **kwargs)


class FileDrop(_FileDrop):
    def __init__(self, parent, drophandlers=None):
        self.parent = parent
        _FileDrop.__init__(self, drophandlers)
        self.unsupported_handler = self.drop_unsupported_handler

    def drop_unsupported_handler(self):
        """Drag'n'drop handler for unsupported files.

        Shows an error message.

        """
        if not hasattr(self.parent, "worker") or not self.parent.worker.is_working():
            InfoDialog(
                self.parent,
                msg=lang.getstr("error.file_type_unsupported")
                + "\n\n"
                + "\n".join(self._filenames),
                ok=lang.getstr("ok"),
                bitmap=geticon(32, "dialog-error"),
            )


class FlatShadedButton(GradientButton):

    __bitmap = None
    _enabled = True

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        bitmap=None,
        label="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.NO_BORDER,
        validator=wx.DefaultValidator,
        name="gradientbutton",
        bgcolour=None,
        fgcolour=None,
    ):
        self.dpiscale = getcfg("app.dpi") / get_default_dpi()
        GradientButton.__init__(
            self,
            parent=parent,
            id=id,
            bitmap=bitmap,
            label=label,
            pos=pos,
            size=size,
            style=style,
            validator=validator,
            name=name,
        )
        self._bgcolour = bgcolour  # Original bgcolour
        self._fgcolour = fgcolour  # Original fgcolour
        self._setcolours(bgcolour, fgcolour)
        self._set_bitmap_labels(self.__bitmap)
        self.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
        self._update_best_size()

    def _set_bitmap_labels(self, bitmap):
        if bitmap:
            self._bitmapdisabled = get_bitmap_disabled(bitmap)
            img = bitmap.ConvertToImage()
            img = img.AdjustChannels(1.1, 1.1, 1.1)
            bitmap = img.ConvertToBitmap()
        else:
            self._bitmapdisabled = bitmap
        self._bitmaphover = bitmap
        self._bitmapselected = bitmap
        self._bitmapfocus = bitmap

    def _setcolours(self, bgcolour=None, fgcolour=None):
        self.BackgroundColour = bgcolour or wx.Colour(0x22, 0x22, 0x22)
        self.ForegroundColour = fgcolour or wx.Colour(0x99, 0x99, 0x99)

    def Disable(self):
        self.Enable(False)

    def DoGetBestSize(self):
        """Overridden base class virtual. Determines the best size of the
        button based on the label and bezel size.
        """

        if not getattr(self, "_lastBestSize", None):
            dummy = "FfGgJjPpYy"
            label = self.GetLabel() or dummy

            dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
            try:
                dc = wx.GCDC(dc)
            except Exception:
                pass
            dc.SetFont(self.GetFont())
            retWidth, retHeight = dc.GetTextExtent(label)
            if label == dummy:
                retWidth = 0
            elif wx.VERSION < (2, 9):
                retWidth += 5

            bmpWidth = bmpHeight = 0
            if self._bitmap:
                if label != dummy:
                    constant = 10
                    if wx.VERSION < (2, 9):
                        retWidth += 5
                else:
                    constant = 0
                # Pin the bitmap height to 10
                bmpWidth, bmpHeight = (
                    self._bitmap.GetWidth() + constant * self.dpiscale,
                    10 * self.dpiscale,
                )
                retWidth += bmpWidth
                retHeight = max(bmpHeight, retHeight)

            self._lastBestSize = wx.Size(
                int(retWidth + 25 * self.dpiscale), int(retHeight + 15 * self.dpiscale)
            )
        return self._lastBestSize

    def OnGainFocus(self, event):
        """Handles the ``wx.EVT_SET_FOCUS`` event for L{GradientButton}.

        :param event: a `wx.FocusEvent` event to be processed.
        """

        self._hasFocus = True
        self._mouseAction = HOVER
        self.Refresh()
        self.Update()

    def OnLoseFocus(self, event):
        """Handles the ``wx.EVT_LEAVE_WINDOW`` event for L{GradientButton}.

        :param event: a `wx.MouseEvent` event to be processed.
        """

        self._hasFocus = False
        pos = wx.GetMousePosition()
        if self.IsShownOnScreen() and not self.ClientRect.Contains(
            self.ScreenToClient(pos)
        ):
            # Note: ScreenToClient will only work if top level parent is shown
            self._mouseAction = None
        self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` event for L{GradientButton}.

        :param event: a `wx.PaintEvent` event to be processed.
        """

        if sys.platform != "win32":
            # AutoBufferedPaintDCFactory is the magic needed for crisp text
            # rendering in HiDPI mode under OS X and Linux
            cls = wx.AutoBufferedPaintDCFactory
        else:
            cls = wx.BufferedPaintDC
        dc = cls(self)
        gc = wx.GraphicsContext.Create(dc)
        dc.SetBackground(wx.Brush(self.Parent.BackgroundColour))
        dc.Clear()

        clientRect = self.GetClientRect()
        capture = wx.Window.GetCapture()

        x, y, width, height = clientRect

        fgcolour = self.ForegroundColour

        if capture != self:

            if self._mouseAction == HOVER or self._hasFocus:
                fill = self.LightColour(self.BackgroundColour, 3)
                fgcolour = self.LightColour(fgcolour, 15)
            else:
                fill = self.BackgroundColour

            shadowOffset = 0
        else:
            fill = self.LightColour(self.BackgroundColour, 3)

            shadowOffset = 1

        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(fill))
        gc.DrawRoundedRectangle(x, y, width, height, 8 * self.dpiscale)

        if self._enabled:
            if capture != self:
                if self._mouseAction == HOVER:
                    bitmap = self._bitmaphover
                else:
                    bitmap = self._bitmap
            else:
                bitmap = self._bitmapselected
        else:
            bitmap = self._bitmapdisabled

        font = gc.CreateFont(self.GetFont(), fgcolour)
        gc.SetFont(font)
        label = self.GetLabel()
        if label and bitmap:
            label = " " + label
        # Note: Using self.GetTextExtent instead of gc.GetTextExtent seems
        # to fix sporadic segfaults with wxPython Phoenix up to 4.0.0a2
        # under Windows (fixed in 4.0.0a3), but self.GetTextExtent is NOT
        # an equivalent replacement for gc.GetTextExtent.
        tw, th = gc.GetTextExtent(label)

        if bitmap:
            bw, bh = bitmap.GetWidth(), bitmap.GetHeight()
            if tw:
                tw += 5
                if wx.VERSION < (2, 9):
                    tw += 5
        else:
            bw = bh = 0

        pos_x = (
            width - bw - tw
        ) / 2 + shadowOffset  # adjust for bitmap and text to centre
        if bitmap:
            pos_y = (height - bh) / 2 + shadowOffset
            gc.DrawBitmap(bitmap, pos_x, pos_y, bw, bh)  # draw bitmap if available
            pos_x = pos_x + 5  # extra spacing from bitmap

        gc.DrawText(
            label, pos_x + bw + shadowOffset, (height - th) / 2 - 0.5 + shadowOffset
        )

    @property
    def BitmapLabel(self):
        return self._bitmap

    @BitmapLabel.setter
    def BitmapLabel(self, bitmap):
        self.SetBitmap(bitmap)

    def Enable(self, enable=True):
        if enable:
            # Restore original colors
            self._setcolours(self._bgcolour, self._fgcolour)
        else:
            # Dim
            self._setcolours(wx.Colour(0x40, 0x40, 0x40), wx.Colour(0x66, 0x66, 0x66))
        GradientButton.Enable(self, enable)
        self._enabled = enable

    @property
    def _bitmap(self):
        return self.__bitmap

    @_bitmap.setter
    def _bitmap(self, bitmap):
        if bitmap is not self.__bitmap:
            self.__bitmap = bitmap
            self._set_bitmap_labels(bitmap)

    def SetBitmap(self, bitmap):
        self._bitmap = bitmap
        self._update_best_size()
        self.Refresh()

    def SetBitmapDisabled(self, bitmap):
        self._bitmapdisabled = bitmap
        self._update_best_size()
        self.Refresh()

    def SetBitmapFocus(self, bitmap):
        self._bitmapfocus = bitmap
        self._update_best_size()
        self.Refresh()

    def SetBitmapHover(self, bitmap):
        self._bitmaphover = bitmap
        self._update_best_size()
        self.Refresh()

    def SetBitmapSelected(self, bitmap):
        self._bitmapselected = bitmap
        self._update_best_size()
        self.Refresh()

    def SetLabel(self, label):
        wx.PyControl.SetLabel(self, label)
        self._update_best_size()

    def _update_best_size(self):
        if hasattr(self, "_lastBestSize"):
            del self._lastBestSize
            self.MinSize = self.DoGetBestSize()

    Label = property(wx.PyControl.GetLabel, SetLabel)


class BorderGradientButton(GradientButton):
    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        bitmap=None,
        label="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.NO_BORDER,
        validator=wx.DefaultValidator,
        name="gradientbutton",
    ):
        self.dpiscale = getcfg("app.dpi") / get_default_dpi()
        self.use_sierra_style = sys.platform == "darwin"
        self._enabled = True
        GradientButton.__init__(
            self,
            parent=parent,
            id=id,
            bitmap=bitmap,
            label=label,
            pos=pos,
            size=size,
            style=style,
            validator=validator,
            name=name
        )
        self.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
        self._bitmapdisabled = self._bitmap
        self._bitmapfocus = self._bitmap
        self._bitmaphover = self._bitmap
        self._bitmapselected = self._bitmap
        set_bitmap_labels(self, focus=False)
        if self.use_sierra_style:
            # Use Sierra-like color scheme
            sel = self._bitmap.ConvertToImage()
            sel.Invert()
            self.SetBitmapFocus(sel.ConvertToBitmap())
            sel = sel.AdjustChannels(1, 1, 1, 0.8)
            sel = sel.ConvertToBitmap()
            self.SetBitmapSelected(sel)

    BitmapLabel = property(
        lambda self: self._bitmap, lambda self, bitmap: self.SetBitmap(bitmap)
    )

    def DarkColour(self, colour, percent):
        """Return dark contrast of `colour`. The colour returned is from the scale of
        `colour` ==> white.

        :param colour: the input colour to be brightened;
        :param percent: determines how dark the colour will be. `percent` = 100
         returns black, `percent` = 0 returns `colour`.
        """

        rd = colour.Red()
        gd = colour.Green()
        bd = colour.Blue()
        high = 100

        # We take the percent way of the colour from colour -. black
        i = percent
        r = ((i * rd * 100) / high) / 100
        g = ((i * gd * 100) / high) / 100
        b = ((i * bd * 100) / high) / 100

        return wx.Colour(int(r), int(g), int(b))

    def Disable(self):
        self.Enable(False)

    def DoGetBestSize(self):
        """Overridden base class virtual. Determines the best size of the
        button based on the label and bezel size.
        """

        label = self.GetLabel()
        if not label:
            return wx.Size(112, 48)

        dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
        try:
            dc = wx.GCDC(dc)
        except Exception:
            pass
        dc.SetFont(self.GetFont())
        retWidth, retHeight = dc.GetTextExtent(label)

        bmpWidth = bmpHeight = 0
        constant = 15 * self.dpiscale
        if self._bitmap:
            bmpWidth, bmpHeight = (
                self._bitmap.GetWidth() + 20 * self.dpiscale,
                self._bitmap.GetHeight(),
            )
            retWidth += bmpWidth
            retHeight = max(bmpHeight, retHeight)

        return wx.Size(int(retWidth + constant), int(retHeight + constant))

    def Enable(self, enable=True):
        self._enabled = enable
        GradientButton.Enable(self, enable)
        self.Update()

    def IsEnabled(self):
        return self._enabled

    Enabled = property(IsEnabled, Enable)

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` event for L{GradientButton}.

        :param event: a `wx.PaintEvent` event to be processed.
        """

        if sys.platform != "win32":
            # AutoBufferedPaintDCFactory is the magic needed for crisp text
            # rendering in HiDPI mode under OS X and Linux
            cls = wx.AutoBufferedPaintDCFactory
        else:
            cls = wx.BufferedPaintDC
        dc = cls(self)
        gc = wx.GraphicsContext.Create(dc)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()

        clientRect = self.GetClientRect()
        gradientRect = wx.Rect(*clientRect)
        capture = wx.Window.GetCapture()

        x, y, width, height = clientRect

        gradientRect.SetHeight(
            int(gradientRect.GetHeight() / 2 + ((capture == self and [1] or [0])[0]))
        )

        fgcolor = self.ForegroundColour

        # Determine fill color based on state and platform
        if self.use_sierra_style:
            # Use Sierra-like color scheme
            if capture == self and self._mouseAction in (CLICK, HOVER):
                # Pressed/selected state
                topStart = wx.Colour(*gamma_encode(74, 150, 253))
                topEnd = wx.Colour(*gamma_encode(8, 103, 221))
                fgcolor = wx.Colour(255, 255, 255, 204)
            elif capture != self and self._hasFocus:
                # Focus state
                topStart = wx.Colour(*gamma_encode(105, 177, 250))
                topEnd = wx.Colour(*gamma_encode(12, 128, 255))
                # fgcolor = wx.WHITE
                fgcolor = wx.BLACK
            else:
                # Normal state
                topStart = wx.WHITE
                topEnd = wx.WHITE
                fgcolor = wx.BLACK
        elif capture != self:
            # Normal, hover or focus state
            if self._mouseAction == HOVER:
                # Hover state
                topStart = self._pressedTopColour
                topEnd = self._pressedBottomColour
                topStart = wx.Colour(topStart.red, topStart.green, topStart.blue, 25)
                topEnd = wx.Colour(topEnd.red, topEnd.green, topEnd.blue, 25)
            else:
                # Normal or focus state
                topStart, topEnd = self._topStartColour, self._bottomEndColour
        else:
            # Pressed/selected state
            topStart = self._pressedTopColour
            topEnd = self._pressedBottomColour
            topStart = wx.Colour(topStart.red, topStart.green, topStart.blue, 51)
            topEnd = wx.Colour(topEnd.red, topEnd.green, topEnd.blue, 51)

        # Determine border color and width based on state and platform
        borderwidth = 1
        if self.use_sierra_style:
            # Use Sierra-like color scheme
            if capture == self and self._mouseAction in (CLICK, HOVER):
                # Pressed/selected state
                bordercolor_top = wx.Colour(*gamma_encode(35, 125, 254))
                bordercolor = wx.Colour(*gamma_encode(2, 63, 221))
            elif capture != self and self._hasFocus:
                # Focus state
                bordercolor_top = wx.Colour(*gamma_encode(74, 160, 249))
                bordercolor = wx.Colour(*gamma_encode(4, 95, 255))
            else:
                # Normal state
                # bordercolor_top = wx.Colour(*gamma_encode(200, 200, 200))
                # bordercolor = wx.Colour(*gamma_encode(172, 172, 172))
                if sys.platform == "darwin":
                    bordercolor_top = wx.Colour(*gamma_encode(0, 0, 0, 55))
                else:
                    bordercolor_top = wx.Colour(*gamma_encode(0, 0, 0, 11))
                bordercolor = wx.Colour(*gamma_encode(0, 0, 0, 83))
        else:
            # Normal, hover, focus or pressed/selected state
            if self._mouseAction == HOVER or self._hasFocus:
                # Hover, focus or pressed/selected state
                bordercolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
                if (
                    sys.platform == "win32"
                    and capture != self
                    and self._mouseAction != HOVER
                ):
                    # Focus state
                    borderwidth = 2
            else:
                # Normal state
                bordercolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
            if capture == self:
                # Pressed/selected state
                bordercolor = self.DarkColour(bordercolor, 71)

        if not self.IsEnabled():
            fgcolor = wx.Colour(fgcolor.red, fgcolor.green, fgcolor.blue, 102)
            bordercolor.Set(
                bordercolor.red,
                bordercolor.green,
                bordercolor.blue,
                int(round(bordercolor.alpha * 153 / 255.0)),
            )

        brush = gc.CreateLinearGradientBrush(0, 1, 0, height - 1, topStart, topEnd)
        gc.SetBrush(brush)

        if self.use_sierra_style:
            # Use Sierra-like color scheme
            # shadowcolor = wx.Colour(*gamma_encode(228, 228, 228))
            if sys.platform == "darwin":
                shadowcolor = wx.Colour(*gamma_encode(0, 0, 0, 8))
            else:
                shadowcolor = wx.Colour(*gamma_encode(0, 0, 0, 19))

            # Draw Sierra-like shadow
            gc.SetPen(wx.Pen(shadowcolor))
            gc.DrawRoundedRectangle(
                borderwidth,
                borderwidth,
                width - 2 - borderwidth,
                height - 1 - borderwidth,
                (height - 1 - borderwidth) / 2.0,
            )

            # Draw borders
            gc.SetPen(wx.Pen(bordercolor))
            gc.DrawRoundedRectangle(
                borderwidth,
                borderwidth,
                width - 2 - borderwidth,
                height - 2 - borderwidth,
                (height - 2 - borderwidth) / 2.0,
            )
            gc.SetPen(wx.Pen(bordercolor_top))
            gc.DrawRoundedRectangle(
                borderwidth,
                borderwidth,
                width - 2 - borderwidth,
                height - 2 - borderwidth * 2,
                (height - 2 - borderwidth * 2) / 2.0,
            )

            # Draw fill
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRoundedRectangle(
                borderwidth * 2,
                borderwidth * 2,
                width - 2 - borderwidth * 2,
                height - 2 - borderwidth * 2,
                (height - 2 - borderwidth * 2) / 2.0,
            )
        else:
            # Draw border and fill
            gc.SetPen(wx.Pen(bordercolor, borderwidth))
            gc.DrawRoundedRectangle(
                borderwidth,
                borderwidth,
                width - 2 - borderwidth,
                height - 2 - borderwidth,
                (height - 2 - borderwidth) / 2.0,
            )

        shadowOffset = 0

        font = gc.CreateFont(self.GetFont(), fgcolor)
        gc.SetFont(font)
        label = self.GetLabel()
        if label and self._bitmap:
            label = " " + label
        # Note: Using self.GetTextExtent instead of gc.GetTextExtent seems
        # to fix sporadic segfaults with wxPython Phoenix up to 4.0.0a2
        # under Windows (fixed in 4.0.0a3), but self.GetTextExtent is NOT
        # an equivalent replacement for gc.GetTextExtent.
        tw, th = gc.GetTextExtent(label)

        if self._bitmap:
            bw, bh = self._bitmap.GetWidth(), self._bitmap.GetHeight()
            if tw:
                tw += 5
                if wx.VERSION < (2, 9):
                    tw += 5
        else:
            bw = bh = 0

        # adjust for bitmap and text to centre
        pos_x = (width - bw - tw) / 2 + shadowOffset
        if self.IsEnabled():
            if capture == self and self._mouseAction in (CLICK, HOVER):
                bitmap = self._bitmapselected
            elif capture != self and self._hasFocus:
                bitmap = self._bitmapfocus
            elif self._mouseAction == HOVER and not get_dialogs(True):
                bitmap = self._bitmapfocus  # self._bitmaphover
            else:
                bitmap = self._bitmapfocus  # self._bitmap
        else:
            bitmap = self._bitmapfocus  # self._bitmapdisabled
        if bitmap:
            pos_y = (height - bh) / 2 + shadowOffset
            gc.DrawBitmap(bitmap, pos_x, pos_y, bw, bh)  # draw bitmap if available
            pos_x = pos_x + 4  # extra spacing from bitmap

        gc.DrawText(
            label, pos_x + bw + shadowOffset, (height - th) / 2.0 - 1 + shadowOffset
        )

    def SetBitmap(self, bitmap):
        self._bitmap = bitmap

    def SetBitmapDisabled(self, bitmap):
        self._bitmapdisabled = bitmap

    def SetBitmapFocus(self, bitmap):
        self._bitmapfocus = bitmap

    def SetBitmapHover(self, bitmap):
        self._bitmaphover = bitmap

    def SetBitmapSelected(self, bitmap):
        self._bitmapselected = bitmap

    def Update(self):
        pass


class CustomGrid(wx.grid.Grid):
    def __init__(self, *args, **kwargs):
        wx.grid.Grid.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.Bind(wx.EVT_SIZE, self.OnResize)
        self.Bind(wx.grid.EVT_GRID_ROW_SIZE, self.OnResize)
        self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnResize)
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnCellLeftClick)
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.OnCellLeftClick)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnCellSelect)
        self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnLabelLeftClick)
        self.GetGridCornerLabelWindow().Bind(wx.EVT_PAINT, self.OnPaintCornerLabel)
        self.GetGridColLabelWindow().Bind(wx.EVT_PAINT, self.OnPaintColLabels)
        self.GetGridRowLabelWindow().Bind(wx.EVT_PAINT, self.OnPaintRowLabels)
        self.SetDefaultCellAlignment(wx.ALIGN_LEFT, wx.ALIGN_CENTER)
        self.SetDefaultCellBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        )
        self.SetDefaultEditor(CustomCellEditor(self))
        self._default_cell_renderer = CustomCellRenderer()
        self.SetDefaultRenderer(self._default_cell_renderer)
        self.SetRowLabelAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)

        self.headerbitmap = None
        if sys.platform == "darwin" or "gtk3" in wx.PlatformInfo:
            # wxMac draws a too short native header
            self.rendernative = False
            self.style = "Mavericks"
        else:
            self.rendernative = True
            self.style = ""
        self._default_col_label_renderer = CustomColLabelRenderer()
        self._default_row_label_renderer = CustomRowLabelRenderer()
        self._col_label_renderers = {}
        self._overwrite_cell_values = True
        self._row_label_renderers = {}
        self.alternate_cell_background_color = True
        self.alternate_col_label_background_color = False
        self.alternate_row_label_background_color = True
        self.draw_col_labels = True
        self.draw_row_labels = True
        self.draw_horizontal_grid_lines = True
        self.draw_vertical_grid_lines = True
        self.selection_alpha = 1.0
        self.show_cursor_outline = True

    if not hasattr(wx.grid.Grid, "CalcCellsExposed"):
        # wxPython < 2.8.10
        def CalcCellsExposed(self, region):
            rows = self.CalcRowLabelsExposed(region)
            cols = self.CalcColLabelsExposed(region)
            cells = []
            for row in rows:
                for col in cols:
                    if row > -1 and col > -1:
                        cells.append((row, col))
            return cells

    if not hasattr(wx.grid.Grid, "CalcColLabelsExposed"):
        # wxPython < 2.8.10
        def CalcColLabelsExposed(self, region):
            x, y = self.CalcUnscrolledPosition((0, 0))
            ri = wx.RegionIterator(region)
            cols = []
            while ri:
                rect = ri.GetRect()
                rect.Offset((x, 0))
                colPos = self.GetColPos(self.XToCol(rect.left))
                while self.GetNumberCols() > colPos >= 0:
                    col = self.GetColAt(colPos)
                    cl, cr = self.GetColLeftRight(col)
                    if cr < rect.left:
                        continue
                    if cl > rect.right:
                        break
                    cols.append(col)
                    colPos += 1
                ri.Next()
            return cols

    if not hasattr(wx.grid.Grid, "CalcRowLabelsExposed"):
        # wxPython < 2.8.10
        def CalcRowLabelsExposed(self, region):
            x, y = self.CalcUnscrolledPosition((0, 0))
            ri = wx.RegionIterator(region)
            rows = []
            while ri:
                rect = ri.GetRect()
                rect.Offset((0, y))
                row = self.YToRow(rect.top)
                while self.GetNumberRows() > row >= 0:
                    rt, rb = self.GetRowTopBottom(row)
                    if rb < rect.top:
                        continue
                    if rt > rect.bottom:
                        break
                    rows.append(row)
                    row += 1
                ri.Next()
            return rows

    # def AppendCols(self, numCols=1):
    #     """th overridden AppendCols method
    #
    #     :param numCols:
    #     :return:
    #     """
    #     raise NotImplementedError("testing")

    def GetColLeftRight(self, col, c=0):
        left = 0
        while c < col:
            left += self.GetColSize(c)
            c += 1
        right = left + self.GetColSize(col) - 1
        return left, right

    def GetRowTopBottom(self, row, r=0):
        top = 0
        while r < row:
            top += self.GetRowSize(r)
            r += 1
        bottom = top + self.GetRowSize(row) - 1
        return top, bottom

    def OnCellLeftClick(self, event):
        if (
            event.CmdDown()
            or event.ControlDown()
            or event.ShiftDown()
            or not isinstance(
                self.GetCellEditor(self.GetGridCursorRow(), self.GetGridCursorCol()),
                CustomCellEditor,
            )
        ):
            event.Skip()
        else:
            self.SetGridCursor(event.Row, event.Col)

    def OnCellSelect(self, event):
        row, col = event.GetRow(), event.GetCol()
        self._anchor_row = row
        self._overwrite_cell_values = True
        self.SelectBlock(event.Row, event.Col, event.Row, event.Col)
        self.Refresh()
        event.Skip()

    def OnKeyDown(self, event):
        keycode = event.KeyCode
        if event.CmdDown() or event.ControlDown():
            # CTRL (Linux/Mac/Windows) / CMD (Mac)
            if keycode == 65:
                # A
                self.SelectAll()
                return
            elif keycode in (67, 88):
                # C / X
                clip = []
                cells = self.GetSelection()
                i = -1
                start_col = self.GetNumberCols()
                for cell in cells:
                    row = cell[0]
                    col = cell[1]
                    if i < row:
                        clip.append([])
                        i = row
                        offset = 0
                    # Skip cols without label
                    if self.GetColLabelSize() and not self.GetColLabelValue(col):
                        offset += 1
                        continue
                    if col - offset < start_col:
                        start_col = col - offset
                    while len(clip[-1]) - 1 < col - offset:
                        clip[-1].append("")
                    clip[-1][col - offset] = self.GetCellValue(row, col)
                for i, row in enumerate(clip):
                    clip[i] = "\t".join(row[start_col:])
                clipdata = wx.TextDataObject()
                clipdata.SetText("\n".join(clip))
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(clipdata)
                wx.TheClipboard.Close()
                return
            elif keycode == 86 and self.IsEditable():
                # V
                do = wx.TextDataObject()
                wx.TheClipboard.Open()
                success = wx.TheClipboard.GetData(do)
                wx.TheClipboard.Close()
                if success:
                    lines = do.GetText().splitlines()
                    for i, line in enumerate(lines):
                        lines[i] = re.sub(r" +", "\t", line).split("\t")
                    # Translate from selected cells into a grid with None values
                    # for not selected cells
                    grid = []
                    cells = self.GetSelection()
                    i = -1
                    start_col = self.GetNumberCols()
                    for cell in cells:
                        row = cell[0]
                        col = cell[1]
                        if i < row:
                            grid.append([])
                            i = row
                            offset = 0
                        # Skip read-only cells and cols without label
                        if self.IsReadOnly(row, col) or (
                            self.GetColLabelSize() and not self.GetColLabelValue(col)
                        ):
                            offset += 1
                            continue
                        if col - offset < start_col:
                            start_col = col - offset
                        while len(grid[-1]) - 1 < col - offset:
                            grid[-1].append(None)
                        grid[-1][col - offset] = cell
                    for i, row in enumerate(grid):
                        grid[i] = row[start_col:]
                    # 'Paste' values from clipboard
                    self.BeginBatch()
                    for i, row in enumerate(grid):
                        for j, cell in enumerate(row):
                            if (
                                cell is not None
                                and len(lines) > i
                                and len(lines[i]) > j
                            ):
                                self.SetCellValue(cell[0], cell[1], lines[i][j])
                                self.ProcessEvent(
                                    wx.grid.GridEvent(
                                        -1,
                                        wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
                                        self,
                                        cell[0],
                                        cell[1],
                                    )
                                )
                    self.EndBatch()
                return
        elif self.IsEditable() and not self.IsCurrentCellReadOnly():
            if isinstance(
                self.GetCellEditor(self.GetGridCursorRow(), self.GetGridCursorCol()),
                CustomCellEditor,
            ):
                ch = None
                if keycode in [
                    wx.WXK_NUMPAD0,
                    wx.WXK_NUMPAD1,
                    wx.WXK_NUMPAD2,
                    wx.WXK_NUMPAD3,
                    wx.WXK_NUMPAD4,
                    wx.WXK_NUMPAD5,
                    wx.WXK_NUMPAD6,
                    wx.WXK_NUMPAD7,
                    wx.WXK_NUMPAD8,
                    wx.WXK_NUMPAD9,
                ]:
                    ch = chr(ord("0") + keycode - wx.WXK_NUMPAD0)
                elif keycode in (wx.WXK_NUMPAD_DECIMAL, wx.WXK_NUMPAD_SEPARATOR):
                    ch = "."
                elif 256 > keycode >= 32:
                    ch = str(chr(keycode))
                if ch is not None or keycode in (wx.WXK_BACK, wx.WXK_DELETE):
                    changed = 0
                    batch = False
                    for i, (row, col) in enumerate(self.GetSelection()):
                        if row > -1 and col > -1 and not self.IsReadOnly(row, col):
                            if changed and not batch:
                                self.BeginBatch()
                                batch = True
                            if self._overwrite_cell_values or keycode == wx.WXK_DELETE:
                                value = ""
                            else:
                                value = self.GetCellValue(row, col)
                            if keycode == wx.WXK_BACK:
                                value = value[:-1]
                            elif keycode != wx.WXK_DELETE:
                                value += ch
                            self.SetCellValue(row, col, value)
                            self.ProcessEvent(
                                wx.grid.GridEvent(
                                    -1,
                                    wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
                                    self,
                                    row,
                                    col,
                                )
                            )
                            changed += 1
                    if batch:
                        self.EndBatch()
                    self._overwrite_cell_values = False
                    if not changed:
                        wx.Bell()
                    return
            elif event.KeyCode == wx.WXK_RETURN or event.KeyCode == wx.WXK_NUMPAD_ENTER:
                self.EnableCellEditControl()
                return
        event.Skip()

    def OnKillFocus(self, event):
        self.Refresh()
        event.Skip()

    def OnLabelLeftClick(self, event):
        row, col = event.GetRow(), event.GetCol()
        if row == -1 and col > -1:
            # Col label clicked
            self.SetFocus()
            self.SetGridCursor(max(self.GetGridCursorRow(), 0), col)
            self.MakeCellVisible(max(self.GetGridCursorRow(), 0), col)
        elif col == -1 and row > -1:
            # Row label clicked
            if self.select_row(
                row, event.ShiftDown(), event.ControlDown() or event.CmdDown()
            ):
                return
        event.Skip()

    def OnPaintColLabels(self, evt):
        window = evt.GetEventObject()
        dc = wx.PaintDC(window)

        try:
            cols = self.CalcColLabelsExposed(window.GetUpdateRegion())
        except wxAssertionError:
            return

        if -1 in cols:
            return

        x, y = self.CalcUnscrolledPosition((0, 0))
        pt = dc.GetDeviceOrigin()
        dc.SetDeviceOrigin(pt.x - x, pt.y)
        leftoffset = 0
        for i, col in enumerate(cols):
            left, right = self.GetColLeftRight(col, cols[0] if i > 0 else 0)
            if i > 0:
                left += leftoffset
                right += leftoffset
            else:
                leftoffset = left
            rect = wx.Rect()
            rect.left = left
            rect.right = right
            rect.y = 0
            rect.height = self.GetColLabelSize()

            renderer = self._col_label_renderers.get(
                col, self._default_col_label_renderer
            )

            renderer.Draw(self, dc, rect, col)

    def OnPaintCornerLabel(self, evt):
        window = evt.GetEventObject()
        dc = wx.PaintDC(window)

        rect = wx.Rect()
        rect.width = self.GetRowLabelSize()
        rect.height = self.GetColLabelSize()
        rect.x = 0
        rect.y = 0
        self._default_col_label_renderer.Draw(self, dc, rect)

    def OnPaintRowLabels(self, evt):
        window = evt.GetEventObject()
        dc = wx.PaintDC(window)

        rows = self.CalcRowLabelsExposed(window.GetUpdateRegion())
        if -1 in rows:
            return

        x, y = self.CalcUnscrolledPosition((0, 0))
        pt = dc.GetDeviceOrigin()
        dc.SetDeviceOrigin(pt.x, pt.y - y)
        topoffset = 0
        for i, row in enumerate(rows):
            top, bottom = self.GetRowTopBottom(row, rows[0] if i > 0 else 0)
            if i > 0:
                top += topoffset
                bottom += topoffset
            else:
                topoffset = top
            rect = wx.Rect()
            rect.top = top
            rect.bottom = bottom
            rect.x = 0
            rect.width = self.GetRowLabelSize()

            renderer = self._row_label_renderers.get(
                row, self._default_row_label_renderer
            )

            renderer.Draw(self, dc, rect, row)

    def OnResize(self, event):
        region = wx.Region(*self.ClientRect.Get())
        for row, col in self.CalcCellsExposed(region):
            cell_renderer = self.GetCellRenderer(row, col)
            if (
                isinstance(cell_renderer, CustomCellRenderer)
                and cell_renderer._selectionbitmaps
            ):
                # On resize, we need to tell any CustomCellRenderer that its
                # bitmaps are no longer valid and are garbage collected
                cell_renderer._selectionbitmaps = {}
        event.Skip()

    def SetColLabelRenderer(self, col, renderer):
        """Register a renderer to be used for drawing the label for the
        given column.
        """
        if renderer is None:
            if col in self._col_label_renderers:
                del self._col_label_renderers[col]
        else:
            self._col_label_renderers[col] = renderer

    def SetDefaultCellBackgroundColour(self, color):
        # Set alpha to 0 so we can detect the default color
        if not isinstance(color, wx.Colour):
            color = wx.Colour(color)
        color.Set(color.Red(), color.Green(), color.Blue(), 0)
        wx.grid.Grid.SetDefaultCellBackgroundColour(self, color)

    def SetRowLabelRenderer(self, row, renderer):
        """Register a renderer to be used for drawing the label for the
        given row.
        """
        if renderer is None:
            if row in self._row_label_renderers:
                del self._row_label_renderers[row]
        else:
            self._row_label_renderers[row] = renderer

    def select_row(self, row, shift=False, ctrl=False):
        self.SetFocus()
        if not shift and not ctrl:
            self.SetGridCursor(row, max(self.GetGridCursorCol(), 0))
            self.SelectRow(row)
            self._anchor_row = row
        self.MakeCellVisible(row, max(self.GetGridCursorCol(), 0))
        if self.IsSelection():
            if shift:
                self.BeginBatch()
                rows = self.GetSelectionRows()
                sel = list(
                    range(min(self._anchor_row, row), max(self._anchor_row, row) + 1)
                )
                desel = []
                add = []
                for i in rows:
                    if i not in sel:
                        desel.append(i)
                for i in sel:
                    if i not in rows:
                        add.append(i)
                if len(desel) >= len(add):
                    # in this case deselecting rows will take as long or longer than selecting, so use SelectRow to speed up the operation
                    self.SelectRow(row)
                else:
                    for i in desel:
                        self.DeselectRow(i)
                for i in add:
                    self.SelectRow(i, True)
                self.EndBatch()
                return False
            elif ctrl:
                if self.IsInSelection(row, 0):
                    self.DeselectRow(row)
                    return True
                else:
                    self.SelectRow(row, True)
        return False


class CustomCheckBox(wx.Panel):
    """A custom checkbox where the label is independent from the checkbox itself.

    Works around wxMac not taking into account text (foreground) color on
    a default checkbox label.

    """

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        label="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.NO_BORDER,
        validator=wx.DefaultValidator,
        name="CustomCheckBox",
    ):
        wx.Panel.__init__(self, parent, id, pos, size, style, name)
        self.BackgroundColour = parent.BackgroundColour
        self.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
        self._cb = wx.CheckBox(self, -1)
        self._enabled = True
        self.Sizer.Add(self._cb, flag=wx.ALIGN_CENTER_VERTICAL)
        if sys.platform == "darwin":
            self._label = wx.StaticText(self, -1, "")
            self.Sizer.Add(self._label, 1, wx.ALIGN_CENTER_VERTICAL)
            self._label.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
            self._label.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
            self._up = True
        else:
            self._label = self._cb
        self._label.Label = label

    def Bind(self, event_id, handler):
        self._cb.Bind(event_id, handler)

    def Disable(self):
        self.Enable(False)

    def Enable(self, enable=True):
        enable = bool(enable)
        if self.Enabled is enable:
            return
        self._enabled = enable
        self._cb.Enable(enable)
        if self._label is not self._cb:
            if not hasattr(self, "_fgcolor"):
                self._fgcolor = self.ForegroundColour
            color = self._fgcolor
            if not enable:
                bgcolor = self.Parent.BackgroundColour
                bgblend = 0.5
                blend = 0.5
                color = wx.Colour(
                    int(round(bgblend * bgcolor.Red() + blend * color.Red())),
                    int(round(bgblend * bgcolor.Green() + blend * color.Green())),
                    int(round(bgblend * bgcolor.Blue() + blend * color.Blue())),
                )
            self._label.ForegroundColour = color

    @property
    def Enabled(self):
        return self.IsEnabled()

    @Enabled.setter
    def Enabled(self, enable=True):
        self.Enable(enable)

    def IsEnabled(self):
        return self._enabled

    def OnLeftDown(self, event):
        if not self.Enabled:
            return
        self._up = False
        self._cb.SetFocus()
        event.Skip()

    def OnLeftUp(self, event):
        if not self.Enabled:
            return
        if not self._up and self.ClientRect.Contains(event.GetPosition()):
            # if the checkbox was down when the mouse was released...
            self.SendCheckBoxEvent()
        self._up = True

    def SendCheckBoxEvent(self):
        """Actually sends the event to the checkbox."""

        self.Value = not self.Value
        checkEvent = wx.CommandEvent(
            wx.wxEVT_COMMAND_CHECKBOX_CLICKED, self._cb.GetId()
        )
        checkEvent.SetInt(int(self.Value))

        # Set the originating object for the event (the checkbox)
        checkEvent.SetEventObject(self._cb)

        # Watch for a possible listener of this event that will catch it and
        # eventually process it
        self._cb.GetEventHandler().ProcessEvent(checkEvent)

    def SetMaxFontSize(self, pointsize=11):
        self._label.SetMaxFontSize(pointsize)

    def GetValue(self):
        """Returns the state of CustomCheckBox, True if checked, False
        otherwise.
        """

        return self._cb.Value

    def IsChecked(self):
        """This is just a maybe more readable synonym for GetValue: just as the
        latter, it returns True if the CustomCheckBox is checked and False
        otherwise.
        """

        return self._cb.Value

    def SetValue(self, state):
        """Sets the CustomCheckBox to the given state. This does not cause a
        wx.wxEVT_COMMAND_CHECKBOX_CLICKED event to get emitted.
        """

        self._cb.Value = state

    def GetLabel(self):
        return self._label.Label

    def SetLabel(self, label):
        self._label.Label = label

    def SetForegroundColour(self, color):
        wx.Panel.SetForegroundColour(self, color)
        self._label.ForegroundColour = color

    @property
    def Label(self):
        return self.GetLabel()

    @Label.setter
    def Label(self, label):
        self.SetLabel(label)

    @property
    def Value(self):
        return self.GetValue()

    @Value.setter
    def Value(self, state):
        self.SetValue(state)

    @property
    def ForegroundColour(self):
        return self.GetForegroundColour()

    @ForegroundColour.setter
    def ForegroundColour(self, color):
        self.SetForegroundColour(color)


class CustomCellEditor(wx.grid.PyGridCellEditor):
    def __init__(self, grid):
        wx.grid.PyGridCellEditor.__init__(self)
        self._grid = grid
        self._cell_renderer = CustomCellRenderer()

    def Create(self, parent, id, evtHandler):
        """Called to create the control, which must derive from wx.Control."""
        print(
            "CustomCellEditor.Create(%r, %r, %r) was called. This "
            "should not happen, but is unlikely an issue." % (parent, id, evtHandler)
        )
        self.SetControl(wx.StaticText(parent, -1, ""))

    def SetSize(self, rect):
        """Called to position/size the edit control within the cell rectangle.
        If you don't fill the cell (the rect) then be sure to override
        PaintBackground and do something meaningful there.
        """
        print(
            "CustomCellEditor.SetSize(%r) was called. This should not "
            "happen, but is unlikely an issue." % rect
        )
        self.Control.SetDimensions(
            rect.x, rect.y, rect.width, rect.height, wx.SIZE_ALLOW_MINUS_ONE
        )

    def Show(self, show, attr):
        """Show or hide the edit control.  You can use the attr (if not None)
        to set colours or fonts for the control.
        """
        print(
            "CustomCellEditor.Show(%r, %r) was called. This should "
            "not happen, but is unlikely an issue." % (show, attr)
        )
        super(self.__class__, self).Show(show, attr)

    def PaintBackground(self, dc, rect, attr=None):
        """Draws the part of the cell not occupied by the edit control.  The
        base  class version just fills it with background colour from the
        attribute.  In this class the edit control fills the whole cell so
        don't do anything at all in order to reduce flicker.
        """
        self._cell_renderer.Draw(
            self._grid,
            attr,
            dc,
            rect,
            self._grid.GetGridCursorRow(),
            self._grid.GetGridCursorCol(),
            True,
        )

    def BeginEdit(self, row, col, grid):
        """Fetch the value from the table and prepare the edit control
        to begin editing.  Set the focus to the edit control.
        """
        print(
            "CustomCellEditor.BeginEdit(%r, %r, %r) was called. This "
            "should not happen, but is unlikely an issue." % (row, col, grid)
        )

    def EndEdit(self, row, col, grid, value=None):
        """Complete the editing of the current cell. Returns True if the value
        has changed.  If necessary, the control may be destroyed.
        """
        print(
            "CustomCellEditor.EndEdit(%r, %r, %r, %r) was called. This "
            "should not happen, but is unlikely an issue." % (row, col, grid, value)
        )
        if wx.VERSION >= (2, 9):
            changed = None
        else:
            changed = False
        return changed

    def Reset(self):
        """Reset the value in the control back to its starting value."""
        print(
            "CustomCellEditor.Reset() was called. This should "
            "not happen, but is unlikely an issue."
        )

    def IsAcceptedKey(self, evt):
        """Return True to allow the given key to start editing: the base class
        version only checks that the event has no modifiers.  F2 is special
        and will always start the editor.
        """
        return False

    def StartingKey(self, evt):
        """If the editor is enabled by pressing keys on the grid, this will be
        called to let the editor do something about that first key if desired.
        """
        print(
            "CustomCellEditor.StartingKey(%r) was called. This should "
            "not happen, but is unlikely an issue." % evt
        )
        evt.Skip()

    def StartingClick(self):
        """If the editor is enabled by clicking on the cell, this method will be
        called to allow the editor to simulate the click on the control if
        needed.
        """

    def Destroy(self):
        """final cleanup"""
        super(self.__class__, self).Destroy()

    def Clone(self):
        """Create a new object which is the copy of this one
        *Must Override*
        """
        return self.__class__()


class CustomCellRenderer(wx.grid.PyGridCellRenderer):
    def __init__(self, *args, **kwargs):
        wx.grid.PyGridCellRenderer.__init__(self)
        self.specialbitmap = getbitmap("theme/checkerboard-10x10x2-333-444")
        self._selectionbitmaps = {}

    def Clone(self):
        return self.__class__()

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        orect = rect
        # if col == grid.GetNumberCols() - 1:
        #  Last column
        # w = max(grid.ClientSize[0] - rect[0], rect[2])
        # rect = wx.Rect(rect[0], rect[1], w, rect[3])
        bgcolor = grid.GetCellBackgroundColour(row, col)
        col_label = grid.GetColLabelValue(col)
        is_default_bgcolor = bgcolor == grid.GetDefaultCellBackgroundColour()
        is_read_only = grid.IsReadOnly(row, col)
        if is_default_bgcolor:
            if (is_read_only or not grid.IsEditable()) and col_label:
                bgcolor = grid.GetLabelBackgroundColour()
            if row % 2 == 0 and grid.alternate_cell_background_color:
                bgcolor = wx.Colour(*[int(v * 0.98) for v in bgcolor])
            elif bgcolor.Alpha() < 255:
                # Make sure it's opaque
                bgcolor = wx.Colour(bgcolor.Red(), bgcolor.Green(), bgcolor.Blue())
        special = bgcolor.Get(True) == (0, 0, 0, 0)
        mavericks = getattr(grid, "style", None) == "Mavericks"
        if not special and mavericks and bgcolor.Red() < 255:
            # Use Mavericks-like color scheme
            newcolor = [
                int(round(min(bgcolor.Get()[i] * (v / 102.0), 255)))
                for i, v in enumerate((98, 100, 102))
            ]
            bgcolor.Set(*newcolor)
        rowselect = grid.GetSelectionMode() == wx.grid.Grid.wxGridSelectRows
        isCursor = grid.show_cursor_outline and (
            (row, col) == (grid.GetGridCursorRow(), grid.GetGridCursorCol())
            or (rowselect and row == grid.GetGridCursorRow())
        )
        if (isSelected or isCursor) and is_default_bgcolor and col_label:
            color = grid.GetSelectionBackground()
            if isSelected:
                textcolor = grid.GetSelectionForeground()
            else:
                textcolor = grid.GetCellTextColour(row, col)
            focus = grid.Parent.FindFocus()
            if not focus or grid not in (
                focus,
                focus.GetParent(),
                focus.GetGrandParent(),
            ):
                if mavericks or sys.platform == "darwin" or "gtk3" in wx.PlatformInfo:
                    # Use Mavericks-like color scheme
                    color = wx.Colour(202, 202, 202)
                    if isSelected:
                        textcolor = wx.Colour(51, 51, 51)
                else:
                    rgb = int((color.Red() + color.Green() + color.Blue()) / 3.0)
                    color = wx.Colour(rgb, rgb, rgb)
            elif mavericks or sys.platform == "darwin" or "gtk3" in wx.PlatformInfo:
                # Use Mavericks-like color scheme
                color = wx.Colour(44, 93, 205)
                if isSelected:
                    textcolor = wx.WHITE
            else:
                alpha = (
                    grid.selection_alpha * 255 or grid.GetSelectionBackground().Alpha()
                )
                # Blend with bg color
                if alpha < 255:
                    # Alpha blending
                    bgblend = (255 - alpha) / 255.0
                    blend = alpha / 255.0
                    color = wx.Colour(
                        int(round(bgblend * bgcolor.Red() + blend * color.Red())),
                        int(round(bgblend * bgcolor.Green() + blend * color.Green())),
                        int(round(bgblend * bgcolor.Blue() + blend * color.Blue())),
                    )
        else:
            color = bgcolor
            textcolor = grid.GetCellTextColour(row, col)
        if special:
            # Special
            image = self.specialbitmap.ConvertToImage()
            image.Rescale(rect[2], rect[3])
            dc.DrawBitmap(image.ConvertToBitmap(), rect[0], rect[1])
        else:
            if (isSelected or isCursor) and col_label:
                dc.SetBrush(wx.Brush(bgcolor))
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.DrawRectangle(rect)
                rect = orect
                if not rowselect:
                    w = 60 + rect[3] * 2
                    if rect.Width > w:
                        rect.Left += int((rect.Width - w) / 2.0)
                        rect.Width = int(w)
                offset = 1  # Selection offset from cell boundary
                cb = 2  # Cursor border
                left = not rowselect or col == 0 or not grid.GetColLabelValue(col - 1)
                right = (
                    not rowselect
                    or col == grid.GetNumberCols() - 1
                    or not grid.GetColLabelValue(col + 1)
                )
                # We could use wx.GCDC, but it is buggy under wxGTK
                # (grid doesn't refresh properly when scrolling).
                # Implement our own supersampling antialiasing method
                # using wx.MemoryDC and cached bitmaps.
                # This has the drawback that it may use a lot of memory if
                # a grid has many cells with different dimensions or color
                # properties, but we make sure that old bitmaps are garbage
                # collected if the grid or rows/cols are resized by binding
                # resize events in CustomGrid initialization.
                key = (
                    rect[2:]
                    + bgcolor.Get()
                    + color.Get()
                    + (left, right, not isSelected and isCursor)
                )
                if not self._selectionbitmaps.get(key):
                    scale = 4.0  # Supersampling factor
                    offset *= scale
                    cb *= scale
                    x, y, w, h = 0, 0, rect[2] * scale, rect[3] * scale
                    self._selectionbitmaps[key] = wx.EmptyBitmap(int(w), int(h))
                    paintdc = dc
                    dc = mdc = wx.MemoryDC(self._selectionbitmaps[key])
                    dc.SetBrush(wx.Brush(bgcolor))
                    dc.SetPen(wx.TRANSPARENT_PEN)
                    dc.DrawRectangle(int(x), int(y), int(w), int(h))
                    dc.SetBrush(wx.Brush(color))
                    dc.SetPen(wx.TRANSPARENT_PEN)
                    draw = dc.DrawRoundedRectangle
                    draw(
                        int(x + offset),
                        int(y + offset),
                        int(w - offset * 2),
                        int(h - offset * 2),
                        int(h / 2.0 - offset),
                    )
                    if not left:
                        dc.DrawRectangle(
                            int(x), int(y + offset), int(h / 2.0), int(h - offset * 2)
                        )
                    if not right:
                        dc.DrawRectangle(
                            int(x + w - h / 2.0),
                            int(y + offset),
                            int(h / 2.0),
                            int(h - offset * 2),
                        )
                    if not isSelected and isCursor:
                        dc.SetBrush(wx.Brush(bgcolor))
                        draw(
                            int(x + offset + cb),
                            int(y + offset + cb),
                            int(w - (offset + cb) * 2),
                            int(h - (offset + cb) * 2),
                            int(h / 2.0 - (offset + cb)),
                        )
                        if not left:
                            dc.DrawRectangle(
                                int(x),
                                int(y + offset + cb),
                                int(h / 2.0),
                                int(h - (offset + cb) * 2),
                            )
                        if not right:
                            dc.DrawRectangle(
                                int(x + w - h / 2.0),
                                int(y + offset + cb),
                                int(h / 2.0),
                                int(h - (offset + cb) * 2),
                            )
                    mdc.SelectObject(wx.NullBitmap)
                    dc = paintdc
                    img = self._selectionbitmaps[key].ConvertToImage()
                    # Scale down to original size ("antialiasing")
                    img.Rescale(rect[2], rect[3])
                    self._selectionbitmaps[key] = img.ConvertToBitmap()
                bmp = self._selectionbitmaps.get(key)
                if bmp:
                    dc.DrawBitmap(bmp, rect[0], rect[1])
            else:
                dc.SetBrush(wx.Brush(color))
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.DrawRectangle(rect)
        dc.SetFont(grid.GetCellFont(row, col))
        dc.SetTextForeground(textcolor)
        self.DrawLabel(grid, dc, orect, row, col)

    def DrawLabel(self, grid, dc, rect, row, col):
        align = grid.GetCellAlignment(row, col)
        if align[1] == wx.ALIGN_CENTER:
            align = align[0], wx.ALIGN_CENTER_VERTICAL
        dc.DrawLabel(grid.GetCellValue(row, col), rect, align[0] | align[1])

    def GetBestSize(self, grid, attr, dc, row, col):
        dc.SetFont(grid.GetCellFont(row, col))
        return dc.GetTextExtent(grid.GetCellValue(row, col))


class CustomCellBoolRenderer(CustomCellRenderer):
    def __init__(self, *args, **kwargs):
        CustomCellRenderer.__init__(self)
        self._bitmap = geticon(16, "checkmark")
        self._bitmap_unchecked = geticon(16, "x")

    def DrawLabel(self, grid, dc, rect, row, col):
        if grid.GetCellValue(row, col) == "1":
            bitmap = self._bitmap
        else:
            bitmap = self._bitmap_unchecked
        x = rect[0] + int((rect[2] - self._bitmap.Size[0]) / 2.0)
        y = rect[1] + int((rect[3] - self._bitmap.Size[1]) / 2.0)
        dc.DrawBitmap(bitmap, x, y)

    def GetBestSize(self, grid, attr, dc, row, col):
        return self._bitmap.Size


class CustomColLabelRenderer(object):
    def __init__(self, bgcolor=None):
        self.bgcolor = bgcolor

    def Draw(self, grid, dc, rect, col=-1):
        if not grid.GetNumberCols():
            return
        orect = rect
        if col == grid.GetNumberCols() - 1:
            # Last column
            w = max(grid.ClientSize[0] - rect[0], rect[2])
            rect = wx.Rect(rect[0], rect[1], w, rect[3])
        mavericks = (
            getattr(grid, "style", None) == "Mavericks" or sys.platform == "darwin"
        )
        if grid.headerbitmap:
            img = grid.headerbitmap.ConvertToImage()
            img.Rescale(rect[2], rect[3], quality=wx.IMAGE_QUALITY_NORMAL)
            dc.DrawBitmap(img.ConvertToBitmap(), rect[0], 0)
            pen = wx.Pen(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW), 1, wx.SOLID
            )
            pen.SetCap(wx.CAP_BUTT)
            dc.SetPen(pen)
            dc.DrawLine(
                rect[0], rect[1] + rect[3] - 1, rect[0] + rect[2], rect[1] + rect[3] - 1
            )
        elif grid.rendernative:
            render = wx.RendererNative.Get()
            render.DrawHeaderButton(grid, dc, rect)
        else:
            if self.bgcolor:
                color = self.bgcolor
            else:
                if mavericks:
                    # Use Mavericks-like color scheme
                    color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOX)
                else:
                    color = grid.GetLabelBackgroundColour()
                if col % 2 == 0 and grid.alternate_col_label_background_color:
                    color = wx.Colour(*[int(v * 0.98) for v in color])
                elif color.Alpha() < 255:
                    # Make sure it's opaque
                    color = wx.Colour(color.Red(), color.Green(), color.Blue())
            dc.SetBrush(wx.Brush(color))
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.DrawRectangle(rect)
            pen = wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW))
            dc.SetPen(pen)
            if getattr(grid, "draw_horizontal_grid_lines", True) or (
                mavericks and not self.bgcolor
            ):
                dc.DrawLine(
                    rect[0],
                    rect[1] + rect[3] - 1,
                    rect[0] + rect[2] - 1,
                    rect[1] + rect[3] - 1,
                )
            if getattr(grid, "draw_vertical_grid_lines", True):
                dc.DrawLine(
                    rect[0] + rect[2] - 1, rect[1], rect[0] + rect[2] - 1, rect[3]
                )
        if getattr(grid, "draw_col_labels", True) and col > -1:
            dc.SetFont(grid.GetLabelFont())
            if (
                mavericks
                and not self.bgcolor
                and (
                    color.Red() == 255 and color.Green() == 255 and color.Blue() == 255
                )
            ):
                # Use Mavericks-like color scheme
                color = wx.Colour(80, 100, 120)
            else:
                color = grid.GetLabelTextColour()
            dc.SetTextForeground(color)
            align = grid.GetColLabelAlignment()
            # if align[1] == wx.ALIGN_CENTER:
            #     align = align[0], wx.ALIGN_CENTER_VERTICAL
            # dc.DrawLabel(" %s " % grid.GetColLabelValue(col), orect, align[0] | align[1])
            dc.DrawLabel(" %s " % grid.GetColLabelValue(col), orect)


class CustomRowLabelRenderer(object):
    def __init__(self, bgcolor=None):
        self.bgcolor = bgcolor

    def Draw(self, grid, dc, rect, row):
        if self.bgcolor:
            color = self.bgcolor
        else:
            color = grid.GetLabelBackgroundColour()
            if row % 2 == 0 and grid.alternate_row_label_background_color:
                color = wx.Colour(*[int(v * 0.98) for v in color])
            elif color.Alpha() < 255:
                # Make sure it's opaque
                color = wx.Colour(color.Red(), color.Green(), color.Blue())
            if getattr(grid, "style", None) == "Mavericks" and color.Red() < 255:
                # Use Mavericks-like color scheme
                newcolor = [
                    int(round(color.Get()[i] * (v / 102.0)))
                    for i, v in enumerate((98, 100, 102))
                ]
                color.Set(*newcolor)
        dc.SetBrush(wx.Brush(color))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(rect)
        pen = wx.Pen(grid.GetGridLineColour())
        dc.SetPen(pen)
        if getattr(grid, "draw_horizontal_grid_lines", True):
            dc.DrawLine(
                rect[0],
                rect[1] + rect[3] - 1,
                rect[0] + rect[2] - 1,
                rect[1] + rect[3] - 1,
            )
        if getattr(grid, "draw_vertical_grid_lines", True):
            dc.DrawLine(rect[0] + rect[2] - 1, rect[1], rect[0] + rect[2] - 1, rect[3])
        if getattr(grid, "draw_row_labels", True):
            dc.SetFont(grid.GetLabelFont())
            dc.SetTextForeground(grid.GetLabelTextColour())
            align = grid.GetRowLabelAlignment()
            if align[1] == wx.ALIGN_CENTER:
                align = align[0], wx.ALIGN_CENTER_VERTICAL
            dc.DrawLabel(" %s " % grid.GetRowLabelValue(row), rect, align[0] | align[1])


class HStretchStaticBitmap(wx.StaticBitmap):
    """A StaticBitmap that will automatically stretch horizontally.

    To be used with sizers.
    """

    def __init__(self, *args, **kwargs):
        wx.StaticBitmap.__init__(self, *args, **kwargs)
        if sys.platform in ("darwin", "win32"):
            # Works (only) under Mac OS X / Windows.
            # Works better (no jump to correct width) under Mac OS X than
            # EVT_SIZE method.
            self.Bind(wx.EVT_PAINT, self.OnPaint)
        else:
            # Works under Mac OS X, Windows and Linux.
            # Under Mac OS X, this visibly jumps to the correct width when
            # first shown on screen.
            self.Bind(wx.EVT_SIZE, self.OnPaint)
        self._init = False

    def OnPaint(self, event):
        if self and self.GetBitmap() and self.GetBitmap().IsOk():
            if hasattr(self, "_bmp"):
                bmp = self._bmp
            else:
                bmp = self.GetBitmap()
                self._bmp = bmp
            w = self.Size[0]
            if getattr(self, "_width", -1) != w:
                img = bmp.ConvertToImage()
                img.Rescale(w, img.GetSize()[1])
                bmp = img.ConvertToBitmap()
                self._width = w
                # Avoid flicker under Windows
                if self._init:
                    self.Freeze()
                self.SetBitmap(bmp)
                self.MinSize = self._bmp.GetSize()
                if self._init:
                    self.IsFrozen() and self.Thaw()
                elif self.IsShownOnScreen():
                    self._init = True
        if event:
            event.Skip()


class HyperLinkCtrl(hyperlink.HyperLinkCtrl):
    def __init__(self, *args, **kwargs):
        hyperlink.HyperLinkCtrl.__init__(self, *args, **kwargs)
        bgcolor, text, linkcolor, vlinkcolor = get_html_colors()
        self.SetColours(linkcolor, vlinkcolor, linkcolor)
        self.DoPopup(False)
        self.UpdateLink()
        self.Bind(hyperlink.EVT_HYPERLINK_RIGHT, self.OnPopup)

    def OnPopup(self, event):
        """Pops up a menu with 'Copy link address'"""
        menuPopUp = wx.Menu("", wx.MENU_TEAROFF)
        menuPopUp.Append(
            hyperlink.wxHYPERLINKS_POPUP_COPY, lang.getstr("link.address.copy")
        )
        self.Bind(wx.EVT_MENU, self.OnPopUpCopy, id=hyperlink.wxHYPERLINKS_POPUP_COPY)
        self.PopupMenu(menuPopUp, event.GetPosition())
        menuPopUp.Destroy()
        self.Unbind(wx.EVT_MENU, id=hyperlink.wxHYPERLINKS_POPUP_COPY)

    if sys.platform not in ("darwin", "win32") and "gtk3" in wx.PlatformInfo:

        def SetFont(self, font):
            scale = (getcfg("app.dpi") / get_default_dpi()) or 1
            font.PointSize = int(font.PointSize * scale)
            hyperlink.HyperLinkCtrl.SetFont(self, font)


def fancytext_Renderer_getCurrentFont(self):
    # Use system font instead of fancytext default font
    font = self.fonts[-1]
    _font = self._font or wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
    if "encoding" in font:
        _font.SetEncoding(font["encoding"])
    if "family" in font:
        _font.SetFamily(font["family"])
    if "size" in font:
        _font.SetPointSize(font["size"])
    if "gtk3" in wx.PlatformInfo:
        scale = getcfg("app.dpi") / get_default_dpi()
        _font.SetPointSize(_font.GetPointSize() * scale)
    if "style" in font:
        _font.SetStyle(font["style"])
    if "weight" in font:
        _font.SetWeight(font["weight"])
    return _font


def fancytext_Renderer_getCurrentColor(self):
    # Use system text color instead of fancytext default color
    font = self.fonts[-1]
    if "color" in font:
        return wx.TheColourDatabase.FindColour(font["color"])
    else:
        return wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)


fancytext.Renderer._font = None
fancytext.Renderer.getCurrentColor = fancytext_Renderer_getCurrentColor
fancytext.Renderer.getCurrentFont = fancytext_Renderer_getCurrentFont


def fancytext_RenderToRenderer(text, renderer, enclose=True):
    text = safe_str(text, "UTF-8")
    try:
        if enclose:
            text = f'<?xml version="1.0"?><FancyText>{text}</FancyText>'
        p = xml.parsers.expat.ParserCreate()
        p.StartElementHandler = renderer.startElement
        p.EndElementHandler = renderer.endElement
        p.CharacterDataHandler = renderer.characterData
        p.Parse(text, True)
    except xml.parsers.expat.error as err:
        raise ValueError(f'error parsing text text "{text}": {err}') from err


fancytext.RenderToRenderer = fancytext_RenderToRenderer


class BetterPyGauge(pygauge.PyGauge):
    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        range=100,
        pos=wx.DefaultPosition,
        size=(-1, 30),
        style=0,
        pd=None,
    ):
        self.pd = pd
        self.dpiscale = getcfg("app.dpi") / get_default_dpi()
        if self.dpiscale > 1:
            size = tuple(int(round(v * self.dpiscale)) if v != -1 else v for v in size)
        pygauge.PyGauge.__init__(self, parent, id, range, pos, size, style)
        self._indeterminate = False
        self.gradientindex = 0
        self._gradients = []
        self._indeterminate_gradients = []
        self._timer = BetterTimer(self)
        self.Unbind(wx.EVT_TIMER)
        self.Bind(EVT_BETTERTIMER, self.OnTimer, self._timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Start()

    def OnDestroy(self, event):
        self._timer.Stop()
        del self._timer

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` event for L{PyGauge}.

        :param event: a `wx.PaintEvent` event to be processed.
        """

        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        dc.SetBackground(wx.Brush(self.Parent.BackgroundColour))
        dc.Clear()

        rect = self.GetClientRect()

        if self._border_colour:
            gc.SetPen(wx.Pen(self._border_colour))
        else:
            gc.SetPen(wx.Pen(self.BackgroundColour))
        gc.SetBrush(wx.Brush(self.BackgroundColour))
        gc.DrawRoundedRectangle(
            rect.X,
            rect.Y,
            rect.Width - 1 * self.dpiscale,
            rect.Height - 1 * self.dpiscale,
            (rect.Height - 1 * self.dpiscale) / 2,
        )

        pad = self.GetBorderPadding()
        if self._border_colour:
            pad += 1
        pad *= self.dpiscale
        if pad:
            rect.Deflate(pad, pad)

        if self._barGradientSorted:
            for i, gradient in enumerate(self._barGradientSorted):
                c1, c2 = gradient
                w = max(
                    rect.Width * (float(self._valueSorted[i]) / self._range),
                    rect.Height,
                )
                gc.SetBrush(
                    gc.CreateLinearGradientBrush(
                        rect.X, rect.Y, rect.Y + w, rect.Y, c1, c2
                    )
                )
                gc.SetPen(wx.TRANSPARENT_PEN)
                gc.DrawRoundedRectangle(
                    rect.X, rect.Y, w, rect.Height, (rect.Height) / 2
                )

    def OnTimer(self, event):
        gradient = self._barGradient
        if self._indeterminate:
            if self.gradientindex < len(self._indeterminate_gradients) - 1:
                self.gradientindex += 1
            else:
                self.gradientindex = 0
            self._barGradient = [self._indeterminate_gradients[self.gradientindex]]
        else:
            if self.gradientindex < len(self._gradients) - 1:
                self.gradientindex += 1
            else:
                self.gradientindex = 0
            self._barGradient = [self._gradients[self.gradientindex]]
        if hasattr(self, "_update_step") and not self._indeterminate:
            stop = True
            for i, v in enumerate(self._value):
                self._value[i] += self._update_step[i]

                if self._update_step[i] > 0:
                    if self._value[i] > self._update_value[i]:
                        self._value[i] = self._update_value[i]
                    else:
                        stop = False
                else:
                    if self._value[i] < self._update_value[i]:
                        self._value[i] = self._update_value[i]
                    else:
                        stop = False
            if self.pd and self.pd.taskbar:
                self.pd.taskbar.set_progress_value(int(round(self.GetValue())))
            if stop:
                del self._update_step
            updated = True
        else:
            updated = False
        if gradient != self._barGradient or updated:
            self.SortForDisplay()
            if self._indeterminate:
                self._valueSorted = [self.GetRange()]
            self.Refresh()

    def IsRunning(self):
        return self._timer.IsRunning()

    def Pulse(self):
        self._indeterminate = True

    def SetBarGradients(self, gradients):
        self._gradients = gradients

    def SetIndeterminateBarGradients(self, gradients):
        self._indeterminate_gradients = gradients

    def SetValue(self, value):
        self._indeterminate = False
        pygauge.PyGauge.SetValue(self, value)
        self.Refresh()

    def Start(self, milliseconds=67):
        self._timer.Start(milliseconds)

    def Stop(self):
        self._timer.Stop()

    def Update(self, value, time=0):
        """Update the gauge by adding `value` to it over `time` milliseconds. The `time` parameter
        **must** be a multiple of 50 milliseconds.

        :param value: The value to be added to the gauge;
        :param time: The length of time in milliseconds that it will take to move the gauge.
        """
        self._indeterminate = False

        if type(value) != type([]):
            value = [value]

        if len(value) != len(self._value):
            raise Exception("ERROR:\n len(value) != len(self.GetValue())")

        self._update_value = []
        self._update_step = []
        for i, v in enumerate(self._value):
            if value[i] < 0 or value[i] > self._range:
                warnings.warn(
                    "Gauge value %r is invalid - must be between 0 "
                    "and %s" % (value[i], self._range),
                    Warning,
                )
                if value[i] < 0:
                    value[i] = 0
                else:
                    value[i] = self._range

            self._update_value.append(value[i])
            self._update_step.append((float(value[i]) - v) / (time / 50))


class BetterStaticFancyTextBase(object):
    def GetLabel(self):
        return self._rawlabel

    @property
    def Label(self):
        return self._rawlabel

    @Label.setter
    def Label(self, label):
        self.SetLabel(label)

    def SetLabel(self, label):
        self._rawlabel = label
        # Wrap ignoring tags, only break in whitespace
        wrapped = ""
        llen = 0
        intag = False
        hyphens = "-\u2012\u2013\u2014\u2015"
        whitespace = "\n\t "
        for c in label:
            if c == "<":
                intag = True
            if c in hyphens:
                hyphen = True
            else:
                hyphen = False
            if intag and c == ">":
                intag = False
            elif not intag:
                llen += 1
                if llen > self.maxlen and (c in whitespace or hyphen):
                    if hyphen:
                        wrapped += c
                    elif llen > self.maxlen + 1:
                        for i, rc in enumerate(reversed(wrapped)):
                            if rc == ">":
                                intag = True
                            elif not intag and rc in whitespace + hyphens:
                                line = wrapped[-i:]
                                llen = 1
                                for rc in reversed(line):
                                    if rc == ">":
                                        intag = True
                                    if not intag:
                                        llen += 1
                                    elif rc == "<":
                                        intag = False
                                wrapped = wrapped[:-i] + "\n" + line
                                break
                            elif intag and rc == "<":
                                intag = False
                    if llen > self.maxlen:
                        c = "\n"
                if c == "\n":
                    llen = 0
            wrapped += c
        self._label = wrapped


class BetterStaticFancyText(BetterStaticFancyTextBase, GenStaticBitmap):
    """Based on wx.lib.fancytext functionality.

    Renders crisp on 'Retina' displays under OS X and in high DPI mode
    under Linux/Windows.

    """

    _enabled = True
    _rawlabel = ""
    maxlen = 119

    def __init__(self, window, id, text, *args, **kargs):
        args = list(args)
        kargs.setdefault("name", "staticFancyText")
        # Ignore background, always use parent background
        if "background" in kargs:
            kargs.pop("background")
        elif args:
            args.pop(0)

        bmp = wx.EmptyBitmap(1, 1)
        GenStaticBitmap.__init__(self, window, id, bmp, *args, **kargs)
        self.Label = text

    def Disable(self):
        self.Enable(False)

    def Enable(self, enable=True):
        self._enabled = enable
        if sys.platform != "win32":
            return
        if enable:
            bmp = self._enabledbitmap
        else:
            bmp = (
                self._enabledbitmap.ConvertToImage()
                .AdjustChannels(1, 1, 1, 0.5)
                .ConvertToBitmap()
            )
        self.SetBitmap(bmp)

    def IsEnabled(self):
        return self._enabled

    Enabled = property(IsEnabled, Enable)

    def GetFont(self):
        return fancytext.Renderer._font or wx.SystemSettings_GetFont(
            wx.SYS_DEFAULT_GUI_FONT
        )

    def OnPaint(self, event):
        if sys.platform != "win32":
            # AutoBufferedPaintDCFactory is the magic needed for crisp text
            # rendering in HiDPI mode under OS X and Linux
            cls = wx.AutoBufferedPaintDCFactory
        else:
            cls = wx.BufferedPaintDC
        dc = cls(self)
        dc.SetBackground(wx.Brush(self.Parent.BackgroundColour, wx.SOLID))
        dc.SetBackgroundMode(wx.TRANSPARENT)
        dc.Clear()
        if sys.platform != "win32":
            fancytext.RenderToDC(self._label, dc, 0, 0)
        elif self._bitmap:
            dc.DrawBitmap(self._bitmap, 0, 0, True)

    def SetFont(self, font):
        fancytext.Renderer._font = font

    def SetLabel(self, label):
        BetterStaticFancyTextBase.SetLabel(self, label)
        background = wx.Brush(self.Parent.BackgroundColour, wx.SOLID)
        try:
            bmp = fancytext.RenderToBitmap(self._label, background)
        except ValueError:
            # XML parsing error, strip all tags
            self._label = re.sub(r"<[^>]*?>", "", self._label)
            self._label = self._label.replace("<", "").replace(">", "")
            bmp = fancytext.RenderToBitmap(self._label, background)
        if sys.platform == "win32":
            self._enabledbitmap = bmp
            self.SetBitmap(bmp)
        else:
            self.Size = self.MinSize = bmp.Size
            self.Refresh()


# Better under GTK (no text cutoff)
class BetterStaticFancyText_SetLabelMarkup(BetterStaticFancyTextBase, wx.Panel):
    def __init__(self, parent, id, text, *args, **kwargs):
        wx.Panel.__init__(self, parent, id, *args, **kwargs)
        self.maxlen = 119
        self._st = wx.StaticText(self, -1, "")
        self.Label = text

    def SetLabel(self, label):
        BetterStaticFancyTextBase.SetLabel(self, label)
        markup = label.replace("<font", "<span")
        markup = markup.replace("</font>", "</span>")
        # Decode entities
        markup = html.unescape(markup)
        self._st.SetLabelMarkup(markup)
        # Figure out min size
        minw = 0
        minh = 0
        normal_font = self.Font
        bold_font = self.Font
        bold_font.Weight = wx.FONTWEIGHT_BOLD
        xh = self.GetTextExtent("X")[1]
        for i, line in enumerate(self._label.splitlines()):
            if line:
                # Account for bold text which is approximately 14% wider
                parts = re.findall(r"(<font weight='bold'>([^<]+)</font>|[^<]+)", line)
                w, h = 0, 0
                for markup, bold in parts:
                    if bold:
                        text = bold
                        font = bold_font
                    else:
                        text = markup
                        font = normal_font
                    # Strip all remaining tags
                    text = re.sub(r"<[^>]*?>", "", text)
                    text = text.replace("<", "").replace(">", "")
                    # Decode entities
                    text = html.unescape(text)
                    te = self.GetFullTextExtent(text, font)[:2]
                    w += te[0]
                    h = max(te[1], h)
                minw = max(w, minw)
            else:
                # Deal with empty lines having text extent of (0, 0)
                h = xh
            minh += h
        self._st.MaxSize = (-1, -1)
        self._st.Size = self._st.MinSize = minw, minh
        self._st.MaxSize = minw, -1
        self.Layout()


if wx.Platform == "__WXGTK__" and hasattr(wx.StaticText, "SetLabelMarkup"):
    BetterStaticFancyText = BetterStaticFancyText_SetLabelMarkup


class InfoDialog(BaseInteractiveDialog):
    """Informational dialog with OK button"""

    def __init__(
        self,
        parent=None,
        id=-1,
        title=appname,
        msg="",
        ok="OK",
        bitmap=None,
        pos=(-1, -1),
        size=(400, -1),
        show=True,
        log=True,
        bitmap_margin=None,
        nowrap=False,
        wrap=70,
    ):
        BaseInteractiveDialog.__init__(
            self,
            parent,
            id,
            title,
            msg,
            ok,
            bitmap,
            pos,
            size,
            show,
            log,
            nowrap=nowrap,
            wrap=wrap,
            bitmap_margin=bitmap_margin,
        )


class InvincibleFrame(BaseFrame):
    """A frame that won't be destroyed when closed"""

    def __init__(
        self,
        parent=None,
        id=-1,
        title="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=wx.DEFAULT_FRAME_STYLE,
        name=wx.FrameNameStr,
    ):
        BaseFrame.__init__(self, parent, id, title, pos, size, style, name)
        self.Bind(wx.EVT_CLOSE, self.OnClose, self)

    def OnClose(self, event):
        self.Hide()


class LogWindow(InvincibleFrame):
    """A log-type window with Clear and Save As buttons"""

    def __init__(
        self,
        parent=None,
        id=-1,
        title=None,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        logctrlstyle=wx.TE_MULTILINE | wx.TE_RICH | wx.NO_BORDER | wx.TE_READONLY,
    ):
        if not title:
            title = lang.getstr("infoframe.title")
        if pos == wx.DefaultPosition:
            pos = getcfg("position.info.x"), getcfg("position.info.y")
        if size == wx.DefaultSize:
            size = getcfg("size.info.w"), getcfg("size.info.h")
        InvincibleFrame.__init__(
            self, parent, id, title, pos=pos, style=wx.DEFAULT_FRAME_STYLE, name="info"
        )
        self.last_visible = False
        self.panel = wx.Panel(self, -1)
        # Fix wrong background color when disabled
        self.panel.Enable = lambda enable=True: None
        self.panel.Disable = lambda: None
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.sizer)
        self.log_txt = wx.TextCtrl(self.panel, -1, "", style=logctrlstyle)
        # Fix wrong background color under Linux when losing focus
        self.log_txt.BackgroundColour = self.log_txt.BackgroundColour
        # Fix wrong background color when disabled
        self.log_txt.Enable = lambda enable=True: None
        self.log_txt.Disable = lambda: None
        if "phoenix" in wx.PlatformInfo:
            kwarg = "faceName"
        else:
            kwarg = "face"
        if sys.platform == "win32":
            font = wx.Font(
                9,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                **{kwarg: "Consolas"},
            )
        elif sys.platform == "darwin":
            font = wx.Font(
                11,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                **{kwarg: "Monaco"},
            )
        else:
            font = wx.Font(
                10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
            )
        self.log_txt.SetFont(font)
        self.log_txt.SetDefaultStyle(
            wx.TextAttr(
                self.log_txt.ForegroundColour, self.log_txt.BackgroundColour, font=font
            )
        )
        bgcol = wx.Colour(
            int(self.log_txt.BackgroundColour.Red() * 0.5),
            int(self.log_txt.BackgroundColour.Green() * 0.5),
            int(self.log_txt.BackgroundColour.Blue() * 0.5),
        )
        fgcol = wx.Colour(
            int(bgcol.Red() + self.log_txt.ForegroundColour.Red() * 0.5),
            int(bgcol.Green() + self.log_txt.ForegroundColour.Green() * 0.5),
            int(bgcol.Blue() + self.log_txt.ForegroundColour.Blue() * 0.5),
        )
        self._1stcolstyle = wx.TextAttr(fgcol, self.log_txt.BackgroundColour, font=font)
        self.sizer.Add(self.log_txt, 1, flag=wx.EXPAND)
        self.log_txt.MinSize = (
            self.log_txt.GetTextExtent("=" * 95)[0]
            + wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
            defaults["size.info.h"] - 24 - max(0, self.Size[1] - self.ClientSize[1]),
        )
        separator = BitmapBackgroundPanel(self.panel, size=(-1, 1))
        separator.SetBackgroundColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
        )
        self.sizer.Add(separator, flag=wx.EXPAND)
        self.btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.btnsizer, flag=wx.EXPAND)
        self.save_as_btn = GenBitmapButton(
            self.panel, -1, geticon(16, "document-save-as"), style=wx.NO_BORDER
        )
        self.save_as_btn.Bind(wx.EVT_BUTTON, self.OnSaveAs)
        self.save_as_btn.SetToolTipString(lang.getstr("save_as"))
        self.btnsizer.Add(self.save_as_btn, flag=wx.ALL, border=4)
        self.archive_btn = GenBitmapButton(
            self.panel, -1, geticon(16, "package-x-generic"), style=wx.NO_BORDER
        )
        self.archive_btn.Bind(wx.EVT_BUTTON, self.create_logs_archive)
        self.archive_btn.SetToolTipString(lang.getstr("archive.create"))
        self.btnsizer.Add(self.archive_btn, flag=wx.ALL, border=4)
        self.clear_btn = GenBitmapButton(
            self.panel, -1, geticon(16, "edit-delete"), style=wx.NO_BORDER
        )
        self.clear_btn.Bind(wx.EVT_BUTTON, self.OnClear)
        self.clear_btn.SetToolTipString(lang.getstr("clear"))
        self.btnsizer.Add(self.clear_btn, flag=wx.ALL, border=4)
        self.sizer.SetSizeHints(self)
        self.sizer.Layout()
        self.SetSaneGeometry(*pos + size)
        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self._tspattern = re.compile(
            r"(?:\d{4}-\d{2}-\d{2} )?(\d{2}:\d{2}:\d{2},\d{3} )"
        )
        self._textwrapper = textwrap.TextWrapper(76)
        self._linecontinuation = " " * 13 + "\u21b3 "
        self._warning_lstr = lang.getstr("warning").lower()
        self._error_lstr = lang.getstr("error").lower()

    def Log(self, txt):
        # TextCtrl.AppendText is an EXPENSIVE operation under OS X.
        # For that reason, assemble the text to be added before calling it.
        lines = []
        start = self.log_txt.GetLastPosition()
        ts = None
        for line in str(txt).split("\n"):
            if sys.platform == "win32":
                # Formatting of boxes
                line = line.replace("\u2500", "-")
            tsmatch = re.match(self._tspattern, line)
            if tsmatch:
                line = line[len(tsmatch.group()) :]
                ts = tsmatch.group(1)
            elif line[:15] == self._linecontinuation:
                ts = line[:13]
                line = line[13:]
            else:
                s = time()
                ms = s - int(s)
                ts = strftime("%H:%M:%S,") + ("%.3f " % ms)[2:]
            if len(line) > 80:
                wrapped = self._textwrapper.wrap(line)
                i_last = len(wrapped) - 1
                for i, line in enumerate(wrapped):
                    if i:
                        line = self._linecontinuation + line
                    else:
                        line = ts + line
                    if i < i_last:
                        line = line.ljust(78 + 13) + " \u21B2"
                    lines.append(line)
            else:
                lines.append(ts + line)
        self.log_txt.AppendText("\n".join(lines) + "\n")
        # TextCtrl.SetStyle is an EXPENSIVE operation, especially under OS X.
        # Only set styles for (up to) the last 1000 lines.
        for line in lines[:-1000]:
            start += len(line + "\n")
        textattr = None
        warning_lstr = self._warning_lstr
        error_lstr = self._error_lstr
        for i, line in enumerate(lines[-1000:]):
            line_lower = line.lower()
            if (
                "brightness error" in line_lower
                or "white point error" in line_lower
                or "maximum neutral error" in line_lower
                or "average neutral error" in line_lower
                or "profile check complete" in line_lower
            ):
                # These are not actual errors
                pass
            elif warning_lstr in line_lower or "warning" in line_lower:
                textattr = wx.TextAttr("#F07F00", font=self.log_txt.Font)
            elif error_lstr in line_lower or "error" in line_lower:
                textattr = wx.TextAttr("#FF3300", font=self.log_txt.Font)
            self.log_txt.SetStyle(start, start + 12, self._1stcolstyle)
            if textattr:
                self.log_txt.SetStyle(start + 12, start + len(line), textattr)
                if not line.endswith(" \u21B2"):
                    textattr = None
            start += len(line + "\n")

    def ScrollToBottom(self):
        self.log_txt.ScrollLines(self.log_txt.GetNumberOfLines())

    def OnClear(self, event):
        self.log_txt.SetValue("")

    def OnClose(self, event):
        setcfg("log.show", 0)
        self.Hide()

    def OnDestroy(self, event):
        event.Skip()

    def OnMove(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            setcfg("position.info.x", x)
            setcfg("position.info.y", y)
        if event:
            event.Skip()

    def OnSaveAs(self, event):
        defaultDir, defaultFile = (
            get_verified_path("last_filedialog_path")[0],
            appname,
        )
        dlg = wx.FileDialog(
            self,
            lang.getstr("save_as"),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            wildcard=lang.getstr("filetype.log") + "|*.log",
            style=wx.SAVE | wx.OVERWRITE_PROMPT,
        )
        dlg.Center(wx.BOTH)
        result = dlg.ShowModal()
        path = dlg.GetPath()
        dlg.Destroy()
        if result == wx.ID_OK:
            if not waccess(path, os.W_OK):
                InfoDialog(
                    self,
                    msg=lang.getstr("error.access_denied.write", path),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
                return
            filename, ext = os.path.splitext(path)
            if ext.lower() != ".log":
                path += ".log"
                if os.path.exists(path):
                    dlg = ConfirmDialog(
                        self,
                        msg=lang.getstr("dialog." "confirm_overwrite", (path)),
                        ok=lang.getstr("overwrite"),
                        cancel=lang.getstr("cancel"),
                        bitmap=geticon(32, "dialog-warning"),
                    )
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result != wx.ID_OK:
                        return
            setcfg("last_filedialog_path", path)
            try:
                file_ = open(path, "w")
                file_.write(self.log_txt.GetValue().encode("UTF-8", "replace"))
                file_.close()
            except Exception as exception:
                InfoDialog(
                    self,
                    msg=str(exception),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )

    def OnSize(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            w, h = self.ClientSize
            setcfg("size.info.w", w)
            setcfg("size.info.h", h)
        if event:
            event.Skip()

    def create_logs_archive(self, event):
        wildcard = lang.getstr("filetype.tgz") + "|*.tgz"
        wildcard += "|" + lang.getstr("filetype.zip") + "|*.zip"
        defaultDir, defaultFile = (
            get_verified_path("last_filedialog_path")[0],
            appname + "-logs",
        )
        dlg = wx.FileDialog(
            self,
            lang.getstr("save_as"),
            defaultDir=defaultDir,
            defaultFile=defaultFile,
            wildcard=wildcard,
            style=wx.SAVE | wx.OVERWRITE_PROMPT,
        )
        dlg.Center(wx.BOTH)
        result = dlg.ShowModal()
        path = dlg.GetPath()
        dlg.Destroy()
        if result == wx.ID_OK:
            if not waccess(path, os.W_OK):
                InfoDialog(
                    self,
                    msg=lang.getstr("error.access_denied.write", path),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
                return
            filename, ext = os.path.splitext(path)
            if path.lower().endswith(".tar.gz"):
                format = "tgz"
            else:
                format = ext[1:]
            if ext.lower() != "." + format and (
                format != "tgz" or not path.lower().endswith(".tar.gz")
            ):
                path += "." + format
                if os.path.exists(path):
                    dlg = ConfirmDialog(
                        self,
                        msg=lang.getstr("dialog." "confirm_overwrite", (path)),
                        ok=lang.getstr("overwrite"),
                        cancel=lang.getstr("cancel"),
                        bitmap=geticon(32, "dialog-warning"),
                    )
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result != wx.ID_OK:
                        return
            setcfg("last_filedialog_path", path)
            if format == "tgz":
                # Create gzipped tar archive
                with tarfile.open(path, "w:gz", encoding="UTF-8") as tar:
                    tar.add(logdir, arcname=os.path.basename(path))
            else:
                # Create ZIP archive
                try:
                    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zip:
                        for filename in os.listdir(logdir):
                            zip.write(os.path.join(logdir, filename), filename)
                except Exception as exception:
                    InfoDialog(
                        self,
                        msg=str(exception),
                        ok=lang.getstr("ok"),
                        bitmap=geticon(32, "dialog-error"),
                    )


class ProgressDialog(wx.Dialog):
    """A progress dialog."""

    bitmaps = {}

    def __init__(
        self,
        title=appname,
        msg="",
        maximum=100,
        parent=None,
        style=None,
        handler=None,
        keyhandler=None,
        start_timer=True,
        pos=None,
        pauseable=False,
        fancy=True,
        allow_close=False,
    ):
        if style is None:
            style = (
                wx.PD_APP_MODAL
                | wx.PD_ELAPSED_TIME
                | wx.PD_REMAINING_TIME
                | wx.PD_CAN_ABORT
                | wx.PD_SMOOTH
            )
        self._style = style
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title, name="progressdialog")
        if fancy:
            self.BackgroundColour = "#141414"
            self.ForegroundColour = "#FFFFFF"
        self.taskbar = None
        if sys.platform == "win32":
            if not fancy:
                bgcolor = self.BackgroundColour
                self.SetBackgroundColour(
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
                )
            if sys.getwindowsversion() >= (6,):
                # No need to enable double buffering under Linux and Mac OS X.
                # Under Windows, enabling double buffering on the panel seems
                # to work best to reduce flicker.
                self.SetDoubleBuffered(True)
        set_icons(self)
        self.Bind(wx.EVT_CLOSE, self.OnClose, self)
        if not pos:
            self.Bind(wx.EVT_MOVE, self.OnMove, self)
        self.timer = BetterTimer(self)
        self.Bind(EVT_BETTERTIMER, handler or self.OnTimer, self.timer)

        self.indeterminate = True
        self.keepGoing = True
        self.skip = False
        self.paused = False
        self.progress_type = 0  # 0 = processing, 1 = measurement
        self.allow_close = allow_close

        margin = 12

        self.sizer0 = wx.BoxSizer(wx.VERTICAL)
        if fancy:
            self.sizerH = wx.BoxSizer(wx.HORIZONTAL)
            self.SetSizer(self.sizerH)
            self.animbmp = AnimatedBitmap(self, -1, size=(200, 200))
            self.sizerH.Add(self.animbmp, 0, flag=wx.ALIGN_CENTER_VERTICAL)
            self.sizerH.Add(self.sizer0, 1, flag=wx.EXPAND)
            try:
                audio.init()
            except Exception as exception:
                print(exception)
            self.processor_sound = audio.Sound(
                get_data_path("theme/engine_hum_loop.wav"), True
            )
            self.generator_sound = audio.Sound(
                get_data_path("theme/pulsing_loop.wav"), True
            )
            self.sound = self.processor_sound
            self.indicator_sound = audio.Sound(get_data_path("theme/beep_boop.wav"))
            ProgressDialog.get_bitmaps(self.progress_type)
            sizer0flag = 0
        else:
            self.SetSizer(self.sizer0)
            sizer0flag = wx.LEFT
        self.sizer1 = wx.BoxSizer(wx.VERTICAL)
        self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer0.Add(
            self.sizer1,
            flag=wx.ALIGN_LEFT | wx.TOP | wx.RIGHT | sizer0flag,
            border=margin,
        )
        self.buttonpanel = wx.Panel(self)
        self.buttonpanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.buttonpanel.Sizer.Add(
            self.sizer2, 1, flag=wx.ALIGN_RIGHT | wx.ALL, border=margin
        )
        if sys.platform == "win32" and not fancy:
            self.buttonpanel_line = wx.Panel(self, size=(-1, 1))
            self.buttonpanel_line.SetBackgroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
            )
            self.sizer0.Add(
                self.buttonpanel_line, flag=wx.TOP | wx.EXPAND, border=margin
            )
            self.buttonpanel.SetBackgroundColour(bgcolor)
        elif fancy:
            self.buttonpanel.BackgroundColour = "#141414"
        self.sizer0.Add(self.buttonpanel, flag=wx.EXPAND)

        self.msg = wx.StaticText(self, -1, "", size=(-1, 74))
        self.sizer1.Add(self.msg, flag=wx.EXPAND | wx.BOTTOM, border=margin)

        self._fpprogress = 0.0
        if fancy:
            self.gauge = BetterPyGauge(
                self, wx.ID_ANY, range=maximum, size=(-1, 4), pd=self
            )
            self.gauge.BackgroundColour = "#003366"
            self.gauge.SetBarGradients(
                [
                    ("#0099CC", "#00CCFF"),
                    ("#0088BB", "#00BBEE"),
                    ("#0077AA", "#00AADD"),
                    ("#006699", "#0099CC"),
                    ("#0077AA", "#00AADD"),
                    ("#0088BB", "#00BBEE"),
                ]
            )
            self.gauge.SetIndeterminateBarGradients(
                [
                    ("#00CCFF", "#001144"),
                    ("#00BBEE", "#002255"),
                    ("#00AADD", "#003366"),
                    ("#0099CC", "#004477"),
                    ("#0088BB", "#005588"),
                    ("#0077AA", "#006699"),
                    ("#006699", "#0077AA"),
                    ("#005588", "#0088BB"),
                    ("#004477", "#0099CC"),
                    ("#003366", "#00AADD"),
                    ("#002255", "#00BBEE"),
                    ("#001144", "#00CCFF"),
                    ("#002255", "#00BBEE"),
                    ("#003366", "#00AADD"),
                    ("#004477", "#0099CC"),
                    ("#005588", "#0088BB"),
                    ("#006699", "#0077AA"),
                    ("#0077AA", "#006699"),
                    ("#0088BB", "#005588"),
                    ("#0099CC", "#004477"),
                    ("#00AADD", "#003366"),
                    ("#00BBEE", "#002255"),
                ]
            )
            self.gauge.SetValue(0)
        else:
            gauge_style = wx.GA_HORIZONTAL
            if style & wx.PD_SMOOTH:
                gauge_style |= wx.GA_SMOOTH
            self.gauge = wx.Gauge(self, wx.ID_ANY, range=maximum, style=gauge_style)
        self.sizer1.Add(self.gauge, flag=wx.EXPAND | wx.BOTTOM, border=margin)

        if style & wx.PD_ELAPSED_TIME or style & wx.PD_REMAINING_TIME:
            self.sizer3 = wx.FlexGridSizer(0, 2, 0, margin)
            self.sizer1.Add(self.sizer3, flag=wx.ALIGN_LEFT)

        if style & wx.PD_ELAPSED_TIME:
            self.elapsed_time_label = wx.StaticText(
                self, -1, lang.getstr("elapsed_time")
            )
            self.elapsed_time_label.SetMaxFontSize(11)
            self.sizer3.Add(self.elapsed_time_label)
            self.elapsed_time = wx.StaticText(self, -1, "")
            self.elapsed_time.SetMaxFontSize(11)
            self.sizer3.Add(self.elapsed_time)
            self.elapsed_timer = BetterTimer(self)
            self.Bind(EVT_BETTERTIMER, self.elapsed_time_handler, self.elapsed_timer)

        if style & wx.PD_REMAINING_TIME:
            self.remaining_time_label = wx.StaticText(
                self, -1, lang.getstr("remaining_time")
            )
            self.remaining_time_label.SetMaxFontSize(11)
            self.sizer3.Add(self.remaining_time_label)
            self.remaining_time = wx.StaticText(self, -1, "")
            self.remaining_time.SetMaxFontSize(11)
            self.sizer3.Add(self.remaining_time)

        self.reset()

        if fancy:

            def buttoncls(parent, id, label):
                return FlatShadedButton(parent, id, None, label, fgcolour="#FFFFFF")

        else:
            buttoncls = wx.Button

        if style & wx.PD_CAN_ABORT:
            self.cancel = buttoncls(self.buttonpanel, wx.ID_ANY, lang.getstr("cancel"))
            self.sizer2.Add(self.cancel)
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.cancel.GetId())

        self.pause_continue = buttoncls(
            self.buttonpanel, wx.ID_ANY, lang.getstr("continue")
        )
        self.sizer2.Prepend((margin, margin))
        self.sizer2.Prepend(self.pause_continue, flag=wx.LEFT, border=margin)
        self.Bind(
            wx.EVT_BUTTON, self.pause_continue_handler, id=self.pause_continue.GetId()
        )
        self.pause_continue.Show(pauseable)

        if fancy:
            bitmap = self.get_sound_on_off_btn_bitmap()
            self.sound_on_off_btn = FlatShadedButton(
                self.buttonpanel, bitmap=bitmap, fgcolour="#FFFFFF"
            )
            self.sizer2.Prepend(self.sound_on_off_btn)
            self.sound_on_off_btn.Bind(wx.EVT_BUTTON, self.play_sound_handler)

        self.buttonpanel.Layout()

        # Use an accelerator table for 0-9, a-z, numpad
        keycodes = list(range(48, 58)) + list(range(97, 123)) + numpad_keycodes
        self.id_to_keycode = {}
        for keycode in keycodes:
            self.id_to_keycode[wx.Window.NewControlId()] = keycode
        accels = []
        for id_ in self.id_to_keycode:
            keycode = self.id_to_keycode[id_]
            self.Bind(wx.EVT_MENU, keyhandler or self.key_handler, id=id_)
            accels.append((wx.ACCEL_NORMAL, keycode, id_))
        self.SetAcceleratorTable(wx.AcceleratorTable(accels))

        self.msg.SetMaxFontSize(11)
        self.msg.Label = "\n".join(["E" * 80] * 4)
        w, h = self.msg.Size
        self.msg.WindowStyle |= wx.ST_NO_AUTORESIZE
        self.msg.SetMinSize((w, h))
        self.msg.SetSize((w, h))
        self.Sizer.SetSizeHints(self)
        self.Sizer.Layout()
        self.msg.SetLabel(msg.replace("&", "&&"))

        self.pause_continue.Label = lang.getstr("pause")

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)

        if "gtk3" in wx.PlatformInfo:
            # Fix background color not working for panels under GTK3
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        # set position
        self.place(pos)

        if start_timer:
            self.start_timer()

        self.Show()
        if style & wx.PD_APP_MODAL:
            self.MakeModal()

    if "gtk3" in wx.PlatformInfo:
        OnEraseBackground = wx_Panel.__dict__["OnEraseBackground"]

    def MakeModal(self, modal=True):
        # wxPython 3.0 deprecates MakeModal, use a replacement implementation
        # based on http://wxpython.org/Phoenix/docs/html/MigrationGuide.html
        if modal and not hasattr(self, "_disabler"):
            self._disabler = BetterWindowDisabler(self)
        if not modal and hasattr(self, "_disabler"):
            del self._disabler

    def OnClose(self, event):
        self.keepGoing = False
        if hasattr(self, "cancel"):
            self.cancel.Disable()
        self.pause_continue.Disable()
        if not self.timer.IsRunning() and self.allow_close:
            self.Destroy()
        elif self.gauge.GetValue() == self.gauge.GetRange():
            event.Skip()

    def OnDestroy(self, event):
        self.stop_timer()
        del self.timer
        if hasattr(wx.Window, "UnreserveControlId"):
            for id in self.id_to_keycode.keys():
                if id < 0:
                    try:
                        wx.Window.UnreserveControlId(id)
                    except wx.wxAssertionError as exception:
                        print(exception)

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

    def OnTimer(self, event):
        if self.keepGoing:
            if not self.pause_continue.IsEnabled():
                self.set_progress_type(int(not self.progress_type))
            self.pause_continue.Enable()
            if self.paused:
                return
            if self._fpprogress < self.gauge.GetRange():
                self.UpdateProgress(self._fpprogress + self.gauge.GetRange() / 1000.0)
            else:
                self.stop_timer(False)
                self.UpdateProgress(
                    self.gauge.GetRange(), "Finished. You may now close this window."
                )
                self.pause_continue.Disable()
                if hasattr(self, "cancel"):
                    self.cancel.Disable()
        else:
            self.Pulse("Aborting...")
            if not hasattr(self, "delayed_stop"):
                self.delayed_stop = wx.CallLater(3000, self.stop_timer, False)
                wx.CallLater(
                    3000, self.Pulse, "Aborted. You may now close this window."
                )

    def GetValue(self):
        return self._fpprogress

    def SetValue(self, value):
        self.UpdateProgress(value)

    Value = property(GetValue, SetValue)

    def Pulse(self, msg=None):
        if msg and msg != self.msg.Label:
            self.msg.SetLabel(msg)
            self.msg.Wrap(self.msg.ContainingSizer.Size[0])
            self.msg.Refresh()
        if getattr(self, "time2", 0):
            self.time2 = 0
            if not self.time3:
                self.time3 = time()
        if not self.indeterminate:
            self.indeterminate = True
            if hasattr(self, "remaining_time"):
                self.remaining_time.Label = "––:––:––"
            if self.taskbar and not self.paused:
                self.taskbar.set_progress_state(taskbar.TBPF_INDETERMINATE)
        self.gauge.Pulse()
        return self.keepGoing, self.skip

    def Resume(self):
        self.keepGoing = True
        if hasattr(self, "sound_on_off_btn"):
            self.set_sound_on_off_btn_bitmap()
        if hasattr(self, "cancel"):
            self.cancel.Enable()
        if self.paused:
            self.pause_continue_handler()
        else:
            self.pause_continue.Enable()

    def UpdateProgress(self, value, msg=None):
        self.indeterminate = False
        if msg and msg != self.msg.Label:
            self.msg.SetLabel(msg)
            self.msg.Wrap(self.msg.ContainingSizer.Size[0])
            self.msg.Refresh()
        prev_value = self._fpprogress
        if value == prev_value:
            return self.keepGoing, self.skip
        self._fpprogress = value
        value = int(round(value))
        if hasattr(self, "time2"):
            t = time()
            if not self.time2:
                if value < self.gauge.GetValue():
                    # Reset
                    self.time2 = t
                else:
                    # Continue
                    self.time4 += time() - self.time3
                    self.time2 = self.time + self.time4
                    self.time3 = 0
        if (
            getcfg("measurement.play_sound")
            and self._fpprogress < prev_value
            and hasattr(self, "indicator_sound")
            and not self.indicator_sound.is_playing
        ):
            self.indicator_sound.safe_play()
        if isinstance(self.gauge, BetterPyGauge) and self._style & wx.PD_SMOOTH:
            if self._fpprogress >= prev_value:
                update_value = abs(self._fpprogress - prev_value)
                if update_value:
                    # Higher ms = smoother animation, but potentially
                    # increased "lag"
                    ms = 450 + 50 * update_value
                    self.gauge.Update(self._fpprogress, ms)
            else:
                self.gauge.Update(self._fpprogress, 50)
        else:
            self.gauge.SetValue(value)
            if self.taskbar:
                self.taskbar.set_progress_value(value)
        return self.keepGoing, self.skip

    UpdatePulse = Pulse

    def anim_fadein(self):
        bitmaps = ProgressDialog.get_bitmaps(self.progress_type)
        if self.progress_type == 0:
            # Processing
            range = (60, 68)
            loop = True
        elif self.progress_type == 1:
            # Measuring
            range = (0, 9)
            loop = False
        else:
            # Generating test patches
            range = (27, 36)
            loop = True
        self.animbmp.SetBitmaps(bitmaps, range=range, loop=loop)
        if self.progress_type == 1:
            self.animbmp.frame = 4
        wx.CallLater(50, lambda: self and self.IsShown() and self.animbmp.Play(24))

    def sound_fadein(self):
        if getcfg("measurement.play_sound"):
            wx.CallLater(
                50,
                lambda: self
                and self.IsShown()
                and self.sound.safe_fade(self.sound_get_delay(), True),
            )

    def anim_fadeout(self):
        self.animbmp.loop = False
        self.animbmp.range = self.animbmp.range[0], -1

    def sound_fadeout(self):
        if self.sound.is_playing:
            self.sound.safe_stop(self.sound_get_delay())

    def sound_get_delay(self):
        if self.sound is self.processor_sound:
            return 3000
        else:
            return 1500

    def elapsed_time_handler(self, event):
        self.elapsed_time.Label = strftime("%H:%M:%S", gmtime(time() - self.time))
        value = self._fpprogress
        if getattr(self, "time2", 0) and value:
            t = time()
            if self.time2 < t:
                remaining = (t - self.time2) / value * (self.gauge.GetRange() - value)
                if remaining >= 0:
                    self.remaining_time.Label = strftime("%H:%M:%S", gmtime(remaining))

    @staticmethod
    def get_bitmaps(progress_type=0):
        if progress_type in ProgressDialog.bitmaps:
            bitmaps = ProgressDialog.bitmaps[progress_type]
        else:
            bitmaps = ProgressDialog.bitmaps[progress_type] = []
            if progress_type == 0:
                # Animation for processing
                for pth in get_data_path("theme/shutter_anim", r"\.png$") or []:
                    im = wx.Image(pth)
                    if im.IsOk():
                        bitmaps.append(im)
                for pth in get_data_path("theme/jet_anim", r"\.png$") or []:
                    im = wx.Image(pth)
                    if not im.IsOk():
                        continue
                    # Blend red
                    im = im.AdjustChannels(1, 0.25, 0)
                    # Adjust for background
                    im.AdjustMinMax(1.0 / 255 * 0x14)
                    bitmaps.append(im)
                # Needs to be exactly 17 images
                if bitmaps and len(bitmaps) == 17:
                    for i in range(7):
                        bitmaps.extend(bitmaps[9:17])
                    bitmaps.extend(bitmaps[9:13])
                    # Fade in
                    for i, im in enumerate(bitmaps[9:19]):
                        bg = bitmaps[8].ConvertToBitmap()
                        im = im.AdjustChannels(1, 1, 1, i / 10.0)
                        bg.Blend(im.ConvertToBitmap(), 0, 0)
                        bitmaps[i + 9] = bg
                    for i, im in enumerate(bitmaps[:9]):
                        bitmaps[i] = im.ConvertToBitmap()
                    # Normal
                    for i in range(41):
                        im = bitmaps[i + 19].Copy()
                        im.RotateHue(0.05 * (i / 50.0))
                        bitmaps[i + 19] = im.ConvertToBitmap()
                    for i, im in enumerate(bitmaps[60:]):
                        im = im.Copy()
                        im.RotateHue(0.05)
                        bitmaps[i + 60] = im.ConvertToBitmap()
                    # Fade out
                    bitmaps.extend(reversed(bitmaps[:60]))
                else:
                    bitmaps = ProgressDialog.bitmaps[progress_type] = []
            elif progress_type == 1:
                # Animation for measurements
                for i, pth in enumerate(
                    get_data_path("theme/shutter_anim", r"\.png$") or []
                ):
                    if i < 5:
                        bmp = getbitmap(os.path.splitext(pth)[0])
                        bitmaps.insert(0, bmp)
                if bitmaps and len(bitmaps) == 5:
                    bitmaps.extend(reversed(bitmaps[:5]))
                    bitmaps.extend(bitmaps[:5])
            else:
                # Animation for generating test patches
                for pth in get_data_path("theme/patch_anim", r"\.png$") or []:
                    im = wx.Image(pth)
                    if im.IsOk():
                        bitmaps.append(im)
                # Needs to be exactly 9 images
                if bitmaps and len(bitmaps) == 9:
                    for i in range(3):
                        bitmaps.extend(bitmaps[:9])
                    # Fade in
                    for i, im in enumerate(bitmaps[:27]):
                        im = im.AdjustChannels(1, 1, 1, i / 27.0)
                        bitmaps[i] = im.ConvertToBitmap()
                    # Normal
                    for i, im in enumerate(bitmaps[27:]):
                        bitmaps[i + 27] = im.ConvertToBitmap()
                    # Fade out
                    for i in range(3):
                        bitmaps.extend(bitmaps[27:36])
                    for i, bmp in enumerate(bitmaps[36:]):
                        im = bmp.ConvertToImage().AdjustChannels(1, 1, 1, 1 - i / 26.0)
                        bitmaps[i + 36] = im.ConvertToBitmap()
                else:
                    bitmaps = ProgressDialog.bitmaps[progress_type] = []
        return bitmaps

    def key_handler(self, event):
        pass

    def pause_continue_handler(self, event=None):
        if not self.pause_continue.IsShown():
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_continue.Label = lang.getstr("continue")
            if self.taskbar:
                self.taskbar.set_progress_state(taskbar.TBPF_PAUSED)
        else:
            self.pause_continue.Label = lang.getstr("pause")
            if self.taskbar:
                if self.indeterminate:
                    state = taskbar.TBPF_INDETERMINATE
                else:
                    state = taskbar.TBPF_NORMAL
                self.taskbar.set_progress_state(state)
        self.pause_continue.Enable(not event)
        self.Layout()
        if getattr(self, "time2", 0):
            self.time2 = 0
            if not self.time3:
                self.time3 = time()

    def place(self, pos=None):
        """Set position"""
        placed = False
        if pos:
            x, y = pos
        else:
            if self.Parent and self.Parent.IsShownOnScreen():
                self.Center()
                placed = True
            else:
                x = getcfg("position.progress.x")
                y = getcfg("position.progress.y")
        if not placed:
            self.SetSaneGeometry(x, y)

    def play_sound_handler(self, event):
        setcfg(
            "measurement.play_sound", int(not (bool(getcfg("measurement.play_sound"))))
        )
        if getcfg("measurement.play_sound"):
            if (
                self.progress_type in (0, 2)
                and self.keepGoing
                and self._fpprogress < self.gauge.GetRange()
            ):
                self.sound.safe_play()
        else:
            if self.sound.is_playing:
                self.sound.safe_stop()
        self.set_sound_on_off_btn_bitmap()

    def get_sound_on_off_btn_bitmap(self):
        if getcfg("measurement.play_sound"):
            bitmap = geticon(16, "sound_volume_full")
        else:
            bitmap = geticon(16, "sound_off")
        im = bitmap.ConvertToImage()
        im.AdjustMinMax(maxvalue=1.5)
        return im.ConvertToBitmap()

    def set_sound_on_off_btn_bitmap(self):
        bitmap = self.get_sound_on_off_btn_bitmap()
        self.sound_on_off_btn._bitmap = bitmap

    def reset(self):
        self._fpprogress = 0
        self.gauge.SetValue(0)
        self.time = time()
        if hasattr(self, "elapsed_time"):
            self.elapsed_time_handler(None)
        if hasattr(self, "remaining_time"):
            self.time2 = 0
            self.time3 = self.time
            self.time4 = 0
            self.remaining_time.Label = "––:––:––"

    def set_progress_type(self, progress_type):
        if progress_type != self.progress_type:
            if self.progress_type == 0:
                # Processing
                delay = 4000
            elif self.progress_type == 1:
                # Measuring
                delay = 500
            else:
                # Generating test patches
                delay = 2000
            if hasattr(self, "animbmp"):
                self.anim_fadeout()
                wx.CallLater(
                    delay,
                    lambda: self
                    and self.progress_type == progress_type
                    and self.anim_fadein(),
                )
            if hasattr(self, "sound"):
                self.sound_fadeout()
                if progress_type in (0, 2):
                    self.set_sound(progress_type)
                    wx.CallLater(
                        delay,
                        lambda: self
                        and self.progress_type == progress_type
                        and self.sound_fadein(),
                    )
            self.progress_type = progress_type

    def set_sound(self, progress_type=0):
        if progress_type == 0 and hasattr(self, "processor_sound"):
            self.sound = self.processor_sound
        elif hasattr(self, "generator_sound"):
            self.sound = self.generator_sound

    def start_timer(self, ms=75):
        self.timer.Start(ms)
        if isinstance(self.gauge, BetterPyGauge) and not self.gauge.IsRunning():
            self.gauge.Start()
        if hasattr(self, "elapsed_timer"):
            self.elapsed_timer.Start(1000)
        if hasattr(self, "animbmp"):
            self.anim_fadein()
        if hasattr(self, "sound") and self.progress_type in (0, 2):
            self.set_sound(self.progress_type)
            self.sound_fadein()
        if taskbar:
            if self.Parent and self.Parent.IsShownOnScreen():
                taskbarframe = self.Parent
            else:
                taskbarframe = self
            self.taskbar = taskbar.Taskbar(taskbarframe, self.gauge.GetRange())
            self.taskbar.set_progress_state(taskbar.TBPF_INDETERMINATE)

    def stop_timer(self, immediate=True):
        if self.taskbar:
            self.taskbar.set_progress_state(taskbar.TBPF_NOPROGRESS)
        if not self.timer.IsRunning():
            return
        self.timer.Stop()
        if isinstance(self.gauge, BetterPyGauge) and immediate:
            self.gauge.Stop()
        if hasattr(self, "elapsed_timer"):
            self.elapsed_timer.Stop()
        if hasattr(self, "animbmp"):
            if immediate:
                self.animbmp.Stop()
            elif self.animbmp.loop or self.animbmp.range[1] != -1:
                self.anim_fadeout()
        if hasattr(self, "sound"):
            self.sound_fadeout()


class FancyProgressDialog(ProgressDialog):
    def __init__(self, *args, **kwargs):
        kwargs["fancy"] = True
        ProgressDialog.__init__(self, *args, **kwargs)


class SimpleBook(labelbook.FlatBookBase):
    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agwStyle=0,
        name="SimpleBook",
    ):

        labelbook.FlatBookBase.__init__(
            self, parent, id, pos, size, style, agwStyle, name
        )

        self._pages = self.CreateImageContainer()

        # Label book specific initialization
        self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._mainSizer)

        if "gtk3" in wx.PlatformInfo:
            # Fix background color not working for panels under GTK3
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    if "gtk3" in wx.PlatformInfo:
        OnEraseBackground = wx_Panel.__dict__["OnEraseBackground"]

    def CreateImageContainer(self):
        """Creates the image container (LabelContainer) class for L{FlatImageBook}."""

        return labelbook.ImageContainerBase(
            self, wx.ID_ANY, agwStyle=self.GetAGWWindowStyleFlag()
        )


class SimpleTerminal(InvincibleFrame):
    """A simple terminal-like window."""

    def __init__(
        self,
        parent=None,
        id=-1,
        title=appname,
        handler=None,
        keyhandler=None,
        start_timer=True,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        consolestyle=wx.TE_CHARWRAP
        | wx.TE_MULTILINE
        | wx.TE_READONLY
        | wx.VSCROLL
        | wx.NO_BORDER,
        show=True,
        name="simpleterminal",
    ):
        if pos == wx.DefaultPosition:
            pos = getcfg("position.progress.x"), getcfg("position.progress.y")
        if size == wx.DefaultSize:
            size = getcfg("size.progress.w"), getcfg("size.progress.h")
        InvincibleFrame.__init__(
            self, parent, id, title, pos=pos, style=wx.DEFAULT_FRAME_STYLE, name=name
        )

        self.Bind(wx.EVT_CLOSE, self.OnClose, self)
        self.Bind(wx.EVT_MOVE, self.OnMove, self)
        self.timer = BetterTimer(self)
        if handler:
            self.Bind(EVT_BETTERTIMER, handler, self.timer)

        self.panel = wx.Panel(self, -1)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.sizer)
        self.console = wx.TextCtrl(self.panel, -1, "", style=consolestyle)
        self.console.SetBackgroundColour("#272727")
        self.console.SetForegroundColour("#808080")
        if "phoenix" in wx.PlatformInfo:
            kwarg = "faceName"
        else:
            kwarg = "face"
        if sys.platform == "win32":
            font = wx.Font(
                9,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                **{kwarg: "Consolas"},
            )
        elif sys.platform == "darwin":
            font = wx.Font(
                11,
                wx.FONTFAMILY_TELETYPE,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
                **{kwarg: "Monaco"},
            )
        else:
            font = wx.Font(
                11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
            )
        self.console.SetFont(font)
        self.sizer.Add(self.console, 1, flag=wx.ALL | wx.EXPAND, border=0)

        if sys.platform == "win32":
            # Mac: TextCtrls don't receive EVT_KEY_DOWN
            self.console.Bind(
                wx.EVT_KEY_DOWN, keyhandler or self.key_handler, self.console
            )
        else:
            # Windows: EVT_CHAR_HOOK only receives "special" keys e.g. ESC, Tab
            self.Bind(wx.EVT_CHAR_HOOK, keyhandler or self.key_handler)

        # set size
        text_extent = self.console.GetTextExtent(" ")
        vscroll_w = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
        w, h = (text_extent[0] * 80 + vscroll_w + 4, text_extent[1] * 24)
        self.console.SetMinSize((w, h))
        w, h = max(size[0], w), max(size[1], h)
        self.console.SetSize((w, h))
        self.sizer.SetSizeHints(self)
        self.sizer.Layout()

        # set position
        placed = False
        if parent:
            if parent.IsShownOnScreen():
                self.Center()
                placed = True
            else:
                x = pos[0] or parent.GetScreenPosition()[0]
                y = pos[1] or parent.GetScreenPosition()[1]
        else:
            x, y = pos
        if not placed:
            self.SetSaneGeometry(x, y, w, h)

        self.lastmsg = ""
        self.keepGoing = True

        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)

        if start_timer:
            self.start_timer()

        if show:
            self.Show()
            self.console.SetFocus()

    def EndModal(self, returncode=wx.ID_OK):
        return returncode

    def MakeModal(self, makemodal=False):
        pass

    def OnClose(self, event):
        if not self.timer.IsRunning():
            self.Destroy()
        else:
            self.keepGoing = False

    def OnDestroy(self, event):
        self.stop_timer()
        del self.timer

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

    def Pulse(self, msg=""):
        self.lastmsg = msg
        return self.keepGoing, False

    def Resume(self):
        self.keepGoing = True

    def UpdateProgress(self, value, msg=""):
        return self.Pulse(msg)

    def UpdatePulse(self, msg=""):
        return self.Pulse(msg)

    def add_text(self, txt):
        pos = self.console.GetLastPosition()
        if txt.startswith("\r"):
            txt = txt.lstrip("\r")
            numlines = self.console.GetNumberOfLines()
            start = pos - self.console.GetLineLength(numlines - 1)
            self.console.Replace(start, pos, txt)
        else:
            self.console.AppendText(txt)

    def flush(self):
        pass

    def isatty(self):
        return True

    def key_handler(self, event):
        pass

    def start_timer(self, ms=50):
        self.timer.Start(ms)

    def stop_timer(self):
        self.timer.Stop()

    def write(self, txt):
        wx.CallAfter(self.add_text, txt)


class TabButton(PlateButton):
    def __init__(self, *args, **kwargs):
        from DisplayCAL.config import get_default_dpi, getcfg

        self.dpiscale = max(getcfg("app.dpi") / get_default_dpi(), 1.0)
        PlateButton.__init__(self, *args, **kwargs)
        self.Unbind(wx.EVT_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def DoGetBestSize(self):
        """Calculate the best size of the button

        :return: :class:`Size`

        """
        width = 0
        height = 6 * self.dpiscale
        if self.Label:
            # NOTE: Should measure with a GraphicsContext to get right
            #       size, but due to random segfaults on linux special
            #       handling is done in the drawing instead...
            lsize = self.GetFullTextExtent(self.Label)
            width += lsize[0]
            height += lsize[1]

        if self._bmp["enable"] is not None:
            bsize = self._bmp["enable"].Size
            width += bsize[0] + 10 * self.dpiscale
            if height <= bsize[1]:
                height = bsize[1] + 6 * self.dpiscale
            else:
                height += 3 * self.dpiscale
        else:
            width += 10 * self.dpiscale

        if self._menu is not None or self._style & platebtn.PB_STYLE_DROPARROW:
            width += 12 * self.dpiscale

        height += 16 * self.dpiscale  # Tab hilite

        best = wx.Size(int(width), int(height))
        self.CacheBestSize(best)
        return best

    def OnFocus(self, evt):
        """Set the visual focus state if need be"""
        if self._pressed:
            # Skip focus over to next control if it came from another control
            if isinstance(evt, wx.FocusEvent) and isinstance(
                evt.GetWindow(), wx.Control
            ):
                self.Navigate(int(not wx.GetKeyState(wx.WXK_SHIFT))) or evt.Skip()
        elif self._state["cur"] == platebtn.PLATE_NORMAL:
            self._SetState(platebtn.PLATE_HIGHLIGHT)

    def OnKillFocus(self, evt):
        """Set the visual state back to normal when focus is lost
        unless the control is currently in a pressed state.

        """
        if self._pressed:
            self._SetState(platebtn.PLATE_PRESSED)
        else:
            self._SetState(platebtn.PLATE_NORMAL)

    def OnLeftDown(self, evt):
        """Depending on the click position will
        show the popup menu if one has been set.

        """
        pos = evt.GetPosition()
        size = self.GetSize()
        if pos[0] >= size[0] - 16:
            if self._menu is not None:
                self.ShowMenu()
            elif self._style & platebtn.PB_STYLE_DROPARROW:
                event = PlateBtnDropArrowPressed()
                event.SetEventObject(self)
                self.EventHandler.ProcessEvent(event)

        if not self._pressed:
            self.SetFocus()

    def OnLeftUp(self, evt):
        """Post a button event.

        :param evt: :class:`MouseEvent`

        """
        self._SetState(platebtn.PLATE_PRESSED)
        PlateButton.OnLeftUp(self, evt)

    def OnKeyUp(self, evt):
        """Execute a single button press action when the Return key is pressed
        and this control has the focus.

        :param evt: wx.EVT_KEY_UP

        """
        if evt.GetKeyCode() == wx.WXK_SPACE:
            self._SetState(platebtn.PLATE_PRESSED)
            self._PostEvent()
        else:
            evt.Skip()

    def OnPaint(self, evt):
        self.__DrawButton()

    def __DrawBitmap(self, gc):
        """Draw the bitmap if one has been set

        :param GCDC `gc`: :class:`GCDC` to draw with
        :return: x cordinate to draw text at

        """
        if self.IsEnabled():
            bmp = self._bmp["enable"]
        else:
            bmp = self._bmp["disable"]

        xpos = 0
        if bmp is not None and bmp.IsOk():
            bw, bh = bmp.GetSize()
            ypos = (self.GetSize()[1] - bh) // 2
            ypos -= 8  # Tab hilite
            gc.DrawBitmap(bmp, xpos, ypos, bmp.GetMask() is not None)
            return bw + xpos
        else:
            return xpos

    def __DrawHighlight(self, gc, width, height):
        """Draw the main highlight/pressed state

        :param GCDC `gc`: :class:`GCDC` to draw with
        :param int `width`: width of highlight
        :param int `height`: height of highlight

        """
        if (
            (self._state["cur"] == platebtn.PLATE_HIGHLIGHT or self.HasFocus())
            and not self._pressed
            and not get_dialogs(True)
        ):
            if sys.platform == "darwin":
                # Use Sierra-like color scheme
                color = wx.Colour(*gamma_encode(0, 105, 217))
            else:
                color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        elif self._pressed:
            color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)
        else:
            return False

        if self._style & platebtn.PB_STYLE_SQUARE:
            rad = 0
        else:
            rad = (height - 3) / 2

        gc.SetPen(wx.TRANSPARENT_PEN)

        if self._style & platebtn.PB_STYLE_GRADIENT:
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            rgc = gc.GetGraphicsContext()
            brush = rgc.CreateLinearGradientBrush(
                0, 1, 0, height, color, platebtn.AdjustAlpha(color, 55)
            )
            rgc.SetBrush(brush)
        else:
            gc.SetBrush(wx.Brush(color))

        # gc.DrawRoundedRectangle(1, 1, width - 2, height - 2, rad)
        gc.DrawRectangle(
            0, int(height + 10 * self.dpiscale), int(width), int(8 * self.dpiscale)
        )
        return True

    def __DrawButton(self):
        """Draw the button"""
        # TODO using a buffered paintdc on windows with the nobg style
        #      causes lots of weird drawing. So currently the use of a
        #      buffered dc is dissabled for this style.
        if platebtn.PB_STYLE_NOBG & self._style:
            dc = wx.PaintDC(self)
        else:
            dc = wx.AutoBufferedPaintDCFactory(self)
            dc.SetBackground(wx.Brush(self.Parent.BackgroundColour))
            dc.Clear()

        gc = wx.GCDC(dc)

        # Setup
        gc.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
        gc.SetBackgroundMode(wx.TRANSPARENT)

        # Calc Object Positions
        width, height = self.GetSize()
        height -= 16  # Tab hilite
        # Note: Using self.GetTextExtent instead of gc.GetTextExtent seems
        # to fix sporadic segfaults with wxPython Phoenix up to 4.0.0a2
        # under Windows (fixed in 4.0.0a3), but self.GetTextExtent is NOT
        # an equivalent replacement for gc.GetTextExtent.
        tw, th = gc.GetTextExtent(self.Label)
        txt_y = max((height - th) // 2, 1)
        height += 16
        height -= 16 * self.dpiscale  # Tab hilite

        # The background needs some help to look transparent on
        # on Gtk and Windows
        if wx.Platform in ["__WXGTK__", "__WXMSW__"]:
            gc.SetBrush(self.GetBackgroundBrush(gc))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRectangle(0, 0, int(width), int(height))

        gc.SetBrush(wx.TRANSPARENT_BRUSH)

        if (
            self._state["cur"] == platebtn.PLATE_HIGHLIGHT
            or self._pressed
            or self.HasFocus()
        ) and self.IsEnabled():
            hl = self.__DrawHighlight(gc, int(width), int(height))
        else:
            hl = False

        if hl:
            txt_c = self._color["htxt"]
        else:
            if self.IsEnabled():
                txt_c = self.GetForegroundColour()
            else:
                txt_c = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)

        gc.SetTextForeground(txt_c)

        # Draw bitmap and text
        txt_x = self.__DrawBitmap(gc)
        t_x = max(
            (width - tw - (txt_x + 8 * self.dpiscale)) // 2, txt_x + 8 * self.dpiscale
        )
        gc.DrawText(self.Label, int(t_x), int(txt_y))
        # self.__DrawDropArrow(gc, width - 10, (height // 2) - 2)


class TaskBarNotification(wx.Frame):
    """A popup window in a visual style similar to Win10 'toast' notifications.

    It will be shown next to the task bar tray, which makes it a possible
    replacement for 'balloon'-style notifications.
    The viewing/hiding animation is implemented as a fade effect.

    """

    def __init__(
        self,
        icon=None,
        title="Notification",
        text="",
        parent=None,
        pos=wx.DefaultPosition,
        timeout=-1,
    ):
        wx.Frame.__init__(
            self,
            parent,
            -1,
            style=wx.FRAME_NO_TASKBAR | wx.NO_BORDER | wx.STAY_ON_TOP,
            name="TaskBarNotification",
        )
        self.SetTransparent(0)
        border = wx.Panel(self)
        if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
            border.SetDoubleBuffered(True)
        border.BackgroundColour = "#484848"
        border.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        panel = wx.Panel(border)
        if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
            panel.SetDoubleBuffered(True)
        border.Sizer.Add(panel, flag=wx.ALL, border=1)
        panel.Bind(wx.EVT_LEFT_DOWN, lambda event: self.fade("out"))
        panel.BackgroundColour = "#1F1F1F"
        panel.ForegroundColour = "#A5A5A5"
        panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        if icon:
            icon = wx.StaticBitmap(panel, -1, icon)
            icon.Bind(wx.EVT_LEFT_DOWN, lambda event: self.fade("out"))
            panel.Sizer.Add(icon, flag=wx.TOP | wx.BOTTOM | wx.LEFT, border=12)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.Sizer.Add(sizer, flag=wx.ALL, border=12)
        title = wx.StaticText(panel, -1, title)
        title.SetMaxFontSize(11)
        title.Bind(wx.EVT_LEFT_DOWN, lambda event: self.fade("out"))
        title.ForegroundColour = wx.WHITE
        font = title.Font
        font.Weight = wx.BOLD
        title.Font = font
        sizer.Add(title)
        msg = wx.StaticText(panel, -1, text)
        msg.SetMaxFontSize(11)
        msg.Bind(wx.EVT_LEFT_DOWN, lambda event: self.fade("out"))
        sizer.Add(msg)
        close = wx.BitmapButton(
            panel, -1, config.getbitmap("theme/x-2px-12x12-999"), style=wx.NO_BORDER
        )
        close.BackgroundColour = panel.BackgroundColour
        close.Bind(wx.EVT_BUTTON, lambda event: self.fade("out"))
        set_bitmap_labels(close, focus=True)
        panel.Sizer.Add(close, flag=wx.TOP | wx.RIGHT | wx.BOTTOM, border=12)
        border.Sizer.SetSizeHints(self)
        border.Sizer.Layout()
        opos = pos
        display = self.GetDisplay()
        if parent:
            client_area = parent.ClientRect
        else:
            client_area = display.ClientArea
        geometry = display.Geometry
        # Determine tray position so we can show our popup
        # next to it
        if client_area[0] != geometry[0]:
            # Task bar is on the left, tray is in bottom left
            pos = [geometry[0], geometry[1] + geometry[3]]
        elif client_area[0] == geometry[0] and client_area[2] < geometry[2]:
            # Task bar is on the right, tray is in bottom right
            pos = [geometry[0] + geometry[2], geometry[1] + geometry[3]]
        elif client_area[1] != geometry[1]:
            # Task bar is at the top, tray is in top right
            pos = [geometry[0] + geometry[2], geometry[1]]
        elif client_area[1] == geometry[1] and client_area[3] < geometry[3]:
            # Task bar is at the bottom, tray is in bottom right
            pos = [geometry[0] + geometry[2], geometry[1] + geometry[3]]
        else:
            # Task bar is probably set to auto-hide, so we cannot use client
            # area to determine its position. Use mouse position instead.
            mousepos = wx.GetMousePosition()
            if mousepos[0] < (geometry[0] + geometry[2]) / 2.0:
                # Assume task bar is on the left, tray is in bottom left
                pos = [geometry[0], geometry[1] + geometry[3]]
            elif (
                mousepos[0] > (geometry[0] + geometry[2]) / 2.0
                and mousepos[1] < (geometry[1] + geometry[3]) / 2.0
            ):
                # Assume task bar is at the top, tray is in top right
                pos = [geometry[0] + geometry[2], geometry[1]]
            else:
                # Assume task tray is in bottom right
                pos = [geometry[0] + geometry[2], geometry[1] + geometry[3]]
        if pos[0] <= client_area[0]:
            pos[0] = client_area[0] + 12
        if pos[1] <= client_area[1]:
            pos[1] = client_area[1] + 12
        if pos[0] + self.Size[0] >= client_area[0] + client_area[2]:
            pos[0] = client_area[0] + client_area[2] - self.Size[0] - 12
        if pos[1] + self.Size[1] >= client_area[1] + client_area[3]:
            pos[1] = client_area[1] + client_area[3] - self.Size[1] - 12
        for i in (0, 1):
            if opos[i] != -1:
                pos[i] = opos[i]
        self.SetPosition(pos)
        if timeout == -1:
            timeout = 6250
        if timeout:
            self._fadeout_timer = wx.CallLater(
                timeout, lambda: self and self.fade("out")
            )
        if hasattr(panel, "SetFocusIgnoringChildren"):
            panel.SetFocusIgnoringChildren()
        self.Show()
        self.fade()

    def fade(self, direction="in", i=1):
        if getattr(self, "_fade_timer", None) and self._fade_timer.IsRunning():
            self._fade_timer.Stop()
            i = self._fade_timer_i
        if direction != "in":
            if hasattr(self, "_fadeout_timer") and self._fadeout_timer.IsRunning():
                self._fadeout_timer.Stop()
            t = 10 - i
        else:
            t = i
        if not self:
            return
        self.SetTransparent(int(t * 25.5))
        if i < 10:
            self._fade_timer_i = i
            self._fade_timer = wx.CallLater(1, self.fade, direction, i + 1)
        elif direction != "in" and self:
            self.Destroy()


class TooltipWindow(InvincibleFrame):
    """A tooltip-style window"""

    def __init__(
        self,
        parent=None,
        id=-1,
        title=appname,
        msg="",
        cols=1,
        bitmap=None,
        pos=(-1, -1),
        size=(400, -1),
        style=(wx.DEFAULT_FRAME_STYLE | wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT)
        & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX),
        wrap=70,
        use_header=True,
        show=True,
        scrolled=False,
    ):
        scale = getcfg("app.dpi") / get_default_dpi()
        if scale > 1 and size == (400, -1):
            size = size[0] * scale, size[1]
        InvincibleFrame.__init__(self, parent, id, title, pos, size, style)
        self.SetPosition(pos)  # yes, this is needed
        set_icons(self)

        margin = 12

        if scrolled:
            self.panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
            self.panel.SetScrollRate(2, 2)
        else:
            self.panel = wx.Panel(self)
        self.panel.BackgroundColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        self.sizer0 = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.sizer0)
        self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer0.Add(self.sizer1, flag=wx.LEFT | wx.ALL, border=margin)

        if bitmap:
            self.bitmap = wx.StaticBitmap(self.panel, -1, bitmap)
            self.sizer1.Add(self.bitmap)

        self.sizer2 = wx.BoxSizer(wx.VERTICAL)
        self.sizer1.Add(self.sizer2)

        if "<" not in msg and wrap:
            msg = util_str.wrap(msg, wrap)
        msg = msg.splitlines()
        for i, line in enumerate(msg):
            if not line and use_header:
                # Use as header
                header = wx.StaticText(self.panel, -1, "\n".join(msg[: i + 1]))
                self.sizer2.Add(header, flag=wx.LEFT, border=margin)
                msg = msg[i + 1 :]
                break
        self.sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer2.Add(self.sizer3, flag=wx.EXPAND)
        rowspercol = int(math.ceil(len(msg) / float(cols)))
        msgs = []
        while msg:
            msgs.append(msg[:rowspercol])
            msg = msg[rowspercol:]
        for msg in msgs:
            label = "\n".join(msg)
            if "<" in label:
                cls = BetterStaticFancyText
            else:
                cls = wx.StaticText
            # We need to initialize the label with something,
            # so initialize it with with "dummy text",
            # and it will be replaced later on...
            col = cls(self.panel, -1, "dummy text")
            if isinstance(col, wx.Panel):
                col.BackgroundColour = self.panel.BackgroundColour
            if "<" in label and wrap:
                col.maxlen = wrap
            col.SetMaxFontSize()
            maxlinewidth = 0
            tabcount = 0
            for line in msg:
                maxlinewidth = max(col.GetTextExtent(line)[0], maxlinewidth)
                tabcount = max(tabcount, line.count("\t"))
            # GetTextExtent doesn't always figure out correct width for
            # tab char, extra spacing needed
            tabwidth = tabcount * col.GetTextExtent("\t")[0]
            col.Label = label
            if "<" not in label:
                col.MinSize = maxlinewidth + tabwidth + margin * 2, -1
            self.sizer3.Add(col, flag=wx.LEFT, border=margin)

        self.sizer0.SetSizeHints(self)
        self.sizer0.Layout()
        if not pos or pos == (-1, -1):
            self.Center(wx.BOTH)
        elif pos[0] == -1:
            self.Center(wx.HORIZONTAL)
        elif pos[1] == -1:
            self.Center(wx.VERTICAL)
        if show:
            self.Show()
            self.Raise()


class TwoWaySplitter(FourWaySplitter):
    def __init__(self, *args, **kwargs):
        FourWaySplitter.__init__(self, *args, **kwargs)
        self._minimum_pane_size = 0
        self._sashbitmap = getbitmap("theme/sash")
        self._splitsize = (800, 400)
        self._expandedsize = (400, 400)
        self._handcursor = wx.StockCursor(wx.CURSOR_HAND)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        # Redrawing the splitter in FourWaySplitter._RedrawIfHotSensitive
        # which happens if the mouse enters or leaves the splitter causes blank
        # windows managed by the splitter under wxGTK if using GTK3.
        # We are using a custom splitter graphic without 'hot' state, so we can
        # circumvent this.
        self.Unbind(wx.EVT_ENTER_WINDOW)

    def _GetSashSize(self):
        """Used internally."""

        if self.HasFlag(wx.SP_NOSASH):
            return 0

        return self._sashbitmap.GetSize()[0]

    # Recompute layout
    def _SizeWindows(self):
        """Recalculate the layout based on split positions and split fractions.

        :see: L{SetHSplit} and L{SetVSplit} for more information about split fractions.
        """
        win0 = self.GetTopLeft()
        win1 = self.GetTopRight()

        width, height = self.GetSize()
        bar_size = self._GetSashSize()
        border = self._GetBorderSize()

        if self._expanded < 0:
            totw = int(width - bar_size - 2 * border)
            self._splitx = int(
                max((self._fhor * totw) / 10000, self._minimum_pane_size)
            )
            self._splity = int(height)
            rightw = max(totw - self._splitx, 0)
            if win0:
                win0.SetPosition((0, 0))
                win0.SetSize((self._splitx, self._splity))
                win0.Show()
            if win1:
                win1.SetPosition((self._splitx + bar_size, 0))
                win1.SetSize((rightw, self._splity))
                win1.Show()

        else:
            if self._expanded < len(self._windows):
                for ii, win in enumerate(self._windows):
                    if ii == self._expanded:
                        win.SetSize(
                            (
                                int(width - bar_size - 2 * border),
                                int(height - 2 * border),
                            )
                        )
                        win.Show()
                    else:
                        win.Hide()

    # Draw the horizontal split
    def DrawSplitter(self, dc):
        """Actually draws the sashes.

        :param dc: an instance of `wx.DC`.
        """

        backColour = wx.Colour(*[int(v * 0.85) for v in self.BackgroundColour[:3]])
        dc.SetBrush(wx.Brush(backColour, wx.SOLID))
        dc.SetPen(wx.Pen(backColour))
        dc.Clear()

        width, height = self.GetSize()

        if self._expanded > -1:
            splitx = width - self._GetSashSize() - 2 * self._GetBorderSize()
        else:
            splitx = self._splitx

        if self._expanded < 0:
            if splitx <= self._minimum_pane_size:
                self._sashbitmap = getbitmap("theme/sash-right")
            else:
                self._sashbitmap = getbitmap("theme/sash")
        else:
            self._sashbitmap = getbitmap("theme/sash-left")
        sashwidth, sashheight = self._sashbitmap.GetSize()

        dc.DrawRectangle(int(splitx), 0, int(sashwidth), int(height))
        dc.DrawBitmap(
            self._sashbitmap, int(splitx), int(height / 2 - sashheight / 2), True
        )

    def GetExpandedSize(self):
        return self._expandedsize

    # Determine split mode
    def GetMode(self, pt):
        """Determines the split mode for L{FourWaySplitter}.

        :param pt: the point at which the mouse has been clicked, an instance of
         `wx.Point`.

        :return: One of the following 3 split modes:

         ================= ==============================
         Split Mode        Description
         ================= ==============================
         ``wx.HORIZONTAL`` the user has clicked on the horizontal sash
         ``wx.VERTICAL``   The user has clicked on the vertical sash
         ``wx.BOTH``       The user has clicked at the intersection between the 2 sashes
         ================= ==============================

        """

        barSize = self._GetSashSize()
        flag = wx.BOTH

        width, height = self.GetSize()
        if self._expanded > -1:
            splitx = width - self._GetSashSize() - 2 * self._GetBorderSize()
        else:
            splitx = self._splitx

        if pt.x < splitx - _TOLERANCE:
            flag &= ~wx.VERTICAL

        if pt.y < self._splity - _TOLERANCE:
            flag &= ~wx.HORIZONTAL

        if pt.x >= splitx + barSize + _TOLERANCE:
            flag &= ~wx.VERTICAL

        if pt.y >= self._splity + barSize + _TOLERANCE:
            flag &= ~wx.HORIZONTAL

        return flag

    def GetSplitSize(self):
        return self._splitsize

    def OnLeaveWindow(self, event):
        """Handles the ``wx.EVT_LEAVE_WINDOW`` event for L{FourWaySplitter}.

        :param event: a `wx.MouseEvent` event to be processed.
        """

        self.SetCursor(wx.STANDARD_CURSOR)

    def OnLeftDClick(self, event):
        if not self.IsEnabled():
            return

        pt = event.GetPosition()

        if self.GetMode(pt):

            barSize = self._GetSashSize()

            winborder, titlebar = get_platform_window_decoration_size()

            self.Freeze()
            self.SetExpanded(-1 if self._expanded > -1 else 0)
            if self._expanded < 0:
                if self.GetExpandedSize()[0] < self.GetSplitSize()[0]:
                    self._fhor = int(
                        math.ceil(
                            (self.GetExpandedSize()[0] - barSize - winborder * 2)
                            / float(self.GetSplitSize()[0] - barSize - winborder * 2)
                            * 10000
                        )
                    )
                else:
                    self._fhor = int(
                        math.ceil(
                            self._minimum_pane_size
                            / float(self.GetSplitSize()[0] - barSize - winborder * 2)
                            * 10000
                        )
                    )
            self.Thaw()

    # Button being released
    def OnLeftUp(self, event):
        """Handles the ``wx.EVT_LEFT_UP`` event for L{FourWaySplitter}.

        :param event: a `wx.MouseEvent` event to be processed.
        """

        if not self.IsEnabled():
            return

        if self.HasCapture():
            self.ReleaseMouse()

        flgs = self._flags

        self._flags &= ~FLAG_CHANGED
        self._flags &= ~FLAG_PRESSED

        if flgs & FLAG_PRESSED:

            if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
                self.DrawTrackSplitter(int(self._splitx), int(self._splity))
                self.DrawSplitter(wx.ClientDC(self))
                self.AdjustLayout()

            if flgs & FLAG_CHANGED:
                event = FourWaySplitterEvent(
                    wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGED, self
                )
                event.SetSashIdx(self._mode)
                event.SetSashPosition(wx.Point(int(self._splitx), int(self._splity)))
                self.GetEventHandler().ProcessEvent(event)
            else:
                self.OnLeftDClick(event)

        self._mode = NOWHERE

    def OnMotion(self, event):
        """Handles the ``wx.EVT_MOTION`` event for L{FourWaySplitter}.

        :param event: a `wx.MouseEvent` event to be processed.
        """

        if self.HasFlag(wx.SP_NOSASH):
            return

        pt = event.GetPosition()

        # Moving split
        if self._flags & FLAG_PRESSED:

            width, height = self.GetSize()
            barSize = self._GetSashSize()
            border = self._GetBorderSize()

            totw = width - barSize - 2 * border

            if pt.x > totw - _TOLERANCE:
                self._expanded = 0
                self._offx += 1
            elif self._expanded > -1 and pt.x > self._minimum_pane_size:
                self._fhor = int((pt.x - barSize - 2 * border) / float(totw) * 10000)
                self._splitx = (self._fhor * totw) / 10000
                self._offx = pt.x - self._splitx + 1
                self._expanded = -1

            oldsplitx = self._splitx
            oldsplity = self._splity

            if self._mode == wx.BOTH:
                self.MoveSplit(pt.x - self._offx, pt.y - self._offy)

            elif self._mode == wx.VERTICAL:
                self.MoveSplit(pt.x - self._offx, self._splity)

            elif self._mode == wx.HORIZONTAL:
                self.MoveSplit(self._splitx, pt.y - self._offy)

            # Send a changing event
            if not self.DoSendChangingEvent(
                wx.Point(int(self._splitx), int(self._splity))
            ):
                self._splitx = oldsplitx
                self._splity = oldsplity
                return

            if int(oldsplitx) != int(self._splitx) or int(oldsplity) != int(self._splity):
                if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
                    self.DrawTrackSplitter(int(oldsplitx), int(oldsplity))
                    self.DrawTrackSplitter(int(self._splitx), int(self._splity))
                else:
                    self.AdjustLayout()

                self._flags |= FLAG_CHANGED

            self.Refresh()

        # Change cursor based on position
        ff = self.GetMode(pt)

        if self._expanded > -1 and self._splitx <= self._minimum_pane_size:
            self.SetCursor(self._handcursor)

        elif ff == wx.BOTH:
            self.SetCursor(self._sashCursorSIZING)

        elif ff == wx.VERTICAL:
            self.SetCursor(self._sashCursorWE)

        elif ff == wx.HORIZONTAL:
            self.SetCursor(self._sashCursorNS)

        else:
            self.SetCursor(self._handcursor)

        event.Skip()

    def SetExpandedSize(self, size):
        self._expandedsize = size

    def SetMinimumPaneSize(self, size=0):
        self._minimum_pane_size = size

    def SetSplitSize(self, size):
        self._splitsize = size


def get_gradient_panel(parent, label, x=16):
    gradientpanel = BitmapBackgroundPanelText(parent, size=(-1, 31))
    gradientpanel.alpha = 0.75
    gradientpanel.blend = True
    gradientpanel.bordertopcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
    gradientpanel.drawbordertop = True
    gradientpanel.label_x = x
    gradientpanel.textalpha = 0.8
    bitmap = bitmaps.get("gradient_panel")
    if not bitmap:
        bitmap = (
            getbitmap("theme/gradient")
            .GetSubBitmap((0, 1, 8, 15))
            .ConvertToImage()
            .Mirror(False)
            .ConvertToBitmap()
        )
        image = bitmap.ConvertToImage()
        databuffer = image.GetDataBuffer()
        for i, byte in enumerate(databuffer):
            if byte > 0:
                databuffer[i] = int(round(ord(byte) * (255.0 / 223.0)))
        bitmap = image.ConvertToBitmap()
        bitmaps["gradient_panel"] = bitmap
    gradientpanel.SetBitmap(bitmap)
    gradientpanel.SetMaxFontSize(11)
    font = gradientpanel.Font
    font.SetWeight(wx.BOLD)
    gradientpanel.Font = font
    gradientpanel.SetLabel(label)
    return gradientpanel


def get_html_colors(allow_alpha=False):
    """Get background, text, link and visited link colors based on system colors"""
    bgcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
    text = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
    linkcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HOTLIGHT)
    if max(linkcolor[:3]) == 0:
        if sys.platform == "darwin":
            # Use Mavericks-like color scheme
            linkcolor = wx.Colour(44, 93, 205)
        else:
            linkcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
    vlinkcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
    if not allow_alpha:
        for key, value in list(locals().items()):
            if isinstance(value, wx.Colour):
                locals()[key].Set(*value[:3])
    return bgcolor, text, linkcolor, vlinkcolor


def get_widget(win, id_name_label):
    # hasattr, getattr, setattr silently convert attribute names to byte strings,
    # we have to make sure there's no UnicodeEncodeError
    if id_name_label == safe_str(str(id_name_label), "ascii") and hasattr(
        win, id_name_label
    ):
        # Attribute name
        try:
            # Trying to access some attributes of wx widgets may
            # raise an exception
            child = getattr(win, id_name_label)
        except Exception:
            return False
        if is_scripting_allowed(win, child):
            return child
    else:
        # ID or label
        try:
            id_name_label = int(id_name_label)
        except ValueError:
            pass
        for child in win.GetAllChildren():
            if is_scripting_allowed(win, child) and (
                child.Id == id_name_label
                or child.Name == id_name_label
                or child.Label == id_name_label
            ):
                return child


def get_toplevel_window(id_name_label):
    try:
        id_name_label = int(id_name_label)
    except ValueError:
        pass
    for win in reversed(wx.GetTopLevelWindows()):
        if (
            win
            and (
                win.Id == id_name_label
                or win.Name == id_name_label
                or win.Label == id_name_label
            )
            and win.IsShown()
        ):
            return win


def is_scripting_allowed(win, child):
    return (
        child
        and child.TopLevelParent is win
        and child.IsShownOnScreen()
        and isinstance(
            child,
            (
                CustomCheckBox,
                aui.AuiNotebook,
                labelbook.FlatBookBase,
                wx.Control,
                wx.Notebook,
                wx.grid.Grid,
            ),
        )
        and not isinstance(child, (SimpleBook, aui.AuiTabCtrl, wx.StaticBitmap))
    )


_elementtable = {}


def format_ui_element(child, format="plain"):
    if child.TopLevelParent:
        if not hasattr(child.TopLevelParent, "_win2name"):
            child.TopLevelParent._win2name = {}
            for name in child.TopLevelParent.__dict__:
                attr = child.TopLevelParent.__dict__[name]
                if isinstance(attr, wx.Window):
                    child.TopLevelParent._win2name[attr] = name
        name = child.TopLevelParent._win2name.get(child, child.Name)
    else:
        name = child.Name
    items = getattr(child, "Items", [])
    value = None
    if not items and isinstance(child, wx.ListCtrl):
        for row in range(child.GetItemCount()):
            item = []
            for col in range(child.GetColumnCount()):
                item.append(child.GetItem(row, col).GetText())
            items.append(" ".join(item))
        row = child.GetFirstSelected()
        if row != wx.NOT_FOUND:
            value = items[row]
    elif isinstance(child, (aui.AuiNotebook, labelbook.FlatBookBase, wx.Notebook)):
        for page_idx in range(child.GetPageCount()):
            items.append(child.GetPageText(page_idx))
        page_idx = child.GetSelection()
        if page_idx != wx.NOT_FOUND:
            value = child.GetPageText(page_idx)
    cols = []
    if isinstance(child, wx.grid.Grid):
        for col in range(child.GetNumberCols()):
            cols.append(child.GetColLabelValue(col))
    if format != "plain":
        uielement = {
            "class": child.__class__.__name__,
            "name": name,
            "enabled": child.IsEnabled(),
            "id": child.Id,
        }
        if child.Label:
            uielement["label"] = child.Label
        if isinstance(child, (CustomCheckBox, wx.CheckBox, wx.RadioButton)):
            uielement["checked"] = child.GetValue()
        elif hasattr(child, "GetValue") and not isinstance(child, wx.ListCtrl):
            uielement["value"] = child.GetValue()
        elif hasattr(child, "GetStringSelection"):
            uielement["value"] = child.GetStringSelection()
        elif value is not None:
            uielement["value"] = value
        if items:
            uielement["items"] = items
        if cols:
            uielement["cols"] = cols
            uielement["rows"] = child.GetNumberRows()
        return uielement
    return "%s %s %s%s %s%s%s%s" % (
        child.__class__.__name__,
        child.Id,
        sp.list2cmdline([name]),
        (child.Label and " " + demjson.encode(child.Label)),
        "enabled" if child.IsEnabled() else "disabled",
        (
            isinstance(child, (CustomCheckBox, wx.CheckBox, wx.RadioButton))
            and child.GetValue()
            and " checked"
        )
        or (
            getattr(child, "GetValue", "")
            and not isinstance(
                child, (CustomCheckBox, wx.CheckBox, wx.RadioButton, wx.ListCtrl)
            )
            and " value " + demjson.encode(child.GetValue())
        )
        or (
            getattr(child, "GetStringSelection", "")
            and " value " + demjson.encode(child.GetStringSelection())
        )
        or (value is not None and " value " + demjson.encode(value) or ""),
        (
            items
            and " items " + demjson.encode(items).strip("[]").replace('","', '" "')
            or ""
        ),
        (
            cols
            and " rows %s cols %s"
            % (
                child.GetNumberRows(),
                demjson.encode(cols).strip("[]").replace('","', '" "'),
            )
            or ""
        ),
    )


def restore_path_dialog_classes():
    wx.DirDialog = _DirDialog
    wx.FileDialog = _FileDialog


def get_appid_from_window_hierarchy(toplevelwindow):
    if isinstance(toplevelwindow, wx.Frame):
        frame = toplevelwindow
    else:
        frame = get_parent_frame(toplevelwindow)
    base_appid = appname.lower()
    return {
        "lut3dframe": base_appid + "-3dlut-maker",
        "lut_viewer": base_appid + "-curve-viewer",
        "profile_info": base_appid + "-profile-info",
        "scriptingframe": base_appid + "-scripting-client",
        "synthiccframe": base_appid + "-synthprofile",
        "tcgen": base_appid + "-testchart-editor",
        "vrml2x3dframe": base_appid + "-vrml-to-x3d-converter",
    }.get(frame and frame.Name, base_appid)


def set_icons(toplevelwindow):
    """Set icon to that of parent frame"""
    appid = get_appid_from_window_hierarchy(toplevelwindow)
    toplevelwindow.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appid))


def show_result_dialog(result, parent=None, pos=None, confirm=False, wrap=70):
    """Show dialog depending on type of result. Result should be an
    exception type. An appropriate visual representation will be chosen
    whether result is of exception type 'Info', 'Warning' or other error."""
    if result.__class__ is Exception and result.args and result.args[0] == "aborted":
        # Special case - aborted
        msg = lang.getstr("aborted")
    else:
        msg = str(result)
    if not pos:
        pos = (-1, -1)
    if isinstance(result, Info):
        bitmap = geticon(32, "dialog-information")
    elif isinstance(result, (Warning, DownloadError)):
        bitmap = geticon(32, "dialog-warning")
    else:
        bitmap = geticon(32, "dialog-error")
    if isinstance(result, DownloadError):
        confirm = lang.getstr("go_to", result.url)
    if confirm:
        cls = ConfirmDialog
        ok = confirm
    else:
        cls = InfoDialog
        ok = lang.getstr("ok")
    nowrap = wrap is None
    dlg = cls(
        parent,
        pos=pos,
        msg=msg,
        ok=ok,
        bitmap=bitmap,
        log=not isinstance(result, (UnloggedError, UnloggedInfo, UnloggedWarning)),
        nowrap=nowrap,
        wrap=wrap,
    )
    if confirm:
        dlg_ok = dlg.ShowModal() == wx.ID_OK
        dlg.Destroy()
        if dlg_ok and isinstance(result, DownloadError):
            launch_file(result.url)
        return dlg_ok


def test():
    config.initcfg()
    lang.init()

    def key_handler(self, event):
        if event.GetEventType() == wx.EVT_CHAR_HOOK.typeId:
            print(
                "Received EVT_CHAR_HOOK",
                event.GetKeyCode(),
                repr(chr(event.GetKeyCode())),
            )
        elif event.GetEventType() == wx.EVT_KEY_DOWN.typeId:
            print(
                "Received EVT_KEY_DOWN",
                event.GetKeyCode(),
                repr(chr(event.GetKeyCode())),
            )
        elif event.GetEventType() == wx.EVT_MENU.typeId:
            print(
                "Received EVT_MENU",
                self.id_to_keycode.get(event.GetId()),
                repr(chr(self.id_to_keycode.get(event.GetId()))),
            )
        event.Skip()

    ProgressDialog.key_handler = key_handler
    SimpleTerminal.key_handler = key_handler

    app = BaseApp(0)
    style = wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH
    p = ProgressDialog(
        msg="".join(("Test " * 5)),
        maximum=10000,
        style=style,
        pauseable=True,
        fancy="+fancy" not in sys.argv[1:],
        allow_close=True,
    )
    # t = SimpleTerminal(start_timer=False)
    app.MainLoop()


if __name__ == "__main__":
    test()
