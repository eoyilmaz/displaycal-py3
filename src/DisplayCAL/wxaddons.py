# -*- coding: utf-8 -*-
from time import sleep
import os
import sys
import threading
import types

from DisplayCAL.colormath import specialpow
from DisplayCAL.wxfixes import wx, GenButton, PlateButton, get_dialogs

from DisplayCAL.lib.agw.gradientbutton import GradientButton
from DisplayCAL import floatspin


def AdjustMinMax(self, minvalue=0.0, maxvalue=1.0):
    """Adjust min/max"""
    buffer = self.GetDataBuffer()
    for i, byte in enumerate(buffer):
        buffer[i] = min(int(round(minvalue * 255 + byte * (maxvalue - minvalue))), 255)


wx.Image.AdjustMinMax = AdjustMinMax


def Blend(self, bitmap, x, y):
    """Blend the given bitmap over the specified position in this bitmap."""
    dc = wx.MemoryDC(self)
    dc.DrawBitmap(bitmap, x, y)


wx.Bitmap.Blend = Blend


def Invert(self):
    """Invert image colors"""
    databuffer = self.GetDataBuffer()
    for i, byte in enumerate(databuffer):
        databuffer[i] = 255 - byte


wx.Image.Invert = Invert


def GammaCorrect(self, from_gamma=-2.4, to_gamma=1.8):
    """Gamma correct"""
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
    """Return the real (non-overlapping) client area of a display"""
    # need to fix overlapping ClientArea on some Linux multi-display setups
    # the client area must be always smaller than the geometry
    clientarea = list(self.ClientArea)
    if self.Geometry[0] > clientarea[0]:
        clientarea[0] = self.Geometry[0]
    if self.Geometry[1] > clientarea[1]:
        clientarea[1] = self.Geometry[1]
    if self.Geometry[2] < clientarea[2]:
        clientarea[2] = self.Geometry[2]
    if self.Geometry[3] < clientarea[3]:
        clientarea[3] = self.Geometry[3]
    return wx.Rect(*clientarea)


wx.Display.GetRealClientArea = GetRealClientArea


def GetAllChildren(self, skip=None):
    """Get children of window and its subwindows"""
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
    """Return the display the window is shown on"""
    display_no = wx.Display.GetFromWindow(self)
    if display_no < 0:  # window outside visible area
        display_no = 0
    return wx.Display(display_no)


wx.Window.GetDisplay = GetDisplay


def SetMaxFontSize(self, pointsize=11):
    font = self.GetFont()
    if font.GetPointSize() > pointsize:
        font.SetPointSize(pointsize)
        self.SetFont(font)


wx.Window.SetMaxFontSize = SetMaxFontSize


def RealCenterOnScreen(self, dir=wx.BOTH):
    """Center the window on the screen it is on, unlike CenterOnScreen which
    always centers on 1st screen.

    """
    x, y = self.Position
    left, top, w, h = self.GetDisplay().ClientArea
    if dir & wx.HORIZONTAL:
        x = left + w / 2 - self.Size[0] / 2
    if dir & wx.VERTICAL:
        y = top + h / 2 - self.Size[1] / 2
    self.Position = x, y


wx.TopLevelWindow.RealCenterOnScreen = RealCenterOnScreen


def SetSaneGeometry(self, x=None, y=None, w=None, h=None):
    """Set a 'sane' window position and/or size (within visible screen area)."""
    if None not in (x, y):
        # First, move to coordinates given
        self.SetPosition((x, y))
    # Returns the first display's client area if the window
    # is completely outside the client area of all displays
    display_client_rect = self.GetDisplay().ClientArea
    if sys.platform not in ("darwin", "win32"):  # Linux
        if os.getenv("XDG_SESSION_TYPE") == "wayland":
            # Client-side decorations
            safety_margin = 0
        else:
            # Assume server-side decorations
            safety_margin = 40
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
    if None not in (x, y):
        if not display_client_rect.ContainsXY(
            x, y
        ) or not display_client_rect.ContainsRect((x, y, self.Size[0], self.Size[1])):
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
    by chosing individual cells.

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
    """Return the selected rows, even if not all cells in a row are selected."""
    rows = []
    i = -1
    for row, _col in self.GetSelection():
        if row > i:
            i = row
            rows.append(row)
    return rows


wx.grid.Grid.GetSelectionRows = GridGetSelectionRows


def IsSizer(self):
    """Check if the window is a sizer"""
    return isinstance(self, wx.Sizer)


wx.Window.IsSizer = IsSizer


def gamma_encode(R, G, B, alpha=wx.ALPHA_OPAQUE):
    """(Re-)Encode R'G'B' colors with specific platform gamma.

    R, G, B = color components in range 0..255

    Note this only has effect under wxMac which assumes a decoding gamma of 1.8

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
    else:
        return [R, G, B, alpha]


def get_platform_window_decoration_size():
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
    """Draw a granger rainbow to a DC"""
    if not isinstance(dc, wx.GCDC):
        raise NotImplementedError("%s lacks alpha transparency support" % dc.__class__)

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
    """Create a granger rainbow bitmap"""
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
    else:
        return bmp


def get_parent_frame(window):
    """Get parent frame (if any)"""
    parent = window.Parent
    while parent:
        if isinstance(parent, wx.Frame):
            return parent
        parent = parent.Parent


class CustomEvent(wx.PyEvent):
    def __init__(self, typeId, object, window=None):
        wx.PyEvent.__init__(self, object.GetId(), typeId)
        self.EventObject = object
        self.Window = window

    def GetWindow(self):
        return self.Window


_global_timer_lock = threading.Lock()


wxEVT_BETTERTIMER = wx.NewEventType()
EVT_BETTERTIMER = wx.PyEventBinder(wxEVT_BETTERTIMER, 1)


class BetterTimerEvent(wx.PyCommandEvent):
    def __init__(self, id=wx.ID_ANY, ms=0):
        wx.PyCommandEvent.__init__(self, wxEVT_BETTERTIMER, id)
        self._ms = ms

    def GetInterval(self):
        return self._ms

    Interval = property(GetInterval)


class BetterTimer(wx.Timer):
    """A wx.Timer replacement.

    Doing GUI updates using regular timers can be incredibly segfaulty under
    wxPython Phoenix when several timers run concurrently.

    This approach uses a global lock to work around the issue.

    """

    def __init__(self, owner=None, timerid=wx.ID_ANY):
        wx.Timer.__init__(self, None, timerid)
        self._owner = owner

    def Notify(self):
        if self._owner and _global_timer_lock.acquire(False):
            try:
                wx.PostEvent(self._owner, BetterTimerEvent(self.Id, self.Interval))
            finally:
                _global_timer_lock.release()


class BetterCallLater(wx.CallLater):
    def __init__(self, millis, callableObj, *args, **kwargs):
        wx.CallLater.__init__(self, millis, callableObj, *args, **kwargs)

    def Notify(self):
        if _global_timer_lock.acquire(True):
            try:
                wx.CallLater.Notify(self)
            finally:
                _global_timer_lock.release()


class ThreadedTimer:
    """A wx.Timer replacement that uses threads instead of actual timers
    which are a limited resource"""

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
        if _global_timer_lock.acquire(self._oneshot):
            try:
                self.Notify()
            finally:
                _global_timer_lock.release()

    def _timer(self):
        self._keep_running = True
        while self._keep_running:
            sleep(self._ms / 1000.0)
            if self._keep_running:
                wx.CallAfter(self._notify)
                if self._oneshot:
                    self._keep_running = False

    def Destroy(self):
        if hasattr(wx.Window, "UnreserveControlId") and self.Id < 0:
            try:
                wx.Window.UnreserveControlId(self.Id)
            except wx.wxAssertionError:
                pass

    def GetId(self):
        return self._id

    def GetInterval(self):
        return self._ms

    def GetOwner(self):
        return self._owner

    def SetOwner(self, owner):
        self._owner = owner

    Id = property(GetId)
    Interval = property(GetInterval)
    Owner = property(GetOwner, SetOwner)

    def IsOneShot(self):
        return self._oneshot

    def IsRunning(self):
        return self._keep_running

    def Notify(self):
        if self._owner:
            self._owner.ProcessEvent(BetterTimerEvent(self._id, self._ms))

    def Start(self, milliseconds=-1, oneShot=False):
        if self._thread and self._thread.is_alive():
            self._keep_running = False
            self._thread.join()
        if milliseconds > -1:
            self._ms = milliseconds
        self._oneshot = oneShot
        self._thread = threading.Thread(target=self._timer, name="ThreadedTimer")
        self._thread.start()

    def Stop(self):
        self._keep_running = False


class ThreadedCallLater(ThreadedTimer):
    def __init__(self, millis, callableObj, *args, **kwargs):
        ThreadedTimer.__init__(self)
        self._oneshot = True
        self._callable = callableObj
        self._has_run = False
        self._result = None
        self.SetArgs(*args, **kwargs)
        self.Start(millis)

    def GetResult(self):
        return self._result

    Result = property(GetResult)

    def HasRun(self):
        return self._has_run

    def Notify(self):
        self._result = self._callable(*self._args, **self._kwargs)
        self._has_run = True

    def SetArgs(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs

    def Start(self, millis=None, *args, **kwargs):
        if args:
            self._args = args
        if kwargs:
            self._kwargs = kwargs
        ThreadedTimer.Start(self, millis, True)

    Restart = Start


class BetterWindowDisabler:
    """Also disables child windows instead of only top level windows. This is
    actually needed under Mac OS X where disabling a top level window will
    not prevent interaction with its children.

    If toplevelparent is given, disable only this window and its child windows.

    """

    windows = set()

    def __init__(self, skip=None, toplevelparent=None, include_menus=False):
        self._windows = []
        self.skip = skip
        self.toplevelparent = toplevelparent
        self.include_menus = include_menus
        self.disable()

    def __del__(self):
        self.enable()

    def disable(self):
        self.enable(False)

    def enable(self, enable=True):
        if not enable:
            skip = self.skip or []
            if skip:
                if not isinstance(skip, (list, tuple)):
                    skip = [skip]
            if self.toplevelparent:
                toplevel = [self.toplevelparent]
            else:
                toplevel = list(wx.GetTopLevelWindows())
            for w in toplevel:
                if (
                    w
                    and w not in skip
                    and "Inspection" not in "%s" % w
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
                    if self.include_menus:
                        menubar = w.GetMenuBar()
                        if menubar:
                            for menu, _label in menubar.GetMenus():
                                for item in menu.GetMenuItems():
                                    self._windows.append(item)

            def Enable(w_, enable=True):
                w_._BetterWindowDisabler_enabled = enable

            def Disable(w_):
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

        for w in self._windows:
            BetterWindowDisabler.windows.remove(w)
            if w:
                if hasattr(w, "_BetterWindowDisabler_Disable"):
                    w.Disable = w._BetterWindowDisabler_Disable
                if hasattr(w, "_BetterWindowDisabler_Enable"):
                    w.Enable = w._BetterWindowDisabler_Enable
                if hasattr(w, "_BetterWindowDisabler_enabled"):
                    w.Enable(w._BetterWindowDisabler_enabled)


class CustomGridCellEvent(CustomEvent):
    def __init__(self, typeId, object, row=-1, col=-1, window=None):
        CustomEvent.__init__(self, typeId, object, window)
        self.Row = row
        self.Col = col

    def GetRow(self):
        return self.Row

    def GetCol(self):
        return self.Col


class PopupMenu:
    """A collection of menus that has a wx.MenuBar-like interface."""

    def __init__(self, parent):
        self.Parent = parent
        self.TopLevelParent = parent.TopLevelParent
        self._menus = []
        self._enabledtop = {}

    def Append(self, menu, title):
        self._menus.append((menu, title))

    def EnableTop(self, pos, enable=True):
        self._enabledtop[pos] = enable

    def FindItemById(self, id):
        for menu, _label in self._menus:
            item = menu.FindItemById(id)
            if item:
                return item

    def FindMenu(self, title):
        for i, (_menu, label) in enumerate(self._menus):
            if title == label:
                return i
        return wx.NOT_FOUND

    def GetMenu(self, index):
        return self._menus[index][0]

    def GetMenuCount(self):
        return len(self._menus)

    def GetMenus(self):
        """Return menus.

        Returns:
            List[wx.Menu]: List of child menus.
        """
        return list(self._menus)

    def SetMenus(self, menus):
        """Set menus.

        Args:
            menus (List[wx.Menu]): A list of wx.Menu instances to set as a
                child of this menubar.
        """
        self._menus = []
        for menu, label in menus:
            self.Append((menu, label))

    Menus = property(GetMenus, SetMenus)

    def IsEnabledTop(self, pos):
        return self._enabledtop.get(pos, True)

    def SetMenuLabel(self, pos, label):
        self._menus[pos] = (self._menus[pos][0], label)

    def bind_keys(self):
        if sys.platform == "darwin":
            accels = self.get_accelerator_entries()
            self.TopLevelParent.SetAcceleratorTable(wx.AcceleratorTable(accels()))
        else:
            self.TopLevelParent.Bind(wx.EVT_CHAR_HOOK, self.key_handler)

    def get_accelerator_entries(self):
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
        """Handle accelerator keys"""
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
        """Popup the list of menus (with actual menus as submenus)"""

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
    def __init__(self, drophandlers=None):
        wx.FileDropTarget.__init__(self)
        if drophandlers is None:
            drophandlers = {}
        self.drophandlers = drophandlers
        self.unsupported_handler = None

    def OnDropFiles(self, x, y, filenames):
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
    ReservedIds = set()

    @classmethod
    def NewId(cls):
        """Replacement for wx.NewId()"""
        start_id = cls.CurrentId

        while True:
            # Skip the part of IDs space that contains hard-coded values
            if cls.CurrentId == wx.ID_LOWEST:
                cls.CurrentId = wx.ID_HIGHEST + 1
            id = cls.CurrentId
            if id < 30095:
                cls.CurrentId += 1
            else:
                cls.CurrentId = 100
            if id not in cls.ReservedIds:
                break
            elif cls.CurrentId == start_id:
                raise RuntimeError(
                    "Error: Out of IDs. Recommend shutting down application."
                )

        cls.ReserveId(id)

        return id

    @classmethod
    def ReserveId(cls, id):
        cls.ReservedIds.add(id)

    @classmethod
    def UnreserveId(cls, id):
        cls.ReservedIds.remove(id)
