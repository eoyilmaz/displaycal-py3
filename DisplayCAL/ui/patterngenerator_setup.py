"""Pattern generator connection setup (madVR / Prisma / live) — Qt port.

Qt port of the madVR and Prisma branches of
``MainFrame.setup_patterngenerator`` (``display_cal.py:10738-11065``): connects
to the pattern-generator destination a 3D LUT install-to-device offer needs
before calling :meth:`DisplayCAL.worker.Worker.install_3dlut`, closing the
last item on the "MainFrame parity-hardening" remaining-gaps list
(:meth:`DisplayCAL.ui.main_window.MainWindow._install_3dlut`'s
``install_via_api`` branch, previously a "not available in this Qt build yet"
notice).

:func:`connect_patterngenerator` covers the two branches
:meth:`~DisplayCAL.ui.main_window.MainWindow._install_3dlut` reaches (madVR,
Prisma). :func:`connect_live_patterngenerator` separately ports the Resolve /
"Web @ localhost" / ``Chromecast *`` branch (``display_cal.py:11042-11089``)
for the visual whitepoint editor's live patch-streaming flow
(:mod:`DisplayCAL.ui.tools.visual_whitepoint_editor`) -- unlike the
madVR/Prisma flow this waits for an *incoming* connection from the
destination rather than dialing out, so it drives ``patterngenerator.wait()``
on a background thread instead of ``connect()``.

Prisma discovery/connectivity reuses
:class:`DisplayCAL.patterngenerators.PrismaPatternGeneratorClient` directly
(plain ``socket``/``threading``, no wx or Qt import) — despite being
described as "mDNS discovery" in earlier porting notes, it is actually a raw
UDP broadcast/response protocol on ports 7737/7747, not real mDNS/zeroconf.

Deliberate deviation from wx: wx's madVR branch only shows a wait dialog (and
only checks/reports the connection outcome) if ``madtpg_connect()`` is still
running after a 200 ms grace period — a fast failure inside that window is
silently swallowed by the caller (``setup_patterngenerator`` falls through to
``return retval``, which stays ``True``), even though the error is still
shown asynchronously via a stray ``wx.CallAfter(show_result_dialog, ...)``.
This port always evaluates the real outcome, fast or slow, and returns
``False`` (with the error shown) on failure either way — the wx behaviour
reads as an unintentional race, not a feature worth preserving.
"""

from __future__ import annotations

import os
import socket
import sys
from time import localtime, strftime
from typing import Callable

from qtpy.QtCore import QObject, Qt, QThread, QTimer, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.debughelpers import Error, Info
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import message_box
from DisplayCAL.util_io import LineCache
from DisplayCAL.worker import Worker


class _CallThread(QThread):
    """Run a zero-argument callable off the GUI thread."""

    #: Emitted with the callable's return value, or an ``Exception`` instance.
    done = Signal(object)

    def __init__(
        self, func: Callable[[], object], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._func = func
        #: Set directly (not just carried by :attr:`done`) so a caller that
        #: blocks on :meth:`QThread.wait` instead of pumping the event loop
        #: -- as :func:`connect_madvr` does -- can read the outcome without
        #: needing a delivered (necessarily queued, cross-thread) signal.
        self.result: object = None

    def run(self) -> None:
        try:
            result = self._func()
        except Exception as exception:  # noqa: BLE001  (reported on GUI thread)
            result = exception
        self.result = result
        self.done.emit(result)


def prisma_upload_filename(lut3d_path: str) -> str:
    """Compute the upload filename Prisma will store the 3D LUT under.

    Port of the filename half of the wx Prisma branch's ``upload`` case:
    shortens known gamut-preset input-profile basenames, otherwise keeps the
    full name, and appends the 3D LUT file's own creation timestamp.
    """
    basename = os.path.basename(getcfg("3dlut.input.profile"))
    name = os.path.splitext(basename)[0]
    gamut = {
        "SMPTE_RP145_NTSC": "NTSC",
        "EBU3213_PAL": "PAL",
        "SMPTE431_P3": "P3",
    }.get(name, name)
    return strftime(
        f"{gamut}-%Y%m%dT%H%M%S.3dl", localtime(os.stat(lut3d_path).st_ctime)
    )


class PrismaHostDialog(QDialog):
    """Prisma hostname/IP entry, with background discovery + connectivity check.

    Qt port of the Prisma branch of ``MainFrame.setup_patterngenerator``.
    Discovered clients (via the pattern generator's own UDP broadcast/listen
    protocol) populate the host combo box as they arrive; accepting only
    succeeds once the entered host has actually been resolved and connected
    to, mirroring wx's OK-button gating.
    """

    #: Emitted (GUI thread) with a discovered client's hostname.
    _client_discovered = Signal(str)

    def __init__(
        self,
        worker: Worker,
        title: str,
        upload: bool,
        lut3d_path: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._upload = upload
        self._checking = False
        self._check_thread: _CallThread | None = None
        self._discover_thread: _CallThread | None = None
        self.filename = ""
        self.setWindowTitle(title)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.getstr("patterngenerator.prisma.specify_host")))

        self.host_ctrl = QComboBox()
        self.host_ctrl.setEditable(True)
        self.host_ctrl.setInsertPolicy(QComboBox.NoInsert)
        host = getcfg("patterngenerator.prisma.host")
        if host:
            self.host_ctrl.addItem(host)
            self.host_ctrl.setCurrentText(host)
        self.host_ctrl.editTextChanged.connect(self._update_ok_enabled)
        layout.addWidget(self.host_ctrl)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #cc0000")
        layout.addWidget(self.error_label)

        self.preset_ctrl = None
        if upload:
            preset_row = QHBoxLayout()
            preset_row.addWidget(QLabel(lang.getstr("3dlut.holder.assign_preset")))
            self.preset_ctrl = QComboBox()
            self.preset_ctrl.addItems(
                config.VALID_VALUES["patterngenerator.prisma.preset"]
            )
            self.preset_ctrl.setCurrentText(getcfg("patterngenerator.prisma.preset"))
            preset_row.addWidget(self.preset_ctrl)
            layout.addLayout(preset_row)
            self.filename = prisma_upload_filename(lut3d_path)
            layout.addWidget(
                QLabel(f"{lang.getstr('filename.upload')}: {self.filename}")
            )

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._check_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._client_discovered.connect(self._on_client_discovered)
        self._update_ok_enabled()

        if worker.patterngenerator:
            worker.patterngenerator.disconnect_client()
        else:
            worker.setup_patterngenerator()
        worker.patterngenerator.bind(
            "on_client_added",
            lambda addr_client: self._client_discovered.emit(addr_client[1]["name"]),
        )
        self._discover_thread = _CallThread(self._discover, parent=self)
        self._discover_thread.start()

    def _discover(self) -> None:
        self._worker.patterngenerator.listen()
        self._worker.patterngenerator.announce()

    def _on_client_discovered(self, name: str) -> None:
        if sys.platform != "win32" and not name.endswith(".local"):
            name += ".local"
        if self.host_ctrl.findText(name) < 0:
            self.host_ctrl.addItem(name)
        if not self.host_ctrl.currentText():
            self.host_ctrl.setCurrentIndex(0)

    def _update_ok_enabled(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(self.host_ctrl.currentText())
        )

    def _check_and_accept(self) -> None:
        host = self.host_ctrl.currentText()
        if not host or self._checking:
            return
        self._checking = True
        self.error_label.setText(lang.getstr("please_wait"))
        self.error_label.setStyleSheet("")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self._check_thread = _CallThread(
            lambda: self._check_host(host), parent=self
        )
        self._check_thread.done.connect(self._on_host_checked)
        self._check_thread.start()

    def _check_host(self, host: str) -> str | Exception:
        try:
            ip = socket.gethostbyname(host)
            self._worker.patterngenerator.host = ip
            self._worker.patterngenerator.connect()
        except OSError as exception:
            return exception
        return ip

    def _on_host_checked(self, result: object) -> None:
        self._checking = False
        self._check_thread = None
        if isinstance(result, Exception):
            self.error_label.setStyleSheet("color: #cc0000")
            if isinstance(result, socket.gaierror):
                self.error_label.setText(lang.getstr("host.invalid.lookup_failed"))
            else:
                self.error_label.setText(str(result))
            self._update_ok_enabled()
        else:
            self.accept()

    def done(self, result: int) -> None:
        if self._worker.patterngenerator:
            self._worker.patterngenerator.listening = False
        if result == QDialog.Accepted:
            setcfg("patterngenerator.prisma.host", self.host_ctrl.currentText())
            if self._upload and self.preset_ctrl is not None:
                setcfg("patterngenerator.prisma.preset", self.preset_ctrl.currentText())
        super().done(result)


def _connect_madtpg(worker: Worker) -> bool | Exception:
    """Port of the madVR branch's background ``connect`` closure."""
    if not worker.madtpg_connect():
        raise Error(lang.getstr("madtpg.launch.failure"))
    return True


def connect_madvr(worker: Worker, parent: QWidget | None, title: str) -> bool | None:
    """Connect to madTPG, showing a cancellable wait dialog if it's slow.

    Qt port of the madVR branch of ``MainFrame.setup_patterngenerator``.

    Returns:
        True: connected successfully.
        False: connection failed (error already shown).
        None: cancelled while waiting to connect.
    """
    thread = _CallThread(lambda: _connect_madtpg(worker))
    thread.start()
    thread.wait(200)
    cancelled = False
    if not thread.isFinished():
        progress = QProgressDialog(
            lang.getstr("please_wait"), lang.getstr("cancel"), 0, 0, parent
        )
        progress.setWindowTitle(title)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        finished_naturally = False

        def _on_cancel() -> None:
            # QProgressDialog.closeEvent() emits `canceled` even when *we*
            # close it (via `_on_thread_finished` below) because the
            # background thread completed on its own -- only treat it as a
            # real user cancel otherwise.
            nonlocal cancelled
            if finished_naturally:
                return
            cancelled = True
            madtpg = getattr(worker, "madtpg", None)
            if madtpg is not None and hasattr(madtpg, "shutdown"):
                madtpg.shutdown()

        def _on_thread_finished() -> None:
            nonlocal finished_naturally
            finished_naturally = True
            progress.close()

        progress.canceled.connect(_on_cancel)
        thread.finished.connect(_on_thread_finished)
        # thread may have finished in the gap between the wait(200) timeout
        # and this connect() call; close() is safe to call on an unshown
        # dialog, so check again rather than risk exec_() blocking forever.
        if thread.isFinished():
            _on_thread_finished()
        else:
            progress.exec_()
    thread.wait()
    if cancelled:
        return None
    result = thread.result
    if isinstance(result, Exception):
        message_box.critical(parent, title, str(result))
        return False
    return bool(result)


def connect_patterngenerator(
    worker: Worker,
    parent: QWidget | None,
    title: str,
    lut3d_path: str = "",
    upload: bool = False,
) -> str | bool | None:
    """Connect to the pattern-generator destination for a 3D LUT install offer.

    Args:
        worker: The worker whose ``patterngenerator``/``madtpg`` this drives.
        parent: Parent widget for any dialogs shown.
        title: Dialog title (mirrors wx's ``title`` parameter).
        lut3d_path: Path to the already-created 3D LUT file (only needed for
            ``upload``, to derive the Prisma upload filename).
        upload: When connecting to Prisma, also collect the target preset and
            compute the upload filename (mirrors wx's ``upload`` parameter).

    Returns:
        True: connected (madVR, or Prisma with ``upload=False``).
        str: connected to Prisma with ``upload=True`` — the upload filename.
        None: the user cancelled.
        False: connection failed, or the display doesn't support this flow.
    """
    display_name = config.get_display_name(None, True)
    if display_name == "Prisma":
        dialog = PrismaHostDialog(worker, title, upload, lut3d_path, parent)
        result = dialog.exec_()
        if result != QDialog.Accepted or not dialog.host_ctrl.currentText():
            return None
        return dialog.filename if upload else True
    if display_name == "madVR":
        return connect_madvr(worker, parent, title)
    return False


def connect_live_patterngenerator(
    worker: Worker, parent: QWidget | None, title: str = APPNAME
) -> bool:
    """Connect to a pattern generator for live measurement patch output.

    Qt port of the Resolve / "Web @ localhost" / ``Chromecast *`` branch of
    ``MainFrame.setup_patterngenerator`` (``display_cal.py:11042-11089``),
    used by the visual whitepoint editor's live patch streaming
    (:mod:`DisplayCAL.ui.tools.visual_whitepoint_editor`). Unlike
    :func:`connect_patterngenerator` (madVR/Prisma, which dials out), these
    destinations accept an *incoming* connection, so this instantiates the
    client via :meth:`Worker.setup_patterngenerator` and then waits on a
    background thread, showing the client's own log output (e.g. "waiting
    for connection host:port") in a cancellable progress dialog.

    Returns:
        bool: True once ``worker.patterngenerator`` is connected, False if
            setup failed or the user cancelled.
    """
    logfile = LineCache(3)
    try:
        worker.setup_patterngenerator(logfile)
    except Exception as exception:  # noqa: BLE001 (reported to the user below)
        message_box.critical(parent, title, str(exception))
        return False
    patterngenerator = worker.patterngenerator
    if hasattr(patterngenerator, "conn"):
        return True

    progress = QProgressDialog("", lang.getstr("cancel"), 0, 0, parent)
    progress.setWindowTitle(title)
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)

    thread = _CallThread(patterngenerator.wait)
    cancelled = False
    finished_naturally = False

    def _on_cancel() -> None:
        # Same "who closed the dialog" race as connect_madvr's _on_cancel.
        nonlocal cancelled
        if finished_naturally:
            return
        cancelled = True
        patterngenerator.listening = False

    def _on_thread_finished() -> None:
        nonlocal finished_naturally
        finished_naturally = True
        progress.close()

    def _poll_log() -> None:
        line = logfile.read()
        if line:
            progress.setLabelText(line)

    timer = QTimer(progress)
    timer.timeout.connect(_poll_log)
    timer.start(100)

    progress.canceled.connect(_on_cancel)
    thread.finished.connect(_on_thread_finished)
    thread.start()
    if thread.isFinished():
        _on_thread_finished()
    else:
        progress.exec_()
    timer.stop()
    thread.wait()

    if cancelled:
        return False
    if isinstance(thread.result, Exception):
        message_box.critical(parent, title, str(thread.result))
        return False
    return hasattr(patterngenerator, "conn")


class Lut3DAPIInstallController(QObject):
    """Install a just-created 3D LUT directly to madVR or Prisma.

    Qt port of the ``install_3dlut_api`` branch of
    ``MainFrame.profile_finish_action`` (``display_cal.py:12504-12556``):
    connects via :func:`connect_patterngenerator` (the madVR/Prisma branches
    of ``MainFrame.setup_patterngenerator``), then runs
    :meth:`DisplayCAL.worker.Worker.install_3dlut` on a background thread.
    """

    #: Emitted once the whole flow ends, cancelled or not.
    finished = Signal()

    def __init__(
        self,
        worker: Worker,
        lut3d_path: str,
        is_prisma: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._lut3d_path = lut3d_path
        self._is_prisma = is_prisma
        self._parent = parent
        self._thread: _CallThread | None = None
        self._progress: QProgressDialog | None = None

    def run(self) -> None:
        title = lang.getstr("3dlut.install")
        result = connect_patterngenerator(
            self._worker,
            self._parent,
            title,
            lut3d_path=self._lut3d_path,
            upload=self._is_prisma,
        )
        if result is None or result is False:
            self.finished.emit()
            return
        filename = result if isinstance(result, str) else None
        self._progress = QProgressDialog(title, "", 0, 0, self._parent)
        self._progress.setWindowTitle(APPNAME)
        self._progress.setCancelButton(None)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.show()
        # Parented: _on_install_done drops the reference while the thread is
        # still finishing, and an unparented QThread destroyed while running
        # aborts the whole application
        self._thread = _CallThread(
            lambda: self._worker.install_3dlut(self._lut3d_path, filename),
            parent=self,
        )
        self._thread.done.connect(self._on_install_done)
        self._thread.start()

    def _on_install_done(self, result: object) -> None:
        self._thread = None
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        title = lang.getstr("3dlut.install")
        if isinstance(result, Info):
            message_box.information(self._parent, title, str(result))
        elif isinstance(result, Exception):
            message_box.critical(self._parent, title, str(result))
        self.finished.emit()
