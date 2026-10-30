"""Colorimeter-correction web-check / import / upload — Qt port.

Qt port of the three remaining pieces of
:meth:`DisplayCAL.display_cal.MainFrame.create_colorimeter_correction_handler`'s
sibling handlers named in the plan's Stage 5+ item (see
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``): checking the online colorimeter-
correction database (``colorimeter_correction_web_handler`` /
``colorimeter_correction_web_check_choose``), importing OEM-exported
corrections (``import_colorimeter_corrections_handler`` and its
producer/consumer), and uploading a correction to the online database
(``upload_colorimeter_correction_handler`` / ``MainFrame
.upload_colorimeter_correction``).

Each flow is a :class:`~qtpy.QtCore.QObject` controller (``WebCheckController``
/ ``ImportController`` / ``UploadController``) that owns a background
:class:`~qtpy.QtCore.QThread` plus an indeterminate progress dialog, mirroring
the ``_CreateThread`` pattern in :mod:`DisplayCAL.ui.colorimeter_correction_window`
and the ``WorkerRunController`` pattern in :mod:`DisplayCAL.ui.worker_runner`.
All three reuse the toolkit-neutral helpers added to
:mod:`DisplayCAL.colorimeter_correction` for this slice (``parse_web_check_
entries``, ``build_web_check_params``, ``build_upload_params``,
``validate_upload_originator``, ``detect_import_kind``,
``discover_auto_import_paths``).

Choosing the system-wide import-scope radio button authenticates via
``Worker.authenticate()``, whose sudo password prompt is serviced by a
:class:`~DisplayCAL.ui.worker_runner.PasswordPromptAdapter` (wired onto the
shared ``Worker`` the same way as ``DisplayCAL/ui/profile_install_window.py``).

Deliberately dropped / simplified versus the wx handlers:

* The "info" button that plots the spectral/matrix data (``CCXXPlot``) is not
  reproduced anywhere here, matching the drop already made in
  :mod:`DisplayCAL.ui.colorimeter_correction_window` (the wx-only ``CCXXPlot``
  visualization remains a future slice).
* These flows run standalone (their own ``Worker``, own progress dialogs) and
  are not yet wired to a live main window, so the post-import ``update_
  measurement_modes`` / ``update_colorimeter_correction_matrix_ctrl_items``
  refresh (MainFrame-only) is not reproduced; the caller (the future Qt main
  window) will need to refresh its own state after a successful import/web
  choice, same as the deferral noted in ``profile_install_window.py``.
"""

from __future__ import annotations

import json as json_module
import os
import sys
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import colorimeter_correction as ccxx_helpers
from DisplayCAL import localization as lang
from DisplayCAL.argyll import get_argyll_util
from DisplayCAL.config import get_argyll_data_dir, get_verified_path, getcfg, setcfg
from DisplayCAL.meta import DOMAIN
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.measurement_flow import observer_items
from DisplayCAL.ui.worker_runner import PasswordPromptAdapter
from DisplayCAL.worker import Worker, check_create_dir, http_request

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent

#: The importers offered by the import dialog, with their display name and
#: the instruments that make each relevant (matches the wx handler).
_IMPORTER_DEFS = (
    (
        "i1d3",
        "i1 Profiler",
        ("i1 DisplayPro, ColorMunki Display", "Spyder4", "Spyder5"),
    ),
    ("icd", "iColor Display", ("DTP94", "i1 Display 2", "Spyder2", "Spyder3")),
    ("spyd4", "Spyder4/5", ("Spyder4", "Spyder5")),
)


class _CallThread(QThread):
    """Run a zero-argument callable off the GUI thread.

    Args:
        func: Callable returning a result (or raising, in which case the
            exception is delivered via :attr:`done` instead of propagating).
        parent (QObject | None): Optional Qt parent.
    """

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


def _indeterminate_progress(title: str, parent: QWidget | None) -> QProgressDialog:
    progress = QProgressDialog(title, "", 0, 0, parent)
    progress.setWindowTitle(title)
    progress.setCancelButton(None)
    progress.setWindowModality(Qt.WindowModal)
    progress.show()
    return progress


def save_correction(cgats_bytes: bytes, parent: QWidget | None = None) -> bool:
    """Write a chosen/created correction to the Argyll data dir, with overwrite check.

    Toolkit-neutral in spirit (mirrors ``colorimeter_correction_check_
    overwrite``) but shown here rather than in ``colorimeter_correction.py``
    since it drives Qt dialogs directly, matching ``CreateCorrectionWindow
    ._save``. The wx version's comport/measurement-mode-control refresh is
    MainFrame-only and not reproduced (see module docstring).

    Returns:
        bool: True if the file was written.
    """
    title = lang.getstr("colorimeter_correction.web_check")
    result = check_create_dir(get_argyll_data_dir())
    if isinstance(result, Exception):
        message_box.critical(parent, title, str(result))
        return False
    path = ccxx_helpers.get_cgats_path(cgats_bytes)
    if os.path.isfile(path):
        reply = message_box.question(
            parent, title, lang.getstr("dialog.confirm_overwrite", path)
        )
        if reply != QMessageBox.Yes:
            return False
    try:
        with open(path, "wb") as cgatsfile:
            cgatsfile.write(cgats_bytes.rstrip(b"\n") + b"\n")
    except OSError as exception:
        message_box.critical(parent, title, str(exception))
        return False
    if getcfg("colorimeter_correction_matrix_file").split(":")[0] != "AUTO":
        setcfg("colorimeter_correction_matrix_file", ":" + path)
    return True


# -- Web check ----------------------------------------------------------------


class _NumericTableWidgetItem(QTableWidgetItem):
    """Table item that sorts numerically instead of lexicographically.

    Falls back to the base class's text comparison for values that aren't
    parseable as ``float`` (e.g. "unknown"/"not_applicable" placeholders).
    """

    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return float(self.text()) < float(other.text())
        except (TypeError, ValueError):
            # Not super().__lt__(other): PySide's vtable slot for this
            # virtual still points at this very override regardless of the
            # MRO, so calling up re-enters here and recurses forever.
            return self.text() < other.text()


class _WebCheckChooserDialog(QDialog):
    """List the corrections the online DB returned and let the user pick one."""

    #: Columns sorted numerically (ΔE*00 values) rather than as plain text.
    _NUMERIC_COLUMN_KEYS = frozenset({"fit_avg_de00", "fit_max_de00"})

    _COLUMN_KEYS = (
        "type",
        "description",
        "display",
        "reference",
        "spectral_resolution",
        "observer",
        "fit_method",
        "fit_avg_de00",
        "fit_max_de00",
        "created",
    )

    def __init__(self, rows: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang.getstr("colorimeter_correction.web_check"))
        self.selected_cgats: bytes | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.getstr("colorimeter_correction.web_check.choose")))

        headers = [
            lang.getstr("type"),
            lang.getstr("description"),
            lang.getstr("display"),
            lang.getstr("reference"),
            lang.getstr("spectral_resolution"),
            lang.getstr("observer"),
            lang.getstr("method"),
            "ΔE*00 " + lang.getstr("profile.self_check.avg"),
            "ΔE*00 " + lang.getstr("profile.self_check.max"),
            lang.getstr("created"),
        ]
        table = QTableWidget(len(rows), len(headers), self)
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for r, row in enumerate(rows):
            for c, key in enumerate(self._COLUMN_KEYS):
                item_cls = (
                    _NumericTableWidgetItem
                    if key in self._NUMERIC_COLUMN_KEYS
                    else QTableWidgetItem
                )
                item = item_cls(str(row[key]))
                if c == 0:
                    # Sorting reorders rows visually, so the row's source
                    # dict travels with its item rather than being looked up
                    # by position in `rows` later.
                    item.setData(Qt.UserRole, row)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        table.setSortingEnabled(True)
        table.itemSelectionChanged.connect(self._update_ok_state)
        self._table = table
        layout.addWidget(table)

        info = lang.getstr("colorimeter_correction.web_check.info")
        if info:
            info_label = QLabel(info)
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)
        self.resize(820, 320)

        if len(rows) == 1:
            table.selectRow(0)
        self._update_ok_state()

    def _update_ok_state(self) -> None:
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(self._table.selectedItems())
        )

    def accept(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = self._table.item(rows[0].row(), 0).data(Qt.UserRole)
            self.selected_cgats = row["cgats"]
        super().accept()


class WebCheckController(QObject):
    """Check the online colorimeter-correction database and save a choice."""

    #: Emitted when the flow ends (chosen-and-saved, cancelled, or failed).
    finished = Signal()

    def __init__(self, worker: Worker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._parent = parent
        self._thread: _CallThread | None = None
        self._progress: QProgressDialog | None = None

    def run(self) -> None:
        """Start the web-check request in the background."""
        self._progress = _indeterminate_progress(
            lang.getstr("colorimeter_correction.web_check"), self._parent
        )
        self._thread = _CallThread(self._fetch)
        self._thread.done.connect(self._on_fetched)
        self._thread.start()

    def _fetch(self) -> list | Exception:
        params = ccxx_helpers.build_web_check_params(self._worker)
        resp = http_request(
            None,
            f"colorimetercorrections.{DOMAIN}",
            "GET",
            "/index.php",
            params,
            silent=True,
        )
        if resp is False:
            return RuntimeError(lang.getstr("colorimeter_correction.web_check.failure"))
        try:
            entries = json_module.loads(resp.read())
        except ValueError:
            entries = None
        if not entries:
            return RuntimeError(lang.getstr("colorimeter_correction.web_check.failure"))
        return entries

    def _on_fetched(self, result: list | Exception) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        title = lang.getstr("colorimeter_correction.web_check")
        if isinstance(result, Exception):
            message_box.information(self._parent, title, str(result))
            self.finished.emit()
            return
        rows = ccxx_helpers.parse_web_check_entries(result, observer_items())
        dialog = _WebCheckChooserDialog(rows, self._parent)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_cgats:
            save_correction(dialog.selected_cgats, self._parent)
        self.finished.emit()


# -- Import -------------------------------------------------------------------


class _ImportOptionsDialog(QDialog):
    """Offer the auto-detect importers, or a manual file/scope choice."""

    def __init__(
        self,
        worker: Worker,
        oeminst: str | None,
        i1d3ccss: str | None,
        spyd4en: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang.getstr("colorimeter_correction.import"))
        self.mode: str | None = None  # "auto" | "files" | None (cancelled)

        layout = QVBoxLayout(self)
        msg = " ".join(
            [
                lang.getstr("oem.import.auto"),
                lang.getstr("oem.import.auto.download_selection"),
            ]
        )
        label = QLabel(msg)
        label.setWordWrap(True)
        layout.addWidget(label)

        self._checkboxes: dict[str, QCheckBox] = {}
        importer_availability = {
            "i1d3": i1d3ccss or oeminst,
            "icd": True,
            "spyd4": spyd4en or oeminst,
        }
        for name, desc, instruments_ in _IMPORTER_DEFS:
            if not importer_availability[name]:
                continue
            checkbox = QCheckBox(f"{desc} ({', '.join(instruments_)})")
            check_exists = worker.spyder4_cal_exists() if name == "spyd4" else False
            if any(
                instrument in worker.instruments and not check_exists
                for instrument in instruments_
            ):
                checkbox.setChecked(True)
            layout.addWidget(checkbox)
            self._checkboxes[name] = checkbox

        self._install_user = QRadioButton(lang.getstr("install_user"))
        self._install_user.setChecked(True)
        self._install_systemwide = QRadioButton(lang.getstr("install_local_system"))
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
    def importers(self) -> dict[str, bool]:
        return {
            name: True
            for name, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        }

    @property
    def asroot(self) -> bool:
        return self._install_systemwide.isChecked()


class ImportController(QObject):
    """Import colorimeter corrections exported by other profiling software."""

    #: Emitted when the flow ends.
    finished = Signal()

    def __init__(self, worker: Worker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._parent = parent
        if worker.password_prompt is None:
            # Elevated (system-wide) imports authenticate via
            # Worker.authenticate(); wire the Qt password prompt regardless of
            # which window constructed this Worker.
            worker.password_prompt = PasswordPromptAdapter(parent=parent)
        self._thread: _CallThread | None = None
        self._progress: QProgressDialog | None = None
        self._oeminst = get_argyll_util("oeminst")
        self._i1d3ccss = None if self._oeminst else get_argyll_util("i1d3ccss")
        self._spyd4en = None if self._oeminst else get_argyll_util("spyd4en")

    def run(self) -> None:
        """Show the import options dialog, then run the chosen import."""
        dialog = _ImportOptionsDialog(
            self._worker, self._oeminst, self._i1d3ccss, self._spyd4en, self._parent
        )
        if dialog.exec_() != QDialog.Accepted or dialog.mode is None:
            self.finished.emit()
            return
        importers = dialog.importers
        if not importers:
            self.finished.emit()
            return
        self._asroot = dialog.asroot

        paths: list = []
        if dialog.mode == "files":
            paths, _filter = file_dialog.get_open_file_names(
                self._parent,
                lang.getstr("colorimeter_correction.import.choose"),
                "",
                f"{lang.getstr('filetype.any')} (*)",
            )
            if not paths:
                self.finished.emit()
                return

        self._importers = importers
        self._paths = paths
        self._auto = dialog.mode == "auto"
        self._progress = _indeterminate_progress(
            lang.getstr("colorimeter_correction.import"), self._parent
        )
        self._thread = _CallThread(self._do_import)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _do_import(self) -> tuple:
        """Run on :class:`_CallThread`. Mirrors the wx producer's body."""
        result: bool | Exception | None = None
        i1d3 = spyd4 = icd = False
        paths = list(self._paths)
        if self._auto and not paths:
            found = ccxx_helpers.discover_auto_import_paths(
                self._importers,
                i1d3,
                self._i1d3ccss,
                spyd4,
                self._spyd4en,
                self._oeminst,
            )
            if found.get("icd"):
                paths.extend(found["icd"])
            i1d3fn = found.get("i1d3", [])
            if len(i1d3fn) > 1:
                paths.append(i1d3fn)
            else:
                paths.extend(i1d3fn)
            if found.get("spyd4"):
                paths.extend(found["spyd4"])
        for path in paths:
            result, i1d3, spyd4, icd = ccxx_helpers.detect_import_kind(
                self._worker,
                result,
                i1d3,
                self._i1d3ccss,
                spyd4,
                self._spyd4en,
                icd,
                self._oeminst,
                path,
                self._asroot,
            )
        # Automatic web-download fallback (when an OEM package isn't found
        # locally): the same toolkit-neutral worker calls the wx producer
        # used, so it runs unchanged on this background thread.
        download_paths = []
        for name in self._importers:
            imported = {"i1d3": i1d3, "icd": icd, "spyd4": spyd4}.get(name, False)
            if (imported and name != "i1d3") or not self._auto:
                continue
            download_name = name
            if name == "icd" and sys.platform == "darwin":
                download_name += ".dmg"
            self._worker.recent.clear()
            self._worker.lastmsg.clear()
            result = self._worker.download(
                f"https://{DOMAIN}/{download_name}", force=name == "i1d3"
            )
            if isinstance(result, Exception):
                break
            if not result:
                result = None
                break
            if os.path.basename(result).lower() == "i1d3.zip":
                result = self._worker.extract_archive(result)
                if isinstance(result, Exception):
                    break
                result = [p for p in result if not os.path.isdir(p)]
            download_paths.append(result)
        if not isinstance(result, Exception) and result:
            for path in download_paths:
                result, i1d3, spyd4, icd = ccxx_helpers.detect_import_kind(
                    self._worker,
                    result,
                    i1d3,
                    self._i1d3ccss,
                    spyd4,
                    self._spyd4en,
                    icd,
                    self._oeminst,
                    path,
                    self._asroot,
                )
        return result, i1d3, spyd4, icd

    def _on_done(self, results: tuple) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        result, i1d3, spyd4, icd = results
        title = lang.getstr("colorimeter_correction.import")
        if isinstance(result, Exception):
            message_box.critical(self._parent, title, str(result))
            self.finished.emit()
            return
        imported = []
        failures = []
        mapping = {
            "i1 Profiler/ColorMunki Display": i1d3,
            "Spyder4/5": spyd4,
            "iColor Display": icd,
        }
        for name, subresult in mapping.items():
            if subresult and not isinstance(subresult, Exception):
                imported.append(name)
            elif subresult is not None:
                failures.append(name)
        if imported:
            message_box.information(
                self._parent,
                title,
                lang.getstr(
                    "colorimeter_correction.import.success", "\n".join(imported)
                ),
            )
        if failures or (not imported and result is not None):
            error = "".join(self._worker.errors) or (
                lang.getstr("colorimeter_correction.import.failure")
                + "\n\n"
                + "\n".join(failures)
            )
            message_box.critical(self._parent, title, error)
        self.finished.emit()


# -- Upload -------------------------------------------------------------------


class UploadController(QObject):
    """Upload a CCMX/CCSS correction to the online database."""

    #: Emitted when the flow ends.
    finished = Signal()

    def __init__(self, worker: Worker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._parent = parent
        self._thread: _CallThread | None = None
        self._progress: QProgressDialog | None = None

    def run(self, path: str | None = None) -> None:
        """Prompt for a correction file (unless ``path`` is given) and upload it."""
        title = lang.getstr("colorimeter_correction.upload")
        if path is None:
            default_dir, _default_file = get_verified_path("last_filedialog_path")
            path, _filter = file_dialog.get_open_file_name(
                self._parent,
                lang.getstr("colorimeter_correction_matrix_file.choose"),
                default_dir,
                f"{lang.getstr('filetype.ccmx')} (*.ccmx *.ccss)",
            )
            if not path:
                self.finished.emit()
                return
            setcfg("last_filedialog_path", path)

        with open(path, "rb") as cgatsfile:
            cgats = cgatsfile.read()
        if not ccxx_helpers.validate_upload_originator(
            cgats.decode("utf-8", "replace"), APPNAME
        ):
            message_box.critical(
                self._parent, title, lang.getstr("colorimeter_correction.upload.deny")
            )
            self.finished.emit()
            return

        reply = message_box.question(
            self._parent, title, lang.getstr("colorimeter_correction.upload.confirm")
        )
        if reply != QMessageBox.Yes:
            self.finished.emit()
            return

        self._params = ccxx_helpers.build_upload_params(cgats)
        self._progress = _indeterminate_progress(title, self._parent)
        self._thread = _CallThread(self._do_upload)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _do_upload(self) -> Exception | str:
        path = "/index.php"
        failure_msg = lang.getstr("colorimeter_correction.upload.failure")
        resp = http_request(
            None,
            f"colorimetercorrections.{DOMAIN}",
            "GET",
            path,
            {
                "get": True,
                "hash": ccxx_helpers.compute_upload_dedup_hash(
                    bytes(self._params["cgats"])
                ),
            },
            silent=True,
        )
        if resp and resp.read().strip().startswith(b"CC"):
            return "exists"
        params = dict(self._params)
        params["put"] = True
        resp = http_request(
            None,
            f"colorimetercorrections.{DOMAIN}",
            "POST",
            path,
            params,
            failure_msg=failure_msg,
            silent=True,
        )
        if resp is False:
            return RuntimeError(failure_msg)
        if resp.status == 201:
            return "success"
        server_msg = resp.read().strip().decode("utf-8", "replace")
        return RuntimeError(f"{failure_msg}\n\n{server_msg}")

    def _on_done(self, result: str | Exception) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        title = lang.getstr("colorimeter_correction.upload")
        if result == "exists":
            message_box.information(
                self._parent,
                title,
                lang.getstr("colorimeter_correction.upload.exists"),
            )
        elif result == "success":
            message_box.information(
                self._parent,
                title,
                lang.getstr("colorimeter_correction.upload.success"),
            )
        else:
            message_box.critical(self._parent, title, str(result))
        self.finished.emit()


# -- Standalone launcher --------------------------------------------------


class ColorimeterCorrectionIOWindow(BaseWindow):
    """Standalone launcher exercising web-check / import / upload.

    Not part of the shipping main window yet (see module docstring); useful
    for manual testing and as the ``python -m`` entry point other ported
    tools use.
    """

    def __init__(self) -> None:
        super().__init__(
            name="colorimetercorrectionio",
            title=lang.getstr("colorimeter_correction_matrix_file"),
            icon_name=f"{APPNAME}-CCXX-maker".lower(),
        )
        self.worker = Worker()
        self.worker.enumerate_displays_and_ports(silent=True)
        self._controller: QObject | None = None

        central = QWidget(self)
        layout = QVBoxLayout(central)
        web_btn = QPushButton(lang.getstr("colorimeter_correction.web_check"))
        web_btn.clicked.connect(self._run_web_check)
        layout.addWidget(web_btn)
        import_btn = QPushButton(lang.getstr("colorimeter_correction.import"))
        import_btn.clicked.connect(self._run_import)
        layout.addWidget(import_btn)
        upload_btn = QPushButton(lang.getstr("colorimeter_correction.upload"))
        upload_btn.clicked.connect(self._run_upload)
        layout.addWidget(upload_btn)
        self.setCentralWidget(central)
        self.resize(360, 160)
        self.restore_position()

    def _run_web_check(self) -> None:
        self._controller = WebCheckController(self.worker, self)
        self._controller.run()

    def _run_import(self) -> None:
        self._controller = ImportController(self.worker, self)
        self._controller.run()

    def _run_upload(self) -> None:
        self._controller = UploadController(self.worker, self)
        self._controller.run()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist config on close, matching the other ported windows."""
        super().closeEvent(event)
        from DisplayCAL import config

        config.writecfg()


def main() -> None:
    """Run the colorimeter-correction web-check/import/upload launcher standalone."""
    from DisplayCAL.ui.application import Application

    app = Application([])
    window = ColorimeterCorrectionIOWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
