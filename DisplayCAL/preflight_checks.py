"""Toolkit-neutral pre-flight checks for the calibrate / profile action buttons.

Ports the config/path predicates and branch logic behind wx's
``MainFrame.check_overwrite``, ``check_show_macos_bugs_warning`` and
``current_cal_choice`` (``display_cal.py``), following the ``profile_finish.py``
/ ``profile_install.py`` precedent: this module computes what to ask and how to
interpret the answer, but never shows a dialog itself. The wx path delegates to
it for the parts listed below; each toolkit still owns building and showing its
own confirm dialog.

Not reproduced here (stays with the wx ``MainFrame`` method, Pile 2): building
the actual ``ConfirmDialog`` widgets (including the two extra checkboxes
``current_cal_choice`` adds to its dialog) and calling ``self.reset_cal()``,
which drives a live video-card LUT write plus (on the wx side only) refreshing
an embedded curve-viewer preview -- the Qt main window does not have one yet.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass

from DisplayCAL import config
from DisplayCAL.config import get_data_path, getcfg
from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError
from DisplayCAL.util_list import intlist
from DisplayCAL.worker import Worker, get_options_from_profile


def resolve_overwrite_path(ext: str = "", filename: str | None = None) -> str:
    """Return the destination path ``check_overwrite`` would test for existence.

    Args:
        ext: The file extension to use if no filename is provided.
        filename: The name of the file to check. If ``None``, the default
            profile name with ``ext`` is used (nested under its own
            same-named subdirectory, matching wx).

    Returns:
        The full destination path.
    """
    if not filename:
        name = getcfg("profile.name.expanded")
        return os.path.join(getcfg("profile.save_path"), name, name + ext)
    return os.path.join(getcfg("profile.save_path"), filename)


def macos_bugs_warning_applicable() -> bool:
    """Whether the macOS-bugs warnings apply to the running platform/version."""
    return sys.platform == "darwin" and intlist(platform.mac_ver()[0].split(".")) >= [
        10,
        8,
    ]


def should_warn_calibration_bugs() -> bool:
    """Whether the current calibration settings hit the macOS black-point bugs."""
    return bool(
        getcfg("calibration.black_point_correction.auto")
        or getcfg("calibration.black_point_correction")
        or getcfg("calibration.black_luminance", False)
    )


def should_warn_profile_bugs() -> bool:
    """Whether the profile would be shown wrong by the Apple CMM (macOS).

    It shows a display profile right only as single curve + matrix with
    black point compensation; an XYZ LUT one makes the whole screen look
    washed out once installed.
    """
    return getcfg("profile.type") != "S" or not getcfg(
        "profile.black_point_compensation"
    )


@dataclass(frozen=True)
class FastMatrixShaperChoiceInfo:
    """Pre-dialog state for ``calibrate_btn_handler``'s fast-matrix-shaper choice.

    Attributes:
        show_dialog: Whether the choice dialog should be shown at all.
        update_profile: Whether the "update the existing profile" wording
            applies (as opposed to the "create a fast matrix shaper profile"
            one) -- true when a calibration update targets an existing
            profile.
        msg_key: The ``lang`` key for the dialog's message.
        ok_key: The ``lang`` key for the dialog's affirmative-action button
            label.
    """

    show_dialog: bool
    update_profile: bool
    msg_key: str
    ok_key: str


def resolve_fast_matrix_shaper_choice_info() -> FastMatrixShaperChoiceInfo:
    """Port of the guard/branch logic in ``calibrate_btn_handler``.

    wx only shows this dialog on a genuine button click (its ``CustomEvent``
    guard, for programmatic/auto-retry re-invocation, has no Qt equivalent
    yet -- every Qt caller is a real click, so that half of the condition is
    omitted here).

    Returns:
        The resolved :class:`FastMatrixShaperChoiceInfo`.
    """
    update_profile = bool(getcfg("calibration.update")) and config.is_profile()
    show_dialog = (
        not getcfg("profile.update")
        and (not getcfg("calibration.update") or config.is_profile())
        and bool(getcfg("trc"))
    )
    if update_profile:
        msg_key, ok_key = "calibration.update_profile_choice", "profile.update"
    else:
        msg_key, ok_key = (
            "calibration.create_fast_matrix_shaper_choice",
            "calibration.create_fast_matrix_shaper",
        )
    return FastMatrixShaperChoiceInfo(show_dialog, update_profile, msg_key, ok_key)


def apply_fast_matrix_shaper_choice(
    info: FastMatrixShaperChoiceInfo, create: bool
) -> None:
    """Port of the post-``ShowModal`` branch in ``calibrate_btn_handler``.

    Args:
        info: The :class:`FastMatrixShaperChoiceInfo` the dialog was built
            from.
        create: Whether the affirmative ("update profile" / "create fast
            matrix shaper") button was clicked, as opposed to the plain
            "Calibrate" button.
    """
    if info.update_profile and create:
        config.setcfg("profile.update", 1)


class CalChoiceProfileInvalidError(Exception):
    """The calibration file's companion profile could not be read/parsed."""


@dataclass(frozen=True)
class CalChoiceInfo:
    """Pre-dialog state for ``current_cal_choice`` (wx's ``ConfirmDialog`` setup)."""

    is_uncalibratable: bool
    cal_path: str | None
    options_dispcal: list[str] | None
    can_use_current_cal: bool
    msg_key: str
    icon: str
    show_reset_checkbox: bool


def resolve_cal_choice_info(worker: Worker) -> CalChoiceInfo:
    """Compute the message/checkbox state ``current_cal_choice`` shows.

    Args:
        worker: The ``Worker`` whose Argyll version / LUT-access capability
            gates ``can_use_current_cal``.

    Returns:
        The resolved :class:`CalChoiceInfo`.

    Raises:
        CalChoiceProfileInvalidError: The configured calibration file is a
            profile (``.icc``/``.icm``) that fails to load.
    """
    if config.is_uncalibratable_display():
        return CalChoiceInfo(
            is_uncalibratable=True,
            cal_path=None,
            options_dispcal=None,
            can_use_current_cal=False,
            msg_key="",
            icon="",
            show_reset_checkbox=False,
        )
    cal = getcfg("calibration.file", False)
    options_dispcal = None
    if cal:
        filename, ext = os.path.splitext(cal)
        if ext.lower() in (".icc", ".icm"):
            try:
                profile = ICCProfile(cal)
            except (OSError, ICCProfileInvalidError) as exception:
                raise CalChoiceProfileInvalidError(cal) from exception
            options_dispcal = [
                f"-{arg}" for arg in get_options_from_profile(profile)[0]
            ]
        cal = f"{filename}.cal" if os.path.isfile(filename + ".cal") else None
    if worker.argyll_version < [1, 1, 0] or not worker.has_lut_access():
        can_use_current_cal = False
    else:
        can_use_current_cal = True
    if cal:
        msg_key, icon = "dialog.cal_info", "information"
    elif can_use_current_cal:
        msg_key, icon = "dialog.current_cal_warning", "warning"
    else:
        msg_key, icon = "dialog.linear_cal_info", "information"
    return CalChoiceInfo(
        is_uncalibratable=False,
        cal_path=cal,
        options_dispcal=options_dispcal,
        can_use_current_cal=can_use_current_cal,
        msg_key=msg_key,
        icon=icon,
        show_reset_checkbox=can_use_current_cal or bool(cal),
    )


@dataclass(frozen=True)
class CalChoiceResult:
    """Post-dialog outcome of ``current_cal_choice``.

    Attributes:
        apply_calibration: What to pass as ``Worker.measure``'s
            ``apply_calibration`` argument: ``None`` to embed the current
            (live) calibration, ``False`` for none, or a ``.cal`` file path.
        reset_video_lut: Whether the caller should reset the video card LUT
            (``MainFrame.reset_cal()``) before proceeding.
        options_dispcal: ``dispcal`` options recovered from the calibration
            file's companion profile, to assign to ``worker.options_dispcal``
            when set.
    """

    apply_calibration: bool | str | None
    reset_video_lut: bool
    options_dispcal: list[str] | None


def compute_cal_choice_result(
    info: CalChoiceInfo, embed_cal: bool, reset_cal: bool
) -> CalChoiceResult:
    """Port of ``current_cal_choice``'s post-``ShowModal`` branch logic.

    Args:
        info: The :class:`CalChoiceInfo` the dialog was built from.
        embed_cal: The dialog's "embed calibration" checkbox state.
        reset_cal: The dialog's "use linear instead" checkbox state (only
            meaningful when :attr:`CalChoiceInfo.show_reset_checkbox`).
    """
    if not embed_cal:
        return CalChoiceResult(
            apply_calibration=False,
            reset_video_lut=info.can_use_current_cal and reset_cal,
            options_dispcal=None,
        )
    if not (info.can_use_current_cal or info.cal_path) or reset_cal:
        return CalChoiceResult(
            apply_calibration=get_data_path("linear.cal"),
            reset_video_lut=False,
            options_dispcal=None,
        )
    if info.cal_path:
        return CalChoiceResult(
            apply_calibration=info.cal_path,
            reset_video_lut=False,
            options_dispcal=info.options_dispcal,
        )
    return CalChoiceResult(
        apply_calibration=None, reset_video_lut=False, options_dispcal=None
    )
