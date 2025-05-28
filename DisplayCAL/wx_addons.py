"""Extensions and utilities for wxPython GUI functionality.

It includes image
manipulation methods, custom event handling, improved timer implementations,
and additional window and display utilities.
"""

import contextlib
import os
import sys
import threading
import types
from time import sleep
from typing import ClassVar

from DisplayCAL import floatspin
from DisplayCAL.colormath import specialpow
from DisplayCAL.lib.agw.gradientbutton import GradientButton
from DisplayCAL.wx_fixes import GenButton, PlateButton, get_dialogs, wx


def AdjustMinMax(self, minvalue=0.0, maxvalue=1.0):  # noqa: D417
    """Adjust min/max.

    Args:
        minvalue (float, optional): The minimum value to adjust to. Defaults to 0.0.
        maxvalue (float, optional): The maximum value to adjust to. Defaults to 1.0.
    """
    buffer = self.GetDataBuffer()
    for i, byte in enumerate(buffer):
        buffer[i] = min(int(round(minvalue * 255 + byte * (maxvalue - minvalue))), 255)


wx.Image.AdjustMinMax = AdjustMinMax


def Blend(self, bitmap, x, y):  # noqa: D417
    """Blend the given bitmap over the specified position in this bitmap.

    Args:
        bitmap (wx.Bitmap): The bitmap to blend over this bitmap.
        x (int): The x-coordinate where the bitmap will be blended.
        y (int): The y-coordinate where the bitmap will be blended.
    """
    dc = wx.MemoryDC(self)
    dc.DrawBitmap(bitmap, x, y)


wx.Bitmap.Blend = Blend


def Invert(self):
    """Invert image colors."""
    databuffer = self.GetDataBuffer()
    for i, byte in enumerate(databuffer):
        databuffer[i] = 255 - byte


wx.Image.Invert = Invert


def GammaCorrect(self, from_gamma=-2.4, to_gamma=1.8):  # noqa: D417
    """Gamma correct.

    Args:
        from_gamma (float, optional): The gamma value to convert from.
            Defaults to -2.4.
        to_gamma (float, optional): The gamma value to convert to.
            Defaults to 1.8.
    """
    buffer = self.GetDataBuffer()
    for i, byte in enumerate(buffer):
        buffer[i] = int(
            round(specialpow(byte / 255.0, from_gamma) ** (1.0 / to_gamma) * 255)
        )


wx.Image.GammaCorrect = GammaCorrect


def IsBW(self):
    """Check if image is grayscale in the most effective way possible.

    Note that this is a costly operation even though it returns as quickly as
    possible for non-grayscale images (i.e. when it encounters the first
    non-equal RGB triplet).

    Returns:
        bool: True if the image is grayscale (all RGB triplets are equal),
            False otherwise.
    """
    triplet = set()
    for i, byte in enumerate(self.GetDataBuffer()):
        triplet.add(byte)
        if i % 3 == 2:
            if len(triplet) != 1:
                return False
            triplet = set()
    return True


wx.Image.IsBW = IsBW


def GetRealClientArea(self):
    """Return the real (non-overlapping) client area of a display.

    Returns:
        wx.Rect: The real client area of the display, adjusted to ensure it
            does not overlap with the window's geometry.
    """
    # need to fix overlapping ClientArea on some Linux multi-display setups
    # the client area must be always smaller than the geometry
    clientarea = list(self.ClientArea)
    clientarea[0] = max(clientarea[0], self.Geometry[0])
    clientarea[1] = max(clientarea[1], self.Geometry[1])
    clientarea[2] = min(clientarea[2], self.Geometry[2])
    clientarea[3] = min(clientarea[3], self.Geometry[3])
    return wx.Rect(*clientarea)


wx.Display.GetRealClientArea = GetRealClientArea


def GetAllChildren(self, skip=None):  # noqa: D417
    """Get children of window and its subwindows.

    Args:
        skip (list | tuple, optional): A list or tuple of windows to skip.
            Defaults to None, which means no windows are skipped.

    Returns:
        list[wx.Window]: A list of all child windows, including subwindows,
            excluding any specified in the skip parameter.
    """
    if not isinstance(skip, (list, tuple)):
        skip = [skip]
    children = [child for child in list(self.GetChildren()) if child not in skip]
    allchildren = []
    for child in children:
        allchildren.append(child)
        if hasattr(child, "GetAllChildren") and callable(child.GetAllChildren):
            allchildren += child.GetAllChildren(skip)
    return allchildren


wx.Window.GetAllChildren = GetAllChildren


def GetDisplay(self):
    """Return the display the window is shown on.

    Returns:
        wx.Display: The display object representing the display the window is
            shown on. If the window is outside the visible area, it returns
            the first display.
    """
    display_no = wx.Display.GetFromWindow(self)
    display_no = max(display_no, 0)  # window outside visible area
    return wx.Display(display_no)


wx.Window.GetDisplay = GetDisplay


def SetMaxFontSize(self, pointsize=11):  # noqa: D417
    """Set the maximum font size for this window.

    Args:
        pointsize (int, optional): The maximum point size for the font.
            Defaults to 11.
    """
    font = self.GetFont()
    if font.GetPointSize() > pointsize:
        font.SetPointSize(pointsize)
        self.SetFont(font)


wx.Window.SetMaxFontSize = SetMaxFontSize


def RealCenterOnScreen(self, dir=wx.BOTH):  # noqa: A002, D417
    """Center the window on the screen that it is on.

    Unlike CenterOnScreen which always centers on 1st screen.

    Args:
        dir (int, optional): The direction to center the window. Can be
            wx.HORIZONTAL, wx.VERTICAL, or wx.BOTH. Defaults to wx.BOTH.
    """
    x, y = self.Position
    left, top, w, h = self.GetDisplay().ClientArea
    if dir & wx.HORIZONTAL:
        x = left + w / 2 - self.Size[0] / 2
    if dir & wx.VERTICAL:
        y = top + h / 2 - self.Size[1] / 2
    self.Position = x, y


wx.TopLevelWindow.RealCenterOnScreen = RealCenterOnScreen


def SetSaneGeometry(self, x=None, y=None, w=None, h=None):  # noqa: D417
    """Set a 'sane' window position and/or size (within visible screen area).

    Args:
        x (int, optional): The x-coordinate to set. If None, the current x
            position is used.
        y (int, optional): The y-coordinate to set. If None, the current y
            position is used.
        w (int, optional): The width to set. If None, the current width is
            used.
        h (int, optional): The height to set. If None, the current height is
            used.
    """
    if None not in (x, y):
        # First, move to coordinates given
        self.SetPosition((x, y))
    # Returns the first display's client area if the window
    # is completely outside the client area of all displays
    display_client_rect = self.GetDisplay().ClientArea
    if sys.platform not in ("darwin", "win32"):  # Linux
        # Client-side decorations on wayland, otherwise assume server-side decorations
        safety_margin = 0 if os.getenv("XDG_SESSION_TYPE") == "wayland" else 40
    else:
        safety_margin = 20
    if None not in (w, h):
        # Set given size, but resize if needed to fit inside client area
        if hasattr(self, "MinClientSize"):
            min_w, min_h = self.MinClientSize
        else:
            min_w, min_h = self.WindowToClientSize(self.MinSize)
        border_lr = self.Size[0] - self.ClientSize[0]
        border_tb = self.Size[1] - self.ClientSize[1]
        self.ClientSize = (
            min(display_client_rect[2] - border_lr, max(w, min_w)),
            min(display_client_rect[3] - border_tb - safety_margin, max(h, min_h)),
        )
    if None not in (x, y) and (
        not display_client_rect.ContainsXY(x, y)
        or not display_client_rect.ContainsRect((x, y, self.Size[0], self.Size[1]))
    ):
        # If outside client area, move into client area
        xy = [x, y]
        for i, pos in enumerate([xy, (x + self.Size[0], y + self.Size[1])]):
            for j in range(2):
                if (
                    pos[j] > display_client_rect[j] + display_client_rect[2 + j]
                    or pos[j] < display_client_rect[j]
                ):
                    if i:
                        xy[j] = (
                            display_client_rect[j]
                            + display_client_rect[2 + j]
                            - self.Size[j]
                        )
                    else:
                        xy[j] = display_client_rect[j]
        self.SetPosition(tuple(xy))


wx.Window.SetSaneGeometry = SetSaneGeometry


def GridGetSelectedRowsFromSelection(self):
    """Return the number of fully selected rows.

    Unlike GetSelectedRows, include rows that have been selected
    by choosing individual cells.

    Returns:
        list[int]: A list of row indices that are fully selected.
    """
    numcols = self.GetNumberCols()
    rows = []
    i = -1
    for cell in self.GetSelection():
        row, col = cell
        if row > i:
            i = row
            rownumcols = 0
        rownumcols += 1
        if rownumcols == numcols:
            rows.append(row)
    return rows


wx.grid.Grid.GetSelectedRowsFromSelection = GridGetSelectedRowsFromSelection


def GridGetSelectionRows(self):
    """Return the selected rows, even if not all cells in a row are selected.

    Returns:
        list[int]: A list of row indices that are selected.
    """
    rows = []
    i = -1
    for row, _col in self.GetSelection():
        if row > i:
            i = row
            rows.append(row)
    return rows


wx.grid.Grid.GetSelectionRows = GridGetSelectionRows


def IsSizer(self):
    """Check if the window is a sizer.

    Returns:
        bool: True if the window is a sizer, False otherwise.
    """
    return isinstance(self, wx.Sizer)


wx.Window.IsSizer = IsSizer


def gamma_encode(R, G, B, alpha=wx.ALPHA_OPAQUE):
    """(Re-)Encode R'G'B' colors with specific platform gamma.

    R, G, B = color components in range 0..255

    Note this only has effect under wxMac which assumes a decoding gamma of 1.8

    Args:
        R (int): Red component (0-255).
        G (int): Green component (0-255).
        B (int): Blue component (0-255).
        alpha (int, optional): Alpha component (0-255). Defaults to wx.ALPHA_OPAQUE.

    Returns:
        list[int]: A list containing the gamma-encoded R, G, B, and alpha values.
    """
    if sys.platform == "darwin":
        # Adjust for wxMac assuming gamma 1.8 instead of sRGB
        # Decode R'G'B' -> linear light using sRGB transfer function, then
        # re-encode to gamma = 1.0 / 1.8 so that when decoded with gamma = 1.8
        # we get the correct sRGB color
        RGBa = [
            int(round(specialpow(v / 255.0, -2.4) ** (1.0 / 1.8) * 255))
            for v in (R, G, B)
        ]
        RGBa.append(alpha)
        return RGBa
    return [R, G, B, alpha]


def get_platform_window_decoration_size():
    """Get the size of the window decoration.

    Returns:
        tuple[int, int]: A tuple containing the border and titlebar size.
    """
    if sys.platform in ("darwin", "win32"):
        # Size includes windows decoration
        if sys.platform == "win32":
            border = 8  # Windows 7
            titlebar = 30  # Windows 7
        else:
            border = 0  # Mac OS X 10.7 Lion
            titlebar = 22  # Mac OS X 10.7 Lion
    else:
        # Linux. Size does not include window decoration
        border = 0
        titlebar = 0
    return border, titlebar


def draw_granger_rainbow(dc, x=0, y=0, width=1920, height=1080):
    """Draw a granger rainbow to a DC.

    Args:
        dc (wx.DC): The device context to draw on.
        x (int, optional): The x-coordinate of the top-left corner. Defaults to 0.
        y (int, optional): The y-coordinate of the top-left corner. Defaults to 0.
        width (int, optional): The width of the rainbow. Defaults to 1920.
        height (int, optional): The height of the rainbow. Defaults to 1080.

    Raises:
        NotImplementedError: If the device context does not support alpha
            transparency.

    """
    if not isinstance(dc, wx.GCDC):
        raise NotImplementedError(f"{dc.__class__} lacks alpha transparency support")

    # Widths
    column_width = int(162.0 / 1920.0 * width)
    rainbow_width = width - column_width * 2
    strip_width = int(rainbow_width / 7.0)
    rainbow_width = strip_width * 7
    column_width = (width - rainbow_width) / 2

    # Gray columns left/right
    dc.GradientFillLinear(
        wx.Rect(x, y, width, height),
        wx.Colour(0, 0, 0),
        wx.Colour(255, 255, 255),
        wx.UP,
    )

    # Granger rainbow
    rainbow = [
        (255, 0, 255),
        (0, 0, 255),
        (0, 255, 255),
        (0, 255, 0),
        (255, 255, 0),
        (255, 0, 0),
        (255, 0, 255),
    ]
    start = rainbow[-2]
    for i, end in enumerate(rainbow):
        dc.GradientFillLinear(
            wx.Rect(x + column_width + strip_width * i, y, strip_width, height),
            wx.Colour(*start),
            wx.Colour(*end),
            wx.RIGHT,
        )
        start = end

    # White-to-black gradient with transparency for shading
    # Top half - white to transparent
    dc.GradientFillLinear(
        wx.Rect(x + column_width, y, rainbow_width, height / 2),
        wx.Colour(0, 0, 0, 0),
        wx.Colour(255, 255, 255, 255),
        wx.UP,
    )
    # Bottom half - transparent to black
    dc.GradientFillLinear(
        wx.Rect(x + column_width, y + height / 2, rainbow_width, height / 2),
        wx.Colour(0, 0, 0, 255),
        wx.Colour(255, 255, 255, 0),
        wx.UP,
    )


def create_granger_rainbow_bitmap(width=1920, height=1080, filename=None):
    """Create a granger rainbow bitmap.

    Args:
        width (int): The width of the bitmap. Defaults to 1920.
        height (int): The height of the bitmap. Defaults to 1080.
        filename (str, optional): If provided, save the bitmap to this file.
            Defaults to None.

    Returns:
        wx.Bitmap: The created bitmap containing the granger rainbow.
    """
    # Main bitmap
    bmp = wx.EmptyBitmap(width, height)
    mdc = wx.MemoryDC(bmp)
    dc = wx.GCDC(mdc)

    draw_granger_rainbow(dc, 0, 0, width, height)

    mdc.SelectObject(wx.NullBitmap)

    if filename:
        name, ext = os.path.splitext(filename)
        ext = ext.lower()
        bmp_type = {
            ".bmp": wx.BITMAP_TYPE_BMP,
            ".jpe": wx.BITMAP_TYPE_JPEG,
            ".jpg": wx.BITMAP_TYPE_JPEG,
            ".jpeg": wx.BITMAP_TYPE_JPEG,
            ".jfif": wx.BITMAP_TYPE_JPEG,
            ".pcx": wx.BITMAP_TYPE_PCX,
            ".png": wx.BITMAP_TYPE_PNG,
            ".tga": wx.BITMAP_TYPE_TGA,
            ".tif": wx.BITMAP_TYPE_TIFF,
            ".tiff": wx.BITMAP_TYPE_TIFF,
            ".xpm": wx.BITMAP_TYPE_XPM,
        }.get(ext, wx.BITMAP_TYPE_PNG)
        bmp.SaveFile(filename, bmp_type)
    return bmp


def get_parent_frame(window):
    """Get parent frame (if any).

    Args:
        window (wx.Window): The wx.Window object to start searching from.

    Returns:
        wx.Frame | None: The parent frame of the window, or None if no parent
            frame is found.
    """
    parent = window.Parent
    while parent:
        if isinstance(parent, wx.Frame):
            return parent
        parent = parent.Parent
    return None


class CustomEvent(wx.PyEvent):
    """A wx.Event replacement.

    Args:
        typeId (int): The event type ID.
        object (wx.Window): The wx.Window object associated with the event.
        window (wx.Window, optional): The window associated with the event.
            Defaults to None.
    """

    def __init__(self, typeId, object, window=None):  # noqa: A002
        wx.PyEvent.__init__(self, object.GetId(), typeId)
        self.EventObject = object
        self.Window = window

    def GetWindow(self):
        """Return the window associated with this event.

        Returns:
            wx.Window: The window associated with this event, or None if not set.
        """
        return self.Window


_GLOBAL_TIMER_LOCK = threading.Lock()


wxEVT_BETTER_TIMER = wx.NewEventType()  # noqa: N816
EVT_BETTER_TIMER = wx.PyEventBinder(wxEVT_BETTER_TIMER, 1)


class BetterTimerEvent(wx.PyCommandEvent):
    """A wx.Timer event replacement.

    Args:
        id (int): The ID of the timer event.
        ms (int): The interval of the timer in milliseconds.
    """

    def __init__(self, id=wx.ID_ANY, ms=0):  # noqa: A002
        wx.PyCommandEvent.__init__(self, wxEVT_BETTER_TIMER, id)
        self._ms = ms

    def GetInterval(self):
        """Return the interval of the timer in milliseconds.

        Returns:
            int: The interval of the timer in milliseconds.
        """
        return self._ms

    Interval = property(GetInterval)


class BetterTimer(wx.Timer):
    """A wx.Timer replacement.

    Doing GUI updates using regular timers can be incredibly SEGFAULTy under
    wxPython Phoenix when several timers run concurrently.

    This approach uses a global lock to work around the issue.

    Args:
        owner (wx.Window, optional): The owner window that will receive the
            timer events. Defaults to None.
        timerid (int): The ID of the timer. If -1, a new ID will be generated.
            Defaults to wx.ID_ANY.
    """

    def __init__(self, owner=None, timerid=wx.ID_ANY):
        wx.Timer.__init__(self, None, timerid)
        self._owner = owner

    def Notify(self):
        """Notify the owner that the timer has expired."""
        if self._owner and _GLOBAL_TIMER_LOCK.acquire(False):
            try:
                wx.PostEvent(self._owner, BetterTimerEvent(self.Id, self.Interval))
            finally:
                _GLOBAL_TIMER_LOCK.release()


class BetterCallLater(wx.CallLater):
    """A wx.CallLater replacement.

    Args:
        millis (int): The number of milliseconds to wait before calling the
            callable.
        callableObj (callable): The callable object to call when the timer
            expires.
        *args: Positional arguments to pass to the callable.
        **kwargs: Keyword arguments to pass to the callable.
    """

    def __init__(self, millis, callableObj, *args, **kwargs):
        wx.CallLater.__init__(self, millis, callableObj, *args, **kwargs)

    def Notify(self):
        """Notify the owner that the timer has expired."""
        if _GLOBAL_TIMER_LOCK.acquire(True):
            try:
                wx.CallLater.Notify(self)
            finally:
                _GLOBAL_TIMER_LOCK.release()


class ThreadedTimer:
    """Threaded wx.Timer replacement.

    This uses threads instead of actual timers which are a limited resource.

    Args:
        owner (wx.Window, optional): The owner window that will receive the
            timer events. Defaults to None.
        timerid (int): The ID of the timer. If -1, a new ID will be generated.
            Defaults to wx.ID_ANY.
    """

    def __init__(self, owner=None, timerid=wx.ID_ANY):
        self._owner = owner
        if timerid < 0:
            timerid = wx.Window.NewControlId()
        self._id = timerid
        self._ms = 0
        self._oneshot = False
        self._keep_running = False
        self._thread = None

    def _notify(self):
        """Notify the owner that the timer has expired."""
        if _GLOBAL_TIMER_LOCK.acquire(self._oneshot):
            try:
                self.Notify()
            finally:
                _GLOBAL_TIMER_LOCK.release()

    def _timer(self):
        """The timer thread that runs the timer logic."""
        self._keep_running = True
        while self._keep_running:
            sleep(self._ms / 1000.0)
            if self._keep_running:
                wx.CallAfter(self._notify)
                if self._oneshot:
                    self._keep_running = False

    def Destroy(self):
        """Destroy the timer and release its resources."""
        if hasattr(wx.Window, "UnreserveControlId") and self.Id < 0:
            with contextlib.suppress(wx.wxAssertionError):
                wx.Window.UnreserveControlId(self.Id)

    def GetId(self):
        """Return the ID of the timer.

        Returns:
            int: The ID of the timer.
        """
        return self._id

    def GetInterval(self):
        """Return the interval of the timer in milliseconds.

        Returns:
            int: The interval of the timer in milliseconds.
        """
        return self._ms

    def GetOwner(self):
        """Return the owner of the timer.

        Returns:
            wx.Window: The owner window that will receive the timer events.
        """
        return self._owner

    def SetOwner(self, owner):
        """Set the owner of the timer.

        Args:
            owner (wx.Window): The owner window that will receive the timer
                events.
        """
        self._owner = owner

    Id = property(GetId)
    Interval = property(GetInterval)
    Owner = property(GetOwner, SetOwner)

    def IsOneShot(self):
        """Check if the timer is a one-shot timer.

        Returns:
            bool: True if the timer is a one-shot timer, False otherwise.
        """
        return self._oneshot

    def IsRunning(self):
        """Check if the timer is currently running.

        Returns:
            bool: True if the timer is running, False otherwise.
        """
        return self._keep_running

    def Notify(self):
        """Notify the owner that the timer has expired."""
        if self._owner:
            self._owner.ProcessEvent(BetterTimerEvent(self._id, self._ms))

    def Start(self, milliseconds=-1, oneShot=False):
        """Start the timer with the given milliseconds and one-shot flag.

        Args:
            milliseconds (int): The number of milliseconds to wait before
                calling the Notify method. If -1, the timer will not be
                restarted.
            oneShot (bool): If True, the timer will only run once and then
                stop. If False, the timer will keep running at the specified
                interval.
        """
        if self._thread and self._thread.is_alive():
            self._keep_running = False
            self._thread.join()
        if milliseconds > -1:
            self._ms = milliseconds
        self._oneshot = oneShot
        self._thread = threading.Thread(target=self._timer, name="ThreadedTimer")
        self._thread.start()

    def Stop(self):
        """Stop the timer."""
        self._keep_running = False


class ThreadedCallLater(ThreadedTimer):
    """Threaded wx.CallLater replacement.

    This uses threads instead of actual timers which are a limited resource.

    Args:
        millis (int): The number of milliseconds to wait before calling the
            callable.
        callableObj (callable): The callable object to call when the timer
            expires.
        *args: Positional arguments to pass to the callable.
        **kwargs: Keyword arguments to pass to the callable.
    """

    def __init__(self, millis, callableObj, *args, **kwargs):
        ThreadedTimer.__init__(self)
        self._oneshot = True
        self._callable = callableObj
        self._has_run = False
        self._result = None
        self.SetArgs(*args, **kwargs)
        self.Start(millis)

    def GetResult(self):
        """Get the result of the callable after the timer has run.

        Returns:
            Any: The result of the callable, or None if the timer has not run.
        """
        return self._result

    Result = property(GetResult)

    def HasRun(self):
        """Check if the timer has run.

        Returns:
            bool: True if the timer has run, False otherwise.
        """
        return self._has_run

    def Notify(self):
        """Notify the owner that the timer has expired and call the callable."""
        self._result = self._callable(*self._args, **self._kwargs)
        self._has_run = True

    def SetArgs(self, *args, **kwargs):
        """Set the arguments to be passed to the callable when the timer expires."""
        self._args = args
        self._kwargs = kwargs

    def Start(self, millis=None, *args, **kwargs):
        """Start the timer with the given milliseconds and optional args/kwargs.

        Args:
            millis (int, optional): The number of milliseconds to wait before
                calling the callable. Defaults to None.
            *args: Positional arguments to pass to the callable.
            **kwargs: Keyword arguments to pass to the callable.
        """
        if args:
            self._args = args
        if kwargs:
            self._kwargs = kwargs
        ThreadedTimer.Start(self, millis, True)

    Restart = Start


class BetterWindowDisabler:
    """Class to disable all top-level windows and their child windows.

    This is actually needed under Mac OS X where disabling a top level window
    will not prevent interaction with its children.

    If toplevelparent is given, disable only this window and its child windows.

    Args:
        skip (list, optional): A list of windows to skip when disabling.
            Defaults to None.
        toplevelparent (wx.Window, optional): The top-level parent window to
            disable. If None, all top-level windows will be disabled.
            Defaults to None.
        include_menus (bool, optional): If True, include menus in the
            disabling process. Defaults to False.
    """

    windows: ClassVar[set] = set()

    def __init__(self, skip=None, toplevelparent=None, include_menus=False):
        self._windows = []
        self.skip = skip
        self.toplevelparent = toplevelparent
        self.include_menus = include_menus
        self.disable()

    def __del__(self) -> None:
        """Destruct the instance."""
        self.enable()

    def disable(self):
        """Disable the windows."""
        self.enable(False)

    def enable(self, enable=True):
        """Enable or disable the windows.

        Args:
            enable (bool): If True, enable the windows; if False, disable them.
        """
        if enable:
            self.restore_window_state()
            return

        skip = self.skip or []
        if skip and not isinstance(skip, (list, tuple)):
            skip = [skip]
        if self.toplevelparent:
            toplevel = [self.toplevelparent]
        else:
            toplevel = list(wx.GetTopLevelWindows())
        for w in toplevel:
            if (
                w
                and w not in skip
                and "Inspection" not in f"{w}"
                and w not in BetterWindowDisabler.windows
            ):
                self._windows.append(w)
                # Selectively add children to our list of handled
                # windows. This prevents a segfault with wxPython 4
                # under macOS where GetAllChildren includes sub-controls
                # of controls, like scrollbars etc.
                for child in w.GetAllChildren(skip + toplevel):
                    if (
                        child
                        and isinstance(
                            child,
                            (
                                wx.BitmapButton,
                                wx.Button,
                                wx.CheckBox,
                                wx.Choice,
                                wx.ComboBox,
                                wx.ListBox,
                                wx.ListCtrl,
                                wx.RadioButton,
                                wx.SpinCtrl,
                                wx.Slider,
                                wx.StaticText,
                                wx.TextCtrl,
                                wx.grid.Grid,
                                floatspin.FloatSpin,
                                GenButton,
                                GradientButton,
                                PlateButton,
                            ),
                        )
                        and child not in BetterWindowDisabler.windows
                    ):
                        # Don't disable panels, this can have weird side
                        # effects for contained controls
                        self._windows.append(child)
                if self.include_menus and (menubar := w.GetMenuBar()):
                    for menu, _label in menubar.GetMenus():
                        for item in menu.GetMenuItems():
                            self._windows.append(item)

        def Enable(w_, enable=True):
            """Enable or disable the window.

            Args:
                w_ (wx.Window): The window to enable or disable.
                enable (bool): If True, enable the window; if False,
                    disable it.
            """
            w_._BetterWindowDisabler_enabled = enable

        def Disable(w_):
            """Disable the window.

            Args:
                w_ (wx.Window): The window to disable.
            """
            w_._BetterWindowDisabler_enabled = False

        for w in reversed(self._windows):
            BetterWindowDisabler.windows.add(w)
            enabled = w.IsEnabled()
            w.Enable(False)
            if hasattr(w, "Disable"):
                w._BetterWindowDisabler_Disable = w.Disable
                w.Disable = types.MethodType(Disable, w)
            w._BetterWindowDisabler_Enable = w.Enable
            w.Enable = types.MethodType(Enable, w)
            w.Enable(enabled)
        return

        self.restore_window_state()

    def restore_window_state(self):
        """Restore the state of all windows that were disabled."""
        for w in self._windows:
            BetterWindowDisabler.windows.remove(w)
            if not w:
                continue  # window has been destroyed
            if hasattr(w, "_BetterWindowDisabler_Disable"):
                w.Disable = w._BetterWindowDisabler_Disable
            if hasattr(w, "_BetterWindowDisabler_Enable"):
                w.Enable = w._BetterWindowDisabler_Enable
            if hasattr(w, "_BetterWindowDisabler_enabled"):
                w.Enable(w._BetterWindowDisabler_enabled)


class CustomGridCellEvent(CustomEvent):
    """Custom event for wx.grid.GridCell.

    Args:
        typeId (int): The event type ID.
        object (wx.grid.GridCell): The grid cell object associated with the
            event.
        row (int, optional): The row index of the grid cell event. Defaults to
            -1.
        col (int, optional): The column index of the grid cell event. Defaults
            to -1.
        window (wx.Window, optional): The window associated with the event.
            Defaults to None.
    """

    def __init__(self, typeId, object, row=-1, col=-1, window=None):  # noqa: A002
        CustomEvent.__init__(self, typeId, object, window)
        self.Row = row
        self.Col = col

    def GetRow(self):
        """Get the row index of the grid cell event.

        Returns:
            int: The row index of the grid cell event.
        """
        return self.Row

    def GetCol(self):
        """Get the column index of the grid cell event.

        Returns:
            int: The column index of the grid cell event.
        """
        return self.Col


class PopupMenu:
    """A collection of menus that has a wx.MenuBar-like interface.

    Args:
        parent (wx.Window): The parent window that will display the popup menu.
    """

    def __init__(self, parent):
        self.Parent = parent
        self.TopLevelParent = parent.TopLevelParent
        self._menus = []
        self._enabledtop = {}

    def Append(self, menu, title):
        """Append a menu to the popup menu."""
        self._menus.append((menu, title))

    def EnableTop(self, pos, enable=True):
        """Enable or disable the top-level menu at the given position.

        Args:
            pos (int): The position of the top-level menu to enable or disable.
            enable (bool): If True, enable the menu; if False, disable it.
        """
        self._enabledtop[pos] = enable

    def FindItemById(self, id):  # noqa: A002
        """Find a menu item by its ID.

        Args:
            id (int): The ID of the menu item to find.

        Returns:
            None | wx.MenuItem: The menu item with the given ID, or None if not
                found.
        """
        for menu, _label in self._menus:
            item = menu.FindItemById(id)
            if item:
                return item
        return None

    def FindMenu(self, title):
        """Find the index of a menu by its title.

        Args:
            title (str): The title of the menu to find.

        Returns:
            int: The index of the menu with the given title, or wx.NOT_FOUND if
                the menu is not found.
        """
        for i, (_menu, label) in enumerate(self._menus):
            if title == label:
                return i
        return wx.NOT_FOUND

    def GetMenu(self, index):
        """Get the menu at the given index.

        Args:
            index (int): The index of the menu to retrieve.

        Returns:
            wx.Menu: The menu at the specified index.
        """
        return self._menus[index][0]

    def GetMenuCount(self):
        """Return the number of menus in this menubar.

        Returns:
            int: The number of menus in this menubar.
        """
        return len(self._menus)

    def GetMenus(self):
        """Return menus.

        Returns:
            list[wx.Menu]: List of child menus.
        """
        return list(self._menus)

    def SetMenus(self, menus):
        """Set menus.

        Args:
            menus (list[wx.Menu]): A list of wx.Menu instances to set as a
                child of this menubar.
        """
        self._menus = []
        for menu, label in menus:
            self.Append((menu, label))

    Menus = property(GetMenus, SetMenus)

    def IsEnabledTop(self, pos):
        """Check if the top-level menu at the given position is enabled.

        Args:
            pos (int): The position of the top-level menu to check.

        Returns:
            bool: True if the top-level menu is enabled, False otherwise.
        """
        return self._enabledtop.get(pos, True)

    def SetMenuLabel(self, pos, label):
        """Set the label of a menu at the given position.

        Args:
            pos (int): The position of the menu to set the label for.
            label (str): The new label for the menu.
        """
        self._menus[pos] = (self._menus[pos][0], label)

    def bind_keys(self):
        """Bind accelerator keys to the top level parent."""
        if sys.platform == "darwin":
            accels = self.get_accelerator_entries()
            self.TopLevelParent.SetAcceleratorTable(wx.AcceleratorTable(accels()))
        else:
            self.TopLevelParent.Bind(wx.EVT_CHAR_HOOK, self.key_handler)

    def get_accelerator_entries(self):
        """Get accelerator entries for all menus.

        Returns:
            list[wx.AcceleratorEntry]: List of accelerator entries for all
                menu items.
        """
        accels = []
        for menu, _label in self._menus:
            for item in menu.MenuItems:
                accel = item.Accel
                if accel:
                    accel = wx.AcceleratorEntry(
                        accel.Flags, accel.KeyCode, accel.Command, item
                    )
                    accels.append(accel)
        return accels

    def key_handler(self, event):
        """Handle accelerator keys.

        Args:
            event (wx.KeyEvent): The key event to handle.s
        """
        keycode = event.KeyCode
        flags = wx.ACCEL_NORMAL
        for key in ("ALT", "CMD", "CTRL", "SHIFT"):
            if wx.GetKeyState(getattr(wx, "WXK_" + key.replace("CTRL", "CONTROL"), -1)):
                flags |= getattr(wx, "ACCEL_" + key.upper())
        for menu, _label in self._menus:
            for item in menu.MenuItems:
                accel = item.Accel
                if accel and accel.KeyCode == keycode and accel.Flags == flags:
                    event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED)
                    event.Id = item.Id
                    if item.Kind == wx.ITEM_RADIO:
                        event.SetInt(1)
                    elif item.Kind == wx.ITEM_CHECK:
                        event.SetInt(int(not item.Checked))
                    self.TopLevelParent.ProcessEvent(event)

    def popup(self):
        """Popup the list of menus (with actual menus as submenus)."""
        top_menu = wx.Menu()

        for menu, label in self._menus:
            top_menu.AppendSubMenu(menu, label)

        self.Parent.PopupMenu(top_menu)

        # Delete menuitems (not submenus)
        for item in top_menu.MenuItems:
            top_menu.Delete(item)

        # Now we can safely destroy the menu without affecting submenus
        top_menu.Destroy()


class FileDrop(wx.FileDropTarget):
    """A wx.FileDropTarget derivative that can handle multiple file types.

    Args:
        drophandlers (dict): A dictionary mapping file extensions to
            handler functions that will be called when files with those
            extensions are dropped. The handler function should accept a
            single argument, the filename.s.
    """

    def __init__(self, drophandlers=None):
        wx.FileDropTarget.__init__(self)
        if drophandlers is None:
            drophandlers = {}
        self.drophandlers = drophandlers
        self.unsupported_handler = None

    def OnDropFiles(self, x, y, filenames):
        """Handle dropped files.

        Args:
            x (int): The x-coordinate of the drop position.
            y (int): The y-coordinate of the drop position.
            filenames (list[str]): List of file paths that were dropped.
        """
        dialogs = get_dialogs()
        interactable = not hasattr(self, "parent") or (
            self.parent.Enabled and (not dialogs or self.parent in dialogs)
        )
        if not interactable:
            wx.Bell()
            return False
        self._files = []
        self._filenames = filenames

        for filename in filenames:
            name, ext = os.path.splitext(filename)
            if ext.lower() in self.drophandlers:
                self._files.append((ext.lower(), filename))

        if self._files:
            self._files.reverse()
            wx.CallLater(1, wx.CallAfter, self.process)
        elif self.unsupported_handler:
            wx.CallLater(1, wx.CallAfter, self.unsupported_handler)
        return False

    def process(self):
        """Process the files that were dropped."""
        ms = 1.0 / 60
        while self._files:
            if hasattr(self, "parent") and hasattr(self.parent, "worker"):
                while self.parent.worker.is_working():
                    wx.Yield()
                    sleep(ms)
                    if self.parent.worker.thread_abort:
                        return
            ext, filename = self._files.pop()
            self.drophandlers[ext](filename)


class IdFactory:
    """Inspired by wxPython 4 (Phoenix) wx.IdManager"""

    CurrentId = 100
    ReservedIds: ClassVar[set] = set()

    @classmethod
    def NewId(cls) -> int:
        """Replacement for wx.NewId().

        Returns:
            int: A new unique ID that is not reserved.
        """
        start_id = cls.CurrentId

        while True:
            # Skip the part of IDs space that contains hard-coded values
            if cls.CurrentId == wx.ID_LOWEST:
                cls.CurrentId = wx.ID_HIGHEST + 1
            id_ = cls.CurrentId
            if id_ < 30095:
                cls.CurrentId += 1
            else:
                cls.CurrentId = 100
            if id_ not in cls.ReservedIds:
                break
            if cls.CurrentId == start_id:
                raise RuntimeError(
                    "Error: Out of IDs. Recommend shutting down application."
                )

        cls.ReserveId(id_)

        return id_

    @classmethod
    def ReserveId(cls, id_) -> None:
        """Reserve an ID.

        Args:
            id_ (int): The ID to reserve.
        """
        cls.ReservedIds.add(id_)

    @classmethod
    def UnreserveId(cls, id_) -> None:
        """Unreserve an ID.

        Args:
            id_ (int): The ID to unreserve.
        """
        cls.ReservedIds.remove(id_)
