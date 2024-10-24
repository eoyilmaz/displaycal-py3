# ------------------------------------------------------------------------------------ #
# GRADIENTBUTTON wxPython IMPLEMENTATION
#
# Andrea Gavana, @ 07 October 2008
# Latest Revision: 27 Dec 2012, 21.00 GMT
#
#
# TODO List
#
# 1) Anything to do?
#
#
# For all kind of problems, requests of enhancements and bug reports,
# please write to me at:
#
# andrea.gavana@gmail.com
# andrea.gavana@maerskoil.com
#
# Or, obviously, to the wxPython mailing list!!!
#
# Tags:        phoenix-port, unittest, documented, py3-port
#
# End Of Comments
# ------------------------------------------------------------------------------------ #

"""`GradientButton` mimics Windows CE mobile gradient buttons.

Description
===========

:class:`GradientButton` is another custom-drawn button class which mimics Windows CE
mobile gradient buttons, using a tri-vertex blended gradient plus some ClearType bold
font (best effect with Tahoma Bold). :class:`GradientButton` supports:

* Triple blended gradient background, with customizable colours;
* Custom colours for the "pressed" state;
* Rounded-corners buttons;
* Text-only or image+text buttons.

And a lot more. Check the demo for an almost complete review of the functionalities.

Usage
=====

Usage example::

import wx
import wx.lib.agw.gradientbutton as GB


class MyFrame(wx.Frame):

    def __init__(self, parent: wx.Window | None) -> None:
        wx.Frame.__init__(self, parent, -1, "GradientButton Demo")

        panel = wx.Panel(self, -1)

        # Create a vertical box sizer
        sizer = wx.BoxSizer(wx.VERTICAL)

        # One button without bitmap
        button_size = wx.Size(100, 50)
        sizer.Add(
            GB.GradientButton(panel, -1, None, "Hello World", size=button_size),
            0,
            wx.ALL,
            10,
        )

        # One button with bitmap
        my_bitmap = wx.Bitmap("my_bitmap.png", wx.BITMAP_TYPE_PNG)
        sizer.Add(
            GB.GradientButton(panel, -1, my_bitmap, "GradientButton", size=button_size),
            0,
            wx.ALL,
            10,
        )

        # Set the sizer for the panel
        panel.SetSizer(sizer)

        # Fit the frame to the sizer
        self.Fit()


# our normal wxApp-derived class, as usual

app = wx.App(False)

frame = MyFrame(None)
app.SetTopWindow(frame)
frame.Show()

app.MainLoop()

Supported Platforms
===================

:class:`GradientButton` has been tested on the following platforms:
  * Windows (Windows XP).


Window Styles
=============

`No particular window styles are available for this class.`


Events Processing
=================

This class processes the following events:

================= ======================================================================
Event Name        Description
================= ======================================================================
``wx.EVT_BUTTON`` Process a `wxEVT_COMMAND_BUTTON_CLICKED` event,
                    when the button is clicked.
================= ======================================================================


License And Version
===================

:class:`GradientButton` is distributed under the wxPython license.

Latest Revision: Andrea Gavana @ 27 Dec 2012, 21.00 GMT

Version 0.3
"""

from typing import Union

import wx


HOVER = 1
"""Flag used to indicate that the mouse is hovering on a :class:`GradientButton`."""
CLICK = 2
"""Flag used to indicate that the :class:`GradientButton` is on a pressed state."""


class GradientButtonEvent(wx.PyCommandEvent):
    """Event sent from :class:`GradientButton` when the button is activated.

    Args:
        eventType (int): the event type;
        eventId (int): the event identifier.
    """

    def __init__(self, eventType: int, eventId: int) -> None:
        wx.PyCommandEvent.__init__(self, eventType, eventId)
        self.isDown = False
        self.theButton: Union[None, GradientButton] = None

    def SetButtonObj(self, btn: "GradientButton") -> None:
        """Set the event object for the event.

        Args:
            btn ('GradientButton'): The button object.
        """
        self.theButton = btn

    def GetButtonObj(self) -> Union[None, "GradientButton"]:
        """Return the object associated with this event.

        Returns:
            Union[None, GradientButton]: The button object associated with this event,
                or None if no button is associated.
        """
        return self.theButton


class GradientButton(wx.Control):
    """This is the main class implementation of :class:`GradientButton`.

    Args:
        parent ('GradientButton'): The :class:`GradientButton` parent;
        id (int): Window identifier. A value of -1 indicates a default value.
        bitmap (None | wx.Bitmap): The button bitmap (if any);
        label (str): The button text label;
        pos (wx.Point): The control position.
            A value of (-1, -1) indicates a default position, chosen by either the
            windowing system or wxPython, depending on platform;
        size (wx.Size): The control size.
            A value of (-1, -1) indicates a default size, chosen by either the
            windowing system or wxPython, depending on platform;
        style (int): The button style (unused);
        align (int): Text/bitmap alignment. wx.CENTER or wx.LEFT;
        validator (wx.Validator): The validator associated to the button;
        name (str): the button name.
    """

    def __init__(
        self,
        parent: "GradientButton",
        id: int = wx.ID_ANY,
        bitmap: Union[None, wx.Bitmap] = None,
        label: str = "",
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = wx.NO_BORDER,
        align: int = wx.CENTER,
        validator: wx.Validator = wx.DefaultValidator,
        name: str = "gradientbutton",
    ) -> None:
        super().__init__(parent, id, pos, size, style, validator, name)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
        self.Bind(wx.EVT_SET_FOCUS, self.OnGainFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnLoseFocus)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)

        self._mouseAction = None
        self._hasFocus = False
        self._alignment = align
        self.SetBitmapLabel(bitmap)

        self.SetLabel(label)
        self.InheritAttributes()
        self.SetInitialSize(size)

        self.SetBaseColours()

    def SetBitmapLabel(self, bitmap: Union[None, wx.Bitmap]) -> None:
        """Set the bitmap label for the button.

        Args:
            bitmap (Union[Non, wx.Bitmap]): the bitmap label to set,.
        """
        self._bitmap = bitmap
        self.Refresh()

    def SetBaseColours(
        self,
        startcolour: Union[None, wx.Colour] = None,
        foregroundcolour: Union[None, wx.Colour] = None, 
    ) -> None:
        """Set the bottom, top, pressed and foreground colour.

        Args:
            startcolour (wx.Colour): based colour to be used for bottom, top and
                pressed.
            foregroundcolour (wx.Colour): colour used for the text.
        """
        if startcolour is None:
            startcolour = wx.BLACK
        if foregroundcolour is None:
            foregroundcolour = wx.WHITE

        self._bottomStartColour = startcolour
        rgba = (
            self._bottomStartColour.Red(),
            self._bottomStartColour.Green(),
            self._bottomStartColour.Blue(),
            self._bottomStartColour.Alpha(),
        )
        self._bottomEndColour = self.LightColour(self._bottomStartColour, 20)
        self._topStartColour = self.LightColour(self._bottomStartColour, 40)
        self._topEndColour = self.LightColour(self._bottomStartColour, 25)
        self._pressedTopColour = self.LightColour(self._bottomStartColour, 20)
        self._pressedBottomColour = wx.Colour(*rgba)
        self.SetForegroundColour(foregroundcolour)

    def LightColour(self, colour: wx.Colour, percent: int) -> wx.Colour:
        """Return light contrast of `colour`.

        The colour returned is from the scale of `colour` ==> white.

        Args:
            colour (wx.Colour): the input colour to be brightened;
            percent (int): determines how light the colour will be.
                `percent` = 100 returns white, `percent` = 0 returns `colour`.

        Returns:
            wx.Colour: The lightened colour.
        """
        end_colour = wx.WHITE
        rd = end_colour.Red() - colour.Red()
        gd = end_colour.Green() - colour.Green()
        bd = end_colour.Blue() - colour.Blue()
        high = 100

        # We take the percent way of the colour from colour -. white
        i = percent
        r = colour.Red() + ((i * rd * 100) / high) / 100
        g = colour.Green() + ((i * gd * 100) / high) / 100
        b = colour.Blue() + ((i * bd * 100) / high) / 100
        a = colour.Alpha()

        return wx.Colour(int(r), int(g), int(b), int(a))

    def OnSize(self, event: wx.SizeEvent) -> None:
        """Handle the ``wx.EVT_SIZE`` event for :class:`GradientButton`.

        Args:
            event (wx.SizeEvent): a :class:`wx.SizeEvent` event to be processed.
        """
        event.Skip()
        self.Refresh()

    def OnLeftDown(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_DOWN`` event for :class:`GradientButton`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if not self.IsEnabled():
            return

        self._mouseAction = CLICK
        self.CaptureMouse()
        self.Refresh()
        event.Skip()

    def OnLeftUp(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_UP`` event for :class:`GradientButton`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if not self.IsEnabled() or not self.HasCapture():
            return

        pos: wx.Point = event.GetPosition()
        rect: wx.Rect = self.GetClientRect()

        if self.HasCapture():
            self.ReleaseMouse()

        if rect.Contains(pos):
            self._mouseAction = HOVER
            self.Notify()
        else:
            self._mouseAction = None

        self.Refresh()
        event.Skip()

    def OnMouseEnter(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_ENTER_WINDOW`` event for :class:`GradientButton`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if not self.IsEnabled():
            return

        self._mouseAction = HOVER
        self.Refresh()
        event.Skip()

    def OnMouseLeave(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEAVE_WINDOW`` event for :class:`GradientButton`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        self._mouseAction = None
        self.Refresh()
        event.Skip()

    def OnGainFocus(self, event: wx.FocusEvent) -> None:
        """Handle the ``wx.EVT_SET_FOCUS`` event for :class:`GradientButton`.

        Args:
            event (wx.FocusEvent): a :class:`FocusEvent` event to be processed.
        """
        self._hasFocus = True
        self.Refresh()
        self.Update()

    def OnLoseFocus(self, event: wx.FocusEvent) -> None:
        """Handle the ``wx.EVT_KILL_FOCUS`` event for :class:`GradientButton`.

        Args:
            event (wx.FocusEvent): a :class:`FocusEvent` event to be processed.
        """
        self._hasFocus = False
        self.Refresh()
        self.Update()

    def OnKeyDown(self, event: wx.KeyEvent) -> None:
        """Handle the ``wx.EVT_KEY_DOWN`` event for :class:`GradientButton`.

        Args:
            event (wx.KeyEvent): a :class:`KeyEvent` event to be processed.
        """
        if self._hasFocus and event.GetKeyCode() == ord(" "):
            self._mouseAction = HOVER
            self.Refresh()
        event.Skip()

    def OnKeyUp(self, event: wx.KeyEvent) -> None:
        """Handle the ``wx.EVT_KEY_UP`` event for :class:`GradientButton`.

        Args:
            event (wx.KeyEvent): a :class:`KeyEvent` event to be processed.
        """
        if self._hasFocus and event.GetKeyCode() == ord(" "):
            self._mouseAction = HOVER
            self.Notify()
            self.Refresh()
        event.Skip()

    def OnPaint(self, event: wx.PaintEvent) -> None:
        """Handle the ``wx.EVT_PAINT`` event for :class:`GradientButton`.

        Args:
            event (wx.PaintEvent): a :class:`PaintEvent` event to be processed.
        """
        dc = wx.BufferedPaintDC(self)
        gc: wx.GraphicsContext = wx.GraphicsContext.Create(dc)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()

        clientRect: wx.Rect = self.GetClientRect()
        gradientRect = wx.Rect(*clientRect)
        capture: wx.Window = wx.Window.GetCapture()

        x, y, width, height = clientRect

        gradientRect.SetHeight(
            gradientRect.GetHeight() // 2 + ((capture == self and [1] or [0])[0])
        )
        if capture != self:
            if self._mouseAction == HOVER:
                topStart: wx.Colour = self.LightColour(self._topStartColour, 10)
                topEnd: wx.Colour = self.LightColour(self._topEndColour, 10)
            else:
                topStart, topEnd = self._topStartColour, self._topEndColour

            rc1 = wx.Rect(x, y, width, height // 2)
            path1: wx.GraphicsPath = self.GetPath(gc, rc1, 8)
            br1: wx.GraphicsBrush = gc.CreateLinearGradientBrush(
                x, y, x, y + height / 2, topStart, topEnd
            )
            gc.SetBrush(br1)
            gc.FillPath(path1)  # draw main

            path4: wx.GraphicsPath = gc.CreatePath()
            path4.AddRectangle(x, y + height / 2 - 8, width, 8)
            path4.CloseSubpath()
            gc.SetBrush(br1)
            gc.FillPath(path4)

        else:

            rc1 = wx.Rect(x, y, width, height)
            path1 = self.GetPath(gc, rc1, 8)
            gc.SetPen(wx.Pen(self._pressedTopColour))
            gc.SetBrush(wx.Brush(self._pressedTopColour))
            gc.FillPath(path1)

        gradientRect.Offset((0, gradientRect.GetHeight()))

        if capture != self:
            if self._mouseAction == HOVER:
                bottomStart: wx.Colour = self.LightColour(self._bottomStartColour, 10)
                bottomEnd: wx.Colour = self.LightColour(self._bottomEndColour, 10)
            else:
                bottomStart, bottomEnd = self._bottomStartColour, self._bottomEndColour

            rc3 = wx.Rect(x, y + height // 2, width, height // 2)
            path3: wx.GraphicsPath = self.GetPath(gc, rc3, 8)
            br3: wx.GraphicsBrush = gc.CreateLinearGradientBrush(
                x, y + height / 2, x, y + height, bottomStart, bottomEnd
            )
            gc.SetBrush(br3)
            gc.FillPath(path3)  # draw main

            path4 = gc.CreatePath()
            path4.AddRectangle(x, y + height / 2, width, 8)
            path4.CloseSubpath()
            gc.SetBrush(br3)
            gc.FillPath(path4)

            shadowOffset = 0
        else:
            rc2 = wx.Rect(
                x + 1, gradientRect.height // 2, gradientRect.width, gradientRect.height
            )
            path2: wx.GraphicsPath = self.GetPath(gc, rc2, 8)
            gc.SetPen(wx.Pen(self._pressedBottomColour))
            gc.SetBrush(wx.Brush(self._pressedBottomColour))
            gc.FillPath(path2)
            shadowOffset = 1

        # Create a ClientDC to get the text extent
        client_dc = wx.ClientDC(self)
        font: wx.Font = self.GetFont()
        client_dc.SetFont(font)
        label: str = self.GetLabel()
        tw, th = client_dc.GetTextExtent(label)

        if self._bitmap:
            bw: int = self._bitmap.GetWidth()
            bh: int = self._bitmap.GetHeight()
        else:
            bw = bh = 0

        # Set default values for pos_x and pos_y
        pos_x: float = 0
        pos_y: float = (height - th) / 2 + shadowOffset

        if self._alignment == wx.CENTER:
            pos_x = (
                width - bw - tw
            ) / 2 + shadowOffset  # adjust for bitmap and text to centre
            pos_y = (height - bh) / 2 + shadowOffset
            if self._bitmap:
                gc.DrawBitmap(
                    self._bitmap, pos_x, pos_y, bw, bh
                )  # draw bitmap if available
                pos_x += bw + 2  # extra spacing from bitmap
        elif self._alignment == wx.LEFT:
            pos_x = 3  # adjust for bitmap and text to left
            pos_y = (height - bh) / 2 + shadowOffset
            if self._bitmap:
                gc.DrawBitmap(
                    self._bitmap, pos_x, pos_y, bw, bh
                )  # draw bitmap if available
                pos_x += bw + 3  # extra spacing from bitmap

        gc.DrawText(label, pos_x + shadowOffset, pos_y)

    def GetPath(self, gc: wx.GraphicsContext, rc: wx.Rect, r: int) -> wx.GraphicsPath:
        """Return a rounded :class:`GraphicsPath` rectangle.

        Args:
            gc (wx.GraphicsContext): an instance of :class:`GraphicsContext`;
            rc (wx.Rect): a client rectangle;
            r (int): the radious of the rounded part of the rectangle.

        Returns:
            wx.GraphicsPath: A rounded rectangle path.
        """
        x, y, w, h = rc
        path: wx.GraphicsPath = gc.CreatePath()
        path.AddRoundedRectangle(x, y, w, h, r)
        path.CloseSubpath()
        return path

    def SetInitialSize(self, size: None | wx.Size = None) -> None:
        """
        Given the current font and bezel width settings, calculate and set a good size.

        Args:
            size (None | wx.Size): an instance of :class:`wx.Size`.
        """
        if size is None:
            size = wx.DefaultSize
        wx.Control.SetInitialSize(self, size)

    SetBestSize = SetInitialSize

    def AcceptsFocus(self) -> bool:
        """Return True if this window can be given focus by mouse click.

        Note:
            Overridden from :class:`wx.Control`.

        Returns:
            bool: True if the window can be given focus by mouse click, False otherwise.
        """
        return self.IsShown() and self.IsEnabled()

    def GetDefaultAttributes(self) -> wx.VisualAttributes:
        """Overridden base class virtual.

        By default we should use the same font/colour attributes as the native
        :class:`Button`.

        Returns:
            wx.VisualAttributes: The default visual attributes for the button.
        """
        return wx.Button.GetClassDefaultAttributes()

    def ShouldInheritColours(self) -> bool:
        """Overridden base class virtual.

        Buttons usually don't inherit the parent's colours.

        Note:
            Overridden from :class:`wx.Control`.

        Returns:
            bool: True if the button should inherit the parent's colours,
                False otherwise.
        """
        return False

    def Enable(self, enable: bool = True) -> None:
        """Enable/disable the button.

        Args:
            enable (bool): ``True`` to enable the button, ``False`` to disable it.

        Note:
            Overridden from :class:`wx.Control`.
        """
        wx.Control.Enable(self, enable)
        self.Refresh()

    def SetTopStartColour(self, colour: wx.Colour) -> None:
        """Set the top start colour for the gradient shading.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._topStartColour = colour
        self.Refresh()

    def GetTopStartColour(self) -> wx.Colour:
        """Return the top start colour for the gradient shading.

        Returns:
            wx.Colour: The top start colour for the gradient shading.
        """
        return self._topStartColour

    def SetTopEndColour(self, colour: wx.Colour) -> None:
        """Set the top end colour for the gradient shading.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._topEndColour = colour
        self.Refresh()

    def GetTopEndColour(self) -> wx.Colour:
        """Return the top end colour for the gradient shading.

        Returns:
            wx.Colour: The top end colour of the gradient.
        """
        return self._topEndColour

    def SetBottomStartColour(self, colour: wx.Colour) -> None:
        """Set the top bottom colour for the gradient shading.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._bottomStartColour = colour
        self.Refresh()

    def GetBottomStartColour(self) -> wx.Colour:
        """Return the bottom start colour for the gradient shading.

        Returns:
            wx.Colour: The bottom start colour for the gradient shading.
        """
        return self._bottomStartColour

    def SetBottomEndColour(self, colour: wx.Colour) -> None:
        """Set the bottom end colour for the gradient shading.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._bottomEndColour = colour
        self.Refresh()

    def GetBottomEndColour(self) -> wx.Colour:
        """Return the bottom end colour for the gradient shading.

        Returns:
            wx.Colour: The bottom end colour of the gradient.
        """
        return self._bottomEndColour

    def SetPressedTopColour(self, colour: wx.Colour) -> None:
        """Set the pressed top start colour for the gradient shading.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._pressedTopColour = colour
        self.Refresh()

    def GetPressedTopColour(self) -> wx.Colour:
        """Return the pressed top start colour for the gradient shading.

        Returns:
            wx.Colour: The pressed top start colour.
        """
        return self._pressedTopColour

    def SetPressedBottomColour(self, colour: wx.Colour) -> None:
        """Set the pressed bottom start colour for the gradient shading.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._pressedBottomColour: wx.Colour = colour
        self.Refresh()

    def GetPressedBottomColour(self) -> wx.Colour:
        """Return the pressed bottom start colour for the gradient shading.

        Returns:
            wx.Colour: The pressed bottom start colour for the gradient shading.
        """
        return self._pressedBottomColour

    def SetForegroundColour(self, colour: wx.Colour) -> None:
        """Set the :class:`GradientButton` foreground (text) colour.

        Args:
            colour (wx.Colour): a valid :class:`wx.Colour` object.

        Note:
            Overridden from :class:`wx.Control`.
        """
        wx.Control.SetForegroundColour(self, colour)
        self.Refresh()

    def DoGetBestSize(self) -> wx.Size:
        """Overridden base class virtual.

        Determines the best size of the button based on the label and bezel size.

        Note:
            Overridden from :class:`wx.Control`.

        Returns:
            :class:`wx.Size`: The best size for the button.
        """
        label: str = self.GetLabel()
        if not label:
            return wx.Size(112, 48)

        dc = wx.ClientDC(self)
        dc.SetFont(self.GetFont())
        retWidth, retHeight = dc.GetTextExtent(label)

        bmpWidth: int = 0
        bmpHeight: int = 0
        constant = 15
        if self._bitmap:
            bmpWidth, bmpHeight = self._bitmap.GetWidth() + 10, self._bitmap.GetHeight()
            retWidth += bmpWidth
            retHeight: int = max(bmpHeight, retHeight)
            constant = 15

        return wx.Size(retWidth + constant, retHeight + constant)

    def SetDefault(self) -> None:
        """Set the default button."""
        tlw: wx.Window = wx.GetTopLevelParent(self)
        if isinstance(tlw, (wx.Dialog, wx.Frame)) and hasattr(tlw, "SetDefaultItem"):
            tlw.SetDefaultItem(self)
        else:
            # Fallback: Set the button as the default in a different way if possible
            if hasattr(self, "SetDefault"):
                self.SetDefault()

    def Notify(self) -> None:
        """Actually send a ``wx.EVT_BUTTON`` event to the listener (if any)."""
        evt = GradientButtonEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId())
        evt.SetButtonObj(self)
        evt.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(evt)
