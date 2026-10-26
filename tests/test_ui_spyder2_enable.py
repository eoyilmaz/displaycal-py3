"""Headless tests for the Qt Spyder2 firmware-enable wizard.

Exercises ``DisplayCAL.ui.spyder2_enable``: the choice dialog, the pure
producer functions (``_enable_spyder2`` / ``_enable_spyder2_producer``), and
``Spyder2EnableController``. Argyll-backed ``Worker`` methods and the network
download are stubbed/monkeypatched so no real Argyll install or network
access is needed. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``.
"""

import os
import sys
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtWidgets import QMessageBox  # noqa: E402

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.ui import spyder2_enable as s2  # noqa: E402
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
def worker(qapp):
    w = Worker()
    w.argyll_version = [1, 2, 0]
    w.instruments = ["Spyder2"]
    return w


def _spin_until(qapp, predicate, timeout_s=30.0):
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


class TestEnableSpyder2Dialog:
    def test_needroot_forces_systemwide(self, qapp, worker):
        worker.argyll_version = [1, 1, 0]
        dialog = s2._EnableSpyder2Dialog(worker, None)
        assert not dialog._install_user.isEnabled()
        assert dialog._install_systemwide.isChecked()
        assert dialog.asroot is True

    def test_no_needroot_defaults_to_user(self, qapp, worker):
        worker.argyll_version = [1, 2, 0]
        dialog = s2._EnableSpyder2Dialog(worker, None)
        assert dialog._install_user.isEnabled()
        assert dialog._install_user.isChecked()
        assert dialog.asroot is False

    def test_choose_auto_sets_mode(self, qapp, worker):
        dialog = s2._EnableSpyder2Dialog(worker, None)
        dialog._choose_auto()
        assert dialog.mode == "auto"

    def test_choose_files_sets_mode(self, qapp, worker):
        dialog = s2._EnableSpyder2Dialog(worker, None)
        dialog._choose_files()
        assert dialog.mode == "files"


class TestEnableSpyder2:
    """Pure ``_enable_spyder2`` (port of ``MainFrame.enable_spyder2``)."""

    def test_passes_path_and_appends_sl_when_asroot(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(s2, "get_argyll_util", lambda name: "/bin/spyd2en")
        seen = {}

        def fake_exec_cmd(self, cmd, args, **kwargs):
            seen["cmd"] = cmd
            seen["args"] = list(args)
            return True

        monkeypatch.setattr(Worker, "exec_cmd", fake_exec_cmd)
        monkeypatch.setattr(
            Worker, "spyder2_firmware_exists", lambda self, scope=None: True
        )
        result = s2._enable_spyder2(worker, "/tmp/installer.exe", True)
        assert result is True
        assert seen["cmd"] == "/bin/spyd2en"
        assert seen["args"] == ["-v", "-Sl", "/tmp/installer.exe"]

    def test_no_sl_when_argyll_below_1_2_0(self, qapp, worker, monkeypatch):
        worker.argyll_version = [1, 1, 0]
        monkeypatch.setattr(s2, "get_argyll_util", lambda name: "/bin/spyd2en")
        seen = {}
        monkeypatch.setattr(
            Worker,
            "exec_cmd",
            lambda self, cmd, args, **k: seen.setdefault("args", list(args)) or True,
        )
        monkeypatch.setattr(
            Worker, "spyder2_firmware_exists", lambda self, scope=None: True
        )
        s2._enable_spyder2(worker, None, True)
        assert seen["args"] == ["-v"]

    def test_result_overridden_by_firmware_check_on_success(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(s2, "get_argyll_util", lambda name: "/bin/spyd2en")
        monkeypatch.setattr(Worker, "exec_cmd", lambda self, cmd, args, **k: True)
        calls = []

        def fake_firmware_exists(self, scope=None):
            calls.append(scope)
            return False

        monkeypatch.setattr(Worker, "spyder2_firmware_exists", fake_firmware_exists)
        result = s2._enable_spyder2(worker, None, True)
        assert result is False
        assert calls == ["l"]

    def test_failure_result_not_overridden(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(s2, "get_argyll_util", lambda name: "/bin/spyd2en")
        monkeypatch.setattr(Worker, "exec_cmd", lambda self, cmd, args, **k: False)
        monkeypatch.setattr(
            Worker,
            "spyder2_firmware_exists",
            lambda self, scope=None: pytest.fail("should not be called"),
        )
        assert s2._enable_spyder2(worker, None, False) is False

    def test_exception_result_not_overridden(self, qapp, worker, monkeypatch):
        exc = Exception("boom")
        monkeypatch.setattr(s2, "get_argyll_util", lambda name: "/bin/spyd2en")
        monkeypatch.setattr(Worker, "exec_cmd", lambda self, cmd, args, **k: exc)
        assert s2._enable_spyder2(worker, None, False) is exc


class TestEnableSpyder2Producer:
    """Pure ``_enable_spyder2_producer`` (port of ``MainFrame.enable_spyder2_producer``)."""

    def test_given_path_enables_directly(self, qapp, worker, monkeypatch):
        seen = []
        monkeypatch.setattr(
            s2,
            "_enable_spyder2",
            lambda w, path, asroot: seen.append((path, asroot)) or True,
        )
        result = s2._enable_spyder2_producer(worker, "/tmp/x.exe", True)
        assert result is True
        assert seen == [("/tmp/x.exe", True)]

    def test_dry_run_returns_none_without_download(self, qapp, worker, monkeypatch):
        # setcfg() mutates the in-memory CFG singleton directly, which
        # initcfg() (the autouse _init_config fixture) doesn't clear -- reset
        # explicitly so this doesn't leak "dry_run" into later tests.
        config.setcfg("dry_run", 1)
        try:
            monkeypatch.setattr(s2, "safe_glob", lambda pattern: [])
            monkeypatch.setattr(
                Worker,
                "download",
                lambda self, *a, **k: pytest.fail("should not download on dry_run"),
            )
            assert s2._enable_spyder2_producer(worker, None, False) is None
        finally:
            config.setcfg("dry_run", 0)

    def test_local_install_found_and_succeeds_skips_download(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(
            s2, "safe_glob", lambda pattern: ["/Applications/Spyder2/Spyder.lib"]
        )
        monkeypatch.setattr(s2, "_enable_spyder2", lambda w, path, asroot: True)
        monkeypatch.setattr(
            Worker, "download", lambda self, *a, **k: pytest.fail("should not download")
        )
        result = s2._enable_spyder2_producer(worker, None, False)
        assert result is True

    def test_falls_back_to_download_when_local_fails(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(s2, "safe_glob", lambda pattern: [])
        seen = []

        def fake_enable(w, path, asroot):
            seen.append(path)
            return True if path == "/tmp/downloaded" else False

        monkeypatch.setattr(s2, "_enable_spyder2", fake_enable)
        monkeypatch.setattr(Worker, "download", lambda self, uri: "/tmp/downloaded")
        result = s2._enable_spyder2_producer(worker, None, False)
        assert result is True
        assert seen == ["/tmp/downloaded"]

    def test_download_exception_propagates(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        exc = Exception("network down")
        monkeypatch.setattr(Worker, "download", lambda self, uri: exc)
        assert s2._enable_spyder2_producer(worker, None, False) is exc

    def test_download_cancelled_returns_none(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(Worker, "download", lambda self, uri: None)
        assert s2._enable_spyder2_producer(worker, None, False) is None


class TestSpyder2EnableController:
    def test_missing_argyll_bin_finishes_without_dialog(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: False)
        opened = []
        monkeypatch.setattr(
            s2._EnableSpyder2Dialog, "exec_", lambda self: opened.append(True)
        )
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert results == [False]
        assert not opened

    def test_cancelling_dialog_finishes_without_running(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)
        monkeypatch.setattr(
            s2._EnableSpyder2Dialog, "exec_", lambda self: s2.QDialog.Rejected
        )
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert results == [False]
        assert controller._thread is None

    def test_files_mode_no_selection_finishes_without_running(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)

        def _fake_exec(self):
            self._choose_files()
            return s2.QDialog.Accepted

        monkeypatch.setattr(s2._EnableSpyder2Dialog, "exec_", _fake_exec)
        monkeypatch.setattr(s2.QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert results == [False]

    def test_successful_auto_enable_shows_success_and_finishes_attempted(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)

        def _fake_exec(self):
            self._choose_auto()
            return s2.QDialog.Accepted

        monkeypatch.setattr(s2._EnableSpyder2Dialog, "exec_", _fake_exec)
        monkeypatch.setattr(
            s2, "_enable_spyder2_producer", lambda w, path, asroot: True
        )
        shown = []
        monkeypatch.setattr(
            QMessageBox,
            "information",
            lambda *a, **k: shown.append("info"),
        )
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert _spin_until(qapp, lambda: results)
        assert results == [True]
        assert shown == ["info"]
        assert isinstance(worker.password_prompt, s2.PasswordPromptAdapter)

    def test_failure_shows_error_and_finishes_attempted(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)

        def _fake_exec(self):
            self._choose_auto()
            return s2.QDialog.Accepted

        monkeypatch.setattr(s2._EnableSpyder2Dialog, "exec_", _fake_exec)
        monkeypatch.setattr(
            s2, "_enable_spyder2_producer", lambda w, path, asroot: False
        )
        worker.errors = []
        shown = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert _spin_until(qapp, lambda: results)
        assert results == [True]
        assert shown == [lang.getstr("enable_spyder2_failure")]

    def test_exception_shows_error_message(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)

        def _fake_exec(self):
            self._choose_auto()
            return s2.QDialog.Accepted

        monkeypatch.setattr(s2._EnableSpyder2Dialog, "exec_", _fake_exec)
        exc = Exception("spyd2en crashed")
        monkeypatch.setattr(s2, "_enable_spyder2_producer", lambda w, path, asroot: exc)
        shown = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert _spin_until(qapp, lambda: results)
        assert results == [True]
        assert shown == ["spyd2en crashed"]

    def test_cancelled_download_shows_no_dialog(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)

        def _fake_exec(self):
            self._choose_auto()
            return s2.QDialog.Accepted

        monkeypatch.setattr(s2._EnableSpyder2Dialog, "exec_", _fake_exec)
        monkeypatch.setattr(
            s2, "_enable_spyder2_producer", lambda w, path, asroot: None
        )
        monkeypatch.setattr(
            QMessageBox,
            "information",
            lambda *a, **k: pytest.fail("should not show a dialog"),
        )
        monkeypatch.setattr(
            QMessageBox,
            "critical",
            lambda *a, **k: pytest.fail("should not show a dialog"),
        )
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert _spin_until(qapp, lambda: results)
        assert results == [True]

    def test_asroot_choice_threads_through_to_producer(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(s2, "check_set_argyll_bin", lambda: True)

        def _fake_exec(self):
            self._install_systemwide.setChecked(True)
            self._choose_auto()
            return s2.QDialog.Accepted

        monkeypatch.setattr(s2._EnableSpyder2Dialog, "exec_", _fake_exec)
        seen_asroot = []

        def fake_producer(w, path, asroot):
            seen_asroot.append(asroot)
            return True

        monkeypatch.setattr(s2, "_enable_spyder2_producer", fake_producer)
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
        controller = s2.Spyder2EnableController(worker, None)
        results = []
        controller.finished.connect(lambda attempted: results.append(attempted))
        controller.run()
        assert _spin_until(qapp, lambda: results)
        assert seen_asroot == [True]
