"""Toolkit-neutral helpers for the measurement report feature.

These are the pure pieces lifted out of ``MainFrame.measurement_report_handler``,
``MainFrame.measurement_report`` and ``MainFrame.measurement_report_consumer``
(``display_cal.py``): chart/profile resolution, the worker-driven TI1/TI3
staging, and the big ``placeholders2data`` assembly, none of which touch wx (or
Qt) widgets directly -- they take a :class:`~DisplayCAL.worker.Worker` and plain
values, matching the ``preflight_checks.py`` precedent of treating ``Worker`` as
an already-toolkit-neutral collaborator. A plain ``DisplayCAL`` module so
importing it never pulls in Qt, matching ``main_settings.py``. The wx frame
delegates to these; the Qt main window (``ui/main_window.py``) reuses them for
its report layer.

The genuinely window-shaped parts (file-save dialog, overwrite confirm, the
progress dialog around the worker run) stay in their respective UI layers.

Three edge cases originally deferred here are now covered too, each split the
same way (pure logic here, dialog/worker-run owned by the Qt window):

* The self-check report (holding Alt while clicking Measure looks up the chart
  through the display profile's own B2A table instead of measuring):
  :func:`perform_self_check_lookup` ports ``measurement_report_handler``'s
  ``self_check_report`` branch.
* ``check_profile_b2a_hires``'s low-res-B2A refusal: :func:`profile_b2a_is_lowres`
  is the pure predicate; the Qt window owns the regenerate-tables offer and the
  ``worker.update_profile_B2A`` run.
* ``measurement_file_check_confirm``'s interactive suspicious-patch review
  grid: :func:`resolve_sanity_check` / :func:`recompute_sanity_row` /
  :func:`apply_sanity_check_result` / :func:`resync_report_ti3_removals` are
  the pure pieces; the Qt window owns the review-grid dialog.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from io import BytesIO
from time import strftime
from typing import TYPE_CHECKING

from DisplayCAL import colormath, config, report
from DisplayCAL import localization as lang
from DisplayCAL.argyll import get_argyll_util, make_argyll_compatible_path
from DisplayCAL.argyll_cgats import extract_cal_from_profile, verify_ti1_rgb_xyz
from DisplayCAL.cgats import (
    CGATS,
    CGATSError,
    CGATSInvalidError,
    CGATSInvalidOperationError,
    CGATSKeyError,
    CGATSTypeError,
    CGATSValueError,
)
from DisplayCAL.colormath import XYZ2Lab
from DisplayCAL.config import DEFAULTS, get_current_profile, get_data_path, getcfg
from DisplayCAL.icc_profile import (
    ChromaticAdaptionTag,
    ICCProfile,
    ICCProfileInvalidError,
    LUT16Type,
    VideoCardGammaType,
    XYZType,
)
from DisplayCAL.util_decimal import float2dec
from DisplayCAL.util_os import launch_file
from DisplayCAL.util_str import ellipsis_, make_filename_safe
from DisplayCAL.worker import (
    _applycal_bug_workaround,
    check_ti3,
    check_ti3_criteria1,
    check_ti3_criteria2,
    get_arg,
    get_cfg_option_from_args,
    get_options_from_profile,
    parse_argument_string,
)

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker

# Characters Argyll / the filesystem cannot carry in a report filename, matching
# the sanitisation the wx handler applies to the display name.
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:;*?"<>|]+')

#: The white-patch device-value query used throughout the report pipeline.
_WHITE_RGB = {"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}


class ReportSetupError(Exception):
    """Raised when the report chart/profile resolution cannot proceed."""


@dataclass
class ReportContext:
    """Everything :func:`resolve_report_context` resolved for one report run.

    Mirrors the local variables ``measurement_report_handler`` builds up before
    calling ``setup_measurement`` (minus the self-check-report branch).
    """

    chart: CGATS
    ti1: CGATS
    ti3_ref: CGATS
    gray: list | None
    profile: ICCProfile
    oprof: ICCProfile
    sim_profile: ICCProfile | None
    devlink: ICCProfile | None
    sim_ti3: CGATS | None
    intent: str
    sim_intent: str | None
    apply_trc: bool
    colormanaged: bool
    use_sim: bool
    use_sim_as_output: bool
    report_type: str
    default_file: str


def default_report_filename(
    report_type: str,
    version_string: str,
    display_name: str,
    timestamp: str | None = None,
) -> str:
    """Build the default ``.html`` filename offered in the save dialog.

    Ports the ``default_file`` construction in ``measurement_report_handler``.

    Args:
        report_type: ``"Measurement"`` or ``"Self Check"``.
        version_string: The application version string (``VERSION_STRING``).
        display_name: The display name, already stripped of the localized
            ``display.primary`` suffix by the caller.
        timestamp: ``"%Y-%m-%d %H-%M"`` timestamp; defaults to now.

    Returns:
        The suggested filename, including the ``.html`` extension.
    """
    if timestamp is None:
        timestamp = strftime("%Y-%m-%d %H-%M")
    safe_display = _UNSAFE_FILENAME_CHARS.sub("_", display_name)
    return f"{report_type} Report {version_string} - {safe_display} - {timestamp}.html"


def resolve_quantization_bits(args: list) -> int | None:
    """Determine the reference-value quantization bit depth from dispread args.

    Ports the ``qbits`` derivation in ``measurement_report_consumer``: an
    explicit ``-Z <bits>`` (or ``-Zbits``) wins, otherwise video encoding
    (``-E``) implies ArgyllCMS' 8-bit default.

    Args:
        args: The dispread argument list (after
            ``worker.add_measurement_features``).

    Returns:
        The bit depth, or ``None`` if no quantization applies.
    """
    quantize_arg = get_arg("-Z", args)
    if quantize_arg:
        try:
            if quantize_arg[1] == "-Z":
                # Next arg is quantization bit depth
                return int(args[quantize_arg[0] + 1])
            # Quantization bit depth is part of arg string
            return int(quantize_arg[1][2:])
        except (IndexError, TypeError, ValueError):
            return None
    elif "-E" in args:
        return 8  # ArgyllCMS default for video encoding (see dispread doc)
    return None


def quantize_gray(gray: list, qbits: int) -> list:
    """Quantize grayscale RGB reference values to ``qbits`` bits.

    Ports the ``gray`` rescaling in ``measurement_report_consumer``.

    Args:
        gray: A list of ``[R, G, B]`` triples in 0-100.
        qbits: The quantization bit depth.

    Returns:
        A new list of quantized ``[R, G, B]`` triples.
    """
    qmax = 2**qbits - 1.0
    return [
        [round(round(v / 100.0 * qmax) / qmax * 100.0, 4) for v in rgb] for rgb in gray
    ]


def report_trc_label(
    trc_gamma: float, trc_gamma_type: str, trc_output_offset: float
) -> str:
    """Return the report's TRC label for the given TRC config values.

    Ports the ``trc`` derivation in ``measurement_report_consumer``: the default
    BT.1886 target (gamma 2.4, type ``B``, no output offset) is labelled
    ``"BT.1886"``, anything else is unlabelled.

    Args:
        trc_gamma: ``measurement_report.trc_gamma``.
        trc_gamma_type: ``measurement_report.trc_gamma_type``.
        trc_output_offset: ``measurement_report.trc_output_offset``.

    Returns:
        ``"BT.1886"`` for the default target, otherwise ``""``.
    """
    if trc_gamma != 2.4 or trc_gamma_type != "B" or trc_output_offset:
        return ""
    return "BT.1886"


def profile_b2a_is_lowres(profile: ICCProfile) -> bool:
    """Whether ``profile`` has a suspiciously low-resolution Argyll B2A table.

    Pure port of ``check_profile_b2a_hires``'s predicate: a colorimetric
    PCS-to-device table with less than 17 grid steps, built by Argyll itself,
    is too coarse for reliable use. The caller (the Qt window) is expected to
    refuse to proceed with the report/install and instead offer to regenerate
    the table via ``worker.update_profile_B2A``.

    Args:
        profile: The profile to check.

    Returns:
        ``True`` if the profile's ``B2A0`` table is a low-resolution table
        Argyll generated.
    """
    return (
        "B2A0" in profile.tags
        and isinstance(profile.tags.B2A0, LUT16Type)
        and profile.tags.B2A0.clut_grid_steps < 17
        and profile.creator == b"argl"
    )


def resolve_report_context(
    worker: Worker, version_string: str, display_name: str
) -> ReportContext:
    """Resolve the chart/profile/simulation setup for a measurement report.

    Ports ``measurement_report_handler``'s body up to (not including) the
    save-path file dialog: loads the configured chart, resolves the
    simulation/devlink/output profiles, computes the optional BT.1886-style
    TRC target, and runs the reference-value chart lookups. The self-check
    report branch is not reproduced (see module docstring).

    Args:
        worker: The worker whose ``chart_lookup`` / ``xicclu`` do the actual
            colour-managed lookups.
        version_string: ``VERSION_STRING``, used in the default filename.
        display_name: The target display's label, already stripped of the
            localized ``display.primary`` suffix by the caller.

    Returns:
        The resolved :class:`ReportContext`.

    Raises:
        ReportSetupError: The chart or a configured profile could not be
            loaded, or none of the chart lookups produced usable data.
    """
    try:
        chart = CGATS(getcfg("measurement_report.chart"), True)
    except (OSError, CGATSError) as exception:
        raise ReportSetupError(str(exception)) from exception

    chart = worker.ensure_patch_sequence(chart, False)
    fields = getcfg("measurement_report.chart.fields")

    paths = []
    use_sim = bool(getcfg("measurement_report.use_simulation_profile"))
    use_sim_as_output = bool(
        getcfg("measurement_report.use_simulation_profile_as_output")
    )
    use_devlink = bool(getcfg("measurement_report.use_devlink_profile"))
    if use_sim:
        if use_sim_as_output and use_devlink:
            devlink_path = getcfg("measurement_report.devlink_profile")
            if devlink_path:
                paths.append(devlink_path)
            else:
                use_devlink = False
        paths.append(getcfg("measurement_report.simulation_profile"))

    sim_profile = None
    devlink = None
    oprof = profile = get_current_profile(True)
    for i, profilepath in enumerate(paths):
        try:
            profile = ICCProfile(profilepath)
        except (OSError, ICCProfileInvalidError) as exception:
            if isinstance(exception, ICCProfileInvalidError):
                message = f"{lang.getstr('profile.invalid')}\n{profilepath}"
            else:
                message = str(exception)
            raise ReportSetupError(message) from exception
        if profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
            raise ReportSetupError(
                "\n".join(
                    [lang.getstr("profile.iccv4.unsupported"), profile.getDescription()]
                )
            )
        if i in (0, 1) and use_sim:
            if use_sim_as_output and profile.colorSpace == b"RGB":
                if i == 0 and use_devlink:
                    devlink = profile
            else:
                if profile.colorSpace != b"RGB":
                    use_sim_as_output = False
                    devlink = None
                sim_profile = profile
                profile = oprof
    if not profile and not oprof:
        raise ReportSetupError(
            lang.getstr(
                "display_profile.not_detected", config.get_display_name(None, True)
            )
        )

    colormanaged = (
        use_sim
        and use_sim_as_output
        and not sim_profile
        and config.get_display_name(None, True) in ("madVR", "Prisma")
        and bool(getcfg("3dlut.enable"))
    )

    mprof = (sim_profile if sim_profile else profile) if use_sim else None
    apply_map = (
        use_sim
        and mprof.colorSpace == b"RGB"
        and isinstance(mprof.tags.get("rXYZ"), XYZType)
        and isinstance(mprof.tags.get("gXYZ"), XYZType)
        and isinstance(mprof.tags.get("bXYZ"), XYZType)
        and not isinstance(mprof.tags.get("A2B0"), LUT16Type)
    )
    apply_off = apply_map and bool(getcfg("measurement_report.apply_black_offset"))
    apply_trc = apply_map and bool(getcfg("measurement_report.apply_trc"))
    bt1886 = None
    if apply_trc or apply_off:
        try:
            odata = worker.xicclu(oprof, (0, 0, 0), pcs="x")
            if len(odata) != 1 or len(odata[0]) != 3:
                raise ValueError(f"Blackpoint is invalid: {odata}")
        except Exception as exception:
            raise ReportSetupError(str(exception)) from exception
        if odata[0][1]:
            xyz_bp = odata[0]
        else:
            xyz_bp = oprof.get_chardata_bkpt()
            if xyz_bp:
                xyz_bp = [v * xyz_bp[1] for v in list(oprof.tags.wtpt.pcs.values())]
            else:
                xyz_bp = [0, 0, 0]
        if apply_trc:
            gamma = getcfg("measurement_report.trc_gamma")
            gamma_type = getcfg("measurement_report.trc_gamma_type")
            outoffset = getcfg("measurement_report.trc_output_offset")
            if gamma_type == "b":
                gamma = colormath.xicc_tech_gamma(gamma, xyz_bp[1], outoffset)
        else:
            outoffset = 1.0
            gamma = 0.0
            for channel in "rgb":
                gamma += mprof.tags[f"{channel}TRC"].get_gamma()
            gamma /= 3.0
        r_xyz = list(mprof.tags.rXYZ.values())
        g_xyz = list(mprof.tags.gXYZ.values())
        b_xyz = list(mprof.tags.bXYZ.values())
        mtx = colormath.Matrix3x3(
            [
                [r_xyz[0], g_xyz[0], b_xyz[0]],
                [r_xyz[1], g_xyz[1], b_xyz[1]],
                [r_xyz[2], g_xyz[2], b_xyz[2]],
            ]
        )
        bt1886 = colormath.BT1886(mtx, xyz_bp, outoffset, gamma, apply_trc)
        if apply_trc:
            for channel in ("r", "g", "b"):
                if channel + "TRC" in mprof.tags:
                    mprof.tags[channel + "TRC"].set_trc(-709)
            mprof.filename = None

    sim_gray = None
    if sim_profile:
        sim_intent = "a" if getcfg("measurement_report.whitepoint.simulate") else "r"
        _void, sim_ti3, sim_gray = worker.chart_lookup(
            chart,
            sim_profile,
            check_missing_fields=True,
            intent=sim_intent,
            bt1886=bt1886,
        )
        if not sim_ti3:
            raise ReportSetupError(
                "Chart lookup produced no usable data for the measurement report."
            )
        intent = (
            "r"
            if sim_intent == "r"
            or getcfg("measurement_report.whitepoint.simulate.relative")
            else "a"
        )
        bt1886 = None
    else:
        sim_ti3 = None
        sim_intent = None
        intent = "r"
        if fields in ("LAB", "XYZ"):
            if getcfg("measurement_report.whitepoint.simulate"):
                sim_intent = "a"
                if not getcfg("measurement_report.whitepoint.simulate.relative"):
                    intent = "a"
            else:
                chart.fix_device_values_scaling()
                chart.adapt(cat=profile.guess_cat() or "Bradford")

    ti1, ti3_ref, gray = worker.chart_lookup(
        sim_ti3 or chart,
        profile,
        bool(sim_ti3) or fields in ("LAB", "XYZ"),
        fields=None if sim_ti3 else fields,
        intent=intent,
        bt1886=bt1886,
    )
    if not ti3_ref:
        raise ReportSetupError(
            "Chart lookup produced no usable data for the measurement report."
        )
    if not gray and sim_gray:
        gray = sim_gray

    if devlink:
        _void, ti1, _void2 = worker.chart_lookup(
            ti1,
            devlink,
            check_missing_fields=True,
            white_patches=1,
            white_patches_total=False,
        )
        if not ti1:
            raise ReportSetupError(
                "Chart lookup produced no usable data for the measurement report."
            )

    report_type = "Measurement"
    return ReportContext(
        chart=chart,
        ti1=ti1,
        ti3_ref=ti3_ref,
        gray=gray,
        profile=profile,
        oprof=oprof,
        sim_profile=sim_profile,
        devlink=devlink,
        sim_ti3=sim_ti3,
        intent=intent,
        sim_intent=sim_intent,
        apply_trc=apply_trc,
        colormanaged=colormanaged,
        use_sim=use_sim,
        use_sim_as_output=use_sim_as_output,
        report_type=report_type,
        default_file=default_report_filename(report_type, version_string, display_name),
    )


def devlink_applies_calibration(devlink: ICCProfile | None) -> bool:
    """Return whether a device link already has the calibration baked in.

    A device link built with "Apply calibration (vcgt)" enabled was created
    with ``collink -a``, which DisplayCAL records in the link's ``meta`` tag.
    Links without that metadata fall back to the current
    ``3dlut.output.profile.apply_cal`` setting.

    Args:
        devlink: The device-link profile, if any.

    Returns:
        True if ``devlink`` is given and was built with ``collink -a``.
    """
    return bool(devlink) and "-a" in parse_argument_string(
        devlink.tags.get("meta", {})
        .get("collink.args", {})
        .get("value", "-a" if getcfg("3dlut.output.profile.apply_cal") else "")
    )


def select_calibration_profile(
    oprof: ICCProfile,
    profile: ICCProfile,
    use_sim_as_output: bool,
    devlink: ICCProfile | None,
) -> ICCProfile:
    """Pick the profile whose calibration is applied while measuring.

    The display profile's calibration is kept unless the simulation profile
    stands in as the display profile, in which case it is only kept when a
    device link that expects the calibration to be applied downstream (i.e.
    built without ``collink -a``) is used.

    Args:
        oprof: The original (display) profile.
        profile: The profile used for the lookup (the simulation profile when
            it stands in as the display profile).
        use_sim_as_output: ``measurement_report.use_simulation_profile_as_output``.
        devlink: The device-link profile, if any.

    Returns:
        ``oprof`` or ``profile``.
    """
    if not use_sim_as_output or (devlink and not devlink_applies_calibration(devlink)):
        return oprof
    return profile


def report_calibration_label(
    oprof: ICCProfile,
    profile: ICCProfile,
    use_sim_as_output: bool,
    devlink: ICCProfile | None,
    self_check_report: bool = False,
) -> str:
    """Describe the calibration that was active during the measurement.

    Args:
        oprof: The original (display) profile.
        profile: The profile used for the lookup.
        use_sim_as_output: ``measurement_report.use_simulation_profile_as_output``.
        devlink: The device-link profile, if any.
        self_check_report: Whether this is a self-check report (no
            measurement took place).

    Returns:
        The ``${CALIBRATION}`` value for the report.
    """
    if self_check_report:
        return "N/A"
    calprof = select_calibration_profile(oprof, profile, use_sim_as_output, devlink)
    if extract_cal_from_profile(calprof, None, False):
        source = "display" if calprof is oprof else "simulation"
        return f"Yes ({source} profile)"
    if use_sim_as_output and devlink_applies_calibration(devlink):
        return "No (already applied by the devicelink profile)"
    return "No (linear)"


def stage_measurement_files(
    worker: Worker,
    save_path: str,
    ti1: CGATS,
    oprof: ICCProfile,
    profile: ICCProfile,
    use_sim_as_output: bool,
    devlink: ICCProfile | None,
) -> tuple[str, str]:
    """Write the TI1 / profile / calibration files a measurement run needs.

    Ports the temp-dir setup in ``measurement_report`` (the part before
    ``worker.start``): creates the temp dir, writes ``ti1`` and ``profile``
    there, and extracts a calibration curve to apply during the read.

    Args:
        worker: The worker whose temp dir / calibration extraction is used.
        save_path: The report's destination path (only its basename is used
            to name the staged files).
        ti1: The TI1 chart to measure.
        oprof: The original (display) profile.
        profile: The profile actually used for the lookup (``oprof`` unless a
            simulation profile is standing in as the output profile).
        use_sim_as_output: ``measurement_report.use_simulation_profile_as_output``.
        devlink: The device-link profile, if any.

    Returns:
        ``(ti1_path, cal_path)``, both inside the worker's temp dir (or
        ``cal_path`` pointing at the bundled ``linear.cal`` when the source
        profile carries no calibration curve).

    Raises:
        Exception: Whatever ``worker.create_tempdir`` / file I/O /
            ``extract_cal_from_profile`` raise.
    """
    temp = worker.create_tempdir()
    if isinstance(temp, Exception):
        raise temp
    name = os.path.splitext(os.path.basename(save_path))[0]
    ti1_path = os.path.join(temp, f"{name}.ti1")
    profile_path = os.path.join(temp, f"{name}.icc")

    with open(ti1_path, "wb") as ti1_file:
        ti1_file.write(bytes(ti1))
    profile.write(profile_path)

    calprof = select_calibration_profile(oprof, profile, use_sim_as_output, devlink)

    cal_path = os.path.join(temp, f"{name}.cal")
    cal = extract_cal_from_profile(calprof, cal_path, False)
    if not cal:
        cal_path = get_data_path("linear.cal")
    return ti1_path, cal_path


def perform_self_check_lookup(
    worker: Worker,
    ti1: CGATS,
    oprof: ICCProfile,
    devlink: ICCProfile | None,
    save_path: str,
) -> tuple[str, ICCProfile]:
    """Look up the chart through the display profile's own tables instead of
    measuring -- the "self-check report" (hold Alt while clicking Measure).

    Pure port of the ``self_check_report and oprof`` branch of
    ``measurement_report_handler``: writes ``oprof`` (baking in its
    calibration curve first if the device link expects one applied), looks
    ``ti1`` up through it directly (no instrument involved), and writes the
    result as a TI3 the caller feeds into :func:`finalize_measurement_report`
    exactly like a real measurement would.

    Args:
        worker: The worker whose ``create_tempdir`` / ``chart_lookup`` /
            ``exec_cmd`` do the actual work.
        ti1: The TI1 chart to look up (``ReportContext.ti1``).
        oprof: The original (display) profile.
        devlink: The device-link profile, if any (only its ``collink.args``
            metadata is inspected, to decide whether a calibration curve
            needs to be baked into ``oprof`` first).
        save_path: The report's destination path (only its basename is used
            to name the staged files).

    Returns:
        ``(ti3_path, oprof)``: the staged TI3 file and, when a calibration
        curve had to be baked in first, the reloaded profile (otherwise the
        same ``oprof`` passed in) -- both feed into
        :func:`finalize_measurement_report` as its ``ti3_path`` / ``oprof``.

    Raises:
        Exception: Whatever ``worker.create_tempdir`` / ``exec_cmd`` /
            ``chart_lookup`` / file I/O raise, or the ``applycal``
            invocation's own failure.
    """
    temp = worker.create_tempdir()
    if isinstance(temp, Exception):
        raise temp
    name = os.path.splitext(os.path.basename(save_path))[0]
    ti3_path = os.path.join(temp, f"{name}.ti3")
    profile_path = os.path.join(temp, f"{name}.icc")

    # Argyll applycal can't deal with single gamma TRC tags or TRC tags with
    # less than 256 entries.
    _applycal_bug_workaround(oprof)
    oprof.write(profile_path)

    if devlink_applies_calibration(devlink):
        oprof_cal_path = os.path.join(temp, f"{name}.cal")
        extract_cal_from_profile(oprof, oprof_cal_path)
        profile_with_cal_path = os.path.join(temp, f"{name}_with_cal.icc")
        applycal = get_argyll_util("applycal")
        if not applycal:
            raise Exception(lang.getstr("argyll.util.not_found", "applycal"))
        result = worker.exec_cmd(
            applycal,
            ["-v", oprof_cal_path, profile_path, profile_with_cal_path],
            capture_output=True,
            skip_scripts=True,
        )
        if not result:
            result = Exception(
                "\n\n".join([lang.getstr("apply_cal.error"), "\n".join(worker.errors)])
            )
        if isinstance(result, Exception) and not getcfg("dry_run"):
            raise result
        odesc = oprof.getDescription()
        oprof = ICCProfile(profile_with_cal_path)
        oprof.setDescription(odesc)

    _void, ti3, _void2 = worker.chart_lookup(
        ti1, oprof, pcs="x", intent="a", white_patches=0
    )
    wtpt = list(oprof.tags.wtpt.values())
    if isinstance(oprof.tags.get("lumi"), XYZType):
        luminance = oprof.tags.lumi.Y
    else:
        luminance = 100
    white_xyz_cdm2 = [v * luminance for v in wtpt]
    ti3.add_keyword(
        "LUMINANCE_XYZ_CDM2", "{:.6f} {:.6f} {:.6f}".format(*white_xyz_cdm2)
    )

    with open(ti3_path, "wb") as ti3_file:
        ti3_file.write(bytes(ti3))
    return ti3_path, oprof


def resolve_working_ti3_path(worker: Worker) -> str | None:
    """Locate the just-measured working TI3 for the profile-build pipeline.

    Pure port of the default-path derivation in
    ``measurement_file_check_confirm`` (used when no explicit TI3 is passed,
    i.e. from ``check_copy_ti3``): the profile-building flow
    (``MainWindow._build_profile_from_measurement``) doesn't have a TI3
    object at hand yet the way the measurement-report flow does, only the
    worker's temp dir and the configured profile name.

    Args:
        worker: The worker whose ``tempdir`` was populated by the just-run
            characterization measurement.

    Returns:
        The working TI3's path, or ``None`` if it can't be found (the caller
        should then proceed without a sanity check, matching wx's
        "let the caller handle missing files" comment).
    """
    tempdir = worker.tempdir
    if not tempdir or not os.path.isdir(tempdir):
        return None
    name = getcfg("profile.name.expanded")
    path = os.path.join(tempdir, f"{make_argyll_compatible_path(name)}.ti3")
    return path if os.path.isfile(path) else None


def compute_ccxx_measurement_basename(worker: Worker) -> str:
    """Derive the save basename for a CCXX-testchart measurement.

    Pure port of the naming half of ``MainFrame.setup_ccxx_measurement``: the
    directory-picking and write-access-check half stays with the Qt caller,
    which owns the dialogs. Called once ``config.is_ccxx_testchart()`` and
    ``profile.save_path`` are already resolved.

    Args:
        worker: Used for the instrument/display name pieces of the basename.

    Returns:
        A filesystem-safe basename (no extension) combining instrument,
        observer, display name, and a timestamp.
    """
    if getcfg("observer") == "1931_2":
        basename = "{} & {} {}".format(
            worker.get_instrument_name(),
            worker.get_display_name(True, True),
            strftime("%Y-%m-%d %H-%M-%S"),
        )
    else:
        basename = "{} ({} {}) & {} {}".format(
            worker.get_instrument_name(),
            lang.getstr(f"observer.{getcfg('observer')}"),
            lang.getstr("observer"),
            worker.get_display_name(True, True),
            strftime("%Y-%m-%d %H-%M-%S"),
        )
    return make_filename_safe(basename)


@dataclass
class SanityCheckRow:
    """One row the sanity-check review grid renders/edits.

    Mirrors one grid row in wx's ``MeasurementFileCheckSanityDialog``: either
    the "previous" patch of a suspicious pair (``has_delta`` ``False``, since
    it is shown for context only) or the flagged patch itself.
    """

    sample_id: float
    rgb: tuple[float, float, float]
    xyz: tuple[float, float, float]
    has_delta: bool
    delta: dict | None
    sRGB_delta: dict | None
    delta_to_sRGB: dict


@dataclass
class SanityCheckContext:
    """Resolved state for one sanity-check review, built by
    :func:`resolve_sanity_check`.

    ``ti3`` / ``items`` are live CGATS objects (not copies): editing/removing
    through :func:`apply_sanity_check_result` mutates the same underlying
    document the caller loaded, matching wx's dialog operating directly on
    ``ti3_1.queryv1("DATA")``.
    """

    ti3: CGATS
    items: list
    black: tuple[float, float, float] | None
    white: tuple[float, float, float] | None
    rows: list[SanityCheckRow]


def resolve_sanity_check(ti3: CGATS, force: bool = False) -> SanityCheckContext | None:
    """Detect suspiciously-off patches in a measured TI3.

    Pure port of the detection half of ``measurement_file_check_confirm``
    (``check_ti3`` / row de-duplication); the interactive review grid itself
    is the caller's (Qt) responsibility -- show it only when this returns
    non-``None``.

    Args:
        ti3: The measured TI3 (or the whole CGATS document containing it --
            ``verify_ti1_rgb_xyz`` finds the right section either way).
        force: Skip the ``ti3.check_sanity.auto`` gate (used by the
            standalone "check measurement file" tool, not currently ported).

    Returns:
        ``None`` if the check is disabled (and not forced) or nothing looks
        suspicious -- the caller should proceed without showing a dialog.
        Otherwise the resolved :class:`SanityCheckContext` to show.
    """
    if not getcfg("ti3.check_sanity.auto") and not force:
        return None
    ti3_1 = verify_ti1_rgb_xyz(ti3)
    suspicious = check_ti3(ti3_1)
    if not suspicious:
        return None

    data = ti3_1.queryv1("DATA")
    black_item = data.queryi1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
    black = (
        (black_item["XYZ_X"], black_item["XYZ_Y"], black_item["XYZ_Z"])
        if black_item
        else None
    )
    white_item = data.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
    white = (
        (white_item["XYZ_X"], white_item["XYZ_Y"], white_item["XYZ_Z"])
        if white_item
        else None
    )

    items: list = []
    rows: list[SanityCheckRow] = []
    for prev, item, delta, sRGB_delta, prev_delta_to_sRGB, delta_to_sRGB in suspicious:
        for cur, cur_delta, cur_sRGB_delta, cur_delta_to_sRGB in (
            (prev, None, None, prev_delta_to_sRGB),
            (item, delta, sRGB_delta, delta_to_sRGB),
        ):
            if not cur or cur in items:
                continue
            items.append(cur)
            rows.append(
                SanityCheckRow(
                    sample_id=cur.SAMPLE_ID,
                    rgb=(cur["RGB_R"], cur["RGB_G"], cur["RGB_B"]),
                    xyz=(cur["XYZ_X"], cur["XYZ_Y"], cur["XYZ_Z"]),
                    has_delta=cur_delta is not None,
                    delta=cur_delta,
                    sRGB_delta=cur_sRGB_delta,
                    delta_to_sRGB=cur_delta_to_sRGB,
                )
            )
    return SanityCheckContext(
        ti3=ti3_1, items=items, black=black, white=white, rows=rows
    )


def recompute_sanity_row(
    ctx: SanityCheckContext,
    row_index: int,
    rgb: tuple[float, float, float],
    xyz: tuple[float, float, float],
) -> tuple[dict | None, dict | None, dict]:
    """Recompute one row's delta values after an in-place RGB/XYZ edit.

    Pure port of ``MeasurementFileCheckSanityDialog.cell_change_handler``'s
    recompute. Faithfully reproduces one of its quirks: when ``row_index``
    has a "previous" row, that previous row's *original* (not any
    since-edited) RGB/XYZ is used, matching wx re-reading
    ``dlg.suspicious_items[event.Row - 1]`` rather than tracking prior edits.

    Args:
        ctx: The context :func:`resolve_sanity_check` returned.
        row_index: The edited row's index into ``ctx.rows`` / ``ctx.items``.
        rgb: The row's new (edited) RGB values, 0-100.
        xyz: The row's new (edited) XYZ values, 0-100.

    Returns:
        ``(delta, sRGB_delta, delta_to_sRGB)`` for the edited row, in the same
        shape as :class:`SanityCheckRow`'s fields.
    """
    sRGBLab, Lab, delta_to_sRGB, _criteria1, _debuginfo = check_ti3_criteria1(
        rgb, xyz, ctx.black, ctx.white, print_debuginfo=True
    )
    if ctx.rows[row_index].has_delta:
        prev_item = ctx.items[row_index - 1]
        prev_rgb = (prev_item["RGB_R"], prev_item["RGB_G"], prev_item["RGB_B"])
        prev_xyz = (prev_item["XYZ_X"], prev_item["XYZ_Y"], prev_item["XYZ_Z"])
        prev_sRGBLab, prev_Lab, _prev_delta_to_sRGB, _c1, _d = check_ti3_criteria1(
            prev_rgb, prev_xyz, ctx.black, ctx.white, print_debuginfo=False
        )
        delta, sRGB_delta, _criteria2 = check_ti3_criteria2(
            prev_Lab, Lab, prev_sRGBLab, sRGBLab, prev_rgb, rgb
        )
    else:
        delta, sRGB_delta = None, None
    return delta, sRGB_delta, delta_to_sRGB


def apply_sanity_check_result(
    ctx: SanityCheckContext,
    removed_row_indexes: list[int],
    mods: dict[int, dict[str, float]],
) -> list:
    """Apply the review grid's edits to the underlying measured TI3.

    Pure port of ``measurement_file_check_confirm``'s result-consumption tail:
    removes unchecked rows (via ``CGATS.remove``, which reindexes correctly)
    and writes back any edited RGB/XYZ cells for the rows that remain.

    Args:
        ctx: The context :func:`resolve_sanity_check` returned.
        removed_row_indexes: Indexes (into ``ctx.rows`` / ``ctx.items``) of
            rows the user unchecked for removal.
        mods: Row index -> ``{field: value}`` for edited-but-kept rows
            (fields are ``RGB_R`` / ``RGB_G`` / ``RGB_B`` / ``XYZ_X`` /
            ``XYZ_Y`` / ``XYZ_Z``).

    Returns:
        The removed CGATS items, in ascending original-row order (feeds
        :func:`resync_report_ti3_removals` for the measurement-report path).
    """
    data = ctx.ti3.queryv1("DATA")
    removed = []
    for index in sorted(removed_row_indexes, reverse=True):
        removed.insert(0, data.remove(ctx.items[index]))
    for index, fields in mods.items():
        if index in removed_row_indexes:
            continue
        item = ctx.items[index]
        for field, value in fields.items():
            item[field] = value
    return removed


def resync_report_ti3_removals(
    ti3_ref: CGATS, sim_ti3: CGATS | None, removed_items: list, offset: int
) -> None:
    """Drop the reference/simulation patches matching sanity-removed items.

    Pure port of ``measurement_report_consumer``'s ``isinstance(result,
    tuple)`` branch: patches the sanity-check dialog dropped from the
    *measured* TI3 must also be dropped from the reference (and simulation)
    TI3s the report compares against, keyed by the same white-patch
    ``offset`` used elsewhere in :func:`finalize_measurement_report`.

    Args:
        ti3_ref: The reference TI3 (mutated in place).
        sim_ti3: The simulation TI3, if any (mutated in place).
        removed_items: The CGATS items :func:`apply_sanity_check_result`
            removed from the measured TI3.
        offset: The measured-vs-reference patch-count offset already computed
            by the caller (accounts for an extra devlink white patch).
    """
    for item in reversed(removed_items):
        key = item.key - offset
        ti3_ref.DATA.pop(key)
        if sim_ti3:
            sim_ti3.DATA.pop(key)


class MeasurementFileError(Exception):
    """A file picked for the standalone "check measurement file" tool is unusable.

    ``str(exception)`` is already the fully-formatted, translated message the
    caller should show verbatim (matching the ``ReportSetupError`` precedent).
    """


@dataclass
class MeasurementFileLoad:
    """A measurement file resolved by :func:`load_measurement_file`."""

    #: The loaded TI3 chart.
    ti3: CGATS
    #: The ICC profile the TI3 was embedded in, or ``None`` for a plain
    #: ``.ti3`` file.
    profile: ICCProfile | None


def load_measurement_file(path: str) -> MeasurementFileLoad:
    """Load a ``.ti3`` file or an ICC profile with an embedded TI3 chart.

    Pure port of the file-loading half of ``measurement_file_check_handler``
    (``display_cal.py``), used by the standalone "check measurement file"
    tool. Fixes a latent bug found while porting: the wx code compared a
    ``bytes`` tag slice against the ``str`` literal ``"CTI3"``, which is
    never equal in Python 3, so the "no embedded TI3" error fired even when a
    valid CTI3 chart was present -- also fixed at the source in
    ``display_cal.py``.

    Args:
        path: Path to a ``.ti3`` file, or an ``.icc``/``.icm`` profile with a
            ``CIED`` or ``targ`` tag holding an embedded CTI3 chart.

    Returns:
        The loaded :class:`MeasurementFileLoad`.

    Raises:
        MeasurementFileError: The profile could not be parsed, had no
            embedded TI3 chart, or the ``.ti3`` file could not be opened.
    """
    _root, ext = os.path.splitext(path)
    if ext.lower() != ".ti3":
        try:
            profile = ICCProfile(path)
        except (OSError, ICCProfileInvalidError) as exception:
            raise MeasurementFileError(
                f"{lang.getstr('profile.invalid')}\n{path}"
            ) from exception
        ti3_data = profile.tags.get("CIED", b"") or profile.tags.get("targ", b"")
        if ti3_data[0:4] != b"CTI3":
            raise MeasurementFileError(
                f"{lang.getstr('profile.no_embedded_ti3')}\n{path}"
            )
        ti3_source = BytesIO(ti3_data)
    else:
        profile = None
        try:
            ti3_source = open(path, "rb")  # noqa: SIM115
        except OSError as exception:
            raise MeasurementFileError(
                lang.getstr("error.file.open", path)
            ) from exception
    return MeasurementFileLoad(ti3=CGATS(ti3_source), profile=profile)


def build_regenerated_profile_tag_data(ti3: CGATS) -> bytes:
    """Serialize a checked TI3 back into embeddable ``textType`` tag data.

    Pure port of the ``profile.tags.targ = TextType(...)`` assignment in
    ``measurement_file_check_handler``. Fixes a second latent bug found while
    porting: the wx code concatenated the ``CGATS`` object itself into the
    byte string instead of ``bytes(ti3)``, which raised ``TypeError`` any
    time this branch actually ran -- also fixed at the source.

    Args:
        ti3: The (possibly sanity-check-edited) TI3 to embed.

    Returns:
        Raw ``textType`` tag data, ready for
        ``DisplayCAL.icc_profile.TextType(data, "targ")``.
    """
    return b"text\0\0\0\0" + bytes(ti3) + b"\0"


def finalize_measurement_report(
    *,
    worker: Worker,
    ti3_path: str,
    profile: ICCProfile,
    sim_profile: ICCProfile | None,
    intent: str,
    sim_intent: str | None,
    devlink: ICCProfile | None,
    ti3_ref: CGATS,
    sim_ti3: CGATS | None,
    save_path: str,
    chart: CGATS,
    gray: list | None,
    apply_trc: bool,
    use_sim: bool,
    use_sim_as_output: bool,
    oprof: ICCProfile,
    instrument_name: str,
    measurement_mode_name: str,
    display_name: str,
    observers: dict,
    version_string: str,
    pack_js: bool = True,
    self_check_report: bool = False,
    removed_items: list | None = None,
) -> None:
    """Process a completed measurement and write the HTML report.

    Ports ``measurement_report_consumer``'s body from just after the
    sanity-check dialog (now handled by the caller via
    :func:`resolve_sanity_check` / :func:`apply_sanity_check_result` -- see
    module docstring) through ``report.create`` / launching the finished
    file. The caller is expected to have already handled the ``Exception`` /
    falsy-result branches of the worker run (matching how
    ``MainWindow._on_measurement_finished`` handles those before calling into
    ``profile_finish.py``) -- this function assumes the measurement (or
    :func:`perform_self_check_lookup`) succeeded.

    Args:
        worker: The worker the measurement ran on (used for ``wrapup`` and
            re-deriving the quantization args).
        ti3_path: Path to the measured TI3 (``measure_ti1``'s working file).
        profile: The profile used for the lookup.
        sim_profile: The simulation profile, if any.
        intent: The rendering intent used for the reference lookup.
        sim_intent: The simulation rendering intent, if any.
        devlink: The device-link profile, if any.
        ti3_ref: The reference TI3 (mutated in place, matching the original).
        sim_ti3: The simulation TI3, if any.
        save_path: Where to write the ``.html`` report.
        chart: The original chart CGATS (only its filename is inspected).
        gray: Grayscale reference patches, if any.
        apply_trc: Whether a BT.1886-style TRC target was applied.
        use_sim: ``measurement_report.use_simulation_profile``.
        use_sim_as_output: ``measurement_report.use_simulation_profile_as_output``.
        oprof: The original (display) profile.
        instrument_name: The selected instrument's label (``comport_ctrl``).
        measurement_mode_name: The selected measurement mode's label.
        display_name: The target display's label, already stripped of the
            localized ``display.primary`` suffix by the caller.
        observers: Observer code -> localized label map (``self.observers_ab``
            / ``self._observers``).
        version_string: ``VERSION_STRING``, embedded in the report.
        pack_js: ``report.pack_js``.
        self_check_report: Whether this is a self-check report (see
            :func:`perform_self_check_lookup`) -- swaps in the profile's own
            device/description for the display/instrument/CCMX placeholders
            since no instrument was actually involved.
        removed_items: CGATS items :func:`apply_sanity_check_result` removed
            from the measured TI3 (if any), so the reference/simulation TI3s
            can be resynced via :func:`resync_report_ti3_removals`.

    Raises:
        Exception: Any CGATS / I/O error encountered while processing the
            measured data or writing the report.
    """
    try:
        ti3_measured = CGATS(ti3_path)[0]
    except (
        OSError,
        CGATSInvalidError,
        CGATSInvalidOperationError,
        CGATSKeyError,
        CGATSTypeError,
        CGATSValueError,
    ) as exception:
        worker.wrapup(exception)
        raise

    qbits = None
    if config.get_display_name() != "Untethered":
        args = []
        if getcfg("extra_args.dispread").strip():
            args += parse_argument_string(getcfg("extra_args.dispread"))
        worker.add_measurement_features(
            args, True, allow_video_levels=True, quantize=True
        )
        qbits = resolve_quantization_bits(args)
    if qbits:
        ti3_ref.quantize_device_values(qbits)
        if gray:
            gray = quantize_gray(gray, qbits)

    ti3_ref.write(f"{os.path.splitext(ti3_path)[0]}_ref.ti3")

    white_ref = ti3_ref.queryi(_WHITE_RGB)
    if devlink:
        ti3_measured.DATA.remove(0)
        offset = len(ti3_measured.DATA) - len(ti3_ref.DATA)
        for i in range(offset):
            for label in ("RGB_R", "RGB_G", "RGB_B"):
                ti3_measured.DATA[i][label] = 100.0
        for i in ti3_ref.DATA:
            for label in ("RGB_R", "RGB_G", "RGB_B"):
                ti3_measured.DATA[i + offset][label] = ti3_ref.DATA[i][label]
        white_measured = ti3_measured.queryi(_WHITE_RGB)
        luminance = float(ti3_measured.LUMINANCE_XYZ_CDM2.split()[1])
        white_xyz_cdm2 = [0, 0, 0]
        for i, label in enumerate(("XYZ_X", "XYZ_Y", "XYZ_Z")):
            white_xyz_cdm2[i] = white_measured[0][label] * luminance / 100.0
        ti3_measured.LUMINANCE_XYZ_CDM2 = "{:.6f} {:.6f} {:.6f}".format(*white_xyz_cdm2)
        scale = 100.0 / white_measured[0]["XYZ_Y"]
        for i in ti3_measured.DATA:
            for label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
                ti3_measured.DATA[i][label] *= scale
    else:
        white_measured = ti3_measured.queryi(_WHITE_RGB)
        offset = max(len(white_measured) - len(white_ref), 0)

    if removed_items:
        resync_report_ti3_removals(ti3_ref, sim_ti3, removed_items, offset)
        white_ref = ti3_ref.queryi(_WHITE_RGB)
        offset = max(len(white_measured) - len(white_ref), 0)

    planckian = False
    if (profile.tags.get("CIED", "") or profile.tags.get("targ", ""))[0:4] == "CTI3":
        options_dispcal = get_options_from_profile(profile)[0]
        for option in options_dispcal:
            if option.startswith("T"):
                planckian = True
                break

    cal_entrycount = 256
    if isinstance(profile.tags.get("vcgt"), VideoCardGammaType):
        rgb = [[], [], []]
        vcgt = profile.tags.vcgt
        if "data" in vcgt:
            cal_entrycount = vcgt["entryCount"]
            for i in range(cal_entrycount):
                for j in range(3):
                    rgb[j].append(
                        float(vcgt["data"][j][i])
                        / (math.pow(256, vcgt["entrySize"]) - 1)
                        * 255
                    )
        else:
            step = 100.0 / 255.0
            for i in range(cal_entrycount):
                for j, chname in enumerate(("red", "green", "blue")):
                    vmin = float2dec(vcgt[chname + "Min"] * 255)
                    v = float2dec(math.pow(step * i / 100.0, vcgt[chname + "Gamma"]))
                    vmax = float2dec(vcgt[chname + "Max"] * 255)
                    rgb[j].append(float2dec(vmin + v * (vmax - vmin), 8))
        cal_rgblevels = [len({round(n) for n in channel}) for channel in rgb]
    else:
        cal_rgblevels = [256, 256, 256]

    if not chart.filename.lower().endswith(".ti1") or sim_ti3:
        for i in ti3_ref.DATA:
            for color in ("RGB_R", "RGB_G", "RGB_B"):
                if sim_ti3 and sim_ti3.DATA[i].get(color) is not None:
                    ti3_ref.DATA[i][color] = sim_ti3.DATA[i][color]
                else:
                    ti3_ref.DATA[i][color] = ti3_measured.DATA[i + offset][color]

    cat = "Bradford"
    ti3_joined = CGATS(bytes(ti3_ref))[0]
    ti3_joined.LUMINANCE_XYZ_CDM2 = ti3_measured.LUMINANCE_XYZ_CDM2
    labels_xyz = ("XYZ_X", "XYZ_Y", "XYZ_Z")
    if (
        "XYZ_X" not in list(ti3_joined.DATA_FORMAT.values())
        and "XYZ_Y" not in list(ti3_joined.DATA_FORMAT.values())
        and "XYZ_Z" not in list(ti3_joined.DATA_FORMAT.values())
    ):
        ti3_joined.DATA_FORMAT.add_data(labels_xyz)
    for i in ti3_joined.DATA:
        for color in labels_xyz:
            ti3_joined.DATA[i][color] = ti3_measured.DATA[i + offset][color]

    worker.wrapup(False)

    wtpt_profile_norm = tuple(n * 100 for n in list(profile.tags.wtpt.values()))
    if isinstance(profile.tags.get("chad"), ChromaticAdaptionTag):
        w_x, w_y, w_z = profile.tags.chad.inverted() * wtpt_profile_norm
        wtpt_profile_norm = tuple((n / w_y) * 100.0 for n in (w_x, w_y, w_z))
        cat = profile.guess_cat() or cat
    elif isinstance(profile.tags.get("arts"), ChromaticAdaptionTag):
        cat = profile.guess_cat() or cat
    if oprof and isinstance(oprof.tags.get("lumi"), XYZType):
        scale = oprof.tags.lumi.Y / 100.0
        wtpt_profile = tuple(n * scale for n in wtpt_profile_norm)
    else:
        wtpt_profile = wtpt_profile_norm

    if sim_profile and "chad" in sim_profile.tags:
        # NOTE: matches the original, which computes this but never uses it.
        wtpt_sim_profile_norm = tuple(  # noqa: F841
            n * 100 for n in list(sim_profile.tags.wtpt.values())
        )

    wtpt_measured = tuple(float(n) for n in ti3_joined.LUMINANCE_XYZ_CDM2.split())
    wtpt_measured_norm = tuple((n / wtpt_measured[1]) * 100 for n in wtpt_measured)

    if intent != "a" and sim_intent != "a":
        white = ti3_joined.queryi(_WHITE_RGB)
        for i in white:
            white[i].update(
                {
                    "XYZ_X": wtpt_measured_norm[0],
                    "XYZ_Y": wtpt_measured_norm[1],
                    "XYZ_Z": wtpt_measured_norm[2],
                }
            )

    black = ti3_joined.queryi1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
    if black:
        bkpt_measured_norm = (black["XYZ_X"], black["XYZ_Y"], black["XYZ_Z"])
        bkpt_measured = tuple(wtpt_measured[1] / 100 * n for n in bkpt_measured_norm)
    else:
        bkpt_measured = None

    labels_lab = ("LAB_L", "LAB_A", "LAB_B")
    for data in (ti3_ref, ti3_joined):
        data_formats = list(data.DATA_FORMAT.values())
        if (
            b"XYZ_X" in data_formats
            and b"XYZ_Y" in data_formats
            and b"XYZ_Z" in data_formats
        ):
            if (
                b"LAB_L" not in data_formats
                and b"LAB_A" not in data_formats
                and b"LAB_B" not in data_formats
            ):
                data.DATA_FORMAT.add_data(labels_lab)
                has_lab = False
            else:
                has_lab = True
            if data is ti3_joined or not has_lab:
                for i in data.DATA:
                    x, y, z = (data.DATA[i][color] for color in labels_xyz)
                    if data is ti3_joined:
                        x, y, z = colormath.adapt(x, y, z, wtpt_measured_norm, cat=cat)
                    lab = XYZ2Lab(x, y, z)
                    for j, color in enumerate(labels_lab):
                        data.DATA[i][color] = lab[j]
        if data is ti3_ref and sim_intent == "a" and intent == "a":
            for i in data.DATA:
                lab_l, lab_a, lab_b = (data.DATA[i][color] for color in labels_lab)
                x, y, z = colormath.Lab2XYZ(lab_l, lab_a, lab_b, scale=100)
                x, y, z = colormath.adapt(x, y, z, wtpt_profile_norm, cat=cat)
                lab = XYZ2Lab(x, y, z)
                for j, color in enumerate(labels_lab):
                    data.DATA[i][color] = lab[j]

    if self_check_report:
        instrument = "N/A"
        ccmx = "N/A"
    else:
        instrument = f"{instrument_name} — {measurement_mode_name}"
        observer = get_cfg_option_from_args(
            "observer", "-Q", getattr(worker, "options_dispread", [])
        )
        if observer != DEFAULTS["observer"]:
            instrument += " — " + observers.get(observer, observer)

        ccmx = "None"
        reference_observer = None
        if worker.instrument_can_use_ccxx():
            ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
            if len(ccmx) > 1 and ccmx[1]:
                ccmxpath = ccmx[1]
                ccmx = os.path.basename(ccmx[1])
                try:
                    cgats = CGATS(ccmxpath)
                except (OSError, CGATSError):
                    pass
                else:
                    filename, ext = os.path.splitext(ccmx)
                    desc = cgats.get_descriptor()
                    desc = lang.getstr(
                        ext[1:] + "." + filename, default=desc.decode("utf-8")
                    )
                    argyll_compatible_path = make_argyll_compatible_path(
                        desc, is_name=True
                    )
                    if argyll_compatible_path != filename:
                        ccmx = "{} &amp;lt;{}&amp;gt;".format(
                            desc, ellipsis_(ccmx, 31, "m")
                        )
                    if cgats.get(0, cgats).type == "CCMX":
                        reference_observer = cgats.queryv1("REFERENCE_OBSERVER")
                        if (
                            reference_observer
                            and reference_observer != DEFAULTS["observer"]
                        ):
                            reference_observer = observers.get(
                                reference_observer, reference_observer
                            )
                            if reference_observer.lower() not in ccmx.lower():
                                ccmx += " — " + reference_observer
            else:
                ccmx = "None"

    if not sim_profile and use_sim and use_sim_as_output:
        sim_profile = profile

    trc = report_trc_label(
        getcfg("measurement_report.trc_gamma"),
        getcfg("measurement_report.trc_gamma_type"),
        getcfg("measurement_report.trc_output_offset"),
    )

    if self_check_report:
        display = oprof.getDeviceModelDescription() or "N/A"
        if oprof is not profile:
            display += f" (Profile: {oprof.getDescription()})"
        report_type = "Self Check"
    else:
        display = display_name
        report_type = "Measurement"

    placeholders2data = {
        "${PLANCKIAN}": 'checked="checked"' if planckian else "",
        "${DISPLAY}": display,
        "${INSTRUMENT}": instrument,
        "${CORRECTION_MATRIX}": ccmx,
        "${BLACKPOINT}": "{:f} {:f} {:f}".format(
            *(bkpt_measured if bkpt_measured else (-1.0, -1.0, -1.0))
        ),
        "${WHITEPOINT}": "{:f} {:f} {:f}".format(*wtpt_measured),
        "${WHITEPOINT_NORMALIZED}": "{:f} {:f} {:f}".format(*wtpt_measured_norm),
        "${PROFILE}": profile.getDescription(),
        "${PROFILE_WHITEPOINT}": "{:f} {:f} {:f}".format(*wtpt_profile),
        "${PROFILE_WHITEPOINT_NORMALIZED}": "{:f} {:f} {:f}".format(*wtpt_profile_norm),
        "${SIMULATION_PROFILE}": sim_profile.getDescription() if sim_profile else "",
        "${TRC_GAMMA}": str(
            getcfg("measurement_report.trc_gamma") if apply_trc else "null"
        ),
        "${TRC_GAMMA_TYPE}": str(
            getcfg("measurement_report.trc_gamma_type") if apply_trc else ""
        ),
        "${TRC_OUTPUT_OFFSET}": str(
            getcfg("measurement_report.trc_output_offset") if apply_trc else 0
        ),
        "${TRC}": trc if apply_trc else "",
        "${WHITEPOINT_SIMULATION}": str(sim_intent == "a").lower(),
        "${WHITEPOINT_SIMULATION_RELATIVE}": str(
            sim_intent == "a" and intent == "r"
        ).lower(),
        "${DEVICELINK_PROFILE}": devlink.getDescription() if devlink else "",
        "${CALIBRATION}": report_calibration_label(
            oprof, profile, use_sim_as_output, devlink, self_check_report
        ),
        "${TESTCHART}": os.path.basename(chart.filename),
        "${ADAPTION}": str(profile.guess_cat(False) or cat),
        "${DATETIME}": strftime("%Y-%m-%d %H:%M:%S"),
        "${REF}": bytes(ti3_ref).decode("utf-8", "replace").replace('"', "&quot;"),
        "${MEASURED}": bytes(ti3_joined)
        .decode("utf-8", "replace")
        .replace('"', "&quot;"),
        "${CAL_ENTRYCOUNT}": str(cal_entrycount),
        "${CAL_RGBLEVELS}": repr(cal_rgblevels),
        "${GRAYSCALE}": repr(gray) if gray else "null",
        "${REPORT_VERSION}": version_string,
        "${REPORT_TYPE}": report_type,
    }

    report.create(save_path, placeholders2data, pack_js)
    launch_file(save_path)
