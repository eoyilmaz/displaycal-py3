from DisplayCAL.dev.mocks import check_call_str


def test_update_estimated_measurement_time_1(setup_argyll):
    """Testing for issue #37.

    ReportFrame.update_estimated_measurement_time() method raising
    TypeError.
    """
    import wx

    from DisplayCAL.config import initcfg
    from DisplayCAL.wx_report_frame import ReportFrame

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


def test_devlink_profile_missing_hint(setup_argyll, data_path):
    """The "no 3D LUT is verified" hint follows the device link (issue 992)."""
    import wx

    from DisplayCAL.config import get_data_path, initcfg, setcfg
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL.wx_report_frame import ReportFrame

    initcfg()
    app = wx.GetApp() or wx.App()  # noqa: F841

    with check_call_str(
        "DisplayCAL.worker.Worker.get_instrument_name",
        "i1 DisplayPro, ColorMunki Display",
    ):
        report_frame = ReportFrame()
    try:
        report_frame.simulation_profile = ICCProfile(get_data_path("ref/Rec709.icm"))
        # set_profile("simulation") would have looked this up via xicclu
        report_frame.XYZbpin = [0, 0, 0]
        setcfg("measurement_report.chart.fields", "RGB")
        setcfg("measurement_report.use_simulation_profile", 1)
        setcfg("measurement_report.use_simulation_profile_as_output", 1)

        setcfg("measurement_report.use_devlink_profile", 0)
        report_frame.mr_update_main_controls()
        assert report_frame.devlink_profile_missing_label.IsShown()
        assert report_frame.devlink_profile_missing_bmp.IsShown()

        setcfg("measurement_report.use_devlink_profile", 1)
        setcfg(
            "measurement_report.devlink_profile",
            str(
                data_path
                / "icc"
                / "BenQ SW271 #1 2021-11-17 14-21 2.2 F-S 1xCurve+MTX.icc"
            ),
        )
        report_frame.mr_update_main_controls()
        assert not report_frame.devlink_profile_missing_label.IsShown()
        assert not report_frame.devlink_profile_missing_bmp.IsShown()
    finally:
        for name in (
            "measurement_report.chart.fields",
            "measurement_report.use_simulation_profile",
            "measurement_report.use_simulation_profile_as_output",
            "measurement_report.use_devlink_profile",
            "measurement_report.devlink_profile",
        ):
            setcfg(name, None)
        report_frame.Destroy()
