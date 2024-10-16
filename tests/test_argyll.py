# -*- coding: utf-8 -*-
import os
from subprocess import Popen

from DisplayCAL.argyll import get_argyll_util, get_argyll_version_string
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
    result = get_argyll_util("ccxxmake")
    expected_result = os.path.join(config.getcfg("argyll.dir"), "ccxxmake")
    assert result == expected_result


def test_get_argyll_version_string_1(argyll):
    """Test worker_base.get_argyll_version_string() function."""
    config.initcfg()
    with check_call(Popen, "communicate", SUBPROCESS_COM):
        result = get_argyll_version_string("ccxxmake")
    expected_result = "2.3.0"
    assert result == expected_result
