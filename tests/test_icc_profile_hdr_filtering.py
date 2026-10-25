"""Tests for issue #627: Profile loader must not apply HDR calibration profile in SDR mode.

The Windows HDR Calibration app stores its profile under the ICMProfileAC
registry value.  When the display is in SDR mode that value must be ignored so
the correct SDR profile (ICMProfile) is used instead.
"""

import os
import types
from unittest import mock

import pytest

from DisplayCAL.icc_profile.display_profile import windows as _icc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_winreg(registry_values):
    """Return a minimal fake winreg module seeded with the given values.

    registry_values: sequence of (name, value, type_) tuples as EnumValue
        would return.
    """
    m = types.ModuleType("winreg")
    m.HKEY_CURRENT_USER = 0x80000001
    m.HKEY_LOCAL_MACHINE = 0x80000002
    m.REG_BINARY = 3
    m.REG_MULTI_SZ = 7

    fake_key = mock.MagicMock()
    m.OpenKey = mock.Mock(return_value=fake_key)
    m.CloseKey = mock.Mock()
    m.QueryInfoKey = mock.Mock(return_value=(0, len(registry_values), 0))
    m.EnumValue = mock.Mock(side_effect=lambda key, i: registry_values[i])
    return m


@pytest.fixture()
def registry_with_both_profiles(tmp_path):
    """Inject a fake winreg with both ICMProfile and ICMProfileAC into icc_profile."""
    sdr_file = tmp_path / "sdr_profile.icm"
    hdr_file = tmp_path / "windows_hdr_calibration.icm"
    sdr_file.write_bytes(b"")
    hdr_file.write_bytes(b"")

    registry_values = [
        ("ICMProfile", [sdr_file.name], 7),
        ("ICMProfileAC", [hdr_file.name], 7),
    ]
    fake_winreg = _make_fake_winreg(registry_values)

    orig_winreg = getattr(_icc, "winreg", None)
    orig_profiles = _icc.ICCPROFILES

    _icc.winreg = fake_winreg
    _icc.ICCPROFILES = [str(tmp_path)]

    yield _icc, sdr_file.name, hdr_file.name

    if orig_winreg is None:
        if hasattr(_icc, "winreg"):
            del _icc.winreg
    else:
        _icc.winreg = orig_winreg
    _icc.ICCPROFILES = orig_profiles


# Monkey-key that represents the last two components of a typical device key.
_MONKEY = ["{4d36e96e-e325-11ce-bfc1-08002be10318}", "0002"]


# ---------------------------------------------------------------------------
# _winreg_get_display_profiles
# ---------------------------------------------------------------------------


class TestWinregGetDisplayProfiles:
    def test_returns_both_profiles_by_default(self, registry_with_both_profiles):
        """Both ICMProfile and ICMProfileAC are returned when filtering is off."""
        icc, sdr, hdr = registry_with_both_profiles
        profiles = icc._winreg_get_display_profiles(_MONKEY)
        assert sdr in profiles
        assert hdr in profiles

    def test_exclude_advanced_color_removes_hdr_entry(
        self, registry_with_both_profiles
    ):
        """With exclude_advanced_color=True, ICMProfileAC entries are dropped."""
        icc, sdr, hdr = registry_with_both_profiles
        profiles = icc._winreg_get_display_profiles(
            _MONKEY, exclude_advanced_color=True
        )
        assert sdr in profiles
        assert hdr not in profiles

    def test_exclude_false_keeps_hdr_entry(self, registry_with_both_profiles):
        """Explicitly passing exclude_advanced_color=False keeps both entries."""
        icc, sdr, hdr = registry_with_both_profiles
        profiles = icc._winreg_get_display_profiles(
            _MONKEY, exclude_advanced_color=False
        )
        assert hdr in profiles


# ---------------------------------------------------------------------------
# _winreg_get_display_profile
# ---------------------------------------------------------------------------


class TestWinregGetDisplayProfile:
    def test_sdr_mode_returns_sdr_profile(self, registry_with_both_profiles):
        """advanced_color_active=False must exclude ICMProfileAC and pick ICMProfile."""
        icc, sdr, hdr = registry_with_both_profiles
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=False
        )
        assert result is not None
        assert sdr in result
        assert hdr not in result

    def test_hdr_mode_returns_hdr_profile(self, registry_with_both_profiles):
        """advanced_color_active=True must keep ICMProfileAC (last entry wins)."""
        icc, sdr, hdr = registry_with_both_profiles
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=True
        )
        assert result is not None
        assert hdr in result

    def test_unknown_hdr_state_prefers_sdr_profile(self, registry_with_both_profiles):
        """advanced_color_active=None (unknown) must prefer the ICMProfile slot."""
        icc, sdr, hdr = registry_with_both_profiles
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=None
        )
        assert result is not None
        assert sdr in result

    def test_only_sdr_profile_in_registry(self, tmp_path):
        """When no ICMProfileAC exists, SDR profile is still returned correctly."""
        sdr_file = tmp_path / "sdr_only.icm"
        sdr_file.write_bytes(b"")

        fake_winreg = _make_fake_winreg([("ICMProfile", [sdr_file.name], 7)])
        orig_winreg = getattr(_icc, "winreg", None)
        orig_profiles = _icc.ICCPROFILES
        _icc.winreg = fake_winreg
        _icc.ICCPROFILES = [str(tmp_path)]
        try:
            result = _icc._winreg_get_display_profile(
                _MONKEY, path_only=True, advanced_color_active=False
            )
            assert result is not None
            assert sdr_file.name in result
        finally:
            if orig_winreg is None:
                if hasattr(_icc, "winreg"):
                    del _icc.winreg
            else:
                _icc.winreg = orig_winreg
            _icc.ICCPROFILES = orig_profiles


# ---------------------------------------------------------------------------
# Issue #989: the profile must follow the display mode, not registry order
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_registry(tmp_path):
    """Return a callable that injects a fake winreg seeded with given values.

    Each profile filename used in the values is created in ``tmp_path`` so it
    passes the existence check.
    """
    orig_winreg = getattr(_icc, "winreg", None)
    orig_profiles = _icc.ICCPROFILES

    def _install(registry_values):
        for _name, value, _type in registry_values:
            for filename in value:
                (tmp_path / filename).write_bytes(b"")
        _icc.winreg = _make_fake_winreg(registry_values)
        _icc.ICCPROFILES = [str(tmp_path)]
        return _icc

    yield _install

    if orig_winreg is None:
        if hasattr(_icc, "winreg"):
            del _icc.winreg
    else:
        _icc.winreg = orig_winreg
    _icc.ICCPROFILES = orig_profiles


class TestProfileFollowsDisplayMode:
    @pytest.mark.parametrize(
        "registry_values",
        [
            # SDR profile installed first (ICMProfile value created first)
            [
                ("ICMProfile", ["sdr.icm"], 7),
                ("ICMProfileAC", ["hdr.icm"], 7),
            ],
            # HDR profile installed first (ICMProfileAC value created first)
            [
                ("ICMProfileAC", ["hdr.icm"], 7),
                ("ICMProfile", ["sdr.icm"], 7),
            ],
        ],
        ids=["sdr_installed_first", "hdr_installed_first"],
    )
    @pytest.mark.parametrize(
        ("advanced_color_active", "expected"),
        [(False, "sdr.icm"), (True, "hdr.icm"), (None, "sdr.icm")],
        ids=["sdr_mode", "hdr_mode", "unknown_mode"],
    )
    def test_registry_value_order_does_not_matter(
        self, fake_registry, registry_values, advanced_color_active, expected
    ):
        """The active mode's slot is used regardless of registry value order."""
        icc = fake_registry(registry_values)
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=advanced_color_active
        )
        assert result is not None
        assert os.path.basename(result) == expected

    def test_last_entry_of_active_slot_is_default(self, fake_registry):
        """Within a slot the last associated profile is the default one."""
        icc = fake_registry(
            [
                ("ICMProfileAC", ["hdr_old.icm", "hdr_new.icm"], 7),
                ("ICMProfile", ["sdr_old.icm", "sdr_new.icm"], 7),
            ]
        )
        sdr = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=False
        )
        hdr = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=True
        )
        assert os.path.basename(sdr) == "sdr_new.icm"
        assert os.path.basename(hdr) == "hdr_new.icm"

    def test_hdr_mode_falls_back_to_sdr_slot(self, fake_registry):
        """In HDR mode without an ICMProfileAC association, ICMProfile is used."""
        icc = fake_registry([("ICMProfile", ["sdr.icm"], 7)])
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=True
        )
        assert os.path.basename(result) == "sdr.icm"

    def test_unknown_mode_falls_back_to_ac_slot(self, fake_registry):
        """With unknown mode and only an ICMProfileAC association, it is used."""
        icc = fake_registry([("ICMProfileAC", ["hdr.icm"], 7)])
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=None
        )
        assert os.path.basename(result) == "hdr.icm"

    def test_sdr_mode_never_uses_ac_slot(self, fake_registry):
        """In SDR mode an ICMProfileAC-only display falls back to sRGB."""
        icc = fake_registry([("ICMProfileAC", ["hdr.icm"], 7)])
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=False
        )
        assert os.path.basename(result) == "sRGB Color Space Profile.icm"
