# ------------------------------------------------------------------------------------ #
# FOURWAYSPLITTER wxPython IMPLEMENTATION
#
# Andrea Gavana, @ 03 Nov 2006
# Latest Revision: 16 Jul 2012, 15.00 GMT
#
#
# TODO List
#
# 1. Any idea?
#
# For All Kind Of Problems, Requests Of Enhancements And Bug Reports,
# Please Write To Me At:
#
# andrea.gavana@maerskoil.com
# andrea.gavana@gmail.com
#
# Or, Obviously, To The wxPython Mailing List!!!
#
# Tags:        phoenix-port, unittest, documented, py3-port
#
# End Of Comments
# ------------------------------------------------------------------------------------ #

"""FourWaySplitter is a layout manager that arranges 4 child panes in a window.

Description
===========

The :class:`FourWaySplitter` is a layout manager which manages four children like four
panes in a window. You can use a four-way splitter for example in a CAD program where
you may want to maintain three orthographic views, and one oblique view of a model.

The :class:`FourWaySplitter` allows interactive repartitioning of the panes by means of
moving the central splitter bars. When the :class:`FourWaySplitter` is itself resized,
each child is proportionally resized, maintaining the same split-percentage.

The main characteristics of :class:`FourWaySplitter` are:

- Handles horizontal, vertical or four way sizing via the sashes;
- Delayed or live update when resizing;
- Possibility to swap windows;
- Setting the vertical and horizontal split fractions;
- Possibility to expand a window by hiding the other 3.

And a lot more. See the demo for a complete review of the functionalities.


Usage
=====

Usage example::

    import wx
    import wx.lib.agw.fourwaysplitter as fws

    class MyFrame(wx.Frame):

        def __init__(self, parent: wx.Window | None) -> None:

            wx.Frame.__init__(self, parent, -1, "FourWaySplitter Demo")

            splitter = fws.FourWaySplitter(self, -1, agwStyle=wx.SP_LIVE_UPDATE)

            # Put in some coloured panels...
            for colour in [wx.RED, wx.WHITE, wx.BLUE, wx.GREEN]:

                panel = wx.Panel(splitter)
                panel.SetBackgroundColour(colour)

                splitter.AppendWindow(panel)


    # our normal wxApp-derived class, as usual

    app = wx.App(0)

    frame = MyFrame(None)
    app.SetTopWindow(frame)
    frame.Show()

    app.MainLoop()



Supported Platforms
===================

:class:`FourWaySplitter` has been tested on the following platforms:
  * Windows (Windows XP);
  * Linux Ubuntu (Dapper 6.06)


Window Styles
=============

This class supports the following window styles:

================== =========== =========================================================
Window Styles      Hex Value   Description
================== =========== =========================================================
``SP_NOSASH``             0x10 No sash will be drawn on :class:`FourWaySplitter`.
``SP_LIVE_UPDATE``        0x80 Don't draw XOR line but resize the child windows
                                immediately.
``SP_3DBORDER``          0x200 Draws a 3D effect border.
================== =========== =========================================================


Events Processing
=================

This class processes the following events:

================================== =====================================================
Event Name                         Description
================================== =====================================================
``EVT_SPLITTER_SASH_POS_CHANGED``  The sash position was changed.
                                    This event is generated after the user releases the
                                    mouse after dragging the splitter. Processes a
                                    ``wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGED``
                                    event.
``EVT_SPLITTER_SASH_POS_CHANGING`` The sash position is in the process of being changed.
                                    You may prevent this change from happening by
                                    calling `Veto` or you may also modify the position
                                    of the tracking bar to properly reflect the position
                                    that would be set if the drag were to be completed
                                    at this point. Processes a
                                    ``wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGING``
                                    event.
================================== =====================================================


License And Version
===================

:class:`FourWaySplitter` is distributed under the wxPython license.

Latest Revision: Andrea Gavana @ 16 Jul 2012, 15.00 GMT

Version 0.5
"""
from typing import Union

import wx

_RENDER_VER: tuple[int, int, int, int] = (2, 6, 1, 1)

# Tolerance for mouse shape and sizing
_TOLERANCE = 5

# Modes
NOWHERE = 0
"""No sashes are changing position."""
FLAG_CHANGED = 1
"""Sashes are changing position."""
FLAG_PRESSED = 2
"""Sashes are in a pressed state."""

# FourWaySplitter styles
SP_NOSASH: int = wx.SP_NOSASH
"""No sash will be drawn on :class:`FourWaySplitter`."""
SP_LIVE_UPDATE: int = wx.SP_LIVE_UPDATE
"""Don't draw XOR line but resize the child windows immediately."""
SP_3DBORDER: int = wx.SP_3DBORDER
"""Draws a 3D effect border."""

# FourWaySplitter events
EVT_SPLITTER_SASH_POS_CHANGING: wx.PyEventBinder = wx.EVT_SPLITTER_SASH_POS_CHANGING
"""The sash position is in the process of being changed.

You may prevent this change from happening by calling `Veto` or you may also modify the
position of the tracking bar to properly reflect the position that would be set if the
drag were to be completed at this point.
Processes a ``wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGING`` event.
"""
EVT_SPLITTER_SASH_POS_CHANGED: wx.PyEventBinder = wx.EVT_SPLITTER_SASH_POS_CHANGED
"""The sash position was changed.

This event is generated after the user releases the mouse after dragging the splitter.
Processes a ``wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGED`` event.
"""

# ------------------------------------------------------------------------------------ #
# Class FourWaySplitterEvent
# ------------------------------------------------------------------------------------ #


class FourWaySplitterEvent(wx.CommandEvent):
    """This event class adds a sash index accessor to :class:`SplitterEvent`.

    The same event type IDs and event binders are used as with :class:`SplitterEvent`.

    Args:
        evtType (int): the event type;
        splitter (Union[None, FourWaySplitter]): The associated :class:`FourWaySplitter`
            window.
    """

    def __init__(
        self,
        evtType: int = wx.wxEVT_NULL,
        splitter: Union[None, "FourWaySplitter"] = None,
    ) -> None:
        wx.CommandEvent.__init__(self, evtType)

        if splitter:
            self.SetEventObject(splitter)
            self.SetId(splitter.GetId())

        self.sashIdx: int = -1
        self.sashPos: int | wx.Point = -1
        self.isAllowed: bool = True

    def SetSashIdx(self, idx: int) -> None:
        """Set the index of the sash currently involved in the event.

        Args:
            idx (int): an integer between 0 and 3,
                representing the index of the sash involved in the event.
        """
        self.sashIdx: int = idx

    def SetSashPosition(self, pos: int | wx.Point) -> None:
        """
        For EVT_SPLITTER_SASH_POS_CHANGED events, set the new sash position.

        In the case of ``EVT_SPLITTER_SASH_POS_CHANGING`` events,
        sets the new tracking bar position so visual feedback during dragging will
        represent that change that will actually take place.
        Set to -1 from the event handler code to prevent repositioning.

        Args:
            pos (int | wx.Point): the new sash position.

        Note:
            May only be called while processing ``EVT_SPLITTER_SASH_POS_CHANGING`` and
                ``EVT_SPLITTER_SASH_POS_CHANGED`` events.
        """
        self.sashPos: int | wx.Point = pos

    def GetSashIdx(self) -> int:
        """Return the index of the sash currently involved in the event.

        Returns:
            int: the index of the sash currently involved in the event.
        """
        return self.sashIdx

    def GetSashPosition(self) -> int | wx.Point:
        """Return the new sash position.

        Returns:
            int | wx.Point: the new sash position.

        Note:
            May only be called while processing ``EVT_SPLITTER_SASH_POS_CHANGING`` and
                ``EVT_SPLITTER_SASH_POS_CHANGED`` events.
        """
        return self.sashPos

    # methods from wx.NotifyEvent
    def Veto(self) -> None:
        """Prevent the change announced by this event from happening.

        Note:
            It is in general a good idea to notify the user about the reasons for
                vetoing the change because otherwise the applications behaviour (which
                just refuses to do what the user wants) might be quite surprising.
        """
        self.isAllowed: bool = False

    def Allow(self) -> None:
        """Do the opposite of :meth:`~FourWaySplitterEvent.Veto`.

        It explicitly allows the event to be processed.
        For most events it is not necessary to call this method as the events are
        allowed anyhow but some are forbidden by default
        (this will be mentioned in the corresponding event description).
        """
        self.isAllowed: bool = True

    def IsAllowed(self) -> bool:
        """Return ``True`` if change is allowed, ``False`` if vetoed.

        Returns:
            bool: ``True`` if change is allowed, ``False`` if vetoed.
        """
        return self.isAllowed


# ---------------------------------------------------------------------------- #
# Class FourWaySplitter
# ---------------------------------------------------------------------------- #


class FourWaySplitter(wx.Panel):
    """Similar to :class:`SplitterWindow`, but with four windows and two sashes.

    Many of the same styles, constants,
    and methods behave the same as in :class:`SplitterWindow`.
    However, in addition to the ability to drag the vertical and the horizontal sash,
    by dragging at the intersection between the two sashes,
    it is possible to resize the four windows at the same time.

    Note:
        These things are not yet supported:
            * Minimum pane size (minimum of what? Width? Height?);
            * Using negative sash positions to indicate a position offset from the end;
            * User controlled unsplitting with double clicks on the sash
                (but supported via the :meth:`FourWaySplitter.SetExpanded()
                <FourWaySplitter.SetExpanded>` method);
            * Sash gravity.
    """

    def __init__(
        self,
        parent: wx.Window,
        id: int = wx.ID_ANY,
        pos: wx.Point = wx.DefaultPosition,
        size: wx.Size = wx.DefaultSize,
        style: int = 0,
        agwStyle: int = 0,
        name: str = "FourWaySplitter",
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
                It can be a combination of the following bits:
                ================== =========== =========================================
                Window Styles      Hex Value   Description
                ================== =========== =========================================
                ``SP_NOSASH``             0x10 No sash will be drawn on
                                                :class:`FourWaySplitter`.
                ``SP_LIVE_UPDATE``        0x80 Don't draw XOR line but resize the child
                                                windows immediately.
                ``SP_3DBORDER``          0x200 Draws a 3D effect border.
                ================== =========== =========================================
            name (str): the window name.
        """
        # always turn on tab traversal
        style |= wx.TAB_TRAVERSAL

        # and turn off any border styles
        style &= ~wx.BORDER_MASK
        style |= wx.BORDER_NONE

        self._agwStyle: int = agwStyle

        # initialize the base class
        wx.Panel.__init__(self, parent, id, pos, size, style, name)
        self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

        self._windows: list[wx.Window] = []

        self._splitx: int = 0
        self._splity: int = 0
        self._expanded: int = -1
        self._fhor: int = 5000
        self._fver: int = 5000
        self._offx: int = 0
        self._offy: int = 0
        self._mode: int = NOWHERE
        self._flags: int = 0
        self._isHot: bool = False

        self._sashTrackerPen = wx.Pen(wx.BLACK, 2, wx.PENSTYLE_SOLID)

        self._sashCursorWE = wx.Cursor(wx.CURSOR_SIZEWE)
        self._sashCursorNS = wx.Cursor(wx.CURSOR_SIZENS)
        self._sashCursorSIZING = wx.Cursor(wx.CURSOR_SIZING)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)

    def _IsVersionGreaterOrEqual(self, version: tuple[int, int, int, int]) -> bool:
        """Compare the current wxPython version with the given version.

        Args:
            version (tuple[int, int, int, int]): a tuple of version numbers.

        Returns:
            bool: ``True`` if the current wxPython version is greater or equal to the
                given version.
        """
        wx_version: tuple[int, int, int] = wx.VERSION[:3]
        return (
            wx_version[0] > version[0]
            or (wx_version[0] == version[0] and wx_version[1] > version[1])
            or (
                wx_version[0] == version[0]
                and wx_version[1] == version[1]
                and wx_version[2] >= version[2]
            )
        )

    def SetAGWWindowStyleFlag(self, agwStyle: int) -> None:
        """Set the :class:`FourWaySplitter` window style flags.

        Args:
            agwStyle (int): the AGW-specific window style.
                This can be a combination of the following bits:
                ================== =========== =========================================
                Window Styles      Hex Value   Description
                ================== =========== =========================================
                ``SP_NOSASH``             0x10 No sash will be drawn on
                                                :class:`FourWaySplitter`.
                ``SP_LIVE_UPDATE``        0x80 Don't draw XOR line but resize the child
                                                windows immediately.
                ``SP_3DBORDER``          0x200 Draws a 3D effect border.
                ================== =========== =========================================
        """
        self._agwStyle = agwStyle
        self.Refresh()

    def GetAGWWindowStyleFlag(self) -> int:
        """Return the :class:`FourWaySplitter` window style.

        See:
            :meth:`~FourWaySplitter.SetAGWWindowStyleFlag` for a list of possible window
                styles.

        Returns:
            int: The AGW-specific window style.
        """
        return self._agwStyle

    def AppendWindow(self, window: wx.Window) -> None:
        """Add a new window to the splitter at the right or bottom.

        Args:
            window (wx.Window): an instance of :class:`wx.Window`.
        """
        self.InsertWindow(len(self._windows), window)

    def InsertWindow(self, idx: int, window: wx.Window) -> None:
        """Insert a new window into the splitter at the position given in `idx`.

        Args:
            idx (int): the index at which the window will be inserted;
            window (wx.Window): an instance of :class:`wx.Window`.
        """
        assert window not in self._windows, "A window can only be in the splitter once!"

        self._windows.insert(idx, window)

        self._SizeWindows()

    def DetachWindow(self, window: wx.Window) -> None:
        """Remove the window from the stack of windows managed by the splitter.

        The window will still exist so you should `Hide` or `Destroy` it as needed.

        Args:
            window (wx.Window): an instance of :class:`wx.Window`.
        """
        assert window in self._windows, "Unknown window!"

        idx: int = self._windows.index(window)
        del self._windows[idx]

        self._SizeWindows()

    def ReplaceWindow(self, oldWindow: wx.Window, newWindow: wx.Window) -> None:
        """Replace `oldWindow` with `newWindow` in the splitter.

        The `oldWindow` window will still exist so you should `Hide` or `Destroy` it as
        needed.

        Args:
            oldWindow (wx.Window): an instance of :class:`wx.Window`;
            newWindow (wx.Window): another instance of :class:`wx.Window`.
        """
        assert oldWindow in self._windows, "Unknown window!"

        idx: int = self._windows.index(oldWindow)
        self._windows[idx] = newWindow

        self._SizeWindows()

    def ExchangeWindows(self, window1: wx.Window, window2: wx.Window) -> None:
        """Trade the positions in the splitter of the two windows.

        Args:
            window1 (wx.Window): an instance of :class:`wx.Window`;
            window2 (wx.Window): another instance of :class:`wx.Window`.
        """
        assert window1 in self._windows, "Unknown window!"
        assert window2 in self._windows, "Unknown window!"

        idx1: int = self._windows.index(window1)
        idx2: int = self._windows.index(window2)
        self._windows[idx1] = window2
        self._windows[idx2] = window1

        if "__WXMSW__" in wx.Platform:
            self.Freeze()

        self._SizeWindows()

        if "__WXMSW__" in wx.Platform:
            self.Thaw()

    def GetWindow(self, idx: int) -> wx.Window | None:
        """Return the window at the index `idx`.

        Args:
            idx (int): the index at which the window is located.

        Returns:
            wx.Window | None: The window at the specified index or ``None`` if the index
                is out of range.
        """
        if len(self._windows) > idx:
            return self._windows[idx]

        return None

    # Get top left child
    def GetTopLeft(self) -> wx.Window | None:
        """Return the top left window (window index: 0).

        Returns:
            wx.Window | None: The top left window or ``None`` if the index is out of
                range.
        """
        return self.GetWindow(0)

    # Get top right child
    def GetTopRight(self) -> wx.Window | None:
        """Return the top right window (window index: 1).

        Returns:
            wx.Window | None: The top right window or ``None`` if the index is out of
                range.
        """
        return self.GetWindow(1)

    # Get bottom left child
    def GetBottomLeft(self) -> wx.Window | None:
        """Return the bottom left window (window index: 2).

        Returns:
            wx.Window | None: The bottom left window or ``None`` if the index is out of
                range.
        """
        return self.GetWindow(2)

    # Get bottom right child
    def GetBottomRight(self) -> wx.Window | None:
        """Return the bottom right window (window index: 3).

        Returns:
            wx.Window | None: The bottom right window or ``None`` if the index is out of
                range.
        """
        return self.GetWindow(3)

    def DoGetBestSize(self) -> wx.Size:
        """Get the size which best suits the window.

        For a control, it would be the minimal size which doesn't truncate the control,
        for a panel - the same size as it would have after a call to `Fit()`.

        Note:
            Overridden from :class:`Panel`.

        Returns:
            wx.Size: The best size for the window.
        """
        if not self._windows:
            # something is better than nothing...
            return wx.Size(10, 10)

        width: int = 0
        height: int = 0
        border: int = self._GetBorderSize()

        tl: wx.Window | None = self.GetTopLeft()
        tr: wx.Window | None = self.GetTopRight()
        bl: wx.Window | None = self.GetBottomLeft()
        br: wx.Window | None = self.GetBottomRight()

        for win in self._windows:
            w, h = win.GetEffectiveMinSize()
            width += w
            height += h

        if tl and tr:
            width += self._GetSashSize()

        if bl and br:
            height += self._GetSashSize()

        return wx.Size(width + 2 * border, height + 2 * border)

    # Recompute layout
    def _SizeWindows(self) -> None:
        """Recalculate the layout based on split positions and split fractions.

        See:
            :meth:`~FourWaySplitter.SetHSplit` and :meth:`~FourWaySplitter.SetVSplit`
                for more information about split fractions.
        """
        win0: wx.Window | None = self.GetTopLeft()
        win1: wx.Window | None = self.GetTopRight()
        win2: wx.Window | None = self.GetBottomLeft()
        win3: wx.Window | None = self.GetBottomRight()

        width, height = self.GetSize()
        barSize: int = self._GetSashSize()
        border: int = self._GetBorderSize()

        if self._expanded < 0:
            totw: int = width - barSize - 2 * border
            toth: int = height - barSize - 2 * border
            self._splitx: int = (self._fhor * totw) // 10000
            self._splity: int = (self._fver * toth) // 10000
            rightw: int = totw - self._splitx
            bottomh: int = toth - self._splity
            if win0:
                win0.SetSize(0, 0, self._splitx, self._splity)
                win0.Show()
            if win1:
                win1.SetSize(self._splitx + barSize, 0, rightw, self._splity)
                win1.Show()
            if win2:
                win2.SetSize(0, self._splity + barSize, self._splitx, bottomh)
                win2.Show()
            if win3:
                win3.SetSize(
                    self._splitx + barSize, self._splity + barSize, rightw, bottomh
                )
                win3.Show()

        else:

            if self._expanded < len(self._windows):
                for ii, win in enumerate(self._windows):
                    if ii == self._expanded:
                        win.SetSize(0, 0, width - 2 * border, height - 2 * border)
                        win.Show()
                    else:
                        win.Hide()

    # Determine split mode
    def GetMode(self, pt: wx.Point) -> int:
        """Determine the split mode for :class:`FourWaySplitter`.

        Args:
            pt (wx.Point): the point at which the mouse has been clicked,
                an instance of :class:`wx.Point`.

        Returns:
            int: One of the following 3 split modes:
                ================= ======================================================
                Split Mode        Description
                ================= ======================================================
                ``wx.HORIZONTAL`` the user has clicked on the horizontal sash
                ``wx.VERTICAL``   the user has clicked on the vertical sash
                ``wx.BOTH``       the user has clicked at the intersection between the 2
                                    sashes
                ================= ======================================================
        """
        barSize: int = self._GetSashSize()
        flag: int = wx.BOTH

        if pt.x < self._splitx - _TOLERANCE:
            flag &= ~wx.VERTICAL

        if pt.y < self._splity - _TOLERANCE:
            flag &= ~wx.HORIZONTAL

        if pt.x >= self._splitx + barSize + _TOLERANCE:
            flag &= ~wx.VERTICAL

        if pt.y >= self._splity + barSize + _TOLERANCE:
            flag &= ~wx.HORIZONTAL

        return flag

    # Move the split intelligently
    def MoveSplit(self, x: int, y: int) -> None:
        """Move the split accordingly to user action.

        Args:
            x (int): the new splitter `x` coordinate;
            y (int): the new splitter `y` coordinate.
        """
        width, height = self.GetSize()
        barSize: int = self._GetSashSize()

        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x > width - barSize:
            x = width - barSize
        if y > height - barSize:
            y = height - barSize

        self._splitx = x
        self._splity = y

    # Adjust layout
    def AdjustLayout(self) -> None:
        """Adjust layout of :class:`FourWaySplitter`.

        Mainly used to recalculate the correct values for split fractions.
        """
        width, height = self.GetSize()
        barSize: int = self._GetSashSize()

        self._fhor: int = (
            width > barSize
            and [(10000 * self._splitx + (width - barSize - 1)) // (width - barSize)]
            or [0]
        )[0]

        self._fver: int = (
            height > barSize
            and [(10000 * self._splity + (height - barSize - 1)) // (height - barSize)]
            or [0]
        )[0]

        self._SizeWindows()

    # Button being pressed
    def OnLeftDown(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_DOWN`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.

        Returns:
            None
        """
        if not self.IsEnabled():
            return

        pt: wx.Point = event.GetPosition()
        self.CaptureMouse()
        self._mode = self.GetMode(pt)

        if self._mode:
            self._offx: int = pt.x - self._splitx
            self._offy: int = pt.y - self._splity
            if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
                self.DrawSplitter(wx.ClientDC(self))
                self.DrawTrackSplitter(self._splitx, self._splity)

            self._flags |= FLAG_PRESSED

    # Button being released
    def OnLeftUp(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEFT_UP`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.

        Returns:
            None
        """
        if not self.IsEnabled():
            return

        if self.HasCapture():
            self.ReleaseMouse()

        flgs: int = self._flags

        self._flags &= ~FLAG_CHANGED
        self._flags &= ~FLAG_PRESSED

        if flgs & FLAG_PRESSED:

            if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
                self.DrawTrackSplitter(self._splitx, self._splity)
                self.DrawSplitter(wx.ClientDC(self))
                self.AdjustLayout()

            if flgs & FLAG_CHANGED:
                splitter_event = FourWaySplitterEvent(
                    wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGED, self
                )
                splitter_event.SetSashIdx(self._mode)
                splitter_event.SetSashPosition(wx.Point(self._splitx, self._splity))
                self.GetEventHandler().ProcessEvent(splitter_event)

        self._mode = NOWHERE

    def OnLeaveWindow(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_LEAVE_WINDOW`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        self.SetCursor(wx.STANDARD_CURSOR)
        self._RedrawIfHotSensitive(False)

    def OnEnterWindow(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_ENTER_WINDOW`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.
        """
        self._RedrawIfHotSensitive(True)

    def _RedrawIfHotSensitive(self, isHot: bool) -> None:
        """Use internally.

        Redraw the splitter if we are using a hot-sensitive splitter.

        Args:
            isHot (bool): ``True`` if the splitter is in a hot state,
                ``False`` otherwise.
        """
        if not self._IsVersionGreaterOrEqual(_RENDER_VER):
            return

        if wx.RendererNative.Get().GetSplitterParams(self).isHotSensitive:
            self._isHot: bool = isHot
            dc = wx.ClientDC(self)
            self.DrawSplitter(dc)

    def OnMotion(self, event: wx.MouseEvent) -> None:
        """Handle the ``wx.EVT_MOTION`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.MouseEvent): a :class:`MouseEvent` event to be processed.

        Returns:
            None
        """
        if self.HasFlag(wx.SP_NOSASH):
            return

        pt: wx.Point = event.GetPosition()

        # Moving split
        if self._flags & FLAG_PRESSED:

            oldsplitx: int = self._splitx
            oldsplity: int = self._splity

            if self._mode == wx.BOTH:
                self.MoveSplit(pt.x - self._offx, pt.y - self._offy)

            elif self._mode == wx.VERTICAL:
                self.MoveSplit(pt.x - self._offx, self._splity)

            elif self._mode == wx.HORIZONTAL:
                self.MoveSplit(self._splitx, pt.y - self._offy)

            # Send a changing event
            if not self.DoSendChangingEvent(wx.Point(self._splitx, self._splity)):
                self._splitx = oldsplitx
                self._splity = oldsplity
                return

            if oldsplitx != self._splitx or oldsplity != self._splity:
                if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
                    self.DrawTrackSplitter(oldsplitx, oldsplity)
                    self.DrawTrackSplitter(self._splitx, self._splity)
                else:
                    self.AdjustLayout()

                self._flags |= FLAG_CHANGED

        # Change cursor based on position
        ff: int = self.GetMode(pt)

        if ff == wx.BOTH:
            self.SetCursor(self._sashCursorSIZING)

        elif ff == wx.VERTICAL:
            self.SetCursor(self._sashCursorWE)

        elif ff == wx.HORIZONTAL:
            self.SetCursor(self._sashCursorNS)

        else:
            self.SetCursor(wx.STANDARD_CURSOR)

        event.Skip()

    def OnPaint(self, event: wx.PaintEvent) -> None:
        """Handle the ``wx.EVT_PAINT`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.PaintEvent): a :class:`PaintEvent` event to be processed.
        """
        dc = wx.PaintDC(self)
        self.DrawSplitter(dc)

    def OnSize(self, event: wx.SizeEvent) -> None:
        """Handle the ``wx.EVT_SIZE`` event for :class:`FourWaySplitter`.

        Args:
            event (wx.SizeEvent): a :class:`SizeEvent` event to be processed.
        """
        parent: wx.Window = wx.GetTopLevelParent(self)
        if isinstance(parent, wx.TopLevelWindow) and parent.IsIconized():
            event.Skip()
            return

        self._SizeWindows()

    def DoSendChangingEvent(self, pt: wx.Point) -> bool:
        """Send a ``EVT_SPLITTER_SASH_POS_CHANGING`` event.

        Args:
            pt (wx.Point): the point at which the splitter is being positioned.

        Returns:
            bool: ``True`` if the event is allowed, ``False`` otherwise.
        """
        # send the event
        event = FourWaySplitterEvent(wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGING, self)
        event.SetSashIdx(self._mode)
        event.SetSashPosition(pt)

        if self.GetEventHandler().ProcessEvent(event) and not event.IsAllowed():
            # the event handler vetoed the change or missing event.Skip()
            return False
        else:
            # or it might have changed the value
            return True

    def _GetSashSize(self) -> int:
        """Use internally.

        Returns:
            int: The size of the sash.
        """
        if self.HasFlag(wx.SP_NOSASH):
            return 0

        if self._IsVersionGreaterOrEqual(_RENDER_VER):
            return wx.RendererNative.Get().GetSplitterParams(self).widthSash
        else:
            return 5

    def _GetBorderSize(self) -> int:
        """Use internally.

        Returns:
            int: The size of the border.
        """
        if self._IsVersionGreaterOrEqual(_RENDER_VER):
            return wx.RendererNative.Get().GetSplitterParams(self).border
        else:
            return 0

    # Draw the horizontal split
    def DrawSplitter(self, dc: wx.DC) -> None:
        """Actually draw the sashes.

        Args:
            dc (wx.DC): an instance of :class:`wx.DC`.

        Returns:
            None
        """
        backColour: wx.Colour = self.GetBackgroundColour()
        dc.SetBrush(wx.Brush(backColour))
        dc.SetPen(wx.Pen(backColour))
        dc.Clear()

        if self._IsVersionGreaterOrEqual(_RENDER_VER):
            if self.HasFlag(wx.SP_3DBORDER):
                wx.RendererNative.Get().DrawSplitterBorder(
                    self, dc, self.GetClientRect()
                )
        else:
            barSize: int = self._GetSashSize()

        # Define barSize here to ensure it is always defined
        barSize = self._GetSashSize()

        # if we are not supposed to use a sash then we're done.
        if self.HasFlag(wx.SP_NOSASH):
            return

        flag = 0
        if self._isHot:
            flag: int = wx.CONTROL_CURRENT

        width, height = self.GetSize()

        if self._mode & wx.VERTICAL:
            if self._IsVersionGreaterOrEqual(_RENDER_VER):
                wx.RendererNative.Get().DrawSplitterSash(
                    self, dc, self.GetClientSize(), self._splitx, wx.VERTICAL, flag
                )
            else:
                dc.DrawRectangle(self._splitx, 0, barSize, height)

        if self._mode & wx.HORIZONTAL:
            if self._IsVersionGreaterOrEqual(_RENDER_VER):
                wx.RendererNative.Get().DrawSplitterSash(
                    self, dc, self.GetClientSize(), self._splity, wx.HORIZONTAL, flag
                )
            else:
                dc.DrawRectangle(0, self._splity, width, barSize)

    def DrawTrackSplitter(self, x: int, y: int) -> None:
        """Draws a fake sash in case we don't have ``wx.SP_LIVE_UPDATE`` style.

        Args:
            x (int): the `x` position of the sash;
            y (int): the `y` position of the sash.

        Note:
            This method relies on :class:`ScreenDC` which is currently unavailable on
                wxMac.
        """
        # Draw a line to represent the dragging sash, for when not doing live updates
        w, h = self.GetClientSize()
        dc = wx.ScreenDC()

        dc.SetLogicalFunction(wx.INVERT)
        dc.SetPen(self._sashTrackerPen)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)

        if self._mode == wx.VERTICAL:
            x1: int = x
            y1 = 2
            x2: int = x
            y2: int = h - 2
            if x1 > w:
                x1 = w
                x2 = w
            elif x1 < 0:
                x1 = 0
                x2 = 0

            x1, y1 = self.ClientToScreen((x1, y1))
            x2, y2 = self.ClientToScreen((x2, y2))

            dc.DrawLine(x1, y1, x2, y2)
            dc.SetLogicalFunction(wx.COPY)

        elif self._mode == wx.HORIZONTAL:

            x1 = 2
            y1: int = y
            x2 = w - 2
            y2 = y
            if y1 > h:
                y1 = h
                y2 = h
            elif y1 < 0:
                y1 = 0
                y2 = 0

            x1, y1 = self.ClientToScreen((x1, y1))
            x2, y2 = self.ClientToScreen((x2, y2))

            dc.DrawLine(x1, y1, x2, y2)
            dc.SetLogicalFunction(wx.COPY)

        elif self._mode == wx.BOTH:

            x1 = 2
            x2 = w - 2
            y1 = y
            y2 = y

            x1, y1 = self.ClientToScreen((x1, y1))
            x2, y2 = self.ClientToScreen((x2, y2))

            dc.DrawLine(x1, y1, x2, y2)

            x1 = x
            x2 = x
            y1 = 2
            y2 = h - 2

            x1, y1 = self.ClientToScreen((x1, y1))
            x2, y2 = self.ClientToScreen((x2, y2))

            dc.DrawLine(x1, y1, x2, y2)
            dc.SetLogicalFunction(wx.COPY)

    # Change horizontal split [fraction*10000]
    def SetHSplit(self, s: int) -> None:
        """Change horizontal split fraction.

        Args:
            s (int): the split fraction,
                which is an integer value between 0 and 10000 (inclusive),
                indicating how much space to allocate to the leftmost panes.
                For example, to split the panes at 35 percent, use::
                fourSplitter.SetHSplit(3500)
        """
        if s < 0:
            s = 0
        if s > 10000:
            s = 10000
        if s != self._fhor:
            self._fhor = s
            self._SizeWindows()

    # Change vertical split [fraction*10000]
    def SetVSplit(self, s: int) -> None:
        """Change vertical split fraction.

        Args:
            s (int): the split fraction,
                which is an integer value between 0 and 10000 (inclusive),
                indicating how much space to allocate to the topmost panes.
                For example, to split the panes at 35 percent,
                use::fourSplitter.SetVSplit(3500)
        """
        if s < 0:
            s = 0
        if s > 10000:
            s = 10000
        if s != self._fver:
            self._fver = s
            self._SizeWindows()

    # Expand one or all of the four panes
    def SetExpanded(self, expanded: int) -> None:
        """Expand a window or revert to four.

        Args:
            expanded (int): an integer >= 0 to expand a window to fill the whole client
                size, or an integer < 0 to return to the four-window view.

        Raises:
            Exception: If the `expanded` index is out of range (>= 4).
        """
        if expanded >= 4:
            raise Exception(f"ERROR: SetExpanded: index out of range: {expanded}")

        if self._expanded != expanded:
            self._expanded: int = expanded
            self._SizeWindows()


if __name__ == "__main__":

    import wx

    class MyFrame(wx.Frame):
        """
        MyFrame is a custom wx.Frame that demonstrates the usage of the FourWaySplitter.

        It initializes a frame with a FourWaySplitter containing four colored panels.

        Args:
            parent (wx.Window | None): The parent window for this frame.
        """

        def __init__(self, parent: wx.Window | None) -> None:
            wx.Frame.__init__(self, parent, -1, "FourWaySplitter Demo")

            splitter = FourWaySplitter(self, -1, agwStyle=wx.SP_LIVE_UPDATE)

            # Put in some coloured panels...
            for colour in [wx.RED, wx.WHITE, wx.BLUE, wx.GREEN]:
                panel = wx.Panel(splitter)
                panel.SetBackgroundColour(colour)
                splitter.AppendWindow(panel)

    # our normal wxApp-derived class, as usual

    app = wx.App(False)

    frame = MyFrame(None)
    app.SetTopWindow(frame)
    frame.Show()

    app.MainLoop()
