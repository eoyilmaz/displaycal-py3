# -*- coding: UTF-8 -*-
"""
Interactive display calibration UI
"""

import os
import re
import sys

if sys.platform == "win32":
    from ctypes import windll
elif sys.platform == "darwin":
    from platform import mac_ver

from DisplayCAL.wxaddons import wx
from DisplayCAL.lib.agw import labelbook
from DisplayCAL.lib.agw.fmresources import *
from DisplayCAL.lib.agw.pygauge import PyGauge

from DisplayCAL.config import (
    get_data_path,
    get_default_dpi,
    get_icon_bundle,
    getbitmap,
    getcfg,
    geticon,
    setcfg,
)
from DisplayCAL.config import enc
from DisplayCAL.log import get_file_logger
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug
from DisplayCAL.util_list import intlist
from DisplayCAL.util_str import wrap
from DisplayCAL.wxwindows import (
    BaseApp,
    BaseFrame,
    FlatShadedButton,
    numpad_keycodes,
    nav_keycodes,
    processing_keycodes,
    wx_Panel,
)
from DisplayCAL import audio
from DisplayCAL import config
from DisplayCAL import localization as lang

BGCOLOUR = wx.Colour(0x33, 0x33, 0x33)
BORDERCOLOUR = wx.Colour(0x22, 0x22, 0x22)
FGCOLOUR = wx.Colour(0x99, 0x99, 0x99)

CRT = True


def get_panel(parent, size=wx.DefaultSize):
    scale = max(getcfg("app.dpi") / get_default_dpi(), 1.0)
    size = tuple(int(round(v * scale)) for v in size)
    panel = wx_Panel(parent, wx.ID_ANY, size=size)
    if debug:
        from random import randint

        panel.SetBackgroundColour(
            wx.Colour(randint(0, 255), randint(0, 255), randint(0, 255))
        )
        get_panel.i += 1
        wx.StaticText(panel, wx.ID_ANY, str(get_panel.i) + " " + str(size))
    else:
        panel.SetBackgroundColour(BGCOLOUR)
    return panel


get_panel.i = 0


def get_xy_vt_dE(groups):
    x = float(groups[0])
    y = float(groups[1])
    vt = ""
    dE = 0
    if len(groups) > 2:
        vt = groups[2] or ""
        if groups[3]:
            dE = float(groups[3])
    return x, y, vt, dE


def set_label_and_size(txtctrl, label):
    txtctrl.SetMinSize((txtctrl.GetSize()[0], -1))
    txtctrl.SetLabel(label)
    txtctrl.SetMinSize(txtctrl.GetSize())


class DisplayAdjustmentImageContainer(labelbook.ImageContainer):
    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agwStyle=0,
        name="ImageContainer",
    ):
        """Override default agw ImageContainer to use BackgroundColour and
        ForegroundColour with no borders/labeltext and hilite image instead of
        hilite shading
        """
        labelbook.ImageContainer.__init__(
            self, parent, id, pos, size, style, agwStyle, name
        )
        imagelist = None
        for img in ("tab_hilite", "tab_selected"):
            bmp = getbitmap("theme/%s" % img)
            if not imagelist:
                img_w, img_h = bmp.Size
                imagelist = wx.ImageList(img_w, img_h)
            imagelist.Add(bmp)
        self.stateimgs = imagelist

    def HitTest(self, pt):
        """Returns the index of the tab at the specified position or ``wx.NOT_FOUND``
        if ``None``, plus the flag style of L{HitTest}.

        :param pt: an instance of `wx.Point`, to test for hits.

        :return: The index of the tab at the specified position plus the hit test
         flag, which can be one of the following bits:

         ====================== ======= ================================
         HitTest Flags           Value  Description
         ====================== ======= ================================
         ``IMG_OVER_IMG``             0 The mouse is over the tab icon
         ``IMG_OVER_PIN``             1 The mouse is over the pin button
         ``IMG_OVER_EW_BORDER``       2 The mouse is over the east-west book border
         ``IMG_NONE``                 3 Nowhere
         ====================== ======= ================================

        """

        if self.GetParent().GetParent().is_busy:
            return -1, IMG_NONE

        style = self.GetParent().GetAGWWindowStyleFlag()

        if style & INB_USE_PIN_BUTTON:
            if self._pinBtnRect.Contains(pt):
                return -1, IMG_OVER_PIN

        for i in range(len(self._pagesInfoVec)):

            if self._pagesInfoVec[i].GetPosition() == wx.Point(-1, -1):
                break
            if i in self.GetParent().disabled_pages:
                continue

            # For Web Hover style, we test the TextRect
            if not self.HasAGWFlag(INB_WEB_HILITE):
                buttonRect = wx.RectPS(
                    (
                        self._pagesInfoVec[i].GetPosition()[0],
                        self._pagesInfoVec[i].GetPosition()[1] + i * 8,
                    ),
                    self._pagesInfoVec[i].GetSize(),
                )
            else:
                buttonRect = self._pagesInfoVec[i].GetTextRect()

            if buttonRect.Contains(pt):
                return i, IMG_OVER_IMG

        if self.PointOnSash(pt):
            return -1, IMG_OVER_EW_BORDER
        else:
            return -1, IMG_NONE

    def OnPaint(self, event):
        """Handles the ``wx.EVT_PAINT`` event for L{ImageContainer}.

        :param event: a `wx.PaintEvent` event to be processed.
        """

        dc = wx.BufferedPaintDC(self)
        style = self.GetParent().GetAGWWindowStyleFlag()

        backBrush = wx.Brush(self.GetBackgroundColour())
        if style & INB_BORDER:
            borderPen = wx.Pen(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DSHADOW))
        else:
            borderPen = wx.TRANSPARENT_PEN

        size = self.GetSize()

        # Background
        dc.SetBrush(backBrush)

        borderPen.SetWidth(1)
        dc.SetPen(borderPen)
        dc.DrawRectangle(0, 0, size.x, size.y)
        bUsePin = (style & INB_USE_PIN_BUTTON and [True] or [False])[0]

        if bUsePin:

            # Draw the pin button
            clientRect = self.GetClientRect()
            pinRect = wx.Rect(clientRect.GetX() + clientRect.GetWidth() - 20, 2, 20, 20)
            self.DrawPin(dc, pinRect, not self._bCollapsed)

            if self._bCollapsed:
                return

        clientSize = 0
        bUseYcoord = style & INB_RIGHT or style & INB_LEFT

        if bUseYcoord:
            clientSize = size.GetHeight()
        else:
            clientSize = size.GetWidth()

        # We reserver 20 pixels for the 'pin' button

        # The drawing of the images start position. This is
        # depenedent of the style, especially when Pin button
        # style is requested

        if bUsePin:
            if style & INB_TOP or style & INB_BOTTOM:
                pos = (style & INB_BORDER and [0] or [1])[0]
            else:
                pos = (style & INB_BORDER and [20] or [21])[0]
        else:
            pos = (style & INB_BORDER and [0] or [1])[0]

        nPadding = 4  # Pad text with 2 pixels on the left and right
        nTextPaddingLeft = 2

        count = 0

        for i in range(len(self._pagesInfoVec)):
            if (
                self.GetParent().GetParent().is_busy
                and i != self.GetParent().GetSelection()
            ):
                continue
            if i in self.GetParent().disabled_pages:
                continue

            count = count + 1

            # incase the 'fit button' style is applied, we set the rectangle width to the
            # text width plus padding
            # Incase the style IS applied, but the style is either LEFT or RIGHT
            # we ignore it
            normalFont = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
            dc.SetFont(normalFont)

            textWidth, textHeight = dc.GetTextExtent(self._pagesInfoVec[i].GetCaption())

            # Restore font to be normal
            normalFont.SetWeight(wx.FONTWEIGHT_NORMAL)
            dc.SetFont(normalFont)

            # Default values for the surronounding rectangle
            # around a button
            rectWidth = self._nImgSize  # To avoid the recangle to 'touch' the borders
            rectHeight = self._nImgSize

            # Incase the style requires non-fixed button (fit to text)
            # recalc the rectangle width
            if (
                style & INB_FIT_BUTTON
                and not ((style & INB_LEFT) or (style & INB_RIGHT))
                and not self._pagesInfoVec[i].GetCaption() == ""
                and not (style & INB_SHOW_ONLY_IMAGES)
            ):

                rectWidth = (
                    (textWidth + nPadding * 2) > rectWidth
                    and [nPadding * 2 + textWidth]
                    or [rectWidth]
                )[0]

                # Make the width an even number
                if rectWidth % 2 != 0:
                    rectWidth += 1

            # Check that we have enough space to draw the button
            # If Pin button is used, consider its space as well (applicable for top/botton style)
            # since in the left/right, its size is already considered in 'pos'
            pinBtnSize = (bUsePin and [20] or [0])[0]

            if pos + rectWidth + pinBtnSize > clientSize:
                break

            # Calculate the button rectangle
            modRectWidth = (
                (style & INB_LEFT or style & INB_RIGHT)
                and [rectWidth - 2]
                or [rectWidth]
            )[0]
            modRectHeight = (
                (style & INB_LEFT or style & INB_RIGHT)
                and [rectHeight]
                or [rectHeight - 2]
            )[0]

            if bUseYcoord:
                buttonRect = wx.Rect(1, pos, modRectWidth, modRectHeight)
            else:
                buttonRect = wx.Rect(pos, 1, modRectWidth, modRectHeight)

            if bUseYcoord:
                rect = wx.Rect(0, pos, rectWidth, rectWidth)
            else:
                rect = wx.Rect(pos, 0, rectWidth, rectWidth)

            # Incase user set both flags:
            # INB_SHOW_ONLY_TEXT and INB_SHOW_ONLY_IMAGES
            # We override them to display both

            if style & INB_SHOW_ONLY_TEXT and style & INB_SHOW_ONLY_IMAGES:

                style ^= INB_SHOW_ONLY_TEXT
                style ^= INB_SHOW_ONLY_IMAGES
                self.GetParent().SetAGWWindowStyleFlag(style)

            # Draw the caption and text
            imgTopPadding = 0
            if (
                not style & INB_SHOW_ONLY_TEXT
                and self._pagesInfoVec[i].GetImageIndex() != -1
            ):

                if bUseYcoord:

                    imgXcoord = 0
                    imgYcoord = (
                        style & INB_SHOW_ONLY_IMAGES and [pos] or [pos + imgTopPadding]
                    )[0] + (8 * (count - 1))

                else:

                    imgXcoord = pos + (rectWidth / 2) - (self._nImgSize / 2)
                    imgYcoord = (
                        style & INB_SHOW_ONLY_IMAGES
                        and [self._nImgSize / 2]
                        or [imgTopPadding]
                    )[0]

                if self._nHoeveredImgIdx == i:
                    self.stateimgs.Draw(
                        0, dc, 0, imgYcoord, wx.IMAGELIST_DRAW_TRANSPARENT, True
                    )

                if self._nIndex == i:
                    self.stateimgs.Draw(
                        1, dc, 0, imgYcoord, wx.IMAGELIST_DRAW_TRANSPARENT, True
                    )

                self._ImageList.Draw(
                    self._pagesInfoVec[i].GetImageIndex(),
                    dc,
                    imgXcoord,
                    imgYcoord,
                    wx.IMAGELIST_DRAW_TRANSPARENT,
                    True,
                )

            # Draw the text
            if (
                not style & INB_SHOW_ONLY_IMAGES
                and not self._pagesInfoVec[i].GetCaption() == ""
            ):

                dc.SetFont(normalFont)

                # Check if the text can fit the size of the rectangle,
                # if not truncate it
                fixedText = self._pagesInfoVec[i].GetCaption()
                if not style & INB_FIT_BUTTON or (
                    style & INB_LEFT or (style & INB_RIGHT)
                ):

                    fixedText = self.FixTextSize(
                        dc, self._pagesInfoVec[i].GetCaption(), self._nImgSize * 2 - 4
                    )

                    # Update the length of the text
                    textWidth, textHeight = dc.GetTextExtent(fixedText)

                if bUseYcoord:

                    textOffsetX = (rectWidth - textWidth) / 2
                    textOffsetY = (
                        not style & INB_SHOW_ONLY_TEXT
                        and [pos + self._nImgSize + imgTopPadding + 3]
                        or [pos + ((self._nImgSize * 2 - textHeight) / 2)]
                    )[0]

                else:

                    textOffsetX = (rectWidth - textWidth) / 2 + pos + nTextPaddingLeft
                    textOffsetY = (
                        not style & INB_SHOW_ONLY_TEXT
                        and [self._nImgSize + imgTopPadding + 3]
                        or [((self._nImgSize * 2 - textHeight) / 2)]
                    )[0]

                dc.SetTextForeground(self.GetForegroundColour())
                dc.DrawText(fixedText, textOffsetX, textOffsetY)

            # Update the page info
            self._pagesInfoVec[i].SetPosition(buttonRect.GetPosition())
            self._pagesInfoVec[i].SetSize(buttonRect.GetSize())

            pos += rectWidth

        # Update all buttons that can not fit into the screen as non-visible
        # for ii in range(count, len(self._pagesInfoVec)):
        # self._pagesInfoVec[ii].SetPosition(wx.Point(-1, -1))

        # Draw the pin button
        if bUsePin:

            clientRect = self.GetClientRect()
            pinRect = wx.Rect(clientRect.GetX() + clientRect.GetWidth() - 20, 2, 20, 20)
            self.DrawPin(dc, pinRect, not self._bCollapsed)


class DisplayAdjustmentFlatImageBook(labelbook.FlatImageBook):
    """Override default agw ImageContainer to use BackgroundColour and ForegroundColour with no borders/labeltext and
    hilite image instead of hilite shading
    """

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agwStyle=0,
        name="FlatImageBook",
    ):
        labelbook.FlatImageBook.__init__(
            self, parent, id, pos, size, style, agwStyle, name
        )

    def CreateImageContainer(self):
        return DisplayAdjustmentImageContainer(
            self, wx.ID_ANY, agwStyle=self.GetAGWWindowStyleFlag()
        )

    def SetAGWWindowStyleFlag(self, agwStyle):
        """Sets the window style.

        :param agwStyle: can be a combination of the following bits.

         =========================== =========== ==================================================
         Window Styles               Hex Value   Description
         =========================== =========== ==================================================
         ``INB_BOTTOM``                      0x1 Place labels below the page area. Available only for L{FlatImageBook}.
         ``INB_LEFT``                        0x2 Place labels on the left side. Available only for L{FlatImageBook}.
         ``INB_RIGHT``                       0x4 Place labels on the right side.
         ``INB_TOP``                         0x8 Place labels above the page area.
         ``INB_BORDER``                     0x10 Draws a border around L{LabelBook} or L{FlatImageBook}.
         ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no images. Available only for L{LabelBook}.
         ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no label texts. Available only for L{LabelBook}.
         ``INB_FIT_BUTTON``                 0x80 Displays a pin button to show/hide the book control.
         ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book tabs. Available only for L{LabelBook}.
         ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to show/hide the book control.
         ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the tabs background. Available only for L{LabelBook}.
         ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave like html hyperlinks. Available only for L{LabelBook}.
         ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab area.
         ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the longest text (or text+image if you have images) in all the tabs.
         =========================== =========== ==================================================
        """

        self._agwStyle = agwStyle

        # Check that we are not in initialization process
        if self._bInitializing:
            return

        if not self._pages:
            return

        # Detach the windows attached to the sizer
        if self.GetSelection() >= 0:
            self._mainSizer.Detach(self._windows[self.GetSelection()])

        self._mainSizer.Detach(self._pages)

        # Create new sizer with the requested orientaion
        className = self.GetName()

        if className == "LabelBook":
            self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            if agwStyle & INB_LEFT or agwStyle & INB_RIGHT:
                self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
            else:
                self._mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.SetSizer(self._mainSizer)

        # Add the tab container and the separator
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)

        if className == "FlatImageBook":
            scale = getcfg("app.dpi") / get_default_dpi()
            if scale < 1:
                scale = 1
            if agwStyle & INB_LEFT or agwStyle & INB_RIGHT:
                border = int(round(24 * scale))
                self._pages.SetSizeHints(self._pages._nImgSize + border, -1)
            else:
                self._pages.SetSizeHints(-1, self._pages._nImgSize)

        # Attach the windows back to the sizer to the sizer
        if self.GetSelection() >= 0:
            self.DoSetSelection(self._windows[self.GetSelection()])

        if agwStyle & INB_FIT_LABELTEXT:
            self.ResizeTabArea()

        self._mainSizer.Layout()
        dummy = wx.SizeEvent(wx.DefaultSize)
        wx.PostEvent(self, dummy)
        self._pages.Refresh()


class DisplayAdjustmentPanel(wx_Panel):
    def __init__(self, parent=None, id=wx.ID_ANY, title="", ctrltype="luminance"):
        # wx_Panel.__init__(self, parent, id)
        super(DisplayAdjustmentPanel, self).__init__(parent, id)
        self.ctrltype = ctrltype
        self.SetBackgroundColour(BGCOLOUR)
        self.SetForegroundColour(FGCOLOUR)
        self.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.title_txt = wx.StaticText(self, wx.ID_ANY, title)
        font = self.title_txt.GetFont()
        font.SetPointSize(font.PointSize + 1)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title_txt.SetFont(font)
        self.title_txt.SetForegroundColour(FGCOLOUR)
        self.GetSizer().Add(self.title_txt)
        self.sizer = wx.FlexGridSizer(0, 2, 0, 0)
        self.GetSizer().Add(self.sizer, flag=wx.TOP, border=8)
        self.gauges = dict()
        self.txt = dict()
        if ctrltype == "check_all":
            txt = wx.StaticText(
                self,
                wx.ID_ANY,
                lang.getstr("calibration.interactive_display_adjustment.check_all"),
            )
            txt.SetForegroundColour(FGCOLOUR)
            txt.SetMaxFontSize(10)
            txt.Wrap(250)
            self.desc = txt
            self.GetSizer().Insert(1, txt, flag=wx.TOP, border=8)
            for name, lstr in (
                ("luminance", "calibration.luminance"),
                ("black_level", "calibration.black_luminance"),
                ("white_point", "whitepoint"),
                ("black_point", "black_point"),
            ):
                bitmap = wx.StaticBitmap(
                    self, wx.ID_ANY, getbitmap("theme/icons/16x16/%s" % name)
                )
                bitmap.SetToolTipString(lang.getstr(lstr))
                self.add_txt(name, bitmap, 4)
            return
        if ctrltype.startswith("rgb"):
            if ctrltype == "rgb_offset":
                # CRT
                lstr = "calibration.interactive_display_adjustment.black_point.crt"
            else:
                lstr = "calibration.interactive_display_adjustment.white_point"
            txt = wx.StaticText(
                self,
                wx.ID_ANY,
                lang.getstr(lstr)
                + " "
                + lang.getstr(
                    "calibration.interactive_display_adjustment.generic_hint.plural"
                ),
            )
            txt.SetForegroundColour(FGCOLOUR)
            txt.SetMaxFontSize(10)
            txt.Wrap(250)
            self.desc = txt
            self.GetSizer().Insert(1, txt, flag=wx.TOP, border=8)
            self.sizer.Add((1, 4))
            self.sizer.Add((1, 4))
            self.add_marker()
            self.add_gauge("R", ctrltype + "_red", "R")
            self.sizer.Add((1, 4))
            self.sizer.Add((1, 4))
            self.add_gauge("G", ctrltype + "_green", "G")
            self.sizer.Add((1, 4))
            self.sizer.Add((1, 4))
            self.add_gauge("B", ctrltype + "_blue", "B")
            self.add_marker("btm")
            self.add_txt("rgb")
        else:
            txt = wx.StaticText(self, wx.ID_ANY, " ")
            txt.SetForegroundColour(FGCOLOUR)
            txt.SetMaxFontSize(10)
            txt.Wrap(250)
            self.desc = txt
            self.GetSizer().Insert(1, txt, flag=wx.TOP, border=8)
        self.sizer.Add((1, 4))
        self.sizer.Add((1, 4))
        self.add_marker()
        bitmapnames = {"rgb_offset": "black_level", "rgb_gain": "luminance"}
        lstrs = {
            "black_level": "calibration.black_luminance",
            "rgb_offset": "calibration.black_luminance",
            "rgb_gain": "calibration.luminance",
            "luminance": "calibration.luminance",
        }
        self.add_gauge(
            "L",
            bitmapnames.get(ctrltype, ctrltype),
            lang.getstr(lstrs.get(ctrltype, ctrltype)),
        )
        self.add_marker("btm")
        self.add_txt("luminance")

    def add_gauge(self, name="R", bitmapname=None, tooltip=None):
        if bitmapname == "black_level" or bitmapname.startswith("rgb_offset"):
            gaugecolors = {
                "R": (wx.Colour(102, 0, 0), wx.Colour(204, 0, 0)),
                "G": (wx.Colour(0, 102, 0), wx.Colour(0, 204, 0)),
                "B": (wx.Colour(0, 0, 102), wx.Colour(0, 0, 204)),
                "L": (wx.Colour(102, 102, 102), wx.Colour(204, 204, 204)),
            }
        else:
            gaugecolors = {
                "R": (wx.Colour(153, 0, 0), wx.Colour(255, 0, 0)),
                "G": (wx.Colour(0, 153, 0), wx.Colour(0, 255, 0)),
                "B": (wx.Colour(0, 0, 153), wx.Colour(0, 0, 255)),
                "L": (wx.Colour(153, 153, 153), wx.Colour(255, 255, 255)),
            }
        scale = max(getcfg("app.dpi") / get_default_dpi(), 1.0)
        self.gauges[name] = PyGauge(
            self, size=(int(round(200 * scale)), int(round(8 * scale)))
        )
        self.gauges[name].SetBackgroundColour(BORDERCOLOUR)
        self.gauges[name].SetBarGradient(gaugecolors[name])
        self.gauges[name].SetBorderColour(BORDERCOLOUR)
        self.gauges[name].SetValue(0)
        if bitmapname:
            self.gauges[name].label = wx.StaticBitmap(
                self, wx.ID_ANY, getbitmap("theme/icons/16x16/%s" % bitmapname)
            )
            if tooltip:
                self.gauges[name].label.SetToolTipString(tooltip)
        else:
            self.gauges[name].label = wx.StaticText(self, wx.ID_ANY, name)
            self.gauges[name].label.SetForegroundColour(FGCOLOUR)
        self.sizer.Add(
            self.gauges[name].label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8
        )
        self.sizer.Add(self.gauges[name], flag=wx.ALIGN_CENTER_VERTICAL)

    def add_marker(self, direction="top"):
        self.sizer.Add((1, 1))
        scale = max(getcfg("app.dpi") / get_default_dpi(), 1.0)
        self.sizer.Add(
            wx.StaticBitmap(
                self,
                -1,
                getbitmap("theme/marker_%s" % direction),
                size=(int(round(200 * scale)), int(round(10 * scale))),
            )
        )

    def add_txt(self, name, spacer=None, border=8):
        checkmark = wx.StaticBitmap(
            self, wx.ID_ANY, getbitmap("theme/icons/16x16/checkmark")
        )
        txtsizer = wx.BoxSizer(wx.HORIZONTAL)
        if spacer:
            self.sizer.Add(spacer, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
            txtsizer.Add(checkmark, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        else:
            self.sizer.Add(
                checkmark,
                flag=wx.RIGHT | wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL,
                border=8,
            )
        initial = lang.getstr("initial")
        current = lang.getstr("current")
        target = lang.getstr("target")
        strings = {len(initial): initial, len(current): current, len(target): target}
        longest = strings[max(strings.keys())]
        label = longest + " x 0.0000 y 0.0000 VDT 0000K 0.0 \u0394E*00\nX"
        checkmark.GetContainingSizer().Hide(checkmark)
        self.sizer.Add(
            txtsizer,
            flag=wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND,
            border=border,
        )
        self.txt[name] = wx.StaticText(
            self, wx.ID_ANY, label, style=wx.ST_NO_AUTORESIZE
        )
        self.txt[name].SetForegroundColour(BGCOLOUR)
        self.txt[name].SetMaxFontSize(10)
        self.txt[name].checkmark = checkmark
        self.txt[name].spacer = spacer
        txtsizer.Add(self.txt[name], 1)
        self.txt[name].Fit()
        self.txt[name].SetMinSize(
            (self.txt[name].GetSize()[0], self.txt[name].GetSize()[1])
        )

    def update_desc(self):
        if self.ctrltype in ("luminance", "black_level"):
            if self.ctrltype == "black_level":
                lstr = "calibration.interactive_display_adjustment.black_level.crt"
            elif getcfg("measurement_mode") == "c":
                # CRT
                lstr = "calibration.interactive_display_adjustment.white_level.crt"
            else:
                lstr = "calibration.interactive_display_adjustment.white_level.lcd"
            self.desc.SetLabel(
                lang.getstr(lstr)
                + " "
                + lang.getstr(
                    "calibration.interactive_display_adjustment.generic_hint.singular"
                )
            )
            self.desc.Wrap(250)


NEVER = False
if os.getenv("XDG_SESSION_TYPE") == "wayland" and NEVER:
    windowcls = wx.Dialog
else:
    windowcls = BaseFrame


class DisplayAdjustmentFrame(windowcls):
    def __init__(self, parent=None, handler=None, keyhandler=None, start_timer=True):
        # windowcls.__init__(self, parent, wx.ID_ANY,
        #                    lang.getstr("calibration.interactive_display_adjustment"),
        #                    style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
        #                    name="displayadjustmentframe")
        super(DisplayAdjustmentFrame, self).__init__(
            parent,
            wx.ID_ANY,
            lang.getstr("calibration.interactive_display_adjustment"),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
            name="displayadjustmentframe",
        )
        self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))
        self.SetBackgroundColour(BGCOLOUR)
        self.sizer = wx.FlexGridSizer(0, 3, 0, 0)
        self.sizer.AddGrowableCol(1)
        self.sizer.AddGrowableRow(2)
        self.SetSizer(self.sizer)

        # FlatImageNotebook
        self.lb = DisplayAdjustmentFlatImageBook(
            self, agwStyle=INB_LEFT | INB_SHOW_ONLY_IMAGES
        )
        self.lb.SetBackgroundColour(BGCOLOUR)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.sizer.Add(self.lb, 1, flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)

        self.pagenum_2_argyll_key_num = {}

        # Page - black luminance
        self.page_black_luminance = DisplayAdjustmentPanel(
            self, wx.ID_ANY, lang.getstr("calibration.black_luminance"), "black_level"
        )
        self.lb.AddPage(
            self.page_black_luminance,
            lang.getstr("calibration.black_luminance"),
            True,
            0,
        )
        self.pagenum_2_argyll_key_num[len(self.pagenum_2_argyll_key_num)] = "1"

        # Page - white point
        self.page_white_point = DisplayAdjustmentPanel(
            self,
            wx.ID_ANY,
            lang.getstr("whitepoint") + " / " + lang.getstr("calibration.luminance"),
            "rgb_gain",
        )
        self.lb.AddPage(self.page_white_point, lang.getstr("whitepoint"), True, 1)
        self.pagenum_2_argyll_key_num[len(self.pagenum_2_argyll_key_num)] = "2"

        # Page - luminance
        self.page_luminance = DisplayAdjustmentPanel(
            self, wx.ID_ANY, lang.getstr("calibration.luminance")
        )
        self.lb.AddPage(
            self.page_luminance, lang.getstr("calibration.luminance"), True, 2
        )
        self.pagenum_2_argyll_key_num[len(self.pagenum_2_argyll_key_num)] = "3"

        # Page - black point
        self.page_black_point = DisplayAdjustmentPanel(
            self,
            wx.ID_ANY,
            lang.getstr("black_point")
            + " / "
            + lang.getstr("calibration.black_luminance"),
            "rgb_offset",
        )
        self.lb.AddPage(self.page_black_point, lang.getstr("black_point"), True, 3)
        self.pagenum_2_argyll_key_num[len(self.pagenum_2_argyll_key_num)] = "4"

        # Page - check all
        self.page_check_all = DisplayAdjustmentPanel(
            self, wx.ID_ANY, lang.getstr("calibration.check_all"), "check_all"
        )
        self.lb.AddPage(
            self.page_check_all, lang.getstr("calibration.check_all"), True, 4
        )
        self.pagenum_2_argyll_key_num[len(self.pagenum_2_argyll_key_num)] = "5"

        # Set colours on tab list
        self.lb.Children[0].SetBackgroundColour(BGCOLOUR)
        self.lb.Children[0].SetForegroundColour(FGCOLOUR)
        # Sound when measuring
        # Needs to be stereo!
        self.measurement_sound = audio.Sound(get_data_path("beep.wav"))

        # Add buttons
        self.btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.sizer.Add(self.btnsizer, flag=wx.ALIGN_RIGHT | wx.EXPAND)
        self.btnsizer.Add(get_panel(self, (2, 12)), 1, flag=wx.EXPAND)
        self.indicator_panel = get_panel(self, (22, 12))
        self.indicator_panel.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
        self.indicator_panel.SetForegroundColour(FGCOLOUR)
        self.btnsizer.Add(self.indicator_panel, flag=wx.EXPAND)
        scale = max(getcfg("app.dpi") / get_default_dpi(), 1.0)
        self.indicator_ctrl = wx.StaticBitmap(
            self.indicator_panel,
            wx.ID_ANY,
            geticon(10, "empty", use_mask=True),
            size=(int(round(10 * scale)), int(round(10 * scale))),
        )
        self.indicator_ctrl.SetForegroundColour(FGCOLOUR)
        self.indicator_panel.GetSizer().Add(
            self.indicator_ctrl, flag=wx.ALIGN_CENTER_VERTICAL
        )
        self.indicator_panel.GetSizer().Add(
            get_panel(self.indicator_panel, (10, 12)), flag=wx.EXPAND
        )
        self.create_start_interactive_adjustment_button()
        self.adjustment_btn.SetDefault()
        self.btnsizer.Add(get_panel(self, (6, 12)), flag=wx.EXPAND)
        bitmap = self.get_sound_on_off_btn_bitmap()
        self.sound_on_off_btn = self.create_gradient_button(
            bitmap, "", name="sound_on_off_btn"
        )
        self.sound_on_off_btn.SetToolTipString(lang.getstr("measurement.play_sound"))
        self.sound_on_off_btn.Bind(wx.EVT_BUTTON, self.measurement_play_sound_handler)
        self.btnsizer.Add(get_panel(self, (12, 12)), flag=wx.EXPAND)
        self.calibration_btn = self.create_gradient_button(
            getbitmap("theme/icons/10x10/skip"), "", name="calibration_btn"
        )
        self.calibration_btn.Bind(wx.EVT_BUTTON, self.continue_to_calibration)
        self.calibration_btn.Disable()
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)
        self.add_panel((12, 12), flag=wx.EXPAND)

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
            for id in self.id_to_keycode:
                keycode = self.id_to_keycode[id]
                self.Bind(wx.EVT_MENU, self.key_handler, id=id)
                accels.append((wx.ACCEL_NORMAL, keycode, id))
                if keycode == wx.WXK_TAB:
                    accels.append((wx.ACCEL_SHIFT, keycode, id))
            self.SetAcceleratorTable(wx.AcceleratorTable(accels))
        else:
            self.Bind(wx.EVT_CHAR_HOOK, self.key_handler)

        # Event handlers
        self.Bind(wx.EVT_CLOSE, self.OnClose, self)
        self.Bind(wx.EVT_MOVE, self.OnMove, self)
        self.timer = wx.Timer(self)
        if handler:
            self.Bind(wx.EVT_TIMER, handler, self.timer)
        self.Bind(labelbook.EVT_IMAGENOTEBOOK_PAGE_CHANGING, self.OnPageChanging)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)

        if "gtk3" in wx.PlatformInfo:
            # Fix background color not working for panels under GTK3
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        # Final initialization steps
        self.logger = get_file_logger("adjust")
        self._setup(True)

        self.Show()

        if start_timer:
            self.start_timer()

    if "gtk3" in wx.PlatformInfo:
        OnEraseBackground = wx_Panel.__dict__["OnEraseBackground"]

    def EndModal(self, returncode=wx.ID_OK):
        return returncode

    def MakeModal(self, makemodal=False):
        pass

    def OnClose(self, event):
        # if getattr(self, "measurement_play_sound_ctrl", None):
        # setcfg("measurement.play_sound",
        # int(self.measurement_play_sound_ctrl.GetValue()))
        config.writecfg()
        if not self.timer.IsRunning():
            self.Destroy()
        else:
            self.keepGoing = False

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

    def OnPageChanging(self, event):
        oldsel = event.GetOldSelection()
        newsel = event.GetSelection()
        self.abort()
        event.Skip()

    def Pulse(self, msg=""):
        if msg:
            msg = str(msg)
            if (
                msg
                in (
                    lang.getstr("instrument.initializing"),
                    lang.getstr("instrument.calibrating"),
                    lang.getstr("please_wait"),
                    lang.getstr("aborting"),
                )
                or msg == " " * 4
                or ": error -" in msg.lower()
                or "failed" in msg.lower()
                or msg.startswith(lang.getstr("webserver.waiting"))
                or msg.startswith(lang.getstr("connection.waiting"))
            ) and msg != self.lastmsg:
                self.lastmsg = msg
                self.Freeze()
                for txt in self.lb.GetCurrentPage().txt.values():
                    txt.checkmark.GetContainingSizer().Hide(txt.checkmark)
                    txt.SetLabel(" ")
                txt = list(self.lb.GetCurrentPage().txt.values())[0]
                if txt.GetLabel() != wrap(msg, 46):
                    txt.SetLabel(wrap(msg, 46))
                    txt.SetForegroundColour(FGCOLOUR)
                self.Thaw()
        return self.keepGoing, False

    def Resume(self):
        self.keepGoing = True
        self.set_sound_on_off_btn_bitmap()

    def UpdateProgress(self, value, msg=""):
        return self.Pulse(msg)

    def UpdatePulse(self, msg=""):
        return self.Pulse(msg)

    def _assign_image_list(self):
        imagelist = None
        modes = {CRT: {"black_luminance": "luminance", "luminance": "contrast"}}
        for img in (
            "black_luminance",
            "white_point",
            "luminance",
            "black_point",
            "check_all",
        ):
            img = modes.get(getcfg("measurement_mode") == "c", {}).get(img, img)
            bmp = getbitmap("theme/icons/72x72/%s" % img)
            if not imagelist:
                img_w, img_h = bmp.Size
                imagelist = wx.ImageList(img_w, img_h)
            imagelist.Add(bmp)
        self.lb.AssignImageList(imagelist)

    def _setup(self, init=False):
        self.logger.info("-" * 80)
        self.cold_run = True
        self.is_busy = None
        self.is_measuring = None
        self.keepGoing = True
        self.lastmsg = ""
        self.target_br = None
        self._assign_image_list()
        if getcfg("measurement_mode") == "c":
            self.lb.disabled_pages = []
            if getcfg("calibration.black_luminance", False):
                self.lb.SetSelection(0)
            else:
                self.lb.disabled_pages.append(0)
                self.lb.SetSelection(1)
        else:
            self.lb.disabled_pages = [0, 3]
            self.lb.SetSelection(1)
        if getcfg("trc"):
            self.calibration_btn.SetLabel(lang.getstr("calibration.start"))
        elif getcfg("calibration.continue_next"):
            self.calibration_btn.SetLabel(lang.getstr("calibration.skip"))
        else:
            self.calibration_btn.SetLabel(lang.getstr("finish"))
        self.calibration_btn.GetContainingSizer().Layout()
        # Update black luminance page description
        self.lb.GetPage(0).update_desc()
        # Update white luminance page description
        self.lb.GetPage(2).update_desc()

        # Set size
        scale = getcfg("app.dpi") / get_default_dpi()
        if scale < 1:
            scale = 1
        img_w, img_h = list(map(int, list(map(round, (84 * scale, 72 * scale)))))
        min_h = (
            (img_h + 8) * (self.lb.GetPageCount() - len(self.lb.disabled_pages)) + 2 - 8
        )
        if init:
            self.lb.SetMinSize((418, min_h))
        self.lb.SetMinSize(
            (self.lb.GetMinSize()[0], max(self.lb.GetMinSize()[1], min_h))
        )
        self.lb.GetCurrentPage().Fit()
        self.lb.GetCurrentPage().Layout()
        self.lb.Fit()
        self.lb.Layout()
        self.SetMinSize((0, 0))
        self.Fit()
        self.Layout()
        # The button sizer will be as wide as the labelbook or wider,
        # so use it as reference
        w = self.btnsizer.CalcMin()[0] - img_w - 12
        for pagenum in range(0, self.lb.GetPageCount()):
            page = self.lb.GetPage(pagenum)
            page.SetSize((w, -1))
            page.desc.SetLabel(page.desc.GetLabel().replace("\n", " "))
            if sys.platform == "darwin" and intlist(mac_ver()[0].split(".")) >= [
                10,
                10,
            ]:
                margin = 24
            else:
                margin = 12
            page.desc.Wrap(w - margin)
            bitmaps = {
                "black_level": {CRT: "luminance", not CRT: "black_level"},
                "luminance": {CRT: "contrast", not CRT: "luminance"},
            }
            if page.ctrltype == "check_all":
                for name in bitmaps:
                    bitmap = bitmaps.get(name).get(getcfg("measurement_mode") == "c")
                    page.txt[name].spacer.SetBitmap(
                        getbitmap("theme/icons/16x16/" + bitmap)
                    )
            else:
                ctrltype = {"rgb_offset": "black_level", "rgb_gain": "luminance"}.get(
                    page.ctrltype, page.ctrltype
                )
                bitmap = bitmaps.get(ctrltype).get(getcfg("measurement_mode") == "c")
                page.gauges["L"].label.SetBitmap(
                    getbitmap("theme/icons/16x16/" + bitmap)
                )
            page.Fit()
            page.Layout()
            for txt in page.txt.values():
                txt.SetLabel(" ")
        self.lb.SetMinSize(
            (self.lb.GetMinSize()[0], max(self.lb.GetCurrentPage().GetSize()[1], min_h))
        )
        self.Fit()
        self.Sizer.SetSizeHints(self)
        self.Sizer.Layout()

        # Set position
        x = getcfg("position.progress.x")
        y = getcfg("position.progress.y")
        self.SetSaneGeometry(x, y)

    def abort(self):
        if self.has_worker_subprocess():
            if self.is_measuring:
                self.worker.safe_send(" ")

    def abort_and_send(self, key):
        self.abort()
        if self.has_worker_subprocess():
            if self.worker.safe_send(key):
                self.is_busy = True
                self.adjustment_btn.Disable()
                self.calibration_btn.Disable()

    def add_panel(self, size=wx.DefaultSize, flag=0):
        panel = get_panel(self, size)
        self.sizer.Add(panel, flag=flag)
        return panel

    def continue_to_calibration(self, event=None):
        if getcfg("trc"):
            self.abort_and_send("7")
        else:
            self.abort_and_send("8")

    def create_start_interactive_adjustment_button(
        self, icon="play", enable=False, startstop="start"
    ):
        if getattr(self, "adjustment_btn", None):
            self.adjustment_btn._bitmap = getbitmap("theme/icons/10x10/%s" % icon)
            self.adjustment_btn.SetLabel(
                lang.getstr("calibration.interactive_display_adjustment.%s" % startstop)
            )
            self.adjustment_btn.Enable(enable)
            return
        self.adjustment_btn = self.create_gradient_button(
            getbitmap("theme/icons/10x10/%s" % icon),
            lang.getstr("calibration.interactive_display_adjustment.%s" % startstop),
            name="adjustment_btn",
        )
        self.adjustment_btn.Bind(wx.EVT_BUTTON, self.start_interactive_adjustment)
        self.adjustment_btn.Enable(enable)

    def create_gradient_button(self, bitmap, label, name):
        btn = FlatShadedButton(
            self, bitmap=bitmap, label=label, name=name, fgcolour=FGCOLOUR
        )
        self.btnsizer.Add(btn)
        self.btnsizer.Layout()
        return btn

    def flush(self):
        pass

    def has_worker_subprocess(self):
        return bool(
            getattr(self, "worker", None) and getattr(self.worker, "subprocess", None)
        )

    def isatty(self):
        return True

    def key_handler(self, event):
        # print {wx.EVT_CHAR.typeId: 'EVT_CHAR',
        # wx.EVT_CHAR_HOOK.typeId: 'EVT_CHAR_HOOK',
        # wx.EVT_KEY_DOWN.typeId: 'EVT_KEY_DOWN',
        # wx.EVT_MENU.typeId: 'EVT_MENU'}.get(event.GetEventType(),
        # event.GetEventType())
        keycode = None
        if event.GetEventType() in (
            wx.EVT_CHAR.typeId,
            wx.EVT_CHAR_HOOK.typeId,
            wx.EVT_KEY_DOWN.typeId,
        ):
            keycode = event.GetKeyCode()
        elif event.GetEventType() == wx.EVT_MENU.typeId:
            keycode = self.id_to_keycode.get(event.GetId())
        if keycode == wx.WXK_TAB:
            self.global_navigate() or event.Skip()
        elif keycode >= 0:
            if keycode == ord(" "):
                if (
                    not isinstance(self.FindFocus(), FlatShadedButton)
                    or self.FindFocus() is self.adjustment_btn
                ):
                    if self.is_measuring:
                        self.abort()
                    else:
                        self.start_interactive_adjustment()
                else:
                    event.Skip()
            elif keycode in [ord(str(c)) for c in range(1, 6)]:
                key_num = chr(keycode)
                pagenum = dict(
                    list(
                        zip(
                            list(self.pagenum_2_argyll_key_num.values()),
                            list(self.pagenum_2_argyll_key_num.keys()),
                        )
                    )
                ).get(key_num)
                if pagenum not in self.lb.disabled_pages and not self.is_measuring:
                    self.lb.SetSelection(pagenum)
                    self.start_interactive_adjustment()
            elif keycode in (ord("\x1b"), ord("7"), ord("8"), ord("Q"), ord("q")):
                if not getcfg("trc") and keycode == ord("7"):
                    # Ignore
                    pass
                elif self.keyhandler:
                    self.keyhandler(event)
                elif self.has_worker_subprocess():
                    self.worker.safe_send(chr(keycode))
                else:
                    event.Skip()
            else:
                event.Skip()
        else:
            event.Skip()

    def measurement_play_sound_handler(self, event):
        # self.measurement_play_sound_ctrl.SetValue(not self.measurement_play_sound_ctrl.GetValue())
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

    def parse_txt(self, txt):
        colors = {True: wx.Colour(0x33, 0xCC, 0x0), False: FGCOLOUR}
        if not txt:
            return
        self.logger.info("%r" % txt)
        self.Pulse(txt)

        if "/ Current" in txt:
            indicator = getbitmap("theme/icons/10x10/record")
        else:
            indicator = getbitmap("theme/icons/10x10/record_outline")

        target_br = re.search(
            r"Target white brightness = (\d+(?:\.\d+)?)".replace(" ", r"\s+"), txt, re.I
        )
        if getcfg("measurement_mode") == "c":
            target_bl = re.search(
                r"Target Near Black = (\d+(?:\.\d+)?), Current = (\d+(?:\.\d+)?)".replace(
                    " ", r"\s+"
                ),
                txt,
                re.I,
            )
            if target_bl:
                self.lb.GetCurrentPage().target_bl = [
                    "Target",
                    float(target_bl.groups()[0]),
                ]
        initial_br = re.search(
            r"(Initial|Target)(?: Br)? (\d+(?:\.\d+)?)\s*(?:, x (\d+(?:\.\d+)?)\s*, y (\d+(?:\.\d+)?)(?:\s*, (?:(V[CD]T \d+K?) )?DE(?: 2K)? (\d+(?:\.\d+)?))?|$)".replace(
                " ", r"\s+"
            ),
            txt,
            re.I,
        )
        current_br = None
        current_bl = None
        if target_br and not getattr(self, "target_br", None):
            self.target_br = ["Target", float(target_br.groups()[0])]
        if initial_br:
            self.lb.GetCurrentPage().initial_br = [
                initial_br.groups()[0],
                float(initial_br.groups()[1]),
            ] + list(initial_br.groups()[2:])
        if self.lb.GetCurrentPage().ctrltype != "check_all":
            current_br = re.search(
                r"Current(?: Br)? (\d+(?:\.\d+)?)".replace(" ", r"\s+"), txt, re.I
            )
        else:
            current_br = re.search(
                r"Target Brightness = (?:\d+(?:\.\d+)?), Current = (\d+(?:\.\d+)?)".replace(
                    " ", r"\s+"
                ),
                txt,
                re.I,
            )
            if not current_br:
                current_br = re.search(
                    r"Current Brightness = (\d+(?:\.\d+)?)".replace(" ", r"\s+"),
                    txt,
                    re.I,
                )
            if getcfg("measurement_mode") == "c":
                if target_bl:
                    current_bl = float(target_bl.groups()[1])
            else:
                current_bl = re.search(
                    r"Black = XYZ (?:\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (?:\d+(?:\.\d+)?)".replace(
                        " ", r"\s+"
                    ),
                    txt,
                    re.I,
                )
                if current_bl:
                    current_bl = float(current_bl.groups()[0])
        xy_dE_rgb = re.search(
            r"x (\d+(?:\.\d+)?)[=+-]*, y (\d+(?:\.\d+)?)[=+-]*,? (?:(V[CD]T \d+K?) )?DE(?: 2K)? (\d+(?:\.\d+)?) R([=+-]+) G([=+-]+) B([=+-]+)".replace(
                " ", r"\s+"
            ),
            txt,
            re.I,
        )
        white_xy_dE_re = r"(?:Target white = x (?:\d+(?:\.\d+)?), y (?:\d+(?:\.\d+)?), Current|Current white) = x (\d+(?:\.\d+)?), y (\d+(?:\.\d+)?), (?:(?:(V[CD]T \d+K?) )?DE(?: 2K)?|error =) (\d+(?:\.\d+)?)".replace(
            " ", r"\s+"
        )
        white_xy_dE = re.search(white_xy_dE_re, txt, re.I)
        black_xy_dE = re.search(white_xy_dE_re.replace(r"white", "black"), txt, re.I)
        white_xy_target = re.search(
            r"Target white = x (\d+(?:\.\d+)?), y (\d+(?:\.\d+)?)".replace(" ", r"\s+"),
            txt,
            re.I,
        )
        black_xy_target = re.search(
            r"Target black = x (\d+(?:\.\d+)?), y (\d+(?:\.\d+)?)".replace(" ", r"\s+"),
            txt,
            re.I,
        )
        if current_br or current_bl or xy_dE_rgb or white_xy_dE or black_xy_dE:
            self.Freeze()
        # for t in ("target_br", "target_bl", "initial_br", "current_br", "current_bl"):
        # if locals()[t]:
        # print "\n" + t, locals()[t].groups(),
        if current_br:
            initial_br = getattr(self.lb.GetCurrentPage(), "initial_br", None)
            if self.lb.GetCurrentPage().ctrltype in (
                "rgb_gain",
                "luminance",
                "check_all",
            ):
                target_br = getattr(self, "target_br", None)
            else:
                target_br = None
            if self.lb.GetCurrentPage().ctrltype == "rgb_gain" and initial_br:
                initial_br = ["Initial"] + initial_br[1:]
            compare_br = (
                target_br or initial_br or ("Initial", float(current_br.groups()[0]))
            )
            lstr = (compare_br[0]).lower()
            if compare_br[1]:
                percent = 100.0 / compare_br[1]
            else:
                percent = 100.0
            l_diff = float(current_br.groups()[0]) - compare_br[1]
            l = int(round(50 + l_diff * percent))
            if self.lb.GetCurrentPage().gauges.get("L"):
                self.lb.GetCurrentPage().gauges["L"].SetValue(min(max(l, 1), 100))
                self.lb.GetCurrentPage().gauges["L"].Refresh()
            if self.lb.GetCurrentPage().txt.get("luminance"):
                if initial_br or target_br:  # and round(l_diff, 2):
                    if round(l_diff, 2) > 0:
                        sign = "+"
                    elif round(l_diff, 2) < 0:
                        sign = "-"
                    else:
                        sign = "\u00B1"  # plusminus
                    label = "%s %.2f cd/m\u00b2\n%s %.2f cd/m\u00b2 (%s%.2f%%)" % (
                        lang.getstr(lstr),
                        compare_br[1],
                        lang.getstr("current"),
                        float(current_br.groups()[0]),
                        sign,
                        abs(l_diff) * percent,
                    )
                else:
                    label = lang.getstr("current") + " %.2f cd/m\u00b2" % float(
                        current_br.groups()[0]
                    )
                self.lb.GetCurrentPage().txt[
                    "luminance"
                ].checkmark.GetContainingSizer().Show(
                    self.lb.GetCurrentPage().txt["luminance"].checkmark,
                    lstr == "target" and abs(l_diff) * percent <= 1,
                )
                self.lb.GetCurrentPage().txt["luminance"].SetForegroundColour(
                    colors[lstr == "target" and abs(l_diff) * percent <= 1]
                )
                set_label_and_size(self.lb.GetCurrentPage().txt["luminance"], label)
        if current_bl and self.lb.GetCurrentPage().txt.get("black_level"):
            target_bl = getattr(self.lb.GetCurrentPage(), "target_bl", None) or getattr(
                self.lb.GetCurrentPage(), "initial_br", None
            )
            if target_bl:
                percent = 100.0 / target_bl[1]
            if target_bl:  # and round(target_bl[1], 2) != round(current_bl, 2):
                l_diff = current_bl - target_bl[1]
                if round(l_diff, 2) > 0:
                    sign = "+"
                elif round(l_diff, 2) < 0:
                    sign = "-"
                else:
                    sign = "\u00B1"  # plusminus
                label = "%s %.2f cd/m\u00b2\n%s %.2f cd/m\u00b2 (%s%.2f%%)" % (
                    lang.getstr("target"),
                    target_bl[1],
                    lang.getstr("current"),
                    current_bl,
                    sign,
                    abs(l_diff) * percent,
                )
            else:
                if target_bl:
                    l_diff = 0
                else:
                    l_diff = None
                label = lang.getstr("current") + " %.2f cd/m\u00b2" % current_bl
            self.lb.GetCurrentPage().txt[
                "black_level"
            ].checkmark.GetContainingSizer().Show(
                self.lb.GetCurrentPage().txt["black_level"].checkmark,
                l_diff is not None and abs(l_diff) * percent <= 1,
            )
            self.lb.GetCurrentPage().txt["black_level"].SetForegroundColour(
                colors[l_diff is not None and abs(l_diff) * percent <= 1]
            )
            set_label_and_size(self.lb.GetCurrentPage().txt["black_level"], label)
        # groups()[0] = x
        # groups()[1] = y
        # groups()[2] = VDT/VCT (optional)
        # groups()[3] = dE
        # groups()[4] = R +-
        # groups()[5] = G +-
        # groups()[6] = B +-
        if xy_dE_rgb:
            x, y, vdt, dE = get_xy_vt_dE(xy_dE_rgb.groups())
            r = int(
                round(
                    50
                    - (
                        xy_dE_rgb.groups()[4].count("+")
                        - xy_dE_rgb.groups()[4].count("-")
                    )
                    * dE
                )
            )
            g = int(
                round(
                    50
                    - (
                        xy_dE_rgb.groups()[5].count("+")
                        - xy_dE_rgb.groups()[5].count("-")
                    )
                    * dE
                )
            )
            b = int(
                round(
                    50
                    - (
                        xy_dE_rgb.groups()[6].count("+")
                        - xy_dE_rgb.groups()[6].count("-")
                    )
                    * dE
                )
            )
            if self.lb.GetCurrentPage().gauges.get("R"):
                self.lb.GetCurrentPage().gauges["R"].SetValue(min(max(r, 1), 100))
                self.lb.GetCurrentPage().gauges["R"].Refresh()
            if self.lb.GetCurrentPage().gauges.get("G"):
                self.lb.GetCurrentPage().gauges["G"].SetValue(min(max(g, 1), 100))
                self.lb.GetCurrentPage().gauges["G"].Refresh()
            if self.lb.GetCurrentPage().gauges.get("B"):
                self.lb.GetCurrentPage().gauges["B"].SetValue(min(max(b, 1), 100))
                self.lb.GetCurrentPage().gauges["B"].Refresh()
            if self.lb.GetCurrentPage().txt.get("rgb"):
                self.lb.GetCurrentPage().txt["rgb"].checkmark.GetContainingSizer().Show(
                    self.lb.GetCurrentPage().txt["rgb"].checkmark, abs(dE) <= 1
                )
                self.lb.GetCurrentPage().txt["rgb"].SetForegroundColour(
                    colors[abs(dE) <= 1]
                )
                label = (
                    lang.getstr("current")
                    + " x %.4f y %.4f %s %.1f \u0394E*00" % (x, y, vdt, dE)
                ).replace("  ", " ")
                initial_br = getattr(self.lb.GetCurrentPage(), "initial_br", None)
                if initial_br and len(initial_br) > 3:
                    x, y, vdt, dE = get_xy_vt_dE(initial_br[2:])
                    label = (
                        lang.getstr(initial_br[0].lower())
                        + " x %.4f y %.4f %s %.1f \u0394E*00\n" % (x, y, vdt, dE)
                    ).replace("  ", " ") + label
                set_label_and_size(self.lb.GetCurrentPage().txt["rgb"], label)
        if white_xy_dE:
            x, y, vdt, dE = get_xy_vt_dE(white_xy_dE.groups())
            if self.lb.GetCurrentPage().txt.get("white_point"):
                self.lb.GetCurrentPage().txt[
                    "white_point"
                ].checkmark.GetContainingSizer().Show(
                    self.lb.GetCurrentPage().txt["white_point"].checkmark, abs(dE) <= 1
                )
                self.lb.GetCurrentPage().txt["white_point"].SetForegroundColour(
                    colors[abs(dE) <= 1]
                )
                label = (
                    lang.getstr("current")
                    + " x %.4f y %.4f %s %.1f \u0394E*00" % (x, y, vdt, dE)
                ).replace("  ", " ")
                if white_xy_target:
                    x, y, vdt, dE = get_xy_vt_dE(white_xy_target.groups())
                    label = (
                        lang.getstr("target") + " x %.4f y %.4f\n" % (x, y)
                    ).replace("  ", " ") + label
                set_label_and_size(self.lb.GetCurrentPage().txt["white_point"], label)
        if black_xy_dE:
            x, y, vdt, dE = get_xy_vt_dE(black_xy_dE.groups())
            if self.lb.GetCurrentPage().txt.get("white_point"):
                self.lb.GetCurrentPage().txt[
                    "black_point"
                ].checkmark.GetContainingSizer().Show(
                    self.lb.GetCurrentPage().txt["black_point"].checkmark, abs(dE) <= 1
                )
                self.lb.GetCurrentPage().txt["black_point"].SetForegroundColour(
                    colors[abs(dE) <= 1]
                )
                label = (
                    lang.getstr("current")
                    + " x %.4f y %.4f %s %.1f \u0394E*00" % (x, y, vdt, dE)
                ).replace("  ", " ")
                if black_xy_target:
                    x, y, vdt, dE = get_xy_vt_dE(black_xy_target.groups())
                    label = (
                        lang.getstr("target") + " x %.4f y %.4f\n" % (x, y)
                    ).replace("  ", " ") + label
                set_label_and_size(self.lb.GetCurrentPage().txt["black_point"], label)
        if (
            current_br or current_bl or xy_dE_rgb
        ) and self.lb.GetCurrentPage().ctrltype != "check_all":
            if getcfg("measurement.play_sound"):
                self.measurement_sound.safe_play()
            self.indicator_ctrl.SetBitmap(indicator)
            self.btnsizer.Layout()
        if current_br or current_bl or xy_dE_rgb or white_xy_dE or black_xy_dE:
            self.lb.GetCurrentPage().Layout()
            self.Thaw()
        if "Press 1 .. 7" in txt or "8) Exit" in txt:
            if self.cold_run:
                self.cold_run = False
                self.Pulse(" " * 4)
            if self.is_measuring is not False:
                self.lb.Children[0].Refresh()
                if self.is_measuring is True:
                    self.create_start_interactive_adjustment_button(enable=True)
                else:
                    self.adjustment_btn.Enable()
                self.is_busy = False
                self.is_measuring = False
                self.indicator_ctrl.SetBitmap(geticon(10, "empty", use_mask=True))
            self.calibration_btn.Enable()
            self.lb.SetFocus()  # Make frame receive EVT_CHAR_HOOK events under Linux
        elif "initial measurements" in txt or "check measurements" in txt:
            self.is_busy = True
            self.lb.Children[0].Refresh()
            self.Pulse(lang.getstr("please_wait"))
            if not self.is_measuring:
                self.create_start_interactive_adjustment_button("pause", True, "stop")
            self.is_measuring = True
            self.lb.SetFocus()  # Make frame receive EVT_CHAR_HOOK events under Linux

    # self.SetTitle("is_measuring %s timer.IsRunning %s keepGoing %s" %
    # (str(self.is_measuring), self.timer.IsRunning(), self.keepGoing))

    def reset(self):
        self.Freeze()
        self._setup()
        # Reset controls
        for pagenum in range(0, self.lb.GetPageCount()):
            page = self.lb.GetPage(pagenum)
            page.initial_br = None
            page.target_bl = None
            for name in ("R", "G", "B", "L"):
                if page.gauges.get(name):
                    page.gauges[name].SetValue(0)
                    page.gauges[name].Refresh()
            for txt in page.txt.values():
                txt.checkmark.GetContainingSizer().Hide(txt.checkmark)
                txt.SetForegroundColour(FGCOLOUR)
        self.create_start_interactive_adjustment_button()
        self.calibration_btn.Disable()
        self.Thaw()

    def start_interactive_adjustment(self, event=None):
        if self.is_measuring:
            self.abort()
        else:
            self.abort_and_send(self.pagenum_2_argyll_key_num[self.lb.GetSelection()])

    def start_timer(self, ms=50):
        self.timer.Start(ms)

    def stop_timer(self):
        self.timer.Stop()

    def write(self, txt):
        wx.CallAfter(self.parse_txt, txt)


if __name__ == "__main__":
    from _thread import start_new_thread
    from time import sleep

    class Subprocess(object):
        def send(self, bytes_):
            start_new_thread(test, (bytes_,))

    class Worker(object):
        def __init__(self):
            self.subprocess = Subprocess()

        def safe_send(self, bytes_):
            self.subprocess.send(bytes_)
            return True

    config.initcfg()
    lang.init()
    app = BaseApp(0)

    if "--crt" in sys.argv[1:]:
        setcfg("measurement_mode", "c")
    else:
        setcfg("measurement_mode", "l")

    app.TopWindow = DisplayAdjustmentFrame(start_timer=False)
    app.TopWindow.worker = Worker()
    app.TopWindow.Show()
    i = 0

    def test(bytes_=None):
        global i
        # 0 = dispcal -v -yl
        # 1 = dispcal -v -yl -b130
        # 2 = dispcal -v -yl -B0.5
        # 3 = dispcal -v -yl -t5200
        # 4 = dispcal -v -yl -t5200 -b130 -B0.5
        menu = r"""
Press 1 .. 7
1) Black level (CRT: Offset/Brightness)
2) White point (Color temperature, R,G,B, Gain/Contrast)
3) White level (CRT: Gain/Contrast, LCD: Brightness/Backlight)
4) Black point (R,G,B, Offset/Brightness)
5) Check all
6) Measure and set ambient for viewing condition adjustment
7) Continue on to calibration
8) Exit
"""
        if bytes_ == " ":
            txt = "\n" + menu
        elif bytes_ == "1":
            # Black level
            txt = [
                r"""Doing some initial measurements
Black = XYZ   0.19   0.20   0.28
Grey  = XYZ  27.20  27.79  24.57
White = XYZ 126.48 128.71 112.75

Adjust CRT brightness to get target level. Press space when done.
   Target 1.29
/ Current 2.02  -""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.20   0.29
                   Grey  = XYZ  27.11  27.76  24.72
                   White = XYZ 125.91 128.38 113.18

                   Adjust CRT brightness to get target level. Press space when done.
                      Target 1.28
                   / Current 2.02  -""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.21   0.28
                   Grey  = XYZ  27.08  27.72  24.87
                   White = XYZ 125.47 127.86 113.60

                   Adjust CRT brightness to get target level. Press space when done.
                      Target 1.28
                   / Current 2.02  -""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.20   0.29
                   Grey  = XYZ  27.11  27.77  25.01
                   White = XYZ 125.21 127.80 113.90

                   Adjust CRT brightness to get target level. Press space when done.
                      Target 1.28
                   / Current 2.03  -""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.20   0.30
                   Grey  = XYZ  23.56  24.14  21.83
                   White = XYZ 124.87 130.00 112.27

                   Adjust CRT brightness to get target level. Press space when done.
                      Target 1.28
                   / Current 1.28""",
            ][i]
        elif bytes_ == "2":
            # White point
            txt = [
                r"""Doing some initial measurements
Red   = XYZ  81.08  39.18   2.41
Green = XYZ  27.63  80.13  10.97
Blue  = XYZ  18.24   9.90  99.75
White = XYZ 126.53 128.96 112.57

Adjust R,G & B gain to desired white point. Press space when done.
  Initial Br 128.96, x 0.3438 , y 0.3504 , VDT 5152K DE 2K  4.7
/ Current Br 128.85, x 0.3439-, y 0.3502+  VDT 5151K DE 2K  4.8  R-  G++ B-""",
                r"""Doing some initial measurements
                   Red   = XYZ  80.48  38.87   2.43
                   Green = XYZ  27.58  79.99  10.96
                   Blue  = XYZ  18.34   9.93 100.24
                   White = XYZ 125.94 128.32 113.11

                   Adjust R,G & B gain to desired white point. Press space when done.
                     Initial Br 130.00, x 0.3428 , y 0.3493 , VDT 5193K DE 2K  4.9
                   / Current Br 128.39, x 0.3428-, y 0.3496+  VDT 5190K DE 2K  4.7  R-  G++ B-""",
                r"""Doing some initial measurements
                   Red   = XYZ  80.01  38.57   2.44
                   Green = XYZ  27.51  79.85  10.95
                   Blue  = XYZ  18.45   9.94 100.77
                   White = XYZ 125.48 127.88 113.70

                   Adjust R,G & B gain to desired white point. Press space when done.
                     Initial Br 127.88, x 0.3419 , y 0.3484 , VDT 5232K DE 2K  5.0
                   / Current Br 127.87, x 0.3419-, y 0.3485+  VDT 5231K DE 2K  4.9  R-  G++ B-""",
                r"""Doing some initial measurements
                   Red   = XYZ  79.69  38.48   2.44
                   Green = XYZ  27.47  79.76  10.95
                   Blue  = XYZ  18.50   9.95 101.06
                   White = XYZ 125.08 127.71 113.91

                   Adjust R,G & B gain to get target x,y. Press space when done.
                      Target Br 127.71, x 0.3401 , y 0.3540
                   / Current Br 127.70, x 0.3412-, y 0.3481+  DE  4.8  R-  G++ B-""",
                r"""Doing some initial measurements
                   Red   = XYZ  79.47  38.41   2.44
                   Green = XYZ  27.41  79.72  10.94
                   Blue  = XYZ  18.52   9.96 101.20
                   White = XYZ 124.87 130.00 112.27

                   Adjust R,G & B gain to get target x,y. Press space when done.
                      Target Br 130.00, x 0.3401 , y 0.3540
                   / Current Br 130.00, x 0.3401=, y 0.3540=  DE  0.0  R=  G= B=""",
            ][i]
        elif bytes_ == "3":
            # White level
            txt = [
                r"""Doing some initial measurements
White = XYZ 126.56 128.83 112.65

Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
  Initial 128.83
/ Current 128.85""",
                r"""Doing some initial measurements
                   White = XYZ 125.87 128.23 113.43

                   Adjust CRT Contrast or LCD Brightness to get target level. Press space when done.
                      Target 130.00
                   / Current 128.24  +""",
                r"""Doing some initial measurements
                   White = XYZ 125.33 127.94 113.70

                   Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
                     Initial 127.94
                   / Current 127.88""",
                r"""Doing some initial measurements
                   White = XYZ 125.00 127.72 114.03

                   Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
                     Initial 127.72
                   / Current 127.69""",
                r"""Doing some initial measurements
                   White = XYZ 124.87 130.00 112.27

                   Adjust CRT Contrast or LCD Brightness to get target level. Press space when done.
                      Target 130.00
                   / Current 130.00""",
            ][i]
        elif bytes_ == "4":
            # Black point
            txt = [
                r"""Doing some initial measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  27.25  27.83  24.52
White = XYZ 126.60 128.86 112.54

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.29, x 0.3440 , y 0.3502
/ Current Br 2.03, x 0.3409+, y 0.3484+  DE  1.7  R++ G+  B-""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.21   0.29
                   Grey  = XYZ  27.19  27.87  24.94
                   White = XYZ 125.83 128.16 113.57

                   Adjust R,G & B offsets to get target x,y. Press space when done.
                      Target Br 1.28, x 0.3423 , y 0.3487
                   / Current Br 2.03, x 0.3391+, y 0.3470+  DE  1.7  R++ G+  B-""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.21   0.29
                   Grey  = XYZ  27.14  27.79  24.97
                   White = XYZ 125.49 127.89 113.90

                   Adjust R,G & B offsets to get target x,y. Press space when done.
                      Target Br 1.28, x 0.3417 , y 0.3482
                   / Current Br 2.02, x 0.3386+, y 0.3466+  DE  1.7  R++ G+  B-""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.21   0.30
                   Grey  = XYZ  27.10  27.79  25.12
                   White = XYZ 125.12 127.68 114.09

                   Adjust R,G & B offsets to get target x,y. Press space when done.
                      Target Br 1.28, x 0.3401 , y 0.3540
                   / Current Br 2.04, x 0.3373+, y 0.3465+  DE  4.4  R+  G++ B-""",
                r"""Doing some initial measurements
                   Black = XYZ   0.19   0.21   0.29
                   Grey  = XYZ  23.56  24.14  21.83
                   White = XYZ 124.87 130.00 112.27

                   Adjust R,G & B offsets to get target x,y. Press space when done.
                      Target Br 1.28, x 0.3401 , y 0.3540
                   / Current Br 1.28, x 0.3401=, y 0.3540=  DE  0.0  R=  G= B=""",
            ][i]
        elif bytes_ == "5":
            # Check all
            txt = [
                r"""Doing check measurements
Black = XYZ   0.19   0.20   0.29
Grey  = XYZ  27.22  27.80  24.49
White = XYZ 126.71 128.91 112.34
1%    = XYZ   1.94   1.98   1.76

  Current Brightness = 128.91
  Target 50% Level  = 24.42, Current = 27.80, error =  2.6%
  Target Near Black =  1.29, Current =  2.02, error =  0.6%
  Current white = x 0.3443, y 0.3503, VDT 5137K DE 2K  5.0
  Target black = x 0.3443, y 0.3503, Current = x 0.3411, y 0.3486, error =  1.73 DE

Press 1 .. 7""",
                r"""Doing check measurements
                   Black = XYZ   0.19   0.21   0.29
                   Grey  = XYZ  27.10  27.75  24.85
                   White = XYZ 125.78 128.17 113.53
                   1%    = XYZ   1.93   1.98   1.79

                     Target Brightness = 130.00, Current = 128.17, error = -1.4%
                     Target 50% Level  = 24.28, Current = 27.75, error =  2.7%
                     Target Near Black =  1.28, Current =  2.02, error =  0.6%
                     Current white = x 0.3423, y 0.3488, VDT 5215K DE 2K  4.9
                     Target black = x 0.3423, y 0.3488, Current = x 0.3391, y 0.3467, error =  1.69 DE

                   Press 1 .. 7""",
                r"""Doing check measurements
                   Black = XYZ   0.19   0.21   0.29
                   Grey  = XYZ  27.09  27.74  24.95
                   White = XYZ 125.32 127.78 113.82
                   1%    = XYZ   1.93   1.98   1.80

                     Current Brightness = 127.78
                     Target 50% Level  = 24.21, Current = 27.74, error =  2.8%
                     Target Near Black =  1.28, Current =  2.02, error =  0.6%
                     Current white = x 0.3415, y 0.3483, VDT 5243K DE 2K  4.9
                     Target black = x 0.3415, y 0.3483, Current = x 0.3386, y 0.3465, error =  1.55 DE

                   Press 1 .. 7""",
                r"""Doing check measurements
                   Black = XYZ   0.19   0.20   0.29
                   Grey  = XYZ  26.98  27.68  24.97
                   White = XYZ 125.00 127.56 113.99
                   1%    = XYZ   1.92   1.97   1.80

                     Current Brightness = 127.56
                     Target 50% Level  = 24.17, Current = 27.68, error =  2.8%
                     Target Near Black =  1.28, Current =  2.02, error =  0.6%
                     Target white = x 0.3401, y 0.3540, Current = x 0.3410, y 0.3480, error =  4.83 DE
                     Target black = x 0.3401, y 0.3540, Current = x 0.3372, y 0.3464, error =  4.48 DE

                   Press 1 .. 7""",
                r"""Doing check measurements
                   Black = XYZ   0.19   0.21   0.29
                   Grey  = XYZ  23.56  24.14  21.83
                   White = XYZ 124.87 130.00 112.27
                   1%    = XYZ   1.92   1.97   1.80

                     Target Brightness = 130.00, Current = 130.00, error = 0.0%
                     Target 50% Level  = 24.14, Current = 24.14, error =  0.0%
                     Target Near Black =  1.27, Current =  1.27, error =  0.0%
                     Target white = x 0.3401, y 0.3540, Current = x 0.3401, y 0.3540, error =  0.00 DE
                     Target black = x 0.3401, y 0.3540, Current = x 0.3401, y 0.3540, error =  0.00 DE

                   Press 1 .. 7""",
            ][i]
        elif bytes_ == "7" or not bytes_:
            if bytes_ == "7":
                if i < 4:
                    i += 1
                else:
                    i -= 4
                wx.CallAfter(app.TopWindow.reset)
            txt = (
                [
                    r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is LCD
Target white = native white point
Target white brightness = native brightness
Target black brightness = native brightness
Target advertised gamma = 2.400000""",
                    r"""Setting up the instrument
                   Place instrument on test window.
                   Hit Esc or Q to give up, any other key to continue:
                   Display type is LCD
                   Target white = native white point
                   Target white brightness = 130.000000 cd/m^2
                   Target black brightness = native brightness
                   Target advertised gamma = 2.400000""",
                    r"""Setting up the instrument
                   Place instrument on test window.
                   Hit Esc or Q to give up, any other key to continue:
                   Display type is LCD
                   Target white = native white point
                   Target white brightness = native brightness
                   Target black brightness = 0.500000 cd/m^2
                   Target advertised gamma = 2.400000""",
                    r"""Setting up the instrument
                   Place instrument on test window.
                   Hit Esc or Q to give up, any other key to continue:
                   Display type is LCD
                   Target white = 5200.000000 degrees kelvin Daylight spectrum
                   Target white brightness = native brightness
                   Target black brightness = native brightness
                   Target advertised gamma = 2.400000""",
                    r"""Setting up the instrument
                   Place instrument on test window.
                   Hit Esc or Q to give up, any other key to continue:
                   Display type is CRT
                   Target white = 5200.000000 degrees kelvin Daylight spectrum
                   Target white brightness = 130.000000 cd/m^2
                   Target black brightness = 0.500000 cd/m^2
                   Target advertised gamma = 2.400000""",
                ][i]
                + r"""

Display adjustment menu:"""
                + menu
            )
        elif bytes_ == "8":
            wx.CallAfter(app.TopWindow.Close)
            return
        else:
            return
        for line in txt.split("\n"):
            sleep(0.0625)
            wx.CallAfter(app.TopWindow.write, line)
            print(line)

    start_new_thread(test, tuple())
    app.MainLoop()
