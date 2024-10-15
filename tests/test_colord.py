# -*- coding: utf-8 -*-

import platform

from DisplayCAL import RealDisplaySizeMM, config
from DisplayCAL.colord import device_id_from_edid
from DisplayCAL.dev.mocks import check_call
from DisplayCAL.edid import get_edid

import pytest

from tests.data.display_data import DisplayData


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
