# -*- coding: utf-8 -*-
"""Tests for the DisplayCAL.ICCProfile module."""
import binascii
import datetime
import sys
from time import strftime

from DisplayCAL import ICCProfile, colormath
from DisplayCAL.ICCProfile import (
    uInt8Number_tohex,
    uInt32Number_tohex,
    s15Fixed16Number_tohex,
    uInt16Number_tohex,
    DictType,
    hexrepr,
    cmms,
    dateTimeNumber,
    ICCProfileTag,
    Text,
    MultiLocalizedUnicodeType, Observer,
)


def test_iccprofile_from_rgb_space():
    """Testing if the ICCProfile.from_rgb_space() method is working properly."""
    rec709_gamma18 = list(colormath.get_rgb_space("Rec. 709"))
    icc = ICCProfile.ICCProfile.from_rgb_space(rec709_gamma18, b"Rec. 709 gamma 1.8")

    assert icc is not None
    result = icc.get_info()
    assert isinstance(result, list)

    expected_result = [
        ["Size", "0 Bytes (0.00 KiB)"],
        ["Preferred CMM", "0x6172676C 'argl' ArgyllCMS"],
        ["ICC version", "2.2"],
        ["Profile class", "Display device profile"],
        ["Color model", "RGB"],
        ["Profile connection space (PCS)", "XYZ"],
        ["Created", "2022-03-09 00:19:53"],
        ["Platform", "Apple"] if sys.platform == "darwin" else ["Platform", "0x2A6E6978 '*nix'"],
        ["Is embedded", "No"],
        ["Can be used independently", "Yes"],
        ["Device", ""],
        ["    Manufacturer", "0x00000000"],
        ["    Model", "0x00000000"],
        ["    Media attributes", "Reflective, Glossy, Positive, Color"],
        ["Default rendering intent", "Perceptual"],
        ["PCS illuminant XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585, CCT 5000K)"],
        ["Creator", "0x4443414C 'DCAL' DisplayCAL"],
        ["Checksum", "0xAF709A5BE63B00419875A95394AE7EDF"],
        ["    Checksum OK", "Yes"],
        ["Description (ASCII)", "Rec. 709 gamma 1.8"],
        ["Copyright", "No copyright"],
        ["Media white point", ""],
        ["    Illuminant-relative XYZ", " 95.05 100.00 108.91 (xy 0.3127 0.3290)"],
        ["    Illuminant-relative CCT", "6503K"],
        ["        ΔE 2000 to daylight locus", "0.09"],
        ["        ΔE 2000 to blackbody locus", "4.57"],
        ["Absolute to media relative transform", "Bradford"],
        ["    Matrix", "0.8951 0.2664 -0.1614"],
        ["        ", "-0.7502 1.7135 0.0367"],
        ["        ", "0.0389 -0.0685 1.0296"],
        ["Chromaticity (illuminant-relative)", ""],
        ['    Channel 1 (R) xy', '0.6400 0.3300'],
        ['    Channel 2 (G) xy', '0.3000 0.6000'],
        ['    Channel 3 (B) xy', '0.1500 0.0600'],
        ["Red matrix column", ""],
        ["    Illuminant-relative XYZ", " 41.24  21.26   1.93 (xy 0.6400 0.3300)"],
        ["    PCS-relative XYZ", " 43.60  22.25   1.39 (xy 0.6484 0.3309)"],
        ["Red tone response curve", ""],
        ["    Number of entries", "1024"],
        ["    Transfer function", "Rec. 709"],
        ["    Minimum Y", "0.0000"],
        ["    Maximum Y", "100.00"],
        ["Green matrix column", ""],
        ["    Illuminant-relative XYZ", " 35.76  71.52  11.92 (xy 0.3000 0.6000)"],
        ["    PCS-relative XYZ", " 38.51  71.69   9.71 (xy 0.3212 0.5979)"],
        ["Green tone response curve", ""],
        ["    Number of entries", "1024"],
        ["    Transfer function", "Rec. 709"],
        ["    Minimum Y", "0.0000"],
        ["    Maximum Y", "100.00"],
        ["Blue matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.05   7.22  95.05 (xy 0.1500 0.0600)"],
        ["    PCS-relative XYZ", " 14.30   6.06  71.39 (xy 0.1559 0.0661)"],
        ["Blue tone response curve", ""],
        ["    Number of entries", "1024"],
        ["    Transfer function", "Rec. 709"],
        ["    Minimum Y", "0.0000"],
        ["    Maximum Y", "100.00"],
    ]
    # can't set the created checksum properly
    expected_result[6] = [
        "Created",
        strftime("%Y-%m-%d %H:%M:%S", icc.dateTime.timetuple()),
    ]
    expected_result[17] = [
        "Checksum",
        "0x{}".format(binascii.hexlify(icc.ID).upper().decode()),
    ]

    assert result == expected_result


def test_iccprofile_from_chromaticies():
    """Testing if the ICCProfile.from_chromaticies() method is working properly."""
    xy = [
        (0.6771560743827527, 0.32205471727089957),
        (0.19945851033134956, 0.7266949701661809),
        (0.1515536624045438, 0.04081563046813107),
        (0.3133857119826585, 0.3283378912104931),
    ]
    desc = "Monitor 1 #1 2022-02-13 20-53 D6500 2.2 VF-S XYZLUT+MTX"
    copyright = "No copyright. Created with DisplayCAL 3.8.9.3 and ArgyllCMS 2.3.0"
    display_manufacturer = None
    display_name = "Monitor 1, Output DP-2"
    cat = "Bradford"

    icc = ICCProfile.ICCProfile.from_chromaticities(
        xy[0][0],
        xy[0][1],
        xy[1][0],
        xy[1][1],
        xy[2][0],
        xy[2][1],
        xy[3][0],
        xy[3][1],
        2.2,
        desc,
        copyright,
        display_manufacturer,
        display_name,
        cat=cat,
    )

    assert isinstance(icc, ICCProfile.ICCProfile)


def test_iccprofile_get_info():
    """Testing if the ICCProfile.get_info() method is working properly."""
    xy = [
        (0.6771560743827527, 0.32205471727089957),
        (0.19945851033134956, 0.7266949701661809),
        (0.1515536624045438, 0.04081563046813107),
        (0.3133857119826585, 0.3283378912104931),
    ]
    desc = "Monitor 1 #1 2022-02-13 20-53 D6500 2.2 VF-S XYZLUT+MTX"
    copyright = "No copyright. Created with DisplayCAL 3.8.9.3 and ArgyllCMS 2.3.0"
    display_manufacturer = None
    display_name = "Monitor 1, Output DP-2"
    cat = "Bradford"

    icc = ICCProfile.ICCProfile.from_chromaticities(
        xy[0][0],
        xy[0][1],
        xy[1][0],
        xy[1][1],
        xy[2][0],
        xy[2][1],
        xy[3][0],
        xy[3][1],
        2.2,
        desc,
        copyright,
        display_manufacturer,
        display_name,
        cat=cat,
    )

    result = icc.get_info()
    assert isinstance(result, list)

    expected_result = [
        ["Size", "0 Bytes (0.00 KiB)"],
        ["Preferred CMM", "0x6172676C 'argl' ArgyllCMS"],
        ["ICC version", "2.2"],
        ["Profile class", "Display device profile"],
        ["Color model", "RGB"],
        ["Profile connection space (PCS)", "XYZ"],
        ["Created", "2022-02-14 02:44:22"],
        ["Platform", "Apple"] if sys.platform == "darwin" else ["Platform", "0x2A6E6978 '*nix'"],
        ["Is embedded", "No"],
        ["Can be used independently", "Yes"],
        ["Device", ""],
        ["    Manufacturer", "0x00000000"],
        ["    Model", "0x00000000"],
        ["    Media attributes", "Reflective, Glossy, Positive, Color"],
        ["Default rendering intent", "Perceptual"],
        ["PCS illuminant XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585, CCT 5000K)"],
        ["Creator", "0x4443414C 'DCAL' DisplayCAL"],
        ["Checksum", "0x02F595E98437CAF1593DB03F9DCD15C9"],
        ["    Checksum OK", "Yes"],
        ["Description", ""],
        ["    ASCII", "Monitor 1 #1 2022-02-13 20-53 D6500 2.2 VF-S XYZLUT+MTX"],
        ["    Unicode", "Monitor 1 #1 2022-02-13 20-53 D6500 2.2 VF-S XYZLUT+MTX"],
        [
            "Copyright",
            "No copyright. Created with DisplayCAL 3.8.9.3 and ArgyllCMS 2.3.0",
        ],
        ["Device model name", ""],
        ["    ASCII", "Monitor 1, Output DP-2"],
        ["    Unicode", "Monitor 1, Output DP-2"],
        ["Media white point", ""],
        ["    Illuminant-relative XYZ", " 95.45 100.00 109.12 (xy 0.3134 0.3283)"],
        ["    Illuminant-relative CCT", "6471K"],
        ["        ΔE 2000 to daylight locus", "1.18"],
        ["        ΔE 2000 to blackbody locus", "3.66"],
        ["Absolute to media relative transform", "Bradford"],
        ["    Matrix", "0.8951 0.2664 -0.1614"],
        ["        ", "-0.7502 1.7135 0.0367"],
        ["        ", "0.0389 -0.0685 1.0296"],
        ["Chromaticity (illuminant-relative)", ""],
        ["    Channel 1 (R) xy", "0.6772 0.3221"],
        ["    Channel 2 (G) xy", "0.1995 0.7267"],
        ["    Channel 3 (B) xy", "0.1516 0.0408"],
        ["Red matrix column", ""],
        ["    Illuminant-relative XYZ", " 57.78  27.48   0.07 (xy 0.6772 0.3221)"],
        ["    PCS-relative XYZ", " 60.96  28.84  -0.07 (xy 0.6794 0.3214)"],
        ["Red tone response curve", "Gamma 2.2"],
        ["Green matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.49  67.35   6.84 (xy 0.1995 0.7267)"],
        ["    PCS-relative XYZ", " 20.41  67.24   6.00 (xy 0.2180 0.7180)"],
        ["Green tone response curve", "Gamma 2.2"],
        ["Blue matrix column", ""],
        ["    Illuminant-relative XYZ", " 19.18   5.17 102.21 (xy 0.1516 0.0408)"],
        ["    PCS-relative XYZ", " 15.05   3.92  76.56 (xy 0.1575 0.0411)"],
        ["Blue tone response curve", "Gamma 2.2"],
    ]

    # can't set the created checksum properly
    expected_result[6] = [
        "Created",
        strftime("%Y-%m-%d %H:%M:%S", icc.dateTime.timetuple()),
    ]
    expected_result[17] = [
        "Checksum",
        "0x{}".format(binascii.hexlify(icc.ID).upper().decode()),
    ]
    assert result == expected_result


def test_iccprofile_from_xyz():
    """Testing if ICCProfile.from_xyz() method is working properly."""
    XYZ = {
        "r": [0.5777977275512667, 0.2747999919455954, 0.0006734086960673902],
        "g": [0.18487094167718518, 0.6735475123298383, 0.06844569117319045],
        "b": [0.19179233077154842, 0.05165249572456644, 1.0220629001307424],
    }
    wXYZ = (0.9544610000000001, 1.0, 1.091182)

    desc = b"Monitor 1 #1 2022-02-13 20-53 D6500 2.2 VF-S XYZLUT+MTX"
    copyright = b"No copyright. Created with DisplayCAL 3.8.9.3 and ArgyllCMS 2.3.0"
    display_manufacturer = None
    display_name = b"Monitor 1, Output DP-2"
    cat = "Bradford"

    mtx = ICCProfile.ICCProfile.from_XYZ(
        XYZ["r"],
        XYZ["g"],
        XYZ["b"],
        wXYZ,
        2.2,
        desc,
        copyright,
        display_manufacturer,
        display_name,
        cat=cat,
    )

    assert isinstance(mtx, ICCProfile.ICCProfile)


def test_uInt8Number_tohex_is_working_properly():
    """Testing if uInt8Number_tohex is working properly."""
    test_value = 1321
    result = uInt8Number_tohex(test_value)
    expected_value = b")"
    assert result == expected_value


def test_uInt32Number_tohex_is_working_properly():
    """Testing if uInt32Number_tohex is working properly."""
    test_value = 132123
    result = uInt32Number_tohex(test_value)
    expected_value = b"\x00\x02\x04\x1b"
    assert result == expected_value


def test_s15Fixed16Number_tohex_is_working_properly():
    """Testing if s15Fixed16Number_tohex is working properly."""
    test_value = 123.12
    result = s15Fixed16Number_tohex(test_value)
    expected_value = b"\x00{\x1e\xb8"
    assert result == expected_value


def test_uInt16Number_tohex_tohex_is_working_properly():
    """Testing if uInt16Number_tohex is working properly."""
    test_value = 12123
    result = uInt16Number_tohex(test_value)
    expected_value = b"/["
    assert result == expected_value


def test_dict_type():
    """Testing the DictType."""
    d = DictType()
    d.update(
        {
            "CMF_product": "DisplayCAL",
            "CMF_binary": "DisplayCAL",
            "CMF_version": "3.8.9.3",
        }
    )

    expected = (
        b"dict\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x10\x00\x00\x00@"
        b"\x00\x00\x00\x16\x00\x00\x00X\x00\x00\x00\x14\x00\x00\x00l\x00\x00\x00\x14"
        b"\x00\x00\x00\x80\x00\x00\x00\x14\x00\x00\x00\x94\x00\x00\x00\x16"
        b"\x00\x00\x00\xac\x00\x00\x00\x0e\x00C\x00M\x00F\x00_\x00p\x00r\x00o\x00d"
        b"\x00u\x00c\x00t\x00\x00\x00D\x00i\x00s\x00p\x00l\x00a\x00y\x00C\x00A\x00L"
        b"\x00C\x00M\x00F\x00_\x00b\x00i\x00n\x00a\x00r\x00y\x00D\x00i\x00s\x00p"
        b"\x00l\x00a\x00y\x00C\x00A\x00L\x00C\x00M\x00F\x00_\x00v\x00e\x00r\x00s"
        b"\x00i\x00o\x00n\x00\x00\x003\x00.\x008\x00.\x009\x00.\x003\x00\x00"
    )

    assert d.tagData == expected


def test_sample_icc_file_1(data_files):
    """Test with sample icc files.

    Args:
        data_files: A fixture supplying data files.
    """
    icc_profile = ICCProfile.ICCProfile(profile=data_files["default.icc"].absolute())
    result = icc_profile.get_info()

    expected_result = [
        ["Size", "20240 Bytes (19.77 KiB)"],
        ["Preferred CMM", "0x6172676C 'argl' ArgyllCMS"],
        ["ICC version", "2.2"],
        ["Profile class", "Display device profile"],
        ["Color model", "RGB"],
        ["Profile connection space (PCS)", "XYZ"],
        ["Created", "2016-01-08 00:59:09"],
        ["Platform", "Microsoft"],
        ["Is embedded", "No"],
        ["Can be used independently", "Yes"],
        ["Device", ""],
        ["    Manufacturer", "0x00000000"],
        ["    Model", "0x00000000"],
        ["    Media attributes", "Reflective, Glossy, Positive, Color"],
        ["Default rendering intent", "Media-relative colorimetric"],
        ["PCS illuminant XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585, CCT 5000K)"],
        ["Creator", "0x6172676C 'argl' ArgyllCMS"],
        ["Checksum", "0xCE27ED7FC7C06FBB9492BC1408729D6C"],
        ["    Checksum OK", "Yes"],
        ["Description (ASCII)", "DisplayCAL calibration preset: Default"],
        ["Copyright", "Created with DisplayCAL and Argyll CMS"],
        ["Media white point", ""],
        ["    Illuminant-relative XYZ", " 95.05 100.00 108.91 (xy 0.3127 0.3290)"],
        ["    Illuminant-relative CCT", "6503K"],
        ["        ΔE 2000 to daylight locus", "0.09"],
        ["        ΔE 2000 to blackbody locus", "4.57"],
        ["Media black point", ""],
        ["    Illuminant-relative XYZ", "0.0000 0.0000 0.0000"],
        ["Video card gamma table", ""],
        ["    Bitdepth", "16"],
        ["    Channels", "3"],
        ["    Number of entries per channel", "256"],
        ["    Channel 1 gamma at 50% input", "1.00"],
        ["    Channel 1 minimum", "0.0000%"],
        ["    Channel 1 maximum", "100.00%"],
        ["    Channel 1 unique values", "256 @ 8 Bit"],
        ["    Channel 1 is linear", "Yes"],
        ["    Channel 2 gamma at 50% input", "1.00"],
        ["    Channel 2 minimum", "0.0000%"],
        ["    Channel 2 maximum", "100.00%"],
        ["    Channel 2 unique values", "256 @ 8 Bit"],
        ["    Channel 2 is linear", "Yes"],
        ["    Channel 3 gamma at 50% input", "1.00"],
        ["    Channel 3 minimum", "0.0000%"],
        ["    Channel 3 maximum", "100.00%"],
        ["    Channel 3 unique values", "256 @ 8 Bit"],
        ["    Channel 3 is linear", "Yes"],
        ["Red matrix column", ""],
        ["    Illuminant-relative XYZ", " 41.24  21.26   1.93 (xy 0.6400 0.3300)"],
        ["    PCS-relative XYZ", " 43.60  22.25   1.39 (xy 0.6484 0.3309)"],
        ["Green matrix column", ""],
        ["    Illuminant-relative XYZ", " 35.76  71.52  11.92 (xy 0.3000 0.6000)"],
        ["    PCS-relative XYZ", " 38.51  71.69   9.71 (xy 0.3212 0.5979)"],
        ["Blue matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.05   7.22  95.05 (xy 0.1500 0.0600)"],
        ["    PCS-relative XYZ", " 14.31   6.06  71.39 (xy 0.1559 0.0661)"],
        ["Red tone response curve", ""],
        ["    Number of entries", "256"],
        ["    Transfer function", "Gamma 2.20 100%"],
        ["    Minimum Y", "0.0000"],
        ["    Maximum Y", "100.00"],
        ["Green tone response curve", ""],
        ["    Number of entries", "256"],
        ["    Transfer function", "Gamma 2.20 100%"],
        ["    Minimum Y", "0.0000"],
        ["    Maximum Y", "100.00"],
        ["Blue tone response curve", ""],
        ["    Number of entries", "256"],
        ["    Transfer function", "Gamma 2.20 100%"],
        ["    Minimum Y", "0.0000"],
        ["    Maximum Y", "100.00"],
        ["Characterization target", "[17538 Bytes]"],
        ["Absolute to media relative transform", "Bradford"],
        ["    Matrix", "0.8951 0.2664 -0.1614"],
        ["        ", "-0.7502 1.7135 0.0367"],
        ["        ", "0.0389 -0.0685 1.0296"],
    ]
    assert result == expected_result


def test_hexrepr_is_with_mapping_supplied():
    """Testing DisplayCAL.ICCProfile.hexrepr with a mapping is supplied."""
    test_bytes_string = b"ADBE"
    expected_result = "0x41444245 'ADBE' Adobe"
    result = hexrepr(test_bytes_string, mapping=cmms)
    assert result == expected_result


def test_hexrepr_is_without_mapping_supplied():
    """Testing DisplayCAL.ICCProfile.hexrepr with no mapping is supplied."""
    test_bytes_string = b"ADBE"
    expected_result = "0x41444245 'ADBE'"
    result = hexrepr(test_bytes_string)
    assert result == expected_result


def test_date_time_number_is_working_properly():
    """Testing if DisplayCAL.ICCProfile.dataTimeNumber function is working properly."""
    test_value = b"\x07\xe6\x00\x02\x00\x13\x00\x12\x00*\x002"
    expected_result = datetime.datetime(2022, 2, 19, 18, 42, 50)
    result = dateTimeNumber(test_value)
    assert result == expected_result


def test_icc_profile_tag_is_working_properly():
    """Testing if the ``ICCProfileTag`` class is working properly."""
    tag_data = b"\0\0\0\0"
    tag_signature = "desc"
    tag = ICCProfileTag(tag_data, tag_signature)
    assert tag is not None
    assert tag.tagData == tag_data
    assert tag.tagSignature == tag_signature


def test_text_tag_is_working_properly():
    """Testing if the ``Text`` Tag is working properly."""
    test_data = b"some text"
    t = Text(test_data)
    t.tagData = test_data
    t.tagSignature = "targ"

    assert str(t) == test_data.decode("UTF-8", "replace")


def test_for_issue_31_1(data_files):
    """Test for #31 with user supplied data."""
    icc_profile_path = data_files[
        "BenQ PD2700U-AC19BB79-F553-4582-B898-4247D669C2F1.icc"
    ]
    icc = ICCProfile.ICCProfile(icc_profile_path)
    result = icc.get_info()
    expected_result = [
        ["Size", "532 Bytes (0.52 KiB)"],
        ["Preferred CMM", "0x6170706C 'appl' Apple"],
        ["ICC version", "4.0"],
        ["Profile class", "Display device profile"],
        ["Color model", "RGB"],
        ["Profile connection space (PCS)", "XYZ"],
        ["Created", "2022-03-11 10:47:41"],
        ["Platform", "Apple"],
        ["Is embedded", "No"],
        ["Can be used independently", "Yes"],
        ["Device", ""],
        ["    Manufacturer", "0x4150504C"],
        ["    Model", "0x00000000"],
        ["    Media attributes", "Reflective, Glossy, Positive, Color"],
        ["Default rendering intent", "Perceptual"],
        ["PCS illuminant XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585, CCT 5000K)"],
        ["Creator", "0x6170706C 'appl'"],
        ["Checksum", "0x30E46970EA5C4B1900877653837B62E9"],
        ["    Checksum OK", "Yes"],
        ["Description (ASCII)", "BenQ PD2700U"],
        ["Copyright", "Copyright Apple Inc., 2022"],
        ["Media white point", ""],
        ["    Illuminant-relative XYZ", " 95.05 100.00 108.91 (xy 0.3127 0.3290)"],
        ["    Illuminant-relative CCT", "6503K"],
        ["        ΔE 2000 to daylight locus", "0.09"],
        ["        ΔE 2000 to blackbody locus", "4.57"],
        ["    PCS-relative XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585)"],
        ["    PCS-relative CCT", "5000K"],
        ["Red matrix column", ""],
        ["    Illuminant-relative XYZ", " 41.24  21.26   1.93 (xy 0.6400 0.3300)"],
        ["    PCS-relative XYZ", " 43.61  22.25   1.39 (xy 0.6485 0.3309)"],
        ["Green matrix column", ""],
        ["    Illuminant-relative XYZ", " 35.76  71.51  11.92 (xy 0.3000 0.6000)"],
        ["    PCS-relative XYZ", " 38.51  71.69   9.71 (xy 0.3212 0.5978)"],
        ["Blue matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.05   7.22  95.08 (xy 0.1500 0.0600)"],
        ["    PCS-relative XYZ", " 14.31   6.06  71.41 (xy 0.1559 0.0660)"],
        ["Red tone response curve", "Gamma 1.96"],
        ["Chromatic adaptation transform", "Bradford"],
        ["    Matrix", "1.0479 0.0229 -0.0502"],
        ["        ", "0.0296 0.9905 -0.0171"],
        ["        ", "-0.0092 0.0151 0.7517"],
        ["Blue tone response curve", "Gamma 1.96"],
        ["Green tone response curve", "Gamma 1.96"],
    ]
    assert result == expected_result


def test_for_issue_31_2(data_files):
    """Test for #31 with user supplied data."""
    icc_profile_path = data_files[
        "BenQ SW271 #1 2021-11-17 14-21 2.2 F-S 1xCurve+MTX.icc"
    ]
    icc = ICCProfile.ICCProfile(icc_profile_path)
    result = icc.get_info()
    expected_result = [
        ["Size", "21420 Bytes (20.92 KiB)"],
        ["Preferred CMM", "0x6172676C 'argl' ArgyllCMS"],
        ["ICC version", "2.2"],
        ["Profile class", "Display device profile"],
        ["Color model", "RGB"],
        ["Profile connection space (PCS)", "XYZ"],
        ["Created", "2021-11-17 14:34:47"],
        ["Platform", "Apple"],
        ["Is embedded", "No"],
        ["Can be used independently", "Yes"],
        ["Device", ""],
        ["    Manufacturer", "0x00000000"],
        ["    Model", "0x00000000"],
        ["    Media attributes", "Reflective, Glossy, Positive, Color"],
        ["Default rendering intent", "Media-relative colorimetric"],
        ["PCS illuminant XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585, CCT 5000K)"],
        ["Creator", "0x6172676C 'argl' ArgyllCMS"],
        ["Checksum", "0x00000000000000000000000000000000"],
        ["    Calculated checksum", "0x7C169FE38BEFC4CFCA0606634C381447"],
        ["Description (ASCII)", "BenQ SW271 #1 2021-11-17 14-21 2.2 F-S 1xCurve+MTX"],
        [
            "Copyright",
            "No copyright. Created with DisplayCAL 3.8.9.3 and ArgyllCMS 2.2.1",
        ],
        ["Device model name (ASCII)", "BenQ SW271"],
        ["Luminance", "158.49 cd/m²"],
        ["Media white point", ""],
        ["    Illuminant-relative XYZ", " 94.97 100.00 109.33 (xy 0.3121 0.3286)"],
        ["    Illuminant-relative CCT", "6539K"],
        ["        ΔE 2000 to daylight locus", "0.09"],
        ["        ΔE 2000 to blackbody locus", "4.71"],
        ["Media black point", ""],
        ["    Illuminant-relative XYZ", "0.1312 0.1389 0.1526 (xy 0.3105 0.3285)"],
        ["    Illuminant-relative CCT", "6630K"],
        ["        ΔE 2000 to daylight locus", "1.32"],
        ["        ΔE 2000 to blackbody locus", "5.68"],
        ["Colorants (PCS-relative)", ""],
        ["    Red XYZ", " 61.86  31.08   1.65 (xy 0.6539 0.3286)"],
        ["    Green XYZ", " 20.25  62.90   5.88 (xy 0.2275 0.7065)"],
        ["    Blue XYZ", " 14.58   6.30  75.18 (xy 0.1518 0.0656)"],
        ["Video card gamma table", ""],
        ["    Bitdepth", "16"],
        ["    Channels", "3"],
        ["    Number of entries per channel", "256"],
        ["    Channel 1 gamma at 50% input", "0.95"],
        ["    Channel 1 minimum", "0.0000%"],
        ["    Channel 1 maximum", "100.00%"],
        ["    Channel 1 unique values", "256 @ 8 Bit"],
        ["    Channel 1 is linear", "No"],
        ["    Channel 2 gamma at 50% input", "0.97"],
        ["    Channel 2 minimum", "0.0000%"],
        ["    Channel 2 maximum", "100.00%"],
        ["    Channel 2 unique values", "256 @ 8 Bit"],
        ["    Channel 2 is linear", "No"],
        ["    Channel 3 gamma at 50% input", "0.96"],
        ["    Channel 3 minimum", "0.0000%"],
        ["    Channel 3 maximum", "100.00%"],
        ["    Channel 3 unique values", "256 @ 8 Bit"],
        ["    Channel 3 is linear", "No"],
        ["Red matrix column", ""],
        ["    Illuminant-relative XYZ", " 58.36  29.54   2.19 (xy 0.6478 0.3279)"],
        ["    PCS-relative XYZ", " 61.81  30.99   1.54 (xy 0.6552 0.3285)"],
        ["Green matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.11  63.03   6.66 (xy 0.2063 0.7179)"],
        ["    PCS-relative XYZ", " 20.14  62.84   5.78 (xy 0.2269 0.7080)"],
        ["Blue matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.50   7.42 100.48 (xy 0.1464 0.0587)"],
        ["    PCS-relative XYZ", " 14.47   6.17  75.17 (xy 0.1510 0.0644)"],
        ["Red tone response curve", "Gamma 2.2"],
        ["Green tone response curve", "Gamma 2.2"],
        ["Blue tone response curve", "Gamma 2.2"],
        ["Characterization target", "[17659 Bytes]"],
        ["Characterization device values", "[17659 Bytes]"],
        ["Characterization measurement values", "[17659 Bytes]"],
        ["Absolute to media relative transform", "Bradford"],
        ["    Matrix", "0.8951 0.2664 -0.1614"],
        ["        ", "-0.7502 1.7135 0.0367"],
        ["        ", "0.0389 -0.0685 1.0296"],
        ["Chromaticity (illuminant-relative)", ""],
        ["    Channel 1 (R) xy", "0.6471 0.3272"],
        ["    Channel 2 (G) xy", "0.2076 0.7142"],
        ["    Channel 3 (B) xy", "0.1472 0.0595"],
        ["Metadata", ""],
        ["    CMF_binary", "DisplayCAL"],
        ["    CMF_version", "3.8.9.3"],
        ["    CMF_product", "DisplayCAL"],
        ["    License", "Public Domain"],
        ["    Quality", "high"],
        ["    OPENICC_automatic_generated", "0"],
        ["    DATA_source", "calib"],
        ["    MEASUREMENT_device", "i1 displaypro, colormunki display"],
        ["    prefix", "CMF_\nDATA_\nMEASUREMENT_\nOPENICC_\nACCURACY_\nGAMUT_"],
        ["    ACCURACY_dE76_avg", "0.876532"],
        ["    ACCURACY_dE76_max", "3.995005"],
        ["    ACCURACY_dE76_rms", "1.164627"],
        ["    GAMUT_volume", "1.52172176238"],
        ["    GAMUT_coverage(dci-p3)", "0.8745"],
        ["    GAMUT_coverage(srgb)", "0.9997"],
        ["    GAMUT_coverage(adobe-rgb)", "0.9997"],
    ]
    assert result == expected_result


def test_for_issue_31_3(data_files):
    """Test for issue #31, an ICC files reported to be creating errors."""
    icc_file_path = data_files["SW271 PM PenalNative_KB1_160_2022-03-17.icc"]
    icc = ICCProfile.ICCProfile(icc_file_path)
    result = icc.get_info()
    expected_result = [
        ["Size", "10656 Bytes (10.41 KiB)"],
        ["Preferred CMM", "0x6170706C 'appl' Apple"],
        ["ICC version", "4.0"],
        ["Profile class", "Display device profile"],
        ["Color model", "RGB"],
        ["Profile connection space (PCS)", "XYZ"],
        ["Created", "2022-03-17 15:42:00"],
        ["Platform", "Apple"],
        ["Is embedded", "No"],
        ["Can be used independently", "Yes"],
        ["Device", ""],
        ["    Manufacturer", "0x00000000"],
        ["    Model", "0x00000000"],
        ["    Media attributes", "Reflective, Glossy, Positive, Color"],
        ["Default rendering intent", "Perceptual"],
        ["PCS illuminant XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585, CCT 5000K)"],
        ["Creator", "0x52442020 'RD  '"],
        ["Checksum", "0xC61B1DD94A0ED672203190C72F1EBA61"],
        ["    Checksum OK", "No"],
        ["    Calculated checksum", "0x4D726857D69314B83F8396D2C3DDBBF9"],
        ["Description", ""],
        ["    ASCII", "SW271 PM PenalNative_KB1_160_2022-03-17"],
        ["    Macintosh", "SW271 PM PenalNative_KB1_160_2022-03-17"],
        ["'dscm'", ""],
        ["    en/US", ""],
        ["Characterization target", "[5938 Bytes]"],
        [
            "Copyright",
            "Copyright © 2011-2020 Remote Director, LLC. All Rights Reserved.",
        ],
        ["Media white point", ""],
        ["    Illuminant-relative XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585)"],
        ["    Illuminant-relative CCT", "5000K"],
        ["        ΔE 2000 to daylight locus", "0.08"],
        ["        ΔE 2000 to blackbody locus", "4.73"],
        ["    PCS-relative XYZ", " 96.42 100.00  82.49 (xy 0.3457 0.3585)"],
        ["    PCS-relative CCT", "5000K"],
        ["Media black point", ""],
        ["    Illuminant-relative XYZ", "0.1480 0.1434 0.3220 (xy 0.2413 0.2338)"],
        ["    Illuminant-relative CCT", "746507K"],
        ["    PCS-relative XYZ", "0.1480 0.1434 0.3220 (xy 0.2413 0.2338)"],
        ["    PCS-relative CCT", "746507K"],
        ["Red matrix column", ""],
        ["    Illuminant-relative XYZ", " 58.29  27.40   0.96 (xy 0.6727 0.3162)"],
        ["    PCS-relative XYZ", " 61.66  28.85   0.60 (xy 0.6768 0.3166)"],
        ["Green matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.42  65.25   7.42 (xy 0.2022 0.7163)"],
        ["    PCS-relative XYZ", " 20.43  65.05   6.39 (xy 0.2223 0.7081)"],
        ["Blue matrix column", ""],
        ["    Illuminant-relative XYZ", " 18.33   7.35 100.53 (xy 0.1453 0.0582)"],
        ["    PCS-relative XYZ", " 14.33   6.10  75.50 (xy 0.1494 0.0636)"],
        ["Luminance", "158.49 cd/m²"],
        ["Red tone response curve", "Gamma 2.2"],
        ["Green tone response curve", "Gamma 2.2"],
        ["Blue tone response curve", "Gamma 2.2"],
        ["Chromatic adaptation transform", "Bradford"],
        ["    Matrix", "1.0479 0.0229 -0.0502"],
        ["        ", "0.0296 0.9905 -0.0171"],
        ["        ", "-0.0093 0.0151 0.7517"],
        ["Video card gamma table", ""],
        ["    Bitdepth", "16"],
        ["    Channels", "3"],
        ["    Number of entries per channel", "256"],
        ["    Channel 1 gamma at 50% input", "1.00"],
        ["    Channel 1 minimum", "0.0000%"],
        ["    Channel 1 maximum", "100.00%"],
        ["    Channel 1 unique values", "256 @ 8 Bit"],
        ["    Channel 1 is linear", "Yes"],
        ["    Channel 2 gamma at 50% input", "1.00"],
        ["    Channel 2 minimum", "0.0000%"],
        ["    Channel 2 maximum", "100.00%"],
        ["    Channel 2 unique values", "256 @ 8 Bit"],
        ["    Channel 2 is linear", "Yes"],
        ["    Channel 3 gamma at 50% input", "1.00"],
        ["    Channel 3 minimum", "0.0000%"],
        ["    Channel 3 maximum", "100.00%"],
        ["    Channel 3 unique values", "256 @ 8 Bit"],
        ["    Channel 3 is linear", "Yes"],
        ["'pICS'", "[1275 Bytes]"],
        ["'pMC '", "'pMC ' [1000 Bytes]"],
    ]
    expected_result[6] = [
        "Created",
        strftime("%Y-%m-%d %H:%M:%S", icc.dateTime.timetuple()),
    ]
    expected_result[17] = [
        "Checksum",
        "0x{}".format(binascii.hexlify(icc.ID).upper().decode()),
    ]
    assert result == expected_result


def test_for_issue_50_1(data_files):
    """Testing DictType.tagData() for issue #50."""
    icc_profile_path = data_files[
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
    ]
    iccp = ICCProfile.ICCProfile(icc_profile_path)
    dict_type = iccp.tags["meta"]
    # It seems that we can't reproduce the error with this ICC profile.
    assert dict_type.tagData != ""


def test_gamut_coverage_1(data_files):
    """Test getting GAMUT_coverage metadata"""
    icc_profile_path = data_files[
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
    ]
    iccp = ICCProfile.ICCProfile(icc_profile_path)

    gamuts = (
        ("srgb", "sRGB", ICCProfile.GAMUT_VOLUME_SRGB),
        ("adobe-rgb", "Adobe RGB", ICCProfile.GAMUT_VOLUME_ADOBERGB),
        ("dci-p3", "DCI P3", ICCProfile.GAMUT_VOLUME_SMPTE431_P3),
    )
    cinfo = []
    for key, name, _volume in gamuts:
        gamut_coverage = float(
            iccp.tags.meta.getvalue("GAMUT_coverage(%s)" % key)
        )
        if gamut_coverage:
            cinfo.append("%.1f%% %s" % (gamut_coverage * 100, name))
    assert cinfo == ['99.7% sRGB', '99.1% Adobe RGB', '93.0% DCI P3']


def test_gamut_volume_1(data_files):
    """Test getting GAMUT_volume metadata"""
    icc_profile_path = data_files[
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
    ]
    iccp = ICCProfile.ICCProfile(icc_profile_path)

    gamuts = (
        ("srgb", "sRGB", ICCProfile.GAMUT_VOLUME_SRGB),
        ("adobe-rgb", "Adobe RGB", ICCProfile.GAMUT_VOLUME_ADOBERGB),
        ("dci-p3", "DCI P3", ICCProfile.GAMUT_VOLUME_SMPTE431_P3),
    )
    vinfo = []
    gamut_volume = float(iccp.tags.meta.getvalue("GAMUT_volume"))
    for _key, name, volume in gamuts:
        vinfo.append(
            "%.1f%% %s"
            % (
                gamut_volume
                * ICCProfile.GAMUT_VOLUME_SRGB
                / volume
                * 100,
                name,
            )
        )
    assert vinfo == ['169.3% sRGB', '116.7% Adobe RGB', '120.0% DCI P3']


def test_set_gamut_metadata_1(data_files):
    """Test ICCProfile.set_gamut_metadata() method."""
    icc_profile_path = data_files[
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
    ]
    iccp = ICCProfile.ICCProfile(icc_profile_path)

    assert iccp.tags.meta["GAMUT_volume"] == '1.6934613892142165'
    assert iccp.tags.meta["GAMUT_coverage(srgb)"] == '0.9967'
    assert iccp.tags.meta["GAMUT_coverage(dci-p3)"] == '0.9296'
    assert iccp.tags.meta["GAMUT_coverage(adobe-rgb)"] == '0.9906'

    gamut_volume = 1.695547156240974
    gamut_coverage = {'srgb': 0.9973000000000001, 'dci-p3': 0.9269, 'adobe-rgb': 0.9897}
    iccp.set_gamut_metadata(gamut_volume=gamut_volume, gamut_coverage=gamut_coverage)

    assert iccp.tags.meta["GAMUT_volume"] == gamut_volume
    assert iccp.tags.meta["GAMUT_coverage(srgb)"] == gamut_coverage['srgb']
    assert iccp.tags.meta["GAMUT_coverage(dci-p3)"] == gamut_coverage['dci-p3']
    assert iccp.tags.meta["GAMUT_coverage(adobe-rgb)"] == gamut_coverage['adobe-rgb']


def test_MultiLocalizedUnicodeType_str_method(data_files):
    """Test for #151."""
    mlut = MultiLocalizedUnicodeType()
    assert str(mlut) == ""


def test_dict_type_to_json():
    """Test DictType.to_json() method."""
    d = DictType()
    d.update(
        {
            "\xab": "\x00",
            "\xaf": "\x12",
        }
    )
    expected_result = '{"\\u00ab": "\\u0000", "\\u00af": "\\u0012"}'
    assert d.to_json() == expected_result


def test_issue_185_parsing_of_ref_srgb_profile_from_argyllcms(argyll):
    """Testing for issue #185, opening sRGB.icm from ArgyllCMS raises TypeError."""
    srgb_profile_path = argyll / ".." / "ref" / "sRGB.icm"
    icc_profile = ICCProfile.ICCProfile(srgb_profile_path)
    # the following should not raise an error
    info = icc_profile.get_info()
