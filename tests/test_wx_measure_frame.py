import pytest
import wx
from _pytest.fixtures import SubRequest

from DisplayCAL import real_display_size_mm
from DisplayCAL.dev.mocks import check_call, check_call_str
from DisplayCAL.wx_measure_frame import get_default_size
from tests.data.display_data import DisplayData


@pytest.fixture(
    scope="session", name="size_in_mm", params=["size_available", "size_unavailable"]
)
def fixture_size_in_mm(request: SubRequest) -> tuple[int, int]:
    """Return display size in mm (width, height)."""
    return (
        DisplayData.DISPLAY_DATA_1["size"]
        if request.param == "size_available"
        else (0, 0)
    )


@pytest.mark.parametrize(
    "real_display",
    (True, False),
    ids=("with_real_display_size_mm", "without_real_display_size_mm"),
)
def test_get_default_size_1(real_display: bool, size_in_mm: tuple[int, int]) -> None:
    """Testing wx_measure_frame.get_default_size() function."""
    with check_call_str("DisplayCAL.wx_measure_frame.getcfg", DisplayData.CFG_DATA):
        with check_call_str(
            "DisplayCAL.wx_measure_frame.get_display_number",
            DisplayData.DISPLAY_DATA_1["screen"],
        ):
            with check_call(wx, "Display", DisplayData()):
                if real_display:
                    with check_call(
                        real_display_size_mm,
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


@pytest.mark.skip(
    reason="TODO: This test is moved from the module, properly implement it."
)
def test_from_module():
    import time

    for rgb in [
        (0.079291, 1 / 51.0, 1 / 51.0),
        (0.079291, 0.089572, 0.094845),
        (0.032927, 0.028376, 0.027248),
        (0.037647, 0.037095, 0.036181),
        (51.2 / 255, 153.7 / 255, 127.4 / 255),
    ]:
        wx.CallAfter(wx.GetApp().TopWindow.show_rgb, rgb)
        time.sleep(0.05)
        input("Press RETURN to continue\n")
        if not wx.GetApp().TopWindow:
            break

    # This is the caller of the test function... implement it properly later on.
    import threading

    t = threading.Thread(target=test)
    app.TopWindow.show_controls(False)
    t.start()

