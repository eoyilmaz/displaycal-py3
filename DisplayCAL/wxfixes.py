# -*- coding: utf-8 -*-

import os
import platform
import re
import shutil
import sys
import tempfile

from DisplayCAL.meta import name as appname, wx_minversion

if os.getenv("GTK_CSD", "0") != "0":
    # Work-around double window decorations, see
    # https://hub.displaycal.net/issue/17331/
    os.environ["GTK_CSD"] = "0"

# wxversion will be removed in Phoenix
try:
    from DisplayCAL import wxversion
except ImportError:
    pass
else:
    if not getattr(sys, "frozen", False) and "wx" not in sys.modules:
        try:
            wxversion.select(["4.0", "3.0", "%i.%i.%i" % wx_minversion[:3]])
        except wxversion.VersionError:
            pass

from wx import __version__ as wx_version
import wx

if wx.VERSION < wx_minversion:
    app = wx.GetApp() or wx.App(0)
    result = wx.MessageBox(
        "This application requires a version of wxPython "
        "greater than or equal to {}, but your most recent "
        "version is {}.\n\n"
        "Would you like to download a new version of wxPython?\n".format(
            ".".join(str(n) for n in wx_minversion), wx.__version__
        ),
        "wxPython Upgrade Needed",
        style=wx.YES_NO,
    )
    if result == wx.YES:
        import webbrowser

        webbrowser.open("http://wxpython.org/")
    app.MainLoop()
    sys.exit()
import wx.grid
from wx.lib.buttons import GenBitmapButton as _GenBitmapButton
from wx.lib.buttons import ThemedGenButton as _ThemedGenButton
from wx.lib.buttons import GenBitmapTextButton as _GenBitmapTextButton
from wx.lib.scrolledpanel import ScrolledPanel
from wx.lib import platebtn
from wx import xrc

from DisplayCAL.colormath import convert_range


if not hasattr(wx.Window, "HasFocus"):
    # wxPython < 3.0
    wx.Window.HasFocus = lambda self: self.FindFocus() is self


if not hasattr(wx, "wxAssertionError"):
    # wxPython < 4.0
    wx.wxAssertionError = wx.PyAssertionError


if not hasattr(platebtn, "PB_STYLE_TOGGLE"):
    platebtn.PB_STYLE_TOGGLE = 32


if not hasattr(platebtn, "PB_STYLE_DROPARROW"):
    platebtn.PB_STYLE_DROPARROW = 16


if "phoenix" in wx.PlatformInfo:
    # Phoenix compatibility

    from wx.lib.agw import aui
    from wx.lib import embeddedimage
    import wx.adv

    # Deprecated items

    wx.DEFAULT = wx.FONTFAMILY_DEFAULT
    wx.DECORATIVE = wx.FONTFAMILY_DECORATIVE
    wx.ROMAN = wx.FONTFAMILY_ROMAN
    wx.SCRIPT = wx.FONTFAMILY_SCRIPT
    wx.SWISS = wx.FONTFAMILY_SWISS
    wx.MODERN = wx.FONTFAMILY_MODERN
    wx.TELETYPE = wx.FONTFAMILY_TELETYPE

    wx.NORMAL = int(float(wx.FONTWEIGHT_NORMAL | wx.FONTSTYLE_NORMAL) / 100) * 100
    wx.LIGHT = wx.FONTWEIGHT_LIGHT
    wx.BOLD = wx.FONTWEIGHT_BOLD

    wx.ITALIC = wx.FONTSTYLE_ITALIC
    wx.SLANT = wx.FONTSTYLE_SLANT

    wx.SOLID = wx.PENSTYLE_SOLID | wx.BRUSHSTYLE_SOLID
    wx.DOT = wx.PENSTYLE_DOT
    wx.LONG_DASH = wx.PENSTYLE_LONG_DASH
    wx.SHORT_DASH = wx.PENSTYLE_SHORT_DASH
    wx.DOT_DASH = wx.PENSTYLE_DOT_DASH
    wx.USER_DASH = wx.PENSTYLE_USER_DASH
    wx.TRANSPARENT = wx.PENSTYLE_TRANSPARENT | wx.BRUSHSTYLE_TRANSPARENT

    wx.STIPPLE_MASK_OPAQUE = wx.BRUSHSTYLE_STIPPLE_MASK_OPAQUE
    wx.STIPPLE_MASK = wx.BRUSHSTYLE_STIPPLE_MASK
    wx.STIPPLE = wx.BRUSHSTYLE_STIPPLE
    wx.BDIAGONAL_HATCH = wx.BRUSHSTYLE_BDIAGONAL_HATCH
    wx.CROSSDIAG_HATCH = wx.BRUSHSTYLE_CROSSDIAG_HATCH
    wx.FDIAGONAL_HATCH = wx.BRUSHSTYLE_FDIAGONAL_HATCH
    wx.CROSS_HATCH = wx.BRUSHSTYLE_CROSS_HATCH
    wx.HORIZONTAL_HATCH = wx.BRUSHSTYLE_HORIZONTAL_HATCH
    wx.VERTICAL_HATCH = wx.BRUSHSTYLE_VERTICAL_HATCH

    embeddedimage.PyEmbeddedImage.getBitmap = embeddedimage.PyEmbeddedImage.GetBitmap

    def BitmapFromIcon(icon):
        bmp = wx.Bitmap()
        bmp.CopyFromIcon(icon)
        return bmp

    def IconFromBitmap(bmp):
        icon = wx.Icon()
        icon.CopyFromBitmap(bmp)
        return bmp

    wx.BitmapFromIcon = BitmapFromIcon
    wx.CursorFromImage = wx.Cursor
    wx.EmptyBitmap = wx.Bitmap
    wx.EmptyBitmapRGBA = (
        lambda width, height, red=0, green=0, blue=0, alpha=0: wx.Bitmap.FromRGBA(
            width, height, red, green, blue, alpha
        )
    )
    wx.EmptyIcon = wx.Icon
    wx.IconFromBitmap = wx.Icon
    wx.ImageFromStream = wx.Image
    wx.ListCtrl.InsertStringItem = lambda self, index, label: self.InsertItem(
        int(index), str(label)
    )
    wx.ListCtrl.SetStringItem = lambda self, index, col, label: self.SetItem(
        int(index), int(col), str(label)
    )
    wx.Menu.RemoveItem = lambda self, item: self.Remove(item)
    wx.NamedColour = wx.Colour
    wx.PyControl = wx.Control
    wx.PyWindow = wx.Window
    wx.PyPanel = wx.Panel
    wx.StockCursor = wx.Cursor
    wx.Window.SetToolTipString = wx.Window.SetToolTip

    # Moved items

    wx.HL_DEFAULT_STYLE = wx.adv.HL_DEFAULT_STYLE
    wx.HyperlinkCtrl = wx.adv.HyperlinkCtrl
    wx.HyperlinkCtrlNameStr = wx.adv.HyperlinkCtrlNameStr

    wx.SOUND_ASYNC = wx.adv.SOUND_ASYNC
    wx.Sound = wx.adv.Sound

    wx.wxEVT_TASKBAR_BALLOON_CLICK = wx.adv.wxEVT_TASKBAR_BALLOON_CLICK
    wx.wxEVT_TASKBAR_BALLOON_TIMEOUT = wx.adv.wxEVT_TASKBAR_BALLOON_TIMEOUT
    wx.wxEVT_TASKBAR_CLICK = wx.adv.wxEVT_TASKBAR_CLICK
    wx.wxEVT_TASKBAR_LEFT_DCLICK = wx.adv.wxEVT_TASKBAR_LEFT_DCLICK
    wx.wxEVT_TASKBAR_LEFT_DOWN = wx.adv.wxEVT_TASKBAR_LEFT_DOWN
    wx.wxEVT_TASKBAR_LEFT_UP = wx.adv.wxEVT_TASKBAR_LEFT_UP
    wx.wxEVT_TASKBAR_MOVE = wx.adv.wxEVT_TASKBAR_MOVE
    wx.wxEVT_TASKBAR_RIGHT_DOWN = wx.adv.wxEVT_TASKBAR_RIGHT_DOWN
    wx.wxEVT_TASKBAR_RIGHT_UP = wx.adv.wxEVT_TASKBAR_RIGHT_UP
    wx.wxEVT_TASKBAR_RIGHT_DCLICK = wx.adv.wxEVT_TASKBAR_RIGHT_DCLICK

    wx.EVT_TASKBAR_BALLOON_CLICK = wx.adv.EVT_TASKBAR_BALLOON_CLICK
    wx.EVT_TASKBAR_BALLOON_TIMEOUT = wx.adv.EVT_TASKBAR_BALLOON_TIMEOUT
    wx.EVT_TASKBAR_CLICK = wx.adv.EVT_TASKBAR_CLICK
    wx.EVT_TASKBAR_LEFT_DCLICK = wx.adv.EVT_TASKBAR_LEFT_DCLICK
    wx.EVT_TASKBAR_LEFT_DOWN = wx.adv.EVT_TASKBAR_LEFT_DOWN
    wx.EVT_TASKBAR_LEFT_UP = wx.adv.EVT_TASKBAR_LEFT_UP
    wx.EVT_TASKBAR_MOVE = wx.adv.EVT_TASKBAR_MOVE
    wx.EVT_TASKBAR_RIGHT_DOWN = wx.adv.EVT_TASKBAR_RIGHT_DOWN
    wx.EVT_TASKBAR_RIGHT_UP = wx.adv.EVT_TASKBAR_RIGHT_UP
    wx.EVT_TASKBAR_RIGHT_DCLICK = wx.adv.EVT_TASKBAR_RIGHT_DCLICK

    # Removed items
    wx.IconBundle.AddIconFromFile = (
        lambda file, type=wx.BITMAP_TYPE_ANY: wx.IconBundle.AddIcon(file, type)
    )

    def ContainsRect(self, *args):
        if len(args) > 1:
            rect = wx.Rect(*args)
        else:
            rect = args[0]
        return self.Contains(rect)

    wx.Rect.ContainsRect = ContainsRect
    wx.Rect.ContainsXY = lambda self, x, y: self.Contains((x, y))
    wx.RectPS = wx.Rect
    wx.RegionFromBitmap = wx.Region

    def GetItemIndex(self, window):
        for index, sizeritem in enumerate(self.Children):
            if sizeritem.Window == window:
                return index

    wx.Sizer.GetItemIndex = GetItemIndex
    wx.TopLevelWindow.Restore = lambda self: self.Iconize(False)

    # Renamed items

    wx.OPEN = wx.FD_OPEN
    wx.OVERWRITE_PROMPT = wx.FD_OVERWRITE_PROMPT
    wx.SAVE = wx.FD_SAVE

    wx.SystemSettings_GetColour = wx.SystemSettings.GetColour
    wx.SystemSettings_GetFont = wx.SystemSettings.GetFont
    wx.SystemSettings_GetMetric = wx.SystemSettings.GetMetric
    wx.grid.EVT_GRID_CELL_CHANGE = wx.grid.EVT_GRID_CELL_CHANGED
    if hasattr(wx.grid.Grid, "GridSelectRows"):
        # wxPython Phoenix 4.0.0a
        wx.grid.Grid.wxGridSelectRows = wx.grid.Grid.GridSelectRows
    else:
        # wxPython Phoenix 4.0.0b
        wx.grid.Grid.wxGridSelectRows = wx.grid.Grid.SelectRows
    wx.grid.PyGridCellEditor = wx.grid.GridCellEditor
    wx.grid.PyGridCellRenderer = wx.grid.GridCellRenderer
    wx.RegionFromBitmapColour = wx.Region

    # Bugfixes

    if not hasattr(wx.grid.GridEvent, "CmdDown"):
        # This may be a bug in the current development version of Phoenix
        wx.grid.GridEvent.CmdDown = lambda self: False

    # Not sure if this is a bug, but the PositionToXY signature differs from
    # current Phoenix docs. Actual return value is a 3-tuple, not a 2-tuple:
    # (bool inrange, int col, int line)
    PositionToXY = wx.TextCtrl.PositionToXY
    wx.TextCtrl.PositionToXY = lambda self, pos: PositionToXY(self, pos)[1:]

    def TabFrame__init__(self, parent):
        pre = wx.Window.__init__(self)

        self._tabs = None
        self._rect = wx.Rect(0, 0, 200, 200)
        self._tab_ctrl_height = 20
        self._tab_rect = wx.Rect()
        self._parent = parent

        # With Phoenix, the TabFrame is unintentionally visible in the top left
        # corner (horizontal and vertical lines with a length of 20px each that
        # are lighter than the border color if tabs are at the top, or a
        # 20x20px square if tabs are at the bottom). Setting its size to 0, 0
        # prevents this. Also see https://github.com/RobinD42/Phoenix/pull/91
        self.Create(parent, size=(0, 0))

    aui.TabFrame.__init__ = TabFrame__init__


wx._ListCtrl = wx.ListCtrl
wx._SpinCtrl = wx.SpinCtrl
wx._StaticText = wx.StaticText
if "gtk3" in wx.PlatformInfo:
    # GTK3 fixes

    class wx_Panel(wx.Panel):
        # Fix panel background color not working under wxGTK3
        def __init__(self, *args, **kwargs):
            if not args and hasattr(wx, "PreFrame"):
                pre = wx.PrePanel()
                self.PostCreate(pre)
                self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
            else:
                wx.Panel.__init__(self, *args, **kwargs)
                self.OnCreate(None)

        def OnCreate(self, event):
            self.Unbind(wx.EVT_WINDOW_CREATE)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        def OnEraseBackground(self, event):
            dc = event.GetDC()
            rect = self.GetClientRect()
            dc.SetClippingRegion(rect.x, rect.y, rect.width, rect.height)
            bgcolor = self.BackgroundColour
            dc.SetBrush(wx.Brush(bgcolor, wx.SOLID))
            dc.SetPen(wx.Pen(bgcolor, wx.SOLID))
            dc.DrawRectangle(*rect)

    from wx import dataview

    DataViewListCtrl = dataview.DataViewListCtrl

    class ListCtrl(DataViewListCtrl):
        # Implement ListCtrl as DataViewListCtrl
        # Works around header rendering ugliness with GTK3

        def __init__(
            self,
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=wx.LC_ICON,
            validator=wx.DefaultValidator,
            name=wx.ListCtrlNameStr,
        ):
            dv_style = 0
            if style & wx.LC_SINGLE_SEL:
                dv_style |= dataview.DV_SINGLE
            DataViewListCtrl.__init__(self, parent, id, pos, size, dv_style, validator)
            self.Name = name
            self._columns = {}
            self._items = {}
            self.Bind(dataview.EVT_DATAVIEW_SELECTION_CHANGED, self.OnEvent)
            self.Bind(dataview.EVT_DATAVIEW_ITEM_ACTIVATED, self.OnEvent)

        def OnEvent(self, event):
            typeId = event.GetEventType()
            if typeId == dataview.EVT_DATAVIEW_SELECTION_CHANGED.typeId:
                if self.GetSelectedRow() != wx.NOT_FOUND:
                    typeId = wx.EVT_LIST_ITEM_SELECTED.typeId
                else:
                    typeId = wx.EVT_LIST_ITEM_DESELECTED.typeId
                event = wx.ListEvent(typeId, self.Id)
            elif typeId == dataview.EVT_DATAVIEW_ITEM_ACTIVATED.typeId:
                event = wx.ListEvent(wx.EVT_LIST_ITEM_ACTIVATED.typeId, self.Id)
            event.SetEventObject(self)
            self.GetEventHandler().ProcessEvent(event)

        def InsertColumn(self, pos, col):
            self._columns[pos] = col

        def SetColumnWidth(self, pos, width):
            self.AppendTextColumn(self._columns[pos], width=int(width))

        def InsertStringItem(self, row, label):
            self._items[row] = []
            return row

        def SetStringItem(self, row, col, label):
            self._items[row].append(label)
            if len(self._items[row]) == len(self._columns):
                # Row complete
                DataViewListCtrl.InsertItem(self, row, self._items[row])

        def GetItem(self, row, col=0):
            item = self.RowToItem(row)
            item.GetId = lambda: row
            item.GetText = lambda: self.GetTextValue(row, col)
            return item

        def SetItemState(self, row, state, stateMask):
            if state == stateMask == wx.LIST_STATE_SELECTED:
                self.SelectRow(row)
            else:
                raise NotImplementedError(
                    "SetItemState is only implemented for selecting a single row"
                )

        def GetNextItem(
            self, row, geometry=wx.LIST_NEXT_ALL, state=wx.LIST_STATE_DONTCARE
        ):
            if (
                row == -1
                and geometry == wx.LIST_NEXT_ALL
                and state == wx.LIST_STATE_SELECTED
            ):
                return self.GetSelectedRow()
            else:
                raise NotImplementedError(
                    "GetNextItem is only implemented for returning the selected row"
                )

        def GetItemCount(self):
            return len(self._items)

        GetFirstSelected = DataViewListCtrl.__dict__["GetSelectedRow"]

        def GetItemState(self, row, stateMask):
            if stateMask == wx.LIST_STATE_SELECTED:
                if self.GetSelectedRow() == row:
                    return wx.LIST_STATE_SELECTED
                else:
                    return 0
            else:
                raise NotImplementedError(
                    "GetItemState is only implemented to check if a row is selected"
                )

        def Select(self, row, on=1):
            if on:
                self.SelectRow(row)
            else:
                self.UnselectRow(row)

    wx.ListCtrl = ListCtrl

    class SpinCtrl(wx._SpinCtrl):
        _spinwidth = 0

        def __init__(
            self,
            parent,
            id=wx.ID_ANY,
            value="",
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=wx.SP_ARROW_KEYS,
            min=0,
            max=100,
            initial=0,
            name="wxSpinCtrl",
        ):
            if size[0] != -1:
                # Adjust initial size for GTK3 to accomodate spin buttons
                if not SpinCtrl._spinwidth:
                    spin = wx.SpinCtrl(parent, -1)
                    text = wx.TextCtrl(parent, -1)
                    SpinCtrl._spinwidth = spin.Size[0] - text.Size[0] + 11
                    spin.Destroy()
                    text.Destroy()
                size = size[0] + SpinCtrl._spinwidth, size[1]
            wx._SpinCtrl.__init__(
                self, parent, id, value, pos, size, style, min, max, initial, name
            )

    wx.SpinCtrl = SpinCtrl

    _StaticText_SetLabel = wx._StaticText.SetLabel

    class StaticText(wx._StaticText):
        def __init__(self, *args, **kwargs):
            wx._StaticText.__init__(self, *args, **kwargs)

        def SetFont(self, font):
            wx.Control.SetFont(self, font)
            self.SetLabel(self.Label)

        def SetLabel(self, label):
            # Fix GTK3 label auto-resize on label change not working
            if not self.WindowStyle & wx.ST_NO_AUTORESIZE:
                self.MaxSize = -1, -1
                self.MinSize = -1, -1
            _StaticText_SetLabel(self, label)
            if not self.WindowStyle & wx.ST_NO_AUTORESIZE:
                # Find widest line
                max_width = 0
                for line in label.splitlines():
                    width = self.GetTextExtent(line)[0]
                    if width > max_width:
                        max_width = width
                self.Size = max_width, -1
                self.MaxSize = self.Size[0], -1

        def Wrap(self, width):
            wx._StaticText.Wrap(self, int(width))
            self.SetLabel(self.Label)

        Label = property(lambda self: self.GetLabel(), SetLabel)

    wx.StaticText = StaticText
else:
    wx_Panel = wx.Panel


wx.AnyButton._SetBitmapLabel = wx.AnyButton.SetBitmapLabel

def SetBitmapLabel(self, bitmap):
    """Override the SetBitmapLabel to avoid flickering."""
    if self.GetBitmapLabel() != bitmap:
        self._SetBitmapLabel(self, bitmap)

wx.AnyButton.SetBitmapLabel = SetBitmapLabel


def BitmapButtonEnable(self, enable=True):
    """Replacement for BitmapButton.Enable which circumvents repainting issues

    (bitmap does not change on button state change)

    """
    wx.Button.Enable(self, enable)
    if not hasattr(self, "_bitmaplabel"):
        self._bitmaplabel = self.GetBitmapLabel()
    if not hasattr(self, "_bitmapdisabled"):
        self._bitmapdisabled = self.GetBitmapDisabled()
    if enable:
        if self._bitmaplabel.IsOk():
            self.SetBitmapLabel(self._bitmaplabel)
    else:
        if self._bitmapdisabled.IsOk():
            self.SetBitmapLabel(self._bitmapdisabled)


def BitmapButtonDisable(self):
    """Replacement for BitmapButton.Disable which circumvents repainting issues

    (bitmap does not change on button state change)

    """
    self.Enable(False)


if "phoenix" not in wx.PlatformInfo:
    wx.BitmapButton.Enable = BitmapButtonEnable
    wx.BitmapButton.Disable = BitmapButtonDisable


def FindMenuItem(self, label):
    """Replacement for wx.Menu.FindItem"""
    label = GTKMenuItemGetFixedLabel(label)
    for menuitem in self.GetMenuItems():
        try:
            fixed_label = GTKMenuItemGetFixedLabel(menuitem.Label)
        except AttributeError:
            # wxPython 4.1.0+
            fixed_label = GTKMenuItemGetFixedLabel(menuitem.GetItemLabelText())
        if fixed_label == label:
            return menuitem.GetId()


wx.Menu.FindItem = FindMenuItem


def GTKMenuItemGetFixedLabel(label):
    if sys.platform not in ("darwin", "win32"):
        # The underscore is a special character under GTK, like the
        # ampersand on Mac OS X and Windows
        # Recent wxPython versions already do the right thing, but we need
        # this workaround for older releases
        if "__" in label:
            label = label.replace("__", "_")
        while label and label[0] == "_":
            label = label[1:]
    return label


if not hasattr(wx.Sizer, "GetItemIndex"):

    def GetItemIndex(self, item):
        for i, child in enumerate(list(self.GetChildren())):
            if child.GetWindow() is item:
                return i
        return -1

    wx.Sizer.GetItemIndex = GetItemIndex


def set_maxsize(window, maxsize):
    window.MaxSize = maxsize


if os.getenv("XDG_SESSION_TYPE") == "wayland":
    # Fix erroneous extra spacing around window contents under Wayland

    is_first_toplevel_window = True

    def fix_wayland_window_size(window):
        global is_first_toplevel_window
        if is_first_toplevel_window:
            # Not needed for first toplevel window
            is_first_toplevel_window = False
        else:
            window.MaxSize = window.Size
            wx.CallAfter(set_maxsize, window, (-1, -1))

    def TopLevelWindow_Show(self, show=True):
        if show and not self.IsShown():
            fix_wayland_window_size(self)
        return _TopLevelWindow_Show(self, show)

    _TopLevelWindow_Show = wx.TopLevelWindow.Show
    wx.TopLevelWindow.Show = TopLevelWindow_Show

    # ~ def Dialog_ShowModal(self):
    # ~ fix_wayland_window_size(self)
    # ~ return _Dialog_ShowModal(self)

    # ~ _Dialog_ShowModal = wx.Dialog.ShowModal
    # ~ wx.Dialog.ShowModal = Dialog_ShowModal

    def Sizer_SetSizeHints(self, window):
        if isinstance(window, wx.Dialog):
            window.MaxSize = (-1, -1)
        _Sizer_SetSizeHints(self, window)

    _Sizer_SetSizeHints = wx.Sizer.SetSizeHints
    wx.Sizer.SetSizeHints = Sizer_SetSizeHints

    def Sizer_Layout(self):
        _Sizer_Layout(self)
        window = self.GetContainingWindow()
        if isinstance(window, wx.Dialog):
            window.MaxSize = window.Size

    _Sizer_Layout = wx.Sizer.Layout
    wx.Sizer.Layout = Sizer_Layout


if sys.platform == "darwin":
    # wxMac seem to lose the foreground color of StaticText
    # when enabled again

    @property
    def StaticTextEnabled(self):
        return self.IsEnabled()

    @StaticTextEnabled.setter
    def StaticTextEnabled(self, enable=True):
        self.Enable(enable)

    wx.StaticText.Enabled = StaticTextEnabled

    def StaticTextDisable(self):
        self.Enable(False)

    wx.StaticText.Disable = StaticTextDisable

    def StaticTextEnable(self, enable=True):
        enable = bool(enable)
        if self.Enabled is enable:
            return
        self._enabled = enable
        if not hasattr(self, "_fgcolor"):
            self._fgcolor = self.ForegroundColour
        color = self._fgcolor
        if not enable:
            bgcolor = self.Parent.BackgroundColour
            bgblend = 0.5
            blend = 0.5
            color = wx.Colour(
                int(round(bgblend * bgcolor.Red() + blend * color.Red())),
                int(round(bgblend * bgcolor.Green() + blend * color.Green())),
                int(round(bgblend * bgcolor.Blue() + blend * color.Blue())),
            )
        self.ForegroundColour = color

    wx.StaticText.Enable = StaticTextEnable

    def StaticTextIsEnabled(self):
        return getattr(self, "_enabled", True)

    wx.StaticText.IsEnabled = StaticTextIsEnabled


wx.Window._SetToolTipString = wx.Window.SetToolTipString


def SetToolTipString(self, string):
    """Replacement for SetToolTipString which updates correctly"""
    wx.Window.SetToolTip(self, None)
    wx.Window._SetToolTipString(self, string)


wx.Window.SetToolTipString = SetToolTipString


def _adjust_sizer_args_scaling_for_appdpi(*args, **kwargs):
    from DisplayCAL.config import get_default_dpi, getcfg

    scale = getcfg("app.dpi") / get_default_dpi()
    if "border" in kwargs:
        kwargs["border"] = int(kwargs["border"])

    if scale > 1:
        args = list(args)
        if kwargs.get("border"):
            kwargs["border"] = int(round(kwargs["border"] * scale))
        elif "border" not in kwargs:
            if (
                isinstance(args[0], (tuple, wx.Size, wx.Sizer, wx.Window))
                and len(args) > 3
                and args[3]
            ):
                # item, proportion, flag, border, ...
                args[3] = int(round(args[3] * scale))
            elif isinstance(args[0], int) and len(args) > 4 and args[4]:
                # width, height, proportion, flag, border, ...
                args[4] = int(round(args[4] * scale))
        if args and isinstance(args[0], (tuple, wx.Size)):
            spacer = list(args[0])
            # print(spacer, '->')
            for i, dimension in enumerate(spacer):
                if dimension > 0:
                    spacer[i] = int(round(dimension * scale))
            # print(spacer)
            args = [tuple(spacer)] + args[1:]
    return args, kwargs


wx._Sizer = wx.Sizer


class Sizer(wx._Sizer):
    def Add(self, *args, **kwargs):
        args, kwargs = _adjust_sizer_args_scaling_for_appdpi(*args, **kwargs)
        return wx._Sizer.Add(self, *args, **kwargs)

    def Insert(self, index, *args, **kwargs):
        args, kwargs = _adjust_sizer_args_scaling_for_appdpi(*args, **kwargs)
        return wx._Sizer.Insert(self, index, *args, **kwargs)


wx.Sizer = Sizer


wx._BoxSizer = wx.BoxSizer


class BoxSizer(wx._BoxSizer):
    Add = Sizer.__dict__["Add"]
    Insert = Sizer.__dict__["Insert"]


wx.BoxSizer = BoxSizer


wx._GridSizer = wx.GridSizer


class GridSizer(wx._GridSizer):
    def __init__(self, rows=0, cols=0, vgap=0, hgap=0):
        if vgap or hgap:
            from DisplayCAL.config import get_default_dpi, getcfg

            scale = getcfg("app.dpi") / get_default_dpi()
            if scale > 1:
                # print(vgap, hgap, '->')
                vgap, hgap = [int(round(v * scale)) for v in (vgap, hgap)]
            # print(vgap, hgap)
        super(GridSizer, self).__init__(rows, cols, vgap, hgap)

    Add = Sizer.__dict__["Add"]
    Insert = Sizer.__dict__["Insert"]


wx.GridSizer = GridSizer


wx._FlexGridSizer = wx.FlexGridSizer


class FlexGridSizer(wx._FlexGridSizer):
    def __init__(self, rows=0, cols=0, vgap=0, hgap=0):
        if vgap or hgap:
            from DisplayCAL.config import get_default_dpi, getcfg

            scale = getcfg("app.dpi") / get_default_dpi()
            if scale > 1:
                # print vgap, hgap, '->',
                vgap, hgap = [int(round(v * scale)) for v in (vgap, hgap)]
            # print vgap, hgap
        super(FlexGridSizer, self).__init__(rows, cols, vgap, hgap)

    Add = Sizer.__dict__["Add"]
    Insert = Sizer.__dict__["Insert"]


wx.FlexGridSizer = FlexGridSizer


def GridGetSelection(self):
    """Return selected rows, cols, block and cells"""
    sel = []
    numrows = self.GetNumberRows()
    numcols = self.GetNumberCols()
    # rows
    rows = self.GetSelectedRows()
    for row in rows:
        for i in range(numcols):
            sel.append((row, i))
    # cols
    cols = self.GetSelectedCols()
    for col in cols:
        for i in range(numrows):
            sel.append((i, col))
    # block
    tl = self.GetSelectionBlockTopLeft()
    br = self.GetSelectionBlockBottomRight()
    if tl and br:
        for n in range(min(len(tl), len(br))):
            for i in range(tl[n][0], br[n][0] + 1):  # rows
                for j in range(tl[n][1], br[n][1] + 1):  # cols
                    sel.append((i, j))
    # single selected cells
    sel.extend(self.GetSelectedCells())
    # sel = list(set(sel))

    new_sel = []
    for item in sel:
        if item not in new_sel:
            new_sel.append(item)
    sel = new_sel

    sel.sort()
    return sel


wx.grid.Grid.GetSelection = GridGetSelection


def adjust_font_size_for_gcdc(font):
    size = get_gcdc_font_size(font.PointSize)
    font.SetPointSize(int(size))
    return font


def get_dc_font_scale(dc):
    """Get correct font scaling factor for DC"""
    pointsize = (1.0, 1.0)
    if isinstance(dc, wx.GCDC):
        pointsize = tuple(1.0 / scale for scale in dc.GetLogicalScale())
    if sys.platform in ("darwin", "win32") or (
        not isinstance(dc, wx.GCDC) and "gtk3" not in wx.PlatformInfo
    ):
        return sum(pointsize) / 2.0
    else:
        # On Linux, we need to correct the font size by a certain factor if
        # wx.GCDC is used, to make text the same size as if wx.GCDC weren't used
        from DisplayCAL.config import get_default_dpi, getcfg, set_default_app_dpi

        set_default_app_dpi()
        scale = getcfg("app.dpi") / get_default_dpi()
    if wx.VERSION < (2, 9):
        # On Linux, we need to correct the font size by a certain factor if
        # wx.GCDC is used, to make text the same size as if wx.GCDC weren't used
        screenppi = list(map(float, wx.ScreenDC().GetPPI()))
        ppi = dc.GetPPI()
        scale *= (screenppi[0] / ppi[0] + screenppi[1] / ppi[1]) / 2.0
    return (scale * pointsize[0] + scale * pointsize[1]) / 2.0


def get_dc_font_size(size, dc):
    """Get correct font size for DC"""
    return int(size * get_dc_font_scale(dc))


def get_gcdc_font_size(size):
    dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
    try:
        dc = wx.GCDC(dc)
    except Exception:
        pass
    return get_dc_font_size(size, dc)


def get_bitmap_disabled(bitmap):
    # Use Rec. 709 luma coefficients to convert to grayscale
    image = bitmap.ConvertToImage().ConvertToGreyscale(0.2126, 0.7152, 0.0722)
    if image.HasMask() and not image.HasAlpha():
        image.InitAlpha()
    if image.HasAlpha():
        alphabuffer = image.GetAlphaBuffer()
        for i, byte in enumerate(alphabuffer):
            if byte > 0:
                alphabuffer[i] = int(round(byte * 0.3))
    return image.ConvertToBitmap()


def get_bitmap_hover(bitmap, ctrl=None):
    image = bitmap.ConvertToImage()
    if image.HasMask() and not image.HasAlpha():
        image.InitAlpha()
    if sys.platform == "darwin":
        color = [44, 93, 205]  # Use Mavericks-like color scheme
    else:
        color = list(wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)[:3])
    R = color[0] / 255.0
    G = color[1] / 255.0
    B = color[2] / 255.0
    # Assume Rec. 709 gamma 2.2 to determine rel. luminance
    lum = 0.2126 * R**2.2 + 0.7152 * G**2.2 + 0.0722 * B**2.2
    is_bw = image.IsBW()
    if ctrl:
        bgcolor = ctrl.Parent.BackgroundColour
        if is_bw:
            # Adjust hilight color by background color if luminance difference
            # is below threshhold
            R = bgcolor[0] / 255.0
            G = bgcolor[1] / 255.0
            B = bgcolor[2] / 255.0
            # Assume Rec. 709 gamma 2.2 to determine rel. luminance
            bglum = 0.2126 * R**2.2 + 0.7152 * G**2.2 + 0.0722 * B**2.2
            lumdiff = (max(lum, bglum) - min(lum, bglum)) ** (1 / 2.2)
            if lumdiff < 1.0 / 3.0:
                if lum > bglum:
                    newmin = bglum ** (1 / 2.2) * 255
                    newmax = 255
                else:
                    newmin = 0
                    newmax = bglum ** (1 / 2.2) * 153  # 60%
                for i, v in enumerate(color):
                    color[i] = int(round(convert_range(v, 0, 255, newmin, newmax)))
    databuffer = image.GetDataBuffer()
    alphabuffer = image.GetAlphaBuffer()
    minv = 256  # Intentionally above max possible value
    j = 0
    RGB = {}
    for i, byte in enumerate(databuffer):
        RGB[i % 3] = byte
        if i % 3 == 2:
            RGBv = list(RGB.values())
            if not is_bw:
                RGBv_max = max(RGBv)
                if minv == 256 and alphabuffer[j] > 32:
                    # If a pixel is at least 12.5% opaque, check if it's value
                    # is less than or equal the previously seen minimum pixel
                    # value as a crude means to determine if the graphic
                    # contains a black outline.
                    minv = min(RGBv_max, minv)

            for k in range(3):
                if is_bw:
                    v = color[k]
                else:
                    v = RGB[k]
                    if minv > 0 and min(RGBv) != RGBv_max:
                        # If the minimum seen at least 12.5% opaque pixel value
                        # is above zero, assume a graphic without black outline
                        # and adjust intensity by applying a power. The hilight
                        # color isn't used.
                        v = (v / 255.0) ** 0.8 * 255
                    else:
                        # If the minimum seen at least 12.5% opaque pixel value
                        # is zero, adjust value by hilight color value, so that
                        # graphics with a black outline get the hilight color
                        # at black.
                        v = convert_range(v, 0, 255, color[k], 255)
                    v = int(round(v))
                databuffer[i - 2 + k] = v
            j += 1
    if isinstance(ctrl, wx.BitmapButton) and sys.platform == "win32":
        # wx.BitmapButton draws the focus bitmap over the normal bitmap,
        # leading to ugly aliased edges. Yuck. Prevent this by setting the
        # background to the control's background color instead of transparent.
        bmp = wx.EmptyBitmap(image.Width, image.Height)
        dc = wx.MemoryDC()
        dc.SelectObject(bmp)
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.Pen(bgcolor, width=0))
        dc.DrawRectangle(0, 0, image.Width, image.Height)
        dc.DrawBitmap(image.ConvertToBitmap(), 0, 0, True)
        dc.SelectObject(wx.NullBitmap)
    else:
        bmp = image.ConvertToBitmap()
    return bmp


def get_bitmap_pressed(bitmap):
    image = bitmap.ConvertToImage()
    if image.HasMask() and not image.HasAlpha():
        image.InitAlpha()
    databuffer = image.GetDataBuffer()
    for i, byte in enumerate(databuffer):
        if byte > 0:
            databuffer[i] = int(round(byte * 0.85))
    return image.ConvertToBitmap()


def get_bitmap_focus(bitmap):
    image = bitmap.ConvertToImage()
    if image.HasMask() and not image.HasAlpha():
        image.InitAlpha()
    databuffer = image.GetDataBuffer()
    for i, byte in enumerate(databuffer):
        if byte > 0:
            databuffer[i] = int(round((byte / 255.0) ** 0.8 * 255))
    return image.ConvertToBitmap()


def set_bitmap_labels(btn, disabled=True, focus=None, pressed=True):
    bitmap = btn.BitmapLabel
    if not bitmap.IsOk():
        size = btn.MinSize
        if -1 in size:
            size = (16, 16)
        bitmap = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE, size=size)
        # Ensure the normal bitmap is set first, fixes #507
        btn.SetBitmapLabel(bitmap)

    # Disabled
    if disabled:
        disabled_bitmap = get_bitmap_disabled(bitmap)
        try:
            btn.SetBitmapDisabled(disabled_bitmap)
        except wx._core.wxAssertionError:
            pass

    # Focus/Hover
    if sys.platform != "darwin" and focus is not False:
        # wxMac applies hover state also to disabled buttons...
        if focus is None:
            # Use hover bitmap
            bmp = get_bitmap_hover(bitmap, btn)
        else:
            # Use focus bitmap
            bmp = get_bitmap_focus(bitmap)
        try:
            btn.SetBitmapFocus(bmp)
        except wx._core.wxAssertionError:
            pass
        if hasattr(btn, "SetBitmapCurrent"):
            # Phoenix
            try:
                btn.SetBitmapCurrent(bmp)
            except wx._core.wxAssertionError:
               pass
        else:
            # Classic
            btn.SetBitmapHover(bmp)

    # Selected
    if pressed:
        if sys.platform == "darwin":
            bmp = get_bitmap_hover(bitmap, btn)
        elif focus is False:
            bmp = get_bitmap_pressed(bitmap)
        if hasattr(btn, "SetBitmapPressed"):
            # Phoenix
            try:
                btn.SetBitmapPressed(bmp)
            except wx._core.wxAssertionError:
                pass
        else:
            # Classic
            btn.SetBitmapSelected(bmp)


def get_dialogs(modal=False):
    """If there are any dialogs open, return them"""
    return [
        window
        for window in list(wx.GetTopLevelWindows())
        if window
        and isinstance(window, wx.Dialog)
        and window.IsShown()
        and (not modal or window.IsModal())
    ]


# wx.DirDialog and wx.FileDialog are normally not returned by
# wx.GetTopLevelWindows, do some trickery to work around

_DirDialog = wx.DirDialog
_FileDialog = wx.FileDialog


class PathDialogBase(wx.Dialog):
    def __init__(self, parent, name):
        wx.Dialog.__init__(self, parent, -1, name=name)
        self._ismodal = False
        self._isshown = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    def __getattr__(self, name):
        return getattr(self.filedialog, name)

    def IsModal(self):
        return self._ismodal

    def IsShown(self):
        return self._isshown

    def OnDestroy(self, event):
        self.filedialog.Destroy()
        event.Skip()
        return 0

    def Show(self, show=True):
        self._isshown = show
        self.filedialog.Show(show)

    def ShowModal(self):
        self._isshown = True
        self._ismodal = True
        returncode = self.filedialog.ShowModal()
        self._ismodal = False
        self._isshown = False
        return returncode


class DirDialog(PathDialogBase):
    def __init__(self, *args, **kwargs):
        PathDialogBase.__init__(self, args[0], name="dirdialog")
        self.filedialog = _DirDialog(*args, **kwargs)


class FileDialog(PathDialogBase):
    def __init__(self, *args, **kwargs):
        PathDialogBase.__init__(self, args[0], name="filedialog")
        self.filedialog = _FileDialog(*args, **kwargs)


wx.DirDialog = DirDialog
wx.FileDialog = FileDialog


wx._ScrolledWindow = wx.ScrolledWindow


class ScrolledWindow(wx._ScrolledWindow):
    """ScrolledWindow that scrolls child controls into view on focus.

    OnChildFocus and ScrollChildIntoView borrowed from wx.lib.scrolledpanel.
    """

    def __init__(self, *args, **kwargs):
        wx._ScrolledWindow.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnChildFocus)

    def OnChildFocus(self, evt):
        # If the child window that gets the focus is not visible,
        # this handler will try to scroll enough to see it.
        evt.Skip()
        child = evt.GetWindow()
        self.ScrollChildIntoView(child)

    def ScrollChildIntoView(self, child):
        """Scrolls the panel such that the specified child window is in view."""
        sppu_x, sppu_y = self.GetScrollPixelsPerUnit()
        vs_x, vs_y = self.GetViewStart()
        cr = child.GetRect()
        clntsz = self.GetClientSize()
        new_vs_x, new_vs_y = -1, -1

        # is it before the left edge?
        if cr.x < 0 < sppu_x:
            new_vs_x = vs_x + (cr.x / sppu_x)

        # is it above the top?
        if cr.y < 0 < sppu_y:
            new_vs_y = vs_y + (cr.y / sppu_y)

        # For the right and bottom edges, scroll enough to show the
        # whole control if possible, but if not just scroll such that
        # the top/left edges are still visible

        # is it past the right edge ?
        if cr.right > clntsz.width and sppu_x > 0:
            diff = (cr.right - clntsz.width) / sppu_x
            if cr.x - diff * sppu_x > 0:
                new_vs_x = vs_x + diff + 1
            else:
                new_vs_x = vs_x + (cr.x / sppu_x)

        # is it below the bottom ?
        if cr.bottom > clntsz.height and sppu_y > 0:
            diff = (cr.bottom - clntsz.height) / sppu_y
            if cr.y - diff * sppu_y > 0:
                new_vs_y = vs_y + diff + 1
            else:
                new_vs_y = vs_y + (cr.y / sppu_y)

        # if we need to adjust
        if new_vs_x != -1 or new_vs_y != -1:
            # print "%s: (%s, %s)" % (self.GetName(), new_vs_x, new_vs_y)
            self.Scroll(int(new_vs_x), int(new_vs_y))


wx.ScrolledWindow = ScrolledWindow
ScrolledPanel.ScrollChildIntoView = ScrolledWindow.ScrollChildIntoView


class GenButton:
    """A generic button, based on wx.lib.buttons.GenButton.

    Fixes wx.lib.buttons.ThemedGenButton not taking into account backgroun
    color when pressed.

    """

    def __init__(self):
        self.bezelWidth = 2
        self.hasFocus = False
        self.up = True
        self.useFocusInd = True

    def OnPaint(self, event):
        (width, height) = self.ClientSize
        x1 = y1 = 0
        x2 = width
        y2 = height

        dc = wx.PaintDC(self)
        brush = self.GetBackgroundBrush(dc)
        if brush is not None:
            brush.SetColour(self.Parent.BackgroundColour)
            dc.SetBackground(brush)
            dc.Clear()

        self.DrawBezel(dc, x1, y1, x2, y2)
        self.DrawLabel(dc, width, height)
        if self.hasFocus and self.useFocusInd:
            self.DrawFocusIndicator(dc, width, height)


if "gtk3" not in wx.PlatformInfo:
    # GTK3 doesn't respect NO_BORDER in hovered state when using wx.BitmapButton
    _GenBitmapButton = wx.BitmapButton


class GenBitmapButton(GenButton, _GenBitmapButton):
    def __init__(self, *args, **kwargs):
        GenButton.__init__(self)
        _GenBitmapButton.__init__(self, *args, **kwargs)
        self.hover = False
        set_bitmap_labels(self)
        if _GenBitmapButton is not wx.BitmapButton:
            self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
            self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)

    @property
    def BitmapFocus(self):
        return self.GetBitmapFocus()

    @BitmapFocus.setter
    def BitmapFocus(self, bitmap):
        self.SetBitmapFocus(self, bitmap)

    @property
    def BitmapDisabled(self):
        return self.GetBitmapDisabled()

    @BitmapDisabled.setter
    def BitmapDisabled(self, bitmap):
        self.SetBitmapDisabled(self, bitmap)

    @property
    def BitmapHover(self):
        return self.GetBitmapHover()

    @BitmapHover.setter
    def BitmapHover(self, bitmap):
        self.SetBitmapHover(self, bitmap)

    @property
    def BitmapSelected(self):
        return self.GetBitmapSelected()

    @BitmapSelected.setter
    def BitmapSelected(self, bitmap):
        self.SetBitmapSelected(self, bitmap)

    @property
    def BitmapLabel(self):
        return self.GetBitmapLabel()

    @BitmapLabel.setter
    def BitmapLabel(self, bitmap):
        self.SetBitmapLabel(self, bitmap)

    def DrawLabel(self, dc, width, height, dx=0, dy=0):
        bmp = self.BitmapLabel
        if self.BitmapDisabled and not self.IsEnabled():
            bmp = self.BitmapDisabled
        elif self.BitmapSelected and not self.up:
            bmp = self.BitmapSelected
        elif self.BitmapHover and self.hover:
            bmp = self.BitmapHover
        elif self.BitmapFocus and self.hasFocus:
            bmp = self.BitmapFocus
        bw, bh = bmp.GetWidth(), bmp.GetHeight()
        hasMask = bmp.GetMask() is not None
        dc.DrawBitmap(
            bmp, int((width - bw) / 2 + dx), int((height - bh) / 2 + dy), hasMask
        )

    def GetBitmapHover(self):
        return self.bmpHover

    def OnMouseEnter(self, event):
        if not self.IsEnabled():
            return
        if not self.hover:
            self.hover = True
            self.Refresh()
        event.Skip()

    def OnMouseLeave(self, event):
        if not self.IsEnabled():
            return
        if self.hover:
            self.hover = False
            self.Refresh()
        event.Skip()

    def SetBitmapHover(self, bitmap):
        self.bmpHover = bitmap


class ThemedGenButton(GenButton, _ThemedGenButton):
    """A themed generic button, based on wx.lib.buttons.ThemedGenButton.

    Fixes wx.lib.buttons.ThemedGenButton sometimes not reflecting enabled
    state correctly as well as not taking into account background color when
    pressed, and mimics a default button under Windows more closely by
    not drawing a focus outline and not shifting the label when pressed.

    Also implements state for SetDefault.

    """

    _reallyenabled = True
    labelDelta = 1

    def __init__(self, *args, **kwargs):
        GenButton.__init__(self)
        _ThemedGenButton.__init__(self, *args, **kwargs)
        self._default = False

    def Disable(self):
        self.Enable(False)

    def DoGetBestSize(self):
        """Overridden base class virtual.  Determines the best size of the
        button based on the label and bezel size.
        """
        w, h, useMin = self._GetLabelSize()
        if self.style & wx.BU_EXACTFIT:
            width = w + 2 + 2 * self.bezelWidth + 4 * int(self.useFocusInd)
            height = h + 2 + 2 * self.bezelWidth + 4 * int(self.useFocusInd)
        else:
            defSize = wx.Button.GetDefaultSize()
            width = 12 + w
            if useMin and width < defSize.width:
                width = defSize.width
            height = 11 + h
            if useMin and height < defSize.height:
                height = defSize.height
            width = width + self.bezelWidth - 2
            height = height + self.bezelWidth - 2
        return (width, height)

    def DrawBezel(self, dc, x1, y1, x2, y2):
        rect = wx.Rect(x1, y1, x2, y2)
        if self.up:
            state = 0
        else:
            state = wx.CONTROL_PRESSED | wx.CONTROL_SELECTED
        if not self.IsEnabled():
            state = wx.CONTROL_DISABLED
        elif self._default:
            state |= wx.CONTROL_ISDEFAULT
        pt = self.ScreenToClient(wx.GetMousePosition())
        if self.GetClientRect().Contains(pt):
            state |= wx.CONTROL_CURRENT
        wx.RendererNative.Get().DrawPushButton(self, dc, rect, state)

    def DrawLabel(self, dc, width, height, dx=0, dy=0):
        dc.SetFont(self.GetFont())
        if self.Enabled:
            dc.SetTextForeground(self.ForegroundColour)
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        label = self.Label
        tw, th = dc.GetTextExtent(label)
        if sys.platform != "win32" and not self.up:
            dx = dy = self.labelDelta
        dc.DrawText(label, int((width - tw) / 2) + dx, int((height - th) / 2) + dy)

    def Enable(self, enable=True):
        if enable != self.Enabled:
            self.Enabled = enable
            wx.PyControl.Enable(self, enable)
            self.Refresh()

    @property
    def Enabled(self):
        return self._reallyenabled

    @Enabled.setter
    def Enabled(self, enabled):
        self._reallyenabled = enabled

    def IsEnabled(self):
        return self.Enabled

    def OnLeftDown(self, event):
        if not self.Enabled:
            return
        self.up = False
        self.CaptureMouse()
        self.SetFocus()
        self.useFocusInd = False
        self.Refresh()
        event.Skip()

    def OnGainFocus(self, event):
        self.hasFocus = True
        self.useFocusInd = bool(self.bezelWidth)
        self.Refresh()
        self.Update()

    def SetDefault(self):
        self._default = True
        _ThemedGenButton.SetDefault(self)


class PlateButton(platebtn.PlateButton):
    """Fixes wx.lib.platebtn.PlateButton sometimes not reflecting enabled state
    correctly aswelll as other quirks

    """

    _reallyenabled = True

    def __init__(self, *args, **kwargs):
        from DisplayCAL.config import get_default_dpi, getcfg

        self.dpiscale = getcfg("app.dpi") / get_default_dpi()
        platebtn.PlateButton.__init__(self, *args, **kwargs)
        self._bmp["hilite"] = None
        if sys.platform == "darwin":
            # Use Sierra-like color scheme
            from DisplayCAL.wxaddons import gamma_encode

            color = wx.Colour(*gamma_encode(0, 105, 217))
        else:
            color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
        self._color["hlight"] = color
        self.Unbind(wx.EVT_LEAVE_WINDOW)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda evt: wx.CallLater(80, self.__LeaveWindow))
        if "gtk2" in wx.PlatformInfo and not isinstance(self.TopLevelParent, wx.Dialog):
            self.BackgroundColour = self.Parent.BackgroundColour

    def DoGetBestSize(self):
        """Calculate the best size of the button

        :return: :class:`Size`

        """
        # A little more padding left + right
        width = 6 * self.dpiscale
        height = 6 * self.dpiscale
        if self.Label:
            # NOTE: Should measure with a GraphicsContext to get right
            #       size, but due to random segfaults on linux special
            #       handling is done in the drawing instead...
            lsize = self.GetFullTextExtent(self.Label)
            width += lsize[0]
            height += lsize[1]

        if self._bmp["enable"] is not None:
            bsize = self._bmp["enable"].Size
            width += bsize[0] + 10 * self.dpiscale
            if height <= bsize[1]:
                height = bsize[1] + 6 * self.dpiscale
            else:
                # No DPI scaling needed here
                height += 3
        else:
            width += 10 * self.dpiscale

        if self._menu is not None or self._style & platebtn.PB_STYLE_DROPARROW:
            width += 12 * self.dpiscale

        best = wx.Size(int(width), int(height))
        self.CacheBestSize(best)
        return best

    def GetBitmapLabel(self):
        """Get the label bitmap

        :return: :class:`Bitmap` or None

        """
        return self._bmp["enable"]

    def SetBitmapHover(self, bmp):
        """Set the bitmap displayed in the button

        :param bmp: :class:`wx.Bitmap`

        """
        self._bmp["hilite"] = bmp

    def __DrawBitmap(self, gc, interactable):
        """Draw the bitmap if one has been set

        :param GCDC `gc`: :class:`GCDC` to draw with
        :return: x cordinate to draw text at

        """
        if self.IsEnabled():
            if (
                self._state["cur"] in (platebtn.PLATE_HIGHLIGHT, platebtn.PLATE_PRESSED)
                and interactable
            ):
                bmp = self._bmp["hilite"]
            else:
                bmp = self._bmp["enable"]
        else:
            bmp = self._bmp["disable"]

        xpos = 4 * self.dpiscale
        if bmp is not None and bmp.IsOk():
            bw, bh = bmp.GetSize()
            ypos = (self.GetSize()[1] - bh) // 2
            gc.DrawBitmap(bmp, int(xpos), int(ypos), bmp.GetMask() is not None)
            return bw + xpos
        else:
            return xpos

    def __DrawButton(self):
        """Draw the button"""
        # TODO using a buffered paintdc on windows with the nobg style
        #      causes lots of weird drawing. So currently the use of a
        #      buffered dc is dissabled for this style.
        if platebtn.PB_STYLE_NOBG & self._style:
            dc = wx.PaintDC(self)
        else:
            dc = wx.AutoBufferedPaintDCFactory(self)
            dc.SetBackground(wx.TRANSPARENT_BRUSH)
            dc.Clear()

        gc = wx.GCDC(dc)

        # Setup
        gc.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
        gc.SetBackgroundMode(wx.TRANSPARENT)

        # Calc Object Positions
        width, height = self.GetSize()
        # Note: Using self.GetTextExtent instead of gc.GetTextExtent seems
        # to fix sporadic segfaults with wxPython Phoenix up to 4.0.0a2
        # under Windows (fixed in 4.0.0a3), but self.GetTextExtent is NOT
        # an equivalent replacement for gc.GetTextExtent.
        tw, th = gc.GetTextExtent(self.Label)
        txt_y = max((height - th) // 2 - 1, 1)

        # The background needs some help to look transparent on
        # on Gtk and Windows
        if wx.Platform in ["__WXGTK__", "__WXMSW__"]:
            gc.SetBrush(self.GetBackgroundBrush(gc))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRectangle(0, 0, width, height)

        gc.SetBrush(wx.TRANSPARENT_BRUSH)

        space = 4 * self.dpiscale

        # Our IsEnabled() override only deals with explit enabled/disabled
        # state, while we also need to deal with interaction state
        # (button enabled and interactable, eg. no modal dialog shown that
        # would prevent interaction)
        dialogs = get_dialogs()
        interactable = not dialogs or self.TopLevelParent in dialogs
        if (
            self._state["cur"] == platebtn.PLATE_HIGHLIGHT
            and self.IsEnabled()
            and interactable
        ):
            gc.SetTextForeground(self._color["htxt"])
            gc.SetPen(wx.TRANSPARENT_PEN)
            self.__DrawHighlight(gc, int(width), int(height))

        elif self._state["cur"] == platebtn.PLATE_PRESSED and self.IsEnabled():
            gc.SetTextForeground(self._color["htxt"])
            pen = wx.Pen(platebtn.AdjustColour(self._color["press"], -80, 220), 1)
            gc.SetPen(pen)

            self.__DrawHighlight(gc, int(width), int(height))
            txt_x = self.__DrawBitmap(gc, interactable)
            t_x = max((width - tw - (txt_x + space)) // 2, txt_x + space)
            gc.DrawText(self.Label, int(t_x), int(txt_y))
            self.__DrawDropArrow(gc, int(width - 10), int((height // 2) - 2))

        else:
            if self.IsEnabled():
                gc.SetTextForeground(self.GetForegroundColour())
            else:
                txt_c = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
                gc.SetTextForeground(txt_c)

        # Draw bitmap and text
        if self._state["cur"] != platebtn.PLATE_PRESSED or not self.IsEnabled():
            txt_x = self.__DrawBitmap(gc, interactable)
            t_x = max((width - tw - (txt_x + space)) // 2, txt_x + space)
            gc.DrawText(self.Label, int(t_x), int(txt_y))
            self.__DrawDropArrow(gc, int(width - 10), int((height // 2) - 2))

    def __LeaveWindow(self):
        """Handle updating the buttons state when the mouse cursor leaves"""
        if (self._style & platebtn.PB_STYLE_TOGGLE) and self._pressed:
            self._SetState(platebtn.PLATE_PRESSED)
        else:
            self._SetState(platebtn.PLATE_NORMAL)
            self._pressed = False

    def __PostEvent(self):
        """Post a button event to parent of this control"""
        if self._style & platebtn.PB_STYLE_TOGGLE:
            etype = wx.wxEVT_COMMAND_TOGGLEBUTTON_CLICKED
        else:
            etype = wx.wxEVT_COMMAND_BUTTON_CLICKED
        bevt = wx.CommandEvent(etype, self.GetId())
        bevt.SetEventObject(self)
        bevt.SetString(self.GetLabel())
        self.GetEventHandler().ProcessEvent(bevt)

    _PostEvent = __PostEvent

    def Update(self):
        pass

    Disable = ThemedGenButton.__dict__["Disable"]
    Enable = ThemedGenButton.__dict__["Enable"]
    Enabled = ThemedGenButton.__dict__["Enabled"]
    IsEnabled = ThemedGenButton.__dict__["IsEnabled"]
    Label = property(
        lambda self: self.GetLabel(), lambda self, label: self.SetLabel(label)
    )


if not hasattr(PlateButton, "_SetState"):
    # wxPython < 3.0
    PlateButton._SetState = PlateButton.SetState


class TempXmlResource:
    _temp = None

    def __init__(self, xmlpath):
        from DisplayCAL.config import get_default_dpi, getcfg

        scale = max(getcfg("app.dpi") / get_default_dpi(), 1)
        if scale > 1 or "gtk3" in wx.PlatformInfo:
            if not TempXmlResource._temp:
                try:
                    TempXmlResource._temp = tempfile.mkdtemp(prefix=appname + "-XRC-")
                except Exception:
                    pass
            if TempXmlResource._temp and os.path.isdir(TempXmlResource._temp):
                # Read original XML
                with open(xmlpath, "rb") as xmlfile:
                    xml = xmlfile.read().decode()
                # Adjust spacing for scale
                for tag in ("border", "hgap", "vgap"):
                    xml = re.sub(
                        r"<%s>(\d+)</%s>" % (tag, tag),
                        lambda match: "<%s>%i</%s>"
                        % (tag, round(int(match.group(1)) * scale), tag),
                        xml,
                    )
                for tag in ("size",):
                    xml = re.sub(
                        r"<%s>(-?\d+)\s*,\s*(-?\d+)</%s>" % (tag, tag),
                        lambda match: "<%s>%i,%i</%s>"
                        % (
                            (tag,)
                            + tuple(
                                round(int(v) * scale) if int(v) > 0 else int(v)
                                for v in match.groups()
                            )
                            + (tag,)
                        ),
                        xml,
                    )
                # Set relative paths to absolute
                basedir = os.path.dirname(os.path.dirname(xmlpath))
                basedir = basedir.replace("\\", "/")
                xml = xml.replace(">../", ">%s/" % basedir)
                # Fix background color not working for panels under wxGTK3
                if "gtk3" in wx.PlatformInfo:
                    xml = xml.replace(
                        'class="wxPanel"',
                        'class="wxPanel" subclass="DisplayCAL.wxfixes.wx_Panel"',
                    )
                    # 'class="wxPanel" subclass="wxfixes.wx_Panel"')
                # Write modified XML
                xmlpath = os.path.join(TempXmlResource._temp, os.path.basename(xmlpath))
                with open(xmlpath, "wb") as xmlfile:
                    xmlfile.write(xml.encode())
                from DisplayCAL.wxwindows import BaseApp

                BaseApp.register_exitfunc(self._cleanup)
        self.xmlpath = xmlpath
        self.res = xrc.XmlResource(xmlpath)

    def _cleanup(self):
        if (
            TempXmlResource._temp
            and self.xmlpath.startswith(TempXmlResource._temp + os.path.sep)
            and os.path.isfile(self.xmlpath)
        ):
            os.remove(self.xmlpath)
            if not os.listdir(TempXmlResource._temp):
                shutil.rmtree(TempXmlResource._temp)

    def __getattr__(self, name):
        return getattr(self.res, name)


class GenBitmapTextButton(GenButton, _GenBitmapTextButton):
    """A generic bitmapped button with text label"""

    def __init__(
        self,
        parent,
        id=-1,
        bitmap=wx.NullBitmap,
        label="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        validator=wx.DefaultValidator,
        name="genbutton",
    ):
        GenButton.__init__(self)
        _GenBitmapTextButton.__init__(
            self, parent, id, bitmap, label, pos, size, style, validator, name
        )
        self._default = False

    def DrawLabel(self, dc, width, height, dx=0, dy=0):
        bmp = self.bmpLabel
        if bmp is not None:  # if the bitmap is used
            if self.bmpDisabled and not self.IsEnabled():
                bmp = self.bmpDisabled
            if self.bmpFocus and self.hasFocus:
                bmp = self.bmpFocus
            if self.bmpSelected and not self.up:
                bmp = self.bmpSelected
            bw, bh = bmp.GetWidth(), bmp.GetHeight()
            if sys.platform != "win32" and not self.up:
                dx = dy = self.labelDelta
            hasMask = bmp.GetMask() is not None
        else:
            bw = bh = 0  # no bitmap -> size is zero

        dc.SetFont(self.GetFont())
        if self.IsEnabled():
            dc.SetTextForeground(self.GetForegroundColour())
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        label = self.GetLabel()
        tw, th = dc.GetTextExtent(label)  # size of text
        sw, sh = dc.GetTextExtent(" ")  # extra spacing from bitmap
        if sys.platform != "win32" and not self.up:
            dx = dy = self.labelDelta

        # adjust for bitmap and text to centre
        pos_x = int((width - bw - sw - tw) / 2) + dx
        if bmp is not None:
            dc.DrawBitmap(
                bmp, pos_x, int((height - bh) / 2) + dy, hasMask
            )  # draw bitmap if available
            pos_x = pos_x + sw  # extra spacing from bitmap

        # draw the text
        dc.DrawText(label, pos_x + dx + bw, int((height - th) / 2) + dy)


class ThemedGenBitmapTextButton(ThemedGenButton, GenBitmapTextButton):
    """A themed generic bitmapped button with text label"""

    pass


class BitmapWithThemedButton(wx.BoxSizer):
    def __init__(
        self,
        parent,
        id=-1,
        bitmap=wx.NullBitmap,
        label="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        style=0,
        validator=wx.DefaultValidator,
        name="button",
    ):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)
        self._bmp = wx.StaticBitmap(parent, -1, bitmap)
        # self.Add(self._bmp, flag=wx.ALIGN_CENTER_VERTICAL)
        self.Add(self._bmp)
        if wx.Platform == "__WXMSW__":
            btncls = ThemedGenButton
        else:
            btncls = wx.Button
        self._btn = btncls(parent, id, label, pos, size, style, validator, name)
        # self.Add(self._btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8)
        self.Add(self._btn, flag=wx.LEFT, border=8)

    def __getattr__(self, name):
        return getattr(self._btn, name)

    def Bind(self, event, handler):
        self._btn.Bind(event, handler)

    def SetBitmapLabel(self, bitmap):
        self._bmp.SetBitmap(bitmap)
        self.Layout()
