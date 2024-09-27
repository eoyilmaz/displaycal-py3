# --------------------------------------------------------------------------- #
# LABELBOOK And FLATIMAGEBOOK Widgets wxPython IMPLEMENTATION                           # noqa: SC100
#
# Original C++ Code From Eran, embedded in the FlatMenu source code                     # noqa: SC100
#
#
# License: wxWidgets license                                                            # noqa: SC100
#
#
# Python Code By:
#
# Andrea Gavana, @ 03 Nov 2006                                                          # noqa: SC100
# Latest Revision: 17 Jan 2011, 15.00 GMT
#
#
# For All Kind Of Problems, Requests Of Enhancements And Bug Reports,
# Please Write To Me At:
#
# andrea.gavana@gmail.com                                                               # noqa: SC100
# gavana@kpo.kz                                                                         # noqa: SC100
#
# Or, Obviously, To The wxPython Mailing List!!!                                        # noqa: SC100
#
# TODO:
# LabelBook - Support IMB_SHOW_ONLY_IMAGES                                              # noqa: SC100
# LabelBook - An option for the draw border to only draw the border between the
#             controls and the pages so the background colour can flow into the
#             window background
#
#
#
# End Of Comments
# --------------------------------------------------------------------------- #

"""
LabelBook and FlatImageBook are a quasi-full generic and owner-drawn implementations of `wx.Notebook`.

Description
===========

LabelBook and FlatImageBook are a quasi-full implementations of the `wx.Notebook`,
and designed to be a drop-in replacement for `wx.Notebook`.
The API functions are similar so one can expect the function to behave in the same way.
LabelBook anf FlatImageBook share their appearance with `wx.Toolbook` and `wx.Listbook`,
while having more options for custom drawings, label positioning,
mouse pointing and so on.
Moreover, they retain also some visual characteristics of the Outlook address book.

Some features:

- They are generic controls;
- Supports for left, right, top (FlatImageBook only),
  bottom (FlatImageBook only) book styles;
- Possibility to draw images only, text only or both (FlatImageBook only);
- Support for a "pin-button", that allows the user to shrink/expand the book tab area;
- Shadows behind tabs (LabelBook only);
- Gradient shading of the tab area (LabelBook only);
- Web-like mouse pointing on tabs style (LabelBook only);
- Many customizable colours
  (tab area, active tab text, tab borders, active tab, highlight) - LabelBook only.

And much more. See the demo for a quasi-complete review of all the
functionalities of LabelBook and FlatImageBook.


Supported Platforms
===================

LabelBook and FlatImageBook have been tested on the following platforms:
  * Windows (Windows XP);
  * Linux Ubuntu (Dapper 6.06)


Window Styles
=============

This class supports the following window styles:

=========================== =========== ========================================
Window Styles               Hex Value   Description
=========================== =========== ========================================
``INB_BOTTOM``                      0x1 Place labels below the page area.
                                        Available only for `FlatImageBook`.
``INB_LEFT``                        0x2 Place labels on the left side.
                                        Available only for `FlatImageBook`.
``INB_RIGHT``                       0x4 Place labels on the right side.
``INB_TOP``                         0x8 Place labels above the page area.
``INB_BORDER``                     0x10 Draws a border around `LabelBook` or
                                        `FlatImageBook`.
``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no images.
                                        Available only for `LabelBook`.
``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no label texts.
                                        Available only for `LabelBook`.
``INB_FIT_BUTTON``                 0x80 Displays a pin button to show/hide the
                                        book control.
``INB_DRAW_SHADOW``               0x100 Draw shadows below the book tabs.
                                        Available only for `LabelBook`.
``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to show/hide the
                                        book control.
``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the tabs background.
                                        Available only for `LabelBook`.
``INB_WEB_HILITE``                0x800 On mouse hovering,
                                        tabs behave like html hyperlinks.
                                        Available only for `LabelBook`.
``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab area.
``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the longest text
                                        (or text+image if you have images) in
                                        all the tabs.
=========================== =========== ========================================


Events Processing
=================

This class processes the following events:

=================================== ============================================
Event Name                          Description
=================================== ============================================
``EVT_IMAGENOTEBOOK_PAGE_CHANGED``  Notify client objects when the active page
                                    in `ImageNotebook` has changed.
``EVT_IMAGENOTEBOOK_PAGE_CHANGING`` Notify client objects when the active page
                                    in `ImageNotebook` is about to change.
``EVT_IMAGENOTEBOOK_PAGE_CLOSED``   Notify client objects when a page in
                                    `ImageNotebook` has been closed.
``EVT_IMAGENOTEBOOK_PAGE_CLOSING``  Notify client objects when a page in
                                    `ImageNotebook` is closing.
=================================== ============================================


License And Version
===================

LabelBook and FlatImageBook are distributed under the wxPython license.

Latest Revision: Andrea Gavana @ 17 Jan 2011, 15.00 GMT

Version 0.5.

"""

__docformat__ = "epytext"


# ----------------------------------------------------------------------
# Beginning Of IMAGENOTEBOOK wxPython Code                                              # noqa: SC100
# ----------------------------------------------------------------------

import wx

from DisplayCAL.lib.agw.artmanager import ArtManager, DCSaver
from DisplayCAL.lib.agw.fmresources import (
    BottomShadow,
    BottomShadowFull,
    IMG_NONE,
    IMG_OVER_EW_BORDER,
    IMG_OVER_IMG,
    IMG_OVER_PIN,
    INB_ACTIVE_TAB_COLOUR,
    INB_ACTIVE_TEXT_COLOUR,
    INB_HILITE_TAB_COLOUR,
    INB_PIN_HOVER,
    INB_PIN_NONE,
    INB_PIN_PRESSED,
    INB_TAB_AREA_BACKGROUND_COLOUR,
    INB_TABS_BORDER_COLOUR,
    INB_TEXT_COLOUR,
    pin_down_xpm,
    pin_left_xpm,
    RightShadow,
)

# FlatImageBook and LabelBook styles
INB_BOTTOM = 1
"""
Place labels below the page area.

Available only for `FlatImageBook`.
"""
INB_LEFT = 2
"""
Place labels on the left side.

Available only for `FlatImageBook`.
"""
INB_RIGHT = 4
"""Place labels on the right side."""
INB_TOP = 8
"""Place labels above the page area."""
INB_BORDER = 16
"""Draws a border around `LabelBook` or `FlatImageBook`."""
INB_SHOW_ONLY_TEXT = 32
"""
Shows only text labels and no images.

Available only for `LabelBook`.
"""
INB_SHOW_ONLY_IMAGES = 64
"""
Shows only tab images and no label texts.

Available only for `LabelBook`.
"""
INB_FIT_BUTTON = 128
"""Displays a pin button to show/hide the book control."""
INB_DRAW_SHADOW = 256
"""
Draw shadows below the book tabs.

Available only for `LabelBook`.
"""
INB_USE_PIN_BUTTON = 512
"""Displays a pin button to show/hide the book control."""
INB_GRADIENT_BACKGROUND = 1024
"""
Draws a gradient shading on the tabs background.

Available only for `LabelBook`.
"""
INB_WEB_HILITE = 2048
"""
On mouse hovering, tabs behave like html hyperlinks.

Available only for `LabelBook`.
"""
INB_NO_RESIZE = 4096
"""Don't allow resizing of the tab area."""
INB_FIT_LABELTEXT = 8192
"""Fits tab area to longest text/image in all tabs."""

wxEVT_IMAGENOTEBOOK_PAGE_CHANGED = wx.wxEVT_COMMAND_NOTEBOOK_PAGE_CHANGED
wxEVT_IMAGENOTEBOOK_PAGE_CHANGING = wx.wxEVT_COMMAND_NOTEBOOK_PAGE_CHANGING
wxEVT_IMAGENOTEBOOK_PAGE_CLOSING = wx.NewEventType()
wxEVT_IMAGENOTEBOOK_PAGE_CLOSED = wx.NewEventType()

# -----------------------------------#
#        ImageNotebookEvent
# -----------------------------------#

EVT_IMAGENOTEBOOK_PAGE_CHANGED = wx.EVT_NOTEBOOK_PAGE_CHANGED
"""Notify client objects when the active page in `ImageNotebook` has changed."""
EVT_IMAGENOTEBOOK_PAGE_CHANGING = wx.EVT_NOTEBOOK_PAGE_CHANGING
"""Notify client objects when the active page in `ImageNotebook` is about to change."""
EVT_IMAGENOTEBOOK_PAGE_CLOSING = wx.PyEventBinder(wxEVT_IMAGENOTEBOOK_PAGE_CLOSING, 1)
"""Notify client objects when a page in `ImageNotebook` is closing."""
EVT_IMAGENOTEBOOK_PAGE_CLOSED = wx.PyEventBinder(wxEVT_IMAGENOTEBOOK_PAGE_CLOSED, 1)
"""Notify client objects when a page in `ImageNotebook` has been closed."""


# ---------------------------------------------------------------------------- #
# Class ImageNotebookEvent
# ---------------------------------------------------------------------------- #


class ImageNotebookEvent(wx.PyCommandEvent):
    """Event sent on page change, changing, closing, or closed."""

    def __init__(self, event_type, event_id=1, sel=-1, oldsel=-1):
        """
        Default class constructor.

        Args:
            event_type: the event type;
            event_id: the event identifier;
            sel: the current selection;
            oldsel: the old selection.
        """
        wx.PyCommandEvent.__init__(self, event_type, event_id)
        self._eventType = event_type
        self._sel = sel
        self._oldsel = oldsel
        self._allowed = True

    def set_selection(self, s):
        """
        Sets the event selection.

        Args:
            s: an integer specifying the new selection.
        """
        self._sel = s

    def set_old_selection(self, s):
        """
        Sets the event old selection.

        Args:
            s: an integer specifying the old selection.
        """
        self._oldsel = s

    def GetSelection(self):
        """Returns the event selection."""
        return self._sel

    def get_old_selection(self):
        """Returns the old event selection."""
        return self._oldsel

    def veto(self):
        """
        Prevents the change announced by this event from happening.

        Note:
            It is in general a good idea to notify the user about the reasons
            for vetoing the change because otherwise the applications behaviour
            (which just refuses to do what the user wants) might be quite surprising.
        """
        self._allowed = False

    def allow(self):
        """
        This is the opposite of L{veto}: it explicitly allows the event to be processed.

        For most events it is not necessary to call this method as the events
        are allowed anyhow but some are forbidden by default
        (this will be mentioned in the corresponding event description).
        """
        self._allowed = True

    def is_allowed(self):
        """Returns ``True`` if change allowed, ``False`` if vetoed."""
        return self._allowed


# ---------------------------------------------------------------------------- #
# Class ImageInfo
# ---------------------------------------------------------------------------- #


class ImageInfo(object):
    """Holds info (caption, image, etc.) for a single tab in L{LabelBook}."""

    def __init__(self, str_caption="", image_index=-1):
        """
        Default class constructor.

        Args:
            str_caption: the tab caption;
            image_index: the tab image index based on the assigned (set)
                `wx.ImageList` (if any).
        """
        self._pos = wx.Point()
        self._size = wx.Size()
        self._strCaption = str_caption
        self._ImageIndex = image_index
        self._captionRect = wx.Rect()

    def set_caption(self, value):
        """
        Sets the tab caption.

        Args:
            value: the new tab caption.
        """
        self._strCaption = value

    def get_caption(self):
        """Returns the tab caption."""
        return self._strCaption

    def set_position(self, value):
        """
        Sets the tab position.

        Args:
            value: the new tab position, an instance of `wx.Point`.
        """
        self._pos = value

    def get_position(self):
        """Returns the tab position."""
        return self._pos

    def set_size(self, value):
        """
        Sets the tab size.

        Args:
            value:  the new tab size, an instance of `wx.Size`.
        """
        self._size = value

    def get_size(self):
        """Returns the tab size."""
        return self._size

    def set_image_index(self, value):
        """
        Sets the tab image index.

        Args:
            value: an index into the image list.
        """
        self._ImageIndex = value

    def get_image_index(self):
        """Returns the tab image index."""
        return self._ImageIndex

    def set_text_rect(self, rect):
        """
        Sets the client rectangle available for the tab text.

        Args:
            rect: the tab text client rectangle, an instance of `wx.Rect`.
        """
        self._captionRect = rect

    def get_text_rect(self):
        """Returns the client rectangle available for the tab text."""
        return self._captionRect


# ---------------------------------------------------------------------------- #
# Class ImageContainerBase
# ---------------------------------------------------------------------------- #


def fix_text_size(dc, text, max_width):
    """
    Fixes the text, to fit `maxWidth` value.

    If the text length exceeds `maxWidth` value this function truncates it
    and appends two dots at the end.
    ("Long Long Long Text" might become "Long Long...").

    Args:
        dc: an instance of `wx.DC`;
        text: the text to fix/truncate;
        max_width: the maximum allowed width for the text, in pixels.
    """
    return ArtManager.Get().TruncateText(dc, text, max_width)


class ImageContainerBase(wx.Panel):
    """Base class for L{FlatImageBook} image container."""

    def __init__(
        self,
        parent,
        window_id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agw_style=0,
        name="ImageContainerBase",
    ):
        """
        Default class constructor.

        Args:
            parent: parent window. Must not be ``None``;
            window_id: window identifier. A value of -1 indicates a default value;
            pos: the control position. A value of (-1, -1) indicates a default position,
                chosen by either the windowing system or wxPython,
                depending on platform;
            size: the control size. A value of (-1, -1) indicates a default size,
                chosen by either the windowing system or wxPython,
                depending on platform;
            style: the underlying `wx.Panel` window style;
            agw_style: the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
            name: the window name.
        """
        self._nIndex = -1
        self._nImgSize = 16
        self._ImageList = None
        self._nHoveredImgIdx = -1
        self._bCollapsed = False
        self._tabAreaSize = (-1, -1)
        self._nPinButtonStatus = INB_PIN_NONE
        self._pagesInfoVec = []
        self._pinBtnRect = wx.Rect()

        wx.Panel.__init__(
            self,
            parent,
            window_id,
            pos,
            size,
            style | wx.NO_BORDER | wx.NO_FULL_REPAINT_ON_RESIZE,
            name,
        )

    def has_agw_flag(self, flag):
        """
        Tests for existence of flag in the style.

        Args:
            flag: a window style. This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
        """
        style = self.GetParent().get_agw_window_style_flag()
        res = (style & flag and [True] or [False])[0]
        return res

    def clear_flag(self, flag):
        """
        Removes flag from the style.

        Args:
            flag: a window style flag.

        See:
            L{has_agw_flag} for a list of possible window style flags.
        """
        parent = self.GetParent()
        agw_style = parent.get_agw_window_style_flag()
        agw_style &= ~flag
        parent.set_agw_window_style_flag(agw_style)

    def assign_image_list(self, imglist):
        """
        Assigns an image list to the L{ImageContainerBase}.

        Args:
            imglist: an instance of `wx.ImageList`.
        """
        if imglist and imglist.GetImageCount() != 0:
            self._nImgSize = imglist.GetBitmap(0).GetHeight()

        self._ImageList = imglist
        parent = self.GetParent()
        agw_style = parent.get_agw_window_style_flag()
        parent.set_agw_window_style_flag(agw_style)

    def get_image_list(self):
        """Return the image list for L{ImageContainerBase}."""
        return self._ImageList

    def get_image_size(self):
        """Returns the image size inside the L{ImageContainerBase} image list."""
        return self._nImgSize

    def can_do_bottom_style(self):
        """
        Allows the parent to examine the children type.

        Some implementation (such as L{LabelBook}),
        does not support top/bottom images, only left/right.
        """
        return False

    def add_page(self, caption, selected=False, img_idx=-1):
        """
        Adds a page to the container.

        Args:
            caption: specifies the text for the new tab;
            selected: specifies whether the page should be selected;
            img_idx: specifies the optional image index for the new tab.
        """
        self._pagesInfoVec.append(ImageInfo(caption, img_idx))
        if selected or len(self._pagesInfoVec) == 1:
            self._nIndex = len(self._pagesInfoVec) - 1

        self.Refresh()

    def insert_page(self, page_idx, caption, selected=False, img_idx=-1):
        """
        Inserts a page into the container at the specified position.

        Args:
            page_idx: specifies the position for the new tab;
            caption: specifies the text for the new tab;
            selected: specifies whether the page should be selected;
            img_idx: specifies the optional image index for the new tab.
        """
        self._pagesInfoVec.insert(page_idx, ImageInfo(caption, img_idx))
        if selected or len(self._pagesInfoVec) == 1:
            self._nIndex = len(self._pagesInfoVec) - 1

        self.Refresh()

    def set_page_image(self, page, img_idx):
        """
        Sets the image for the given page.

        Args:
            page: the index of the tab;
            img_idx: specifies the optional image index for the tab.
        """
        img_info = self._pagesInfoVec[page]
        img_info.SetImageIndex(img_idx)

    def set_page_text(self, page, text):
        """
        Sets the tab caption for the given page.

        Args:
            page: the index of the tab;
            text: the new tab caption.
        """
        img_info = self._pagesInfoVec[page]
        img_info.SetCaption(text)

    def get_page_image(self, page):
        """
        Returns the image index for the given page.

        Args:
            page: the index of the tab.
        """
        img_info = self._pagesInfoVec[page]
        return img_info.GetImageIndex()

    def get_page_text(self, page):
        """
        Returns the tab caption for the given page.

        Args:
            page: the index of the tab.
        """
        img_info = self._pagesInfoVec[page]
        return img_info.GetCaption()

    def clear_all(self):
        """Deletes all the pages in the container."""
        self._pagesInfoVec = []
        self._nIndex = wx.NOT_FOUND

    def do_delete_page(self, page):
        """
        Does the actual page deletion.

        Args:
            page: the index of the tab.
        """
        # Remove the page from the vector
        book = self.GetParent()
        self._pagesInfoVec.pop(page)

        if self._nIndex >= page:
            self._nIndex = self._nIndex - 1

        # The delete page was the last first on the array,
        # but the book still has more pages,
        # so we set the active page to be the first one (0)
        if self._nIndex < 0 < len(self._pagesInfoVec):
            self._nIndex = 0

        # Refresh the tabs
        if self._nIndex >= 0:

            book._bForceSelection = True
            book.set_selection(self._nIndex)
            book._bForceSelection = False

        if not self._pagesInfoVec:
            # Erase the page container drawings
            dc = wx.ClientDC(self)
            dc.Clear()

    def on_size(self, event):
        """
        Handles the ``wx.EVT_SIZE`` event for L{ImageContainerBase}.

        Args:
            event: a `wx.SizeEvent` event to be processed.
        """
        self.Refresh()  # Call on paint
        event.Skip()

    def on_erase_background(self, event):
        """
        Handles the ``wx.EVT_ERASE_BACKGROUND`` event for L{ImageContainerBase}.

        Args:
            event: a `wx.EraseEvent` event to be processed.

        Note:
            This method is intentionally empty to reduce flicker.
        """
        pass

    def HitTest(self, pt):
        """
        Returns tab index at position or ``wx.NOT_FOUND``, plus L{HitTest} flag.

        Args:
            pt: an instance of `wx.Point`, to test for hits.

        Returns:
            The index of the tab at the specified position plus the hit test flag,
                which can be one of the following bits:
                ====================== ======= ================================
                HitTest Flags           Value  Description
                ====================== ======= ================================
                ``IMG_OVER_IMG``             0 The mouse is over the tab icon
                ``IMG_OVER_PIN``             1 The mouse is over the pin button
                ``IMG_OVER_EW_BORDER``       2 The mouse is over the east-west
                                                book border
                ``IMG_NONE``                 3 Nowhere
                ====================== ======= ================================
        """
        style = self.GetParent().get_agw_window_style_flag()

        if style & INB_USE_PIN_BUTTON:
            if self._pinBtnRect.Contains(pt):
                return -1, IMG_OVER_PIN

        for index in range(len(self._pagesInfoVec)):

            if self._pagesInfoVec[index].get_position() == wx.Point(-1, -1):
                break

            # For Web Hover style, we test the TextRect                                 # noqa: SC100
            if not self.has_agw_flag(INB_WEB_HILITE):
                button_rect = wx.Rect(
                    self._pagesInfoVec[index].get_position(),
                    self._pagesInfoVec[index].get_size(),
                )
            else:
                button_rect = self._pagesInfoVec[index].get_text_rect()

            if button_rect.Contains(pt):
                return index, IMG_OVER_IMG

        if self.point_on_sash(pt):
            return -1, IMG_OVER_EW_BORDER
        else:
            return -1, IMG_NONE

    def point_on_sash(self, pt):
        """
        Tests whether pt is located on the sash.

        Args:
            pt: an instance of `wx.Point`, to test for hits.
        """
        # Check if we are on a sash border
        clt_rect = self.GetClientRect()

        if self.has_agw_flag(INB_LEFT) or self.has_agw_flag(INB_TOP):
            if pt.x > clt_rect.x + clt_rect.width - 4:
                return True

        else:
            if pt.x < 4:
                return True

        return False

    def on_mouse_left_down(self, event):
        """
        Handles the ``wx.EVT_LEFT_DOWN`` event for L{ImageContainerBase}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        event.Skip()

        # Support for collapse/expand
        style = self.GetParent().get_agw_window_style_flag()
        if style & INB_USE_PIN_BUTTON:

            if self._pinBtnRect.Contains(event.get_position()):

                self._nPinButtonStatus = INB_PIN_PRESSED
                dc = wx.ClientDC(self)
                self.draw_pin(dc, self._pinBtnRect, not self._bCollapsed)
                return

        # In case panel is collapsed, there is nothing to check
        if self._bCollapsed:
            return

        tab_idx, where = self.HitTest(event.get_position())

        if where == IMG_OVER_IMG:
            self._nHoveredImgIdx = -1

        if tab_idx == -1:
            return

        self.GetParent().set_selection(tab_idx)

    def on_mouse_leave_window(self, event):
        """
        Handles the ``wx.EVT_LEAVE_WINDOW`` event for L{ImageContainerBase}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        b_repaint = self._nHoveredImgIdx != -1
        self._nHoveredImgIdx = -1

        # Make sure the pin button status is NONE in case we were in pin button style
        style = self.GetParent().get_agw_window_style_flag()

        if style & INB_USE_PIN_BUTTON:

            self._nPinButtonStatus = INB_PIN_NONE
            dc = wx.ClientDC(self)
            self.draw_pin(dc, self._pinBtnRect, not self._bCollapsed)

        # Restore cursor
        wx.SetCursor(wx.StockCursor(wx.CURSOR_ARROW))

        if b_repaint:
            self.Refresh()

    def on_mouse_left_up(self, event):
        """
        Handles the ``wx.EVT_LEFT_UP`` event for L{ImageContainerBase}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        style = self.GetParent().get_agw_window_style_flag()

        if style & INB_USE_PIN_BUTTON:

            b_is_label_container = not self.can_do_bottom_style()

            if self._pinBtnRect.Contains(event.get_position()):

                self._nPinButtonStatus = INB_PIN_NONE
                self._bCollapsed = not self._bCollapsed

                if self._bCollapsed:

                    # Save the current tab area width
                    self._tabAreaSize = wx.Size(self.GetSize())

                    if b_is_label_container:

                        self.SetSizeHints(20, self._tabAreaSize.y)

                    else:

                        if style & INB_BOTTOM or style & INB_TOP:
                            self.SetSizeHints(self._tabAreaSize.x, 20)
                        else:
                            self.SetSizeHints(20, self._tabAreaSize.y)

                else:

                    if b_is_label_container:

                        self.SetSizeHints(self._tabAreaSize.x, -1)

                    else:

                        # Restore the tab area size
                        if style & INB_BOTTOM or style & INB_TOP:
                            self.SetSizeHints(-1, self._tabAreaSize.y)
                        else:
                            self.SetSizeHints(self._tabAreaSize.x, -1)

                self.GetParent().GetSizer().Layout()
                self.Refresh()
                return

    def on_mouse_move(self, event):
        """
        Handles the ``wx.EVT_MOTION`` event for L{ImageContainerBase}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        style = self.GetParent().get_agw_window_style_flag()
        if style & INB_USE_PIN_BUTTON:

            # Check to see if we are in the pin button rect                             # noqa: SC100
            if (
                not self._pinBtnRect.Contains(event.get_position())
                and self._nPinButtonStatus == INB_PIN_PRESSED
            ):

                self._nPinButtonStatus = INB_PIN_NONE
                dc = wx.ClientDC(self)
                self.draw_pin(dc, self._pinBtnRect, not self._bCollapsed)

        img_idx, where = self.HitTest(event.get_position())
        self._nHoveredImgIdx = img_idx

        if not self._bCollapsed:

            if 0 <= self._nHoveredImgIdx < len(self._pagesInfoVec):

                # Change the cursor to be Hand
                if (
                    self.has_agw_flag(INB_WEB_HILITE)
                    and self._nHoveredImgIdx != self._nIndex
                ):
                    wx.SetCursor(wx.StockCursor(wx.CURSOR_HAND))

            else:

                # Restore the cursor only if we have the Web hover style set,
                # and we are not currently hovering the sash
                if self.has_agw_flag(INB_WEB_HILITE) and not self.point_on_sash(
                    event.get_position()
                ):
                    wx.SetCursor(wx.StockCursor(wx.CURSOR_ARROW))

        # Don't display hover effect when hovering the selected label

        if self._nHoveredImgIdx == self._nIndex:
            self._nHoveredImgIdx = -1

        self.Refresh()

    def draw_pin(self, dc, rect, down_pin):
        """
        Draw a pin button, that allows collapsing of the image panel.

        Args:
            dc: an instance of `wx.DC`;
            rect: the pin button client rectangle;
            down_pin: ``True`` if the pin button is facing downwards,
                ``False`` if it is facing leftwards.
        """
        # Set the bitmap according to the button status

        if down_pin:
            pin_bmp = wx.BitmapFromXPMData(pin_down_xpm)
        else:
            pin_bmp = wx.BitmapFromXPMData(pin_left_xpm)

        xx = rect.x + 2

        if self._nPinButtonStatus in [INB_PIN_HOVER, INB_PIN_NONE]:

            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetPen(wx.BLACK_PEN)
            dc.DrawRectangle(xx, rect.y, 16, 16)

            # Draw upper and left border with grey colour
            dc.SetPen(wx.WHITE_PEN)
            dc.DrawLine(xx, rect.y, xx + 16, rect.y)
            dc.DrawLine(xx, rect.y, xx, rect.y + 16)

        elif self._nPinButtonStatus == INB_PIN_PRESSED:

            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.SetPen(wx.Pen(wx.NamedColour("LIGHT GREY")))
            dc.DrawRectangle(xx, rect.y, 16, 16)

            # Draw upper and left border with grey colour
            dc.SetPen(wx.BLACK_PEN)
            dc.DrawLine(xx, rect.y, xx + 16, rect.y)
            dc.DrawLine(xx, rect.y, xx, rect.y + 16)

        # Set the masking
        pin_bmp.SetMask(wx.Mask(pin_bmp, wx.WHITE))

        # Draw the new bitmap
        dc.DrawBitmap(pin_bmp, xx, rect.y, True)

        # Save the pin rect                                                             # noqa: SC100
        self._pinBtnRect = rect


# ---------------------------------------------------------------------------- #
# Class ImageContainer
# ---------------------------------------------------------------------------- #


class ImageContainer(ImageContainerBase):
    """Base class for L{FlatImageBook} image container."""

    def __init__(
        self,
        parent,
        window_id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agw_style=0,
        name="ImageContainer",
    ):
        """
        Default class constructor.

        Args:
            parent: parent window. Must not be ``None``;
            window_id: window identifier. A value of -1 indicates a default value;
            pos: the control position. A value of (-1, -1) indicates a default position,
                chosen by either the windowing system or wxPython,
                depending on platform;
            size: the control size. A value of (-1, -1) indicates a default size,
                chosen by either the windowing system or wxPython,
                depending on platform;
            style: the underlying `wx.Panel` window style;
            agw_style: the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
            name: the window name.
        """
        ImageContainerBase.__init__(
            self, parent, window_id, pos, size, style, agw_style, name
        )

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_mouse_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_mouse_left_up)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_mouse_leave_window)

    def on_size(self, event):
        """
        Handles the ``wx.EVT_SIZE`` event for L{ImageContainer}.

        Args:
            event: a `wx.SizeEvent` event to be processed.
        """
        ImageContainerBase.on_size(self, event)
        event.Skip()

    def on_mouse_left_down(self, event):
        """
        Handles the ``wx.EVT_LEFT_DOWN`` event for L{ImageContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        ImageContainerBase.on_mouse_left_down(self, event)
        event.Skip()

    def on_mouse_left_up(self, event):
        """
        Handles the ``wx.EVT_LEFT_UP`` event for L{ImageContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        ImageContainerBase.on_mouse_left_up(self, event)
        event.Skip()

    def on_erase_background(self, event):
        """
        Handles the ``wx.EVT_ERASE_BACKGROUND`` event for L{ImageContainer}.

        Args:
            event: a `wx.EraseEvent` event to be processed.
        """
        ImageContainerBase.on_erase_background(self, event)

    def on_mouse_move(self, event):
        """
        Handles the ``wx.EVT_MOTION`` event for L{ImageContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        ImageContainerBase.on_mouse_move(self, event)
        event.Skip()

    def on_mouse_leave_window(self, event):
        """
        Handles the ``wx.EVT_LEAVE_WINDOW`` event for L{ImageContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        ImageContainerBase.on_mouse_leave_window(self, event)
        event.Skip()

    def can_do_bottom_style(self):
        """
        Allows the parent to examine the children type.

        Some implementation (such as L{LabelBook}),
        does not support top/bottom images, only left/right.
        """
        return True

    def on_paint(self, event):
        """
        Handles the ``wx.EVT_PAINT`` event for L{ImageContainer}.

        Args:
            event: a `wx.PaintEvent` event to be processed.
        """
        dc = wx.BufferedPaintDC(self)
        style = self.GetParent().get_agw_window_style_flag()

        back_brush = wx.WHITE_BRUSH
        if style & INB_BORDER:
            border_pen = wx.Pen(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DSHADOW))
        else:
            border_pen = wx.TRANSPARENT_PEN

        size = self.GetSize()

        # Background
        dc.SetBrush(back_brush)

        border_pen.SetWidth(1)
        dc.SetPen(border_pen)
        dc.DrawRectangle(0, 0, size.x, size.y)
        b_use_pin = (style & INB_USE_PIN_BUTTON and [True] or [False])[0]

        if b_use_pin:

            # Draw the pin button
            client_rect = self.GetClientRect()
            pin_rect = wx.Rect(
                client_rect.GetX() + client_rect.GetWidth() - 20, 2, 20, 20
            )
            self.draw_pin(dc, pin_rect, not self._bCollapsed)

            if self._bCollapsed:
                return

        border_pen = wx.BLACK_PEN
        border_pen.SetWidth(1)
        dc.SetPen(border_pen)
        dc.DrawLine(0, size.y, size.x, size.y)
        dc.DrawPoint(0, size.y)

        client_size = 0
        b_use_ycoord = style & INB_RIGHT or style & INB_LEFT

        if b_use_ycoord:
            client_size = size.GetHeight()
        else:
            client_size = size.GetWidth()

        # We reserve 20 pixels for the 'pin' button

        # The drawing of the images start position.
        # This is dependent of the style, especially when Pin button style is requested

        if b_use_pin:
            if style & INB_TOP or style & INB_BOTTOM:
                pos = (style & INB_BORDER and [0] or [1])[0]
            else:
                pos = (style & INB_BORDER and [20] or [21])[0]
        else:
            pos = (style & INB_BORDER and [0] or [1])[0]

        n_padding = 4  # Pad text with 2 pixels on the left and right
        n_text_padding_left = 2

        count = 0

        for i in range(len(self._pagesInfoVec)):

            count = count + 1

            # in case the 'fit button' style is applied,
            # we set the rectangle width to the text width plus padding
            # In case the style IS applied, but the style is either LEFT or RIGHT
            # we ignore it
            normal_font = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
            dc.SetFont(normal_font)

            text_width, text_height = dc.GetTextExtent(
                self._pagesInfoVec[i].get_caption()
            )

            # Restore font to be normal
            normal_font.SetWeight(wx.FONTWEIGHT_NORMAL)
            dc.SetFont(normal_font)

            # Default values for the surrounding rectangle around a button
            rect_width = (
                self._nImgSize * 2
            )  # To avoid the rectangle to 'touch' the borders
            rect_height = self._nImgSize * 2

            # In case the style requires non-fixed button (fit to text)
            # recalc the rectangle width                                                # noqa: SC100
            if (
                style & INB_FIT_BUTTON
                and not ((style & INB_LEFT) or (style & INB_RIGHT))
                and not self._pagesInfoVec[i].get_caption() == ""
                and not (style & INB_SHOW_ONLY_IMAGES)
            ):

                rect_width = (
                    (text_width + n_padding * 2) > rect_width
                    and [n_padding * 2 + text_width]
                    or [rect_width]
                )[0]

                # Make the width an even number
                if rect_width % 2 != 0:
                    rect_width += 1

            # Check that we have enough space to draw the button
            # If Pin button is used,
            # consider its space as well (applicable for top/bottom style)
            # since in the left/right, its size is already considered in 'pos'          # noqa: SC100
            pin_btn_size = (b_use_pin and [20] or [0])[0]

            if pos + rect_width + pin_btn_size > client_size:
                break

            # Calculate the button rectangle
            mod_rect_width = (
                (style & INB_LEFT or style & INB_RIGHT)
                and [rect_width - 2]
                or [rect_width]
            )[0]
            mod_rect_height = (
                (style & INB_LEFT or style & INB_RIGHT)
                and [rect_height]
                or [rect_height - 2]
            )[0]

            if b_use_ycoord:
                button_rect = wx.Rect(1, pos, mod_rect_width, mod_rect_height)
            else:
                button_rect = wx.Rect(pos, 1, mod_rect_width, mod_rect_height)

            # Check if we need to draw a rectangle around the button
            if self._nIndex == i:

                # Set the colours
                pen_colour = wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION)
                brush_colour = ArtManager.Get().LightColour(
                    wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION), 75
                )

                dc.SetPen(wx.Pen(pen_colour))
                dc.SetBrush(wx.Brush(brush_colour))

                # Fix the surrounding of the rect if border is set                      # noqa: SC100
                if style & INB_BORDER:

                    if style & INB_TOP or style & INB_BOTTOM:
                        button_rect = wx.Rect(
                            button_rect.x + 1,
                            button_rect.y,
                            button_rect.width - 1,
                            button_rect.height,
                        )
                    else:
                        button_rect = wx.Rect(
                            button_rect.x,
                            button_rect.y + 1,
                            button_rect.width,
                            button_rect.height - 1,
                        )

                dc.DrawRectangle(button_rect)

            if self._nHoveredImgIdx == i:

                # Set the colours
                pen_colour = wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION)
                brush_colour = ArtManager.Get().LightColour(
                    wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION), 90
                )

                dc.SetPen(wx.Pen(pen_colour))
                dc.SetBrush(wx.Brush(brush_colour))

                # Fix the surrounding of the rect if border is set                      # noqa: SC100
                if style & INB_BORDER:

                    if style & INB_TOP or style & INB_BOTTOM:
                        button_rect = wx.Rect(
                            button_rect.x + 1,
                            button_rect.y,
                            button_rect.width - 1,
                            button_rect.height,
                        )
                    else:
                        button_rect = wx.Rect(
                            button_rect.x,
                            button_rect.y + 1,
                            button_rect.width,
                            button_rect.height - 1,
                        )

                dc.DrawRectangle(button_rect)

            if b_use_ycoord:
                rect = wx.Rect(0, pos, rect_width, rect_width)
            else:
                rect = wx.Rect(pos, 0, rect_width, rect_width)

            # In case user set both flags:
            # INB_SHOW_ONLY_TEXT and INB_SHOW_ONLY_IMAGES                               # noqa: SC100
            # We override them to display both

            if style & INB_SHOW_ONLY_TEXT and style & INB_SHOW_ONLY_IMAGES:

                style ^= INB_SHOW_ONLY_TEXT
                style ^= INB_SHOW_ONLY_IMAGES
                self.GetParent().set_agw_window_style_flag(style)

            # Draw the caption and text
            img_top_padding = 10
            if (
                not style & INB_SHOW_ONLY_TEXT
                and self._pagesInfoVec[i].get_image_index() != -1
            ):

                if b_use_ycoord:

                    img_xcoord = self._nImgSize / 2
                    img_ycoord = (
                        style & INB_SHOW_ONLY_IMAGES
                        and [pos + self._nImgSize / 2]
                        or [pos + img_top_padding]
                    )[0]

                else:

                    img_xcoord = pos + (rect_width / 2) - (self._nImgSize / 2)
                    img_ycoord = (
                        style & INB_SHOW_ONLY_IMAGES
                        and [self._nImgSize / 2]
                        or [img_top_padding]
                    )[0]

                self._ImageList.Draw(
                    self._pagesInfoVec[i].get_image_index(),
                    dc,
                    img_xcoord,
                    img_ycoord,
                    wx.IMAGELIST_DRAW_TRANSPARENT,
                    True,
                )

            # Draw the text
            if (
                not style & INB_SHOW_ONLY_IMAGES
                and not self._pagesInfoVec[i].get_caption() == ""
            ):

                dc.SetFont(normal_font)

                # Check if the text can fit the size of the rectangle,
                # if not truncate it
                fixed_text = self._pagesInfoVec[i].get_caption()
                if not style & INB_FIT_BUTTON or (
                    style & INB_LEFT or (style & INB_RIGHT)
                ):

                    fixed_text = fix_text_size(
                        dc, self._pagesInfoVec[i].get_caption(), self._nImgSize * 2 - 4
                    )

                    # Update the length of the text
                    text_width, text_height = dc.GetTextExtent(fixed_text)

                if b_use_ycoord:

                    text_offset_x = (rect_width - text_width) / 2
                    text_offset_y = (
                        not style & INB_SHOW_ONLY_TEXT
                        and [pos + self._nImgSize + img_top_padding + 3]
                        or [pos + ((self._nImgSize * 2 - text_height) / 2)]
                    )[0]

                else:

                    text_offset_x = (
                        (rect_width - text_width) / 2 + pos + n_text_padding_left
                    )
                    text_offset_y = (
                        not style & INB_SHOW_ONLY_TEXT
                        and [self._nImgSize + img_top_padding + 3]
                        or [((self._nImgSize * 2 - text_height) / 2)]
                    )[0]

                dc.SetTextForeground(
                    wx.SystemSettings_GetColour(wx.SYS_COLOUR_WINDOWTEXT)
                )
                dc.DrawText(fixed_text, text_offset_x, text_offset_y)

            # Update the page info
            self._pagesInfoVec[i].set_position(button_rect.GetPosition())
            self._pagesInfoVec[i].set_size(button_rect.GetSize())

            pos += rect_width

        # Update all buttons that can not fit into the screen as non-visible
        for ii in range(count, len(self._pagesInfoVec)):
            self._pagesInfoVec[ii].set_position(wx.Point(-1, -1))

        # Draw the pin button
        if b_use_pin:

            client_rect = self.GetClientRect()
            pin_rect = wx.Rect(
                client_rect.GetX() + client_rect.GetWidth() - 20, 2, 20, 20
            )
            self.draw_pin(dc, pin_rect, not self._bCollapsed)


# ---------------------------------------------------------------------------- #
# Class LabelContainer
# ---------------------------------------------------------------------------- #


class LabelContainer(ImageContainerBase):
    """Base class for L{LabelBook}."""

    def __init__(
        self,
        parent,
        window_id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agw_style=0,
        name="LabelContainer",
    ):
        """
        Default class constructor.

        Args:
            parent: parent window. Must not be ``None``;
            window_id: window identifier. A value of -1 indicates a default value;
            pos: the control position. A value of (-1, -1) indicates a default position,
                chosen by either the windowing system or wxPython,
                depending on platform;
            size: the control size. A value of (-1, -1) indicates a default size,
                chosen by either the windowing system or wxPython,
                depending on platform;
            style: the underlying `wx.Panel` window style;
            agw_style: the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
            name: the window name.
        """
        ImageContainerBase.__init__(
            self, parent, window_id, pos, size, style, agw_style, name
        )
        self._nTabAreaWidth = 100
        self._oldCursor = wx.NullCursor
        self._coloursMap = {}
        self._skin = wx.NullBitmap
        self._sashRect = wx.Rect()

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_mouse_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_mouse_left_up)
        self.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_mouse_leave_window)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)

    def on_size(self, event):
        """
        Handles the ``wx.EVT_SIZE`` event for L{LabelContainer}.

        Args:
            event: a `wx.SizeEvent` event to be processed.
        """
        ImageContainerBase.on_size(self, event)
        event.Skip()

    def on_erase_background(self, event):
        """
        Handles the ``wx.EVT_ERASE_BACKGROUND`` event for L{LabelContainer}.

        Args:
            event: a `wx.EraseEvent` event to be processed.
        """
        ImageContainerBase.on_erase_background(self, event)

    def get_tab_area_width(self):
        """Returns the width of the tab area."""
        return self._nTabAreaWidth

    def set_tab_area_width(self, width):
        """
        Sets the width of the tab area.

        Args:
            width: the width of the tab area, in pixels.
        """
        self._nTabAreaWidth = width

    def can_do_bottom_style(self):
        """
        Allows the parent to examine the children type.

        Some implementation (such as L{LabelBook}),
        does not support top/bottom images, only left/right.
        """
        return False

    def set_background_bitmap(self, bmp):
        """
        Sets the background bitmap for the control.

        Args:
            bmp: a valid `wx.Bitmap` object.
        """
        self._skin = bmp

    def on_paint(self, event):
        """
        Handles the ``wx.EVT_PAINT`` event for L{LabelContainer}.

        Args:
            event: a `wx.PaintEvent` event to be processed.
        """
        global i
        style = self.GetParent().get_agw_window_style_flag()

        dc = wx.BufferedPaintDC(self)
        back_brush = wx.Brush(self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR])
        if self.has_agw_flag(INB_BORDER):
            border_pen = wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR])
        else:
            border_pen = wx.TRANSPARENT_PEN

        size = self.GetSize()

        # Set the pen & brush
        dc.SetBrush(back_brush)
        dc.SetPen(border_pen)

        # In case user set both flags, we override them to display both
        # INB_SHOW_ONLY_TEXT and INB_SHOW_ONLY_IMAGES                                   # noqa: SC100
        if style & INB_SHOW_ONLY_TEXT and style & INB_SHOW_ONLY_IMAGES:

            style ^= INB_SHOW_ONLY_TEXT
            style ^= INB_SHOW_ONLY_IMAGES
            self.GetParent().set_agw_window_style_flag(style)

        if self.has_agw_flag(INB_GRADIENT_BACKGROUND) and not self._skin.Ok():

            # Draw gradient in the background area
            start_colour = self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR]
            end_colour = ArtManager.Get().LightColour(
                self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR], 50
            )
            ArtManager.Get().PaintStraightGradientBox(
                dc, wx.Rect(0, 0, size.x / 2, size.y), start_colour, end_colour, False
            )
            ArtManager.Get().PaintStraightGradientBox(
                dc,
                wx.Rect(size.x / 2, 0, size.x / 2, size.y),
                end_colour,
                start_colour,
                False,
            )

        else:

            # Draw the border and background
            if self._skin.Ok():

                dc.SetBrush(wx.TRANSPARENT_BRUSH)
                self.draw_background_bitmap(dc)

            dc.DrawRectangle(wx.Rect(0, 0, size.x, size.y))

        # Draw border
        if self.has_agw_flag(INB_BORDER) and self.has_agw_flag(INB_GRADIENT_BACKGROUND):

            # Just draw the border with transparent brush
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(wx.Rect(0, 0, size.x, size.y))

        b_use_pin = (self.has_agw_flag(INB_USE_PIN_BUTTON) and [True] or [False])[0]

        if b_use_pin:

            # Draw the pin button
            client_rect = self.GetClientRect()
            pin_rect = wx.Rect(
                client_rect.GetX() + client_rect.GetWidth() - 20, 2, 20, 20
            )
            self.draw_pin(dc, pin_rect, not self._bCollapsed)

            if self._bCollapsed:
                return

        dc.SetPen(wx.BLACK_PEN)
        self.SetSizeHints(self._nTabAreaWidth, -1)

        # We reserve 20 pixels for the pin button
        posy = 20
        count = 0

        for i in range(len(self._pagesInfoVec)):
            count = count + 1
            # Default values for the surrounding rectangle around a button
            rect_width = self._nTabAreaWidth

            if self.has_agw_flag(INB_SHOW_ONLY_TEXT):
                font = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
                font.SetPointSize(
                    font.GetPointSize() * self.GetParent().get_font_size_multiple()
                )
                if self.GetParent().get_font_bold():
                    font.SetWeight(wx.FONTWEIGHT_BOLD)
                dc.SetFont(font)
                w, h = dc.GetTextExtent(self._pagesInfoVec[i].get_caption())
                rect_height = h * 2
            else:
                rect_height = self._nImgSize * 2

            # Check that we have enough space to draw the button
            if posy + rect_height > size.GetHeight():
                break

            # Calculate the button rectangle
            posx = 0

            button_rect = wx.Rect(posx, posy, rect_width, rect_height)
            indx = self._pagesInfoVec[i].get_image_index()

            if indx == -1:
                bmp = wx.NullBitmap
            else:
                bmp = self._ImageList.GetBitmap(indx)

            self.draw_label(
                dc,
                button_rect,
                self._pagesInfoVec[i].get_caption(),
                bmp,
                self._pagesInfoVec[i],
                self.has_agw_flag(INB_LEFT) or self.has_agw_flag(INB_TOP),
                i,
                self._nIndex == i,
                self._nHoveredImgIdx == i,
            )

            posy += rect_height

        # Update all buttons that can not fit into the screen as non-visible
        for ii in range(count, len(self._pagesInfoVec)):
            self._pagesInfoVec[i].set_position(wx.Point(-1, -1))

        if b_use_pin:

            client_rect = self.GetClientRect()
            pin_rect = wx.Rect(
                client_rect.GetX() + client_rect.GetWidth() - 20, 2, 20, 20
            )
            self.draw_pin(dc, pin_rect, not self._bCollapsed)

    def draw_background_bitmap(self, dc):
        """
        Draws a bitmap as the background of the control.

        Args:
            dc: an instance of `wx.DC`.
        """
        client_rect = self.GetClientRect()
        width = client_rect.GetWidth()
        height = client_rect.GetHeight()
        covered_y = covered_x = 0
        xstep = self._skin.GetWidth()
        ystep = self._skin.GetHeight()
        bmp_rect = wx.Rect(0, 0, xstep, ystep)
        if bmp_rect != client_rect:

            mem_dc = wx.MemoryDC()
            bmp = wx.EmptyBitmap(width, height)
            mem_dc.SelectObject(bmp)

            while covered_y < height:

                while covered_x < width:

                    mem_dc.DrawBitmap(self._skin, covered_x, covered_y, True)
                    covered_x += xstep

                covered_x = 0
                covered_y += ystep

            mem_dc.SelectObject(wx.NullBitmap)
            # self._skin = bmp
            dc.DrawBitmap(bmp, 0, 0)

        else:

            dc.DrawBitmap(self._skin, 0, 0)

    def on_mouse_left_up(self, event):
        """
        Handles the ``wx.EVT_LEFT_UP`` event for L{LabelContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        if self.has_agw_flag(INB_NO_RESIZE):

            ImageContainerBase.on_mouse_left_up(self, event)
            return

        if self.HasCapture():
            self.ReleaseMouse()

        # Sash was being dragged?
        if not self._sashRect.IsEmpty():

            # Remove sash
            ArtManager.Get().DrawDragSash(self._sashRect)
            self.resize(event)

            self._sashRect = wx.Rect()
            return

        self._sashRect = wx.Rect()

        # Restore cursor
        if self._oldCursor.Ok():

            wx.SetCursor(self._oldCursor)
            self._oldCursor = wx.NullCursor

        ImageContainerBase.on_mouse_left_up(self, event)

    def resize(self, event):
        """
        Actually resizes the tab area.

        Args:
            event: an instance of `wx.SizeEvent`.
        """
        # resize our size
        self._tabAreaSize = self.GetSize()
        new_width = self._tabAreaSize.x
        x = event.GetX()

        if self.has_agw_flag(INB_BOTTOM) or self.has_agw_flag(INB_RIGHT):

            new_width -= event.GetX()

        else:

            new_width = x

        if new_width < 100:  # Don't allow width to be lower than that
            new_width = 100

        self.SetSizeHints(new_width, self._tabAreaSize.y)

        # Update the tab new area width
        self._nTabAreaWidth = new_width
        self.GetParent().Freeze()
        self.GetParent().GetSizer().Layout()
        self.GetParent().Thaw()

    def on_mouse_move(self, event):
        """
        Handles the ``wx.EVT_MOTION`` event for L{LabelContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        if self.has_agw_flag(INB_NO_RESIZE):

            ImageContainerBase.on_mouse_move(self, event)
            return

        # Remove old sash
        if not self._sashRect.IsEmpty():
            ArtManager.Get().DrawDragSash(self._sashRect)

        if event.LeftIsDown():

            if not self._sashRect.IsEmpty():

                # Progress sash, and redraw it
                client_rect = self.GetClientRect()
                pt = self.ClientToScreen(wx.Point(event.GetX(), 0))
                self._sashRect = wx.RectPS(pt, wx.Size(4, client_rect.height))
                ArtManager.Get().DrawDragSash(self._sashRect)

            else:

                # Sash is not being dragged
                if self._oldCursor.Ok():
                    wx.SetCursor(self._oldCursor)
                    self._oldCursor = wx.NullCursor

        else:

            if self.HasCapture():
                self.ReleaseMouse()

            if self.point_on_sash(event.get_position()):

                # Change cursor to EW cursor                                            # noqa: SC100
                self._oldCursor = self.GetCursor()
                wx.SetCursor(wx.StockCursor(wx.CURSOR_SIZEWE))

            elif self._oldCursor.Ok():

                wx.SetCursor(self._oldCursor)
                self._oldCursor = wx.NullCursor

            self._sashRect = wx.Rect()
            ImageContainerBase.on_mouse_move(self, event)

    def on_mouse_left_down(self, event):
        """
        Handles the ``wx.EVT_LEFT_DOWN`` event for L{LabelContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        if self.has_agw_flag(INB_NO_RESIZE):

            ImageContainerBase.on_mouse_left_down(self, event)
            return

        img_idx, where = self.HitTest(event.get_position())

        if IMG_OVER_EW_BORDER == where and not self._bCollapsed:

            # We are over the sash
            if not self._sashRect.IsEmpty():
                ArtManager.Get().DrawDragSash(self._sashRect)
            else:
                # first time, begin drawing sash
                self.CaptureMouse()

                # Change mouse cursor
                self._oldCursor = self.GetCursor()
                wx.SetCursor(wx.StockCursor(wx.CURSOR_SIZEWE))

            client_rect = self.GetClientRect()
            pt = self.ClientToScreen(wx.Point(event.GetX(), 0))
            self._sashRect = wx.RectPS(pt, wx.Size(4, client_rect.height))

            ArtManager.Get().DrawDragSash(self._sashRect)

        else:
            ImageContainerBase.on_mouse_left_down(self, event)

    def on_mouse_leave_window(self, event):
        """
        Handles the ``wx.EVT_LEAVE_WINDOW`` event for L{LabelContainer}.

        Args:
            event: a `wx.MouseEvent` event to be processed.
        """
        if self.has_agw_flag(INB_NO_RESIZE):

            ImageContainerBase.on_mouse_leave_window(self, event)
            return

        # If Sash is being dragged, ignore this event
        if not self.HasCapture():
            ImageContainerBase.on_mouse_leave_window(self, event)

    def draw_regular_hover(self, dc, rect):
        """
        Draws a rounded rectangle around the current tab.

        Args:
            dc: an instance of `wx.DC`;
            rect: the current tab client rectangle.
        """
        # The hovered tab with default border
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen(wx.WHITE))

        # We draw CCW                                                                   # noqa: SC100
        if self.has_agw_flag(INB_RIGHT) or self.has_agw_flag(INB_TOP):

            # Right images
            # Upper line
            dc.DrawLine(rect.x + 1, rect.y, rect.x + rect.width, rect.y)

            # Right line (white)
            dc.DrawLine(
                rect.x + rect.width, rect.y, rect.x + rect.width, rect.y + rect.height
            )

            # Bottom diagonal - we change pen
            dc.SetPen(wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR]))

            # Bottom line
            dc.DrawLine(
                rect.x + rect.width, rect.y + rect.height, rect.x, rect.y + rect.height
            )

        else:

            # Left images
            # Upper line white
            dc.DrawLine(rect.x, rect.y, rect.x + rect.width - 1, rect.y)

            # Left line
            dc.DrawLine(rect.x, rect.y, rect.x, rect.y + rect.height)

            # Bottom diagonal, we change the pen
            dc.SetPen(wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR]))

            # Bottom line
            dc.DrawLine(
                rect.x, rect.y + rect.height, rect.x + rect.width, rect.y + rect.height
            )

    def draw_web_hover(self, dc, caption, x_coord, y_coord):
        """
        Draws a web style hover effect (cursor set to hand & text is underlined).

        Args:
            dc: an instance of `wx.DC`;
            caption: the tab caption text;
            x_coord: the x position of the tab caption;
            y_coord: the y position of the tab caption.
        """
        # Redraw the text with underlined font
        under_lined_font = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
        under_lined_font.SetPointSize(
            under_lined_font.GetPointSize() * self.GetParent().get_font_size_multiple()
        )
        if self.GetParent().get_font_bold():
            under_lined_font.SetWeight(wx.FONTWEIGHT_BOLD)
        under_lined_font.SetUnderlined(True)
        dc.SetFont(under_lined_font)
        dc.DrawText(caption, x_coord, y_coord)

    def set_colour(self, which, colour):
        """
        Sets a colour for a parameter.

        Args:
            which: can be one of the following parameters:
                ================================== ======= =====================
                Colour Key                          Value  Description
                ================================== ======= =====================
                ``INB_TAB_AREA_BACKGROUND_COLOUR``     100 The tab area
                                                            background colour
                ``INB_ACTIVE_TAB_COLOUR``              101 The active tab
                                                            background colour
                ``INB_TABS_BORDER_COLOUR``             102 The tabs border colour
                ``INB_TEXT_COLOUR``                    103 The tab caption text colour
                ``INB_ACTIVE_TEXT_COLOUR``             104 The active tab
                                                            caption text colour
                ``INB_HILITE_TAB_COLOUR``              105 The tab caption
                                                            highlight text colour
                ================================== ======= =====================
            colour: a valid `wx.Colour` object.
        """
        self._coloursMap[which] = colour

    def get_colour(self, which):
        """
        Returns a colour for a parameter.

        Args:
            which: the colour key.

        See:
            L{set_colour} for a list of valid colour keys.
        """
        if which not in self._coloursMap:
            return wx.Colour()

        return self._coloursMap[which]

    def initialize_colours(self):
        """Initializes the colours map to be used for this control."""
        # Initialize map colours
        self._coloursMap.update(
            {
                INB_TAB_AREA_BACKGROUND_COLOUR: ArtManager.Get().LightColour(
                    ArtManager.Get().FrameColour(), 50
                )
            }
        )
        self._coloursMap.update(
            {INB_ACTIVE_TAB_COLOUR: ArtManager.Get().GetMenuFaceColour()}
        )
        self._coloursMap.update(
            {
                INB_TABS_BORDER_COLOUR: wx.SystemSettings_GetColour(
                    wx.SYS_COLOUR_3DSHADOW
                )
            }
        )
        self._coloursMap.update({INB_HILITE_TAB_COLOUR: wx.NamedColour("LIGHT BLUE")})
        self._coloursMap.update({INB_TEXT_COLOUR: wx.WHITE})
        self._coloursMap.update({INB_ACTIVE_TEXT_COLOUR: wx.BLACK})

        # don't allow bright colour one on the other
        if not ArtManager.Get().IsDark(
            self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR]
        ) and not ArtManager.Get().IsDark(self._coloursMap[INB_TEXT_COLOUR]):

            self._coloursMap[INB_TEXT_COLOUR] = ArtManager.Get().DarkColour(
                self._coloursMap[INB_TEXT_COLOUR], 100
            )

    def draw_label(
        self, dc, rect, text, bmp, img_info, orientation_left, img_idx, selected, hover
    ):
        """
        Draws a label using the specified dc.

        Args:
            dc: an instance of `wx.DC`;
            rect: the text client rectangle;
            text: the actual text string;
            bmp: a bitmap to be drawn next to the text;
            img_info: an instance of L{ImageInfo};
            orientation_left: ``True`` if the book has the ``INB_RIGHT`` or
                ``INB_LEFT`` style set;
            img_idx: the tab image index;
            selected: ``True`` if the tab is selected, ``False`` otherwise;
            hover: ``True`` if the tab is being hovered with the mouse,
                ``False`` otherwise.
        """
        dcsaver = DCSaver(dc)
        n_padding = 6

        if orientation_left:

            rect.x += n_padding
            rect.width -= n_padding

        else:

            rect.width -= n_padding

        text_rect = wx.Rect(*rect)
        img_rect = wx.Rect(*rect)

        font = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetPointSize(
            font.GetPointSize() * self.GetParent().get_font_size_multiple()
        )
        if self.GetParent().get_font_bold():
            font.SetWeight(wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)

        # First we define the rectangle for the text
        w, h = dc.GetTextExtent(text)

        # ----------------------------------------------------------------------
        # Label layout:
        # [ n_padding | Image | n_padding | Text | n_padding ]
        # ----------------------------------------------------------------------

        # Text bounding rectangle
        text_rect.x += n_padding
        text_rect.y = rect.y + (rect.height - h) / 2
        text_rect.width = rect.width - 2 * n_padding

        if bmp.Ok() and not self.has_agw_flag(INB_SHOW_ONLY_TEXT):
            text_rect.x += bmp.GetWidth() + n_padding
            text_rect.width -= bmp.GetWidth() + n_padding

        text_rect.height = h

        # Truncate text if needed
        caption = ArtManager.Get().TruncateText(dc, text, text_rect.width)

        # Image bounding rectangle
        if bmp.Ok() and not self.has_agw_flag(INB_SHOW_ONLY_TEXT):

            img_rect.x += n_padding
            img_rect.width = bmp.GetWidth()
            img_rect.y = rect.y + (rect.height - bmp.GetHeight()) / 2
            img_rect.height = bmp.GetHeight()

        # Draw bounding rectangle
        if selected:

            # First we colour the tab
            dc.SetBrush(wx.Brush(self._coloursMap[INB_ACTIVE_TAB_COLOUR]))

            if self.has_agw_flag(INB_BORDER):
                dc.SetPen(wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR]))
            else:
                dc.SetPen(wx.Pen(self._coloursMap[INB_ACTIVE_TAB_COLOUR]))

            label_rect = wx.Rect(*rect)

            if orientation_left:
                label_rect.width += 3
            else:
                label_rect.width += 3
                label_rect.x -= 3

            dc.DrawRoundedRectangle(label_rect, 3)

            if not orientation_left and self.has_agw_flag(INB_DRAW_SHADOW):
                dc.SetPen(wx.BLACK_PEN)
                dc.DrawPoint(
                    label_rect.x + label_rect.width - 1,
                    label_rect.y + label_rect.height - 1,
                )

        # Draw the text & bitmap
        if caption != "":

            if selected:
                dc.SetTextForeground(self._coloursMap[INB_ACTIVE_TEXT_COLOUR])
            else:
                dc.SetTextForeground(self._coloursMap[INB_TEXT_COLOUR])

            dc.DrawText(caption, text_rect.x, text_rect.y)
            img_info.set_text_rect(text_rect)

        else:

            img_info.set_text_rect(wx.Rect())

        if bmp.Ok() and not self.has_agw_flag(INB_SHOW_ONLY_TEXT):
            dc.DrawBitmap(bmp, img_rect.x, img_rect.y, True)

        # Drop shadow
        if self.has_agw_flag(INB_DRAW_SHADOW) and selected:

            sstyle = 0
            if orientation_left:
                sstyle = BottomShadow
            else:
                sstyle = BottomShadowFull | RightShadow

            if self.has_agw_flag(INB_WEB_HILITE):

                # Always drop shadow for this style
                ArtManager.Get().DrawBitmapShadow(dc, rect, sstyle)

            else:

                if img_idx + 1 != self._nHoveredImgIdx:

                    ArtManager.Get().DrawBitmapShadow(dc, rect, sstyle)

        # Draw hover effect
        if hover:

            if self.has_agw_flag(INB_WEB_HILITE) and caption != "":
                self.draw_web_hover(dc, caption, text_rect.x, text_rect.y)
            else:
                self.draw_regular_hover(dc, rect)

        # Update the page information bout position and size
        img_info.set_position(rect.get_position())
        img_info.set_size(rect.get_size())


# ---------------------------------------------------------------------------- #
# Class FlatBookBase
# ---------------------------------------------------------------------------- #


class FlatBookBase(wx.Panel):
    """Base class for the containing window for L{LabelBook} and L{FlatImageBook}."""

    def __init__(
        self,
        parent,
        window_id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agw_style=0,
        name="FlatBookBase",
    ):
        """
        Default class constructor.

        Args:
            parent: parent window. Must not be ``None``;
            window_id: window identifier. A value of -1 indicates a default value;
            pos: the control position. A value of (-1, -1) indicates a default position,
                chosen by either the windowing system or wxPython,
                depending on platform;
            size: the control size. A value of (-1, -1) indicates a default size,
                chosen by either the windowing system or wxPython,
                depending on platform;
            style: the underlying `wx.Panel` window style;
            agw_style: the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
            name: the window name.
        """
        self._pages = None
        self._bInitializing = True
        self._pages = None
        self._bForceSelection = False
        self._windows = []
        self._fontSizeMultiple = 1.0
        self._fontBold = False

        style |= wx.TAB_TRAVERSAL
        self._agwStyle = agw_style

        wx.Panel.__init__(self, parent, window_id, pos, size, style, name)
        self._bInitializing = False

    def set_agw_window_style_flag(self, agw_style):
        """
        Sets the window style.

        Args:
            agw_style: can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
        """
        self._agwStyle = agw_style

        # Check that we are not in initialization process
        if self._bInitializing:
            return

        if not self._pages:
            return

        # Detach the windows attached to the sizer
        if self.GetSelection() >= 0:
            self._mainSizer.Detach(self._windows[self.GetSelection()])

        self._mainSizer.Detach(self._pages)

        # Create new sizer with the requested orientation
        class_name = self.GetName()

        if class_name == "LabelBook":
            self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            if agw_style & INB_LEFT or agw_style & INB_RIGHT:
                self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
            else:
                self._mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.SetSizer(self._mainSizer)

        # Add the tab container and the separator
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)

        if class_name == "FlatImageBook":

            if agw_style & INB_LEFT or agw_style & INB_RIGHT:
                self._pages.SetSizeHints(self._pages._nImgSize * 2, -1)
            else:
                self._pages.SetSizeHints(-1, self._pages._nImgSize * 2)

        # Attach the windows back to the sizer to the sizer
        if self.GetSelection() >= 0:
            self.do_set_selection(self._windows[self.GetSelection()])

        if agw_style & INB_FIT_LABELTEXT:
            self.resize_tab_area()

        self._mainSizer.Layout()
        dummy = wx.SizeEvent()
        wx.PostEvent(self, dummy)
        self._pages.Refresh()

    def get_agw_window_style_flag(self):
        """
        Returns the L{FlatBookBase} window style.

        See:
            L{set_agw_window_style_flag} for a list of possible window style flags.
        """
        return self._agwStyle

    def has_agw_flag(self, flag):
        """
        Returns whether a flag is present in the L{FlatBookBase} style.

        Args:
            flag: one of the possible L{FlatBookBase} window styles.

        See:
            L{set_agw_window_style_flag} for a list of possible window style flags.
        """
        agw_style = self.get_agw_window_style_flag()
        res = (agw_style & flag and [True] or [False])[0]
        return res

    def add_page(self, page, text, select=False, image_id=-1):
        """
        Adds a page to the book.

        Args:
            page: specifies the new page;
            text: specifies the text for the new page;
            select: specifies whether the page should be selected;
            image_id: specifies the optional image index for the new page.

        Note:
            The call to this function generates the page changing events.
        """
        if not page:
            return

        page.Reparent(self)

        self._windows.append(page)

        if select or len(self._windows) == 1:
            self.do_set_selection(page)
        else:
            page.Hide()

        self._pages.add_page(text, select, image_id)
        self.resize_tab_area()
        self.Refresh()

    def insert_page(self, page_idx, page, text, select=False, image_id=-1):
        """
        Inserts a page into the book at the specified position.

        Args:
            page_idx: specifies the position for the new page;
            page: specifies the new page;
            text: specifies the text for the new page;
            select: specifies whether the page should be selected;
            image_id: specifies the optional image index for the new page.

        Note:
            The call to this function generates the page changing events.
        """
        if not page:
            return

        page.Reparent(self)

        self._windows.insert(page_idx, page)

        if select or len(self._windows) == 1:
            self.do_set_selection(page)
        else:
            page.Hide()

        self._pages.insert_page(page_idx, text, select, image_id)
        self.resize_tab_area()
        self.Refresh()

    def delete_page(self, page):
        """
        Deletes the specified page, and the associated window.

        Args:
            page: an integer specifying the page to be deleted.

        Note:
            The call to this function generates the page changing events.
        """
        if page >= len(self._windows) or page < 0:
            return

        # Fire a closing event
        event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSING, self.GetId())
        event.set_selection(page)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

        # The event handler allows it?
        if not event.is_allowed():
            return False

        self.Freeze()

        # Delete the requested page
        page_removed = self._windows[page]

        # If the page is the current window, remove it from the sizer as well
        if page == self.GetSelection():
            self._mainSizer.Detach(page_removed)

        # Remove it from the array as well
        self._windows.pop(page)

        # Now we can destroy it in wxWidgets use Destroy instead of delete              # noqa: SC100
        page_removed.Destroy()
        self._mainSizer.Layout()

        self._pages.do_delete_page(page)
        self.resize_tab_area()
        self.Thaw()

        # Fire a closed event
        closed_event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSED, self.GetId())
        closed_event.set_selection(page)
        closed_event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(closed_event)

    def remove_page(self, page):
        """
        Deletes the specified page, without deleting the associated window.

        Args:
            page: an integer specifying the page to be removed.

        Note:
            The call to this function generates the page changing events.
        """
        if page >= len(self._windows):
            return False

        # Fire a closing event
        event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSING, self.GetId())
        event.set_selection(page)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

        # The event handler allows it?
        if not event.is_allowed():
            return False

        self.Freeze()

        # Remove the requested page
        page_removed = self._windows[page]

        # If the page is the current window, remove it from the size as well
        if page == self.GetSelection():
            self._mainSizer.Detach(page_removed)

        # Remove it from the array as well
        self._windows.pop(page)
        self._mainSizer.Layout()
        self.resize_tab_area()
        self.Thaw()

        self._pages.do_delete_page(page)

        # Fire a closed event
        closed_event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSED, self.GetId())
        closed_event.set_selection(page)
        closed_event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(closed_event)

        return True

    def resize_tab_area(self):
        """Resizes the tab area if the control has the ``INB_FIT_LABELTEXT`` style set."""
        agw_style = self.get_agw_window_style_flag()

        if agw_style & INB_FIT_LABELTEXT == 0:
            return

        if agw_style & INB_LEFT or agw_style & INB_RIGHT:
            dc = wx.MemoryDC()
            dc.SelectObject(wx.EmptyBitmap(1, 1))
            font = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font.SetPointSize(font.GetPointSize() * self._fontSizeMultiple)
            if self.get_font_bold():
                font.SetWeight(wx.FONTWEIGHT_BOLD)
            dc.SetFont(font)
            max_w = 0

            for page in range(self.GetPageCount()):
                caption = self._pages.get_page_text(page)
                w, h = dc.GetTextExtent(caption)
                max_w = max(max_w, w)

            max_w += 24  # TODO this is 6*4 6 is nPadding from drawlabel                 # noqa: SC100

            if not agw_style & INB_SHOW_ONLY_TEXT:
                max_w += self._pages._nImgSize * 2

            max_w = max(max_w, 100)
            self._pages.SetSizeHints(max_w, -1)
            self._pages._nTabAreaWidth = max_w

    def delete_all_pages(self):
        """Deletes all the pages in the book."""
        if not self._windows:
            return

        self.Freeze()

        for win in self._windows:
            win.Destroy()

        self._windows = []
        self.Thaw()

        # remove old selection
        self._pages.clear_all()
        self._pages.Refresh()

    def SetSelection(self, page):
        """
        Changes the selection from currently visible/selected page to the page given by page.

        Args:
            page: an integer specifying the page to be selected.

        Note:
            The call to this function generates the page changing events.
        """
        if page >= len(self._windows):
            return

        if page == self.GetSelection() and not self._bForceSelection:
            return

        old_selection = self.GetSelection()

        # Generate an event that indicates that an image is about to be selected
        event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CHANGING, self.GetId())
        event.set_selection(page)
        event.set_old_selection(old_selection)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

        # The event handler allows it?
        if not event.is_allowed() and not self._bForceSelection:
            return

        self.do_set_selection(self._windows[page])
        # Now we can update the new selection
        self._pages._nIndex = page

        # Refresh calls the on_paint of this class
        self._pages.Refresh()

        # Generate an event that indicates that an image was selected
        event_changed = ImageNotebookEvent(
            wxEVT_IMAGENOTEBOOK_PAGE_CHANGED, self.GetId()
        )
        event_changed.SetEventObject(self)
        event_changed.set_old_selection(old_selection)
        event_changed.set_selection(page)
        self.GetEventHandler().ProcessEvent(event_changed)

    def assign_image_list(self, imglist):
        """
        Assigns an image list to the control.

        Args:
            imglist: an instance of `wx.ImageList`.
        """
        self._pages.assign_image_list(imglist)

        # Force change
        self.set_agw_window_style_flag(self.get_agw_window_style_flag())

    def GetSelection(self):
        """Returns the current selection."""
        if self._pages:
            return self._pages._nIndex
        else:
            return -1

    def do_set_selection(self, window):
        """
        Select the window by the provided pointer.

        Args:
            window: an instance of `wx.Window`.
        """
        cur_sel = self.GetSelection()
        agw_style = self.get_agw_window_style_flag()
        # Replace the window in the sizer
        self.Freeze()

        # Check if a new selection was made
        b_insert_first = agw_style & INB_BOTTOM or agw_style & INB_RIGHT

        if cur_sel >= 0:

            # Remove the window from the main sizer
            self._mainSizer.Detach(self._windows[cur_sel])
            self._windows[cur_sel].Hide()

        if b_insert_first:
            self._mainSizer.Insert(0, window, 1, wx.EXPAND)
        else:
            self._mainSizer.Add(window, 1, wx.EXPAND)

        window.Show()
        self._mainSizer.Layout()
        self.Thaw()

    def get_image_list(self):
        """Returns the associated image list."""
        return self._pages.get_image_list()

    def GetPageCount(self):
        """Returns the number of pages in the book."""
        return len(self._windows)

    def get_font_bold(self):
        """Gets the font bold status."""
        return self._fontBold

    def set_font_bold(self, bold):
        """
        Sets whether the page captions are bold or not.

        Args:
            bold: ``True`` or ``False``.
        """
        self._fontBold = bold

    def get_font_size_multiple(self):
        """Gets the font size multiple for the page captions."""
        return self._fontSizeMultiple

    def set_font_size_multiple(self, multiple):
        """
        Sets the font size multiple for the page captions.

        Args:
            multiple: The multiple to be applied to the system font to get the
                font size.
        """
        self._fontSizeMultiple = multiple

    def SetPageImage(self, page, image_id):
        """
        Sets the image index for the given page.

        Args:
            page: an integer specifying the page index;
            image_id: an index into the image list.
        """
        self._pages.set_page_image(page, image_id)
        self._pages.Refresh()

    def SetPageText(self, page, text):
        """
        Sets the text for the given page.

        Args:
            page: an integer specifying the page index;
            text: the new tab label.
        """
        self._pages.set_page_text(page, text)
        self._pages.Refresh()

    def GetPageText(self, page):
        """
        Returns the text for the given page.

        Args:
            page: an integer specifying the page index.
        """
        return self._pages.get_page_text(page)

    def GetPageImage(self, page):
        """
        Returns the image index for the given page.

        Args:
            page: an integer specifying the page index.
        """
        return self._pages.get_page_image(page)

    def GetPage(self, page):
        """
        Returns the window at the given page position.

        Args:
            page: an integer specifying the page to be returned.
        """
        if page >= len(self._windows):
            return

        return self._windows[page]

    def GetCurrentPage(self):
        """Returns the currently selected notebook page or ``None``."""
        if self.GetSelection() < 0:
            return

        return self.GetPage(self.GetSelection())

    def advance_selection(self, forward=True):
        """
        Cycles through the tabs.

        Args:
            forward: if ``True``,
                the selection is advanced in ascending order (to the right),
                otherwise the selection is advanced in descending order.

        Note:
            The call to this function generates the page changing events.
        """
        n_sel = self.GetSelection()

        if n_sel < 0:
            return

        n_max = self.GetPageCount() - 1

        if forward:
            new_selection = (n_sel == n_max and [0] or [n_sel + 1])[0]
        else:
            new_selection = (n_sel == 0 and [n_max] or [n_sel - 1])[0]

        self.SetSelection(new_selection)

    def change_selection(self, page):
        """
        Changes the selection for the given page, returning the previous selection.

        Args:
            page: an integer specifying the page to be selected.

        Note:
            The call to this function does not generate the page changing events.
        """
        if page < 0 or page >= self.GetPageCount():
            return

        old_page = self.GetSelection()
        self.do_set_selection(page)

        return old_page

    CurrentPage = property(GetCurrentPage, doc="See `GetCurrentPage`")
    Page = property(GetPage, doc="See `GetPage`")
    PageCount = property(GetPageCount, doc="See `GetPageCount`")
    PageImage = property(
        GetPageImage, SetPageImage, doc="See `get_page_image, set_page_image`"
    )
    PageText = property(
        GetPageText, SetPageText, doc="See `get_page_text, set_page_text`"
    )
    Selection = property(
        GetSelection, SetSelection, doc="See `GetSelection, set_selection`"
    )


# ---------------------------------------------------------------------------- #
# Class FlatImageBook
# ---------------------------------------------------------------------------- #


class FlatImageBook(FlatBookBase):
    """
    Default implementation of the image book.

    It is like a `wx.Notebook`,
    except that images are used to control the different pages.
    This container is usually used for configuration dialogs etc.

    Note:
        Currently, this control works properly for images of size 32x32 and bigger.
    """

    def __init__(
        self,
        parent,
        window_id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agw_style=0,
        name="FlatImageBook",
    ):
        """
        Default class constructor.

        Args:
            parent: parent window. Must not be ``None``;
            window_id: window identifier. A value of -1 indicates a default value;
            pos: the control position. A value of (-1, -1) indicates a default position,
                chosen by either the windowing system or wxPython,
                depending on platform;
            size: the control size. A value of (-1, -1) indicates a default size,
                chosen by either the windowing system or wxPython,
                depending on platform;
            style: the underlying `wx.Panel` window style;
            agw_style: the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
            name: the window name.
        """
        FlatBookBase.__init__(
            self, parent, window_id, pos, size, style, agw_style, name
        )

        self._pages = self.create_image_container()

        if agw_style & INB_LEFT or agw_style & INB_RIGHT:
            self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            self._mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.SetSizer(self._mainSizer)

        # Add the tab container to the sizer
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)

        if agw_style & INB_LEFT or agw_style & INB_RIGHT:
            self._pages.SetSizeHints(self._pages.get_image_size() * 2, -1)
        else:
            self._pages.SetSizeHints(-1, self._pages.get_image_size() * 2)

        self._mainSizer.Layout()

    def create_image_container(self):
        """Creates the image container class for L{FlatImageBook}."""
        return ImageContainer(
            self, wx.ID_ANY, agw_style=self.get_agw_window_style_flag()
        )


# ---------------------------------------------------------------------------- #
# Class LabelBook
# ---------------------------------------------------------------------------- #


class LabelBook(FlatBookBase):
    """
    An implementation of a notebook control.

    Except that instead of having tabs to show labels,
    it labels to the right or left (arranged horizontally).
    """

    def __init__(
        self,
        parent,
        window_id=wx.ID_ANY,
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        agw_style=0,
        name="LabelBook",
    ):
        """
        Default class constructor.

        Args:
            parent: parent window. Must not be ``None``;
            window_id: window identifier. A value of -1 indicates a default value;
            pos: the control position. A value of (-1, -1) indicates a default position,
                chosen by either the windowing system or wxPython,
                depending on platform;
            size: the control size. A value of (-1, -1) indicates a default size,
                chosen by either the windowing system or wxPython,
                depending on platform;
            style: the underlying `wx.Panel` window style;
            agw_style: the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ========================
                Window Styles               Hex Value   Description
                =========================== =========== ========================
                ``INB_BOTTOM``                      0x1 Place labels below the
                                                        page area. Available
                                                        only for L{FlatImageBook}.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        L{FlatImageBook}.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the
                                                        page area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        L{LabelBook} or
                                                        L{FlatImageBook}.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels
                                                        and no images.
                                                        Available only for L{LabelBook}.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images
                                                        and no label texts.
                                                        Available only for L{LabelBook}.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the
                                                        book tabs.
                                                        Available only for L{LabelBook}.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading
                                                        on the tabs background.
                                                        Available only for L{LabelBook}.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs
                                                        behave like html hyperlinks.
                                                        Available only for L{LabelBook}.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of
                                                        the tab area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to
                                                        the longest text (or
                                                        text+image if you have images)
                                                        in all the tabs.
                =========================== =========== ========================
            name: the window name.
        """
        FlatBookBase.__init__(
            self, parent, window_id, pos, size, style, agw_style, name
        )

        self._pages = self.create_image_container()

        # Label book specific initialization
        self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._mainSizer)

        # Add the tab container to the sizer
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)
        self._pages.SetSizeHints(self._pages.get_tab_area_width(), -1)

        # Initialize the colours maps
        self._pages.initialize_colours()

        self.Bind(wx.EVT_SIZE, self.on_size)

    def create_image_container(self):
        """Creates the image container (LabelContainer) class for L{FlatImageBook}."""
        return LabelContainer(
            self, wx.ID_ANY, agw_style=self.get_agw_window_style_flag()
        )

    def set_colour(self, which, colour):
        """
        Sets the colour for the specified parameter.

        Args:
            which: the colour key;
            colour: a valid `wx.Colour` instance.

        See:
            L{LabelContainer.set_colour} for a list of valid colour keys.
        """
        self._pages.set_colour(which, colour)

    def get_colour(self, which):
        """
        Returns the colour for the specified parameter.

        Args:
            which: the colour key.

        See:
            L{LabelContainer.set_colour} for a list of valid colour keys.
        """
        return self._pages.get_colour(which)

    def on_size(self, event):
        """
        Handles the ``wx.EVT_SIZE`` event for L{LabelBook}.

        Args:
            event: a `wx.SizeEvent` event to be processed.
        """
        self._pages.Refresh()
        event.Skip()
