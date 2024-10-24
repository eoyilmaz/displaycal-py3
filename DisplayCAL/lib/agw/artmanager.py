# -*- coding: utf-8 -*-
"""Drawing routines and customizations for the AGW widgets
:class:`~wx.lib.agw.labelbook.LabelBook` and :class:`~wx.lib.agw.flatmenu.FlatMenu`.
"""

import random

from six import BytesIO

from typing import Callable, Dict, List, Tuple, Type, Union

from DisplayCAL.lib.agw.fmresources import (
    BU_EXT_LEFT_ALIGN_STYLE,
    BU_EXT_RIGHT_ALIGN_STYLE,
    BU_EXT_RIGHT_TO_LEFT_STYLE,
    BottomShadow,
    BottomShadowFull,
    CS_DROPSHADOW,
    ControlDisabled,
    ControlFocus,
    ControlPressed,
    RightShadow,
    Style2007,
    StyleXP,
    arrow_down,
    arrow_up,
    shadow_bottom_alpha,
    shadow_bottom_left_alpha,
    shadow_bottom_left_xpm,
    shadow_bottom_xpm,
    shadow_center_alpha,
    shadow_center_xpm,
    shadow_right_alpha,
    shadow_right_top_alpha,
    shadow_right_top_xpm,
    shadow_right_xpm,
)

import wx

# ------------------------------------------------------------------------------------ #
# Class DCSaver
# ------------------------------------------------------------------------------------ #

_: Callable[[str], str] = wx.GetTranslation

_libimported = None

if wx.Platform == "__WXMSW__":
    osVersion = wx.GetOsVersion()
    # Shadows behind menus are supported only in XP
    if osVersion[1] == 5 and osVersion[2] == 1:
        try:
            import win32api
            import win32con
            import winxpgui

            _libimported = "MH"
        except ImportError:
            try:
                import ctypes

                _libimported = "ctypes"
            except ImportError:
                pass
    else:
        _libimported = None


class DCSaver(object):
    """Construct a DC saver.

    The dc is copied as-is.

    Args:
        pdc (wx.DC): An instance of :class:`wx.DC`.
    """

    def __init__(self, pdc: wx.DC):
        self._pdc = pdc
        self._pen = pdc.GetPen()
        self._brush = pdc.GetBrush()

    def __del__(self) -> None:
        """While destructing, restore the dc pen and brush."""
        if self._pdc:
            self._pdc.SetPen(self._pen)
            self._pdc.SetBrush(self._brush)


# ------------------------------------------------------------------------------------ #
# Class RendererBase
# ------------------------------------------------------------------------------------ #


class RendererBase(object):
    """Base class for all theme renderers."""

    def DrawButtonBorders(
        self, dc: wx.DC, rect: wx.Rect, penColour: wx.Colour, brushColour: wx.Colour
    ) -> None:
        """Draw borders for buttons.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            penColour (wx.Colour): a valid :class:`wx.Colour` for the pen border.
            brushColour (wx.Colour): a valid :class:`wx.Colour` for the brush.
        """
        # Keep old pen and brush
        _ = DCSaver(dc)

        # Set new pen and brush
        dc.SetPen(wx.Pen(penColour))
        dc.SetBrush(wx.Brush(brushColour))

        # Draw the rectangle
        dc.DrawRectangle(rect)

    def DrawBitmapArea(
        self,
        dc: wx.DC,
        xpm_name: str,
        rect: wx.Rect,
        baseColour: wx.Colour,
        flipSide: bool,
    ) -> None:
        """Draw the area below a bitmap and the bitmap itself using a gradient shading.

        Args:
            dc (wx.DC): :class:`wx.DC` instance.
            xpm_name (str): The name of the XPM bitmap.
            rect (wx.Rect): The bitmap client rectangle.
            baseColour (wx.Colour): A valid :class:`wx.Colour` for the bitmap
                background.
            flipSide (bool): `True` to flip the gradient direction, `False` otherwise.
        """
        # draw the gradient area
        if not flipSide:
            ArtManager.Get().PaintDiagonalGradientBox(
                dc,
                rect,
                wx.WHITE,
                ArtManager.Get().LightColour(baseColour, 20),
                True,
                False,
            )
        else:
            ArtManager.Get().PaintDiagonalGradientBox(
                dc,
                rect,
                ArtManager.Get().LightColour(baseColour, 20),
                wx.WHITE,
                True,
                False,
            )

        # draw arrow
        arrowDown = wx.Bitmap(xpm_name)
        arrowDown.SetMask(wx.Mask(arrowDown, wx.WHITE))
        dc.DrawBitmap(arrowDown, rect.x + 1, rect.y + 1, True)

    def DrawBitmapBorders(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        penColour: wx.Colour,
        bitmapBorderUpperLeftPen: wx.Colour,
    ) -> None:
        """Draw borders for a bitmap.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            penColour (wx.Colour): A valid :class:`wx.Colour` for the pen border.
            bitmapBorderUpperLeftPen (wx.Colour): A valid :class:`wx.Colour` for the pen
                upper left border.
        """
        # Keep old pen and brush
        _ = DCSaver(dc)

        # lower right side
        dc.SetPen(wx.Pen(penColour))
        dc.DrawLine(
            rect.x,
            rect.y + rect.height - 1,
            rect.x + rect.width,
            rect.y + rect.height - 1,
        )
        dc.DrawLine(
            rect.x + rect.width - 1,
            rect.y,
            rect.x + rect.width - 1,
            rect.y + rect.height,
        )

        # upper left side
        dc.SetPen(wx.Pen(bitmapBorderUpperLeftPen))
        dc.DrawLine(rect.x, rect.y, rect.x + rect.width, rect.y)
        dc.DrawLine(rect.x, rect.y, rect.x, rect.y + rect.height)

    def GetMenuFaceColour(self) -> wx.Colour:
        """Return the foreground colour for the menu.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE), 80
        )

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for text colour when enabled.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return wx.BLACK

    def GetTextColourDisable(self) -> wx.Colour:
        """Return the colour used for text colour when disabled.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT), 30
        )

    def GetFont(self) -> wx.Font:
        """Return the font used for text.

        Returns:
            wx.Font: A :class:`wx.Font` instance.
        """
        return wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

    def DrawButton(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input_: Union[None, bool, wx.Colour] = None,
    ) -> None:
        """Draw a button using the appropriate theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            input_ (Union[None, bool, wx.Colour]): a flag used to call the right method.

        Raises:
            NotImplementedError: This method must be implemented in derived classes.
        """
        raise NotImplementedError(
            "DrawButton method must be implemented in derived classes"
        )

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the toolbar's client rectangle.

        Raises:
            NotImplementedError: This method must be implemented in derived classes.
        """
        raise NotImplementedError(
            "DrawToolBarBg method must be implemented in derived classes"
        )

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menu bar's client rectangle.

        Raises:
            NotImplementedError: This method must be implemented in derived classes.
        """
        raise NotImplementedError(
            "DrawMenuBarBg method must be implemented in derived classes"
        )


# ------------------------------------------------------------------------------------ #
# Class RendererXP
# ------------------------------------------------------------------------------------ #


class RendererXP(RendererBase):
    """Xp-Style renderer."""

    def __init__(self) -> None:
        RendererBase.__init__(self)

    def DrawButton(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input_: Union[None, bool, wx.Colour] = None,
    ) -> None:
        """Draw a button using the XP theme.

        Args:
            dc (wx.DC): An instance of :class:`wx.DC`.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            input_ (Union[None, bool, wx.Colour]): a flag used to call the right method.
        """
        if input_ is None or isinstance(input_, bool):
            self.DrawButtonTheme(dc, rect, state, input_)
        else:
            self.DrawButtonColour(dc, rect, state, input_)

    def DrawButtonTheme(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        useLightColours: Union[None, bool] = None
    ) -> None:
        """Draw a button using the XP theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            useLightColours (bool): `True` to use light colours, `False` otherwise.
        """
        # switch according to the status
        if state == ControlFocus:
            penColour = ArtManager.Get().FrameColour()
            brushColour = ArtManager.Get().BackgroundColour()
        elif state == ControlPressed:
            penColour = ArtManager.Get().FrameColour()
            brushColour = ArtManager.Get().HighlightBackgroundColour()
        else:
            penColour = ArtManager.Get().FrameColour()
            brushColour = ArtManager.Get().BackgroundColour()

        # Draw the button borders
        self.DrawButtonBorders(dc, rect, penColour, brushColour)

    def DrawButtonColour(
        self, dc: wx.DC, rect: wx.Rect, state: int, colour: wx.Colour
    ) -> None:
        """Draw a button using the XP theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            colour (wx.Colour): a valid :class:`wx.Colour` instance.
        """
        # switch according to the status
        if state == ControlFocus:
            penColour = colour
            brushColour = ArtManager.Get().LightColour(colour, 75)
        elif state == ControlPressed:
            penColour = colour
            brushColour = ArtManager.Get().LightColour(colour, 60)
        else:
            penColour = colour
            brushColour = ArtManager.Get().LightColour(colour, 75)

        # Draw the button borders
        self.DrawButtonBorders(dc, rect, penColour, brushColour)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The menu bar's client rectangle.
        """
        # For office style, we simple draw a rectangle with a gradient colouring
        artMgr = ArtManager.Get()
        vertical = artMgr.GetMBVerticalGradient()

        _ = DCSaver(dc)

        # fill with gradient
        startColour = artMgr.GetMenuBarFaceColour()
        if artMgr.IsDark(startColour):
            startColour = artMgr.LightColour(startColour, 50)

        endColour = artMgr.LightColour(startColour, 90)
        artMgr.PaintStraightGradientBox(dc, rect, startColour, endColour, vertical)

        # Draw the border
        if artMgr.GetMenuBarBorder():
            dc.SetPen(wx.Pen(startColour))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(rect)

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The toolbar's client rectangle.
        """
        artMgr = ArtManager.Get()

        if not artMgr.GetRaiseToolbar():
            return

        # For office style, we simple draw a rectangle with a gradient colouring
        vertical = artMgr.GetMBVerticalGradient()

        _ = DCSaver(dc)

        # fill with gradient
        startColour = artMgr.GetMenuBarFaceColour()
        if artMgr.IsDark(startColour):
            startColour = artMgr.LightColour(startColour, 50)

        startColour = artMgr.LightColour(startColour, 20)

        endColour = artMgr.LightColour(startColour, 90)
        artMgr.PaintStraightGradientBox(dc, rect, startColour, endColour, vertical)
        artMgr.DrawBitmapShadow(dc, rect)

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for text colour when enabled.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return wx.BLACK


# ------------------------------------------------------------------------------------ #
# Class RendererMSOffice2007
# ------------------------------------------------------------------------------------ #


class RendererMSOffice2007(RendererBase):
    """Windows MS Office 2007 style."""

    def __init__(self) -> None:
        RendererBase.__init__(self)

    def GetColoursAccordingToState(self, state: int) -> Tuple[int, int, int, int]:
        """Return a tuple according to the menu item state.

        Args:
            state (int): One of the following bits:

         ==================== ======= ==========================
         Item State            Value  Description
         ==================== ======= ==========================
         ``ControlPressed``         0 The item is pressed
         ``ControlFocus``           1 The item is focused
         ``ControlDisabled``        2 The item is disabled
         ``ControlNormal``          3 Normal state
         ==================== ======= ==========================

        Returns:
            A tuple containing the gradient percentages.
        """
        # switch according to the status
        if state == ControlFocus:
            upperBoxTopPercent = 95
            upperBoxBottomPercent = 50
            lowerBoxTopPercent = 40
            lowerBoxBottomPercent = 90

        elif state == ControlPressed:
            upperBoxTopPercent = 75
            upperBoxBottomPercent = 90
            lowerBoxTopPercent = 90
            lowerBoxBottomPercent = 40

        elif state == ControlDisabled:
            upperBoxTopPercent = 100
            upperBoxBottomPercent = 100
            lowerBoxTopPercent = 70
            lowerBoxBottomPercent = 70

        else:
            upperBoxTopPercent = 90
            upperBoxBottomPercent = 50
            lowerBoxTopPercent = 30
            lowerBoxBottomPercent = 75

        return (
            upperBoxTopPercent,
            upperBoxBottomPercent,
            lowerBoxTopPercent,
            lowerBoxBottomPercent,
        )

    def DrawButton(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input_: Union[None, bool, wx.Colour] = None,
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            input_ (Union[None, bool, wx.Colour]): A flag used to call the right method.
        """
        if input_ is None or isinstance(input_, bool):
            self.DrawButtonTheme(dc, rect, state, input_)
        else:
            self.DrawButtonColour(dc, rect, state, input_)

    def DrawButtonTheme(
        self, dc: wx.DC, rect: wx.Rect, state: int, useLightColours: Union[None | bool]
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            useLightColours (Union[None | bool]): `True` to use light colours,
                ``False`` otherwise.
        """
        self.DrawButtonColour(
            dc, rect, state, ArtManager.Get().GetThemeBaseColour(useLightColours)
        )
        self.DrawButtonColour(
            dc, rect, state, ArtManager.Get().GetThemeBaseColour(useLightColours)
        )

    def DrawButtonColour(self, dc, rect, state, colour):
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            colour (wx.Colour): a valid :class:`wx.Colour` instance.
        """
        artMgr = ArtManager.Get()

        # Keep old pen and brush
        _ = DCSaver(dc)

        # Define the rounded rectangle base on the given rect
        # we need an array of 9 points for it
        baseColour = colour

        # Define the middle points
        leftPt = wx.Point(rect.x, rect.y + (rect.height / 2))
        rightPt = wx.Point(rect.x + rect.width - 1, rect.y + (rect.height / 2))

        # Define the top region
        top = wx.Rect((rect.GetLeft(), rect.GetTop()), rightPt)
        bottom = wx.Rect(leftPt, (rect.GetRight(), rect.GetBottom()))

        (
            upperBoxTopPercent,
            upperBoxBottomPercent,
            lowerBoxTopPercent,
            lowerBoxBottomPercent,
        ) = self.GetColoursAccordingToState(state)

        topStartColour = artMgr.LightColour(baseColour, upperBoxTopPercent)
        topEndColour = artMgr.LightColour(baseColour, upperBoxBottomPercent)
        bottomStartColour = artMgr.LightColour(
            baseColour, lowerBoxTopPercent
        )
        bottomEndColour = artMgr.LightColour(
            baseColour, lowerBoxBottomPercent
        )

        artMgr.PaintStraightGradientBox(dc, top, topStartColour, topEndColour)
        artMgr.PaintStraightGradientBox(dc, bottom, bottomStartColour, bottomEndColour)

        rr = wx.Rect(rect.x, rect.y, rect.width, rect.height)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        frameColour = artMgr.LightColour(baseColour, 60)
        dc.SetPen(wx.Pen(frameColour))
        dc.DrawRectangle(rr)

        wc = artMgr.LightColour(baseColour, 80)
        dc.SetPen(wx.Pen(wc))
        rr.Deflate(1, 1)
        dc.DrawRectangle(rr)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menu bar's client rectangle.
        """
        # Keep old pen and brush
        _ = DCSaver(dc)
        artMgr = ArtManager.Get()
        baseColour = artMgr.GetMenuBarFaceColour()

        dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.DrawRectangle(rect)

        # Define the rounded rectangle base on the given rect
        # we need an array of 9 points for it
        regPts = [wx.Point() for _ in range(9)]
        radius = 2

        regPts[0] = wx.Point(rect.x, rect.y + radius)
        regPts[1] = wx.Point(rect.x + radius, rect.y)
        regPts[2] = wx.Point(rect.x + rect.width - radius - 1, rect.y)
        regPts[3] = wx.Point(rect.x + rect.width - 1, rect.y + radius)
        regPts[4] = wx.Point(rect.x + rect.width - 1, rect.y + rect.height - radius - 1)
        regPts[5] = wx.Point(rect.x + rect.width - radius - 1, rect.y + rect.height - 1)
        regPts[6] = wx.Point(rect.x + radius, rect.y + rect.height - 1)
        regPts[7] = wx.Point(rect.x, rect.y + rect.height - radius - 1)
        regPts[8] = regPts[0]

        # Define the middle points
        factor = artMgr.GetMenuBgFactor()

        leftPt1 = wx.Point(rect.x, rect.y + (rect.height / factor))
        rightPt1 = wx.Point(rect.x + rect.width, rect.y + (rect.height / factor))

        leftPt2 = wx.Point(rect.x, rect.y + (rect.height / factor) * (factor - 1))
        rightPt2 = wx.Point(
            rect.x + rect.width, rect.y + (rect.height / factor) * (factor - 1)
        )

        # Define the top region
        topReg = [wx.Point() for _ in range(7)]
        topReg[0] = regPts[0]
        topReg[1] = regPts[1]
        topReg[2] = wx.Point(regPts[2].x + 1, regPts[2].y)
        topReg[3] = wx.Point(regPts[3].x + 1, regPts[3].y)
        topReg[4] = wx.Point(rightPt1.x, rightPt1.y + 1)
        topReg[5] = wx.Point(leftPt1.x, leftPt1.y + 1)
        topReg[6] = topReg[0]

        # Define the middle region
        middle = wx.Rect(leftPt1, wx.Point(rightPt2.x - 2, rightPt2.y))

        # Define the bottom region
        bottom = wx.Rect(leftPt2, wx.Point(rect.GetRight() - 1, rect.GetBottom()))

        topStartColour = artMgr.LightColour(baseColour, 90)
        topEndColour = artMgr.LightColour(baseColour, 60)
        bottomStartColour = artMgr.LightColour(baseColour, 40)
        bottomEndColour = artMgr.LightColour(baseColour, 20)

        topRegion = wx.Region(topReg)

        artMgr.PaintGradientRegion(dc, topRegion, topStartColour, topEndColour)
        artMgr.PaintStraightGradientBox(dc, bottom, bottomStartColour, bottomEndColour)
        artMgr.PaintStraightGradientBox(dc, middle, topEndColour, bottomStartColour)

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect):
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The toolbar's client rectangle.
        """
        artMgr = ArtManager.Get()

        if not artMgr.GetRaiseToolbar():
            return

        # Keep old pen and brush
        _ = DCSaver(dc)

        baseColour = artMgr.GetMenuBarFaceColour()
        baseColour = artMgr.LightColour(baseColour, 20)

        dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.DrawRectangle(rect)

        radius = 2

        # Define the rounded rectangle base on the given rect
        # we need an array of 9 points for it
        regPts = [None] * 9

        regPts[0] = wx.Point(rect.x, rect.y + radius)
        regPts[1] = wx.Point(rect.x + radius, rect.y)
        regPts[2] = wx.Point(rect.x + rect.width - radius - 1, rect.y)
        regPts[3] = wx.Point(rect.x + rect.width - 1, rect.y + radius)
        regPts[4] = wx.Point(rect.x + rect.width - 1, rect.y + rect.height - radius - 1)
        regPts[5] = wx.Point(rect.x + rect.width - radius - 1, rect.y + rect.height - 1)
        regPts[6] = wx.Point(rect.x + radius, rect.y + rect.height - 1)
        regPts[7] = wx.Point(rect.x, rect.y + rect.height - radius - 1)
        regPts[8] = regPts[0]

        # Define the middle points
        factor = artMgr.GetMenuBgFactor()

        leftPt1 = wx.Point(rect.x, rect.y + (rect.height / factor))
        rightPt1 = wx.Point(rect.x + rect.width, rect.y + (rect.height / factor))

        leftPt2 = wx.Point(rect.x, rect.y + (rect.height / factor) * (factor - 1))
        rightPt2 = wx.Point(
            rect.x + rect.width, rect.y + (rect.height / factor) * (factor - 1)
        )

        # Define the top region
        topReg = [None] * 7
        topReg[0] = regPts[0]
        topReg[1] = regPts[1]
        topReg[2] = wx.Point(regPts[2].x + 1, regPts[2].y)
        topReg[3] = wx.Point(regPts[3].x + 1, regPts[3].y)
        topReg[4] = wx.Point(rightPt1.x, rightPt1.y + 1)
        topReg[5] = wx.Point(leftPt1.x, leftPt1.y + 1)
        topReg[6] = topReg[0]

        # Define the middle region
        middle = wx.Rect(leftPt1, wx.Point(rightPt2.x - 2, rightPt2.y))

        # Define the bottom region
        bottom = wx.Rect(leftPt2, wx.Point(rect.GetRight() - 1, rect.GetBottom()))

        topStartColour = artMgr.LightColour(baseColour, 90)
        topEndColour = artMgr.LightColour(baseColour, 60)
        bottomStartColour = artMgr.LightColour(baseColour, 40)
        bottomEndColour = artMgr.LightColour(baseColour, 20)

        topRegion = wx.Region(topReg)

        artMgr.PaintGradientRegion(dc, topRegion, topStartColour, topEndColour)
        artMgr.PaintStraightGradientBox(dc, bottom, bottomStartColour, bottomEndColour)
        artMgr.PaintStraightGradientBox(dc, middle, topEndColour, bottomStartColour)

        artMgr.DrawBitmapShadow(dc, rect)

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for text colour when enabled.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return wx.Colour("MIDNIGHT BLUE")


# ------------------------------------------------------------------------------------ #
# Class ArtManager
# ------------------------------------------------------------------------------------ #


class ArtManager(wx.EvtHandler):
    """This class provides utilities for creating shadows and adjusting colors."""

    _alignmentBuffer = 7
    _menuTheme: int = StyleXP
    _verticalGradient = False
    _renderers: Dict[int, RendererBase] = {}
    _bmpShadowEnabled = False
    _ms2007sunken = False
    _drowMBBorder = True
    _menuBgFactor = 5
    _menuBarColourScheme: str = _("Default")
    _raiseTB = True
    _bitmaps: Dict[str, wx.Bitmap] = {}
    _transparency = 255

    def __init__(self) -> None:
        wx.EvtHandler.__init__(self)
        self._menuBarBgColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)

        # connect an event handler to the system colour change event
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self.OnSysColourChange)

        # Initialize the menu bar selection colour
        self._menuBarSelColour = wx.Colour(0, 0, 0)  # Default to black

    def SetTransparency(self, amount: int) -> None:
        """Set the alpha channel value for transparent windows.

        Args:
            amount (int): The actual transparency value (between 0 and 255).

        Raises:
            Exception: If the `amount` parameter is lower than ``0`` or greater than
                ``255``.
        """
        if self._transparency == amount:
            return

        if amount < 0 or amount > 255:
            raise Exception("Invalid transparency value")

        self._transparency = amount

    def GetTransparency(self) -> int:
        """Return the alpha channel value for transparent windows.

        Returns:
            int: An integer representing the alpha channel value.
        """
        return self._transparency

    @classmethod
    def ConvertToBitmap(
        cls, xpm: Union[List[str], bytes], alpha: Union[None, List[int]] = None
    ) -> wx.Bitmap:
        """Convert the given image to a bitmap, optionally overlaying an alpha channel.

        Args:
            xpm (Union[List[str], bytes]): A list of strings formatted as XPM.
            alpha (Union[None, List[int]]): A list of alpha values, the same size as the
                xpm bitmap.

        Raises:
            TypeError: If `xpm` is not a list of strings or a bytes object.

        Returns:
            wx.Bitmap: An instance of :class:`wx.Bitmap`.
        """
        if isinstance(xpm, bytes):
            img = wx.ImageFromStream(BytesIO(xpm))
        elif isinstance(xpm, list) and all(isinstance(data, str) for data in xpm):
            img = wx.Bitmap(xpm).ConvertToImage()
        else:
            raise TypeError("xpm must be a list of strings or a bytes object")

        if alpha is not None:
            x = img.GetWidth()
            y = img.GetHeight()
            img.InitAlpha()
            for jj in range(y):
                for ii in range(x):
                    img.SetAlpha(ii, jj, alpha[jj * x + ii])

        return wx.Bitmap(img)

    def Initialize(self) -> None:
        """Initialize the bitmaps and colours."""
        # create wxBitmaps from the xpm's
        self._rightBottomCorner = self.ConvertToBitmap(
            shadow_center_xpm, shadow_center_alpha
        )
        self._bottom = self.ConvertToBitmap(
            shadow_bottom_xpm, shadow_bottom_alpha
        )
        self._bottomLeft = self.ConvertToBitmap(
            shadow_bottom_left_xpm, shadow_bottom_left_alpha
        )
        self._rightTop = self.ConvertToBitmap(
            shadow_right_top_xpm, shadow_right_top_alpha
        )
        self._right = self.ConvertToBitmap(
            shadow_right_xpm, shadow_right_alpha
        )

        # initialise the colour map
        self.InitColours()
        self.SetMenuBarColour(self._menuBarColourScheme)

        # Create common bitmaps
        self.FillStockBitmaps()

    def FillStockBitmaps(self) -> None:
        """Initialize few standard bitmaps."""
        bmp = self.ConvertToBitmap(arrow_down, alpha=None)
        bmp.SetMask(wx.Mask(bmp, wx.Colour(0, 128, 128)))
        self._bitmaps.update({"arrow_down": bmp})

        bmp = self.ConvertToBitmap(arrow_up, alpha=None)
        bmp.SetMask(wx.Mask(bmp, wx.Colour(0, 128, 128)))
        self._bitmaps.update({"arrow_up": bmp})

    def GetStockBitmap(self, name):
        """Return a bitmap from a stock.

        Args:
            name (str): The bitmap name.

        Returns:
            wx.Bitmap: The stock bitmap, if `name` was found in the stock bitmap
                dictionary. Otherwise, :class:`NullBitmap` is returned.
        """
        return self._bitmaps.get(name, wx.NullBitmap)

    @classmethod
    def Get(cls: Type["ArtManager"]) -> "ArtManager":
        """Accessor to the unique art manager object.

        Returns:
            A unique instance of :class:`ArtManager`.
        """
        if not hasattr(cls, "_instance"):
            cls._instance = ArtManager()
            cls._instance.Initialize()

            # Initialize the renderers map
            cls._renderers[StyleXP] = RendererXP()
            cls._renderers[Style2007] = RendererMSOffice2007()

        return cls._instance

    @classmethod
    def Free(cls) -> None:
        """Destructor for the unique art manager object."""
        if hasattr(cls, "_instance"):
            del cls._instance

    def OnSysColourChange(self, event: wx.SysColourChangedEvent) -> None:
        """Handle the ``wx.EVT_SYS_COLOUR_CHANGED`` event for :class:`ArtManager`.

        Args:
            event (wx.SysColourChangedEvent): A :class:`SysColourChangedEvent` event to
                be processed.
        """
        # reinitialise the colour map
        self.InitColours()

    def LightColour(self, colour: wx.Colour, percent: int) -> wx.Colour:
        """Return light contrast of `colour`.

        The colour returned is from the scale of `colour` ==> white.

        Args:
            colour (wx.Colour): The input colour to be brightened, an instance of
                :class:`wx.Colour`.
            percent (int): Determines how light the colour will be.
                `percent` = ``100`` returns white, `percent` = ``0`` returns `colour`.

        Returns:
            wx.Colour: A light contrast of the input `colour`.
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

    def DarkColour(self, colour: wx.Colour, percent: int) -> wx.Colour:
        """Like :meth:`.LightColour`, but create a darker colour by `percent`.

        Args:
            colour (wx.Colour): The input colour to be darkened.
            percent (int): Determines how dark the colour will be.
                `percent` = ``100`` returns black, `percent` = ``0`` returns `colour`.

        Returns:
            wx.Colour: A dark contrast of the input `colour`.
        """
        end_colour = wx.BLACK
        rd = end_colour.Red() - colour.Red()
        gd = end_colour.Green() - colour.Green()
        bd = end_colour.Blue() - colour.Blue()
        high = 100

        # We take the percent way of the colour from colour -. white
        i = percent
        r = colour.Red() + ((i * rd * 100) / high) / 100
        g = colour.Green() + ((i * gd * 100) / high) / 100
        b = colour.Blue() + ((i * bd * 100) / high) / 100

        return wx.Colour(int(r), int(g), int(b))

    def PaintStraightGradientBox(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        startColour: wx.Colour,
        endColour: wx.Colour,
        vertical: bool = True
    ) -> None:
        """Paint the rectangle with gradient colouring.

        The gradient lines are either horizontal or vertical.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            startColour (wx.Colour): The first colour of the gradient shading.
            endColour (wx.EndColour): The second colour of the gradient shading.
            vertical (bool): ``True`` for gradient colouring in the vertical direction,
                ``False`` for horizontal shading.
        """
        _ = DCSaver(dc)

        if vertical:
            high = rect.GetHeight() - 1
            direction = wx.SOUTH
        else:
            high = rect.GetWidth() - 1
            direction = wx.EAST

        if high < 1:
            return

        dc.GradientFillLinear(rect, startColour, endColour, direction)

    def PaintGradientRegion(
        self,
        dc: wx.DC,
        region: wx.Region,
        startColour: wx.Colour,
        endColour: wx.Colour,
        vertical: bool = True
    ) -> None:
        """Paint a region with gradient colouring.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            region (wx.Region): A region to be filled with gradient shading.
            startColour (wx.Colour): The first colour of the gradient shading.
            endColour (wx.Colour): The second colour of the gradient shading.
            vertical (bool): ``True`` for gradient colouring in the vertical direction,
                ``False`` for horizontal shading.
        """
        # The way to achieve non-rectangle
        memDC = wx.MemoryDC()
        rect = region.GetBox()
        bitmap = wx.Bitmap(rect.width, rect.height)
        memDC.SelectObject(bitmap)

        # Colour the whole rectangle with gradient
        rr = wx.Rect(0, 0, rect.width, rect.height)
        self.PaintStraightGradientBox(memDC, rr, startColour, endColour, vertical)

        # Convert the region to a black and white bitmap with the white pixels being
        # inside the region we draw the bitmap over the gradient coloured rectangle,
        # with mask set to white, this will cause our region to be coloured with the
        # gradient, while area outside the region will be painted with black.
        # Then we simply draw the bitmap to the dc with mask set to black.
        tmpRegion = wx.Region(rect.x, rect.y, rect.width, rect.height)
        tmpRegion.Offset(-rect.x, -rect.y)
        regionBmp = tmpRegion.ConvertToBitmap()
        regionBmp.SetMask(wx.Mask(regionBmp, wx.WHITE))

        # The function ConvertToBitmap() return a rectangle bitmap which is shorter by 1
        # pixel on the height and width (this is correct behavior,
        # since DrawLine does not include the second point as part of the line)
        # we fix this issue by drawing our own line at the bottom and left side of the
        # rectangle
        memDC.SetPen(wx.BLACK_PEN)
        memDC.DrawBitmap(regionBmp, 0, 0, True)
        memDC.DrawLine(0, rr.height - 1, rr.width, rr.height - 1)
        memDC.DrawLine(rr.width - 1, 0, rr.width - 1, rr.height)

        memDC.SelectObject(wx.NullBitmap)
        bitmap.SetMask(wx.Mask(bitmap, wx.BLACK))
        dc.DrawBitmap(bitmap, rect.x, rect.y, True)

    def PaintDiagonalGradientBox(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        startColour: wx.Colour,
        endColour: wx.Colour,
        startAtUpperLeft: bool = True,
        trimToSquare: bool = True,
    ) -> None:
        """Paint rectangle with gradient colouring.

        The gradient lines are diagonal and may start from the upper left corner or from
        the upper right corner.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            startColour (wx.Colour): The first colour of the gradient shading.
            endColour (wx.Colour): The second colour of the gradient shading.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the upper
                left corner of the rectangle, ``False`` to start at the upper right
                corner.
            trimToSquare (bool): ``True`` to trim the gradient lines in a square.
        """
        # gradient fill from colour 1 to colour 2 with top to bottom
        if rect.height < 1 or rect.width < 1:
            return

        # Save the current pen and brush
        savedPen = dc.GetPen()
        savedBrush = dc.GetBrush()

        # calculate some basic numbers
        size, sizeX, sizeY, proportion = self._calculate_sizes(rect, trimToSquare)
        rstep, gstep, bstep = self._calculate_steps(startColour, endColour, size)

        self._draw_upper_triangle(
            dc,
            rect,
            startColour,
            rstep,
            gstep,
            bstep,
            size,
            sizeX,
            sizeY,
            proportion,
            startAtUpperLeft,
        )
        self._draw_lower_triangle(
            dc,
            rect,
            startColour,
            rstep,
            gstep,
            bstep,
            size,
            sizeX,
            sizeY,
            proportion,
            startAtUpperLeft,
        )

        # Restore the pen and brush
        dc.SetPen(savedPen)
        dc.SetBrush(savedBrush)

    def _calculate_sizes(
        self, rect: wx.Rect, trimToSquare: bool
    ) -> Tuple[int, int, int, float]:
        """Calculate the sizes for the gradient drawing.

        Args:
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            trimToSquare (bool): ``True`` to trim the gradient lines in a square.

        Returns:
            Tuple[int, int, int, float]: A tuple containing the size, sizeX, sizeY and
                proportion.
        """
        if rect.width > rect.height:
            if trimToSquare:
                size = rect.height
                sizeX = sizeY = rect.height - 1
                proportion = 1.0  # Square proportion is 1.0
            else:
                proportion = float(rect.heigh) / float(rect.width)
                size = rect.width
                sizeX = rect.width - 1
                sizeY = rect.height - 1
        else:
            if trimToSquare:
                size = rect.width
                sizeX = sizeY = rect.width - 1
                proportion = 1.0  # Square proportion is 1.0
            else:
                sizeX = rect.width - 1
                size = rect.height
                sizeY = rect.height - 1
                proportion = float(rect.width) / float(rect.height)
        return size, sizeX, sizeY, proportion

    def _calculate_steps(
        self, startColour: wx.Colour, endColour: wx.Colour, size: int
    ) -> Tuple[float, float, float]:
        """Calculate the gradient steps for the diagonal gradient drawing.

        Args:
            startColour (wx.Colour): The first colour of the gradient shading.
            endColour (wx.Colour): The second colour of the gradient shading.
            size (int): The size of the gradient.

        Returns:
            A tuple containing the rstep, gstep, and bstep.
        """
        # calculate gradient coefficients
        col2 = endColour
        col1 = startColour
        rstep = float(col2.Red() - col1.Red()) / float(size)
        gstep = float(col2.Green() - col1.Green()) / float(size)
        bstep = float(col2.Blue() - col1.Blue()) / float(size)
        return rstep, gstep, bstep

    def _draw_upper_triangle(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        startColour: wx.Colour,
        rstep: float,
        gstep: float,
        bstep: float,
        size: int,
        sizeX: int,
        sizeY: int,
        proportion: float,
        startAtUpperLeft: bool,
    ) -> None:
        """Draw the upper triangle of the diagonal gradient.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            startColour (wx.Colour): The first colour of the gradient shading.
            rstep (float): The red step of the gradient.
            gstep (float): The green step of the gradient.
            bstep (float): The blue step of the gradient.
            size (int): The size of the gradient.
            sizeX (int): The width of the gradient.
            sizeY (int): The height of the gradient.
            proportion (float): The proportion of the gradient.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the upper
                left corner of the rectangle, ``False`` to start at the upper right
                corner.
        """
        rf, gf, bf = 0.0, 0.0, 0.0
        # draw the upper triangle
        for i in range(size):
            currCol = wx.Colour(
                startColour.Red() + rf,
                startColour.Green() + gf,
                startColour.Blue() + bf,
            )
            dc.SetBrush(wx.Brush(currCol, wx.BRUSHSTYLE_SOLID))
            dc.SetPen(wx.Pen(currCol))
            self._draw_line_and_point(
                dc, rect, i, sizeX, sizeY, proportion, startAtUpperLeft
            )
            rf += rstep / 2
            gf += gstep / 2
            bf += bstep / 2

    def _draw_lower_tiangle(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        startColour: wx.Colour,
        rstep: float,
        gstep: float,
        bstep: float,
        size: int,
        sizeX: int,
        sizeY: int,
        proportion: float,
        startAtUpperLeft: bool,
    ) -> None:
        """Draw the lower triangle of the diagonal gradient.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            startColour (wx.Colour): The first colour of the gradient shading.
            rstep (float): The red step of the gradient.
            gstep (float): The green step of the gradient.
            bstep (float): The blue step of the gradient.
            size (int): The size of the gradient.
            sizeX (int): The width of the gradient.
            sizeY (int): The height of the gradient.
            proportion (float): The proportion of the gradient.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the upper
                left corner of the rectangle, ``False`` to start at the upper right
                corner.
        """
        rf = rstep * size / 2
        gf = gstep * size / 2
        bf = bstep * size / 2
        # draw the lower triangle
        for i in range(size):
            currCol = wx.Colour(
                startColour.Red() + rf,
                startColour.Green() + gf,
                startColour.Blue() + bf,
            )
            dc.SetBrush(wx.Brush(currCol, wx.BRUSHSTYLE_SOLID))
            dc.SetPen(wx.Pen(currCol))
            self._draw_line_and_point(
                dc, rect, i, sizeX, sizeY, proportion, startAtUpperLeft, lower=True
            )
            rf += rstep / 2
            gf += gstep / 2
            bf += bstep / 2

    def _draw_line_and_point(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        i: int,
        sizeX: int,
        sizeY: int,
        proportion: float,
        startAtUpperLeft: bool,
        lower: bool = False,
    ) -> None:
        """Draw a line and a point for the diagonal gradient.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            i (int): The current step in the gradient.
            sizeX (int): The width of the gradient.
            sizeY (int): The height of the gradient.
            proportion (float): The proportion of the gradient.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the upper
                left corner of the rectangle, ``False`` to start at the upper right
                corner.
            lower (bool): ``True`` to draw the lower triangle, ``False`` to draw the
            upper triangle.
        """
        if startAtUpperLeft:
            if rect.width > rect.height:
                if lower:
                    dc.DrawLine(
                        rect.x + i,
                        rect.y + sizeY,
                        rect.x + sizeX,
                        int(rect.y + proportion * i),
                    )
                    dc.DrawPoint(rect.x + sizeX, int(rect.y + proportion * i))
                else:
                    dc.DrawLine(
                        rect.x + i, rect.y, rect.x, int(rect.y + proportion * i)
                    )
                    dc.DrawPoint(rect.x, int(rect.y + proportion * i))
            else:
                if lower:
                    dc.DrawLine(
                        int(rect.x + proportion * i),
                        rect.y + sizeY,
                        rect.x + sizeX,
                        rect.y + i,
                    )
                    dc.DrawPoint(rect.x + sizeX, rect.y + i)
                else:
                    dc.DrawLine(
                        int(rect.x + proportion * i), rect.y, rect.x, rect.y + i
                    )
                    dc.DrawPoint(rect.x, rect.y + i)
        else:
            if rect.width > rect.height:
                if lower:
                    dc.DrawLine(
                        rect.x + i, rect.y + sizeY, rect.x + sizeX - i, rect.y + sizeY
                    )
                    dc.DrawPoint(rect.x + sizeX - i, rect.y + sizeY)
                else:
                    dc.DrawLine(
                        rect.x + sizeX - i,
                        rect.y,
                        rect.x + sizeX,
                        int(rect.y + proportion * i),
                    )
                    dc.DrawPoint(rect.x + sizeX, int(rect.y + proportion * i))
            else:
                xTo = max(int(rect.x + sizeX - proportion * i), rect.x)
                if lower:
                    dc.DrawLine(rect.x, rect.y + i, xTo, rect.y + sizeY)
                    dc.DrawPoint(xTo, rect.y + sizeY)
                else:
                    dc.DrawLine(xTo, rect.y, rect.x + sizeX, rect.y + i)
                    dc.DrawPoint(rect.x + sizeX, rect.y + i)

    def PaintCrescentGradientBox(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        startColour: wx.Colour,
        endColour: wx.Colour,
        concave: bool = True,
    ) -> None:
        """Paint a region with gradient colouring.

        The gradient is in crescent shape which fits the 2007 style.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            startColour (wx.Colour): The first colour of the gradient shading.
            endColour (wx.Colour): The second colour of the gradient shading.
            concave (bool): ``True`` for a concave effect, ``False`` for a convex one.
        """
        diagonalRectWidth = rect.GetWidth() / 4
        spare = rect.width - 4 * diagonalRectWidth
        leftRect = wx.Rect(rect.x, rect.y, diagonalRectWidth, rect.GetHeight())
        rightRect = wx.Rect(
            rect.x + 3 * diagonalRectWidth + spare,
            rect.y,
            diagonalRectWidth,
            rect.GetHeight(),
        )

        if concave:

            self.PaintStraightGradientBox(
                dc, rect, self.MixColours(startColour, endColour, 50), endColour
            )
            self.PaintDiagonalGradientBox(
                dc, leftRect, startColour, endColour, True, False
            )
            self.PaintDiagonalGradientBox(
                dc, rightRect, startColour, endColour, False, False
            )

        else:

            self.PaintStraightGradientBox(
                dc, rect, endColour, self.MixColours(endColour, startColour, 50)
            )
            self.PaintDiagonalGradientBox(
                dc, leftRect, endColour, startColour, False, False
            )
            self.PaintDiagonalGradientBox(
                dc, rightRect, endColour, startColour, True, False
            )

    def FrameColour(self) -> wx.Colour:
        """Return the surrounding colour for a control.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        return wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION)

    def BackgroundColour(self) -> wx.Colour:
        """Return the background colour of a control when not in focus.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        return self.LightColour(self.FrameColour(), 75)

    def HighlightBackgroundColour(self) -> wx.Colour:
        """Return the background colour of a control when it is in focus.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        return self.LightColour(self.FrameColour(), 60)

    def MixColours(
        self, firstColour: wx.Colour, secondColour: wx.Colour, percent: int
    ) -> wx.Colour:
        """Return mix of input colours.

        Args:
            firstColour (wx.Colour): The first colour to be mixed.
            secondColour (wx.Colour): The second colour to be mixed.
            percent (int): The relative percentage of `firstColour` with respect to
                `secondColour`.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        # calculate gradient coefficients
        redOffset = float(
            (secondColour.Red() * (100 - percent) / 100)
            - (firstColour.Red() * percent / 100)
        )
        greenOffset = float(
            (secondColour.Green() * (100 - percent) / 100)
            - (firstColour.Green() * percent / 100)
        )
        blueOffset = float(
            (secondColour.Blue() * (100 - percent) / 100)
            - (firstColour.Blue() * percent / 100)
        )

        return wx.Colour(
            firstColour.Red() + redOffset,
            firstColour.Green() + greenOffset,
            firstColour.Blue() + blueOffset,
        )

    @classmethod
    def RandomColour(cls) -> wx.Colour:
        """Create a random colour.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        r = random.randint(0, 255)  # Random value between 0-255
        g = random.randint(0, 255)  # Random value between 0-255
        b = random.randint(0, 255)  # Random value between 0-255
        return wx.Colour(r, g, b)

    def IsDark(self, colour: wx.Colour) -> bool:
        """Return whether a colour is dark or light.

        Args:
            colour (wx.Colour): A :class:`wx.Colour`.

        Returns:
            bool: ``True`` if the average RGB values are dark, ``False`` otherwise.
        """
        evg = (colour.Red() + colour.Green() + colour.Blue()) / 3
        return evg < 127

    @classmethod
    def TruncateText(cls, dc: wx.DC, text: str, maxWidth: int) -> Union[str, None]:
        """Truncate a given string to fit given width size.

        If the text does not fit into the given width it is truncated to fit.
        The format of the fixed text is ``truncate text ...``.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            text (str): The text to be (eventually) truncated.
            maxWidth (int): The maximum width allowed for the text.

        Returns:
            Union[str, None]: A string containing the (possibly) truncated text.
        """
        textLen = len(text)
        tempText = text
        rectSize = maxWidth

        fixedText = ""

        textW, _ = dc.GetTextExtent(text)

        if rectSize >= textW:
            return text

        # The text does not fit in the designated area, so we need to truncate it a bit
        suffix = ".."
        w, _ = dc.GetTextExtent(suffix)
        rectSize -= w

        for _ in range(textLen, -1, -1):
            textW, _ = dc.GetTextExtent(tempText)
            if rectSize >= textW:
                fixedText = tempText
                fixedText += ".."
                return fixedText

            tempText = tempText[:-1]

    def DrawButton(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        theme: int,
        state: int,
        input_: Union[None, bool, wx.Colour] = None,
    ) -> None:
        """Colour rectangle according to the theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            theme (int): The theme to use to draw the button.
            state (int): The button state.
            input_ (Union[None, bool, wx.Colour]): A flag used to call the right method.
        """
        if input_ is None or isinstance(input_, bool):
            self.DrawButtonTheme(dc, rect, theme, state, bool(input_))
        else:
            self.DrawButtonColour(dc, rect, theme, state, input_)

    def DrawButtonTheme(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        theme: int,
        state: int,
        useLightColours: bool = True,
    ):
        """Draw a button using the appropriate theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            theme (int): The theme to use to draw the button.
            state (int): The button state.
            useLightColours (bool): ``True`` to use light colours, ``False`` otherwise.
        """
        renderer = self._renderers[int(theme)]

        # Set background colour if non given by caller
        renderer.DrawButton(dc, rect, state, useLightColours)

    def DrawButtonColour(self, dc, rect, theme, state, colour):
        """Draw a button using the appropriate theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            theme (int): The theme to use to draw the button.
            state (int): The button state.
            colour (wx.Colour): A valid :class:`wx.Colour` instance.
        """
        renderer = self._renderers[theme]
        renderer.DrawButton(dc, rect, state, colour)

    def CanMakeWindowsTransparent(self) -> bool:
        """Check if the current OS supports transparancy.

        Returns:
            bool: ``True`` if the system supports transparency of toplevel windows,
                otherwise returns ``False``.
        """
        if wx.Platform == "__WXMSW__":
            version = wx.GetOsDescription()
            found = (
                version.find("XP") >= 0
                or version.find("2000") >= 0
                or version.find("NT") >= 0
            )
            return found
        elif wx.Platform == "__WXMAC__":
            return True
        else:
            return False

    def MakeWindowTransparent(self, wnd, amount):
        """Make a toplevel window transparent if the system supports it.

        On supported windows systems (Win2000 and greater), this function will make a
        frame window transparent by a certain amount.

        Args:
            wnd (wx.TopLevelWindow): The toplevel window to make transparent.
            amount (int): The window transparency to apply.
        """
        if wnd.GetSize() == (0, 0):
            return

        # This API call is not in all SDKs, only the newer ones,
        # so we will runtime bind this
        if wx.Platform == "__WXMSW__":
            hwnd = wnd.GetHandle()

            if not hasattr(self, "_winlib"):
                if _libimported == "MH":
                    self._winlib = win32api.LoadLibrary("user32")
                elif _libimported == "ctypes":
                    self._winlib = ctypes.windll.user32

            if _libimported == "MH":
                pSetLayeredWindowAttributes = win32api.GetProcAddress(
                    self._winlib, "SetLayeredWindowAttributes"
                )

                if pSetLayeredWindowAttributes is None:
                    return

                exstyle = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if 0 == (exstyle & 0x80000):
                    win32api.SetWindowLong(
                        hwnd, win32con.GWL_EXSTYLE, exstyle | 0x80000
                    )

                winxpgui.SetLayeredWindowAttributes(hwnd, 0, amount, 2)

            elif _libimported == "ctypes":
                style = self._winlib.GetWindowLongA(hwnd, 0xFFFFFFEC)
                style |= 0x00080000
                self._winlib.SetWindowLongA(hwnd, 0xFFFFFFEC, style)
                self._winlib.SetLayeredWindowAttributes(hwnd, 0, amount, 2)
        else:
            if not wnd.CanSetTransparent():
                return
            wnd.SetTransparent(amount)

    def DrawBitmapShadow(self, dc, rect, where=BottomShadow | RightShadow):
        """Draw a shadow using background bitmap.

        Assumption: the background was already drawn on the dc

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The bitmap's client rectangle.
            where (int): Where to draw the shadow. This can be any combination of the
                following bits:

                ===================== ======= =======================
                Shadow Settings        Value  Description
                ===================== ======= =======================
                ``RightShadow``             1 Right side shadow
                ``BottomShadow``            2 Not full bottom shadow
                ``BottomShadowFull``        4 Full bottom shadow
                ===================== ======= =======================
        """
        shadowSize = 5

        # the rect must be at least 5x5 pixels
        if rect.height < 2 * shadowSize or rect.width < 2 * shadowSize:
            return

        # Start by drawing the right bottom corner
        if where & BottomShadow or where & BottomShadowFull:
            dc.DrawBitmap(
                self._rightBottomCorner, rect.x + rect.width, rect.y + rect.height, True
            )

        # Draw right side shadow
        xx = rect.x + rect.width
        yy = rect.y + rect.height - shadowSize

        if where & RightShadow:
            while yy - rect.y > 2 * shadowSize:
                dc.DrawBitmap(self._right, xx, yy, True)
                yy -= shadowSize

            dc.DrawBitmap(self._rightTop, xx, yy - shadowSize, True)

        if where & BottomShadow:
            xx = rect.x + rect.width - shadowSize
            yy = rect.height + rect.y
            while xx - rect.x > 2 * shadowSize:
                dc.DrawBitmap(self._bottom, xx, yy, True)
                xx -= shadowSize

            dc.DrawBitmap(self._bottomLeft, xx - shadowSize, yy, True)

        if where & BottomShadowFull:
            xx = rect.x + rect.width - shadowSize
            yy = rect.height + rect.y
            while xx - rect.x >= 0:
                dc.DrawBitmap(self._bottom, xx, yy, True)
                xx -= shadowSize

            dc.DrawBitmap(self._bottom, xx, yy, True)

    def DropShadow(self, wnd: wx.TopLevelWindow, drop=True) -> None:
        """Add a shadow under the window (Windows only).

        Args:
            wnd (wx.TopLevelWindow): The window for which we are dropping a shadow.
            drop (bool): ``True`` to drop a shadow, ``False`` to remove it.
        """
        if not self.CanMakeWindowsTransparent() or not _libimported:
            return

        if "__WXMSW__" in wx.Platform:

            hwnd = wnd.GetHandle()

            if not hasattr(self, "_winlib"):
                if _libimported == "MH":
                    self._winlib = win32api.LoadLibrary("user32")
                elif _libimported == "ctypes":
                    self._winlib = ctypes.windll.user32

            if _libimported == "MH":
                csstyle = win32api.GetWindowLong(hwnd, win32con.GCL_STYLE)
            else:
                csstyle = self._winlib.GetWindowLongA(hwnd, win32con.GCL_STYLE)

            if drop:
                if csstyle & CS_DROPSHADOW:
                    return
                else:
                    csstyle |= CS_DROPSHADOW  # Nothing to be done
            else:
                if csstyle & CS_DROPSHADOW:
                    csstyle &= ~(CS_DROPSHADOW)
                else:
                    return  # Nothing to be done

            win32api.SetWindowLong(hwnd, win32con.GCL_STYLE, csstyle)

    def GetBitmapStartLocation(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        bitmap: wx.Bitmap,
        text: str = "",
        style: int = 0,
    ) -> Tuple[float, float]:
        """Return the top left `x` and `y` coordinates of the bitmap drawing.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The bitmap's client rectangle.
            bitmap (wx.Bitmap): The bitmap associated with the button.
            text (str): The button label.
            style (int): The button style. This can be one of the following bits:

                ============================== ======= ================================
                Button style                    Value  Description
                ============================== ======= ================================
                ``BU_EXT_XP_STYLE``               1    A button with a XP style
                ``BU_EXT_2007_STYLE``             2    A button with a MS Office 2007
                                                       style
                ``BU_EXT_LEFT_ALIGN_STYLE``       4    A left-aligned button
                ``BU_EXT_CENTER_ALIGN_STYLE``     8    A center-aligned button
                ``BU_EXT_RIGHT_ALIGN_STYLE``      16   A right-aligned button
                ``BU_EXT_RIGHT_TO_LEFT_STYLE``    32   A button suitable for
                                                       right-to-left languages
                ============================== ======= ================================


        Returns:
            Tuple[float, float]: A tuple containing the top left `x` and `y` coordinates
                of the bitmap drawing.
        """
        alignmentBuffer = self.GetAlignBuffer()

        # get the startLocationY
        fixedTextWidth = fixedTextHeight = 0

        if not text:
            fixedTextHeight = bitmap.GetHeight()
        else:
            fixedTextWidth, fixedTextHeight = dc.GetTextExtent(text)

        startLocationY = rect.y + (rect.height - fixedTextHeight) / 2

        # get the startLocationX
        if style & BU_EXT_RIGHT_TO_LEFT_STYLE:
            startLocationX = rect.x + rect.width - alignmentBuffer - bitmap.GetWidth()
        else:
            if style & BU_EXT_RIGHT_ALIGN_STYLE:
                maxWidth = (
                    rect.x + rect.width - (2 * alignmentBuffer) - bitmap.GetWidth()
                )  # the alignment is for both sides

                # get the truncated text. The text may stay as is, it is not a must that
                # is will be truncated
                fixedText = self.TruncateText(dc, text, maxWidth)

                # get the fixed text dimensions
                fixedTextWidth, _ = dc.GetTextExtent(fixedText)

                # calculate the start location
                startLocationX = maxWidth - fixedTextWidth

            elif style & BU_EXT_LEFT_ALIGN_STYLE:
                # calculate the start location
                startLocationX = alignmentBuffer

            else:  # meaning BU_EXT_CENTER_ALIGN_STYLE
                maxWidth = (
                    rect.x + rect.width - (2 * alignmentBuffer) - bitmap.GetWidth()
                )  # the alignment is for both sides

                # get the truncated text. The text may stay as is, it is not a must that
                # is will be truncated
                fixedText = self.TruncateText(dc, text, maxWidth)

                # get the fixed text dimensions
                fixedTextWidth, _ = dc.GetTextExtent(fixedText)

                if maxWidth > fixedTextWidth:
                    # calculate the start location
                    startLocationX = (maxWidth - fixedTextWidth) / 2

                else:
                    # calculate the start location
                    startLocationX = maxWidth - fixedTextWidth

        # it is very important to validate that the start location is not less than the
        # alignment buffer
        if startLocationX < alignmentBuffer:
            startLocationX = alignmentBuffer

        return startLocationX, startLocationY

    def GetTextStartLocation(
        self, dc: wx.DC, rect: wx.Rect, bitmap: wx.Bitmap, text: str, style: int = 0
    ) -> Tuple[float, float, Union[str, None]]:
        """Return the top left `x` and `y` coordinates of the text drawing.

        In case the text is too long, the text is being fixed (the text is cut and a
        '...' mark is added in the end).

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The text's client rectangle.
            bitmap (wx.Bitmap): The bitmap associated with the button.
            text (str): The button label.
            style (int): The button style.

        Returns:
            Tuple[float, float, Union[str, None]]: A tuple containing the top left `x`
                and `y` coordinates of the text drawing, plus the truncated version of
                the input `text`.

        See :meth:`~ArtManager.GetBitmapStartLocation`for a list of valid button styles.
        """
        alignmentBuffer = self.GetAlignBuffer()

        # get the bitmap offset
        bitmapOffset = 0
        if bitmap != wx.NullBitmap:
            bitmapOffset = bitmap.GetWidth()

        # get the truncated text.
        # The text may stay as is, it is not a must that it will be truncated
        maxWidth = (
            rect.x + rect.width - (2 * alignmentBuffer) - bitmapOffset
        )  # the alignment is for both sides
        fixedText = self.TruncateText(dc, text, maxWidth)

        # get the fixed text dimensions
        fixedTextWidth, fixedTextHeight = dc.GetTextExtent(fixedText)
        startLocationY = (rect.height - fixedTextHeight) / 2 + rect.y

        # get the startLocationX
        if style & BU_EXT_RIGHT_TO_LEFT_STYLE:
            startLocationX = maxWidth - fixedTextWidth + alignmentBuffer
        else:
            if style & BU_EXT_LEFT_ALIGN_STYLE:
                # calculate the start location
                startLocationX = bitmapOffset + alignmentBuffer
            elif style & BU_EXT_RIGHT_ALIGN_STYLE:
                # calculate the start location
                startLocationX = (
                    maxWidth - fixedTextWidth + bitmapOffset + alignmentBuffer
                )
            else:  # meaning wxBU_EXT_CENTER_ALIGN_STYLE
                # calculate the start location
                startLocationX = (
                    (maxWidth - fixedTextWidth) / 2 + bitmapOffset + alignmentBuffer
                )

        # it is very important to validate that the start location is not less than the
        # alignment buffer
        if startLocationX < alignmentBuffer:
            startLocationX = alignmentBuffer

        return startLocationX, startLocationY, fixedText

    def DrawTextAndBitmap(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        text: str,
        enable: bool = True,
        font: wx.Font = wx.NullFont,
        fontColour: wx.Colour = wx.BLACK,
        bitmap: wx.Bitmap = wx.NullBitmap,
        grayBitmap: wx.Bitmap = wx.NullBitmap,
        style: int = 0,
    ) -> None:
        """Draw the text & bitmap on the input dc.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The text and bitmap client rectangle.
            text (str): the button label.
            enable (bool): ``True`` if the button is enabled, ``False`` otherwise.
            font (wx.Font): The font to use to draw the text.
            fontColour (wx.Colour): The colour to use to draw the text.
            bitmap (wx.Bitmap): The bitmap associated with the button.
            grayBitmap (wx.Bitmap): A greyed-out version of the input `bitmap`
                representing a disabled bitmap.
            style (int): The button style.

        See: :meth:`~ArtManager.GetBitmapStartLocation` for a list of valid button
            styles.
        """
        # enable colours
        if enable:
            dc.SetTextForeground(fontColour)
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        # set the font
        if font.IsSameAs(wx.NullFont):
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

        dc.SetFont(font)

        startLocationX = startLocationY = 0.0

        if not bitmap.IsSameAs(wx.NullBitmap):
            # calculate the bitmap start location
            startLocationX, startLocationY = self.GetBitmapStartLocation(
                dc, rect, bitmap, text, style
            )

            # draw the bitmap
            if enable:
                dc.DrawBitmap(bitmap, startLocationX, startLocationY, True)
            else:
                dc.DrawBitmap(grayBitmap, startLocationX, startLocationY, True)

        # calculate the text start location
        location, labelOnly = self.GetAccelIndex(text)
        startLocationX, startLocationY, fixedText = self.GetTextStartLocation(
            dc, rect, bitmap, labelOnly, style
        )

        if fixedText is None:
            fixedText = ""

        # after all the calculations are finished, it is time to draw the text underline
        # the first letter that is marked with a '&'
        if location == -1 or font.GetUnderlined() or location >= len(fixedText):
            # draw the text
            dc.DrawText(fixedText, startLocationX, startLocationY)
        else:
            # underline the first '&'
            before = fixedText[0:location]
            underlineLetter = fixedText[location]
            after = fixedText[location + 1:]

            # before
            dc.DrawText(before, startLocationX, startLocationY)

            # underlineLetter
            if "__WXGTK__" not in wx.Platform:
                w1, _ = dc.GetTextExtent(before)
                font.SetUnderlined(True)
                dc.SetFont(font)
                dc.DrawText(underlineLetter, startLocationX + w1, startLocationY)
            else:
                w1, _ = dc.GetTextExtent(before)
                dc.DrawText(underlineLetter, startLocationX + w1, startLocationY)

                # Draw the underline ourselves since using the Underline in GTK,
                # causes the line to be too close to the letter
                uderlineLetterW, uderlineLetterH = dc.GetTextExtent(underlineLetter)

                curPen = dc.GetPen()
                dc.SetPen(wx.BLACK_PEN)

                dc.DrawLine(
                    startLocationX + w1,
                    startLocationY + uderlineLetterH - 2,
                    startLocationX + w1 + uderlineLetterW,
                    startLocationY + uderlineLetterH - 2,
                )
                dc.SetPen(curPen)

            # after
            w2, _ = dc.GetTextExtent(underlineLetter)
            font.SetUnderlined(False)
            dc.SetFont(font)
            dc.DrawText(after, startLocationX + w1 + w2, startLocationY)

    def CalcButtonBestSize(self, label: str, bmp: wx.Bitmap) -> wx.Size:
        """Return the best fit size for the supplied label & bitmap.

        Args:
            label (str): The button label.
            bmp (wx.Bitmap): The bitmap associated with the button.

        Returns:
            wx.Size: Representing the best fit size for the supplied label & bitmap.
        """
        if "__WXMSW__" in wx.Platform:
            HEIGHT = 22
        else:
            HEIGHT = 26

        dc = wx.MemoryDC()
        dc.SelectBitmap(wx.Bitmap(1, 1))

        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        width, height, _ = dc.GetFullMultiLineTextExtent(label)

        width += 2 * self.GetAlignBuffer()

        if bmp.IsOk():
            # allocate extra space for the bitmap
            heightBmp = bmp.GetHeight() + 2
            if height < heightBmp:
                height = heightBmp

            width += bmp.GetWidth() + 2

        if height < HEIGHT:
            height = HEIGHT

        dc.SelectBitmap(wx.NullBitmap)

        return wx.Size(width, height)

    def GetMenuFaceColour(self) -> wx.Colour:
        """Return the colour used for the menu foreground.

        Returns:
            wx.Colour: The colour used for the menu foreground.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetMenuFaceColour()

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for enabled menu items.

        Returns:
            wx.Colour: The colour used for enabled menu items.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetTextColourEnable()

    def GetTextColourDisable(self) -> wx.Font:
        """Return the colour used for disabled menu items.

        Returns:
            wx.Colour: The colour used for disabled menu items.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetTextColourDisable()

    def GetFont(self) -> wx.Font:
        """Return the font used by this theme.

        Returns:
            wx.Font: The font used by this theme.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetFont()

    def GetAccelIndex(self, label: str) -> Tuple[int, str]:
        """Return the mnemonic index and the label without the ampersand mnemonic.

        (e.g. 'lab&el' ==> will result in 3 and labelOnly = label).

        Args:
            label (str): A string containing an ampersand.

        Returns:
            Tuple[int, str]: A tuple containing the mnemonic index of the label and the
                label stripped of the ampersand mnemonic.
        """
        indexAccel = 0
        while True:
            indexAccel = label.find("&", indexAccel)
            if indexAccel == -1:
                return indexAccel, label
            if label[indexAccel: indexAccel + 2] == "&&":
                label = label[0:indexAccel] + label[indexAccel + 1:]
                indexAccel += 1
            else:
                break

        labelOnly = label[0:indexAccel] + label[indexAccel + 1:]

        return indexAccel, labelOnly

    def GetThemeBaseColour(
        self, useLightColours: Union[None, bool] = True
    ) -> wx.Colour:
        """Return the theme base colour.

        If no theme is active, return the active caption colour lightened by 30%.

        Args:
            useLightColours (Union[None, bool]): ``True`` to use light colours,
                ``False`` otherwise.

        Returns:
            wx.Colour: The theme base colour or the 30% lightened active caption colour.
        """
        if not useLightColours and not self.IsDark(self.FrameColour()):
            return wx.Colour("GOLD")
        else:
            return self.LightColour(self.FrameColour(), 30)

    def GetAlignBuffer(self) -> int:
        """Return the padding buffer for a text or bitmap.

        Returns:
            int: An integer representing the padding buffer.
        """
        return self._alignmentBuffer

    def SetMenuTheme(self, theme: int) -> None:
        """Set the menu theme, possible values (Style2007, StyleXP, StyleVista).

        Args:
            theme (int): A rendering theme class, either `StyleXP`, `Style2007` or
                `StyleVista`.
        """
        self._menuTheme = theme

    def GetMenuTheme(self) -> int:
        """Return the currently used menu theme.

        Returns:
            int: An int containing the currently used theme for the menu.
        """
        return self._menuTheme

    def AddMenuTheme(self, render: RendererBase) -> int:
        """Add a new theme to the stock.

        Args:
            render (RendererBase): A rendering theme class, which must be derived from
                :class:`RendererBase`.

        Returns:
            int: An integer representing the size of the renderers dictionary.
        """
        # Add new theme
        lastRenderer = len(self._renderers)
        self._renderers[lastRenderer] = render

        return lastRenderer

    def SetMS2007ButtonSunken(self, sunken: bool) -> None:
        """Set MS 2007 button style sunken or not.

        Args:
            sunken (bool): ``True`` to have a sunken border effect, ``False`` otherwise.
        """
        self._ms2007sunken = sunken

    def GetMS2007ButtonSunken(self) -> bool:
        """Return the sunken flag for MS 2007 buttons.

        Returns:
            bool: ``True`` if the MS 2007 buttons are sunken, ``False`` otherwise.
        """
        return self._ms2007sunken

    def GetMBVerticalGradient(self) -> bool:
        """Return ``True`` if the menu bar should be painted with vertical gradient.

        Returns:
            bool: A boolean indicating whether the menu bar should be painted with
                vertical gradient.
        """
        return self._verticalGradient

    def SetMBVerticalGradient(self, v: bool) -> None:
        """Set the menu bar gradient style.

        Args:
            v (bool): ``True`` for a vertical shaded gradient, ``False`` otherwise.
        """
        self._verticalGradient = v

    def DrawMenuBarBorder(self, border: bool) -> None:
        """Enable menu border drawing (XP style only).

        Args:
            border (bool): ``True`` to draw the menubar border, ``False`` otherwise.
        """
        self._drowMBBorder = border

    def GetMenuBarBorder(self) -> bool:
        """Return menu bar border drawing flag.

        Returns:
            bool: ``True`` if the menu bar border is to be drawn, ``False`` otherwise.
        """
        return self._drowMBBorder

    def GetMenuBgFactor(self) -> int:
        """Return the visibility depth of the menu in Metallic style.

        The higher the value, the menu bar will look more raised.

        Returns:
            int: An integer representing the visibility depth of the menu.
        """
        return self._menuBgFactor

    def DrawDragSash(self, rect: wx.Rect) -> None:
        """Draw resize sash.

        Args:
            rect (wx.Rect): The sash client rectangle.
        """
        dc = wx.ScreenDC()
        mem_dc = wx.MemoryDC()

        bmp = wx.Bitmap(rect.width, rect.height)
        mem_dc.SelectObject(bmp)
        mem_dc.SetBrush(wx.WHITE_BRUSH)
        mem_dc.SetPen(wx.Pen(wx.WHITE, 1))
        mem_dc.DrawRectangle(0, 0, rect.width, rect.height)

        dc.Blit(rect.x, rect.y, rect.width, rect.height, mem_dc, 0, 0, wx.XOR)

    def TakeScreenShot(self, rect: wx.Rect, bmp: wx.Bitmap) -> None:
        """Take a screenshot of the screen at given position & size (rect).

        Args:
            rect (wx.Rect): The screen rectangle we wish to capture.
            bmp (wx.Bitmap): Currently unused.
        """
        # Create a DC for the whole screen area
        dcScreen = wx.ScreenDC()

        # Create a Bitmap that will later on hold the screenshot image
        # Note that the Bitmap must have a size big enough to hold the screenshot
        # -1 means using the current default colour depth
        bmp = wx.Bitmap(rect.width, rect.height)

        # Create a memory DC that will be used for actually taking the screenshot
        memDC = wx.MemoryDC()

        # Tell the memory DC to use our Bitmap
        # all drawing action on the memory DC will go to the Bitmap now
        memDC.SelectObject(bmp)

        # Blit (in this case copy)
        # the actual screen on the memory DC and thus the Bitmap
        memDC.Blit(
            0,  # Copy to this X coordinate
            0,  # Copy to this Y coordinate
            rect.width,  # Copy this width
            rect.height,  # Copy this height
            dcScreen,  # From where do we copy?
            rect.x,  # What's the X offset in the original DC?
            rect.y,  # What's the Y offset in the original DC?
        )

        # Select the Bitmap out of the memory DC by selecting a new uninitialized Bitmap
        memDC.SelectObject(wx.NullBitmap)

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The toolbar's client rectangle.
        """
        renderer = self._renderers[self.GetMenuTheme()]

        # Set background colour if non given by caller
        renderer.DrawToolBarBg(dc, rect)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The menubar's client rectangle.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        # Set background colour if non given by caller
        renderer.DrawMenuBarBg(dc, rect)

    def SetMenuBarColour(self, scheme: str) -> None:
        """Set the menu bar colour scheme to use.

        Args:
            scheme (str): A string representing a colour scheme (i.e., 'Default',
                'Dark', 'Dark Olive Green', 'Generic').
        """
        self._menuBarColourScheme = scheme
        # set default colour
        if scheme in self._colourSchemeMap:
            self._menuBarBgColour = self._colourSchemeMap[scheme]

    def GetMenuBarColourScheme(self) -> str:
        """Return the current colour scheme.

        Returns:
            str: A string representing the current colour scheme.
        """
        return self._menuBarColourScheme

    def GetMenuBarFaceColour(self) -> wx.Colour:
        """Return the menu bar face colour.

        Returns:
            wx.Colour: The menu bar face colour.
        """
        return self._menuBarBgColour

    def GetMenuBarSelectionColour(self) -> wx.Colour:
        """Return the menu bar selection colour.

        Returns:
            wx.Colour: The menu bar selection colour.
        """
        return self._menuBarSelColour

    def InitColours(self) -> None:
        """Initialise the colour map."""
        self._colourSchemeMap = {
            _("Default"): wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE),
            _("Dark"): wx.BLACK,
            _("Dark Olive Green"): wx.Colour("DARK OLIVE GREEN"),
            _("Generic"): wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION),
        }

    def GetColourSchemes(self) -> List[str]:
        """Return the available colour schemes.

        Returns:
            List[str]: A list of strings representing the available colour schemes.
        """
        return list(self._colourSchemeMap)

    def CreateGreyBitmap(self, bmp):
        """Create a grey bitmap image from the input bitmap.

        Args:
            bmp (wx.Bitmap): A valid :class:`wx.Bitmap` object to be greyed out.

        Returns:
            wx.Bitmap: A greyed-out representation of the input bitmap.
        """
        img = bmp.ConvertToImage()
        return wx.Bitmap(img.ConvertToGreyscale())

    def GetRaiseToolbar(self) -> bool:
        """Return ``True`` if we are dropping a shadow under a toolbar.

        Returns:
            bool: A boolean indicating whether a shadow is dropped under a toolbar.
        """
        return self._raiseTB

    def SetRaiseToolbar(self, rais: bool) -> None:
        """Enable/disable toobar shadow drop.

        Args:
            rais (bool): ``True`` to drop a shadow below a toolbar, ``False`` otherwise.
        """
        self._raiseTB = rais
