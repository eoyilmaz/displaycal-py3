"""Tests for the Qt port of the apply-profiles hot-plug monitoring thread (issue #891).

``QtProfileLoader`` inherits
:meth:`DisplayCAL.profile_loader.ProfileLoader._check_display_conf` (the
Windows display/process hot-plug poller) unchanged; only the toolkit hooks it
calls to touch UI state from its background thread
(``_post_to_gui_thread``/``_post_to_gui_thread_delayed``,
``_animate_busy_icon``, ``_enumerate_own_top_level_windows``,
``_request_forced_shutdown``) are overridden here, plus ``exit()``'s
confirmation gate. These tests exercise those seams directly rather than the
inherited Windows-only polling logic itself (which needs a real win32
environment to run meaningfully and is unchanged/already covered by the wx
build's production usage).
"""

import os
from unittest import mock

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtWidgets import QDialog, QWidget  # noqa: E402

from DisplayCAL.ui.tools.apply_profiles import (  # noqa: E402
    QtProfileLoader,
    _CallBridge,
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


def _make_pl(monkeypatch):
    """Build a ``QtProfileLoader`` without running ``__init__``'s Qt bootstrap."""
    pl = QtProfileLoader.__new__(QtProfileLoader)
    monkeypatch.setattr(pl, "get_title", lambda: "DisplayCAL Apply Profiles")
    return pl


class _FakeApp:
    def __init__(self):
        self.quit_calls = 0

    def quit(self):
        self.quit_calls += 1


def test_enumerate_own_top_level_windows_excludes_dialogs(qapp, monkeypatch):
    pl = _make_pl(monkeypatch)
    widget = QWidget()
    dialog = QDialog()
    try:
        windows = pl._enumerate_own_top_level_windows()
        assert widget in windows
        assert dialog not in windows
    finally:
        widget.deleteLater()
        dialog.deleteLater()
        qapp.processEvents()


def test_post_to_gui_thread_runs_the_callable(qapp, monkeypatch):
    pl = _make_pl(monkeypatch)
    pl._call_bridge = _CallBridge()
    pl._call_bridge.requested.connect(pl._dispatch_call)

    calls = []
    pl._post_to_gui_thread(calls.append, "from-background")
    # A direct (non-queued) connection above runs synchronously; assert the
    # callable is actually invoked with the given args rather than swallowed.
    assert calls == ["from-background"]


def test_post_to_gui_thread_delayed_schedules_with_qtimer(qapp, monkeypatch):
    pl = _make_pl(monkeypatch)
    pl._call_bridge = _CallBridge()
    pl._call_bridge.requested.connect(pl._dispatch_call)

    with mock.patch(
        "DisplayCAL.ui.tools.apply_profiles.QTimer.singleShot"
    ) as single_shot:
        pl._post_to_gui_thread_delayed(1000, lambda: None)
    assert single_shot.call_count == 1
    assert single_shot.call_args[0][0] == 1000


def test_animate_busy_icon_steps_the_tray_animation(qapp, monkeypatch):
    pl = _make_pl(monkeypatch)
    pl.tray = mock.Mock()
    pl._animate_busy_icon()
    pl.tray.animate.assert_called_once_with()


def test_animate_busy_icon_without_a_tray_is_a_noop(qapp, monkeypatch):
    pl = _make_pl(monkeypatch)
    pl.tray = None
    assert pl._animate_busy_icon() is None


def test_request_forced_shutdown_quits_without_confirmation(qapp, monkeypatch):
    pl = _make_pl(monkeypatch)
    fake_app = _FakeApp()
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    pl._request_forced_shutdown()
    assert fake_app.quit_calls == 1


def test_exit_with_no_event_skips_confirmation(qapp, monkeypatch):
    """Automated callers (oneshot exit, fatal error) pass no event -- must not block on a prompt."""
    pl = _make_pl(monkeypatch)
    fake_app = _FakeApp()
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.calibration_management_isenabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    question = mock.Mock(side_effect=AssertionError("should not prompt"))
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QMessageBox.question", question
    )

    pl.exit()

    question.assert_not_called()
    assert fake_app.quit_calls == 1


def test_exit_from_tray_menu_confirms_and_quits_on_yes(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox

    pl = _make_pl(monkeypatch)
    fake_app = _FakeApp()
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.calibration_management_isenabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )

    # Qt's QAction.triggered(bool) passes checked=False, not None.
    pl.exit(False)

    assert fake_app.quit_calls == 1


def test_exit_from_tray_menu_cancelled_does_not_quit(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox

    pl = _make_pl(monkeypatch)
    fake_app = _FakeApp()
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.calibration_management_isenabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QApplication.instance",
        staticmethod(lambda: fake_app),
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )

    pl.exit(False)

    assert fake_app.quit_calls == 0


def test_setup_ui_starts_hotplug_thread_on_windows(qapp, monkeypatch):
    monkeypatch.setattr("DisplayCAL.ui.tools.apply_profiles.sys.platform", "win32")
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QSystemTrayIcon.isSystemTrayAvailable",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles._ScriptingHost",
        lambda pl: mock.Mock(),
    )
    started = {}

    class _FakeThread:
        def __init__(self, target=None, name=None):
            started["target"] = target
            started["name"] = name

        def start(self):
            started["started"] = True

    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.threading.Thread", _FakeThread
    )
    windll = mock.Mock()
    monkeypatch.setattr(
        "DisplayCAL.profile_loader.ctypes.windll", windll, raising=False
    )

    pl = _make_pl(monkeypatch)
    pl._skip = False

    pl._setup_ui()

    assert started == {
        "target": pl._check_display_conf_wrapper,
        "name": "DisplayConfigurationMonitoring",
        "started": True,
    }
    assert pl._pid == os.getpid()
    # Inherited apply_profiles()/_check_display_conf() need gdi32 for the
    # gamma ramps (AttributeError on QtProfileLoader missing gdi32).
    assert pl.gdi32 is windll.gdi32


def test_setup_ui_notifies_when_gdi32_fails_to_load(qapp, monkeypatch):
    monkeypatch.setattr("DisplayCAL.ui.tools.apply_profiles.sys.platform", "win32")
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QSystemTrayIcon.isSystemTrayAvailable",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles._ScriptingHost",
        lambda pl: mock.Mock(),
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.threading.Thread",
        lambda *a, **k: mock.Mock(),
    )

    class _BrokenWindll:
        @property
        def gdi32(self):
            raise OSError("gdi32 not found")

    monkeypatch.setattr(
        "DisplayCAL.profile_loader.ctypes.windll", _BrokenWindll(), raising=False
    )

    pl = _make_pl(monkeypatch)
    pl._skip = False
    monkeypatch.setattr(pl, "notify", mock.Mock())

    pl._setup_ui()

    assert pl.gdi32 is None
    pl.notify.assert_called_once_with([], ["gdi32 not found"], show_notification=True)


def test_setup_ui_does_not_start_hotplug_thread_off_windows(qapp, monkeypatch):
    monkeypatch.setattr("DisplayCAL.ui.tools.apply_profiles.sys.platform", "linux")
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.QSystemTrayIcon.isSystemTrayAvailable",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles._ScriptingHost",
        lambda pl: mock.Mock(),
    )
    threads = []
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.apply_profiles.threading.Thread",
        lambda *a, **k: threads.append((a, k)) or mock.Mock(),
    )

    pl = _make_pl(monkeypatch)
    pl._skip = False
    config.setcfg("profile_loader.macos_reapply_watch", 0)

    pl._setup_ui()

    assert threads == []
    assert not hasattr(pl, "_pid")
