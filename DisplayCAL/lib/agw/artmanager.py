"""Drawing routines and customizations for AGW widgets."""

from __future__ import annotations

import random
from io import BytesIO
from typing import Callable, ClassVar

import wx

from DisplayCAL.lib.agw.fmresources import (
    ARROW_DOWN,
    ARROW_UP,
    BOTTOM_SHADOW,
    BOTTOM_SHADOW_FULL,
    BU_EXT_LEFT_ALIGN_STYLE,
    BU_EXT_RIGHT_ALIGN_STYLE,
    BU_EXT_RIGHT_TO_LEFT_STYLE,
    CONTROL_DISABLED,
    CONTROL_FOCUS,
    CONTROL_PRESSED,
    CS_DROPSHADOW,
    RIGHT_SHADOW,
    SHADOW_BOTTOM_ALPHA,
    SHADOW_BOTTOM_LEFT_ALPHA,
    SHADOW_BOTTOM_LEFT_XPM,
    SHADOW_BOTTOM_XPM,
    SHADOW_CENTER_ALPHA,
    SHADOW_CENTER_XPM,
    SHADOW_RIGHT_ALPHA,
    SHADOW_RIGHT_TOP_ALPHA,
    SHADOW_RIGHT_TOP_XPM,
    SHADOW_RIGHT_XPM,
    STYLE_2007,
    STYLE_XP,
)

# ------------------------------------------------------------------------------------ #
# Class DCSaver
# ------------------------------------------------------------------------------------ #

_: Callable[[str], str] = wx.GetTranslation

_libimported = None

if wx.Platform == "__WXMSW__":
    OS_VERSION = wx.GetOsVersion()
    # Shadows behind menus are supported only in XP
    if OS_VERSION[1] == 5 and OS_VERSION[2] == 1:
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


class DCSaver:
    """Construct a DC saver.

    The dc is copied as-is.

    Args:
        pdc (wx.DC): An instance of :class:`wx.DC`.
    """

    def __init__(self, pdc: wx.DC) -> None:
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


class RendererBase:
    """Base class for all theme renderers."""

    def DrawButtonBorders(  # noqa: N802
        self, dc: wx.DC, rect: wx.Rect, pen_colour: wx.Colour, brush_colour: wx.Colour
    ) -> None:
        """Draw borders for buttons.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            pen_colour (wx.Colour): a valid :class:`wx.Colour` for the pen
                border.
            brush_colour (wx.Colour): a valid :class:`wx.Colour` for the brush.
        """
        # Keep old pen and brush
        _ = DCSaver(dc)

        # Set new pen and brush
        dc.SetPen(wx.Pen(pen_colour))
        dc.SetBrush(wx.Brush(brush_colour))

        # Draw the rectangle
        dc.DrawRectangle(rect)

    def DrawBitmapArea(  # noqa: N802
        self,
        dc: wx.DC,
        xpm_name: str,
        rect: wx.Rect,
        base_colour: wx.Colour,
        flip_side: bool,
    ) -> None:
        """Draw the area below a bitmap and the bitmap itself using a gradient shading.

        Args:
            dc (wx.DC): :class:`wx.DC` instance.
            xpm_name (str): The name of the XPM bitmap.
            rect (wx.Rect): The bitmap client rectangle.
            base_colour (wx.Colour): A valid :class:`wx.Colour` for the bitmap
                background.
            flip_side (bool): `True` to flip the gradient direction, `False`
                otherwise.
        """
        # draw the gradient area
        if not flip_side:
            ArtManager.Get().PaintDiagonalGradientBox(
                dc,
                rect,
                wx.WHITE,
                ArtManager.Get().LightColour(base_colour, 20),
                True,
                False,
            )
        else:
            ArtManager.Get().PaintDiagonalGradientBox(
                dc,
                rect,
                ArtManager.Get().LightColour(base_colour, 20),
                wx.WHITE,
                True,
                False,
            )

        # draw arrow
        arrow_down = wx.Bitmap(xpm_name)
        arrow_down.SetMask(wx.Mask(arrow_down, wx.WHITE))
        dc.DrawBitmap(arrow_down, rect.x + 1, rect.y + 1, True)

    def DrawBitmapBorders(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        pen_colour: wx.Colour,
        bitmap_border_upper_left_pen: wx.Colour,
    ) -> None:
        """Draw borders for a bitmap.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            pen_colour (wx.Colour): A valid :class:`wx.Colour` for the pen
                border.
            bitmap_border_upper_left_pen (wx.Colour): A valid
                :class:`wx.Colour` for the pen upper left border.
        """
        # Keep old pen and brush
        _ = DCSaver(dc)

        # lower right side
        dc.SetPen(wx.Pen(pen_colour))
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
        dc.SetPen(wx.Pen(bitmap_border_upper_left_pen))
        dc.DrawLine(rect.x, rect.y, rect.x + rect.width, rect.y)
        dc.DrawLine(rect.x, rect.y, rect.x, rect.y + rect.height)

    def GetMenuFaceColour(self) -> wx.Colour:  # noqa: N802
        """Return the foreground colour for the menu.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE), 80
        )

    def GetTextColourEnable(self) -> wx.Colour:  # noqa: N802
        """Return the colour used for text colour when enabled.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return wx.BLACK

    def GetTextColourDisable(self) -> wx.Colour:  # noqa: N802
        """Return the colour used for text colour when disabled.

        Returns:
            wx.Colour: A :class:`wx.Colour` instance.
        """
        return ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT), 30
        )

    def GetFont(self) -> wx.Font:  # noqa: N802
        """Return the font used for text.

        Returns:
            wx.Font: A :class:`wx.Font` instance.
        """
        return wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

    def DrawButton(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input_: None | bool | wx.Colour = None,
    ) -> None:
        """Draw a button using the appropriate theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            input_ (None | bool | wx.Colour): a flag used to call the
                right method.

        Raises:
            NotImplementedError: This method must be implemented in derived
                classes.
        """
        raise NotImplementedError(
            "DrawButton method must be implemented in derived classes"
        )

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
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

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
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

    def DrawButton(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input_: None | bool | wx.Colour = None,
    ) -> None:
        """Draw a button using the XP theme.

        Args:
            dc (wx.DC): An instance of :class:`wx.DC`.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            input_ (None | bool | wx.Colour): a flag used to call the
                right method.
        """
        if input_ is None or isinstance(input_, bool):
            self.DrawButtonTheme(dc, rect, state, input_)
        else:
            self.DrawButtonColour(dc, rect, state, input_)

    def DrawButtonTheme(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        use_light_colours: None | bool = None,
    ) -> None:
        """Draw a button using the XP theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            use_light_colours (None | bool): `True` to use light colours,
                `False` otherwise.
        """
        # switch according to the status
        if state == CONTROL_FOCUS:
            pen_colour = ArtManager.Get().FrameColour()
            brush_colour = ArtManager.Get().BackgroundColour()
        elif state == CONTROL_PRESSED:
            pen_colour = ArtManager.Get().FrameColour()
            brush_colour = ArtManager.Get().HighlightBackgroundColour()
        else:
            pen_colour = ArtManager.Get().FrameColour()
            brush_colour = ArtManager.Get().BackgroundColour()

        # Draw the button borders
        self.DrawButtonBorders(dc, rect, pen_colour, brush_colour)

    def DrawButtonColour(  # noqa: N802
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
        if state == CONTROL_FOCUS:
            pen_colour = colour
            brush_colour = ArtManager.Get().LightColour(colour, 75)
        elif state == CONTROL_PRESSED:
            pen_colour = colour
            brush_colour = ArtManager.Get().LightColour(colour, 60)
        else:
            pen_colour = colour
            brush_colour = ArtManager.Get().LightColour(colour, 75)

        # Draw the button borders
        self.DrawButtonBorders(dc, rect, pen_colour, brush_colour)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The menu bar's client rectangle.
        """
        # For office style, we simple draw a rectangle with a gradient colouring
        art_mgr = ArtManager.Get()
        vertical = art_mgr.GetMBVerticalGradient()

        _ = DCSaver(dc)

        # fill with gradient
        start_colour = art_mgr.GetMenuBarFaceColour()
        if art_mgr.IsDark(start_colour):
            start_colour = art_mgr.LightColour(start_colour, 50)

        end_colour = art_mgr.LightColour(start_colour, 90)
        art_mgr.PaintStraightGradientBox(dc, rect, start_colour, end_colour, vertical)

        # Draw the border
        if art_mgr.GetMenuBarBorder():
            dc.SetPen(wx.Pen(start_colour))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(rect)

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The toolbar's client rectangle.
        """
        art_mgr = ArtManager.Get()

        if not art_mgr.GetRaiseToolbar():
            return

        # For office style, we simple draw a rectangle with a gradient colouring
        vertical = art_mgr.GetMBVerticalGradient()

        _ = DCSaver(dc)

        # fill with gradient
        start_colour = art_mgr.GetMenuBarFaceColour()
        if art_mgr.IsDark(start_colour):
            start_colour = art_mgr.LightColour(start_colour, 50)

        start_colour = art_mgr.LightColour(start_colour, 20)

        end_colour = art_mgr.LightColour(start_colour, 90)
        art_mgr.PaintStraightGradientBox(dc, rect, start_colour, end_colour, vertical)
        art_mgr.DrawBitmapShadow(dc, rect)

    def GetTextColourEnable(self) -> wx.Colour:  # noqa: N802
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

    def GetColoursAccordingToState(self, state: int) -> tuple[int, int, int, int]:  # noqa: N802
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
            tuple[int, int, int, int, bool, bool]: A tuple containing the
                gradient percentages.
        """
        # switch according to the status
        if state == CONTROL_FOCUS:
            upper_box_top_percent = 95
            upper_box_bottom_percent = 50
            lower_box_top_percent = 40
            lower_box_bottom_percent = 90
            concave_upper_box = True
            concave_lower_box = True

        elif state == CONTROL_PRESSED:
            upper_box_top_percent = 75
            upper_box_bottom_percent = 90
            lower_box_top_percent = 90
            lower_box_bottom_percent = 40
            concave_upper_box = True
            concave_lower_box = True

        elif state == CONTROL_DISABLED:
            upper_box_top_percent = 100
            upper_box_bottom_percent = 100
            lower_box_top_percent = 70
            lower_box_bottom_percent = 70
            concave_upper_box = True
            concave_lower_box = True

        else:
            upper_box_top_percent = 90
            upper_box_bottom_percent = 50
            lower_box_top_percent = 30
            lower_box_bottom_percent = 75
            concave_upper_box = True
            concave_lower_box = True

        return (
            upper_box_top_percent,
            upper_box_bottom_percent,
            lower_box_top_percent,
            lower_box_bottom_percent,
            concave_upper_box,
            concave_lower_box,
        )

    def DrawButton(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        state: int,
        input_: None | bool | wx.Colour = None,
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            input_ (None | bool | wx.Colour): A flag used to call the
                right method.
        """
        if input_ is None or isinstance(input_, bool):
            self.DrawButtonTheme(dc, rect, state, input_)
        else:
            self.DrawButtonColour(dc, rect, state, input_)

    def DrawButtonTheme(  # noqa: N802
        self, dc: wx.DC, rect: wx.Rect, state: int, use_light_colours: None | bool
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the button's client rectangle.
            state (int): the button state.
            use_light_colours (None | bool): `True` to use light colours,
                ``False`` otherwise.
        """
        self.DrawButtonColour(
            dc, rect, state, ArtManager.Get().GetThemeBaseColour(use_light_colours)
        )

    def DrawButtonColour(  # noqa: N802
        self, dc: wx.DC, rect: wx.Rect, state: int, colour: wx.Colour
    ) -> None:
        """Draw a button using the MS Office 2007 theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            state (int): The button state.
            colour (wx.Colour): a valid :class:`wx.Colour` instance.
        """
        art_mgr = ArtManager.Get()

        # Keep old pen and brush
        _ = DCSaver(dc)

        # Define the rounded rectangle base on the given rect
        # we need an array of 9 points for it
        base_colour = colour

        # Define the middle points
        left_pt = wx.Point(rect.x, rect.y + (rect.height / 2))
        right_pt = wx.Point(rect.x + rect.width - 1, rect.y + (rect.height / 2))

        # Define the top region
        top = wx.Rect((rect.GetLeft(), rect.GetTop()), right_pt)
        bottom = wx.Rect(left_pt, (rect.GetRight(), rect.GetBottom()))

        (
            upper_box_top_percent,
            upper_box_bottom_percent,
            lower_box_top_percent,
            lower_box_bottom_percent,
            concave_upper_box,
            concave_lower_box,
        ) = self.GetColoursAccordingToState(state)

        top_start_colour = art_mgr.LightColour(base_colour, upper_box_top_percent)
        top_end_colour = art_mgr.LightColour(base_colour, upper_box_bottom_percent)
        bottom_start_colour = art_mgr.LightColour(base_colour, lower_box_top_percent)
        bottom_end_colour = art_mgr.LightColour(base_colour, lower_box_bottom_percent)

        art_mgr.PaintStraightGradientBox(dc, top, top_start_colour, top_end_colour)
        art_mgr.PaintStraightGradientBox(
            dc, bottom, bottom_start_colour, bottom_end_colour
        )

        rr = wx.Rect(rect.x, rect.y, rect.width, rect.height)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        frame_colour = art_mgr.LightColour(base_colour, 60)
        dc.SetPen(wx.Pen(frame_colour))
        dc.DrawRectangle(rr)

        wc = art_mgr.LightColour(base_colour, 80)
        dc.SetPen(wx.Pen(wc))
        rr.Deflate(1, 1)
        dc.DrawRectangle(rr)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the menu bar's client rectangle.
        """
        # Keep old pen and brush
        _ = DCSaver(dc)
        art_mgr = ArtManager.Get()
        base_colour = art_mgr.GetMenuBarFaceColour()

        dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.DrawRectangle(rect)

        # Define the rounded rectangle base on the given rect
        # we need an array of 9 points for it
        reg_pts = [wx.Point() for _ in range(9)]
        radius = 2

        reg_pts[0] = wx.Point(rect.x, rect.y + radius)
        reg_pts[1] = wx.Point(rect.x + radius, rect.y)
        reg_pts[2] = wx.Point(rect.x + rect.width - radius - 1, rect.y)
        reg_pts[3] = wx.Point(rect.x + rect.width - 1, rect.y + radius)
        reg_pts[4] = wx.Point(
            rect.x + rect.width - 1, rect.y + rect.height - radius - 1
        )
        reg_pts[5] = wx.Point(
            rect.x + rect.width - radius - 1, rect.y + rect.height - 1
        )
        reg_pts[6] = wx.Point(rect.x + radius, rect.y + rect.height - 1)
        reg_pts[7] = wx.Point(rect.x, rect.y + rect.height - radius - 1)
        reg_pts[8] = reg_pts[0]

        # Define the middle points
        factor = art_mgr.GetMenuBgFactor()

        left_pt1 = wx.Point(rect.x, rect.y + (rect.height / factor))
        left_pt2 = wx.Point(rect.x, rect.y + (rect.height / factor) * (factor - 1))

        right_pt1 = wx.Point(rect.x + rect.width, rect.y + (rect.height / factor))
        right_pt2 = wx.Point(
            rect.x + rect.width, rect.y + (rect.height / factor) * (factor - 1)
        )

        # Define the top region
        top_reg = [wx.Point() for _ in range(7)]
        top_reg[0] = reg_pts[0]
        top_reg[1] = reg_pts[1]
        top_reg[2] = wx.Point(reg_pts[2].x + 1, reg_pts[2].y)
        top_reg[3] = wx.Point(reg_pts[3].x + 1, reg_pts[3].y)
        top_reg[4] = wx.Point(right_pt1.x, right_pt1.y + 1)
        top_reg[5] = wx.Point(left_pt1.x, left_pt1.y + 1)
        top_reg[6] = top_reg[0]

        # Define the middle region
        middle = wx.Rect(left_pt1, wx.Point(right_pt2.x - 2, right_pt2.y))

        # Define the bottom region
        bottom = wx.Rect(left_pt2, wx.Point(rect.GetRight() - 1, rect.GetBottom()))

        top_start_colour = art_mgr.LightColour(base_colour, 90)
        top_end_colour = art_mgr.LightColour(base_colour, 60)
        bottom_start_colour = art_mgr.LightColour(base_colour, 40)
        bottom_end_colour = art_mgr.LightColour(base_colour, 20)

        top_region = wx.Region(top_reg)

        art_mgr.PaintGradientRegion(dc, top_region, top_start_colour, top_end_colour)
        art_mgr.PaintStraightGradientBox(
            dc, bottom, bottom_start_colour, bottom_end_colour
        )
        art_mgr.PaintStraightGradientBox(
            dc, middle, top_end_colour, bottom_start_colour
        )

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The toolbar's client rectangle.
        """
        art_mgr = ArtManager.Get()

        if not art_mgr.GetRaiseToolbar():
            return

        # Keep old pen and brush
        _ = DCSaver(dc)

        base_colour = art_mgr.GetMenuBarFaceColour()
        base_colour = art_mgr.LightColour(base_colour, 20)

        dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)))
        dc.DrawRectangle(rect)

        radius = 2

        # Define the rounded rectangle base on the given rect
        # we need an array of 9 points for it
        reg_pts = [None] * 9

        reg_pts[0] = wx.Point(rect.x, rect.y + radius)
        reg_pts[1] = wx.Point(rect.x + radius, rect.y)
        reg_pts[2] = wx.Point(rect.x + rect.width - radius - 1, rect.y)
        reg_pts[3] = wx.Point(rect.x + rect.width - 1, rect.y + radius)
        reg_pts[4] = wx.Point(
            rect.x + rect.width - 1, rect.y + rect.height - radius - 1
        )
        reg_pts[5] = wx.Point(
            rect.x + rect.width - radius - 1, rect.y + rect.height - 1
        )
        reg_pts[6] = wx.Point(rect.x + radius, rect.y + rect.height - 1)
        reg_pts[7] = wx.Point(rect.x, rect.y + rect.height - radius - 1)
        reg_pts[8] = reg_pts[0]

        # Define the middle points
        factor = art_mgr.GetMenuBgFactor()

        left_pt1 = wx.Point(rect.x, rect.y + (rect.height / factor))
        right_pt1 = wx.Point(rect.x + rect.width, rect.y + (rect.height / factor))

        left_pt2 = wx.Point(rect.x, rect.y + (rect.height / factor) * (factor - 1))
        right_pt2 = wx.Point(
            rect.x + rect.width, rect.y + (rect.height / factor) * (factor - 1)
        )

        # Define the top region
        top_reg = [None] * 7
        top_reg[0] = reg_pts[0]
        top_reg[1] = reg_pts[1]
        top_reg[2] = wx.Point(reg_pts[2].x + 1, reg_pts[2].y)
        top_reg[3] = wx.Point(reg_pts[3].x + 1, reg_pts[3].y)
        top_reg[4] = wx.Point(right_pt1.x, right_pt1.y + 1)
        top_reg[5] = wx.Point(left_pt1.x, left_pt1.y + 1)
        top_reg[6] = top_reg[0]

        # Define the middle region
        middle = wx.Rect(left_pt1, wx.Point(right_pt2.x - 2, right_pt2.y))

        # Define the bottom region
        bottom = wx.Rect(left_pt2, wx.Point(rect.GetRight() - 1, rect.GetBottom()))

        top_start_colour = art_mgr.LightColour(base_colour, 90)
        top_end_colour = art_mgr.LightColour(base_colour, 60)
        bottom_start_colour = art_mgr.LightColour(base_colour, 40)
        bottom_end_colour = art_mgr.LightColour(base_colour, 20)

        top_region = wx.Region(top_reg)

        art_mgr.PaintGradientRegion(dc, top_region, top_start_colour, top_end_colour)
        art_mgr.PaintStraightGradientBox(
            dc, bottom, bottom_start_colour, bottom_end_colour
        )
        art_mgr.PaintStraightGradientBox(
            dc, middle, top_end_colour, bottom_start_colour
        )

        art_mgr.DrawBitmapShadow(dc, rect)

    def GetTextColourEnable(self) -> wx.Colour:  # noqa: N802
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

    _alignment_buffer = 7
    _menu_theme: int = STYLE_XP
    _vertical_gradient = False
    _renderers: ClassVar[dict[int, RendererBase]] = {STYLE_XP: None, STYLE_2007: None}
    _bmp_shadow_enabled = False
    _ms2007sunken = False
    _draw_mb_border = True
    _menu_bg_factor = 5
    _menu_bar_colour_scheme: str = _("Default")
    _raise_trace_back = True
    _bitmaps: ClassVar[dict[str, wx.Bitmap]] = {}
    _transparency = 255

    def __init__(self) -> None:
        wx.EvtHandler.__init__(self)
        self._menuBarBgColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE)

        # connect an event handler to the system colour change event
        self.Bind(wx.EVT_SYS_COLOUR_CHANGED, self.OnSysColourChange)

        # Initialize the menu bar selection colour
        self._menuBarSelColour = wx.Colour(0, 0, 0)  # Default to black

    def SetTransparency(self, amount: int) -> None:  # noqa: N802
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

    def GetTransparency(self) -> int:  # noqa: N802
        """Return the alpha channel value for transparent windows.

        Returns:
            int: An integer representing the alpha channel value.
        """
        return self._transparency

    @classmethod
    def ConvertToBitmap(  # noqa: N802
        cls, xpm: list[str] | bytes, alpha: None | list[int] = None
    ) -> wx.Bitmap:
        """Convert the given image to a bitmap, optionally overlaying an alpha channel.

        Args:
            xpm (list[str] | bytes): A list of strings formatted as XPM.
            alpha (None | list[int]): A list of alpha values, the same size
                as the xpm bitmap.

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

    def Initialize(self) -> None:  # noqa: N802
        """Initialize the bitmaps and colours."""
        # create wxBitmaps from the xpm's
        self._rightBottomCorner = self.ConvertToBitmap(
            SHADOW_CENTER_XPM, SHADOW_CENTER_ALPHA
        )
        self._bottom = self.ConvertToBitmap(SHADOW_BOTTOM_XPM, SHADOW_BOTTOM_ALPHA)
        self._bottomLeft = self.ConvertToBitmap(
            SHADOW_BOTTOM_LEFT_XPM, SHADOW_BOTTOM_LEFT_ALPHA
        )
        self._rightTop = self.ConvertToBitmap(
            SHADOW_RIGHT_TOP_XPM, SHADOW_RIGHT_TOP_ALPHA
        )
        self._right = self.ConvertToBitmap(SHADOW_RIGHT_XPM, SHADOW_RIGHT_ALPHA)

        # initialise the colour map
        self.InitColours()
        self.SetMenuBarColour(self._menu_bar_colour_scheme)

        # Create common bitmaps
        self.FillStockBitmaps()

    def FillStockBitmaps(self) -> None:  # noqa: N802
        """Initialize few standard bitmaps."""
        bmp = self.ConvertToBitmap(ARROW_DOWN, alpha=None)
        bmp.SetMask(wx.Mask(bmp, wx.Colour(0, 128, 128)))
        self._bitmaps.update({"arrow_down": bmp})

        bmp = self.ConvertToBitmap(ARROW_UP, alpha=None)
        bmp.SetMask(wx.Mask(bmp, wx.Colour(0, 128, 128)))
        self._bitmaps.update({"arrow_up": bmp})

    def GetStockBitmap(self, name: str) -> wx.Bitmap:  # noqa: N802
        """Return a bitmap from a stock.

        Args:
            name (str): The bitmap name.

        Returns:
            wx.Bitmap: The stock bitmap, if `name` was found in the stock bitmap
                dictionary. Otherwise, :class:`NullBitmap` is returned.
        """
        return self._bitmaps.get(name, wx.NullBitmap)

    @classmethod
    def Get(cls: type[ArtManager]) -> ArtManager:  # noqa: N802
        """Accessor to the unique art manager object.

        Returns:
            A unique instance of :class:`ArtManager`.
        """
        if not hasattr(cls, "_instance"):
            cls._instance = ArtManager()
            cls._instance.Initialize()

            # Initialize the renderers map
            cls._renderers[STYLE_XP] = RendererXP()
            cls._renderers[STYLE_2007] = RendererMSOffice2007()

        return cls._instance

    @classmethod
    def Free(cls) -> None:  # noqa: N802
        """Destructor for the unique art manager object."""
        if hasattr(cls, "_instance"):
            del cls._instance

    def OnSysColourChange(self, event: wx.SysColourChangedEvent) -> None:  # noqa: N802
        """Handle the ``wx.EVT_SYS_COLOUR_CHANGED`` event for :class:`ArtManager`.

        Args:
            event (wx.SysColourChangedEvent): A :class:`SysColourChangedEvent` event to
                be processed.
        """
        # reinitialise the colour map
        self.InitColours()

    def LightColour(self, colour: wx.Colour, percent: int) -> wx.Colour:  # noqa: N802
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

    def DarkColour(self, colour: wx.Colour, percent: int) -> wx.Colour:  # noqa: N802
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

    def PaintStraightGradientBox(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        start_colour: wx.Colour,
        end_colour: wx.Colour,
        vertical: bool = True,
    ) -> None:
        """Paint the rectangle with gradient coloring.

        The gradient lines are either horizontal or vertical.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            start_colour (wx.Colour): The first colour of the gradient
                shading.
            end_colour (wx.EndColour): The second colour of the gradient
                shading.
            vertical (bool): ``True`` for gradient coloring in the vertical
                direction, ``False`` for horizontal shading.
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

        dc.GradientFillLinear(rect, start_colour, end_colour, direction)

    def PaintGradientRegion(  # noqa: N802
        self,
        dc: wx.DC,
        region: wx.Region,
        start_colour: wx.Colour,
        end_colour: wx.Colour,
        vertical: bool = True,
    ) -> None:
        """Paint a region with gradient coloring.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            region (wx.Region): A region to be filled with gradient shading.
            start_colour (wx.Colour): The first colour of the gradient shading.
            end_colour (wx.Colour): The second colour of the gradient shading.
            vertical (bool): ``True`` for gradient coloring in the vertical
                direction, ``False`` for horizontal shading.
        """
        # The way to achieve non-rectangle
        mem_dc = wx.MemoryDC()
        rect = region.GetBox()
        bitmap = wx.Bitmap(rect.width, rect.height)
        mem_dc.SelectObject(bitmap)

        # Colour the whole rectangle with gradient
        rr = wx.Rect(0, 0, rect.width, rect.height)
        self.PaintStraightGradientBox(mem_dc, rr, start_colour, end_colour, vertical)

        # Convert the region to a black and white bitmap with the white pixels
        # being inside the region we draw the bitmap over the gradient coloured
        # rectangle, with mask set to white, this will cause our region to be
        # coloured with the gradient, while area outside the region will be
        # painted with black. Then we simply draw the bitmap to the dc with
        # mask set to black.
        tmp_region = wx.Region(rect.x, rect.y, rect.width, rect.height)
        tmp_region.Offset(-rect.x, -rect.y)
        region_bmp = tmp_region.ConvertToBitmap()
        region_bmp.SetMask(wx.Mask(region_bmp, wx.WHITE))

        # The function ConvertToBitmap() return a rectangle bitmap which is
        # shorter by 1 pixel on the height and width (this is correct behavior,
        # since DrawLine does not include the second point as part of the line)
        # we fix this issue by drawing our own line at the bottom and left side
        # of the rectangle
        mem_dc.SetPen(wx.BLACK_PEN)
        mem_dc.DrawBitmap(region_bmp, 0, 0, True)
        mem_dc.DrawLine(0, rr.height - 1, rr.width, rr.height - 1)
        mem_dc.DrawLine(rr.width - 1, 0, rr.width - 1, rr.height)

        mem_dc.SelectObject(wx.NullBitmap)
        bitmap.SetMask(wx.Mask(bitmap, wx.BLACK))
        dc.DrawBitmap(bitmap, rect.x, rect.y, True)

    def PaintDiagonalGradientBox(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        start_colour: wx.Colour,
        end_colour: wx.Colour,
        start_at_upper_left: bool = True,
        trim_to_square: bool = True,
    ) -> None:
        """Paint rectangle with gradient coloring.

        The gradient lines are diagonal and may start from the upper left
        corner or from the upper right corner.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            start_colour (wx.Colour): The first colour of the gradient shading.
            end_colour (wx.Colour): The second colour of the gradient shading.
            start_at_upper_left (bool): ``True`` to start the gradient lines at
                the upper left corner of the rectangle, ``False`` to start at
                the upper right corner.
            trim_to_square (bool): ``True`` to trim the gradient lines in a
                square.
        """
        # gradient fill from colour 1 to colour 2 with top to bottom
        if rect.height < 1 or rect.width < 1:
            return

        # Save the current pen and brush
        saved_pen = dc.GetPen()
        saved_brush = dc.GetBrush()

        # calculate some basic numbers
        size, size_x, size_y, proportion = self._calculate_sizes(rect, trim_to_square)
        rstep, gstep, bstep = self._calculate_steps(start_colour, end_colour, size)

        self._draw_upper_triangle(
            dc,
            rect,
            start_colour,
            rstep,
            gstep,
            bstep,
            size,
            size_x,
            size_y,
            proportion,
            start_at_upper_left,
        )
        self._draw_lower_triangle(
            dc,
            rect,
            start_colour,
            rstep,
            gstep,
            bstep,
            size,
            size_x,
            size_y,
            proportion,
            start_at_upper_left,
        )

        # Restore the pen and brush
        dc.SetPen(saved_pen)
        dc.SetBrush(saved_brush)

    def _calculate_sizes(
        self, rect: wx.Rect, trim_to_square: bool
    ) -> tuple[int, int, int, float]:
        """Calculate the sizes for the gradient drawing.

        Args:
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            trim_to_square (bool): ``True`` to trim the gradient lines in a
                square.

        Returns:
            tuple[int, int, int, float]: A tuple containing the size, sizeX,
                sizeY and proportion.
        """
        if rect.width > rect.height:
            if trim_to_square:
                size = rect.height
                size_x = size_y = rect.height - 1
                proportion = 1.0  # Square proportion is 1.0
            else:
                proportion = float(rect.heigh) / float(rect.width)
                size = rect.width
                size_x = rect.width - 1
                size_y = rect.height - 1
        elif trim_to_square:
            size = rect.width
            size_x = size_y = rect.width - 1
            proportion = 1.0  # Square proportion is 1.0
        else:
            size_x = rect.width - 1
            size = rect.height
            size_y = rect.height - 1
            proportion = float(rect.width) / float(rect.height)
        return size, size_x, size_y, proportion

    def _calculate_steps(
        self, start_colour: wx.Colour, end_colour: wx.Colour, size: int
    ) -> tuple[float, float, float]:
        """Calculate the gradient steps for the diagonal gradient drawing.

        Args:
            start_colour (wx.Colour): The first colour of the gradient shading.
            end_colour (wx.Colour): The second colour of the gradient shading.
            size (int): The size of the gradient.

        Returns:
            A tuple containing the rstep, gstep, and bstep.
        """
        # calculate gradient coefficients
        col2 = end_colour
        col1 = start_colour
        rstep = float(col2.Red() - col1.Red()) / float(size)
        gstep = float(col2.Green() - col1.Green()) / float(size)
        bstep = float(col2.Blue() - col1.Blue()) / float(size)
        return rstep, gstep, bstep

    def _draw_upper_triangle(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        start_colour: wx.Colour,
        rstep: float,
        gstep: float,
        bstep: float,
        size: int,
        size_x: int,
        size_y: int,
        proportion: float,
        start_at_upper_left: bool,
    ) -> None:
        """Draw the upper triangle of the diagonal gradient.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            start_colour (wx.Colour): The first colour of the gradient shading.
            rstep (float): The red step of the gradient.
            gstep (float): The green step of the gradient.
            bstep (float): The blue step of the gradient.
            size (int): The size of the gradient.
            size_x (int): The width of the gradient.
            size_y (int): The height of the gradient.
            proportion (float): The proportion of the gradient.
            start_at_upper_left (bool): ``True`` to start the gradient lines at
                the upper left corner of the rectangle, ``False`` to start at
                the upper right corner.
        """
        rf, gf, bf = 0.0, 0.0, 0.0
        # draw the upper triangle
        for i in range(size):
            curr_col = wx.Colour(
                start_colour.Red() + rf,
                start_colour.Green() + gf,
                start_colour.Blue() + bf,
            )
            dc.SetBrush(wx.Brush(curr_col, wx.BRUSHSTYLE_SOLID))
            dc.SetPen(wx.Pen(curr_col))
            self._draw_line_and_point(
                dc, rect, i, size_x, size_y, proportion, start_at_upper_left
            )
            rf += rstep / 2
            gf += gstep / 2
            bf += bstep / 2

    def _draw_lower_tiangle(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        start_colour: wx.Colour,
        rstep: float,
        gstep: float,
        bstep: float,
        size: int,
        size_x: int,
        size_y: int,
        proportion: float,
        start_at_upper_left: bool,
    ) -> None:
        """Draw the lower triangle of the diagonal gradient.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            start_colour (wx.Colour): The first colour of the gradient shading.
            rstep (float): The red step of the gradient.
            gstep (float): The green step of the gradient.
            bstep (float): The blue step of the gradient.
            size (int): The size of the gradient.
            size_x (int): The width of the gradient.
            size_y (int): The height of the gradient.
            proportion (float): The proportion of the gradient.
            start_at_upper_left (bool): ``True`` to start the gradient lines at
                the upper left corner of the rectangle, ``False`` to start at
                the upper right corner.
        """
        rf = rstep * size / 2
        gf = gstep * size / 2
        bf = bstep * size / 2
        # draw the lower triangle
        for i in range(size):
            curr_col = wx.Colour(
                start_colour.Red() + rf,
                start_colour.Green() + gf,
                start_colour.Blue() + bf,
            )
            dc.SetBrush(wx.Brush(curr_col, wx.BRUSHSTYLE_SOLID))
            dc.SetPen(wx.Pen(curr_col))
            self._draw_line_and_point(
                dc, rect, i, size_x, size_y, proportion, start_at_upper_left, lower=True
            )
            rf += rstep / 2
            gf += gstep / 2
            bf += bstep / 2

    def _draw_line_and_point(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        i: int,
        size_x: int,
        size_y: int,
        proportion: float,
        start_at_upper_left: bool,
        lower: bool = False,
    ) -> None:
        """Draw a line and a point for the diagonal gradient.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            i (int): The current step in the gradient.
            size_x (int): The width of the gradient.
            size_y (int): The height of the gradient.
            proportion (float): The proportion of the gradient.
            start_at_upper_left (bool): ``True`` to start the gradient lines at
                the upper left corner of the rectangle, ``False`` to start at
                the upper right corner.
            lower (bool): ``True`` to draw the lower triangle, ``False`` to
                draw the upper triangle.
        """
        if start_at_upper_left:
            if rect.width > rect.height:
                if lower:
                    dc.DrawLine(
                        rect.x + i,
                        rect.y + size_y,
                        rect.x + size_x,
                        int(rect.y + proportion * i),
                    )
                    dc.DrawPoint(rect.x + size_x, int(rect.y + proportion * i))
                else:
                    dc.DrawLine(
                        rect.x + i, rect.y, rect.x, int(rect.y + proportion * i)
                    )
                    dc.DrawPoint(rect.x, int(rect.y + proportion * i))
            elif lower:
                dc.DrawLine(
                    int(rect.x + proportion * i),
                    rect.y + size_y,
                    rect.x + size_x,
                    rect.y + i,
                )
                dc.DrawPoint(rect.x + size_x, rect.y + i)
            else:
                dc.DrawLine(int(rect.x + proportion * i), rect.y, rect.x, rect.y + i)
                dc.DrawPoint(rect.x, rect.y + i)
        elif rect.width > rect.height:
            if lower:
                dc.DrawLine(
                    rect.x + i, rect.y + size_y, rect.x + size_x - i, rect.y + size_y
                )
                dc.DrawPoint(rect.x + size_x - i, rect.y + size_y)
            else:
                dc.DrawLine(
                    rect.x + size_x - i,
                    rect.y,
                    rect.x + size_x,
                    int(rect.y + proportion * i),
                )
                dc.DrawPoint(rect.x + size_x, int(rect.y + proportion * i))
        else:
            x_to = max(int(rect.x + size_x - proportion * i), rect.x)
            if lower:
                dc.DrawLine(rect.x, rect.y + i, x_to, rect.y + size_y)
                dc.DrawPoint(x_to, rect.y + size_y)
            else:
                dc.DrawLine(x_to, rect.y, rect.x + size_x, rect.y + i)
                dc.DrawPoint(rect.x + size_x, rect.y + i)

    def PaintCrescentGradientBox(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        start_colour: wx.Colour,
        end_colour: wx.Colour,
        concave: bool = True,
    ) -> None:
        """Paint a region with gradient colouring.

        The gradient is in crescent shape which fits the 2007 style.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            start_colour (wx.Colour): The first colour of the gradient shading.
            end_colour (wx.Colour): The second colour of the gradient shading.
            concave (bool): ``True`` for a concave effect, ``False`` for a
                convex one.
        """
        diagonal_rect_width = rect.GetWidth() / 4
        spare = rect.width - 4 * diagonal_rect_width
        left_rect = wx.Rect(rect.x, rect.y, diagonal_rect_width, rect.GetHeight())
        right_rect = wx.Rect(
            rect.x + 3 * diagonal_rect_width + spare,
            rect.y,
            diagonal_rect_width,
            rect.GetHeight(),
        )

        if concave:
            self.PaintStraightGradientBox(
                dc, rect, self.MixColours(start_colour, end_colour, 50), end_colour
            )
            self.PaintDiagonalGradientBox(
                dc, left_rect, start_colour, end_colour, True, False
            )
            self.PaintDiagonalGradientBox(
                dc, right_rect, start_colour, end_colour, False, False
            )

        else:
            self.PaintStraightGradientBox(
                dc, rect, end_colour, self.MixColours(end_colour, start_colour, 50)
            )
            self.PaintDiagonalGradientBox(
                dc, left_rect, end_colour, start_colour, False, False
            )
            self.PaintDiagonalGradientBox(
                dc, right_rect, end_colour, start_colour, True, False
            )

    def FrameColour(self) -> wx.Colour:  # noqa: N802
        """Return the surrounding colour for a control.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        return wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION)

    def BackgroundColour(self) -> wx.Colour:  # noqa: N802
        """Return the background colour of a control when not in focus.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        return self.LightColour(self.FrameColour(), 75)

    def HighlightBackgroundColour(self) -> wx.Colour:  # noqa: N802
        """Return the background colour of a control when it is in focus.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        return self.LightColour(self.FrameColour(), 60)

    def MixColours(  # noqa: N802
        self, first_colour: wx.Colour, second_colour: wx.Colour, percent: int
    ) -> wx.Colour:
        """Return mix of input colours.

        Args:
            first_colour (wx.Colour): The first colour to be mixed.
            second_colour (wx.Colour): The second colour to be mixed.
            percent (int): The relative percentage of `first_colour` with
                respect to `second_colour`.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        # calculate gradient coefficients
        red_offset = float(
            (second_colour.Red() * (100 - percent) / 100)
            - (first_colour.Red() * percent / 100)
        )
        green_offset = float(
            (second_colour.Green() * (100 - percent) / 100)
            - (first_colour.Green() * percent / 100)
        )
        blue_offset = float(
            (second_colour.Blue() * (100 - percent) / 100)
            - (first_colour.Blue() * percent / 100)
        )

        return wx.Colour(
            first_colour.Red() + red_offset,
            first_colour.Green() + green_offset,
            first_colour.Blue() + blue_offset,
        )

    @classmethod
    def RandomColour(cls) -> wx.Colour:  # noqa: N802
        """Create a random colour.

        Returns:
            wx.Colour: An instance of :class:`wx.Colour`.
        """
        r = random.randint(0, 255)  # Random value between 0-255  # noqa: S311
        g = random.randint(0, 255)  # Random value between 0-255  # noqa: S311
        b = random.randint(0, 255)  # Random value between 0-255  # noqa: S311
        return wx.Colour(r, g, b)

    def IsDark(self, colour: wx.Colour) -> bool:  # noqa: N802
        """Return whether a colour is dark or light.

        Args:
            colour (wx.Colour): A :class:`wx.Colour`.

        Returns:
            bool: ``True`` if the average RGB values are dark, ``False``
                otherwise.
        """
        evg = (colour.Red() + colour.Green() + colour.Blue()) / 3
        return evg < 127

    @classmethod
    def TruncateText(cls, dc: wx.DC, text: str, max_width: int) -> None | str:  # noqa: N802
        """Truncate a given string to fit given width size.

        If the text does not fit into the given width it is truncated to fit.
        The format of the fixed text is ``truncate text ...``.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            text (str): The text to be (eventually) truncated.
            max_width (int): The maximum width allowed for the text.

        Returns:
            None | str: A string containing the (possibly) truncated
                text.
        """
        text_len = len(text)
        temp_text = text
        rect_size = max_width

        fixed_text = ""

        text_w, _ = dc.GetTextExtent(text)

        if rect_size >= text_w:
            return text

        # The text does not fit in the designated area, so we need to truncate
        # it a bit
        suffix = ".."
        w, _ = dc.GetTextExtent(suffix)
        rect_size -= w

        for _ in range(text_len, -1, -1):
            text_w, _ = dc.GetTextExtent(temp_text)
            if rect_size >= text_w:
                fixed_text = temp_text
                fixed_text += ".."
                return fixed_text

            temp_text = temp_text[:-1]

        return None

    def DrawButton(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        theme: int,
        state: int,
        input_: None | bool | wx.Colour = None,
    ) -> None:
        """Colour rectangle according to the theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The rectangle to be filled with gradient shading.
            theme (int): The theme to use to draw the button.
            state (int): The button state.
            input_ (None | bool | wx.Colour): A flag used to call the
                right method.
        """
        if input_ is None or isinstance(input_, bool):
            self.DrawButtonTheme(dc, rect, theme, state, bool(input_))
        else:
            self.DrawButtonColour(dc, rect, theme, state, input_)

    def DrawButtonTheme(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        theme: int,
        state: int,
        use_light_colours: bool = True,
    ) -> None:
        """Draw a button using the appropriate theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The button's client rectangle.
            theme (int): The theme to use to draw the button.
            state (int): The button state.
            use_light_colours (bool): ``True`` to use light colours, ``False``
                otherwise.
        """
        renderer = self._renderers[int(theme)]

        # Set background colour if non given by caller
        renderer.DrawButton(dc, rect, state, use_light_colours)

    def DrawButtonColour(  # noqa: N802
        self, dc: wx.DC, rect: wx.Rect, theme: int, state: int, colour: wx.Colour
    ) -> None:
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

    def CanMakeWindowsTransparent(self) -> bool:  # noqa: N802
        """Check if the current OS supports transparency.

        Returns:
            bool: ``True`` if the system supports transparency of toplevel
                windows, otherwise returns ``False``.
        """
        if wx.Platform == "__WXMSW__":
            version = wx.GetOsDescription()
            return (
                version.find("XP") >= 0
                or version.find("2000") >= 0
                or version.find("NT") >= 0
            )
        if wx.Platform == "__WXMAC__":  # noqa: SIM103
            return True
        # Linux
        return False

    def MakeWindowTransparent(self, wnd: wx.TopLevelWindow, amount: int) -> None:  # noqa: N802
        """Make a toplevel window transparent if the system supports it.

        On supported windows systems (Win2000 and greater), this function will
        make a frame window transparent by a certain amount.

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
                p_set_layered_window_attributes = win32api.GetProcAddress(
                    self._winlib, "SetLayeredWindowAttributes"
                )

                if p_set_layered_window_attributes is None:
                    return

                exstyle = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if (exstyle & 0x80000) == 0:
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

    def DrawBitmapShadow(  # noqa: N802
        self, dc: wx.DC, rect: wx.Rect, where: int = BOTTOM_SHADOW | RIGHT_SHADOW
    ) -> None:
        """Draw a shadow using background bitmap.

        Assumption: the background was already drawn on the dc

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The bitmap's client rectangle.
            where (int): Where to draw the shadow. This can be any combination
                of the following bits:

                ===================== ======= =======================
                Shadow Settings        Value  Description
                ===================== ======= =======================
                ``RightShadow``             1 Right side shadow
                ``BottomShadow``            2 Not full bottom shadow
                ``BottomShadowFull``        4 Full bottom shadow
                ===================== ======= =======================
        """
        shadow_size = 5

        # the rect must be at least 5x5 pixels
        if rect.height < 2 * shadow_size or rect.width < 2 * shadow_size:
            return

        # Start by drawing the right bottom corner
        if where & BOTTOM_SHADOW or where & BOTTOM_SHADOW_FULL:
            dc.DrawBitmap(
                self._rightBottomCorner, rect.x + rect.width, rect.y + rect.height, True
            )

        # Draw right side shadow
        xx = rect.x + rect.width
        yy = rect.y + rect.height - shadow_size

        if where & RIGHT_SHADOW:
            while yy - rect.y > 2 * shadow_size:
                dc.DrawBitmap(self._right, xx, yy, True)
                yy -= shadow_size

            dc.DrawBitmap(self._rightTop, xx, yy - shadow_size, True)

        if where & BOTTOM_SHADOW:
            xx = rect.x + rect.width - shadow_size
            yy = rect.height + rect.y
            while xx - rect.x > 2 * shadow_size:
                dc.DrawBitmap(self._bottom, xx, yy, True)
                xx -= shadow_size

            dc.DrawBitmap(self._bottomLeft, xx - shadow_size, yy, True)

        if where & BOTTOM_SHADOW_FULL:
            xx = rect.x + rect.width - shadow_size
            yy = rect.height + rect.y
            while xx - rect.x >= 0:
                dc.DrawBitmap(self._bottom, xx, yy, True)
                xx -= shadow_size

            dc.DrawBitmap(self._bottom, xx, yy, True)

    def DropShadow(self, wnd: wx.TopLevelWindow, drop: bool = True) -> None:  # noqa: N802
        """Add a shadow under the window (Windows only).

        Args:
            wnd (wx.TopLevelWindow): The window for which we are dropping a
                shadow.
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
                csstyle |= CS_DROPSHADOW  # Nothing to be done
            elif csstyle & CS_DROPSHADOW:
                csstyle &= ~(CS_DROPSHADOW)
            else:
                return  # Nothing to be done

            win32api.SetWindowLong(hwnd, win32con.GCL_STYLE, csstyle)

    def GetBitmapStartLocation(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        bitmap: wx.Bitmap,
        text: str = "",
        style: int = 0,
    ) -> tuple[float, float]:
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
            tuple[float, float]: A tuple containing the top left `x` and `y`
                coordinates of the bitmap drawing.
        """
        alignment_buffer = self.GetAlignBuffer()

        # get the startLocationY
        fixed_text_width = fixed_text_height = 0

        if not text:
            fixed_text_height = bitmap.GetHeight()
        else:
            fixed_text_width, fixed_text_height = dc.GetTextExtent(text)

        start_location_y = rect.y + (rect.height - fixed_text_height) / 2

        # get the startLocationX
        if style & BU_EXT_RIGHT_TO_LEFT_STYLE:
            start_location_x = (
                rect.x + rect.width - alignment_buffer - bitmap.GetWidth()
            )
        elif style & BU_EXT_RIGHT_ALIGN_STYLE:
            max_width = (
                rect.x + rect.width - (2 * alignment_buffer) - bitmap.GetWidth()
            )  # the alignment is for both sides

            # get the truncated text. The text may stay as is, it is not a
            # must that is will be truncated
            fixed_text = self.TruncateText(dc, text, max_width)

            # get the fixed text dimensions
            fixed_text_width, _ = dc.GetTextExtent(fixed_text)

            # calculate the start location
            start_location_x = max_width - fixed_text_width

        elif style & BU_EXT_LEFT_ALIGN_STYLE:
            # calculate the start location
            start_location_x = alignment_buffer

        else:  # meaning BU_EXT_CENTER_ALIGN_STYLE
            max_width = (
                rect.x + rect.width - (2 * alignment_buffer) - bitmap.GetWidth()
            )  # the alignment is for both sides

            # get the truncated text. The text may stay as is, it is not a
            # must that is will be truncated
            fixed_text = self.TruncateText(dc, text, max_width)

            # get the fixed text dimensions
            fixed_text_width, _ = dc.GetTextExtent(fixed_text)

            if max_width > fixed_text_width:
                # calculate the start location
                start_location_x = (max_width - fixed_text_width) / 2

            else:
                # calculate the start location
                start_location_x = max_width - fixed_text_width

        # it is very important to validate that the start location is not less
        # than the alignment buffer
        start_location_x = max(start_location_x, alignment_buffer)

        return start_location_x, start_location_y

    def GetTextStartLocation(  # noqa: N802
        self, dc: wx.DC, rect: wx.Rect, bitmap: wx.Bitmap, text: str, style: int = 0
    ) -> tuple[float, float, None | str]:
        """Return the top left `x` and `y` coordinates of the text drawing.

        In case the text is too long, the text is being fixed (the text is cut
        and a '...' mark is added in the end).

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The text's client rectangle.
            bitmap (wx.Bitmap): The bitmap associated with the button.
            text (str): The button label.
            style (int): The button style.

        Returns:
            tuple[float, float, None | str]: A tuple containing the top
                left `x` and `y` coordinates of the text drawing, plus the
                truncated version of the input `text`.

        See :meth:`~ArtManager.GetBitmapStartLocation`for a list of valid button
        styles.
        """
        alignment_buffer = self.GetAlignBuffer()

        # get the bitmap offset
        bitmap_offset = 0
        if bitmap != wx.NullBitmap:
            bitmap_offset = bitmap.GetWidth()

        # get the truncated text.
        # The text may stay as is, it is not a must that it will be truncated
        max_width = (
            rect.x + rect.width - (2 * alignment_buffer) - bitmap_offset
        )  # the alignment is for both sides
        fixed_text = self.TruncateText(dc, text, max_width)

        # get the fixed text dimensions
        fixed_text_width, fixed_text_height = dc.GetTextExtent(fixed_text)
        start_location_y = (rect.height - fixed_text_height) / 2 + rect.y

        # get the startLocationX
        if style & BU_EXT_RIGHT_TO_LEFT_STYLE:
            start_location_x = max_width - fixed_text_width + alignment_buffer
        elif style & BU_EXT_LEFT_ALIGN_STYLE:
            # calculate the start location
            start_location_x = bitmap_offset + alignment_buffer
        elif style & BU_EXT_RIGHT_ALIGN_STYLE:
            # calculate the start location
            start_location_x = (
                max_width - fixed_text_width + bitmap_offset + alignment_buffer
            )
        else:  # meaning wxBU_EXT_CENTER_ALIGN_STYLE
            # calculate the start location
            start_location_x = (
                (max_width - fixed_text_width) / 2 + bitmap_offset + alignment_buffer
            )

        # it is very important to validate that the start location is not less
        # than the alignment buffer
        start_location_x = max(start_location_x, alignment_buffer)

        return start_location_x, start_location_y, fixed_text

    def DrawTextAndBitmap(  # noqa: N802
        self,
        dc: wx.DC,
        rect: wx.Rect,
        text: str,
        enable: bool = True,
        font: wx.Font = wx.NullFont,
        font_colour: wx.Colour = wx.BLACK,
        bitmap: wx.Bitmap = wx.NullBitmap,
        gray_bitmap: wx.Bitmap = wx.NullBitmap,
        style: int = 0,
    ) -> None:
        """Draw the text & bitmap on the input dc.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The text and bitmap client rectangle.
            text (str): the button label.
            enable (bool): ``True`` if the button is enabled, ``False`` otherwise.
            font (wx.Font): The font to use to draw the text.
            font_colour (wx.Colour): The colour to use to draw the text.
            bitmap (wx.Bitmap): The bitmap associated with the button.
            gray_bitmap (wx.Bitmap): A greyed-out version of the input `bitmap`
                representing a disabled bitmap.
            style (int): The button style.

        See: :meth:`~ArtManager.GetBitmapStartLocation` for a list of valid button
            styles.
        """
        # enable colours
        if enable:
            dc.SetTextForeground(font_colour)
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        # set the font
        if font.IsSameAs(wx.NullFont):
            font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

        dc.SetFont(font)

        start_location_x = start_location_y = 0.0

        if not bitmap.IsSameAs(wx.NullBitmap):
            # calculate the bitmap start location
            start_location_x, start_location_y = self.GetBitmapStartLocation(
                dc, rect, bitmap, text, style
            )

            # draw the bitmap
            if enable:
                dc.DrawBitmap(bitmap, start_location_x, start_location_y, True)
            else:
                dc.DrawBitmap(gray_bitmap, start_location_x, start_location_y, True)

        # calculate the text start location
        location, label_only = self.GetAccelIndex(text)
        start_location_x, start_location_y, fixed_text = self.GetTextStartLocation(
            dc, rect, bitmap, label_only, style
        )

        if fixed_text is None:
            fixed_text = ""

        # after all the calculations are finished, it is time to draw the text underline
        # the first letter that is marked with a '&'
        if location == -1 or font.GetUnderlined() or location >= len(fixed_text):
            # draw the text
            dc.DrawText(fixed_text, start_location_x, start_location_y)
        else:
            # underline the first '&'
            before = fixed_text[0:location]
            underline_letter = fixed_text[location]
            after = fixed_text[location + 1 :]

            # before
            dc.DrawText(before, start_location_x, start_location_y)

            # underlineLetter
            if "__WXGTK__" not in wx.Platform:
                w1, _ = dc.GetTextExtent(before)
                font.SetUnderlined(True)
                dc.SetFont(font)
                dc.DrawText(underline_letter, start_location_x + w1, start_location_y)
            else:
                w1, _ = dc.GetTextExtent(before)
                dc.DrawText(underline_letter, start_location_x + w1, start_location_y)

                # Draw the underline ourselves since using the Underline in GTK,
                # causes the line to be too close to the letter
                uderline_letter_w, uderline_letter_h = dc.GetTextExtent(
                    underline_letter
                )

                cur_pen = dc.GetPen()
                dc.SetPen(wx.BLACK_PEN)

                dc.DrawLine(
                    start_location_x + w1,
                    start_location_y + uderline_letter_h - 2,
                    start_location_x + w1 + uderline_letter_w,
                    start_location_y + uderline_letter_h - 2,
                )
                dc.SetPen(cur_pen)

            # after
            w2, _ = dc.GetTextExtent(underline_letter)
            font.SetUnderlined(False)
            dc.SetFont(font)
            dc.DrawText(after, start_location_x + w1 + w2, start_location_y)

    def CalcButtonBestSize(self, label: str, bmp: wx.Bitmap) -> wx.Size:  # noqa: N802
        """Return the best fit size for the supplied label & bitmap.

        Args:
            label (str): The button label.
            bmp (wx.Bitmap): The bitmap associated with the button.

        Returns:
            wx.Size: Representing the best fit size for the supplied label & bitmap.
        """
        default_height = 22 if "__WXMSW__" in wx.Platform else 26

        dc = wx.MemoryDC()
        dc.SelectBitmap(wx.Bitmap(1, 1))

        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        width, height, _ = dc.GetFullMultiLineTextExtent(label)

        width += 2 * self.GetAlignBuffer()

        if bmp.IsOk():
            # allocate extra space for the bitmap
            height_bmp = bmp.GetHeight() + 2
            height = max(height, height_bmp)

            width += bmp.GetWidth() + 2

        height = max(height, default_height)

        dc.SelectBitmap(wx.NullBitmap)

        return wx.Size(width, height)

    def GetMenuFaceColour(self) -> wx.Colour:  # noqa: N802
        """Return the colour used for the menu foreground.

        Returns:
            wx.Colour: The colour used for the menu foreground.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetMenuFaceColour()

    def GetTextColourEnable(self) -> wx.Colour:  # noqa: N802
        """Return the colour used for enabled menu items.

        Returns:
            wx.Colour: The colour used for enabled menu items.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetTextColourEnable()

    def GetTextColourDisable(self) -> wx.Font:  # noqa: N802
        """Return the colour used for disabled menu items.

        Returns:
            wx.Colour: The colour used for disabled menu items.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetTextColourDisable()

    def GetFont(self) -> wx.Font:  # noqa: N802
        """Return the font used by this theme.

        Returns:
            wx.Font: The font used by this theme.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        return renderer.GetFont()

    def GetAccelIndex(self, label: str) -> tuple[int, str]:  # noqa: N802
        """Return the mnemonic index and the label without the ampersand mnemonic.

        (e.g. 'lab&el' ==> will result in 3 and labelOnly = label).

        Args:
            label (str): A string containing an ampersand.

        Returns:
            tuple[int, str]: A tuple containing the mnemonic index of the label
                and the label stripped of the ampersand mnemonic.
        """
        index_accel = 0
        while True:
            index_accel = label.find("&", index_accel)
            if index_accel == -1:
                return index_accel, label
            if label[index_accel : index_accel + 2] == "&&":
                label = label[0:index_accel] + label[index_accel + 1 :]
                index_accel += 1
            else:
                break

        label_only = label[0:index_accel] + label[index_accel + 1 :]

        return index_accel, label_only

    def GetThemeBaseColour(self, use_light_colours: None | bool = True) -> wx.Colour:  # noqa: N802
        """Return the theme base colour.

        If no theme is active, return the active caption colour lightened by 30%.

        Args:
            use_light_colours (None | bool): ``True`` to use light colours,
                ``False`` otherwise.

        Returns:
            wx.Colour: The theme base colour or the 30% lightened active caption
                colour.
        """
        if not use_light_colours and not self.IsDark(self.FrameColour()):
            return wx.Colour("GOLD")
        return self.LightColour(self.FrameColour(), 30)

    def GetAlignBuffer(self) -> int:  # noqa: N802
        """Return the padding buffer for a text or bitmap.

        Returns:
            int: An integer representing the padding buffer.
        """
        return self._alignment_buffer

    def SetMenuTheme(self, theme: int) -> None:  # noqa: N802
        """Set the menu theme, possible values (Style2007, StyleXP, StyleVista).

        Args:
            theme (int): A rendering theme class, either `StyleXP`, `Style2007` or
                `StyleVista`.
        """
        self._menu_theme = theme

    def GetMenuTheme(self) -> int:  # noqa: N802
        """Return the currently used menu theme.

        Returns:
            int: An int containing the currently used theme for the menu.
        """
        return self._menu_theme

    def AddMenuTheme(self, render: RendererBase) -> int:  # noqa: N802
        """Add a new theme to the stock.

        Args:
            render (RendererBase): A rendering theme class, which must be
                derived from :class:`RendererBase`.

        Returns:
            int: An integer representing the size of the renderers dictionary.
        """
        # Add new theme
        last_renderer = len(self._renderers)
        self._renderers[last_renderer] = render

        return last_renderer

    def SetMS2007ButtonSunken(self, sunken: bool) -> None:  # noqa: N802
        """Set MS 2007 button style sunken or not.

        Args:
            sunken (bool): ``True`` to have a sunken border effect, ``False``
                otherwise.
        """
        self._ms2007sunken = sunken

    def GetMS2007ButtonSunken(self) -> bool:  # noqa: N802
        """Return the sunken flag for MS 2007 buttons.

        Returns:
            bool: ``True`` if the MS 2007 buttons are sunken, ``False`` otherwise.
        """
        return self._ms2007sunken

    def GetMBVerticalGradient(self) -> bool:  # noqa: N802
        """Return ``True`` if the menu bar should be painted with vertical gradient.

        Returns:
            bool: A boolean indicating whether the menu bar should be painted with
                vertical gradient.
        """
        return self._vertical_gradient

    def SetMBVerticalGradient(self, v: bool) -> None:  # noqa: N802
        """Set the menu bar gradient style.

        Args:
            v (bool): ``True`` for a vertical shaded gradient, ``False`` otherwise.
        """
        self._vertical_gradient = v

    def DrawMenuBarBorder(self, border: bool) -> None:  # noqa: N802
        """Enable menu border drawing (XP style only).

        Args:
            border (bool): ``True`` to draw the menubar border, ``False`` otherwise.
        """
        self._draw_mb_border = border

    def GetMenuBarBorder(self) -> bool:  # noqa: N802
        """Return menu bar border drawing flag.

        Returns:
            bool: ``True`` if the menu bar border is to be drawn, ``False`` otherwise.
        """
        return self._draw_mb_border

    def GetMenuBgFactor(self) -> int:  # noqa: N802
        """Return the visibility depth of the menu in Metallic style.

        The higher the value, the menu bar will look more raised.

        Returns:
            int: An integer representing the visibility depth of the menu.
        """
        return self._menu_bg_factor

    def DrawDragSash(self, rect: wx.Rect) -> None:  # noqa: N802
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

    def TakeScreenShot(self, rect: wx.Rect, bmp: wx.Bitmap) -> None:  # noqa: N802
        """Take a screenshot of the screen at given position & size (rect).

        Args:
            rect (wx.Rect): The screen rectangle we wish to capture.
            bmp (wx.Bitmap): Currently unused.
        """
        # Create a DC for the whole screen area
        dc_screen = wx.ScreenDC()

        # Create a Bitmap that will later on hold the screenshot image
        # Note that the Bitmap must have a size big enough to hold the screenshot
        # -1 means using the current default colour depth
        bmp = wx.Bitmap(rect.width, rect.height)

        # Create a memory DC that will be used for actually taking the screenshot
        mem_dc = wx.MemoryDC()

        # Tell the memory DC to use our Bitmap
        # all drawing action on the memory DC will go to the Bitmap now
        mem_dc.SelectObject(bmp)

        # Blit (in this case copy)
        # the actual screen on the memory DC and thus the Bitmap
        mem_dc.Blit(
            0,  # Copy to this X coordinate
            0,  # Copy to this Y coordinate
            rect.width,  # Copy this width
            rect.height,  # Copy this height
            dc_screen,  # From where do we copy?
            rect.x,  # What's the X offset in the original DC?
            rect.y,  # What's the Y offset in the original DC?
        )

        # Select the Bitmap out of the memory DC by selecting a new uninitialized Bitmap
        mem_dc.SelectObject(wx.NullBitmap)

    def DrawToolBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
        """Draw the toolbar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The toolbar's client rectangle.
        """
        renderer = self._renderers[self.GetMenuTheme()]

        # Set background colour if non given by caller
        renderer.DrawToolBarBg(dc, rect)

    def DrawMenuBarBg(self, dc: wx.DC, rect: wx.Rect) -> None:  # noqa: N802
        """Draw the menu bar background according to the active theme.

        Args:
            dc (wx.DC): A :class:`wx.DC` instance.
            rect (wx.Rect): The menubar's client rectangle.
        """
        renderer = self._renderers[self.GetMenuTheme()]
        # Set background colour if non given by caller
        renderer.DrawMenuBarBg(dc, rect)

    def SetMenuBarColour(self, scheme: str) -> None:  # noqa: N802
        """Set the menu bar colour scheme to use.

        Args:
            scheme (str): A string representing a colour scheme (i.e., 'Default',
                'Dark', 'Dark Olive Green', 'Generic').
        """
        self._menu_bar_colour_scheme = scheme
        # set default colour
        if scheme in self._colourSchemeMap:
            self._menuBarBgColour = self._colourSchemeMap[scheme]

    def GetMenuBarColourScheme(self) -> str:  # noqa: N802
        """Return the current colour scheme.

        Returns:
            str: A string representing the current colour scheme.
        """
        return self._menu_bar_colour_scheme

    def GetMenuBarFaceColour(self) -> wx.Colour:  # noqa: N802
        """Return the menu bar face colour.

        Returns:
            wx.Colour: The menu bar face colour.
        """
        return self._menuBarBgColour

    def GetMenuBarSelectionColour(self) -> wx.Colour:  # noqa: N802
        """Return the menu bar selection colour.

        Returns:
            wx.Colour: The menu bar selection colour.
        """
        return self._menuBarSelColour

    def InitColours(self) -> None:  # noqa: N802
        """Initialise the colour map."""
        self._colourSchemeMap = {
            _("Default"): wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DFACE),
            _("Dark"): wx.BLACK,
            _("Dark Olive Green"): wx.Colour("DARK OLIVE GREEN"),
            _("Generic"): wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION),
        }

    def GetColourSchemes(self) -> list[str]:  # noqa: N802
        """Return the available colour schemes.

        Returns:
            list[str]: A list of strings representing the available colour
                schemes.
        """
        return list(self._colourSchemeMap)

    def CreateGreyBitmap(self, bmp: wx.Bitmap) -> wx.Bitmap:  # noqa: N802
        """Create a grey bitmap image from the input bitmap.

        Args:
            bmp (wx.Bitmap): A valid :class:`wx.Bitmap` object to be greyed out.

        Returns:
            wx.Bitmap: A greyed-out representation of the input bitmap.
        """
        img = bmp.ConvertToImage()
        return wx.Bitmap(img.ConvertToGreyscale())

    def GetRaiseToolbar(self) -> bool:  # noqa: N802
        """Return ``True`` if we are dropping a shadow under a toolbar.

        Returns:
            bool: A boolean indicating whether a shadow is dropped under a
                toolbar.
        """
        return self._raise_trace_back

    def SetRaiseToolbar(self, raise_: bool) -> None:  # noqa: N802
        """Enable/disable toobar shadow drop.

        Args:
            raise_ (bool): ``True`` to drop a shadow below a toolbar, ``False``
                otherwise.
        """
        self._raise_trace_back = raise_
