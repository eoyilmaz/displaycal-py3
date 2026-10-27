"""Apply-profiles tray daemon -- Qt port.

Qt counterpart of :class:`DisplayCAL.profile_loader.ProfileLoader` /
:class:`DisplayCAL.profile_loader.TaskBarIcon`: the background daemon that
loads calibration/profiles on login, normally registered as a startup task
(``displaycal-apply-profiles``).

:class:`QtProfileLoader` subclasses the wx ``ProfileLoader`` and overrides only
its small set of wx-specific hook methods (``_bootstrap_app``, ``_setup_ui``,
``_teardown_ui``, ``_refresh_visual_state``, ``notify``,
``apply_profiles_and_warn_on_error``, ``_toggle_fix_profile_associations``,
``exit``); everything else (state setup, ``apply_profiles()``'s
dispwin/colord/macOS-verify-retry loop, ``_should_apply_profiles``,
``writecfg``, ``_macos_watch``, ``_is_displaycal_running``, ...) is inherited
unchanged, so the actual calibration-loading logic can never drift between
the two UI toolkits.

Unlike the wx tray (Windows-only), the Qt tray icon is enabled on every
platform: ``QSystemTrayIcon`` makes this essentially free, and it is the only
way to see/exercise this daemon's UI outside of a Windows box.

The Windows device/process hot-plug monitoring thread
(``ProfileLoader._check_display_conf``, started here as
``_check_display_conf_thread``) *is* started on Windows, giving this build
the same "reapply when displays change or other calibration software
launches/exits" behavior as the wx build; only its handful of direct wx
GUI-thread touchpoints (``wx.CallAfter``, wx window enumeration, the taskbar
icon's busy animation) are overridden below via the toolkit hooks
``ProfileLoader`` exposes for them
(``_post_to_gui_thread``/``_post_to_gui_thread_delayed``,
``_enumerate_own_top_level_windows``, ``_animate_busy_icon``,
``_request_forced_shutdown``) -- the polling/decision logic itself is
inherited unchanged, same as everything else. The
``apply-profiles``/``reset-vcgt`` IPC commands and a tray double-click still
also call ``QtProfileLoader.trigger_reapply()`` for an immediate
(backgrounded) re-apply rather than waiting on the poller's ~3 second cycle;
harmless on Windows (the two simply race on ``self.lock``) and still the only
route to a reapply on the platforms where the poller doesn't run. Profile
Associations and Fix Profile Associations (see
:mod:`DisplayCAL.ui.tools.profile_associations` and
:mod:`DisplayCAL.ui.tools.fix_profile_associations`) are both ported, but
wired up on Windows only -- the WCS/registry APIs and device enumeration they
drive (and ``ProfileLoader.monitors``, the display list they read) have no
cross-platform equivalent.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import Callable

from qtpy.QtCore import QObject, Qt, QTimer, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QActionGroup,
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from DisplayCAL import config, profile_loader
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.profile_loader import calibration_management_isenabled
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap, pil_to_qpixmap, rotate_hue
from DisplayCAL.ui.scripting import ScriptingHostMixin

_BITDEPTHS = (8, 10, 12, 14, 16)

#: Tooltip for menu items whose dialog has not been ported to Qt yet (see
#: module docstring's list of deferred follow-ups). Not run through
#: ``lang.getstr`` -- this is a temporary Qt-build-only label, not worth
#: adding a translation key for across every locale until the dialogs land.
_NOT_AVAILABLE_TOOLTIP = "Not yet available in the Qt build"


class _NotifyBridge(QObject):
    """Marshals :meth:`QtProfileLoader.notify` onto the GUI thread."""

    #: Emitted with ``(results, errors, sticky, show_notification)``.
    requested = Signal(list, list, bool, bool)


class _CallBridge(QObject):
    """Marshals arbitrary callables onto the GUI thread.

    Backs :meth:`QtProfileLoader._post_to_gui_thread`/
    :meth:`~QtProfileLoader._post_to_gui_thread_delayed`, the toolkit hooks
    the inherited hot-plug monitoring thread
    (:meth:`~DisplayCAL.profile_loader.ProfileLoader._check_display_conf`,
    running on a background thread) uses instead of calling ``wx.CallAfter``
    directly. A plain ``QTimer.singleShot`` from that background thread would
    not work: the timer would be constructed there and never fire, since that
    thread runs no Qt event loop to deliver it.
    """

    #: Emitted with ``(func, args, delay_ms)``.
    requested = Signal(object, tuple, int)


class _ScriptingHost(ScriptingHostMixin, QWidget):
    """Hidden widget exposing the daemon's IPC command surface.

    A never-shown ``QWidget`` (rather than a bare ``QObject``): several
    :class:`~DisplayCAL.ui.scripting.ScriptingHostMixin` methods
    (``activate_self``, ``get_top_window``'s ``self`` fallback) assume
    ``QWidget``-shaped methods. Mirrors wx's ``PLFrame``.

    Args:
        pl (QtProfileLoader): The owning profile loader.
    """

    def __init__(self, pl: QtProfileLoader) -> None:
        super().__init__()
        self.pl = pl
        self.setObjectName(f"{APPNAME}-apply-profiles")
        self.setWindowTitle(pl.get_title())

    def close(self) -> bool:
        """Quit the application unconditionally.

        The generic ``exit`` IPC command
        (:meth:`~DisplayCAL.ui.scripting.ScriptingHostMixin.close_all`) closes
        every top-level widget, which is this method for the never-shown IPC
        host -- there is no visible window whose closing would otherwise tell
        Qt to quit. Unlike the tray menu's Quit action
        (:meth:`QtProfileLoader.exit`), this skips the confirmation dialog:
        an IPC caller asking the daemon to exit has no user present to answer
        one.

        Returns:
            bool: Always True (mirrors ``QWidget.close``'s return value).
        """
        app = QApplication.instance()
        if app is not None:
            app.quit()
        return super().close()

    def get_commands(self) -> list:
        """Return the commands this daemon understands.

        Returns:
            list: The common commands plus the apply-profiles specific ones.
        """
        return [
            *self.get_common_commands(),
            "apply-profiles [force|display-changed]",
            "notify <message> [silent][sticky]",
            "reset-vcgt [force]",
            "setlanguage <languagecode>",
        ]

    def process_data(self, data: list) -> str:  # noqa: C901
        """Handle the apply-profiles specific IPC commands.

        Mirrors :meth:`DisplayCAL.profile_loader.PLFrame.process_data`.

        Args:
            data (list): The split command line.

        Returns:
            str: The response, or ``"invalid"`` if unrecognized.
        """
        pl = self.pl
        if data[0] in ("apply-profiles", "reset-vcgt") and (
            len(data) == 1
            or (len(data) == 2 and data[1] in ("force", "display-changed"))
        ):
            if (
                not ("--force" in sys.argv[1:] or len(data) == 2)
                and calibration_management_isenabled()
            ):
                return lang.getstr("calibration.load.handled_by_os")
            if (len(data) == 1 and pl._is_displaycal_running()) or pl._is_other_running(
                False
            ):
                return "forbidden"
            if data[-1] == "display-changed":
                with pl.lock:
                    if pl._has_display_changed:
                        pl._manual_restore = getcfg("profile.load_on_login") and 2
            elif data[0] == "reset-vcgt":
                pl._set_reset_gamma_ramps(None, len(data))
            else:
                pl._set_manual_restore(None, len(data))
            # Trigger the reload right away instead of only flipping a flag
            # for the hot-plug poller (Windows only -- see module docstring)
            # to notice on its next ~3 second cycle.
            pl.trigger_reapply()
            return "ok"
        if data[0] == "notify" and (
            len(data) == 2
            or (len(data) == 3 and data[2] in ("silent", "sticky"))
            or (len(data) == 4 and "silent" in data[2:] and "sticky" in data[2:])
        ):
            pl.notify(
                [data[1]],
                [],
                sticky="sticky" in data[2:],
                show_notification="silent" not in data[2:],
            )
            return "ok"
        if data[0] == "setlanguage" and len(data) == 2:
            setcfg("lang", data[1])
            pl._refresh_visual_state()
            pl.writecfg()
            return "ok"
        return "invalid"


class ApplyProfilesTrayIcon(QSystemTrayIcon):
    """Qt tray icon for the apply-profiles daemon.

    Qt counterpart of :class:`DisplayCAL.profile_loader.TaskBarIcon`,
    including its frame-by-frame busy animation (see :meth:`animate`).

    Args:
        pl (QtProfileLoader): The owning profile loader.
    """

    def __init__(self, pl: QtProfileLoader) -> None:
        self._icon_index = 0
        self._active_icons: list[QIcon] = []
        self._build_active_icons()
        super().__init__(self._active_icons[0])
        self.pl = pl
        self._reset_icon = QIcon(get_theme_pixmap(16, "apply-profiles-reset"))
        self._error_icon = QIcon(get_theme_pixmap(16, "apply-profiles-error"))
        self._balloon_text: str | None = None
        self._balloon_icon = QSystemTrayIcon.MessageIcon.Information
        self._notification_shown = False
        self.setToolTip(pl.get_title())
        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._rebuild_menu)
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)
        self._rebuild_menu()
        self.set_visual_state()

    def _build_active_icons(self) -> None:
        """(Re)build the busy-animation frame list from the current cfg.

        Mirrors wx's ``TaskBarIcon.set_icons``: 1/4/8 frames depending on
        ``profile_loader.tray_icon_animation_quality`` (0/1/2), each the base
        tray icon with its hue rotated by an even fraction of the full circle.
        """
        from PIL import Image

        anim_quality = getcfg("profile_loader.tray_icon_animation_quality")
        numframes = 8 if anim_quality == 2 else 4 if anim_quality == 1 else 1
        path = config.get_data_path("theme/icons/16x16/apply-profiles-tray.png")
        base = Image.open(path).convert("RGBA")
        self._active_icons = [
            QIcon(pil_to_qpixmap(rotate_hue(base, i / numframes)))
            for i in range(numframes)
        ]
        self._icon_index = 0

    # -- menu ----------------------------------------------------------

    def _rebuild_menu(self) -> None:  # noqa: C901
        """Rebuild the context menu from live config.

        Mirrors wx's ``TaskBarIcon.CreatePopupMenu`` (rebuilt on every popup).
        """
        pl = self.pl
        menu = self._menu
        menu.clear()

        blocked = pl._is_displaycal_running() or pl._is_other_running(False)
        managed = "--force" not in sys.argv[1:] and calibration_management_isenabled()

        restore_group = QActionGroup(menu)
        restore_group.setExclusive(True)
        restore_action = menu.addAction(
            lang.getstr("calibration.load_from_display_profiles")
        )
        restore_action.setCheckable(True)
        restore_action.setEnabled(not blocked and not managed)
        restore_action.setChecked(not pl._reset_gamma_ramps)
        restore_group.addAction(restore_action)
        restore_action.triggered.connect(lambda: pl._set_manual_restore(True))

        reset_action = menu.addAction(lang.getstr("calibration.reset"))
        reset_action.setCheckable(True)
        reset_action.setEnabled(not blocked and not managed)
        reset_action.setChecked(bool(pl._reset_gamma_ramps))
        restore_group.addAction(reset_action)
        reset_action.triggered.connect(lambda: pl._set_reset_gamma_ramps(True))

        menu.addSeparator()

        preserve_label = (
            lang.getstr("profile.load_on_login")
            + " && "
            + (
                lang.getstr("calibration.preserve")[0].lower()
                + lang.getstr("calibration.preserve")[1:]
                if lang.getcode() != "de"
                else lang.getstr("calibration.preserve")
            )
        )
        preserve_action = menu.addAction(preserve_label)
        preserve_action.setCheckable(True)
        preserve_action.setEnabled(not blocked and not managed)
        preserve_action.setChecked(bool(getcfg("profile.load_on_login")))
        preserve_action.triggered.connect(self._on_preserve_toggled)

        fix_action = menu.addAction(
            lang.getstr("profile_loader.fix_profile_associations")
        )
        fix_action.setCheckable(True)
        if pl._can_fix_profile_associations():
            fix_action.setChecked(
                bool(getcfg("profile_loader.fix_profile_associations"))
            )
            fix_action.triggered.connect(self._on_fix_profile_associations_toggled)
        else:
            fix_action.setEnabled(False)
            fix_action.setToolTip(_NOT_AVAILABLE_TOOLTIP)

        notifications_action = menu.addAction(lang.getstr("show_notifications"))
        notifications_action.setCheckable(True)
        notifications_action.setChecked(
            bool(getcfg("profile_loader.show_notifications"))
        )
        notifications_action.triggered.connect(
            lambda checked: setcfg("profile_loader.show_notifications", int(checked))
        )

        animation_action = menu.addAction(lang.getstr("tray_icon_animation"))
        animation_action.setCheckable(True)
        animation_action.setChecked(
            bool(getcfg("profile_loader.tray_icon_animation_quality"))
        )
        animation_action.triggered.connect(self._on_animation_toggled)

        menu.addSeparator()

        bitdepth_menu = menu.addMenu(lang.getstr("bitdepth"))
        bitdepth_group = QActionGroup(bitdepth_menu)
        bitdepth_group.setExclusive(True)
        current_bits = getcfg("profile_loader.quantize_bits")
        for bits in _BITDEPTHS:
            action = bitdepth_menu.addAction(str(bits))
            action.setCheckable(True)
            action.setChecked(bits == current_bits)
            action.triggered.connect(lambda checked, bits=bits: self._on_bitdepth(bits))
            bitdepth_group.addAction(action)

        menu.addSeparator()

        exceptions_action = menu.addAction(lang.getstr("exceptions"))
        exceptions_action.triggered.connect(pl.set_exceptions)

        menu.addSeparator()

        associations_action = menu.addAction(lang.getstr("profile_associations"))
        if sys.platform == "win32":
            associations_action.triggered.connect(pl._set_profile_associations)
        else:
            # ProfileAssociationsDialog drives Windows-only WCS/registry APIs
            # (see DisplayCAL.ui.tools.profile_associations); the feature has
            # no cross-platform equivalent to fall back to.
            associations_action.setEnabled(False)
            associations_action.setToolTip(_NOT_AVAILABLE_TOOLTIP)

        if sys.platform == "win32":
            display_settings_action = menu.addAction(
                lang.getstr("mswin.open_display_settings")
            )
            display_settings_action.triggered.connect(pl.open_display_settings)

        menu.addSeparator()
        quit_action = menu.addAction(lang.getstr("menuitem.quit"))
        quit_action.triggered.connect(pl.exit)

    # -- menu action handlers -------------------------------------------

    def _on_preserve_toggled(self, checked: bool) -> None:
        """Toggle ``profile.load_on_login`` and re-apply if just enabled.

        Args:
            checked (bool): The new checked state.
        """
        pl = self.pl
        setcfg("profile.load_on_login", int(checked))
        pl.writecfg()
        if checked:
            pl.trigger_reapply()
        else:
            pl._refresh_visual_state()

    def _on_animation_toggled(self, checked: bool) -> None:
        """Persist the tray-icon-animation cfg toggle and rebuild its frames.

        Mirrors wx's ``TaskBarIcon.set_animation``.

        Args:
            checked (bool): The new checked state.
        """
        setcfg("profile_loader.tray_icon_animation_quality", 2 if checked else 0)
        self._build_active_icons()

    def _on_fix_profile_associations_toggled(self, checked: bool) -> None:
        """Confirm and apply a change to the "fix profile associations" setting.

        Mirrors wx's ``TaskBarIcon.CreatePopupMenu`` wiring the tray menu item
        straight to ``ProfileLoader._toggle_fix_profile_associations``, with
        no parent window (``QSystemTrayIcon`` isn't a ``QWidget``, so the
        confirmation dialog is parentless here, unlike the one opened from
        the profile-associations checkbox).

        Args:
            checked (bool): The new checked state requested by the user.
        """
        from DisplayCAL.ui.tools.profile_associations import _CheckedEvent

        self.pl._toggle_fix_profile_associations(_CheckedEvent(checked))

    def _on_bitdepth(self, bits: int) -> None:
        """Set the quantization bit depth, mirroring wx's ``set_bitdepth``.

        Args:
            bits (int): The bit depth to set.
        """
        pl = self.pl
        setcfg("profile_loader.quantize_bits", bits)
        with pl.lock:
            pl._quantize = 2**bits - 1.0
            pl.ramps = {}
            pl._manual_restore = True

    # -- click handling --------------------------------------------------

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (single/double click).

        Args:
            reason (QSystemTrayIcon.ActivationReason): How the icon was
                activated.
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.pl._is_other_running(False):
                return
            with self.pl.lock:
                self.pl._manual_restore = True
            self.pl.trigger_reapply()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_status(toggle=True)

    # -- visuals -----------------------------------------------------------

    def set_visual_state(self) -> None:
        """Refresh the tray icon and tooltip from the current daemon state."""
        pl = self.pl
        if not pl.monitoring:
            return
        if any(
            success is False
            for success in list(pl.setgammaramp_success.values())[
                : len(pl.monitors) or 1
            ]
        ):
            icon = self._error_icon
        elif pl._reset_gamma_ramps:
            icon = self._reset_icon
        else:
            icon = self._active_icons[self._icon_index]
        self.setIcon(icon)
        self.setToolTip(pl.get_title())

    def animate(self) -> None:
        """Step the busy-animation frame, mirroring wx's ``TaskBarIcon.animate``.

        Advances through ``self._active_icons`` one frame at a time,
        rescheduling itself on a :class:`QTimer` until it reaches the last
        frame, then resets back to frame 0. Called by
        :meth:`QtProfileLoader._animate_busy_icon` (from the hot-plug
        monitoring thread) each time it notices profiles should be applied
        and the system isn't idle.
        """
        if not self.pl.monitoring:
            return
        numframes = len(self._active_icons)
        if self._icon_index < numframes - 1:
            self._icon_index += 1
        else:
            self._icon_index = 0
        self.set_visual_state()
        if self._icon_index > 0:
            QTimer.singleShot(int(200 / numframes), self.animate)

    def show_status(
        self,
        text: str | None = None,
        sticky: bool = False,
        show_notification: bool = True,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        toggle: bool = False,
    ) -> None:
        """Show a status balloon, mirroring wx's ``TaskBarIcon.show_notification``.

        Args:
            text (str | None): The text to display; falls back to the last
                sticky text, then to :meth:`~QtProfileLoader.get_notification_text`.
            sticky (bool): Whether ``text`` should persist as the default.
            show_notification (bool): Whether to actually show the balloon.
            icon (QSystemTrayIcon.MessageIcon): The balloon's icon.
            toggle (bool): If a balloon is already showing, hide it instead of
                re-showing (best-effort -- Qt exposes no way to query or
                dismiss a shown message, unlike wx's custom balloon widget).
        """
        if (sticky or text) and show_notification:
            show_notification = bool(getcfg("profile_loader.show_notifications"))
        if sticky:
            self._balloon_text = text
            self._balloon_icon = icon
        elif text:
            self._balloon_text = None
            self._balloon_icon = QSystemTrayIcon.MessageIcon.Information
        else:
            text = self._balloon_text
            icon = self._balloon_icon or icon
        if not text:
            text = self.pl.get_notification_text()
        if not show_notification:
            return
        if toggle and self._notification_shown:
            self._notification_shown = False
            return
        self.showMessage(self.pl.get_title(), text, icon)
        self._notification_shown = True


class QtProfileLoader(profile_loader.ProfileLoader):
    """Qt subclass of :class:`~DisplayCAL.profile_loader.ProfileLoader`.

    Overrides only the wx-specific UI touchpoints; every other method (the
    actual calibration-loading logic) is inherited unchanged. See the module
    docstring for the list of deferred follow-ups.
    """

    tray: ApplyProfilesTrayIcon | None

    def _bootstrap_app(self) -> None:
        """No-op: the Qt ``Application`` is already constructed by :func:`main`."""
        self._app = None

    def _setup_ui(self) -> None:
        """Set up the cross-platform Qt tray icon and IPC host."""
        self._notify_bridge = _NotifyBridge()
        self._notify_bridge.requested.connect(
            self._notify_on_gui_thread, Qt.QueuedConnection
        )
        self._call_bridge = _CallBridge()
        self._call_bridge.requested.connect(self._dispatch_call, Qt.QueuedConnection)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = ApplyProfilesTrayIcon(self)
            self.tray.show()
        else:
            print("Warning - no system tray available, running headless")
            self.tray = None
        self._tray_active = self.tray is not None

        self.host = _ScriptingHost(self)
        self.host.listen()

        if sys.platform == "win32":
            # Matches wx's setup_taskbar_icon(): _look_for_known_processes()
            # (reached from the monitoring thread started below, and from the
            # tray menu's own _is_other_running() checks) excludes our own
            # process by pid.
            self._pid = os.getpid()
            # Also matches wx's setup_taskbar_icon(): the inherited
            # calibration-loading logic sets/reads the gamma ramps via gdi32.
            if exception := self._init_gdi32():
                self.notify([], [str(exception)], show_notification=True)
            self._check_display_conf_thread = threading.Thread(
                target=self._check_display_conf_wrapper,
                name="DisplayConfigurationMonitoring",
            )
            self._check_display_conf_thread.start()
        elif (
            sys.platform == "darwin"
            and config.getcfg("profile.load_on_login")
            and "--force" not in sys.argv[1:]
            and not self._skip
            and config.getcfg("profile_loader.macos_reapply_watch")
        ):
            threading.Thread(
                target=self._macos_watch,
                name="MacOSVideoLUTWatch",
                daemon=True,
            ).start()

    def _dispatch_call(self, func: Callable, args: tuple, delay_ms: int) -> None:
        """GUI-thread slot backing :class:`_CallBridge`.

        Args:
            func (Callable): The callable to run.
            args (tuple): Positional arguments to pass to ``func``.
            delay_ms (int): Delay in milliseconds before running ``func``;
                0 runs it immediately.
        """
        if delay_ms:
            QTimer.singleShot(delay_ms, lambda: func(*args))
        else:
            func(*args)

    def _post_to_gui_thread(self, func: Callable, *args: object) -> None:
        """Qt override: marshal ``func(*args)`` onto the GUI thread.

        See :meth:`DisplayCAL.profile_loader.ProfileLoader._post_to_gui_thread`.
        """
        self._call_bridge.requested.emit(func, args, 0)

    def _post_to_gui_thread_delayed(
        self, delay_ms: int, func: Callable, *args: object
    ) -> None:
        """Qt override: marshal a delayed ``func(*args)`` call onto the GUI thread.

        See
        :meth:`DisplayCAL.profile_loader.ProfileLoader._post_to_gui_thread_delayed`.
        """
        self._call_bridge.requested.emit(func, args, delay_ms)

    def _animate_busy_icon(self) -> None:
        """Qt override: step the tray icon's busy-animation frame.

        See :meth:`ApplyProfilesTrayIcon.animate` and
        :meth:`DisplayCAL.profile_loader.ProfileLoader._animate_busy_icon`.
        """
        if self.tray is not None:
            self.tray.animate()

    def _enumerate_own_top_level_windows(self) -> list:
        r"""Qt override: list this process's own top-level, non-dialog widgets.

        Mirrors the wx default's intent (notice when something external has
        closed one of our windows, as a hint to comply and exit) using
        ``QApplication.topLevelWidgets()`` instead of wx's window
        enumeration; ``QDialog``\ s (Exceptions, Profile Associations, ...)
        are excluded just like wx excludes ``wx.Dialog``\ s, so opening/
        closing one of those doesn't look like an external close request.

        Returns:
            list: The process's own top-level, non-dialog widgets.
        """
        app = QApplication.instance()
        if app is None:
            return []
        return [
            widget
            for widget in app.topLevelWidgets()
            if not isinstance(widget, QDialog)
        ]

    def _request_forced_shutdown(self) -> None:
        """Qt override: quit immediately, without the confirmation prompt.

        See
        :meth:`DisplayCAL.profile_loader.ProfileLoader._request_forced_shutdown`.
        """
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _teardown_ui(self) -> None:
        """Hide the tray icon and stop the IPC host."""
        if self.tray is not None:
            self.tray.hide()
        if getattr(self, "host", None):
            self.host.stop_listening()

    def _refresh_visual_state(self) -> None:
        """Refresh the tray icon's visual state, if a tray exists."""
        if self.tray is not None:
            self.tray.set_visual_state()

    def trigger_reapply(self) -> None:
        """Re-apply profiles/calibration in the background.

        The Qt build has no continuous hot-plug polling thread (see module
        docstring), so callers that would have merely flipped a flag for that
        poller to notice (the ``apply-profiles``/``reset-vcgt`` IPC commands,
        a tray double-click) call this instead to trigger the reload directly.
        """
        threading.Thread(
            target=self.apply_profiles_and_warn_on_error,
            args=(True, None),
            name="ApplyProfilesReapply",
            daemon=True,
        ).start()

    def notify(
        self,
        results: list,
        errors: list,
        sticky: bool = False,
        show_notification: bool = False,
    ) -> None:
        """Notify the user about the results of profile application.

        Safe to call from any thread: marshals onto the GUI thread via a
        queued signal before touching the tray icon.

        Args:
            results (list): List of successful profile applications.
            errors (list): List of errors encountered during profile application.
            sticky (bool): Whether the notification should be sticky.
            show_notification (bool): Whether to show the notification.
        """
        self._notify_bridge.requested.emit(results, errors, sticky, show_notification)

    def _notify_on_gui_thread(
        self, results: list, errors: list, sticky: bool, show_notification: bool
    ) -> None:
        """GUI-thread half of :meth:`notify`.

        Args:
            results (list): List of successful profile applications.
            errors (list): List of errors encountered during profile application.
            sticky (bool): Whether the notification should be sticky.
            show_notification (bool): Whether to show the notification.
        """
        if self.tray is None:
            return
        self.tray.set_visual_state()
        combined = [*results, *errors]
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if errors
            else QSystemTrayIcon.MessageIcon.Information
        )
        self.tray.show_status("\n".join(combined), sticky, show_notification, icon)

    def apply_profiles_and_warn_on_error(
        self, event: object = None, index: int | None = None
    ) -> list | None:
        """Apply profiles and show a warning dialog if there are errors.

        Args:
            event: Truthy if triggered by a direct user/IPC action (enables
                the post-apply notification, matching the inherited
                ``apply_profiles()``'s convention).
            index (int | None): The index of the monitor to apply profiles
                to. If None, applies to all monitors.

        Returns:
            list | None: The errors returned by ``apply_profiles()``.
        """
        errors = self.apply_profiles(event, index)
        if (
            errors
            and (
                config.getcfg("profile_loader.error.show_msg")
                or "--error-dialog" in sys.argv[1:]
            )
            and "--silent" not in sys.argv[1:]
        ):
            QMessageBox.critical(None, self.get_title(), "\n".join(errors))
        return errors

    def _set_profile_associations(self, event: object = None) -> None:
        """Open the Qt profile-associations dialog.

        Only ever wired up on Windows (see module docstring); the dialog
        itself would just show no displays anywhere else since
        ``self.monitors`` stays empty off Windows.

        Args:
            event: Unused; kept for interface parity with the wx override.
        """
        print("Set profile associations")
        from DisplayCAL.ui.tools.profile_associations import ProfileAssociationsDialog

        dlg = ProfileAssociationsDialog(self)
        dlg.exec()

    def open_display_settings(self, event: object = None) -> None:
        """Open the Windows display settings.

        Mirrors wx's ``TaskBarIcon.open_display_settings``. Only ever wired
        up on Windows (see module docstring).

        Args:
            event: Unused; kept for interface parity with the wx override.
        """
        print("Menu command: Open display settings")
        try:
            subprocess.call(
                [  # noqa: S607
                    "control",
                    "/name",
                    "Microsoft.Display",
                    "/page",
                    "Settings",
                ],
                close_fds=True,
            )
        except Exception as exception:
            QApplication.beep()
            print(exception)

    def set_exceptions(self, event: object = None) -> None:
        """Open the Qt exceptions dialog and persist any changes.

        Mirrors wx's ``TaskBarIcon.set_exceptions``.

        Args:
            event: Unused; kept for interface parity with the wx override.
        """
        print("Menu command: Set exceptions")
        from DisplayCAL.ui.tools.profile_loader_exceptions import (
            ProfileLoaderExceptionsDialog,
        )

        dlg = ProfileLoaderExceptionsDialog(self._exceptions, self._known_apps)
        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted:
            exceptions = []
            for key in dlg._exceptions:
                enabled, reset, path = dlg._exceptions[key]
                exceptions.append(f"{enabled:d}:{reset:d}:{path}")
                print(
                    f"Enabled={bool(enabled)}",
                    "Action={}".format((reset and "Reset") or "Disable"),
                    path,
                )
            if not exceptions:
                print("Clearing exceptions")
            setcfg("profile_loader.exceptions", ";".join(exceptions))
            self._exceptions = dlg._exceptions
            self._exception_names = {os.path.basename(key) for key in dlg._exceptions}
            self.writecfg()
        else:
            print("Cancelled setting exceptions")

    def _toggle_fix_profile_associations(
        self, event: object, parent: QWidget | None = None
    ) -> bool:
        """Toggle the fix profile associations setting (Qt override).

        Overrides the inherited wx
        :meth:`~DisplayCAL.profile_loader.ProfileLoader._toggle_fix_profile_associations`
        to show
        :class:`~DisplayCAL.ui.tools.fix_profile_associations.FixProfileAssociationsDialog`
        instead of the wx dialog; the confirm/apply logic below (setcfg,
        ``_set_display_profiles``/``_reset_display_profile_associations``,
        ``writecfg``) is otherwise identical to the inherited wx version.

        Args:
            event: An object with an ``IsChecked()`` method -- see
                :class:`DisplayCAL.ui.tools.profile_associations._CheckedEvent`
                for the duck-typed adapter callers use when there's no real
                Qt event.
            parent (QWidget | None): Optional parent widget for the
                confirmation dialog.

        Returns:
            bool: The new "fix profile associations" state.
        """
        print("Toggle fix profile associations", event.IsChecked())
        if event.IsChecked():
            from DisplayCAL.ui.tools.fix_profile_associations import (
                FixProfileAssociationsDialog,
            )

            dlg = FixProfileAssociationsDialog(self, parent)
            try:
                result = dlg.exec()
            finally:
                dlg.close()
            if result != QDialog.DialogCode.Accepted:
                print("Cancelled toggling fix profile associations")
                return False
        if self.lock.locked():
            print("Waiting to acquire lock...")
        with self.lock:
            print("Acquired lock")
            setcfg("profile_loader.fix_profile_associations", int(event.IsChecked()))
            if event.IsChecked():
                self._set_display_profiles()
            else:
                self._reset_display_profile_associations()
            self._manual_restore = True
            self.writecfg()
            print("Releasing lock")
        return event.IsChecked()

    def exit(self, event: object = None) -> None:
        """Quit the daemon, confirming first unless the OS manages calibration.

        Args:
            event: Truthy (including ``False``, as Qt's ``QAction.triggered``
                passes it) when this is a real interactive trigger, e.g. the
                tray menu's Quit action; ``None`` for programmatic/automated
                callers (the hot-plug monitoring thread's ``--oneshot`` and
                forced-shutdown paths, a fatal error) which have no user
                present to answer a confirmation prompt and so always skip
                it, mirroring the wx override's ``if event and ...`` gate.
        """
        print(f"Executing QtProfileLoader.exit({event})")
        if event is not None and (
            not calibration_management_isenabled()
            or getcfg("profile_loader.fix_profile_associations")
        ):
            result = QMessageBox.question(
                None,
                self.get_title(),
                lang.getstr("profile_loader.exit_warning"),
            )
            if result != QMessageBox.StandardButton.Yes:
                print(f"Cancelled QtProfileLoader.exit({event})")
                return
        app = QApplication.instance()
        if app is not None:
            app.quit()


def main() -> int:
    """Entry point for the Qt apply-profiles daemon.

    Returns:
        int: The Qt application exit code.
    """
    unknown_option = profile_loader.filter_unknown_args()
    if "--help" in sys.argv[1:] or unknown_option:
        if unknown_option:
            print(f"{sys.argv[0]}: unrecognized option `{unknown_option}'")
        profile_loader.display_help_message()
        return 0
    if "-V" in sys.argv[1:] or "--version" in sys.argv[1:]:
        from DisplayCAL.meta import VERSION_STRING

        print(f"{sys.argv[0]} {VERSION_STRING}")
        return 0

    config.initcfg("apply-profiles")

    if (
        "--force" not in sys.argv[1:]
        and not config.getcfg("profile.load_on_login")
        and sys.platform != "win32"
    ):
        # Early exit incase profile loading has been disabled and isn't forced.
        # (Kept for parity with wx; less relevant under Qt now that a
        # cross-platform tray exists, but a disabled daemon still shouldn't
        # launch a tray icon nobody asked for.)
        return 0

    if "--error-dialog" in sys.argv[1:]:
        config.setcfg("profile_loader.error.show_msg", 1)
        config.writecfg(
            module="apply-profiles",
            options=("argyll.dir", "profile.load_on_login", "profile_loader"),
        )

    lang.init()
    # profile_loader.py defers binding its own module-level ``lang`` name until
    # its wx ``main()`` runs (avoids a circular import at module load time);
    # since we bypass that ``main()``, bind it here instead -- every inherited
    # method (``get_title``, ``apply_profiles``, ...) references bare ``lang``.
    profile_loader.lang = lang

    app = Application(sys.argv)
    pl = QtProfileLoader()
    Application.register_exitfunc(pl.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
