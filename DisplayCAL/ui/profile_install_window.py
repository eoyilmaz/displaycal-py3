"""Profile install / load-on-login window — Qt port.

Qt equivalent of the profile-install portion of
:meth:`DisplayCAL.display_cal.MainFrame.profile_finish` /
``install_profile_handler`` / ``select_install_profile_handler``: pick an
``.icc``/``.icm`` display profile, choose an install scope and whether it
should reload on login, and install it via
:meth:`DisplayCAL.worker.Worker.install_profile` on a background thread
(the same one-shot-Argyll-call-behind-an-indeterminate-progress-dialog pattern
as :mod:`DisplayCAL.ui.tools.lut3d` /
:mod:`DisplayCAL.ui.colorimeter_correction_window`).
Reuses the toolkit-neutral :mod:`DisplayCAL.profile_install` validation /
scope / result-summary helpers shared with the still-shipping wx path.

Installing with an elevated scope (local system / network) authenticates via
:meth:`DisplayCAL.worker.Worker.authenticate`, whose sudo password prompt is
serviced by a :class:`~DisplayCAL.ui.worker_runner.PasswordPromptAdapter`
assigned to ``self.worker.password_prompt`` (in place of the wx
``ConfirmDialog`` that seam falls back to). Windows elevation (UAC) and
macOS/Linux "already root" don't go through this prompt at all
(``Worker.authenticate`` returns early in both cases), matching wx.

Deliberately dropped / deferred versus the wx dialog:

* The calibration-preview and "show LUT" checkboxes depend on a live
  calibration session on the running main window (the wx dialog reads
  ``self.cal`` / ``self.preview``); they return with the Qt main window. The
  "show profile info" checkbox is kept, but opens the already-ported
  :class:`DisplayCAL.ui.tools.profile_info.ProfileInfoWindow` directly rather
  than toggling an embedded frame.
* The 3D LUT install branch of ``profile_finish`` (madVR/Prisma/pattern
  generator) is a separate feature already covered by the ported
  :mod:`DisplayCAL.ui.tools.lut3d`.
* "Profile share" is dead code upstream (icc.opensuse.org has been down since
  #194); not reproduced here either.
* The Windows profile-loader IPC resync (talking to a separately running
  "apply-profiles" tray process over the scripting socket) is not reproduced;
  ``profile.load_on_login`` is still written directly, which is what
  :meth:`Worker.install_profile` itself reads.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

from qtpy.QtCore import QObject, QThread, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL import profile_install as pi
from DisplayCAL.argyll import check_set_argyll_bin
from DisplayCAL.config import get_verified_path, getcfg, setcfg, writecfg
from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.tools.profile_info import ProfileInfoWindow
from DisplayCAL.ui.worker_runner import PasswordPromptAdapter
from DisplayCAL.util_os import is_superuser, which
from DisplayCAL.worker import Worker

if sys.platform == "win32":
    from DisplayCAL import util_win


class _InstallThread(QThread):
    """Run :meth:`Worker.install_profile` off the GUI thread.

    Args:
        worker (Worker): The worker to install through.
        profile_path (str): Path to the profile to install.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the ``(argyll, colord, oyranos, loader)`` result tuple, or
    #: an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, worker: Worker, profile_path: str, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._profile_path = profile_path

    def run(self) -> None:
        try:
            result = self._worker.install_profile(
                self._profile_path, capture_output=True, skip_scripts=True
            )
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class InstallProfileWindow(BaseWindow):
    """Window to pick, validate and install a display profile."""

    def __init__(self) -> None:
        super().__init__(
            name="install-profile",
            title=lang.getstr("profile.install"),
            icon_name=f"{APPNAME}-profile-info".lower(),
        )
        self.worker = Worker()
        self.worker.set_argyll_version("dispwin")
        self.worker.enumerate_displays_and_ports(silent=True)
        self.worker.password_prompt = PasswordPromptAdapter(parent=self)
        self._thread: _InstallThread | None = None
        self._progress: QProgressDialog | None = None
        self._profile: ICCProfile | None = None
        self._profile_path = ""
        self._profile_info_window = None
        self._scope_buttons: dict[str, QRadioButton] = {}

        self._build_ui()

        droptarget = FileDropTarget({".icc": self._load_path, ".icm": self._load_path})
        droptarget.install_on(self)

        self._update_load_on_login_controls()
        self._update_install_enabled()

    # -- construction --------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        path_row = QHBoxLayout()
        self.path_label = QLabel(lang.getstr("install_display_profile"))
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self.show_profile_info_btn = QPushButton(lang.getstr("profile.info.show"))
        self.show_profile_info_btn.clicked.connect(self._show_profile_info)
        self.show_profile_info_btn.setEnabled(False)
        layout.addWidget(self.show_profile_info_btn)

        self.load_on_login_check = QCheckBox()
        self.load_on_login_check.toggled.connect(self._load_on_login_changed)
        layout.addWidget(self.load_on_login_check)

        self.load_by_os_check = None
        if sys.platform == "win32" and sys.getwindowsversion() >= (6, 1):
            self.load_by_os_check = QCheckBox(
                lang.getstr("profile.load_on_login.handled_by_os")
            )
            self.load_by_os_check.toggled.connect(self._load_by_os_changed)
            layout.addWidget(self.load_by_os_check)

        scope_options = pi.resolve_install_scope_options(
            argyll_version=self.worker.argyll_version,
            is_superuser_or_sudo=self._is_superuser_or_sudo(),
            windows_version=self._windows_version(),
            network_profiles_dir_exists=sys.platform == "darwin"
            and os.path.isdir("/Network/Library/ColorSync/Profiles"),
        )
        if scope_options:
            scope_box = QGroupBox()
            scope_layout = QVBoxLayout(scope_box)
            group = QButtonGroup(self)
            labels = {
                "u": "profile.install_user",
                "l": "profile.install_local_system",
                "n": "profile.install_network",
            }
            for code in scope_options:
                button = QRadioButton(lang.getstr(labels[code]))
                button.setChecked(getcfg("profile.install_scope") == code)
                button.toggled.connect(self._make_scope_handler(code))
                group.addButton(button)
                scope_layout.addWidget(button)
                self._scope_buttons[code] = button
            if not any(button.isChecked() for button in self._scope_buttons.values()):
                self._scope_buttons["u"].setChecked(True)
            layout.addWidget(scope_box)
        else:
            setcfg("profile.install_scope", "u")

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.install_btn = QPushButton(lang.getstr("profile.install"))
        self.install_btn.setDefault(True)
        self.install_btn.clicked.connect(self._install)
        button_row.addWidget(self.install_btn)
        close_btn = QPushButton(lang.getstr("close"))
        close_btn.clicked.connect(self.close)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        self.setCentralWidget(central)
        self.resize(420, 320)

    # -- platform helpers ------------------------------------------------

    @staticmethod
    def _is_superuser_or_sudo() -> bool:
        if sys.platform == "win32":
            return False
        return is_superuser() or bool(which("sudo"))

    @staticmethod
    def _windows_version() -> tuple[int, ...] | None:
        if sys.platform != "win32":
            return None
        return tuple(sys.getwindowsversion())

    # -- profile selection -------------------------------------------------

    def _browse(self) -> None:
        default_dir, default_file = get_verified_path("last_icc_path")
        path, _ = file_dialog.get_open_file_name(
            self,
            lang.getstr("install_display_profile"),
            f"{default_dir}/{default_file}" if default_file else default_dir,
            f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
        )
        if path:
            self._load_path(path)

    def load_profile(self, path: str) -> None:
        """Pre-select ``path`` for installation, as if the user had browsed to it."""
        self._load_path(path)

    def _load_path(self, path: str) -> None:
        try:
            profile = pi.load_installable_profile(path)
        except (OSError, ICCProfileInvalidError):
            message_box.critical(
                self, self.windowTitle(), f"{lang.getstr('profile.invalid')}\n{path}"
            )
            return
        except pi.ProfileUnsupportedError as exception:
            message_box.critical(self, self.windowTitle(), f"{exception}\n{path}")
            return
        self._profile = profile
        self._profile_path = path
        setcfg("last_icc_path", path)
        setcfg("last_cal_or_icc_path", path)
        self.path_label.setText(path)
        self._update_install_enabled()

    def _show_profile_info(self) -> None:
        if not self._profile_path:
            return
        if self._profile_info_window is None:
            self._profile_info_window = ProfileInfoWindow()
        self._profile_info_window.load_profile(self._profile_path)
        self._profile_info_window.show()
        self._profile_info_window.raise_()
        self._profile_info_window.activateWindow()

    def _update_install_enabled(self) -> None:
        has_profile = bool(self._profile_path)
        self.install_btn.setEnabled(has_profile)
        self.show_profile_info_btn.setEnabled(has_profile)

    # -- load on login -------------------------------------------------

    def _update_load_on_login_controls(self) -> None:
        os_cal = (
            sys.platform == "win32"
            and sys.getwindowsversion() >= (6, 1)
            and util_win.calibration_management_isenabled()
        )
        self.load_on_login_check.setText(pi.get_profile_load_on_login_label(os_cal))
        self.load_on_login_check.setChecked(
            bool(getcfg("profile.load_on_login")) or os_cal
        )
        if self.load_by_os_check is not None:
            self.load_by_os_check.setChecked(bool(os_cal))
            self.load_on_login_check.setEnabled(
                is_superuser() or not util_win.calibration_management_isenabled()
            )
            self.load_by_os_check.setEnabled(
                is_superuser() and self.load_on_login_check.isChecked()
            )

    def _load_on_login_changed(self, checked: bool) -> None:
        setcfg("profile.load_on_login", int(checked))
        if self.load_by_os_check is not None:
            self.load_by_os_check.setEnabled(is_superuser() and checked)
            if not checked and self.load_by_os_check.isChecked() and is_superuser():
                self.load_by_os_check.setChecked(False)

    def _load_by_os_changed(self, checked: bool) -> None:
        if not is_superuser():
            return
        try:
            util_win.enable_calibration_management(checked)
        except Exception as exception:  # noqa: BLE001  (best-effort, matches wx)
            print(f"util_win.enable_calibration_management({checked}): {exception}")
            return
        self.load_on_login_check.setText(pi.get_profile_load_on_login_label(checked))

    # -- install scope -------------------------------------------------

    def _make_scope_handler(self, code: str) -> Callable[[bool], None]:
        def handler(checked: bool) -> None:
            if checked:
                setcfg("profile.install_scope", code)

        return handler

    # -- install ---------------------------------------------------------

    def _install(self) -> None:
        if not self._profile_path or not check_set_argyll_bin():
            return
        writecfg()
        self.install_btn.setEnabled(False)
        self._progress = QProgressDialog(lang.getstr("profile.install"), "", 0, 0, self)
        self._progress.setWindowTitle(self.windowTitle())
        self._progress.setCancelButton(None)
        self._progress.show()
        self._thread = _InstallThread(self.worker, self._profile_path, parent=self)
        self._thread.done.connect(self._on_install_done)
        self._thread.start()

    def _on_install_done(self, result: object) -> None:
        self._thread = None
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        self.install_btn.setEnabled(True)
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
        else:
            show_install_summary(self, self.windowTitle(), result)
        # wx's install dialog is gone once the install ran, close this window
        # too. Closed after the result was shown, as closing the last window
        # first would quit the standalone tool before the result is seen.
        self.close()


def show_install_summary(parent: QWidget | None, title: str, result: tuple) -> None:
    """Show the outcome of a completed :meth:`Worker.install_profile` call.

    Ports the per-backend (ArgyllCMS/colord/Oyranos/profile-loader) success
    breakdown in ``MainFrame.profile_finish_consumer``. Shared with
    :mod:`DisplayCAL.ui.main_window`'s post-calibration/profiling completion
    dialog, which installs directly rather than going through
    :class:`InstallProfileWindow`.

    Args:
        parent (QWidget | None): Parent window for the message box.
        title (str): Message box title.
        result (tuple): The ``(argyll, colord, oyranos, loader)`` result tuple
            from :meth:`Worker.install_profile`.
    """
    summary = pi.summarize_install_result(*result)
    text = lang.getstr(f"profile.install.{summary.message_key}")
    if summary.details:
        text += "\n\n" + "\n".join(
            f"{name}: {detail_text}" for name, _ok, detail_text in summary.details
        )
    box = {
        "success": QMessageBox.information,
        "warning": QMessageBox.warning,
        "error": QMessageBox.critical,
    }[summary.message_key]
    box(parent, title, text)


def main() -> int:
    """Run the profile install window standalone.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg()
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = InstallProfileWindow()
    app.top_window = window
    window.show()
    window.listen()
    app.process_argv()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
