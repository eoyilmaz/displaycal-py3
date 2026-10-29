"""Spyder2 colorimeter firmware-enable wizard — Qt port.

Qt port of ``display_cal.MainFrame.enable_spyder2_handler`` / ``enable_spyder2``
/ ``enable_spyder2_producer`` / ``enable_spyder2_consumer`` (``display_cal.py``):
runs Argyll's ``spyd2en`` utility to patch a Spyder 2 colorimeter's PLD
firmware file into place, either found automatically (OEM software already
installed locally, or downloaded from the web) or from a user-selected
installer file/archive.

Elevated (system-wide) installs authenticate via
:meth:`DisplayCAL.worker.Worker.authenticate`, serviced by the same
:class:`~DisplayCAL.ui.worker_runner.PasswordPromptAdapter` /
``worker.password_prompt`` seam as :mod:`DisplayCAL.ui.profile_install_window`
and :mod:`DisplayCAL.ui.colorimeter_correction_io`. Unlike wx -- which
authenticates synchronously on the GUI thread *before* dispatching to a
worker thread, because wx's own ``exec_cmd`` refuses to show its password
dialog off the main thread -- this port just lets ``Worker.exec_cmd``'s
elevated branch authenticate directly on the background :class:`_EnableThread`,
since the Qt adapter is itself thread-safe (matching the simpler pattern
already used by :class:`DisplayCAL.ui.profile_install_window.InstallProfileWindow`).

The "run the correction-import check again after enabling" recursion wx does
via ``enable_spyder2_handler``'s ``check_instrument_setup`` bool lives in the
caller (``MainWindow._run_instrument_setup_and_donation_check``), driven by
:data:`DisplayCAL.instrument_setup.InstrumentSetupNeeds.recheck_after_spyder2`,
not here.
"""

from __future__ import annotations

import os
import sys
from time import sleep
from typing import Callable

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL.argyll import check_set_argyll_bin, get_argyll_util
from DisplayCAL.config import getcfg
from DisplayCAL.meta import DOMAIN
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.worker_runner import PasswordPromptAdapter
from DisplayCAL.util_os import getenvu, safe_glob
from DisplayCAL.worker import Worker


def _enable_spyder2(worker: Worker, path: str | None, asroot: bool) -> bool | Exception:
    """Run ``spyd2en`` and verify the firmware landed. Port of ``MainFrame.enable_spyder2``."""
    cmd = get_argyll_util("spyd2en")
    args = ["-v"]
    if asroot and worker.argyll_version >= [1, 2, 0]:
        args.append("-Sl")
    if path:
        args.append(path)
    result = worker.exec_cmd(
        cmd,
        args,
        capture_output=True,
        skip_scripts=True,
        silent=False,
        asroot=asroot,
        title=lang.getstr("enable_spyder2"),
    )
    if asroot and sys.platform == "win32":
        # Wait for async process
        sleep(1)
    if result and not isinstance(result, Exception):
        result = worker.spyder2_firmware_exists(scope="l" if asroot else "u")
    return result


def _enable_spyder2_producer(
    worker: Worker, path: str | None, asroot: bool
) -> bool | Exception | None:
    """Locate the OEM installer (given, local, or downloaded) and enable Spyder2.

    Port of ``MainFrame.enable_spyder2_producer``, runs on the background thread.
    """
    if path:
        return _enable_spyder2(worker, path, asroot)

    if sys.platform in ("darwin", "win32"):
        # Look for Spyder.lib/CVSpyder.dll ourself because spyd2en
        # will only try some fixed paths
        if sys.platform == "darwin":
            wildcard = os.path.join(
                os.path.sep,
                "Applications",
                "Spyder2*",
                "Spyder2*.app",
                "Contents",
                "MacOSClassic",
                "Spyder.lib",
            )
        else:
            wildcard = os.path.join(
                getenvu("PROGRAMFILES", ""),
                "ColorVision",
                "Spyder2*",
                "CVSpyder.dll",
            )
        found = safe_glob(wildcard)
        path = found[0] if found else None
    if getcfg("dry_run"):
        return None
    if path:
        result = _enable_spyder2(worker, path, asroot)
        if result and not isinstance(result, Exception):
            return result
    # Download from web
    path = worker.download(f"https://{DOMAIN}/spyd2")
    if isinstance(path, Exception):
        return path
    if not path:
        # Cancelled
        return None
    return _enable_spyder2(worker, path, asroot)


class _EnableThread(QThread):
    """Run a zero-argument callable off the GUI thread."""

    #: Emitted with the callable's return value, or an ``Exception`` instance.
    done = Signal(object)

    def __init__(
        self, func: Callable[[], object], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._func = func

    def run(self) -> None:
        try:
            result = self._func()
        except Exception as exception:  # noqa: BLE001  (reported on GUI thread)
            result = exception
        self.done.emit(result)


class _EnableSpyder2Dialog(QDialog):
    """Auto-detect vs. manual-installer-file choice, plus install-scope radios.

    Port of the ``ConfirmDialog`` built inline in
    ``MainFrame.enable_spyder2_handler``.
    """

    def __init__(self, worker: Worker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang.getstr("enable_spyder2"))
        self.mode: str | None = None  # "auto" | "files" | None (cancelled)

        layout = QVBoxLayout(self)
        msg = lang.getstr("oem.import.auto")
        if sys.platform == "win32":
            msg = " ".join([lang.getstr("oem.import.auto_windows"), msg])
        label = QLabel(msg)
        label.setWordWrap(True)
        layout.addWidget(label)

        needroot = worker.argyll_version < [1, 2, 0]
        self._install_user = QRadioButton(lang.getstr("install_user"))
        self._install_user.setEnabled(not needroot)
        self._install_user.setChecked(not needroot)
        self._install_systemwide = QRadioButton(lang.getstr("install_local_system"))
        self._install_systemwide.setChecked(needroot)
        layout.addSpacing(8)
        layout.addWidget(self._install_user)
        layout.addWidget(self._install_systemwide)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        files_btn = QPushButton(lang.getstr("file.select"))
        files_btn.clicked.connect(self._choose_files)
        button_row.addWidget(files_btn)
        auto_btn = QPushButton(lang.getstr("auto"))
        auto_btn.setDefault(True)
        auto_btn.clicked.connect(self._choose_auto)
        button_row.addWidget(auto_btn)
        cancel_btn = QPushButton(lang.getstr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

    def _choose_auto(self) -> None:
        self.mode = "auto"
        self.accept()

    def _choose_files(self) -> None:
        self.mode = "files"
        self.accept()

    @property
    def asroot(self) -> bool:
        return self._install_systemwide.isChecked()


class Spyder2EnableController(QObject):
    """Enable a Spyder 2 colorimeter by installing/patching its PLD firmware."""

    #: Emitted when the flow ends. ``attempted`` is True if the enable was
    #: actually run (success or failure), False if the user cancelled before
    #: that point (dialog Cancel, or the file picker was dismissed) -- mirrors
    #: wx's distinction between a cancelled ``ConfirmDialog`` (no further
    #: action) and a completed attempt (which chains back into
    #: ``check_instrument_setup``).
    finished = Signal(bool)

    def __init__(self, worker: Worker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._parent = parent
        if worker.password_prompt is None:
            worker.password_prompt = PasswordPromptAdapter(parent=parent)
        self._thread: _EnableThread | None = None
        self._progress: QProgressDialog | None = None
        self._path: str | None = None
        self._asroot = False

    def run(self) -> None:
        """Show the choice dialog, then run the enable flow."""
        if not check_set_argyll_bin():
            self.finished.emit(False)
            return
        dialog = _EnableSpyder2Dialog(self._worker, self._parent)
        if dialog.exec_() != QDialog.Accepted or dialog.mode is None:
            self.finished.emit(False)
            return
        self._asroot = dialog.asroot

        path = None
        if dialog.mode == "files":
            path, _filter = file_dialog.get_open_file_name(
                self._parent,
                lang.getstr("file.select"),
                "",
                f"{lang.getstr('filetype.any')} (*)",
            )
            if not path:
                self.finished.emit(False)
                return

        self._path = path
        self._progress = QProgressDialog(
            lang.getstr("enable_spyder2"), "", 0, 0, self._parent
        )
        self._progress.setWindowTitle(lang.getstr("enable_spyder2"))
        self._progress.setCancelButton(None)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.show()
        self._thread = _EnableThread(self._do_enable)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _do_enable(self) -> bool | Exception | None:
        return _enable_spyder2_producer(self._worker, self._path, self._asroot)

    def _on_done(self, result: bool | Exception | None) -> None:
        self._thread = None
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        title = lang.getstr("enable_spyder2")
        if isinstance(result, Exception):
            message_box.critical(self._parent, title, str(result))
        elif result:
            message_box.information(
                self._parent, title, lang.getstr("enable_spyder2_success")
            )
        elif result is False:
            error = "".join(self._worker.errors) or lang.getstr(
                "enable_spyder2_failure"
            )
            message_box.critical(self._parent, title, error)
        # result is None: cancelled mid-flow (e.g. declined the web download);
        # matches wx, which shows no dialog for that case either.
        self.finished.emit(True)
