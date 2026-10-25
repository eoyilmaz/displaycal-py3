"""Tests for the direct-CoreGraphics macOS VideoLUT reload path (issue #824).

Argyll's ``dispwin`` has to exit after every invocation, and macOS's own
cleanup of a just-exited process's transient VideoLUT claim can clobber a
*different*, untouched display's gamma table. These helpers apply
calibration directly via CoreGraphics from DisplayCAL's own long-lived
process instead, avoiding that OS bug entirely (see
DisplayCAL.worker.reload_macos_videoluts and
DisplayCAL.profile_loader.ProfileLoader._reload_clobbered_displays).
"""

from unittest import mock

from DisplayCAL.worker import (
    _get_macos_display_profile,
    get_macos_display_identity,
    reload_macos_videoluts,
    vcgt_values_to_videolut,
)


def test_get_macos_display_profile_prefers_coregraphics_over_applescript():
    """CoreGraphics profile data is used without falling back to AppleScript.

    ``get_display_profile`` queries the "Image Events" AppleScript scripting
    interface, which is confirmed broken on current macOS (Tahoe). The
    CoreGraphics-native path must be tried first and, when it succeeds, must
    not fall back at all.
    """
    sentinel_profile = mock.Mock()
    with (
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data",
            return_value=b"fake-icc-bytes",
        ),
        mock.patch(
            "DisplayCAL.worker.ICCProfile", return_value=sentinel_profile
        ) as mock_icc_profile,
        mock.patch("DisplayCAL.worker.get_display_profile") as mock_applescript,
    ):
        profile = _get_macos_display_profile(0)
    assert profile is sentinel_profile
    mock_icc_profile.assert_called_once_with(b"fake-icc-bytes")
    mock_applescript.assert_not_called()


def test_get_macos_display_profile_falls_back_when_coregraphics_has_no_data():
    """No CoreGraphics profile data falls back to the AppleScript path."""
    sentinel_profile = mock.Mock()
    with (
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data", return_value=None
        ),
        mock.patch(
            "DisplayCAL.worker.get_display_profile", return_value=sentinel_profile
        ),
    ):
        profile = _get_macos_display_profile(0)
    assert profile is sentinel_profile


def test_get_macos_display_profile_falls_back_on_unparseable_data():
    """Data CoreGraphics returns that fails to parse also falls back."""
    sentinel_profile = mock.Mock()
    with (
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data",
            return_value=b"not-a-valid-icc-profile",
        ),
        mock.patch(
            "DisplayCAL.worker.ICCProfile", side_effect=ValueError("bad profile")
        ),
        mock.patch(
            "DisplayCAL.worker.get_display_profile", return_value=sentinel_profile
        ),
    ):
        profile = _get_macos_display_profile(0)
    assert profile is sentinel_profile


def test_vcgt_values_to_videolut_identity_same_size():
    """A 256-entry linear vcgt interpolated to 256 entries is unchanged."""
    points = [[i, round(i / 255.0 * 65535)] for i in range(256)]
    out = vcgt_values_to_videolut(points, 256)
    assert len(out) == 256
    assert out[0] == 0.0
    assert abs(out[-1] - 1.0) < 1e-9
    assert abs(out[128] - points[128][1] / 65535.0) < 1e-6


def test_vcgt_values_to_videolut_interpolates_to_different_size():
    """Interpolating a 256-entry table to a smaller VideoLUT stays monotonic."""
    points = [[i, round(i / 255.0 * 65535)] for i in range(256)]
    out = vcgt_values_to_videolut(points, 4)
    assert len(out) == 4
    assert out[0] == 0.0
    assert abs(out[-1] - 1.0) < 1e-9
    assert out == sorted(out)


def test_vcgt_values_to_videolut_handles_degenerate_input():
    """A single-point or empty input doesn't crash and returns a flat table."""
    assert vcgt_values_to_videolut([[0, 32768]], 8) == [32768 / 65535.0] * 8
    assert vcgt_values_to_videolut([], 4) == [1.0] * 4


def _fake_vcgt(r_points, g_points, b_points):
    vcgt = mock.Mock()
    vcgt.get_values.return_value = (r_points, g_points, b_points, [])
    return vcgt


def test_reload_macos_videoluts_applies_profile_vcgt():
    """A clobbered display's profile vcgt is interpolated and applied."""
    r_points = [[i, round(i / 255.0 * 65535)] for i in range(256)]
    g_points = [[i, round(i / 255.0 * 65535)] for i in range(256)]
    b_points = [[i, round(i / 255.0 * 65535)] for i in range(256)]
    profile = mock.Mock()
    profile.tags = {"vcgt": _fake_vcgt(r_points, g_points, b_points)}

    set_calls = []

    def fake_set(display_index, red, green, blue):
        set_calls.append((display_index, len(red), len(green), len(blue)))
        return True

    with (
        mock.patch("DisplayCAL.worker.get_macos_videolut_capacity", return_value=64),
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data", return_value=None
        ),
        mock.patch("DisplayCAL.worker.get_display_profile", return_value=profile),
        mock.patch("DisplayCAL.worker.set_macos_videolut", side_effect=fake_set),
    ):
        reloaded = reload_macos_videoluts([0])
    assert reloaded == [0]
    assert set_calls == [(0, 64, 64, 64)]


def test_reload_macos_videoluts_falls_back_to_linear_without_vcgt():
    """A profile without a vcgt tag gets a linear ramp instead of failing."""
    profile = mock.Mock()
    profile.tags = {}

    set_calls = []

    def fake_set(display_index, red, green, blue):
        set_calls.append((display_index, red, green, blue))
        return True

    with (
        mock.patch("DisplayCAL.worker.get_macos_videolut_capacity", return_value=4),
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data", return_value=None
        ),
        mock.patch("DisplayCAL.worker.get_display_profile", return_value=profile),
        mock.patch("DisplayCAL.worker.set_macos_videolut", side_effect=fake_set),
    ):
        reloaded = reload_macos_videoluts([0])
    assert reloaded == [0]
    _, red, green, blue = set_calls[0]
    assert red == green == blue == [0.0, 1 / 3, 2 / 3, 1.0]


def test_reload_macos_videoluts_skips_display_without_capacity():
    """A display whose VideoLUT capacity can't be read is left alone."""
    with (
        mock.patch("DisplayCAL.worker.get_macos_videolut_capacity", return_value=None),
        mock.patch("DisplayCAL.worker.set_macos_videolut") as mock_set,
    ):
        reloaded = reload_macos_videoluts([0])
    assert reloaded == []
    mock_set.assert_not_called()


def test_reload_macos_videoluts_reports_set_failure():
    """A display that fails to apply the table is not reported as reloaded."""
    profile = mock.Mock()
    profile.tags = {}
    logged = []
    with (
        mock.patch("DisplayCAL.worker.get_macos_videolut_capacity", return_value=4),
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data", return_value=None
        ),
        mock.patch("DisplayCAL.worker.get_display_profile", return_value=profile),
        mock.patch("DisplayCAL.worker.set_macos_videolut", return_value=False),
    ):
        reloaded = reload_macos_videoluts([0], log=logged.append)
    assert reloaded == []
    assert logged and "display 1" in logged[0]


def test_reload_macos_videoluts_applies_all_displays_in_one_call():
    """Multiple clobbered displays are all reloaded from this single call."""
    profile = mock.Mock()
    profile.tags = {}
    set_calls = []

    def fake_set(display_index, red, green, blue):
        set_calls.append(display_index)
        return True

    with (
        mock.patch("DisplayCAL.worker.get_macos_videolut_capacity", return_value=4),
        mock.patch(
            "DisplayCAL.worker.get_macos_display_profile_data", return_value=None
        ),
        mock.patch("DisplayCAL.worker.get_display_profile", return_value=profile),
        mock.patch("DisplayCAL.worker.set_macos_videolut", side_effect=fake_set),
    ):
        reloaded = reload_macos_videoluts([0, 1])
    assert reloaded == [0, 1]
    assert set_calls == [0, 1]


def test_get_macos_display_identity():
    """The CoreGraphics id and vendor/product numbers are returned by index."""
    cg = mock.Mock()
    cg.CGDisplayVendorNumber.side_effect = {2: 0x09D1, 3: 0x1E6D}.get
    cg.CGDisplayModelNumber.side_effect = {2: 0x8048, 3: 0x5CBB}.get
    with mock.patch(
        "DisplayCAL.worker._macos_active_display_ids", return_value=(cg, [2, 3])
    ):
        assert get_macos_display_identity(0) == (2, 0x09D1, 0x8048)
        assert get_macos_display_identity(1) == (3, 0x1E6D, 0x5CBB)
        assert get_macos_display_identity(2) is None


def test_get_macos_display_identity_without_coregraphics():
    """None is returned when CoreGraphics is unavailable."""
    with mock.patch(
        "DisplayCAL.worker._macos_active_display_ids", return_value=(None, [])
    ):
        assert get_macos_display_identity(0) is None
