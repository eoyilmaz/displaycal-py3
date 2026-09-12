"""Profile reads can fail while an installed ICC file is being replaced."""

import struct
from unittest import mock

import pytest

from DisplayCAL import profile_loader
from DisplayCAL.colormath import get_rgb_space
from DisplayCAL.icc_profile import ICCProfile, VideoCardGammaFormulaType


def make_loader():
    """Use the ramp code without starting a tray icon or touching the display."""
    loader = profile_loader.ProfileLoader.__new__(profile_loader.ProfileLoader)
    loader.profiles = {}
    loader.ramps = {}
    loader._reset_gamma_ramps = False
    loader._manual_restore = False
    loader._quantize = 65535.0
    return loader


def generate_ramp(loader, path, key="display-1"):
    return loader._generate_gamma_ramp(
        False, [], [], "Test display", key, str(path), False, "Test profile"
    )[1]


def make_profile(path, calibrated=True):
    profile = ICCProfile.from_rgb_space(get_rgb_space("sRGB"), "Test profile")
    if calibrated:
        data = b"vcgt" + b"\0" * 4 + struct.pack(">I", 1)
        data += struct.pack(">III", 2 * 65536, 0, 65536) * 3
        profile.tags["vcgt"] = VideoCardGammaFormulaType(data, "vcgt")
    profile.write(str(path))


@pytest.mark.parametrize("failures", [1, 2])
@pytest.mark.parametrize("manual_restore", [False, True])
def test_profile_read_is_retried_without_an_association_change(
    tmp_path, failures, manual_restore
):
    path = tmp_path / "calibrated.icc"
    make_profile(path)
    loader = make_loader()
    loader._manual_restore = manual_restore
    reads = 0

    def read_profile(filename=None):
        nonlocal reads
        if filename:
            reads += 1
            if reads <= failures:
                raise PermissionError("Profile is temporarily locked")
        return ICCProfile(filename)

    with mock.patch.object(profile_loader, "ICCProfile", side_effect=read_profile):
        for _ in range(failures):
            fallback = generate_ramp(loader, path)
            assert fallback[0][128] == 32896
        recovered = generate_ramp(loader, path)
        # The file and association have not changed. Retry must replace the
        # temporary linear fallback with the profile's gamma 2.0 calibration.
        assert recovered[0][128] < 17000
        assert reads == failures + 1
        assert generate_ramp(loader, path) is recovered
        assert reads == failures + 1


@pytest.mark.parametrize("calibrated", [False, True])
def test_successful_profiles_are_still_cached(tmp_path, calibrated):
    path = tmp_path / "valid.icc"
    make_profile(path, calibrated)
    loader = make_loader()
    with mock.patch.object(profile_loader, "ICCProfile", wraps=ICCProfile) as read:
        ramp = generate_ramp(loader, path)
        assert generate_ramp(loader, path) is ramp
        read.assert_called_once_with(str(path))


def test_explicit_reset_does_not_read_the_profile(tmp_path):
    loader = make_loader()
    loader._reset_gamma_ramps = True
    with mock.patch.object(profile_loader, "ICCProfile", wraps=ICCProfile) as read:
        ramp = generate_ramp(loader, tmp_path / "unused.icc")
        assert ramp[0][128] == 32896
        assert generate_ramp(loader, tmp_path / "unused.icc") is ramp
        read.assert_not_called()
