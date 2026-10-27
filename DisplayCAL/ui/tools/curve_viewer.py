"""Curve viewer — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_lut_viewer` (the ``curve-viewer`` tool).
Loads an ICC profile and shows its tone curves with
:class:`~DisplayCAL.ui.plot.curve.CurvePlot` in three modes:

* ``vcgt`` — calibration video-card-gamma curves (read from the tag),
* ``trc`` — the ``*TRC`` tone-response tags (read from the tag),
* ``measured`` — the *measured* tone response, computed live through Argyll
  ``xicclu`` with rendering-intent, lookup-direction (forward / inverse, plus
  backward variants for cLUT profiles) and cLUT/matrix controls.

It also loads ``.cal`` calibration files and can show the live video-card LUT
read back from the graphics card ("show actual LUT"), apply black point
compensation, install/reload a display's vcgt, save the plot or vcgt, show
advanced per-tag shaper curves, and (the standalone window only) follow the
display it's dragged onto.

The curve-and-controls view itself lives in :class:`CurvePanel`, a plain
``QWidget`` with no window chrome, so other tools (e.g.
:mod:`DisplayCAL.ui.tools.profile_info`) can embed the same tone-response view
without depending on this module's standalone window.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import (
    get_argyll_display_number,
    get_data_path,
    get_display_profile,
    get_verified_path,
    getcfg,
    is_virtual_display,
    setcfg,
)
from DisplayCAL.icc_profile import VideoCardGammaType
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.plot.curve import CurvePlot
from DisplayCAL.ui.plot.curve_data import (
    CURVE_MODES,
    DIRECTIONS,
    apply_bpc,
    available_curve_modes,
    available_directions,
    available_shaper_modes,
    curve_display,
    extract_curves,
    extract_shaper_curve,
    install_vcgt,
    load_profile_or_cal,
    measured_tone_response,
    read_current_lut,
    reload_display_vcgt,
    shaper_mode_lang_key,
)
from DisplayCAL.worker import Worker

if TYPE_CHECKING:
    from qtpy.QtGui import QMoveEvent, QShowEvent

    from DisplayCAL.icc_profile import ICCProfile

#: Profile file suffixes accepted for opening / drag-and-drop (``.cal`` is
#: wrapped in a fake profile).
PROFILE_SUFFIXES = (".icc", ".icm", ".cal")

#: Rendering intents offered for the measured tone response: lang key -> code.
INTENTS = {
    "gamap.intents.r": "r",
    "gamap.intents.a": "a",
    "gamap.intents.p": "p",
    "gamap.intents.s": "s",
}

#: Direction code -> human label key (inverse of curve_data.DIRECTIONS).
_DIRECTION_LABELS = {code: key for key, code in DIRECTIONS.items()}


class _MeasuredThread(QThread):
    """Compute the measured tone response off the GUI thread.

    Args:
        profile (ICCProfile): The RGB profile to measure.
        worker (Worker): The worker driving ``xicclu``.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        use_clut (bool): Use the cLUT path when the profile has one.
        direction (str): Lookup direction (``f``/``if``/``b``/``ib``).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with ``curves`` (dict) or, on failure, an ``Exception``.
    done = Signal(object)

    def __init__(
        self,
        profile: ICCProfile,
        worker: Worker,
        intent: str,
        use_clut: bool,
        direction: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._args = (profile, worker, intent, use_clut, direction)

    def run(self) -> None:
        profile, worker, intent, use_clut, direction = self._args
        try:
            self.done.emit(
                measured_tone_response(profile, worker, intent, use_clut, direction)
            )
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception)
        finally:
            worker.wrapup(False)


class _LutReadThread(QThread):
    """Read the live video-card LUT off the GUI thread.

    Args:
        worker (Worker): The worker driving ``dispwin``.
        display_no (int): Argyll display index (1-based).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the read-back profile or, on failure, an ``Exception``.
    done = Signal(object)

    def __init__(
        self, worker: Worker, display_no: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._display_no = display_no

    def run(self) -> None:
        try:
            self.done.emit(read_current_lut(self._worker, self._display_no))
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception)
        finally:
            self._worker.wrapup(False)


class _ActionThread(QThread):
    """Run a zero-argument callable driving ``worker`` off the GUI thread.

    Shared by the vcgt actions (install / reload), which drive Argyll
    ``dispwin`` and so shouldn't block the GUI.

    Args:
        worker (Worker): The worker the callable drives (only used to
            ``wrapup`` afterwards).
        func (Callable[[], object]): The action to run; its return value (or
            raised exception) is emitted via :attr:`done`.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the callable's return value or, on failure, an ``Exception``.
    done = Signal(object)

    def __init__(
        self,
        worker: Worker,
        func: Callable[[], object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._func = func

    def run(self) -> None:
        try:
            result = self._func()
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)
        self._worker.wrapup(False)


class CurvePanel(QWidget):
    """Embeddable calibration / tone-response / measured curve view.

    Owns its own :class:`~DisplayCAL.worker.Worker` and background threads, so
    it can be dropped into any window (standalone or as one view among
    several) without the host needing to know about ``xicclu`` or LUT
    readback.

    Args:
        parent (QWidget | None): Optional parent widget.
        show_mode_selector (bool): Show the built-in mode (vcgt / [rgb]TRC /
            measured) selector row. Hosts that drive the mode from their own
            combo (e.g. :mod:`DisplayCAL.ui.tools.profile_info`) pass ``False``
            and call :meth:`set_mode`.
    """

    #: Emitted whenever a new profile is displayed (user-loaded or read-back).
    profile_changed = Signal(object)

    #: Emitted with the formatted ``"x   y"`` cursor readout ("" when off-plot),
    #: so a host can show it in its own status area instead of the built-in one.
    cursor_moved = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        show_mode_selector: bool = True,
        show_actual_lut: bool = True,
        show_coords: bool = True,
    ) -> None:
        super().__init__(parent)
        self._profile: ICCProfile | None = None  # currently displayed
        self._user_profile: ICCProfile | None = None  # last loaded by the user
        # Last drawn curves in normalised (0..1) form, so re-scaling the axes
        # (e.g. toggling L*) doesn't recompute the measured response.
        self._raw_curves: dict[str, list[tuple[float, float]]] = {}
        self.worker = Worker()
        self._thread: _MeasuredThread | None = None
        self._read_thread: _LutReadThread | None = None
        self._action_thread: _ActionThread | None = None

        self.mode_combo = QComboBox()
        self.mode_combo.currentIndexChanged.connect(self._redraw)

        # Short literal labels, full translated tooltips (matches wx's own
        # fallback-UI labels for this toolbar, which are likewise untranslated).
        self.save_plot_btn = QPushButton("Save")
        self.save_plot_btn.setToolTip(
            f"{lang.getstr('save_as')} (*.bmp, *.png, *.jpg, *.xbm, *.xpm)"
        )
        self.save_plot_btn.clicked.connect(self._save_plot)
        self.save_plot_btn.setEnabled(False)

        # wx's reload/BPC/install/save-CAL toolbar, shown only in vcgt mode.
        self.reload_vcgt_btn = QPushButton("Reload")
        self.reload_vcgt_btn.setToolTip(
            lang.getstr("calibration.load_from_display_profile")
        )
        self.reload_vcgt_btn.clicked.connect(self._reload_vcgt)
        self.apply_bpc_btn = QPushButton("BPC")
        self.apply_bpc_btn.setToolTip(lang.getstr("black_point_compensation"))
        self.apply_bpc_btn.clicked.connect(self._apply_bpc)
        self.install_vcgt_btn = QPushButton("Apply")
        self.install_vcgt_btn.setToolTip(lang.getstr("apply_cal"))
        self.install_vcgt_btn.clicked.connect(self._install_vcgt)
        self.save_vcgt_btn = QPushButton("Save CAL")
        self.save_vcgt_btn.setToolTip(f"{lang.getstr('save_as')} (*.cal)")
        self.save_vcgt_btn.clicked.connect(self._save_cal)

        # wx "L* →": plot the tone response against perceptual L* (default) or
        # linear luminance. Re-scales the axes only, so no recompute.
        self.show_as_L = QCheckBox("L* →")
        self.show_as_L.setChecked(True)
        self.show_as_L.toggled.connect(self._render)

        self._show_actual_lut = show_actual_lut
        self.actual_lut_check = QCheckBox(lang.getstr("calibration.show_actual_lut"))
        self.actual_lut_check.toggled.connect(self._on_actual_lut_toggled)

        # Per-channel R/G/B toggles (wx ``add_toggles``): filter which primaries
        # are drawn without recomputing the (possibly expensive) curve data.
        self.channel_checks: dict[str, QCheckBox] = {}
        for name in ("R", "G", "B"):
            check = QCheckBox(name)
            check.setChecked(True)
            check.toggled.connect(
                lambda checked, n=name: self.plot.set_channel_hidden(n, not checked)
            )
            self.channel_checks[name] = check

        # Controls shown only for the measured tone response.
        self.intent_label = QLabel(lang.getstr("rendering_intent"))
        self.intent_combo = QComboBox()
        for key in INTENTS:
            self.intent_combo.addItem(lang.getstr(key), INTENTS[key])
        self.intent_combo.currentIndexChanged.connect(self._redraw)
        self.direction_label = QLabel(lang.getstr("direction"))
        self.direction_combo = QComboBox()
        self.direction_combo.currentIndexChanged.connect(self._redraw)
        # Literal "LUT" label (untranslated, like wx's own toggle_clut
        # checkbox) - not lang.getstr("use_separate_lut_access"), which is an
        # unrelated app-wide "Advanced" menu setting about hardware video
        # card gamma table access, not this cLUT-vs-matrix lookup choice.
        self.clut_check = QCheckBox("LUT")
        self.clut_check.setToolTip(
            "Use the profile's CLUT (if present) for the measured tone "
            "response, instead of the colorimetric matrix/shaper"
        )
        self.clut_check.setChecked(True)
        self.clut_check.toggled.connect(self._redraw)

        self.status = QLabel("")
        # Live input/output readout under the cursor (wx point labels). Shown in
        # the panel's own controls row unless a host opts to display it itself
        # (``show_coords=False``) via the ``cursor_moved`` signal.
        self._show_coords = show_coords
        self.coords_label = QLabel("")
        self.plot = CurvePlot()
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Matches wx_lut_viewer.LUTFrame: a small top toolbar with just the
        # mode selector, the plot filling the remaining space, and the
        # rendering-intent/direction/CLUT/actual-LUT controls in a row below
        # the plot (not above it).
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mode_row = QWidget()
        mode_row = QHBoxLayout(self.mode_row)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addWidget(QLabel(lang.getstr("mode")))
        mode_row.addWidget(self.mode_combo)
        mode_row.addWidget(self.save_plot_btn)
        mode_row.addStretch(1)
        self.mode_row.setVisible(show_mode_selector)
        layout.addWidget(self.mode_row)
        layout.addWidget(self.plot, 1)

        # vcgt-only action toolbar (wx's reload/BPC/install/save-CAL buttons),
        # shown only in vcgt mode.
        self.vcgt_actions_row = QWidget()
        vcgt_actions_row = QHBoxLayout(self.vcgt_actions_row)
        vcgt_actions_row.setContentsMargins(0, 0, 0, 0)
        vcgt_actions_row.addStretch(1)
        for button in (
            self.reload_vcgt_btn,
            self.apply_bpc_btn,
            self.install_vcgt_btn,
            self.save_vcgt_btn,
        ):
            vcgt_actions_row.addWidget(button)
        vcgt_actions_row.addStretch(1)
        layout.addWidget(self.vcgt_actions_row)

        # Centred L*/channel toggles below the plot (wx cbox_sizer): the L*
        # toggle first, then the R/G/B primaries.
        self.channel_row = QWidget()
        channel_row = QHBoxLayout(self.channel_row)
        channel_row.setContentsMargins(0, 0, 0, 0)
        channel_row.addStretch(1)
        channel_row.addWidget(self.show_as_L)
        channel_row.addSpacing(12)
        for check in self.channel_checks.values():
            channel_row.addWidget(check)
        channel_row.addStretch(1)
        layout.addWidget(self.channel_row)

        # Measured-only controls, stacked vertically (each label/field on its
        # own row) so they don't widen the panel the way a single side-by-side
        # row does. Centred as a block under the channel toggles.
        self.intent_row = QWidget()
        intent_row = QHBoxLayout(self.intent_row)
        intent_row.setContentsMargins(0, 0, 0, 0)
        intent_row.addWidget(self.intent_label)
        intent_row.addWidget(self.intent_combo, 1)
        self.direction_row = QWidget()
        direction_row = QHBoxLayout(self.direction_row)
        direction_row.setContentsMargins(0, 0, 0, 0)
        direction_row.addWidget(self.direction_label)
        direction_row.addWidget(self.direction_combo, 1)

        # Right-align both labels to a common width so their combos line up.
        label_width = max(
            self.intent_label.sizeHint().width(),
            self.direction_label.sizeHint().width(),
        )
        for label in (self.intent_label, self.direction_label):
            label.setMinimumWidth(label_width)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.measured_controls = QWidget()
        measured_controls = QVBoxLayout(self.measured_controls)
        measured_controls.setContentsMargins(0, 0, 0, 0)
        measured_controls.addWidget(self.intent_row)
        measured_controls.addWidget(self.direction_row)
        measured_controls.addWidget(self.clut_check)

        measured_row = QHBoxLayout()
        measured_row.addStretch(1)
        measured_row.addWidget(self.measured_controls)
        measured_row.addStretch(1)
        layout.addLayout(measured_row)

        controls = QHBoxLayout()
        if show_coords:
            controls.addWidget(self.coords_label)
        controls.addStretch(1)
        controls.addWidget(self.actual_lut_check)
        controls.addStretch(1)
        controls.addWidget(self.status)
        layout.addLayout(controls)

        self.actual_lut_check.setVisible(show_actual_lut)
        self._update_controls_visibility()

    def _update_controls_visibility(self) -> None:
        """Show intent/direction/CLUT controls only in the measured mode."""
        measured = self.mode_combo.currentData() == "measured"
        has_clut = bool(
            self._profile
            and ("A2B0" in self._profile.tags or "B2A0" in self._profile.tags)
        )
        # Direction is only worth offering when there is more than one.
        multi_direction = measured and self.direction_combo.count() > 1
        self.intent_row.setVisible(measured)
        self.direction_row.setVisible(multi_direction)
        self.clut_check.setVisible(measured and has_clut)
        self.measured_controls.setVisible(measured)
        # L* toggle only applies to the tone response (trc/measured), whose
        # X axis is the perceptual/linear response; vcgt is device in/out.
        self.show_as_L.setVisible(self.mode_combo.currentData() in ("trc", "measured"))
        self._update_vcgt_actions_visibility()

    def _update_vcgt_actions_visibility(self) -> None:
        """Show/enable the reload/BPC/install/save-CAL buttons in vcgt mode only.

        Mirrors ``LUTFrame.DrawLUT``'s ``*_btn.Enable``/``Show`` calls.
        """
        is_vcgt = self.mode_combo.currentData() == "vcgt"
        has_vcgt = bool(
            self._profile
            and isinstance(self._profile.tags.get("vcgt"), VideoCardGammaType)
        )
        self.vcgt_actions_row.setVisible(is_vcgt)
        self.reload_vcgt_btn.setEnabled(is_vcgt and bool(self._profile))
        enable_bpc = is_vcgt and has_vcgt
        if enable_bpc:
            values = self._profile.tags["vcgt"].getNormalizedValues()
            enable_bpc = values[0] != (0, 0, 0)
        self.apply_bpc_btn.setEnabled(enable_bpc)
        self.install_vcgt_btn.setEnabled(is_vcgt and has_vcgt)
        self.save_vcgt_btn.setEnabled(is_vcgt and has_vcgt)

    def _update_channel_row(self) -> None:
        """Show a channel toggle only for channels currently plotted.

        Called after each draw, once ``CurvePlot`` holds the new curve data.
        """
        channels = self.plot._channels
        for name, check in self.channel_checks.items():
            check.setVisible(name in channels)
        self.channel_row.setVisible(any(n in channels for n in self.channel_checks))
        self.save_plot_btn.setEnabled(bool(channels))

    def _on_mouse_moved(self, pos: object) -> None:
        """Update the input/output readout as the cursor moves over the plot.

        Args:
            pos (object): The scene position emitted by pyqtgraph.
        """
        plot_item = self.plot.getPlotItem()
        if plot_item.sceneBoundingRect().contains(pos):
            point = plot_item.vb.mapSceneToView(pos)
            text = f"{point.x():.1f}   {point.y():.1f}"
        else:
            text = ""
        if self._show_coords:
            self.coords_label.setText(text)
        self.cursor_moved.emit(text)

    # -- loading -------------------------------------------------------------

    def load_profile(self, path: str) -> None:
        """Load an ICC profile or ``.cal`` file at ``path`` and show its curves.

        Args:
            path (str): Path to an ``.icc``/``.icm`` profile or ``.cal`` file.
        """
        try:
            profile = load_profile_or_cal(os.path.abspath(path))
        except Exception as exception:  # noqa: BLE001
            self.status.setText(f"{lang.getstr('error')}: {exception}")
            return
        if profile is None:
            self.status.setText(f"{lang.getstr('error.file.open', path)}")
            return
        self._user_profile = profile
        # A freshly loaded profile supersedes any "show actual LUT" view.
        self.actual_lut_check.blockSignals(True)
        self.actual_lut_check.setChecked(False)
        self.actual_lut_check.blockSignals(False)
        self.set_profile(profile)

    def set_profile(self, profile: ICCProfile) -> None:
        """Display ``profile`` (user-loaded or read-back), repopulating modes.

        Args:
            profile (ICCProfile): The profile to display.
        """
        self._profile = profile
        self.profile_changed.emit(profile)

        modes = available_curve_modes(profile)
        shaper_modes = available_shaper_modes(profile)
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        for mode in modes:
            label = lang.getstr(CURVE_MODES[mode], default="Measured tone response")
            self.mode_combo.addItem(label, mode)
        for mode in shaper_modes:
            self.mode_combo.addItem(lang.getstr(shaper_mode_lang_key(mode)), mode)
        self.mode_combo.blockSignals(False)
        modes = modes + shaper_modes

        self.direction_combo.blockSignals(True)
        self.direction_combo.clear()
        if profile.colorSpace == b"RGB":
            for code in available_directions(profile):
                self.direction_combo.addItem(lang.getstr(_DIRECTION_LABELS[code]), code)
        self.direction_combo.blockSignals(False)

        if not modes:
            self.plot.draw_curves({})
            self._update_channel_row()
            self.status.setText(lang.getstr("profile.no_vcgt"))
            return
        self._redraw()

    def set_mode(self, mode: str) -> bool:
        """Select a tone-curve mode by key, redrawing if it changed.

        Lets a host that hides the built-in selector (``show_mode_selector=
        False``) drive the mode from its own combo.

        Args:
            mode (str): A ``CURVE_MODES`` key (``vcgt`` / ``trc`` / ``measured``).

        Returns:
            bool: ``True`` if the mode is available and selected, else ``False``.
        """
        index = self.mode_combo.findData(mode)
        if index < 0:
            return False
        if index == self.mode_combo.currentIndex():
            # currentIndexChanged won't fire; redraw explicitly (the host may
            # have switched away and back to this already-current mode).
            self._redraw()
        else:
            self.mode_combo.setCurrentIndex(index)
        return True

    def _on_actual_lut_toggled(self, checked: bool) -> None:
        """Switch between the loaded profile and the live video-card LUT.

        Args:
            checked (bool): Whether the "show actual LUT" box is checked.
        """
        if not checked:
            if self._user_profile is not None:
                self.set_profile(self._user_profile)
            return
        if self._read_thread is not None and self._read_thread.isRunning():
            return
        self.status.setText(lang.getstr("please_wait"))
        self._read_thread = _LutReadThread(
            self.worker, getcfg("display.number") or 1, parent=self
        )
        self._read_thread.done.connect(self._on_lut_read)
        self._read_thread.start()

    def _on_lut_read(self, result: object) -> None:
        """Receive the read-back LUT profile on the GUI thread.

        Args:
            result (object): The read-back profile, or an ``Exception`` on
                failure.
        """
        self._read_thread = None
        if isinstance(result, Exception):
            self.actual_lut_check.blockSignals(True)
            self.actual_lut_check.setChecked(False)
            self.actual_lut_check.blockSignals(False)
            self.status.setText(f"{lang.getstr('error')}: {result}")
            return
        self.set_profile(result)

    def _redraw(self) -> None:
        """Recompute the raw curves for the selected mode, then render them."""
        if self._profile is None or self.mode_combo.count() == 0:
            return
        self._update_controls_visibility()
        mode = self.mode_combo.currentData()
        if mode == "measured":
            self._draw_measured()
            return
        if "." in mode:  # advanced shaper curve, e.g. "A2B0.input"
            self._draw_shaper(mode)
            return
        self._raw_curves = extract_curves(self._profile, mode)
        self._render()
        self.status.setText(self._profile.getDescription())

    def _draw_shaper(self, mode: str) -> None:
        """Draw an advanced per-tag shaper curve (already display-scaled).

        Args:
            mode (str): A key from :func:`~DisplayCAL.ui.plot.curve_data.
                available_shaper_modes` (e.g. ``"A2B0.input"``).
        """
        channels, x_max, y_max, x_label, y_label = extract_shaper_curve(
            self._profile, mode
        )
        self.plot.draw_curves(
            channels,
            show_linear=True,
            x_range=(0.0, x_max),
            y_range=(0.0, y_max),
            x_label=x_label,
            y_label=y_label,
        )
        self._update_channel_row()
        self.status.setText(self._profile.getDescription())

    def _render(self) -> None:
        """Draw the cached raw curves on wx's per-mode display axes.

        Applies :func:`curve_display` (device 0..255 for vcgt; L*/Y 0..100 vs
        device 0..255 for trc/measured), so toggling ``L* →`` only re-scales the
        axes without recomputing the (possibly expensive) curve data.
        """
        mode = self.mode_combo.currentData()
        channels, x_max, y_max, x_label, y_label = curve_display(
            mode, self._raw_curves, self.show_as_L.isChecked()
        )
        self.plot.draw_curves(
            channels,
            show_linear=True,
            x_range=(0.0, x_max),
            y_range=(0.0, y_max),
            x_label=f"{x_label} {lang.getstr('in')}",
            y_label=f"{y_label} {lang.getstr('out')}",
        )
        self._update_channel_row()

    def _draw_measured(self) -> None:
        """Compute the measured tone response on a worker thread, then draw."""
        if self._thread is not None and self._thread.isRunning():
            return
        self.status.setText(lang.getstr("please_wait"))
        self._thread = _MeasuredThread(
            self._profile,
            self.worker,
            self.intent_combo.currentData(),
            self.clut_check.isChecked(),
            self.direction_combo.currentData() or "f",
            parent=self,
        )
        self._thread.done.connect(self._on_measured_ready)
        self._thread.start()

    def _on_measured_ready(self, result: object) -> None:
        """Receive measured curves on the GUI thread and draw them.

        Args:
            result (object): The measured curves dict, or an ``Exception`` on
                failure.
        """
        self._thread = None
        if isinstance(result, Exception):
            self._raw_curves = {}
            self.plot.draw_curves({})
            self._update_channel_row()
            self.status.setText(f"{lang.getstr('error')}: {result}")
            return
        self._raw_curves = result
        self._render()
        self.status.setText(self._profile.getDescription())

    # -- vcgt actions ----------------------------------------------------

    def _apply_bpc(self) -> None:
        """Apply black point compensation to the displayed vcgt and reload it."""
        try:
            profile = apply_bpc(self._profile)
        except Exception as exception:  # noqa: BLE001
            self.status.setText(f"{lang.getstr('error')}: {exception}")
            return
        self._user_profile = profile
        self.set_profile(profile)

    def _install_vcgt(self) -> None:
        """Install the displayed vcgt to the display via Argyll ``dispwin``."""
        if self._action_thread is not None and self._action_thread.isRunning():
            return
        self.status.setText(lang.getstr("please_wait"))
        profile = self._profile
        self._action_thread = _ActionThread(
            self.worker, lambda: install_vcgt(profile, self.worker), parent=self
        )
        self._action_thread.done.connect(self._on_install_vcgt_done)
        self._action_thread.start()

    def _on_install_vcgt_done(self, result: object) -> None:
        """Receive the install-vcgt result on the GUI thread.

        Args:
            result (object): ``None`` on success, or an ``Exception``.
        """
        self._action_thread = None
        if isinstance(result, Exception):
            self.status.setText(f"{lang.getstr('error')}: {result}")
            return
        self.status.setText(self._profile.getDescription())

    def _reload_vcgt(self) -> None:
        """Reload the vcgt from the current display profile via ``dispwin``."""
        if self._action_thread is not None and self._action_thread.isRunning():
            return
        self.status.setText(lang.getstr("please_wait"))
        self._action_thread = _ActionThread(
            self.worker, lambda: reload_display_vcgt(self.worker), parent=self
        )
        self._action_thread.done.connect(self._on_reload_vcgt_done)
        self._action_thread.start()

    def _on_reload_vcgt_done(self, result: object) -> None:
        """Receive the reloaded display profile on the GUI thread.

        Args:
            result (object): The reloaded ``ICCProfile``, or an ``Exception``.
        """
        self._action_thread = None
        if isinstance(result, Exception):
            self.status.setText(f"{lang.getstr('error')}: {result}")
            return
        self._user_profile = result
        self.set_profile(result)

    # -- save --------------------------------------------------------------

    def _save_plot(self) -> None:
        """Save the current plot as an image (wx's generic ``SaveFile``)."""
        if self._profile is None:
            return
        import pyqtgraph.exporters as pg_exporters

        mode_label = self.mode_combo.currentText()
        base = os.path.splitext(
            os.path.basename(self._profile.filename or lang.getstr("unnamed"))
        )[0]
        default_dir, _ = get_verified_path("last_filedialog_path")
        default_path = os.path.join(default_dir, f"{mode_label} {base}.png")
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("save_as"),
            default_path,
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp);;XPM (*.xpm);;XBM (*.xbm)",
        )
        if not path:
            return
        setcfg("last_filedialog_path", path)
        try:
            exporter = pg_exporters.ImageExporter(self.plot.getPlotItem())
            exporter.export(path)
        except Exception as exception:  # noqa: BLE001
            message_box.critical(self, self.window().windowTitle(), str(exception))

    def _save_cal(self) -> None:
        """Save the displayed vcgt as an Argyll ``.cal`` file."""
        if self._profile is None:
            return
        from DisplayCAL.argyll_cgats import vcgt_to_cal

        base = os.path.splitext(
            os.path.basename(self._profile.filename or lang.getstr("unnamed"))
        )[0]
        default_dir, _ = get_verified_path("last_filedialog_path")
        default_path = os.path.join(default_dir, f"{base}.cal")
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, lang.getstr("save_as"), default_path, "CAL (*.cal)"
        )
        if not path:
            return
        setcfg("last_filedialog_path", path)
        try:
            vcgt_to_cal(self._profile).write(path)
        except Exception as exception:  # noqa: BLE001
            message_box.critical(self, self.window().windowTitle(), str(exception))

    # -- per-monitor auto-follow -------------------------------------------

    def follow_display(self, display_no: int) -> None:
        """Reload for the display ``display_no`` (the window moved onto it).

        Mirrors ``LUTFrame.move_handler``/``load_lut``: shows the live LUT if
        "show actual LUT" is on, else that display's profile.

        Args:
            display_no (int): The Argyll display index (0-based) the
                standalone window is now on.
        """
        if self.actual_lut_check.isChecked():
            self._on_actual_lut_toggled(True)
            return
        profile = get_display_profile(display_no)
        if profile is not None:
            self._user_profile = profile
            self.set_profile(profile)


class CurveViewerWindow(BaseWindow):
    """Standalone window wrapping :class:`CurvePanel` with file drop/scripting."""

    def __init__(self) -> None:
        super().__init__(
            name="curve-viewer",
            title=lang.getstr("calibration.lut_viewer.title"),
            icon_name=f"{APPNAME}-curve-viewer".lower(),
        )
        self.panel = CurvePanel(self)
        self.panel.profile_changed.connect(self._on_profile_changed)
        self.setCentralWidget(self.panel)
        self.resize(820, 720)

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(PROFILE_SUFFIXES, self.load_profile),
            parent=self,
        )
        self.droptarget.install_on(self)
        self.init_menubar()

        self._current_geometry: tuple[int, int, int, int] | None = None

    # -- per-monitor auto-follow --------------------------------------------

    def _current_display_geometry(self) -> tuple[int, int, int, int] | None:
        """Return the ``(x, y, w, h)`` pixel geometry of the window's screen.

        Returns:
            tuple[int, int, int, int] | None: The geometry, or ``None`` if no
                screen could be resolved.
        """
        handle = self.windowHandle()
        screen = handle.screen() if handle is not None else None
        screen = screen or QApplication.primaryScreen()
        if screen is None:
            return None
        geo = screen.geometry()
        return (geo.x(), geo.y(), geo.width(), geo.height())

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        """Record the initial screen geometry so the first move is a no-op."""
        super().showEvent(event)
        self._current_geometry = self._current_display_geometry()

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802 (Qt override)
        """Reload the display's profile whenever the window moves to another screen.

        Mirrors ``LUTFrame.move_handler``: dragging the window onto a
        different physical display re-points ``display.number`` and reloads
        that display's profile (or, if "show actual LUT" is on, its live LUT).

        Args:
            event (QMoveEvent): The Qt move event.
        """
        super().moveEvent(event)
        if not self.isVisible() or config.is_ui_native_wayland():
            return
        geometry = self._current_display_geometry()
        if geometry is None or geometry == self._current_geometry:
            return
        self._current_geometry = geometry
        display_no = get_argyll_display_number(geometry)
        if display_no is None or is_virtual_display(display_no):
            return
        setcfg("display.number", display_no + 1)
        self.panel.follow_display(display_no)

    def _on_profile_changed(self, profile: ICCProfile) -> None:
        """Update the window title to reflect the displayed profile.

        Args:
            profile (ICCProfile): The newly displayed profile.
        """
        self.setWindowTitle(
            f"{lang.getstr('calibration.lut_viewer.title')} — "
            f"{profile.getDescription()}"
        )

    def load_profile(self, path: str) -> None:
        """Load an ICC profile or ``.cal`` file at ``path``.

        Args:
            path (str): Path to an ``.icc``/``.icm`` profile or ``.cal`` file.
        """
        self.panel.load_profile(path)

    # -- scripting ---------------------------------------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's file-opening commands.
        """
        return [
            *self.get_common_commands(),
            "curve-viewer [filename]",
            "load <filename>",
        ]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"``, ``"fail"`` or ``"invalid"``.
        """
        return self.open_files_command(data, "curve-viewer")


def main() -> int:
    """Entry point for the Qt curve viewer.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("curve-viewer")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = CurveViewerWindow()
    app.top_window = window
    window.show()
    window.listen()

    profiles = [a for a in sys.argv[1:] if os.path.isfile(a)]
    window.load_profile(profiles[0] if profiles else get_data_path("ref/sRGB.icm"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
