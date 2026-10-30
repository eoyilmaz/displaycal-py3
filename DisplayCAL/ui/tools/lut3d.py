"""3D LUT maker — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_lut_3d_frame` (the ``3DLUT-maker`` tool).
It builds a 3D LUT that maps a source colorspace (input profile) through to a
display (output profile), optionally via an abstract profile, driving Argyll
``collink`` through :meth:`DisplayCAL.worker.Worker.create_3dlut`.

Notable differences versus the wx version:

* Controls are built directly with Qt layouts instead of the ``3dlut.xrc``
  resource. The large :class:`DisplayCAL.wx_lut_3d_frame.LUT3DMixin` is shared
  with the (still-wx) main window; rather than move it, the standalone-tool
  behaviour is reimplemented here against the binding-agnostic backend
  (:mod:`DisplayCAL.config`, :mod:`DisplayCAL.colormath`,
  :mod:`DisplayCAL.icc_profile`, the worker), mirroring how
  :mod:`DisplayCAL.ui.tools.synth_profile` inlined the HDR roll-off controls.
* Because this is always the standalone window (never the embedded main-window
  tab), the ``isinstance(self, LUT3DFrame)`` / ``self.Parent`` branches of the
  mixin collapse away, and the main-window-only paths of ``lut3d_create_handler``
  (copying an existing LUT, the non-linear videoLUT warning) are dropped.
* The Argyll ``collink`` run is executed on a small :class:`QThread`
  (:class:`_CreateThread`) with an indeterminate progress dialog, instead of the
  heavyweight :meth:`DisplayCAL.worker.Worker.start` progress machinery.
"""

from __future__ import annotations

import os
import sys
from functools import partial

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import colormath, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll_names import VIDEO_ENCODINGS
from DisplayCAL.config import (
    DEFAULTS,
    PROFILE_EXT,
    get_data_path,
    get_verified_path,
    getcfg,
    setcfg,
)
from DisplayCAL.icc_profile import (
    CurveType,
    DictType,
    ICCProfile,
    ICCProfileInvalidError,
    LUT16Type,
    VideoCardGammaType,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_os import waccess
from DisplayCAL.worker import Worker, get_current_profile_path

#: File suffixes accepted for the profile controls / drag-and-drop.
PROFILE_SUFFIXES = (".icc", ".icm")

#: Tone-curve chooser labels, in control order (mirrors ``lut3d_setup_language``).
TONE_CURVE_ITEMS = (
    "Gamma 2.2",  # 0 - pure power gamma 2.2
    "trc.rec1886",  # 1 - BT.1886
    "trc.smpte2084.hardclip",  # 2
    "trc.smpte2084.rolloffclip",  # 3
    "trc.hlg",  # 4 - Hybrid Log-Gamma
    "custom",  # 5 - custom gamma
)

#: Built-in content colorspaces offered by the content-colorspace chooser.
CONTENT_COLORSPACE_NAMES = ["Rec. 2020", "DCI P3 D65", "Rec. 709"]


class _GuardContext:
    """Suppress re-entrant control-change handlers while active.

    Qt (unlike wx ``FloatSpin``/``Slider``) emits ``valueChanged`` / ``toggled``
    from programmatic ``setValue`` / ``setChecked``. While this context is
    active, :attr:`LUT3DWindow._updating` is truthy so the value-changed slots
    return early instead of recursing when the bulk ``update_*`` methods set
    control values. It saves and restores the previous flag so nesting is safe.

    Args:
        window (LUT3DWindow): The window whose update guard to toggle.
    """

    def __init__(self, window: LUT3DWindow) -> None:
        self._window = window

    def __enter__(self) -> None:
        self._prev = self._window._updating
        self._window._updating = True

    def __exit__(self, *exc) -> None:
        self._window._updating = self._prev


class _CreateThread(QThread):
    """Run :meth:`LUT3DWindow.create_3dlut` off the GUI thread.

    Args:
        window (LUT3DWindow): The owning window (provides ``create_3dlut``).
        args (tuple): Positional arguments for ``create_3dlut``.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with ``True`` on success or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self,
        window: LUT3DWindow,
        args: tuple,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._args = args

    def run(self) -> None:
        try:
            result = self._window.create_3dlut(*self._args)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _ProfileBrowse(QWidget):
    """An editable path combo box plus a browse button.

    Qt stand-in for wx ``FileBrowseButtonWithHistory``: an editable combo box
    (the drop-down keeps the recently-used paths as history) followed by a
    browse button. The current value is the combo's edit text.

    Args:
        dialog_title (str): Title for the file-open dialog.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted when the path changes (browse, history pick or typed entry).
    changed = Signal()

    def __init__(self, dialog_title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._current_path = ""
        self._committed_text = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.NoInsert)
        self._combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._combo.activated.connect(self._on_activated)
        self._combo.lineEdit().editingFinished.connect(self._on_edit_finished)
        layout.addWidget(self._combo, 1)
        self._btn = QPushButton("…")
        self._btn.setFixedWidth(32)
        self._btn.clicked.connect(self._on_browse)
        layout.addWidget(self._btn)

    def path(self) -> str:
        """Return the current path.

        Returns:
            str: The current path (may be empty).
        """
        return self._current_path

    @staticmethod
    def _display_name(path: str) -> str:
        """Return a friendly display name for a path, wx ``GetName`` parity.

        Args:
            path (str): The file path to get the name for.

        Returns:
            str: The ICC profile description if available, else the file's
                base name, translated.
        """
        name = None
        if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
            try:
                profile = ICCProfile(path)
            except (OSError, ICCProfileInvalidError):
                pass
            else:
                name = profile.getDescription()
        if not name:
            name = os.path.basename(path)
        return lang.getstr(name)

    def set_history(self, paths: list[str]) -> None:
        """Seed the combo's drop-down list without changing the current text.

        Each entry is shown by its friendly profile name (data holds the
        real path), matching wx's ``SetHistory``/``GetName``.

        Args:
            paths (list[str]): Paths to pre-populate the history with.
        """
        current = self._combo.currentText()
        for path in paths:
            if self._combo.findData(path) == -1:
                self._combo.addItem(self._display_name(path), path)
        self._combo.setEditText(current)

    def set_path(self, path: str | None) -> None:
        """Set the current path without emitting :attr:`changed`.

        The combo shows the friendly profile name for ``path`` (wx parity);
        :meth:`path` keeps returning the real path regardless of what is
        displayed.

        Args:
            path (str | None): The path to show (``None`` clears the field).
        """
        path = path or ""
        if path and self._combo.findData(path) == -1:
            self._combo.addItem(self._display_name(path), path)
        self._current_path = path
        self._committed_text = self._display_name(path) if path else ""
        self._combo.setEditText(self._committed_text)

    def _on_activated(self, index: int) -> None:
        path = self._combo.itemData(index)
        if path is None:
            path = self._combo.currentText()
        self._current_path = path
        self._committed_text = self._display_name(path) if path else ""
        self._combo.setEditText(self._committed_text)
        self.changed.emit()

    def _on_edit_finished(self) -> None:
        # editingFinished also fires on focus-out without changes; only react
        # to an actual edit, mirroring the wx changeCallback. A typed value
        # is treated as a literal path (there is no name to resolve it from
        # until it is committed).
        text = self._combo.currentText()
        if text == self._committed_text:
            return
        if text and self._combo.findData(text) == -1:
            self._combo.addItem(self._display_name(text), text)
        self._current_path = text
        self._committed_text = self._display_name(text) if text else ""
        self._combo.setEditText(self._committed_text)
        self.changed.emit()

    def _on_browse(self) -> None:
        default_dir = os.path.dirname(self.path()) if self.path() else ""
        wildcard = f"{lang.getstr('filetype.icc')} (*.icc *.icm)"
        path, _ = file_dialog.get_open_file_name(
            self, self._dialog_title, default_dir, wildcard
        )
        if path:
            self.set_path(path)
            self.changed.emit()


class LUT3DWindow(BaseWindow):
    """Window for creating 3D LUTs from an input and output profile."""

    def __init__(self) -> None:
        super().__init__(
            name="lut3dframe",
            title=lang.getstr("3dlut.frame.title"),
            icon_name=f"{APPNAME}-3DLUT-maker".lower(),
        )
        self.worker = Worker()
        self.worker.set_argyll_version("collink")
        self._thread: _CreateThread | None = None
        self._progress: QProgressDialog | None = None
        self._updating = False

        # Profile lookup blackpoints (see the wx frame). XYZbpout starts
        # slightly above zero so the output-offset controls show if no output
        # profile is selected yet.
        self.XYZbpin = [0.0, 0.0, 0.0]
        self.XYZbpout = [0.001, 0.001, 0.001]
        self.input_profile: ICCProfile | None = None
        self.output_profile: ICCProfile | None = None

        self.trc_gamma_types_ab = {0: "b", 1: "B"}
        self.trc_gamma_types_ba = {"b": 0, "B": 1}

        self._build_ui()
        self.setup_language()

        for which in ("input", "abstract", "output"):
            ctrl = getattr(self, f"{which}_profile_ctrl")
            ctrl.changed.connect(getattr(self, f"{which}_profile_ctrl_handler"))
            droptarget = FileDropTarget(
                drophandlers=dict.fromkeys(
                    PROFILE_SUFFIXES, getattr(self, f"{which}_drop_handler")
                ),
                parent=self,
            )
            droptarget.install_on(ctrl)

        self.update_controls()
        self.restore_position()

    def _guard(self) -> _GuardContext:
        """Return a context manager that suppresses re-entrant handlers.

        Returns:
            _GuardContext: A context manager toggling :attr:`_updating`.
        """
        return _GuardContext(self)

    # -- UI construction ---------------------------------------------------

    def _spin(
        self,
        minimum: float,
        maximum: float,
        increment: float,
        digits: int,
        width: int = 115,
    ) -> QDoubleSpinBox:
        """Create a configured float spin box.

        Args:
            minimum (float): Minimum value.
            maximum (float): Maximum value.
            increment (float): Single-step increment.
            digits (int): Number of displayed decimal places.
            width (int): Fixed width in pixels.

        Returns:
            QDoubleSpinBox: The configured spin box.
        """
        spin = QDoubleSpinBox()
        spin.setDecimals(digits)
        spin.setRange(minimum, maximum)
        spin.setSingleStep(increment)
        spin.setKeyboardTracking(False)
        spin.setFixedWidth(width)
        return spin

    def _build_ui(self) -> None:
        """Build the scrollable 2-column control grid and bottom button bar."""
        panel = QWidget()
        self._grid = QGridLayout(panel)
        self._grid.setContentsMargins(12, 12, 12, 12)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)
        self._grid.setColumnStretch(1, 1)
        self._row = 0

        # Row: input profile.
        self.input_profile_ctrl = _ProfileBrowse(lang.getstr("3dlut.input.profile"))
        self.input_profile_ctrl.set_history(get_data_path("ref", r"\.(icc|icm)$") or [])
        self._add_row(
            QLabel(lang.getstr("3dlut.input.profile")), self.input_profile_ctrl
        )

        # Row: tone curve + HDR + content colorspace + black offset block.
        self.lut3d_trc_label = QLabel(lang.getstr("trc"))
        self._add_row(self.lut3d_trc_label, self._build_trc_block())

        # Row: abstract profile.
        self.abstract_profile_cb = QCheckBox(lang.getstr("3dlut.use_abstract_profile"))
        self.abstract_profile_cb.toggled.connect(self.use_abstract_profile_ctrl_handler)
        self.abstract_profile_ctrl = _ProfileBrowse(
            lang.getstr("3dlut.use_abstract_profile")
        )
        self._add_row(self.abstract_profile_cb, self.abstract_profile_ctrl)

        # Row: output profile + "current" button.
        self.output_profile_label = QLabel(lang.getstr("output.profile"))
        output_box = QWidget()
        output_layout = QHBoxLayout(output_box)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_profile_ctrl = _ProfileBrowse(lang.getstr("output.profile"))
        output_layout.addWidget(self.output_profile_ctrl, 1)
        self.output_profile_current_btn = QPushButton(lang.getstr("profile.current"))
        self.output_profile_current_btn.clicked.connect(
            self.output_profile_current_ctrl_handler
        )
        output_layout.addWidget(self.output_profile_current_btn)
        self._add_row(self.output_profile_label, output_box)

        # Row: apply calibration.
        self.lut3d_apply_cal_cb = QCheckBox(lang.getstr("apply_cal"))
        self.lut3d_apply_cal_cb.setEnabled(False)
        self.lut3d_apply_cal_cb.toggled.connect(self.lut3d_apply_cal_ctrl_handler)
        self._add_row(None, self.lut3d_apply_cal_cb)

        # Rows: gamut mapping mode.
        self.gamut_mapping_mode = QLabel(lang.getstr("gamut_mapping.mode"))
        self.gamut_mapping_inverse_a2b = QRadioButton(
            lang.getstr("gamut_mapping.mode.inverse_a2b")
        )
        self.gamut_mapping_b2a = QRadioButton(lang.getstr("gamut_mapping.mode.b2a"))
        self._gamut_group = QButtonGroup(self)
        self._gamut_group.addButton(self.gamut_mapping_inverse_a2b)
        self._gamut_group.addButton(self.gamut_mapping_b2a)
        self.gamut_mapping_inverse_a2b.toggled.connect(
            self.lut3d_gamut_mapping_mode_handler
        )
        self._add_row(self.gamut_mapping_mode, self.gamut_mapping_inverse_a2b)
        self._add_row(None, self.gamut_mapping_b2a)

        # Row: rendering intent.
        self.lut3d_rendering_intent_label = QLabel(lang.getstr("rendering_intent"))
        self.lut3d_rendering_intent_ctrl = QComboBox()
        self.lut3d_rendering_intent_ctrl.activated.connect(
            self.lut3d_rendering_intent_ctrl_handler
        )
        self._add_row(
            self.lut3d_rendering_intent_label, self.lut3d_rendering_intent_ctrl
        )

        # Row: format + HDR display mode.
        format_box = QWidget()
        format_layout = QHBoxLayout(format_box)
        format_layout.setContentsMargins(0, 0, 0, 0)
        self.lut3d_format_ctrl = QComboBox()
        self.lut3d_format_ctrl.activated.connect(self.lut3d_format_ctrl_handler)
        format_layout.addWidget(self.lut3d_format_ctrl, 1)
        self.lut3d_hdr_display_ctrl = QComboBox()
        self.lut3d_hdr_display_ctrl.activated.connect(self.lut3d_hdr_display_handler)
        format_layout.addWidget(self.lut3d_hdr_display_ctrl)
        self._add_row(QLabel(lang.getstr("3dlut.format")), format_box)

        # Rows: encoding input/output.
        self.encoding_input_label = QLabel(lang.getstr("3dlut.encoding.input"))
        self.encoding_input_ctrl = QComboBox()
        self.encoding_input_ctrl.activated.connect(
            self.lut3d_encoding_input_ctrl_handler
        )
        self._add_row(self.encoding_input_label, self.encoding_input_ctrl)
        self.encoding_output_label = QLabel(lang.getstr("3dlut.encoding.output"))
        self.encoding_output_ctrl = QComboBox()
        self.encoding_output_ctrl.activated.connect(
            self.lut3d_encoding_output_ctrl_handler
        )
        self._add_row(self.encoding_output_label, self.encoding_output_ctrl)

        # Row: size.
        self.lut3d_size_label = QLabel(lang.getstr("3dlut.size"))
        self.lut3d_size_ctrl = QComboBox()
        self.lut3d_size_ctrl.activated.connect(self.lut3d_size_ctrl_handler)
        self._add_row(self.lut3d_size_label, self.lut3d_size_ctrl)

        # Rows: bit depth input/output.
        self.lut3d_bitdepth_input_label = QLabel(lang.getstr("3dlut.bitdepth.input"))
        self.lut3d_bitdepth_input_ctrl = QComboBox()
        self.lut3d_bitdepth_input_ctrl.activated.connect(
            self.lut3d_bitdepth_input_ctrl_handler
        )
        self._add_row(self.lut3d_bitdepth_input_label, self.lut3d_bitdepth_input_ctrl)
        self.lut3d_bitdepth_output_label = QLabel(lang.getstr("3dlut.bitdepth.output"))
        self.lut3d_bitdepth_output_ctrl = QComboBox()
        self.lut3d_bitdepth_output_ctrl.activated.connect(
            self.lut3d_bitdepth_output_ctrl_handler
        )
        self._add_row(self.lut3d_bitdepth_output_label, self.lut3d_bitdepth_output_ctrl)

        self._grid.setRowStretch(self._row, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._build_button_bar())
        self.setCentralWidget(central)
        self.resize(680, 640)

    def _add_row(self, left: QWidget | None, right: QWidget) -> None:
        """Add a label/control pair to the main 2-column grid.

        Args:
            left (QWidget | None): The left-column widget, or ``None`` to leave
                the label cell empty (mirrors the wx spacer rows).
            right (QWidget): The right-column control.
        """
        if left is not None:
            self._grid.addWidget(left, self._row, 0, Qt.AlignVCenter)
        self._grid.addWidget(right, self._row, 1)
        self._row += 1

    def _build_trc_block(self) -> QWidget:
        """Build the tone-curve / HDR / content-colorspace / black-offset block.

        Returns:
            QWidget: The container widget for the whole TRC block (the wx
            single-column sub-sizer in the "trc" row).
        """
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # -- apply-mode radios ------------------------------------------------
        self._trc_apply_group = QButtonGroup(self)

        none_row = QWidget()
        none_layout = QHBoxLayout(none_row)
        none_layout.setContentsMargins(0, 0, 0, 0)
        self.lut3d_trc_apply_none_ctrl = QRadioButton(lang.getstr("unmodified"))
        self.lut3d_trc_apply_none_ctrl.toggled.connect(
            self.lut3d_trc_apply_ctrl_handler
        )
        self._trc_apply_group.addButton(self.lut3d_trc_apply_none_ctrl)
        none_layout.addWidget(self.lut3d_trc_apply_none_ctrl)
        self.lut3d_input_value_clipping_bmp = QLabel()
        clipping_pixmap = get_theme_pixmap(16, "dialog-warning")
        if not clipping_pixmap.isNull():
            self.lut3d_input_value_clipping_bmp.setPixmap(clipping_pixmap)
        self.lut3d_input_value_clipping_bmp.setVisible(False)
        none_layout.addWidget(self.lut3d_input_value_clipping_bmp)
        self.lut3d_input_value_clipping_label = QLabel(
            lang.getstr("warning.input_value_clipping")
        )
        self.lut3d_input_value_clipping_label.setStyleSheet("color: #F07F00")
        self.lut3d_input_value_clipping_label.setVisible(False)
        none_layout.addWidget(self.lut3d_input_value_clipping_label)
        none_layout.addStretch(1)
        layout.addWidget(none_row)

        self.lut3d_trc_apply_black_offset_ctrl = QRadioButton(
            lang.getstr("apply_black_output_offset")
        )
        self.lut3d_trc_apply_black_offset_ctrl.toggled.connect(
            self.lut3d_trc_apply_ctrl_handler
        )
        self._trc_apply_group.addButton(self.lut3d_trc_apply_black_offset_ctrl)
        layout.addWidget(self.lut3d_trc_apply_black_offset_ctrl)

        # -- apply-TRC radio + tone curve + gamma + peak luminance ------------
        trc_row = QWidget()
        trc_layout = QHBoxLayout(trc_row)
        trc_layout.setContentsMargins(0, 0, 0, 0)
        self.lut3d_trc_apply_ctrl = QRadioButton()
        self.lut3d_trc_apply_ctrl.toggled.connect(self.lut3d_trc_apply_ctrl_handler)
        self._trc_apply_group.addButton(self.lut3d_trc_apply_ctrl)
        trc_layout.addWidget(self.lut3d_trc_apply_ctrl)

        self.lut3d_trc_ctrl = QComboBox()
        self.lut3d_trc_ctrl.activated.connect(self.lut3d_trc_ctrl_handler)
        trc_layout.addWidget(self.lut3d_trc_ctrl)

        self.lut3d_trc_gamma_label = QLabel(lang.getstr("trc.gamma"))
        trc_layout.addWidget(self.lut3d_trc_gamma_label)
        self.lut3d_trc_gamma_ctrl = QComboBox()
        self.lut3d_trc_gamma_ctrl.setEditable(True)
        self.lut3d_trc_gamma_ctrl.addItems(["2.2", "2.4"])
        self.lut3d_trc_gamma_ctrl.setFixedWidth(80)
        self.lut3d_trc_gamma_ctrl.activated.connect(
            lambda _i: self.lut3d_trc_gamma_ctrl_handler()
        )
        self.lut3d_trc_gamma_ctrl.lineEdit().editingFinished.connect(
            self.lut3d_trc_gamma_ctrl_handler
        )
        trc_layout.addWidget(self.lut3d_trc_gamma_ctrl)

        self.lut3d_trc_gamma_type_ctrl = QComboBox()
        self.lut3d_trc_gamma_type_ctrl.activated.connect(
            self.lut3d_trc_gamma_type_ctrl_handler
        )
        trc_layout.addWidget(self.lut3d_trc_gamma_type_ctrl)

        self.lut3d_hdr_peak_luminance_label = QLabel(
            lang.getstr("display_peak_luminance")
        )
        trc_layout.addWidget(self.lut3d_hdr_peak_luminance_label)
        self.lut3d_hdr_peak_luminance_ctrl = self._spin(
            100.0, 10000.0, 1.0, 0, width=90
        )
        self.lut3d_hdr_peak_luminance_ctrl.valueChanged.connect(
            self.lut3d_hdr_peak_luminance_handler
        )
        trc_layout.addWidget(self.lut3d_hdr_peak_luminance_ctrl)
        self.lut3d_hdr_peak_luminance_ctrl_label = QLabel("cd/m²")
        trc_layout.addWidget(self.lut3d_hdr_peak_luminance_ctrl_label)
        trc_layout.addStretch(1)
        layout.addWidget(trc_row)

        layout.addWidget(self._build_hdr_rows())
        layout.addWidget(self._build_black_offset_row())
        return block

    def _build_hdr_rows(self) -> QWidget:
        """Build the HDR saturation/hue/mastering/content-colorspace rows.

        Returns:
            QWidget: The HDR rows container.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 0, 0, 0)
        layout.setSpacing(6)

        # Saturation slider.
        self.hdr_sat_row = QWidget()
        sat_layout = QHBoxLayout(self.hdr_sat_row)
        sat_layout.setContentsMargins(0, 0, 0, 0)
        sat_layout.addWidget(QLabel(lang.getstr("preserve_luminance")))
        self.lut3d_hdr_sat_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_hdr_sat_ctrl.setRange(0, 100)
        self.lut3d_hdr_sat_ctrl.setFixedWidth(128)
        self.lut3d_hdr_sat_ctrl.valueChanged.connect(self.lut3d_hdr_sat_ctrl_handler)
        sat_layout.addWidget(self.lut3d_hdr_sat_ctrl)
        sat_layout.addWidget(QLabel(lang.getstr("preserve_saturation")))
        self.lut3d_hdr_sat_val = QLabel("")
        sat_layout.addWidget(self.lut3d_hdr_sat_val)
        sat_layout.addStretch(1)
        layout.addWidget(self.hdr_sat_row)

        # Hue slider + spin.
        self.hdr_hue_row = QWidget()
        hue_layout = QHBoxLayout(self.hdr_hue_row)
        hue_layout.setContentsMargins(0, 0, 0, 0)
        hue_layout.addWidget(QLabel(lang.getstr("preserve_hue")))
        self.lut3d_hdr_hue_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_hdr_hue_ctrl.setRange(0, 100)
        self.lut3d_hdr_hue_ctrl.setFixedWidth(128)
        self.lut3d_hdr_hue_ctrl.valueChanged.connect(self._on_hdr_hue_slider)
        hue_layout.addWidget(self.lut3d_hdr_hue_ctrl)
        self.lut3d_hdr_hue_intctrl = QSpinBox()
        self.lut3d_hdr_hue_intctrl.setRange(0, 100)
        self.lut3d_hdr_hue_intctrl.setSuffix(" %")
        self.lut3d_hdr_hue_intctrl.valueChanged.connect(self._on_hdr_hue_spin)
        hue_layout.addWidget(self.lut3d_hdr_hue_intctrl)
        hue_layout.addStretch(1)
        layout.addWidget(self.hdr_hue_row)

        # Mastering display min luminance.
        self.hdr_minmll_row = self._labeled_row(
            "mastering_display_black_luminance", "lut3d_hdr_minmll_label"
        )
        self.lut3d_hdr_minmll_ctrl = self._spin(0.0, 0.1, 0.0001, 4, width=115)
        self.lut3d_hdr_minmll_ctrl.valueChanged.connect(self.lut3d_hdr_minmll_handler)
        self.hdr_minmll_row.layout().addWidget(self.lut3d_hdr_minmll_ctrl)
        self.hdr_minmll_row.layout().addWidget(QLabel("cd/m²"))
        self.hdr_minmll_row.layout().addStretch(1)
        layout.addWidget(self.hdr_minmll_row)

        # Mastering display peak luminance + alt-clip.
        self.hdr_maxmll_row = self._labeled_row(
            "mastering_display_peak_luminance", "lut3d_hdr_maxmll_label"
        )
        self.lut3d_hdr_maxmll_ctrl = self._spin(100.0, 10000.0, 1.0, 0, width=115)
        self.lut3d_hdr_maxmll_ctrl.valueChanged.connect(self.lut3d_hdr_maxmll_handler)
        self.hdr_maxmll_row.layout().addWidget(self.lut3d_hdr_maxmll_ctrl)
        self.hdr_maxmll_row.layout().addWidget(QLabel("cd/m²"))
        self.lut3d_hdr_maxmll_alt_clip_cb = QCheckBox(lang.getstr("adjust_rolloff"))
        self.lut3d_hdr_maxmll_alt_clip_cb.toggled.connect(
            self.lut3d_hdr_maxmll_alt_clip_handler
        )
        self.hdr_maxmll_row.layout().addWidget(self.lut3d_hdr_maxmll_alt_clip_cb)
        self.hdr_maxmll_row.layout().addStretch(1)
        layout.addWidget(self.hdr_maxmll_row)

        # Diffuse-white readout.
        self.hdr_diffuse_white_row = self._labeled_row(
            "3dlut.hdr.rolloff.diffuse_white", "lut3d_hdr_diffuse_white_label"
        )
        self.lut3d_hdr_diffuse_white_txt = QLabel("")
        self.hdr_diffuse_white_row.layout().addWidget(self.lut3d_hdr_diffuse_white_txt)
        self.hdr_diffuse_white_row.layout().addWidget(QLabel("cd/m²"))
        self.hdr_diffuse_white_row.layout().addStretch(1)
        layout.addWidget(self.hdr_diffuse_white_row)

        # Ambient luminance (HLG).
        self.hdr_ambient_row = self._labeled_row(
            "calibration.ambient_viewcond_adjust", "lut3d_hdr_ambient_luminance_label"
        )
        self.lut3d_hdr_ambient_luminance_ctrl = self._spin(
            0.01, 10000.0, 0.01, 2, width=115
        )
        self.lut3d_hdr_ambient_luminance_ctrl.valueChanged.connect(
            self.lut3d_hdr_ambient_luminance_handler
        )
        self.hdr_ambient_row.layout().addWidget(self.lut3d_hdr_ambient_luminance_ctrl)
        self.hdr_ambient_row.layout().addWidget(QLabel("cd/m²"))
        self.hdr_ambient_row.layout().addStretch(1)
        layout.addWidget(self.hdr_ambient_row)

        # System gamma readout (HLG).
        self.hdr_system_gamma_row = self._labeled_row(
            "3dlut.hdr.system_gamma", "lut3d_hdr_system_gamma_label"
        )
        self.lut3d_hdr_system_gamma_txt = QLabel("")
        self.hdr_system_gamma_row.layout().addWidget(self.lut3d_hdr_system_gamma_txt)
        self.hdr_system_gamma_row.layout().addStretch(1)
        layout.addWidget(self.hdr_system_gamma_row)

        # Content colorspace chooser.
        self.content_colorspace_row = self._labeled_row(
            "3dlut.content.colorspace", "lut3d_content_colorspace_label"
        )
        self.lut3d_content_colorspace_ctrl = QComboBox()
        self.lut3d_content_colorspace_ctrl.activated.connect(
            self.lut3d_content_colorspace_handler
        )
        self.content_colorspace_row.layout().addWidget(
            self.lut3d_content_colorspace_ctrl
        )
        self.content_colorspace_row.layout().addStretch(1)
        layout.addWidget(self.content_colorspace_row)

        # Content colorspace primaries grid.
        layout.addWidget(self._build_content_colorspace_grid())
        return container

    def _build_content_colorspace_grid(self) -> QWidget:
        """Build the white/red/green/blue x/y content-colorspace spin grid.

        Returns:
            QWidget: The primaries grid container.
        """
        self.content_colorspace_grid = QWidget()
        grid = QGridLayout(self.content_colorspace_grid)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(8)
        for r, color in enumerate(("white", "red", "green", "blue")):
            row_label = QLabel(lang.getstr(color))
            setattr(self, f"lut3d_content_colorspace_{color[0]}_label", row_label)
            grid.addWidget(row_label, r, 0, Qt.AlignVCenter)
            for c, coord in enumerate("xy"):
                spin = self._spin(-1.0, 1.0, 0.0001, 4, width=100)
                setattr(self, f"lut3d_content_colorspace_{color}_{coord}", spin)
                spin.valueChanged.connect(
                    partial(self._on_content_colorspace_xy, color, coord)
                )
                coord_label = QLabel(coord)
                setattr(
                    self,
                    f"lut3d_content_colorspace_{color}_{coord}_label",
                    coord_label,
                )
                grid.addWidget(coord_label, r, c * 2 + 1, Qt.AlignVCenter)
                grid.addWidget(spin, r, c * 2 + 2)
        grid.setColumnStretch(5, 1)
        return self.content_colorspace_grid

    def _labeled_row(self, label_key: str, attr: str) -> QWidget:
        """Create a horizontal row starting with a named label.

        Args:
            label_key (str): Localization key for the leading label.
            attr (str): Attribute name to bind the label to.

        Returns:
            QWidget: The row widget (an :class:`QHBoxLayout` to append to).
        """
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(lang.getstr(label_key))
        setattr(self, attr, label)
        row_layout.addWidget(label)
        return row

    def _build_black_offset_row(self) -> QWidget:
        """Build the black output offset slider + spin row.

        Returns:
            QWidget: The black-output-offset row widget.
        """
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.lut3d_trc_black_output_offset_label = QLabel(
            lang.getstr("calibration.black_output_offset")
        )
        layout.addWidget(self.lut3d_trc_black_output_offset_label)
        self.lut3d_trc_black_output_offset_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_trc_black_output_offset_ctrl.setRange(0, 100)
        self.lut3d_trc_black_output_offset_ctrl.setFixedWidth(128)
        self.lut3d_trc_black_output_offset_ctrl.valueChanged.connect(
            self._on_black_offset_slider
        )
        layout.addWidget(self.lut3d_trc_black_output_offset_ctrl)
        self.lut3d_trc_black_output_offset_intctrl = QSpinBox()
        self.lut3d_trc_black_output_offset_intctrl.setRange(0, 100)
        self.lut3d_trc_black_output_offset_intctrl.setSuffix(" %")
        self.lut3d_trc_black_output_offset_intctrl.valueChanged.connect(
            self._on_black_offset_spin
        )
        layout.addWidget(self.lut3d_trc_black_output_offset_intctrl)
        layout.addStretch(1)
        return row

    def _build_button_bar(self) -> QWidget:
        """Build the bottom bar with the Create 3D LUT button.

        Returns:
            QWidget: The button-bar widget.
        """
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addStretch(1)
        self.lut3d_create_btn = QPushButton(lang.getstr("3dlut.create"))
        self.lut3d_create_btn.setEnabled(False)
        self.lut3d_create_btn.setDefault(True)
        self.lut3d_create_btn.clicked.connect(self.lut3d_create_handler)
        layout.addWidget(self.lut3d_create_btn)
        return bar

    # -- language / combo population ---------------------------------------

    def setup_language(self) -> None:
        """Populate the combo boxes and their key<->index maps."""
        self.lut3d_trc_ctrl.clear()
        self.lut3d_trc_ctrl.addItems([lang.getstr(item) for item in TONE_CURVE_ITEMS])

        self.trc_gamma_types_ab = {0: "b", 1: "B"}
        self.trc_gamma_types_ba = {"b": 0, "B": 1}
        self.lut3d_trc_gamma_type_ctrl.clear()
        self.lut3d_trc_gamma_type_ctrl.addItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )

        self.lut3d_content_colorspace_ctrl.clear()
        self.lut3d_content_colorspace_ctrl.addItems(
            [*CONTENT_COLORSPACE_NAMES, lang.getstr("custom")]
        )

        self.rendering_intents_ab = {}
        self.rendering_intents_ba = {}
        self.lut3d_rendering_intent_ctrl.clear()
        intents = list(config.VALID_VALUES["3dlut.rendering_intent"])
        if self.worker.argyll_version < [1, 8, 3] and "lp" in intents:
            intents.remove("lp")
        for i, ri in enumerate(intents):
            self.lut3d_rendering_intent_ctrl.addItem(lang.getstr("gamap.intents." + ri))
            self.rendering_intents_ab[i] = ri
            self.rendering_intents_ba[ri] = i

        self.lut3d_formats_ab = {}
        self.lut3d_formats_ba = {}
        self.lut3d_format_ctrl.clear()
        i = 0
        for file_format in config.VALID_VALUES["3dlut.format"]:
            if file_format != "madVR" or self.worker.argyll_version >= [1, 6]:
                self.lut3d_format_ctrl.addItem(
                    lang.getstr(f"3dlut.format.{file_format}")
                )
                self.lut3d_formats_ab[i] = file_format
                self.lut3d_formats_ba[file_format] = i
                i += 1

        self.lut3d_hdr_display_ctrl.clear()
        self.lut3d_hdr_display_ctrl.addItems(
            [
                lang.getstr(item)
                for item in ("3dlut.format.madVR.hdr_to_sdr", "3dlut.format.madVR.hdr")
            ]
        )

        self.lut3d_size_ab = {}
        self.lut3d_size_ba = {}
        self.lut3d_size_ctrl.clear()
        for i, size in enumerate(config.VALID_VALUES["3dlut.size"]):
            self.lut3d_size_ctrl.addItem("%sx%sx%s" % ((size,) * 3))
            self.lut3d_size_ab[i] = size
            self.lut3d_size_ba[size] = i

        self.lut3d_bitdepth_ab = {}
        self.lut3d_bitdepth_ba = {}
        self.lut3d_bitdepth_input_ctrl.clear()
        self.lut3d_bitdepth_output_ctrl.clear()
        for i, bitdepth in enumerate(config.VALID_VALUES["3dlut.bitdepth.input"]):
            self.lut3d_bitdepth_input_ctrl.addItem(str(bitdepth))
            self.lut3d_bitdepth_output_ctrl.addItem(str(bitdepth))
            self.lut3d_bitdepth_ab[i] = bitdepth
            self.lut3d_bitdepth_ba[bitdepth] = i

    def lut3d_setup_encoding_ctrl(self) -> None:
        """Populate the input/output encoding combos for the current format."""
        file_format = getcfg("3dlut.format")
        if file_format == "madVR":
            encodings = ["t"]
            DEFAULTS["3dlut.encoding.input"] = "t"
            DEFAULTS["3dlut.encoding.output"] = "t"
        else:
            encodings = ["n"] if file_format == "dcl" else list(VIDEO_ENCODINGS)
            DEFAULTS["3dlut.encoding.input"] = "n"
            DEFAULTS["3dlut.encoding.output"] = "n"
        if (
            self.worker.argyll_version >= [1, 7]
            and self.worker.argyll_version != [1, 7, 0, "_beta"]
            and file_format != "dcl"
        ):
            encodings.insert(2, "T")
        config.VALID_VALUES["3dlut.encoding.input"] = encodings
        config.VALID_VALUES["3dlut.encoding.output"] = [
            v for v in encodings if v not in ("T", "x", "X")
        ]
        self.encoding_input_ab = {}
        self.encoding_input_ba = {}
        self.encoding_output_ab = {}
        self.encoding_output_ba = {}
        self.encoding_input_ctrl.clear()
        self.encoding_output_ctrl.clear()
        for i, encoding in enumerate(config.VALID_VALUES["3dlut.encoding.input"]):
            self.encoding_input_ctrl.addItem(
                lang.getstr(f"3dlut.encoding.type_{encoding}")
            )
            self.encoding_input_ab[i] = encoding
            self.encoding_input_ba[encoding] = i
        for o, encoding in enumerate(config.VALID_VALUES["3dlut.encoding.output"]):
            self.encoding_output_ctrl.addItem(
                lang.getstr(f"3dlut.encoding.type_{encoding}")
            )
            self.encoding_output_ab[o] = encoding
            self.encoding_output_ba[encoding] = o

    # -- profile controls --------------------------------------------------

    def use_abstract_profile_ctrl_handler(self, _checked: bool = False) -> None:
        """Persist and apply the abstract-profile checkbox state."""
        if self._updating:
            return
        setcfg("3dlut.use_abstract_profile", int(self.abstract_profile_cb.isChecked()))
        self.abstract_profile_ctrl.setEnabled(
            bool(getcfg("3dlut.use_abstract_profile"))
        )

    def input_drop_handler(self, path: str) -> None:
        """Set the input profile from a dropped file.

        Args:
            path (str): The dropped profile path.
        """
        if not self.worker.is_working():
            self.input_profile_ctrl.set_path(path)
            self.set_profile("input")

    def abstract_drop_handler(self, path: str) -> None:
        """Set the abstract profile from a dropped file.

        Args:
            path (str): The dropped profile path.
        """
        if not self.worker.is_working():
            self.abstract_profile_ctrl.set_path(path)
            self.set_profile("abstract")

    def output_drop_handler(self, path: str) -> None:
        """Set the output profile from a dropped file.

        Args:
            path (str): The dropped profile path.
        """
        if not self.worker.is_working():
            self.output_profile_ctrl.set_path(path)
            self.set_profile("output")

    def input_profile_ctrl_handler(self, event: object = True) -> None:
        """Handle a change to the input-profile control.

        Args:
            event (object): Truthy when triggered by the user (not silent).
        """
        self.set_profile("input", silent=not event)

    def abstract_profile_ctrl_handler(self, event: object = True) -> None:
        """Handle a change to the abstract-profile control.

        Args:
            event (object): Truthy when triggered by the user (not silent).
        """
        self.set_profile("abstract", silent=not event)

    def output_profile_ctrl_handler(self, event: object = True) -> None:
        """Handle a change to the output-profile control.

        Args:
            event (object): Truthy when triggered by the user (not silent).
        """
        self.set_profile("output", silent=not event)

    def output_profile_current_ctrl_handler(self, _checked: bool = False) -> None:
        """Set the output profile to the currently installed display profile."""
        profile_path = get_current_profile_path(True, True)
        if profile_path and os.path.isfile(profile_path):
            self.output_profile_ctrl.set_path(profile_path)
            self.set_profile("output", profile_path or False)

    def set_profile_ctrl_path(self, which: str) -> None:
        """Reset a profile control's shown path from config.

        Args:
            which (str): One of ``"input"``, ``"abstract"``, ``"output"``.
        """
        getattr(self, f"{which}_profile_ctrl").set_path(
            getcfg(f"3dlut.{which}.profile")
        )

    def set_profile(
        self, which: str, profile_path: str | bool | None = None, silent: bool = False
    ) -> ICCProfile | None:
        """Validate and apply a profile for one of the profile controls.

        This is the standalone-window subset of the wx
        ``LUT3DFrame.set_profile`` (device-link input handling is preserved;
        the main-window branches are dropped).

        Args:
            which (str): One of ``"input"``, ``"abstract"``, ``"output"``.
            profile_path (str | bool | None): Only meaningful for ``"output"``.
            silent (bool): Suppress error dialogs when True.

        Returns:
            ICCProfile | None: The loaded profile, or ``None``.
        """
        path = getattr(self, f"{which}_profile_ctrl").path()
        if which == "output":
            if profile_path is None:
                profile_path = get_current_profile_path(True, True)
            self.output_profile_current_btn.setEnabled(
                self.output_profile_ctrl.isVisible()
                and bool(profile_path)
                and os.path.isfile(profile_path)
                and profile_path != path
            )
        if path:
            if not os.path.isfile(path):
                if not silent:
                    self._error(lang.getstr("file.missing", path))
                return None
            try:
                profile = ICCProfile(path)
            except ICCProfileInvalidError:
                if not silent:
                    self._error(f"{lang.getstr('profile.invalid')}\n{path}")
                return None
            except OSError as exception:
                if not silent:
                    self._error(str(exception))
                return None
            if (
                which in ("input", "output")
                and (
                    profile.profileClass not in (b"mntr", b"link", b"scnr", b"spac")
                    or profile.colorSpace != b"RGB"
                )
            ) or (
                which == "abstract"
                and (
                    profile.profileClass != b"abst"
                    or profile.colorSpace not in (b"Lab", b"XYZ")
                )
            ):
                self._error(
                    lang.getstr(
                        "profile.unsupported",
                        (
                            profile.profileClass.decode("utf-8"),
                            profile.colorSpace.decode("utf-8"),
                        ),
                    )
                )
                self.set_profile_ctrl_path(which)
                return None
            result = self._apply_valid_profile(which, profile, path, silent)
            if result is not False:
                return result
            self.set_profile_ctrl_path(which)
        elif which == "input":
            self.set_profile_ctrl_path(which)
            self.lut3d_update_encoding_controls()
        elif not silent:
            setattr(self, f"{which}_profile", None)
            setcfg(f"3dlut.{which}.profile", None)
            if which == "output":
                self.lut3d_apply_cal_cb.setEnabled(False)
                self.lut3d_create_btn.setEnabled(False)
        return None

    def _apply_valid_profile(
        self, which: str, profile: ICCProfile, path: str, silent: bool
    ) -> ICCProfile | None | bool:
        """Apply an already-validated profile and refresh dependent controls.

        Args:
            which (str): One of ``"input"``, ``"abstract"``, ``"output"``.
            profile (ICCProfile): The loaded, validated profile.
            path (str): The profile path.
            silent (bool): Suppress error dialogs when True.

        Returns:
            ICCProfile | None | bool: The applied profile, ``None`` when the
            output control is hidden (device-link input), or ``False`` on a
            recoverable lookup error (caller resets the control path).
        """
        if profile.profileClass == b"link":
            if which == "output":
                self.input_profile_ctrl.set_path(path)
                if getcfg("3dlut.output.profile") == path:
                    setcfg("3dlut.output.profile", None)
                self.output_profile_ctrl.set_path(getcfg("3dlut.output.profile"))
                self.set_profile("input", silent=silent)
                return None
            self._show_device_link_layout()
        elif which == "input":
            if (
                self.input_profile is None
                or getcfg("3dlut.input.profile") != profile.filename
            ):
                odata = self._lookup_blackpoint(profile)
                if odata is None:
                    return False
                self.XYZbpin = odata
            self._show_input_layout()
            self.input_profile = profile
            if not self.set_profile("output", silent=silent):
                self.update_linking_controls()
                self.lut3d_trc_apply_ctrl_handler()
        elif which == "output":
            if (
                self.output_profile is None
                or getcfg("3dlut.output.profile") != profile.filename
            ):
                odata = self._lookup_blackpoint(profile)
                if odata is None:
                    return False
                if odata[1]:
                    self.XYZbpout = odata
                else:
                    XYZbp = profile.get_chardata_bkpt()
                    self.XYZbpout = XYZbp if XYZbp else [0, 0, 0]
            self._show_output_layout(profile)
        setattr(self, f"{which}_profile", profile)
        if which == "output" and not self.output_profile_ctrl.isVisible():
            return None
        setcfg(f"3dlut.{which}.profile", profile.filename)
        self._update_create_enabled(profile)
        return profile

    def _lookup_blackpoint(self, profile: ICCProfile) -> list | None:
        """Look up a profile's XYZ blackpoint via ``xicclu``.

        Args:
            profile (ICCProfile): The profile to look up.

        Returns:
            list | None: The XYZ blackpoint, or ``None`` on error.
        """
        try:
            odata = self.worker.xicclu(profile, (0, 0, 0), pcs="x")
        except Exception as exception:  # noqa: BLE001
            self._error(str(exception))
            return None
        if len(odata) != 1 or len(odata[0]) != 3:
            self._error(f"Blackpoint is invalid: {odata}")
            return None
        return odata[0]

    def _show_device_link_layout(self) -> None:
        """Hide the output/abstract/gamut controls for a device-link input."""
        self.abstract_profile_cb.setChecked(False)
        self.abstract_profile_cb.setVisible(False)
        self.abstract_profile_ctrl.setVisible(False)
        self.output_profile_label.setVisible(False)
        self.output_profile_ctrl.setVisible(False)
        self.output_profile_current_btn.setVisible(False)
        self.lut3d_apply_cal_cb.setVisible(False)
        self.lut3d_trc_label.setVisible(False)
        self.lut3d_trc_apply_none_ctrl.setVisible(False)
        self.lut3d_input_value_clipping_label.setVisible(False)
        self.lut3d_trc_apply_black_offset_ctrl.setVisible(False)
        self.gamut_mapping_mode.setVisible(False)
        self.gamut_mapping_inverse_a2b.setVisible(False)
        self.gamut_mapping_b2a.setVisible(False)
        self.lut3d_show_encoding_controls(False)
        self.lut3d_show_trc_controls(False)
        self.lut3d_rendering_intent_label.setVisible(False)
        self.lut3d_rendering_intent_ctrl.setVisible(False)

    def _show_input_layout(self) -> None:
        """Show the controls relevant once a device input profile is set."""
        self.lut3d_trc_label.setVisible(True)
        self.lut3d_trc_apply_none_ctrl.setVisible(True)
        self.lut3d_trc_apply_black_offset_ctrl.setVisible(True)
        self.gamut_mapping_mode.setVisible(True)
        self.gamut_mapping_inverse_a2b.setVisible(True)
        self.gamut_mapping_b2a.setVisible(True)
        enable = bool(getcfg("3dlut.use_abstract_profile"))
        self.abstract_profile_cb.setChecked(enable)
        self.abstract_profile_cb.setVisible(True)
        self.abstract_profile_ctrl.setEnabled(enable)
        self.abstract_profile_ctrl.setVisible(True)
        self.output_profile_label.setVisible(True)
        self.output_profile_ctrl.setVisible(True)
        self.output_profile_current_btn.setVisible(True)
        self.lut3d_apply_cal_cb.setVisible(True)
        self.lut3d_show_encoding_controls()
        self.lut3d_update_encoding_controls()

    def _show_output_layout(self, profile: ICCProfile) -> None:
        """Enable output-dependent controls (apply-cal, B2A gamut mapping).

        Args:
            profile (ICCProfile): The output profile.
        """
        enable_apply_cal = isinstance(profile.tags.get("vcgt"), VideoCardGammaType)
        self.lut3d_apply_cal_cb.setChecked(
            enable_apply_cal and bool(getcfg("3dlut.output.profile.apply_cal"))
        )
        self.lut3d_apply_cal_cb.setEnabled(enable_apply_cal)
        self.gamut_mapping_inverse_a2b.setEnabled(True)
        allow_b2a_gamap = (
            "B2A0" in profile.tags
            and isinstance(profile.tags.B2A0, LUT16Type)
            and profile.tags.B2A0.clut_grid_steps >= 17
        )
        self.gamut_mapping_b2a.setEnabled(allow_b2a_gamap)
        if not allow_b2a_gamap:
            setcfg("3dlut.gamap.use_b2a", 0)
        self.update_linking_controls()
        self.lut3d_trc_apply_ctrl_handler()
        self.lut3d_rendering_intent_label.setVisible(True)
        self.lut3d_rendering_intent_ctrl.setVisible(True)

    def _update_create_enabled(self, profile: ICCProfile) -> None:
        """Enable the Create button when input+output profiles are valid.

        Args:
            profile (ICCProfile): The most recently applied profile.
        """
        self.lut3d_create_btn.setEnabled(
            bool(getcfg("3dlut.input.profile"))
            and os.path.isfile(getcfg("3dlut.input.profile"))
            and (
                (
                    bool(getcfg("3dlut.output.profile"))
                    and os.path.isfile(getcfg("3dlut.output.profile"))
                )
                or profile.profileClass == b"link"
            )
            and (
                getcfg("3dlut.format") != "madVR"
                or self.output_profile_ctrl.isVisible()
            )
        )

    def update_controls(self) -> None:
        """Load control values from config and refresh dependent state."""
        with self._guard():
            self.lut3d_create_btn.setEnabled(False)
            self.input_profile_ctrl.set_path(getcfg("3dlut.input.profile"))
            self.output_profile_ctrl.set_path(getcfg("3dlut.output.profile"))
            self.input_profile_ctrl_handler(None)
            enable = bool(getcfg("3dlut.use_abstract_profile"))
            self.abstract_profile_cb.setChecked(enable)
            self.abstract_profile_ctrl.set_path(getcfg("3dlut.abstract.profile"))
            self.abstract_profile_ctrl_handler(None)
            self.output_profile_ctrl_handler(None)
            self.lut3d_update_shared_controls()

    def update_linking_controls(self) -> None:
        """Update the TRC apply-mode radios from the input/output profiles."""
        with self._guard():
            self._update_linking_controls()

    def _update_linking_controls(self) -> None:
        """Body of :meth:`update_linking_controls` (guard applied by caller)."""
        self.gamut_mapping_inverse_a2b.setChecked(not getcfg("3dlut.gamap.use_b2a"))
        self.gamut_mapping_b2a.setChecked(bool(getcfg("3dlut.gamap.use_b2a")))
        profile = self.input_profile
        if (
            profile is not None
            and "rTRC" in profile.tags
            and "gTRC" in profile.tags
            and "bTRC" in profile.tags
            and profile.tags.rTRC == profile.tags.gTRC == profile.tags.bTRC
            and isinstance(profile.tags.rTRC, CurveType)
        ):
            tf = profile.tags.rTRC.get_transfer_function(outoffset=1.0)
            if getcfg("3dlut.input.profile") != profile.filename:
                setcfg(
                    "3dlut.apply_trc",
                    int(
                        tf[0][1] in (-240, -709)
                        or (tf[0][0].startswith("Gamma") and tf[1] >= 0.95)
                    ),
                )
                setcfg(
                    "3dlut.apply_black_offset",
                    int(
                        tf[0][1] not in (-240, -709)
                        and (not tf[0][0].startswith("Gamma") or tf[1] < 0.95)
                        and self.XYZbpin != self.XYZbpout
                    ),
                )
                if tf[0][0].startswith("Gamma") and tf[1] >= 0.95:
                    if not getcfg("3dlut.trc_gamma.backup", False):
                        setcfg("3dlut.trc_gamma.backup", getcfg("3dlut.trc_gamma"))
                    setcfg("3dlut.trc_gamma", round(tf[0][1], 2))
                elif getcfg("3dlut.trc_gamma.backup", False):
                    setcfg("3dlut.trc_gamma", getcfg("3dlut.trc_gamma.backup"))
                    setcfg("3dlut.trc_gamma.backup", None)
            self.lut3d_trc_apply_black_offset_ctrl.setEnabled(
                tf[0][1] not in (-240, -709) and self.XYZbpin != self.XYZbpout
            )
            self.lut3d_update_trc_controls()
        elif profile is not None and (
            isinstance(profile.tags.get("A2B0"), LUT16Type)
            and isinstance(profile.tags.get("A2B1", LUT16Type()), LUT16Type)
            and isinstance(profile.tags.get("A2B2", LUT16Type()), LUT16Type)
        ):
            self.lut3d_trc_apply_black_offset_ctrl.setEnabled(
                self.XYZbpin != self.XYZbpout
            )
            if self.XYZbpin == self.XYZbpout:
                setcfg("3dlut.apply_black_offset", 0)
        else:
            self.lut3d_trc_apply_black_offset_ctrl.setEnabled(False)
            setcfg("3dlut.apply_black_offset", 0)
        if getcfg("3dlut.apply_black_offset"):
            self.lut3d_trc_apply_black_offset_ctrl.setChecked(True)
        elif getcfg("3dlut.apply_trc"):
            self.lut3d_trc_apply_ctrl.setChecked(True)
        else:
            self.lut3d_trc_apply_none_ctrl.setChecked(True)
        self.lut3d_show_trc_controls()

    # -- shared option plumbing --------------------------------------------

    def lut3d_set_option(self, option: str, value: object) -> None:
        """Persist a 3D-LUT option and refresh dependent readouts.

        Args:
            option (str): The config key to set.
            value: The value to store.
        """
        setcfg(option, value)
        if option in (
            "3dlut.hdr_peak_luminance",
            "3dlut.hdr_minmll",
            "3dlut.hdr_maxmll",
        ):
            self.lut3d_show_hdr_maxmll_alt_clip_ctrl()
            self.lut3d_hdr_update_diffuse_white()
        elif option == "3dlut.hdr_ambient_luminance":
            self.lut3d_hdr_update_system_gamma()

    def lut3d_update_shared_controls(self) -> None:
        """Sync every combo/slider to config (mirrors the wx method)."""
        self.lut3d_update_trc_controls()
        self.lut3d_rendering_intent_ctrl.setCurrentIndex(
            self.rendering_intents_ba[getcfg("3dlut.rendering_intent")]
        )
        self.lut3d_format_ctrl.setCurrentIndex(
            self.lut3d_formats_ba.get(
                getcfg("3dlut.format"),
                self.lut3d_formats_ba[DEFAULTS["3dlut.format"]],
            )
        )
        self.lut3d_hdr_display_ctrl.setCurrentIndex(getcfg("3dlut.hdr_display"))
        self.lut3d_size_ctrl.setCurrentIndex(self.lut3d_size_ba[getcfg("3dlut.size")])
        self.lut3d_enable_size_controls()
        self.lut3d_bitdepth_input_ctrl.setCurrentIndex(
            self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.input")]
        )
        self.lut3d_bitdepth_output_ctrl.setCurrentIndex(
            self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.output")]
        )
        self.lut3d_update_encoding_controls()
        self.lut3d_show_bitdepth_controls()

    def lut3d_update_trc_control(self) -> None:
        """Select the tone-curve combo entry matching the current TRC config."""
        trc = getcfg("3dlut.trc")
        if trc.startswith("smpte2084"):
            self.lut3d_trc_ctrl.setCurrentIndex(2 if trc == "smpte2084.hardclip" else 3)
        elif trc == "hlg":
            self.lut3d_trc_ctrl.setCurrentIndex(4)
        elif (
            getcfg("3dlut.trc_gamma_type") == "B"
            and getcfg("3dlut.trc_output_offset") == 0
            and getcfg("3dlut.trc_gamma") == 2.4
        ):
            self.lut3d_trc_ctrl.setCurrentIndex(1)
            setcfg("3dlut.trc", "bt1886")
        elif (
            getcfg("3dlut.trc_gamma_type") == "b"
            and getcfg("3dlut.trc_output_offset") == 1
            and getcfg("3dlut.trc_gamma") == 2.2
        ):
            self.lut3d_trc_ctrl.setCurrentIndex(0)
            setcfg("3dlut.trc", "gamma2.2")
        else:
            self.lut3d_trc_ctrl.setCurrentIndex(5)
            setcfg("3dlut.trc", "customgamma")

    def lut3d_update_trc_controls(self) -> None:
        """Sync all TRC/HDR/content controls to config."""
        with self._guard():
            self._update_trc_controls()

    def _update_trc_controls(self) -> None:
        """Body of :meth:`lut3d_update_trc_controls` (guard applied by caller)."""
        self.lut3d_update_trc_control()
        self.lut3d_trc_gamma_ctrl.setCurrentText(str(getcfg("3dlut.trc_gamma")))
        self.lut3d_trc_gamma_type_ctrl.setCurrentIndex(
            self.trc_gamma_types_ba[getcfg("3dlut.trc_gamma_type")]
        )
        outoffset = int(getcfg("3dlut.trc_output_offset") * 100)
        self.lut3d_trc_black_output_offset_ctrl.setValue(outoffset)
        self.lut3d_trc_black_output_offset_intctrl.setValue(outoffset)
        target_peak = getcfg("3dlut.hdr_peak_luminance")
        maxmll = getcfg("3dlut.hdr_maxmll")
        if maxmll < target_peak:
            maxmll = target_peak
            setcfg("3dlut.hdr_maxmll", maxmll)
        self.lut3d_hdr_maxmll_ctrl.setRange(target_peak, 10000)
        self.lut3d_hdr_peak_luminance_ctrl.setValue(target_peak)
        self.lut3d_hdr_minmll_ctrl.setValue(getcfg("3dlut.hdr_minmll"))
        self.lut3d_hdr_maxmll_ctrl.setValue(maxmll)
        self.lut3d_hdr_maxmll_alt_clip_cb.setChecked(
            not bool(getcfg("3dlut.hdr_maxmll_alt_clip"))
        )
        self.lut3d_hdr_update_diffuse_white()
        self.lut3d_hdr_ambient_luminance_ctrl.setValue(
            getcfg("3dlut.hdr_ambient_luminance")
        )
        self.lut3d_hdr_update_system_gamma()
        content_colors = []
        for color in ("red", "green", "blue", "white"):
            for coord in "xy":
                v = getcfg(f"3dlut.content.colorspace.{color}.{coord}")
                getattr(self, f"lut3d_content_colorspace_{color}_{coord}").setValue(v)
                content_colors.append(round(v, 4))
        rgb_space_name = colormath.find_primaries_wp_xy_rgb_space_name(
            content_colors, CONTENT_COLORSPACE_NAMES
        )
        if rgb_space_name:
            i = CONTENT_COLORSPACE_NAMES.index(rgb_space_name)
        else:
            i = self.lut3d_content_colorspace_ctrl.count() - 1
        self.lut3d_content_colorspace_ctrl.setCurrentIndex(i)
        self.lut3d_hdr_sat_ctrl.setValue(round(getcfg("3dlut.hdr_sat") * 100))
        self.lut3d_hdr_update_sat_val()
        hue = round(getcfg("3dlut.hdr_hue") * 100)
        self.lut3d_hdr_hue_ctrl.setValue(hue)
        self.lut3d_hdr_hue_intctrl.setValue(hue)

    def lut3d_hdr_update_sat_val(self) -> None:
        """Update the saturation/luminance percentage readout."""
        v = getcfg("3dlut.hdr_sat") * 100
        self.lut3d_hdr_sat_val.setText(f"{100 - v:.0f}% / {v:.0f}%")

    def lut3d_hdr_update_system_gamma(self) -> None:
        """Update the HLG system-gamma readout from ambient luminance."""
        hlg = colormath.HLG(ambient_cdm2=getcfg("3dlut.hdr_ambient_luminance"))
        self.lut3d_hdr_system_gamma_txt.setText(str(stripzeros(f"{hlg.gamma:.4f}")))

    def lut3d_hdr_update_diffuse_white(self) -> None:
        """Update the BT.2390 diffuse-white roll-off readout."""
        bt2390 = colormath.BT2390(
            0,
            getcfg("3dlut.hdr_peak_luminance"),
            getcfg("3dlut.hdr_minmll"),
            getcfg("3dlut.hdr_maxmll"),
            getcfg("3dlut.hdr_maxmll_alt_clip"),
        )
        diffuse_ref_cdm2 = 94.37844
        diffuse_PQ = colormath.special_pow(diffuse_ref_cdm2 / 10000, 1.0 / -2084)
        diffuse_tgt_cdm2 = (
            colormath.special_pow(bt2390.apply(diffuse_PQ), -2084) * 10000
        )
        color = "#CC0000" if diffuse_tgt_cdm2 < diffuse_ref_cdm2 else "#008000"
        self.lut3d_hdr_diffuse_white_txt.setStyleSheet(f"color: {color}")
        self.lut3d_hdr_diffuse_white_txt.setText(f"{diffuse_tgt_cdm2:.2f}")

    # -- show / hide -------------------------------------------------------

    def lut3d_enable_size_controls(self) -> None:
        """Enable the size combo unless the format forces a fixed size."""
        self.lut3d_size_ctrl.setEnabled(
            getcfg("3dlut.format") not in ("eeColor", "madVR")
        )

    def lut3d_show_bitdepth_controls(self) -> None:
        """Show the bit-depth combos only for formats that use them."""
        input_show = getcfg("3dlut.format") == "3dl"
        self.lut3d_bitdepth_input_label.setVisible(input_show)
        self.lut3d_bitdepth_input_ctrl.setVisible(input_show)
        output_show = getcfg("3dlut.format") in ("3dl", "png")
        self.lut3d_bitdepth_output_label.setVisible(output_show)
        self.lut3d_bitdepth_output_ctrl.setVisible(output_show)

    def lut3d_show_hdr_display_control(self) -> None:
        """Show the madVR HDR-display combo only when applicable."""
        self.lut3d_hdr_display_ctrl.setVisible(
            getcfg("3dlut.apply_trc")
            and getcfg("3dlut.trc").startswith("smpte2084")
            and getcfg("3dlut.format") == "madVR"
        )

    def lut3d_show_hdr_maxmll_alt_clip_ctrl(self) -> None:
        """Show the alt-clip checkbox only when peak roll-off applies."""
        show = self.hdr_maxmll_row.isVisible()
        self.lut3d_hdr_maxmll_alt_clip_cb.setVisible(
            show and getcfg("3dlut.hdr_maxmll") < 10000
        )

    def lut3d_show_encoding_controls(self, show: bool = True) -> None:
        """Show the encoding combos subject to the Argyll version.

        Args:
            show (bool): Whether the encoding controls may be shown.
        """
        show = show and (
            (
                self.worker.argyll_version >= [1, 7]
                and self.worker.argyll_version != [1, 7, 0, "_beta"]
            )
            or self.worker.argyll_version >= [1, 6]
        )
        self.encoding_input_label.setVisible(show)
        self.encoding_input_ctrl.setVisible(show)
        show = show and self.worker.argyll_version >= [1, 6]
        self.encoding_output_label.setVisible(show)
        self.encoding_output_ctrl.setVisible(show)

    def lut3d_show_trc_controls(self, show: bool = True) -> None:
        """Show/hide the TRC and HDR controls per the current tone curve.

        Args:
            show (bool): Whether the TRC controls may be shown.
        """
        show = show and self.worker.argyll_version >= [1, 6]
        self.lut3d_trc_apply_ctrl.setVisible(show)
        self.lut3d_trc_ctrl.setVisible(show)
        trc = getcfg("3dlut.trc")
        smpte2084 = trc.startswith("smpte2084")
        hlg = trc == "hlg"
        hdr = smpte2084 or hlg
        # In the standalone window the "advanced options" gate is always open.
        self.lut3d_trc_gamma_label.setVisible(show and not hdr)
        self.lut3d_trc_gamma_ctrl.setVisible(show and not hdr)
        smpte2084r = trc == "smpte2084.rolloffclip"
        showcc = smpte2084r or hlg
        self.content_colorspace_row.setVisible(showcc)
        sel = self.lut3d_content_colorspace_ctrl.currentIndex()
        lastsel = self.lut3d_content_colorspace_ctrl.count() - 1
        self.content_colorspace_grid.setVisible(showcc and sel == lastsel)
        self.hdr_minmll_row.setVisible(show and smpte2084)
        self.hdr_maxmll_row.setVisible(show and smpte2084r)
        self.lut3d_show_hdr_maxmll_alt_clip_ctrl()
        self.hdr_diffuse_white_row.setVisible(show and smpte2084r)
        self.hdr_ambient_row.setVisible(show and hlg)
        self.hdr_system_gamma_row.setVisible(show and hlg)
        self.hdr_sat_row.setVisible(show and smpte2084r)
        self.hdr_hue_row.setVisible(show and smpte2084r)
        show = (show or smpte2084) and not hlg
        show = show and self.XYZbpout > [0, 0, 0]
        self.lut3d_trc_gamma_type_ctrl.setVisible(show and not hdr)
        self.lut3d_trc_black_output_offset_label.setVisible(show)
        self.lut3d_trc_black_output_offset_ctrl.setVisible(show)
        self.lut3d_trc_black_output_offset_intctrl.setVisible(show)
        self.lut3d_hdr_peak_luminance_label.setVisible(smpte2084)
        self.lut3d_hdr_peak_luminance_ctrl.setVisible(smpte2084)
        self.lut3d_hdr_peak_luminance_ctrl_label.setVisible(smpte2084)
        self.lut3d_show_hdr_display_control()

    def lut3d_show_input_value_clipping_warning(self, _layout: object = True) -> None:
        """Show the input-value-clipping warning for the unmodified TRC mode."""
        show = (
            self.lut3d_trc_apply_none_ctrl.isChecked()
            and self.XYZbpout > self.XYZbpin
            and getcfg("3dlut.rendering_intent")
            not in ("la", "p", "pa", "ms", "s", "lp")
        )
        self.lut3d_input_value_clipping_bmp.setVisible(show)
        self.lut3d_input_value_clipping_label.setVisible(show)

    # -- signal slots ------------------------------------------------------

    def lut3d_apply_cal_ctrl_handler(self, _checked: bool = False) -> None:
        """Persist the apply-calibration checkbox state."""
        if self._updating:
            return
        setcfg(
            "3dlut.output.profile.apply_cal", int(self.lut3d_apply_cal_cb.isChecked())
        )

    def lut3d_trc_apply_ctrl_handler(self, _checked: bool = False) -> None:
        """Enable/disable TRC controls and persist the apply mode."""
        v = self.lut3d_trc_apply_ctrl.isChecked()
        self.lut3d_trc_ctrl.setEnabled(v)
        self.lut3d_trc_gamma_label.setEnabled(v)
        self.lut3d_trc_gamma_ctrl.setEnabled(v)
        self.lut3d_trc_gamma_type_ctrl.setEnabled(v)
        if _checked is True and not self._updating:
            setcfg("3dlut.apply_trc", int(v))
            setcfg(
                "3dlut.apply_black_offset",
                int(self.lut3d_trc_apply_black_offset_ctrl.isChecked()),
            )
        for name in (
            "lut3d_hdr_peak_luminance_label",
            "lut3d_hdr_peak_luminance_ctrl",
            "lut3d_hdr_peak_luminance_ctrl_label",
            "lut3d_hdr_minmll_label",
            "lut3d_hdr_maxmll_label",
            "lut3d_hdr_diffuse_white_label",
            "lut3d_hdr_diffuse_white_txt",
            "lut3d_hdr_ambient_luminance_label",
            "lut3d_hdr_ambient_luminance_ctrl",
            "lut3d_hdr_system_gamma_label",
            "lut3d_hdr_system_gamma_txt",
            "lut3d_content_colorspace_label",
            "lut3d_content_colorspace_ctrl",
            "lut3d_hdr_minmll_ctrl",
            "lut3d_hdr_maxmll_ctrl",
            "lut3d_trc_black_output_offset_label",
            "lut3d_trc_black_output_offset_ctrl",
            "lut3d_trc_black_output_offset_intctrl",
        ):
            getattr(self, name).setEnabled(v)
        for color in ("white", "red", "green", "blue"):
            getattr(self, f"lut3d_content_colorspace_{color[0]}_label").setEnabled(v)
            for coord in "xy":
                getattr(self, f"lut3d_content_colorspace_{color}_{coord}").setEnabled(v)
                getattr(
                    self, f"lut3d_content_colorspace_{color}_{coord}_label"
                ).setEnabled(v)
        self.lut3d_show_input_value_clipping_warning(_checked)
        self.lut3d_show_hdr_display_control()

    def lut3d_trc_ctrl_handler(self, _index: int = 0) -> None:
        """Handle a tone-curve selection change."""
        sel = self.lut3d_trc_ctrl.currentIndex()
        if sel == 1:
            self.lut3d_set_option("3dlut.trc_gamma", 2.4)
            self.lut3d_set_option("3dlut.trc_gamma_type", "B")
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "bt1886"
        elif sel == 0:
            self.lut3d_set_option("3dlut.trc_gamma", 2.2)
            self.lut3d_set_option("3dlut.trc_gamma_type", "b")
            self.lut3d_set_option("3dlut.trc_output_offset", 1.0)
            trc = "gamma2.2"
        elif sel == 2:
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "smpte2084.hardclip"
            self.lut3d_set_option("3dlut.hdr_maxmll", 10000)
        elif sel == 3:
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "smpte2084.rolloffclip"
            self.lut3d_set_option("3dlut.hdr_maxmll", 10000)
        elif sel == 4:
            self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
            trc = "hlg"
        else:
            trc = "customgamma"
        self.lut3d_set_option("3dlut.trc", trc)
        if trc != "customgamma":
            self.lut3d_update_trc_controls()
        self.lut3d_show_trc_controls()

    def lut3d_trc_gamma_ctrl_handler(self) -> None:
        """Validate and persist the custom-gamma entry."""
        try:
            v = float(self.lut3d_trc_gamma_ctrl.currentText().replace(",", "."))
            if (
                v < config.VALID_RANGES["3dlut.trc_gamma"][0]
                or v > config.VALID_RANGES["3dlut.trc_gamma"][1]
            ):
                raise ValueError
        except ValueError:
            QApplication.beep()
            self.lut3d_trc_gamma_ctrl.setCurrentText(str(getcfg("3dlut.trc_gamma")))
            return
        if str(v) != self.lut3d_trc_gamma_ctrl.currentText():
            self.lut3d_trc_gamma_ctrl.setCurrentText(str(v))
        if v != getcfg("3dlut.trc_gamma"):
            self.lut3d_set_option("3dlut.trc_gamma", v)
            self.lut3d_update_trc_control()

    def lut3d_trc_gamma_type_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the TRC gamma-type selection."""
        v = self.trc_gamma_types_ab[self.lut3d_trc_gamma_type_ctrl.currentIndex()]
        if v != getcfg("3dlut.trc_gamma_type"):
            self.lut3d_set_option("3dlut.trc_gamma_type", v)
            self.lut3d_update_trc_control()
            self.lut3d_show_trc_controls()

    def _on_black_offset_slider(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_trc_black_output_offset_intctrl.setValue(value)
        self._apply_black_offset(value)

    def _on_black_offset_spin(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_trc_black_output_offset_ctrl.setValue(value)
        self._apply_black_offset(value)

    def _apply_black_offset(self, value: int) -> None:
        v = value / 100.0
        if v != getcfg("3dlut.trc_output_offset"):
            self.lut3d_set_option("3dlut.trc_output_offset", v)
            self.lut3d_update_trc_control()

    def lut3d_hdr_peak_luminance_handler(self, _value: float = 0.0) -> None:
        """Persist the HDR peak-luminance value and clamp maxmll."""
        if self._updating:
            return
        target_peak = self.lut3d_hdr_peak_luminance_ctrl.value()
        if self.lut3d_hdr_maxmll_ctrl.value() < target_peak:
            setcfg("3dlut.hdr_maxmll", target_peak)
        self.lut3d_hdr_maxmll_ctrl.setRange(target_peak, 10000)
        self.lut3d_set_option("3dlut.hdr_peak_luminance", target_peak)

    def lut3d_hdr_ambient_luminance_handler(self, _value: float = 0.0) -> None:
        """Persist the HDR ambient-luminance value."""
        if self._updating:
            return
        self.lut3d_set_option(
            "3dlut.hdr_ambient_luminance", self.lut3d_hdr_ambient_luminance_ctrl.value()
        )

    def lut3d_hdr_minmll_handler(self, _value: float = 0.0) -> None:
        """Persist the HDR minimum-MLL value."""
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_minmll", self.lut3d_hdr_minmll_ctrl.value())

    def lut3d_hdr_maxmll_handler(self, _value: float = 0.0) -> None:
        """Persist the HDR maximum-MLL value."""
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_maxmll", self.lut3d_hdr_maxmll_ctrl.value())

    def lut3d_hdr_maxmll_alt_clip_handler(self, _checked: bool = False) -> None:
        """Persist the alternate master-white-clip checkbox state."""
        if self._updating:
            return
        self.lut3d_set_option(
            "3dlut.hdr_maxmll_alt_clip",
            int(not self.lut3d_hdr_maxmll_alt_clip_cb.isChecked()),
        )
        self.lut3d_hdr_update_diffuse_white()

    def lut3d_hdr_sat_ctrl_handler(self, _value: int = 0) -> None:
        """Persist the HDR saturation slider value."""
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_sat", self.lut3d_hdr_sat_ctrl.value() / 100.0)
        self.lut3d_hdr_update_sat_val()

    def _on_hdr_hue_slider(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_hdr_hue_intctrl.setValue(value)
        self._apply_hdr_hue(value)

    def _on_hdr_hue_spin(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_hdr_hue_ctrl.setValue(value)
        self._apply_hdr_hue(value)

    def _apply_hdr_hue(self, value: int) -> None:
        v = value / 100.0
        if v != getcfg("3dlut.hdr_hue"):
            self.lut3d_set_option("3dlut.hdr_hue", v)

    def lut3d_hdr_display_handler(self, _index: int = 0) -> None:
        """Persist the madVR HDR-display mode, confirming HDR passthrough."""
        if (
            self.lut3d_hdr_display_ctrl.currentIndex()
            and not getcfg("3dlut.hdr_display")
            and not self._confirm(lang.getstr("3dlut.format.madVR.hdr.confirm"))
        ):
            self.lut3d_hdr_display_ctrl.setCurrentIndex(0)
            return
        self.lut3d_set_option(
            "3dlut.hdr_display", self.lut3d_hdr_display_ctrl.currentIndex()
        )

    def lut3d_content_colorspace_handler(self, _index: int = 0) -> None:
        """Apply a content-colorspace preset (or reveal the custom grid)."""
        sel = self.lut3d_content_colorspace_ctrl.currentIndex()
        try:
            rgb_space = CONTENT_COLORSPACE_NAMES[sel]
        except IndexError:
            rgb_space = None
        else:
            rgb_space = colormath.get_rgb_space(rgb_space)
            for i, color in enumerate(("white", "red", "green", "blue")):
                if i == 0:
                    xyY = colormath.XYZ2xyY(*rgb_space[1])
                else:
                    xyY = rgb_space[2:][i - 1]
                for j, coord in enumerate("xy"):
                    self.lut3d_set_option(
                        f"3dlut.content.colorspace.{color}.{coord}", round(xyY[j], 4)
                    )
            self.lut3d_update_trc_controls()
        self.content_colorspace_grid.setVisible(not rgb_space)

    def _on_content_colorspace_xy(
        self, color: str, coord: str, _value: float = 0.0
    ) -> None:
        """Slot adapter for a content-colorspace coordinate spin box.

        Args:
            color (str): One of ``white``/``red``/``green``/``blue``.
            coord (str): ``x`` or ``y``.
            _value (float): The new spin value (unused; read back in the handler).
        """
        self.lut3d_content_colorspace_xy_handler(color, coord)

    def lut3d_content_colorspace_xy_handler(self, color: str, coord: str) -> None:
        """Persist a manually-edited content-colorspace coordinate.

        Args:
            color (str): One of ``white``/``red``/``green``/``blue``.
            coord (str): ``x`` or ``y``.
        """
        if self._updating:
            return
        ctrl = getattr(self, f"lut3d_content_colorspace_{color}_{coord}")
        self.lut3d_set_option(f"3dlut.content.colorspace.{color}.{coord}", ctrl.value())
        self.lut3d_update_trc_controls()

    def lut3d_gamut_mapping_mode_handler(self, _checked: bool = False) -> None:
        """Persist the gamut-mapping mode and refresh linking controls."""
        if self._updating:
            return
        self.lut3d_set_option(
            "3dlut.gamap.use_b2a", int(self.gamut_mapping_b2a.isChecked())
        )
        self.update_linking_controls()

    def lut3d_rendering_intent_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the rendering-intent selection."""
        self.lut3d_set_option(
            "3dlut.rendering_intent",
            self.rendering_intents_ab[self.lut3d_rendering_intent_ctrl.currentIndex()],
        )
        self.lut3d_show_input_value_clipping_warning(True)

    def lut3d_format_ctrl_handler(self, _index: int = 0) -> None:
        """Apply a 3D-LUT format selection (with its encoding/size overrides)."""
        file_format = self.lut3d_formats_ab[self.lut3d_format_ctrl.currentIndex()]
        encoding_overrides = ("dcl", "eeColor", "madVR", "ReShade")
        size_overrides = ("dcl", "eeColor", "madVR", "mga", "ReShade")
        if (
            getcfg("3dlut.format") in encoding_overrides
            and file_format not in encoding_overrides
        ):
            setcfg("3dlut.encoding.input", getcfg("3dlut.encoding.input.backup"))
            setcfg("3dlut.encoding.output", getcfg("3dlut.encoding.output.backup"))
        if getcfg("3dlut.format") in size_overrides:
            setcfg("3dlut.size", getcfg("3dlut.size.backup"))
        if (
            getcfg("3dlut.format") not in encoding_overrides
            and file_format in encoding_overrides
        ):
            setcfg("3dlut.encoding.input.backup", getcfg("3dlut.encoding.input"))
            setcfg("3dlut.encoding.output.backup", getcfg("3dlut.encoding.output"))
        self.lut3d_set_option("3dlut.format", file_format)
        if file_format in size_overrides:
            setcfg("3dlut.size.backup", getcfg("3dlut.size"))
        if file_format == "eeColor":
            if getcfg("3dlut.encoding.input") not in ("t", "T"):
                self.lut3d_set_option("3dlut.encoding.input", "t")
            self.lut3d_set_option("3dlut.encoding.output", "t")
            self.lut3d_set_option("3dlut.size", 65)
        elif file_format == "mga":
            self.lut3d_set_option("3dlut.bitdepth.output", 16)
        elif file_format == "madVR":
            if getcfg("3dlut.encoding.input") not in ("t", "T"):
                self.lut3d_set_option("3dlut.encoding.input", "t")
            self.lut3d_set_option("3dlut.encoding.output", "t")
            self.lut3d_set_option("3dlut.size", 65)
        elif file_format in ("png", "ReShade"):
            if file_format == "ReShade":
                self.lut3d_set_option("3dlut.encoding.input", "n")
                self.lut3d_set_option("3dlut.encoding.output", "n")
                self.lut3d_set_option("3dlut.bitdepth.output", 8)
            elif getcfg("3dlut.bitdepth.output") not in (8, 16):
                self.lut3d_set_option("3dlut.bitdepth.output", 8)
        elif file_format == "dcl":
            self.lut3d_set_option("3dlut.encoding.input", "n")
            self.lut3d_set_option("3dlut.encoding.output", "n")
            self.lut3d_set_option("3dlut.size", 33)
            self.lut3d_set_option("3dlut.bitdepth.output", 12)
        size = getcfg("3dlut.size")
        snap_size = self.lut3d_snap_size(size)
        if snap_size != size:
            self.lut3d_set_option("3dlut.size", snap_size)
        self.lut3d_size_ctrl.setCurrentIndex(self.lut3d_size_ba[getcfg("3dlut.size")])
        self.lut3d_bitdepth_output_ctrl.setCurrentIndex(
            self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.output")]
        )
        self.lut3d_update_encoding_controls()
        self.lut3d_enable_size_controls()
        self.lut3d_show_bitdepth_controls()
        self.lut3d_show_hdr_display_control()
        self.lut3d_create_btn.setEnabled(
            file_format != "madVR" or self.output_profile_ctrl.isVisible()
        )

    def lut3d_snap_size(self, size: int) -> int:
        """Snap a size to the nearest value valid for the current format.

        Args:
            size (int): The requested 3D-LUT size.

        Returns:
            int: The snapped size.
        """
        if getcfg("3dlut.format") == "mga" and size not in (17, 33):
            size = 17 if size < 33 else 33
        elif getcfg("3dlut.format") == "ReShade" and size not in (16, 32, 64):
            if size < 32:
                size = 16
            elif size < 64:
                size = 32
            else:
                size = 64
        return size

    def lut3d_size_ctrl_handler(self, _index: int = 0) -> None:
        """Apply a 3D-LUT size selection, snapping to a valid value."""
        size = self.lut3d_size_ab[self.lut3d_size_ctrl.currentIndex()]
        snap_size = self.lut3d_snap_size(size)
        if snap_size != size:
            QApplication.beep()
            self.lut3d_size_ctrl.setCurrentIndex(self.lut3d_size_ba[snap_size])
        self.lut3d_set_option("3dlut.size", snap_size)

    def lut3d_bitdepth_input_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the input bit-depth selection."""
        self.lut3d_set_option(
            "3dlut.bitdepth.input",
            self.lut3d_bitdepth_ab[self.lut3d_bitdepth_input_ctrl.currentIndex()],
        )

    def lut3d_bitdepth_output_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the output bit-depth selection (clamped for png/ReShade)."""
        bitdepth = self.lut3d_bitdepth_ab[
            self.lut3d_bitdepth_output_ctrl.currentIndex()
        ]
        if getcfg("3dlut.format") in ("png", "ReShade") and bitdepth not in (8, 16):
            QApplication.beep()
            self.lut3d_bitdepth_output_ctrl.setCurrentIndex(self.lut3d_bitdepth_ba[8])
            bitdepth = 8
        self.lut3d_set_option("3dlut.bitdepth.output", bitdepth)

    def lut3d_encoding_input_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the input-encoding selection."""
        encoding = self.encoding_input_ab[self.encoding_input_ctrl.currentIndex()]
        self.lut3d_set_option("3dlut.encoding.input", encoding)
        self.lut3d_update_encoding_controls()

    def lut3d_encoding_output_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the output-encoding selection (confirming for madVR)."""
        encoding = self.encoding_output_ab[self.encoding_output_ctrl.currentIndex()]
        if getcfg("3dlut.format") == "madVR" and encoding != "t":
            profile = self.output_profile
            devicename = None
            if (
                profile
                and "meta" in profile.tags
                and isinstance(profile.tags.meta, DictType)
                and "EDID_model" in profile.tags.meta
            ):
                devicename = profile.tags.meta["EDID_model"]
            if not self._confirm(
                lang.getstr(
                    "3dlut.encoding.output.warning.madvr",
                    devicename or lang.getstr("device.name.placeholder"),
                )
            ):
                self.encoding_output_ctrl.setCurrentIndex(
                    self.encoding_output_ba[getcfg("3dlut.encoding.output")]
                )
                return
        self.lut3d_set_option("3dlut.encoding.output", encoding)
        self.lut3d_update_encoding_controls()

    def lut3d_update_encoding_controls(self) -> None:
        """Repopulate and re-select the encoding combos for the format."""
        self.lut3d_setup_encoding_ctrl()
        self.encoding_input_ctrl.setCurrentIndex(
            self.encoding_input_ba[getcfg("3dlut.encoding.input")]
        )
        self.encoding_input_ctrl.setEnabled(self.encoding_input_ctrl.count() > 1)
        self.encoding_output_ctrl.setCurrentIndex(
            self.encoding_output_ba[getcfg("3dlut.encoding.output")]
        )
        self.encoding_output_ctrl.setEnabled(
            getcfg("3dlut.format") not in ("dcl", "madVR")
        )

    # -- creation ----------------------------------------------------------

    def lut3d_create_handler(self, _checked: bool = False) -> None:
        """Validate inputs, prompt for a path and start the LUT creation."""
        from DisplayCAL.argyll import check_set_argyll_bin

        if not check_set_argyll_bin():
            return
        profile_in = self.set_profile("input")
        profile_abst = (
            self.set_profile("abstract")
            if getcfg("3dlut.use_abstract_profile")
            else None
        )
        profile_out = self.set_profile("output")
        if None in (profile_in, profile_out) and not (
            profile_in and profile_in.profileClass == "link"
        ):
            return
        if (
            profile_out
            and profile_in.is_same(profile_out, force_calculation=True)
            and not self._confirm(
                lang.getstr("error.source_dest_same"), confirm=lang.getstr("continue")
            )
        ):
            return

        path = self._prompt_lut_path()
        if not path:
            return
        if not waccess(path, os.W_OK):
            self._error(lang.getstr("error.access_denied.write", path))
            return
        setcfg("last_3dlut_path", path)
        config.writecfg(
            module="3DLUT-maker",
            options=(
                "3dlut.",
                "last_3dlut_path",
                "position.lut3dframe",
                "size.lut3dframe",
            ),
        )

        if self._thread is not None and self._thread.isRunning():
            return
        self.worker.interactive = False
        self.lut3d_create_btn.setEnabled(False)
        self._progress = QProgressDialog(lang.getstr("3dlut.create"), "", 0, 0, self)
        self._progress.setWindowTitle(self.windowTitle())
        self._progress.setCancelButton(None)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.show()
        self._thread = _CreateThread(
            self, (profile_in, profile_abst, profile_out, path), parent=self
        )
        self._thread.done.connect(self._on_create_done)
        self._thread.start()

    def _prompt_lut_path(self) -> str:
        """Prompt for the 3D-LUT output path based on the selected format.

        Returns:
            str: The chosen path, or an empty string if cancelled.
        """
        default_dir, default_file = get_verified_path("last_3dlut_path")
        ext = getcfg("3dlut.format")
        if ext == "ReShade":
            directory = file_dialog.get_existing_directory(
                self, lang.getstr("3dlut.install"), default_dir
            )
            if not directory:
                return ""
            return os.path.join(directory.rstrip(os.path.sep), "ColorLookupTable.png")
        if ext == "eeColor":
            ext = "txt"
        elif ext == "madVR":
            ext = "3dlut"
        elif ext == "icc":
            ext = PROFILE_EXT[1:]
        default_file = (
            os.path.splitext(default_file or lang.getstr("unnamed"))[0] + "." + ext
        )
        path, _ = file_dialog.get_save_file_name(
            self,
            lang.getstr("3dlut.save_as"),
            os.path.join(default_dir, default_file),
            f"*.{ext}",
        )
        if not path:
            return ""
        if os.path.splitext(path)[1][1:].lower() != ext.lower():
            path += f".{ext}"
        return path

    def create_3dlut(
        self,
        profile_in: ICCProfile,
        profile_abst: ICCProfile | None,
        profile_out: ICCProfile | None,
        path: str,
    ) -> bool | Exception:
        """Run Argyll ``collink`` to build the 3D LUT (off the GUI thread).

        Args:
            profile_in (ICCProfile): Input profile.
            profile_abst (ICCProfile | None): Abstract profile, if used.
            profile_out (ICCProfile | None): Output profile.
            path (str): Path to write the 3D LUT to.

        Returns:
            bool | Exception: ``True`` on success, or the raised exception.
        """
        apply_cal = (
            profile_out
            and isinstance(profile_out.tags.get("vcgt"), VideoCardGammaType)
            and getcfg("3dlut.output.profile.apply_cal")
        )
        if getcfg("3dlut.apply_trc"):
            trc = getcfg("3dlut.trc")
            if trc.startswith("smpte2084") or trc == "hlg":
                trc_gamma = getcfg("3dlut.trc")
            else:
                trc_gamma = getcfg("3dlut.trc_gamma")
        else:
            trc_gamma = None
        content_rgb_space = [1.0, [], [], [], []]
        for i, color in enumerate(("white", "red", "green", "blue")):
            for coord in "xy":
                content_rgb_space[i + 1].append(
                    getcfg(f"3dlut.content.colorspace.{color}.{coord}")
                )
            content_rgb_space[i + 1].append(1.0)
        content_rgb_space[1] = colormath.xyY2XYZ(*content_rgb_space[1])
        content_rgb_space = colormath.get_rgb_space(content_rgb_space)
        try:
            profile_in = ICCProfile(profile_in.filename)
            self.worker.create_3dlut(
                profile_in,
                path,
                profile_abst,
                profile_out,
                apply_cal=apply_cal,
                intent=getcfg("3dlut.rendering_intent"),
                file_format=getcfg("3dlut.format"),
                size=getcfg("3dlut.size"),
                input_bits=getcfg("3dlut.bitdepth.input"),
                output_bits=getcfg("3dlut.bitdepth.output"),
                input_encoding=getcfg("3dlut.encoding.input"),
                output_encoding=getcfg("3dlut.encoding.output"),
                trc_gamma=trc_gamma,
                trc_gamma_type=getcfg("3dlut.trc_gamma_type"),
                trc_output_offset=getcfg("3dlut.trc_output_offset"),
                apply_black_offset=getcfg("3dlut.apply_black_offset"),
                use_b2a=getcfg("3dlut.gamap.use_b2a"),
                white_cdm2=getcfg("3dlut.hdr_peak_luminance"),
                minmll=getcfg("3dlut.hdr_minmll"),
                maxmll=getcfg("3dlut.hdr_maxmll"),
                use_alternate_master_white_clip=getcfg("3dlut.hdr_maxmll_alt_clip"),
                hdr_sat=getcfg("3dlut.hdr_sat"),
                hdr_hue=getcfg("3dlut.hdr_hue"),
                ambient_cdm2=getcfg("3dlut.hdr_ambient_luminance"),
                content_rgb_space=content_rgb_space,
                hdr_display=getcfg("3dlut.hdr_display"),
            )
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            return exception
        return True

    def _on_create_done(self, result: object) -> None:
        """Handle a finished LUT creation on the GUI thread.

        Args:
            result: ``True`` on success, or an ``Exception`` on failure.
        """
        self._thread = None
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        self.worker.wrapup(False)
        self.lut3d_create_btn.setEnabled(True)
        if isinstance(result, Exception):
            self._error(str(result))

    # -- helpers -----------------------------------------------------------

    def _error(self, message: str) -> None:
        """Show a modal error dialog.

        Args:
            message (str): The message to display.
        """
        message_box.critical(self, self.windowTitle(), message)

    def _confirm(self, message: str, confirm: str | None = None) -> bool:
        """Show a modal confirmation dialog.

        Args:
            message (str): The message to display.
            confirm (str | None): Unused label parity with the wx signature.

        Returns:
            bool: True if the user accepted.
        """
        return (
            message_box.question(
                self,
                self.windowTitle(),
                message,
                QMessageBox.Ok | QMessageBox.Cancel,
            )
            == QMessageBox.Ok
        )

    # -- scripting / lifecycle ---------------------------------------------

    def get_commands(self) -> list:
        """Return this tool's scripting commands.

        Returns:
            list: The available scripting commands.
        """
        return [*self.get_common_commands(), "3DLUT-maker [create <filename>]"]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"`` or ``"invalid"``.
        """
        if data[0] == "3DLUT-maker" and (
            len(data) == 1 or (len(data) == 3 and data[1] == "create")
        ):
            self.activateWindow()
            self.raise_()
            return "ok"
        return "invalid"

    def closeEvent(self, event: object) -> None:  # noqa: N802
        """Persist settings and position before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        if self._thread is not None and self._thread.isRunning():
            self.worker.abort_subprocess(True)
            self._thread.wait()
        config.writecfg(
            module="3DLUT-maker",
            options=(
                "3dlut.",
                "last_3dlut_path",
                "position.lut3dframe",
                "size.lut3dframe",
            ),
        )
        super().closeEvent(event)


def main() -> int:
    """Entry point for the Qt 3D LUT maker.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("3DLUT-maker")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = LUT3DWindow()
    app.top_window = window
    window.show()
    window.listen()
    app.process_argv()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
