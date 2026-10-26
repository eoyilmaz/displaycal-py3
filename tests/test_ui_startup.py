"""Tests for the Qt splash screen ``DisplayCAL.ui.startup`` (Stage 6).

``welcome_message`` / ``should_enumerate_ports`` / ``zoom_scales`` are pure
marshalling helpers lifted out of ``display_cal.StartupFrame``, tested without
a display. ``_SplashAnimator`` and ``StartupController`` are exercised
headless via the shared offscreen ``QApplication``, with a fake worker (no
Argyll / hardware needed) and short-circuited frame lists/sound so the tests
don't wait on real animation timing or touch the audio subsystem. See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 6).
"""

import os
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL.config import setcfg  # noqa: E402
from DisplayCAL.ui import startup  # noqa: E402


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


@pytest.fixture(autouse=True)
def _no_sound(monkeypatch):
    """Never touch the real audio subsystem in tests."""
    monkeypatch.setattr(startup, "play_startup_sound", lambda: None)


def _spin_until(qapp, predicate, timeout_s=30.0):
    """Pump the event loop until ``predicate`` is true or the timeout elapses."""
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


class _FakeWorker:
    def __init__(self, exception=None):
        self._exception = exception
        self.displays = []
        self.instruments = []
        self.abort_calls = 0
        self.enumerate_calls = []

    def enumerate_displays_and_ports(self, enumerate_ports=True, silent=False):
        self.enumerate_calls.append((enumerate_ports, silent))
        if self._exception is not None:
            raise self._exception
        self.displays = ["Fake @ 0, 0, 1x1 [PRIMARY]"]
        self.instruments = ["Fake Meter"]

    def abort_subprocess(self, confirm=False):
        self.abort_calls += 1


# --- pure helpers ------------------------------------------------------------


def test_welcome_message_differs_first_run_vs_returning(monkeypatch):
    monkeypatch.setattr(startup, "hascfg", lambda *a, **k: False)
    first_run = startup.welcome_message()
    monkeypatch.setattr(startup, "hascfg", lambda *a, **k: True)
    returning = startup.welcome_message()
    assert first_run and returning
    assert first_run != returning


def test_should_enumerate_ports_when_no_instruments_configured():
    setcfg("instruments", [])
    setcfg("enumerate_ports.auto", 0)
    assert startup.should_enumerate_ports()


def test_should_enumerate_ports_skips_when_forced_off(monkeypatch):
    monkeypatch.setattr(startup, "FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION", True)
    setcfg("instruments", [])
    assert not startup.should_enumerate_ports()


def test_should_enumerate_ports_respects_single_known_instrument():
    setcfg("instruments", ["Known Meter"])
    setcfg("enumerate_ports.auto", 0)
    assert not startup.should_enumerate_ports()


def test_zoom_scales_ends_at_one():
    scales = startup.zoom_scales()
    assert scales[-1] == 1.0
    assert len(scales) == 17  # 15 eased steps + 1.02 overshoot + 1.0 settle
    # Monotonically approaches 1.0 across the eased portion.
    assert scales[0] < scales[7] < scales[14]


# --- asset loading -----------------------------------------------------------


def test_splash_pixmap_loads_asset(qapp):
    pixmap = startup.splash_pixmap()
    assert not pixmap.isNull()


def test_load_anim_frames_loads_real_assets(qapp):
    frames = startup.load_anim_frames()
    assert len(frames) == 16
    assert all(not frame.isNull() for frame in frames)


def test_load_version_frames_matches_alpha_step_count(qapp):
    frames = startup.load_version_frames()
    assert len(frames) == len(startup._VERSION_ALPHAS)


# --- _SplashAnimator ---------------------------------------------------------


@pytest.fixture
def fast_animator(qapp, monkeypatch):
    """A splash animator with a couple of fake frames and no per-frame delay."""
    monkeypatch.setattr(startup, "_FRAME_INTERVAL_MS", 0)
    from qtpy.QtGui import QPixmap

    frame = QPixmap(4, 4)
    frame.fill()
    monkeypatch.setattr(startup, "load_anim_frames", lambda: [frame, frame])
    monkeypatch.setattr(startup, "load_version_frames", lambda: [frame])
    splash = startup.QSplashScreen(frame)
    animator = startup._SplashAnimator(splash, "hello")
    yield animator
    splash.close()


def test_animator_plays_all_frames_then_finishes(qapp, fast_animator):
    finished = []
    fast_animator.start(lambda: finished.append(True))
    assert _spin_until(qapp, lambda: finished)
    assert fast_animator._frame == fast_animator._total


def test_animator_finishes_immediately_with_no_frames(qapp, monkeypatch):
    monkeypatch.setattr(startup, "load_anim_frames", list)
    monkeypatch.setattr(startup, "load_version_frames", list)
    splash = startup.QSplashScreen(startup.splash_pixmap())
    animator = startup._SplashAnimator(splash, "hello")
    finished = []
    animator.start(lambda: finished.append(True))
    assert finished == [True]
    splash.close()


# --- StartupController -------------------------------------------------------


@pytest.fixture
def _fast_controller_animation(monkeypatch):
    """Skip real frame assets/timing so controller tests focus on the wiring."""
    monkeypatch.setattr(startup, "_FRAME_INTERVAL_MS", 0)
    monkeypatch.setattr(startup, "load_anim_frames", list)
    monkeypatch.setattr(startup, "load_version_frames", list)


def test_controller_enumerates_and_calls_ready(qapp, _fast_controller_animation):
    worker = _FakeWorker()
    ready = []
    controller = startup.StartupController(ready.append, worker=worker)
    try:
        controller.start()
        assert _spin_until(qapp, lambda: ready)
        assert ready == [worker]
        assert worker.displays == ["Fake @ 0, 0, 1x1 [PRIMARY]"]
    finally:
        controller.splash.close()


def test_controller_still_calls_ready_on_enumeration_error(
    qapp, _fast_controller_animation
):
    worker = _FakeWorker(exception=RuntimeError("boom"))
    ready = []
    controller = startup.StartupController(ready.append, worker=worker)
    try:
        controller.start()
        assert _spin_until(qapp, lambda: ready)
        assert ready == [worker]
    finally:
        controller.splash.close()


def test_controller_waits_for_animation_even_if_enumeration_is_instant(
    qapp, monkeypatch
):
    # A slow animation (a handful of real-interval frames) must still gate
    # readiness even though enumeration itself resolves on the next tick.
    monkeypatch.setattr(startup, "_FRAME_INTERVAL_MS", 50)
    from qtpy.QtGui import QPixmap

    frame = QPixmap(4, 4)
    frame.fill()
    monkeypatch.setattr(startup, "load_anim_frames", lambda: [frame] * 4)
    monkeypatch.setattr(startup, "load_version_frames", list)

    worker = _FakeWorker()
    ready = []
    controller = startup.StartupController(ready.append, worker=worker)
    try:
        start = time.monotonic()
        controller.start()
        assert _spin_until(qapp, lambda: ready)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms >= 100  # at least a few 50ms frame ticks elapsed
    finally:
        controller.splash.close()


def test_controller_shows_welcome_message(qapp):
    worker = _FakeWorker()
    controller = startup.StartupController(lambda w: None, worker=worker)
    try:
        assert controller.splash.pixmap().isNull() is False
    finally:
        controller.splash.close()
