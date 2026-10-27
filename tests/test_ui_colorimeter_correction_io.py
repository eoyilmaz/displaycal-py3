"""Headless tests for the Qt colorimeter-correction web-check/import/upload flows.

Exercises ``DisplayCAL.ui.colorimeter_correction_io`` (Stage 5+, the final
colorimeter-correction slice): the web-check chooser dialog and its
``WebCheckController``, the import options dialog and ``ImportController``,
and ``UploadController``. Network calls (``http_request``) and Argyll-backed
worker methods are stubbed/monkeypatched so no network or Argyll install is
needed. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``.
"""

import os
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.ui import colorimeter_correction_io as ccio  # noqa: E402
from DisplayCAL.worker import Worker  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


@pytest.fixture
def stub_worker(monkeypatch):
    def fake(self, *args, **kwargs):
        self.displays = ["DELL U2413 @ 0, 0, 1920x1080 [PRIMARY]"]
        self.instruments = ["i1 DisplayPro, ColorMunki Display"]

    monkeypatch.setattr(Worker, "enumerate_displays_and_ports", fake)


@pytest.fixture
def worker(qapp, stub_worker):
    w = Worker()
    w.enumerate_displays_and_ports(silent=True)
    return w


def _spin_until(qapp, predicate, timeout_s=30.0):
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


_ROW = {
    "cgats": b'CCMX\n\nDISPLAY "LCD Monitor"\n',
    "type": "Matrix",
    "description": "i1 DisplayPro, ColorMunki Display",
    "display": "Dell U2413",
    "reference": "i1 Pro",
    "spectral_resolution": "N/A",
    "observer": "Unknown",
    "fit_method": "N/A",
    "fit_avg_de00": "N/A",
    "fit_max_de00": "N/A",
    "created": "2012-04-19 13:24:37",
}


class TestWebCheckChooserDialog:
    def test_single_row_is_preselected_and_ok_enabled(self, qapp):
        dialog = ccio._WebCheckChooserDialog([_ROW], None)
        assert dialog._table.selectedItems()
        assert dialog._buttons.button(ccio.QDialogButtonBox.Ok).isEnabled()
        dialog.accept()
        assert dialog.selected_cgats == _ROW["cgats"]

    def test_multiple_rows_start_with_ok_disabled(self, qapp):
        dialog = ccio._WebCheckChooserDialog([_ROW, dict(_ROW)], None)
        assert not dialog._table.selectedItems()
        assert not dialog._buttons.button(ccio.QDialogButtonBox.Ok).isEnabled()

    def test_selecting_a_row_enables_ok(self, qapp):
        dialog = ccio._WebCheckChooserDialog([_ROW, dict(_ROW)], None)
        dialog._table.selectRow(1)
        assert dialog._buttons.button(ccio.QDialogButtonBox.Ok).isEnabled()

    def test_table_is_sortable(self, qapp):
        dialog = ccio._WebCheckChooserDialog([_ROW], None)
        assert dialog._table.isSortingEnabled()

    def test_de00_columns_sort_numerically_not_lexicographically(self, qapp):
        from qtpy.QtCore import Qt as _Qt

        rows = [
            dict(_ROW, cgats=b"A", display="A Display", fit_avg_de00="10.0"),
            dict(_ROW, cgats=b"B", display="B Display", fit_avg_de00="2.0"),
            dict(_ROW, cgats=b"C", display="C Display", fit_avg_de00="1.5"),
        ]
        dialog = ccio._WebCheckChooserDialog(rows, None)
        col = dialog._COLUMN_KEYS.index("fit_avg_de00")
        dialog._table.sortByColumn(col, _Qt.AscendingOrder)
        displays = [
            dialog._table.item(r, 0).data(_Qt.UserRole)["display"]
            for r in range(dialog._table.rowCount())
        ]
        # Numeric order (1.5 < 2.0 < 10.0), not lexicographic ("1.5" <
        # "10.0" < "2.0").
        assert displays == ["C Display", "B Display", "A Display"]

    def test_de00_column_sort_with_non_numeric_values_does_not_recurse(self, qapp):
        # Regression test: rows where fit_max_de00 is "Not applicable" (CCSS
        # entries, not CCMX) mixed with numeric CCMX entries once triggered
        # infinite recursion, because the non-numeric fallback called
        # super().__lt__(), which PySide re-dispatches back to this very
        # override rather than the base implementation.
        from qtpy.QtCore import Qt as _Qt

        rows = [
            dict(_ROW, cgats=b"A", display="A Display", fit_max_de00="Not applicable"),
            dict(_ROW, cgats=b"B", display="B Display", fit_max_de00="2.0"),
            dict(_ROW, cgats=b"C", display="C Display", fit_max_de00="1.0"),
        ]
        dialog = ccio._WebCheckChooserDialog(rows, None)
        col = dialog._COLUMN_KEYS.index("fit_max_de00")
        dialog._table.sortByColumn(col, _Qt.AscendingOrder)
        assert dialog._table.rowCount() == 3

    def test_accept_returns_correct_row_after_sorting(self, qapp):
        from qtpy.QtCore import Qt as _Qt

        rows = [
            dict(_ROW, cgats=b"A", display="A Display", fit_avg_de00="10.0"),
            dict(_ROW, cgats=b"B", display="B Display", fit_avg_de00="2.0"),
            dict(_ROW, cgats=b"C", display="C Display", fit_avg_de00="1.5"),
        ]
        dialog = ccio._WebCheckChooserDialog(rows, None)
        col = dialog._COLUMN_KEYS.index("fit_avg_de00")
        dialog._table.sortByColumn(col, _Qt.AscendingOrder)
        # After sorting, visual row 0 is "C Display" (lowest ΔE*00 avg).
        dialog._table.selectRow(0)
        dialog.accept()
        assert dialog.selected_cgats == b"C"


class TestWebCheckController:
    def test_fetch_failure_shows_message_and_finishes(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(ccio, "http_request", lambda *a, **k: False)
        infos = []
        monkeypatch.setattr(
            ccio.QMessageBox, "information", lambda *a, **k: infos.append(a)
        )
        controller = ccio.WebCheckController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run()
        assert _spin_until(qapp, lambda: finished)
        assert infos

    def test_fetch_success_opens_chooser_and_saves(
        self, qapp, worker, monkeypatch, tmp_path
    ):
        import json as json_module

        cgats_text = 'CCMX\n\nDESCRIPTOR "test"\nDISPLAY "LCD Monitor"\n'

        class _FakeResp:
            def read(self):
                return json_module.dumps(
                    [{"cgats": cgats_text, "type": "ccmx", "display": "Dell U2413"}]
                ).encode("utf-8")

        monkeypatch.setattr(ccio, "http_request", lambda *a, **k: _FakeResp())
        monkeypatch.setattr(config, "get_argyll_data_dir", lambda: str(tmp_path))
        monkeypatch.setattr(
            ccio, "_indeterminate_progress", lambda *a, **k: _NullProgress()
        )

        # Auto-accept the chooser dialog as if the user picked the only row.
        def _fake_exec(self):
            self._table.selectRow(0)
            self.accept()
            return ccio.QDialog.Accepted

        monkeypatch.setattr(ccio._WebCheckChooserDialog, "exec_", _fake_exec)
        controller = ccio.WebCheckController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run()
        assert _spin_until(qapp, lambda: finished)
        saved = list(tmp_path.glob("*.ccmx"))
        assert len(saved) == 1


class _NullProgress:
    def close(self):
        pass


class TestImportOptionsDialog:
    def test_icd_always_offered(self, qapp, worker):
        dialog = ccio._ImportOptionsDialog(worker, None, None, None, None)
        assert "icd" in dialog._checkboxes

    def test_i1d3_hidden_without_any_utility(self, qapp, worker):
        dialog = ccio._ImportOptionsDialog(worker, None, None, None, None)
        assert "i1d3" not in dialog._checkboxes

    def test_i1d3_offered_with_oeminst(self, qapp, worker):
        dialog = ccio._ImportOptionsDialog(worker, "/bin/oeminst", None, None, None)
        assert "i1d3" in dialog._checkboxes
        # Present instrument -> pre-checked.
        assert dialog._checkboxes["i1d3"].isChecked()

    def test_auto_button_sets_mode(self, qapp, worker):
        dialog = ccio._ImportOptionsDialog(worker, "/bin/oeminst", None, None, None)
        dialog._choose_auto()
        assert dialog.mode == "auto"

    def test_files_button_sets_mode(self, qapp, worker):
        dialog = ccio._ImportOptionsDialog(worker, "/bin/oeminst", None, None, None)
        dialog._choose_files()
        assert dialog.mode == "files"


class TestImportController:
    def test_cancelling_dialog_finishes_without_running(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(
            ccio._ImportOptionsDialog, "exec_", lambda self: ccio.QDialog.Rejected
        )
        controller = ccio.ImportController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run()
        assert finished
        assert controller._thread is None

    def test_asroot_choice_threads_through_to_detect_import_kind(
        self, qapp, worker, monkeypatch
    ):
        # A system-wide import authenticates via Worker.authenticate() (the
        # PasswordPromptAdapter seam), no longer a not-yet-available stub;
        # detect_import_kind() is mocked here since exercising the real
        # sudo/authenticate round-trip is worker.py's own coverage. Uses the
        # "files" mode (not "auto") so the auto-download fallback loop -- which
        # would otherwise reach out to the real network for any importer the
        # dialog auto-checked from stub_worker's instrument list -- never runs.
        def _fake_exec(self):
            self._checkboxes["icd"].setChecked(True)
            self._install_systemwide.setChecked(True)
            self._choose_files()
            return ccio.QDialog.Accepted

        monkeypatch.setattr(ccio._ImportOptionsDialog, "exec_", _fake_exec)
        monkeypatch.setattr(
            ccio.QFileDialog,
            "getOpenFileNames",
            lambda *a, **k: (["/tmp/DeviceCorrections.txt"], ""),
        )
        seen_asroot = []

        def fake_detect(
            worker_, result, i1d3, i1d3ccss, spyd4, spyd4en, icd, oeminst, path, asroot
        ):
            seen_asroot.append(asroot)
            return True, i1d3, spyd4, True

        monkeypatch.setattr(ccio.ccxx_helpers, "detect_import_kind", fake_detect)
        monkeypatch.setattr(ccio.QMessageBox, "information", lambda *a, **k: None)
        # The worker fixture's stub instrument list also auto-checks the i1d3
        # importer box; since only the "icd" file is fed through, _on_done
        # reports it as a failure -- mock critical() too so that (unrelated to
        # the asroot seam under test) doesn't pop a real modal dialog.
        monkeypatch.setattr(ccio.QMessageBox, "critical", lambda *a, **k: None)
        controller = ccio.ImportController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run()
        assert _spin_until(qapp, lambda: finished)
        assert seen_asroot == [True]
        assert isinstance(worker.password_prompt, ccio.PasswordPromptAdapter)

    def test_asroot_choice_threads_through_auto_download_fallback(
        self, qapp, worker, monkeypatch
    ):
        # Regression test for issue #810: the auto-download-fallback loop in
        # _do_import() once hardcoded asroot=False in its detect_import_kind()
        # call instead of threading dialog.asroot through, unlike the first
        # (direct-path) call site covered by the test above. Uses "auto" mode
        # with discover_auto_import_paths() mocked empty so the direct-path
        # loop never calls detect_import_kind(), isolating the fallback loop.
        def _fake_exec(self):
            self._install_systemwide.setChecked(True)
            self._choose_auto()
            return ccio.QDialog.Accepted

        monkeypatch.setattr(ccio._ImportOptionsDialog, "exec_", _fake_exec)
        monkeypatch.setattr(
            ccio.ccxx_helpers, "discover_auto_import_paths", lambda *a, **k: {}
        )
        monkeypatch.setattr(
            ccio.Worker, "download", lambda self, *a, **k: "/tmp/i1d3_download"
        )
        seen_asroot = []

        def fake_detect(
            worker_, result, i1d3, i1d3ccss, spyd4, spyd4en, icd, oeminst, path, asroot
        ):
            seen_asroot.append(asroot)
            return True, True, spyd4, icd

        monkeypatch.setattr(ccio.ccxx_helpers, "detect_import_kind", fake_detect)
        monkeypatch.setattr(ccio.QMessageBox, "information", lambda *a, **k: None)
        monkeypatch.setattr(ccio.QMessageBox, "critical", lambda *a, **k: None)
        controller = ccio.ImportController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run()
        assert _spin_until(qapp, lambda: finished)
        assert seen_asroot == [True]


class TestUploadController:
    def test_non_argyll_originator_is_rejected(
        self, qapp, worker, tmp_path, monkeypatch
    ):
        path = tmp_path / "correction.ccmx"
        path.write_bytes(b'CCMX\n\nORIGINATOR "SomeOtherApp"\nDISPLAY "x"\n')
        errors = []
        monkeypatch.setattr(
            ccio.QMessageBox, "critical", lambda *a, **k: errors.append(a)
        )
        controller = ccio.UploadController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run(str(path))
        assert finished
        assert errors
        assert controller._thread is None

    def test_declining_confirm_does_not_upload(
        self, qapp, worker, tmp_path, monkeypatch
    ):
        path = tmp_path / "correction.ccmx"
        path.write_bytes(b'CCMX\n\nORIGINATOR "Argyll dispcal"\nDISPLAY "x"\n')
        monkeypatch.setattr(
            ccio.QMessageBox, "question", lambda *a, **k: ccio.QMessageBox.No
        )
        controller = ccio.UploadController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run(str(path))
        assert finished
        assert controller._thread is None

    def test_successful_upload_reports_success(
        self, qapp, worker, tmp_path, monkeypatch
    ):
        path = tmp_path / "correction.ccmx"
        path.write_bytes(b'CCMX\n\nORIGINATOR "Argyll dispcal"\nDISPLAY "x"\n')
        monkeypatch.setattr(
            ccio.QMessageBox, "question", lambda *a, **k: ccio.QMessageBox.Yes
        )
        infos = []
        monkeypatch.setattr(
            ccio.QMessageBox, "information", lambda *a, **k: infos.append(a)
        )

        class _DupResp:
            def read(self):
                return b"NOTFOUND"

        class _PostResp:
            status = 201

        responses = [_DupResp(), _PostResp()]
        monkeypatch.setattr(ccio, "http_request", lambda *a, **k: responses.pop(0))
        controller = ccio.UploadController(worker, None)
        finished = []
        controller.finished.connect(lambda: finished.append(True))
        controller.run(str(path))
        assert _spin_until(qapp, lambda: finished)
        assert infos
