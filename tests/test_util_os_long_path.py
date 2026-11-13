"""Tests for DisplayCAL.util_os.make_win32_compatible_long_path.

On Windows, util_os wraps os.stat, open() etc. so that paths longer than
MAX_PATH get the "\\\\?\\" prefix. pathlib passes Path objects to os.stat, and
prefixing those raised "can only concatenate str (not "WindowsPath") to str".
That aborted opening the main window when a setting held a long profile path.
"""

import os
import pathlib
import sys

import pytest

from DisplayCAL.util_os import make_win32_compatible_long_path

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

PREFIX = "\\\\?\\"


def _long_path(base) -> str:
    """Return an absolute path longer than MAX_PATH below base."""
    return os.path.join(str(base), "x" * 120, "y" * 120, "profile.icm")


def test_long_str_path_gets_prefix(tmp_path):
    path = _long_path(tmp_path)

    assert make_win32_compatible_long_path(path) == PREFIX + path


def test_long_pathlib_path_gets_prefix(tmp_path):
    path = _long_path(tmp_path)

    assert make_win32_compatible_long_path(pathlib.Path(path)) == PREFIX + path


def test_long_bytes_path_gets_bytes_prefix(tmp_path):
    path = os.fsencode(_long_path(tmp_path))

    result = make_win32_compatible_long_path(path)

    assert result == os.fsencode(PREFIX) + path


def test_short_and_already_prefixed_paths_are_unchanged(tmp_path):
    short = pathlib.Path(tmp_path, "profile.icm")
    prefixed = PREFIX + _long_path(tmp_path)

    assert make_win32_compatible_long_path(short) is short
    assert make_win32_compatible_long_path(prefixed) == prefixed


def test_file_descriptor_is_unchanged():
    assert make_win32_compatible_long_path(3) == 3


def test_pathlib_is_file_on_long_missing_path_does_not_raise_type_error(tmp_path):
    """The call that aborted opening the main window."""
    # A profile path whose "²" was mis-encoded over and over, as found in a
    # DisplayCAL.ini written by 3.9.17
    name = "S2721QS #1 2024-12-16 80cdm" + "Ãƒâ€šÃ‚" * 60 + "² D6500 2.4.icm"
    path = pathlib.Path(tmp_path, name)

    try:
        assert not path.is_file()
    except OSError:
        pass  # a file name this long may be rejected, which callers handle
