"""ArgyllCMS doesn't probe the Mac's Bluetooth incoming port for instruments.

Every Mac has /dev/cu.Bluetooth-Incoming-Port and no instrument is ever on
it, but ArgyllCMS opens and closes it while looking for instruments: closing
it blocks for about 11 s. On a MacBook (M1, macOS 15.7) that made
DisplayCAL's start 13.6 s instead of 2.6, and every ArgyllCMS run of a
calibration wait 12 s before connecting to the i1Display3 instead of 1.1.
"""

import pytest

from DisplayCAL import main, util_mac


def test_the_bluetooth_incoming_port_is_left_out_of_the_scan():
    environ = {}

    util_mac.skip_bluetooth_serial_scan(environ)

    assert environ == {"ARGYLL_EXCLUDE_SERIAL_SCAN": "/dev/cu.Bluetooth-Incoming-Port"}


def test_a_users_own_exclusion_stays():
    environ = {"ARGYLL_EXCLUDE_SERIAL_SCAN": "/dev/cu.usbserial-1"}

    util_mac.skip_bluetooth_serial_scan(environ)

    assert environ == {"ARGYLL_EXCLUDE_SERIAL_SCAN": "/dev/cu.usbserial-1"}


@pytest.mark.parametrize("platform, expected", [("darwin", 1), ("win32", 0)])
def test_displaycal_does_it_when_it_starts_on_a_mac(monkeypatch, platform, expected):
    calls = []
    monkeypatch.setattr(main.sys, "platform", platform)
    monkeypatch.setattr(
        util_mac, "skip_bluetooth_serial_scan", lambda *a: calls.append(a)
    )
    monkeypatch.setattr(main.mp, "freeze_support", lambda: None)
    monkeypatch.setattr(main, "_main", lambda *a: None)

    main.main()

    assert len(calls) == expected
