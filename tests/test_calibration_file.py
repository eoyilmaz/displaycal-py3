"""Tests for the toolkit-neutral calibration/profile-file header-bar helpers.

Covers the pure pieces of ``MainFrame.load_cal_handler`` extracted into
``DisplayCAL/calibration_file.py``: the EDID/instrument auto-matching, the
ICC-profile-load config defaults, and the session-archive import. No display
or QApplication is needed.
"""

import os
import zipfile
from types import SimpleNamespace

import pytest

from DisplayCAL import calibration_file as cf
from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg


@pytest.fixture(autouse=True)
def _restore_config():
    """Undo the ``setcfg()`` calls these tests make.

    Several tests point ``displays`` at madVR/Resolve/Prisma and flip
    ``3dlut.enable`` / ``measurement_report.use_devlink_profile``. Left in
    place, a later test on the same pytest-xdist worker sees a virtual
    display instead of an ordinary one.
    """
    saved = dict(config.CFG["Default"])
    yield
    config.CFG["Default"] = saved


class FakeProfile:
    """Minimal stand-in for :class:`~DisplayCAL.icc_profile.ICCProfile`."""

    def __init__(self, model_description="", meta=None):
        self._model_description = model_description
        self.tags = {"meta": meta or {}}

    def getDeviceModelDescription(self):  # noqa: N802 (matches ICCProfile's API)
        return self._model_description


class FakeWorker:
    """Minimal worker exposing what ``match_display_and_instrument`` touches."""

    def __init__(self, display_edid=None, display_names=None, instruments=None):
        self.display_edid = display_edid or []
        self.display_names = display_names or []
        self.instruments = instruments or []


class TestMatchDisplayAndInstrument:
    def test_no_metadata_finds_nothing(self):
        setcfg("displays", ["Display 1 @ 0, 0, 1920x1080"])
        setcfg("display.number", 1)
        profile = FakeProfile()
        worker = FakeWorker(
            display_edid=[{}], display_names=["Display 1"], instruments=[]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index is None
        assert match.instrument_index is None

    def test_unique_model_description_match_selects_display(self):
        setcfg(
            "displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"]
        )
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="Display 2")
        worker = FakeWorker(
            display_edid=[{}, {}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 1
        assert match.display_changed is True

    def test_currently_selected_display_is_not_flagged_changed(self):
        setcfg(
            "displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"]
        )
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="Display 1")
        worker = FakeWorker(
            display_edid=[{}, {}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 0
        assert match.display_changed is False

    def test_ambiguous_model_description_match_is_not_applied(self):
        setcfg(
            "displays", ["Display 1 @ 0, 0, 1920x1080", "Display 1 @ 0, 0, 1024x768"]
        )
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="Display 1")
        worker = FakeWorker(
            display_edid=[{}, {}],
            display_names=["Display 1", "Display 1"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index is None

    def test_edid_md5_match_used_when_no_model_description(self):
        setcfg(
            "displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"]
        )
        setcfg("display.number", 1)
        profile = FakeProfile(meta={"EDID_md5": {"value": "abc123"}})
        worker = FakeWorker(
            display_edid=[{}, {"hash": "abc123"}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 1

    def test_edid_monitor_name_match(self):
        setcfg(
            "displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"]
        )
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="DELL U2410")
        worker = FakeWorker(
            display_edid=[{}, {"monitor_name": "DELL U2410"}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 1

    def test_virtual_display_match_reenables_3dlut_tab(self):
        setcfg("displays", ["madVR"])
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="madVR")
        worker = FakeWorker(display_edid=[{}], display_names=["madVR"], instruments=[])

        match = cf.match_display_and_instrument(profile, worker)

        assert match.reenable_3dlut_tab is True

    def test_instrument_match_by_measurement_device(self):
        profile = FakeProfile(
            meta={"MEASUREMENT_device": {"value": "colormunki display"}}
        )
        worker = FakeWorker(
            display_edid=[], display_names=[], instruments=["ColorMunki Display"]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.instrument_index == 0
        assert match.instrument_match is True

    def test_no_instrument_match_leaves_index_none(self):
        profile = FakeProfile(
            meta={"MEASUREMENT_device": {"value": "some other device"}}
        )
        worker = FakeWorker(
            display_edid=[], display_names=[], instruments=["ColorMunki Display"]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.instrument_index is None
        assert match.instrument_match is False


class TestApplyIccProfileLoadDefaults:
    def test_non_preset_updates_3dlut_source_profiles(self):
        setcfg("3dlut.tab.enable", 1)
        setcfg("3dlut.tab.enable.backup", 1)

        cf.apply_icc_profile_load_defaults("/path/to/profile.icc", is_preset=False)

        assert getcfg("last_icc_path") == "/path/to/profile.icc"
        assert getcfg("3dlut.output.profile") == "/path/to/profile.icc"
        assert getcfg("measurement_report.output_profile") == "/path/to/profile.icc"
        assert getcfg("3dlut.tab.enable") == 0
        assert getcfg("3dlut.tab.enable.backup") == 0

    def test_preset_does_not_overwrite_3dlut_source_profiles(self):
        setcfg("3dlut.output.profile", "/existing.icc")
        setcfg("measurement_report.output_profile", "/existing.icc")

        cf.apply_icc_profile_load_defaults("/path/to/preset.icc", is_preset=True)

        assert getcfg("last_icc_path") == "/path/to/preset.icc"
        assert getcfg("3dlut.output.profile") == "/existing.icc"
        assert getcfg("measurement_report.output_profile") == "/existing.icc"


#: The stripped lines of a ``dispwin -s`` video LUT snapshot, which is what a
#: profile-only session saves as its ``.cal`` file.
VIDEO_LUT_SNAPSHOT_LINES = [
    b"CAL",
    b"",
    b'DESCRIPTOR "Argyll Device Calibration Curves"',
    b'ORIGINATOR "Argyll synthcal"',
    b'DEVICE_CLASS "DISPLAY"',
    b'COLOR_REP "RGB"',
    b"BEGIN_DATA_FORMAT",
    b"RGB_I RGB_R RGB_G RGB_B",
    b"END_DATA_FORMAT",
]


class TestFindSettingsProfileForCal:
    @pytest.mark.parametrize("ext", [".icc", ".icm"])
    def test_settingsless_cal_returns_sibling_profile(self, tmp_path, ext):
        cal = tmp_path / "session.cal"
        cal.write_bytes(b"CAL\n")
        profile = tmp_path / f"session{ext}"
        profile.write_bytes(b"")

        result = cf.find_settings_profile_for_cal(str(cal), VIDEO_LUT_SNAPSHOT_LINES)

        assert result == str(profile)

    def test_settingsless_cal_without_sibling_profile_returns_none(self, tmp_path):
        cal = tmp_path / "session.cal"
        cal.write_bytes(b"CAL\n")
        (tmp_path / "other.icc").write_bytes(b"")

        assert (
            cf.find_settings_profile_for_cal(str(cal), VIDEO_LUT_SNAPSHOT_LINES) is None
        )

    def test_legacy_cal_with_settings_returns_none(self, tmp_path):
        cal = tmp_path / "session.cal"
        cal.write_bytes(b"CAL\n")
        (tmp_path / "session.icc").write_bytes(b"")
        lines = [*VIDEO_LUT_SNAPSHOT_LINES, b'TARGET_GAMMA "2.2"']

        assert cf.find_settings_profile_for_cal(str(cal), lines) is None


class TestParseLegacyCal:
    def test_non_display_device_class_is_invalid(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "PRINTER"']

        result = cf.parse_legacy_cal(lines, worker)

        assert result.invalid is True

    def test_device_type_sets_measurement_mode(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'DEVICE_TYPE "CRT"']

        result = cf.parse_legacy_cal(lines, worker)

        assert result.invalid is False
        assert getcfg("measurement_mode") == "c"
        assert "-yc" in worker.options_dispcal

    def test_target_gamma_named_curve_sets_trc(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'TARGET_GAMMA "REC709"']

        result = cf.parse_legacy_cal(lines, worker)

        assert getcfg("trc") == "709"
        assert getcfg("trc.type") == "g"
        assert any(opt.startswith("-g709") for opt in worker.options_dispcal)
        assert lang.getstr("trc") in result.settings

    def test_target_gamma_numeric_value_sets_trc(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'TARGET_GAMMA "2.200000"']

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("trc")) == 2.2
        assert getcfg("trc.type") == "g"

    def test_target_white_xyz_sets_whitepoint_and_luminance(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'TARGET_WHITE_XYZ "95.045000 100.000000 108.905000"',
        ]

        result = cf.parse_legacy_cal(lines, worker)

        # setcfg(..., None) resets to the config default (not a real None),
        # matching the rest of this module's ``setcfg(name, None)`` resets.
        assert getcfg("whitepoint.colortemp") == cf.DEFAULTS["whitepoint.colortemp"]
        assert abs(float(getcfg("whitepoint.x")) - 0.3127) < 0.001
        assert abs(float(getcfg("whitepoint.y")) - 0.3290) < 0.001
        assert float(getcfg("calibration.luminance")) == 100
        assert any(opt.startswith("-w") for opt in worker.options_dispcal)
        assert any(opt.startswith("-b") for opt in worker.options_dispcal)
        assert lang.getstr("whitepoint") in result.settings
        assert lang.getstr("calibration.luminance") in result.settings

    def test_degree_of_black_output_offset(self):
        # NOTE: the legacy CGATS keyword is a 0-100 percentage, but
        # ``calibration.black_output_offset`` is scoped to [0, 1] in the
        # current config schema (VALID_VALUES) -- a pre-existing mismatch
        # already present in the wx original this is a faithful port of
        # (only the bytes/str comparisons were fixed), so a "50" input
        # clamps to the config key's max (1), not 50. Ported faithfully
        # rather than rescaled.
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'DEGREE_OF_BLACK_OUTPUT_OFFSET "50.000000"',
        ]

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("calibration.black_output_offset")) == 1
        assert any(opt.startswith("-f1") for opt in worker.options_dispcal)

    def test_black_point_correction_present_disables_auto(self):
        setcfg("calibration.black_point_correction.auto", 0)
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'BLACK_POINT_CORRECTION "0.500000"',
        ]

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("calibration.black_point_correction")) == 0.5
        assert any(opt.startswith("-k0.5") for opt in worker.options_dispcal)
        # An explicit, non-negative value was found -- don't fall back to auto.
        assert getcfg("calibration.black_point_correction.auto") == 0

    def test_missing_black_point_correction_enables_auto(self):
        setcfg("calibration.black_point_correction.auto", 0)
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"']

        cf.parse_legacy_cal(lines, worker)

        assert getcfg("calibration.black_point_correction.auto") == 1

    def test_target_black_brightness(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'TARGET_BLACK_BRIGHTNESS "0.500000"',
        ]

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("calibration.black_luminance")) == 0.5
        assert any(opt.startswith("-B0.5") for opt in worker.options_dispcal)

    def test_quality(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'QUALITY "High"']

        cf.parse_legacy_cal(lines, worker)

        assert getcfg("calibration.quality") == "h"
        assert "-qh" in worker.options_dispcal

    def test_unrecognized_lines_are_ignored(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b"# just a comment", b"NUMBER_OF_FIELDS 3"]

        result = cf.parse_legacy_cal(lines, worker)

        assert result.invalid is False
        assert result.settings == []


def _ti3_header(*lines: bytes) -> list[bytes]:
    """Build a minimal ``ti3_lines`` list: some header lines + the sentinel."""
    return [*lines, b"BEGIN_DATA_FORMAT"]


class TestApplyProfileB2aFlagsFromTi3:
    def test_use_black_point_compensation_yes(self):
        setcfg("profile.black_point_compensation", 0)
        lines = _ti3_header(b'USE_BLACK_POINT_COMPENSATION "YES"')

        cf.apply_profile_b2a_flags_from_ti3(
            lines, is_preset=False, is_3dlut_preset=False
        )

        assert getcfg("profile.black_point_compensation") == 1

    def test_use_black_point_compensation_no_disables_on_non_preset(self):
        setcfg("profile.black_point_compensation", 1)
        lines = _ti3_header(b'USE_BLACK_POINT_COMPENSATION "NO"')

        cf.apply_profile_b2a_flags_from_ti3(
            lines, is_preset=False, is_3dlut_preset=False
        )

        assert getcfg("profile.black_point_compensation") == 0

    def test_hires_b2a_yes_sets_flag(self):
        setcfg("profile.b2a.hires", 0)
        lines = _ti3_header(b'HIRES_B2A "YES"')

        cf.apply_profile_b2a_flags_from_ti3(
            lines, is_preset=False, is_3dlut_preset=False
        )

        assert getcfg("profile.b2a.hires") == 1

    def test_smooth_b2a_yes_implies_hires_unless_explicitly_no(self):
        setcfg("profile.b2a.hires", 0)
        setcfg("profile.b2a.hires.smooth", 0)
        lines = _ti3_header(b'SMOOTH_B2A "YES"')

        cf.apply_profile_b2a_flags_from_ti3(
            lines, is_preset=False, is_3dlut_preset=False
        )

        assert getcfg("profile.b2a.hires") == 1
        assert getcfg("profile.b2a.hires.smooth") == 1

    def test_smooth_b2a_yes_does_not_force_hires_when_hires_explicitly_no(self):
        setcfg("profile.b2a.hires", 1)
        setcfg("profile.b2a.hires.smooth", 0)
        lines = _ti3_header(b'HIRES_B2A "NO"', b'SMOOTH_B2A "YES"')

        cf.apply_profile_b2a_flags_from_ti3(
            lines, is_preset=False, is_3dlut_preset=False
        )

        assert getcfg("profile.b2a.hires") == 0
        assert getcfg("profile.b2a.hires.smooth") == 1


class TestApplyLut3dConfigMapper:
    def test_no_begin_data_format_is_a_noop(self):
        simset = cf.apply_lut3d_config_mapper(
            [b'SOME_KEYWORD "value"'],
            "/tmp/test.cal",
            False,
            False,
            False,
            False,
            False,
        )

        assert simset is False

    def test_negative_size_value_is_decoded_not_stringified_repr(self):
        # HIRES_B2A_SIZE "-1" fails CGATS's unsigned-number auto-conversion
        # regex and comes back from queryv1() as bytes; a blind str(bytes)
        # would store the literal "b'-1'" -- a latent bug fixed while
        # porting this block (also fixed at the source in display_cal.py).
        lines = _ti3_header(b'HIRES_B2A_SIZE "-1"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("profile.b2a.hires.size") == -1

    def test_gamut_mapping_mode_g_maps_to_0(self):
        # cfgvalue comes back as bytes (b"G"); comparing it against the str
        # "G" (the wx original's bug) is always False -- fixed to compare
        # against b"G" so a real "G" value actually maps to 0.
        lines = _ti3_header(b'3DLUT_GAMUT_MAPPING_MODE "G"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.gamap.use_b2a") == 0

    def test_gamut_mapping_mode_other_maps_to_1(self):
        lines = _ti3_header(b'3DLUT_GAMUT_MAPPING_MODE "g"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.gamap.use_b2a") == 1

    def test_patch_sequence_is_lowercased_without_crashing(self):
        # cfgvalue.lower().replace("_rgb_", "_RGB_") with str args on a
        # bytes cfgvalue raised TypeError in the wx original whenever this
        # keyword was present at all -- fixed to use bytes replace args.
        lines = _ti3_header(b'PATCH_SEQUENCE "OPTIMIZE_DISPLAY_RESPONSE_DELAY"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("testchart.patch_sequence") == "optimize_display_response_delay"

    def test_patch_sequence_rgb_marker_uppercased(self):
        # Mirrors how the writer round-trips this keyword: it upper()s the
        # config value before writing, so a valid "..._RGB_..." enum value
        # comes back as "..._RGB_..." (all-caps) on disk; the lower()+
        # replace() here restores the enum's actual mixed case on read.
        lines = _ti3_header(b'PATCH_SEQUENCE "MAXIMIZE_RGB_DIFFERENCE"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("testchart.patch_sequence") == "maximize_RGB_difference"

    def test_negative_gamma_sets_type_b(self):
        lines = _ti3_header(b'3DLUT_GAMMA "-2.400000"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.trc_gamma_type") == "B"
        assert float(getcfg("3dlut.trc_gamma")) == 2.4
        assert getcfg("measurement_report.trc_gamma_type") == "B"

    def test_positive_gamma_sets_type_b_lowercase(self):
        lines = _ti3_header(b'3DLUT_GAMMA "2.200000"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.trc_gamma_type") == "b"
        assert float(getcfg("3dlut.trc_gamma")) == 2.2

    def test_simulation_profile_keyword_sets_simset(self):
        lines = _ti3_header(b'SIMULATION_PROFILE "hdr.icc"')

        simset = cf.apply_lut3d_config_mapper(
            lines, "/tmp/somewhere/test.cal", False, False, False, False, False
        )

        assert simset is True
        assert getcfg("measurement_report.simulation_profile") == os.path.join(
            "/tmp/somewhere", "hdr.icc"
        )

    def test_relative_source_profile_resolved_against_file_dir(self):
        lines = _ti3_header(b'3DLUT_SOURCE_PROFILE "foo.icc"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/somewhere/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.input.profile") == os.path.join(
            "/tmp/somewhere", "foo.icc"
        )
        # Sync onto measurement report settings too (not an HDR/simset load).
        assert getcfg("measurement_report.simulation_profile") == os.path.join(
            "/tmp/somewhere", "foo.icc"
        )
        assert getcfg("measurement_report.use_simulation_profile") == 1

    def test_any_3dlut_keyword_enables_3dlut_create_and_tab(self):
        setcfg("3dlut.create", 0)
        setcfg("3dlut.tab.enable", 0)
        lines = _ti3_header(b'3DLUT_SIZE "33"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.create") == 1
        assert getcfg("3dlut.tab.enable") == 1
        assert getcfg("3dlut.tab.enable.backup") == 1

    def test_content_colorspace_is_applied(self):
        lines = _ti3_header(b'3DLUT_CONTENT_COLORSPACE_WHITE_X "0.312700"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.content.colorspace.white.x") == 0.3127

    def test_trc_fallback_bt1886_when_not_set_explicitly(self):
        setcfg("3dlut.trc_gamma_type", "B")
        setcfg("3dlut.trc_output_offset", 0)
        setcfg("3dlut.trc_gamma", 2.4)
        lines = _ti3_header(b'3DLUT_SIZE "33"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.trc") == "bt1886"

    def test_trc_fallback_gamma22_when_not_set_explicitly(self):
        setcfg("3dlut.trc_gamma_type", "b")
        setcfg("3dlut.trc_output_offset", 1)
        setcfg("3dlut.trc_gamma", 2.2)
        lines = _ti3_header(b'3DLUT_SIZE "33"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.trc") == "gamma2.2"

    def test_trc_not_overwritten_when_keyword_present(self):
        setcfg("3dlut.trc_gamma_type", "B")
        setcfg("3dlut.trc_output_offset", 0)
        setcfg("3dlut.trc_gamma", 2.4)
        lines = _ti3_header(b'3DLUT_TRC "customgamma"')

        cf.apply_lut3d_config_mapper(
            lines, "/tmp/test.cal", False, False, False, False, False
        )

        assert getcfg("3dlut.trc") == "customgamma"

    def test_display_update_delay_overridden_when_display_and_instrument_match(self):
        setcfg("measure.override_min_display_update_delay_ms", 0)
        setcfg("measure.override_min_display_update_delay_ms.backup", None)
        setcfg("measure.min_display_update_delay_ms", 30)
        lines = _ti3_header(b'MIN_DISPLAY_UPDATE_DELAY_MS "150"')

        cf.apply_lut3d_config_mapper(
            lines,
            "/tmp/test.cal",
            False,
            False,
            display_match=True,
            instrument_match=True,
            has_instrument_id=True,
        )

        assert getcfg("measure.override_min_display_update_delay_ms") == 1
        assert int(getcfg("measure.min_display_update_delay_ms")) == 150

    def test_display_update_delay_untouched_without_match_or_backup(self):
        setcfg("measure.override_min_display_update_delay_ms", 0)
        setcfg("measure.override_min_display_update_delay_ms.backup", None)
        lines = _ti3_header(b'MIN_DISPLAY_UPDATE_DELAY_MS "150"')

        cf.apply_lut3d_config_mapper(
            lines,
            "/tmp/test.cal",
            False,
            False,
            display_match=False,
            instrument_match=False,
            has_instrument_id=True,
        )

        assert getcfg("measure.override_min_display_update_delay_ms") == 0


class TestApplyLut3dDisplayOverrides:
    def test_resolve_disables_3dlut_and_uses_devlink(self):
        setcfg("displays", ["Resolve"])
        setcfg("display.number", 1)
        setcfg("3dlut.enable", 1)
        setcfg("measurement_report.use_devlink_profile", 0)

        cf.apply_lut3d_display_overrides(False)

        assert getcfg("3dlut.enable") == 0
        assert getcfg("measurement_report.use_devlink_profile") == 1

    def test_prisma_enables_3dlut(self):
        setcfg("displays", ["Prisma"])
        setcfg("display.number", 1)
        setcfg("3dlut.enable", 0)
        setcfg("measurement_report.use_devlink_profile", 1)

        cf.apply_lut3d_display_overrides(False)

        assert getcfg("3dlut.enable") == 1
        assert getcfg("measurement_report.use_devlink_profile") == 0

    def test_madvr_hdr_simset_disables_3dlut(self):
        setcfg("displays", ["Some Display @ 0, 0, 1920x1080"])
        setcfg("display.number", 1)
        setcfg("3dlut.format", "madVR")
        setcfg("3dlut.enable", 1)
        setcfg("measurement_report.use_devlink_profile", 0)

        cf.apply_lut3d_display_overrides(True)

        assert getcfg("3dlut.enable") == 0
        assert getcfg("measurement_report.use_devlink_profile") == 1

    def test_madvr_without_simset_is_untouched(self):
        setcfg("displays", ["Some Display @ 0, 0, 1920x1080"])
        setcfg("display.number", 1)
        setcfg("3dlut.format", "madVR")
        setcfg("3dlut.enable", 1)
        setcfg("measurement_report.use_devlink_profile", 0)

        cf.apply_lut3d_display_overrides(False)

        assert getcfg("3dlut.enable") == 1
        assert getcfg("measurement_report.use_devlink_profile") == 0


class TestImportSessionArchive:
    def test_zip_extracts_and_returns_storage_path(self, tmp_path):
        cal_file = tmp_path / "test.cal"
        cal_file.write_text("dummy")
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(cal_file, "test.cal")
        tempdir = tmp_path / "extract"
        tempdir.mkdir()
        setcfg("profile.save_path", str(tmp_path / "storage"))

        request = cf.SessionArchiveImportRequest(
            path=str(archive_path),
            basename="test",
            ext=".zip",
            tempdir=str(tempdir),
        )
        result = cf.import_session_archive(request, exec_cmd=None)

        assert not isinstance(result, Exception)
        # Uses the extracted file's own extension (.cal), not the archive's
        # (.zip) -- a latent bug in the wx original this port also fixes.
        assert result == os.path.join(str(tmp_path / "storage"), "test", "test.cal")
        assert (tempdir / "test.cal").exists()

    def test_zip_without_session_file_returns_error(self, tmp_path):
        other_file = tmp_path / "notes.txt"
        other_file.write_text("dummy")
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(other_file, "notes.txt")
        tempdir = tmp_path / "extract"
        tempdir.mkdir()

        request = cf.SessionArchiveImportRequest(
            path=str(archive_path),
            basename="test",
            ext=".zip",
            tempdir=str(tempdir),
        )
        result = cf.import_session_archive(request, exec_cmd=None)

        assert isinstance(result, Exception)

    def test_7z_without_sevenzip_returns_error(self, tmp_path):
        request = cf.SessionArchiveImportRequest(
            path=str(tmp_path / "test.7z"),
            basename="test",
            ext=".7z",
            tempdir=str(tmp_path),
            sevenzip=None,
        )

        result = cf.import_session_archive(request, exec_cmd=None)

        assert isinstance(result, Exception)

    def test_7z_extracts_using_exec_cmd(self, tmp_path):
        tempdir = tmp_path / "extract"
        tempdir.mkdir()

        def fake_exec_cmd(*args, **kwargs):
            (tempdir / "test.icc").write_text("dummy")
            return True

        setcfg("profile.save_path", str(tmp_path / "storage"))
        request = cf.SessionArchiveImportRequest(
            path=str(tmp_path / "test.7z"),
            basename="test",
            ext=".7z",
            tempdir=str(tempdir),
            sevenzip="/usr/bin/7z",
        )

        result = cf.import_session_archive(request, exec_cmd=fake_exec_cmd)

        assert result == os.path.join(str(tmp_path / "storage"), "test", "test.icc")


def test_restore_defaults_keeps_ui_toolkit_preferences():
    """Restoring defaults must not silently switch a Qt user back to wx."""
    setcfg("ui.toolkit", "qt")
    setcfg("ui.offer_qt", 0)
    try:
        cf.restore_defaults()
        assert getcfg("ui.toolkit") == "qt"
        assert getcfg("ui.offer_qt") == 0
    finally:
        setcfg("ui.toolkit", None)
        setcfg("ui.offer_qt", None)
