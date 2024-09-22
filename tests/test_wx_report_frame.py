# -*- coding: utf-8 -*-

from DisplayCAL.dev.mocks import check_call, check_call_str
from tests.data.display_data import DisplayData


def test_update_estimated_measurement_time_1(argyll):
    """Testing for issue #37

    wxReportFrame.ReportFrame.update_estimated_measurement_time() method raising
    TypeError.
    """
    from DisplayCAL.config import initcfg
    from DisplayCAL.wxReportFrame import ReportFrame
    import wx

    initcfg()
    app = wx.GetApp()
    if not app:
        app = wx.App()

    with check_call_str(
        "DisplayCAL.worker.Worker.get_instrument_name",
        "i1 DisplayPro, ColorMunki Display",
        call_count=2,
    ):
        report_frame = ReportFrame()
        # this shouldn't raise any TypeErrors as reported in #37
        report_frame.update_estimated_measurement_time("chart")
