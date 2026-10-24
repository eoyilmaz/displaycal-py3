from binascii import hexlify

import pytest

from DisplayCAL import colord
from DisplayCAL.colord import device_id_from_edid

PROFILE_FILENAME = "/home/user/.local/share/icc/test.icc"


def test_device_id_from_edid_1():
    """Testing DisplayCAL.colord.device_id_from_edid() function."""
    edid = {
        "edid": b"00ffffffffffff005a633a7a0f010101311e0104b53c22783bb091ab524ea0260f505"
            b"4bfef80e1c0d100d1c0b300a9408180810081c0565e00a0a0a02950302035005550210000"
            b"1a000000ff005738553230343930303130340a000000fd00184b0f5a1e000a20202020202"
            b"0000000fc00565032373638610a2020202020017b020322f155901f05145a5904131e1d0f"
            b"0e07061211161503020123097f0783010000023a801871382d40582c450055502100001e0"
            b"11d8018711c1620582c250055502100009e023a80d072382d40102c458055502100001e01"
            b"1d007251d01e206e28550055502100001e584d00b8a1381440f82c4b0055502100"
            b"001e000000d2",
        "hash": "aee2b726b409d9d54ed5924ad309781d",
        "header": b"00ffffff",
        "manufacturer_id": "YSF",
        "product_id": 26214,
        "serial_32": 808478310,
        "week_of_manufacture": 53,
        "year_of_manufacture": 2087,
        "edid_version": 54,
        "edid_revision": 51,
        "max_h_size_cm": 97,
        "max_v_size_cm": 55,
        "gamma": 1.97,
        "features": 48,
        "red_x": 0.1923828125,
        "red_y": 0.189453125,
        "green_x": 0.1923828125,
        "green_y": 0.189453125,
        "blue_x": 0.19140625,
        "blue_y": 0.2021484375,
        "white_x": 0.19140625,
        "white_y": 0.19140625,
        "ext_flag": 50,
        "checksum": 48,
        "checksum_valid": False,
    }

    device_id = device_id_from_edid(edid)
    assert isinstance(device_id, str)
    assert device_id == "xrandr-808478310"


def test_get_profile_install_parameters_calculates_missing_profile_id(
    random_icc_profile, monkeypatch, tmp_path
):
    """A profile without a header ID gets one, so it matches colord's ID."""
    monkeypatch.setattr(colord, "XDG_DATA_HOME", str(tmp_path), raising=False)
    profile, _ = random_icc_profile
    profile.ID = b"\0" * 16

    _, _, profile_id = colord.get_profile_install_parameters(profile)

    assert profile.ID != b"\0" * 16
    assert profile.calculate_id(set_id=False) == profile.ID
    assert profile_id == "icc-" + hexlify(profile.ID).decode()
    # The profile is rewritten so the file contains the calculated ID
    assert profile.filename is None


def test_get_profile_install_parameters_keeps_existing_profile_id(
    random_icc_profile, monkeypatch, tmp_path
):
    """A profile with a header ID keeps it, as colord uses it as is."""
    monkeypatch.setattr(colord, "XDG_DATA_HOME", str(tmp_path), raising=False)
    profile, _ = random_icc_profile
    profile.ID = b"\x01" * 16

    _, _, profile_id = colord.get_profile_install_parameters(profile)

    assert profile_id == "icc-" + "01" * 16


def test_query_colord_for_newly_added_profile_finds_profile_by_id(monkeypatch):
    """The profile is looked up by its ID first."""
    calls = []

    def fake_find(what, search):
        calls.append((what, search))
        return "/org/freedesktop/ColorManager/profiles/icc_123"

    monkeypatch.setattr(colord, "find", fake_find)
    monkeypatch.setattr(colord, "sleep", lambda secs: None)

    cdprofile = colord.query_colord_for_newly_added_profile(
        "icc-123", filename=PROFILE_FILENAME, timeout=2
    )

    assert cdprofile == "/org/freedesktop/ColorManager/profiles/icc_123"
    assert calls == [("profile-by-id", "icc-123")]


def test_query_colord_for_newly_added_profile_falls_back_to_filename(monkeypatch):
    """The profile is looked up by its filename if it isn't found by its ID."""
    calls = []

    def fake_find(what, search):
        calls.append((what, search))
        if what == "profile-by-id":
            raise colord.CDObjectNotFoundError("not found")
        return "/org/freedesktop/ColorManager/profiles/icc_456"

    monkeypatch.setattr(colord, "find", fake_find)
    monkeypatch.setattr(colord, "sleep", lambda secs: None)

    cdprofile = colord.query_colord_for_newly_added_profile(
        "icc-123", filename=PROFILE_FILENAME, timeout=2
    )

    assert cdprofile == "/org/freedesktop/ColorManager/profiles/icc_456"
    # Both lookups happen within the same polling iteration
    assert calls == [
        ("profile-by-id", "icc-123"),
        ("profile-by-filename", PROFILE_FILENAME),
    ]


def test_query_colord_for_newly_added_profile_timeout_reports_query_error(
    monkeypatch,
):
    """A timeout reports the last query error instead of swallowing it."""

    def fake_find(what, search):
        raise colord.CDObjectQueryError("colord exploded")

    sleeps = []
    monkeypatch.setattr(colord, "find", fake_find)
    monkeypatch.setattr(colord, "sleep", sleeps.append)

    with pytest.raises(colord.CDTimeoutError) as exc_info:
        colord.query_colord_for_newly_added_profile(
            "icc-123", filename=PROFILE_FILENAME, timeout=3
        )

    assert "icc-123" in str(exc_info.value)
    assert PROFILE_FILENAME in str(exc_info.value)
    assert "colord exploded" in str(exc_info.value)
    # The timeout is not spent twice
    assert sleeps == [1, 1, 1]


def test_query_colord_for_newly_added_profile_propagates_colord_errors(monkeypatch):
    """Errors other than query errors are not retried."""

    def fake_find(what, search):
        raise colord.CDError("colord API not available")

    monkeypatch.setattr(colord, "find", fake_find)
    monkeypatch.setattr(colord, "sleep", lambda secs: None)

    with pytest.raises(colord.CDError, match="colord API not available"):
        colord.query_colord_for_newly_added_profile("icc-123", timeout=2)


class FakeColordClient:
    """Fake Colord GI client."""

    def __init__(self, profiles_by_id=None, profiles_by_filename=None):
        self.profiles_by_id = profiles_by_id or {}
        self.profiles_by_filename = profiles_by_filename or {}
        self.calls = []

    def find_profile_sync(self, profile_id, cancellable):
        self.calls.append(("id", profile_id))
        if profile_id not in self.profiles_by_id:
            raise RuntimeError(f"profile id '{profile_id}' does not exist")
        return self.profiles_by_id[profile_id]

    def find_profile_by_filename_sync(self, filename, cancellable):
        self.calls.append(("filename", filename))
        if filename not in self.profiles_by_filename:
            raise RuntimeError(f"profile filename '{filename}' does not exist")
        return self.profiles_by_filename[filename]


def test_query_colord_gi_for_newly_added_profile_finds_profile_by_id(monkeypatch):
    """The GI client looks the profile up by its ID first."""
    cdprofile = object()
    client = FakeColordClient(profiles_by_id={"icc-123": cdprofile})
    monkeypatch.setattr(colord, "cancellable", None, raising=False)
    monkeypatch.setattr(colord, "sleep", lambda secs: None)

    result = colord.query_colord_gi_for_newly_added_profile(
        client, "icc-123", filename=PROFILE_FILENAME, timeout=2
    )

    assert result is cdprofile
    assert client.calls == [("id", "icc-123")]


def test_query_colord_gi_for_newly_added_profile_falls_back_to_filename(
    monkeypatch,
):
    """The GI client looks the profile up by its filename if needed."""
    cdprofile = object()
    client = FakeColordClient(profiles_by_filename={PROFILE_FILENAME: cdprofile})
    monkeypatch.setattr(colord, "cancellable", None, raising=False)
    monkeypatch.setattr(colord, "sleep", lambda secs: None)

    result = colord.query_colord_gi_for_newly_added_profile(
        client, "icc-123", filename=PROFILE_FILENAME, timeout=2
    )

    assert result is cdprofile
    assert client.calls == [("id", "icc-123"), ("filename", PROFILE_FILENAME)]


def test_query_colord_gi_for_newly_added_profile_timeout_reports_error(
    monkeypatch,
):
    """A GI client timeout reports the last error."""
    client = FakeColordClient()
    monkeypatch.setattr(colord, "cancellable", None, raising=False)
    monkeypatch.setattr(colord, "sleep", lambda secs: None)

    with pytest.raises(colord.CDTimeoutError, match="does not exist"):
        colord.query_colord_gi_for_newly_added_profile(
            client, "icc-123", filename=PROFILE_FILENAME, timeout=2
        )
