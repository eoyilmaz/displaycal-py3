# -*- coding: utf-8 -*-
from typing import Tuple

import pytest
import wx
from _pytest.fixtures import SubRequest

from DisplayCAL import RealDisplaySizeMM
from DisplayCAL.dev.mocks import check_call, check_call_str
from DisplayCAL.wxMeasureFrame import get_default_size
from tests.data.display_data import DisplayData


@pytest.fixture(
    scope="session", name="size_in_mm", params=["size_available", "size_unavailable"]
)
def fixture_size_in_mm(request: SubRequest) -> Tuple[int, int]:
    """Return display size in mm (width, height)."""
    return (
        DisplayData.DISPLAY_DATA_1["size"]
        if request.param == "size_available"
        else (0, 0)
    )


@pytest.mark.parametrize(
    "real_display",
    (True, False),
    ids=("with_RealDisplaySizeMM", "without_RealDisplaySizeMM"),
)
def test_get_default_size_1(real_display: bool, size_in_mm: Tuple[int, int]) -> None:
    """Testing wxMeasureFrame.get_default_size() function."""
    with check_call_str("DisplayCAL.wxMeasureFrame.getcfg", DisplayData.CFG_DATA):
        with check_call_str(
            "DisplayCAL.wxMeasureFrame.get_display_number",
            DisplayData.DISPLAY_DATA_1["screen"],
        ):
            with check_call(wx, "Display", DisplayData()):
                if real_display:
                    with check_call(
                        RealDisplaySizeMM,
                        "RealDisplaySizeMM",
                        DisplayData.DISPLAY_DATA_1["size"],
                    ):
                        result = get_default_size()
                else:
                    with check_call(
                        wx, "DisplaySize", DisplayData.DISPLAY_DATA_1["size"]
                    ):
                        with check_call(wx, "DisplaySizeMM", size_in_mm):
                            result = get_default_size()
    assert isinstance(result, int)
    assert result > 1
