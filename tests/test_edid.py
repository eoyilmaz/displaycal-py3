"""This module contains tests for the EDID parsing functionality in DisplayCAL."""

import binascii
import codecs
import json

import pytest

from DisplayCAL import config, real_display_size_mm
from DisplayCAL.config import getcfg
from DisplayCAL.dev.mocks import check_call
from DisplayCAL.edid import (
    get_display_name_from_system_profiler,
    get_edid,
    get_edid_darwin,
    get_edid_from_xrandr,
    parse_edid,
    parse_manufacturer_id,
)
from tests.data.display_data import DisplayData


# @pytest.mark.skipif(
#     platform.system() == "Darwin", reason="Not working as expected on MacOS"
# )
def test_get_edid_1(clear_displays, monkeypatch, patch_subprocess, data_files):
    """Testing DisplayCAL.colord.device_id_from_edid() function."""
    # patch xrandr
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.edid.sys.platform", "linux")
    monkeypatch.setattr("DisplayCAL.edid.which", lambda x: "xrandr")
    xrandr_data_file_name = "xrandr_output_4.txt"
    with open(data_files[xrandr_data_file_name], "rb") as xrandr_data_file:
        xrandr_data = xrandr_data_file.read()
    patch_subprocess.output["xrandr--verbose"] = xrandr_data

    with (
        check_call(
            config,
            "getcfg",
            DisplayData.CFG_DATA,
            call_count=-1,
        ),
        check_call(
            real_display_size_mm,
            "_enumerate_displays",
            DisplayData.enumerate_displays(),
            call_count=-1,
        ),
    ):
        result = get_edid(0)

    assert isinstance(result, dict)
    assert "blue_x" in result
    assert isinstance(result["blue_y"], float)
    assert "blue_y" in result
    assert isinstance(result["blue_y"], float)
    assert "checksum" in result
    assert result["checksum"] > 0
    assert "checksum_valid" in result
    assert result["checksum_valid"] is True
    assert "edid" in result
    assert isinstance(result["edid"], bytes)
    assert "edid_revision" in result
    assert isinstance(result["edid_revision"], int)
    assert "edid_version" in result
    assert isinstance(result["edid_version"], int)
    assert "ext_flag" in result
    assert isinstance(result["ext_flag"], int)
    assert "features" in result
    assert isinstance(result["features"], int)
    assert "gamma" in result
    assert isinstance(result["gamma"], float)
    assert "green_x" in result
    assert isinstance(result["green_x"], float)
    assert "green_y" in result
    assert isinstance(result["green_y"], float)
    assert "hash" in result
    assert isinstance(result["hash"], str)
    assert "header" in result
    assert isinstance(result["header"], bytes)
    assert "manufacturer" in result
    assert isinstance(result["manufacturer"], str)
    assert "manufacturer_id" in result
    assert isinstance(result["manufacturer_id"], str)
    assert "max_h_size_cm" in result
    assert isinstance(result["max_h_size_cm"], int)
    assert "max_v_size_cm" in result
    assert isinstance(result["max_v_size_cm"], int)
    assert "product_id" in result
    assert isinstance(result["product_id"], int)
    assert "red_x" in result
    assert isinstance(result["red_x"], float)
    assert "red_y" in result
    assert isinstance(result["red_y"], float)
    assert "serial_32" in result
    assert isinstance(result["serial_32"], int)
    assert "week_of_manufacture" in result
    assert isinstance(result["week_of_manufacture"], int)
    assert "white_x" in result
    assert isinstance(result["white_x"], float)
    assert "white_y" in result
    assert isinstance(result["white_y"], float)
    assert "year_of_manufacture" in result
    assert isinstance(result["year_of_manufacture"], int)


# def test_get_edid_3(clear_displays):
#     """Testing DisplayCAL.colord.device_id_from_edid() function."""
#     config.initcfg()
#     display = RDSMM.get_display(0)
#     edid = display.get("edid")
#     assert isinstance(edid, str)
#     edid = edid.encode("utf-8")
#
#     # assert len(edid) == 256
#     assert edid == (
#         b"\x00\xff\xff\xff\xff\xff\xff\x00\x10\xac\xe0@L405\x05\x1b\x01\x04\xb57\x1fx:U"
#         b"\xc5\xafO3\xb8%\x0bPT\xa5K\x00qO\xa9@\x81\x80\xd1\xc0\x01\x01\x01\x01\x01\x01"
#         b"\x01\x01V^\x00\xa0\xa0\xa0)P0 5\x00)7!\x00\x00\x1a\x00\x00\x00\xff\x00"
#         b"TYPR371U504L\n\x00\x00\x00\xfc\x00DELL UP2516D\n\x00\x00\x00\xfd\x002K\x1eX"
#         b"\x19\x01\n      \x01,\x02\x03\x1c\xf1O\x90\x05\x04\x03\x02\x07\x16\x01\x06"
#         b"\x11\x12\x15\x13\x14\x1f#\t\x1f\x07\x83\x01\x00\x00\x02:\x80\x18q8-@X,E"
#         b"\x00)7!\x00\x00\x1e~9\x00\xa0\x808\x1f@0 :\x00)7!\x00\x00\x1a\x01\x1d\x00rQ"
#         b"\xd0\x1e n(U\x00)7!\x00\x00\x1e\xbf\x16\x00\xa0\x808\x13@0 :\x00)7!\x00\x00"
#         b"\x1a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
#         b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x86"
#     )


_VP2768A_HEX = (
    "00ffffffffffff005a633a7a0f010101"
    "311e0104b53c22783bb091ab524ea026"
    "0f5054bfef80e1c0d100d1c0b300a940"
    "8180810081c0565e00a0a0a029503020"
    "350055502100001a000000ff00573855"
    "3230343930303130340a000000fd0018"
    "4b0f5a1e000a202020202020000000fc"
    "00565032373638610a2020202020017b"
    "020322f155901f05145a5904131e1d0f"
    "0e07061211161503020123097f078301"
    "0000023a801871382d40582c45005550"
    "2100001e011d8018711c1620582c2500"
    "55502100009e023a80d072382d40102c"
    "458055502100001e011d007251d01e20"
    "6e28550055502100001e584d00b8a138"
    "1440f82c4b0055502100001e000000d2"
)
_VP2768A_EDID = binascii.unhexlify(_VP2768A_HEX)

_U28E590_HEX = (
    "00ffffffffffff004c2d4d0c46584d30"
    "231a0104b53d23783a5fb1a2574fa228"
    "0f5054bfef80714f810081c08180a9c0"
    "b300950001014dd000a0f0703e803020"
    "35005f592100001a000000fd00384b1e"
    "873c000a202020202020000000fc0055"
    "3238453539300a2020202020000000ff"
    "00485450483930303130330a20200166"
    "02030ef041102309070783010000023a"
    "801871382d40582c45005f592100001e"
    "565e00a0a0a02950302035005f592100"
    "001a04740030f2705a80b0588a005f59"
    "2100001e000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000052"
)
_U28E590_EDID = binascii.unhexlify(_U28E590_HEX)

_ACER_ET430K_HEX = (
    "00ffffffffffff0004725805436e6072"
    "1a1b0103805e35782aa191a9544d9c26"
    "0f5054bfef80714f8140818081c08100"
    "9500b300d1c04dd000a0f0703e803020"
    "3500ad113200001a565e00a0a0a02950"
    "2f203500ad113200001a000000fd0032"
    "3c1e8c3c000a202020202020000000fc"
    "00416365722045543433304b0a200129"
    "020341f1506101600304121305141f10"
    "0706026b5f23090707830100006b030c"
    "002000383c2000200167d85dc4017880"
    "00e305e001e40f050000e60607016060"
    "45023a801871382d40582c4500ad1132"
    "00001e011d007251d01e206e285500ad"
    "113200001e8c0ad08a20e02d10103e96"
    "00ad1132000018000000000000000088"
)
_ACER_ET430K_EDID = binascii.unhexlify(_ACER_ET430K_HEX)

_VP2768A_RESULT = {
    "edid": _VP2768A_EDID,
    "hash": "c809a7de5f47319307d2358f3d578078",
    "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
    "manufacturer": "ViewSonic Corporation",
    "manufacturer_id": "VSC",
    "product_id": 31290,
    "serial_32": 16843023,
    "serial_ascii": "W8U204900104",
    "week_of_manufacture": 49,
    "year_of_manufacture": 2020,
    "edid_version": 1,
    "edid_revision": 4,
    "max_h_size_cm": 60,
    "max_v_size_cm": 34,
    "gamma": 2.2,
    "features": 59,
    "red_x": 0.669921875,
    "red_y": 0.3232421875,
    "green_x": 0.3046875,
    "green_y": 0.625,
    "blue_x": 0.150390625,
    "blue_y": 0.0595703125,
    "white_x": 0.3125,
    "white_y": 0.3291015625,
    "ext_flag": 1,
    "checksum": 123,
    "checksum_valid": True,
    "monitor_name": "VP2768a",
}


@pytest.mark.parametrize(
    "xrandr_data_file_name,dispwin_data_file_name,getcfg_displays_output,display_no,expected_result",
    [
        [
            "xrandr_output_1.txt",
            "dispwin_output_1.txt",
            ["DP-4 @ 0, 0, 2560x1440 [PRIMARY]"],
            0,
            _VP2768A_RESULT,
        ],
        [
            "xrandr_output_2.txt",
            "dispwin_output_2.txt",
            ["DP-4 @ 0, 0, 2560x1440 [PRIMARY]", "DP-2 @ 2160, 0, 3840x2160"],
            0,
            _VP2768A_RESULT,
        ],
        [
            "xrandr_output_2.txt",
            "dispwin_output_2.txt",
            ["DP-4 @ 0, 0, 2560x1440 [PRIMARY]", "DP-2 @ 2160, 0, 3840x2160"],
            1,
            {
                "edid": _U28E590_EDID,
                "hash": "a719d259d3e729176b9f56e1c875e8c1",
                "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
                "manufacturer": "Samsung Electric Company",
                "manufacturer_id": "SAM",
                "product_id": 3149,
                "serial_32": 810375238,
                "serial_ascii": "HTPH900103",
                "week_of_manufacture": 35,
                "year_of_manufacture": 2016,
                "edid_version": 1,
                "edid_revision": 4,
                "max_h_size_cm": 61,
                "max_v_size_cm": 35,
                "gamma": 2.2,
                "features": 58,
                "red_x": 0.6337890625,
                "red_y": 0.3408203125,
                "green_x": 0.3115234375,
                "green_y": 0.6357421875,
                "blue_x": 0.158203125,
                "blue_y": 0.0615234375,
                "white_x": 0.3125,
                "white_y": 0.3291015625,
                "ext_flag": 1,
                "checksum": 102,
                "checksum_valid": True,
                "monitor_name": "U28E590",
            },
        ],
        [
            "xrandr_output_3.txt",
            "dispwin_output_3.txt",
            ["HDMI-A-0 @ 0, 0, 3840x2160 [PRIMARY]"],
            0,
            {
                "edid": _ACER_ET430K_EDID,
                "hash": "23d07c7921998829a4b68374e1000cfe",
                "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
                "manufacturer": "Acer Technologies",
                "manufacturer_id": "ACR",
                "product_id": 1368,
                "serial_32": 1918922307,
                "week_of_manufacture": 26,
                "year_of_manufacture": 2017,
                "edid_version": 1,
                "edid_revision": 3,
                "max_h_size_cm": 94,
                "max_v_size_cm": 53,
                "gamma": 2.2,
                "features": 42,
                "red_x": 0.662109375,
                "red_y": 0.330078125,
                "green_x": 0.30078125,
                "green_y": 0.6103515625,
                "blue_x": 0.150390625,
                "blue_y": 0.0595703125,
                "white_x": 0.3125,
                "white_y": 0.3291015625,
                "ext_flag": 1,
                "checksum": 41,
                "checksum_valid": True,
                "monitor_name": "Acer ET430K",
            },
        ],
        # ArgyllCMS >= 3.3.0 reports just the xrandr output name ("DP-2"), but
        # xrandr may show the output as "Monitor 1, Output DP-2 connected".
        # Verify that the ", Output <name> connected" fallback matching works.
        [
            "xrandr_output_4.txt",
            "dispwin_output_5.txt",
            ["DP-2 @ 0, 0, 1280x1024 [PRIMARY]"],
            0,
            _VP2768A_RESULT,
        ],
    ],
)
def test_get_edid_4(
    monkeypatch,
    patch_subprocess,
    patch_argyll_util,
    clear_displays,
    data_files,
    xrandr_data_file_name,
    dispwin_data_file_name,
    getcfg_displays_output,
    display_no,
    expected_result,
):
    """DisplayCAL.edid.get_edid() gets the EDID data from xrandr --verbose command."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.real_display_size_mm.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.real_display_size_mm.sys.platform", "linux")
    monkeypatch.setattr("DisplayCAL.edid.sys.platform", "linux")
    monkeypatch.setattr("DisplayCAL.edid.which", lambda x: "xrandr")

    # patch xrandr
    with open(data_files[xrandr_data_file_name], "rb") as xrandr_data_file:
        xrandr_data = xrandr_data_file.read()
    patch_subprocess.output["xrandr--verbose"] = xrandr_data

    # patch dispwin
    with open(data_files[dispwin_data_file_name], "rb") as dispwin_data_file:
        dispwin_data = dispwin_data_file.read()
    patch_subprocess.output["dispwin-v-d0"] = dispwin_data

    # patch real_display_size_mm.getcfg("displays")
    orig_getcfg = getcfg

    def patched_getcfg(config_value):
        if config_value == "displays":
            return getcfg_displays_output + [
                "Web @ localhost",
                "madVR",
                "Prisma",
                "Resolve",
                "Untethered",
            ]
        return orig_getcfg(config_value)

    monkeypatch.setattr("DisplayCAL.config.getcfg", patched_getcfg)

    result = get_edid(display_no=display_no)
    assert result == expected_result


def test_parse_edid_1():
    """Testing DisplayCAL.edid.parse_edid() function."""
    raw_edid = (
        b"\x00\xff\xff\xff\xff\xff\xff\x00\x10\xac\xe0@L405\x05\x1b\x01\x04\xb57\x1fx:U"
        b"\xc5\xafO3\xb8%\x0bPT\xa5K\x00qO\xa9@\x81\x80\xd1\xc0\x01\x01\x01\x01\x01\x01"
        b"\x01\x01V^\x00\xa0\xa0\xa0)P0 5\x00)7!\x00\x00\x1a\x00\x00\x00\xff\x00"
        b"TYPR371U504L\n\x00\x00\x00\xfc\x00DELL UP2516D\n\x00\x00\x00\xfd\x002K\x1eX"
        b"\x19\x01\n      \x01,\x02\x03\x1c\xf1O\x90\x05\x04\x03\x02\x07\x16\x01\x06"
        b"\x11\x12\x15\x13\x14\x1f#\t\x1f\x07\x83\x01\x00\x00\x02:\x80\x18q8-@X,E"
        b"\x00)7!\x00\x00\x1e~9\x00\xa0\x808\x1f@0 :\x00)7!\x00\x00\x1a\x01\x1d\x00rQ"
        b"\xd0\x1e n(U\x00)7!\x00\x00\x1e\xbf\x16\x00\xa0\x808\x13@0 :\x00)7!\x00\x00"
        b"\x1a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x86"
    )
    result = parse_edid(raw_edid)
    expected_result = {
        "blue_x": 0.1474609375,
        "blue_y": 0.04296875,
        "checksum": 44,
        "checksum_valid": True,
        "edid": b"\x00\xff\xff\xff\xff\xff\xff\x00\x10\xac\xe0@L405\x05\x1b\x01\x04"
        b"\xb57\x1fx:U\xc5\xafO3\xb8%\x0bPT\xa5K\x00qO\xa9@\x81\x80"
        b"\xd1\xc0\x01\x01\x01\x01\x01\x01\x01\x01V^\x00\xa0\xa0\xa0)P0 "
        b"5\x00)7!\x00\x00\x1a\x00\x00\x00\xff\x00TYPR371U504L\n\x00\x00"
        b"\x00\xfc\x00DELL UP2516D\n\x00\x00\x00\xfd\x002K\x1eX\x19\x01\n    "
        b"  \x01,\x02\x03\x1c\xf1O\x90\x05\x04\x03\x02\x07\x16\x01\x06\x11\x12"
        b"\x15\x13\x14\x1f#\t\x1f\x07\x83\x01\x00\x00\x02:\x80\x18q8-@X,E\x00"
        b")7!\x00\x00\x1e~9\x00\xa0\x808\x1f@0 :\x00)7!\x00\x00\x1a"
        b"\x01\x1d\x00rQ\xd0\x1e n(U\x00)7!\x00\x00\x1e\xbf\x16\x00\xa0\x808"
        b"\x13@0 :\x00)7!\x00\x00\x1a\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x86",
        "edid_revision": 4,
        "edid_version": 1,
        "ext_flag": 1,
        "features": 58,
        "gamma": 2.2,
        "green_x": 0.2001953125,
        "green_y": 0.7197265625,
        "hash": "40cf706d53476076b828fb8a78af796d",
        "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
        "manufacturer": "Dell, Inc.",
        "manufacturer_id": "DEL",
        "max_h_size_cm": 55,
        "max_v_size_cm": 31,
        "monitor_name": "DELL UP2516D",
        "product_id": 16608,
        "red_x": 0.6845703125,
        "red_y": 0.3095703125,
        "serial_32": 892351564,
        "serial_ascii": "TYPR371U504L",
        "week_of_manufacture": 5,
        "white_x": 0.3134765625,
        "white_y": 0.3291015625,
        "year_of_manufacture": 2017,
    }
    assert result == expected_result


def test_parse_edid_2():
    """Testing DisplayCAL.edid.parse_edid() function. for #50."""
    xrandr_edid_data = """
                00ffffffffffff0004725805436e6072
                1a1b0103805e35782aa191a9544d9c26
                0f5054bfef80714f8140818081c08100
                9500b300d1c04dd000a0f0703e803020
                3500ad113200001a565e00a0a0a02950
                2f203500ad113200001a000000fd0032
                3c1e8c3c000a202020202020000000fc
                00416365722045543433304b0a200129
                020341f1506101600304121305141f10
                0706026b5f23090707830100006b030c
                002000383c2000200167d85dc4017880
                00e305e001e40f050000e60607016060
                45023a801871382d40582c4500ad1132
                00001e011d007251d01e206e285500ad
                113200001e8c0ad08a20e02d10103e96
                00ad1132000018000000000000000088"""
    xrandr_edid_data = "".join(xrandr_edid_data.split("\n")).replace(" ", "").strip()
    raw_edid = codecs.decode(xrandr_edid_data, "hex")
    result = parse_edid(raw_edid)
    expected_result = {
        "blue_x": 0.150390625,
        "blue_y": 0.0595703125,
        "checksum": 41,
        "checksum_valid": True,
        "edid": b"\x00\xff\xff\xff\xff\xff\xff\x00\x04rX\x05Cn`r\x1a\x1b\x01\x03"
        b"\x80^5x*\xa1\x91\xa9TM\x9c&\x0fPT\xbf\xef\x80qO\x81@\x81\x80"
        b"\x81\xc0\x81\x00\x95\x00\xb3\x00\xd1\xc0M\xd0\x00\xa0\xf0p>\x800 "
        b"5\x00\xad\x112\x00\x00\x1aV^\x00\xa0\xa0\xa0)P/ 5\x00\xad\x112\x00"
        b"\x00\x1a\x00\x00\x00\xfd\x002<\x1e\x8c<\x00\n      \x00\x00\x00\xfc"
        b"\x00Acer ET430K\n \x01)\x02\x03A\xf1Pa\x01`\x03\x04\x12\x13"
        b"\x05\x14\x1f\x10\x07\x06\x02k_#\t\x07\x07\x83\x01\x00\x00k\x03\x0c"
        b"\x00 \x008< \x00 \x01g\xd8]\xc4\x01x\x80\x00\xe3\x05\xe0"
        b"\x01\xe4\x0f\x05\x00\x00\xe6\x06\x07\x01``E\x02:\x80\x18q8-@X,E"
        b"\x00\xad\x112\x00\x00\x1e\x01\x1d\x00rQ\xd0\x1e n(U\x00\xad"
        b"\x112\x00\x00\x1e\x8c\n\xd0\x8a \xe0-\x10\x10>\x96\x00\xad\x112"
        b"\x00\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00\x88",
        "edid_revision": 3,
        "edid_version": 1,
        "ext_flag": 1,
        "features": 42,
        "gamma": 2.2,
        "green_x": 0.30078125,
        "green_y": 0.6103515625,
        "hash": "23d07c7921998829a4b68374e1000cfe",
        "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
        "manufacturer": "Acer Technologies",
        "manufacturer_id": "ACR",
        "max_h_size_cm": 94,
        "max_v_size_cm": 53,
        "monitor_name": "Acer ET430K",
        "product_id": 1368,
        "red_x": 0.662109375,
        "red_y": 0.330078125,
        "serial_32": 1918922307,
        "week_of_manufacture": 26,
        "white_x": 0.3125,
        "white_y": 0.3291015625,
        "year_of_manufacture": 2017,
    }
    assert result == expected_result


def test_parse_edid_3():
    """Testing DisplayCAL.edid.parse_edid() function. for #119."""
    xrandr_edid_data = """
        00ffffffffffff0009e5120800000000
        1f1c0104a5221378030980955c5a9129
        21505400000001010101010101010101
        010101010101033a803671381e403020
        360058c21000001a0000000000000000
        00000000000000000000000000fe0042
        4f452043510a202020202020000000fe
        004e5431353646484d2d4e36310a00ed
    """
    xrandr_edid_data = "".join(xrandr_edid_data.split("\n")).replace(" ", "").strip()
    raw_edid = codecs.decode(xrandr_edid_data, "hex")
    expected_raw_edid = (
        b"\x00\xff\xff\xff\xff\xff\xff\x00\t\xe5\x12\x08\x00\x00\x00\x00"
        b'\x1f\x1c\x01\x04\xa5"\x13x\x03\t\x80\x95\\Z\x91)!PT\x00'
        b"\x00\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
        b"\x01\x01\x03:\x806q8\x1e@0 6\x00X\xc2\x10\x00\x00\x1a"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\xfe\x00BOE CQ\n      \x00\x00\x00\xfe\x00NT1"
        b"56FHM-N61\n\x00\xed"
    )
    assert raw_edid == expected_raw_edid
    assert len(raw_edid) == 128

    result = parse_edid(raw_edid)
    expected_result = {
        "ascii": "NT156FHM-N61",
        "blue_x": 0.162109375,
        "blue_y": 0.12890625,
        "checksum": 237,
        "checksum_valid": True,
        "edid": b"\x00\xff\xff\xff\xff\xff\xff\x00\t\xe5\x12\x08\x00\x00\x00\x00"
        b'\x1f\x1c\x01\x04\xa5"\x13x\x03\t\x80\x95\\Z\x91)!PT\x00'
        b"\x00\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
        b"\x01\x01\x03:\x806q8\x1e@0 6\x00X\xc2\x10\x00\x00\x1a"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\xfe\x00BOE CQ\n      \x00\x00\x00\xfe\x00NT1"
        b"56FHM-N61\n\x00\xed",
        "edid_revision": 4,
        "edid_version": 1,
        "ext_flag": 0,
        "features": 3,
        "gamma": 2.2,
        "green_x": 0.353515625,
        "green_y": 0.5673828125,
        "hash": "db067630cf478ff8638db83f2724a40b",
        "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
        "manufacturer": "BOE",
        "manufacturer_id": "BOE",
        "max_h_size_cm": 34,
        "max_v_size_cm": 19,
        "product_id": 2066,
        "red_x": 0.58203125,
        "red_y": 0.359375,
        "serial_32": 0,
        "week_of_manufacture": 31,
        "white_x": 0.3125,
        "white_y": 0.328125,
        "year_of_manufacture": 2018,
    }
    assert result == expected_result


def test_parse_edid_4():
    """Testing DisplayCAL.edid.parse_edid() function. for #119."""
    raw_edid = (
        b"\x00\xc3\xbf\xc3\xbf\xc3\xbf\xc3\xbf\xc3\xbf\xc3\xbf\x00\x10\xc2"
        b"\xac\xc3\xa0@L405\x05\x1b\x01\x04\xc2\xb57\x1fx:U\xc3\x85\xc2\xafO3\xc2\xb8%"
        b"\x0bPT\xc2\xa5K\x00qO\xc2\xa9@\xc2\x81\xc2\x80\xc3\x91\xc3\x80"
        b"\x01\x01\x01\x01\x01\x01\x01\x01V^\x00\xc2\xa0\xc2\xa0\xc2\xa0)P0 5\x00)"
        b"7!\x00\x00\x1a\x00\x00\x00\xc3\xbf\x00TYPR371U504L\n\x00\x00\x00\xc3"
        b"\xbc\x00DELL UP2516D\n\x00\x00\x00\xc3\xbd\x002K\x1eX\x19\x01\n      \x01,"
        b"\x02\x03\x1c\xc3\xb1O\xc2\x90\x05\x04\x03\x02\x07\x16\x01\x06"
        b"\x11\x12\x15\x13\x14\x1f#\t\x1f\x07\xc2\x83\x01\x00\x00\x02:\xc2\x80\x18q8-@"
        b"X,E\x00)7!\x00\x00\x1e~9\x00\xc2\xa0\xc2\x808\x1f@0 :\x00)7!\x00"
        b"\x00\x1a\x01\x1d\x00rQ\xc3\x90\x1e n(U\x00)7!\x00\x00\x1e\xc2\xbf\x16"
        b"\x00\xc2\xa0\xc2\x808\x13@0 :\x00)7!\x00\x00\x1a\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\xc2\x86"
    )
    result = parse_edid(raw_edid)
    expected_result = {
        "blue_x": 0.1474609375,
        "blue_y": 0.04296875,
        "checksum": 44,
        "checksum_valid": True,
        "edid": (
            b"\x00\xff\xff\xff\xff\xff\xff\x00\x10\xac\xe0@L405\x05\x1b\x01\x04"
            b"\xb57\x1fx:U\xc5\xafO3\xb8%\x0bPT\xa5K\x00qO\xa9@\x81\x80"
            b"\xd1\xc0\x01\x01\x01\x01\x01\x01\x01\x01V^\x00\xa0\xa0\xa0)P0 "
            b"5\x00)7!\x00\x00\x1a\x00\x00\x00\xff\x00TYPR371U504L\n\x00\x00"
            b"\x00\xfc\x00DELL UP2516D\n\x00\x00\x00\xfd\x002K\x1eX\x19\x01\n    "
            b"  \x01,\x02\x03\x1c\xf1O\x90\x05\x04\x03\x02\x07\x16\x01\x06\x11\x12"
            b"\x15\x13\x14\x1f#\t\x1f\x07\x83\x01\x00\x00\x02:\x80\x18q8-@X,E\x00"
            b")7!\x00\x00\x1e~9\x00\xa0\x808\x1f@0 :\x00)7!\x00\x00\x1a"
            b"\x01\x1d\x00rQ\xd0\x1e n(U\x00)7!\x00\x00\x1e\xbf\x16\x00\xa0\x808"
            b"\x13@0 :\x00)7!\x00\x00\x1a\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x86"
        ),
        "edid_revision": 4,
        "edid_version": 1,
        "ext_flag": 1,
        "features": 58,
        "gamma": 2.2,
        "green_x": 0.2001953125,
        "green_y": 0.7197265625,
        "hash": "40cf706d53476076b828fb8a78af796d",
        "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
        "manufacturer": "Dell, Inc.",
        "manufacturer_id": "DEL",
        "max_h_size_cm": 55,
        "max_v_size_cm": 31,
        "monitor_name": "DELL UP2516D",
        "product_id": 16608,
        "red_x": 0.6845703125,
        "red_y": 0.3095703125,
        "serial_32": 892351564,
        "serial_ascii": "TYPR371U504L",
        "week_of_manufacture": 5,
        "white_x": 0.3134765625,
        "white_y": 0.3291015625,
        "year_of_manufacture": 2017,
    }
    assert result == expected_result


def test_parse_edid_5():
    """Testing DisplayCAL.edid.parse_edid() function with a 384 byte EDID."""
    xrandr_edid_data = """
                00ffffffffffff004c2d5c10564a5843
                0c1f0104b53c22783a2eb5ae4f46a626
                115054bfef8081c0810081809500a9c0
                b300714f0101565e00a0a0a029503020
                350055502100001a000000fd0832f01e
                6762000a202020202020000000fc004c
                433237473778540a20202020000000ff
                0048345a523330323437300a20200231
                02031cf147903f1f0413120323090707
                83010000e305c000e30605015a8780a0
                70384d403020350055502100001a23e8
                8078703887401c20980c55502100001a
                6fc200a0a0a055503020350055502100
                001a98e200a0a0a02950084035005550
                2100001a023a801871382d40582c4500
                56502100001e00000000000000000088
                7012170000030114e17b0188ff099f00
                2f801f009f053100020004008a000000
                00000000000000000000000000000000
                00000000000000000000000000000000
                00000000000000000000000000000000
                00000000000000000000000000000000
                00000000000000000000000000000000
                00000000000000000000000000000090"""
    xrandr_edid_data = "".join(xrandr_edid_data.split("\n")).replace(" ", "").strip()
    raw_edid = codecs.decode(xrandr_edid_data, "hex")
    result = parse_edid(raw_edid)
    expected_result = {
        "blue_x": 0.150390625,
        "blue_y": 0.0693359375,
        "checksum": 49,
        "checksum_valid": True,
        "edid": b'\x00\xff\xff\xff\xff\xff\xff\x00L-\\\x10VJXC\x0c\x1f\x01\x04\xb5<"x'
        b":.\xb5\xaeOF\xa6&\x11PT\xbf\xef\x80\x81\xc0\x81\x00\x81\x80"
        b"\x95\x00\xa9\xc0\xb3\x00qO\x01\x01V^\x00\xa0\xa0\xa0)P0 5\x00UP"
        b"!\x00\x00\x1a\x00\x00\x00\xfd\x082\xf0\x1egb\x00\n      \x00\x00"
        b"\x00\xfc\x00LC27G7xT\n    \x00\x00\x00\xff\x00H4ZR302470\n  \x021"
        b"\x02\x03\x1c\xf1G\x90?\x1f\x04\x13\x12\x03#\t\x07\x07"
        b"\x83\x01\x00\x00\xe3\x05\xc0\x00\xe3\x06\x05\x01Z\x87\x80\xa0p8M@"
        b"0 5\x00UP!\x00\x00\x1a#\xe8\x80xp8\x87@\x1c \x98\x0cUP!\x00\x00\x1a"
        b"o\xc2\x00\xa0\xa0\xa0UP0 5\x00UP!\x00\x00\x1a\x98\xe2"
        b"\x00\xa0\xa0\xa0)P\x08@5\x00UP!\x00\x00\x1a\x02:\x80\x18q8-@X,E\x00"
        b"VP!\x00\x00\x1e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x88p\x12\x17\x00"
        b"\x00\x03\x01\x14\xe1{\x01\x88\xff\t\x9f\x00/\x80\x1f\x00"
        b"\x9f\x051\x00\x02\x00\x04\x00\x8a\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x90",
        "edid_revision": 4,
        "edid_version": 1,
        "ext_flag": 2,
        "features": 58,
        "gamma": 2.2,
        "green_x": 0.2763671875,
        "green_y": 0.650390625,
        "hash": "c0c868ec1d10057c60a6f0cd40282568",
        "header": b"\x00\xff\xff\xff\xff\xff\xff\x00",
        "manufacturer": "Samsung Electric Company",
        "manufacturer_id": "SAM",
        "max_h_size_cm": 60,
        "max_v_size_cm": 34,
        "monitor_name": "LC27G7xT",
        "product_id": 4188,
        "red_x": 0.6796875,
        "red_y": 0.310546875,
        "serial_32": 1129859670,
        "serial_ascii": "H4ZR302470",
        "week_of_manufacture": 12,
        "white_x": 0.3134765625,
        "white_y": 0.3291015625,
        "year_of_manufacture": 2021,
    }
    assert result == expected_result


def test_parse_edid_6():
    """parse_edid() with test data."""
    edid = DisplayData.DISPLAY_DATA_2["edid"]
    result = parse_edid(edid)
    assert result == DisplayData.DISPLAY_DATA_2


def test_parse_manufacturer_id_1():
    """Test parse_manufacturer_id."""
    manufacturer_id_raw = b"\x10\xac"
    manufacturer_id = parse_manufacturer_id(manufacturer_id_raw)
    assert manufacturer_id == "DEL"


def test_get_edid_windows_wmi_returns_bytes():
    """get_edid_windows_wmi must return bytes not str (Python 3 fix for issue #703).

    WMI returns EDID as a tuple of ints. The old code used
    ''.join(chr(i) for i in edid[0]) which produces a unicode str in Python 3,
    causing md5() in parse_edid to raise TypeError (silently suppressed),
    leaving the monitor with its generic 'Plug and play' device string instead
    of the real EDID monitor name.
    """
    from DisplayCAL.edid import get_edid_windows_wmi

    raw_edid = (
        b"\x00\xff\xff\xff\xff\xff\xff\x00\x10\xac\xe0@L405\x05\x1b\x01\x04\xb57\x1fx:U"
        b"\xc5\xafO3\xb8%\x0bPT\xa5K\x00qO\xa9@\x81\x80\xd1\xc0\x01\x01\x01\x01\x01\x01"
        b"\x01\x01V^\x00\xa0\xa0\xa0)P0 5\x00)7!\x00\x00\x1a\x00\x00\x00\xff\x00"
        b"TYPR371U504L\n\x00\x00\x00\xfc\x00DELL UP2516D\n\x00\x00\x00\xfd\x002K\x1eX"
        b"\x19\x01\n      \x01,\x02\x03\x1c\xf1O\x90\x05\x04\x03\x02\x07\x16\x01\x06"
        b"\x11\x12\x15\x13\x14\x1f#\t\x1f\x07\x83\x01\x00\x00\x02:\x80\x18q8-@X,E"
        b"\x00)7!\x00\x00\x1e~9\x00\xa0\x808\x1f@0 :\x00)7!\x00\x00\x1a\x01\x1d\x00rQ"
        b"\xd0\x1e n(U\x00)7!\x00\x00\x1e\xbf\x16\x00\xa0\x808\x13@0 :\x00)7!\x00\x00"
        b"\x1a\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x86"
    )
    edid_as_ints = tuple(raw_edid)

    class MockMonitor:
        InstanceName = "DISPLAY\\DELL_UP2516D\\0"

        def WmiGetMonitorRawEEdidV1Block(self, block):
            return (edid_as_ints, 0)

    class MockWMIConnection:
        def WmiMonitorDescriptorMethods(self):
            return [MockMonitor()]

    result = get_edid_windows_wmi("DELL_UP2516D", MockWMIConnection(), False)

    assert isinstance(result, bytes), (
        f"get_edid_windows_wmi must return bytes, got {type(result).__name__}"
    )
    assert result == raw_edid

    parsed = parse_edid(result)
    assert parsed.get("monitor_name") == "DELL UP2516D"


def _make_ioreg_output(*edid_hex_list):
    """Build a fake ioreg output string containing the given EDID hex blobs."""
    lines = []
    for edid_hex in edid_hex_list:
        lines.append(f'"IODisplayEDID" = <{edid_hex}>')
    return "\n".join(lines).encode()


def test_get_edid_darwin_name_match(monkeypatch, patch_subprocess):
    """get_edid_darwin() returns the EDID whose monitor_name matches display_name."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["ioreg-cIODisplay-S-w0"] = _make_ioreg_output(_VP2768A_HEX)

    result = get_edid_darwin("VP2768a", display_no=0)

    assert result == _VP2768A_EDID


def test_get_edid_darwin_index_fallback(monkeypatch, patch_subprocess):
    """get_edid_darwin() falls back to display_no index when name does not match.

    Covers the case where ArgyllCMS returns a generic name such as "Display #1"
    on macOS Tahoe / Apple Silicon (issue #773).
    """
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["ioreg-cIODisplay-S-w0"] = _make_ioreg_output(_VP2768A_HEX)

    result = get_edid_darwin("Display #1", display_no=0)

    assert result == _VP2768A_EDID
    parsed = parse_edid(result)
    assert parsed.get("monitor_name") == "VP2768a"


def test_get_edid_darwin_index_out_of_range(monkeypatch, patch_subprocess):
    """get_edid_darwin() returns None when display_no exceeds available EDIDs."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["ioreg-cIODisplay-S-w0"] = _make_ioreg_output(_VP2768A_HEX)

    result = get_edid_darwin("Display #2", display_no=1)

    assert result is None


def test_get_edid_darwin_multi_display_index_fallback(monkeypatch, patch_subprocess):
    """get_edid_darwin() selects the correct EDID by index for multi-display setups."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["ioreg-cIODisplay-S-w0"] = _make_ioreg_output(
        _VP2768A_HEX, _U28E590_HEX
    )

    result0 = get_edid_darwin("Display #1", display_no=0)
    result1 = get_edid_darwin("Display #2", display_no=1)

    assert result0 == _VP2768A_EDID
    assert result1 == _U28E590_EDID


# ---------------------------------------------------------------------------
# Linux (xrandr) fallback tests
# ---------------------------------------------------------------------------


def _make_xrandr_output(*entries):
    """Build a minimal fake xrandr --verbose output.

    Each entry is a (output_name, edid_hex) tuple.  Connected outputs are
    listed in order with their EDID blocks embedded.
    """
    lines = [b"Screen 0: minimum 8 x 8, current 2560 x 1440, maximum 32767 x 32767"]
    for i, (output_name, edid_hex) in enumerate(entries):
        name = output_name.encode() if isinstance(output_name, str) else output_name
        primary = b" primary" if i == 0 else b""
        lines.append(
            name + b" connected" + primary + b" 2560x1440+0+0 (normal) 597mm x 336mm"
        )
        lines.append(b"\tEDID:")
        # Split hex into 32-char rows (16 bytes each) as xrandr does
        for j in range(0, len(edid_hex), 32):
            lines.append(b"\t\t" + edid_hex[j : j + 32].encode())
    return b"\n".join(lines)


def test_get_edid_from_xrandr_index_fallback_no_display(monkeypatch, patch_subprocess):
    """get_edid_from_xrandr() falls back to index when get_display() returns None.

    This covers the case where the geometry-based display lookup fails
    (e.g. stale getcfg('displays') on first run).
    """
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.edid.which", lambda x: "xrandr")
    monkeypatch.setattr(
        "DisplayCAL.edid.real_display_size_mm.get_display", lambda n: None
    )
    patch_subprocess.output["xrandr--verbose"] = _make_xrandr_output(
        ("DP-4", _VP2768A_HEX)
    )

    result = get_edid_from_xrandr(0)

    assert result == _VP2768A_EDID
    parsed = parse_edid(result)
    assert parsed.get("monitor_name") == "VP2768a"


def test_get_edid_from_xrandr_index_fallback_name_mismatch(
    monkeypatch, patch_subprocess
):
    """get_edid_from_xrandr() falls back to index when xrandr name does not match.

    This covers the case where ArgyllCMS provides a generic name (e.g. "Monitor 1")
    that does not appear in xrandr output as an output name (issue #773 on Linux).
    """
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.edid.which", lambda x: "xrandr")
    monkeypatch.setattr(
        "DisplayCAL.edid.real_display_size_mm.get_display",
        lambda n: {"name": b"Monitor 1", "description": b"Monitor 1 @ 0, 0, 2560x1440"},
    )
    patch_subprocess.output["xrandr--verbose"] = _make_xrandr_output(
        ("DP-4", _VP2768A_HEX)
    )

    result = get_edid_from_xrandr(0)

    assert result == _VP2768A_EDID
    parsed = parse_edid(result)
    assert parsed.get("monitor_name") == "VP2768a"


def test_get_edid_from_xrandr_index_fallback_multi_display(
    monkeypatch, patch_subprocess
):
    """get_edid_from_xrandr() fallback selects the Nth EDID for multi-display setups."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.edid.which", lambda x: "xrandr")
    monkeypatch.setattr(
        "DisplayCAL.edid.real_display_size_mm.get_display", lambda n: None
    )
    patch_subprocess.output["xrandr--verbose"] = _make_xrandr_output(
        ("DP-4", _VP2768A_HEX),
        ("DP-2", _U28E590_HEX),
    )

    result0 = get_edid_from_xrandr(0)
    result1 = get_edid_from_xrandr(1)

    assert result0 == _VP2768A_EDID
    assert result1 == _U28E590_EDID


def test_get_edid_from_xrandr_index_out_of_range(monkeypatch, patch_subprocess):
    """get_edid_from_xrandr() returns None when display_no exceeds available EDIDs."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.edid.which", lambda x: "xrandr")
    monkeypatch.setattr(
        "DisplayCAL.edid.real_display_size_mm.get_display", lambda n: None
    )
    patch_subprocess.output["xrandr--verbose"] = _make_xrandr_output(
        ("DP-4", _VP2768A_HEX)
    )

    result = get_edid_from_xrandr(1)

    assert result is None


# ---------------------------------------------------------------------------
# system_profiler fallback tests (macOS Tahoe / Apple Silicon)
# ---------------------------------------------------------------------------

_SYSTEM_PROFILER_JSON = json.dumps(
    {
        "SPDisplaysDataType": [
            {
                "_name": "Apple M4 Max",
                "spdisplays_ndrvs": [
                    {
                        "_name": "Built-in Retina Display",
                        "spdisplays_resolution": "3024 x 1964 Retina",
                    },
                    {
                        "_name": "LG UltraFine 4K",
                        "spdisplays_resolution": "3840 x 2160 (UHD 4K)",
                    },
                ],
            }
        ]
    }
).encode()

# Reflects the actual macOS Tahoe / M1 Pro format seen in the field:
# resolution keys are underscore-prefixed (_spdisplays_resolution, _spdisplays_pixels)
_SYSTEM_PROFILER_JSON_TAHOE = json.dumps(
    {
        "SPDisplaysDataType": [
            {
                "_name": "Apple M1 Pro",
                "spdisplays_ndrvs": [
                    {
                        "_name": "Color LCD",
                        "_spdisplays_pixels": "3456 x 2234",
                        "_spdisplays_resolution": "1728 x 1117 @ 120.00Hz",
                        "spdisplays_pixelresolution": "spdisplays_3456x2234Retina",
                        "spdisplays_connection_type": "spdisplays_internal",
                    },
                ],
            }
        ]
    }
).encode()


def test_get_display_name_from_system_profiler_match(monkeypatch, patch_subprocess):
    """get_display_name_from_system_profiler() returns name matched by resolution."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = (
        _SYSTEM_PROFILER_JSON
    )

    result = get_display_name_from_system_profiler(3840, 2160)

    assert result == "LG UltraFine 4K"


def test_get_display_name_from_system_profiler_builtin(monkeypatch, patch_subprocess):
    """get_display_name_from_system_profiler() matches built-in display by resolution."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = (
        _SYSTEM_PROFILER_JSON
    )

    result = get_display_name_from_system_profiler(3024, 1964)

    assert result == "Built-in Retina Display"


def test_get_display_name_from_system_profiler_no_match(monkeypatch, patch_subprocess):
    """get_display_name_from_system_profiler() returns None when resolution not found."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = (
        _SYSTEM_PROFILER_JSON
    )

    result = get_display_name_from_system_profiler(1920, 1080)

    assert result is None


def test_get_display_name_from_system_profiler_hidpi_physical(
    monkeypatch, patch_subprocess
):
    """Physical (3840x2160) pixels match inside a HiDPI resolution string."""
    data = json.dumps(
        {
            "SPDisplaysDataType": [
                {
                    "_name": "Apple M4 Max",
                    "spdisplays_ndrvs": [
                        {
                            "_name": "LG UltraFine 5K",
                            "spdisplays_resolution": "2560 x 1440 (3840 x 2160 HiDPI)",
                        },
                    ],
                }
            ]
        }
    ).encode()
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = data

    assert get_display_name_from_system_profiler(3840, 2160) == "LG UltraFine 5K"


def test_get_display_name_from_system_profiler_hidpi_logical(
    monkeypatch, patch_subprocess
):
    """Logical (2560x1440) pixels match inside a HiDPI resolution string."""
    data = json.dumps(
        {
            "SPDisplaysDataType": [
                {
                    "_name": "Apple M4 Max",
                    "spdisplays_ndrvs": [
                        {
                            "_name": "LG UltraFine 5K",
                            "spdisplays_resolution": "2560 x 1440 (3840 x 2160 HiDPI)",
                        },
                    ],
                }
            ]
        }
    ).encode()
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = data

    assert get_display_name_from_system_profiler(2560, 1440) == "LG UltraFine 5K"


def test_get_display_name_from_system_profiler_pixelresolution_key(
    monkeypatch, patch_subprocess
):
    """spdisplays_pixelresolution key (format 'spdisplays_3840x2160') is used as fallback."""
    data = json.dumps(
        {
            "SPDisplaysDataType": [
                {
                    "_name": "Apple M4 Max",
                    "spdisplays_ndrvs": [
                        {
                            "_name": "ASUS ProArt PA329CV",
                            "spdisplays_pixelresolution": "spdisplays_3840x2160",
                        },
                    ],
                }
            ]
        }
    ).encode()
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = data

    assert get_display_name_from_system_profiler(3840, 2160) == "ASUS ProArt PA329CV"


def test_get_display_name_from_system_profiler_native_resolution_key(
    monkeypatch, patch_subprocess
):
    """spdisplays_native-resolution key is checked when spdisplays_resolution missing."""
    data = json.dumps(
        {
            "SPDisplaysDataType": [
                {
                    "_name": "Apple M4 Max",
                    "spdisplays_ndrvs": [
                        {
                            "_name": "Dell U2723QE",
                            "spdisplays_native-resolution": "3840 x 2160",
                        },
                    ],
                }
            ]
        }
    ).encode()
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = data

    assert get_display_name_from_system_profiler(3840, 2160) == "Dell U2723QE"


def test_get_display_name_from_system_profiler_tahoe_underscore_resolution(
    monkeypatch, patch_subprocess
):
    """MacOS Tahoe uses _spdisplays_resolution (underscore prefix) for the resolution key."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = (
        _SYSTEM_PROFILER_JSON_TAHOE
    )

    # 1728x1117 is what Argyll (dispwin) reports; it matches _spdisplays_resolution
    result = get_display_name_from_system_profiler(1728, 1117)

    assert result == "Color LCD"


def test_get_display_name_from_system_profiler_tahoe_no_match(
    monkeypatch, patch_subprocess
):
    """_spdisplays_pixels (physical 2x) does not match Argyll logical resolution."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = (
        _SYSTEM_PROFILER_JSON_TAHOE
    )

    # Physical pixel count (3456x2234) — Argyll reports logical (1728x1117),
    # so asking for physical should NOT match via _spdisplays_resolution but WILL
    # match via _spdisplays_pixels.
    result = get_display_name_from_system_profiler(3456, 2234)

    assert result == "Color LCD"


# Reflects issue #991: two different displays with the same 1920x1080 logical
# resolution (BenQ via USB-C, LG via HDMI on an M5 Pro Mac mini)
_SYSTEM_PROFILER_JSON_SAME_RESOLUTION = json.dumps(
    {
        "SPDisplaysDataType": [
            {
                "_name": "Apple M5 Pro",
                "spdisplays_ndrvs": [
                    {
                        "_name": "BenQ PD2706U",
                        "_spdisplays_display-product-id": "8048",
                        "_spdisplays_display-vendor-id": "9d1",
                        "_spdisplays_displayID": "2",
                        "_spdisplays_pixels": "3840 x 2160",
                        "_spdisplays_resolution": "1920 x 1080 @ 60.00Hz",
                    },
                    {
                        "_name": "LG ULTRAFINE",
                        "_spdisplays_display-product-id": "5cbb",
                        "_spdisplays_display-vendor-id": "1e6d",
                        "_spdisplays_displayID": "3",
                        "_spdisplays_pixels": "3840 x 2160",
                        "_spdisplays_resolution": "1920 x 1080 @ 60.00Hz",
                    },
                ],
            }
        ]
    }
).encode()


@pytest.mark.parametrize(
    "identity, expected",
    [
        ((2, 0x09D1, 0x8048), "BenQ PD2706U"),
        ((3, 0x1E6D, 0x5CBB), "LG ULTRAFINE"),
        # Unknown display id, vendor/product still identifies the display
        ((99, 0x1E6D, 0x5CBB), "LG ULTRAFINE"),
        # Neither matches, falls back to the first resolution match
        ((99, 0x1234, 0x5678), "BenQ PD2706U"),
        ((), "BenQ PD2706U"),
    ],
)
def test_get_display_name_from_system_profiler_same_resolution(
    monkeypatch, patch_subprocess, identity, expected
):
    """Displays sharing a resolution are told apart by id/vendor/product (#991)."""
    monkeypatch.setattr("DisplayCAL.edid.subprocess", patch_subprocess)
    patch_subprocess.output["system_profilerSPDisplaysDataType-json"] = (
        _SYSTEM_PROFILER_JSON_SAME_RESOLUTION
    )

    assert get_display_name_from_system_profiler(1920, 1080, *identity) == expected
