import os
from subprocess import Popen
import sys

import pytest

from DisplayCAL import config
from DisplayCAL.argyll import (
    debug_print,
    get_argyll_util,
    get_argyll_version,
    get_argyll_version_string,
    verbose_print,
)

from DisplayCAL.dev.mocks import check_call, check_call_str
from tests.data.argyll_sp_data import SUBPROCESS_COM


@pytest.fixture(scope="function")
def setup_verbose_level(request):
    """Fixture to set up the verbose level for tests."""
    from DisplayCAL import options

    orig_value = options.VERBOSE
    options.VERBOSE = request.param
    yield
    options.VERBOSE = orig_value


@pytest.fixture(scope="function")
def setup_debug_level(request):
    """Fixture to set up the debug level for tests."""
    from DisplayCAL import options

    orig_value = options.DEBUG
    options.DEBUG = request.param
    yield
    options.DEBUG = orig_value


# todo: deactivated test temporarily
# def test_xicclu_is_working_properly(data_files):
#     """testing if ``DisplayCAL.worker_base.Xicclu`` is working properly"""
#     from DisplayCAL.icc_profile import ICCProfile
#     from DisplayCAL.worker_base import Xicclu
#
#     profile = ICCProfile(profile=data_files["default.icc"].absolute())
#     xicclu = Xicclu(profile, "r", "a", pcs="X", scale=100)
#     assert xicclu() is not None


def test_get_argyll_util(setup_argyll):
    """Test get_argyll_util() function."""
    config.initcfg()
    result = get_argyll_util("ccxxmake")
    expected_result = os.path.join(config.getcfg("argyll.dir"), "ccxxmake")
    if sys.platform == "win32":
        expected_result += ".exe"
    assert result == expected_result


def test_get_argyll_version_string_1(setup_argyll):
    """Test get_argyll_version_string() function."""
    config.initcfg()
    with check_call(Popen, "communicate", SUBPROCESS_COM):
        result = get_argyll_version_string("ccxxmake")
    expected_result = "2.3.0"
    assert result == expected_result


def test_get_argyll_version_1(setup_argyll):
    """Test get_argyll_version() function."""
    with check_call_str("DisplayCAL.argyll.get_argyll_version_string", "2.3.0"):
        result = get_argyll_version("ccxxmake")
    expected_result = [2, 3, 0]
    assert result == expected_result


def test_verbose_print_verbose_level_skipped(setup_argyll, capsys):
    """Test verbose_print() function."""
    test_value = "Test message"
    verbose_print(test_value)
    assert capsys.readouterr().out == f"{test_value}\n"


@pytest.mark.parametrize("setup_verbose_level", [3], indirect=True)
def test_verbose_print_verbose_level_is_lower_than_verbose(
    setup_argyll, setup_verbose_level, capsys
):
    """Test verbose_print() function."""
    test_value = "Test message"
    verbose_print(test_value, verbose_level=2)
    assert capsys.readouterr().out == f"{test_value}\n"


@pytest.mark.parametrize("setup_verbose_level", [3], indirect=True)
def test_verbose_print_verbose_level_is_equal_to_verbose(
    setup_argyll, setup_verbose_level, capsys
):
    """Test verbose_print() function."""
    test_value = "Test message"
    verbose_print(test_value, verbose_level=3)
    assert capsys.readouterr().out == f"{test_value}\n"


@pytest.mark.parametrize("setup_verbose_level", [3], indirect=True)
def test_verbose_print_verbose_level_is_higher_than_verbose(
    setup_argyll, setup_verbose_level, capsys
):
    """Test verbose_print() function."""
    test_value = "Test message"
    verbose_print(test_value, verbose_level=4)
    assert capsys.readouterr().out != f"{test_value}\n"


@pytest.mark.parametrize(
    "setup_verbose_level, test_value",
    [(3, True), (3, False)],
    indirect=["setup_verbose_level"],
)
def test_verbose_print_verbose_with_an_if_statement(
    setup_argyll, setup_verbose_level, test_value, capsys
):
    """Test verbose_print() function with an if statement."""
    cond1_value = ["Info:", "name", "=", "exe"]
    cond2_value = ["Info:", "name", "not found in", "PATH"]
    verbose_print(*(cond1_value if test_value else cond2_value), verbose_level=3)

    assert capsys.readouterr().out == (
        " ".join(cond1_value if test_value else cond2_value) + "\n"
    )

@pytest.mark.parametrize("setup_debug_level", [1], indirect=True)
def test_debug_print_debug_level_skipped(setup_argyll, setup_debug_level, capsys):
    """Test debug_print() function."""
    test_value = "Test message"
    debug_print(test_value)
    assert capsys.readouterr().out == f"{test_value}\n"


@pytest.mark.parametrize("setup_debug_level", [3], indirect=True)
def test_debug_print_debug_level_is_lower_than_debug(
    setup_argyll, setup_debug_level, capsys
):
    """Test debug_print() function."""
    test_value = "Test message"
    debug_print(test_value, debug_level=2)
    assert capsys.readouterr().out == f"{test_value}\n"


@pytest.mark.parametrize("setup_debug_level", [3], indirect=True)
def test_debug_print_debug_level_is_equal_to_debug(
    setup_argyll, setup_debug_level, capsys
):
    """Test debug_print() function."""
    test_value = "Test message"
    debug_print(test_value, debug_level=3)
    assert capsys.readouterr().out == f"{test_value}\n"


@pytest.mark.parametrize("setup_debug_level", [3], indirect=True)
def test_debug_print_debug_level_is_higher_than_debug(
    setup_argyll, setup_debug_level, capsys
):
    """Test debug_print() function."""
    test_value = "Test message"
    debug_print(test_value, debug_level=4)
    assert capsys.readouterr().out != f"{test_value}\n"


@pytest.mark.parametrize(
    "setup_debug_level, test_value",
    [(3, True), (3, False)],
    indirect=["setup_debug_level"],
)
def test_debug_print_debug_with_an_if_statement(
    setup_argyll, setup_debug_level, test_value, capsys
):
    """Test debug_print() function with an if statement."""
    cond1_value = ["Info:", "name", "=", "exe"]
    cond2_value = ["Info:", "name", "not found in", "PATH"]
    debug_print(*(cond1_value if test_value else cond2_value), debug_level=3)

    assert capsys.readouterr().out == (
        " ".join(cond1_value if test_value else cond2_value) + "\n"
    )
