"""Headless tests for the Qt update-check dialogs/controller.

Exercises ``DisplayCAL.ui.update_check_window``: the "update available"
dialog, the "up to date" notice, and ``UpdateCheckController``. Network calls
go through the toolkit-neutral :mod:`DisplayCAL.update_check`, monkeypatched
here so no real network access happens.
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
from DisplayCAL import update_check as uc  # noqa: E402
from DisplayCAL.config import getcfg, setcfg  # noqa: E402
from DisplayCAL.ui import update_check_window as ucw  # noqa: E402


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


@pytest.fixture(autouse=True)
def _join_controller_threads(monkeypatch):
    """Wait for every controller's check thread before the next test starts.

    A thread still running at teardown delivers its result into the next
    test (whose patched dialog then records it), and a collected controller
    destroys its ``QThread`` while it is still running.
    """
    controllers = []
    run = ucw.UpdateCheckController.run

    def tracked_run(self, *args, **kwargs):
        controllers.append(self)
        run(self, *args, **kwargs)

    monkeypatch.setattr(ucw.UpdateCheckController, "run", tracked_run)
    yield
    for controller in controllers:
        controller._thread.wait()


def _spin_until(qapp, predicate, timeout_s=30.0):
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


class _FakeWorker:
    def __init__(self, argyll_version=None):
        self.argyll_version = argyll_version or [0, 0, 0]


_APP_RESULT = uc.UpdateCheckResult(
    component="app",
    current_version="1.0.0",
    new_version="2.0.0",
    changelog_html="<p>Changes</p>",
    download_url="https://example.com/DisplayCAL-2.0.0.tar.gz",
    release_page_url="https://example.com/releases",
)

_ARGYLL_RESULT = uc.UpdateCheckResult(
    component="argyll",
    current_version="2.0.0",
    new_version="2.1.0",
    changelog_html=None,
    download_url=None,
    release_page_url="https://www.argyllcms.com/",
)


class TestUpdateAvailableDialog:
    def test_shows_direct_download_button_when_url_resolved(self, qapp):
        dialog = ucw._UpdateAvailableDialog(_APP_RESULT, None)
        assert dialog._url == _APP_RESULT.download_url
        assert lang.getstr("download") in [
            dialog.findChild(ucw.QDialogButtonBox).buttons()[0].text()
        ]

    def test_falls_back_to_website_button_without_download_url(self, qapp):
        dialog = ucw._UpdateAvailableDialog(_ARGYLL_RESULT, None)
        assert dialog._url == _ARGYLL_RESULT.release_page_url

    def test_accept_persists_onstartup_checkbox(self, qapp, monkeypatch):
        setcfg("update_check", 1)
        launched = []
        monkeypatch.setattr(ucw, "launch_file", lambda url: launched.append(url))
        dialog = ucw._UpdateAvailableDialog(_APP_RESULT, None)
        dialog._onstartup_checkbox.setChecked(False)
        dialog._open_url()
        assert getcfg("update_check") == 0
        assert launched == [_APP_RESULT.download_url]

    def test_reject_persists_onstartup_checkbox_without_opening_url(
        self, qapp, monkeypatch
    ):
        setcfg("update_check", 0)
        launched = []
        monkeypatch.setattr(ucw, "launch_file", lambda url: launched.append(url))
        dialog = ucw._UpdateAvailableDialog(_APP_RESULT, None)
        dialog._onstartup_checkbox.setChecked(True)
        dialog.reject()
        assert getcfg("update_check") == 1
        assert launched == []


class TestShowUpToDateDialog:
    def test_persists_onstartup_checkbox_state(self, qapp, monkeypatch):
        setcfg("update_check", 1)
        captured = {}

        def fake_exec(self):
            captured["checkbox"] = self.checkBox()
            captured["checkbox"].setChecked(False)
            return ucw.QMessageBox.Ok

        monkeypatch.setattr(ucw.QMessageBox, "exec_", fake_exec)
        ucw.show_up_to_date_dialog(None)
        assert getcfg("update_check") == 0
        assert captured["checkbox"] is not None


class TestUpdateCheckController:
    def test_finds_app_update_shows_dialog_and_emits_true(self, qapp, monkeypatch):
        monkeypatch.setattr(uc, "check_app_update", lambda: _APP_RESULT)
        monkeypatch.setattr(uc, "check_argyll_update", lambda *_a: None)
        shown = []
        monkeypatch.setattr(
            ucw._UpdateAvailableDialog,
            "exec_",
            lambda self: shown.append(self._url) or ucw.QDialog.Rejected,
        )
        controller = ucw.UpdateCheckController(_FakeWorker(), None)
        results = []
        controller.finished.connect(results.append)
        controller.run(silent=True)
        assert _spin_until(qapp, lambda: results)
        assert results == [True]
        assert shown == [_APP_RESULT.download_url]

    def test_finds_argyll_update_shows_dialog(self, qapp, monkeypatch):
        monkeypatch.setattr(uc, "check_app_update", lambda: None)
        monkeypatch.setattr(uc, "check_argyll_update", lambda *_a: _ARGYLL_RESULT)
        shown = []
        monkeypatch.setattr(
            ucw._UpdateAvailableDialog,
            "exec_",
            lambda self: shown.append(self._url) or ucw.QDialog.Rejected,
        )
        controller = ucw.UpdateCheckController(
            _FakeWorker(argyll_version=[2, 0, 0]), None
        )
        results = []
        controller.finished.connect(results.append)
        controller.run(silent=True)
        assert _spin_until(qapp, lambda: results)
        assert results == [True]
        assert shown == [_ARGYLL_RESULT.release_page_url]

    def test_nothing_found_silent_shows_no_dialog(self, qapp, monkeypatch):
        monkeypatch.setattr(uc, "check_app_update", lambda: None)
        monkeypatch.setattr(uc, "check_argyll_update", lambda *_a: None)
        monkeypatch.setattr(
            ucw, "show_up_to_date_dialog", lambda *a, **k: pytest.fail("shown")
        )
        controller = ucw.UpdateCheckController(_FakeWorker(), None)
        results = []
        controller.finished.connect(results.append)
        controller.run(silent=True)
        assert _spin_until(qapp, lambda: results)
        assert results == [False]

    def test_nothing_found_not_silent_shows_up_to_date_dialog(self, qapp, monkeypatch):
        monkeypatch.setattr(uc, "check_app_update", lambda: None)
        monkeypatch.setattr(uc, "check_argyll_update", lambda *_a: None)
        calls = []
        monkeypatch.setattr(
            ucw, "show_up_to_date_dialog", lambda *a, **k: calls.append(True)
        )
        controller = ucw.UpdateCheckController(_FakeWorker(), None)
        results = []
        controller.finished.connect(results.append)
        controller.run(silent=False)
        assert _spin_until(qapp, lambda: results)
        assert calls
        assert results == [False]
