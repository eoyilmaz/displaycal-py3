import sys
from unittest import mock

import pytest
import wx
from _pytest.fixtures import SubRequest
from DisplayCAL import real_display_size_mm
from DisplayCAL import wx_measure_frame
from DisplayCAL.dev.mocks import check_call, check_call_str
from DisplayCAL.wx_measure_frame import (
    get_argyll_measureframe_dimensions,
    get_default_size,
    get_ui_to_x_scale_factor,
)
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
def test_get_default_size_1(
    real_display: bool, size_in_mm: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
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
                        "real_display_size_mm",
                        DisplayData.DISPLAY_DATA_1["size"],
                    ):
                        result = get_default_size()
                else:
                    with (
                        check_call(
                            wx, "DisplaySize", DisplayData.DISPLAY_DATA_1["size"]
                        ),
                        check_call(wx, "DisplaySizeMM", size_in_mm),
                    ):
                        result = get_default_size()
    assert isinstance(result, int)
    assert result > 1


def test_get_default_size_is_100mm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default measure frame size is 100 mm."""
    monkeypatch.setattr(
        wx_measure_frame,
        "getcfg",
        lambda name, raw=False: ["PHL 278E1 @ 0, 0, 2560x1440"],
    )
    monkeypatch.setattr(wx_measure_frame, "get_display_number", lambda display_no: 0)
    monkeypatch.setattr(
        real_display_size_mm, "real_display_size_mm", lambda display_no: (600, 340)
    )

    class FakeDisplay:
        def __init__(self, index: int) -> None:
            self.Geometry = wx.Rect(0, 0, 2560, 1440)

        @staticmethod
        def GetCount() -> int:
            return 1

    monkeypatch.setattr(wx_measure_frame.wx, "Display", FakeDisplay)
    # 100 mm at 2560 px / 600 mm density, scaled by the default size factor:
    # round(1.5 * 100 * 2560 / 600)
    assert get_default_size() == 640


def test_get_ui_to_x_scale_factor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The UI to X scale factor is the X screen size over the UI screen size."""
    monkeypatch.setattr(
        real_display_size_mm, "get_x_screen_size", lambda: (8960, 2880, 2371, 762)
    )
    # The wx branch is used when there is no Qt application
    monkeypatch.delitem(sys.modules, "qtpy", raising=False)
    displays = [wx.Rect(0, 0, 2560, 1440), wx.Rect(2560, 0, 1920, 1080)]

    class FakeDisplay:
        def __init__(self, index: int) -> None:
            self.Geometry = displays[index]

        @staticmethod
        def GetCount() -> int:
            return len(displays)

    monkeypatch.setattr(wx_measure_frame.wx, "Display", FakeDisplay)
    monkeypatch.setattr(wx_measure_frame.wx, "GetApp", lambda: object())
    # Union of both display rects is 4480x1440 px, X screen is 8960x2880 px
    assert get_ui_to_x_scale_factor() == 2.0


def test_get_ui_to_x_scale_factor_no_x_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The UI to X scale factor falls back to 1.0 without an X screen."""
    monkeypatch.setattr(real_display_size_mm, "get_x_screen_size", lambda: None)
    assert get_ui_to_x_scale_factor() == 1.0


def test_get_argyll_measureframe_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    """The measure frame scale is converted to Argyll -P units.

    With HiDPI scaling, one UI pixel spans several X screen pixels, and
    Argyll's test window base (100 mm at the X screen's density) differs from
    the measure frame's base (100 mm at the display's own density).
    """
    # X screen reports 96 DPI (XWayland), display 0 is 2560 px wide over
    # 600 mm, so the measure frame base is round(100 * 2560 / 600) = 427
    monkeypatch.setattr(
        real_display_size_mm, "get_x_screen_px_per_mm", lambda: (3.78, 3.77)
    )
    monkeypatch.setattr(wx_measure_frame, "get_ui_to_x_scale_factor", lambda: 2.0)
    monkeypatch.setattr(wx_measure_frame, "get_default_size", lambda: 427)
    result = get_argyll_measureframe_dimensions("0.25,0.5,1.5")
    x, y, scale = [float(v) for v in result.split(",")]
    assert (x, y) == (0.25, 0.5)
    # 1.5 * 427 * 2 / 378 -- the patch is drawn at 1.5 * 427 * 2 X screen px,
    # i.e. the same size the 640 px (HiDPI-scaled) measure frame had
    assert scale == pytest.approx(1.5 * 427 * 2 / 378)


def test_get_argyll_measureframe_dimensions_without_x_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an X screen, the scale is passed through unchanged."""
    monkeypatch.setattr(real_display_size_mm, "get_x_screen_px_per_mm", lambda: None)
    assert get_argyll_measureframe_dimensions("0.25,0.5,1.5") == "0.25,0.5,1.5"


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
