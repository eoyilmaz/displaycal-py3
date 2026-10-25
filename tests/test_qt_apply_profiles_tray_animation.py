"""Tests for the Qt apply-profiles tray icon's busy animation (issue #892).

wx's ``TaskBarIcon`` animates its tray icon while applying profiles
(``animate()``/``set_icons()`` in ``DisplayCAL/profile_loader.py``): 1/4/8
hue-rotated frames depending on ``profile_loader.tray_icon_animation_quality``,
stepped through on a timer. These tests exercise the Qt port's equivalent
(``ApplyProfilesTrayIcon._build_active_icons``/``animate``) directly, without
a real system tray or Argyll/display hardware.
"""

import os
from unittest import mock

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui.assets import pil_to_qpixmap, rotate_hue  # noqa: E402
from DisplayCAL.ui.tools.apply_profiles import ApplyProfilesTrayIcon  # noqa: E402


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


def _make_tray(qapp, monkeypatch):
    """Build an ``ApplyProfilesTrayIcon`` without a real ``QtProfileLoader``."""
    tray = ApplyProfilesTrayIcon.__new__(ApplyProfilesTrayIcon)
    tray._icon_index = 0
    tray._active_icons = []
    tray._build_active_icons()
    pl = mock.Mock()
    pl.monitoring = True
    pl.setgammaramp_success = {}
    pl.monitors = []
    pl._reset_gamma_ramps = False
    pl.get_title.return_value = "DisplayCAL Apply Profiles"
    tray.pl = pl
    tray._reset_icon = mock.Mock()
    tray._error_icon = mock.Mock()
    monkeypatch.setattr(tray, "setIcon", mock.Mock())
    monkeypatch.setattr(tray, "setToolTip", mock.Mock())
    return tray


@pytest.mark.parametrize("quality, expected_numframes", [(0, 1), (1, 4), (2, 8)])
def test_build_active_icons_frame_count_follows_animation_quality(
    qapp, monkeypatch, quality, expected_numframes
):
    config.setcfg("profile_loader.tray_icon_animation_quality", quality)
    tray = _make_tray(qapp, monkeypatch)
    assert len(tray._active_icons) == expected_numframes


def test_animation_toggle_rebuilds_frames(qapp, monkeypatch):
    config.setcfg("profile_loader.tray_icon_animation_quality", 0)
    tray = _make_tray(qapp, monkeypatch)
    assert len(tray._active_icons) == 1

    tray._on_animation_toggled(True)

    assert config.getcfg("profile_loader.tray_icon_animation_quality") == 2
    assert len(tray._active_icons) == 8


def test_animate_steps_through_frames_and_resets(qapp, monkeypatch):
    config.setcfg("profile_loader.tray_icon_animation_quality", 1)
    tray = _make_tray(qapp, monkeypatch)
    assert len(tray._active_icons) == 4

    with mock.patch(
        "DisplayCAL.ui.tools.apply_profiles.QTimer.singleShot"
    ) as single_shot:
        tray.animate()
        assert tray._icon_index == 1
        single_shot.assert_called_once()
        assert single_shot.call_args[0][0] == 50  # 200ms / 4 frames

        tray.animate()
        tray.animate()
        assert tray._icon_index == 3

        tray.animate()  # reaches the last frame -> resets, no reschedule
        assert tray._icon_index == 0
        assert single_shot.call_count == 3


def test_animate_is_a_noop_when_not_monitoring(qapp, monkeypatch):
    tray = _make_tray(qapp, monkeypatch)
    tray.pl.monitoring = False
    with mock.patch(
        "DisplayCAL.ui.tools.apply_profiles.QTimer.singleShot"
    ) as single_shot:
        tray.animate()
    assert tray._icon_index == 0
    single_shot.assert_not_called()


def test_set_visual_state_uses_current_animation_frame(qapp, monkeypatch):
    config.setcfg("profile_loader.tray_icon_animation_quality", 1)
    tray = _make_tray(qapp, monkeypatch)

    with mock.patch("DisplayCAL.ui.tools.apply_profiles.QTimer.singleShot"):
        tray.animate()

    tray.set_visual_state()

    tray.setIcon.assert_called_with(tray._active_icons[tray._icon_index])


def test_set_visual_state_prefers_error_icon_over_animation_frame(qapp, monkeypatch):
    tray = _make_tray(qapp, monkeypatch)
    tray.pl.setgammaramp_success = {0: False}
    tray.pl.monitors = [mock.Mock()]

    tray.set_visual_state()

    tray.setIcon.assert_called_with(tray._error_icon)


def test_rotate_hue_rotates_chromatic_pixels(qapp):
    from PIL import Image

    img = Image.new("RGBA", (1, 1), (255, 0, 0, 255))  # pure red, hue == 0

    rotated = rotate_hue(img, 1 / 3)

    pixmap = pil_to_qpixmap(rotated)
    hue, saturation, value, _ = pixmap.toImage().pixelColor(0, 0).getHsvF()
    assert hue == pytest.approx(1 / 3, abs=1 / 256)
    assert saturation == pytest.approx(1.0, abs=1e-3)
    assert value == pytest.approx(1.0, abs=1e-3)


def test_rotate_hue_skips_achromatic_pixels():
    from PIL import Image

    img = Image.new("RGBA", (1, 1), (128, 128, 128, 255))  # gray, hue undefined

    rotated = rotate_hue(img, 0.5)

    assert rotated.getpixel((0, 0)) == (128, 128, 128, 255)


def test_rotate_hue_zero_fraction_returns_equivalent_pixels():
    from PIL import Image

    img = Image.new("RGBA", (1, 1), (10, 20, 30, 255))

    rotated = rotate_hue(img, 0)

    assert rotated.getpixel((0, 0)) == (10, 20, 30, 255)
