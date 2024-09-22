# -*- coding: utf-8 -*-
import os
from subprocess import Popen

from DisplayCAL import worker_base
from DisplayCAL import config
from DisplayCAL.dev.mocks import check_call

from tests.data.argyll_sp_data import SUBPROCESS_COM

# todo: deactivated test temporarily
# def test_xicclu_is_working_properly(data_files):
#     """testing if ``DisplayCAL.worker_base.Xicclu`` is working properly"""
#     from DisplayCAL import ICCProfile
#     from DisplayCAL.worker_base import Xicclu
#
#     profile = ICCProfile.ICCProfile(profile=data_files["default.icc"].absolute())
#     xicclu = Xicclu(profile, "r", "a", pcs="X", scale=100)
#     assert xicclu() is not None


def test_get_argyll_util(argyll):
    """Test worker_base.get_argyll_util() function."""
    config.initcfg()
    result = worker_base.get_argyll_util("ccxxmake")
    expected_result = os.path.join(config.getcfg("argyll.dir"), "ccxxmake")
    assert result == expected_result


def test_get_argyll_version_string_1(argyll):
    """Test worker_base.get_argyll_version_string() function."""
    config.initcfg()
    with check_call(Popen, "communicate", SUBPROCESS_COM):
        result = worker_base.get_argyll_version_string("ccxxmake")
    expected_result = "2.3.0"
    assert result == expected_result


def test_printcmdline_1():
    """Test worker_base.printcmdline() function for issue #73"""
    # Command line:
    cmd = "/home/eoyilmaz/.local/bin/Argyll_V2.3.0/bin/colprof"
    args = [
        "-v",
        "-qh",
        "-ax",
        "-bn",
        "-C",
        b"No copyright. Created with DisplayCAL 3.8.9.3 and Argyll CMS 2.3.0",
        "-A",
        "Dell, Inc.",
        "-D",
        "UP2516D_#1_2022-04-01_00-26_2.2_F-S_XYZLUT+MTX",
        "/tmp/DisplayCAL-i91d9z8_/UP2516D_#1_2022-04-01_00-26_2.2_F-S_XYZLUT+MTX",
    ]
    # fn = "<bound method WorkerBase.log of <DisplayCAL.worker.Worker object at 0x7f7b941bb6a0>>"
    cwd = "/tmp/DisplayCAL-i91d9z8_"
    worker_base.printcmdline(cmd=cmd, args=args, cwd=cwd)
