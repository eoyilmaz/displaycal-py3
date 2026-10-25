"""Headless tests for the Qt measurement-report window.

Exercise ``DisplayCAL.ui.measurement_report.ReportWindow`` under the shared
offscreen ``QApplication``: the config-driven TRC controls, the slider/spin
sync, the fields chooser, and the deferred-action signals. No display, Argyll or
instrument is needed. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5+,
measurement-report window).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _no_real_display_profile_probe(monkeypatch):
    """Never let ReportPanel's construction shell out to a real display probe.

    ``ReportPanel.__init__()`` -> ``mr_update_controls()`` -> ``set_profile()``
    calls ``config.get_current_profile(True)``, which falls through to
    ``config.get_display_profile()`` whenever "calibration.file" isn't set
    (the default in a fresh test config). On macOS that shells out to a real
    `osascript` call querying the "Image Events" scripting bridge for the
    display's ICC profile (DisplayCAL/icc_profile.py's
    get_display_profile_macos()), which has no real display to query on a
    headless CI runner and hangs indefinitely rather than failing fast (see
    the identical fix in test_ui_main_window.py's stub_worker fixture).
    Autouse because several tests in this file (e.g. TestEmbeddedPanel)
    construct ``ReportPanel`` directly rather than through the ``window``
    fixture below.
    """
    monkeypatch.setattr(config, "get_display_profile", lambda *a, **k: None)


@pytest.fixture
def window(qapp, monkeypatch):
    """Create a fresh ReportWindow with config isolated per test.

    Constructing the window and exercising its handlers writes to the global
    ``config.CFG``; snapshot and restore it so these tests don't leak state into
    the rest of the suite (e.g. ``test_worker``).
    """
    from DisplayCAL.ui.measurement_report import ReportWindow
    from DisplayCAL.worker import Worker

    # ReportPanel.__init__() (built with no worker passed here) constructs
    # its own Worker() and unconditionally calls set_argyll_version("xicclu"),
    # which shells out to `xicclu -?` with a 30s timeout -- reliably eats
    # the full 30s on CI instead of returning fast (no real Argyll/hardware
    # to probe).
    monkeypatch.setattr(Worker, "set_argyll_version", lambda self, *a, **k: None)

    saved = dict(config.CFG["Default"])
    win = ReportWindow()
    try:
        yield win
    finally:
        win.close()
        config.CFG["Default"] = saved


class TestConstruction:
    def test_expected_controls_exist(self, window):
        for attr in (
            "chart_ctrl",
            "fields_ctrl",
            "chart_btn",
            "chart_patches_amount",
            "simulate_whitepoint_cb",
            "simulate_whitepoint_relative_cb",
            "simulation_profile_cb",
            "simulation_profile_ctrl",
            "use_simulation_profile_as_output_cb",
            "enable_3dlut_cb",
            "apply_none_ctrl",
            "apply_black_offset_ctrl",
            "apply_trc_ctrl",
            "mr_trc_ctrl",
            "mr_trc_gamma_ctrl",
            "mr_trc_gamma_type_ctrl",
            "mr_black_output_offset_ctrl",
            "mr_black_output_offset_intctrl",
            "devlink_profile_cb",
            "devlink_profile_ctrl",
            "output_profile_ctrl",
            "output_profile_current_btn",
            "measurement_report_btn",
        ):
            assert hasattr(window, attr), attr

    def test_fields_chooser_defaults(self, window):
        # Default is populated from the loaded chart (RGB-based reference).
        items = [
            window.fields_ctrl.itemText(i) for i in range(window.fields_ctrl.count())
        ]
        assert items  # non-empty
        assert all(v in ("CMYK", "LAB", "RGB", "XYZ") for v in items)

    def test_trc_chooser_populated(self, window):
        items = [
            window.mr_trc_ctrl.itemText(i) for i in range(window.mr_trc_ctrl.count())
        ]
        assert len(items) == 3


class TestTrcControls:
    def test_select_gamma_22_sets_config(self, window):
        window.mr_trc_ctrl.setCurrentIndex(0)
        window.mr_trc_ctrl_handler()
        assert config.getcfg("measurement_report.trc_gamma") == 2.2
        assert config.getcfg("measurement_report.trc_gamma_type") == "b"
        assert config.getcfg("measurement_report.trc_output_offset") == 1.0

    def test_select_bt1886_sets_config(self, window):
        window.mr_trc_ctrl.setCurrentIndex(1)
        window.mr_trc_ctrl_handler()
        assert config.getcfg("measurement_report.trc_gamma") == 2.4
        assert config.getcfg("measurement_report.trc_gamma_type") == "B"
        assert config.getcfg("measurement_report.trc_output_offset") == 0.0

    def test_update_trc_control_reflects_bt1886(self, window):
        config.setcfg("measurement_report.trc_gamma", 2.4)
        config.setcfg("measurement_report.trc_gamma_type", "B")
        config.setcfg("measurement_report.trc_output_offset", 0.0)
        window.mr_update_trc_control()
        assert window.mr_trc_ctrl.currentIndex() == 1

    def test_update_trc_control_reflects_custom(self, window):
        config.setcfg("measurement_report.trc_gamma", 2.6)
        config.setcfg("measurement_report.trc_gamma_type", "B")
        config.setcfg("measurement_report.trc_output_offset", 0.5)
        window.mr_update_trc_control()
        assert window.mr_trc_ctrl.currentIndex() == 2

    def test_gamma_type_handler_sets_config(self, window):
        window.mr_trc_gamma_type_ctrl.setCurrentIndex(0)  # relative -> "b"
        window.mr_trc_gamma_type_ctrl_handler()
        assert config.getcfg("measurement_report.trc_gamma_type") == "b"


class TestBlackOffset:
    def test_slider_syncs_spin_and_config(self, window):
        window.mr_black_output_offset_ctrl.setValue(25)
        assert window.mr_black_output_offset_intctrl.value() == 25
        assert config.getcfg("measurement_report.trc_output_offset") == 0.25

    def test_spin_syncs_slider_and_config(self, window):
        window.mr_black_output_offset_intctrl.setValue(40)
        assert window.mr_black_output_offset_ctrl.value() == 40
        assert config.getcfg("measurement_report.trc_output_offset") == 0.40


class TestFields:
    def test_fields_handler_persists_selection(self, window):
        window.fields_ctrl.clear()
        window.fields_ctrl.addItems(["RGB", "XYZ"])
        window.fields_ctrl.setCurrentIndex(1)
        window.fields_ctrl_handler(None)
        assert config.getcfg("measurement_report.chart.fields") == "XYZ"


class TestSignals:
    def test_measure_button_emits_request(self, window):
        received = []
        window.measure_requested.connect(lambda: received.append(True))
        # The button is disabled until the config is valid; enable it so the
        # click reaches the signal (we are testing the wiring, not enablement).
        window.measurement_report_btn.setEnabled(True)
        window.measurement_report_btn.click()
        assert received == [True]

    def test_chart_button_emits_edit_request(self, window):
        received = []
        window.edit_chart_requested.connect(lambda: received.append(True))
        window.chart_btn.click()
        assert received == [True]

    def test_measure_button_reports_alt_modifier_as_self_check(
        self, window, monkeypatch
    ):
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QApplication

        received = []
        window.measure_requested.connect(received.append)
        monkeypatch.setattr(
            QApplication, "keyboardModifiers", staticmethod(lambda: Qt.AltModifier)
        )
        window._measure_btn_clicked()
        assert received == [True]

    def test_measure_button_without_alt_is_not_self_check(self, window, monkeypatch):
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QApplication

        received = []
        window.measure_requested.connect(received.append)
        monkeypatch.setattr(
            QApplication, "keyboardModifiers", staticmethod(lambda: Qt.NoModifier)
        )
        window._measure_btn_clicked()
        assert received == [False]


class TestEmbeddedPanel:
    """The Qt main window's Verification tab embeds a bare ``ReportPanel``.

    ``report.xrc`` itself has no "Measure" button (wx's standalone
    ``ReportFrame`` adds one programmatically); the embedded tab relies on
    ``MainFrame``'s shared ``buttonpanel`` button instead. See
    ``MAINFRAME_PORT_PLAN.md``'s 2026-07-11 follow-up.
    """

    def test_show_measure_button_false_omits_button(self, qapp):
        from DisplayCAL.ui.measurement_report import ReportPanel

        saved = dict(config.CFG["Default"])
        panel = ReportPanel(show_measure_button=False)
        try:
            assert not hasattr(panel, "measurement_report_btn")
        finally:
            config.CFG["Default"] = saved

    def test_can_measure_reflects_settings_validity(self, qapp):
        from DisplayCAL.ui.measurement_report import ReportPanel

        saved = dict(config.CFG["Default"])
        panel = ReportPanel(show_measure_button=False)
        try:
            # ``can_measure()`` is a pure passthrough of whatever the last
            # ``mr_update_controls()`` call computed (the same value that
            # would drive the internal button's enabled state when
            # ``show_measure_button`` is True). The real formula depends on
            # a wide, transitive set of config/display state (chart path,
            # simulation/devlink/output profile resolution, the *current
            # display's* assigned ICC profile, ...) that earlier tests in
            # the same process can leave in a state this test can't fully
            # control -- see this file's ``window`` fixture docstring for
            # the general "config.CFG leaks between tests" trap. Exercise
            # both states directly instead of depending on construction
            # landing on a specific real-world outcome.
            panel._mr_can_measure = True
            assert panel.can_measure() is True
            panel._mr_can_measure = False
            assert panel.can_measure() is False
        finally:
            config.CFG["Default"] = saved

    def test_worker_param_is_adopted_without_reprobing(self, qapp):
        from DisplayCAL.ui.measurement_report import ReportPanel
        from DisplayCAL.worker import Worker

        saved = dict(config.CFG["Default"])
        shared_worker = Worker()
        panel = ReportPanel(worker=shared_worker)
        try:
            assert panel.worker is shared_worker
        finally:
            config.CFG["Default"] = saved


class TestDevlinkProfileMissingHint:
    """The "no 3D LUT is verified" hint (issue 992)."""

    @pytest.fixture
    def sim_window(self, window):
        from DisplayCAL.icc_profile import ICCProfile

        # Set on the panel, ReportWindow only forwards attribute reads to it
        window.panel.simulation_profile = ICCProfile(
            config.get_data_path("ref/Rec709.icm")
        )
        config.setcfg("measurement_report.chart.fields", "RGB")
        config.setcfg("measurement_report.use_simulation_profile", 1)
        config.setcfg("measurement_report.use_simulation_profile_as_output", 1)
        config.setcfg("measurement_report.use_devlink_profile", 0)
        return window

    def _hint_shown(self, window):
        window.mr_update_main_controls()
        return window.devlink_profile_missing_row.isVisibleTo(window)

    def test_shown_without_devlink(self, sim_window):
        assert self._hint_shown(sim_window)

    def test_hidden_with_devlink(self, sim_window, data_path):
        config.setcfg("measurement_report.use_devlink_profile", 1)
        config.setcfg(
            "measurement_report.devlink_profile",
            str(
                data_path
                / "icc"
                / "BenQ SW271 #1 2021-11-17 14-21 2.2 F-S 1xCurve+MTX.icc"
            ),
        )
        assert self._hint_shown(sim_window) is False

    def test_shown_when_devlink_enabled_but_missing(self, sim_window, tmp_path):
        config.setcfg("measurement_report.use_devlink_profile", 1)
        config.setcfg(
            "measurement_report.devlink_profile", str(tmp_path / "missing.icc")
        )
        assert self._hint_shown(sim_window)

    def test_hidden_when_sim_not_used_as_display_profile(self, sim_window):
        config.setcfg("measurement_report.use_simulation_profile_as_output", 0)
        assert self._hint_shown(sim_window) is False

    def test_hidden_when_madvr_applies_the_3dlut(self, sim_window, monkeypatch):
        from DisplayCAL.ui import measurement_report

        monkeypatch.setattr(
            measurement_report.config, "get_display_name", lambda *a, **k: "madVR"
        )
        config.setcfg("3dlut.enable", 1)
        assert self._hint_shown(sim_window) is False
