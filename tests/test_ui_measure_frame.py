"""Tests for the toolkit-neutral geometry maths in ``DisplayCAL.ui.measure_frame``.

These cover the relative<->pixel conversions extracted from the wx
``MeasureFrame`` (``place_n_zoom`` / ``get_dimensions`` / ``get_default_size``).
They need no display or ``QApplication`` — the functions are pure and take the
display geometry as plain tuples (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``,
Stage 1).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

from DisplayCAL.ui.measure_frame import (  # noqa: E402
    MeasureFrame,
    compute_dimensions,
    compute_frame_geometry,
    default_measureframe_size,
)

# A typical 1920x1080 display with a 40px-high panel/taskbar reserved.
DISPLAY = (0, 0, 1920, 1080)
CLIENT = (0, 0, 1920, 1040)
DEFAULT_SIZE = 300.0


def test_default_measureframe_size_uses_larger_axis():
    """The default patch uses the axis with the highest pixel density."""
    # 1920 / 510 mm ~= 3.76 px/mm is the denser axis here.
    result = default_measureframe_size((1920, 1080), (510.0, 287.0))
    assert result == round(MEASUREFRAME_DEFAULT_SIZE_FACTOR * 100.0 * 1920 / 510.0)


def test_compute_frame_geometry_centered():
    """A centred unit-scale patch lands centred at the default pixel size."""
    side, pos, scale = compute_frame_geometry(
        0.5, 0.5, 1.0, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    assert side == 300
    # (1920 - 300) * 0.5 = 810 ; (1080 - 300) * 0.5 - 25 titlebar = 365
    assert pos == (810, 365)
    assert scale == 1.0


def test_compute_frame_geometry_clamps_to_min_size():
    """A tiny scale is floored to the control-fitting minimum square."""
    side, _pos, _scale = compute_frame_geometry(
        0.5, 0.5, 0.1, DISPLAY, CLIENT, DEFAULT_SIZE, 150, 0
    )
    assert side == 150


def test_compute_frame_geometry_fullscreen_forces_scale_50():
    """A patch as large as the display reports Argyll's maximum scale of 50."""
    _side, _pos, scale = compute_frame_geometry(
        0.5, 0.5, 50.0, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    assert scale == 50


def test_compute_frame_geometry_position_never_below_client_origin():
    """The top-left is clamped to the usable client origin."""
    client = (0, 50, 1920, 990)
    _side, pos, _scale = compute_frame_geometry(
        0.0, 0.0, 1.0, DISPLAY, client, DEFAULT_SIZE, 120, 25
    )
    assert pos[0] >= client[0]
    assert pos[1] >= client[1]


def test_compute_dimensions_roundtrips_center():
    """A centred pixel geometry maps back to ``0.5,0.5,scale``."""
    side, pos, _scale = compute_frame_geometry(
        0.5, 0.5, 1.0, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    dims = compute_dimensions((side, side), pos, DISPLAY, CLIENT, DEFAULT_SIZE, 25)
    assert dims == "0.5,0.5,1.0"


@pytest.mark.parametrize(
    "x,y,scale", [(0.5, 0.5, 1.0), (0.25, 0.75, 2.0), (0.0, 0.0, 1.5)]
)
def test_place_then_dimensions_roundtrip(x, y, scale):
    """Placing then reading back reproduces the original coordinates."""
    side, pos, saved_scale = compute_frame_geometry(
        x, y, scale, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    dims = compute_dimensions((side, side), pos, DISPLAY, CLIENT, DEFAULT_SIZE, 25)
    got_x, got_y, got_scale = (float(v) for v in dims.split(","))
    assert got_x == pytest.approx(x, abs=1e-3)
    assert got_y == pytest.approx(y, abs=1e-3)
    assert got_scale == pytest.approx(saved_scale, abs=1e-3)


def test_compute_dimensions_detects_fullscreen():
    """A near-display-sized patch is reported as fullscreen (scale 50, centred)."""
    dims = compute_dimensions((1920, 1040), (0, 0), DISPLAY, CLIENT, DEFAULT_SIZE, 25)
    assert dims == "0.5,0.5,50.0"


# --- widget lifecycle: geometry persistence across the show/hide cycle -----
#
# ``MainWindow`` keeps a single ``MeasureFrame`` alive for the whole session
# and hides (rather than closes) it between the interactive-placement step and
# the actual measurement. wx's ``MeasureFrame.Show(False)`` saves the current
# geometry to config every time; without the equivalent here, a position/size
# the user picked by dragging or resizing the window (as opposed to using the
# zoom buttons, which already save via ``place_n_zoom``) is silently discarded
# and ``dispread`` draws its patch wherever the frame was last placed instead
# of where the user actually left it.

pytest.importorskip("qtpy")

from DisplayCAL import config as _config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.config import MEASUREFRAME_DEFAULT_SIZE_FACTOR, getcfg, setcfg  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init():
    """Config + localization must be live for the widget to build its labels."""
    _config.initcfg()
    lang.init()
    yield


def test_hide_persists_current_geometry(qapp):
    frame = MeasureFrame()
    try:
        frame.show()
        frame.setFixedSize(321, 321)
        frame.move(10, 20)
        expected = frame.get_dimensions()
        # A sentinel clearly different from whatever get_dimensions() reads,
        # so the assertion below can only pass if hideEvent actually ran.
        setcfg("dimensions.measureframe", "0,0,1")

        frame.hide()

        assert getcfg("dimensions.measureframe") == expected
    finally:
        frame.deleteLater()


def test_show_reapplies_stored_dimensions_every_time(qapp):
    frame = MeasureFrame()
    try:
        setcfg("dimensions.measureframe", "0.5,0.5,1.0")
        frame.show()
        first_size = frame.size()
        frame.hide()

        # Something else (e.g. a previous show/hide cycle) changes config
        # while the frame is hidden ...
        setcfg("dimensions.measureframe", "0.5,0.5,2.0")

        # ... showing again must pick up the new geometry, not just keep
        # whatever the window happened to have from its first show.
        frame.show()

        assert frame.size() != first_size
    finally:
        frame.deleteLater()


# --- closing directly (X button / Esc) instead of pressing Measure ---------
#
# Regression coverage for the "closing the Measurement Area frame leaves the
# app dead" bug: MainWindow.hide()s itself before presenting this frame, so
# nothing ever brought it back if the user closed the frame instead of
# clicking Measure. MeasureFrame itself stays toolkit/owner-neutral -- it only
# exposes a close_guard veto hook and a frame_closed notification signal, the
# owner (MainWindow) decides what either of those actually do.


def test_close_without_guard_hides_and_emits_frame_closed(qapp):
    """With no owner installed, closing behaves like a plain window close."""
    frame = MeasureFrame()
    try:
        frame.show()
        received = []
        frame.frame_closed.connect(lambda: received.append(True))

        frame.close()

        assert received == [True]
        assert not frame.isVisible()
    finally:
        frame.deleteLater()


def test_close_guard_veto_keeps_frame_open_and_suppresses_signal(qapp):
    """A close_guard returning False vetoes the close entirely."""
    frame = MeasureFrame()
    try:
        frame.show()
        frame.close_guard = lambda: False
        received = []
        frame.frame_closed.connect(lambda: received.append(True))

        frame.close()

        assert received == []
        assert frame.isVisible()
    finally:
        frame.deleteLater()


def test_close_guard_allow_closes_and_emits_frame_closed(qapp):
    """A close_guard returning True lets the close proceed as normal."""
    frame = MeasureFrame()
    try:
        frame.show()
        frame.close_guard = lambda: True
        received = []
        frame.frame_closed.connect(lambda: received.append(True))

        frame.close()

        assert received == [True]
        assert not frame.isVisible()
    finally:
        frame.deleteLater()


def test_main_writes_config_on_exit(monkeypatch):
    """The standalone frame writes the config before exiting.

    The parent process reloads it from disk to pick up the chosen geometry.
    """
    from unittest.mock import MagicMock

    from DisplayCAL.ui import measure_frame as mf

    writecfg = MagicMock()
    monkeypatch.setattr(mf.config, "initcfg", MagicMock())
    monkeypatch.setattr(mf.config, "writecfg", writecfg)
    monkeypatch.setattr(mf, "Application", MagicMock())
    monkeypatch.setattr(mf, "Worker", MagicMock())
    monkeypatch.setattr(mf, "MeasureFrame", MagicMock(exitcode=1))

    assert mf.main() == 0
    writecfg.assert_called_once_with()


def test_default_measureframe_size_is_factor_times_100mm():
    """The default patch size is MEASUREFRAME_DEFAULT_SIZE_FACTOR x 100 mm."""
    from DisplayCAL.ui.measure_frame import default_measureframe_size

    # 100 mm at 2560 px / 600 mm density, scaled by the default size factor
    assert default_measureframe_size((2560, 1440), (600.0, 340.0)) == 640


def test_default_size_uses_display_physical_size(qapp, monkeypatch):
    """The 100 mm default comes from the display's own physical size."""
    from DisplayCAL.ui import measure_frame

    monkeypatch.setattr(
        measure_frame,
        "resolve_screen_size_mm",
        lambda screen, geometry: [600.0, 340.0],
    )
    frame = MeasureFrame()
    try:
        geo = frame._current_screen().geometry()
        expected = float(
            measure_frame.default_measureframe_size(
                (geo.width(), geo.height()), [600.0, 340.0]
            )
        )
        assert frame._default_measureframe_size() == expected
    finally:
        frame.deleteLater()
