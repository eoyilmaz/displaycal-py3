# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Tuple

import pytest

from DisplayCAL import argyll_cgats
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.cgats import CGATS
from DisplayCAL.debughelpers import Error


def test_quote_nonoption_args_1():
    """Testing if the quote_nonoption_args() function is working properly."""
    test_value = [
        "/home/erkan.yilmaz/Downloads/Argyll_V2.3.0/bin/dispread",
        "-v",
        "-d1",
        "-c1",
        "-yn",
        "-P0.4711274060494959,1,1.0",
        "-k",
        "'Monitor 1 #1 2022-03-02 23-45 D6500 2.2 F-S XYZLUT+MTX.cal'",
        "'Monitor 1 #1 2022-03-02 23-45 D6500 2.2 F-S XYZLUT+MTX'",
    ]

    expected_result = [
        b'"/home/erkan.yilmaz/Downloads/Argyll_V2.3.0/bin/dispread"',
        b"-v",
        b"-d1",
        b"-c1",
        b"-yn",
        b"-P0.4711274060494959,1,1.0",
        b"-k",
        b"\"'Monitor 1 #1 2022-03-02 23-45 D6500 2.2 F-S XYZLUT+MTX.cal'\"",
        b"\"'Monitor 1 #1 2022-03-02 23-45 D6500 2.2 F-S XYZLUT+MTX'\"",
    ]

    result = argyll_cgats.quote_nonoption_args(test_value)
    assert result == expected_result


def test_vcgt_to_cal_1(data_files):
    """Testing the vcgt_to_cal() function."""
    icc_path = data_files["UP2516D #1 2022-03-23 16-06 D6500 2.2 F-S XYZLUT+MTX.icc"]
    profile = ICCProfile(icc_path)
    cgats = argyll_cgats.vcgt_to_cal(profile)
    assert cgats[0]["COLOR_REP"] == b"RGB"
    assert cgats[0]["DATA_FORMAT"] == {
        0: b"RGB_I",
        1: b"RGB_R",
        2: b"RGB_G",
        3: b"RGB_B",
    }
    assert cgats[0]["DESCRIPTOR"] == b"Argyll Device Calibration State"
    assert cgats[0]["DEVICE_CLASS"] == b"DISPLAY"
    assert cgats[0]["KEYWORDS"] == {0: b"DEVICE_CLASS", 1: b"COLOR_REP", 2: b"RGB_I"}
    assert cgats[0]["ORIGINATOR"] == b"vcgt"


@pytest.mark.parametrize(
    "icc_name,exception",
    (
        ("UP2516D #1 2022-03-23 16-06 D6500 2.2 F-S XYZLUT+MTX.icc", False),
        ("vcgt_cm_test_yellowish_blueish.icc", False),
        ("BenQ PD2700U-AC19BB79-F553-4582-B898-4247D669C2F1.icc", True),
    ),
)
def test_extract_cal_from_profile_1(data_files, icc_name: str, exception: bool) -> None:
    """Testing the extract_cal_from_profile() function."""
    icc_path = data_files[icc_name]
    profile = ICCProfile(icc_path)
    if exception:
        with pytest.raises(Error):
            argyll_cgats.extract_cal_from_profile(profile)
    else:
        cgats = argyll_cgats.extract_cal_from_profile(profile)
        assert cgats[0]["COLOR_REP"] == b"RGB"
        assert cgats[0]["DATA_FORMAT"] == {
            0: b"RGB_I",
            1: b"RGB_R",
            2: b"RGB_G",
            3: b"RGB_B",
        }
        assert cgats[0]["DESCRIPTOR"] == b"Argyll Device Calibration State"
        assert cgats[0]["DEVICE_CLASS"] == b"DISPLAY"
        assert cgats[0]["KEYWORDS"] == {
            0: b"DEVICE_CLASS",
            1: b"COLOR_REP",
            2: b"RGB_I",
        }
        assert cgats[0]["ORIGINATOR"] == b"vcgt"


@pytest.mark.parametrize(
    "profile, result",
    (
        ("0_16_proper.ti3", b"CTI1"),
        ("BenQ PD2700U-AC19BB79-F553-4582-B898-4247D669C2F1.icc", None),
    ),
)
def test_ti3_to_ti1_1(data_files, profile: str, result: bytes | None) -> None:
    """Testing the ti3_to_ti1() function."""
    path = data_files[profile]
    if not result:
        assert not argyll_cgats.ti3_to_ti1(path)
    else:
        assert result in argyll_cgats.ti3_to_ti1(path)


def test_ti3_to_ti1_2(data_files):
    """Testing the argyll_cgats.ti3_to_ti1() function."""
    ti3_path = data_files["0_16_from_issue_129.ti3"].absolute()
    result = argyll_cgats.ti3_to_ti1(ti3_path)
    assert result == (
        b"CTI1   \n"
        b"\n"
        b'DESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        b'ORIGINATOR "Argyll targen"\n'
        b'CREATED "Sun Jun  5 13:08:54 2022"\n'
        b'COLOR_REP "RGB"\n'
        b'TARGET_INSTRUMENT "Datacolor Spyder3"\n'
        b'DISPLAY_TYPE_REFRESH "NO"\n'
        b'DISPLAY_TYPE_BASE_ID "1"\n'
        b'INSTRUMENT_TYPE_SPECTRAL "NO"\n'
        b'NORMALIZED_TO_Y_100 "YES"\n'
        b'VIDEO_LUT_CALIBRATION_POSSIBLE "YES"\n'
        b"\n"
        b"NUMBER_OF_FIELDS 7\n"
        b"BEGIN_DATA_FORMAT\n"
        b"SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        b"END_DATA_FORMAT\n"
        b"\n"
        b"NUMBER_OF_SETS 3\n"
        b"BEGIN_DATA\n"
        b"1 100.0000 100.0000 100.0000 95.01040 100.0000 92.72020\n"
        b"2 0.000000 0.000000 0.000000 0.277593 0.255279 0.423145\n"
        b"3 6.250000 6.250000 6.250000 0.512380 0.536117 0.705578\n"
        b"END_DATA\n"
    )


@pytest.mark.parametrize("gray", (True, False), ids=("with gray", "without gray"))
@pytest.mark.parametrize(
    "include_neutrals",
    (True, False),
    ids=("include neutrals", "don't include neutrals"),
)
@pytest.mark.parametrize(
    "profile, sets",
    (
        ("0_16_proper.ti3", (3, 2, 0, 1)),
        ("Monitor_AllBlack.ti3", (52, 120, 120, 167)),
    ),
)
def test_extract_device_gray_primaries(
    data_files,
    profile: str,
    sets: Tuple[int, int, int, int],
    include_neutrals: bool,
    gray: bool,
) -> None:
    """Testing the extract_device_gray_primaries() function."""
    path = data_files[profile]
    cgats = CGATS(cgats=path)
    (
        ti3_extracted,
        RGB_XYZ_extracted,
        RGB_XYZ_remaining,
    ) = argyll_cgats.extract_device_gray_primaries(
        cgats, include_neutrals=include_neutrals, gray=gray
    )
    assert len(ti3_extracted) == 4
    assert len(RGB_XYZ_extracted) == sets[0] if gray else sets[1]
    assert len(RGB_XYZ_remaining) == sets[2] if gray else sets[3]


def test_verify_cgats_1(data_files):
    """Testing verify_cgats() for #129."""
    ti1 = CGATS(data_files["issue129_0_16.ti1"])
    result = argyll_cgats.verify_cgats(ti1, ("RGB_R", "RGB_B", "RGB_G"))
    expected_result = {
        "APPROX_WHITE_POINT": b"95.045781 100.000003 108.905751",
        "COLOR_REP": b"RGB",
        "CREATED": b"Thu Apr 20 12:22:05 2017",
        "DATA": {
            0: {
                "RGB_B": 100.0,
                "RGB_G": 100.0,
                "RGB_R": 100.0,
                "SAMPLE_ID": 1,
                "XYZ_X": 95.046,
                "XYZ_Y": 100.0,
                "XYZ_Z": 108.91,
            },
            1: {
                "RGB_B": 0.0,
                "RGB_G": 0.0,
                "RGB_R": 0.0,
                "SAMPLE_ID": 2,
                "XYZ_X": 0.0,
                "XYZ_Y": 0.0,
                "XYZ_Z": 0.0,
            },
            2: {
                "RGB_B": 6.25,
                "RGB_G": 6.25,
                "RGB_R": 6.25,
                "SAMPLE_ID": 3,
                "XYZ_X": 0.2132,
                "XYZ_Y": 0.2241,
                "XYZ_Z": 0.2443,
            },
        },
        "DATA_FORMAT": {
            0: b"SAMPLE_ID",
            1: b"RGB_R",
            2: b"RGB_G",
            3: b"RGB_B",
            4: b"XYZ_X",
            5: b"XYZ_Y",
            6: b"XYZ_Z",
        },
        "DESCRIPTOR": b"Argyll Calibration Target chart information 1",
        "NUMBER_OF_FIELDS": None,
        "NUMBER_OF_SETS": None,
        "ORIGINATOR": b"Argyll targen",
    }
    assert result == expected_result


def test_verify_cgats_2(data_files):
    """Testing verify_cgats() for #129."""
    cgats = CGATS(
        argyll_cgats.ti3_to_ti1(
            open(data_files["issue129_0_16.ti3"], "rb"),
        )
    )
    result = argyll_cgats.verify_cgats(cgats, ("RGB_R", "RGB_B", "RGB_G"))
    expected_result = {
        "COLOR_REP": b"RGB",
        "CREATED": b"Tue Jun  7 19:06:44 2022",
        "DATA": {
            0: {
                "RGB_B": 100.0,
                "RGB_G": 100.0,
                "RGB_R": 100.0,
                "SAMPLE_ID": 1,
                "XYZ_X": 95.7972,
                "XYZ_Y": 100.0,
                "XYZ_Z": 94.14447,
            },
            1: {
                "RGB_B": 0.0,
                "RGB_G": 0.0,
                "RGB_R": 0.0,
                "SAMPLE_ID": 2,
                "XYZ_X": 0.224507,
                "XYZ_Y": 0.227491,
                "XYZ_Z": 0.371222,
            },
            2: {
                "RGB_B": 6.25,
                "RGB_G": 6.25,
                "RGB_R": 6.25,
                "SAMPLE_ID": 3,
                "XYZ_X": 0.50435,
                "XYZ_Y": 0.524262,
                "XYZ_Z": 0.660054,
            },
        },
        "DATA_FORMAT": {
            0: b"SAMPLE_ID",
            1: b"RGB_R",
            2: b"RGB_G",
            3: b"RGB_B",
            4: b"XYZ_X",
            5: b"XYZ_Y",
            6: b"XYZ_Z",
        },
        "DESCRIPTOR": b"Argyll Calibration Target chart information 1",
        "DISPLAY_TYPE_BASE_ID": 1,
        "DISPLAY_TYPE_REFRESH": b"NO",
        "INSTRUMENT_TYPE_SPECTRAL": b"NO",
        "NORMALIZED_TO_Y_100": b"YES",
        "NUMBER_OF_FIELDS": None,
        "NUMBER_OF_SETS": None,
        "ORIGINATOR": b"Argyll targen",
        "TARGET_INSTRUMENT": b"Datacolor Spyder3",
        "VIDEO_LUT_CALIBRATION_POSSIBLE": b"YES",
    }
    assert result == expected_result


def test_verify_ti1_rgb_xyz_1(data_files):
    """Testing verify_ti1_rgb_xyz() for #129."""
    ti1 = CGATS(data_files["issue129_0_16.ti1"])
    result = argyll_cgats.verify_ti1_rgb_xyz(ti1)
    expected_result = {
        "APPROX_WHITE_POINT": b"95.045781 100.000003 108.905751",
        "COLOR_REP": b"RGB",
        "CREATED": b"Thu Apr 20 12:22:05 2017",
        "DATA": {
            0: {
                "RGB_B": 100.0,
                "RGB_G": 100.0,
                "RGB_R": 100.0,
                "SAMPLE_ID": 1,
                "XYZ_X": 95.046,
                "XYZ_Y": 100.0,
                "XYZ_Z": 108.91,
            },
            1: {
                "RGB_B": 0.0,
                "RGB_G": 0.0,
                "RGB_R": 0.0,
                "SAMPLE_ID": 2,
                "XYZ_X": 0.0,
                "XYZ_Y": 0.0,
                "XYZ_Z": 0.0,
            },
            2: {
                "RGB_B": 6.25,
                "RGB_G": 6.25,
                "RGB_R": 6.25,
                "SAMPLE_ID": 3,
                "XYZ_X": 0.2132,
                "XYZ_Y": 0.2241,
                "XYZ_Z": 0.2443,
            },
        },
        "DATA_FORMAT": {
            0: b"SAMPLE_ID",
            1: b"RGB_R",
            2: b"RGB_G",
            3: b"RGB_B",
            4: b"XYZ_X",
            5: b"XYZ_Y",
            6: b"XYZ_Z",
        },
        "DESCRIPTOR": b"Argyll Calibration Target chart information 1",
        "NUMBER_OF_FIELDS": None,
        "NUMBER_OF_SETS": None,
        "ORIGINATOR": b"Argyll targen",
    }
    assert result == expected_result
