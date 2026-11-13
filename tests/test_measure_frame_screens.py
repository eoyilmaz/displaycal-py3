"""Tests for finding the Qt screen of an Argyll display (measurement area moves there)."""

from types import SimpleNamespace

import pytest

pytest.importorskip("qtpy")

from DisplayCAL.ui.measure_frame import screen_for_argyll_display  # noqa: E402


def screen(name, x, y, w, h):
    rect = SimpleNamespace(x=lambda: x, y=lambda: y, width=lambda: w, height=lambda: h)
    return SimpleNamespace(name=lambda: name, geometry=lambda: rect)


DELL = screen("DELL S2721QS", 0, 0, 2560, 1440)  # 3840x2160 at 150 %
MI = screen("Mi Monitor", 3840, 718, 2560, 1440)


def test_matches_by_model_name_despite_scaling():
    found = screen_for_argyll_display("DELL S2721QS @ 0, 0, 3840x2160", [MI, DELL])

    assert found is DELL


def test_two_displays_of_the_same_model_are_told_apart_by_position():
    left = screen("DELL S2721QS", 0, 0, 2560, 1440)
    right = screen("DELL S2721QS", 3840, 0, 2560, 1440)

    found = screen_for_argyll_display("DELL S2721QS @ 3840, 0, 3840x2160", [left, right])

    assert found is right


def test_no_screen_for_a_virtual_display():
    assert screen_for_argyll_display("Web @ localhost", [DELL, MI]) is None
