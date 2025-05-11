import os
import pytest
import sys

from DisplayCAL import wxversion


@pytest.fixture(scope="function")
def setup_sys_path():
    """Setup sys.path."""
    orig_sys_path = sys.path[:]
    yield
    sys.path = orig_sys_path[:]


@pytest.fixture(scope="function")
def setup_selected():
    """Setup wxversion._SELECTED."""
    orig_selected = wxversion._SELECTED
    wxversion._SELECTED = None
    yield
    wxversion._SELECTED = orig_selected


@pytest.fixture(scope="function")
def setup_ensure_debug(scope="function"):
    """Setup wxversion._DEBUG."""
    orig_debug = wxversion._EM_DEBUG
    wxversion._EM_DEBUG = True
    yield
    wxversion._EM_DEBUG = orig_debug


# @pytest.fixture(scope="function")
# def setup_select(version, options_required=False):
#     # setup
#     orig_sys_path = sys.path[:]

#     # test
#     wxversion.select(version, options_required)
#     print(f"Asked for {version}, ({options_required}):\t got: {sys.path[0]}")

#     # reset
#     sys.path = orig_sys_path[:]
#     wxversion._SELECTED = None


# @pytest.fixture(scope="function")
# def setup_ensure_minimal(version, options_required=False):
#     # setup
#     savepath = sys.path[:]

#     # test
#     wxversion.ensure_minimal(version, options_required)
#     print(f"EM: Asked for {version}, ({options_required}):\t got: {sys.path[0]}")

#     # reset
#     sys.path = savepath[:]
#     wxversion._SELECTED = None


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
    for name in names:
        d = os.path.join("/tmp", name)
        os.mkdir(d)
        os.mkdir(os.path.join(d, "wx"))

    # setup sys.path to see those dirs
    sys.path.append("/tmp")
    yield names

    # cleanup
    for name in names:
        d = os.path.join("/tmp", name)
        os.rmdir(os.path.join(d, "wx"))
        os.rmdir(d)


def test_get_installed(setup_tests):
    result = wxversion.get_installed()
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
        wxversion.select(version, options_required=options_required)
        if isinstance(version, str):
            parts = version.split("-")
        elif isinstance(version, list):
            parts = version[-1].split("-")
        expected_version = parts[0].split(".")
        expected_version = tuple(expected_version)
        assert expected_version[:1] == wxversion._SELECTED.version[:1]
    else:
        with pytest.raises(wxversion.VersionError):
            wxversion.select(version, options_required=options_required)


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
            wxversion.check_installed(version, options_required=options_required)
            is expected
        )
    else:
        with pytest.raises(wxversion.VersionError):
            wxversion.check_installed(version, options_required=options_required)


def test_select_consecutive(setup_tests):
    """check for exception when incompatible versions are requested."""
    wxversion.select("2.4")
    with pytest.raises(wxversion.VersionError) as cm:
        wxversion.select("2.5")

    assert str(cm.value) == "A previously selected wx version does not match the new request."


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
        wxversion.ensure_minimal(version, options_required=options_required)
        if options_required:
            assert wxversion._SELECTED.version[:1] == ("2",)
        else:
            assert wxversion._SELECTED.version[:1] == ("4",)
    else:
        with pytest.raises(wxversion.VersionError):
            wxversion.ensure_minimal(version, options_required=options_required)
