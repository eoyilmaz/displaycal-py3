"""Profile reads can fail while an installed ICC file is being replaced."""

import struct
from unittest import mock

import pytest

from DisplayCAL import localization, profile_loader
from DisplayCAL.colormath import get_rgb_space
from DisplayCAL.icc_profile import ICCProfile, VideoCardGammaFormulaType


@pytest.fixture(autouse=True)
def bind_lang(monkeypatch):
    """``profile_loader.main()`` binds the ``lang`` global at runtime."""
    localization.init()
    monkeypatch.setattr(profile_loader, "lang", localization, raising=False)


def make_loader():
    """Use the ramp code without starting a tray icon or touching the display."""
    loader = profile_loader.ProfileLoader.__new__(profile_loader.ProfileLoader)
    loader.profiles = {}
    loader.ramps = {}
    loader._profile_read_failures = {}
    loader._reset_gamma_ramps = False
    loader._manual_restore = False
    loader._quantize = 65535.0
    return loader


def generate_ramp(loader, path, key="display-1", errors=None):
    return loader._generate_gamma_ramp(
        False,
        [],
        [] if errors is None else errors,
        "Test display",
        key,
        str(path),
        False,
        "Test profile",
    )[1]


def locked_reader(fail_reads):
    """Return an ``ICCProfile`` stand-in failing the first ``fail_reads`` reads."""
    reads = []

    def read_profile(filename=None):
        if filename:
            reads.append(filename)
            if len(reads) <= fail_reads:
                raise PermissionError("Profile is temporarily locked")
        return ICCProfile(filename)

    return read_profile, reads


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
    read_profile, reads = locked_reader(fail_reads=failures)
    with mock.patch.object(profile_loader, "ICCProfile", side_effect=read_profile):
        for _ in range(failures):
            fallback = generate_ramp(loader, path)
            assert fallback[0][128] == 32896
        recovered = generate_ramp(loader, path)
        # The file and association have not changed. Retry must replace the
        # temporary linear fallback with the profile's gamma 2.0 calibration.
        assert recovered[0][128] < 17000
        assert len(reads) == failures + 1
        assert generate_ramp(loader, path) is recovered
        assert len(reads) == failures + 1


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


def test_persistent_read_failure_is_cached_and_logged_once(tmp_path, capsys):
    path = tmp_path / "calibrated.icc"
    make_profile(path)
    loader = make_loader()
    retries = loader.PROFILE_READ_RETRIES
    read_profile, reads = locked_reader(fail_reads=retries + 5)
    with mock.patch.object(profile_loader, "ICCProfile", side_effect=read_profile):
        for _ in range(retries + 5):
            ramp = generate_ramp(loader, path)
            assert ramp[0][128] == 32896
    # Polling stops re-reading the file once the retries are used up
    assert len(reads) == retries
    output = capsys.readouterr().out
    assert output.count("Profile is temporarily locked") == 1
    assert output.count("Using temporary linear gamma ramps") == 1
    assert output.count("Caching linear gamma ramps for unreadable profile") == 1


def test_changed_read_error_is_logged_again(tmp_path, capsys):
    path = tmp_path / "calibrated.icc"
    make_profile(path)
    loader = make_loader()
    errors = iter(
        [PermissionError("locked"), PermissionError("locked"), OSError("gone")]
    )

    def read_profile(filename=None):
        raise next(errors)

    with mock.patch.object(profile_loader, "ICCProfile", side_effect=read_profile):
        for _ in range(3):
            generate_ramp(loader, path)
    output = capsys.readouterr().out
    assert output.count("locked") == 1
    assert output.count("gone") == 1


def test_manual_restore_retries_a_cached_unreadable_profile(tmp_path):
    path = tmp_path / "calibrated.icc"
    make_profile(path)
    loader = make_loader()
    retries = loader.PROFILE_READ_RETRIES
    read_profile, reads = locked_reader(fail_reads=retries)
    with mock.patch.object(profile_loader, "ICCProfile", side_effect=read_profile):
        for _ in range(retries + 1):
            assert generate_ramp(loader, path)[0][128] == 32896
        assert len(reads) == retries
        loader._manual_restore = True
        recovered = generate_ramp(loader, path)
        assert recovered[0][128] < 17000
        assert len(reads) == retries + 1
        assert "display-1" not in loader._profile_read_failures
        loader._manual_restore = False
        assert generate_ramp(loader, path) is recovered


@pytest.mark.parametrize("manual_restore", [False, True])
def test_read_failure_is_reported_only_when_loading_was_requested(
    tmp_path, manual_restore
):
    path = tmp_path / "calibrated.icc"
    make_profile(path)
    loader = make_loader()
    loader._manual_restore = manual_restore
    read_profile, _reads = locked_reader(fail_reads=1)
    errors = []
    with mock.patch.object(profile_loader, "ICCProfile", side_effect=read_profile):
        generate_ramp(loader, path, errors=errors)
    if manual_restore:
        assert errors == ["Test display: Display profile couldn't be loaded."]
    else:
        assert errors == []
