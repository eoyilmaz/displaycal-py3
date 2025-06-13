from DisplayCAL.dev.mocks import check_call, check_call_str
from tests.data.display_data import DisplayData


def test_update_estimated_measurement_time_1(setup_argyll):
    """Testing for issue #37.

    ReportFrame.update_estimated_measurement_time() method raising
    TypeError.
    """
    from DisplayCAL.config import initcfg
    from DisplayCAL.wx_report_frame import ReportFrame
    import wx

    initcfg()
    app = wx.GetApp() or wx.App()

    with check_call_str(
        "DisplayCAL.worker.Worker.get_instrument_name",
        "i1 DisplayPro, ColorMunki Display",
        call_count=2,
    ):
        report_frame = ReportFrame()
        # this shouldn't raise any TypeErrors as reported in #37
        report_frame.update_estimated_measurement_time("chart")
