# -*- coding: utf-8 -*-
"""
Drop-In replacement for wx.TaskBarIcon

This one won't stop showing updates to the icon like wx.TaskBarIcon

"""

import ctypes
import os
import sys

import win32api
import win32con
import win32gui
import winerror

from DisplayCAL.options import debug, verbose
from DisplayCAL.wxaddons import wx, IdFactory


class Menu(wx.EvtHandler):
    def __init__(self):
        wx.EvtHandler.__init__(self)
        self.hmenu = win32gui.CreatePopupMenu()
        self.MenuItems = []
        self.Parent = None
        self._menuitems = {}
        # With wxPython 4, calling <EvtHandler>.Destroy() no longer makes the
        # instance evaluate to False in boolean comparisons, so we emulate that
        # functionality
        self._destroyed = False

    def Append(self, id, text, help="", kind=wx.ITEM_NORMAL):
        return self.AppendItem(MenuItem(self, id, text, help, kind))

    def AppendCheckItem(self, id, text, help=""):
        return self.Append(id, text, help, wx.ITEM_CHECK)

    def AppendItem(self, item):
        if item.Kind == wx.ITEM_SEPARATOR:
            flags = win32con.MF_SEPARATOR
        else:
            if item.subMenu:
                flags = win32con.MF_POPUP | win32con.MF_STRING
            else:
                flags = 0
            if not item.Enabled:
                flags |= win32con.MF_DISABLED
        # Use ctypes instead of win32gui.AppendMenu for unicode support
        ctypes.windll.User32.AppendMenuW(
            self.hmenu, flags, item.Id, str(item.ItemLabel)
        )
        self.MenuItems.append(item)
        self._menuitems[item.Id] = item
        if item.Checked:
            self.Check(item.Id)
        return item

    def AppendSubMenu(self, submenu, text, help=""):
        item = MenuItem(self, submenu.hmenu, text, help, wx.ITEM_NORMAL, submenu)
        return self.AppendItem(item)

    def AppendRadioItem(self, id, text, help=""):
        return self.Append(id, text, help, wx.ITEM_RADIO)

    def AppendSeparator(self):
        return self.Append(-1, "", kind=wx.ITEM_SEPARATOR)

    def Check(self, id, check=True):
        flags = win32con.MF_BYCOMMAND
        item_check = self._menuitems[id]
        if item_check.Kind == wx.ITEM_RADIO:
            if not check:
                return
            item_first = item_check
            item_last = item_check
            index = self.MenuItems.index(item_check)
            menuitems = self.MenuItems[:index]
            while menuitems:
                item = menuitems.pop()
                if item.Kind == wx.ITEM_RADIO:
                    item_first = item
                    item.Checked = False
                else:
                    break
            menuitems = self.MenuItems[index:]
            menuitems.reverse()
            while menuitems:
                item = menuitems.pop()
                if item.Kind == wx.ITEM_RADIO:
                    item_last = item
                    item.Checked = False
                else:
                    break
            win32gui.CheckMenuRadioItem(
                self.hmenu, item_first.Id, item_last.Id, item_check.Id, flags
            )
        else:
            if check:
                flags |= win32con.MF_CHECKED
            win32gui.CheckMenuItem(self.hmenu, item_check.Id, flags)
        item_check.Checked = check

    def Destroy(self):
        for menuitem in self.MenuItems:
            menuitem.Destroy()
        if not self.Parent:
            if debug or verbose > 1:
                print("DestroyMenu HMENU", self.hmenu)
            win32gui.DestroyMenu(self.hmenu)
        if debug or verbose > 1:
            print("Destroy", self.__class__.__name__, self)
        self._destroyed = True
        wx.EvtHandler.Destroy(self)

    def __bool__(self):
        return not self._destroyed

    def Enable(self, id, enable=True):
        flags = win32con.MF_BYCOMMAND
        if not enable:
            flags |= win32con.MF_DISABLED
        item = self._menuitems[id]
        win32gui.EnableMenuItem(self.hmenu, item.Id, flags)
        item.Enabled = enable


class MenuItem:
    def __init__(
        self, menu, id=-1, text="", help="", kind=wx.ITEM_NORMAL, subMenu=None
    ):
        if id == -1:
            id = IdFactory.NewId()
        self.Menu = menu
        self.Id = id
        self.ItemLabel = text
        self.Help = help
        self.Kind = kind
        self.Enabled = True
        self.Checked = False
        self.subMenu = subMenu
        if subMenu:
            self.subMenu.Parent = menu

    def Check(self, check=True):
        self.Checked = check
        if self.Id in self.Menu._menuitems:
            self.Menu.Check(self.Id, check)

    def Destroy(self):
        if self.subMenu:
            self.subMenu.Destroy()
        if debug or verbose > 1:
            print(
                "Destroy",
                self.__class__.__name__,
                self.Id,
                _get_kind_str(self.Kind),
                self.ItemLabel,
            )
        if self.Id in IdFactory.ReservedIds:
            IdFactory.UnreserveId(self.Id)

    def Enable(self, enable=True):
        self.Enabled = enable
        if self.Id in self.Menu._menuitems:
            self.Menu.Enable(self.Id, enable)

    def GetId(self):
        return self.Id


class SysTrayIcon(wx.EvtHandler):
    def __init__(self):
        wx.EvtHandler.__init__(self)
        msg_TaskbarCreated = win32gui.RegisterWindowMessage("TaskbarCreated")
        message_map = {
            msg_TaskbarCreated: self.OnTaskbarCreated,
            win32con.WM_DESTROY: self.OnDestroy,
            win32con.WM_COMMAND: self.OnCommand,
            win32con.WM_USER + 20: self.OnTaskbarNotify,
        }

        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "SysTrayIcon"
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        wc.hCursor = win32api.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = message_map

        classAtom = win32gui.RegisterClass(wc)

        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(
            wc.lpszClassName,
            "SysTrayIcon",
            style,
            0,
            0,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            0,
            0,
            hinst,
            None,
        )
        win32gui.UpdateWindow(self.hwnd)
        self._nid = None
        self.in_popup = False
        self.menu = None
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.OnRightUp)
        # With wxPython 4, calling <EvtHandler>.Destroy() no longer makes the
        # instance evaluate to False in boolean comparisons, so we emulate that
        # functionality
        self._destroyed = False

    def CreatePopupMenu(self):
        """Override this method in derived classes"""
        if self.menu:
            return self.menu
        menu = Menu()
        item = menu.AppendRadioItem(-1, "Radio 1")
        item.Check()
        menu.Bind(
            wx.EVT_MENU,
            lambda event: menu.Check(event.Id, event.IsChecked()),
            id=item.Id,
        )
        item = menu.AppendRadioItem(-1, "Radio 2")
        menu.Bind(
            wx.EVT_MENU,
            lambda event: menu.Check(event.Id, event.IsChecked()),
            id=item.Id,
        )
        menu.AppendSeparator()
        item = menu.AppendCheckItem(-1, "Checkable")
        item.Check()
        menu.Bind(
            wx.EVT_MENU,
            lambda event: menu.Check(event.Id, event.IsChecked()),
            id=item.Id,
        )
        menu.AppendSeparator()
        item = menu.AppendCheckItem(-1, "Disabled")
        item.Enable(False)
        menu.AppendSeparator()
        submenu = Menu()
        item = submenu.AppendCheckItem(-1, "Sub menu item")
        submenu.Bind(
            wx.EVT_MENU,
            lambda event: submenu.Check(event.Id, event.IsChecked()),
            id=item.Id,
        )
        subsubmenu = Menu()
        item = subsubmenu.AppendCheckItem(-1, "Sub sub menu item")
        subsubmenu.Bind(
            wx.EVT_MENU,
            lambda event: subsubmenu.Check(event.Id, event.IsChecked()),
            id=item.Id,
        )
        submenu.AppendSubMenu(subsubmenu, "Sub sub menu")
        menu.AppendSubMenu(submenu, "Sub menu")
        menu.AppendSeparator()
        item = menu.Append(-1, "Exit")
        menu.Bind(
            wx.EVT_MENU, lambda event: win32gui.DestroyWindow(self.hwnd), id=item.Id
        )
        return menu

    def OnCommand(self, hwnd, msg, wparam, lparam):
        print(
            "SysTrayIcon.OnCommand(hwnd={}, msg={}, wparam={}, lparam={})".format(
                repr(hwnd), repr(msg), repr(wparam), repr(lparam)
            )
        )
        if not self.menu:
            print("Warning: Don't have menu")
            return 0
        if wparam is None:
            print("Warning: No menu item is selected")
            return 0
        item = _get_selected_menu_item(wparam, self.menu)
        if not item:
            print(f"Warning: Don't have menu item ID {wparam}")
            return 0
        if debug or verbose > 1:
            print(
                item.__class__.__name__,
                item.Id,
                _get_kind_str(item.Kind),
                item.ItemLabel,
            )
        event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED)
        event.Id = item.Id
        if item.Kind == wx.ITEM_RADIO:
            event.SetInt(1)
        elif item.Kind == wx.ITEM_CHECK:
            event.SetInt(int(not item.Checked))
        item.Menu.ProcessEvent(event)
        return 0

    def OnDestroy(self, hwnd, msg, wparam, lparam):
        self.Destroy()
        if not wx.GetApp() or not wx.GetApp().IsMainLoopRunning():
            win32gui.PostQuitMessage(0)
        return 0

    def Destroy(self):
        if self.menu:
            self.menu.Destroy()
        self.RemoveIcon()
        self._destroyed = True
        wx.EvtHandler.Destroy(self)

    def __bool__(self):
        return not self._destroyed

    def OnRightUp(self, event):
        self.PopupMenu(self.CreatePopupMenu())

    def OnTaskbarCreated(self, hwnd, msg, wparam, lparam):
        if self._nid:
            hicon, tooltip = self._nid[4:6]
            self._nid = None
            self.SetIcon(hicon, tooltip)

    def OnTaskbarNotify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONDOWN:
            self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_LEFT_DOWN))
        elif lparam == win32con.WM_LBUTTONUP:
            self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_LEFT_UP))
        elif lparam == win32con.WM_LBUTTONDBLCLK:
            self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_LEFT_DCLICK))
        elif lparam == win32con.WM_RBUTTONDOWN:
            self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_RIGHT_DOWN))
        elif lparam == win32con.WM_RBUTTONUP:
            self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_RIGHT_UP))
        return 1

    def PopupMenu(self, menu):
        if self.in_popup:
            return
        self.in_popup = True
        self.menu = menu
        try:
            pos = win32gui.GetCursorPos()
            # See remarks section under
            # https://msdn.microsoft.com/en-us/library/windows/desktop/ms648002(v=vs.85).aspx
            try:
                win32gui.SetForegroundWindow(self.hwnd)
            except win32gui.error:
                # Calls to SetForegroundWindow will fail if (e.g.) the Win10
                # start menu is currently shown
                pass
            win32gui.TrackPopupMenu(
                menu.hmenu, win32con.TPM_RIGHTBUTTON, pos[0], pos[1], 0, self.hwnd, None
            )
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        finally:
            self.in_popup = False

    def RemoveIcon(self):
        if self._nid:
            self._nid = None
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
            except win32gui.error:
                return False
            return True
        return False

    def SetIcon(self, hicon, tooltip=""):
        if isinstance(hicon, wx.Icon):
            hicon = hicon.GetHandle()
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        if self._nid:
            msg = win32gui.NIM_MODIFY
        else:
            msg = win32gui.NIM_ADD
        self._nid = (self.hwnd, 0, flags, win32con.WM_USER + 20, hicon, tooltip)
        try:
            win32gui.Shell_NotifyIcon(msg, self._nid)
        except win32gui.error:
            return False
        return True


def _get_kind_str(kind):
    return {
        wx.ITEM_SEPARATOR: "ITEM_SEPARATOR",
        wx.ITEM_NORMAL: "ITEM_NORMAL",
        wx.ITEM_CHECK: "ITEM_CHECK",
        wx.ITEM_RADIO: "ITEM_RADIO",
        wx.ITEM_DROPDOWN: "ITEM_DROPDOWN",
        wx.ITEM_MAX: "ITEM_MAX",
    }.get(kind, str(kind))


def _get_selected_menu_item(id, menu):
    if id in menu._menuitems:
        return menu._menuitems[id]
    else:
        for item in menu.MenuItems:
            if item.subMenu:
                item = _get_selected_menu_item(id, item.subMenu)
                if item:
                    return item


def main():
    app = wx.App(0)
    hinst = win32gui.GetModuleHandle(None)
    try:
        hicon = win32gui.LoadImage(
            hinst, 1, win32con.IMAGE_ICON, 0, 0, win32con.LR_DEFAULTSIZE
        )
    except win32gui.error:
        hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
    tooltip = os.path.basename(sys.executable)
    icon = SysTrayIcon()
    icon.Bind(
        wx.EVT_TASKBAR_LEFT_UP,
        lambda event: wx.MessageDialog(
            None,
            "Native system tray icon demo (Windows only)",
            "SysTrayIcon class",
            wx.OK | wx.ICON_INFORMATION,
        ).ShowModal(),
    )
    icon.SetIcon(hicon, tooltip)
    win32gui.PumpMessages()


if __name__ == "__main__":
    main()
