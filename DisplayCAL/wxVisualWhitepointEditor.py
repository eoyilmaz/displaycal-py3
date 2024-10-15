# -*- coding: utf-8 -*-
"""
Visual whitepoint editor.

Based on wx.lib.agw.cubecolourdialog 0.4 by Andrea Gavana @ 26 Feb 2012

License: wxPython license
"""

import colorsys
import os
import re
import sys
import threading
from math import atan2, cos, pi, sin, sqrt
from time import sleep

from DisplayCAL import (
    ICCProfile as ICCP,
    localization as lang,
)
from DisplayCAL.config import (
    defaults,
    fs_enc,
    get_argyll_display_number,
    get_default_dpi,
    get_display_name,
    get_icon_bundle,
    getbitmap,
    getcfg,
    geticon,
    initcfg,
    profile_ext,
    setcfg,
)
from DisplayCAL.meta import (
    name as appname,
)
from DisplayCAL.util_list import intlist
from DisplayCAL.util_str import safe_asciize, wrap
from DisplayCAL.worker import (
    Error,
    UnloggedError,
    Warn,
    Worker,
    get_argyll_util,
    show_result_dialog,
)
from DisplayCAL.wxfixes import (
    GenBitmapButton as BitmapButton,
    get_bitmap_disabled,
    get_bitmap_hover,
    get_bitmap_pressed,
    wx,
    wx_Panel,
)
from DisplayCAL.wxwindows import (
    FlatShadedButton,
    HStretchStaticBitmap,
    TaskBarNotification,
)

from wx.lib.agw import aui
from wx.lib.intctrl import IntCtrl

if sys.platform == "darwin":
    from platform import mac_ver

try:
    from DisplayCAL import RealDisplaySizeMM as RDSMM
except ImportError:
    RDSMM = None

# Use non-native mini frames on all platforms
aui.framemanager.AuiManager_UseNativeMiniframes = (
    lambda manager: (manager.GetAGWFlags() & aui.AUI_MGR_USE_NATIVE_MINIFRAMES)
    == aui.AUI_MGR_USE_NATIVE_MINIFRAMES
)

colourAttributes = ["r", "g", "b", "h", "s", "v"]
colourMaxValues = [255, 255, 255, 359, 255, 255]


def rad2deg(x):
    """Transforms radians into degrees.

    :param x: a float representing an angle in radians.
    """

    return 180.0 * x / pi


def deg2rad(x):
    """Transforms degrees into radians.

    :param x: a float representing an angle in degrees.
    """

    return x * pi / 180.0


def s(i) -> int:
    """Scale for HiDPI if necessary"""
    return int(i * max(getcfg("app.dpi") / get_default_dpi(), 1))


def update_patterngenerator(self):
    while self and wx.App.IsMainLoopRunning():
        if self.update_patterngenerator_event.wait(0.05):
            self.update_patterngenerator_event.clear()
            x, y, size = self.patterngenerator_config
            self.patterngenerator.send(
                (
                    self._colour.r / 255.0,
                    self._colour.g / 255.0,
                    self._colour.b / 255.0,
                ),
                (
                    self._bgcolour.r / 255.0,
                    self._bgcolour.g / 255.0,
                    self._bgcolour.b / 255.0,
                ),
                x=x,
                y=y,
                w=size,
                h=size,
            )
        sleep(0.05)


def _show_result_after(*args, **kwargs):
    wx.CallAfter(show_result_dialog, *args, **kwargs)


def _wait_thread(fn, *args, **kwargs):
    # Wait until thread is finished. Yield while waiting.
    thread = threading.Thread(
        target=fn, name="VisualWhitepointEditorMaintenance", args=args, kwargs=kwargs
    )
    thread.start()
    while thread.is_alive():
        wx.Yield()
        sleep(0.05)


def Distance(pt1, pt2):
    """Returns the distance between 2 points.

    :param pt1: an instance of :class:`Point`;
    :param pt2: another instance of :class:`Point`.
    """

    distance = sqrt((pt1.x - pt2.x) ** 2.0 + (pt1.y - pt2.y) ** 2.0)
    return int(round(distance))


def AngleFromPoint(pt, center):
    """Returns the angle between the x-axis and the line connecting the center and
    the point `pt`.

    :param pt: an instance of :class:`Point`;
    :param center: a float value representing the center.
    """

    y = -1 * (pt.y - center.y)
    x = pt.x - center.x
    if x == 0 and y == 0:

        return 0.0

    else:

        return atan2(y, x)


class AuiDarkDockArt(aui.dockart.AuiDefaultDockArt):
    def __init__(self, *args, **kwargs):
        aui.dockart.AuiDefaultDockArt.__init__(self, *args, **kwargs)
        if hasattr(self, "SetDefaultColours"):
            self.SetDefaultColours(wx.Colour(51, 51, 51))
        else:
            self.SetColour(
                aui.dockart.AUI_DOCKART_INACTIVE_CAPTION_COLOUR, wx.Colour(43, 43, 43)
            )
        self.SetColour(
            aui.dockart.AUI_DOCKART_INACTIVE_CAPTION_TEXT_COLOUR,
            wx.Colour(153, 153, 153),
        )
        self.SetColour(aui.dockart.AUI_DOCKART_BORDER_COLOUR, wx.Colour(51, 102, 204))
        if hasattr(aui, "AUI_DOCKART_HINT_WINDOW_COLOUR"):
            self.SetColour(
                aui.dockart.AUI_DOCKART_HINT_WINDOW_COLOUR, wx.Colour(102, 153, 204)
            )
        self.SetMetric(aui.AUI_DOCKART_GRADIENT_TYPE, aui.AUI_GRADIENT_NONE)
        self.SetCustomPaneBitmap(
            geticon(16, "button-pin"), aui.dockart.AUI_BUTTON_CLOSE, False
        )
        self.SetCustomPaneBitmap(
            geticon(16, "button-pin"), aui.dockart.AUI_BUTTON_PIN, False
        )

    def DrawBackground(self, dc, window, orient, rect):
        """Draws a background.

        :param dc: a :class:`DC` device context;
        :param window: an instance of :class:`Window`;
        :param integer `orient`: the gradient (if any) orientation;
        :param Rect `rect`: the background rectangle.
        """

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Colour(51, 51, 51)))
        dc.DrawRectangle(rect.x, rect.y, rect.width, rect.height)

    def DrawPaneButton(self, dc, window, button, button_state, _rect, pane):
        """Draws a pane button in the pane caption area.

        :param dc: a :class:`DC` device context;
        :param window: an instance of :class:`Window`;
        :param integer `button`: the button to be drawn;
        :param integer `button_state`: the pane button state;
        :param Rect `_rect`: the pane caption rectangle;
        :param pane: the pane for which the button is drawn.
        """

        if not pane:
            return

        if button == aui.dockart.AUI_BUTTON_CLOSE:
            if pane.state & aui.dockart.optionActive:
                bmp = self._active_close_bitmap
            else:
                bmp = self._inactive_close_bitmap

        elif button == aui.dockart.AUI_BUTTON_PIN:
            if pane.state & aui.dockart.optionActive:
                bmp = self._active_pin_bitmap
            else:
                bmp = self._inactive_pin_bitmap

        elif button == aui.dockart.AUI_BUTTON_MAXIMIZE_RESTORE:
            if pane.IsMaximized():
                if pane.state & aui.dockart.optionActive:
                    bmp = self._active_restore_bitmap
                else:
                    bmp = self._inactive_restore_bitmap
            else:
                if pane.state & aui.dockart.optionActive:
                    bmp = self._active_maximize_bitmap
                else:
                    bmp = self._inactive_maximize_bitmap

        elif button == aui.dockart.AUI_BUTTON_MINIMIZE:
            if pane.state & aui.dockart.optionActive:
                bmp = self._active_minimize_bitmap
            else:
                bmp = self._inactive_minimize_bitmap

        isVertical = pane.HasCaptionLeft()

        rect = wx.Rect(*_rect)

        if isVertical:
            old_x = rect.x
            rect.x = int(rect.x + (rect.width / 2) - (bmp.GetWidth() / 2))
            rect.width = old_x + rect.width - rect.x - 1
        else:
            old_y = rect.y
            rect.y = int(rect.y + (rect.height / 2) - (bmp.GetHeight() / 2))
            rect.height = old_y + rect.height - rect.y - 1

        if button_state == aui.dockart.AUI_BUTTON_STATE_PRESSED:
            rect.x += 1
            rect.y += 1

        if button_state == aui.dockart.AUI_BUTTON_STATE_HOVER:
            bmp = get_bitmap_hover(bmp)
        elif button_state == aui.dockart.AUI_BUTTON_STATE_PRESSED:
            bmp = get_bitmap_pressed(bmp)

        if isVertical:
            bmp = wx.ImageFromBitmap(bmp).Rotate90(clockwise=False).ConvertToBitmap()

        # draw the button itself
        dc.DrawBitmap(bmp, rect.x, rect.y, True)

    def SetCustomPaneBitmap(self, bmp, button, active, maximize=False):
        """Sets a custom button bitmap for the pane button.

        :param Bitmap `bmp`: the actual bitmap to set;
        :param integer `button`: the button identifier;
        :param bool `active`: whether it is the bitmap for the active button or not;
        :param bool `maximize`: used to distinguish between the maximize and restore bitmaps.
        """

        if button == aui.dockart.AUI_BUTTON_CLOSE:
            if active:
                self._active_close_bitmap = bmp
            else:
                self._inactive_close_bitmap = bmp

            if wx.Platform == "__WXMAC__":
                self._custom_pane_bitmaps = True

        elif button == aui.dockart.AUI_BUTTON_PIN:
            if active:
                self._active_pin_bitmap = bmp
            else:
                self._inactive_pin_bitmap = bmp

        elif button == aui.dockart.AUI_BUTTON_MAXIMIZE_RESTORE:
            if maximize:
                if active:
                    self._active_maximize_bitmap = bmp
                else:
                    self._inactive_maximize_bitmap = bmp
            else:
                if active:
                    self._active_restore_bitmap = bmp
                else:
                    self._inactive_restore_bitmap = bmp

        elif button == aui.dockart.AUI_BUTTON_MINIMIZE:
            if active:
                self._active_minimize_bitmap = bmp
            else:
                self._inactive_minimize_bitmap = bmp


class AuiManager_LRDocking(aui.AuiManager):
    """AuiManager with only left/right docking.

    Also, it is not necessary to hover the drop guide, a drop hint will show
    near the edges regardless.

    """

    def CreateGuideWindows(self):
        self.DestroyGuideWindows()

    def DoDrop(self, docks, panes, target, pt, offset=None):
        """This is an important function. It basically takes a mouse position,
        and determines where the panes new position would be. If the pane is to be
        dropped, it performs the drop operation using the specified dock and pane
        arrays. By specifying copy dock and pane arrays when calling, a "what-if"
        scenario can be performed, giving precise coordinates for drop hints.

        :param docks: a list of :class:`AuiDockInfo` classes;
        :param panes: a list of :class:`AuiPaneInfo` instances;
        :param Point `pt`: a mouse position to check for a drop operation;
        :param Point `offset`: a possible offset from the input point `pt`.
        """
        if offset is None:
            offset = wx.Point(0, 0)

        if target.IsToolbar():
            return self.DoDropToolbar(docks, panes, target, pt, offset)
        else:
            if target.IsFloating():
                allow, hint = self.DoDropFloatingPane(docks, panes, target, pt)
                if allow:
                    return allow, hint
            return self.DoDropNonFloatingPane(docks, panes, target, pt)

    def DoDropNonFloatingPane(self, docks, panes, target, pt):
        """Handles the situation in which the dropped pane is not floating.

        :param docks: a list of :class:`AuiDockInfo` classes;
        :param panes: a list of :class:`AuiPaneInfo` instances;
        :param AuiPaneInfo `target`: the target pane containing the toolbar;
        :param Point `pt`: a mouse position to check for a drop operation.
        """
        # The ONLY change from
        # wx.lib.framemanager.FrameManager.DoDropNonFloatingPane
        # is the removal of top offset by setting new_row_pixels_y to 0.
        # This way, the drag hint is shown when the mouse is near the right
        # frame side irrespective of mouse Y position.

        # screenPt = self._frame.ClientToScreen(pt)
        # clientSize = self._frame.GetClientSize()
        # frameRect = aui.GetInternalFrameRect(self._frame, self._docks)

        drop = self.CopyTarget(target)

        # The result should always be shown
        drop.Show()

        part = self.HitTest(pt.x, pt.y)

        if not part:
            return False, target

        if part.type == aui.AuiDockUIPart.typeDockSizer:

            if len(part.dock.panes) != 1:
                return False, target

            part = self.GetPanePart(part.dock.panes[0].window)
            if not part:
                return False, target

        if not part.pane:
            return False, target

        part = self.GetPanePart(part.pane.window)
        if not part:
            return False, target

        insert_dock_row = False
        insert_row = part.pane.dock_row
        insert_dir = part.pane.dock_direction
        insert_layer = part.pane.dock_layer

        direction = part.pane.dock_direction

        if direction == aui.AUI_DOCK_TOP:
            if part.rect.y <= pt.y < part.rect.y + aui.auiInsertRowPixels:
                insert_dock_row = True

        elif direction == aui.AUI_DOCK_BOTTOM:
            if (
                part.rect.y + part.rect.height - aui.auiInsertRowPixels
                < pt.y
                <= part.rect.y + part.rect.height
            ):
                insert_dock_row = True

        elif direction == aui.AUI_DOCK_LEFT:
            if part.rect.x <= pt.x < part.rect.x + aui.auiInsertRowPixels:
                insert_dock_row = True

        elif direction == aui.AUI_DOCK_RIGHT:
            if (
                part.rect.x + part.rect.width - aui.auiInsertRowPixels
                < pt.x
                <= part.rect.x + part.rect.width
            ):
                insert_dock_row = True

        elif direction == aui.AUI_DOCK_CENTER:

            # "new row pixels" will be set to the default, but
            # must never exceed 20% of the window size
            new_row_pixels_x = s(20)
            new_row_pixels_y = 0

            if new_row_pixels_x > (part.rect.width * 20) / 100:
                new_row_pixels_x = (part.rect.width * 20) / 100

            if new_row_pixels_y > (part.rect.height * 20) / 100:
                new_row_pixels_y = (part.rect.height * 20) / 100

            # determine if the mouse pointer is in a location that
            # will cause a new row to be inserted.  The hot spot positions
            # are along the borders of the center pane

            insert_layer = 0
            insert_dock_row = True
            pr = part.rect

            if pr.x <= pt.x < pr.x + new_row_pixels_x:
                insert_dir = aui.AUI_DOCK_LEFT
            elif pr.y <= pt.y < pr.y + new_row_pixels_y:
                insert_dir = aui.AUI_DOCK_TOP
            elif pr.x + pr.width - new_row_pixels_x <= pt.x < pr.x + pr.width:
                insert_dir = aui.AUI_DOCK_RIGHT
            elif pr.y + pr.height - new_row_pixels_y <= pt.y < pr.y + pr.height:
                insert_dir = aui.AUI_DOCK_BOTTOM
            else:
                return False, target

            insert_row = aui.GetMaxRow(panes, insert_dir, insert_layer) + 1

        if insert_dock_row:

            panes = aui.DoInsertDockRow(panes, insert_dir, insert_layer, insert_row)
            drop.Dock().Direction(insert_dir).Layer(insert_layer).Row(
                insert_row
            ).Position(0)

            return self.ProcessDockResult(target, drop)

        # determine the mouse offset and the pane size, both in the
        # direction of the dock itself, and perpendicular to the dock

        if part.orientation == wx.VERTICAL:

            offset = pt.y - part.rect.y
            size = part.rect.GetHeight()

        else:

            offset = pt.x - part.rect.x
            size = part.rect.GetWidth()

        drop_position = part.pane.dock_pos

        # if we are in the top/left part of the pane,
        # insert the pane before the pane being hovered over
        if offset <= size / 2:

            drop_position = part.pane.dock_pos
            panes = aui.DoInsertPane(
                panes,
                part.pane.dock_direction,
                part.pane.dock_layer,
                part.pane.dock_row,
                part.pane.dock_pos,
            )

        # if we are in the bottom/right part of the pane,
        # insert the pane before the pane being hovered over
        if offset > size / 2:

            drop_position = part.pane.dock_pos + 1
            panes = aui.DoInsertPane(
                panes,
                part.pane.dock_direction,
                part.pane.dock_layer,
                part.pane.dock_row,
                part.pane.dock_pos + 1,
            )

        drop.Dock().Direction(part.dock.dock_direction).Layer(part.dock.dock_layer).Row(
            part.dock.dock_row
        ).Position(drop_position)

        return self.ProcessDockResult(target, drop)


class Colour(object):
    """This is a class similar to :class:`Colour`, which adds Hue, Saturation and
    Brightness capability. It contains also methods to convert RGB triplets
    into HSB triplets and vice-versa.
    """

    def __init__(self, colour):
        """Default class constructor.

        :param colour: a standard :class:`Colour`.
        """

        self.r = colour.Red()
        self.g = colour.Green()
        self.b = colour.Blue()
        self._alpha = colour.Alpha()

        self.ToHSV()

    def ToRGB(self):
        """Converts a HSV triplet into a RGB triplet."""

        maxVal = self.v
        delta = (maxVal * self.s) / 255.0
        minVal = maxVal - delta

        hue = float(self.h)

        if self.h > 300 or self.h <= 60:

            self.r = maxVal

            if self.h > 300:

                self.g = int(round(minVal))
                hue = (hue - 360.0) / 60.0
                self.b = int(round(-(hue * delta - minVal)))

            else:

                self.b = int(round(minVal))
                hue = hue / 60.0
                self.g = int(round(hue * delta + minVal))

        elif 60 < self.h < 180:

            self.g = int(round(maxVal))

            if self.h < 120:

                self.b = int(round(minVal))
                hue = (hue / 60.0 - 2.0) * delta
                self.r = int(round(minVal - hue))

            else:

                self.r = int(round(minVal))
                hue = (hue / 60.0 - 2.0) * delta
                self.b = int(round(minVal + hue))

        else:

            self.b = int(round(maxVal))

            if self.h < 240:

                self.r = int(round(minVal))
                hue = (hue / 60.0 - 4.0) * delta
                self.g = int(round(minVal - hue))

            else:

                self.g = int(round(minVal))
                hue = (hue / 60.0 - 4.0) * delta
                self.r = int(round(minVal + hue))

    def ToHSV(self):
        """Converts a RGB triplet into a HSV triplet."""

        minVal = float(min(self.r, min(self.g, self.b)))
        maxVal = float(max(self.r, max(self.g, self.b)))
        delta = maxVal - minVal

        self.v = int(round(maxVal))

        if abs(delta) < 1e-6:

            self.h = self.s = 0

        else:

            temp = delta / maxVal
            self.s = int(round(temp * 255.0))

            if self.r == int(round(maxVal)):

                temp = float(self.g - self.b) / delta

            elif self.g == int(round(maxVal)):

                temp = 2.0 + (float(self.b - self.r) / delta)

            else:

                temp = 4.0 + (float(self.r - self.g) / delta)

            temp *= 60
            if temp < 0:

                temp += 360

            elif temp >= 360.0:

                temp = 0

            self.h = int(round(temp))

    def GetPyColour(self):
        """Returns the wxPython :class:`Colour` associated with this instance."""

        return wx.Colour(int(self.r), int(self.g), int(self.b), int(self._alpha))


class BasePyControl(wx.PyControl):
    """Base class used to hold common code for the HSB colour wheel and the RGB
    colour cube.
    """

    def __init__(self, parent, bitmap=None):
        """Default class constructor.
        Used internally. Do not call it in your code!

        :param parent: the control parent;
        :param bitmap: the background bitmap for this custom control.
        """

        wx.PyControl.__init__(self, parent, style=wx.NO_BORDER)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        self._bitmap = bitmap

        self._mainFrame = wx.GetTopLevelParent(self)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` for :class:`BasePyControl`.

        :param event: a :class:`PaintEvent` event to be processed.
        """

        dc = wx.AutoBufferedPaintDC(self)

        self.Draw(dc)

    def Draw(self, dc):
        if "gtk3" in wx.PlatformInfo:
            bgcolour = self.Parent.BackgroundColour
        else:
            bgcolour = self.BackgroundColour
        dc.SetBackground(wx.Brush(bgcolour))

        dc.Clear()
        dc.DrawBitmap(self._bitmap, 0, 0, True)

    def OnEraseBackground(self, event):
        """Handles the ``wx.EVT_ERASE_BACKGROUND`` for :class:`BasePyControl`.

        :param event: a :class:`EraseEvent` event to be processed.

        :note: This is intentionally empty to reduce flicker.
        """

        pass

    def DrawMarkers(self, dc=None):
        """Draws the markers on top of the background bitmap.

        :param dc: an instance of :class:`DC`.

        :note: This method must be overridden in derived classes.
        """

        pass

    def DrawLines(self, dc):
        """Draws the lines connecting the markers on top of the background bitmap.

        :param dc: an instance of :class:`DC`.

        :note: This method must be overridden in derived classes.
        """

        pass

    def AcceptsFocusFromKeyboard(self):
        """Can this window be given focus by keyboard navigation? If not, the
        only way to give it focus (provided it accepts it at all) is to click
        it.

        :note: This method always returns ``False`` as we do not accept focus from
         the keyboard.

        :note: Overridden from :class:`PyControl`.
        """

        return False

    def AcceptsFocus(self):
        """Can this window be given focus by mouse click?

        :note: This method always returns ``False`` as we do not accept focus from
         mouse click.

        :note: Overridden from :class:`PyControl`.
        """

        return False

    def OnLeftDown(self, event):
        """Handles the ``wx.EVT_LEFT_DOWN`` for :class:`BasePyControl`.

        :param event: a :class:`MouseEvent` event to be processed.

        :note: This method must be overridden in derived classes.
        """

        pass

    def OnLeftUp(self, event):
        """Handles the ``wx.EVT_LEFT_UP`` for :class:`BasePyControl`.

        :param event: a :class:`MouseEvent` event to be processed.

        :note: This method must be overridden in derived classes.
        """

        pass

    def OnMotion(self, event):
        """Handles the ``wx.EVT_MOTION`` for :class:`BasePyControl`.

        :param event: a :class:`MouseEvent` event to be processed.

        :note: This method must be overridden in derived classes.
        """

        pass

    def OnSize(self, event):
        """Handles the ``wx.EVT_SIZE`` for :class:`BasePyControl`.

        :param event: a :class:`SizeEvent` event to be processed.
        """

        self.Refresh()

    def DoGetBestSize(self):
        """Overridden base class virtual. Determines the best size of the
        control based on the bitmap size.

        :note: Overridden from :class:`PyControl`.
        """

        return wx.Size(self._bitmap.GetWidth(), self._bitmap.GetHeight())


class BasePyButton(BasePyControl):
    def __init__(self, parent, bitmap):
        BasePyControl.__init__(self, parent, bitmap)
        self._bitmap_enabled = bitmap
        self._bitmap_disabled = get_bitmap_disabled(bitmap)
        self._bitmap_hover = get_bitmap_hover(bitmap)
        self._bitmap_pressed = get_bitmap_pressed(bitmap)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)

    def OnLeftDown(self, event):
        if self.Enabled:
            self._bitmap = self._bitmap_pressed
            self.Refresh()
        event.Skip()

    def OnLeftUp(self, event):
        if self.Enabled:
            self._bitmap = self._bitmap_hover
            self.Refresh()
        event.Skip()

    def OnMouseEnter(self, event):
        if self.Enabled:
            if self.HasCapture():
                self._bitmap = self._bitmap_pressed
            else:
                self._bitmap = self._bitmap_hover
            self.Refresh()
        event.Skip()

    def OnMouseLeave(self, event):
        if self.Enabled:
            self._bitmap = self._bitmap_enabled
            self.Refresh()
        event.Skip()

    def Enable(self, enable=True):
        if enable != self.Enabled:
            BasePyControl.Enable(self, enable)
            if self.Enabled:
                self._bitmap = self._bitmap_enabled
            else:
                self._bitmap = self._bitmap_disabled
            self.Refresh()


class HSVWheel(BasePyControl):
    """Implements the drawing, mouse handling and sizing routines for the HSV
    colour wheel.
    """

    def __init__(self, parent, bgcolour):
        """Default class constructor.
        Used internally. Do not call it in your code!

        :param parent: the control parent window.
        """

        BasePyControl.__init__(self, parent, bitmap=getbitmap("theme/colorwheel"))
        self._bitmap = (
            self._bitmap.ConvertToImage()
            .AdjustChannels(0.8, 0.8, 0.8)
            .ConvertToBitmap()
        )
        self._mouseIn = False
        self._buffer = wx.EmptyBitmap(self._bitmap.Width, self._bitmap.Height)
        self._bg = wx.EmptyBitmap(self._bitmap.Width, self._bitmap.Height)
        self._bgdc = wx.MemoryDC(self._bg)
        self.BackgroundColour = bgcolour
        self.Draw(self._bgdc)

    def DrawMarkers(self, dc=None):
        """Draws the markers on top of the background bitmap.

        :param dc: an instance of :class:`DC`.
        """

        if dc is None:
            dc = wx.ClientDC(self)
            if sys.platform != "darwin":
                dc = wx.BufferedDC(dc, self._buffer)

        # Blit the DC with our background to the current DC.
        # Much faster than redrawing the background every time.
        dc.Blit(0, 0, self._bg.Width, self._bg.Height, self._bgdc, 0, 0)

        brightMark = self._mainFrame._currentRect
        darkMarkOuter = wx.Rect(
            brightMark.x - 1,
            brightMark.y - 1,
            brightMark.width + 2,
            brightMark.height + 2,
        )
        darkMarkInner = wx.Rect(
            brightMark.x + 1,
            brightMark.y + 1,
            brightMark.width - 2,
            brightMark.height - 2,
        )
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        for pencolour, rect in (
            (wx.Colour(34, 34, 34), darkMarkOuter),
            (wx.LIGHT_GREY, brightMark),
            (wx.Colour(34, 34, 34), darkMarkInner),
        ):
            dc.SetPen(wx.Pen(pencolour, 1))

            dc.DrawRectangle(rect)

    def OnLeftDown(self, event):
        """Handles the ``wx.EVT_LEFT_DOWN`` for :class:`HSVWheel`.

        :param event: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())
        self._mouseIn = False

        if self.InCircle(point):
            self._mouseIn = True

        if self._mouseIn:
            self.CaptureMouse()
            self.TrackPoint(point)

    def OnLeftUp(self, event):
        """Handles the ``wx.EVT_LEFT_UP`` for :class:`HSVWheel`.

        :param event: a :class:`MouseEvent` event to be processed.
        """

        if self.GetCapture():
            self.ReleaseMouse()
            self._mouseIn = False

    def OnMotion(self, event):
        """Handles the ``wx.EVT_MOTION`` for :class:`HSVWheel`.

        :param event: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())

        if self.GetCapture() and self._mouseIn:
            self.TrackPoint(point)

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` for :class:`BasePyControl`.

        :param event: a :class:`PaintEvent` event to be processed.
        """

        dc = wx.AutoBufferedPaintDC(self)

        if self._mainFrame._initOver:
            self.DrawMarkers(dc)
        else:
            self.Draw(dc)

    def InCircle(self, pt):
        """Returns whether a point is inside the HSV wheel or not.

        :param pt: an instance of :class:`Point`.
        """

        return Distance(pt, self._mainFrame._centre) <= (self._bitmap.Size[0]) / 2

    def TrackPoint(self, pt):
        """Track a mouse event inside the HSV colour wheel.

        :param pt: an instance of :class:`Point`.
        """

        if not self._mouseIn:
            return

        mainFrame = self._mainFrame
        colour = mainFrame._colour

        colour.h = int(round(rad2deg(AngleFromPoint(pt, mainFrame._centre))))
        if colour.h < 0:
            colour.h += 360

        colour.s = int(
            round(
                Distance(pt, mainFrame._centre)
                * 255.0
                / ((self._bitmap.Size[0] - s(12)) / 2)
                * 0.2
            )
        )
        if colour.s > 255:
            colour.s = 255

        mainFrame.CalcRects()
        self.DrawMarkers()
        colour.ToRGB()
        mainFrame.SetSpinVals()

        mainFrame.DrawBright()


class BaseLineCtrl(wx.PyControl):
    """Base class used to hold common code for the Alpha channel control and the
    brightness palette control.
    """

    def __init__(self, parent, size=wx.DefaultSize):
        """Default class constructor.
        Used internally. Do not call it in your code!

        :param parent: the control parent window.
        """

        wx.PyControl.__init__(self, parent, size=size, style=wx.NO_BORDER)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        self._mainFrame = wx.GetTopLevelParent(self)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    def OnEraseBackground(self, event):
        """Handles the ``wx.EVT_ERASE_BACKGROUND`` for :class:`BaseLineCtrl`.

        :param event: a :class:`EraseEvent` event to be processed.

        :note: This is intentionally empty to reduce flicker.
        """

        pass

    def OnLeftDown(self, event):
        """Handles the ``wx.EVT_LEFT_DOWN`` for :class:`BaseLineCtrl`.

        :param event: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())
        theRect = self.GetClientRect()

        if not theRect.Contains(point):
            event.Skip()
            return

        self.CaptureMouse()
        self.TrackPoint(point)

    def OnLeftUp(self, event):
        """Handles the ``wx.EVT_LEFT_UP`` for :class:`BaseLineCtrl`.

        :param event: a :class:`MouseEvent` event to be processed.
        """

        if self.GetCapture():
            self.ReleaseMouse()
        self.Refresh()  # Needed for proper redrawing after click under OS X

    def OnMotion(self, event):
        """Handles the ``wx.EVT_MOTION`` for :class:`BaseLineCtrl`.

        :param event: a :class:`MouseEvent` event to be processed.
        """

        point = wx.Point(event.GetX(), event.GetY())

        if self.GetCapture():
            self.TrackPoint(point)

    def OnSize(self, event):
        """Handles the ``wx.EVT_SIZE`` for :class:`BaseLineCtrl`.

        :param event: a :class:`SizeEvent` event to be processed.
        """

        self.Refresh()

    def BuildRect(self):
        """Internal method."""

        brightRect = wx.Rect(*self.GetClientRect())
        brightRect.x += s(2)
        brightRect.y += s(2)
        brightRect.width -= s(4)
        brightRect.height -= s(4)

        return brightRect

    def AcceptsFocusFromKeyboard(self):
        """Can this window be given focus by keyboard navigation? If not, the
        only way to give it focus (provided it accepts it at all) is to click
        it.

        :note: This method always returns ``False`` as we do not accept focus from
         the keyboard.

        :note: Overridden from :class:`PyControl`.
        """

        return False

    def AcceptsFocus(self):
        """Can this window be given focus by mouse click?

        :note: This method always returns ``False`` as we do not accept focus from
         mouse click.

        :note: Overridden from :class:`PyControl`.
        """

        return False


class BrightCtrl(BaseLineCtrl):
    """Implements the drawing, mouse handling and sizing routines for the brightness
    palette control.
    """

    def __init__(self, parent, colour=None):
        """Default class constructor.
        Used internally. Do not call it in your code!

        :param parent: the control parent window.
        """

        BaseLineCtrl.__init__(self, parent, size=(s(20), s(102)))
        self._colour = colour or self._mainFrame._colour
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_MOUSEWHEEL, self.mousewheel_handler)

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` for :class:`BrightCtrl`.

        :param event: a :class:`PaintEvent` event to be processed.
        """

        dc = wx.AutoBufferedPaintDC(self)

        self.DrawMarkers(dc)

    def DoGetBestSize(self):
        """Overridden base class virtual. Determines the best size of the control.

        :note: Overridden from :class:`PyControl`.
        """

        return wx.Size(s(20), s(102))

    def Draw(self, dc):
        if "gtk3" in wx.PlatformInfo:
            bgcolour = self.Parent.BackgroundColour
        else:
            bgcolour = self.BackgroundColour
        dc.SetBackground(wx.Brush(bgcolour))
        dc.Clear()

        colour = self._colour.GetPyColour()
        brightRect = self.BuildRect()

        target_red = colour.Red()
        target_green = colour.Green()
        target_blue = colour.Blue()

        h, s, v = colorsys.rgb_to_hsv(
            target_red / 255.0, target_green / 255.0, target_blue / 255.0
        )
        v = 0.8
        vstep = v / (brightRect.height - 1)

        for y_pos in range(brightRect.y, brightRect.height + brightRect.y):
            r, g, b = [round(c * 255.0) for c in colorsys.hsv_to_rgb(h, s, v)]
            colour = wx.Colour(int(r), int(g), int(b))
            dc.SetPen(wx.Pen(colour, 1, wx.SOLID))
            dc.DrawRectangle(brightRect.x, y_pos, brightRect.width, 1)
            v = v - vstep

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(brightRect)

    def TrackPoint(self, pt):
        """Tracks a mouse action inside the palette control.

        :param pt: an instance of :class:`Point`.
        """

        brightRect = self.BuildRect()
        d = brightRect.GetBottom() - pt.y
        d *= 255
        d /= brightRect.height
        if d < 0:
            d = 0
        if d > 255:
            d = 255

        mainFrame = self._mainFrame
        colour = self._colour

        colour.v = int(round(d))
        mainFrame.DrawMarkers()

        colour.ToRGB()
        mainFrame.SetSpinVals()

    def DrawMarkers(self, dc=None):
        """Draws square markers used with mouse gestures.

        :param dc: an instance of :class:`DC`.
        """

        if dc is None:
            dc = wx.ClientDC(self)
            if sys.platform != "darwin":
                dc = wx.BufferedDC(dc)
        self.Draw(dc)

        colour = self._colour
        brightRect = self.BuildRect()

        y = int(round(colour.v / 255.0 * (brightRect.height - s(6))))
        y = brightRect.height - s(4) - 1 - y
        h = s(8)
        darkMarkOuter = wx.Rect(brightRect.x - 2, y - 1, brightRect.width + 4, h)
        brightMark = wx.Rect(brightRect.x - 1, y, brightRect.width + 2, h - 2)
        darkMarkInner = wx.Rect(brightRect.x, y + 1, brightRect.width, h - 4)

        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        for pencolour, rect in (
            (wx.Colour(34, 34, 34), darkMarkOuter),
            (wx.LIGHT_GREY, brightMark),
            (wx.Colour(34, 34, 34), darkMarkInner),
        ):
            dc.SetPen(wx.Pen(pencolour, 1))

            dc.DrawRectangle(rect)

    def mousewheel_handler(self, event):
        self._spin(event.GetWheelRotation())

    def _spin(self, direction):
        if direction > 0:
            if self._colour.v < 255:
                self._colour.v += 1
        else:
            if self._colour.v > 0:
                self._colour.v -= 1

        self._mainFrame.DrawMarkers()

        self._colour.ToRGB()
        self._mainFrame.SetSpinVals()


class HSlider(BaseLineCtrl):
    """Implements the drawing, mouse handling and sizing routines for the
    slider control.
    """

    def __init__(self, parent, value=0, minval=0, maxval=100, onchange=None):
        """Default class constructor.
        Used internally. Do not call it in your code!

        :param parent: the control parent window.
        """

        BaseLineCtrl.__init__(self, parent, size=(s(140), s(8)))
        self.value = value
        self.minval = minval
        self.maxval = maxval
        self.onchange = onchange
        self._hasfocus = False
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SET_FOCUS, self.focus_handler)
        self.Bind(wx.EVT_KILL_FOCUS, self.focus_handler)
        self.Bind(wx.EVT_KEY_DOWN, self.key_handler)
        self.Bind(wx.EVT_KEY_UP, self.key_handler)
        self.Bind(wx.EVT_MOUSEWHEEL, self.mousewheel_handler)

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` for :class:`BrightCtrl`.

        :param event: a :class:`PaintEvent` event to be processed.
        """

        dc = wx.AutoBufferedPaintDC(self)

        self.DrawMarkers(dc)

    def DoGetBestSize(self):
        """Overridden base class virtual. Determines the best size of the control.

        :note: Overridden from :class:`PyControl`.
        """

        return wx.Size(s(140), s(8))

    def BuildRect(self):
        brightRect = self.GetClientRect()
        brightRect.y += int((brightRect.height - 8) / 2.0)
        brightRect.height = s(8)

        return brightRect

    def Draw(self, dc):
        if "gtk3" in wx.PlatformInfo:
            bgcolour = self.Parent.BackgroundColour
        else:
            bgcolour = self.BackgroundColour
        dc.SetBackground(wx.Brush(bgcolour))
        dc.Clear()

        brightRect = self.BuildRect()

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Colour(76, 76, 76)))
        dc.DrawRectangle(brightRect)

    def TrackPoint(self, pt):
        """Tracks a mouse action inside the palette control.

        :param pt: an instance of :class:`Point`.
        """

        brightRect = self.BuildRect()
        d = pt.x
        d *= self.maxval
        d /= brightRect.width
        if d < self.minval:
            d = self.minval
        if d > self.maxval:
            d = self.maxval
        self.value = d

        self.DrawMarkers()

        if callable(self.onchange):
            self.onchange()

    def DrawMarkers(self, dc=None):
        """Draws square markers used with mouse gestures.

        :param dc: an instance of :class:`DC`.
        """

        if dc is None:
            dc = wx.ClientDC(self)
            if sys.platform != "darwin":
                dc = wx.BufferedDC(dc)
        self.Draw(dc)

        brightRect = self.BuildRect()

        w = s(8)
        x = int(
            round(
                (self.value - self.minval)
                / float(self.maxval - self.minval)
                * (brightRect.width - w)
            )
        )
        brightMark = wx.Rect(x, brightRect.y, w, brightRect.height)

        dc.SetBrush(wx.Brush(wx.Colour(153, 153, 153)))
        dc.DrawRectangle(brightMark)

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value
        self.DrawMarkers()

    @property
    def Value(self):
        return self.GetValue()

    @Value.setter
    def Value(self, value):
        self.SetValue(value)

    def GetMax(self):
        return self.maxval

    def GetMin(self):
        return self.minval

    def SetMax(self, maxval):
        self.maxval = maxval
        self.Refresh()

    @property
    def Max(self):
        return self.GetMax()

    @Max.setter
    def Max(self, value):
        self.SetMax(value)

    def focus_handler(self, event):
        self._hasfocus = event.GetEventType() == wx.EVT_SET_FOCUS.evtType[0]

    def key_handler(self, event):
        if event.KeyCode in (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT):
            self._spin(1)
        elif event.KeyCode in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT):
            self._spin(-1)
        else:
            event.Skip()

    def mousewheel_handler(self, event):
        self._spin(event.GetWheelRotation())

    def _spin(self, direction):
        inc = (self.maxval - self.minval) / self.ClientSize[0]
        if direction > 0:
            if self.Value < self.maxval:
                self.Value += inc
        else:
            if self.Value > self.minval:
                self.Value -= inc
        self._mainFrame.area_handler()


class NumSpin(wx_Panel):
    def __init__(self, parent, id=-1, *args, **kwargs):
        wx_Panel.__init__(self, parent)
        self.BackgroundColour = "#404040"
        self.Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.numctrl = IntCtrl(self, -1, *args, **kwargs)
        self.numctrl.BackgroundColour = self.BackgroundColour
        self.numctrl.SetColors("#999999", "#CC0000")
        self.numctrl.Bind(wx.EVT_KEY_DOWN, self.key_handler)
        self.numctrl.Bind(wx.EVT_MOUSEWHEEL, self.mousewheel_handler)
        self.Sizer.Add(self.numctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, s(5))
        vsizer = wx.BoxSizer(wx.VERTICAL)
        self.Sizer.Add(vsizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, s(2))
        self.spinup = BasePyButton(self, geticon(10, "spin_up"))
        self.spinup.BackgroundColour = self.BackgroundColour
        self.spinup.Bind(wx.EVT_LEFT_DOWN, self.left_down_handler)
        self.spinup.Bind(wx.EVT_LEFT_UP, self.left_up_handler)
        vsizer.Add(self.spinup, 0, wx.BOTTOM, s(1))
        self.spindn = BasePyButton(self, geticon(10, "spin_down"))
        self.spindn.BackgroundColour = self.BackgroundColour
        self.spindn.Bind(wx.EVT_LEFT_DOWN, self.left_down_handler)
        self.spindn.Bind(wx.EVT_LEFT_UP, self.left_up_handler)
        vsizer.Add(self.spindn, 0, wx.ALIGN_TOP | wx.TOP, s(1))
        self._left_down_count = 0
        self._left_up_count = 0

    def __getattr__(self, name):
        return getattr(self.numctrl, name)

    def is_button_pressed(self, btn):
        return (
            btn.Enabled
            and btn.HasCapture()
            and btn.ClientRect.Contains(btn.ScreenToClient(wx.GetMousePosition()))
        )

    def left_down_handler(self, event):
        self._left_down_count += 1
        if self._capture_mouse(event):
            if event.GetEventObject() is self.spinup:
                self._spin(1, event, bell=False)
            else:
                self._spin(-1, event, bell=False)
        event.Skip()

    def left_up_handler(self, event):
        self._left_up_count += 1
        while self._left_up_count > self._left_down_count:
            # Broken platform (wxMac?) :-(
            # print 'UP', self._left_up_count, 'DN', self._left_down_count
            self.left_down_handler(event)
        obj = event.GetEventObject()
        if obj.HasCapture():
            obj.ReleaseMouse()
        event.Skip()

    def key_handler(self, event):
        if event.KeyCode in (wx.WXK_UP, wx.WXK_NUMPAD_UP):
            self._spin(1, event, bell=False)
        elif event.KeyCode in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
            self._spin(-1, event, bell=False)
        else:
            event.Skip()

    def mousewheel_handler(self, event):
        if event.GetWheelRotation() > 0:
            self._spin(1, event, bell=False)
        else:
            self._spin(-1, event, bell=False)

    def _capture_mouse(self, event):
        obj = event.GetEventObject()
        if obj.Enabled and not obj.HasCapture():
            point = wx.Point(event.GetX(), event.GetY())
            if obj.ClientRect.Contains(point):
                obj.CaptureMouse()
                return True
        return obj.Enabled and obj.HasCapture()

    def _spin(self, inc, event, n=None, delay=500, bell=True):
        current = self.numctrl.GetValue()
        if n is None:
            n = current + inc
        if inc > 0:
            btn = self.spinup
        else:
            btn = self.spindn
        if event or self.is_button_pressed(btn):
            if n == current or (inc > 0 and n < current) or (inc < 0 and n > current):
                # print '!_spin', current, inc, n, delay, bell
                pass
            elif self.numctrl.GetMin() <= n <= self.numctrl.GetMax():
                # print '_spin', current, inc, n, delay, bell
                self.SetValue(n)
            elif bell:
                wx.Bell()
        if btn.Enabled and btn.HasCapture():
            current = self.numctrl.GetValue()
            wx.CallLater(delay, self._spin, inc, None, current + inc, 100)

    def GetValue(self):
        return self.numctrl.GetValue()

    def SetValue(self, value):
        self.numctrl.SetValue(value)
        if self.numctrl.GetMax() <= value:
            self.spinup.HasCapture() and self.spinup.ReleaseMouse()
        if self.numctrl.GetMin() >= value:
            self.spindn.HasCapture() and self.spindn.ReleaseMouse()
        self.spinup.Enable(self.numctrl.GetMax() > value)
        self.spindn.Enable(self.numctrl.GetMin() < value)

    @property
    def Value(self):
        return self.GetValue()

    @Value.setter
    def Value(self, value):
        self.SetValue(value)


class ProfileManager(object):
    """Manages profiles associated with the display that a window is on.

    Clears calibration on the display we're on, and restores it when moved
    to another display or the window is closed.

    """

    managers = []

    def __init__(self, window, geometry=None, profile=None):
        self._display = window.GetDisplay()
        self._lock = threading.Lock()
        self._profiles = {}
        self._srgb_profile = ICCP.ICCProfile.from_named_rgb_space("sRGB")
        self._srgb_profile.setDescription(
            appname + " Visual Whitepoint Editor " "Temporary Profile"
        )
        self._srgb_profile.calculateID()
        self._window = window
        self._window.Bind(wx.EVT_CLOSE, self.window_close_handler)
        self._window.Bind(wx.EVT_MOVE, self.window_move_handler)
        self._window.Bind(wx.EVT_DISPLAY_CHANGED, self.display_changed_handler)
        self._worker = Worker()
        ProfileManager.managers.append(self)
        self.update(False)
        self._profiles_overridden = {}
        if geometry and profile:
            self._profiles_overridden[geometry] = profile

    def _manage_display(self, display_no, geometry):
        # Has to be thread-safe!
        with self._lock:
            try:
                display_profile = ICCP.get_display_profile(display_no)
            except (ICCP.ICCProfileInvalidError, IOError, IndexError) as exception:
                print(
                    "Could not get display profile for display %i" % (display_no + 1),
                    "@ %i, %i, %ix%i:" % geometry,
                    exception,
                )
            else:
                profile = self._profiles_overridden.get(geometry)
                if not profile:
                    profile = display_profile
                if display_profile and display_profile.ID != self._srgb_profile.ID:
                    # Set initial whitepoint according to vcgt
                    # Convert calibration information from embedded WCS
                    # profile (if present) to VideCardGammaType if the
                    # latter is not present
                    if (
                        isinstance(profile.tags.get("MS00"), ICCP.WcsProfilesTagType)
                        and "vcgt" not in profile.tags
                    ):
                        profile.tags["vcgt"] = profile.tags["MS00"].get_vcgt()
                    if isinstance(profile.tags.get("vcgt"), ICCP.VideoCardGammaType):
                        values = profile.tags.vcgt.getNormalizedValues()
                        RGB = []
                        for i in range(3):
                            RGB.append(int(round(values[-1][i] * 255)))
                        (
                            self._window._colour.r,
                            self._window._colour.g,
                            self._window._colour.b,
                        ) = RGB
                        self._window._colour.ToHSV()
                        wx.CallAfter(self._window.DrawAll)
                    # Remember profile, but discard profile filename
                    # (Important - can't re-install profile from same path
                    # where it is installed!)
                    if not self._set_profile_temp_filename(display_profile):
                        return
                    self._profiles[geometry] = display_profile
                    self._install_profile(display_no, self._srgb_profile)

    def _install_profile(self, display_no, profile, wrapup=False):
        # Has to be thread-safe!
        if self._window.patterngenerator:
            return
        dispwin = get_argyll_util("dispwin")
        if not dispwin:
            _show_result_after(Error(lang.getstr("argyll.util.not_found", "dispwin")))
            return
        if not profile.fileName or not os.path.isfile(profile.fileName):
            if not self._set_profile_temp_filename(profile):
                return
            profile.write()
        result = self._worker.exec_cmd(
            dispwin,
            ["-v", "-d%i" % (display_no + 1), "-I", profile.fileName],
            capture_output=True,
            dry_run=False,
        )
        if not result:
            result = UnloggedError("".join(self._worker.errors))
        if isinstance(result, Exception):
            _show_result_after(result, wrap=120)
        if wrapup:
            self._worker.wrapup(False)  # Remove temporary profiles
            ProfileManager.managers.remove(self)

    def _install_profile_locked(self, display_no, profile, wrapup=False):
        # Has to be thread-safe!
        with self._lock:
            self._install_profile(display_no, profile, wrapup)

    def _set_profile_temp_filename(self, profile):
        temp = self._worker.create_tempdir()
        if isinstance(temp, Exception):
            _show_result_after(temp)
            return
        if profile.fileName:
            profile_name = os.path.basename(profile.fileName)
        else:
            profile_name = profile.getDescription() + profile_ext
        if (
            sys.platform in ("win32", "darwin")
            or fs_enc.upper() not in ("UTF8", "UTF-8")
        ) and re.search(r"[^\x20-\x7e]", profile_name):
            profile_name = safe_asciize(profile_name)
        profile.fileName = os.path.join(temp, profile_name)
        return True

    def _stop_timer(self):
        if hasattr(self, "_update_timer") and self._update_timer.IsRunning():
            self._update_timer.Stop()

    def update(self, restore_display_profiles=True):
        """Clear calibration on the current display, and restore it on
        the previous one (if any)

        """
        if restore_display_profiles:
            self.restore_display_profiles()
        display_no = get_argyll_display_number(self._display.Geometry)
        if display_no is not None:
            geometry = self._display.Geometry.Get()
            threading.Thread(
                target=self._manage_display,
                name="VisualWhitepointEditor.DisplayManager[Display %d @ %d, %d, %dx%d]"
                % ((display_no,) + geometry),
                args=(display_no, geometry),
            ).start()
            if not self._window.patterngenerator:
                display_name = get_display_name(display_no, True)
                if display_name:
                    display_name = display_name.replace(
                        "[PRIMARY]", lang.getstr("display.primary")
                    )
                    self._window.SetTitle(
                        display_name + " ‒ " + lang.getstr("whitepoint.visual_editor")
                    )
        else:
            msg = lang.getstr("whitepoint.visual_editor.display_changed.warning")
            print(msg)

    def restore_display_profiles(self, wrapup=False, wait=False):
        """Reinstall memorized display profiles, restore calibration"""
        while self._profiles:
            geometry, profile = self._profiles.popitem()
            display_no = get_argyll_display_number(geometry)
            if display_no is not None:
                thread = threading.Thread(
                    target=self._install_profile_locked,
                    name="VisualWhitepointEditor.ProfileInstallation[Display %d @ %d, %d, %dx%d]"
                    % ((display_no,) + geometry),
                    args=(display_no, profile, wrapup),
                )
                thread.start()
                if wait:
                    thread.join()
            else:
                msg = lang.getstr("whitepoint.visual_editor.display_changed.warning")
                print(msg)

    def display_changed_handler(self, event):
        # Houston, we (may) have a problem! Memorized profile associations may
        # no longer be correct.
        def warn_update():
            msg = lang.getstr("whitepoint.visual_editor.display_changed.warning")
            show_result_dialog(Warn(msg))
            self and self.update()

        wx.CallLater(1000, warn_update)

    def window_close_handler(self, event):
        """Restores profile(s) when the managed window is closed."""
        self._stop_timer()
        self.restore_display_profiles(True, True)
        event.Skip()

    def window_move_handler(self, event):
        """Clear calibration on the current display, and restore it on
        the previous one (if any) when the window is moved from one to
        another display.

        """
        display = self._window.GetDisplay()
        if not self._display or display.Geometry != self._display.Geometry:
            self._display = display
            self._stop_timer()

            def update():
                self._window and self.update()

            self._update_timer = wx.CallLater(50, update)
        event.Skip()


class VisualWhitepointEditor(wx.Frame):
    """This is the VisualWhitepointEditor main class implementation."""

    def __init__(
        self,
        parent,
        colourData=None,
        title=wx.EmptyString,
        pos=wx.DefaultPosition,
        patterngenerator=None,
        geometry=None,
        profile=None,
    ):
        """Default class constructor.

        :param colourData: a standard :class:`ColourData` (as used in :class:`ColourFrame`);
         to hide the alpha channel control or not.
        :param patterngenerator: a patterngenerator object
        :param geometry: the geometry of the display the profile is assigned to
        :param profile: the profile of the display with the given geometry
        """

        self.patterngenerator = patterngenerator
        self.update_patterngenerator_event = threading.Event()

        style = wx.DEFAULT_FRAME_STYLE
        if patterngenerator:
            style &= ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)

        wx.Frame.__init__(
            self,
            parent,
            id=wx.ID_ANY,
            title=title or lang.getstr("whitepoint.visual_editor"),
            pos=pos,
            style=style,
            name="VisualWhitepointEditor",
        )

        if not patterngenerator:
            self._mgr = AuiManager_LRDocking(
                self,
                aui.AUI_MGR_DEFAULT
                | aui.AUI_MGR_LIVE_RESIZE
                | aui.AUI_MGR_SMOOTH_DOCKING,
            )
            self._mgr.SetArtProvider(AuiDarkDockArt())

        self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))

        if colourData:
            self._colourData = colourData
        else:
            self._colourData = wx.ColourData()
            RGB = []
            for attribute in "rgb":
                RGB.append(getcfg("whitepoint.visual_editor." + attribute))
            self._colourData.SetColour(wx.Colour(*RGB))

        self._colour = Colour(self._colourData.GetColour())
        self._bgcolour = Colour(self._colourData.GetColour())
        self._bgcolour.v = getcfg("whitepoint.visual_editor.bg_v")
        self._bgcolour.ToRGB()

        self._inMouse = False
        self._initOver = False
        self._inDrawAll = False

        self.mainPanel = wx_Panel(self, -1)
        self.mainPanel.BackgroundColour = "#333333"
        self.mainPanel.ForegroundColour = "#999999"
        self.bgPanel = wx_Panel(self, -1)
        self.bgPanel.Show(not patterngenerator)

        self.hsvBitmap = HSVWheel(self.mainPanel, self.mainPanel.BackgroundColour)
        self.brightCtrl = BrightCtrl(self.mainPanel)
        self.brightCtrl.BackgroundColour = self.mainPanel.BackgroundColour
        self.bgBrightCtrl = BrightCtrl(self.mainPanel, self._bgcolour)
        self.bgBrightCtrl.BackgroundColour = self.mainPanel.BackgroundColour
        if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
            # No need to enable double buffering under Linux and Mac OS X.
            # Under Windows, enabling double buffering on the panel seems
            # to work best to reduce flicker.
            self.mainPanel.SetDoubleBuffered(True)
            self.bgPanel.SetDoubleBuffered(True)

        self.newColourPanel = wx_Panel(self.bgPanel, style=wx.SIMPLE_BORDER)

        self.redSpin = NumSpin(
            self.mainPanel, -1, min=0, max=255, style=wx.NO_BORDER | wx.ALIGN_RIGHT
        )
        self.greenSpin = NumSpin(
            self.mainPanel, -1, min=0, max=255, style=wx.NO_BORDER | wx.ALIGN_RIGHT
        )
        self.blueSpin = NumSpin(
            self.mainPanel, -1, min=0, max=255, style=wx.NO_BORDER | wx.ALIGN_RIGHT
        )
        self.hueSpin = NumSpin(
            self.mainPanel, -1, min=0, max=359, style=wx.NO_BORDER | wx.ALIGN_RIGHT
        )
        self.saturationSpin = NumSpin(
            self.mainPanel, -1, min=0, max=255, style=wx.NO_BORDER | wx.ALIGN_RIGHT
        )
        self.brightnessSpin = NumSpin(
            self.mainPanel, -1, min=0, max=255, style=wx.NO_BORDER | wx.ALIGN_RIGHT
        )
        self.reset_btn = FlatShadedButton(
            self.mainPanel, -1, label=lang.getstr("reset"), fgcolour="#999999"
        )
        x, y, scale = (
            float(v)
            for v in getcfg("dimensions.measureframe.whitepoint.visual_editor").split(
                ","
            )
        )

        self.area_size_slider = HSlider(
            self.mainPanel, min(scale * 100, 1000), 10, 1000, self.area_handler
        )

        self.display_size_mm = {}
        self.set_area_size_slider_max()
        self.set_default_size()

        self.area_size_slider.BackgroundColour = self.mainPanel.BackgroundColour

        if "gtk3" in wx.PlatformInfo:
            size = (16, 16)
        else:
            size = (-1, -1)
        self.zoomnormalbutton = BitmapButton(
            self.mainPanel,
            -1,
            geticon(16, "zoom-original-outline"),
            size=size,
            style=wx.NO_BORDER,
        )
        self.zoomnormalbutton.BackgroundColour = self.mainPanel.BackgroundColour
        self.Bind(wx.EVT_BUTTON, self.zoomnormal_handler, self.zoomnormalbutton)
        self.zoomnormalbutton.SetToolTipString(
            lang.getstr("measureframe." "zoomnormal")
        )
        self.area_x_slider = HSlider(
            self.mainPanel, int(round(x * 1000)), 0, 1000, self.area_handler
        )
        self.area_x_slider.BackgroundColour = self.mainPanel.BackgroundColour
        self.center_x_button = BitmapButton(
            self.mainPanel,
            -1,
            geticon(16, "window-center-outline"),
            size=size,
            style=wx.NO_BORDER,
        )
        self.center_x_button.BackgroundColour = self.mainPanel.BackgroundColour
        self.Bind(wx.EVT_BUTTON, self.center_x_handler, self.center_x_button)
        self.center_x_button.SetToolTipString(lang.getstr("measureframe.center"))
        self.area_y_slider = HSlider(
            self.mainPanel, int(round(y * 1000)), 0, 1000, self.area_handler
        )
        self.area_y_slider.BackgroundColour = self.mainPanel.BackgroundColour
        self.center_y_button = BitmapButton(
            self.mainPanel,
            -1,
            geticon(16, "window-center-outline"),
            size=size,
            style=wx.NO_BORDER,
        )
        self.center_y_button.BackgroundColour = self.mainPanel.BackgroundColour
        self.Bind(wx.EVT_BUTTON, self.center_y_handler, self.center_y_button)
        self.center_y_button.SetToolTipString(lang.getstr("measureframe.center"))
        self.measure_btn = FlatShadedButton(
            self.mainPanel,
            -1,
            label=lang.getstr("measure"),
            name="visual_whitepoint_editor_measure_btn",
            fgcolour="#999999",
        )
        self.measure_btn.SetDefault()

        self.Bind(wx.EVT_SIZE, self.size_handler)

        self.SetProperties()
        self.DoLayout()

        self.spinCtrls = [
            self.redSpin,
            self.greenSpin,
            self.blueSpin,
            self.hueSpin,
            self.saturationSpin,
            self.brightnessSpin,
        ]

        for spin in self.spinCtrls:
            spin.Bind(wx.EVT_TEXT, self.OnSpinCtrl)

        self.reset_btn.Bind(wx.EVT_BUTTON, self.reset_handler)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_SHOW, self.show_handler)
        self.Bind(wx.EVT_MAXIMIZE, self.maximize_handler)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)

        # Set up panes
        self.mainPanel.Fit()
        mainPanelSize = (self.mainPanel.Size[0], self.mainPanel.Size[1] + s(10))
        if not patterngenerator:
            self._mgr.AddPane(
                self.mainPanel,
                aui.AuiPaneInfo()
                .Name("mainPanel")
                .Fixed()
                .Left()
                .TopDockable(False)
                .BottomDockable(False)
                .PaneBorder(False)
                .CloseButton(False)
                .PinButton(True)
                .MinSize(mainPanelSize),
            )
            self._mgr.AddPane(
                self.bgPanel,
                aui.AuiPaneInfo()
                .Name("bgPanel")
                .CenterPane()
                .CloseButton(False)
                .PaneBorder(False),
            )
            self._mgr.Update()

            self.Bind(aui.EVT_AUI_PANE_CLOSE, self.close_pane_handler)
            self.Bind(aui.EVT_AUI_PANE_FLOATED, self.float_pane_handler)
            self.Bind(aui.EVT_AUI_PANE_DOCKED, self.float_pane_handler)

        # Account for pane titlebar
        self.Sizer.SetSizeHints(self)
        self.Sizer.Layout()
        if not patterngenerator:
            if hasattr(self, "MinClientSize"):
                # wxPython 2.9+
                minClientSize = self.MinClientSize
            else:
                minClientSize = self.WindowToClientSize(self.MinSize)
            w, h = self.newColourPanel.Size
            self.ClientSize = mainPanelSize[0] + w + s(26), max(
                minClientSize[1], h + s(26)
            )
            if sys.platform not in ("win32", "darwin"):
                correction = s(40)
            else:
                correction = 0
            w, h = (int(round(self.default_size)),) * 2
            minClientSize = (
                mainPanelSize[0] + max(minClientSize[1], w + s(26)),
                max(minClientSize[1], h + s(26)) + correction,
            )
            if hasattr(self, "MinClientSize"):
                # wxPython 2.9+
                self.MinClientSize = minClientSize
            else:
                self.MinSize = self.ClientToWindowSize(minClientSize)

        x, y = self.Position
        w, h = self.Size

        if not patterngenerator and (
            self.newColourPanel.Size[0]
            > min(
                self.bgPanel.Size[0], self.GetDisplay().ClientArea[2] - mainPanelSize[0]
            )
            or self.newColourPanel.Size[1]
            > min(self.bgPanel.Size[1], self.GetDisplay().ClientArea[3])
        ):
            w, h = self.GetDisplay().ClientArea[2:]

        self.SetSaneGeometry(x, y, w, h)

        if patterngenerator:
            self.update_patterngenerator_thread = threading.Thread(
                target=update_patterngenerator,
                name="VisualWhitepointEditorPatternGeneratorUpdateThread",
                args=(self,),
            )
            self.update_patterngenerator_thread.start()

        self._pm = ProfileManager(self, geometry, profile)
        self.Bind(wx.EVT_MOVE, self.move_handler)

        wx.CallAfter(self.InitFrame)

        self.keepGoing = True

        self.measure_btn.Bind(wx.EVT_BUTTON, self.measure)

    def SetProperties(self):
        """Sets some initial properties for :class:`VisualWhitepointEditor` (sizes, values)."""
        min_w = self.redSpin.numctrl.GetTextExtent("255")[0] + s(30)
        self.redSpin.SetMinSize((min_w, -1))
        self.greenSpin.SetMinSize((min_w, -1))
        self.blueSpin.SetMinSize((min_w, -1))
        self.hueSpin.SetMinSize((min_w, -1))
        self.saturationSpin.SetMinSize((min_w, -1))
        self.brightnessSpin.SetMinSize((min_w, -1))

    def DoLayout(self):
        """Layouts all the controls in the :class:`VisualWhitepointEditor`."""

        margin = s(12)

        dialogSizer = wx.FlexGridSizer(1, 2, 0, 0)
        dialogSizer.AddGrowableRow(0)
        dialogSizer.AddGrowableCol(1)
        mainSizer = wx.BoxSizer(wx.VERTICAL)

        shadow = HStretchStaticBitmap(
            self.mainPanel, -1, getbitmap("theme/shadow-bordertop")
        )
        mainSizer.Add(shadow, 0, wx.EXPAND)
        label = wx.StaticText(self.mainPanel, -1, lang.getstr("whitepoint"))
        label.SetMaxFontSize(11)
        font = label.Font
        font.SetWeight(wx.BOLD)
        label.Font = font
        mainSizer.Add(label, 0, wx.LEFT, margin)

        hsvGridSizer = wx.GridSizer(2, 3, margin, margin)
        hsvSizer = wx.BoxSizer(wx.HORIZONTAL)

        hsvSizer.Add(self.hsvBitmap, 0, wx.ALL, margin)
        hsvSizer.Add(self.brightCtrl, 0, wx.TOP | wx.BOTTOM, margin + s(5) + 2)
        hsvSizer.Add((margin + s(5), 1))
        hsvSizer.Add(self.bgBrightCtrl, 0, wx.TOP | wx.BOTTOM, margin + s(5) + 2)
        hsvSizer.Add((margin + s(5), 1))
        mainSizer.Add(hsvSizer, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER, margin)

        for channel in ("red", "green", "blue", "hue", "saturation", "brightness"):
            label = wx.StaticText(self.mainPanel, -1, lang.getstr(channel))
            label.SetMaxFontSize(11)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(label)
            sizer.Add(getattr(self, channel + "Spin"), 0, wx.TOP | wx.EXPAND, s(4))
            hsvGridSizer.Add(sizer, 0, wx.EXPAND)
        mainSizer.Add(hsvGridSizer, 0, wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER, margin)
        mainSizer.Add(self.reset_btn, 0, wx.ALL | wx.ALIGN_CENTER, margin)

        shadow = HStretchStaticBitmap(
            self.mainPanel, -1, getbitmap("theme/shadow-bordertop")
        )
        mainSizer.Add(shadow, 0, wx.EXPAND, margin)
        area_slider_label = wx.StaticText(
            self.mainPanel, -1, lang.getstr("measureframe.title")
        )
        area_slider_label.SetMaxFontSize(11)
        font = area_slider_label.Font
        font.SetWeight(wx.BOLD)
        area_slider_label.Font = font
        mainSizer.Add(area_slider_label, 0, wx.LEFT | wx.BOTTOM, margin)
        if "gtk3" in wx.PlatformInfo:
            vmargin = margin
        else:
            vmargin = s(6)
        slider_sizer = wx.FlexGridSizer(3, 3, vmargin, margin)
        slider_sizer.AddGrowableCol(1)
        mainSizer.Add(slider_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, margin)
        area_size_label = wx.StaticText(self.mainPanel, -1, lang.getstr("size"))
        area_size_label.SetMaxFontSize(11)
        slider_sizer.Add(area_size_label, 0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(self.area_size_slider, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        slider_sizer.Add(self.zoomnormalbutton, 0, wx.ALIGN_CENTER_VERTICAL)
        area_x_label = wx.StaticText(self.mainPanel, -1, "X")
        area_x_label.SetMaxFontSize(11)
        slider_sizer.Add(area_x_label, 0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(self.area_x_slider, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        slider_sizer.Add(self.center_x_button, 0, wx.ALIGN_CENTER_VERTICAL)
        area_y_label = wx.StaticText(self.mainPanel, -1, "Y")
        area_y_label.SetMaxFontSize(11)
        slider_sizer.Add(area_y_label, 0, wx.ALIGN_CENTER_VERTICAL)
        slider_sizer.Add(self.area_y_slider, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
        slider_sizer.Add(self.center_y_button, 0, wx.ALIGN_CENTER_VERTICAL)
        mainSizer.Add(self.measure_btn, 0, wx.ALL | wx.ALIGN_CENTER, margin)

        self.mainPanel.SetAutoLayout(True)
        self.mainPanel.SetSizer(mainSizer)
        mainSizer.Fit(self.mainPanel)
        mainSizer.SetSizeHints(self.mainPanel)

        dialogSizer.Add(self.mainPanel, 0, wx.EXPAND)
        if self.bgPanel.IsShown():
            dialogSizer.Add(self.bgPanel, 1, wx.EXPAND, 0)
        self.SetAutoLayout(True)
        self.SetSizer(dialogSizer)
        dialogSizer.Fit(self)
        dialogSizer.SetSizeHints(self)
        self.Layout()

        self.mainSizer = mainSizer
        self.dialogSizer = dialogSizer

    def InitFrame(self):
        """Initialize the :class:`VisualWhitepointEditor`."""

        hsvRect = self.hsvBitmap.GetClientRect()
        self._centre = wx.Point(
            int(hsvRect.x + hsvRect.width / 2), int(hsvRect.y + hsvRect.height / 2)
        )

        self.CalcRects()

        self.SetSpinVals()

        self._initOver = True
        wx.CallAfter(self.Refresh)

    def show_handler(self, event):
        if (
            not self.patterngenerator
            and getattr(event, "IsShown", getattr(event, "GetShow", bool))()
            and sys.platform == "darwin"
            and intlist(mac_ver()[0].split(".")) >= [10, 10]
        ):
            # Under Yosemite and up, if users use the default titlebar zoom
            # button to go fullscreen, they will be left with a black screen
            # after the window has been closed (shortcoming of wxMac).
            # It is possible to switch back to normal view by alt-tabbing,
            # but users need to be made aware of it.
            wx.CallAfter(
                self.notify,
                wrap(lang.getstr("fullscreen.osx.warning"), 80),
                icon=geticon(32, "dialog-warning"),
                timeout=0,
            )
        event.Skip()

    def CalcRects(self):
        """Calculates the brightness control user-selected rect."""

        RECT_WIDTH = s(5)

        pt = self.PtFromAngle(self._colour.h, self._colour.s, self._centre)
        self._currentRect = wx.Rect(
            pt.x - RECT_WIDTH, pt.y - RECT_WIDTH, 2 * RECT_WIDTH, 2 * RECT_WIDTH
        )

    def DrawMarkers(self, dc=None):
        """Draws the markers for all the controls.

        :param dc: an instance of :class:`DC`. If `dc` is ``None``, a :class:`ClientDC` is
         created on the fly.
        """

        self.hsvBitmap.DrawMarkers(dc)
        self.brightCtrl.DrawMarkers(dc)
        self.bgBrightCtrl.DrawMarkers(dc)

    def DrawHSB(self):
        """Refreshes the HSB colour wheel."""

        self.hsvBitmap.Refresh()

    def DrawBright(self):
        """Refreshes the brightness control."""

        self.brightCtrl.Refresh()
        self.bgBrightCtrl.Refresh()

    def SetSpinVals(self):
        """Sets the values for all the spin controls."""

        self.redSpin.SetValue(self._colour.r)
        self.greenSpin.SetValue(self._colour.g)
        self.blueSpin.SetValue(self._colour.b)

        self.hueSpin.SetValue(self._colour.h)
        self.saturationSpin.SetValue(self._colour.s)
        self.brightnessSpin.SetValue(self._colour.v)

        self.SetPanelColours()
        self.update_patterngenerator()

    def update_patterngenerator(self):
        if self.patterngenerator:
            size = min(
                (
                    self.area_size_slider.GetValue()
                    / float(
                        self.area_size_slider.GetMax() - self.area_size_slider.GetMin()
                    )
                ),
                1,
            )
            x = max(
                self.area_x_slider.GetValue()
                / float(self.area_x_slider.GetMax())
                * (1 - size),
                0,
            )
            y = max(
                self.area_y_slider.GetValue()
                / float(self.area_y_slider.GetMax())
                * (1 - size),
                0,
            )
            self.patterngenerator_config = x, y, size
            self.update_patterngenerator_event.set()

    def SetPanelColours(self):
        """Assigns colours to the colour panels."""

        self.newColourPanel.BackgroundColour = self._colour.GetPyColour()
        self._bgcolour.h = self._colour.h
        self._bgcolour.s = self._colour.s
        self._bgcolour.ToRGB()
        self.bgPanel.BackgroundColour = self._bgcolour.GetPyColour()
        self.bgPanel.Refresh()

    def OnCloseWindow(self, event):
        """Handles the ``wx.EVT_CLOSE`` event for :class:`VisualWhitepointEditor`.

        :param event: a :class:`CloseEvent` event to be processed.
        """

        if self.IsFullScreen():
            self.ShowFullScreen(False)
        event.Skip()

    def OnKeyDown(self, event):
        """Handles the ``wx.EVT_CHAR_HOOK`` event for :class:`VisualWhitepointEditor`.

        :param event: a :class:`KeyEvent` event to be processed.
        """

        if event.GetKeyCode() == wx.WXK_ESCAPE:
            if self.IsFullScreen():
                self.ShowFullScreen(False)
                self.Restore()
            else:
                self.Close()
        # elif event.KeyCode in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP,
        # wx.WXK_DOWN):
        # self._colour.h += {wx.WXK_LEFT: 1,
        # wx.WXK_RIGHT: -1,
        # wx.WXK_UP: 0,
        # wx.WXK_DOWN: 0}[event.KeyCode]
        # if self._colour.h > 359:
        # self._colour.h = 0
        # elif self._colour.h < 0:
        # self._colour.h = 359
        # self._colour.s += {wx.WXK_LEFT: 0,
        # wx.WXK_RIGHT: 0,
        # wx.WXK_UP: 1,
        # wx.WXK_DOWN: -1}[event.KeyCode]
        # if self._colour.s > 255:
        # self._colour.s = 255
        # elif self._colour.s < 0:
        # self._colour.s = 0
        # print self._colour.h, self._colour.s
        # self._colour.ToRGB()
        # self.DrawAll()
        else:
            event.Skip()

    def PtFromAngle(self, angle, sat, center):
        """Given the angle with respect to the x-axis, returns the point based on
        the saturation value.

        :param angle: a float representing an angle;
        :param sat: a float representing the colour saturation value;
        :param center: a float value representing the center.
        """

        angle = deg2rad(angle)
        sat = min(
            sat * ((self.hsvBitmap._bitmap.Size[0] - s(12)) / 2) / 51.0,
            ((self.hsvBitmap._bitmap.Size[0] - s(12)) / 2),
        )

        x = sat * cos(angle)
        y = sat * sin(angle)

        pt = wx.Point(int(round(x)), -int(round(y)))
        pt.x += center.x
        pt.y += center.y

        return pt

    def OnSpinCtrl(self, event):
        """Handles the ``wx.EVT_SPINCTRL`` event for RGB and HSB colours.

        :param event: a :class:`SpinEvent` event to be processed.
        """

        obj = event.GetEventObject().Parent
        position = self.spinCtrls.index(obj)
        colourVal = event.GetString()
        try:
            colourVal = int(colourVal)
        except Exception:
            wx.Bell()
            return

        attribute, maxVal = colourAttributes[position], colourMaxValues[position]

        self.AssignColourValue(attribute, colourVal, maxVal, position)

    def AssignColourValue(self, attribute, colourVal, maxVal, position):
        """Common code to handle spin control changes."""

        originalVal = getattr(self._colour, attribute)
        if colourVal != originalVal and self._initOver:

            if colourVal < 0:
                colourVal = 0
            if colourVal > maxVal:
                colourVal = maxVal

            setattr(self._colour, attribute, colourVal)
            if position < 3:
                self._colour.ToHSV()
            else:
                self._colour.ToRGB()

            self.DrawAll()

    def DrawAll(self):
        """Draws all the custom controls after a colour change."""

        if self._initOver and not self._inDrawAll:
            self._inDrawAll = True

            self.hsvBitmap.DrawMarkers()

            self.brightCtrl.DrawMarkers()

            self.CalcRects()

            self.DrawHSB()
            self.DrawBright()

            self.SetSpinVals()
            self._inDrawAll = False

    def GetColourData(self):
        """Returns a wxPython compatible :class:`ColourData`."""

        self._colourData.SetColour(self._colour.GetPyColour())
        return self._colourData

    def GetRGBAColour(self):
        """Returns a 4-elements tuple of red, green, blue, alpha components."""

        return (self._colour.r, self._colour.g, self._colour.b, self._colour._alpha)

    def GetHSVAColour(self):
        """Returns a 4-elements tuple of hue, saturation, brightness, alpha components."""

        return (self._colour.h, self._colour.s, self._colour.v, self._colour._alpha)

    def EndModal(self, returncode=wx.ID_OK):
        return returncode

    def MakeModal(self, makemodal=False):
        pass

    def Pulse(self, msg=""):
        return self.keepGoing, False

    def Resume(self):
        self.keepGoing = True

    def UpdateProgress(self, value=None, msg=""):
        return self.Pulse(msg)

    def UpdatePulse(self, msg=""):
        return self.Pulse(msg)

    def area_handler(self, event=None):
        scale = self.area_size_slider.Value / 100.0
        x = self.area_x_slider.Value / 1000.0
        y = self.area_y_slider.Value / 1000.0
        w, h = (int(round(self.default_size * scale)),) * 2
        self.bgPanel.MinSize = -1, -1
        self.newColourPanel.Size = w, h
        self.bgPanel.MinSize = w + s(24), h + s(24)
        bg_w, bg_h = (float(v) for v in self.bgPanel.Size)
        self.newColourPanel.Position = (int((bg_w - (w)) * x)), int(((bg_h - (h)) * y))
        if event:
            event.Skip()
        if event and event.GetEventType() == wx.EVT_SIZE.evtType[0]:
            wx.CallAfter(self.area_handler)
        else:
            self.bgPanel.Refresh()
        self.update_patterngenerator()

    def center_x_handler(self, event):
        self.area_x_slider.SetValue(500)
        self.area_handler()

    def center_y_handler(self, event):
        self.area_y_slider.SetValue(500)
        self.area_handler()

    def close_pane_handler(self, event):
        event.Veto()  # Prevent closing of pane
        self.dock_pane()

    def dock_pane(self):
        self._mgr.GetPane("mainPanel").Dock().CloseButton(False)
        self._mgr.Update()
        self.mainPanel.Refresh()
        self.area_handler()

    def float_pane_handler(self, event):
        if event.GetEventType() == aui.EVT_AUI_PANE_FLOATED.evtType[0]:
            pos = [
                self.Position[i]
                + (self.Size[i] - self.ClientSize[i]) / {0: 2, 1: 1}[i]
                + s(10)
                for i in (0, 1)
            ]
            pos[0] += self.mainPanel.Position[0]
            pos[1] -= (self.Size[0] - self.ClientSize[0]) / 2
            self._mgr.GetPane("mainPanel").FloatingPosition(pos).CloseButton(True)
            wx.CallAfter(self.area_handler)
        else:
            wx.CallAfter(self.dock_pane)

    def flush(self):
        pass

    def maximize_handler(self, event):
        """Handles maximize and fullscreen events"""
        # print '_isfullscreen?', getattr(self, "_isfullscreen", False)
        if not getattr(self, "_isfullscreen", False):
            self._isfullscreen = True
            # print 'Setting fullscreen...'
            self.ShowFullScreen(True)
            # print '...done setting fullscreen.'
            wx.CallAfter(self.notify, lang.getstr("fullscreen.message"))

    def move_handler(self, event):
        event.Skip()
        display = self.GetDisplay()
        if not self._pm._display or display.Geometry != self._pm._display.Geometry:
            self.set_area_size_slider_max()
            self.set_default_size()
            self.area_handler()

    def measure(self, event):
        if (
            not self.Parent
            or not hasattr(self.Parent, "ambient_measure_handler")
            or not self.Parent.worker.displays
            or not self.Parent.worker.instruments
        ):
            wx.Bell()
            return
        self.measure_btn.Disable()
        self.setcfg()
        self.Parent.ambient_measure_handler(event)

    def notify(self, msg, title=None, icon=None, timeout=-1):
        # Notification needs to have this frame as toplevel parent so key events
        # bubble to parent
        # print 'Showing fullscreen notification'
        if getattr(self, "notification", None):
            self.notification.fade("out")
        self.notification = TaskBarNotification(
            icon or geticon(32, "dialog-information"),
            title or self.Title,
            msg,
            self.bgPanel,
            (-1, s(32)),
            timeout,
        )
        self.notification.Center(wx.HORIZONTAL)

    def size_handler(self, event):
        if getattr(self, "_isfullscreen", False):
            if getattr(self, "notification", None):
                # print 'Fading out notification'
                self.notification.fade("out")
        wx.CallAfter(self._check_fullscreen)
        self.area_handler(event)

    def _check_fullscreen(self):
        # print '_isfullscreen?', getattr(self, "_isfullscreen", False)
        if getattr(self, "_isfullscreen", False):
            self._isfullscreen = self.IsFullScreen()
            # print 'IsFullScreen()?', self._isfullscreen

    def start_timer(self, ms=50):
        pass

    def stop_timer(self):
        pass

    def reset_handler(self, event):
        RGB = []
        for attribute in "rgb":
            RGB.append(defaults["whitepoint.visual_editor." + attribute])
        self._colourData.SetColour(wx.Colour(*RGB))
        self._colour.r, self._colour.g, self._colour.b = self._colourData.GetColour()[
            :3
        ]
        self._colour.ToHSV()
        self._bgcolour.v = defaults["whitepoint.visual_editor.bg_v"]
        self.DrawAll()

    def set_area_size_slider_max(self):
        # Set max value according to display size
        maxv = 1000
        if RDSMM:
            geometry = self.GetDisplay().Geometry.Get()
            display_no = get_argyll_display_number(geometry)
            if display_no is not None:
                size_mm = RDSMM.RealDisplaySizeMM(display_no)
                if 0 not in size_mm:
                    self.display_size_mm[geometry] = [float(v) for v in size_mm]
                    maxv = int(round(max(size_mm) / 100.0 * 100))
        if maxv > 100:
            self.area_size_slider.SetMax(maxv)
            if self.area_size_slider.GetValue() > self.area_size_slider.GetMax():
                self.area_size_slider.SetValue(maxv)

    def set_default_size(self):
        geometry = self.GetDisplay().Geometry.Get()
        size_mm = self.display_size_mm.get(geometry)
        if size_mm:
            px_per_mm = max(geometry[2] / size_mm[0], geometry[3] / size_mm[1])
            self.default_size = px_per_mm * 100
        else:
            self.default_size = 300

    def setcfg(self):
        for attribute in "rgb":
            value = getattr(self._colour, attribute)
            setcfg("whitepoint.visual_editor." + attribute, value)
        setcfg("whitepoint.visual_editor.bg_v", self._bgcolour.v)
        x, y = (
            ctrl.Value / 1000.0 for ctrl in (self.area_x_slider, self.area_y_slider)
        )
        scale = self.area_size_slider.Value / 100.0
        setcfg(
            "dimensions.measureframe.whitepoint.visual_editor",
            "%f,%f,%f" % (x, y, scale),
        )

    def write(self, txt):
        pass

    def zoomnormal_handler(self, event):
        scale = float(
            defaults["dimensions.measureframe.whitepoint.visual_editor"].split(",")[2]
        )
        self.area_size_slider.SetValue(int(round(scale * 100)))
        self.area_handler()


if __name__ == "__main__":
    from DisplayCAL.wxwindows import BaseApp

    initcfg()
    lang.init()
    app = BaseApp(0)
    worker = Worker()
    worker.enumerate_displays_and_ports(check_lut_access=False, enumerate_ports=False)
    app.TopWindow = VisualWhitepointEditor(None)
    app.TopWindow.Show()
    app.MainLoop()
