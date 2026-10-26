"""Tests for the Qt curve-viewer action buttons added for issue #849.

Exercises ``DisplayCAL.ui.tools.curve_viewer.CurvePanel``/``CurveViewerWindow``
under the shared offscreen ``QApplication``: the vcgt-only action toolbar
(reload / BPC / install / save-CAL), saving the plot as an image, showing
advanced per-tag shaper curves, and the standalone window's per-monitor
auto-follow. Argyll ``dispwin``/``xicclu`` calls are stubbed so no real
display or Argyll install is needed. See ``DisplayCAL/wx_lut_viewer.py``
(``LUTFrame``) for the wx originals these mirror.
"""

import os
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.config import setcfg  # noqa: E402
from DisplayCAL.icc_profile import ICCProfile  # noqa: E402
from DisplayCAL.ui.tools import curve_viewer as cv  # noqa: E402
from DisplayCAL.worker import Worker  # noqa: E402

_ICC_DIR = os.path.join(os.path.dirname(__file__), "data", "icc")

#: Non-zero vcgt black point + A2B/B2A LUT16Type cLUT tags.
_CLUT_PROFILE = os.path.join(
    _ICC_DIR, "Monitor 1 #1 2022-03-09 16-13 D6500 2.2 F-S XYZLUT+MTX.icc"
)
#: Clean ASCII description, vcgt only (no cLUT tags).
_VCGT_PROFILE = os.path.join(_ICC_DIR, "vcgt_cm_test_cyanish_reddish.icc")


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
def _init_config():
    config.initcfg()
    setcfg("show_advanced_options", 0)
    yield


def _spin_until(qapp, predicate, timeout_s=30.0):
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


@pytest.fixture
def panel(qapp):
    p = cv.CurvePanel()
    yield p
    p.deleteLater()


# -- vcgt action toolbar visibility ------------------------------------------


def test_vcgt_actions_hidden_outside_vcgt_mode(panel):
    profile = ICCProfile(_CLUT_PROFILE)  # has vcgt + trc + measured modes
    panel.set_profile(profile)
    panel.set_mode("trc")

    assert panel.vcgt_actions_row.isHidden()


def test_vcgt_actions_shown_and_enabled_in_vcgt_mode(panel):
    profile = ICCProfile(_CLUT_PROFILE)
    panel.set_profile(profile)
    assert panel.set_mode("vcgt")

    assert not panel.vcgt_actions_row.isHidden()
    assert panel.reload_vcgt_btn.isEnabled()
    assert panel.install_vcgt_btn.isEnabled()
    assert panel.save_vcgt_btn.isEnabled()
    # This fixture's vcgt has a non-zero black point (see test_ui_plot_curve_data.py).
    assert panel.apply_bpc_btn.isEnabled()


def test_apply_bpc_disabled_when_black_point_already_zero(panel):
    profile = ICCProfile(_VCGT_PROFILE)
    assert profile.tags["vcgt"].getNormalizedValues()[0] == (0.0, 0.0, 0.0)
    panel.set_profile(profile)
    panel.set_mode("vcgt")

    assert not panel.apply_bpc_btn.isEnabled()


# -- vcgt actions -------------------------------------------------------------


def test_apply_bpc_click_reloads_a_zeroed_profile(panel):
    profile = ICCProfile(_CLUT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")

    panel._apply_bpc()

    assert panel._profile is not profile
    assert panel._profile.tags["vcgt"].getNormalizedValues()[0] == pytest.approx(
        (0.0, 0.0, 0.0), abs=1e-9
    )


def test_install_vcgt_button_runs_worker_and_clears_status(
    qapp, panel, monkeypatch, tmp_path
):
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")
    calls = []
    monkeypatch.setattr(
        Worker, "prepare_dispwin", lambda self, cal: (["dispwin"], ["-d1", cal])
    )
    monkeypatch.setattr(
        Worker, "exec_cmd", lambda self, *a, **k: calls.append(a) or True
    )
    monkeypatch.setattr(Worker, "create_tempdir", lambda self: str(tmp_path))

    panel.install_vcgt_btn.click()
    assert _spin_until(qapp, lambda: panel._action_thread is None)

    assert calls
    assert lang.getstr("error") not in panel.status.text()


def test_install_vcgt_button_reports_exception(qapp, panel, monkeypatch):
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")
    monkeypatch.setattr(
        Worker,
        "prepare_dispwin",
        lambda self, cal: (_ for _ in ()).throw(RuntimeError("no dispwin")),
    )

    panel.install_vcgt_btn.click()
    assert _spin_until(qapp, lambda: panel._action_thread is None)

    assert "no dispwin" in panel.status.text()


def test_reload_vcgt_button_updates_profile(qapp, panel, monkeypatch):
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")
    other_profile = ICCProfile(_CLUT_PROFILE)
    monkeypatch.setattr(
        Worker, "prepare_dispwin", lambda self, cal: (["dispwin"], ["-d1"])
    )
    monkeypatch.setattr(Worker, "exec_cmd", lambda self, *a, **k: True)
    monkeypatch.setattr(config, "get_display_profile", lambda: other_profile)

    panel.reload_vcgt_btn.click()
    assert _spin_until(qapp, lambda: panel._action_thread is None)

    assert panel._profile is other_profile


# -- save ----------------------------------------------------------------------


def test_save_cal_writes_vcgt_file(panel, monkeypatch, tmp_path):
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")
    out_path = str(tmp_path / "out.cal")
    monkeypatch.setattr(
        cv.QFileDialog, "getSaveFileName", lambda *a, **k: (out_path, "")
    )

    panel._save_cal()

    assert os.path.isfile(out_path)
    with open(out_path) as f:
        assert "CAL" in f.read()


def test_save_cal_noop_when_dialog_cancelled(panel, monkeypatch, tmp_path):
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")
    monkeypatch.setattr(cv.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))

    panel._save_cal()  # must not raise despite no chosen path


def test_save_plot_exports_image(panel, monkeypatch, tmp_path):
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    panel.set_mode("vcgt")
    out_path = str(tmp_path / "out.png")
    monkeypatch.setattr(
        cv.QFileDialog, "getSaveFileName", lambda *a, **k: (out_path, "")
    )

    panel._save_plot()

    assert os.path.isfile(out_path)


def test_save_plot_button_enabled_only_with_curves(panel):
    assert not panel.save_plot_btn.isEnabled()
    profile = ICCProfile(_VCGT_PROFILE)
    panel.set_profile(profile)
    assert panel.save_plot_btn.isEnabled()


# -- advanced shaper curves -----------------------------------------------------


def test_shaper_modes_hidden_without_advanced_options(panel):
    profile = ICCProfile(_CLUT_PROFILE)
    panel.set_profile(profile)

    modes = [panel.mode_combo.itemData(i) for i in range(panel.mode_combo.count())]
    assert not any("." in m for m in modes)


def test_shaper_modes_listed_and_drawn_with_advanced_options(panel):
    setcfg("show_advanced_options", 1)
    profile = ICCProfile(_CLUT_PROFILE)
    panel.set_profile(profile)

    modes = [panel.mode_combo.itemData(i) for i in range(panel.mode_combo.count())]
    assert "A2B0.input" in modes

    assert panel.set_mode("A2B0.input")
    assert set(panel.plot._channels) == {"R", "G", "B"}
    # Shaper curves aren't vcgt: the toolbar stays hidden.
    assert panel.vcgt_actions_row.isHidden()


# -- per-monitor auto-follow (standalone window only) --------------------------


def test_follow_display_loads_that_displays_profile(qapp, monkeypatch):
    window = cv.CurveViewerWindow()
    try:
        other_profile = ICCProfile(_VCGT_PROFILE)
        monkeypatch.setattr(cv, "get_display_profile", lambda display_no: other_profile)

        window.panel.follow_display(2)

        assert window.panel._profile is other_profile
    finally:
        window.close()


def test_follow_display_shows_live_lut_when_actual_lut_checked(qapp, monkeypatch):
    window = cv.CurveViewerWindow()
    try:
        # Set the checked state without running the real (dispwin-driving)
        # toggled handler; follow_display() only reads isChecked().
        window.panel.actual_lut_check.blockSignals(True)
        window.panel.actual_lut_check.setChecked(True)
        window.panel.actual_lut_check.blockSignals(False)
        called = []
        monkeypatch.setattr(
            window.panel,
            "_on_actual_lut_toggled",
            lambda checked: called.append(checked),
        )

        window.panel.follow_display(0)

        assert called == [True]
    finally:
        window.close()
