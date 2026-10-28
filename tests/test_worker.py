from __future__ import annotations

import configparser
import io
import os
import pathlib
import shutil
import sys
import tempfile
from unittest.mock import MagicMock
from urllib.error import URLError

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.argyll import (
    get_argyll_latest_version,
    get_argyll_util,
    make_argyll_compatible_path,
)
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import getcfg, initcfg, setcfg
from DisplayCAL.debughelpers import Error
from DisplayCAL.dev.mocks import check_call_str
from DisplayCAL.icc_profile import (
    ICCProfile,
    ICCProfileTag,
    LUT16Type,
    MakeAndModelType,
)
from DisplayCAL.meta import DOMAIN
from DisplayCAL.worker import (
    Sudo,
    Worker,
    add_keywords_to_cgats,
    check_cal_isfile,
    check_create_dir,
    check_file_isfile,
    check_profile_isfile,
    check_ti3_criteria1,
    create_shaper_curves,
    extract_device_gray_primaries,
    get_argyll_version_string,
    get_options_from_profile,
    get_pattern_geometry,
)
from tests.data.display_data import DisplayData


def test_get_options_from_profile_1(data_files):
    """Test ``DisplayCAL.worker.get_options_from_profile()`` function"""
    profile_path = data_files[
        "UP2516D #1 2022-03-23 16-06 D6500 2.2 F-S XYZLUT+MTX.icc"
    ].absolute()
    options = get_options_from_profile(profile=profile_path)
    assert options == (
        [
            "t6500",
            "g2.2",
            "f1.0",
            "A4.0",
            "d1",
            "c1",
            "yl",
            "P0.48923385077616427,0.8797619047619047,1.4894179894179895",
            "H",
        ],
        ["qh", "aX", 'A "Dell, Inc."'],
    )


def test_get_options_from_profile_2(data_files):
    """Test ``DisplayCAL.worker.get_options_from_profile()`` function, for #69"""
    profile_path = data_files["SW271 PM PenalNative_KB1_160_2022-03-17.icc"].absolute()
    options = get_options_from_profile(profile=profile_path)
    assert options == ([], [])  # no options on that profile


def test_make_argyll_compatible_path_1():
    """make_argyll_compatible_path is working properly with bytes input."""
    test_value = "C:\\Program Files\\some path\\executable.exe"
    result = make_argyll_compatible_path(test_value)
    if sys.platform == "win32":
        expected_result = "C:\\Program Files\\some path\\executable.exe"
    else:
        expected_result = "C_Program Files_some path_executable.exe"
    assert result == expected_result


def test_make_argyll_compatible_path_2():
    """make_argyll_compatible_path is working properly with bytes input."""
    test_value = b"C:\\Program Files\\some path\\executable.exe"
    result = make_argyll_compatible_path(test_value)
    if sys.platform == "win32":
        expected_result = b"C:\\Program Files\\some path\\executable.exe"
    else:
        expected_result = b"C_Program Files_some path_executable.exe"
    assert result == expected_result


def test_make_argyll_compatible_path_is_name_strips_path_separators():
    """A profile name/description containing '/' must not be able to smuggle
    a path separator into the sanitized filename (#819)."""
    test_value = "My Display / Profile"
    result = make_argyll_compatible_path(test_value, is_name=True)
    assert "/" not in result
    assert os.path.sep not in result
    assert result == "My Display _ Profile"


def test_make_argyll_compatible_path_is_name_strips_path_separators_bytes():
    """Same as above but for bytes input."""
    test_value = b"My Display / Profile"
    result = make_argyll_compatible_path(test_value, is_name=True)
    assert b"/" not in result
    assert result == b"My Display _ Profile"


def test_make_argyll_compatible_path_is_name_strips_all_invalid_chars():
    """is_name=True should strip the full set of filename-invalid characters,
    not just path separators."""
    test_value = 'a\\b/c:d;e*f?g"h<i>j|k'
    result = make_argyll_compatible_path(test_value, is_name=True)
    for char in '\\/:;*?"<>|':
        assert char not in result


def test_clear_cmd_output_tolerates_cleared_thread_attribute():
    """``clear_cmd_output`` must not crash when ``worker.thread`` is ``None``.

    The Qt ``WorkerRunController`` sets ``worker.thread = None`` right before
    calling its consumer (``ui/worker_runner.py``'s ``_ProducerThread``), so a
    consumer that itself calls ``exec_cmd`` (and thus ``clear_cmd_output``)
    hits this exact state -- confirmed via a live crash where
    ``ui/main_window.py``'s ``_on_profile_build_finished`` called
    ``self._load_cal(...)`` -> ``worker.exec_cmd`` ->
    ``clear_cmd_output`` with ``self.thread`` already ``None``.
    ``hasattr(self, "thread")`` is True in that state (the attribute exists,
    just set to ``None``), so the old ``hasattr(...) and
    self.thread.is_alive()`` guard still called ``.is_alive()`` on ``None``.
    """
    worker = Worker()
    worker.thread = None
    worker.interactive = True
    # Must not raise AttributeError: 'NoneType' object has no attribute 'is_alive'.
    worker.clear_cmd_output()


def test_write_frame_insertion_logs_float_config_values(monkeypatch, tmp_path):
    """Frame insertion must not crash on its float config values (issue 984).

    ``patterngenerator.ffp_insertion.duration`` and ``.level`` are floats
    (defaults 5.0 and 0.15), so formatting them with ``:d`` in the log line
    raised ``ValueError: Unknown format code 'd' for object of type 'float'``
    as soon as the first frame insertion was due.
    """
    cfg = {
        "patterngenerator.ffp_insertion": 1,
        "patterngenerator.ffp_insertion.interval": 0.0,
        "patterngenerator.ffp_insertion.duration": 2.5,
        "patterngenerator.ffp_insertion.level": 0.15,
        "measure.override_min_display_update_delay_ms": 0,
    }
    worker = Worker()
    monkeypatch.setattr(
        "DisplayCAL.worker.getcfg",
        lambda name, *args, **kwargs: (
            cfg[name] if name in cfg else getcfg(name, *args, **kwargs)
        ),
    )
    monkeypatch.setattr(Worker, "_use_patternwindow", True)
    worker.use_madnet_tpg = False
    worker.patterngenerator_sent_count = 2
    worker.tempdir = str(tmp_path)
    # Skip the frame insertion and settle delays.
    worker.thread_abort = True
    sent = []
    monkeypatch.setattr(
        worker, "patterngenerator_send", lambda rgb, *args, **kwargs: sent.append(rgb)
    )
    monkeypatch.setattr(worker, "audio_visual_feedback", lambda txt: None)
    monkeypatch.setattr(worker, "parse", lambda txt: None)
    logged = []
    monkeypatch.setattr(worker, "log", lambda *args, **kwargs: logged.append(args))

    worker._write("Current RGB 0 0 0 0.5000 0.5000 0.5000\n")

    assert any(
        "Frame insertion duration 2.5s, level = 15%" in str(args[0]) for args in logged
    )
    assert sent == [(0.15, 0.15, 0.15), [0.5, 0.5, 0.5]]


def test_worker_get_instrument_name_1():
    """Worker.get_instrument_name() is working properly."""
    worker = Worker()
    result = worker.get_instrument_name()
    expected_result = ""
    assert result == expected_result


def test_worker_get_instrument_features():
    """Worker.get_instrument_features() is working properly."""
    worker = Worker()
    result = worker.get_instrument_features()
    assert result == {}


def test_worker_instrument_supports_css_1():
    """Testing if Worker.instrument_supports_ccss is working properly"""
    worker = Worker()
    result = worker.instrument_supports_ccss()
    expected_result = None
    assert result == expected_result


@pytest.mark.parametrize("measurement_mode", ["-yo", "-ym"])
@pytest.mark.parametrize("argyll_version", [[3, 4, 1], [3, 5, 0]])
def test_check_spyder2024_measurement_mode_rejects_broken_modes(
    measurement_mode, argyll_version
):
    """OLED/Mini-LED on a Spyder 2024 is rejected with ArgyllCMS <= 3.5.0."""
    lang.init()
    worker = Worker()
    worker.argyll_version = argyll_version
    worker.argyll_version_string = ".".join(str(n) for n in argyll_version)
    result = worker.check_spyder2024_measurement_mode(
        ["-v", measurement_mode], "Spyder 2024"
    )
    assert isinstance(result, Error)
    assert worker.argyll_version_string in str(result)


@pytest.mark.parametrize(
    "instrument_name,measurement_mode,argyll_version",
    [
        ("Spyder 2024", "-ye", [3, 5, 0]),
        ("Spyder 2024", "-yl", [3, 5, 0]),
        ("Spyder 2024", "-yo", [3, 5, 1]),
        ("Spyder 2024", "-ym", [3, 6, 0]),
        ("SpyderX2", "-yo", [3, 5, 0]),
        ("i1 DisplayPro, ColorMunki Display, Spyder4", "-ym", [3, 5, 0]),
    ],
)
def test_check_spyder2024_measurement_mode_allows_other_cases(
    instrument_name, measurement_mode, argyll_version
):
    """Other modes, instruments and newer ArgyllCMS versions pass the check."""
    worker = Worker()
    worker.argyll_version = argyll_version
    result = worker.check_spyder2024_measurement_mode(
        ["-v", measurement_mode], instrument_name
    )
    assert result is None


def test_check_spyder2024_measurement_mode_without_mode_arg():
    """No ``-y`` argument (e.g. ambient measurement) passes the check."""
    worker = Worker()
    worker.argyll_version = [3, 5, 0]
    assert worker.check_spyder2024_measurement_mode(["-v", "-a"], "Spyder 2024") is None


def test_add_measurement_features_rejects_spyder2024_oled(monkeypatch):
    """add_measurement_features() returns the Spyder 2024 OLED error."""
    worker = Worker()
    worker.argyll_version = [3, 5, 0]
    worker.argyll_version_string = "3.5.0"
    monkeypatch.setattr(worker, "get_instrument_name", lambda: "Spyder 2024")
    measurement_mode = getcfg("measurement_mode")
    setcfg("measurement_mode", "o")
    try:
        result = worker.add_measurement_features(["-v"], display=False)
    finally:
        setcfg("measurement_mode", measurement_mode)
    assert isinstance(result, Error)


@pytest.mark.parametrize(
    "native_wayland, expected",
    [(False, "-P0.1,0.9,4.711"), (True, "-P0.5,0.5,4.711")],
)
def test_add_measurement_features_measureframe(monkeypatch, native_wayland, expected):
    """The measure frame position is passed on unless the UI is native Wayland.

    On native Wayland only the user's scale is kept and the patch is centered.
    The stored scale is converted to Argyll ``-P`` units either way.
    """
    worker = Worker()
    worker.argyll_version = [3, 5, 0]
    worker.argyll_version_string = "3.5.0"
    monkeypatch.setattr(worker, "get_instrument_name", lambda: "i1 DisplayPro")
    monkeypatch.setattr(config, "get_display_name", lambda *args: "Monitor 1")
    monkeypatch.setattr(config, "is_ui_native_wayland", lambda: native_wayland)

    def fake_convert(dimensions_measureframe):
        x, y, _scale = dimensions_measureframe.split(",")
        return f"{x},{y},4.711"

    monkeypatch.setattr(
        "DisplayCAL.worker.get_argyll_measureframe_dimensions", fake_convert
    )
    measureframe = getcfg("dimensions.measureframe")
    setcfg("dimensions.measureframe", "0.1,0.9,2.5")
    args = ["-v"]
    try:
        result = worker.add_measurement_features(args, display=True)
    finally:
        setcfg("dimensions.measureframe", measureframe)
    assert result is True
    assert expected in args


def test_add_measurement_features_chromecast_skips_measureframe_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chromecast sizing is percentage-based and must not use X-pixel units."""
    worker = Worker()
    worker.argyll_version = [3, 5, 0]
    worker.argyll_version_string = "3.5.0"
    monkeypatch.setattr(worker, "get_instrument_name", lambda: "i1 DisplayPro")
    monkeypatch.setattr(config, "get_display_name", lambda *args: "Monitor 1")
    monkeypatch.setattr(config, "is_ui_native_wayland", lambda: False)
    monkeypatch.setattr(
        config, "get_measureframe_dimensions", lambda dimensions, percent: "0.5,0.5,2.0"
    )
    monkeypatch.setattr(
        "DisplayCAL.worker.get_argyll_measureframe_dimensions",
        lambda dimensions: pytest.fail("Chromecast dimensions must not be converted"),
    )
    args = ["-v", "-dcc"]
    assert worker.add_measurement_features(args, display=True) is True
    assert "-P0.5,0.5,2.0" in args


@pytest.mark.parametrize("native_wayland", [False, True])
def test_get_pattern_geometry_position(monkeypatch, native_wayland):
    """The pattern is only forced to the center on native Wayland."""
    monkeypatch.setattr(config, "get_display_name", lambda *args: "Monitor 1")
    monkeypatch.setattr(config, "is_ui_native_wayland", lambda: native_wayland)
    measureframe = getcfg("dimensions.measureframe")
    setcfg("dimensions.measureframe", "0,0,1.0")
    try:
        x, y, _w, _h, _size = get_pattern_geometry()
    finally:
        setcfg("dimensions.measureframe", measureframe)
    assert (x > 0 and y > 0) is native_wayland


# @pytest.mark.skip(reason="Test segfaults with python 3.12 - further investigation required.")
def test_generate_b2a_from_inverse_table(data_files, setup_argyll):
    """Test Worker.generate_B2A_from_inverse_table() method"""
    import wx

    from DisplayCAL.argyll import ARGYLL_UTILS
    from DisplayCAL.config import setcfg, writecfg

    # Other tests in this module call initcfg() which re-reads DisplayCAL.ini
    # from disk. Under xdist, a concurrent worker may have overwritten that
    # file with its own (now-deleted) temp Argyll path, poisoning our
    # in-process config. Re-assert the path from the session fixture and
    # flush the utility-lookup cache so get_argyll_util() searches fresh.
    setcfg("argyll.dir", str(setup_argyll))
    ARGYLL_UTILS.clear()
    writecfg()  # pool workers (SpawnPoolWorker-*) read config from disk

    # for some reason we sometimes need to have a wx.App() running
    _ = wx.GetApp() or wx.App()
    worker = Worker()
    icc_profile1 = ICCProfile(
        profile=data_files[
            "Monitor 1 #1 2022-03-09 16-13 D6500 2.2 F-S XYZLUT+MTX.icc"
        ].absolute()
    )
    logfile = io.StringIO()
    result = worker.generate_B2A_from_inverse_table(icc_profile1, logfile=logfile)
    assert result is True


def test_apply_black_offset_signature_uses_logfile() -> None:
    """ICCProfile/LUT16Type.apply_black_offset keep the ``logfile`` parameter.

    Guards the contract the caller relies on (see the functional test below).
    """
    import inspect

    for cls in (ICCProfile, LUT16Type):
        params = inspect.signature(cls.apply_black_offset).parameters
        assert "logfile" in params, (
            f"{cls.__name__}.apply_black_offset lost its 'logfile' parameter"
        )
        assert "logfiles" not in params, (
            f"{cls.__name__}.apply_black_offset must not use 'logfiles'"
        )


def test_blend_profile_blackpoint_calls_apply_black_offset_with_logfile(
    data_files, monkeypatch
) -> None:
    """blend_profile_blackpoint must call apply_black_offset with ``logfile=``.

    Regression: it used ``logfiles=``, which raised
    ``apply_black_offset() got an unexpected keyword argument 'logfiles'`` and
    aborted 3D LUT creation whenever a black offset was applied. profile1's
    apply_black_offset is replaced with a strict-signature stub (mirroring
    ICCProfile.apply_black_offset) so that a ``logfiles=`` call would raise
    TypeError here, exactly as it did in production.
    """
    icc_path = data_files[
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
    ].absolute()
    profile1 = ICCProfile(profile=icc_path)
    profile2 = ICCProfile(profile=icc_path)

    received = {}

    def strict_apply_black_offset(
        XYZbp,
        power=40.0,
        include_A2B=True,
        set_blackpoint=True,
        logfile=None,
        thread_abort=None,
        abortmessage="Aborted",
        include_trc=True,
    ):
        received["logfile"] = logfile

    profile1.apply_black_offset = strict_apply_black_offset

    worker = Worker()
    monkeypatch.setattr(
        worker, "xicclu", lambda profile, idata, **kwargs: [[0.0, 0.0, 0.0]]
    )
    # apply_trc=False forces the branch that applies the black offset.
    worker.blend_profile_blackpoint(profile1, profile2, apply_trc=False)

    assert "logfile" in received, "apply_black_offset was not called"
    assert received["logfile"] is not None


def test_generate_b2a_whitepoint_check_tolerance(data_files, monkeypatch) -> None:
    """The whitepoint sanity check accepts near-D50 and rejects grossly wrong.

    Regression: the check required the normalised white to round to exactly
    D50 (0.964, 1.0, 0.825), so a real profile whose adapted white was off D50
    by ~0.001 (chromatic adaptation / measurement / 16-bit encoding) was
    wrongly rejected with "Invalid white XYZ". It now uses a 0.01 tolerance,
    which still catches a grossly wrong white from a failed inverse lookup.
    """
    import wx

    _ = wx.GetApp() or wx.App()
    worker = Worker()
    profile = ICCProfile(
        profile=data_files[
            "Monitor 1 #1 2022-03-09 16-13 D6500 2.2 F-S XYZLUT+MTX.icc"
        ].absolute()
    )
    # xicclu returns [black, white, R, G, B] in XYZ for idata
    # [[0,0,0],[1,1,1],[1,0,0],[0,1,0],[0,0,1]].
    primaries = [[0.43, 0.22, 0.02], [0.38, 0.71, 0.10], [0.18, 0.07, 0.72]]

    # White ~0.001 off D50 (normalises to ~0.965/1.0/0.824) - must be accepted.
    def xicclu_near_d50(prof, idata, *args, **kwargs):
        return [[0.001, 0.001, 0.001], [0.9647, 0.9995, 0.8240], *primaries]

    monkeypatch.setattr(worker, "xicclu", xicclu_near_d50)
    try:
        worker.generate_B2A_from_inverse_table(profile, logfile=io.StringIO())
    except Exception as exc:  # may still fail later for unrelated reasons
        assert "Invalid white" not in str(exc), (
            "a near-D50 white was wrongly rejected by the sanity check"
        )

    # Grossly wrong white (normalises far from D50) - must still be rejected.
    def xicclu_bad_white(prof, idata, *args, **kwargs):
        return [[0.0, 0.0, 0.0], [0.5, 0.5, 0.4], *primaries]

    monkeypatch.setattr(worker, "xicclu", xicclu_bad_white)
    with pytest.raises(Error, match="Invalid white"):
        worker.generate_B2A_from_inverse_table(profile, logfile=io.StringIO())


def test_create_rgb_xyz_clut_fwd_profile_rgb_in_within_device_range(
    data_files, monkeypatch
) -> None:
    """The upsampled cLUT lookup grid must stay within device 0..100%.

    Regression for the stale ``step`` bug in create_RGB_XYZ_cLUT_fwd_profile:
    RGB_in was built with the previous low-resolution iclutres step, so its
    coordinates ran far past device 100% (e.g. iclutres=5 -> 32 * 25 = 800).
    xicclu(scale=100) then clamped those out-of-range inputs to the white
    corner, filling most of the A2B cLUT with the white point.
    """
    setcfg("profile.quality", "h")
    worker = Worker()
    ti3 = CGATS(
        str(
            data_files[
                "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.ti3"
            ].absolute()
        )
    )

    captured = {}

    def fake_xicclu(prof, idata, *args, **kwargs):
        # Capture the first lookup (the upsampling grid) and return in-gamut XYZ
        captured.setdefault("rgb_in", [list(row) for row in idata])
        return [[50.0, 50.0, 50.0] for _ in idata]

    monkeypatch.setattr(worker, "xicclu", fake_xicclu)
    worker.create_RGB_XYZ_cLUT_fwd_profile(ti3, "test", "", "", "")

    assert "rgb_in" in captured, "the cLUT upsampling lookup was never reached"
    max_value = max(max(row) for row in captured["rgb_in"])
    assert max_value <= 100.0 + 1e-6, (
        f"RGB_in grid overshoots device 100% (max={max_value:.2f}) - "
        "stale-step regression in create_RGB_XYZ_cLUT_fwd_profile"
    )


def test_sudo_class_initialization():
    """Test worker.Sudo class initialization"""
    sudo = Sudo()
    assert sudo is not None


def test_download_method_1():
    """Test Worker.download() method."""
    worker = Worker()
    uri = f"https://{DOMAIN}/i1d3"
    result = worker.download(uri)
    assert result is not None


def test_download_method_2():
    """Test Worker.download() method."""
    worker = Worker()
    uri = f"https://{DOMAIN}/i1d3"
    result = worker.download(uri, force=True)
    assert result is not None


def test_download_method_3():
    """Test Worker.download() method."""
    worker = Worker()
    uri = f"https://{DOMAIN}/spyd2"
    result = worker.download(uri)
    assert result is not None


def test_download_method_4():
    """Test Worker.download() method."""
    worker = Worker()
    uri = f"https://{DOMAIN}/spyd2"
    result = worker.download(uri, force=True)
    assert result is not None


def test_get_display_name_1():
    """Testing Worker.get_display_name() method."""
    initcfg()
    setcfg("display.number", 1)
    worker = Worker()
    result = worker.get_display_name(False, True, False)
    assert result == ""


def test_get_pwd():
    """Testing Worker.get_display_name() method."""
    initcfg()
    worker = Worker()
    test_value = "test_value"
    worker.pwd = test_value
    assert worker.pwd == test_value


def test_worker_password_prompt_defaults_to_none():
    """A fresh Worker has no password-prompt seam (wx fallback stays default)."""
    worker = Worker()
    assert worker.password_prompt is None


def test_detected_levels_issue_confirm_prefers_progress_wnd_confirm3():
    """Under Qt (progress_wnd.confirm3 present), no wx ConfirmDialog is built.

    Worker._detect_video_levels() used to build/show a 3-button wx
    ConfirmDialog directly, which asserts with "No wx.App created yet" when
    there is no running wx.App (the Qt UI path). detected_levels_issue_confirm
    must route through progress_wnd.confirm3() instead when it's available.
    """
    worker = Worker()
    seen = {}

    class FakeProgressWnd:
        def confirm3(self, msg, retry, alt, cancel):
            seen["msg"] = msg
            seen["retry"] = retry
            seen["alt"] = alt
            seen["cancel"] = cancel
            return "alt"

    worker.progress_wnd = FakeProgressWnd()
    worker._detected_levels_issue_confirm_wait = True
    worker.detected_levels_issue_confirm()
    assert seen  # confirm3 was actually called, not the wx dialog
    assert worker._use_detected_video_levels is True
    assert worker._detected_levels_issue_confirm_wait is False


def test_detect_video_levels_msvc_nan_readings_report_invalid_luminance(
    monkeypatch, tmp_path
):
    """MSVC "-nan(ind)" readings give the invalid luminance error (#978).

    Argyll's Windows builds write NaN readings as "-nan(ind)", which the
    CGATS parser used to reject with "Invalid data type for b'XYZ_X'
    (expected float, got bytes)" before the NaN luminance check was reached.
    """
    initcfg()
    lang.init()
    worker = Worker()
    monkeypatch.setattr(worker, "create_tempdir", lambda: str(tmp_path))

    def fake_measure_ti1(ti1_path, *args, **kwargs):
        (tmp_path / "0_16.ti3").write_bytes(
            b"""CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll dispread"
DEVICE_CLASS "DISPLAY"
COLOR_REP "RGB_XYZ"
LUMINANCE_XYZ_CDM2 "-nan(ind) -nan(ind) -nan(ind)"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 100.00 100.00 100.00 -nan(ind) -nan(ind) -nan(ind)
2 0.0000 0.0000 0.0000 -nan(ind) -nan(ind) -nan(ind)
3 6.2500 6.2500 6.2500 -nan(ind) -nan(ind) -nan(ind)
END_DATA
"""
        )
        return True

    monkeypatch.setattr(worker, "measure_ti1", fake_measure_ti1)

    result = worker._detect_video_levels()

    assert isinstance(result, Error)
    assert str(result) == lang.getstr("error.luminance.invalid")


def test_abort_subprocess_confirm_prefers_progress_wnd_confirm(monkeypatch):
    """confirm=True routes through progress_wnd.confirm(), never a wx ConfirmDialog.

    abort_subprocess() used to build a wx ConfirmDialog directly whenever
    confirm=True and progress_wnd was set, which asserts with "No wx.App
    created yet" under the Qt UI (no running wx.App) -- the same hazard
    already fixed for detected_levels_issue_confirm() above. It must prefer a
    callable progress_wnd.confirm() instead, mirroring _prompt_confirm().
    """
    import DisplayCAL.worker as worker_module
    from DisplayCAL import localization as lang

    def _boom(*_args, **_kwargs):
        raise AssertionError("must not construct a wx ConfirmDialog under Qt")

    monkeypatch.setattr(worker_module, "ConfirmDialog", _boom)

    worker = Worker()
    seen = {}

    class FakeProgressWnd:
        def confirm(self, msg, ok, cancel, icon):
            seen["msg"] = msg
            seen["ok"] = ok
            seen["cancel"] = cancel
            seen["icon"] = icon
            return False

    worker.progress_wnd = FakeProgressWnd()

    worker.abort_subprocess(confirm=True)

    assert seen  # confirm() was actually called, not the wx dialog
    assert seen["msg"] == lang.getstr("dialog.confirm_cancel")
    # Declining leaves the abort request cleared rather than proceeding.
    assert worker.abort_requested is False


def test_abort_subprocess_confirm_true_proceeds_past_guard(monkeypatch):
    """Confirming via progress_wnd.confirm() proceeds to the actual abort."""
    import DisplayCAL.worker as worker_module

    started = []

    def _fake_thread(*args, **kwargs):
        started.append((args, kwargs))
        return MagicMock()

    monkeypatch.setattr(worker_module.threading, "Thread", _fake_thread)
    monkeypatch.setattr(worker_module.wx, "GetApp", lambda: None)

    worker = Worker()
    worker.use_patterngenerator = False
    worker.use_madnet_tpg = False
    worker.progress_wnd = type(
        "FakeProgressWnd", (), {"confirm": lambda self, *a, **k: True}
    )()

    worker.abort_subprocess(confirm=True)

    assert worker.subprocess_abort is True
    # The Qt-safe (no wx.App) termination path actually ran.
    assert started


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Worker.authenticate() returns None on Windows without touching "
    "Sudo at all (sudo/password-prompt auth is POSIX-only).",
)
def test_worker_authenticate_threads_password_prompt(monkeypatch):
    """Worker.authenticate() passes Worker.password_prompt to Sudo.authenticate()."""
    import wx

    # authenticate() unconditionally constructs a BetterWindowDisabler(),
    # which calls wx.GetTopLevelWindows(); under GTK/Linux with no wx.App
    # running this crashes the process natively (no Python traceback), not
    # just a normal assertion, taking the whole pytest-xdist worker down.
    _ = wx.GetApp() or wx.App()
    worker = Worker()
    prompt_seam = object()
    worker.password_prompt = prompt_seam
    seen = {}

    def fake_sudo_authenticate(self, args, title, parent=None, prompt=None):
        seen["prompt"] = prompt
        return "allowed", "s3cr3t"

    monkeypatch.setattr(Sudo, "authenticate", fake_sudo_authenticate)

    result = worker.authenticate(sys.executable, "Title")

    assert seen["prompt"] is prompt_seam
    assert result is True
    assert worker.pwd == "s3cr3t"


def test_update_profile_1(random_icc_profile):
    """Testing Worker.update_profile() method."""
    from DisplayCAL import worker

    worker.dbus_session = None
    worker.dbus_system = None
    initcfg()
    worker = Worker()

    icc_profile, icc_profile_path = random_icc_profile
    with check_call_str(
        "DisplayCAL.worker.Worker.get_display_edid", DisplayData.DISPLAY_DATA_2
    ):
        worker.update_profile(icc_profile_path, tags=True)


def test_update_profile_custom_mmod_tag_sets_device_header(random_icc_profile):
    """Worker.update_profile() copies a preserved mmod tag to the header.

    "Create profile from measurement data" with a profile source preserves its
    mmod tag. Indexing the tag's 2-byte manufacturer/model values gave ints and
    crashed with "can't concat int to bytes" (issue 972).
    """
    from DisplayCAL import worker

    worker.dbus_session = None
    worker.dbus_system = None
    initcfg()

    icc_profile, icc_profile_path = random_icc_profile
    # Laid out like Worker.update_profile(tags=True) writes it from an EDID
    # with manufacturer bytes 0x10 0xAC and product code bytes 0xD0 0xA0
    mmod = ICCProfileTag(
        b"mmod" + b"\0" * 6 + b"\x10\xac" + b"\0" * 2 + b"\xa0\xd0" + b"\0" * 24,
        "mmod",
    )
    icc_profile.tags.mmod = mmod
    icc_profile.write(icc_profile_path)
    source = ICCProfile(icc_profile_path)
    assert isinstance(source.tags.mmod, MakeAndModelType)

    result = Worker().update_profile(
        ICCProfile(icc_profile_path), tags={"mmod": source.tags.mmod}
    )

    assert result is True
    updated = ICCProfile(icc_profile_path)
    assert updated.device["manufacturer"] == b"\0\0\xac\x10"
    assert updated.device["model"] == b"\0\0\xa0\xd0"


def test_exec_cmd_1():
    """Test worker.exec_cmd() function for issue #73"""
    # Command line:
    cmd = "/home/eoyilmaz/.local/bin/Argyll_V2.3.0/bin/colprof"
    args = [
        "-v",
        "-qh",
        "-ax",
        "-bn",
        "-C",
        b"No copyright. Created with DisplayCAL 3.8.9.3 and Argyll CMS 2.3.0",
        "-A",
        "Dell, Inc.",
        "-D",
        "UP2516D_#1_2022-04-01_00-26_2.2_F-S_XYZLUT+MTX",
        "/tmp/DisplayCAL-i91d9z8_/UP2516D_#1_2022-04-01_00-26_2.2_F-S_XYZLUT+MTX",
    ]
    cwd = "/tmp/DisplayCAL-i91d9z8_"
    worker = Worker()
    worker.exec_cmd(cmd=cmd, args=args)


def test_is_allowed_1():
    """Test Sudo.is_allowed() function for issue #76"""
    sudo = Sudo()
    result = sudo.is_allowed()
    assert result != ""


class _FakeSudoProcess:
    """Stand-in for a ``wexpect.spawn`` handle, driven by a scripted sequence.

    Each ``.expect()`` call consumes the next ``(after, before, exitstatus,
    alive)`` tuple, mirroring how ``Sudo.authenticate``/``_expect_timeout``
    read ``.after``/``.before``/``.exitstatus``/``.isalive()`` after a real
    ``wexpect`` expect call.
    """

    def __init__(self, script):
        self._script = list(script)
        self.after = None
        self.before = b""
        self.exitstatus = None
        self._alive = True
        self.sent = []

    def expect(self, patterns, timeout=None):  # noqa: ARG002
        self.after, self.before, self.exitstatus, self._alive = self._script.pop(0)
        return 0

    def isalive(self):
        return self._alive

    def send(self, data):
        self.sent.append(data)

    def sendcontrol(self, char):  # noqa: ARG002
        pass

    def terminate(self, force=False):  # noqa: ARG002
        return True


def test_sudo_authenticate_uses_prompt_seam(monkeypatch):
    """Sudo.authenticate() calls a given prompt callable instead of the wx dialog."""
    from DisplayCAL import wexpect
    from DisplayCAL import worker as worker_module

    sudo = Sudo()
    sudo.sudo = "/usr/bin/sudo"
    monkeypatch.setattr(Sudo, "kill", lambda self: None)
    monkeypatch.setattr(Sudo, "is_allowed", lambda self, args=None, pwd="": "allowed")

    fake_process = _FakeSudoProcess(
        [
            ("Password:", b"", None, True),
            (wexpect.EOF, b"", 0, False),
        ]
    )
    monkeypatch.setattr(
        worker_module.wexpect, "spawn", lambda *args, **kwargs: fake_process
    )

    prompts = []

    def fake_prompt(msg):
        prompts.append(msg)
        return "hunter2"

    result, pwd = sudo.authenticate(["true"], "Title", prompt=fake_prompt)

    assert result == "allowed"
    assert pwd == "hunter2"
    assert len(prompts) == 1
    assert fake_process.sent == ["hunter2" + os.linesep]


def test_sudo_authenticate_prompt_cancel_returns_false(monkeypatch):
    """Cancelling the prompt (returning None) aborts authentication."""
    from DisplayCAL import worker as worker_module

    sudo = Sudo()
    sudo.sudo = "/usr/bin/sudo"
    monkeypatch.setattr(Sudo, "kill", lambda self: None)
    monkeypatch.setattr(Sudo, "_terminate", lambda self: None)

    fake_process = _FakeSudoProcess([("Password:", b"", None, True)])
    monkeypatch.setattr(
        worker_module.wexpect, "spawn", lambda *args, **kwargs: fake_process
    )

    result, pwd = sudo.authenticate(["true"], "Title", prompt=lambda msg: None)

    assert result is False
    assert pwd == ""
    assert fake_process.sent == []


def test_sudo_authenticate_prompt_retries_on_rejected_password(monkeypatch):
    """A rejected password re-prompts with the sudo error prepended."""
    from DisplayCAL import wexpect
    from DisplayCAL import worker as worker_module

    sudo = Sudo()
    sudo.sudo = "/usr/bin/sudo"
    monkeypatch.setattr(Sudo, "kill", lambda self: None)
    monkeypatch.setattr(Sudo, "is_allowed", lambda self, args=None, pwd="": "allowed")

    fake_process = _FakeSudoProcess(
        [
            ("Password:", b"", None, True),
            ("Password:", b"Sorry, try again.", None, True),
            (wexpect.EOF, b"", 0, False),
        ]
    )
    monkeypatch.setattr(
        worker_module.wexpect, "spawn", lambda *args, **kwargs: fake_process
    )

    prompts = []

    def fake_prompt(msg):
        prompts.append(msg)
        return "wrong" if len(prompts) == 1 else "right"

    result, pwd = sudo.authenticate(["true"], "Title", prompt=fake_prompt)

    assert result == "allowed"
    assert pwd == "right"
    assert len(prompts) == 2
    assert "Sorry, try again." in prompts[1]


def test_ti3_lookup_to_ti1_1(data_files, setup_argyll):
    """Test Worker.ti3_lookup_to_ti1() function for #129"""
    ti3_path = data_files["0_16_from_issue_129.ti3"].absolute()
    profile_path = data_files[
        "UP2516D #1 2022-03-23 16-06 D6500 2.2 F-S XYZLUT+MTX.icc"
    ].absolute()

    ti3_cgat = CGATS(ti3_path)
    icc_profile = ICCProfile(profile_path)
    config.initcfg()
    worker = Worker()
    ti1, ti3v = worker.ti3_lookup_to_ti1(ti3_cgat, icc_profile)
    assert isinstance(ti1, CGATS)
    assert isinstance(ti3v, CGATS)
    assert ti1 == {
        0: {
            "COLOR_REP": b"RGB",
            "DATA": {
                0: {
                    "RGB_B": 99.9959,
                    "RGB_G": 100.0,
                    "RGB_R": 97.1526,
                    "SAMPLE_ID": 1,
                    "XYZ_X": 95.0104,
                    "XYZ_Y": 100.0,
                    "XYZ_Z": 92.7202,
                },
                1: {
                    "RGB_B": 9.1428,
                    "RGB_G": 5.8338,
                    "RGB_R": 5.842,
                    "SAMPLE_ID": 2,
                    "XYZ_X": 0.277593,
                    "XYZ_Y": 0.255279,
                    "XYZ_Z": 0.423145,
                },
                2: {
                    "RGB_B": 11.6181,
                    "RGB_G": 9.1081,
                    "RGB_R": 8.0801,
                    "SAMPLE_ID": 3,
                    "XYZ_X": 0.51238,
                    "XYZ_Y": 0.536117,
                    "XYZ_Z": 0.705578,
                },
            },
            "DATA_FORMAT": {
                0: b"SAMPLE_ID",
                1: b"RGB_R",
                2: b"RGB_G",
                3: b"RGB_B",
                4: b"XYZ_X",
                5: b"XYZ_Y",
                6: b"XYZ_Z",
            },
            "DESCRIPTOR": b"Argyll Calibration Target chart information 1",
            "KEYWORDS": {0: b"COLOR_REP"},
            "NUMBER_OF_FIELDS": None,
            "NUMBER_OF_SETS": None,
        }
    }

    assert ti3v == {
        "COLOR_REP": b"RGB_XYZ",
        "CREATED": b"Sun Jun  5 13:08:54 2022",
        "DATA": {
            0: {
                "RGB_B": 99.9959,
                "RGB_G": 100.0,
                "RGB_R": 97.1526,
                "SAMPLE_ID": 1,
                "XYZ_X": 95.0104,
                "XYZ_Y": 100.0,
                "XYZ_Z": 92.7202,
            },
            1: {
                "RGB_B": 9.1428,
                "RGB_G": 5.8338,
                "RGB_R": 5.842,
                "SAMPLE_ID": 2,
                "XYZ_X": 0.277593,
                "XYZ_Y": 0.255279,
                "XYZ_Z": 0.423145,
            },
            2: {
                "RGB_B": 11.6181,
                "RGB_G": 9.1081,
                "RGB_R": 8.0801,
                "SAMPLE_ID": 3,
                "XYZ_X": 0.51238,
                "XYZ_Y": 0.536117,
                "XYZ_Z": 0.705578,
            },
        },
        "DATA_FORMAT": {
            0: b"SAMPLE_ID",
            1: b"RGB_R",
            2: b"RGB_G",
            3: b"RGB_B",
            4: b"XYZ_X",
            5: b"XYZ_Y",
            6: b"XYZ_Z",
        },
        "DESCRIPTOR": b"Argyll Calibration Target chart information 3",
        "DEVICE_CLASS": b"DISPLAY",
        "DISPLAY_TYPE_BASE_ID": 1,
        "DISPLAY_TYPE_REFRESH": b"NO",
        "INSTRUMENT_TYPE_SPECTRAL": b"NO",
        "LUMINANCE_XYZ_CDM2": b"42.204124 44.420532 41.186805",
        "NORMALIZED_TO_Y_100": b"YES",
        "NUMBER_OF_FIELDS": None,
        "NUMBER_OF_SETS": None,
        "ORIGINATOR": b"Argyll dispread",
        "TARGET_INSTRUMENT": b"Datacolor Spyder3",
        "VIDEO_LUT_CALIBRATION_POSSIBLE": b"YES",
    }


def test_add_keywords_to_cgats(data_files) -> None:
    """Test if keywords are added to cgats by add_keywords_to_cgats."""
    path = data_files["0_16.ti3"].absolute()
    cgats = CGATS(cgats=path)
    assert "keyword" not in cgats[0]
    options = {"keyword": "Value"}
    alternated_cgats = add_keywords_to_cgats(cgats, options)
    assert "keyword" in alternated_cgats[0]


def test_check_create_dir() -> None:
    """Test function 'check_create_dir'."""
    assert check_create_dir("test_dir") == True


@pytest.mark.parametrize("file", (True, False))
def test_check_cal_isfile(data_files, file: bool) -> None:
    """Test 'check_cal_isfile'."""
    path = data_files["Monitor.cal"].absolute() if file else "no_file"
    assert check_cal_isfile(path) == True if file else "error.calibration.file_missing"


@pytest.mark.parametrize("file", (True, False))
def test_check_profile_isfile(data_files, file: bool) -> None:
    """Test 'check_profile_isfile'."""
    path = data_files["Monitor.cal"].absolute() if file else "no_file"
    assert check_profile_isfile(path) == True if file else "error.profile.file_missing"


# todo: test is working locally but not on CI
@pytest.mark.skip(
    reason="First execution of test fails on remote CI server. "
    "All following tests are positive."
)
@pytest.mark.parametrize("silent", (True, False), ids=("silent", "not silent"))
@pytest.mark.parametrize(
    "path,result",
    (
        ("data/cgats0.txt", ("True", "True")),
        ("no_file", ("False", "file.missing")),
        (".", ("False", "file.notfile")),
    ),
)
def test_check_file_isfile(
    data_files, silent: bool, path: str, result: tuple[str, str]
) -> None:
    """Test if file gets detected."""
    assert (
        str(check_file_isfile(path, silent=silent)) == result[0]
        if silent
        else result[1]
    )


@pytest.mark.parametrize(
    "sample,result",
    (
        (
            {
                "SAMPLE_ID": 1,
                "RGB_R": 50,
                "RGB_G": 50,
                "RGB_B": 50,
                "XYZ_X": 0.5,
                "XYZ_Y": 0.5,
                "XYZ_Z": 0.5,
            },
            True,
        ),
        (
            {
                "SAMPLE_ID": 2,
                "RGB_R": 6,
                "RGB_G": 6,
                "RGB_B": 6,
                "XYZ_X": 0.5,
                "XYZ_Y": 0.5,
                "XYZ_Z": 0.5,
            },
            False,
        ),
    ),
)
def test_check_ti3_criteria1(sample: dict[str:float], result: bool) -> None:
    """Test for ti3 criteria1 check."""
    black = (0, 0, 0)
    white = (110, 110, 110)
    criteria = check_ti3_criteria1(
        (sample["RGB_R"], sample["RGB_G"], sample["RGB_B"]),
        (sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"]),
        black,
        white,
        print_debuginfo=True,
    )
    assert criteria[3] == result


def test_prepare_colprof_for_271(monkeypatch, data_path):
    """Bug report 271."""
    assert isinstance(data_path, pathlib.Path)

    def patched_getcfg(key):
        """Patched getcfg()"""
        cfg = {
            "argyll.version": "2.3.1",
            "profile.name.expanded": "test_profile",
            "profile.quality": "m",
            "profile.type": "l",
            "gamap_saturation": False,
            "gamap_perceptual": False,
            "profile.quality.b2a": "h",
            "profile.b2a.hires": True,
            "copyright": "",
            "extra_args.colprof": "",
            "profile.black_point_compensation": False,
            "profile.black_point_correction": False,
            "profile.b2a.hires.size": 17,
            "profile.b2a.hires.smooth": True,
            "measure.override_min_display_update_delay_ms": False,
            "measure.override_display_settle_time_mult": False,
            "patterngenerator.ffp_insertion": False,
            "testchart.patch_sequence": "",
            "3dlut.create": False,
        }
        return cfg[key]

    monkeypatch.setattr("DisplayCAL.worker.getcfg", patched_getcfg)

    def patched_os_path_exists(filepath):
        return True

    monkeypatch.setattr("DisplayCAL.worker.os.path.exists", patched_os_path_exists)

    def patched_os_path_isfile(filepath):
        return True

    monkeypatch.setattr("DisplayCAL.worker.os.path.isfile", patched_os_path_isfile)

    worker = Worker()
    in_out_file = pathlib.Path(worker.setup_inout("test_profile")).with_suffix(".ti3")

    # copy the test file to the target path
    test_file_path = data_path / "sample" / "issue271" / "test_profile.ti3"
    os.makedirs(in_out_file.parent, exist_ok=True)
    shutil.copy(test_file_path, in_out_file)

    # This should not raise the:
    # TypeError: startswith first arg must be bytes or a tuple of bytes, not str
    worker.prepare_colprof()


def test_prepare_dispcal_1(monkeypatch: pytest.MonkeyPatch):
    """Worker.prepare_dispcal() return value should be quoted properly."""
    # prepare_dispcal() builds its arg list from many getcfg() calls, which
    # only fall back to config.DEFAULTS for options that were never set.
    # Other tests (in this module and others) call setcfg()/writecfg() and
    # leave options set for the rest of the pytest-xdist worker process;
    # initcfg() alone does not clear them, it only merges whatever is on
    # disk into the same in-memory CFG. Under xdist, which tests ran earlier
    # on this worker is nondeterministic, so leftover options made the
    # hardcoded expected_result below flaky (e.g. a stray
    # "calibration.black_point_correction.auto" left truthy silently drops
    # the "-k0.0" arg, shifting every index after it).
    #
    # Snapshot and clear every option currently set in config.CFG's
    # "Default" section (the config module monkeypatches
    # configparser.DEFAULTSECT to "Default", so that's the real section
    # setcfg()/getcfg() read and write) so this test starts from a
    # guaranteed config.DEFAULTS state, then restore the snapshot afterwards
    # so we don't clobber session-scoped state other tests depend on (e.g.
    # the setup_argyll fixture's "argyll.dir"/"argyll.version").
    original_cfg = dict(config.CFG["Default"])
    for name in list(config.CFG["Default"]):
        setcfg(name, None)
    # The -P scale is converted to Argyll units where there is an X screen to
    # ask; not relevant for this test, keep the pass-through behavior
    monkeypatch.setattr(
        "DisplayCAL.worker.get_argyll_measureframe_dimensions", lambda dims: dims
    )
    try:
        worker = Worker()
        return_val = worker.prepare_dispcal()
        expected_result = [
            "-v2",
            "-d0",
            "-c1",
            return_val[1][3],  # '-yl',
            return_val[1][4],  # '-P0.5,0.5,1.0',
            "-ql",
            return_val[1][6],  # '-t',
            "-g2.2",
            "-f1.0",
            return_val[1][9],  # '-k0.0',
            "/var/folders/8l/xy1__ym94nn35x86xyg56xq80000gn/T/DisplayCAL-2fdjtyql/",
        ]
        assert return_val[0] == get_argyll_util("dispcal")
        assert isinstance(return_val[1], list)
        assert return_val[1][:-1] == expected_result[:-1]  # don't check the final part
        assert tempfile.gettempdir() in return_val[1][-1]  # in a temp path
    finally:
        for name in list(config.CFG["Default"]):
            setcfg(name, None)
        for name, value in original_cfg.items():
            setcfg(name, value)


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Not working properly on GitHub.",
)
def test_get_argyll_version_string_returns_a_proper_value():
    """get_argyll_version_string() returns a proper value."""
    import wx

    config.initcfg()
    app = wx.GetApp() or wx.App()

    assert get_argyll_version_string(name="ccxxmake", silent=False) != "0.0.0"


def test_get_argyll_latest_version_returns_str():
    """get_argyll_latest_version() returns a str."""
    result = get_argyll_latest_version()
    assert isinstance(result, str)


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Test is randomly failing on CI machines.",
)
def test_get_argyll_latest_version_returns_latest_argyll_cms_version():
    """get_argyll_latest_version() returns the latest argyll cms version."""
    result = get_argyll_latest_version()
    assert result == "3.5.0"


def test_get_argyll_latest_version_returns_the_default_version_if_no_internet_connect(
    monkeypatch,
):
    """get_argyll_latest_version() returns the default argyll cms version if no internet connection."""

    def patched_urlopen(*args, **kwargs):
        raise URLError(
            "<urlopen error [Errno 8] nodename nor servname provided, or not known>"
        )

    monkeypatch.setattr("DisplayCAL.argyll.urllib.request.urlopen", patched_urlopen)
    monkeypatch.setattr("DisplayCAL.argyll.time.sleep", lambda _: None)
    get_argyll_latest_version.cache_clear()
    result = get_argyll_latest_version()
    assert result == config.DEFAULTS.get("argyll.version")


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true" and sys.platform == "linux",
    reason="Not working properly on GitHub on Linux machines.",
)
def test_get_technology_strings_returns_dict(setup_argyll):
    """Test get_technology_strings() returns a dict."""
    worker = Worker()
    result = worker.get_technology_strings()
    assert isinstance(result, dict)


def test_get_technology_strings_without_argyll_returns_from_argyll_17():
    """Test get_technology_strings() returns a dictionary from argyll 1.7."""
    get_argyll_latest_version.cache_clear()
    worker = Worker()
    worker.argyll_version = [0, 0, 0]

    result = worker.get_technology_strings()
    assert result == {
        "c": "CRT",
        "m": "Plasma",
        "l": "LCD",
        "1": "LCD CCFL",
        "2": "LCD CCFL IPS",
        "3": "LCD CCFL VPA",
        "4": "LCD CCFL TFT",
        "L": "LCD CCFL Wide Gamut",
        "5": "LCD CCFL Wide Gamut IPS",
        "6": "LCD CCFL Wide Gamut VPA",
        "7": "LCD CCFL Wide Gamut TFT",
        "e": "LCD White LED",
        "8": "LCD White LED IPS",
        "9": "LCD White LED VPA",
        "d": "LCD White LED TFT",
        "b": "LCD RGB LED",
        "f": "LCD RGB LED IPS",
        "g": "LCD RGB LED VPA",
        "i": "LCD RGB LED TFT",
        "h": "LCD RG Phosphor",
        "j": "LCD RG Phosphor IPS",
        "k": "LCD RG Phosphor VPA",
        "n": "LCD RG Phosphor TFT",
        "o": "LED OLED",
        "a": "LED AMOLED",
        "p": "DLP Projector",
        "q": "DLP Projector RGB Filter Wheel",
        "r": "DPL Projector RGBW Filter Wheel",
        "s": "DLP Projector RGBCMY Filter Wheel",
        "u": "Unknown",
    }


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true" and sys.platform in ("linux", "win32"),
    reason="Not working properly on GitHub on Linux and Windows machines: the "
    "real (unmocked) get_argyll_version_string() subprocess call doesn't "
    "reliably report a version on hosted CI runners, same underlying issue as "
    "test_get_argyll_version_string_returns_a_proper_value's unconditional skip.",
)
def test_get_technology_strings_with_argyll_returns_expected_data(setup_argyll):
    """Test get_technology_strings() returns a dict with correct data."""
    get_argyll_latest_version.cache_clear()
    worker = Worker()
    assert worker.argyll_version != [0, 0, 0]
    result = worker.get_technology_strings()
    expected = {
        "c": "CRT",
        "m": "Plasma",
        "l": "LCD",
        "1": "LCD CCFL",
        "2": "LCD CCFL IPS",
        "3": "LCD CCFL PVA",
        "4": "LCD CCFL TFT",
        "L": "LCD CCFL Wide Gamut",
        "5": "LCD CCFL Wide Gamut IPS",
        "6": "LCD CCFL Wide Gamut PVA",
        "7": "LCD CCFL Wide Gamut TFT",
        "e": "LCD White LED",
        "8": "LCD White LED IPS",
        "9": "LCD White LED PVA",
        "d": "LCD White LED TFT",
        "b": "LCD RGB LED",
        "f": "LCD RGB LED IPS",
        "g": "LCD RGB LED PVA",
        "j": "LCD RGB LED TFT",
        "h": "LCD RG Phosphor",
        "k": "LCD RG Phosphor IPS",
        "n": "LCD RG Phosphor PVA",
        "q": "LCD RG Phosphor TFT",
        "r": "LCD PFS Phosphor",
        "s": "LCD PFS Phosphor IPS",
        "t": "LCD PFS Phosphor PVA",
        "v": "LCD PFS Phosphor TFT",
        "i": "LCD GB-R Phosphor",
        "x": "LCD GB-R Phosphor IPS",
        "y": "LCD GB-R Phosphor PVA",
        "z": "LCD GB-R Phosphor TFT",
        "o": "LED OLED",
        "a": "LED AMOLED",
        "w": "LED WOLED",
        "p": "DLP Projector",
        "A": "DLP Projector RGB Filter Wheel",
        "B": "DLP Projector RGBW Filter Wheel",
        "C": "DLP Projector RGBCMY Filter Wheel",
        "u": "Unknown",
    }
    assert result == expected


def test_get_technology_strings_parses_ccxxmake_output(monkeypatch):
    """Technology parser should extract -t entries from ccxxmake output."""
    worker = Worker()
    worker.argyll_version = [3, 5, 0]

    def patched_exec_cmd(*args, **kwargs):
        worker.output = [
            "-t c CRT",
            "-t q LCD PFS Phosphor TFT",
            "-t o LED OLED",
            "-Y ignored option section",
        ]
        return True

    monkeypatch.setattr(worker, "exec_cmd", patched_exec_cmd)
    result = worker.get_technology_strings()
    assert result == {
        "c": "CRT",
        "q": "LCD PFS Phosphor TFT",
        "o": "LED OLED",
    }


def _build_matrix_from_primaries(RGB_XYZ, remaining, white_scale=1.0):
    """Build a from-chromaticities matrix profile like ``_create_simple_matrix_profile``.

    ``white_scale`` lets the test simulate an inconsistency between the matrix
    white and the gray-ramp white, which is what makes the shaper curve endpoint
    drop below 1.0 (see issue #710).
    """
    from DisplayCAL import colormath

    XYZbp = RGB_XYZ[(0, 0, 0)]
    XYZwp = RGB_XYZ[(100, 100, 100)]
    xy = []
    for R, G, B in [(100, 0, 0), (0, 100, 0), (0, 0, 100), (100, 100, 100)]:
        src = RGB_XYZ if R == G == B else remaining
        X, Y, Z = src[(R, G, B)]
        if XYZbp != (0, 0, 0):
            X, Y, Z = colormath.blend_blackpoint(X, Y, Z, XYZbp, (0, 0, 0), XYZwp)
        xy.append(colormath.XYZ2xyY(*(v / 100 for v in (X, Y, Z)))[:2])
    profile = ICCProfile.from_chromaticities(
        xy[0][0],
        xy[0][1],
        xy[1][0],
        xy[1][1],
        xy[2][0],
        xy[2][1],
        xy[3][0],
        xy[3][1],
        2.2,
        "t",
        "c",
        None,
        None,
        cat="Bradford",
    )
    if white_scale != 1.0:
        # Make the matrix map device (1, 1, 1) to a brighter-than-media white,
        # mimicking a matrix/gray-ramp white inconsistency.
        for channel in "rgb":
            tag = profile.tags[channel + "XYZ"]
            tag.X /= white_scale
            tag.Y /= white_scale
            tag.Z /= white_scale
    return profile


@pytest.mark.parametrize("white_scale", [1.0, 0.9757])
def test_create_shaper_curves_trc_endpoint_reaches_one(data_files, white_scale):
    """Matrix display shaper curves must reach 1.0 at device max (issue #710).

    A TRC endpoint below 1.0 makes device white map to a fraction of media
    white, which causes a CMM to clip near-white source values to device white
    when inverting the profile at limited precision.
    """
    from DisplayCAL import colormath

    ti3 = CGATS(
        str(data_files["UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.ti3"])
    )[0]
    _, RGB_XYZ, remaining = extract_device_gray_primaries(ti3, True, lambda *a: None)
    profile = _build_matrix_from_primaries(RGB_XYZ, remaining, white_scale)
    bwd_mtx = colormath.get_rgb_space(profile.get_rgb_space("pcs", 1))[-1].inverted()

    curves = create_shaper_curves(
        RGB_XYZ,
        bwd_mtx,
        single_curve=True,
        bpc=False,
        profile=profile,
        options_dispcal=[],
        optimize=True,
        cat="Bradford",
    )

    for curve in curves:
        # Endpoint reaches device max ...
        assert curve[-1] == pytest.approx(1.0, abs=1e-9)
        # ... and the curve is still monotonically increasing.
        assert all(curve[i] <= curve[i + 1] + 1e-9 for i in range(len(curve) - 1))


def test_create_shaper_curves_device_max_maps_to_white_point(data_files, monkeypatch):
    """Device max must be interpolated to the white point XYZ (issue #985).

    The per channel values are normalized to reach 1.0 for the gamma based
    interpolation and must be mapped back to the white point afterwards,
    including the last entry. Otherwise device max maps to (1, 1, 1) instead of
    the white point whenever its normalized Y lands just below 1.0, which skews
    the curves and gets amplified by the endpoint normalization of issue #710.
    """
    from DisplayCAL import colormath

    interp_values = []

    class SpyInterp(colormath.Interp):
        def __init__(self, xp, fp, *args, **kwargs):
            interp_values.append(list(fp))
            super().__init__(xp, fp, *args, **kwargs)

    ti3 = CGATS(
        str(data_files["UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.ti3"])
    )[0]
    _, RGB_XYZ, remaining = extract_device_gray_primaries(ti3, True, lambda *a: None)
    profile = _build_matrix_from_primaries(RGB_XYZ, remaining, 1.0)
    bwd_mtx = colormath.get_rgb_space(profile.get_rgb_space("pcs", 1))[-1].inverted()

    monkeypatch.setattr(colormath, "Interp", SpyInterp)
    create_shaper_curves(
        RGB_XYZ,
        bwd_mtx,
        single_curve=False,
        bpc=False,
        profile=profile,
        options_dispcal=[],
        cat="Bradford",
    )

    # The R->X, G->Y and B->Z interpolators are created first
    endpoint = [values[-1] for values in interp_values[:3]]
    assert endpoint == pytest.approx(colormath.get_whitepoint("D50"), abs=1e-9)


@pytest.mark.parametrize(
    "viewgam_output,expected_coverage",
    [
        # Unix-style paths (forward slash)
        (
            [
                "Intersecting volume = 1198577.5 cubic units",
                "'/usr/share/DisplayCAL/ref/ClayRGB1998.gam' volume = 1209985.9 cubic units, intersect = 99.06%",
                "'/home/user/profile.gam' volume = 1411797.2 cubic units, intersect = 84.90%",
            ],
            0.9906,
        ),
        # Windows-style paths (backslash) -- issue #693
        (
            [
                "Intersecting volume = 1198577.5 cubic units",
                r"'C:\Program Files\DisplayCAL\ref\ClayRGB1998.gam' volume = 1209985.9 cubic units, intersect = 99.06%",
                r"'C:\Users\user\profile.gam' volume = 1411797.2 cubic units, intersect = 84.90%",
            ],
            0.9906,
        ),
    ],
)
def test_create_gamut_view_worker_parses_coverage(viewgam_output, expected_coverage):
    """Coverage percentage is parsed from both Unix and Windows viewgam output paths.

    Regression test for issue #693: on Windows, viewgam outputs backslash paths
    which the old regex only matched forward slashes and missed Windows paths.
    """
    mock_worker = MagicMock()
    mock_worker.exec_cmd.return_value = True
    mock_worker.output = viewgam_output

    gamut_coverage = {}
    Worker.create_gamut_view_worker(
        mock_worker,
        viewgam="viewgam",
        args=[],
        key="adobe-rgb",
        src="ClayRGB1998",
        gamut_coverage=gamut_coverage,
    )

    assert "adobe-rgb" in gamut_coverage
    assert gamut_coverage["adobe-rgb"] == pytest.approx(expected_coverage, rel=1e-4)


@pytest.mark.parametrize(
    "old_value, expected",
    [
        ("2012_2", "2015_2"),
        ("2012_10", "2015_10"),
    ],
    ids=["2012_2->2015_2", "2012_10->2015_10"],
)
def test_enumerate_displays_migrates_cie2012_observer_names_for_argyll_34(
    monkeypatch, request, old_value, expected
):
    """ArgyllCMS 3.4.0 renamed the "2012_*" observers to "2015_*".

    Stored config values must be migrated automatically on first run with the new
    ArgyllCMS so they don't silently revert to the default "1931_2" observer.
    Without migration, getcfg("observer") sees "2012_2" as invalid (not in
    VALID_VALUES) and returns the default "1931_2", which means the -Q flag is never
    passed to dispcal/dispread, producing wrong calibration and measurement results
    (issue #623).
    """
    from DisplayCAL import config as _config

    observer_keys = [
        "observer",
        "colorimeter_correction.observer",
        "colorimeter_correction.observer.reference",
    ]

    # Save existing CFG values so the test doesn't pollute global config state.
    originals = {
        k: _config.CFG.get(configparser.DEFAULTSECT, k, fallback=None)
        for k in observer_keys
    }

    def restore_cfg():
        for key, val in originals.items():
            if val is None:
                _config.CFG.remove_option(configparser.DEFAULTSECT, key)
            else:
                _config.CFG.set(configparser.DEFAULTSECT, key, val)

    request.addfinalizer(restore_cfg)

    # Preserve VALID_VALUES entries so monkeypatch restores them after the test.
    for key in observer_keys:
        monkeypatch.setitem(
            _config.VALID_VALUES, key, list(_config.VALID_VALUES.get(key, []))
        )

    # Write old-style names directly to CFG, bypassing VALID_VALUES validation,
    # to simulate a config saved with ArgyllCMS < 3.4.0.
    for key in observer_keys:
        _config.CFG.set(configparser.DEFAULTSECT, key, old_value)

    worker = Worker()
    monkeypatch.setattr("DisplayCAL.worker.check_argyll_bin", lambda: True)
    monkeypatch.setattr("DisplayCAL.worker.writecfg", lambda *a, **kw: None)

    def fake_exec_cmd(*args, **kwargs):
        worker.output = ["dispcal  - Display calibration  Version 3.4.0"]
        return True

    monkeypatch.setattr(worker, "exec_cmd", fake_exec_cmd)

    worker.enumerate_displays_and_ports(
        silent=True, check_lut_access=False, enumerate_ports=False
    )

    for key in observer_keys:
        result = getcfg(key)
        assert result == expected, (
            f"{key!r} should have been migrated from {old_value!r} "
            f"to {expected!r}, got {result!r}"
        )


# ---------------------------------------------------------------------------
# check_instrument_calibration tests (issue #617 – ColorMunki infinite loop)
# ---------------------------------------------------------------------------

COLORMUNKI_CAL_MSG = "Set instrument sensor to calibration position"


def _make_worker_for_cal_test(monkeypatch):
    """Return a Worker with do_instrument_calibration and safe_send mocked."""
    worker = Worker()
    # These attributes are normally set in the worker-thread setup; init them
    # manually so the calibration method can be called without a running subprocess.
    worker.instrument_calibration_complete = False
    worker._last_calibration_msg = None
    worker.do_instrument_calibration_calls = []
    worker.safe_send_calls = []

    def fake_do_instrument_calibration(failed=False):
        worker.do_instrument_calibration_calls.append(failed)

    def fake_safe_send(data):
        worker.safe_send_calls.append(data)

    monkeypatch.setattr(
        worker, "do_instrument_calibration", fake_do_instrument_calibration
    )
    monkeypatch.setattr(worker, "safe_send", fake_safe_send)
    return worker


def test_check_instrument_calibration_first_prompt_shows_dialog(monkeypatch):
    """First occurrence of a calibration prompt must show the dialog."""
    worker = _make_worker_for_cal_test(monkeypatch)
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    assert len(worker.do_instrument_calibration_calls) == 1
    assert worker.do_instrument_calibration_calls[0] is False
    assert worker.safe_send_calls == []
    assert worker._last_calibration_msg == COLORMUNKI_CAL_MSG


def test_check_instrument_calibration_duplicate_prompt_auto_retries(monkeypatch):
    """Second occurrence of the same prompt must auto-send a space, not show dialog."""
    worker = _make_worker_for_cal_test(monkeypatch)
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    # Dialog shown only once; second call triggers a silent keypress
    assert len(worker.do_instrument_calibration_calls) == 1
    assert worker.safe_send_calls == [" "]


def test_check_instrument_calibration_complete_stops_further_dialogs(monkeypatch):
    """After calibration complete, subsequent prompts must be ignored."""
    worker = _make_worker_for_cal_test(monkeypatch)
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    worker.check_instrument_calibration("Calibration complete")
    assert worker.instrument_calibration_complete is True
    assert worker._last_calibration_msg is None
    # A further prompt arrives – must be silently ignored
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    assert len(worker.do_instrument_calibration_calls) == 1
    assert worker.safe_send_calls == []


def test_check_instrument_calibration_failure_allows_retry_dialog(monkeypatch):
    """After a calibration failure, the next calibration prompt must show a dialog.

    The duplicate-suppression state is reset on failure so the user is not stuck
    in a silent auto-retry loop after a failed calibration attempt.
    """
    worker = _make_worker_for_cal_test(monkeypatch)
    # First prompt: dialog shown, duplicate tracking starts
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    assert len(worker.do_instrument_calibration_calls) == 1
    # Simulate duplicate that would normally be auto-retried silently
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    assert worker.safe_send_calls == [" "]
    # Calibration fails: reset state so the NEXT prompt opens the dialog again
    worker._last_calibration_msg = (
        None  # mirrors what do_instrument_calibration does on cancel
    )
    worker.check_instrument_calibration(COLORMUNKI_CAL_MSG)
    assert len(worker.do_instrument_calibration_calls) == 2
    assert worker.do_instrument_calibration_calls[1] is False
    # No additional silent retries should have been sent
    assert len(worker.safe_send_calls) == 1
