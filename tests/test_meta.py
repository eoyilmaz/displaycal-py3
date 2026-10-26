"""Tests for DisplayCAL/meta.py."""

import pytest

from DisplayCAL.meta import parse_version


@pytest.mark.parametrize(
    "version, expected",
    [
        ("3.10.0", ((3, 10, 0), False)),
        ("3.9.18.1", ((3, 9, 18), False)),
        ("3.10.0rc1", ((3, 10, 0), True)),
        ("3.10.0b2", ((3, 10, 0), True)),
        ("3.10.0.dev105", ((3, 10, 0), True)),
        ("0.0.0", ((0, 0, 0), False)),
    ],
)
def test_parse_version(version, expected):
    assert parse_version(version) == expected
