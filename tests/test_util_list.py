"""Tests for DisplayCAL.util_list."""

import pytest

from DisplayCAL.util_list import index_fallback_ignorecase, index_ignorecase


def test_index_ignorecase_lowercases_the_value_too():
    # Issue 1028: only the list items were lowercased, so a value with
    # uppercase letters never matched
    assert index_ignorecase(["auto", "C:\\Charts\\a.ti1"], "c:\\charts\\A.TI1") == 1


def test_index_ignorecase_raises_when_missing():
    with pytest.raises(ValueError):
        index_ignorecase(["auto"], "missing")


def test_index_fallback_ignorecase_prefers_case_sensitive_match():
    assert index_fallback_ignorecase(["A.ti1", "a.ti1"], "a.ti1") == 1


def test_index_fallback_ignorecase_falls_back_to_ignoring_case():
    assert index_fallback_ignorecase(["auto", "C:\\Charts\\a.ti1"], "C:\\CHARTS\\A.ti1") == 1
