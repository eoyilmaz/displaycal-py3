r"""Reusable scripting / IPC socket server for the Qt UI.

Qt successor to the scripting host that lived on
:class:`DisplayCAL.wx_windows.BaseFrame` (``listen`` / ``connection_handler`` /
``message_handler`` / ``send_response`` / ``finish_processing``). DisplayCAL's
windows can be driven over a TCP socket (the ``displaycal-scripting-client`` and
the ``send_command`` CLI talk to it); the protocol is line-based, with one
command per line and an ``\\4``-terminated response.

The socket lifecycle and the non-UI commands (``getappname``, ``getcfg``,
``getcommands``, ``getdefault(s)``, ``getvalid``, ``setresponseformat``) are
entirely binding-agnostic, so they are carried over essentially verbatim. The
only toolkit-specific piece is marshalling a received command onto the GUI
thread before it touches widgets: wx used ``wx.CallAfter``; here a small
:class:`QObject` bridge re-emits the command through a queued signal so
:meth:`ScriptingHostMixin.finish_processing` runs on the GUI thread.

``finish_processing`` implements the toolkit-agnostic and window-level commands
(``getstate``, ``setcfg``, ``refresh``, ``restore-defaults``, ``setlanguage``,
``exit``, ``close``, ``activate``, ``getactivewindow``, ``getwindows``,
``echo``, ``abort``) and delegates everything else to an overridable
:meth:`process_data`. The deep per-widget introspection commands from the wx
frame (``interact``, ``getuielement(s)``, ``getmenus``/``getmenuitems``,
``getcellvalues``, ``invokemenu``) are inherently window-specific and are left
to be added by individual windows as they are ported.
"""

from __future__ import annotations

import contextlib
import errno
import os
import socket
import sys
import threading
from datetime import datetime
from time import sleep

from qtpy.QtCore import QObject, Qt, Signal
from qtpy.QtWidgets import QApplication, QWidget

from DisplayCAL import config
from DisplayCAL import demjson_compat as demjson
from DisplayCAL import localization as lang
from DisplayCAL.config import (
    APPBASENAME,
    CONFIG_HOME,
    DEFAULTS,
    get_data_path,
    getcfg,
    setcfg,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.network import ScriptingClientSocket, get_network_addr
from DisplayCAL.util_str import safe_str
from DisplayCAL.util_xml import dict2xml
from DisplayCAL.wexpect import split_command_line

#: Per-connection response format ("plain", "json[.pretty]", "xml[.pretty]").
#: Keyed by the live socket, mirroring the wx module-level state.
responseformats: dict = {}

#: Modules whose lock files are scanned to discover running scripting hosts.
_SCRIPTING_HOST_MODULES = (
    "3DLUT-maker",
    "curve-viewer",
    "profile-info",
    "scripting-client",
    "synthprofile",
    "testchart-editor",
    "VRML-to-X3D-converter",
    "apply-profiles",
)


class _FinishBridge(QObject):
    """Marshals a received command onto the GUI thread.

    A message-handler worker thread emits :attr:`requested`; because the bridge
    lives on the GUI thread, the queued connection delivers the command to
    :meth:`ScriptingHostMixin.finish_processing` on the GUI thread.
    """

    #: Emitted with ``(data, conn, command_timestamp)``.
    requested = Signal(object, object, str)


def format_ui_element(  # noqa: C901
    widget: QWidget, file_format: str = "plain"
) -> dict | str:
    """Describe a Qt widget for a scripting response.

    Qt counterpart of :func:`DisplayCAL.wx_windows.format_ui_element`, covering
    the common interactive widgets. Window-specific containers (grids, list
    views) are described by class/name only until the owning window adds richer
    handling.

    Args:
        widget (QWidget): The widget to describe.
        file_format (str): ``"plain"`` for a single text line, otherwise a dict
            (serialized as JSON/XML by :meth:`ScriptingHostMixin.send_response`).

    Returns:
        dict | str: The element description in the requested format.
    """
    cls = type(widget).__name__
    name = widget.objectName() or ""
    enabled = widget.isEnabled()
    label = ""
    value = None
    checked = None
    items: list[str] = []
    if (
        hasattr(widget, "isCheckable")
        and hasattr(widget, "isChecked")
        and widget.isCheckable()
    ):
        # QCheckBox / QRadioButton / checkable QPushButton.
        checked = widget.isChecked()
    if hasattr(widget, "text") and not items:
        with contextlib.suppress(TypeError):
            label = widget.text() or ""
    if hasattr(widget, "currentText"):
        # QComboBox.
        value = widget.currentText()
        if hasattr(widget, "count") and hasattr(widget, "itemText"):
            items = [widget.itemText(i) for i in range(widget.count())]
    elif hasattr(widget, "value") and checked is None:
        # QSpinBox / QDoubleSpinBox / QSlider.
        with contextlib.suppress(TypeError):
            value = widget.value()

    if file_format != "plain":
        uielement: dict = {"class": cls, "name": name, "enabled": enabled}
        if label:
            uielement["label"] = label
        if checked is not None:
            uielement["checked"] = checked
        elif value is not None:
            uielement["value"] = value
        if items:
            uielement["items"] = items
        return uielement

    parts = [cls, name or "-", "enabled" if enabled else "disabled"]
    if checked is not None:
        parts.append("checked" if checked else "unchecked")
    elif value is not None:
        parts.append("value " + demjson.encode(value))
    return " ".join(parts)


def get_toplevel_window(id_name_label: str) -> QWidget | None:
    """Return a visible top-level window matching ``id_name_label``.

    Args:
        id_name_label (str): An object name or window title to match.

    Returns:
        QWidget | None: The most recently stacked matching visible window, or
        ``None`` if none match.
    """
    app = QApplication.instance()
    if app is None:
        return None
    for win in reversed(app.topLevelWidgets()):
        if win.isVisible() and id_name_label in (win.objectName(), win.windowTitle()):
            return win
    return None


class ScriptingHostMixin:
    """Mixin adding the scripting / IPC socket server to a Qt window.

    Mix into a top-level window (e.g. a :class:`~DisplayCAL.ui.base_window.BaseWindow`
    subclass). Call :meth:`listen` once the window exists to start serving, and
    :meth:`stop_listening` (done for you in
    :meth:`~DisplayCAL.ui.base_window.BaseWindow.closeEvent`) to stop.
    """

    # -- server lifecycle --------------------------------------------------

    def listen(self) -> None:
        """Start serving the scripting socket, if one was set up at launch."""
        if not isinstance(getattr(sys, "_appsocket", None), socket.socket):
            return
        addr, port = sys._appsocket.getsockname()
        if addr == "0.0.0.0":  # noqa: S104
            with contextlib.suppress(OSError):
                addr = get_network_addr()
        print(lang.getstr("app.listening", (addr, port)))
        # Re-emit received commands onto the GUI thread (queued connection).
        self._finish_bridge = _FinishBridge()
        self._finish_bridge.requested.connect(
            self.finish_processing, Qt.QueuedConnection
        )
        self.listening = True
        self.listener = threading.Thread(
            target=self.connection_handler,
            name="ScriptingHost.ConnectionHandler",
            daemon=True,
        )
        self.listener.start()

    def stop_listening(self) -> None:
        """Stop serving the scripting socket."""
        self.listening = False

    def open_connection(self, ip: str, port: int) -> ScriptingClientSocket | OSError:
        """Connect to another scripting host's socket.

        Named ``open_connection`` rather than ``connect``: on a ``QObject``
        subclass (every window mixing this in), a plain ``connect`` method is
        silently shadowed by Qt's own signal-connection ``connect`` at the
        binding level regardless of Python MRO, so calling ``self.connect(...)``
        would raise a ``TypeError`` from PySide/PyQt instead of ever reaching
        this method.

        Args:
            ip (str): The IP address to connect to.
            port (int): The port to connect to.

        Returns:
            ScriptingClientSocket | OSError: The connected socket, or the
            ``OSError`` raised on failure.
        """
        if getattr(self, "conn", None):
            self.conn.disconnect()
        conn = ScriptingClientSocket()
        conn.settimeout(3)
        try:
            conn.connect((ip, port))
        except OSError as exception:
            del conn
            return exception
        return conn

    def connection_handler(self) -> None:
        """Accept incoming connections and spawn a handler thread per client."""
        self._msghandlercount = 0
        while self and getattr(self, "listening", False):
            try:
                conn, addrport = sys._appsocket.accept()
            except socket.timeout:
                continue
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                break
            if addrport[0] != "127.0.0.1" and not getcfg("app.allow_network_clients"):
                conn.close()
                print(lang.getstr("app.client.network.disallowed", addrport))
                sleep(0.2)
                continue
            try:
                conn.settimeout(0.2)
            except OSError as exception:
                conn.close()
                print(lang.getstr("app.client.ignored", exception))
                sleep(0.2)
                continue
            print(lang.getstr("app.client.connect", addrport))
            self._msghandlercount += 1
            threading.Thread(
                target=self.message_handler,
                name=f"ScriptingHost.MessageHandler-{self._msghandlercount}",
                args=(conn, addrport),
                daemon=True,
            ).start()
        sys._appsocket.close()

    def message_handler(self, conn: socket.socket, addrport: tuple) -> None:
        """Read commands from one client connection and dispatch them.

        Non-UI commands are answered directly on this worker thread; commands
        that touch the UI are marshalled onto the GUI thread via the bridge.

        Args:
            conn (socket.socket): The client connection.
            addrport (tuple): The client's ``(address, port)``.
        """
        responseformats[conn] = "plain"
        buffer = ""
        while self and getattr(self, "listening", False):
            try:
                incoming = conn.recv(4096)
                if isinstance(incoming, bytes):
                    incoming = incoming.decode("utf-8")
            except socket.timeout:
                continue
            except OSError as exception:
                if exception.errno == errno.EWOULDBLOCK:
                    sleep(0.05)
                    continue
                break
            if not incoming:
                break
            buffer += incoming
            while "\n" in buffer and self and getattr(self, "listening", False):
                end = buffer.find("\n")
                line = buffer[:end].strip()
                buffer = buffer[end + 1 :]
                if not line:
                    continue
                command_timestamp = datetime.now().strftime("%Y-%m-%dTH:%M:%S.%f")
                print(lang.getstr("app.incoming_message", (*addrport, line)))
                data = split_command_line(str(line))
                response = self._handle_non_ui_command(data, conn)
                if response is not None:
                    self.send_response(response, data, conn, command_timestamp)
                    continue
                # UI command: run on the GUI thread.
                self._finish_bridge.requested.emit(data, conn, command_timestamp)
        with contextlib.suppress(OSError):
            conn.shutdown(socket.SHUT_RDWR)
        print(lang.getstr("app.client.disconnect", addrport))
        conn.close()
        responseformats.pop(conn, None)

    # -- non-UI commands (answered off the GUI thread) ---------------------

    def _handle_non_ui_command(  # noqa: C901
        self, data: list, conn: socket.socket
    ) -> object | None:
        """Answer a command that needs no UI access, else return ``None``.

        Args:
            data (list): The split command line.
            conn (socket.socket): The client connection (selects the format).

        Returns:
            The response object, or ``None`` if the command needs the GUI thread.
        """
        fmt = responseformats[conn]
        if data[0] == "getappname" and len(data) == 1:
            return config.PYNAME
        if data[0] == "getcfg" and len(data) < 3:
            if len(data) == 2:
                if data[1] not in DEFAULTS:
                    return "invalid"
                if fmt.startswith("xml"):
                    return {"name": data[1], "value": getcfg(data[1])}
                return {data[1]: getcfg(data[1])}
            response = [] if fmt != "plain" else {}
            for name in sorted(DEFAULTS):
                value = getcfg(name, False)
                if value is None:
                    continue
                if fmt != "plain":
                    response.append({"name": name, "value": value})
                else:
                    response[name] = value
            return response
        if data[0] == "getcommands" and len(data) == 1:
            return sorted(self.get_commands())
        if data[0] == "getdefault" and len(data) == 2:
            if data[1] not in DEFAULTS:
                return "invalid"
            if fmt != "plain":
                return {"name": data[1], "value": DEFAULTS[data[1]]}
            return {data[1]: DEFAULTS[data[1]]}
        if data[0] == "getdefaults" and len(data) == 1:
            response = [] if fmt != "plain" else {}
            for name in sorted(DEFAULTS):
                if fmt != "plain":
                    response.append({"name": name, "value": DEFAULTS[name]})
                else:
                    response[name] = DEFAULTS[name]
            return response
        if data[0] == "getvalid" and len(data) == 1:
            return self._get_valid(fmt)
        if (
            data[0] == "setresponseformat"
            and len(data) == 2
            and data[1] in ("json", "json.pretty", "plain", "xml", "xml.pretty")
        ):
            responseformats[conn] = data[1]
            return "ok"
        return None

    def _get_valid(self, fmt: str) -> dict | list:
        """Return the valid config ranges/values in the requested format.

        Args:
            fmt (str): The response format.

        Returns:
            The valid ranges/values as a dict (structured formats) or a list of
            ``[section]`` / ``name = values`` lines (plain).
        """
        if fmt != "plain":
            response: dict = {}
            for section, options in (
                ("ranges", config.VALID_RANGES),
                ("values", config.VALID_VALUES),
            ):
                valid = response[section] = []
                for name, values in options.items():
                    valid.append({"name": name, "values": values})
            return response
        lines = []
        for section, options in (
            ("ranges", config.VALID_RANGES),
            ("values", config.VALID_VALUES),
        ):
            lines.append(f"[{section}]")
            for name, values in options.items():
                joined = " ".join(demjson.encode(value) for value in values)
                lines.append(f"{name} = {joined}")
        return lines

    # -- command catalog ---------------------------------------------------

    def get_commands(self) -> list:
        """Return the commands this window understands.

        Returns:
            list: The supported command strings (override to extend).
        """
        return self.get_common_commands()

    def get_common_commands(self) -> list:
        """Return the commands every scripting host understands.

        Returns:
            list: The common command strings.
        """
        cmds = [
            "abort",
            "activate [window]",
            "close [window]",
            "echo <string>",
            "exit [force]",
            "getactivewindow",
            "getappname",
            "getcommands",
            "getcfg [option]",
            "getdefault <option>",
            "getdefaults",
            "getstate",
            "getvalid",
            "getwindows",
            "restore-defaults [category...]",
            "setcfg <option> <value>",
            "setresponseformat <format>",
        ]
        if hasattr(self, "update_controls"):
            cmds.append("refresh")
            cmds.append("setlanguage <languagecode>")
        return cmds

    def get_scripting_hosts(self) -> list:
        """Return the running scripting hosts discovered via lock files.

        Returns:
            list: ``"ip:port lockfilebasename"`` entries, sorted.
        """
        scripting_hosts = []
        lock_file_basenames = [APPBASENAME]
        lock_file_basenames.extend(
            f"{APPBASENAME}-{module}" for module in _SCRIPTING_HOST_MODULES
        )
        for lock_file_basename in lock_file_basenames:
            lockfilename = os.path.join(CONFIG_HOME, f"{lock_file_basename}.lock")
            if not os.path.isfile(lockfilename):
                continue
            ports = []
            try:
                with open(lockfilename) as lockfile:
                    for line in lockfile.read().splitlines():
                        if not line:
                            continue
                        port = line.split(":", 1)[1] if ":" in line else line
                        if port:
                            ports.append(port)
            except OSError as exception:
                print(f"Warning - could not read lockfile {lockfilename}:", exception)
            else:
                scripting_hosts.extend(
                    f"127.0.0.1:{port} {lock_file_basename}" for port in ports
                )
        scripting_hosts.sort()
        return scripting_hosts

    def send_command(self, scripting_host_name_suffix: str, command: str) -> object:
        """Send ``command`` to a running scripting host and return its response.

        Args:
            scripting_host_name_suffix (str): Module suffix identifying the host.
            command (str): The command line to send.

        Returns:
            The host's response string, or an ``Exception`` on failure.
        """
        lock_name = APPBASENAME
        scripting_host = APPNAME
        if scripting_host_name_suffix:
            lock_name += "-" + scripting_host_name_suffix
            scripting_host += "-" + scripting_host_name_suffix
        response = None
        try:
            for host in self.get_scripting_hosts():
                ip_port, name = host.split(None, 1)
                if name != lock_name:
                    continue
                ip, port = ip_port.split(":", 1)
                conn = self.open_connection(ip, int(port))
                if isinstance(conn, Exception):
                    raise conn
                # Confirm we reached the expected app (the port could have been
                # reused if it exited unexpectedly).
                conn.send_command("getappname")
                response = conn.get_single_response()
                if response == scripting_host:
                    conn.send_command(command)
                    response = conn.get_single_response()
                    print(f"{scripting_host} {command} returned", response)
                else:
                    print(
                        f"Warning - {scripting_host} not running under expected port",
                        port,
                    )
                del conn
                return response
            print(f"Warning - {scripting_host} not running?")
        except Exception as exception:  # noqa: BLE001
            print(f"Warning - couldn't talk to {scripting_host}:", exception)
            return exception
        return response

    # -- responses ---------------------------------------------------------

    def send_response(
        self,
        response: object,
        data: list,
        conn: socket.socket,
        command_timestamp: str,
        win: QWidget | None = None,
    ) -> None:
        """Serialize ``response`` in the connection's format and send it.

        Args:
            response: The response object (str / list / dict).
            data (list): The command that produced this response.
            conn (socket.socket): The client connection.
            command_timestamp (str): When the command was received.
            win (QWidget | None): The element a UI command acted on, if any.
        """
        fmt = responseformats.get(conn)
        if not fmt:
            # Client connection has broken down in the meantime.
            return
        if response == "invalid":
            print(lang.getstr("app.incoming_message.invalid"))
        if fmt != "plain":
            if not isinstance(response, (str, list)):
                response = [response]
            command = {"name": data[0], "timestamp": command_timestamp}
            if data[1:]:
                command["arguments"] = data[1:]
            response = {
                "command": command,
                "result": response,
                "timestamp": datetime.now().strftime("%Y-%m-%dTH:%M:%S.%f"),
            }
            if win:
                response["object"] = format_ui_element(win, fmt)
        if fmt.startswith("json"):
            response = demjson.encode(response, compactly=fmt == "json")
        elif fmt.startswith("xml"):
            response = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                + (("\n") if fmt == "xml.pretty" else "")
                + dict2xml(response, "response", pretty=fmt == "xml.pretty")
            )
        else:
            if isinstance(response, dict):
                response = [f"{name} = {value}" for name, value in response.items()]
            if isinstance(response, list):
                response = "\n".join(response)
        try:
            conn.sendall(f"{safe_str(response, 'utf-8')}\4".encode())
        except OSError as exception:
            print(exception)

    # -- UI state ----------------------------------------------------------

    def get_app_state(self, file_format: str) -> str:
        """Return the coarse application state for scripting.

        Args:
            file_format (str): The response format (unused; kept for parity).

        Returns:
            str: ``"blocked"`` (a modal dialog is up), ``"busy"`` (the worker is
            running) or ``"idle"``.
        """
        app = QApplication.instance()
        modal = app.activeModalWidget() if app else None
        if modal is not None and modal.isVisible():
            return "blocked"
        if hasattr(self, "worker") and self.worker.is_working():
            return "busy"
        return "idle"

    def get_top_window(self) -> QWidget:
        """Return the window scripting commands should target.

        Returns:
            QWidget: The active modal widget, else the active window, else self.
        """
        app = QApplication.instance()
        if app is not None:
            modal = app.activeModalWidget()
            if modal is not None and modal.isVisible():
                return modal
            active = app.activeWindow()
            if active is not None and active.isVisible():
                return active
        return self

    def close_all(self) -> None:
        """Close every top-level window (used by ``exit``)."""
        app = QApplication.instance()
        if app is None:
            return
        for win in list(app.topLevelWidgets()):
            win.close()

    def process_data(self, data: list) -> str:
        """Handle a window-specific command; overridden by subclasses.

        Args:
            data (list): The split command line.

        Returns:
            str: The response, or ``"invalid"`` if unrecognized.
        """
        return "invalid"

    def activate_self(self) -> None:
        """Bring this window to the front (un-minimize, raise, focus)."""
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def open_files_command(self, data: list, command: str, multi: bool = False) -> str:
        """Handle the standard ``<command> [file...]`` / ``load <file...>`` commands.

        Raises the window and routes any supplied paths through its drop target;
        relative paths that do not exist are resolved via
        :func:`DisplayCAL.config.get_data_path`. Override hook for file-opening
        tools whose drop target already maps suffixes to load handlers.

        Args:
            data (list): The split command line.
            command (str): This tool's own command name (e.g. ``"curve-viewer"``).
            multi (bool): Whether more than one filename is accepted.

        Returns:
            str: ``"ok"``, ``"fail"`` (a path could not be resolved) or
            ``"invalid"`` (not a recognized command/arity).
        """
        if multi:
            recognized = data[0] in (command, "load") and (
                data[0] == command or len(data) > 1
            )
        else:
            recognized = (data[0] == command and len(data) < 3) or (
                data[0] == "load" and len(data) == 2
            )
        if not recognized:
            return "invalid"
        self.activate_self()
        paths = []
        for raw in data[1:]:
            path = raw
            if not os.path.isfile(path) and not os.path.isabs(path):
                path = get_data_path(path)
            if not path:
                return "fail"
            paths.append(path)
        if paths:
            self.droptarget.drop_files(paths)
        return "ok"

    # -- UI commands (run on the GUI thread via the bridge) ----------------

    def finish_processing(
        self, data: list, conn: socket.socket, command_timestamp: str
    ) -> None:
        """Run a UI command on the GUI thread and send its response.

        Args:
            data (list): The split command line.
            conn (socket.socket): The client connection.
            command_timestamp (str): When the command was received.
        """
        fmt = responseformats.get(conn)
        if not fmt:
            return
        state = self.get_app_state("plain")
        force_setcfg = False
        if data[0] == "setcfg" and len(data) == 4 and data[-1] == "force":
            data.pop()
            force_setcfg = True
        allowed_when_busy = {
            "abort",
            "activate",
            "close",
            "exit",
            "getactivewindow",
            "getstate",
            "getwindows",
        }
        if (
            state in ("blocked", "busy")
            and data[0] not in allowed_when_busy
            and not force_setcfg
        ):
            self.send_response(state, data, conn, command_timestamp)
            return
        win = self._dispatch_ui_command(data, fmt)
        # _dispatch_ui_command stores its response on the instance so it can
        # also hand back an optional acted-on window for the response envelope.
        self.send_response(self._last_response, data, conn, command_timestamp, win)

    def _dispatch_ui_command(  # noqa: C901
        self, data: list, fmt: str
    ) -> QWidget | None:
        """Execute a UI/window command, recording the response.

        Args:
            data (list): The split command line.
            fmt (str): The client connection's response format.

        Returns:
            QWidget | None: The window the response should describe, if any.
        """
        response = "ok"
        win = None
        if data[0] == "abort":
            worker = getattr(self, "worker", None)
            if worker and not worker.abort_all() and worker.is_working():
                response = "failed"
        elif data[0] == "exit":
            self.close_all()
        elif data[0] == "close" and len(data) < 3:
            target = (
                get_toplevel_window(data[1])
                if len(data) == 2
                else self.get_top_window()
            )
            if target is not None:
                target.close()
            else:
                response = "invalid"
        elif data[0] == "activate" and len(data) < 3:
            target = (
                get_toplevel_window(data[1])
                if len(data) == 2
                else self.get_top_window()
            )
            if target is not None and target.isVisible():
                if target.isMinimized():
                    target.showNormal()
                target.raise_()
                target.activateWindow()
            else:
                response = "invalid"
        elif data[0] == "echo" and len(data) > 1:
            print(" ".join(data[1:]))
        elif data[0] == "getstate" and len(data) == 1:
            response = self.get_app_state(fmt)
        elif data[0] == "getactivewindow" and len(data) == 1:
            response = format_ui_element(self.get_top_window(), fmt)
        elif data[0] == "getwindows" and len(data) == 1:
            app = QApplication.instance()
            wins = [w for w in app.topLevelWidgets() if w.isVisible()] if app else []
            response = [format_ui_element(w, fmt) for w in wins]
        elif data[0] == "setcfg" and len(data) == 3:
            response = self._set_cfg(data[1], data[2])
        else:
            response = self._process_overridable(data, fmt)
        self._last_response = response
        return win

    def _set_cfg(self, name: str, raw_value: str) -> str:
        """Set a config option from a string value (with type coercion).

        Args:
            name (str): The config option name.
            raw_value (str): The value as received over the socket.

        Returns:
            str: ``"ok"``, ``"failed"`` or ``"invalid"``.
        """
        if name not in DEFAULTS:
            return "invalid"
        value: object = raw_value
        if raw_value == "null":
            value = None
        elif raw_value == "false":
            value = 0
        elif raw_value == "true":
            value = 1
        elif DEFAULTS[name] is not None:
            with contextlib.suppress(ValueError):
                value = type(DEFAULTS[name])(raw_value)
        setcfg(name, value)
        return "ok" if getcfg(name, False) == value else "failed"

    def _process_overridable(self, data: list, fmt: str) -> str:
        """Delegate to :meth:`process_data`, then handle generic fallbacks.

        Args:
            data (list): The split command line.
            fmt (str): The client connection's response format.

        Returns:
            str: The command response.
        """
        try:
            response = self.process_data(data)
        except Exception as exception:  # noqa: BLE001
            print(exception)
            if fmt != "plain":
                return {
                    "class": exception.__class__.__name__,
                    "error": str(exception),
                }
            return "error " + demjson.encode(str(exception))
        if response != "invalid":
            return response
        if data[0] == "refresh" and len(data) == 1 and hasattr(self, "update_controls"):
            self.update_controls()
            return "ok"
        if data[0] == "restore-defaults":
            for name in DEFAULTS:
                if len(data) > 1 and not any(
                    name.startswith(prefix) for prefix in data[1:]
                ):
                    continue
                setcfg(name, None)
            return "ok"
        if (
            data[0] == "setlanguage"
            and len(data) == 2
            and hasattr(self, "update_controls")
        ):
            setcfg("lang", data[1])
            if hasattr(self, "setup_language"):
                self.setup_language()
            self.update_controls()
            return "ok"
        return response
