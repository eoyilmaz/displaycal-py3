"""Toolkit-neutral helpers for the calibration/profile-file header bar.

Pure pieces lifted out of ``MainFrame``'s calibration-file-bar handlers
(``display_cal.py``): the recent-calibrations/presets bootstrap, current-file
resolution, calibration-file parsing, the config-restore /
CGATS-option-to-config dispatch behind ``load_cal_handler``, the
related-files-for-deletion scan, and session-archive file selection. The
per-option setter functions this module dispatches to already live in
:mod:`DisplayCAL.main_settings` (Stage 0); this module supplies the
orchestration ``load_cal_handler`` used to call them. None of it touches a GUI
toolkit, so both the still-shipping wx path and the Qt header bar
(:mod:`DisplayCAL.ui.main_window`) can share it.

Deliberately not reproduced here (documented, not silently dropped):

* The "d" dispcal option's virtual-display auto-select (``-dweb`` /
  ``-dmadvr``, used by the ``video_*`` pattern-generator presets) -- already
  deferred Pile-2 pattern-generator scope (see ``MAINFRAME_PORT_PLAN.md``'s
  "Deferred to the Qt main window").
* Cross-window resync (``lut3dframe``, ``reportframe``) -- those tool windows
  aren't ported to Qt.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from typing import Callable

from send2trash import send2trash

from DisplayCAL import localization as lang
from DisplayCAL import main_settings
from DisplayCAL.cgats import CGATS
from DisplayCAL.colormath import XYZ2xyY
from DisplayCAL.config import (
    DEFAULTS,
    EXE_EXT,
    PROFILE_EXT,
    get_data_path,
    get_display_name,
    getcfg,
    is_virtual_display,
    setcfg,
)
from DisplayCAL.debughelpers import Error
from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError, Text
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_io import TarFileProper
from DisplayCAL.util_list import index_fallback_ignorecase, natsort
from DisplayCAL.util_os import safe_glob
from DisplayCAL.util_str import safe_str, strtr
from DisplayCAL.worker import Worker

#: Recognized calibration/profile file extensions (mirrors ``display_cal``'s
#: module-level constants of the same name, duplicated here to avoid pulling
#: wx into this toolkit-neutral module).
ICCPROFILE_FILE_EXTENSIONS = (".icc", ".icm")
COMPRESSED_FILE_EXTENSIONS = (".7z", ".tar.gz", ".tgz", ".zip")


class CalibrationFileError(Exception):
    """A calibration/profile file failed to validate or parse.

    Args:
        lang_key: A :mod:`DisplayCAL.localization` key describing the error.
        path: The file path involved, appended to the message if given.
    """

    def __init__(self, lang_key: str, path: str | None = None) -> None:
        self.lang_key = lang_key
        self.path = path
        message = lang.getstr(lang_key)
        if path:
            message = f"{message}\n{path}"
        super().__init__(message)


def build_recent_calibrations() -> tuple[list[str], list[str]]:
    """Return ``(recent_cals, presets)``, mirroring ``MainFrame.__init__``.

    ``recent_cals`` always starts with a leading ``""`` entry (the "new
    settings" / no-calibration choice), followed by any bundled presets, then
    the paths persisted in the ``recent_cals`` config option.
    """
    recent_cals = getcfg("recent_cals").split(os.pathsep)
    while "" in recent_cals:
        recent_cals.remove("")
    recent_cals.insert(0, "")

    presets: list[str] = []
    found = get_data_path("presets", r".*\.(?:icc|icm)$")
    if isinstance(found, list):
        presets = natsort(found)
        presets.reverse()
        for preset in presets:
            if preset in recent_cals:
                recent_cals.remove(preset)
            recent_cals.insert(1, preset)
    return recent_cals, presets


def get_unpreseted_recent_calibrations(
    recent_cals: list[str], presets: list[str]
) -> list[str]:
    """Return ``recent_cals`` entries that are not bundled presets."""
    return [recent_cal for recent_cal in recent_cals if recent_cal not in presets]


@dataclass
class CalibrationSelection:
    """The result of resolving the current ``calibration.file`` config value."""

    cal: str | None
    filename: str | None
    profile_path: str | None
    profile_exists: bool
    #: True if ``cal`` was not already in ``recent_cals`` and should be
    #: appended (and persisted to the ``recent_cals`` config option).
    is_new_recent: bool
    #: True if ``cal`` no longer exists on disk and should be dropped from
    #: ``recent_cals`` (mirrors wx clearing the selection back to "new").
    missing: bool = False


def resolve_calibration_selection(
    cal: str | None, recent_cals: list[str]
) -> CalibrationSelection:
    """Resolve ``cal`` against ``recent_cals``.

    Mirrors wx's ``update_calibration_file_ctrl`` method of the same name.

    Args:
        cal: The ``calibration.file`` config value (may be ``None``/falsy).
        recent_cals: The current in-memory recent-calibrations list.

    Returns:
        A :class:`CalibrationSelection` describing what to show / persist.
        Callers are responsible for actually mutating ``recent_cals`` and the
        ``recent_cals`` config option based on ``is_new_recent`` / ``missing``,
        since this function does not mutate its input.
    """
    if cal and os.path.isfile(cal):
        filename, ext = os.path.splitext(cal)
        is_new_recent = cal not in recent_cals
        if ext.lower() in ICCPROFILE_FILE_EXTENSIONS:
            profile_path = cal
        else:
            profile_path = filename + PROFILE_EXT
        return CalibrationSelection(
            cal=cal,
            filename=filename,
            profile_path=profile_path,
            profile_exists=os.path.exists(profile_path),
            is_new_recent=is_new_recent,
        )
    return CalibrationSelection(
        cal=None,
        filename=None,
        profile_path=None,
        profile_exists=False,
        is_new_recent=False,
        missing=bool(cal) and cal in recent_cals[1:],
    )


def parse_calibration_file(path: str) -> tuple[ICCProfile | None, list[bytes]]:
    """Parse a ``.cal`` file or ICC profile, returning ``(profile, ti3_lines)``.

    Faithful port of ``parse_calibration_file`` / ``validate_icc_profile`` /
    ``validate_calibration_data``, minus the wx ``InfoDialog`` calls (raises
    :class:`CalibrationFileError` instead).
    """
    ext = os.path.splitext(path)[-1]
    if ext.lower() not in ICCPROFILE_FILE_EXTENSIONS:
        try:
            with open(path, "rb") as cal_file:
                return None, [line.strip() for line in cal_file]
        except OSError as exception:
            raise CalibrationFileError("error.file.open", path) from exception

    try:
        profile = ICCProfile(path)
    except (OSError, ICCProfileInvalidError) as exception:
        raise CalibrationFileError("profile.invalid", path) from exception
    if profile.profileClass != b"mntr" or profile.colorSpace != b"RGB":
        raise CalibrationFileError("profile.invalid", path)

    cied = profile.tags.get("CIED")
    if cied:
        with io.BytesIO(cied) as cal_data:
            return profile, [line.strip() for line in cal_data]

    targ = profile.tags.get("targ")
    if not (targ and isinstance(targ, Text)):
        raise CalibrationFileError("profile.no_targ", path)
    with io.BytesIO(targ.tagData) as cal_data:
        return profile, [line.strip() for line in cal_data]


#: Config keys never touched by :func:`restore_defaults`, mirroring
#: ``restore_defaults_handler``'s ``skip`` list verbatim.
_RESTORE_SKIP = (
    "allow_skip_sensor_cal",
    "app.allow_network_clients",
    "app.port",
    "argyll.dir",
    "argyll.version",
    "calibration.autoload",
    "calibration.black_point_rate.enabled",
    "calibration.file.previous",
    "calibration.update",
    "colorimeter_correction.instrument",
    "colorimeter_correction.instrument.reference",
    "colorimeter_correction.measurement_mode",
    "colorimeter_correction.measurement_mode.reference",
    "colorimeter_correction.measurement_mode.reference.projector",
    "colorimeter_correction_matrix_file",
    "comport.number",
    "copyright",
    "dimensions.measureframe.whitepoint.visual_editor",
    "display.number",
    "display.technology",
    "display_lut.link",
    "display_lut.number",
    "displays",
    "dry_run",
    "enumerate_ports.auto",
    "gamma",
    "iccgamut.surface_detail",
    "instruments",
    "lang",
    "last_3dlut_path",
    "last_cal_path",
    "last_cal_or_icc_path",
    "last_colorimeter_ti3_path",
    "last_filedialog_path",
    "last_icc_path",
    "last_reference_ti3_path",
    "last_testchart_export_path",
    "last_ti1_path",
    "last_ti3_path",
    "last_vrml_path",
    "log.show",
    "lut_viewer.show",
    "lut_viewer.show_actual_lut",
    "measurement_mode",
    "measurement_mode.projector",
    "measurement.name.expanded",
    "measurement.play_sound",
    "measurement.save_path",
    "multiprocessing.max_cpus",
    "patterngenerator.apl",
    "patterngenerator.resolve",
    "patterngenerator.resolve.port",
    "profile.b2a.hires.diagpng",
    "profile.create_gamut_views",
    "profile.install_scope",
    "profile.license",
    "profile.load_on_login",
    "profile.name",
    "profile.name.expanded",
    "profile.save_path",
    "profile_loader.check_gamma_ramps",
    "profile_loader.error.show_msg",
    "profile_loader.exceptions",
    "profile_loader.fix_profile_associations",
    "profile_loader.known_apps",
    "profile_loader.known_window_classes",
    "profile_loader.reset_gamma_ramps",
    "profile_loader.use_madhcnet",
    "profile_loader.verify_calibration",
    "profile.update",
    "position.x",
    "position.y",
    "position.info.x",
    "position.info.y",
    "position.lut_viewer.x",
    "position.lut_viewer.y",
    "position.lut3dframe.x",
    "position.lut3dframe.y",
    "position.synthiccframe.x",
    "position.synthiccframe.y",
    "position.profile_info.x",
    "position.profile_info.y",
    "position.progress.x",
    "position.progress.y",
    "position.reportframe.x",
    "position.reportframe.y",
    "position.scripting.x",
    "position.scripting.y",
    "position.tcgen.x",
    "position.tcgen.y",
    "recent_cals",
    "report.pack_js",
    "settings.changed",
    "show_advanced_options",
    "show_donation_message",
    "skip_legacy_serial_ports",
    "skip_scripts",
    "sudo.preserve_environment",
    "tc_precond_profile",
    "tc_vrml_cie",
    "tc_vrml_cie_colorspace",
    "tc_vrml_device",
    "tc_vrml_device_colorspace",
    "tc.show",
    "uniformity.measure.continuous",
    "untethered.measure.auto",
    "untethered.measure.manual.delay",
    "untethered.max_delta.chroma",
    "untethered.min_delta",
    "untethered.min_delta.lightness",
    "update_check",
    "webserver.portnumber",
    "whitepoint.visual_editor.bg_v",
    "whitepoint.visual_editor.b",
    "whitepoint.visual_editor.g",
    "whitepoint.visual_editor.r",
    "x3dom.cache",
    "x3dom.embed",
)


def restore_defaults(
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    override: dict | None = None,
) -> None:
    """Reset config keys to their defaults, mirroring ``restore_defaults_handler``.

    Only the config-mutating body is ported (the confirmation dialog and the
    window-refresh tail in wx only run when triggered from a menu, i.e. with a
    real event; ``load_cal_handler`` always calls this with no event).
    """
    override_default = {
        "app.dpi": None,
        "calibration.black_luminance": None,
        "calibration.luminance": None,
        "gamap_src_viewcond": None,
        "gamap_out_viewcond": None,
        "testchart.file": "auto",
        "trc": DEFAULTS["gamma"],
        "whitepoint.colortemp": None,
        "whitepoint.x": None,
        "whitepoint.y": None,
        "3dlut.whitepoint.x": None,
        "3dlut.whitepoint.y": None,
    }
    if override:
        override_default.update(override)
    override = override_default

    def _matches(name: str) -> bool:
        included = len(include) == 0 or any(name.find(item) == 0 for item in include)
        excluded = len(exclude) != 0 and any(name.find(item) == 0 for item in exclude)
        return included and not excluded

    for name in DEFAULTS:
        if name not in _RESTORE_SKIP and name not in override and _matches(name):
            if name.endswith(".backup") and name == "measurement_mode.backup":
                setcfg("measurement_mode", getcfg("measurement_mode.backup"))
            setcfg(name, None)
    for name in override:
        if _matches(name):
            setcfg(name, override[name])


#: dispcal option letter -> ``main_settings`` setter taking just ``option``.
#: The "d" (display number) and "X"/"E" options are intentionally excluded,
#: see module docstring; "k", "V", "YA", "H", "F" need a constant or extra
#: argument instead of ``option`` itself and are handled inline below.
_DISPCAL_OPTION_SETTERS = {
    "m": main_settings.set_interactive_display_adjustment_config_with_option,
    "q": main_settings.set_calibration_quality_config_with_option,
    "y": main_settings.set_measurement_mode_config_with_option,
    "t": main_settings.set_whitepoint_temperature_config_with_option,
    "T": main_settings.set_whitepoint_temperature_config_with_option,
    "W": main_settings.set_whitepoint_config_with_option,
    "b": main_settings.set_calibration_luminance_config_with_option,
    "g": main_settings.set_tone_response_curve_config_with_option,
    "G": main_settings.set_tone_response_curve_config_with_option,
    "f": main_settings.set_calibration_black_output_offset_config_with_option,
    "a": main_settings.set_ambient_view_condition_adjustment_config_with_option,
    "A": main_settings.set_calibration_black_point_rate_config_with_option,
    "B": main_settings.set_calibration_black_luminance_config_with_option,
    "P": main_settings.set_measureframe_config_with_option,
    "p": main_settings.set_measurement_mode_projector_config_with_option,
    "I": main_settings.set_drift_compensation_config_with_option,
    "Q": main_settings.set_tristimulus_observer_config_with_option,
}

#: colprof option letter -> ``main_settings`` setter taking just ``option``.
_COLPROF_OPTION_SETTERS = {
    "q": main_settings.set_profile_quality_config_with_option,
    "b": main_settings.set_profile_quality_b2a_config_with_option,
    "s": main_settings.set_gamap_profile_config_with_option,
    "S": main_settings.set_gamap_profile_config_with_option,
    "c": main_settings.set_gamap_src_viewcond_config_with_option,
    "d": main_settings.set_gamap_out_viewcond_config_with_option,
    "t": main_settings.set_gamap_perceptual_intent_config_with_option,
    "T": main_settings.set_gamap_saturation_intent_config_with_option,
}


def _dispatch_dispcal_option(option: str, black_point_correction: bool) -> bool:
    """Apply one dispcal option, returning the updated black-point-correction flag."""
    head, pair = option[0:1], option[0:2]
    if head == "k":
        (black_point_correction,) = (
            main_settings.set_black_point_correction_config_with_option(
                option, black_point_correction
            )
        )
    elif head == "V":
        main_settings.set_measurement_mode_adaptive_config_with_option(1)
    elif pair == "YA":
        main_settings.set_measurement_mode_adaptive_config_with_option(0)
    elif head == "H":
        main_settings.set_measurement_mode_highres_config_with_option(1)
    elif head == "F":
        main_settings.set_measure_darken_background_config_with_option(1)
    else:
        setter = _DISPCAL_OPTION_SETTERS.get(head, _DISPCAL_OPTION_SETTERS.get(pair))
        if setter is not None:
            setter(option)
    return black_point_correction


def apply_calibration_options(
    options_dispcal: list[str] | None, options_colprof: list[str] | None
) -> None:
    """Dispatch dispcal/colprof options to their ``main_settings`` config setters.

    Faithful port of ``load_cal_handler``'s two dispatch loops for the setters
    that ``main_settings`` already exposes (see module docstring for what's
    excluded: the "d"/display-number option, and the HDR 3D LUT config-mapper
    block that follows them in wx).
    """
    trc = bool(options_dispcal) and any(
        option[0:1] in ("g", "G") for option in options_dispcal
    )
    restore_defaults(
        include=(
            "calibration",
            "drift_compensation",
            "measure.darken_background",
            "measure.override_min_display_update_delay_ms",
            "measure.min_display_update_delay_ms",
            "measure.override_display_settle_time_mult",
            "measure.display_settle_time_mult",
            "observer",
            "patterngenerator.ffp_insertion",
            "trc",
            "whitepoint",
        ),
        exclude=(
            "calibration.black_point_correction_choice.show",
            "calibration.update",
            "calibration.use_video_lut",
            "measure.darken_background.show_warning",
            "patterngenerator.ffp_insertion.interval",
            "patterngenerator.ffp_insertion.duration",
            "patterngenerator.ffp_insertion.level",
            "trc.should_use_viewcond_adjust.show_msg",
        ),
        override={"trc": ""} if not trc else None,
    )

    black_point_correction = False
    if options_dispcal:
        for option in options_dispcal:
            black_point_correction = _dispatch_dispcal_option(
                option, black_point_correction
            )
        if trc and not black_point_correction:
            setcfg("calibration.black_point_correction.auto", 1)
    main_settings.update_whitepoint_config_from_temperature()

    if options_colprof:
        restore_defaults(
            include=(
                "profile",
                "gamap_",
                "3dlut.create",
                "3dlut.output.profile.apply_cal",
                "3dlut.trc",
                "testchart.auto_optimize",
                "testchart.patch_sequence",
            ),
            exclude=(
                "3dlut.tab.enable.backup",
                "profile.update",
                "profile.name",
                "gamap_default_intent",
            ),
        )
        for option in options_colprof:
            setter = _COLPROF_OPTION_SETTERS.get(
                option[0:1], _COLPROF_OPTION_SETTERS.get(option[0:2])
            )
            if setter is None:
                continue
            setter(option)


@dataclass
class DisplayInstrumentMatch:
    """Result of :func:`match_display_and_instrument`.

    Callers apply the found indexes via ``setcfg`` (and, in wx, the
    ``get_set_display()`` / ``update_comports()`` UI-sync calls this
    function deliberately doesn't reproduce -- the Qt caller's own
    ``update_controls()`` already repopulates both selectors from config).
    """

    #: Index into ``worker.display_edid``/``display_names``, or ``None`` if
    #: no unambiguous match was found.
    display_index: int | None = None
    #: Whether ``display_index`` differs from the currently selected display.
    display_changed: bool = False
    #: Whether the matched display is virtual/"SII REPEATER", in which case
    #: wx re-enables the 3D LUT tab it disabled when it started loading an
    #: ICC profile (see ``apply_icc_profile_load_defaults``).
    reenable_3dlut_tab: bool = False
    #: Index into ``worker.instruments``, or ``None`` if no match was found.
    instrument_index: int | None = None
    instrument_match: bool = False
    #: Whether the profile carried an embedded instrument ID at all
    #: (regardless of whether it matched), needed by
    #: :func:`apply_lut3d_config_mapper`'s display-update-delay/settle-time
    #: override gating.
    has_instrument_id: bool = False


def match_display_and_instrument(
    profile: ICCProfile, worker: Worker
) -> DisplayInstrumentMatch:
    """Match a loaded ICC profile's embedded EDID/instrument info.

    Faithful port of the ``display_name_indexes`` / ``edid_md5_indexes`` /
    instrument-matching block in ``load_cal_handler``, against the displays
    and instruments ``worker`` last enumerated.
    """
    match = DisplayInstrumentMatch()

    display_name = profile.getDeviceModelDescription()
    profile_tags_meta = profile.tags.get("meta", {})
    edid_md5 = profile_tags_meta.get("EDID_md5", {}).get("value")
    if display_name or edid_md5:
        display_name_indexes = []
        edid_md5_indexes = []
        for i, edid in enumerate(worker.display_edid):
            if display_name in (
                edid.get("monitor_name", False),
                worker.display_names[i],
            ):
                display_name_indexes.append(i)
            if edid_md5 == edid.get("hash", False):
                edid_md5_indexes.append(i)

        display_index = None
        if len(display_name_indexes) == 1:
            display_index = display_name_indexes[0]
        elif len(edid_md5_indexes) == 1:
            display_index = edid_md5_indexes[0]
        # Else: several matches: can't be sure which is the right one, do
        # nothing (matching wx).

        if display_index is not None:
            match.display_index = display_index
            match.display_changed = get_display_name(None, False) != get_display_name(
                display_index, False
            )
            if is_virtual_display() or get_display_name() == "SII REPEATER":
                match.reenable_3dlut_tab = True

    instrument_id = profile_tags_meta.get("MEASUREMENT_device", {}).get("value")
    match.has_instrument_id = bool(instrument_id)
    if instrument_id:
        for i, instrument in enumerate(worker.instruments):
            if instrument.lower() == instrument_id:
                match.instrument_index = i
                match.instrument_match = True
                break

    return match


def apply_icc_profile_load_defaults(path: str, is_preset: bool) -> None:
    """Apply the config side effects ``load_cal_handler`` sets when loading an ICC profile.

    Faithful port of the top of ``load_cal_handler``'s ICC-profile branch,
    minus the EDID/instrument matching (:func:`match_display_and_instrument`,
    called separately since it needs a ``Worker`` and returns indexes for the
    caller to ``setcfg``/repopulate controls with).
    """
    setcfg("last_icc_path", path)
    if not is_preset:
        setcfg("3dlut.output.profile", path)
        setcfg("measurement_report.output_profile", path)
    # Disable 3D LUT tab when switching from madVR / Resolve; re-enabled by
    # the caller if match_display_and_instrument() finds a virtual display.
    setcfg("3dlut.tab.enable", 0)
    setcfg("3dlut.tab.enable.backup", 0)


def apply_profile_b2a_flags_from_ti3(
    ti3_lines: list[bytes], is_preset: bool, is_3dlut_preset: bool
) -> None:
    """Sync BPC/hires-B2A/smooth-B2A checkboxes from a loaded TI3's flags.

    Faithful port of the ``USE_BLACK_POINT_COMPENSATION``/``HIRES_B2A``/
    ``SMOOTH_B2A`` checks at the top of ``load_cal_handler``'s post-dispatch
    tail. Fixes a latent bug found while porting (also fixed at the source in
    ``display_cal.py``, following the established pattern for this
    lightly-tested part of ``load_cal_handler`` -- see the module docstring):
    every check compared these ``str`` literals against ``ti3_lines`` (a
    ``list[bytes]``, since :func:`parse_calibration_file` opens non-ICC files
    in binary mode), so none of them could ever match -- this whole block was
    dead code.
    """
    if b'USE_BLACK_POINT_COMPENSATION "YES"' in ti3_lines:
        setcfg("profile.black_point_compensation", 1)
    elif b'USE_BLACK_POINT_COMPENSATION "NO"' in ti3_lines and (
        sys.platform != "darwin" or not is_preset or is_3dlut_preset
    ):
        # Only disable BPC if not OS X, or if a preset, or if a 3D LUT preset
        setcfg("profile.black_point_compensation", 0)
    if b'HIRES_B2A "YES"' in ti3_lines:
        setcfg("profile.b2a.hires", 1)
    elif b'HIRES_B2A "NO"' in ti3_lines:
        setcfg("profile.b2a.hires", 0)
    if b'SMOOTH_B2A "YES"' in ti3_lines:
        if b'HIRES_B2A "NO"' not in ti3_lines:
            setcfg("profile.b2a.hires", 1)
        setcfg("profile.b2a.hires.smooth", 1)
    elif b'SMOOTH_B2A "NO"' in ti3_lines:
        if b'HIRES_B2A "YES"' not in ti3_lines:
            setcfg("profile.b2a.hires", 0)
        setcfg("profile.b2a.hires.smooth", 0)


#: Header/DATA_FORMAT keyword -> config key, for the 3D LUT / measurement-
#: report metadata a loaded ICC profile or "modern" ``.cal`` file's CGATS
#: header (before ``BEGIN_DATA_FORMAT``) may carry. Mirrors
#: ``load_cal_handler``'s ``config_mapper`` dict verbatim, including the
#: legacy ``3DLUT_HDR_MAXCLL`` -> ``3dlut.hdr_maxmll`` alias.
_LUT3D_CONFIG_MAPPER = {
    "SMOOTH_B2A_SIZE": "profile.b2a.hires.size",
    "HIRES_B2A_SIZE": "profile.b2a.hires.size",
    # NOTE profile black point correction is not the same as calibration
    # black point correction! See Worker.create_profile in worker.py
    "BLACK_POINT_CORRECTION": "profile.black_point_correction",
    "MIN_DISPLAY_UPDATE_DELAY_MS": "measure.min_display_update_delay_ms",
    "DISPLAY_SETTLE_TIME_MULT": "measure.display_settle_time_mult",
    "FFP_INSERTION_INTERVAL": "patterngenerator.ffp_insertion.interval",
    "FFP_INSERTION_DURATION": "patterngenerator.ffp_insertion.duration",
    "FFP_INSERTION_LEVEL": "patterngenerator.ffp_insertion.level",
    "AUTO_OPTIMIZE": "testchart.auto_optimize",
    "PATCH_SEQUENCE": "testchart.patch_sequence",
    "3DLUT_SOURCE_PROFILE": "3dlut.input.profile",
    "3DLUT_TRC": "3dlut.trc",
    "3DLUT_HDR_PEAK_LUMINANCE": "3dlut.hdr_peak_luminance",
    "3DLUT_HDR_SAT": "3dlut.hdr_sat",
    "3DLUT_HDR_HUE": "3dlut.hdr_hue",
    "3DLUT_HDR_DISPLAY": "3dlut.hdr_display",
    # MaxCLL is no longer used, map to mastering display max light level (MaxMLL)
    "3DLUT_HDR_MAXCLL": "3dlut.hdr_maxmll",
    "3DLUT_HDR_MAXMLL": "3dlut.hdr_maxmll",
    "3DLUT_HDR_MAXMLL_ALT_CLIP": "3dlut.hdr_maxmll_alt_clip",
    "3DLUT_HDR_MINMLL": "3dlut.hdr_minmll",
    "3DLUT_HDR_AMBIENT_LUMINANCE": "3dlut.hdr_ambient_luminance",
    "3DLUT_GAMMA": "3dlut.trc_gamma",
    "3DLUT_DEGREE_OF_BLACK_OUTPUT_OFFSET": "3dlut.trc_output_offset",
    "3DLUT_INPUT_ENCODING": "3dlut.encoding.input",
    "3DLUT_OUTPUT_ENCODING": "3dlut.encoding.output",
    "3DLUT_GAMUT_MAPPING_MODE": "3dlut.gamap.use_b2a",
    "3DLUT_RENDERING_INTENT": "3dlut.rendering_intent",
    "3DLUT_FORMAT": "3dlut.format",
    "3DLUT_SIZE": "3dlut.size",
    "3DLUT_INPUT_BITDEPTH": "3dlut.bitdepth.input",
    "3DLUT_OUTPUT_BITDEPTH": "3dlut.bitdepth.output",
    "3DLUT_APPLY_CAL": "3dlut.output.profile.apply_cal",
    "SIMULATION_PROFILE": "measurement_report.simulation_profile",
}


def _decode_cfgvalue(cfgvalue: bytes | int | float) -> str:
    """Return ``cfgvalue`` as ``str``, decoding it first if it's ``bytes``.

    :meth:`CGATS.queryv1` auto-converts unsigned numeric header values to
    ``int``/``float`` but leaves quoted/signed/non-numeric ones as ``bytes``
    -- plain ``str(cfgvalue)`` on those stringifies the ``bytes`` repr
    (``"b'...'"``) instead of the value, corrupting the config. See
    :func:`apply_lut3d_config_mapper`'s docstring.
    """
    if isinstance(cfgvalue, bytes):
        return cfgvalue.decode("utf-8")
    return str(cfgvalue)


def apply_lut3d_config_mapper(
    ti3_lines: list[bytes],
    path: str,
    is_preset: bool,
    is_3dlut_preset: bool,
    display_match: bool,
    instrument_match: bool,
    has_instrument_id: bool,
) -> bool:
    """Sync 3D LUT / measurement-report HDR metadata from a loaded TI3.

    Faithful port of ``load_cal_handler``'s ``config_mapper`` block -- the
    largest of the calibration/profile-file header bar's deferred pieces
    (see module docstring) -- plus the content-colorspace loop and 3D LUT TRC
    enumeration fallback that follow it in wx. Only does anything if the TI3
    has a ``BEGIN_DATA_FORMAT`` section (present in every file DisplayCAL
    itself writes).

    Fixes three latent bugs found while porting, also fixed at the source in
    ``display_cal.py``:

    * The block's own guard, ``"BEGIN_DATA_FORMAT" in ti3_lines``, compared a
      ``str`` literal against ``ti3_lines`` (``list[bytes]``, since
      :func:`parse_calibration_file` opens non-ICC files in binary mode) --
      always ``False``, so this entire ~200-line block (all 3D LUT metadata
      loading from a saved profile/cal file) was unreachable dead code.
    * ``3DLUT_GAMUT_MAPPING_MODE``'s value comparison (``cfgvalue == "G"``)
      compared ``bytes`` (:meth:`CGATS.queryv1` never auto-converts a
      single-letter value to numeric) against a ``str`` literal -- always
      ``False``, so ``3dlut.gamap.use_b2a`` was always set to ``1``
      regardless of the file's actual setting.
    * ``PATCH_SEQUENCE``'s ``cfgvalue.lower().replace("_rgb_", "_RGB_")``
      called ``bytes.replace`` with ``str`` arguments, raising ``TypeError``
      (crashing the whole load) whenever a file actually carried this
      keyword.

    Also generalizes the plain ``cfgvalue = str(cfgvalue)`` before every
    ``setcfg`` call into :func:`_decode_cfgvalue`: for any keyword
    :meth:`CGATS.queryv1` left as ``bytes``, that stringified the ``bytes``
    repr instead of the value.

    Args:
        ti3_lines: The parsed calibration file's raw lines.
        path: The file's own path (used to resolve relative profile paths).
        is_preset: Whether ``path`` is one of the bundled presets.
        is_3dlut_preset: Whether ``path`` is a bundled 3D LUT preset.
        display_match: Whether :func:`match_display_and_instrument` found a
            display match (always ``False`` for a non-ICC ``.cal`` file).
        instrument_match: Whether it found an instrument match.
        has_instrument_id: Whether the profile carried an embedded
            instrument ID at all (:attr:`DisplayInstrumentMatch.has_instrument_id`).

    Returns:
        ``simset``: ``True`` if ``SIMULATION_PROFILE`` was read from the file
        (only set for HDR 3D LUTs) -- pass to
        :func:`apply_lut3d_display_overrides`.
    """
    simset = False
    if b"BEGIN_DATA_FORMAT" not in ti3_lines:
        return simset

    cfgend = ti3_lines.index(b"BEGIN_DATA_FORMAT")
    cfgpart = CGATS(b"\n".join(ti3_lines[:cfgend]))
    lut3d_trc_set = False

    for keyword, cfgname in _LUT3D_CONFIG_MAPPER.items():
        cfgvalue = cfgpart.queryv1(keyword)
        if keyword in ("MIN_DISPLAY_UPDATE_DELAY_MS", "DISPLAY_SETTLE_TIME_MULT"):
            backup = getcfg(f"measure.override_{keyword.lower()}.backup", False)
            if (
                cfgvalue is not None
                and display_match
                and (instrument_match or not has_instrument_id)
            ):
                # Only set display update delay if a matching
                # display/instrument stored in profile meta tag or no
                # instrument ID (i.e. a preset)
                if backup is None:
                    setcfg(
                        f"measure.override_{keyword.lower()}.backup",
                        getcfg(f"measure.override_{keyword.lower()}"),
                    )
                    setcfg(
                        f"measure.{keyword.lower()}.backup",
                        getcfg(f"measure.{keyword.lower()}"),
                    )
                setcfg(f"measure.override_{keyword.lower()}", 1)
            elif backup is not None:
                setcfg(f"measure.override_{keyword.lower()}", backup)
                cfgvalue = getcfg(f"measure.{keyword.lower()}.backup")
                setcfg(f"measure.override_{keyword.lower()}.backup", None)
                setcfg(f"measure.{keyword.lower()}.backup", None)
        elif cfgvalue is not None:
            if keyword == "AUTO_OPTIMIZE" and cfgvalue:
                setcfg("testchart.file", "auto")
                if is_preset and not is_3dlut_preset and sys.platform == "darwin":
                    # Profile type forced to matrix due to OS X bugs with
                    # cLUT profiles. Set smallest testchart.
                    cfgvalue = 1
            elif keyword == "PATCH_SEQUENCE":
                cfgvalue = cfgvalue.lower().replace(b"_rgb_", b"_RGB_")
            elif keyword == "3DLUT_GAMMA":
                try:
                    cfgvalue = float(cfgvalue)
                except (TypeError, ValueError):
                    pass
                else:
                    if cfgvalue < 0:
                        gamma_type = "B"
                        cfgvalue = abs(cfgvalue)
                    else:
                        gamma_type = "b"
                    setcfg("3dlut.trc_gamma_type", gamma_type)
                    # Sync measurement report settings
                    setcfg("measurement_report.trc_gamma_type", gamma_type)
                    setcfg("measurement_report.apply_black_offset", 0)
                    setcfg("measurement_report.apply_trc", 1)
            elif keyword == "3DLUT_GAMUT_MAPPING_MODE":
                cfgvalue = 0 if cfgvalue == b"G" else 1
            elif keyword in (
                "FFP_INSERTION_INTERVAL",
                "FFP_INSERTION_DURATION",
                "FFP_INSERTION_LEVEL",
            ):
                setcfg("patterngenerator.ffp_insertion", 1)
            if keyword.startswith("3DLUT"):
                setcfg("3dlut.create", 1)
                setcfg("3dlut.tab.enable", 1)
                setcfg("3dlut.tab.enable.backup", 1)
        if cfgvalue is not None:
            cfgvalue = _decode_cfgvalue(cfgvalue)
            if cfgname.endswith("profile") and (
                not os.path.isabs(cfgvalue) or not os.path.isfile(cfgvalue)
            ):
                if os.path.basename(os.path.dirname(cfgvalue)) == "ref":
                    # Fall back to ref file if not absolute path or not found
                    cfgvalue = (
                        get_data_path("ref/" + os.path.basename(cfgvalue)) or cfgvalue
                    )
                elif not os.path.dirname(cfgvalue):
                    # Use profile dir
                    cfgvalue = os.path.join(os.path.dirname(path), cfgvalue)
            setcfg(cfgname, cfgvalue)
            if keyword == "SIMULATION_PROFILE":
                # Only HDR 3D LUTs will have this set
                simset = True
            # Sync measurement report settings
            if cfgname == "3dlut.input.profile":
                if not simset:
                    setcfg("measurement_report.simulation_profile", cfgvalue)
                setcfg("measurement_report.use_simulation_profile", 1)
                setcfg("measurement_report.use_simulation_profile_as_output", 1)
            elif cfgname in ("3dlut.trc_gamma", "3dlut.trc_output_offset"):
                cfgname = cfgname.replace("3dlut", "measurement_report")
                setcfg(cfgname, cfgvalue)
            elif cfgname == "3dlut.format":
                if cfgvalue == "madVR" and not simset:
                    setcfg("3dlut.enable", 1)
                if (cfgvalue == "madVR" and not simset) or cfgvalue == "eeColor":
                    setcfg("measurement_report.use_devlink_profile", 0)
            elif cfgname == "3dlut.trc":
                lut3d_trc_set = True

    # Content color space (currently only used for HDR)
    for color in ("white", "red", "green", "blue"):
        for coord in "xy":
            keyword = f"3DLUT_CONTENT_COLORSPACE_{color.upper()}_{coord.upper()}"
            cfgvalue = cfgpart.queryv1(keyword)
            if cfgvalue is None:
                continue
            cfgvalue = _decode_cfgvalue(cfgvalue)
            with contextlib.suppress(ValueError):
                cfgvalue = round(float(cfgvalue), 4)
            setcfg(f"3dlut.content.colorspace.{color}.{coord}", cfgvalue)

    # Make sure 3D LUT TRC enumeration matches parameters for older profiles
    # not containing 3DLUT_TRC
    if not lut3d_trc_set:
        if (
            getcfg("3dlut.trc_gamma_type") == "B"
            and getcfg("3dlut.trc_output_offset") == 0
            and getcfg("3dlut.trc_gamma") == 2.4
        ):
            setcfg("3dlut.trc", "bt1886")  # BT.1886
        elif (
            getcfg("3dlut.trc_gamma_type") == "b"
            and getcfg("3dlut.trc_output_offset") == 1
            and getcfg("3dlut.trc_gamma") == 2.2
        ):
            setcfg("3dlut.trc", "gamma2.2")  # Pure power gamma 2.2
        else:
            setcfg("3dlut.trc", "customgamma")  # Custom

    return simset


def apply_lut3d_display_overrides(simset: bool) -> None:
    """Apply the Resolve/Prisma/madVR 3D-LUT-enable overrides after a file load.

    Faithful port of the tail of ``load_cal_handler`` that runs right after
    the ``config_mapper`` block (see :func:`apply_lut3d_config_mapper`):
    forces ``3dlut.enable`` off for Resolve (uses its own devlink profile
    instead), on for Prisma, and off again for madVR when ``simset`` (an HDR
    3D LUT was loaded), since madVR currently has no other way to verify an
    HDR 3D LUT.
    """
    if get_display_name() == "Resolve":
        setcfg("3dlut.enable", 0)
        setcfg("measurement_report.use_devlink_profile", 1)
    elif get_display_name(None, True) == "Prisma":
        setcfg("3dlut.enable", 1)
        setcfg("measurement_report.use_devlink_profile", 0)
    if getcfg("3dlut.format") == "madVR" and simset:
        # Currently, it is not possible to verify HDR 3D LUTs through madVR
        # in another way
        setcfg("3dlut.enable", 0)
        setcfg("measurement_report.use_devlink_profile", 1)


@dataclass
class LegacyCalResult:
    """Result of :func:`parse_legacy_cal`."""

    #: True if the file's ``DEVICE_CLASS`` isn't ``DISPLAY`` (not a display
    #: calibration file); the caller should show an error and stop.
    invalid: bool = False
    #: Human-readable labels of the settings that were found and applied,
    #: for a "settings loaded: ..." style message. Empty if the file had none
    #: of the recognized legacy keywords.
    settings: list[str] = field(default_factory=list)


def parse_legacy_cal(ti3_lines: list[bytes], worker: Worker) -> LegacyCalResult:
    """Parse a pre-``ARGYLL_DISPCAL_ARGS`` ``.cal`` file (old Argyll releases).

    Faithful port of the legacy branch at the tail of ``load_cal_handler``,
    minus the wx ``InfoDialog`` calls (the caller shows those based on
    ``LegacyCalResult.invalid``/``.settings``). Applies recognized settings
    via ``setcfg`` and populates ``worker.options_dispcal`` directly, exactly
    like the wx original.

    This also fixes a latent bug found while porting: the wx original
    compared ``ti3_lines`` (``bytes``, since ``parse_calibration_file`` opens
    non-ICC files in binary mode) against ``str`` keyword/value literals
    (``line[0] == "DEVICE_CLASS"``, ``value == "DISPLAY"``, ...) and read
    ``value.lower()[0]`` (an ``int`` on ``bytes``, not a one-character
    string) -- never true/always wrong in Python 3, so this whole branch was
    dead code, except for ``BLACK_POINT_CORRECTION`` where
    ``stripzeros(value) >= 0`` compared a ``str`` to an ``int`` and raised
    ``TypeError``. Fixed at the source in ``display_cal.py`` too, so the
    still-shipping wx path gets a working (if rarely-hit) legacy-``.cal``
    loader instead of dead/crashing code.
    """
    result = LegacyCalResult()
    worker.options_dispcal = []
    black_point_correction = False
    for raw_line in ti3_lines:
        line = raw_line.strip().split(b" ", 1)
        if len(line) <= 1:
            continue
        key = line[0]
        value = line[1][1:-1].decode("utf-8", "replace")  # strip quotes
        if key == b"DEVICE_CLASS":
            if value != "DISPLAY":
                result.invalid = True
                return result
        elif key == b"DEVICE_TYPE":
            measurement_mode = value.lower()[0:1]
            if measurement_mode in ("c", "l"):
                setcfg("measurement_mode", measurement_mode)
                worker.options_dispcal.append("-y" + measurement_mode)
        elif key == b"NATIVE_TARGET_WHITE":
            setcfg("whitepoint.colortemp", None)
            setcfg("whitepoint.x", None)
            setcfg("whitepoint.y", None)
            setcfg("3dlut.whitepoint.x", None)
            setcfg("3dlut.whitepoint.y", None)
            result.settings.append(lang.getstr("whitepoint"))
        elif key == b"TARGET_WHITE_XYZ":
            xyz = value.split()
            try:
                xyz = [float(component) / 100 for component in xyz]
            except ValueError:
                continue
            x, y, y_lum = XYZ2xyY(xyz[0], xyz[1], xyz[2])
            if lang.getstr("whitepoint") not in result.settings:
                setcfg("whitepoint.colortemp", None)
                setcfg("whitepoint.x", round(x, 4))
                setcfg("whitepoint.y", round(y, 4))
                setcfg("3dlut.whitepoint.x", round(x, 4))
                setcfg("3dlut.whitepoint.y", round(y, 4))
                worker.options_dispcal.append(
                    "-w{},{}".format(getcfg("whitepoint.x"), getcfg("whitepoint.y"))
                )
                result.settings.append(lang.getstr("whitepoint"))
            setcfg("calibration.luminance", stripzeros(round(y_lum * 100, 3)))
            worker.options_dispcal.append(
                "-b{}".format(getcfg("calibration.luminance"))
            )
            result.settings.append(lang.getstr("calibration.luminance"))
        elif key == b"TARGET_GAMMA":
            setcfg("trc", None)
            if value in ("L_STAR", "REC709", "SMPTE240M", "sRGB"):
                setcfg("trc.type", "g")
            if value == "L_STAR":
                setcfg("trc", "l")
            elif value == "REC709":
                setcfg("trc", "709")
            elif value == "SMPTE240M":
                setcfg("trc", "240")
            elif value == "sRGB":
                setcfg("trc", "s")
            else:
                try:
                    gamma = stripzeros(value)
                    if float(gamma) < 0:
                        setcfg("trc.type", "G")
                        gamma = abs(float(gamma))
                    else:
                        setcfg("trc.type", "g")
                    setcfg("trc", gamma)
                except ValueError:
                    continue
            worker.options_dispcal.append("-" + getcfg("trc.type") + str(getcfg("trc")))
            result.settings.append(lang.getstr("trc"))
        elif key == b"DEGREE_OF_BLACK_OUTPUT_OFFSET":
            setcfg("calibration.black_output_offset", stripzeros(value))
            worker.options_dispcal.append(
                "-f{}".format(getcfg("calibration.black_output_offset"))
            )
            result.settings.append(lang.getstr("calibration.black_output_offset"))
        elif key == b"BLACK_POINT_CORRECTION":
            if float(stripzeros(value)) >= 0:
                black_point_correction = True
                setcfg("calibration.black_point_correction", stripzeros(value))
                worker.options_dispcal.append(
                    "-k{}".format(getcfg("calibration.black_point_correction"))
                )
            result.settings.append(lang.getstr("calibration.black_point_correction"))
        elif key == b"TARGET_BLACK_BRIGHTNESS":
            setcfg("calibration.black_luminance", stripzeros(value))
            worker.options_dispcal.append(
                "-B{}".format(getcfg("calibration.black_luminance"))
            )
            result.settings.append(lang.getstr("calibration.black_luminance"))
        elif key == b"QUALITY":
            setcfg("calibration.quality", value.lower()[0:1])
            worker.options_dispcal.append("-q{}".format(getcfg("calibration.quality")))
            result.settings.append(lang.getstr("calibration.quality"))

    if not black_point_correction:
        setcfg("calibration.black_point_correction.auto", 1)

    return result


#: Keywords :func:`parse_legacy_cal` turns into settings.
_LEGACY_CAL_SETTING_KEYWORDS = (
    b"NATIVE_TARGET_WHITE",
    b"TARGET_WHITE_XYZ",
    b"TARGET_GAMMA",
    b"DEGREE_OF_BLACK_OUTPUT_OFFSET",
    b"BLACK_POINT_CORRECTION",
    b"TARGET_BLACK_BRIGHTNESS",
    b"QUALITY",
)


def find_settings_profile_for_cal(path: str, ti3_lines: list[bytes]) -> str | None:
    """Return the session profile to load settings from instead of a ``.cal``.

    A profile-only session (calibration skipped) stores the video LUT that
    was active while measuring as a plain ``dispwin -s`` ``.cal`` file, which
    has neither an ``ARGYLL_DISPCAL_ARGS`` section nor any of the keywords
    :func:`parse_legacy_cal` understands, so loading it can only ever report
    "no settings". The session's settings live in the profile next to it.

    Args:
        path: Path to the ``.cal`` file.
        ti3_lines: The file's stripped lines, as returned by
            :func:`parse_calibration_file`.

    Returns:
        The path of a same-named ``.icc``/``.icm`` profile next to ``path``,
        or ``None`` if the ``.cal`` file has settings of its own or there is
        no such profile.
    """
    if any(
        line.split(b" ", 1)[0] in _LEGACY_CAL_SETTING_KEYWORDS for line in ti3_lines
    ):
        return None
    stem = os.path.splitext(path)[0]
    for ext in (PROFILE_EXT, *ICCPROFILE_FILE_EXTENSIONS):
        profile_path = stem + ext
        if os.path.isfile(profile_path):
            return profile_path
    return None


def related_files_for(cal: str, dircontents: list[str]) -> dict[str, bool]:
    """Return the calibration dir entries related to ``cal``, all pre-checked.

    Faithful port of ``initialize_related_files``.
    """
    related_files: dict[str, bool] = {}
    for entry in dircontents:
        fn, ext = os.path.splitext(entry)
        if ext.lower() in (".app", ".command", ".sh", ".bat"):
            fn, ext = os.path.splitext(fn)
        if (
            fn.startswith(os.path.splitext(os.path.basename(cal))[0])
            or ext.lower() in (".ccss", ".ccmx")
            or entry.lower() in ("0_16.ti1", "0_16.ti3", "0_16.log")
        ):
            related_files[entry] = True
    return related_files


def delete_related_files(
    cal: str, related_files: dict[str, bool]
) -> tuple[list[str], list[str]]:
    """Send the checked related files to the trash.

    Faithful port of ``delete_related_files_and_cleanup``'s send2trash half
    (minus the wx error dialogs -- callers inspect ``orphan_related_files``,
    the entries that survived, to report failures themselves).

    Returns:
        ``(delete_related_files, orphan_related_files)``: the files that were
        selected for deletion, and the subset that could not be removed.
    """
    delete_files = [
        os.path.join(os.path.dirname(cal), related_file)
        for related_file, checked in related_files.items()
        if checked
    ]
    if not delete_files:
        return delete_files, []
    send2trash(delete_files)
    orphan_files = [path for path in delete_files if os.path.exists(path)]
    return delete_files, orphan_files


def session_archive_filenames(cal: str) -> tuple[list[str], list[str], str]:
    """Return ``(filenames, dirfilenames, dirname)`` for a session archive of ``cal``.

    Faithful port of the file-selection half of ``create_session_archive_handler``.
    """
    dirname = os.path.dirname(cal)
    path_name = os.path.splitext(cal)[0]
    dirfilenames = sorted(os.path.join(dirname, name) for name in os.listdir(dirname))
    filenames = sorted(
        set(
            safe_glob(path_name + "*")
            + safe_glob(os.path.join(dirname, "*.ccmx"))
            + safe_glob(os.path.join(dirname, "*.ccss"))
            + safe_glob(os.path.join(dirname, "0_16.ti1"))
            + safe_glob(os.path.join(dirname, "0_16.ti3"))
            + safe_glob(os.path.join(dirname, "0_16.log"))
        )
    )
    return filenames, dirfilenames, dirname


def session_archive_has_3dlut_files(
    filenames: list[str], lut3d_formats: list[str]
) -> tuple[bool, list[str]]:
    """Return ``(has_3dlut, lut3d_ext)`` for the given archive file list.

    ``lut3d_formats`` should be ``config.VALID_VALUES["3dlut.format"]``.
    """
    lut3d_ext = [
        "." + strtr(lut3d_format, {"eeColor": "txt", "madVR": "3dlut"})
        for lut3d_format in lut3d_formats
        if lut3d_format not in ("icc", "icm", "png")
    ]
    has_3dlut = any(
        os.path.splitext(filename)[1].lower() in lut3d_ext for filename in filenames
    )
    return has_3dlut, lut3d_ext


@dataclass
class SessionArchiveRequest:
    """Bundles :func:`create_session_archive`'s arguments for one archive run."""

    dirname: str
    dirfilenames: list[str]
    filenames: list[str]
    archive_path: str
    exclude_ext: list[str] | None = None
    sevenzip: str | None = None


def create_session_archive(
    request: SessionArchiveRequest, exec_cmd: Callable[..., bool | Exception]
) -> bool | Exception:
    """Create the session archive described by ``request``.

    Faithful port of ``create_session_archive_producer``. ``exec_cmd`` runs
    the 7-Zip command line (``worker.exec_cmd`` in practice); the ZIP/TAR path
    doesn't need it.
    """
    dirname = request.dirname
    dirfilenames = request.dirfilenames
    filenames = list(request.filenames)
    archive_path = request.archive_path
    exclude_ext = request.exclude_ext
    sevenzip = request.sevenzip

    if sevenzip:
        if filenames == dirfilenames:
            filenames = [dirname]
        if os.path.isfile(archive_path):
            os.remove(archive_path)
        args = ["a", "-y"]
        if exclude_ext:
            args.extend(f"-xr!*{ext}" for ext in exclude_ext)
        return exec_cmd(
            sevenzip, [*args, archive_path, *filenames], capture_output=True
        )

    dirbasename = ""
    if filenames == dirfilenames:
        dirbasename = os.path.basename(dirname)
    try:
        if archive_path.lower().endswith((".tgz", ".tar.gz")):
            archive = TarFileProper.open(archive_path, "w:gz", encoding="UTF-8")
            writefile = archive.add
        else:
            archive = zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED)
            writefile = archive.write
        with archive:
            for filename in filenames:
                if exclude_ext and os.path.splitext(filename)[1].lower() in exclude_ext:
                    continue
                writefile(
                    filename, os.path.join(dirbasename, os.path.basename(filename))
                )
    except Exception as exception:  # noqa: BLE001 (reported to caller, not logged here)
        return exception
    return True


@dataclass
class SessionArchiveImportRequest:
    """Bundles :func:`import_session_archive`'s arguments for one import run."""

    path: str
    basename: str
    ext: str
    tempdir: str
    sevenzip: str | None = None


def import_session_archive(
    request: SessionArchiveImportRequest, exec_cmd: Callable[..., bool | Exception]
) -> str | Exception:
    """Extract a compressed session archive into ``request.tempdir``.

    Faithful port of ``import_session_archive_producer``. ``exec_cmd`` runs
    the 7-Zip extraction command line (``worker.exec_cmd`` in practice); the
    ZIP/TAR path doesn't need it.

    Returns:
        The would-be storage path (``<profile.save_path>/<basename>/<basename><ext>``)
        the caller should pass as ``dst_path`` to ``Worker.wrapup()`` to move
        the extracted files there, or an ``Exception``/:class:`Error` if the
        archive isn't a session archive or extraction failed.
    """
    path = request.path
    basename = request.basename
    ext = request.ext
    temp = request.tempdir

    if ext.lower() == ".7z":
        if not request.sevenzip:
            return Error(lang.getstr("file.missing", f"7z{EXE_EXT}"))
        result = exec_cmd(
            request.sevenzip,
            ["e", "-y", path],
            capture_output=True,
            log_output=False,
            skip_scripts=True,
            working_dir=temp,
        )
        if not result or isinstance(result, Exception):
            return result
        found_ext = None
        for ext_ in (".icc", ".icm", ".cal"):
            if os.path.isfile(os.path.join(temp, f"{basename}{ext_}")):
                found_ext = ext_
                break
        if not found_ext:
            return Error(
                lang.getstr("error.not_a_session_archive", os.path.basename(path))
            )
        nested = os.path.join(temp, basename)
        if os.path.isdir(nested):
            shutil.rmtree(nested)
    else:
        if path.lower().endswith((".tgz", ".tar.gz")):
            archive = TarFileProper.open(path, "r", encoding="UTF-8")
            getinfo = archive.getmember
            getnames = archive.getnames
        else:
            archive = zipfile.ZipFile(path, "r")
            getinfo = archive.getinfo
            getnames = archive.namelist
        try:
            with archive:
                info = None
                for ext_ in (".icc", ".icm", ".cal"):
                    for name in (f"{basename}/{basename}{ext_}", f"{basename}{ext_}"):
                        if isinstance(archive, zipfile.ZipFile):
                            names = (name, safe_str(name, "cp437"))
                        else:
                            names = (safe_str(name, "UTF-8"),)
                        for name_variant in names:
                            try:
                                info = getinfo(name_variant)
                            except KeyError:
                                continue
                            break
                        if info:
                            break
                    if info:
                        break
                if not info:
                    return Error(
                        lang.getstr(
                            "error.not_a_session_archive", os.path.basename(path)
                        )
                    )
                found_ext = ext_
                for name in getnames():
                    if not isinstance(archive, zipfile.ZipFile):
                        archive.extract(name, temp, False)
                        continue
                    outname = str(name)
                    with open(
                        os.path.join(temp, os.path.basename(outname)), "wb"
                    ) as outfile:
                        outfile.write(archive.read(name))
        except Exception as exception:  # noqa: BLE001 (reported to caller, not logged here)
            return exception
    # Use the extracted file's own extension (.cal/.icc/.icm), not the
    # archive's (.7z/.tgz/.zip) -- see the module's parent bug-fix note in
    # ``display_cal.py``'s ``import_session_archive_producer``.
    return os.path.join(getcfg("profile.save_path"), basename, basename + found_ext)


__all__ = [
    "COMPRESSED_FILE_EXTENSIONS",
    "ICCPROFILE_FILE_EXTENSIONS",
    "CalibrationFileError",
    "CalibrationSelection",
    "DisplayInstrumentMatch",
    "LegacyCalResult",
    "SessionArchiveImportRequest",
    "SessionArchiveRequest",
    "apply_calibration_options",
    "apply_icc_profile_load_defaults",
    "apply_lut3d_config_mapper",
    "apply_lut3d_display_overrides",
    "apply_profile_b2a_flags_from_ti3",
    "build_recent_calibrations",
    "create_session_archive",
    "delete_related_files",
    "get_unpreseted_recent_calibrations",
    "import_session_archive",
    "index_fallback_ignorecase",
    "match_display_and_instrument",
    "parse_calibration_file",
    "parse_legacy_cal",
    "related_files_for",
    "resolve_calibration_selection",
    "restore_defaults",
    "session_archive_filenames",
    "session_archive_has_3dlut_files",
]
