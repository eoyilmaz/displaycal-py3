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


def test_real_display_size_mm():
    """Test DisplayCAL.RealDisplaySizeMM.RealDisplaySizeMM() function."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            display_size = RealDisplaySizeMM.RealDisplaySizeMM(0)
    assert display_size != (0, 0)
    assert display_size[0] > 1
    assert display_size[1] > 1


def test_xrandr_output_x_id_1():
    """Test DisplayCAL.RealDisplaySizeMM.GetXRandROutputXID() function."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            result = RealDisplaySizeMM.GetXRandROutputXID(0)
    assert result != 0


def test_enumerate_displays():
    """Test DisplayCAL.RealDisplaySizeMM.enumerate_displays() function."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
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
    assert result[0]["xrandr_name"] != ""
    assert RealDisplaySizeMM._displays is not None


def test_get_display():
    """Test DisplayCAL.RealDisplaySizeMM.get_display() function."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            display = RealDisplaySizeMM.get_display()
    assert RealDisplaySizeMM._displays is not None
    assert isinstance(display, dict)


def test_get_x_display():
    """Test DisplayCAL.RealDisplaySizeMM.get_x_display() function."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
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
def test_get_x_icc_profile_atom_id(function) -> None:
    """Test DisplayCAL.RealDisplaySizeMM.get_x_icc_profile_atom_id() function."""
    RealDisplaySizeMM._displays = None
    assert RealDisplaySizeMM._displays is None
    with check_call(
        RealDisplaySizeMM, "_enumerate_displays", DisplayData.enumerate_displays()
    ):
        with check_call(config, "getcfg", DisplayData.CFG_DATA, call_count=2):
            result = function(0)
    assert result is not None
    assert isinstance(result, int)


@pytest.mark.skipif('fake_dbus' not in sys.modules,
                    reason="requires the DBus library")
def test_get_wayland_display(monkeypatch: MonkeyPatch) -> None:
    """Test if wayland display is returned."""
    with mock.patch.object(RealDisplaySizeMM, "DBusObject", new=FakeDBusObject):
        display = RealDisplaySizeMM.get_wayland_display(0, 0, 0, 0)
    assert display["xrandr_name"] == "DP-2"
    assert display["size_mm"] == (597, 336)
