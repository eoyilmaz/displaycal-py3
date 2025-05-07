# -*- coding: utf-8 -*-
from typing import Dict, Union

import pytest
from _pytest.fixtures import SubRequest

from DisplayCAL.argyll_instruments import (
    get_canonical_instrument_name,
    remove_vendor_names,
)
from DisplayCAL.cgats import CGATS

INSTR_STR = "i1 DisplayPro, ColorMunki Display"
INSTR_STR_INVERSE = "eye-one displayPro, ColorMunki Display"

REPLACEMENT_STR_STR = {
    "DTP94-LCD mode": "DTP94",
    "eye-one display": "i1 Display",
    "Spyder 2 LCD": "Spyder2",
    "Spyder 3": "Spyder3",
}

REPLACEMENT_BSTR_BSTR = {
    b"DTP94-LCD mode": b"DTP94",
    b"eye-one display": b"i1 Display",
    b"Spyder 2 LCD": b"Spyder2",
    b"Spyder 3": b"Spyder3",
}

REPLACEMENT_STR_BSTR = {
    "DTP94-LCD mode": b"DTP94",
    "eye-one display": b"i1 Display",
    "Spyder 2 LCD": b"Spyder2",
    "Spyder 3": b"Spyder3",
}

REPLACEMENT_BSTR_STR = {
    b"DTP94-LCD mode": "DTP94",
    b"eye-one display": "i1 Display",
    b"Spyder 2 LCD": "Spyder2",
    b"Spyder 3": "Spyder3",
}


@pytest.fixture(
    scope="session",
    name="inst_str_format",
    params=("instrument_byte", "instrument_str"),
)
def fixture_inst_str_format(request: SubRequest) -> str:
    """ "Return string format of instrument."""
    return request.param


@pytest.fixture(scope="module", name="target_instrument")
def fixture_target_instrument(inst_str_format: str, data_files) -> Union[bytes, str]:
    """Return target instrument."""
    path = data_files["0_16.ti3"]
    cgats = CGATS(path)
    if inst_str_format == "instrument_byte":
        target_instrument = cgats.queryv1("TARGET_INSTRUMENT")
        assert target_instrument == b"X-Rite i1 DisplayPro, ColorMunki Display"
    else:
        target_instrument = cgats.queryv1("TARGET_INSTRUMENT").decode("utf-8")
        assert target_instrument == "X-Rite i1 DisplayPro, ColorMunki Display"
    return target_instrument


@pytest.mark.parametrize("inverse", (True, False), ids=("inverse", "not inverse"))
@pytest.mark.parametrize(
    "replacement",
    (
        REPLACEMENT_STR_STR,
        REPLACEMENT_BSTR_BSTR,
        REPLACEMENT_BSTR_STR,
        REPLACEMENT_STR_BSTR,
        None,
    ),
    ids=(
        "rep_string-string",
        "rep_bytes-bytes",
        "rep_bytes-string",
        "rep_string-bytes",
        "no replacement",
    ),
)
def test_get_canonical_instrument_name(
    replacement: Dict[Union[str, bytes], Union[str, bytes]],
    target_instrument: Union[bytes, str],
    inverse: bool,
) -> None:
    """Test argyll_instruments.get_canonical_instrument_name()."""
    result = get_canonical_instrument_name(target_instrument, replacement, inverse)
    if inverse and replacement:
        expected_result = (
            INSTR_STR_INVERSE.encode("utf-8")
            if isinstance(target_instrument, bytes)
            else INSTR_STR_INVERSE
        )
    else:
        expected_result = (
            INSTR_STR.encode("utf-8")
            if isinstance(target_instrument, bytes)
            else INSTR_STR
        )
    assert result == expected_result


def test_remove_vendor_names(target_instrument: Union[bytes, str]) -> None:
    """testing the argyll_instruments.remove_vendor_names() function"""
    if isinstance(target_instrument, str):
        pytest.skip()
    result = remove_vendor_names(target_instrument)
    expected_result = b"i1 DisplayPro, ColorMunki Display"
    assert result == expected_result
