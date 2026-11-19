"""Tests for the macOS display profile lookup (ColorSync, then AppleScript)."""

import sys

import pytest

from DisplayCAL.icc_profile.display_profile import macos


def test_colorsync_path_comes_first(monkeypatch, data_path):
    path = str(data_path / "icc" / "BenQ SW271 #1 2021-11-17 14-21 2.2 F-S 1xCurve+MTX.icc")
    monkeypatch.setattr(macos, "colorsync_profile_path", lambda display_no: path)
    monkeypatch.setattr(
        "DisplayCAL.util_mac.osascript", lambda script: pytest.fail("no AppleScript")
    )

    assert macos.get_display_profile_macos(0, path_only=True) == path
    assert macos.get_display_profile_macos(0).filename == path


def test_applescript_when_colorsync_has_no_file(monkeypatch):
    """Image Events: what older macOS versions answered (15 no longer does)."""
    monkeypatch.setattr(macos, "colorsync_profile_path", lambda display_no: None)
    scripts = []
    monkeypatch.setattr(
        "DisplayCAL.util_mac.osascript",
        lambda script: scripts.append(script) or (0, b"/Library/x.icc\n", b""),
    )

    assert macos.get_display_profile_macos(1, path_only=True) == "/Library/x.icc"
    assert "display 2" in "\n".join(scripts[0])


def test_no_profile_anywhere_is_none(monkeypatch):
    monkeypatch.setattr(macos, "colorsync_profile_path", lambda display_no: None)
    monkeypatch.setattr("DisplayCAL.util_mac.osascript", lambda script: (0, b"", b""))

    assert macos.get_display_profile_macos(0) is None


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_colorsync_reads_the_real_display_without_crashing():
    path = macos.colorsync_profile_path(0)

    assert path is None or path.endswith((".icc", ".icm", ".ICC", ".ICM"))
    assert macos.colorsync_profile_path(99) is None  # no such display
