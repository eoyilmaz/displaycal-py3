"""Tests for the toolkit-neutral pre-flight-check helpers.

Covers the pure pieces extracted from ``MainFrame.check_overwrite``,
``check_show_macos_bugs_warning`` and ``current_cal_choice``
(``DisplayCAL/preflight_checks.py``). No display or QApplication is needed.
"""

import os
import shutil

import pytest

from DisplayCAL import preflight_checks as pfc
from DisplayCAL.config import getcfg, setcfg


class FakeWorker:
    """Minimal worker exposing what ``resolve_cal_choice_info`` touches."""

    def __init__(self, argyll_version=None, lut_access=True):
        self.argyll_version = (
            argyll_version if argyll_version is not None else [3, 0, 0]
        )
        self._lut_access = lut_access

    def has_lut_access(self):
        return self._lut_access


class TestResolveOverwritePath:
    def test_default_filename_nests_under_profile_name_dir(self):
        setcfg("profile.save_path", "/save")
        setcfg("profile.name.expanded", "MyProfile")
        expected = os.path.join("/save", "MyProfile", "MyProfile.icc")
        assert pfc.resolve_overwrite_path(".icc") == expected

    def test_explicit_filename_joins_save_path_directly(self):
        setcfg("profile.save_path", "/save")
        assert pfc.resolve_overwrite_path(filename="foo.ti3") == os.path.join(
            "/save", "foo.ti3"
        )


class TestMacosBugsWarningApplicable:
    def test_non_darwin_platform_never_applicable(self, monkeypatch):
        monkeypatch.setattr(pfc.sys, "platform", "linux")
        assert pfc.macos_bugs_warning_applicable() is False

    def test_darwin_below_10_8_not_applicable(self, monkeypatch):
        monkeypatch.setattr(pfc.sys, "platform", "darwin")
        monkeypatch.setattr(pfc.platform, "mac_ver", lambda: ("10.7.5", (), ""))
        assert pfc.macos_bugs_warning_applicable() is False

    def test_darwin_10_8_or_above_applicable(self, monkeypatch):
        monkeypatch.setattr(pfc.sys, "platform", "darwin")
        monkeypatch.setattr(pfc.platform, "mac_ver", lambda: ("10.15.7", (), ""))
        assert pfc.macos_bugs_warning_applicable() is True


class TestShouldWarnCalibrationBugs:
    def test_no_flags_set_no_warning(self):
        setcfg("calibration.black_point_correction.auto", 0)
        setcfg("calibration.black_point_correction", 0)
        setcfg("calibration.black_luminance", None)
        assert pfc.should_warn_calibration_bugs() is False

    @pytest.mark.parametrize(
        "key,value",
        [
            ("calibration.black_point_correction.auto", 1),
            ("calibration.black_point_correction", 1),
            ("calibration.black_luminance", 80.0),
        ],
    )
    def test_any_flag_triggers_warning(self, key, value):
        setcfg("calibration.black_point_correction.auto", 0)
        setcfg("calibration.black_point_correction", 0)
        setcfg("calibration.black_luminance", None)
        setcfg(key, value)
        assert pfc.should_warn_calibration_bugs() is True


class TestShouldWarnProfileBugs:
    """The Apple CMM shows only single curve + matrix with BPC right.

    Any other type is warned about, as DisplayCAL used to (``profile.type
    != "S" or not BPC``). Moved into preflight_checks, it was turned round:
    an XYZ LUT profile was made without a word and turned a MacBook's
    screen washed out and yellow once installed, while the safe choice got
    the warning.
    """

    @pytest.mark.parametrize("profile_type", ["X", "x", "l", "s", "g", "G"])
    def test_any_other_type_warns(self, profile_type):
        setcfg("profile.type", profile_type)
        setcfg("profile.black_point_compensation", 1)
        assert pfc.should_warn_profile_bugs() is True

    def test_s_type_without_bpc_warns(self):
        setcfg("profile.type", "S")
        setcfg("profile.black_point_compensation", 0)
        assert pfc.should_warn_profile_bugs() is True

    def test_s_type_with_bpc_no_warning(self):
        setcfg("profile.type", "S")
        setcfg("profile.black_point_compensation", 1)
        assert pfc.should_warn_profile_bugs() is False


class TestResolveCalChoiceInfo:
    def test_uncalibratable_display_short_circuits(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: True)
        info = pfc.resolve_cal_choice_info(FakeWorker())
        assert info.is_uncalibratable is True
        assert info.can_use_current_cal is False
        assert info.show_reset_checkbox is False

    def test_no_cal_file_with_lut_access_warns_current_cal(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: False)
        setcfg("calibration.file", None)
        info = pfc.resolve_cal_choice_info(FakeWorker(lut_access=True))
        assert info.cal_path is None
        assert info.can_use_current_cal is True
        assert info.msg_key == "dialog.current_cal_warning"
        assert info.show_reset_checkbox is True

    def test_no_lut_access_falls_back_to_linear_info(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: False)
        setcfg("calibration.file", None)
        info = pfc.resolve_cal_choice_info(FakeWorker(lut_access=False))
        assert info.can_use_current_cal is False
        assert info.msg_key == "dialog.linear_cal_info"
        assert info.show_reset_checkbox is False

    def test_old_argyll_version_disables_current_cal(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: False)
        setcfg("calibration.file", None)
        info = pfc.resolve_cal_choice_info(
            FakeWorker(argyll_version=[1, 0, 0], lut_access=True)
        )
        assert info.can_use_current_cal is False

    def test_existing_cal_file_uses_cal_info_message(
        self, monkeypatch, tmp_path, data_path
    ):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: False)
        # "calibration.file" is validated by setcfg to point at a file that
        # exists on disk, so use a real (copied) profile rather than a bare
        # nonexistent path.
        src = data_path / "icc" / "vcgt_cm_test_cyanish_reddish.icc"
        icc_file = tmp_path / "profile.icc"
        shutil.copyfile(src, icc_file)
        cal_file = tmp_path / "profile.cal"
        cal_file.write_text("fake cal")
        setcfg("calibration.file", str(icc_file))
        assert getcfg("calibration.file") == str(icc_file)
        info = pfc.resolve_cal_choice_info(FakeWorker(lut_access=True))
        assert info.cal_path == str(cal_file)
        assert info.msg_key == "dialog.cal_info"
        assert info.show_reset_checkbox is True

    def test_invalid_profile_raises(self, monkeypatch, tmp_path):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: False)
        bogus = tmp_path / "bogus.icc"
        bogus.write_bytes(b"not an icc profile")
        setcfg("calibration.file", str(bogus))
        with pytest.raises(pfc.CalChoiceProfileInvalidError):
            pfc.resolve_cal_choice_info(FakeWorker())

    def test_valid_profile_extracts_dispcal_options(self, monkeypatch, data_path):
        monkeypatch.setattr(pfc.config, "is_uncalibratable_display", lambda: False)
        profile_path = str(data_path / "icc" / "vcgt_cm_test_cyanish_reddish.icc")
        setcfg("calibration.file", profile_path)
        info = pfc.resolve_cal_choice_info(FakeWorker())
        assert info.options_dispcal == []


class TestComputeCalChoiceResult:
    def _info(self, **overrides):
        base = dict(
            is_uncalibratable=False,
            cal_path=None,
            options_dispcal=None,
            can_use_current_cal=True,
            msg_key="dialog.current_cal_warning",
            icon="warning",
            show_reset_checkbox=True,
        )
        base.update(overrides)
        return pfc.CalChoiceInfo(**base)

    def test_embed_unchecked_no_reset_returns_false(self):
        result = pfc.compute_cal_choice_result(
            self._info(), embed_cal=False, reset_cal=False
        )
        assert result.apply_calibration is False
        assert result.reset_video_lut is False

    def test_embed_unchecked_with_reset_resets_video_lut(self):
        result = pfc.compute_cal_choice_result(
            self._info(), embed_cal=False, reset_cal=True
        )
        assert result.apply_calibration is False
        assert result.reset_video_lut is True

    def test_embed_unchecked_reset_ignored_without_current_cal(self):
        info = self._info(can_use_current_cal=False, show_reset_checkbox=False)
        result = pfc.compute_cal_choice_result(info, embed_cal=False, reset_cal=True)
        assert result.reset_video_lut is False

    def test_embed_checked_no_current_cal_or_file_uses_linear(self, monkeypatch):
        monkeypatch.setattr(pfc, "get_data_path", lambda name: f"/data/{name}")
        info = self._info(can_use_current_cal=False, cal_path=None)
        result = pfc.compute_cal_choice_result(info, embed_cal=True, reset_cal=False)
        assert result.apply_calibration == "/data/linear.cal"

    def test_embed_checked_reset_forces_linear_even_with_cal_file(self, monkeypatch):
        monkeypatch.setattr(pfc, "get_data_path", lambda name: f"/data/{name}")
        info = self._info(cal_path="/path/to/file.cal")
        result = pfc.compute_cal_choice_result(info, embed_cal=True, reset_cal=True)
        assert result.apply_calibration == "/data/linear.cal"

    def test_embed_checked_cal_file_returns_path_and_options(self):
        info = self._info(cal_path="/path/to/file.cal", options_dispcal=["-qh"])
        result = pfc.compute_cal_choice_result(info, embed_cal=True, reset_cal=False)
        assert result.apply_calibration == "/path/to/file.cal"
        assert result.options_dispcal == ["-qh"]

    def test_embed_checked_current_cal_returns_none(self):
        info = self._info(cal_path=None, can_use_current_cal=True)
        result = pfc.compute_cal_choice_result(info, embed_cal=True, reset_cal=False)
        assert result.apply_calibration is None
        assert result.reset_video_lut is False


class TestResolveFastMatrixShaperChoiceInfo:
    def _setcfg(self, *, profile_update=0, calibration_update=0, trc=2.2):
        setcfg("profile.update", profile_update)
        setcfg("calibration.update", calibration_update)
        setcfg("trc", trc)

    def test_defaults_show_dialog_with_fast_matrix_shaper_wording(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_profile", lambda: False)
        self._setcfg()
        info = pfc.resolve_fast_matrix_shaper_choice_info()
        assert info.show_dialog is True
        assert info.update_profile is False
        assert info.msg_key == "calibration.create_fast_matrix_shaper_choice"
        assert info.ok_key == "calibration.create_fast_matrix_shaper"

    def test_calibration_update_of_a_profile_shows_update_wording(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_profile", lambda: True)
        self._setcfg(calibration_update=1)
        info = pfc.resolve_fast_matrix_shaper_choice_info()
        assert info.show_dialog is True
        assert info.update_profile is True
        assert info.msg_key == "calibration.update_profile_choice"
        assert info.ok_key == "profile.update"

    def test_calibration_update_of_a_non_profile_hides_dialog(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_profile", lambda: False)
        self._setcfg(calibration_update=1)
        assert pfc.resolve_fast_matrix_shaper_choice_info().show_dialog is False

    def test_profile_update_already_set_hides_dialog(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_profile", lambda: False)
        self._setcfg(profile_update=1)
        assert pfc.resolve_fast_matrix_shaper_choice_info().show_dialog is False

    def test_no_trc_hides_dialog(self, monkeypatch):
        monkeypatch.setattr(pfc.config, "is_profile", lambda: False)
        self._setcfg(trc="")
        assert pfc.resolve_fast_matrix_shaper_choice_info().show_dialog is False


class TestApplyFastMatrixShaperChoice:
    def test_update_profile_and_create_sets_profile_update(self):
        setcfg("profile.update", 0)
        info = pfc.FastMatrixShaperChoiceInfo(
            show_dialog=True,
            update_profile=True,
            msg_key="calibration.update_profile_choice",
            ok_key="profile.update",
        )
        pfc.apply_fast_matrix_shaper_choice(info, create=True)
        assert getcfg("profile.update") == 1

    def test_update_profile_but_declined_leaves_profile_update_unset(self):
        setcfg("profile.update", 0)
        info = pfc.FastMatrixShaperChoiceInfo(
            show_dialog=True,
            update_profile=True,
            msg_key="calibration.update_profile_choice",
            ok_key="profile.update",
        )
        pfc.apply_fast_matrix_shaper_choice(info, create=False)
        assert getcfg("profile.update") == 0

    def test_fast_matrix_shaper_choice_never_sets_profile_update(self):
        setcfg("profile.update", 0)
        info = pfc.FastMatrixShaperChoiceInfo(
            show_dialog=True,
            update_profile=False,
            msg_key="calibration.create_fast_matrix_shaper_choice",
            ok_key="calibration.create_fast_matrix_shaper",
        )
        pfc.apply_fast_matrix_shaper_choice(info, create=True)
        assert getcfg("profile.update") == 0
