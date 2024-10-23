# ------------------------------------------------------------------------------------ #
# LABELBOOK And FLATIMAGEBOOK Widgets wxPython IMPLEMENTATION
#
# Original C++ Code From Eran, embedded in the FlatMenu source code
#
#
# License: wxWidgets license
#
#
# Python Code By:
#
# Andrea Gavana, @ 03 Nov 2006
# Latest Revision: 22 Jan 2013, 21.00 GMT
#
#
# For All Kind Of Problems, Requests Of Enhancements And Bug Reports,
# Please Write To Me At:
#
# andrea.gavana@gmail.com
# andrea.gavana@maerskoil.com
#
# Or, Obviously, To The wxPython Mailing List!!!
#
# TODO:
# LabelBook - Support IMB_SHOW_ONLY_IMAGES
# LabelBook - An option to only draw the border between the controls and the pages so
#             the background colour can flow into the window background
#
# Tags:        phoenix-port, unittest, documented, py3-port
#
#
# End Of Comments
# ------------------------------------------------------------------------------------ #

"""LabelBook and FlatImageBook are owner-drawn notebooks.

Description
===========

:class:`LabelBook` and :class:`FlatImageBook` are quasi-full implementations of the
:class:`Notebook`, and designed to be a drop-in replacement for :class:`Notebook`.
The API functions are similar so one can expect the function to behave in the same way.
:class:`LabelBook` and :class:`FlatImageBook` share their appearance with
:class:`Toolbook` and :class:`Listbook`, while having more options for custom drawings,
label positioning, mouse pointing and so on.
Moreover, they retain also some visual characteristics of the Outlook address book.

Some features:

- They are generic controls;
- Supports for left, right, top (:class:`FlatImageBook` only),
  bottom (:class:`FlatImageBook` only) book styles;
- Possibility to draw images only, text only or both (:class:`FlatImageBook` only);
- Support for a "pin-button", that allows the user to shrink/expand the book tab area;
- Shadows behind tabs (:class:`LabelBook` only);
- Gradient shading of the tab area (:class:`LabelBook` only);
- Web-like mouse pointing on tabs style (:class:`LabelBook` only);
- Many customizable colours
  (tab area, active tab text, tab borders, active tab, highlight)
  :class:`LabelBook` only.

And much more. See the demo for a quasi-complete review of all the functionalities of
:class:`LabelBook` and :class:`FlatImageBook`.


Usage
=====

Usage example::

import wx
import wx.lib.agw.labelbook as LB


class MyFrame(wx.Frame):

    def __init__(self, parent: wx.Window | None) -> None:
        wx.Frame.__init__(self, parent, -1, "LabelBook Demo")

        # Possible values for Tab placement are INB_TOP, INB_BOTTOM, INB_RIGHT, INB_LEFT
        notebook = LB.LabelBook(
            self,
            -1,
            agwStyle=LB.INB_FIT_LABELTEXT
            | LB.INB_LEFT
            | LB.INB_DRAW_SHADOW
            | LB.INB_GRADIENT_BACKGROUND,
        )

        pane1 = wx.Panel(notebook)
        pane2 = wx.Panel(notebook)

        imagelist = wx.ImageList(32, 32)
        imagelist.Add(wx.Bitmap("my_bitmap.png", wx.BITMAP_TYPE_PNG))
        notebook.AssignImageList(imagelist)

        notebook.AddPage(pane1, "Tab1", True, 0)
        notebook.AddPage(pane2, "Tab2", False, 0)


# our normal wxApp-derived class, as usual
app = wx.App(False)

frame = MyFrame(None)
app.SetTopWindow(frame)
frame.Show()

app.MainLoop()

Supported Platforms
===================

:class:`LabelBook` and :class:`FlatImageBook` have been tested on the following
platforms:
  * Windows (Windows XP);
  * Linux Ubuntu (Dapper 6.06)


Window Styles
=============

This class supports the following window styles:

=========================== =========== ================================================
Window Styles               Hex Value   Description
=========================== =========== ================================================
``INB_BOTTOM``                      0x1 Place labels below the page area.
                                        Available only for :class:`FlatImageBook`.
``INB_LEFT``                        0x2 Place labels on the left side.
                                        Available only for :class:`FlatImageBook`.
``INB_RIGHT``                       0x4 Place labels on the right side.
``INB_TOP``                         0x8 Place labels above the page area.
``INB_BORDER``                     0x10 Draws a border around :class:`LabelBook` or
                                        :class:`FlatImageBook`.
``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no images.
                                        Available only for :class:`LabelBook`.
``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no label texts.
                                        Available only for :class:`LabelBook`.
``INB_FIT_BUTTON``                 0x80 Displays a pin button to show/hide the book
                                        control.
``INB_DRAW_SHADOW``               0x100 Draw shadows below the book tabs.
                                        Available only for :class:`LabelBook`.
``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to show/hide the book
                                        control.
``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the tabs background.
                                        Available only for :class:`LabelBook`.
``INB_WEB_HILITE``                0x800 On mouse hovering,
                                        tabs behave like html hyperlinks.
                                        Available only for :class:`LabelBook`.
``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab area.
``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the longest text (or
                                        text+image if you have images) in all the tabs.
``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using a bold font.
=========================== =========== ================================================


Events Processing
=================

This class processes the following events:

=================================== ====================================================
Event Name                          Description
=================================== ====================================================
``EVT_IMAGENOTEBOOK_PAGE_CHANGED``  Notify client objects when the active page in
                                    :class:`FlatImageBook` or :class:`LabelBook` has
                                    changed.
``EVT_IMAGENOTEBOOK_PAGE_CHANGING`` Notify client objects when the active page in
                                    :class:`FlatImageBook` or :class:`LabelBook` is
                                    about to change.
``EVT_IMAGENOTEBOOK_PAGE_CLOSED``   Notify client objects when a page in
                                    :class:`FlatImageBook` or :class:`LabelBook` has
                                    been closed.
``EVT_IMAGENOTEBOOK_PAGE_CLOSING``  Notify client objects when a page in
                                    :class:`FlatImageBook` or :class:`LabelBook` is
                                    closing.
=================================== ====================================================


TODOs
=====

- :class:`LabelBook`: support ``IMB_SHOW_ONLY_IMAGES``;
- :class:`LabelBook`: an option to only draw the border between the controls and the
  pages so the background colour can flow into the window background.


License And Version
===================

:class:`LabelBook` and :class:`FlatImageBook` are distributed under the wxPython
license.

Latest Revision: Andrea Gavana @ 22 Jan 2013, 21.00 GMT

Version 0.6.
"""

__version__ = "0.6"


# --------------------------------------------------------------------------------------
# Beginning Of IMAGENOTEBOOK wxPython Code
# --------------------------------------------------------------------------------------

from enum import IntFlag

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
    INB_TABS_BORDER_COLOUR,
    INB_TAB_AREA_BACKGROUND_COLOUR,
    INB_TEXT_COLOUR,
    RightShadow,
    pin_down_xpm,
    pin_left_xpm,
)

import wx


class ImageBookStyle(IntFlag):
    INB_BOTTOM = 1
    """Place labels below the page area.

    Available only for :class:`FlatImageBook`.
    """
    INB_LEFT = 2
    """Place labels on the left side.

    Available only for :class:`FlatImageBook`.
    """
    INB_RIGHT = 4
    """Place labels on the right side."""
    INB_TOP = 8
    """Place labels above the page area."""
    INB_BORDER = 16
    """Draw a border around :class:`LabelBook` or :class:`FlatImageBook`."""
    INB_SHOW_ONLY_TEXT = 32
    """Show only text labels and no images.

    Available only for :class:`LabelBook`.
    """
    INB_SHOW_ONLY_IMAGES = 64
    """Show only tab images and no label texts.

    Available only for :class:`LabelBook`.
    """
    INB_FIT_BUTTON = 128
    """Display a pin button to show/hide the book control."""
    INB_DRAW_SHADOW = 256
    """Draw shadows below the book tabs.

    Available only for :class:`LabelBook`.
    """
    INB_USE_PIN_BUTTON = 512
    """Display a pin button to show/hide the book control."""
    INB_GRADIENT_BACKGROUND = 1024
    """Draw a gradient shading on the tabs background.

    Available only for :class:`LabelBook`.
    """
    INB_WEB_HILITE = 2048
    """On mouse hovering, tabs behave like html hyperlinks.

    Available only for :class:`LabelBook`.
    """
    INB_NO_RESIZE = 4096
    """Don't allow resizing of the tab area."""
    INB_FIT_LABELTEXT = 8192
    """Fit the tab area to the longest text (or text+image)."""
    INB_BOLD_TAB_SELECTION = 16384
    """Show the selected tab text using a bold font."""


wxEVT_IMAGENOTEBOOK_PAGE_CHANGED: int = wx.wxEVT_COMMAND_NOTEBOOK_PAGE_CHANGED
wxEVT_IMAGENOTEBOOK_PAGE_CHANGING: int = wx.wxEVT_COMMAND_NOTEBOOK_PAGE_CHANGING
wxEVT_IMAGENOTEBOOK_PAGE_CLOSING: int = wx.NewEventType()
wxEVT_IMAGENOTEBOOK_PAGE_CLOSED: int = wx.NewEventType()

# --------------------------------------------------------------------------------------#
#        ImageNotebookEvent
# --------------------------------------------------------------------------------------#

EVT_IMAGENOTEBOOK_PAGE_CHANGED: wx.PyEventBinder = wx.EVT_NOTEBOOK_PAGE_CHANGED
"""Notify clients when the active page in FlatImageBook or LabelBook changes."""
EVT_IMAGENOTEBOOK_PAGE_CHANGING: wx.PyEventBinder = wx.EVT_NOTEBOOK_PAGE_CHANGING
"""Notify clients when the active page changes."""
EVT_IMAGENOTEBOOK_PAGE_CLOSING = wx.PyEventBinder(wxEVT_IMAGENOTEBOOK_PAGE_CLOSING, 1)
"""Notify clients when a page in :class:`FlatImageBook` or :class:`LabelBook` closes."""
EVT_IMAGENOTEBOOK_PAGE_CLOSED = wx.PyEventBinder(wxEVT_IMAGENOTEBOOK_PAGE_CLOSED, 1)
"""Notify clients when a page in FlatImageBook or LabelBook is closed."""


# ------------------------------------------------------------------------------------ #
# Class ImageNotebookEvent
# ------------------------------------------------------------------------------------ #


class ImageNotebookEvent(wx.PyCommandEvent):
    """These events are sent when page changes or closures are mapped in the parent."""

    def __init__(
        self, eventType: int, eventId: int = 1, sel: int = -1, oldsel: int = -1
    ) -> None:
        """Construct the default class.

        Args:
            eventType (int): the event type;
            eventId (int): the event identifier;
            sel (int): the current selection;
            oldsel (int): the old selection.
        """
        wx.PyCommandEvent.__init__(self, eventType, eventId)
        self._eventType: int = eventType
        self._sel: int = sel
        self._oldsel: int = oldsel
        self._allowed = True

    def SetSelection(self, s: int) -> None:
        """Set the event selection.

        Args:
            s (int): an integer specifying the new selection.
        """
        self._sel = s

    def SetOldSelection(self, s: int) -> None:
        """Set the event old selection.

        Args:
            s (int): an integer specifying the old selection.
        """
        self._oldsel = s

    def GetSelection(self) -> int:
        """Return the event selection."""
        return self._sel

    def GetOldSelection(self) -> int:
        """Return the old event selection."""
        return self._oldsel

    def Veto(self) -> None:
        """Prevent the change announced by this event from happening.

        Note:
            It is in general a good idea to notify the user about the reasons for
            vetoing the change because otherwise the applications behaviour
            (which just refuses to do what the user wants) might be quite surprising.
        """
        self._allowed = False

    def Allow(self) -> None:
        """Explicitly allow the event to be processed.

        This is the opposite of :meth:`~ImageNotebookEvent.Veto`.
        For most events it is not necessary to call this method as the events are
        allowed anyhow but some are forbidden by default
        (this will be mentioned in the corresponding event description).
        """
        self._allowed = True

    def IsAllowed(self) -> bool:
        """Return ``True`` if allowed, ``False`` if vetoed."""
        return self._allowed


# ------------------------------------------------------------------------------------ #
# Class ImageInfo
# ------------------------------------------------------------------------------------ #


class ImageInfo(object):
    """This class stores tab info (caption, image, etc.) for :class:`LabelBook`."""

    def __init__(
        self, strCaption: str = "", imageIndex: int = -1, enabled: bool = True
    ) -> None:
        """Construct the default class.

        Args:
            strCaption (str): the tab caption;
            imageIndex (int): the tab image index based on the assigned (set)
                :class:`wx.ImageList` (if any);
            enabled (bool): sets the tab as enabled or disabled.
        """
        self._pos = wx.Point()
        self._size = wx.Size()
        self._strCaption: str = strCaption
        self._ImageIndex: int = imageIndex
        self._captionRect = wx.Rect()
        self._bEnabled: bool = enabled

    def SetCaption(self, value: str) -> None:
        """Set the tab caption.

        Args:
            value (str): the new tab caption.
        """
        self._strCaption = value

    def GetCaption(self) -> str:
        """Return the tab caption."""
        return self._strCaption

    def SetPosition(self, value: wx.Point) -> None:
        """Set the tab position.

        Args:
            value (wx.Point): the new tab position, an instance of :class:`wx.Point`.
        """
        self._pos: wx.Point = value

    def GetPosition(self) -> wx.Point:
        """Return the tab position."""
        return self._pos

    def SetSize(self, value: wx.Size) -> None:
        """Set the tab size.

        Args:
            value (wx.Size):  the new tab size, an instance of :class:`wx.Size`.
        """
        self._size: wx.Size = value

    def GetSize(self) -> wx.Size:
        """Return the tab size."""
        return self._size

    def SetImageIndex(self, value: int) -> None:
        """Set the tab image index.

        Args:
            value (int): an index into the image list..
        """
        self._ImageIndex = value

    def GetImageIndex(self) -> int:
        """Return the tab image index."""
        return self._ImageIndex

    def SetTextRect(self, rect: wx.Rect) -> None:
        """Set the client rectangle available for the tab text.

        Args:
            rect (wx.Rect): the tab text client rectangle,
                an instance of :class:`wx.Rect`.
        """
        self._captionRect: wx.Rect = rect

    def GetTextRect(self) -> wx.Rect:
        """Return the client rectangle available for the tab text."""
        return self._captionRect

    def GetEnabled(self) -> bool:
        """Return whether the tab is enabled or not."""
        return self._bEnabled

    def EnableTab(self, enabled: bool) -> None:
        """Set the tab enabled or disabled.

        Args:
            enabled (bool): ``True`` to enable a tab, ``False`` to disable it.
        """
        self._bEnabled = enabled


# ------------------------------------------------------------------------------------ #
# Class ImageContainerBase
# ------------------------------------------------------------------------------------ #


class ImageContainerBase(wx.Panel):
    """Base class for :class:`FlatImageBook` image container."""

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "ImageContainerBase",
    ) -> None:
        """Construct the default class.

        Args:
            parent (wx.Window): parent window. Must not be ``None``;
            id (int): window identifier. A value of -1 indicates a default value;
            pos (wx.Point): the control position.
                A value of (-1, -1) indicates a default position, chosen by either the
                windowing system or wxPython, depending on platform;
            size (wx.Size): the control size.
                A value of (-1, -1) indicates a default size, chosen by either the
                windowing system or wxPython, depending on platform;
            style (int): the underlying :class:`Panel` window style;
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
            name (str): the window name.
        """
        self._nIndex = -1
        self._nImgSize = 16
        self._ImageList = None
        self._nHoveredImgIdx = -1
        self._bCollapsed = False
        self._tabAreaSize: wx.Size = wx.Size(-1, -1)
        self._nPinButtonStatus: int = INB_PIN_NONE
        self._pagesInfoVec: list[ImageInfo] = []
        self._pinBtnRect: wx.Rect = wx.Rect()

        wx.Panel.__init__(
            self,
            parent,
            id,
            pos,
            size,
            style | wx.NO_BORDER | wx.NO_FULL_REPAINT_ON_RESIZE,
            name,
        )

    def HasAGWFlag(self, flag: int) -> bool:
        """Test for existence of flag in the style.

        Args:
            flag (int): a window style. This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
        """
        style: int = self.GetParent().GetAGWWindowStyleFlag()
        res: bool = (style & flag and [True] or [False])[0]
        return res

    def ClearFlag(self, flag: int) -> None:
        """Remove flag from the style.

        Args:
            flag (int): a window style flag.

        See:
            :meth:`~ImageContainerBase.HasAGWFlag` for a list of possible window style
                flags.
        """
        parent: wx.Window = self.GetParent()
        if isinstance(parent, LabelBook):
            agwStyle: int = parent.GetAGWWindowStyleFlag()
            agwStyle &= ~flag
            parent.SetAGWWindowStyleFlag(agwStyle)
        else:
            raise TypeError(
                "Parent must be an instance of LabelBook or a compatible AGW class"
            )

    def AssignImageList(self, imglist: wx.ImageList) -> None:
        """Assign an image list to the :class:`wx.ImageContainerBase`.

        Args:
            imglist (wx.ImageList): an instance of :class:`wx.ImageList`.
        """
        if imglist and imglist.GetImageCount() != 0:
            self._nImgSize: int = imglist.GetBitmap(0).GetHeight()

        self._ImageList: None | wx.ImageList = imglist
        parent: wx.Window = self.GetParent()
        if isinstance(parent, LabelBook):
            agwStyle: int = parent.GetAGWWindowStyleFlag()
            parent.SetAGWWindowStyleFlag(agwStyle)
        else:
            raise TypeError(
                "Parent must be an instance of LabelBook or a compatible AGW class"
            )

    def GetImageList(self) -> None | wx.ImageList:
        """Return the image list for :class:`wx.ImageContainerBase`."""
        return self._ImageList

    def GetImageSize(self) -> int:
        """Return the image size in the :class:`wx.ImageContainerBase` image list."""
        return self._nImgSize

    def FixTextSize(self, dc: wx.DC, text: str, maxWidth: int) -> str | None:
        """Fix the text, to fit `maxWidth` value.

        If the text length exceeds `maxWidth` value this function truncates it and
        appends two dots at the end.
        ("Long Long Long Text" might become "Long Long...").

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`;
            text (str): the text to fix/truncate;
            maxWidth (int): the maximum allowed width for the text, in pixels.
        """
        return ArtManager.Get().TruncateText(dc, text, maxWidth)

    def CanDoBottomStyle(self) -> bool:
        """Allow the parent to examine the children type.

        Some implementation (such as :class:`LabelBook`),
        does not support top/bottom images, only left/right.
        """
        return False

    def AddPage(self, caption: str, selected: bool = False, imgIdx: int = -1) -> None:
        """Add a page to the container.

        Args:
            caption (str): specifies the text for the new tab;
            selected (bool): specifies whether the page should be selected;
            imgIdx (int): specifies the optional image index for the new tab.
        """
        self._pagesInfoVec.append(ImageInfo(caption, imgIdx))
        if selected or len(self._pagesInfoVec) == 1:
            self._nIndex: int = len(self._pagesInfoVec) - 1

        self.Refresh()

    def InsertPage(
        self, page_idx: int, caption: str, selected: bool = False, imgIdx: int = -1
    ) -> None:
        """Insert a page into the container at the specified position.

        Args:
            page_idx (int): specifies the position for the new tab;
            caption (str): specifies the text for the new tab;
            selected (bool): specifies whether the page should be selected;
            imgIdx (int): specifies the optional image index for the new tab.
        """
        self._pagesInfoVec.insert(page_idx, ImageInfo(caption, imgIdx))
        if selected or len(self._pagesInfoVec) == 1:
            self._nIndex = len(self._pagesInfoVec) - 1

        self.Refresh()

    def SetPageImage(self, page: int, imgIdx: int) -> None:
        """Set the image for the given page.

        Args:
            page (int): the index of the tab;
            imgIdx (int): specifies the optional image index for the tab.
        """
        imgInfo: ImageInfo = self._pagesInfoVec[page]
        imgInfo.SetImageIndex(imgIdx)

    def SetPageText(self, page: int, text: str) -> None:
        """Set the tab caption for the given page.

        Args:
            page (int): the index of the tab;
            text (str): the new tab caption.
        """
        imgInfo: ImageInfo = self._pagesInfoVec[page]
        imgInfo.SetCaption(text)

    def GetPageImage(self, page: int) -> int:
        """Return the image index for the given page.

        Args:
            page (int): the index of the tab.
        """
        imgInfo: ImageInfo = self._pagesInfoVec[page]
        return imgInfo.GetImageIndex()

    def GetPageText(self, page: int) -> str:
        """Return the tab caption for the given page.

        Args:
            page (int): the index of the tab.
        """
        imgInfo: ImageInfo = self._pagesInfoVec[page]
        return imgInfo.GetCaption()

    def GetEnabled(self, page: int) -> bool:
        """Return whether a tab is enabled or not.

        Args:
            page (int): an integer specifying the page index.
        """
        if page >= len(self._pagesInfoVec):
            return True  # Adding a page - enabled by default

        imgInfo: ImageInfo = self._pagesInfoVec[page]
        return imgInfo.GetEnabled()

    def EnableTab(self, page: int, enabled: bool = True) -> None:
        """Enable or disable a tab.

        Args:
            page (int): an integer specifying the page index;
            enabled (bool): ``True`` to enable a tab, ``False`` to disable it.
        """
        if page >= len(self._pagesInfoVec):
            return

        imgInfo: ImageInfo = self._pagesInfoVec[page]
        imgInfo.EnableTab(enabled)

    def ClearAll(self) -> None:
        """Delete all the pages in the container."""
        self._pagesInfoVec = []
        self._nIndex = wx.NOT_FOUND

    def DoDeletePage(self, page: int) -> None:
        """Delete the page.

        Args:
            page (int): the index of the tab.
        """
        # Remove the page from the vector
        book: wx.Window = self.GetParent()
        self._pagesInfoVec.pop(page)

        if self._nIndex >= page:
            self._nIndex = self._nIndex - 1

        # The delete page was the last first on the array, but the book still has more
        # pages, so we set the active page to be the first one (0)
        if self._nIndex < 0 and len(self._pagesInfoVec) > 0:
            self._nIndex = 0

        # Refresh the tabs
        if self._nIndex >= 0:

            if isinstance(book, FlatBookBase):
                book._bForceSelection = True
                book.SetSelection(self._nIndex)
                book._bForceSelection = False

        if not self._pagesInfoVec:
            # Erase the page container drawings
            dc = wx.ClientDC(self)
            dc.Clear()

    def OnSize(self, event: wx.SizeEvent) -> None:
        """Handle the ``wx.EVT_SIZE`` event for :class:`wx.ImageContainerBase`.

        Args:
            event (wx.SizeEvent): a :class:`wx.SizeEvent` event to be processed.
        """
        self.Refresh()  # Call on paint
        event.Skip()

    def OnEraseBackground(self, event: wx.EraseEvent) -> None:
        """
        Handle the ``wx.EVT_ERASE_BACKGROUND`` event for :class:`wx.ImageContainerBase`.

        Args:
            event (wx.EraseEvent): a :class:`EraseEvent` event to be processed.

        Note:
            This method is intentionally empty to reduce flicker.
        """
        pass

    def HitTest(self, pt: wx.Point) -> tuple[int, int]:
        """Return the index of the tab at the specified position or NOT_FOUND if None.

        plus the flag style of :meth:`~ImageContainerBase.HitTest`.

        Args:
            pt (wx.Point): an instance of :class:`wx.Point`, to test for hits.

        Returns:
            The index of the tab at the specified position plus the hit test flag,
                which can be one of the following bits:
                ====================== ======= =========================================
                HitTest Flags           Value  Description
                ====================== ======= =========================================
                ``IMG_OVER_IMG``             0 The mouse is over the tab icon
                ``IMG_OVER_PIN``             1 The mouse is over the pin button
                ``IMG_OVER_EW_BORDER``       2 The mouse is over the east-west book
                                                border
                ``IMG_NONE``                 3 Nowhere
                ====================== ======= =========================================
        """
        style: int = self.GetParent().GetAGWWindowStyleFlag()

        if style & ImageBookStyle.INB_USE_PIN_BUTTON:
            if self._pinBtnRect.Contains(pt):
                return -1, IMG_OVER_PIN

        for i in range(len(self._pagesInfoVec)):

            if self._pagesInfoVec[i].GetPosition() == wx.Point(-1, -1):
                break

            # For Web Hover style, we test the TextRect
            if not self.HasAGWFlag(ImageBookStyle.INB_WEB_HILITE):
                buttonRect = wx.Rect(
                    self._pagesInfoVec[i].GetPosition(), self._pagesInfoVec[i].GetSize()
                )
            else:
                buttonRect: wx.Rect = self._pagesInfoVec[i].GetTextRect()

            if buttonRect.Contains(pt):
                return i, IMG_OVER_IMG

        if self.PointOnSash(pt):
            return -1, IMG_OVER_EW_BORDER
        else:
            return -1, IMG_NONE

    def PointOnSash(self, pt: wx.Point) -> bool:
        """Test whether pt is located on the sash.

        Args:
            pt (wx.Point): an instance of :class:`wx.Point`, to test for hits.
        """
        # Check if we are on a the sash border
        cltRect: wx.Rect = self.GetClientRect()

        if self.HasAGWFlag(ImageBookStyle.INB_LEFT) or self.HasAGWFlag(
            ImageBookStyle.INB_TOP
        ):
            if pt.x > cltRect.x + cltRect.width - 4:
                return True

        else:
            if pt.x < 4:
                return True

        return False

    def OnMouseLeftDown(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_DOWN`` event for :class:`wx.ImageContainerBase`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        event.Skip()

        # Support for collapse/expand
        style: int = self.GetParent().GetAGWWindowStyleFlag()
        if style & ImageBookStyle.INB_USE_PIN_BUTTON:

            if self._pinBtnRect.Contains(event.GetPosition()):

                self._nPinButtonStatus = INB_PIN_PRESSED
                dc = wx.ClientDC(self)
                self.DrawPin(dc, self._pinBtnRect, not self._bCollapsed)
                return

        # In case panel is collapsed, there is nothing to check
        if self._bCollapsed:
            return

        tabIdx, where = self.HitTest(event.GetPosition())

        if where == IMG_OVER_IMG:
            self._nHoveredImgIdx = -1

        if tabIdx == -1:
            return

        self.GetParent().SetSelection(tabIdx)

    def OnMouseLeaveWindow(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEAVE_WINDOW`` event for :class:`wx.ImageContainerBase`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        bRepaint: bool = self._nHoveredImgIdx != -1
        self._nHoveredImgIdx = -1

        # Make sure the pin button status is NONE in case we were in pin button style
        style: int = self.GetParent().GetAGWWindowStyleFlag()

        if style & ImageBookStyle.INB_USE_PIN_BUTTON:

            self._nPinButtonStatus = INB_PIN_NONE
            dc = wx.ClientDC(self)
            self.DrawPin(dc, self._pinBtnRect, not self._bCollapsed)

        # Restore cursor
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

        if bRepaint:
            self.Refresh()

    def OnMouseLeftUp(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_UP`` event for :class:`wx.ImageContainerBase`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        style: int = self.GetParent().GetAGWWindowStyleFlag()

        if style & ImageBookStyle.INB_USE_PIN_BUTTON:

            bIsLabelContainer: bool = not self.CanDoBottomStyle()

            if self._pinBtnRect.Contains(event.GetPosition()):

                self._nPinButtonStatus = INB_PIN_NONE
                self._bCollapsed: bool = not self._bCollapsed

                if self._bCollapsed:

                    # Save the current tab area width
                    self._tabAreaSize = self.GetSize()

                    if bIsLabelContainer:

                        self.SetSizeHints(20, self._tabAreaSize[1])

                    else:

                        if (
                            style & ImageBookStyle.INB_BOTTOM
                            or style & ImageBookStyle.INB_TOP
                        ):
                            self.SetSizeHints(self._tabAreaSize[0], 20)
                        else:
                            self.SetSizeHints(20, self._tabAreaSize[1])

                else:

                    if bIsLabelContainer:

                        self.SetSizeHints(self._tabAreaSize[0], -1)

                    else:

                        # Restore the tab area size
                        if (
                            style & ImageBookStyle.INB_BOTTOM
                            or style & ImageBookStyle.INB_TOP
                        ):
                            self.SetSizeHints(-1, self._tabAreaSize[1])
                        else:
                            self.SetSizeHints(self._tabAreaSize[0], -1)

                self.GetParent().GetSizer().Layout()
                self.Refresh()
                return

    def OnMouseMove(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_MOTION`` event for :class:`wx.ImageContainerBase`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        style: int = self.GetParent().GetAGWWindowStyleFlag()
        if style & ImageBookStyle.INB_USE_PIN_BUTTON:

            # Check to see if we are in the pin button rect
            if (
                not self._pinBtnRect.Contains(event.GetPosition())
                and self._nPinButtonStatus == INB_PIN_PRESSED
            ):

                self._nPinButtonStatus = INB_PIN_NONE
                dc = wx.ClientDC(self)
                self.DrawPin(dc, self._pinBtnRect, not self._bCollapsed)

        imgIdx, where = self.HitTest(event.GetPosition())

        # Allow hovering unless over current tab or tab is disabled
        self._nHoveredImgIdx = -1

        if (
            imgIdx < len(self._pagesInfoVec)
            and self.GetEnabled(imgIdx)
            and imgIdx != self._nIndex
        ):
            self._nHoveredImgIdx: int = imgIdx

        if not self._bCollapsed:

            if self._nHoveredImgIdx >= 0 and self.HasAGWFlag(
                ImageBookStyle.INB_WEB_HILITE
            ):

                # Change the cursor to be Hand if we have the Web hover style set
                self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

            elif not self.PointOnSash(event.GetPosition()):

                # Restore the cursor if we are not currently hovering the sash
                self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

        self.Refresh()

    def DrawPin(self, dc: wx.DC, rect: wx.Rect, downPin: bool) -> None:
        """Draw a pin button, that allows collapsing of the image panel.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`;
            rect (wx.Rect): the pin button client rectangle;
            downPin (bool): ``True`` if the pin button is facing downwards,
                ``False`` if it is facing leftwards.
        """
        # Set the bitmap according to the button status

        if downPin:
            pinBmp = wx.Bitmap(pin_down_xpm)
        else:
            pinBmp = wx.Bitmap(pin_left_xpm)

        xx: int = rect.x + 2

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
            dc.SetPen(wx.LIGHT_GREY_PEN)
            dc.DrawRectangle(xx, rect.y, 16, 16)

            # Draw upper and left border with grey colour
            dc.SetPen(wx.BLACK_PEN)
            dc.DrawLine(xx, rect.y, xx + 16, rect.y)
            dc.DrawLine(xx, rect.y, xx, rect.y + 16)

        # Set the masking
        pinBmp.SetMask(wx.Mask(pinBmp, wx.WHITE))

        # Draw the new bitmap
        dc.DrawBitmap(pinBmp, xx, rect.y, True)

        # Save the pin rect
        self._pinBtnRect = rect


# ------------------------------------------------------------------------------------ #
# Class ImageContainer
# ------------------------------------------------------------------------------------ #


class ImageContainer(ImageContainerBase):
    """Base class for :class:`FlatImageBook` image container."""

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "ImageContainer",
    ) -> None:
        """Construct the default class.

        Args:
            parent (wx.Window): parent window. Must not be ``None``;
            id (int): window identifier. A value of -1 indicates a default value;
            pos (wx.Point): the control position.
                A value of (-1, -1) indicates a default position, chosen by either the
                windowing system or wxPython, depending on platform;
            size (wx.Size): the control size.
                A value of (-1, -1) indicates a default size, chosen by either the
                windowing system or wxPython, depending on platform;
            style (int): the underlying :class:`Panel` window style;
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
            name (str): the window name.
        """
        ImageContainerBase.__init__(self, parent, id, pos, size, style, agwStyle, name)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseLeftUp)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeaveWindow)

        self.padding = 4  # Define padding as a class attribute

    def OnSize(self, event: wx.SizeEvent) -> None:
        """Handle the ``wx.EVT_SIZE`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.SizeEvent): a :class:`wx.SizeEvent` event to be processed.
        """
        ImageContainerBase.OnSize(self, event)
        event.Skip()

    def OnMouseLeftDown(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_DOWN`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        ImageContainerBase.OnMouseLeftDown(self, event)
        event.Skip()

    def OnMouseLeftUp(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_UP`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        ImageContainerBase.OnMouseLeftUp(self, event)
        event.Skip()

    def OnEraseBackground(self, event: wx.EraseEvent) -> None:
        """Handle the ``wx.EVT_ERASE_BACKGROUND`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.EraseEvent): a :class:`EraseEvent` event to be processed.
        """
        ImageContainerBase.OnEraseBackground(self, event)

    def OnMouseMove(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_MOTION`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        ImageContainerBase.OnMouseMove(self, event)
        event.Skip()

    def OnMouseLeaveWindow(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEAVE_WINDOW`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        ImageContainerBase.OnMouseLeaveWindow(self, event)
        event.Skip()

    def CanDoBottomStyle(self) -> bool:
        """Allow the parent to examine the children type.

        Some implementation (such as :class:`LabelBook`),
        does not support top/bottom images, only left/right.
        """
        return True

    def OnPaint(self, event: wx.PaintEvent) -> None:
        """Handle the ``wx.EVT_PAINT`` event for :class:`wx.ImageContainer`.

        Args:
            event (wx.PaintEvent): a :class:`PaintEvent` event to be processed.
        """
        dc = wx.BufferedPaintDC(self)
        style: int = ImageBookStyle(self.GetParent().GetAGWWindowStyleFlag())

        self._draw_background(dc, style)
        self._draw_pin_button(dc, style)
        self._draw_buttons(dc, style)

    def _draw_background(self, dc: wx.DC, style: ImageBookStyle) -> None:
        size: wx.Size = self.GetSize()
        backBrush: wx.Brush = wx.WHITE_BRUSH
        borderPen: wx.Pen = (
            wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW))
            if style & ImageBookStyle.INB_BORDER
            else wx.TRANSPARENT_PEN
        )

        dc.SetBrush(backBrush)
        dc.SetPen(borderPen)
        dc.DrawRectangle(0, 0, size.width, size.height)

    def _draw_pin_button(self, dc: wx.DC, style: ImageBookStyle) -> None:
        if not (style & ImageBookStyle.INB_USE_PIN_BUTTON):
            return

        clientRect: wx.Rect = self.GetClientRect()
        pinRect = wx.Rect(clientRect.x + clientRect.width - 20, 2, 20, 20)
        self.DrawPin(dc, pinRect, not self._bCollapsed)

        if self._bCollapsed:
            return

    def _draw_buttons(self, dc: wx.DC, style: ImageBookStyle) -> None:
        size: wx.Size = self.GetSize()
        bUsePin: ImageBookStyle = style & ImageBookStyle.INB_USE_PIN_BUTTON
        bUseYcoord: ImageBookStyle = style & (
            ImageBookStyle.INB_RIGHT | ImageBookStyle.INB_LEFT
        )
        clientSize: int = size.height if bUseYcoord else size.width
        pinBtnSize: int = 20 if bUsePin else 0

        normalFont: wx.Font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        boldFont: wx.Font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        boldFont.SetWeight(wx.FONTWEIGHT_BOLD)

        padding = 4
        textPaddingLeft = 2
        imgTopPadding = 10

        pos: int = 0 if style & ImageBookStyle.INB_BORDER else 1
        if bUsePin and (style & (ImageBookStyle.INB_TOP | ImageBookStyle.INB_BOTTOM)):
            pos += 20

        for i, pageInfo in enumerate(self._pagesInfoVec):
            if (
                pos + self._get_button_width(dc, pageInfo, style, pinBtnSize)
                > clientSize
            ):
                break

            buttonRect: wx.Rect = self._get_button_rect(pos, size, style)
            self._draw_button(
                dc,
                i,
                buttonRect,
                style,
                normalFont,
                boldFont,
                padding,
                textPaddingLeft,
                imgTopPadding,
            )

            pos += self._get_button_width(dc, pageInfo, style, pinBtnSize)

        self._update_non_visible_buttons(pos)

    def _get_button_width(
        self, dc: wx.DC, pageInfo: ImageInfo, style: ImageBookStyle, pinBtnSize: int
    ) -> int:
        rectWidth: int = self._nImgSize * 2
        if (
            style & ImageBookStyle.INB_FIT_BUTTON
            and not (style & (ImageBookStyle.INB_LEFT | ImageBookStyle.INB_RIGHT))
            and pageInfo.GetCaption()
            and not (style & ImageBookStyle.INB_SHOW_ONLY_IMAGES)
        ):
            textWidth, _ = dc.GetTextExtent(pageInfo.GetCaption())
            rectWidth = max(rectWidth, textWidth + self.padding * 2)
            if rectWidth % 2 != 0:
                rectWidth += 1

        return rectWidth + pinBtnSize

    def _get_button_rect(
        self, pos: int, size: wx.Size, style: ImageBookStyle
    ) -> wx.Rect:
        rectWidth: int = self._nImgSize * 2
        rectHeight: int = self._nImgSize * 2

        if style & (ImageBookStyle.INB_RIGHT | ImageBookStyle.INB_LEFT):
            rectWidth -= 2
        else:
            rectHeight -= 2

        if style & (ImageBookStyle.INB_RIGHT | ImageBookStyle.INB_LEFT):
            return wx.Rect(1, pos, rectWidth, rectHeight)
        else:
            return wx.Rect(pos, 1, rectWidth, rectHeight)

    def _draw_button(
        self,
        dc: wx.DC,
        index: int,
        buttonRect: wx.Rect,
        style: ImageBookStyle,
        normalFont: wx.Font,
        boldFont: wx.Font,
        padding: int,
        textPaddingLeft: int,
        imgTopPadding: int,
    ) -> None:
        if self._nIndex == index:
            self._draw_selected_button(dc, buttonRect, style)

        if self._nHoveredImgIdx == index:
            self._draw_hovered_button(dc, buttonRect, style)

        self._draw_button_content(
            dc,
            index,
            buttonRect,
            style,
            normalFont,
            boldFont,
            padding,
            textPaddingLeft,
            imgTopPadding,
        )

    def _draw_selected_button(
        self, dc: wx.DC, buttonRect: wx.Rect, style: ImageBookStyle
    ) -> None:
        penColour: wx.Colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION)
        brushColour: wx.Colour = ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION), 75
        )

        dc.SetPen(wx.Pen(penColour))
        dc.SetBrush(wx.Brush(brushColour))

        if style & ImageBookStyle.INB_BORDER:
            buttonRect = self._adjust_button_rect(buttonRect, style)

        dc.DrawRectangle(buttonRect)

    def _draw_hovered_button(
        self, dc: wx.DC, buttonRect: wx.Rect, style: ImageBookStyle
    ) -> None:
        penColour: wx.Colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION)
        brushColour: wx.Colour = ArtManager.Get().LightColour(
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_ACTIVECAPTION), 90
        )

        dc.SetPen(wx.Pen(penColour))
        dc.SetBrush(wx.Brush(brushColour))

        if style & ImageBookStyle.INB_BORDER:
            buttonRect = self._adjust_button_rect(buttonRect, style)

        dc.DrawRectangle(buttonRect)

    def _adjust_button_rect(
        self, buttonRect: wx.Rect, style: ImageBookStyle
    ) -> wx.Rect:
        if style & (ImageBookStyle.INB_TOP | ImageBookStyle.INB_BOTTOM):
            return wx.Rect(
                buttonRect.x + 1, buttonRect.y, buttonRect.width - 1, buttonRect.height
            )
        else:
            return wx.Rect(
                buttonRect.x, buttonRect.y + 1, buttonRect.width, buttonRect.height - 1
            )

    def _draw_button_content(
        self,
        dc: wx.DC,
        index: int,
        buttonRect: wx.Rect,
        style: ImageBookStyle,
        normalFont: wx.Font,
        boldFont: wx.Font,
        padding: int,
        textPaddingLeft: int,
        imgTopPadding: int,
    ) -> None:
        pageInfo: ImageInfo = self._pagesInfoVec[index]
        dc.SetFont(
            normalFont
            if not (
                style & ImageBookStyle.INB_BOLD_TAB_SELECTION and self._nIndex == index
            )
            else boldFont
        )

        if not (
            style & ImageBookStyle.INB_SHOW_ONLY_TEXT
            and style & ImageBookStyle.INB_SHOW_ONLY_IMAGES
        ):
            if (
                style & ImageBookStyle.INB_SHOW_ONLY_TEXT
                and style & ImageBookStyle.INB_SHOW_ONLY_IMAGES
            ):
                style ^= ImageBookStyle.INB_SHOW_ONLY_TEXT
                style ^= ImageBookStyle.INB_SHOW_ONLY_IMAGES
                self.GetParent().SetAGWWindowStyleFlag(style)

            if (
                not style & ImageBookStyle.INB_SHOW_ONLY_TEXT
                and pageInfo.GetImageIndex() != -1
                and self._ImageList is not None
            ):
                imgXcoord, imgYcoord = self._get_image_coords(
                    buttonRect, style, padding, imgTopPadding
                )
                self._ImageList.Draw(
                    pageInfo.GetImageIndex(),
                    dc,
                    imgXcoord,
                    imgYcoord,
                    wx.IMAGELIST_DRAW_TRANSPARENT,
                    True,
                )

            if (
                not style & ImageBookStyle.INB_SHOW_ONLY_IMAGES
                and pageInfo.GetCaption()
            ):
                fixedText: str | None = self._get_fixed_text(
                    dc, pageInfo.GetCaption(), style, padding
                )
                textOffsetX, textOffsetY = self._get_text_coords(
                    dc,
                    buttonRect,
                    style,
                    padding,
                    textPaddingLeft,
                    imgTopPadding,
                    index,
                )
                dc.SetTextForeground(
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
                )
                dc.DrawText(fixedText, textOffsetX, textOffsetY)

        pageInfo.SetPosition(buttonRect.GetPosition())
        pageInfo.SetSize(buttonRect.GetSize())

    def _get_image_coords(
        self,
        buttonRect: wx.Rect,
        style: ImageBookStyle,
        padding: int,
        imgTopPadding: int,
    ) -> tuple[int, int]:
        if style & (ImageBookStyle.INB_RIGHT | ImageBookStyle.INB_LEFT):
            imgXcoord: int = self._nImgSize // 2
            imgYcoord: int = buttonRect.y + (
                self._nImgSize // 2
                if style & ImageBookStyle.INB_SHOW_ONLY_IMAGES
                else imgTopPadding
            )
        else:
            imgXcoord = buttonRect.x + (buttonRect.width // 2) - (self._nImgSize // 2)
            imgYcoord = (
                self._nImgSize // 2
                if style & ImageBookStyle.INB_SHOW_ONLY_IMAGES
                else imgTopPadding
            )

        return imgXcoord, imgYcoord

    def _get_fixed_text(
        self, dc: wx.DC, caption: str, style: ImageBookStyle, padding: int
    ) -> str | None:
        if not (
            style & ImageBookStyle.INB_FIT_BUTTON
            or style & (ImageBookStyle.INB_LEFT | ImageBookStyle.INB_RIGHT)
        ):
            return self.FixTextSize(dc, caption, self._nImgSize * 2 - 4)

        return caption

    def _get_text_coords(
        self,
        dc: wx.DC,
        buttonRect: wx.Rect,
        style: ImageBookStyle,
        padding: int,
        textPaddingLeft: int,
        imgTopPadding: int,
        index: int,
    ) -> tuple[int, int]:
        textWidth, textHeight = dc.GetTextExtent(
            self._get_fixed_text(
                dc, self._pagesInfoVec[index].GetCaption(), style, padding
            )
        )

        if style & (ImageBookStyle.INB_RIGHT | ImageBookStyle.INB_LEFT):
            textOffsetX: int = (buttonRect.width - textWidth) // 2
            textOffsetY: int = buttonRect.y + (
                imgTopPadding + 3
                if not style & ImageBookStyle.INB_SHOW_ONLY_TEXT
                else (self._nImgSize * 2 - textHeight) // 2
            )
        else:
            textOffsetX = (
                (buttonRect.width - textWidth) // 2 + buttonRect.x + textPaddingLeft
            )
            textOffsetY = (
                imgTopPadding + 3
                if not style & ImageBookStyle.INB_SHOW_ONLY_TEXT
                else (self._nImgSize * 2 - textHeight) // 2
            )

        return textOffsetX, textOffsetY

    def _update_non_visible_buttons(self, pos: int) -> None:
        for ii in range(pos // (self._nImgSize * 2), len(self._pagesInfoVec)):
            self._pagesInfoVec[ii].SetPosition(wx.Point(-1, -1))


# ------------------------------------------------------------------------------------ #
# Class LabelContainer
# ------------------------------------------------------------------------------------ #


class LabelContainer(ImageContainerBase):
    """Base class for :class:`LabelBook`."""

    nPadding = 6

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "LabelContainer",
    ) -> None:
        """Construct the default class.

        Args:
            parent (wx.Window): parent window. Must not be ``None``;
            id (int): window identifier. A value of -1 indicates a default value;
            pos (wx.Point): the control position.
                A value of (-1, -1) indicates a default position, chosen by either the
                windowing system or wxPython, depending on platform;
            size (wx.Size): the control size.
                A value of (-1, -1) indicates a default size, chosen by either the
                windowing system or wxPython, depending on platform;
            style (int): the underlying :class:`Panel` window style;
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
            name (str): the window name.
        """
        ImageContainerBase.__init__(self, parent, id, pos, size, style, agwStyle, name)
        self._nTabAreaWidth = 100
        self._oldCursor: wx.Cursor = wx.NullCursor
        self._coloursMap: dict[int, wx.Colour] = {}
        self._skin: wx.Bitmap = wx.NullBitmap
        self._sashRect = wx.Rect()

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMove)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeaveWindow)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        self._ImageList: None | wx.ImageList = None
        self._initialize_image_list()

    def _initialize_image_list(self) -> None:
        # Initialize the image list with default values or from a source
        self._ImageList = wx.ImageList(16, 16)  # Example initialization

    def OnSize(self, event: wx.SizeEvent) -> None:
        """Handle the ``wx.EVT_SIZE`` event for :class:`LabelContainer`.

        Args:
            event (wx.SizeEvent): a :class:`wx.SizeEvent` event to be processed.
        """
        ImageContainerBase.OnSize(self, event)
        event.Skip()

    def OnEraseBackground(self, event: wx.EraseEvent) -> None:
        """Handle the ``wx.EVT_ERASE_BACKGROUND`` event for :class:`LabelContainer`.

        Args:
            event (wx.EraseEvent): a :class:`EraseEvent` event to be processed.
        """
        ImageContainerBase.OnEraseBackground(self, event)

    def GetTabAreaWidth(self) -> int:
        """Return the width of the tab area."""
        return self._nTabAreaWidth

    def SetTabAreaWidth(self, width: int) -> None:
        """Set the width of the tab area.

        Args:
            width (int): the width of the tab area, in pixels.
        """
        self._nTabAreaWidth: int = width
        self.SetSizeHints(width, -1)

    def CanDoBottomStyle(self) -> bool:
        """Allow the parent to examine the children type.

        Some implementation (such as :class:`LabelBook`),
        does not support top/bottom images, only left/right.
        """
        return False

    def SetBackgroundBitmap(self, bmp: wx.Bitmap) -> None:
        """Set the background bitmap for the control.

        Args:
            bmp (wx.Bitmap): a valid :class:`wx.Bitmap` object.
        """
        self._skin = bmp

    def OnPaint(self, event: wx.PaintEvent) -> None:
        """Handle the ``wx.EVT_PAINT`` event for :class:`LabelContainer`.

        Args:
            event (wx.PaintEvent): a :class:`PaintEvent` event to be processed.
        """
        style: int = self.GetParent().GetAGWWindowStyleFlag()

        # In case user set both flags, we override them to display both
        # INB_SHOW_ONLY_TEXT and INB_SHOW_ONLY_IMAGES
        if (
            style & ImageBookStyle.INB_SHOW_ONLY_TEXT
            and style & ImageBookStyle.INB_SHOW_ONLY_IMAGES
        ):
            style ^= ImageBookStyle.INB_SHOW_ONLY_TEXT
            style ^= ImageBookStyle.INB_SHOW_ONLY_IMAGES
            self.GetParent().SetAGWWindowStyleFlag(style)

        dc = wx.BufferedPaintDC(self)
        self._draw_background(dc)
        self._draw_tabs(dc)
        self._draw_pin_button(dc)

    def _draw_background(self, dc: wx.DC) -> None:
        """Draw the background of the control.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
        """
        size: wx.Size = self.GetSize()
        backBrush = wx.Brush(self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR])
        borderPen: wx.Pen = (
            wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR])
            if self.HasAGWFlag(ImageBookStyle.INB_BORDER)
            else wx.TRANSPARENT_PEN
        )

        dc.SetBrush(backBrush)
        dc.SetPen(borderPen)
        dc.DrawRectangle(wx.Rect(0, 0, size.x, size.y))

        if (
            self.HasAGWFlag(ImageBookStyle.INB_GRADIENT_BACKGROUND)
            and not self._skin.IsOk()
        ):
            self._draw_gradient_background(dc, size)

    def _draw_gradient_background(self, dc: wx.DC, size: wx.Size) -> None:
        """Draw a gradient background.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            size (wx.Size): the size of the control.
        """
        startColour: wx.Colour = self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR]
        endColour: wx.Colour = ArtManager.Get().LightColour(startColour, 50)

        ArtManager.Get().PaintStraightGradientBox(
            dc, wx.Rect(0, 0, size.x // 2, size.y), startColour, endColour, False
        )
        ArtManager.Get().PaintStraightGradientBox(
            dc,
            wx.Rect(size.x // 2, 0, size.x // 2, size.y),
            endColour,
            startColour,
            False,
        )

    def _draw_tabs(self, dc: wx.DC) -> None:
        """Draw the tabs.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
        """
        size: wx.Size = self.GetSize()
        posy = 20
        count = 0

        for i in range(len(self._pagesInfoVec)):
            count += 1
            rectWidth: int = self._nTabAreaWidth
            rectHeight: int = self._calculate_tab_height(i)

            if posy + rectHeight > size.GetHeight():
                break

            buttonRect = wx.Rect(0, posy, rectWidth, rectHeight)
            self._draw_tab(
                dc,
                buttonRect,
                i,
                selected=self._nIndex == i,
                hover=self._nHoveredImgIdx == i,
            )
            posy += rectHeight

        self._update_non_visible_tabs(count)

    def _calculate_tab_height(self, index: int) -> int:
        """Calculate the height of a tab.

        Args:
            index (int): the index of the tab.

        Returns:
            int: the height of the tab.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_SHOW_ONLY_TEXT):
            font: wx.Font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
            font.SetPointSize(
                int(font.GetPointSize() * self.GetParent().GetFontSizeMultiple())
            )
            if self.GetParent().GetFontBold():
                font.SetWeight(wx.FONTWEIGHT_BOLD)
            elif (
                self.HasAGWFlag(ImageBookStyle.INB_BOLD_TAB_SELECTION)
                and self._nIndex == index
            ):
                font.SetWeight(wx.FONTWEIGHT_BOLD)

            dc = wx.ClientDC(self)
            dc.SetFont(font)
            w, h = dc.GetTextExtent(self._pagesInfoVec[index].GetCaption())
            return h * 2
        else:
            return self._nImgSize * 2

    def _draw_tab(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        index: int,
        selected: bool,
        hover: bool,
    ) -> None:
        """Draw a single tab.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the tab client rectangle.
            index (int): the index of the tab.
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise.
            hover (bool): ``True`` if the tab is being hovered with the mouse,
                ``False`` otherwise.
        """
        orientationLeft: bool = self.HasAGWFlag(
            ImageBookStyle.INB_LEFT
        ) or self.HasAGWFlag(ImageBookStyle.INB_TOP)
        text: str = self._pagesInfoVec[index].GetCaption()
        bmp: wx.Bitmap = self._get_tab_bitmap(index)
        textRect: wx.Rect = self._calculate_text_rect(dc, rect, text, bmp)
        imgRect: wx.Rect = self._calculate_image_rect(dc, rect, bmp)
        imgInfo: ImageInfo = self._pagesInfoVec[
            index
        ]  # Assuming ImageInfo is a part of _pagesInfoVec

        self._draw_tab_background(dc, rect, selected, orientationLeft)
        self._draw_tab_text(dc, textRect, text, selected, imgInfo)
        self._draw_tab_image(dc, imgRect, bmp)
        self._draw_tab_shadow(dc, rect, selected, index, hover)
        self._draw_tab_hover_effect(dc, rect, textRect, text, selected, hover, imgInfo)

        self._pagesInfoVec[index].SetPosition(rect.GetPosition())
        self._pagesInfoVec[index].SetSize(rect.GetSize())

    def _get_tab_bitmap(self, index: int) -> wx.Bitmap:
        """Get the bitmap for a tab.

        Args:
            index (int): the index of the tab.

        Returns:
            wx.Bitmap: the bitmap for the tab.
        """
        if self._ImageList is None or self._pagesInfoVec[index].GetImageIndex() == -1:
            return wx.NullBitmap
        return self._ImageList.GetBitmap(self._pagesInfoVec[index].GetImageIndex())

    def _update_non_visible_tabs(self, count: int) -> None:
        """Update the visibility of tabs that do not fit on the screen.

        Args:
            count (int): the number of tabs that fit on the screen.
        """
        for ii in range(count, len(self._pagesInfoVec)):
            self._pagesInfoVec[ii].SetPosition(wx.Point(-1, -1))

    def _draw_pin_button(self, dc: wx.DC) -> None:
        """Draw the pin button if it is enabled and the control is not collapsed.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_USE_PIN_BUTTON) and not self._bCollapsed:
            clientRect: wx.Rect = self.GetClientRect()
            pinRect = wx.Rect(clientRect.GetX() + clientRect.GetWidth() - 20, 2, 20, 20)
            self.DrawPin(dc, pinRect, not self._bCollapsed)

    def DrawBackgroundBitmap(self, dc: wx.DC) -> None:
        """Draw a bitmap as the background of the control.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
        """
        clientRect: wx.Rect = self.GetClientRect()
        width: int = clientRect.GetWidth()
        height: int = clientRect.GetHeight()
        xstep: int = self._skin.GetWidth()
        ystep: int = self._skin.GetHeight()
        bmpRect = wx.Rect(0, 0, xstep, ystep)

        if bmpRect != clientRect:
            self._draw_tiled_background(dc, width, height, xstep, ystep)
        else:
            dc.DrawBitmap(self._skin, 0, 0)

    def _draw_tiled_background(
        self, dc: wx.DC, width: int, height: int, xstep: int, ystep: int
    ) -> None:
        """Draw a tiled background.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            width (int): the width of the control.
            height (int): the height of the control.
            xstep (int): the width of the background bitmap.
            ystep (int): the height of the background bitmap.
        """
        mem_dc = wx.MemoryDC()
        bmp = wx.Bitmap(width, height)
        mem_dc.SelectObject(bmp)

        coveredY = 0
        coveredX = 0

        while coveredY < height:
            while coveredX < width:
                mem_dc.DrawBitmap(self._skin, coveredX, coveredY, True)
                coveredX += xstep
            coveredX = 0
            coveredY += ystep

        mem_dc.SelectObject(wx.NullBitmap)
        dc.DrawBitmap(bmp, 0, 0)

    def OnMouseLeftUp(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_UP`` event for :class:`LabelContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_NO_RESIZE):
            ImageContainerBase.OnMouseLeftUp(self, event)
            return

        if self.HasCapture():
            self.ReleaseMouse()

        if not self._sashRect.IsEmpty():
            self._handle_sash_release(event)
            return

        self._sashRect = wx.Rect()

        if self._oldCursor.IsOk():
            self.SetCursor(self._oldCursor)
            self._oldCursor = wx.NullCursor

        ImageContainerBase.OnMouseLeftUp(self, event)

    def _handle_sash_release(self, event: wx.MouseEvent) -> None:
        """Handle the release of the sash.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        ArtManager.Get().DrawDragSash(self._sashRect)
        size_event = wx.SizeEvent(self.GetSize())
        self.Resize(size_event)
        self._sashRect = wx.Rect()

    def Resize(self, event: wx.SizeEvent) -> None:
        """Actually resize the tab area.

        Args:
            event (wx.SizeEvent): an instance of :class:`wx.SizeEvent`.
        """
        self._tabAreaSize = self.GetSize()
        newWidth: int = self._tabAreaSize.width
        eventSize: wx.Size = event.GetSize()

        if self.HasAGWFlag(ImageBookStyle.INB_BOTTOM) or self.HasAGWFlag(
            ImageBookStyle.INB_RIGHT
        ):
            newWidth -= eventSize.width
        else:
            newWidth = eventSize.width

        if newWidth < 100:  # Don't allow width to be lower than that
            newWidth = 100

        self.SetSizeHints(newWidth, self._tabAreaSize.height)
        self.GetParent().Freeze()
        self.GetParent().GetSizer().Layout()
        self.GetParent().Thaw()

    def OnMouseMove(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_MOTION`` event for :class:`LabelContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_NO_RESIZE):
            ImageContainerBase.OnMouseMove(self, event)
            return

        if not self._sashRect.IsEmpty():
            self._handle_sash_drag(event)
        elif event.LeftIsDown():
            self._handle_sash_start(event)
        else:
            self._handle_cursor_change(event)

    def _handle_sash_drag(self, event: wx.MouseEvent) -> None:
        """Handle the dragging of the sash.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        ArtManager.Get().DrawDragSash(self._sashRect)
        clientRect: wx.Rect = self.GetClientRect()
        pt: wx.Point = self.ClientToScreen(wx.Point(event.GetX(), 0))
        self._sashRect = wx.Rect(pt, wx.Size(4, clientRect.height))
        ArtManager.Get().DrawDragSash(self._sashRect)

    def _handle_sash_start(self, event: wx.MouseEvent) -> None:
        """Handle the start of sash dragging.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        imgIdx, where = self.HitTest(event.GetPosition())
        if IMG_OVER_EW_BORDER == where and not self._bCollapsed:
            if not self._sashRect.IsEmpty():
                ArtManager.Get().DrawDragSash(self._sashRect)
            else:
                self.CaptureMouse()
                self._oldCursor = self.GetCursor()
                self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE))
                clientRect: wx.Rect = self.GetClientRect()
                pt: wx.Point = self.ClientToScreen(wx.Point(event.GetX(), 0))
                self._sashRect = wx.Rect(pt, wx.Size(4, clientRect.height))
                ArtManager.Get().DrawDragSash(self._sashRect)

    def _handle_cursor_change(self, event: wx.MouseEvent) -> None:
        """Handle the change of cursor when not dragging the sash.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if self.PointOnSash(event.GetPosition()):
            self._oldCursor = self.GetCursor()
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE))
        elif self._oldCursor.IsOk():
            self.SetCursor(self._oldCursor)
            self._oldCursor = wx.NullCursor

        self._sashRect = wx.Rect()
        ImageContainerBase.OnMouseMove(self, event)

    def OnMouseLeftDown(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_DOWN`` event for :class:`LabelContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_NO_RESIZE):
            ImageContainerBase.OnMouseLeftDown(self, event)
            return

        imgIdx, where = self.HitTest(event.GetPosition())

        if IMG_OVER_EW_BORDER == where and not self._bCollapsed:
            if not self._sashRect.IsEmpty():
                ArtManager.Get().DrawDragSash(self._sashRect)
            else:
                self.CaptureMouse()
                self._oldCursor = self.GetCursor()
                self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE))
                clientRect: wx.Rect = self.GetClientRect()
                pt: wx.Point = self.ClientToScreen(wx.Point(event.GetX(), 0))
                self._sashRect = wx.Rect(pt, wx.Size(4, clientRect.height))
                ArtManager.Get().DrawDragSash(self._sashRect)
        else:
            ImageContainerBase.OnMouseLeftDown(self, event)

    def OnMouseLeaveWindow(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEAVE_WINDOW`` event for :class:`LabelContainer`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_NO_RESIZE):
            ImageContainerBase.OnMouseLeaveWindow(self, event)
            return

        if not self.HasCapture():
            ImageContainerBase.OnMouseLeaveWindow(self, event)

    def DrawRegularHover(self, dc: wx.DC, rect: wx.Rect, imgInfo: ImageInfo) -> None:
        """Draw a rounded rectangle around the current tab.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`;
            rect (wx.Rect): the current tab client rectangle.
            imgInfo (ImageInfo): an instance of :class:`ImageInfo`.
        """
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen(wx.WHITE))

        if self.HasAGWFlag(ImageBookStyle.INB_RIGHT) or self.HasAGWFlag(
            ImageBookStyle.INB_TOP
        ):
            dc.DrawLine(rect.x + 1, rect.y, rect.x + rect.width, rect.y)
            dc.DrawLine(
                rect.x + rect.width, rect.y, rect.x + rect.width, rect.y + rect.height
            )
            dc.SetPen(wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR]))
            dc.DrawLine(
                rect.x + rect.width, rect.y + rect.height, rect.x, rect.y + rect.height
            )
        else:
            dc.DrawLine(rect.x, rect.y, rect.x + rect.width - 1, rect.y)
            dc.DrawLine(rect.x, rect.y, rect.x, rect.y + rect.height)
            dc.SetPen(wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR]))
            dc.DrawLine(
                rect.x, rect.y + rect.height, rect.x + rect.width, rect.y + rect.height
            )

    def DrawWebHover(
        self,
        dc: wx.DC,
        caption: str | None,
        xCoord: int,
        yCoord: int,
        selected: bool,
        imgInfo: ImageInfo,
    ) -> None:
        """Draw a web style hover effect (set cursor to hand & underline text).

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`;
            caption (str): the tab caption text;
            xCoord (int): the x position of the tab caption;
            yCoord (int): the y position of the tab caption;
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise.
            imgInfo (ImageInfo): an instance of :class:`ImageInfo`.
        """
        underLinedFont: wx.Font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        underLinedFont.SetPointSize(
            int(underLinedFont.GetPointSize() * self.GetParent().GetFontSizeMultiple())
        )
        if self.GetParent().GetFontBold():
            underLinedFont.SetWeight(wx.FONTWEIGHT_BOLD)
        elif self.HasAGWFlag(ImageBookStyle.INB_BOLD_TAB_SELECTION) and selected:
            underLinedFont.SetWeight(wx.FONTWEIGHT_BOLD)

        underLinedFont.SetUnderlined(True)
        dc.SetFont(underLinedFont)
        dc.DrawText(caption, xCoord, yCoord)

    def SetColour(self, which: int, colour: wx.Colour) -> None:
        """Set a colour for a parameter.

        Args:
            which (int): can be one of the following parameters:
                ================================== ======= =============================
                Colour Key                          Value  Description
                ================================== ======= =============================
                ``INB_TAB_AREA_BACKGROUND_COLOUR``     100 The tab area background
                                                            colour
                ``INB_ACTIVE_TAB_COLOUR``              101 The active tab background
                                                            colour
                ``INB_TABS_BORDER_COLOUR``             102 The tabs border colour
                ``INB_TEXT_COLOUR``                    103 The tab caption text colour
                ``INB_ACTIVE_TEXT_COLOUR``             104 The active tab caption text
                                                            colour
                ``INB_HILITE_TAB_COLOUR``              105 The tab caption highlight
                                                            text colour
                ================================== ======= =============================
            colour (wx.Colour): a valid :class:`wx.Colour` object.
        """
        self._coloursMap[which] = colour

    def GetColour(self, which: int) -> wx.Colour:
        """Return a colour for a parameter.

        Args:
            which (int): the colour key.

        See:
            :meth:`~LabelContainer.SetColour` for a list of valid colour keys.
        """
        return self._coloursMap.get(which, wx.Colour())

    def InitializeColours(self) -> None:
        """Initialize the colours map to be used for this control."""
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
                INB_TABS_BORDER_COLOUR: wx.SystemSettings.GetColour(
                    wx.SYS_COLOUR_3DSHADOW
                )
            }
        )
        self._coloursMap.update({INB_HILITE_TAB_COLOUR: wx.Colour("LIGHT BLUE")})
        self._coloursMap.update({INB_TEXT_COLOUR: wx.WHITE})
        self._coloursMap.update({INB_ACTIVE_TEXT_COLOUR: wx.BLACK})

        if not ArtManager.Get().IsDark(
            self._coloursMap[INB_TAB_AREA_BACKGROUND_COLOUR]
        ) and not ArtManager.Get().IsDark(self._coloursMap[INB_TEXT_COLOUR]):
            self._coloursMap[INB_TEXT_COLOUR] = ArtManager.Get().DarkColour(
                self._coloursMap[INB_TEXT_COLOUR], 100
            )

    def DrawLabel(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        text: str,
        bmp: wx.Bitmap,
        imgInfo: ImageInfo,
        orientationLeft: bool,
        imgIdx: int,
        selected: bool,
        hover: bool,
    ) -> None:
        """Draw a label using the specified dc.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`;
            rect (wx.Rect): the text client rectangle;
            text (str): the actual text string;
            bmp (wx.Bitmap): a bitmap to be drawn next to the text;
            imgInfo (ImageInfo): an instance of :class:`ImageInfo`;
            orientationLeft (bool): ``True`` if the book has the ``INB_RIGHT`` or
                ``INB_LEFT`` style set;
            imgIdx (int): the tab image index;
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise;
            hover (bool): ``True`` if the tab is being hovered with the mouse,
                ``False`` otherwise.
        """
        dcsaver = DCSaver(dc)
        nPadding = 6

        if orientationLeft:
            rect.x += nPadding
            rect.width -= nPadding
        else:
            rect.width -= nPadding

        textRect: wx.Rect = self._calculate_text_rect(dc, rect, text, bmp)
        imgRect: wx.Rect = self._calculate_image_rect(dc, rect, bmp)

        self._draw_tab_background(dc, rect, selected, orientationLeft)
        self._draw_tab_text(dc, textRect, text, selected, imgInfo)
        self._draw_tab_image(dc, imgRect, bmp)
        self._draw_tab_shadow(dc, rect, selected, imgIdx, hover)
        self._draw_tab_hover_effect(dc, rect, textRect, text, selected, hover, imgInfo)

        imgInfo.SetPosition(rect.GetPosition())
        imgInfo.SetSize(rect.GetSize())

        del dcsaver

    def _calculate_text_rect(
        self, dc: wx.DC, rect: wx.Rect, text: str, bmp: wx.Bitmap
    ) -> wx.Rect:
        """Calculate the text bounding rectangle.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the tab client rectangle.
            text (str): the tab caption text.
            bmp (wx.Bitmap): the tab bitmap.

        Returns:
            wx.Rect: the text bounding rectangle.
        """
        nPadding = 6

        font: wx.Font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetPointSize(
            int(font.GetPointSize() * self.GetParent().GetFontSizeMultiple())
        )
        if self.GetParent().GetFontBold():
            font.SetWeight(wx.FONTWEIGHT_BOLD)
        elif (
            self.HasAGWFlag(ImageBookStyle.INB_BOLD_TAB_SELECTION)
            and self._nIndex == self._nHoveredImgIdx
        ):
            font.SetWeight(wx.FONTWEIGHT_BOLD)

        dc.SetFont(font)
        w, h = dc.GetTextExtent(text)
        textRect = wx.Rect(
            rect.x + nPadding,
            rect.y + (rect.height - h) // 2,
            rect.width - 2 * nPadding,
            h,
        )

        if bmp.IsOk() and not self.HasAGWFlag(ImageBookStyle.INB_SHOW_ONLY_TEXT):
            textRect.x += bmp.GetWidth() + nPadding
            textRect.width -= bmp.GetWidth() + nPadding

        # Truncate text if needed
        caption: str | None = ArtManager.Get().TruncateText(dc, text, textRect.width)
        if caption is not None:
            textRect.width = dc.GetTextExtent(caption)[0]

        return textRect

    def _calculate_image_rect(
        self, dc: wx.DC, rect: wx.Rect, bmp: wx.Bitmap
    ) -> wx.Rect:
        """Calculate the image bounding rectangle.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the tab client rectangle.
            bmp (wx.Bitmap): the tab bitmap.

        Returns:
            wx.Rect: the image bounding rectangle.
        """
        if bmp.IsOk() and not self.HasAGWFlag(ImageBookStyle.INB_SHOW_ONLY_TEXT):
            imgRect = wx.Rect(
                rect.x + self.nPadding,
                rect.y + (rect.height - bmp.GetHeight()) // 2,
                bmp.GetWidth(),
                bmp.GetHeight(),
            )
            return imgRect
        return wx.Rect()

    def _draw_tab_background(
        self, dc: wx.DC, rect: wx.Rect, selected: bool, orientationLeft: bool
    ) -> None:
        """Draw the tab background.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the tab client rectangle.
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise.
            orientationLeft (bool): ``True`` if the book has the ``INB_RIGHT`` or
                ``INB_LEFT`` style set.
        """
        if selected:
            dc.SetBrush(wx.Brush(self._coloursMap[INB_ACTIVE_TAB_COLOUR]))
            dc.SetPen(
                wx.Pen(self._coloursMap[INB_TABS_BORDER_COLOUR])
                if self.HasAGWFlag(ImageBookStyle.INB_BORDER)
                else wx.Pen(self._coloursMap[INB_ACTIVE_TAB_COLOUR])
            )
            labelRect = wx.Rect(*rect)

            if orientationLeft:
                labelRect.width += 3
            else:
                labelRect.width += 3
                labelRect.x -= 3

            dc.DrawRoundedRectangle(labelRect, 3)

            if not orientationLeft and self.HasAGWFlag(ImageBookStyle.INB_DRAW_SHADOW):
                dc.SetPen(wx.BLACK_PEN)
                dc.DrawPoint(
                    labelRect.x + labelRect.width - 1,
                    labelRect.y + labelRect.height - 1,
                )

    def _draw_tab_text(
        self,
        dc: wx.DC,
        textRect: wx.Rect,
        text: str,
        selected: bool,
        imgInfo: ImageInfo,
    ) -> None:
        """Draw the tab text.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            textRect (wx.Rect): the text bounding rectangle.
            text (str): the tab caption text.
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise.
            imgInfo (ImageInfo): an instance of :class:`ImageInfo`.
        """
        if text:
            dc.SetTextForeground(
                self._coloursMap[INB_ACTIVE_TEXT_COLOUR]
                if selected
                else self._coloursMap[INB_TEXT_COLOUR]
            )
            dc.DrawText(text, textRect.x, textRect.y)
            imgInfo.SetTextRect(textRect)

    def _draw_tab_image(self, dc: wx.DC, imgRect: wx.Rect, bmp: wx.Bitmap) -> None:
        """Draw the tab image.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            imgRect (wx.Rect): the image bounding rectangle.
            bmp (wx.Bitmap): the tab bitmap.
        """
        if bmp.IsOk() and not self.HasAGWFlag(ImageBookStyle.INB_SHOW_ONLY_TEXT):
            dc.DrawBitmap(bmp, imgRect.x, imgRect.y, True)

    def _draw_tab_shadow(
        self, dc: wx.DC, rect: wx.Rect, selected: bool, imgIdx: int, hover: bool
    ) -> None:
        """Draw the tab shadow.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the tab client rectangle.
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise.
            imgIdx (int): the tab image index.
            hover (bool): ``True`` if the tab is being hovered with the mouse,
                ``False`` otherwise.
        """
        if self.HasAGWFlag(ImageBookStyle.INB_DRAW_SHADOW) and selected:
            sstyle: int = (
                BottomShadow
                if self.HasAGWFlag(ImageBookStyle.INB_LEFT)
                else BottomShadowFull | RightShadow
            )
            if (
                self.HasAGWFlag(ImageBookStyle.INB_WEB_HILITE)
                or imgIdx + 1 != self._nHoveredImgIdx
            ):
                ArtManager.Get().DrawBitmapShadow(dc, rect, sstyle)

    def _draw_tab_hover_effect(
        self,
        dc: wx.DC,
        rect: wx.Rect,
        textRect: wx.Rect,
        text: str,
        selected: bool,
        hover: bool,
        imgInfo: ImageInfo,
    ) -> None:
        """Draw the tab hover effect.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.
            rect (wx.Rect): the tab client rectangle.
            textRect (wx.Rect): the text bounding rectangle.
            text (str): the tab caption text.
            selected (bool): ``True`` if the tab is selected, ``False`` otherwise.
            hover (bool): ``True`` if the tab is being hovered with the mouse,
                ``False`` otherwise.
            imgInfo (ImageInfo): an instance of :class:`ImageInfo`.
        """
        if hover:
            if self.HasAGWFlag(ImageBookStyle.INB_WEB_HILITE) and text:
                self.DrawWebHover(dc, text, textRect.x, textRect.y, selected, imgInfo)
            else:
                self.DrawRegularHover(dc, rect, imgInfo)


# ------------------------------------------------------------------------------------ #
# Class PageImageDescriptor
# ------------------------------------------------------------------------------------ #


class PageImageDescriptor:
    def __get__(self, instance: "FlatBookBase", owner: type) -> int:
        return instance.GetPageImage(instance.GetSelection())

    def __set__(self, instance: "FlatBookBase", value: int) -> None:
        instance.SetPageImage(instance.GetSelection(), value)


# ------------------------------------------------------------------------------------ #
# Class FlatBookBase
# ------------------------------------------------------------------------------------ #


class FlatBookBase(wx.Panel):
    """Base class for :class:`LabelBook` and :class:`FlatImageBook` containers."""

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "FlatBookBase",
    ) -> None:
        """Construct the default class.

        Args:
            parent (wx.Window): parent window. Must not be ``None``;
            id (int): window identifier. A value of -1 indicates a default value;
            pos (wx.Point): the control position.
                A value of (-1, -1) indicates a default position, chosen by either the
                windowing system or wxPython, depending on platform;
            size (wx.Size): the control size.
                A value of (-1, -1) indicates a default size, chosen by either the
                windowing system or wxPython, depending on platform;
            style (int): the underlying :class:`Panel` window style;
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
            name (str): the window name.
        """
        self._pages = None
        self._bInitializing = True
        self._bForceSelection = False
        self._windows: list[wx.Window] = []
        self._fontSizeMultiple = 1.0
        self._fontBold = False

        style |= wx.TAB_TRAVERSAL
        self._agwStyle: int = agwStyle

        wx.Panel.__init__(self, parent, id, pos, size, style, name)
        self._bInitializing = False

        self.Bind(wx.EVT_NAVIGATION_KEY, self.OnNavigationKey)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda evt: True)

        # Ensure _pages is initialized
        if isinstance(self, FlatImageBook):
            self._pages = self.CreateImageContainer()
        elif isinstance(self, LabelBook):
            self._pages = self.CreateImageContainer()

        if self._pages is None:
            raise ValueError("ImageContainer is not initialized")

        # Add the tab container to the sizer
        self._mainSizer = wx.BoxSizer(
            wx.HORIZONTAL
            if self.HasAGWFlag(ImageBookStyle.INB_LEFT)
            or self.HasAGWFlag(ImageBookStyle.INB_RIGHT)
            else wx.VERTICAL
        )
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)
        self.SetSizer(self._mainSizer)
        self._mainSizer.Layout()

    def CreateImageContainer(self) -> ImageContainerBase:
        """Create the image container class for :class:`FlatBookBase`."""
        return ImageContainer(self, wx.ID_ANY, agwStyle=self.GetAGWWindowStyleFlag())

    def SetAGWWindowStyleFlag(self, agwStyle: int) -> None:
        """Set the window style.

        Args:
            agwStyle (int): can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
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

        if isinstance(self, LabelBook):
            self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            if (
                agwStyle & ImageBookStyle.INB_LEFT
                or agwStyle & ImageBookStyle.INB_RIGHT
            ):
                self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
            else:
                self._mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.SetSizer(self._mainSizer)

        # Add the tab container and the separator
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)

        if isinstance(self, FlatImageBook):
            if (
                agwStyle & ImageBookStyle.INB_LEFT
                or agwStyle & ImageBookStyle.INB_RIGHT
            ):
                self._pages.SetSizeHints(self._pages._nImgSize * 2, -1)
            else:
                self._pages.SetSizeHints(-1, self._pages._nImgSize * 2)

        # Attach the windows back to the sizer to the sizer
        if self.GetSelection() >= 0:
            self.DoSetSelection(self._windows[self.GetSelection()])

        if agwStyle & ImageBookStyle.INB_FIT_LABELTEXT:
            self.ResizeTabArea()

        self._mainSizer.Layout()
        dummy = wx.SizeEvent(self.GetSize())
        wx.PostEvent(self, dummy)
        self._pages.Refresh()

    def GetAGWWindowStyleFlag(self) -> int:
        """Return the :class:`FlatBookBase` window style.

        See:
            :meth:`~FlatBookBase.SetAGWWindowStyleFlag` for a list of possible window
                style flags.
        """
        return self._agwStyle

    def HasAGWFlag(self, flag: int) -> bool:
        """Return whether a flag is present in the :class:`FlatBookBase` style.

        Args:
            flag (int): one of the possible :class:`FlatBookBase` window styles.

        See:
            :meth:`~FlatBookBase.SetAGWWindowStyleFlag` for a list of possible window
                style flags.
        """
        agwStyle: int = self.GetAGWWindowStyleFlag()
        res: bool = (agwStyle & flag and [True] or [False])[0]
        return res

    def AddPage(
        self, page: wx.Window, text: str, select: bool = False, imageId: int = -1
    ) -> None:
        """Add a page to the book.

        Args:
            page (wx.Window): specifies the new page;
            text (str): specifies the text for the new page;
            select (bool): specifies whether the page should be selected;
            imageId (int): specifies the optional image index for the new page.

        Note:
            The call to this function generates the page changing events.
        """
        if not page:
            return

        if self._pages is None:
            raise ValueError("ImageContainer is not initialized")

        page.Reparent(self)

        self._windows.append(page)

        if select or len(self._windows) == 1:
            self.SetSelection(len(self._windows) - 1)
        else:
            page.Hide()

        self._pages.AddPage(text, select, imageId)
        self.ResizeTabArea()
        self.Refresh()

    def InsertPage(
        self,
        page_idx: int,
        page: wx.Window,
        text: str,
        select: bool = False,
        imageId: int = -1,
    ) -> None:
        """Insert a page into the book at the specified position.

        Args:
            page_idx (int): specifies the position for the new page;
            page (wx.Window): specifies the new page;
            text (str): specifies the text for the new page;
            select (bool): specifies whether the page should be selected;
            imageId (int): specifies the optional image index for the new page.

        Note:
            The call to this function generates the page changing events.
        """
        if not page:
            return

        if self._pages is None:
            raise ValueError("LabelContainer is not initialized")

        page.Reparent(self)

        self._windows.insert(page_idx, page)

        if select or len(self._windows) == 1:
            self.SetSelection(page_idx)
        else:
            page.Hide()

        self._pages.InsertPage(page_idx, text, select, imageId)
        self.ResizeTabArea()
        self.Refresh()

    def DeletePage(self, page: int) -> None | bool:
        """Delete the specified page, and the associated window.

        Args:
            page (int): an integer specifying the page to be deleted.

        Note:
            The call to this function generates the page changing events.
        """
        if page >= len(self._windows) or page < 0:
            return

        # Fire a closing event
        event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSING, self.GetId())
        event.SetSelection(page)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

        # The event handler allows it?
        if not event.IsAllowed():
            return False

        self.Freeze()

        # Delete the requested page
        pageRemoved: wx.Window = self._windows[page]

        # If the page is the current window, remove it from the sizer as well
        if page == self.GetSelection():
            self._mainSizer.Detach(pageRemoved)

        # Remove it from the array as well
        self._windows.pop(page)

        # Now we can destroy it in wxWidgets use Destroy instead of delete
        pageRemoved.Destroy()
        self._mainSizer.Layout()

        if self._pages:
            self._pages.DoDeletePage(page)
            self.ResizeTabArea()

        self.Thaw()

        # Fire a closed event
        closedEvent = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSED, self.GetId())
        closedEvent.SetSelection(page)
        closedEvent.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(closedEvent)

    def RemovePage(self, page: int) -> bool:
        """Delete the specified page, without deleting the associated window.

        Args:
            page (int): an integer specifying the page to be removed.

        Note:
            The call to this function generates the page changing events.
        """
        if page >= len(self._windows):
            return False

        # Fire a closing event
        event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSING, self.GetId())
        event.SetSelection(page)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

        # The event handler allows it?
        if not event.IsAllowed():
            return False

        self.Freeze()

        # Remove the requested page
        pageRemoved: wx.Window = self._windows[page]

        # If the page is the current window, remove it from the sizer as well
        if page == self.GetSelection():
            self._mainSizer.Detach(pageRemoved)

        # Remove it from the array as well
        self._windows.pop(page)
        self._mainSizer.Layout()
        self.ResizeTabArea()
        self.Thaw()

        if self._pages is not None:
            self._pages.DoDeletePage(page)

        # Fire a closed event
        closedEvent = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CLOSED, self.GetId())
        closedEvent.SetSelection(page)
        closedEvent.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(closedEvent)

        return True

    def ResizeTabArea(self) -> None:
        """Resize the tab area if ``INB_FIT_LABELTEXT`` style is set."""
        if self._pages is None:
            return

        agwStyle: int = self.GetAGWWindowStyleFlag()

        if agwStyle & ImageBookStyle.INB_FIT_LABELTEXT == 0:
            return

        if isinstance(self._pages, LabelContainer):
            self._pages.SetTabAreaWidth(self._calculate_max_tab_width())
            self._pages.Refresh()

    def _calculate_max_tab_width(self) -> int:
        """Calculate the maximum width needed for the tab area."""
        if self._pages is None:
            return 100

        dc = wx.MemoryDC()
        dc.SelectObject(wx.Bitmap(1, 1))
        font: wx.Font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetPointSize(int(font.GetPointSize() * self._fontSizeMultiple))
        if self.GetFontBold() or self.HasAGWFlag(ImageBookStyle.INB_BOLD_TAB_SELECTION):
            font.SetWeight(wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        maxW = 0

        for page in range(self.GetPageCount()):
            caption: str = self._pages.GetPageText(page)
            w, h = dc.GetTextExtent(caption)
            maxW: int = max(maxW, w)

        maxW += 24  # TODO this is 6*4 6 is nPadding from drawlabel

        if not self.HasAGWFlag(ImageBookStyle.INB_SHOW_ONLY_TEXT):
            maxW += self._pages._nImgSize * 2

        maxW = max(maxW, 100)
        return maxW

    def DeleteAllPages(self) -> None:
        """Delete all the pages in the book."""
        if not self._windows:
            return

        self.Freeze()

        for win in self._windows:
            win.Destroy()

        self._windows = []
        self.Thaw()

        if self._pages:
            self._pages.ClearAll()
            self._pages.Refresh()

    def SetSelection(self, page: int) -> None:
        """Change selection to the page given by page.

        Args:
            page (int): an integer specifying the page to be selected.

        Note:
            The call to this function generates the page changing events.
        """
        if self._pages is None:
            raise ValueError("Pages container is not initialized")

        if page >= len(self._windows):
            return

        if not self.GetEnabled(page):
            return

        if page == self.GetSelection() and not self._bForceSelection:
            return

        oldSelection: int = self.GetSelection()

        # Generate an event that indicates that an image is about to be selected
        event = ImageNotebookEvent(wxEVT_IMAGENOTEBOOK_PAGE_CHANGING, self.GetId())
        event.SetSelection(page)
        event.SetOldSelection(oldSelection)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

        # The event handler allows it?
        if not event.IsAllowed() and not self._bForceSelection:
            return

        self.DoSetSelection(self._windows[page])
        # Now we can update the new selection
        self._pages._nIndex = page

        # Refresh calls the OnPaint of this class
        self._pages.Refresh()

        # Generate an event that indicates that an image was selected
        eventChanged = ImageNotebookEvent(
            wxEVT_IMAGENOTEBOOK_PAGE_CHANGED, self.GetId()
        )
        eventChanged.SetEventObject(self)
        eventChanged.SetOldSelection(oldSelection)
        eventChanged.SetSelection(page)
        self.GetEventHandler().ProcessEvent(eventChanged)

    def AssignImageList(self, imglist: wx.ImageList) -> None:
        """Assign an image list to the control.

        Args:
            imglist (wx.ImageList): an instance of :class:`wx.ImageList`.
        """
        if self._pages is None:
            raise ValueError("ImageContainer is not initialized")

        self._pages.AssignImageList(imglist)

        # Force change
        self.SetAGWWindowStyleFlag(self.GetAGWWindowStyleFlag())

    def GetSelection(self) -> int:
        """Return the current selection."""
        if self._pages:
            return self._pages._nIndex
        else:
            return -1

    def DoSetSelection(self, window: wx.Window) -> None:
        """Select the window by the provided pointer.

        Args:
            window (wx.Window): an instance of :class:`wx.Window`.
        """
        curSel: int = self.GetSelection()
        agwStyle: int = self.GetAGWWindowStyleFlag()
        # Replace the window in the sizer
        self.Freeze()

        # Check if a new selection was made
        bInsertFirst: int = (
            agwStyle & ImageBookStyle.INB_BOTTOM or agwStyle & ImageBookStyle.INB_RIGHT
        )

        if curSel >= 0:

            # Remove the window from the main sizer
            self._mainSizer.Detach(self._windows[curSel])
            self._windows[curSel].Hide()

        if bInsertFirst:
            self._mainSizer.Insert(0, window, 1, wx.EXPAND)
        else:
            self._mainSizer.Add(window, 1, wx.EXPAND)

        window.Show()
        self._mainSizer.Layout()
        self.Thaw()

    def GetImageList(self) -> None | wx.ImageList:
        """Return the associated image list."""
        if self._pages is None:
            return None
        return self._pages.GetImageList()

    def GetPageCount(self) -> int:
        """Return the number of pages in the book."""
        return len(self._windows)

    def GetFontBold(self) -> bool:
        """Get the font bold status."""
        return self._fontBold

    def SetFontBold(self, bold: bool) -> None:
        """Set whether the page captions are bold or not.

        Args:
            bold (bool): ``True`` or ``False``.
        """
        self._fontBold: bool = bold

    def GetFontSizeMultiple(self) -> float:
        """Get the font size multiple for the page captions."""
        return self._fontSizeMultiple

    def SetFontSizeMultiple(self, multiple: float) -> None:
        """Set the font size multiple for the page captions.

        Args:
            multiple (float): The multiple to be applied to the system font to get the
                our font size.
        """
        self._fontSizeMultiple: float = multiple

    def SetPageImage(self, page: int, imageId: int) -> None:
        """Set the image index for the given page.

        Args:
            page (int): an integer specifying the page index;
            image_id (int): an index into the image list.
        """
        if self._pages is None:
            raise ValueError("ImageContainer is not initialized")

        self._pages.SetPageImage(page, imageId)
        self._pages.Refresh()

    def SetPageText(self, page: int, text: str) -> None:
        """Set the text for the given page.

        Args:
            page (int): an integer specifying the page index;
            text (str): the new tab label.
        """
        if self._pages is None:
            raise ValueError("Pages container is not initialized")
        self._pages.SetPageText(page, text)
        self._pages.Refresh()

    def GetPageText(self, page: int) -> str:
        """Return the text for the given page.

        Args:
            page (int): an integer specifying the page index.
        """
        if self._pages is None:
            raise ValueError("Pages container is not initialized")
        return self._pages.GetPageText(page)

    def GetPageImage(self, page: int) -> int:
        """Return the image index for the given page.

        Args:
            page (int): an integer specifying the page index.
        """
        if self._pages is None:
            raise ValueError("ImageContainer is not initialized")
        return self._pages.GetPageImage(page)

    def GetEnabled(self, page: int) -> bool:
        """Return whether a tab is enabled or not.

        Args:
            page (int): an integer specifying the page index.
        """
        if self._pages is None:
            raise ValueError("Pages container is not initialized")
        return self._pages.GetEnabled(page)

    def EnableTab(self, page: int, enabled: bool = True) -> None:
        """Enable or disable a tab.

        Args:
            page (int): an integer specifying the page index;
            enabled (bool): ``True`` to enable a tab, ``False`` to disable it.
        """
        if page >= len(self._windows):
            return

        if self._pages is None:
            raise ValueError("Pages container is not initialized")

        self._windows[page].Enable(enabled)
        self._pages.EnableTab(page, enabled)

    def GetPage(self, page: int) -> None | wx.Window:
        """Return the window at the given page position.

        Args:
            page (int): an integer specifying the page to be returned.
        """
        if page >= len(self._windows):
            return

        return self._windows[page]

    def GetCurrentPage(self) -> None | wx.Window:
        """Return the currently selected notebook page or ``None``."""
        selection: int = self.GetSelection()
        if selection < 0:
            return None
        return self.GetPage(selection)

    def OnNavigationKey(self, event: wx.NavigationKeyEvent) -> None:
        """Handle the ``wx.EVT_NAVIGATION_KEY`` event for :class:`FlatBookBase`.

        Args:
            event (wx.NavigationKeyEvent): a :class:`NavigationKeyEvent` event to be
                processed.
        """
        if event.IsWindowChange():
            if self.GetPageCount() == 0:
                return

            # change pages
            self.AdvanceSelection(event.GetDirection())

        else:
            event.Skip()

    def AdvanceSelection(self, forward: bool = True) -> None:
        """Cycle through the tabs.

        Args:
            forward (bool): if ``True``, the selection is advanced in ascending order
                (to the right), otherwise the selection is advanced in descending order.

        Note:
            The call to this function generates the page changing events.
        """
        nSel: int = self.GetSelection()

        if nSel < 0:
            return

        nMax: int = self.GetPageCount() - 1

        if forward:
            newSelection: int = (nSel == nMax and [0] or [nSel + 1])[0]
        else:
            newSelection = (nSel == 0 and [nMax] or [nSel - 1])[0]

        self.SetSelection(newSelection)

    def ChangeSelection(self, page: int) -> None | int:
        """Change the selection for the given page, returning the previous selection.

        Args:
            page (int): an integer specifying the page to be selected.

        Note:
            The call to this function does not generate the page changing events.
        """
        if page < 0 or page >= self.GetPageCount():
            return

        oldPage: int = self.GetSelection()
        if page >= 0 and page < len(self._windows):
            self.DoSetSelection(self._windows[page])  # Pass the window object

        return oldPage

    def _get_page_text(self) -> str:
        page: int = self.GetSelection()
        if page >= 0:
            return self.GetPageText(page)
        return ""

    def _set_page_text(self, text: str) -> None:
        page: int = self.GetSelection()
        if page >= 0:
            self.SetPageText(page, text)

    CurrentPage = property(GetCurrentPage, doc="See `GetCurrentPage`")
    Page = property(GetCurrentPage, doc="See `GetCurrentPage`")
    PageCount = property(GetPageCount, doc="See `GetPageCount`")
    PageImage = PageImageDescriptor()
    PageText = property(
        _get_page_text, _set_page_text, doc="See `GetPageText, SetPageText`"
    )
    Selection = property(
        GetSelection, SetSelection, doc="See `GetSelection, SetSelection`"
    )


# ---------------------------------------------------------------------------- #
# Class FlatImageBook
# ---------------------------------------------------------------------------- #


class FlatImageBook(FlatBookBase):
    """Default implementation of the image book.

    It is like a :class:`Notebook`,
    except that images are used to control the different pages.

    This container is usually used for configuration dialogs etc.

    Note:
        Currently, this control works properly for images of size 32x32 and bigger.
    """

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "FlatImageBook",
    ) -> None:
        """Construct the default class.

        Args:
            parent (wx.Window): parent window. Must not be ``None``;
            id (int): window identifier. A value of -1 indicates a default value;
            pos (wx.Point): the control position.
                A value of (-1, -1) indicates a default position, chosen by either the
                windowing system or wxPython, depending on platform;
            size (wx.Size): the control size.
                A value of (-1, -1) indicates a default size, chosen by either the
                windowing system or wxPython, depending on platform;
            style (int): the underlying :class:`Panel` window style;
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
            name (str): the window name.
        """
        FlatBookBase.__init__(self, parent, id, pos, size, style, agwStyle, name)

        self._pages: ImageContainer = self.CreateImageContainer()

        if self._pages is None:
            raise ValueError("Failed to create ImageContainer")

        if agwStyle & ImageBookStyle.INB_LEFT or agwStyle & ImageBookStyle.INB_RIGHT:
            self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        else:
            self._mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.SetSizer(self._mainSizer)

        # Add the tab container to the sizer
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)

        if agwStyle & ImageBookStyle.INB_LEFT or agwStyle & ImageBookStyle.INB_RIGHT:
            self._pages.SetSizeHints(self._pages.GetImageSize() * 2, -1)
        else:
            self._pages.SetSizeHints(-1, self._pages.GetImageSize() * 2)

        self._mainSizer.Layout()

    def CreateImageContainer(self) -> ImageContainer:
        """Create the image container class for :class:`FlatImageBook`."""
        return ImageContainer(self, wx.ID_ANY, agwStyle=self.GetAGWWindowStyleFlag())


# ---------------------------------------------------------------------------- #
# Class LabelBook
# ---------------------------------------------------------------------------- #


class LabelBook(FlatBookBase):
    """An implementation of a notebook control.

    Except that instead of having tabs to show labels,
    it labels to the right or left (arranged horizontally).
    """

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "LabelBook",
    ) -> None:
        """Construct the default class.

        Args:
            parent (wx.Window): parent window. Must not be ``None``;
            id (int): window identifier. A value of -1 indicates a default value;
            pos (wx.Point): the control position.
                A value of (-1, -1) indicates a default position, chosen by either the
                windowing system or wxPython, depending on platform;
            size (wx.Size): the control size.
                A value of (-1, -1) indicates a default size, chosen by either the
                windowing system or wxPython, depending on platform;
            style (int): the underlying :class:`Panel` window style;
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                =========================== =========== ================================
                Window Styles               Hex Value   Description
                =========================== =========== ================================
                ``INB_BOTTOM``                      0x1 Place labels below the page
                                                        area. Available only for
                                                        :class:`FlatImageBook`.
                ``INB_LEFT``                        0x2 Place labels on the left side.
                                                        Available only for
                                                        :class:`FlatImageBook`.
                ``INB_RIGHT``                       0x4 Place labels on the right side.
                ``INB_TOP``                         0x8 Place labels above the page
                                                        area.
                ``INB_BORDER``                     0x10 Draws a border around
                                                        :class:`LabelBook` or
                                                        :class:`FlatImageBook`.
                ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no
                                                        images. Available only for
                                                        :class:`LabelBook`.
                ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no
                                                        label texts. Available only for
                                                        :class:`LabelBook`.
                ``INB_FIT_BUTTON``                 0x80 Displays a pin button to
                                                        show/hide the book control.
                ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book
                                                        tabs. Available only for
                                                        :class:`LabelBook`.
                ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to
                                                        show/hide the book control.
                ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the
                                                        tabs background. Available only
                                                        for :class:`LabelBook`.
                ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave
                                                        like html hyperlinks. Available
                                                        only for :class:`LabelBook`.
                ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab
                                                        area.
                ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the
                                                        longest text (or text+image if
                                                        you have images) in all the
                                                        tabs.
                ``INB_BOLD_TAB_SELECTION``       0x4000 Show the selected tab text using
                                                        a bold font.
                =========================== =========== ================================
            name (str): the window name.
        """
        FlatBookBase.__init__(self, parent, id, pos, size, style, agwStyle, name)

        self._pages: LabelContainer = self.CreateImageContainer()
        print(f"self._pages initialized: {self._pages}")

        if self._pages is None:
            raise ValueError("Failed to create LabelContainer")

        # Label book specific initialization
        self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(self._mainSizer)

        # Add the tab container to the sizer
        self._mainSizer.Add(self._pages, 0, wx.EXPAND)
        self._pages.SetSizeHints(self._pages.GetTabAreaWidth(), -1)

        # Initialize the colours maps
        self._pages.InitializeColours()

        self.Bind(wx.EVT_SIZE, self.OnSize)

    def CreateImageContainer(self) -> LabelContainer:
        """Create the image container (LabelContainer) class for :class:`LabelBook`."""
        return LabelContainer(self, wx.ID_ANY, agwStyle=self.GetAGWWindowStyleFlag())

    def SetColour(self, which: int, colour: wx.Colour) -> None:
        """Set the colour for the specified parameter.

        Args:
            which (int): the colour key;
            colour (wx.Colour): a valid :class:`wx.Colour` instance.

        See:
            :meth:`LabelContainer.SetColour() <LabelContainer.SetColour>` for a list of
                valid colour keys.
        """
        self._pages.SetColour(which, colour)

    def GetColour(self, which: int) -> wx.Colour:
        """Return the colour for the specified parameter.

        Args:
            which (int): the colour key.

        See:
            :meth:`LabelContainer.SetColour() <LabelContainer.SetColour>` for a list of
                valid colour keys.
        """
        return self._pages.GetColour(which)

    def OnSize(self, event: wx.SizeEvent) -> None:
        """Handle the ``wx.EVT_SIZE`` event for :class:`LabelBook`.

        Args:
            event (wx.SizeEvent): a :class:`wx.SizeEvent` event to be processed.
        """
        self._pages.Refresh()
        event.Skip()
