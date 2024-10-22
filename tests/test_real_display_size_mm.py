# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from unittest import mock

import pytest
from _pytest.monkeypatch import MonkeyPatch

from DisplayCAL import RealDisplaySizeMM, config
from DisplayCAL.dev.mocks import check_call
from tests.data.display_data import DisplayData

try:
    from tests.data.fake_dbus import FakeDBusObject
except ImportError:
    pass


@pytest.fixture(scope="function")
def patch_subprocess_on_rdsmm(monkeypatch, patch_subprocess):
    """Patch DisplayCAL.RealDisplaySizeMM.subprocess to return whatever we want."""
    monkeypatch.setattr("DisplayCAL.RealDisplaySizeMM.subprocess", patch_subprocess)
    yield patch_subprocess


def test_real_display_size_mm(clear_displays):
    """Test RealDisplaySizeMM() function."""
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            display_size = RealDisplaySizeMM.RealDisplaySizeMM(0)
    assert display_size != (0, 0)
    assert display_size[0] > 1
    assert display_size[1] > 1


def test_xrandr_output_x_id_1(clear_displays):
    """Test GetXRandROutputXID() function."""
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            result = RealDisplaySizeMM.GetXRandROutputXID(0)
    assert result != 0


def test_enumerate_displays(clear_displays):
    """Test enumerate_displays() function."""
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        result = RealDisplaySizeMM.enumerate_displays()
    assert result[0]["description"] != ""
    assert result[0]["edid"] != ""
    assert result[0]["icc_profile_atom_id"] != ""
    assert result[0]["icc_profile_output_atom_id"] != ""
    assert result[0]["name"] != ""
    assert result[0]["output"] != ""
    assert result[0]["pos"] != ""
    assert result[0]["ramdac_screen"] != ""
    assert result[0]["screen"] != ""
    assert result[0]["size"] != ""
    assert isinstance(result[0]["size"][0], int)
    assert isinstance(result[0]["size"][1], int)
    assert result[0]["size_mm"] != ""
    assert isinstance(result[0]["size_mm"][0], int)
    assert isinstance(result[0]["size_mm"][1], int)
    assert result[0]["x11_screen"] != ""
    # assert result[0]["xrandr_name"] != ""
    assert RealDisplaySizeMM._displays is not None


def test__enumerate_displays_dispwin_path_is_none(monkeypatch, clear_displays):
    """_enumerate_displays() dispwin path is None returns empty list."""
    monkeypatch.setattr(
        "DisplayCAL.RealDisplaySizeMM.argyll.get_argyll_util", lambda x: None
    )
    result = RealDisplaySizeMM._enumerate_displays()
    assert result == []


def test__enumerate_displays_uses_argyll_dispwin(
    patch_subprocess_on_rdsmm, patch_argyll_util
):
    """_enumerate_displays() uses dispwin."""
    PatchedSubprocess = patch_subprocess_on_rdsmm
    PatchedSubprocess.output["dispwin-v-d0"] = DisplayData.DISPWIN_OUTPUT_1
    PatchedArgyll = patch_argyll_util
    assert PatchedSubprocess.passed_args == []
    assert PatchedSubprocess.passed_kwargs == {}
    result = RealDisplaySizeMM._enumerate_displays()
    # assert result == DisplayData.DISPWIN_OUTPUT_1
    assert PatchedSubprocess.passed_args != []
    assert "dispwin" in PatchedSubprocess.passed_args[0][0]
    assert PatchedSubprocess.passed_args[0][1] == "-v"
    assert PatchedSubprocess.passed_args[0][2] == "-d0"


def test__enumerate_displays_uses_argyll_dispwin_output_1(
    clear_displays, patch_subprocess_on_rdsmm, patch_argyll_util
):
    """_enumerate_displays() uses dispwin."""
    patch_subprocess_on_rdsmm.output["dispwin-v-d0"] = DisplayData.DISPWIN_OUTPUT_1
    result = RealDisplaySizeMM._enumerate_displays()
    assert isinstance(result, list)
    assert len(result) == 1
    assert (
        result[0]["description"]
        == b"Built-in Retina Display, at 0, 0, width 1728, height 1117 (Primary Display)"
    )
    assert result[0]["name"] == b"Built-in Retina Display"
    assert result[0]["size"] == (1728, 1117)
    assert result[0]["pos"] == (0, 0)


def test__enumerate_displays_uses_argyll_dispwin_output_2(
    patch_subprocess_on_rdsmm, patch_argyll_util
):
    """_enumerate_displays() uses dispwin."""
    patch_subprocess_on_rdsmm.output["dispwin-v-d0"] = DisplayData.DISPWIN_OUTPUT_2
    result = RealDisplaySizeMM._enumerate_displays()
    assert isinstance(result, list)
    assert len(result) == 2
    assert (
        result[0]["description"]
        == b"Built-in Retina Display, at 0, 0, width 1728, height 1117 (Primary Display)"
    )
    assert result[0]["name"] == b"Built-in Retina Display"
    assert result[0]["size"] == (1728, 1117)
    assert result[0]["pos"] == (0, 0)
    assert (
        result[1]["description"]
        == b"DELL U2720Q, at 1728, -575, width 3008, height 1692"
    )
    assert result[1]["name"] == b"DELL U2720Q"
    assert result[1]["size"] == (3008, 1692)
    assert result[1]["pos"] == (1728, -575)


def test__enumerate_displays_without_a_proper_dispwin_output_missing_lines(
    patch_subprocess_on_rdsmm, patch_argyll_util
):
    """_enumerate_displays() return empty list when dispwin returns no usable data."""
    patch_subprocess_on_rdsmm.output["dispwin-v-d0"] = DisplayData.DISPWIN_OUTPUT_3
    result = RealDisplaySizeMM._enumerate_displays()
    assert isinstance(result, list)
    assert len(result) == 0


def test__enumerate_displays_without_a_proper_dispwin_output_with_wrong_formatted_data(
    patch_subprocess_on_rdsmm, patch_argyll_util
):
    """_enumerate_displays() return empty list when dispwin returns no usable data."""
    from DisplayCAL import localization as lang

    lang.init()
    patch_subprocess_on_rdsmm.output["dispwin-v-d0"] = DisplayData.DISPWIN_OUTPUT_4
    with pytest.raises(ValueError) as cm:
        result = RealDisplaySizeMM._enumerate_displays()
    assert str(cm.value) == (
        "An internal error occurred.\n"
        "Error code: -1\n"
        "Error message: dispwin returns no usable data while enumerating displays."
    )


def test__enumerate_displays_without_a_proper_dispwin_output_with_partial_match(
    patch_subprocess_on_rdsmm, patch_argyll_util
):
    """_enumerate_displays() return empty list when dispwin returns no usable data."""
    from DisplayCAL import localization as lang

    lang.init()
    patch_subprocess_on_rdsmm.output["dispwin-v-d0"] = DisplayData.DISPWIN_OUTPUT_5
    with pytest.raises(ValueError) as cm:
        result = RealDisplaySizeMM._enumerate_displays()
    assert str(cm.value) == (
        "An internal error occurred.\n"
        "Error code: -1\n"
        "Error message: dispwin returns no usable data while enumerating displays."
    )


def test_get_display(clear_displays):
    """Test DisplayCAL.RealDisplaySizeMM.get_display() function."""
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            display = RealDisplaySizeMM.get_display()
    assert RealDisplaySizeMM._displays is not None
    assert isinstance(display, dict)


def test_get_x_display(clear_displays):
    """Test DisplayCAL.RealDisplaySizeMM.get_x_display() function."""
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            display = RealDisplaySizeMM.get_x_display(0)
    assert isinstance(display, tuple)
    assert len(display) == 3


@pytest.mark.parametrize(
    "function",
    (
        RealDisplaySizeMM.get_x_icc_profile_atom_id,
        RealDisplaySizeMM.get_x_icc_profile_output_atom_id,
    ),
)
def test_get_x_icc_profile_atom_id(clear_displays, function) -> None:
    """Test DisplayCAL.RealDisplaySizeMM.get_x_icc_profile_atom_id() function."""
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            result = function(0)
    assert result is not None
    assert isinstance(result, int)


@pytest.mark.skipif("fake_dbus" not in sys.modules, reason="requires the DBus library")
def test_get_wayland_display(monkeypatch: MonkeyPatch) -> None:
    """Test if wayland display is returned."""
    with mock.patch.object(RealDisplaySizeMM, "DBusObject", new=FakeDBusObject):
        display = RealDisplaySizeMM.get_wayland_display(0, 0, 0, 0)
    assert display["xrandr_name"] == "DP-2"
    assert display["size_mm"] == (597, 336)


def test_get_dispwin_output_dispwin_path_is_none_returns_empty_bytes(
    clear_displays, monkeypatch
):
    """get_dispwin_output() argyll.get_argyll_util("dispwin") returns None."""

    def patched_get_argyll_util(*args):
        return None

    monkeypatch.setattr(
        "DisplayCAL.RealDisplaySizeMM.argyll.get_argyll_util", patched_get_argyll_util
    )
    assert RealDisplaySizeMM.get_dispwin_output() == b""


def test_get_dispwin_output_returns_dispwin_output_as_bytes(
    clear_displays, data_files, patch_subprocess
):
    """get_dispwin_output() returns bytes."""
    # patch dispwin
    dispwin_data_file_name = "dispwin_output_1.txt"
    with open(data_files[dispwin_data_file_name], "rb") as dispwin_data_file:
        dispwin_data = dispwin_data_file.read()
    patch_subprocess.output["dispwin-v-d0"] = dispwin_data
    assert isinstance(RealDisplaySizeMM.get_dispwin_output(), bytes)
