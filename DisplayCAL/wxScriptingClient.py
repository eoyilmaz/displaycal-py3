# -*- coding: utf-8 -*-

import errno
import os
import socket
import sys
import threading
from time import sleep

from DisplayCAL import (
    config,
    localization as lang,
)
from DisplayCAL.config import confighome, getcfg, geticon, initcfg, setcfg, writecfg
from DisplayCAL.meta import (
    name as appname,
)
from DisplayCAL.util_str import safe_str, universal_newlines
from DisplayCAL.wexpect import split_command_line
from DisplayCAL.wxaddons import wx
from DisplayCAL.wxfixes import GenBitmapButton
from DisplayCAL.wxwindows import BaseApp, SimpleTerminal, numpad_keycodes

# from wexpect import split_command_line

import wx.lib.delayedresult as delayedresult

ERRORCOLOR = "#FF3300"
RESPONSECOLOR = "#CCCCCC"


class ScriptingClientFrame(SimpleTerminal):
    def __init__(self):
        SimpleTerminal.__init__(
            self,
            None,
            wx.ID_ANY,
            lang.getstr("scripting-client"),
            start_timer=False,
            pos=(getcfg("position.scripting.x"), getcfg("position.scripting.y")),
            size=(getcfg("size.scripting.w"), getcfg("size.scripting.h")),
            consolestyle=wx.TE_CHARWRAP
            | wx.TE_MULTILINE
            | wx.TE_PROCESS_ENTER
            | wx.TE_RICH
            | wx.VSCROLL
            | wx.NO_BORDER,
            show=False,
            name="scriptingframe",
        )
        self.SetIcons(
            config.get_icon_bundle([256, 48, 32, 16], appname + "-scripting-client")
        )
        self.console.SetForegroundColour("#EEEEEE")
        self.console.SetDefaultStyle(wx.TextAttr("#EEEEEE"))

        self.busy = False
        self.commands = []
        self.history = []
        self.historyfilename = os.path.join(
            confighome, "%s-scripting-client.history" % config.appbasename
        )
        if os.path.isfile(self.historyfilename):
            try:
                with open(self.historyfilename) as historyfile:
                    for line in historyfile:
                        self.history.append(line.rstrip("\r\n"))
            except EnvironmentError as exception:
                print("Warning - couldn't read history file:", exception)
        # Always have empty selection at bottom
        self.history.append("")
        self.historypos = len(self.history) - 1

        self.overwrite = False

        # Determine which application we should connect to by default (if any)
        self.conn = None
        scripting_hosts = self.get_scripting_hosts()

        self.sizer.Layout()
        if sys.platform != "darwin":
            # Under Mac OS X, the transparency messes up the window shadow if
            # there is another window's border behind
            self.SetTransparent(240)

        self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Unbind(wx.EVT_CHAR_HOOK)
        self.console.Unbind(wx.EVT_KEY_DOWN, self.console)
        self.console.Bind(wx.EVT_KEY_DOWN, self.key_handler)
        self.console.Bind(wx.EVT_TEXT_COPY, self.copy_text_handler)
        self.console.Bind(wx.EVT_TEXT_PASTE, self.paste_text_handler)
        if sys.platform == "darwin":
            # Under Mac OS X, pasting text via the context menu isn't catched
            # by EVT_TEXT_PASTE. TODO: Implement custom context menu.
            self.console.Bind(wx.EVT_CONTEXT_MENU, lambda event: None)

        if scripting_hosts:
            self.add_text("> getscriptinghosts" + "\n")
            for host in scripting_hosts:
                self.add_text(host + "\n")
            ip_port = scripting_hosts[0].split()[0]
            self.add_text("> connect " + ip_port + "\n")
            self.connect_handler(ip_port)

    def OnActivate(self, event):
        self.console.SetFocus()
        linecount = self.console.GetNumberOfLines()
        lastline = self.console.GetLineText(linecount - 1)
        lastpos = self.console.GetLastPosition()
        start, end = self.console.GetSelection()
        if start == end and self.console.GetInsertionPoint() < lastpos - len(lastline):
            self.console.SetInsertionPoint(lastpos)

    def OnClose(self, event):
        # So we can send_command('close') ourselves without prematurely exiting
        # the wx main loop
        while self.busy:
            wx.Yield()
            sleep(0.05)
        # Hide first (looks nicer)
        self.Hide()
        try:
            with open(self.historyfilename, "wb") as historyfile:
                for command in self.history:
                    if command:
                        historyfile.write(
                            (safe_str(command, "UTF-8") + os.linesep).encode("utf-8")
                        )
        except EnvironmentError as exception:
            print("Warning - couldn't write history file:", exception)
        self.listening = False
        # Need to use CallAfter to prevent hang under Windows if minimized
        wx.CallAfter(self.Destroy)

    def OnMove(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            x, y = self.GetScreenPosition()
            setcfg("position.scripting.x", x)
            setcfg("position.scripting.y", y)
        if event:
            event.Skip()

    def OnSize(self, event=None):
        if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
            w, h = self.ClientSize
            setcfg("size.scripting.w", w)
            setcfg("size.scripting.h", h)
        if event:
            event.Skip()

    def add_error_text(self, text):
        self.add_text(text)
        end = self.console.GetLastPosition()
        start = end - len(text)
        self.mark_text(start, end, ERRORCOLOR)

    def check_result(
        self, delayedResult, get_response=False, additional_commands=None, colorize=True
    ):
        try:
            result = delayedResult.get()
        except Exception as exception:
            if hasattr(exception, "originalTraceback"):
                self.add_text(exception.originalTraceback)
            result = exception
        if result:
            if isinstance(result, socket.socket):
                self.conn = result
                result = lang.getstr("connection.established")
            text = "%s\n" % result
            self.add_text(text)
            if colorize or isinstance(result, Exception):
                end = self.console.GetLastPosition()
                start = end - len(text)
                if isinstance(result, Exception):
                    color = ERRORCOLOR
                else:
                    color = RESPONSECOLOR
                self.mark_text(start, end, color)
        if get_response and not isinstance(result, Exception):
            delayedresult.startWorker(
                self.check_result, get_response, cargs=(False, additional_commands)
            )
        else:
            self.add_text("> ")
            if additional_commands:
                self.add_text(additional_commands[0].rstrip("\n"))
                if additional_commands[0].endswith("\n"):
                    self.send_command_handler(
                        additional_commands[0], additional_commands[1:]
                    )
                    return
            self.console.SetFocus()
            self.busy = False

    def clear(self):
        self.console.Clear()
        self.add_text("> ")
        self.console.SetInsertionPoint(2)

    def connect_handler(self, ip_port):
        ip, port = ip_port.split(":", 1)
        try:
            port = int(port)
        except ValueError:
            self.add_error_text(lang.getstr("port.invalid", port) + "\n")
            self.add_text("> ")
            return
        if self.conn:
            self.disconnect()
        self.add_text(lang.getstr("connecting.to", (ip, port)) + "\n")
        self.busy = True
        delayedresult.startWorker(
            self.check_result,
            self.connect,
            cargs=(self.get_app_info, None, False),
            wargs=(ip, port),
        )

    def copy_text_handler(self, event):
        # Override native copy to clipboard because reading the text back
        # from wx.TheClipboard results in wrongly encoded characters under
        # Mac OS X
        # TODO: The correct way to fix this would actually be in the pasting
        # code because pasting text that was copied from other sources still
        # has the problem with this workaround
        clipdata = wx.TextDataObject()
        clipdata.SetText(self.console.GetStringSelection())
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(clipdata)
        wx.TheClipboard.Close()

    def disconnect(self):
        if self.conn:
            try:
                peer = self.conn.getpeername()
                self.conn.shutdown(socket.SHUT_RDWR)
            except socket.error as exception:
                if exception.errno != errno.ENOTCONN:
                    self.add_text("%s\n" % exception)
            else:
                self.add_text(lang.getstr("disconnected.from", peer) + "\n")
            self.conn.close()
            del self.conn
            self.conn = None
            self.commands = []
        else:
            self.add_error_text(lang.getstr("not_connected") + "\n")

    def get_app_info(self):
        commands = ["setresponseformat plain", "getcommands", "getappname"]
        try:
            for command in commands:
                self.conn.send_command(command)
                response = self.conn.get_single_response()
                if command == "getcommands":
                    self.commands = response.splitlines()
                elif command == "getappname":
                    wx.CallAfter(
                        self.add_text,
                        lang.getstr(
                            "connected.to.at", ((response,) + self.conn.getpeername())
                        )
                        + "\n%s\n" % lang.getstr("scripting-client.cmdhelptext"),
                    )
        except socket.error as exception:
            return exception

    def get_commands(self):
        return self.get_common_commands() + [
            "clear",
            "connect <ip>:<port>",
            "disconnect",
            "echo <string>",
            "getscriptinghosts",
        ]

    def get_common_commands(self):
        cmds = SimpleTerminal.get_common_commands(self)
        return [cmd for cmd in cmds if not cmd.startswith("echo ")]

    def get_last_line(self):
        linecount = self.console.GetNumberOfLines()
        lastline = self.console.GetLineText(linecount - 1)
        lastpos = self.console.GetLastPosition()
        start, end = self.console.GetSelection()
        startcol, startrow = self.console.PositionToXY(start)
        endcol, endrow = self.console.PositionToXY(end)
        if startcol > lastpos or endcol > lastpos:
            # Under Mac OS X, PositionToXY seems to be broken and returns insane
            # numbers. Calculate them ourselves. Note they will only be correct
            # for the last line, but that's all we care about.
            startcol = len(lastline) - (lastpos - start)
            endcol = len(lastline) - (lastpos - end)
        return lastline, lastpos, startcol, endcol

    def get_response(self):
        try:
            return b"< " + b"\n< ".join(self.conn.get_single_response().splitlines())
        except socket.error as exception:
            return exception

    def key_handler(self, event):
        # safe_print("KeyCode", event.KeyCode, "UnicodeKey", event.UnicodeKey,
        # "AltDown:", event.AltDown(),
        # "CmdDown:", event.CmdDown(),
        # "ControlDown:", event.ControlDown(),
        # "MetaDown:", event.MetaDown(),
        # "ShiftDown:", event.ShiftDown(),
        # "console.CanUndo:", self.console.CanUndo(),
        # "console.CanRedo:", self.console.CanRedo())
        insertionpoint = self.console.GetInsertionPoint()
        lastline, lastpos, startcol, endcol = self.get_last_line()
        # safe_print(insertionpoint, lastline, lastpos, startcol, endcol)
        cmd_or_ctrl = (event.ControlDown() or event.CmdDown()) and not event.AltDown()
        if cmd_or_ctrl and event.KeyCode == 65:
            # A
            self.console.SelectAll()
        elif cmd_or_ctrl and event.KeyCode in (67, 88):
            # C
            self.copy_text_handler(None)
        elif insertionpoint >= lastpos - len(lastline):
            if cmd_or_ctrl:
                if startcol > 1 and event.KeyCode == 86:
                    # V
                    self.paste_text_handler(None)
                elif event.KeyCode in (89, 90):
                    # Y / Z
                    if event.KeyCode == 89 or (
                        sys.platform != "win32" and event.ShiftDown()
                    ):
                        if self.console.CanRedo():
                            self.console.Redo()
                        else:
                            wx.Bell()
                    elif self.console.CanUndo() and lastline[2:]:
                        self.console.Undo()
                    else:
                        wx.Bell()
                elif event.KeyCode != wx.WXK_SHIFT and event.UnicodeKey:
                    # wxPython 3 "Phoenix" defines UnicodeKey as "\x00" when
                    # control key pressed
                    if event.UnicodeKey != "\0":
                        wx.Bell()
            elif event.KeyCode in (10, 13, wx.WXK_NUMPAD_ENTER):
                # Enter, return key
                self.send_command_handler(lastline[2:])
            elif event.KeyCode == wx.WXK_BACK:
                # Backspace
                if startcol > 1 and endcol > 2:
                    if endcol > startcol:
                        # TextCtrl.WriteText would be optimal, but it doesn't
                        # do anything under wxGTK with wxPython 2.8.12
                        self.add_text("\r" + lastline[:startcol] + lastline[endcol:])
                        self.console.SetInsertionPoint(
                            lastpos - len(lastline) + startcol
                        )
                    else:
                        event.Skip()
                else:
                    wx.Bell()
            elif event.KeyCode in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
                if startcol > 1 and (endcol < len(lastline) or startcol < endcol):
                    if endcol > startcol:
                        # TextCtrl.WriteText would be optimal, but it doesn't
                        # do anything under wxGTK with wxPython 2.8.12
                        self.add_text("\r" + lastline[:startcol] + lastline[endcol:])
                        self.console.SetInsertionPoint(
                            lastpos - len(lastline) + startcol
                        )
                    else:
                        event.Skip()
                else:
                    wx.Bell()
            elif event.KeyCode in (
                wx.WXK_DOWN,
                wx.WXK_NUMPAD_DOWN,
                wx.WXK_NUMPAD_PAGEDOWN,
                wx.WXK_PAGEDOWN,
            ):
                if self.historypos < len(self.history) - 1:
                    self.historypos += 1
                    self.add_text("\r> " + self.history[self.historypos])
                else:
                    wx.Bell()
            elif event.KeyCode in (wx.WXK_END, wx.WXK_NUMPAD_END):
                event.Skip()
            elif event.KeyCode in (wx.WXK_HOME, wx.WXK_NUMPAD_HOME):
                self.console.SetInsertionPoint(lastpos - len(lastline) + 2)
            elif event.KeyCode in (wx.WXK_INSERT, wx.WXK_NUMPAD_INSERT):
                self.overwrite = not self.overwrite
            elif event.KeyCode in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT):
                if startcol > 2:
                    event.Skip()
                else:
                    wx.Bell()
            elif event.KeyCode in (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT):
                if endcol < len(lastline):
                    event.Skip()
                else:
                    wx.Bell()
            elif event.KeyCode in (
                wx.WXK_UP,
                wx.WXK_NUMPAD_UP,
                wx.WXK_NUMPAD_PAGEUP,
                wx.WXK_PAGEUP,
            ):
                if self.historypos > 0:
                    self.historypos -= 1
                    self.add_text("\r> " + self.history[self.historypos])
                else:
                    wx.Bell()
            elif event.KeyCode == wx.WXK_TAB:
                # Tab completion
                # Can't use built-in AutoComplete feature because it only
                # works for single-line TextCtrls
                commonpart = lastline[2:endcol]
                candidates = []
                for command in sorted(list(set(self.commands + self.get_commands()))):
                    command = command.split()[0]
                    if command.startswith(commonpart):
                        candidates.append(command)
                findcommon = bool(candidates)
                while findcommon and len(candidates[0]) > len(commonpart):
                    commonpart += candidates[0][len(commonpart)]
                    for candidate in candidates:
                        if candidate.startswith(commonpart):
                            continue
                        else:
                            commonpart = commonpart[:-1]
                            findcommon = False
                            break
                if len(candidates) > 1:
                    self.add_text("\n%s\n" % " ".join(candidates))
                self.add_text("\r> " + commonpart + lastline[endcol:])
                self.console.SetInsertionPoint(
                    self.console.GetLastPosition() - len(lastline[endcol:])
                )
            elif event.UnicodeKey or event.KeyCode in numpad_keycodes:
                if startcol > 1:
                    event.Skip()
                    if self.overwrite and startcol == endcol:
                        self.add_text(
                            "\r> " + lastline[2:startcol] + lastline[endcol + 1 :]
                        )
                        self.console.SetInsertionPoint(insertionpoint)
                else:
                    wx.Bell()
                    self.console.SetInsertionPoint(lastpos)
        elif event.KeyCode not in (
            wx.WXK_ALT,
            wx.WXK_COMMAND,
            wx.WXK_CONTROL,
            wx.WXK_SHIFT,
        ):
            wx.Bell()
            self.console.SetInsertionPoint(lastpos)

    def mark_text(self, start, end, color):
        self.console.SetStyle(start, end, wx.TextAttr(color))

    def paste_text_handler(self, event):
        do = wx.TextDataObject()
        wx.TheClipboard.Open()
        success = wx.TheClipboard.GetData(do)
        wx.TheClipboard.Close()
        if success:
            insertionpoint = self.console.GetInsertionPoint()
            lastline, lastpos, startcol, endcol = self.get_last_line()
            cliptext = universal_newlines(do.GetText())
            lines = cliptext.replace("\n", "\n\0").split("\0")
            command1 = lastline[2:startcol] + lines[0].rstrip("\n") + lastline[endcol:]
            self.add_text("\r> " + command1)
            if "\n" in cliptext:
                self.send_command_handler(command1, lines[1:])
            else:
                self.console.SetInsertionPoint(insertionpoint + len(cliptext))

    def process_data(self, data):
        if data[0] == "echo" and len(data) > 1:
            linecount = self.console.GetNumberOfLines()
            lastline = self.console.GetLineText(linecount - 1)
            if lastline:
                self.add_text("\n")
            txt = " ".join(data[1:])
            print(txt)
            self.add_text(txt + "\n")
            if lastline:
                self.add_text("> ")
            return "ok"
        return "invalid"

    def process_data_local(self, data):
        if data[0] == "clear" and len(data) == 1:
            self.clear()
        elif data[0] == "connect" and len(data) == 2 and len(data[1].split(":")) == 2:
            wx.CallAfter(self.connect_handler, data[1])
        elif data[0] == "disconnect" and len(data) == 1:
            self.disconnect()
            self.add_text("> ")
        # elif data[0] == "echo" and len(data) > 1:
        # self.add_text(" ".join(data[1:]) + "\n")
        # return
        elif data[0] == "getscriptinghosts" and len(data) == 1:
            return self.get_scripting_hosts()
        else:
            return "invalid"
        return "ok"

    def send_command(self, command):
        try:
            self.conn.send_command(command)
        except socket.error as exception:
            return exception
        if not wx.GetApp().IsMainLoopRunning():
            delayedresult.AbortEvent()()

    def send_command_handler(self, command, additional_commands=None):
        self.add_text("\n")
        command = command.strip()
        if not command:
            self.add_text("> ")
            return
        data = split_command_line(command)
        response = self.process_data_local(data)
        if response == "ok":
            pass
        elif isinstance(response, list):
            self.add_text("\n".join(response))
            self.add_text("\n> ")
        elif not self or not self.conn:
            self.add_error_text(lang.getstr("not_connected") + "\n")
            self.add_text("> ")
        else:
            self.busy = True
            delayedresult.startWorker(
                self.check_result,
                self.send_command,
                cargs=(self.get_response, additional_commands),
                wargs=(command,),
            )
        self.history.insert(len(self.history) - 1, command)
        if len(self.history) > 1000:
            del self.history[0]
        self.historypos = len(self.history) - 1


def main():
    config.initcfg("scripting-client")
    lang.init()
    app = BaseApp(0)
    app.TopWindow = ScriptingClientFrame()
    if sys.platform == "darwin":
        app.TopWindow.init_menubar()
    app.TopWindow.listen()
    app.TopWindow.Show()
    app.MainLoop()
    writecfg(
        module="scripting-client", options=("position.scripting", "size.scripting")
    )


if __name__ == "__main__":
    main()
