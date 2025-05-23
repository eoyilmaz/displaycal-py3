import os
import pytest
import sys
import tempfile

from DisplayCAL import wx_version


@pytest.fixture(scope="function")
def setup_sys_path():
    """Setup sys.path."""
    orig_sys_path = sys.path[:]
    yield
    sys.path = orig_sys_path[:]


@pytest.fixture(scope="function")
def setup_selected():
    """Setup wx_version._SELECTED."""
    orig_selected = wx_version._SELECTED
    wx_version._SELECTED = None
    yield
    wx_version._SELECTED = orig_selected


@pytest.fixture(scope="function")
def setup_ensure_debug(scope="function"):
    """Setup wx_version._DEBUG."""
    orig_debug = wx_version._EM_DEBUG
    wx_version._EM_DEBUG = True
    yield
    wx_version._EM_DEBUG = orig_debug


@pytest.fixture(scope="function")
def setup_tests(setup_sys_path, setup_selected):
    sys.modules.pop("wx", None)
    # make some test dirs
    names = [
        "wx-2.4-gtk-ansi",
        "wx-2.5.2-gtk2-unicode",
        "wx-2.5.3-gtk-ansi",
        "wx-2.6-gtk2-unicode",
        "wx-2.6-gtk2-ansi",
        "wx-2.6-gtk-ansi",
        "wx-2.7.1-gtk2-ansi",
    ]
    temp_dir = tempfile.mkdtemp()
    for name in names:
        d = os.path.join(temp_dir, name)
        os.mkdir(d)
        os.mkdir(os.path.join(d, "wx"))

    # setup sys.path to see those dirs
    sys.path.append(temp_dir)
    yield names

    # cleanup
    for name in names:
        d = os.path.join(temp_dir, name)
        os.rmdir(os.path.join(d, "wx"))
        os.rmdir(d)
    os.rmdir(temp_dir)


def test_get_installed(setup_tests):
    result = wx_version.get_installed()
    assert result[1:] == [
        # wx.__version__,
        "2.7.1-gtk2-ansi",
        "2.6-gtk2-unicode",
        "2.6-gtk2-ansi",
        "2.6-gtk-ansi",
        "2.5.3-gtk-ansi",
        "2.5.2-gtk2-unicode",
        "2.4-gtk-ansi",
    ]


@pytest.mark.parametrize(
    "version, options_required, expected, raises_error",
    [
        ("2.4", False, True, False),
        ("2.4-unicode", False, True, False),
        ("2.5-unicode", False, True, False),
        ("2.5", False, True, False),
        ("2.5-gtk2", False, True, False),
        ("2.5.2", False, True, False),
        ("2.5-ansi", False, True, False),
        ("2.6", False, True, False),
        ("2.6-ansi", False, True, False),
        ("2.6-unicode", True, True, False),
        # Multiple versions
        (["2.5.2", "2.5.3", "2.6"], False, True, False),
        (["2.6-unicode", "2.7-unicode"], True, True, False),
        (["2.6", "2.7"], False, True, False),
        (["2.6-unicode", "2.7-unicode"], False, True, False),
        (["2.6-unicode", "2.7-unicode"], True, True, False),
        ("2.9", False, False, True),
        ("2.99-bogus", False, True, True),
    ],
)
def test_select(setup_tests, version, options_required, expected, raises_error):
    if not raises_error:
        wx_version.select(version, options_required=options_required)
        if isinstance(version, str):
            parts = version.split("-")
        elif isinstance(version, list):
            parts = version[-1].split("-")
        expected_version = parts[0].split(".")
        expected_version = tuple(expected_version)
        assert expected_version[:1] == wx_version._SELECTED.version[:1]
    else:
        with pytest.raises(wx_version.VersionError):
            wx_version.select(version, options_required=options_required)


@pytest.mark.parametrize(
    "version, options_required, expected, raises_error",
    [
        ("2.4", False, True, False),
        ("2.4-unicode", False, True, False),
        ("2.5-unicode", False, True, False),
        ("2.5", False, True, False),
        ("2.5-gtk2", False, True, False),
        ("2.5.2", False, True, False),
        ("2.5-ansi", False, True, False),
        ("2.6", False, True, False),
        ("2.6-ansi", False, True, False),
        ("2.6-unicode", True, True, False),
        # Multiple versions
        (["2.5.2", "2.5.3", "2.6"], False, True, False),
        (["2.6-unicode", "2.7-unicode"], True, True, False),
        (["2.6", "2.7"], False, True, False),
        (["2.6-unicode", "2.7-unicode"], False, True, False),
        (["2.6-unicode", "2.7-unicode"], True, True, False),
        # ("2.9", False, False, True),
        # ("2.99-bogus", False, True, True),
    ],
)
def test_check_installed(
    setup_tests, version, options_required, expected, raises_error
):
    if not raises_error:
        assert (
            wx_version.check_installed(version, options_required=options_required)
            is expected
        )
    else:
        with pytest.raises(wx_version.VersionError):
            wx_version.check_installed(version, options_required=options_required)


def test_select_consecutive(setup_tests):
    """check for exception when incompatible versions are requested."""
    wx_version.select("2.4")
    with pytest.raises(wx_version.VersionError) as cm:
        wx_version.select("2.5")

    assert (
        str(cm.value)
        == "A previously selected wx version does not match the new request."
    )


@pytest.mark.parametrize(
    "version, options_required, raises_error",
    [
        ("2.6", False, False),
        ("2.6-unicode", False, False),
        ("2.6-unicode", True, False),
        # ("2.9", False, True),
    ],
)
def test_select_ensure_minimal(
    setup_tests, setup_ensure_debug, version, options_required, raises_error
):
    if not raises_error:
        wx_version.ensure_minimal(version, options_required=options_required)
        if options_required:
            assert wx_version._SELECTED.version[:1] == ("2",)
        else:
            assert wx_version._SELECTED.version[:1] == ("4",)
    else:
        with pytest.raises(wx_version.VersionError):
            wx_version.ensure_minimal(version, options_required=options_required)


def test_select_ensure_minimal_min_version_is_not_string(
    setup_tests, setup_ensure_debug
):
    """Test that ensure_minimal raises an error if the version is not a string."""
    with pytest.raises(TypeError) as cm:
        wx_version.ensure_minimal(2.6, options_required=False)

    assert str(cm.value) == "min_version must be a string"
