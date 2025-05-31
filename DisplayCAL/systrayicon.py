"""Drop-In replacement for wx.TaskBarIcon.

This one won't stop showing updates to the icon like wx.TaskBarIcon

"""

from __future__ import annotations

import contextlib
import ctypes
import os
import sys

import win32api
import win32con
import win32gui

from DisplayCAL.options import DEBUG, VERBOSE
from DisplayCAL.wx_addons import IdFactory, wx


class Menu(wx.EvtHandler):
    """A class that represents a system tray icon menu."""

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

    def Append(self, id, text, help="", kind=wx.ITEM_NORMAL):  # noqa: A002
        """Append a menu item to the menu.

        Args:
            id (int): The ID of the menu item. If -1, a new ID will be
                generated.
            text (str): The label text for the menu item.
            help (str): Help text for the menu item, not used in this
                implementation.
            kind (int): The type of the menu item, e.g., wx.ITEM_NORMAL,
                wx.ITEM_CHECK, etc.

        Returns:
            MenuItem: A MenuItem instance representing the appended item.
        """
        return self.AppendItem(MenuItem(self, id, text, help, kind))

    def AppendCheckItem(self, id, text, help=""):  # noqa: A002
        """Append a checkable menu item to the menu.

        Args:
            id (int): The ID of the menu item. If -1, a new ID will be
                generated.
            text (str): The label text for the menu item.
            help (str): Help text for the menu item, not used in this
                implementation.

        Returns:
            MenuItem: A MenuItem instance representing the checkable item.
        """
        return self.Append(id, text, help, wx.ITEM_CHECK)

    def AppendItem(self, item):
        """Append a menu item to the menu.

        Args:
            item (MenuItem): The MenuItem instance to append.

        Returns:
            MenuItem: The appended MenuItem instance.
        """
        if item.Kind == wx.ITEM_SEPARATOR:
            flags = win32con.MF_SEPARATOR
        else:
            flags = win32con.MF_POPUP | win32con.MF_STRING if item.subMenu else 0
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

    def AppendSubMenu(self, submenu, text, help=""):  # noqa: A002
        """Append a submenu to the menu.

        Args:
            submenu (Menu): The submenu to append.
            text (str): The label text for the submenu.
            help (str): Help text for the submenu, not used in this
                implementation.

        Returns:
            MenuItem: A MenuItem instance representing the submenu.
        """
        item = MenuItem(self, submenu.hmenu, text, help, wx.ITEM_NORMAL, submenu)
        return self.AppendItem(item)

    def AppendRadioItem(self, id, text, help=""):  # noqa: A002
        """Append a radio item to the menu.

        Args:
            id (int): The ID of the menu item. If -1, a new ID will be
                generated.
            text (str): The label text for the menu item.
            help (str): Help text for the menu item, not used in this
                implementation.

        Returns:
            MenuItem: A MenuItem instance representing the radio item.
        """
        return self.Append(id, text, help, wx.ITEM_RADIO)

    def AppendSeparator(self):
        """Append a separator to the menu.

        Returns:
            MenuItem: A MenuItem instance representing the separator.
        """
        return self.Append(-1, "", kind=wx.ITEM_SEPARATOR)

    def Check(self, id, check=True):  # noqa: A002
        """Check or uncheck a menu item by its ID.

        Args:
            id (int): The ID of the menu item to check or uncheck.
            check (bool): True to check the menu item, False to uncheck it.
        """
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
        """Destroy the Menu instance and all its menu items."""
        for menuitem in self.MenuItems:
            menuitem.Destroy()
        if not self.Parent:
            if DEBUG or VERBOSE > 1:
                print("DestroyMenu HMENU", self.hmenu)
            win32gui.DestroyMenu(self.hmenu)
        if DEBUG or VERBOSE > 1:
            print("Destroy", self.__class__.__name__, self)
        self._destroyed = True
        wx.EvtHandler.Destroy(self)

    def __bool__(self) -> bool:
        """Return the Menu instance's destroyed state as a bool.

        Returns:
            bool: True if the Menu instance is not destroyed,
        """
        return not self._destroyed

    def Enable(self, id, enable=True):  # noqa: A002
        """Enable or disable a menu item by its ID.

        Args:
            id (int): The ID of the menu item to enable or disable.
            enable (bool): True to enable the menu item, False to disable it.
        """
        flags = win32con.MF_BYCOMMAND
        if not enable:
            flags |= win32con.MF_DISABLED
        item = self._menuitems[id]
        win32gui.EnableMenuItem(self.hmenu, item.Id, flags)
        item.Enabled = enable


class MenuItem:
    """A class that represents a menu item in a system tray icon.

    Args:
        menu (Menu): The parent menu to which this item belongs.
        id_ (int): The ID of the menu item. Defaults to -1, which generates a
            new ID.
        text (str): The label text for the menu item.
        help (str): Help text for the menu item, not used in this
            implementation.
        kind (int): The type of the menu item, e.g., wx.ITEM_NORMAL,
            wx.ITEM_CHECK, etc.
        subMenu (Menu): An optional submenu associated with this menu item.
    """

    def __init__(
        self,
        menu,
        id_=-1,
        text="",
        help="",  # noqa: A002
        kind=wx.ITEM_NORMAL,
        subMenu=None,
    ):
        if id_ == -1:
            id_ = IdFactory.NewId()
        self.Menu = menu
        self.Id = id_
        self.ItemLabel = text
        self.Help = help
        self.Kind = kind
        self.Enabled = True
        self.Checked = False
        self.subMenu = subMenu
        if subMenu:
            self.subMenu.Parent = menu

    def Check(self, check=True):
        """Check or uncheck the menu item."""
        self.Checked = check
        if self.Id in self.Menu._menuitems:
            self.Menu.Check(self.Id, check)

    def Destroy(self):
        """Destroy the menu item and its associated submenu if it exists."""
        if self.subMenu:
            self.subMenu.Destroy()
        if DEBUG or VERBOSE > 1:
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
        """Enable or disable the menu item.

        Args:
            enable (bool): True to enable the menu item, False to disable it.
        """
        self.Enabled = enable
        if self.Id in self.Menu._menuitems:
            self.Menu.Enable(self.Id, enable)

    def GetId(self):
        """Get the ID of the menu item.

        Returns:
            int: The ID of the menu item.
        """
        return self.Id


class SysTrayIcon(wx.EvtHandler):
    """A class that creates a system tray icon with a context menu."""

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

        _classAtom = win32gui.RegisterClass(wc)

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
        """Override this method in derived classes.

        Returns:
            Menu: A wx.Menu instance representing the context menu for the
                system tray icon.
        """
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
        """Handle the command event when a menu item is selected.

        Args:
            hwnd (int): Handle to the window.
            msg (int): Message identifier.
            wparam (int): Additional message information, typically the ID of the
                selected menu item.
            lparam (int): Additional message information, not used in this context.

        Returns:
            int: Always returns 0 to indicate the message was processed.
        """
        print(
            f"SysTrayIcon.OnCommand(hwnd={hwnd!r}, msg={msg!r}, "
            f"wparam={wparam!r}, lparam={lparam!r})"
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
        if DEBUG or VERBOSE > 1:
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
        """Handle the window destroy event.

        Args:
            hwnd (int): Handle to the window.
            msg (int): Message identifier.
            wparam (int): Additional message information.
            lparam (int): Additional message information.

        Returns:
            int: Always returns 0 to indicate the message was processed.
        """
        self.Destroy()
        if not wx.GetApp() or not wx.GetApp().IsMainLoopRunning():
            win32gui.PostQuitMessage(0)
        return 0

    def Destroy(self):
        """Destroy the SysTrayIcon instance and remove the icon from the system tray."""
        if self.menu:
            self.menu.Destroy()
        self.RemoveIcon()
        self._destroyed = True
        wx.EvtHandler.Destroy(self)

    def __bool__(self) -> bool:
        """Return the SysTrayIcon instance's destroyed state as a bool.

        Returns:
            bool: True if the SysTrayIcon instance is not destroyed,
        """
        return not self._destroyed

    def OnRightUp(self, event):
        """Handle the right mouse button up event.

        Args:
            event (wx.Event): The event object containing information about the
                right mouse button up event.
        """
        self.PopupMenu(self.CreatePopupMenu())

    def OnTaskbarCreated(self, hwnd, msg, wparam, lparam):
        """Handle the taskbar created event.

        Args:
            hwnd (int): Handle to the window.
            msg (int): Message identifier.
            wparam (int): Additional message information.
            lparam (int): Additional message information.
        """
        if not self._nid:
            return
        hicon, tooltip = self._nid[4:6]
        self._nid = None
        self.SetIcon(hicon, tooltip)

    def OnTaskbarNotify(self, hwnd, msg, wparam, lparam):
        """Handle taskbar notifications.

        Args:
            hwnd (int): Handle to the window.
            msg (int): Message identifier.
            wparam (int): Additional message information.
            lparam (int): Additional message information, indicating the type of
                mouse event (e.g., left button down, right button up).

        Returns:
            int: Always returns 1 to indicate the message was processed.
        """
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
        """Display a context menu at the current cursor position.

        Args:
            menu (Menu): The menu to display.
        """
        if self.in_popup:
            return
        self.in_popup = True
        self.menu = menu
        try:
            pos = win32gui.GetCursorPos()
            # See remarks section under
            # https://msdn.microsoft.com/en-us/library/windows/desktop/ms648002(v=vs.85).aspx
            with contextlib.suppress(win32gui.error):
                win32gui.SetForegroundWindow(self.hwnd)
                # Calls to SetForegroundWindow will fail if (e.g.) the Win10
                # start menu is currently shown
            win32gui.TrackPopupMenu(
                menu.hmenu, win32con.TPM_RIGHTBUTTON, pos[0], pos[1], 0, self.hwnd, None
            )
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        finally:
            self.in_popup = False

    def RemoveIcon(self):
        """Remove the system tray icon.

        Returns:
            bool: True if the icon was removed successfully, False otherwise.
        """
        if not self._nid:
            return False
        self._nid = None
        try:
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
        except win32gui.error:
            return False
        return True

    def SetIcon(self, hicon, tooltip=""):
        """Set the icon and tooltip for the system tray icon.

        Args:
            hicon (wx.Icon or int): The icon to set, can be a wx.Icon instance
                or an icon handle.
            tooltip (str): The tooltip text to display when hovering over the
                icon.

        Returns:
            bool: True if the icon was set successfully, False otherwise.
        """
        if isinstance(hicon, wx.Icon):
            hicon = hicon.GetHandle()
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        msg = win32gui.NIM_MODIFY if self._nid else win32gui.NIM_ADD
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


def _get_selected_menu_item(id: int, menu: Menu) -> None | MenuItem:  # noqa: A002
    """Recursively search for a menu item by ID in the menu and its submenus.

    Args:
        id (int): The ID of the menu item to search for.
        menu (Menu): The menu to search in.

    Returns:
        None | MenuItem: The found menu item or None if not found.
    """
    if id in menu._menuitems:
        return menu._menuitems[id]

    for item in menu.MenuItems:
        if not item.subMenu:
            continue
        item = _get_selected_menu_item(id, item.subMenu)
        if item:
            return item

    return None


def main():
    """Main function to create and run the system tray icon."""
    _app = wx.App(0)
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
