"""Tests for the ICC v2 text description tag (DisplayCAL.icc_profile.tags.text)."""

from DisplayCAL.icc_profile import ICCProfile


def test_a_utf16_macintosh_part_is_read_as_utf16(data_path):
    """Some writers put UTF-16 (with its byte order mark) in the ScriptCode part.

    Read as Mac Roman it came out as '˛ˇ\\x00M\\x00o...' wherever the
    profile's name is shown.
    """
    profile = ICCProfile(
        str(
            data_path
            / "icc"
            / "Monitor 1 #1 2022-03-09 16-13 D6500 2.2 F-S XYZLUT+MTX.icc"
        )
    )

    assert profile.getDescription() == "Monitor 1 #1 2022-03-09 16-"


def test_a_plain_profile_keeps_its_description(data_path):
    profile = ICCProfile(
        str(
            data_path
            / "icc"
            / "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
        )
    )

    assert (
        profile.getDescription()
        == "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX"
    )
