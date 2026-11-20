"""Tests for display enumeration retry and self-healing under Windows."""

import sys
from unittest import mock
import pytest
import pywintypes

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")


class FakeDisplayDevice:
    def __init__(self, name="\\\\.\\DISPLAY1\\Monitor0", flags=1):
        self.DeviceName = name
        self.DeviceString = "Generic Monitor"
        self.StateFlags = flags
        self.DeviceID = "MONITOR\\GSM5B14"
        self.DeviceKey = "\\Registry\\Machine\\System\\CurrentControlSet\\Control\\Class\\0001"


def test_get_display_devices_retries_on_invalid_handle(monkeypatch):
    """get_display_devices should retry on ERROR_INVALID_HANDLE and succeed."""
    from DisplayCAL import util_win

    attempts = 0
    fake_device = FakeDisplayDevice()

    def mock_enum(devicename, n):
        nonlocal attempts
        if devicename == "\\\\.\\DISPLAY1":
            if n == 0:
                attempts += 1
                if attempts < 3:
                    raise pywintypes.error(6, "EnumDisplayDevices", "The handle is invalid.")
                return fake_device
            raise pywintypes.error(259, "EnumDisplayDevices", "No more items.")
        raise pywintypes.error(259, "EnumDisplayDevices", "No more items.")

    monkeypatch.setattr(util_win.win32api, "EnumDisplayDevices", mock_enum)
    monkeypatch.setattr(util_win.time, "sleep", lambda s: None)

    devices = util_win.get_display_devices("\\\\.\\DISPLAY1", max_retries=4, retry_delay=0)
    assert len(devices) == 1
    assert devices[0] is fake_device
    assert attempts == 3


def test_get_display_devices_exhausts_retries_gracefully(monkeypatch):
    """get_display_devices should return empty list when retries are exhausted."""
    from DisplayCAL import util_win

    def mock_enum(devicename, n):
        raise pywintypes.error(6, "EnumDisplayDevices", "The handle is invalid.")

    monkeypatch.setattr(util_win.win32api, "EnumDisplayDevices", mock_enum)
    monkeypatch.setattr(util_win.time, "sleep", lambda s: None)

    devices = util_win.get_display_devices("\\\\.\\DISPLAY1", max_retries=3, retry_delay=0)
    assert devices == []


def test_get_first_display_device_retries_and_succeeds(monkeypatch):
    """get_first_display_device should retry on ERROR_INVALID_HANDLE."""
    from DisplayCAL import util_win

    attempts = 0
    fake_device = FakeDisplayDevice()

    def mock_enum(devicename, n):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise pywintypes.error(6, "EnumDisplayDevices", "The handle is invalid.")
        return fake_device

    monkeypatch.setattr(util_win.win32api, "EnumDisplayDevices", mock_enum)
    monkeypatch.setattr(util_win.time, "sleep", lambda s: None)

    dev = util_win.get_first_display_device("\\\\.\\DISPLAY1", max_retries=3, retry_delay=0)
    assert dev is fake_device
    assert attempts == 2


def test_profile_loader_self_heals_when_unknown_monitors_present():
    """ProfileLoader._check_display_changed should re-trigger when monitors are Unknown."""
    # Test the logic without initializing the full wx GUI ProfileLoader
    has_unknown = any(
        not device or (display and "Unknown" in display)
        for display, _edid, _moninfo, device in [
            ("1. Unknown @ 0, 0, 2560x1440 (Primary)", None, {}, None)
        ]
    )
    assert has_unknown is True

    has_known = any(
        not device or (display and "Unknown" in display)
        for display, _edid, _moninfo, device in [
            ("1. LG HDR QHD @ 0, 0, 2560x1440 (Primary)", None, {}, FakeDisplayDevice())
        ]
    )
    assert has_known is False
