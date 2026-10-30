"""Tests for the Qt profile install window ``DisplayCAL.ui.profile_install_window``.

These drive the window headless via the shared offscreen ``QApplication``
fixture. Display/port enumeration and the actual Argyll ``dispwin`` install are
stubbed so the tests need no Argyll install or real display. See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5+).
"""

import os
import time

import pytest

from DisplayCAL import config
from DisplayCAL import profile_install as pi
from DisplayCAL.worker import Worker

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui import profile_install_window as piw  # noqa: E402

_VALID_PROFILE = os.path.join(
    os.path.dirname(__file__), "data", "icc", "vcgt_cm_test_cyanish_reddish.icc"
)


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


@pytest.fixture
def stub_worker(monkeypatch):
    """Stub worker enumeration so no Argyll / hardware is needed."""

    def fake(self, *args, **kwargs):
        self.displays = ["DELL U2413 @ 0, 0, 1920x1080 [PRIMARY]"]
        self.instruments = ["i1 DisplayPro, ColorMunki Display"]

    monkeypatch.setattr(Worker, "enumerate_displays_and_ports", fake)


@pytest.fixture
def fixed_scope_options(monkeypatch):
    """Force a deterministic, non-empty scope choice regardless of the host."""
    monkeypatch.setattr(
        piw.pi, "resolve_install_scope_options", lambda **kw: ["u", "l"]
    )


@pytest.fixture
def window(qapp, stub_worker, fixed_scope_options):
    # profile.install_scope persists across tests in the shared config module;
    # pin it so each test starts from a known scope regardless of what an
    # earlier test left behind.
    config.setcfg("profile.install_scope", "u")
    win = piw.InstallProfileWindow()
    yield win
    win.close()


def _spin_until(qapp, predicate, timeout_s=30.0):
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


# --- construction -----------------------------------------------------------


def test_starts_with_no_profile_selected(window):
    assert not window.install_btn.isEnabled()
    assert not window.show_profile_info_btn.isEnabled()


def test_scope_buttons_built_from_resolved_options(window):
    assert set(window._scope_buttons) == {"u", "l"}
    assert window._scope_buttons["u"].isChecked()


def test_no_scope_options_forces_user_scope(qapp, stub_worker, monkeypatch):
    monkeypatch.setattr(piw.pi, "resolve_install_scope_options", lambda **kw: [])
    win = piw.InstallProfileWindow()
    try:
        assert win._scope_buttons == {}
        assert config.getcfg("profile.install_scope") == "u"
    finally:
        win.close()


# --- profile selection --------------------------------------------------


def test_load_valid_profile_enables_controls(window):
    window._load_path(_VALID_PROFILE)
    assert window.install_btn.isEnabled()
    assert window.show_profile_info_btn.isEnabled()
    assert window.path_label.text() == _VALID_PROFILE
    assert config.getcfg("last_icc_path") == _VALID_PROFILE


def test_load_missing_file_shows_error_and_leaves_state_unchanged(window, monkeypatch):
    errors = []
    monkeypatch.setattr(piw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._load_path("/nonexistent/path/profile.icc")

    assert errors
    assert not window.install_btn.isEnabled()


def test_load_unsupported_profile_shows_specific_error(window, monkeypatch):
    errors = []
    monkeypatch.setattr(piw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    def fake_load(path):
        raise pi.ProfileUnsupportedError(b"scnr", b"CMYK")

    monkeypatch.setattr(piw.pi, "load_installable_profile", fake_load)

    window._load_path("irrelevant.icc")

    assert errors
    assert not window.install_btn.isEnabled()


def test_show_profile_info_opens_and_loads(window, monkeypatch):
    window._load_path(_VALID_PROFILE)

    class _FakeProfileInfoWindow:
        def __init__(self):
            self.loaded = None
            self._visible = False

        def load_profile(self, path):
            self.loaded = path

        def show(self):
            self._visible = True

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def isVisible(self):
            return self._visible

    monkeypatch.setattr(piw, "ProfileInfoWindow", _FakeProfileInfoWindow)

    window._show_profile_info()

    assert window._profile_info_window.loaded == _VALID_PROFILE
    assert window._profile_info_window.isVisible()


# --- load on login ----------------------------------------------------------


def test_load_on_login_checkbox_persists_config(window):
    window.load_on_login_check.setChecked(True)
    assert config.getcfg("profile.load_on_login") == 1
    window.load_on_login_check.setChecked(False)
    assert config.getcfg("profile.load_on_login") == 0


# --- install scope ------------------------------------------------------


def test_scope_selection_persists_config(window):
    window._scope_buttons["l"].setChecked(True)
    assert config.getcfg("profile.install_scope") == "l"
    window._scope_buttons["u"].setChecked(True)
    assert config.getcfg("profile.install_scope") == "u"


# --- install --------------------------------------------------------------


def test_install_with_elevated_scope_runs_worker(qapp, window, monkeypatch):
    # Elevated (local-system) installs authenticate via Worker.authenticate(),
    # serviced by the window's PasswordPromptAdapter -- no longer a
    # not-yet-available stub. install_profile() itself is mocked here since
    # exercising the real sudo/authenticate round-trip is worker.py's own
    # test coverage (test_worker.py's Sudo.authenticate() prompt-seam tests).
    window._load_path(_VALID_PROFILE)
    window._scope_buttons["l"].setChecked(True)
    monkeypatch.setattr(piw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(piw, "writecfg", lambda *a, **k: None)
    ran = []

    def fake_install_profile(self, *args, **kwargs):
        ran.append(True)
        return True, None, None, None

    monkeypatch.setattr(Worker, "install_profile", fake_install_profile)
    infos = []
    monkeypatch.setattr(piw.QMessageBox, "information", lambda *a, **k: infos.append(a))

    window._install()
    assert _spin_until(qapp, lambda: window._thread is None)

    assert ran == [True]
    assert isinstance(window.worker.password_prompt, piw.PasswordPromptAdapter)


def test_install_runs_worker_and_reports_success(qapp, window, monkeypatch):
    window._load_path(_VALID_PROFILE)
    monkeypatch.setattr(piw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(piw, "writecfg", lambda *a, **k: None)
    monkeypatch.setattr(
        Worker, "install_profile", lambda self, *a, **k: (True, None, None, None)
    )
    infos = []
    monkeypatch.setattr(
        piw.QMessageBox,
        "information",
        lambda *a, **k: infos.append(window.isVisible()),
    )
    window.show()

    window._install()
    assert _spin_until(qapp, lambda: window._thread is None)

    # The result is shown while the window is still open, then it closes
    # like the wx dialog does.
    assert infos == [True]
    assert not window.isVisible()
    assert window.install_btn.isEnabled()


def test_install_reports_exception(qapp, window, monkeypatch):
    window._load_path(_VALID_PROFILE)
    monkeypatch.setattr(piw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(piw, "writecfg", lambda *a, **k: None)
    boom = RuntimeError("dispwin exploded")

    def fake_install(self, *a, **k):
        raise boom

    monkeypatch.setattr(Worker, "install_profile", fake_install)
    errors = []
    monkeypatch.setattr(piw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window.show()

    window._install()
    assert _spin_until(qapp, lambda: window._thread is None)

    assert errors
    assert "dispwin exploded" in errors[0][2]
    assert not window.isVisible()
