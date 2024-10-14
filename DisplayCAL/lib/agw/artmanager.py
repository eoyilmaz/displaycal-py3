# -*- coding: utf-8 -*-
"""Drawing routines and customizations for AGW widgets `LabelBook` and `FlatMenu`."""

import io
import random
import sys
from typing import Callable, Type

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

# ---------------------------------------------------------------------------- #
# Class DCSaver
# ---------------------------------------------------------------------------- #

# Constants
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002

_: Callable[[str], str] = wx.GetTranslation


class DCSaver(object):
    """Construct a DC saver.

    The dc is copied as-is.
    """

    def __init__(self, pdc: wx.DC) -> None:
        """Initialize the default class constructor.

        Args:
            pdc: an instance of :class:`wx.DC`.
        """
        self._pdc: wx.DC = pdc
        self._pen: wx.Pen = pdc.GetPen()
        self._brush: wx.Brush = pdc.GetBrush()

    def __del__(self) -> None:
        """While destructing, restores the dc pen and brush."""
        if self._pdc:
            self._pdc.SetPen(self._pen)
            self._pdc.SetBrush(self._brush)


# ---------------------------------------------------------------------------- #
# Class RendererBase                                                                    # noqa: SC100
# ---------------------------------------------------------------------------- #


class RendererBase(object):
    """Base class for all theme renderers."""

    def __init__(self) -> None:
        """Initialize the default class constructor.

        Intentionally empty.
        """
        pass

    def DrawButtonBorders(
        self, dc: wx.DC, rect: wx.Rect, penColour: wx.Colour, brushColour: wx.Colour
    ) -> None:
        """Draws borders for buttons.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            penColour (wx.Colour): a valid :class:`wx.Colour` for the pen border.
            brushColour (wx.Colour): a valid :class:`wx.Colour` for the brush.
        """
        # Keep old pen and brush
        dcsaver = DCSaver(dc)

        # Set new pen and brush
        dc.SetPen(wx.Pen(penColour))
        dc.SetBrush(wx.Brush(brushColour))

        # Draw the rectangle
        dc.DrawRectangle(rect)

        # Restore old pen and brush
        del dcsaver

    def DrawBitmapArea(
        self,
        dc: wx.DC,
        xpm_name: str,
        rect: wx.Rect,
        baseColour: wx.Colour,
        flipSide: bool,
    ) -> None:
        """
        Draws the area below a bitmap and the bitmap itself using a gradient shading.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            xpm_name (str): a name of a XPM bitmap.
            rect (wx.Rect): the bitmap client rectangle.
            baseColour (wx.Colour): a valid :class:`wx.Colour` for the bitmap
                background.
            flipSide (bool): ``True`` to flip the gradient direction,
                ``False`` otherwise.
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
        """
        Draws borders for a bitmap.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            penColour (wx.Colour): a valid :class:`wx.Colour` for the pen border.
            bitmapBorderUpperLeftPen (wx.Colour): a valid :class:`wx.Colour` for the pen
                upper left border.
        """
        # Keep old pen and brush
        dcsaver = DCSaver(dc)

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

        # Restore old pen and brush
        del dcsaver

    def GetMenuFaceColour(self) -> wx.Colour:
        """Return the foreground colour for the menu.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE), 80
        )

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for text colour when enabled.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return wx.BLACK

    def GetTextColourDisable(self) -> wx.Colour:
        """Return the colour used for text colour when disabled.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT), 30
        )

    def GetFont(self) -> wx.Font:
        """Return the font used for text.

        Returns:
            An instance of :class:`wx.Font`.
        """
        return wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

    def DrawButton(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input: None | bool | wx.Colour = None,
    ) -> None:
        """Draw a button using the appropriate theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            input (None | bool | wx.Colour): a flag used to call the right method.

        Raises:
            NotImplementedError: This method must be implemented in derived classes.
        """
        raise NotImplementedError(
            "DrawButton method must be implemented in derived classes"
        )

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """
        Draws the toolbar background according to the active theme.

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
        """
        Draws the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menu bar's client rectangle.

        Raises:
            NotImplementedError: This method must be implemented in derived classes.
        """
        raise NotImplementedError(
            "DrawMenuBarBg method must be implemented in derived classes"
        )


# ---------------------------------------------------------------------------- #
# Class RendererXP                                                                      # noqa: SC100
# ---------------------------------------------------------------------------- #


class RendererXP(RendererBase):
    """Xp-Style renderer."""

    def __init__(self) -> None:
        """Construct the default class."""
        RendererBase.__init__(self)

    def DrawButton(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input: None | bool | wx.Colour = None,
    ) -> None:
        """Draws a button using the XP theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            input (None | bool | wx.Colour): a flag used to call the right method.
        """
        if input is None or isinstance(input, bool):
            self.DrawButtonTheme(dc, rect, state, input)
        else:
            self.DrawButtonColour(dc, rect, state, input)

    def DrawButtonTheme(
        self, dc: wx.DC, rect: wx.Rect, state: int, useLightColours: None | bool
    ) -> None:
        """Draws a button using the XP theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            useLightColours (None | bool): ``True`` to use light colours,
                ``False`` otherwise.
        """
        # switch according to the status
        if state == ControlFocus:
            penColour: wx.Colour = ArtManager.Get().FrameColour()
            brushColour: wx.Colour = ArtManager.Get().BackgroundColour()
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
        """Draws a button using the XP theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            colour (wx.Colour): a valid :class:`wx.Colour` instance.
        """
        # switch according to the status
        if state == ControlFocus:
            penColour: wx.Colour = colour
            brushColour: wx.Colour = ArtManager.Get().LightColour(colour, 75)
        elif state == ControlPressed:
            penColour = colour
            brushColour = ArtManager.Get().LightColour(colour, 60)
        else:
            penColour = colour
            brushColour = ArtManager.Get().LightColour(colour, 75)

        # Draw the button borders
        self.DrawButtonBorders(dc, rect, penColour, brushColour)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draws the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menu bar's client rectangle.
        """
        # For office style, we simple draw a rectangle with a gradient colouring
        artMgr: ArtManager = ArtManager.Get()
        vertical: bool = artMgr.GetMBVerticalGradient()

        # Keep old pen and brush
        dcsaver = DCSaver(dc)

        # fill with gradient
        startColour: wx.Colour = artMgr.GetMenuBarFaceColour()
        if artMgr.IsDark(startColour):
            startColour = artMgr.LightColour(startColour, 50)

        endColour: wx.Colour = artMgr.LightColour(startColour, 90)
        artMgr.PaintStraightGradientBox(dc, rect, startColour, endColour, vertical)

        # Draw the border
        if artMgr.GetMenuBarBorder():
            dc.SetPen(wx.Pen(startColour))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(rect)

        # Restore old pen and brush
        del dcsaver

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draws the toolbar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the toolbar's client rectangle.
        """
        artMgr: ArtManager = ArtManager.Get()

        if not artMgr.GetRaiseToolbar():
            return

        # For office style, we simple draw a rectangle with a gradient colouring
        vertical: bool = artMgr.GetMBVerticalGradient()

        # Keep old pen and brush
        dcsaver = DCSaver(dc)

        # fill with gradient
        startColour: wx.Colour = artMgr.GetMenuBarFaceColour()
        if artMgr.IsDark(startColour):
            startColour = artMgr.LightColour(startColour, 50)

        startColour = artMgr.LightColour(startColour, 20)

        endColour: wx.Colour = artMgr.LightColour(startColour, 90)
        artMgr.PaintStraightGradientBox(dc, rect, startColour, endColour, vertical)
        artMgr.DrawBitmapShadow(dc, rect)

        # Restore old pen and brush
        del dcsaver

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for text colour when enabled.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return wx.BLACK


# ---------------------------------------------------------------------------- #
# Class RendererMSOffice2007                                                            # noqa: SC100
# ---------------------------------------------------------------------------- #


class RendererMSOffice2007(RendererBase):
    """Windows MS Office 2007 style."""

    def __init__(self) -> None:
        """Construct the default class."""
        RendererBase.__init__(self)

    def GetColoursAccordingToState(self, state: int) -> tuple[int, int, int, int]:
        """Return a tuple according to the menu item state.

        Args:
            state (int): one of the following bits:
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
        input: None | bool | wx.Colour = None,
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            input (None | bool | wx.Colour): a flag used to call the right method.
        """
        if input is None or isinstance(input, bool):
            self.DrawButtonTheme(dc, rect, state, input)
        else:
            self.DrawButtonColour(dc, rect, state, input)

    def DrawButtonTheme(
        self, dc: wx.DC, rect: wx.Rect, state: int, useLightColours: None | bool
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            useLightColours (None | bool): ``True`` to use light colours,
                ``False`` otherwise.
        """
        self.DrawButtonColour(
            dc, rect, state, ArtManager.Get().GetThemeBaseColour(useLightColours)
        )

    def DrawButtonColour(
        self, dc: wx.DC, rect: wx.Rect, state: int, colour: wx.Colour
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            colour (wx.Colour): a valid :class:`wx.Colour` instance.
        """
        artMgr: ArtManager = ArtManager.Get()

        # Keep old pen and brush
        dcsaver = DCSaver(dc)

        # Define the rounded rectangle base on the given rect                           # noqa: SC100
        # we need an array of 9 points for it
        baseColour: wx.Colour = colour

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

        topStartColour: wx.Colour = artMgr.LightColour(baseColour, upperBoxTopPercent)
        topEndColour: wx.Colour = artMgr.LightColour(baseColour, upperBoxBottomPercent)
        bottomStartColour: wx.Colour = artMgr.LightColour(
            baseColour, lowerBoxTopPercent
        )
        bottomEndColour: wx.Colour = artMgr.LightColour(
            baseColour, lowerBoxBottomPercent
        )

        artMgr.PaintStraightGradientBox(dc, top, topStartColour, topEndColour)
        artMgr.PaintStraightGradientBox(dc, bottom, bottomStartColour, bottomEndColour)

        rr = wx.Rect(rect.x, rect.y, rect.width, rect.height)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        frameColour: wx.Colour = artMgr.LightColour(baseColour, 60)
        dc.SetPen(wx.Pen(frameColour))
        dc.DrawRectangle(rr)

        wc: wx.Colour = artMgr.LightColour(baseColour, 80)
        dc.SetPen(wx.Pen(wc))
        rr.Deflate(1, 1)
        dc.DrawRectangle(rr)

        # Restore old pen and brush
        del dcsaver

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menu bar's client rectangle.
        """
        # Keep old pen and brush
        dcsaver = DCSaver(dc)
        artMgr: ArtManager = ArtManager.Get()
        baseColour: wx.Colour = artMgr.GetMenuBarFaceColour()

        dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.DrawRectangle(rect)

        # Define the rounded rectangle base on the given rect                           # noqa: SC100
        # we need an array of 9 points for it
        regPts: list[wx.Point] = [wx.Point() for _ in range(9)]
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
        factor: int = artMgr.GetMenuBgFactor()

        leftPt1 = wx.Point(rect.x, rect.y + (rect.height / factor))
        rightPt1 = wx.Point(rect.x + rect.width, rect.y + (rect.height / factor))

        leftPt2 = wx.Point(rect.x, rect.y + (rect.height / factor) * (factor - 1))
        rightPt2 = wx.Point(
            rect.x + rect.width, rect.y + (rect.height / factor) * (factor - 1)
        )

        # Define the top region
        topReg: list[wx.Point] = [wx.Point() for _ in range(7)]
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

        topStartColour: wx.Colour = artMgr.LightColour(baseColour, 90)
        topEndColour: wx.Colour = artMgr.LightColour(baseColour, 60)
        bottomStartColour: wx.Colour = artMgr.LightColour(baseColour, 40)
        bottomEndColour: wx.Colour = artMgr.LightColour(baseColour, 20)

        topRegion = wx.Region(topReg)

        artMgr.PaintGradientRegion(dc, topRegion, topStartColour, topEndColour)
        artMgr.PaintStraightGradientBox(dc, bottom, bottomStartColour, bottomEndColour)
        artMgr.PaintStraightGradientBox(dc, middle, topEndColour, bottomStartColour)

        # Restore old pen and brush
        del dcsaver

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the toolbar's client rectangle.
        """
        artMgr: ArtManager = ArtManager.Get()

        if not artMgr.GetRaiseToolbar():
            return

        # Keep old pen and brush
        dcsaver = DCSaver(dc)

        baseColour: wx.Colour = artMgr.GetMenuBarFaceColour()
        baseColour = artMgr.LightColour(baseColour, 20)

        dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.DrawRectangle(rect)

        radius = 2

        # Define the rounded rectangle base on the given rect                           # noqa: SC100
        # we need an array of 9 points for it
        regPts: list[wx.Point] = [wx.Point() for _ in range(9)]

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
        factor: int = artMgr.GetMenuBgFactor()

        leftPt1 = wx.Point(rect.x, rect.y + (rect.height / factor))
        rightPt1 = wx.Point(rect.x + rect.width, rect.y + (rect.height / factor))

        leftPt2 = wx.Point(rect.x, rect.y + (rect.height / factor) * (factor - 1))
        rightPt2 = wx.Point(
            rect.x + rect.width, rect.y + (rect.height / factor) * (factor - 1)
        )

        # Define the top region
        topReg: list[wx.Point] = [wx.Point() for _ in range(7)]
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

        topStartColour: wx.Colour = artMgr.LightColour(baseColour, 90)
        topEndColour: wx.Colour = artMgr.LightColour(baseColour, 60)
        bottomStartColour: wx.Colour = artMgr.LightColour(baseColour, 40)
        bottomEndColour: wx.Colour = artMgr.LightColour(baseColour, 20)

        topRegion = wx.Region(topReg)

        artMgr.PaintGradientRegion(dc, topRegion, topStartColour, topEndColour)
        artMgr.PaintStraightGradientBox(dc, bottom, bottomStartColour, bottomEndColour)
        artMgr.PaintStraightGradientBox(dc, middle, topEndColour, bottomStartColour)

        artMgr.DrawBitmapShadow(dc, rect)

        # Restore old pen and brush
        del dcsaver

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for text colour when enabled.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return wx.BLACK


# ---------------------------------------------------------------------------- #
# Class ArtManager
# ---------------------------------------------------------------------------- #


class ArtManager(wx.EvtHandler):
    """This class provides utilities for creating shadows and adjusting colors."""

    _alignmentBuffer = 7
    _menuTheme: int = StyleXP
    _verticalGradient = False
    _renderers: dict[int, RendererBase] = {}
    _bmpShadowEnabled = False
    _ms2007sunken = False
    _drowMBBorder = True
    _menuBgFactor = 5
    _menuBarColourScheme: str = _("Default")
    _raiseTB = True
    _bitmaps: dict[str, wx.Bitmap] = {}
    _transparency = 255

    def __init__(self) -> None:
        """Construct the default class."""
        wx.EvtHandler.__init__(self)
        self._menuBarBgColour: wx.Colour = wx.SystemSettings.GetColour(
            wx.SYS_COLOUR_3DFACE
        )

        # connect an event handler to the system colour change event
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self.OnSysColourChange)

        # Initialize the menu bar selection colour
        self._menuBarSelColour = wx.Colour(0, 0, 0)  # Default to black

    def SetTransparency(self, amount: int) -> None:
        """Set the alpha channel value for transparent windows.

        Args:
            amount (int): the actual transparency value (between 0 and 255).

        Raises:
            Exception: if the `amount` parameter is lower than ``0`` or greater
                than ``255``.
        """
        if self._transparency == amount:
            return

        if amount < 0 or amount > 255:
            raise Exception("Invalid transparency value")

        self._transparency: int = amount

    def GetTransparency(self) -> int:
        """Return the alpha channel value for transparent windows.

        Returns:
            An integer representing the alpha channel value.
        """
        return self._transparency

    def ConvertToBitmap(
        self, xpm: list[str] | bytes, alpha: None | list[int] = None
    ) -> wx.Bitmap:
        """Convert the given image to a bitmap, optionally overlaying an alpha channel.

        Args:
            xpm (list[str] | bytes): a list of strings formatted as XPM or a
                bytes object.
            alpha (None | list[int]): a list of alpha values (integers),
                the same size as the xpm bitmap.

        Returns:
            An instance of :class:`wx.Bitmap`.

        Raises:
            TypeError: If `xpm` is not a list of strings or a bytes object.
        """
        if alpha is not None:

            if isinstance(xpm, bytes):
                img: wx.Image = wx.ImageFromStream(io.BytesIO(xpm))
            else:
                img = wx.Bitmap(xpm).ConvertToImage()

            x: int = img.GetWidth()
            y: int = img.GetHeight()
            img.InitAlpha()
            for jj in range(y):
                for ii in range(x):
                    img.SetAlpha(ii, jj, alpha[jj * x + ii])

        else:

            if isinstance(xpm, bytes):
                img = wx.ImageFromStream(io.BytesIO(xpm))
            else:
                # Ensure xpm is a list of strings before joining                        # noqa: SC100
                if isinstance(xpm, list):
                    xpm_data: bytes = "\n".join(xpm).encode("utf-8")
                else:
                    raise TypeError("xpm must be a list of strings or a bytes object")

                img = wx.ImageFromStream(io.BytesIO(xpm_data))

        return wx.Bitmap(img)

    def Initialize(self) -> None:
        """Initialize the bitmaps and colours."""

        # create wxBitmaps from the xpm's                                               # noqa: SC100
        def ensure_strings(xpm_data: list[str] | list[bytes]) -> list[str]:
            return [
                (
                    x
                    if isinstance(x, str)
                    else (
                        x.tobytes().decode("utf-8")
                        if isinstance(x, memoryview)
                        else x.decode("utf-8")
                    )
                )
                for x in xpm_data
            ]

        self._rightBottomCorner: wx.Bitmap = self.ConvertToBitmap(
            ensure_strings(shadow_center_xpm), shadow_center_alpha
        )
        self._bottom: wx.Bitmap = self.ConvertToBitmap(
            ensure_strings(shadow_bottom_xpm), shadow_bottom_alpha
        )
        self._bottomLeft: wx.Bitmap = self.ConvertToBitmap(
            ensure_strings(shadow_bottom_left_xpm), shadow_bottom_left_alpha
        )
        self._rightTop: wx.Bitmap = self.ConvertToBitmap(
            ensure_strings(shadow_right_top_xpm), shadow_right_top_alpha
        )
        self._right: wx.Bitmap = self.ConvertToBitmap(
            ensure_strings(shadow_right_xpm), shadow_right_alpha
        )

        # initialise the colour map
        self.InitColours()
        self.SetMenuBarColour(self._menuBarColourScheme)

        # Create common bitmaps
        self.FillStockBitmaps()

    def FillStockBitmaps(self) -> None:
        """Initialize few standard bitmaps."""
        bmp: wx.Bitmap = self.ConvertToBitmap(arrow_down, alpha=None)
        bmp.SetMask(wx.Mask(bmp, wx.Colour(0, 128, 128)))
        self._bitmaps.update({"arrow_down": bmp})

        bmp = self.ConvertToBitmap(arrow_up, alpha=None)
        bmp.SetMask(wx.Mask(bmp, wx.Colour(0, 128, 128)))
        self._bitmaps.update({"arrow_up": bmp})

    def GetStockBitmap(self, name: str) -> wx.Bitmap:
        """Return a bitmap from a stock.

        Args:
            name (str): the bitmap name.

        Returns:
            The stock bitmap, if `name` was found in the stock bitmap dictionary.
                Otherwise, :class:`NullBitmap` is returned.
        """
        return self._bitmaps.get(name, wx.NullBitmap)

    @classmethod
    def Get(cls: Type["ArtManager"]) -> "ArtManager":
        """Accessor to the unique art manager object.

        Returns:
            An instance of :class:`ArtManager`.
        """
        if not hasattr(cls, "_instance"):
            cls._instance: "ArtManager" = cls()
            cls._instance.Initialize()

            # Initialize the renderers                                                  # noqa: SC100
            if StyleXP not in cls._renderers:
                cls._renderers[StyleXP] = RendererXP()
            if Style2007 not in cls._renderers:
                cls._renderers[Style2007] = RendererMSOffice2007()

        return cls._instance

    @classmethod
    def Free(cls: Type["ArtManager"]) -> None:
        """Destructor for the unique art manager object."""
        if hasattr(cls, "_instance"):
            del cls._instance

    def OnSysColourChange(self, event: wx.SysColourChangedEvent) -> None:
        """Handle the ``wx.EVT_SYS_COLOUR_CHANGED`` event for :class:`ArtManager`.

        Args:
            event (wx.SysColourChangedEvent): a :class:`SysColourChangedEvent`
                event to be processed.
        """
        # reinitialise the colour map
        self.InitColours()

    def LightColour(self, colour: wx.Colour, percent: int) -> wx.Colour:
        """Return light contrast of `colour`.

        The colour returned is from the scale of `colour` ==> white.

        Args:
            colour (wx.Colour): the input colour to be brightened,
                an instance of :class:`wx.Colour`.
            percent (int): determines how light the colour will be.
                `percent` = ``100`` returns white, `percent` = ``0`` returns `colour`.

        Returns:
            A light contrast of the input `colour`, an instance of :class:`wx.Colour`.
        """
        end_colour: wx.Colour = wx.WHITE
        rd: float = end_colour.Red() - colour.Red()
        gd: float = end_colour.Green() - colour.Green()
        bd: float = end_colour.Blue() - colour.Blue()
        high = 100

        # We take the percent way of the colour from colour ==> white
        i: int = percent
        r: float = colour.Red() + ((i * rd * 100) / high) / 100
        g: float = colour.Green() + ((i * gd * 100) / high) / 100
        b: float = colour.Blue() + ((i * bd * 100) / high) / 100
        a: float = colour.Alpha()

        return wx.Colour(int(r), int(g), int(b), int(a))

    def DarkColour(self, colour: wx.Colour, percent: int) -> wx.Colour:
        """Like :meth:`~ArtManager.LightColour`, but creates a darker colour by `percent`.

        Args:
            colour (wx.Colour): the input colour to be darkened,
                an instance of :class:`wx.Colour`.
            percent (int): determines how dark the colour will be.
                `percent` = ``100`` returns black, `percent` = ``0`` returns `colour`.

        Returns:
            A dark contrast of the input `colour`, an instance of :class:`wx.Colour`.
        """
        end_colour: wx.Colour = wx.BLACK
        rd: float = end_colour.Red() - colour.Red()
        gd: float = end_colour.Green() - colour.Green()
        bd: float = end_colour.Blue() - colour.Blue()
        high = 100

        # We take the percent way of the colour from colour ==> black
        i: int = percent
        r: float = colour.Red() + ((i * rd * 100) / high) / 100
        g: float = colour.Green() + ((i * gd * 100) / high) / 100
        b: float = colour.Blue() + ((i * bd * 100) / high) / 100

        return wx.Colour(int(r), int(g), int(b))

    def PaintStraightGradientBox(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        startColour: wx.Colour,
        endColour: wx.Colour,
        vertical: bool = True,
    ) -> None:
        """Paint the rectangle with gradient colouring.

        The gradient lines are either horizontal or vertical.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            startColour (wx.Colour): the first colour of the gradient shading.
            endColour (wx.Colour): the second colour of the gradient shading.
            vertical (bool): ``True`` for gradient colouring in the vertical direction,
                ``False`` for horizontal shading.
        """
        # Keep old pen and brush
        dcsaver = DCSaver(dc)

        if vertical:
            high: int = rect.GetHeight() - 1
            direction: int = wx.SOUTH
        else:
            high = rect.GetWidth() - 1
            direction = wx.EAST

        if high < 1:
            return

        dc.GradientFillLinear(rect, startColour, endColour, direction)

        # Restore old pen and brush
        del dcsaver

    def PaintGradientRegion(
        self,
        dc: wx.DC,
        region: wx.Region,
        startColour: wx.Colour,
        endColour: wx.Colour,
        vertical: bool = True,
    ) -> None:
        """Paint a region with gradient colouring.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            region (wx.Region): a region to be filled with gradient shading
                (an instance of :class:`Region`).
            startColour (wx.Colour): the first colour of the gradient shading.
            endColour (wx.Colour): the second colour of the gradient shading.
            vertical (bool): ``True`` for gradient colouring in the vertical direction,
                ``False`` for horizontal shading.
        """
        # The way to achieve non-rectangle
        memDC = wx.MemoryDC()
        rect: wx.Rect = region.GetBox()
        bitmap = wx.Bitmap(rect.width, rect.height)
        memDC.SelectObject(bitmap)

        # Colour the whole rectangle with gradient
        rr = wx.Rect(0, 0, rect.width, rect.height)
        self.PaintStraightGradientBox(memDC, rr, startColour, endColour, vertical)

        # Convert the region to a black and white bitmap with the white pixels
        # being inside the region we draw the bitmap over the gradient coloured
        # rectangle, with mask set to white,
        # this will cause our region to be coloured with the gradient,
        # while area outside the region will be painted with black.
        # then we simply draw the bitmap to the dc with mask set to black
        tmpRegion = wx.Region(rect.x, rect.y, rect.width, rect.height)
        tmpRegion.Offset(-rect.x, -rect.y)
        regionBmp: wx.Bitmap = tmpRegion.ConvertToBitmap()
        regionBmp.SetMask(wx.Mask(regionBmp, wx.WHITE))

        # The function ConvertToBitmap() return a rectangle bitmap which is
        # shorter by 1 pixel on the height and width (this is correct behavior,         # noqa: SC100
        # since DrawLine does not include the second point as part of the line)
        # we fix this issue by drawing our own line at the bottom and left side
        # of the rectangle
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

        The gradient lines are diagonal and may start from the upper left corner
        or from the upper right corner.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            startColour (wx.Colour): the first colour of the gradient shading.
            endColour (wx.Colour): the second colour of the gradient shading.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the
                upper left corner of the rectangle,
                ``False`` to start at the upper right corner.
            trimToSquare (bool): ``True`` to trim the gradient lines in a square.
        """
        # gradient fill from colour 1 to colour 2 with top to bottom
        if rect.height < 1 or rect.width < 1:
            return

        # Save the current pen and brush
        savedPen: wx.Pen = dc.GetPen()
        savedBrush: wx.Brush = dc.GetBrush()

        size, sizeX, sizeY, proportion = self.calculate_sizes(rect, trimToSquare)
        rstep, gstep, bstep = self.calculate_steps(startColour, endColour, size)

        self.draw_upper_triangle(
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
        self.draw_lower_triangle(
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

    def calculate_sizes(
        self, rect: wx.Rect, trimToSquare: bool
    ) -> tuple[int, int, int, float]:
        """Calculate the sizes for the gradient drawing.

        Args:
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            trimToSquare (bool): ``True`` to trim the gradient lines in a square.

        Returns:
            A tuple containing the size, sizeX, sizeY, and proportion.
        """
        if rect.width > rect.height:
            if trimToSquare:
                size: int = rect.height
                sizeX: int = rect.height - 1
                sizeY: int = rect.height - 1
                proportion = 1.0  # Square proportion is 1.0
            else:
                proportion: float = float(rect.height) / float(rect.width)
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

    def calculate_steps(
        self, startColour: wx.Colour, endColour: wx.Colour, size: int
    ) -> tuple[float, float, float]:
        """Calculate the gradient steps for the diagonal gradient drawing.

        Args:
            startColour (wx.Colour): the first colour of the gradient shading.
            endColour (wx.Colour): the second colour of the gradient shading.
            size (int): the size of the gradient.

        Returns:
            A tuple containing the rstep, gstep, and bstep.
        """
        # calculate gradient coefficients
        col2: wx.Colour = endColour
        col1: wx.Colour = startColour
        rstep: float = float(col2.Red() - col1.Red()) / float(size)
        gstep: float = float(col2.Green() - col1.Green()) / float(size)
        bstep: float = float(col2.Blue() - col1.Blue()) / float(size)
        return rstep, gstep, bstep

    def draw_upper_triangle(
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
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            startColour (wx.Colour): the first colour of the gradient shading.
            rstep (float): the red step of the gradient.
            gstep (float): the green step of the gradient.
            bstep (float): the blue step of the gradient.
            size (int): the size of the gradient.
            sizeX (int): the width of the gradient.
            sizeY (int): the height of the gradient.
            proportion (float): the proportion of the gradient.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the
                upper left corner of the rectangle,
                ``False`` to start at the upper right corner.
        """
        rf: float = 0
        gf: float = 0
        bf: float = 0
        # draw the upper triangle
        for i in range(size):
            currCol = wx.Colour(
                startColour.Red() + rf,
                startColour.Green() + gf,
                startColour.Blue() + bf,
            )
            dc.SetBrush(wx.Brush(currCol, wx.BRUSHSTYLE_SOLID))
            dc.SetPen(wx.Pen(currCol))
            self.draw_line_and_point(
                dc, rect, i, sizeX, sizeY, proportion, startAtUpperLeft
            )
            rf += rstep / 2
            gf += gstep / 2
            bf += bstep / 2

    def draw_lower_triangle(
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
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            startColour (wx.Colour): the first colour of the gradient shading.
            rstep (float): the red step of the gradient.
            gstep (float): the green step of the gradient.
            bstep (float): the blue step of the gradient.
            size (int): the size of the gradient.
            sizeX (int): the width of the gradient.
            sizeY (int): the height of the gradient.
            proportion (float): the proportion of the gradient.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the
                upper left corner of the rectangle,
                ``False`` to start at the upper right corner.
        """
        rf: float = rstep * size / 2
        gf: float = gstep * size / 2
        bf: float = bstep * size / 2
        # draw the lower triangle
        for i in range(size):
            currCol = wx.Colour(
                startColour.Red() + rf,
                startColour.Green() + gf,
                startColour.Blue() + bf,
            )
            dc.SetBrush(wx.Brush(currCol, wx.BRUSHSTYLE_SOLID))
            dc.SetPen(wx.Pen(currCol))
            self.draw_line_and_point(
                dc, rect, i, sizeX, sizeY, proportion, startAtUpperLeft, lower=True
            )
            rf += rstep / 2
            gf += gstep / 2
            bf += bstep / 2

    def draw_line_and_point(
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
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            i (int): the current step in the gradient.
            sizeX (int): the width of the gradient.
            sizeY (int): the height of the gradient.
            proportion (float): the proportion of the gradient.
            startAtUpperLeft (bool): ``True`` to start the gradient lines at the
                upper left corner of the rectangle,
                ``False`` to start at the upper right corner.
            lower (bool): ``True`` to draw the lower triangle,
                ``False`` to draw the upper triangle.
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
                xTo: int = max(int(rect.x + sizeX - proportion * i), rect.x)
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
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            startColour (wx.Colour): the first colour of the gradient shading.
            endColour (wx.Colour): the second colour of the gradient shading.
            concave (bool): ``True`` for a concave effect, ``False`` for a convex one.
        """
        diagonalRectWidth: float = rect.GetWidth() / 4
        spare: int = rect.width - 4 * diagonalRectWidth
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
            An instance of :class:`wx.Colour`.
        """
        return wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION)

    def BackgroundColour(self) -> wx.Colour:
        """Return the background colour of a control when not in focus.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return self.LightColour(self.FrameColour(), 75)

    def HighlightBackgroundColour(self) -> wx.Colour:
        """Return the background colour of a control when it is in focus.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return self.LightColour(self.FrameColour(), 60)

    def MixColours(
        self, firstColour: wx.Colour, secondColour: wx.Colour, percent: int
    ) -> wx.Colour:
        """Return mix of input colours.

        Args:
            firstColour (wx.Colour): the first colour to be mixed,
                an instance of :class:`wx.Colour`.
            secondColour (wx.Colour): the second colour to be mixed,
                an instance of :class:`wx.Colour`.
            percent (int): the relative percentage of `firstColour` with
                respect to `secondColour`.

        Returns:
            An instance of :class:`wx.Colour`.
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

    def RandomColour(self) -> wx.Colour:
        """Create a random colour.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        r: int = random.randint(0, 255)  # Random value between 0-255
        g: int = random.randint(0, 255)  # Random value between 0-255
        b: int = random.randint(0, 255)  # Random value between 0-255

        return wx.Colour(r, g, b)

    def IsDark(self, colour: wx.Colour) -> bool:
        """Return whether a colour is dark or light.

        Args:
            colour (wx.Colour): an instance of :class:`wx.Colour`.

        Returns:
            A boolean indicating whether the average RGB values are dark.
        """
        evg: float = (colour.Red() + colour.Green() + colour.Blue()) / 3

        if evg < 127:
            return True

        return False

    def TruncateText(self, dc: wx.DC, text: str, maxWidth: int) -> str | None:
        """Truncate a given string to fit given width size.

        If the text does not fit into the given width it is truncated to fit.
        The format of the fixed text is ``truncate text ...``.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            text (str): the text to be (eventually) truncated.
            maxWidth (int): the maximum width allowed for the text.

        Returns:
            A string containing the (possibly) truncated text.
        """
        textLen: int = len(text)
        tempText: str = text
        rectSize: int = maxWidth

        fixedText: str = ""

        textW: int = dc.GetTextExtent(text)[0]

        if rectSize >= textW:
            return text

        # The text does not fit in the designated area, so we need to truncate it a bit
        suffix = ".."
        w: int = dc.GetTextExtent(suffix)[0]
        rectSize -= w

        for _ in range(textLen, -1, -1):
            textW = dc.GetTextExtent(tempText)[0]
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
        input: None | bool | wx.Colour = None,
    ) -> None:
        """Colour rectangle according to the theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the rectangle to be filled with gradient shading.
            theme (int): the theme to use to draw the button.
            state (int): the button state.
            input (None | bool | wx.Colour): a flag used to call the right method.
        """
        if input is None or isinstance(input, bool):
            use_light_colours = bool(input)  # Convert input to boolean
            self.DrawButtonTheme(dc, rect, theme, state, use_light_colours)
        else:
            self.DrawButtonColour(dc, rect, theme, state, input)

    def DrawButtonTheme(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        theme: int,
        state: int,
        useLightColours: bool = True,
    ) -> None:
        """Draws a button using the appropriate theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            theme (int): the theme to use to draw the button.
            state (int): the button state.
            useLightColours (bool): ``True`` to use light colours, ``False`` otherwise.

        Raises:
            ValueError: If the `theme` value is not a valid integer.
        """
        # Ensure theme is an integer
        if isinstance(theme, str):
            try:
                theme = int(theme)
            except ValueError:
                raise ValueError(f"Invalid theme value: {theme}")

        renderer: RendererBase = self._renderers[theme]

        # Set background colour if non given by caller
        renderer.DrawButton(dc, rect, state, useLightColours)

    def DrawButtonColour(
        self, dc: wx.DC, rect: wx.Rect, theme: int, state: int, colour: wx.Colour
    ) -> None:
        """Draws a button using the appropriate theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            theme (int): the theme to use to draw the button.
            state (int): the button state.
            colour (wx.Colour): a valid :class:`wx.Colour` instance.
        """
        renderer: RendererBase = self._renderers[theme]
        renderer.DrawButton(dc, rect, state, colour)

    def CanMakeWindowsTransparent(self) -> bool:
        """Use internally.

        Returns:
            A boolean indicating whether the system supports transparency of
                toplevel windows.
        """
        if wx.Platform == "__WXMSW__":
            version: str = wx.GetOsDescription()
            found: bool = (
                version.find("XP") >= 0
                or version.find("2000") >= 0
                or version.find("NT") >= 0
            )
            return found
        elif wx.Platform == "__WXMAC__":
            return True
        else:
            return False

    def MakeWindowTransparent(self, wnd: wx.TopLevelWindow, amount: int) -> None:
        """Use internally.

        Makes a toplevel window transparent if the system supports it.

        Args:
            wnd (wx.TopLevelWindow): the toplevel window to make transparent,
                an instance of :class:`wx.TopLevelWindow`.
            amount (int): the window transparency to apply.
        """
        if wnd.GetSize() == (0, 0):
            return

        # this API call is not in all SDKs, only the newer ones,
        # so we will runtime bind this
        if sys.platform == "win32":
            hwnd: int = wnd.GetHandle()

            if not hasattr(self, "_winlib"):
                import ctypes

                self._winlib: WinDLL = ctypes.windll.user32

            # Get the extended window style
            exstyle: int = self._winlib.GetWindowLongA(hwnd, GWL_EXSTYLE)
            if exstyle == 0:
                return

            # Set the WS_EX_LAYERED style                                               # noqa: SC100
            exstyle |= WS_EX_LAYERED
            self._winlib.SetWindowLongA(hwnd, GWL_EXSTYLE, exstyle)

            # Set the transparency
            self._winlib.SetLayeredWindowAttributes(hwnd, 0, amount, LWA_ALPHA)
        else:
            if not wnd.CanSetTransparent():
                return
            wnd.SetTransparent(amount)

    def DrawBitmapShadow(
        self, dc: wx.DC, rect: wx.Rect, where: int = BottomShadow | RightShadow
    ) -> None:
        """
        Draws a shadow using background bitmap.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the bitmap's client rectangle.
            where (int): where to draw the shadow.
                This can be any combination of the following bits:
                ========================== ======= =============================
                Shadow Settings             Value  Description
                ========================== ======= =============================
                ``RightShadow``                  1 Right side shadow
                ``BottomShadow``                 2 Not full bottom shadow
                ``BottomShadowFull``             4 Full bottom shadow
                ========================== ======= =============================
        """
        shadowSize = 5

        # the rect must be at least 5x5 pixels                                          # noqa: SC100
        if rect.height < 2 * shadowSize or rect.width < 2 * shadowSize:
            return

        # Start by drawing the right bottom corner
        if where & BottomShadow or where & BottomShadowFull:
            dc.DrawBitmap(
                self._rightBottomCorner, rect.x + rect.width, rect.y + rect.height, True
            )

        # Draw right side shadow
        xx: int = rect.x + rect.width
        yy: int = rect.y + rect.height - shadowSize

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

    def DropShadow(self, wnd: wx.TopLevelWindow, drop: bool = True) -> None:
        """Add a shadow under the window (Windows only).

        Args:
            wnd (wx.TopLevelWindow): the window for which we are dropping a shadow,
                an instance of :class:`TopLevelWindow`.
            drop (bool): ``True`` to drop a shadow, ``False`` to remove it.
        """
        if not self.CanMakeWindowsTransparent():
            return

        if "__WXMSW__" in wx.Platform:

            hwnd: int = wnd.GetHandle()

            if not hasattr(self, "_winlib"):
                    try:
                        import win32api

                        self._winlib = win32api.LoadLibrary("user32")
                    except ImportError:
                        import ctypes

                        self._winlib = ctypes.windll.user32

            import win32con

            try:
                import win32api

                csstyle: int = win32api.GetWindowLong(hwnd, win32con.GCL_STYLE)
            except (ImportError, AttributeError):
                csstyle = self._winlib.GetWindowLongA(hwnd, win32con.GCL_STYLE)

            if drop:
                if csstyle & CS_DROPSHADOW:
                    return
                else:
                    csstyle |= CS_DROPSHADOW  # Nothing to be done
            else:
                if csstyle & CS_DROPSHADOW:
                    csstyle &= ~CS_DROPSHADOW
                else:
                    return  # Nothing to be done

            import win32api

            win32api.SetWindowLong(hwnd, win32con.GCL_STYLE, csstyle)

    def GetBitmapStartLocation(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        bitmap: wx.Bitmap,
        text: str = "",
        style: int = 0,
    ) -> tuple[float, float]:
        """Return the top left `x` and `y` coordinates of the bitmap drawing.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the bitmap's client rectangle.
            bitmap (wx.Bitmap): the bitmap associated with the button.
            text (str): the button label.
            style (int): the button style. This can be one of the following bits:
                ============================== ======= =========================
                Button style                    Value  Description
                ============================== ======= =========================
                ``BU_EXT_XP_STYLE``               1    A button with a XP style
                ``BU_EXT_2007_STYLE``             2    A button with a MS Office
                                                        2007 style
                ``BU_EXT_LEFT_ALIGN_STYLE``       4    A left-aligned button
                ``BU_EXT_CENTER_ALIGN_STYLE``     8    A center-aligned button
                ``BU_EXT_RIGHT_ALIGN_STYLE``      16   A right-aligned button
                ``BU_EXT_RIGHT_TO_LEFT_STYLE``    32   A button suitable for
                                                        right-to-left languages
                ============================== ======= =========================

        Returns:
            A tuple containing the top left `x` and `y` coordinates of the
                bitmap drawing.
        """
        alignmentBuffer: int = self.GetAlignBuffer()

        # get the startLocationY
        fixedTextWidth: int = 0
        fixedTextHeight: int = 0

        if not text:
            fixedTextHeight = bitmap.GetHeight()
        else:
            fixedTextWidth, fixedTextHeight = dc.GetTextExtent(text)

        startLocationY: float = rect.y + (rect.height - fixedTextHeight) / 2

        # get the startLocationX
        if style & BU_EXT_RIGHT_TO_LEFT_STYLE:
            startLocationX: float = (
                rect.x + rect.width - alignmentBuffer - bitmap.GetWidth()
            )
        else:
            if style & BU_EXT_RIGHT_ALIGN_STYLE:
                maxWidth: int = (
                    rect.x + rect.width - (2 * alignmentBuffer) - bitmap.GetWidth()
                )
                fixedText: str | None = self.TruncateText(dc, text, maxWidth)
                fixedTextWidth = dc.GetTextExtent(fixedText)[0]
                startLocationX = maxWidth - fixedTextWidth
            elif style & BU_EXT_LEFT_ALIGN_STYLE:
                startLocationX = alignmentBuffer
            else:  # meaning BU_EXT_CENTER_ALIGN_STYLE
                maxWidth = (
                    rect.x + rect.width - (2 * alignmentBuffer) - bitmap.GetWidth()
                )
                fixedText = self.TruncateText(dc, text, maxWidth)
                fixedTextWidth = dc.GetTextExtent(fixedText)[0]
                if maxWidth > fixedTextWidth:
                    startLocationX = (maxWidth - fixedTextWidth) / 2
                else:
                    startLocationX = maxWidth - fixedTextWidth

        # it is very important to validate that the start location is not less
        # than the alignment buffer
        if startLocationX < alignmentBuffer:
            startLocationX = alignmentBuffer

        return startLocationX, startLocationY

    def GetTextStartLocation(
        self, dc: wx.DC, rect: wx.Rect, bitmap: wx.Bitmap, text: str, style: int = 0
    ) -> tuple[float, float, str | None]:
        """Return the top left `x` and `y` coordinates of the text drawing.

        In case the text is too long,
        the text is being fixed (the text is cut and a '...' mark is added in the end).

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the text's client rectangle.
            bitmap (wx.Bitmap): the bitmap associated with the button.
            text (str): the button label.
            style (int): the button style.

        Returns:
            A tuple containing the top left `x` and `y` coordinates of the text drawing,
                plus the truncated version of the input `text`.

        See:
            :meth:`~ArtManager.GetBitmapStartLocation` for a list of valid
                button styles.
        """
        alignmentBuffer: int = self.GetAlignBuffer()

        # get the bitmap offset
        bitmapOffset = 0
        if bitmap != wx.NullBitmap:
            bitmapOffset: int = bitmap.GetWidth()

        # get the truncated text.
        # The text may stay as is, it is not a must that it will be truncated
        maxWidth: int = rect.x + rect.width - (2 * alignmentBuffer) - bitmapOffset
        fixedText: str | None = self.TruncateText(dc, text, maxWidth)

        # get the fixed text dimensions
        fixedTextWidth, fixedTextHeight = dc.GetTextExtent(fixedText)
        startLocationY: float = (rect.height - fixedTextHeight) / 2 + rect.y

        # get the startLocationX
        if style & BU_EXT_RIGHT_TO_LEFT_STYLE:
            startLocationX: float = maxWidth - fixedTextWidth + alignmentBuffer
        else:
            if style & BU_EXT_LEFT_ALIGN_STYLE:
                startLocationX = bitmapOffset + alignmentBuffer
            elif style & BU_EXT_RIGHT_ALIGN_STYLE:
                startLocationX = (
                    maxWidth - fixedTextWidth + bitmapOffset + alignmentBuffer
                )
            else:  # meaning BU_EXT_CENTER_ALIGN_STYLE
                startLocationX = (
                    (maxWidth - fixedTextWidth) / 2 + bitmapOffset + alignmentBuffer
                )

        # it is very important to validate that the start location is not less
        # than the alignment buffer
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
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the text and bitmap client rectangle.
            text (str): the button label.
            enable (bool): ``True`` if the button is enabled, ``False`` otherwise.
            font (wx.Font): the font to use to draw the text,
                an instance of :class:`wx.Font`.
            fontColour (wx.Colour): the colour to use to draw the text,
                an instance of :class:`wx.Colour`.
            bitmap (wx.Bitmap): the bitmap associated with the button,
                an instance of :class:`wx.Bitmap`.
            grayBitmap (wx.Bitmap): a greyed-out version of the input `bitmap`
                representing a disabled bitmap, an instance of :class:`wx.Bitmap`.
            style (int): the button style.

        See:
            :meth:`~ArtManager.GetBitmapStartLocation` for a list of valid
                button styles.
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

        startLocationX: float = 0
        startLocationY: float = 0

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

        # Ensure fixedText is a string
        if fixedText is None:
            fixedText: None | str = ""

        # after all the calculations are finished, it is time to draw the text
        # underline the first letter that is marked with a '&'
        if location == -1 or font.GetUnderlined() or location >= len(fixedText):
            # draw the text
            dc.DrawText(fixedText, startLocationX, startLocationY)
        else:
            # underline the first '&'
            before: str = fixedText[0:location]
            underlineLetter: str = fixedText[location]
            after: str = fixedText[location + 1 :]

            # before
            dc.DrawText(before, startLocationX, startLocationY)

            # underlineLetter
            if "__WXGTK__" not in wx.Platform:
                w1: int = dc.GetTextExtent(before)[0]
                font.SetUnderlined(True)
                dc.SetFont(font)
                dc.DrawText(underlineLetter, startLocationX + w1, startLocationY)
            else:
                w1 = dc.GetTextExtent(before)[0]
                dc.DrawText(underlineLetter, startLocationX + w1, startLocationY)

                # Draw the underline ourselves since using the Underline in GTK,        # noqa: SC100
                # causes the line to be too close to the letter
                uderlineLetterW, uderlineLetterH = dc.GetTextExtent(underlineLetter)

                curPen: wx.Pen = dc.GetPen()
                dc.SetPen(wx.BLACK_PEN)

                dc.DrawLine(
                    startLocationX + w1,
                    startLocationY + uderlineLetterH - 2,
                    startLocationX + w1 + uderlineLetterW,
                    startLocationY + uderlineLetterH - 2,
                )
                dc.SetPen(curPen)

            # after
            w2: int = dc.GetTextExtent(underlineLetter)[0]
            font.SetUnderlined(False)
            dc.SetFont(font)
            dc.DrawText(after, startLocationX + w1 + w2, startLocationY)

    def CalcButtonBestSize(self, label: str, bmp: wx.Bitmap) -> wx.Size:
        """Return the best fit size for the supplied label & bitmap.

        Args:
            label (str): the button label.
            bmp (wx.Bitmap): the bitmap associated with the button,
                an instance of :class:`wx.Bitmap`.

        Returns:
            A :class:`wx.Size` object representing the best fit size.
        """
        if "__WXMSW__" in wx.Platform:
            HEIGHT = 22
        else:
            HEIGHT = 26

        dc = wx.MemoryDC()
        bitmap = wx.Bitmap(1, 1)
        dc.SelectObject(bitmap)

        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        width, height = dc.GetMultiLineTextExtent(label)[0:2]

        width += 2 * self.GetAlignBuffer()

        if bmp.IsOk():
            # allocate extra space for the bitmap
            heightBmp: int = bmp.GetHeight() + 2
            if height < heightBmp:
                height: int = heightBmp

            width += bmp.GetWidth() + 2

        if height < HEIGHT:
            height = HEIGHT

        dc.SelectObject(wx.NullBitmap)

        return wx.Size(width, height)

    def GetMenuFaceColour(self) -> wx.Colour:
        """Return the colour used for the menu foreground.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        renderer: RendererBase = self._renderers[self.GetMenuTheme()]
        return renderer.GetMenuFaceColour()

    def GetTextColourEnable(self) -> wx.Colour:
        """Return the colour used for enabled menu items.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        renderer: RendererBase = self._renderers[self.GetMenuTheme()]
        return renderer.GetTextColourEnable()

    def GetTextColourDisable(self) -> wx.Colour:
        """Return the colour used for disabled menu items.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        renderer: RendererBase = self._renderers[self.GetMenuTheme()]
        return renderer.GetTextColourDisable()

    def GetFont(self) -> wx.Font:
        """Return the font used by this theme.

        Returns:
            An instance of :class:`wx.Font`.
        """
        renderer: RendererBase = self._renderers[self.GetMenuTheme()]
        return renderer.GetFont()

    def GetAccelIndex(self, label: str) -> tuple[int, str]:
        """Return the mnemonic index and the label without the ampersand mnemonic.

        (e.g. 'lab&el' ==> will result in 3 and labelOnly = label).

        Args:
            label (str): a string containing an ampersand.

        Returns:
            A tuple containing the mnemonic index of the label and the label
                stripped of the ampersand mnemonic.
        """
        indexAccel = 0
        while True:
            indexAccel: int = label.find("&", indexAccel)
            if indexAccel == -1:
                return indexAccel, label
            if label[indexAccel : indexAccel + 2] == "&&":
                label = label[0:indexAccel] + label[indexAccel + 1 :]
                indexAccel += 1
            else:
                break

        labelOnly: str = label[0:indexAccel] + label[indexAccel + 1 :]

        return indexAccel, labelOnly

    def GetThemeBaseColour(self, useLightColours: bool | None = True) -> wx.Colour:
        """Return the theme base colour or the active caption colour lightened by 30%.

        Args:
            useLightColours (bool | None): ``True`` to use light colours,
                ``False`` otherwise.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        if not useLightColours and not self.IsDark(self.FrameColour()):
            return wx.Colour("GOLD")
        else:
            return self.LightColour(self.FrameColour(), 30)

    def GetAlignBuffer(self) -> int:
        """Return the padding buffer for a text or bitmap.

        Returns:
            An integer representing the padding buffer.
        """
        return self._alignmentBuffer

    def SetMenuTheme(self, theme: int) -> None:
        """Set the menu theme, possible values (Style2007, StyleXP, StyleVista).

        Args:
            theme (int): a rendering theme class, either `StyleXP`,
                `Style2007` or `StyleVista`.
        """
        self._menuTheme = theme

    def GetMenuTheme(self) -> int:
        """Return the currently used menu theme.

        Returns:
            An integer representing the currently used theme for the menu.
        """
        return self._menuTheme

    def AddMenuTheme(self, render: RendererBase) -> int:
        """Add a new theme to the stock.

        Args:
            render (RendererBase): a rendering theme class,
                which must be derived from :class:`RendererBase`.

        Returns:
            An integer representing the size of the renderers dictionary.
        """
        # Add new theme
        lastRenderer: int = len(self._renderers)
        self._renderers[lastRenderer] = render

        return lastRenderer

    def SetMS2007ButtonSunken(self, sunken: bool) -> None:
        """Set MS 2007 button style sunken or not.

        Args:
            sunken (bool): ``True`` to have a sunken border effect, ``False`` otherwise.
        """
        self._ms2007sunken: bool = sunken

    def GetMS2007ButtonSunken(self) -> bool:
        """Return the sunken flag for MS 2007 buttons.

        Returns:
            A boolean indicating whether the MS 2007 buttons are sunken.
        """
        return self._ms2007sunken

    def GetMBVerticalGradient(self) -> bool:
        """Return ``True`` if the menu bar should be painted with vertical gradient.

        Returns:
            A boolean indicating whether the menu bar should be painted with
                vertical gradient.
        """
        return self._verticalGradient

    def SetMBVerticalGradient(self, v: bool) -> None:
        """Set the menu bar gradient style.

        Args:
            v (bool): ``True`` for a vertical shaded gradient, ``False`` otherwise.
        """
        self._verticalGradient: bool = v

    def DrawMenuBarBorder(self, border: bool) -> None:
        """Enable menu border drawing (XP style only).

        Args:
            border (bool): ``True`` to draw the menubar border, ``False`` otherwise.
        """
        self._drowMBBorder: bool = border

    def GetMenuBarBorder(self) -> bool:
        """Return menu bar border drawing flag.

        Returns:
            A boolean indicating whether the menu bar border is to be drawn.
        """
        return self._drowMBBorder

    def GetMenuBgFactor(self) -> int:
        """Get the visibility depth of the menu in Metallic style.

        The higher the value, the menu bar will look more raised.

        Returns:
            An integer representing the visibility depth of the menu.
        """
        return self._menuBgFactor

    def DrawDragSash(self, rect: wx.Rect) -> None:
        """Draws resize sash.

        Args:
            rect (wx.Rect): the sash client rectangle.
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
            rect (wx.Rect): the screen rectangle we wish to capture.
            bmp (wx.Bitmap): currently unused.
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

        # Blit (in this case copy) the actual screen on the memory DC and thus          # noqa: SC100
        # the Bitmap
        memDC.Blit(
            0,  # Copy to this X coordinate
            0,  # Copy to this Y coordinate
            rect.width,  # Copy this width
            rect.height,  # Copy this height
            dcScreen,  # From where do we copy?
            rect.x,  # What's the X offset in the original DC?
            rect.y,  # What's the Y offset in the original DC?
        )

        # Select the Bitmap out of the memory DC by selecting a new
        # uninitialized Bitmap
        memDC.SelectObject(wx.NullBitmap)

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draws the toolbar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the toolbar's client rectangle.
        """
        renderer: RendererBase = self._renderers[self.GetMenuTheme()]

        # Set background colour if non given by caller
        renderer.DrawToolBarBg(dc, rect)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:
        """Draws the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menubar's client rectangle.
        """
        renderer: RendererBase = self._renderers[self.GetMenuTheme()]
        # Set background colour if non given by caller
        renderer.DrawMenuBarBg(dc, rect)

    def SetMenuBarColour(self, scheme: str) -> None:
        """Set the menu bar colour scheme to use.

        Args:
            scheme (str): a string representing a colour scheme
                (i.e., 'Default', 'Dark', 'Dark Olive Green', 'Generic').
        """
        self._menuBarColourScheme = scheme
        # set default colour
        if scheme in self._colourSchemeMap:
            self._menuBarBgColour = self._colourSchemeMap[scheme]

    def GetMenuBarColourScheme(self) -> str:
        """Return the current colour scheme.

        Returns:
            A string representing the current colour scheme.
        """
        return self._menuBarColourScheme

    def GetMenuBarFaceColour(self) -> wx.Colour:
        """Return the menu bar face colour.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return self._menuBarBgColour

    def GetMenuBarSelectionColour(self) -> wx.Colour:
        """Return the menu bar selection colour.

        Returns:
            An instance of :class:`wx.Colour`.
        """
        return self._menuBarSelColour

    def InitColours(self) -> None:
        """Initialise the colour map."""
        self._colourSchemeMap: dict[str, wx.Colour] = {
            _("Default"): wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE),
            _("Dark"): wx.BLACK,
            _("Dark Olive Green"): wx.Colour("DARK OLIVE GREEN"),
            _("Generic"): wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION),
        }

    def GetColourSchemes(self) -> list[str]:
        """Return the available colour schemes.

        Returns:
            A list of strings representing the available colour schemes.
        """
        return list(self._colourSchemeMap)

    def CreateGreyBitmap(self, bmp: wx.Bitmap) -> wx.Bitmap:
        """Create a grey bitmap image from the input bitmap.

        Args:
            bmp (wx.Bitmap): a valid :class:`wx.Bitmap` object to be greyed out.

        Returns:
            A greyed-out representation of the input bitmap,
                an instance of :class:`wx.Bitmap`.
        """
        img: wx.Image = bmp.ConvertToImage()
        return wx.Bitmap(img.ConvertToGreyscale())

    def GetRaiseToolbar(self) -> bool:
        """Return ``True`` if we are dropping a shadow under a toolbar.

        Returns:
            A boolean indicating whether a shadow is dropped under a toolbar.
        """
        return self._raiseTB

    def SetRaiseToolbar(self, rais: bool) -> None:
        """Enables/disables toolbar shadow drop.

        Args:
            rais (bool): ``True`` to drop a shadow below a toolbar, ``False`` otherwise.
        """
        self._raiseTB: bool = rais
