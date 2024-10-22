# -*- coding: utf-8 -*-
import codecs
import sys

import pytest

from DisplayCAL import config, RealDisplaySizeMM
from DisplayCAL.config import getcfg
from DisplayCAL.dev.mocks import check_call
from tests.data.display_data import DisplayData
from DisplayCAL.edid import get_edid, parse_edid, parse_manufacturer_id


# @pytest.mark.skipif(sys.platform == "darwin", reason="Not working as expected on MacOS")
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

    with check_call(
        config,
        "getcfg",
        DisplayData.CFG_DATA,
        call_count=-1,
    ):
        with check_call(
            RealDisplaySizeMM,
            "_enumerate_displays",
            DisplayData.enumerate_displays(),
            call_count=-1,
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
    assert result["checksum_valid"] is False 
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
    assert "manufacturer" not in result
    # assert isinstance(result["manufacturer"], str)
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


@pytest.mark.parametrize(
    "xrandr_data_file_name,dispwin_data_file_name,getcfg_displays_output,display_no,expected_result",
    [
        [
            "xrandr_output_1.txt",
            "dispwin_output_1.txt",
            ["DP-4 @ 0, 0, 2560x1440 [PRIMARY]"],
            0,
            {
                "edid": b"00ffffffffffff005a633a7a0f010101311e0104b53c22783bb091ab524ea0260f5054bfef80e1c0d100d1c0b300a9408180810081c0565e00a0a0a029503020350055502100001a000000ff005738553230343930303130340a000000fd00184b0f5a1e000a202020202020000000fc00565032373638610a2020202020017b020322f155901f05145a5904131e1d0f0e07061211161503020123097f0783010000023a801871382d40582c450055502100001e011d8018711c1620582c250055502100009e023a80d072382d40102c458055502100001e011d007251d01e206e28550055502100001e584d00b8a1381440f82c4b0055502100001e000000d2",
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
            },
        ],
        [
            "xrandr_output_2.txt",
            "dispwin_output_2.txt",
            ["DP-4 @ 0, 0, 2560x1440 [PRIMARY]", "DP-2 @ 2160, 0, 3840x2160"],
            0,
            {
                "edid": b"00ffffffffffff005a633a7a0f010101311e0104b53c22783bb091ab524ea0260f5054bfef80e1c0d100d1c0b300a9408180810081c0565e00a0a0a029503020350055502100001a000000ff005738553230343930303130340a000000fd00184b0f5a1e000a202020202020000000fc00565032373638610a2020202020017b020322f155901f05145a5904131e1d0f0e07061211161503020123097f0783010000023a801871382d40582c450055502100001e011d8018711c1620582c250055502100009e023a80d072382d40102c458055502100001e011d007251d01e206e28550055502100001e584d00b8a1381440f82c4b0055502100001e000000d2",
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
            },
        ],
        [
            "xrandr_output_2.txt",
            "dispwin_output_2.txt",
            ["DP-4 @ 0, 0, 2560x1440 [PRIMARY]", "DP-2 @ 2160, 0, 3840x2160"],
            1,
            {
                "edid": b"00ffffffffffff004c2d4d0c46584d30231a0104b53d23783a5fb1a2574fa2280f5054bfef80714f810081c08180a9c0b300950001014dd000a0f0703e80302035005f592100001a000000fd00384b1e873c000a202020202020000000fc00553238453539300a2020202020000000ff00485450483930303130330a2020016602030ef041102309070783010000023a801871382d40582c45005f592100001e565e00a0a0a02950302035005f592100001a04740030f2705a80b0588a005f592100001e000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000052",
                "hash": "ce204468c25bc6df152fba3b1237c286",
                "header": b"00ffffff",
                "manufacturer_id": "YSF",
                "product_id": 26214,
                "serial_32": 808478310,
                "week_of_manufacture": 52,
                "year_of_manufacture": 2089,
                "edid_version": 50,
                "edid_revision": 100,
                "max_h_size_cm": 100,
                "max_v_size_cm": 48,
                "gamma": 1.99,
                "features": 52,
                "red_x": 0.21875,
                "red_y": 0.2060546875,
                "green_x": 0.3916015625,
                "green_y": 0.201171875,
                "blue_x": 0.1875,
                "blue_y": 0.1982421875,
                "white_x": 0.2001953125,
                "white_y": 0.1923828125,
                "ext_flag": 50,
                "checksum": 48,
                "checksum_valid": False,
            },
        ],
        [
            "xrandr_output_3.txt",
            "dispwin_output_3.txt",
            ["HDMI-A-0 @ 0, 0, 3840x2160 [PRIMARY]"],
            0,
            {
                "edid": b"00ffffffffffff0004725805436e60721a1b0103805e35782aa191a9544d9c260f5054bfef80714f8140818081c081009500b300d1c04dd000a0f0703e8030203500ad113200001a565e00a0a0a029502f203500ad113200001a000000fd00323c1e8c3c000a202020202020000000fc00416365722045543433304b0a200129020341f1506101600304121305141f100706026b5f23090707830100006b030c002000383c2000200167d85dc401788000e305e001e40f050000e6060701606045023a801871382d40582c4500ad113200001e011d007251d01e206e285500ad113200001e8c0ad08a20e02d10103e9600ad1132000018000000000000000088",
                "hash": "2f78783c69d1a435d655b34dc64c2b51",
                "header": b"00ffffff",
                "manufacturer_id": "YSF",
                "product_id": 26214,
                "serial_32": 808478310,
                "week_of_manufacture": 48,
                "year_of_manufacture": 2042,
                "edid_version": 55,
                "edid_revision": 50,
                "max_h_size_cm": 56,
                "max_v_size_cm": 48,
                "gamma": 1.53,
                "features": 52,
                "red_x": 0.39453125,
                "red_y": 0.2138671875,
                "green_x": 0.1875,
                "green_y": 0.2177734375,
                "blue_x": 0.1953125,
                "blue_y": 0.1943359375,
                "white_x": 0.3798828125,
                "white_y": 0.193359375,
                "ext_flag": 50,
                "checksum": 48,
                "checksum_valid": False,
            },
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
    monkeypatch.setattr("DisplayCAL.RealDisplaySizeMM.subprocess", patch_subprocess)
    monkeypatch.setattr("DisplayCAL.RealDisplaySizeMM.sys.platform", "linux")
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

    # patch RealDisplaySizeMM.getcfg("displays")
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
        else:
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
    """Testing DisplayCAL.edid.parse_edid() function. for #50"""
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
