"""Measurement-report creation window — Qt port.

Qt equivalent of :class:`DisplayCAL.wx_report_frame.ReportFrame`: the settings
window where the user picks a test chart / reference, optional simulation,
device-link and output profiles, the tone-response target (unmodified / black
output offset / BT.1886-style TRC) and whitepoint-simulation options before
kicking off a measurement report.

The load-bearing, toolkit-neutral string/number helpers this window relies on
(default report filename, quantization, the BT.1886 label) already live in the
Qt-free :mod:`DisplayCAL.measurement_report` module and are shared with the
still-shipping wx path.

Two pieces of the wx frame are deliberately *not* reproduced here and are
surfaced as Qt signals for the Qt main window to wire up, matching the
deferral :class:`DisplayCAL.ui.measure_frame.MeasureFrame` made for its
Measure button:

* :attr:`ReportPanel.measure_requested` — the actual measurement run
  (``setup_measurement`` / ``measurement_report`` / the big
  ``measurement_report_consumer`` ``placeholders2data`` assembly) lives in
  ``MainWindow``; standalone the button just emits this signal. Its bool
  argument mirrors wx's ``wx.GetKeyState(wx.WXK_ALT)`` read in
  ``measurement_report_handler``: ``True`` when Alt is held at click time,
  requesting a "self-check report" (look the chart up through the display
  profile's own tables instead of measuring) rather than a real measurement.
  The button's label swaps to ``self_check_report`` while Alt is held, same as
  wx's ``MainFrame.check_keydown`` polling timer.
* :attr:`ReportPanel.edit_chart_requested` — opening the test-chart editor on
  the parent window; standalone it is a no-op.

The wx frame is built from ``xrc/report.xrc``; here the same widget set and
top-to-bottom order is hand-built with native Qt widgets. The custom wx
``FileBrowseButtonWithHistory`` is replaced by the same editable-combo +
browse-button stand-in the Qt 3D LUT window uses (:class:`_FileBrowse`).
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
from time import gmtime, strftime
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.cgats import (
    CGATS,
    CGATSInvalidError,
    CGATSInvalidOperationError,
    CGATSKeyError,
    CGATSTypeError,
    CGATSValueError,
)
from DisplayCAL.config import (
    get_data_path,
    getcfg,
    setcfg,
)
from DisplayCAL.icc_profile import (
    CurveType,
    ICCProfile,
    ICCProfileInvalidError,
    LUT16Type,
    XYZType,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.tooltip_window import info_text_html
from DisplayCAL.util_list import natsort_key_factory
from DisplayCAL.worker import Worker, get_current_profile_path

if TYPE_CHECKING:
    from collections.abc import Callable

    from qtpy.QtGui import QCloseEvent

#: File suffixes accepted for the profile controls / drag-and-drop.
PROFILE_SUFFIXES = (".icc", ".icm")

#: File suffixes accepted for the chart / reference control.
CHART_SUFFIXES = (".cgats", ".cie", ".ti1", ".ti2", ".ti3", ".txt")

#: The tone-response target chooser labels, in control order (matches the wx
#: ``mr_trc_ctrl`` items).
TRC_ITEMS = ("Gamma 2.2", "trc.rec1886", "custom")


def friendly_file_name(path: str) -> str:
    """Return a human-readable label for ``path``.

    Port of ``FileBrowseBitmapButtonWithChoiceHistory.GetName()``
    (``wx_windows.py``): an ICC/ICM profile's embedded description if it has
    one and is readable, else the file's base name -- run through
    ``lang.getstr()`` either way, so a bundled testchart's file name (e.g.
    ``"verify_extended.ti1"``, itself used as the translation key in
    ``lang/en.yaml``) resolves to its friendly name ("Extended verification
    testchart") while an arbitrary user file just keeps its own base name.

    Args:
        path (str): An absolute file path.
    """
    name = None
    if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
        with contextlib.suppress(OSError, ICCProfileInvalidError):
            name = ICCProfile(path).getDescription()
    if not name:
        name = os.path.basename(path)
    return lang.getstr(name)


class _GuardContext:
    """Suppress re-entrant control-change handlers while active.

    Qt emits ``toggled`` / ``valueChanged`` from programmatic ``setChecked`` /
    ``setValue`` (wx does not fire events from ``SetValue``), so while this
    context is active :attr:`ReportPanel._updating` is truthy and the affected
    slots return early instead of recursing when the bulk update methods set
    control values. The previous flag is saved/restored so nesting is safe.

    Args:
        window (ReportPanel): The panel whose update guard to toggle.
    """

    def __init__(self, window: ReportPanel) -> None:
        self._window = window

    def __enter__(self) -> None:
        self._prev = self._window._updating
        self._window._updating = True

    def __exit__(self, *exc) -> None:
        self._window._updating = self._prev


class _FileBrowse(QWidget):
    """An editable path combo box with history plus a browse button.

    Qt stand-in for wx ``FileBrowseButtonWithHistory``: an editable combo box
    (the drop-down keeps recently-used / preset paths as history) followed by a
    browse button.

    Args:
        dialog_title (str): Title for the file-open dialog.
        wildcard (str): Qt name filter, e.g. ``"ICC (*.icc *.icm)"``.
        parent (QWidget | None): Optional Qt parent.
        name_func (Callable[[str], str] | None): Converts an absolute path to
            the label shown in the combo (history items and the current
            selection alike); the real path is kept as each item's
            ``Qt.UserRole`` data and returned by :meth:`path` regardless of
            what's displayed. Defaults to showing the raw path verbatim.
            Mirrors wx's ``FileBrowseBitmapButtonWithChoiceHistory.GetName()``
            (see :func:`friendly_file_name`), which is why e.g. the
            Verification tab's chart/profile pickers show "Extended
            verification testchart" instead of the bundled ``.ti1``'s full
            path.
    """

    #: Emitted when the path changes (browse, history pick or typed entry).
    changed = Signal()

    def __init__(
        self,
        dialog_title: str = "",
        wildcard: str = "",
        parent: QWidget | None = None,
        name_func: Callable[[str], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._wildcard = wildcard
        self._committed = ""
        self._history: list[str] = []
        self._name_func = name_func or (lambda path: path)
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

        Resolves through the selected item's stored path when the visible
        text is an unmodified history/preset label; falls back to the raw
        edit text for freeform typing, matching :meth:`set_path`.

        Returns:
            str: The current path (may be empty).
        """
        index = self._combo.currentIndex()
        if index >= 0 and self._combo.itemText(index) == self._combo.currentText():
            data = self._combo.itemData(index)
            if data:
                return data
        return self._combo.currentText()

    def set_path(self, path: str | None) -> None:
        """Set the current path without emitting :attr:`changed`.

        Args:
            path (str | None): The path to show (``None`` clears the field).
        """
        path = path or ""
        self._committed = path
        if not path:
            self._combo.setEditText("")
            return
        index = self._combo.findData(path)
        if index == -1:
            self._combo.addItem(self._name_func(path), path)
            index = self._combo.count() - 1
        self._combo.setCurrentIndex(index)

    def set_history(self, paths: list[str]) -> None:
        """Populate the drop-down history, preserving the current path.

        Args:
            paths (list[str]): Absolute paths to offer in the drop-down.
        """
        self._history = list(paths)
        current = self._committed
        self._combo.blockSignals(True)
        self._combo.clear()
        for path in self._history:
            self._combo.addItem(self._name_func(path), path)
        self._combo.blockSignals(False)
        self.set_path(current)

    def _on_activated(self, _index: int) -> None:
        self._committed = self.path()
        self.changed.emit()

    def _on_edit_finished(self) -> None:
        # editingFinished also fires on focus-out without changes; only react to
        # an actual edit, mirroring the wx changeCallback.
        current = self.path()
        if current != self._committed:
            self._committed = current
            self.changed.emit()

    def _on_browse(self) -> None:
        default_dir = os.path.dirname(self.path()) if self.path() else ""
        path, _ = file_dialog.get_open_file_name(
            self, self._dialog_title, default_dir, self._wildcard
        )
        if path:
            self.set_path(path)
            self.changed.emit()


class ReportPanel(QWidget):
    """The measurement-report settings controls.

    Qt equivalent of wx's ``report.xrc`` panel (``mr_settings_panel``): the
    same widget set embeds both in the standalone :class:`ReportWindow` (via
    ``setCentralWidget``) and as the Qt main window's Verification tab
    (mirroring wx's ``MainFrame`` embedding the same panel as its 5th tab,
    ``display_cal.py:2450-2458``).

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    #: Emitted when the Measure button is pressed. The Qt main window connects
    #: this to its measurement flow; standalone it just re-enables the button.
    #: The argument is ``True`` when Alt was held at click time (self-check
    #: report), matching wx's ``wx.GetKeyState(wx.WXK_ALT)`` read.
    measure_requested = Signal(bool)

    #: Emitted when the test-chart-editor button is pressed. The Qt main window
    #: opens its test-chart editor; standalone it is a no-op.
    edit_chart_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        show_measure_button: bool = True,
        worker: Worker | None = None,
    ) -> None:
        """Construct the panel.

        Args:
            parent (QWidget | None): Optional parent widget.
            show_measure_button (bool): Whether to build the panel's own
                "Measure" button. ``report.xrc`` itself has no such button --
                wx's standalone ``ReportFrame`` adds one programmatically
                (``wx_report_frame.py:78``), while the embedded ``MainFrame``
                tab relies on the shared ``buttonpanel``'s
                ``measurement_report_btn`` instead. Default ``True`` matches
                the standalone case (:class:`ReportWindow`); the Qt main
                window's Verification tab passes ``False``.
            worker (Worker | None): A pre-enumerated worker to adopt, mirroring
                wx's ``MainFrame`` (which inherits ``ReportFrame`` and so
                shares one ``self.worker`` for both) -- the Qt main window
                passes its own instead of paying for a second Argyll-version
                probe. Standalone (and tests) get a fresh one when omitted.
        """
        super().__init__(parent)
        self._show_measure_button = show_measure_button
        #: Set by :meth:`mr_update_controls`; see :meth:`can_measure`.
        self._mr_can_measure = False
        if worker is not None:
            self.worker = worker
        else:
            self.worker = Worker()
            self.worker.set_argyll_version("xicclu")

        # Profile-lookup blackpoints (see the wx frame). XYZbpout starts as None
        # and is seeded slightly above zero when an output profile is selected
        # so the black-output-offset controls show if the profile is missing.
        self.XYZbpin: list | None = None
        self.XYZbpout: list | None = None

        self.trc_gamma_types_ab = {0: "b", 1: "B"}
        self.trc_gamma_types_ba = {"b": 0, "B": 1}

        self._updating = False

        self._build_ui()
        self.mr_setup_language()

        for which in (
            "chart",
            "simulation_profile",
            "devlink_profile",
            "output_profile",
        ):
            ctrl = getattr(self, f"{which}_ctrl")
            ctrl.changed.connect(getattr(self, f"{which}_ctrl_handler"))
            if which.endswith("_profile"):
                suffixes = PROFILE_SUFFIXES
            else:
                suffixes = CHART_SUFFIXES
            handler = getattr(self, f"{which}_drop_handler")
            droptarget = FileDropTarget(
                drophandlers=dict.fromkeys(suffixes, handler), parent=self
            )
            droptarget.install_on(ctrl)

        self.mr_update_controls()

    def _guard(self) -> _GuardContext:
        """Return a context manager that suppresses re-entrant handlers.

        Returns:
            _GuardContext: A context manager toggling :attr:`_updating`.
        """
        return _GuardContext(self)

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        """Build the settings grid, Measure button and info panel."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header label (bold, matching wx's ``init_controls`` font-weight bump
        # for ``mr_settings_label`` alongside the other tabs' headers).
        self.mr_settings_label = QLabel(lang.getstr("verification.settings"))
        self.mr_settings_label.setContentsMargins(16, 14, 0, 10)
        header_font = self.mr_settings_label.font()
        header_font.setBold(True)
        self.mr_settings_label.setFont(header_font)
        root.addWidget(self.mr_settings_label)

        # 2-column settings grid.
        grid_host = QWidget()
        self._grid = QGridLayout(grid_host)
        self._grid.setContentsMargins(16, 0, 16, 16)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(8)
        self._grid.setColumnStretch(1, 1)
        self._row = 0

        self._build_chart_row()
        self.chart_meas_time = QLabel("")
        self._add_row(None, self.chart_meas_time)
        self._build_whitepoint_row()
        self._build_simulation_rows()
        self._build_trc_row()
        self._build_devlink_row()
        self._build_output_row()
        root.addWidget(grid_host)

        # Measure button (wx inserts it between the grid and info panel,
        # right-aligned) -- only for the standalone window; the embedded
        # Verification tab uses the shared action-bar button instead (see
        # :meth:`__init__`).
        if self._show_measure_button:
            button_row = QHBoxLayout()
            button_row.setContentsMargins(0, 0, 16, 16)
            button_row.addStretch(1)
            self.measurement_report_btn = QPushButton(lang.getstr("measure"))
            self.measurement_report_btn.setDefault(True)
            self.measurement_report_btn.clicked.connect(self._measure_btn_clicked)
            button_row.addWidget(self.measurement_report_btn)
            root.addLayout(button_row)

        root.addWidget(self._build_info_panel(), 1)

    def _measure_btn_clicked(self) -> None:
        """Emit :attr:`measure_requested`, reporting whether Alt is held.

        Qt equivalent of wx's ``wx.GetKeyState(wx.WXK_ALT)`` read in
        ``measurement_report_handler`` -- holding Alt while clicking requests
        a self-check report instead of a real measurement.
        """
        self_check_report = bool(QApplication.keyboardModifiers() & Qt.AltModifier)
        self.measure_requested.emit(self_check_report)

    def _add_row(self, left: QWidget | None, right: QWidget) -> None:
        """Add a label/control pair to the settings grid.

        Args:
            left (QWidget | None): The left-column widget, or ``None`` for the
                wx spacer rows.
            right (QWidget): The right-column control.
        """
        if left is not None:
            self._grid.addWidget(left, self._row, 0, Qt.AlignVCenter)
        self._grid.addWidget(right, self._row, 1)
        self._row += 1

    def _build_chart_row(self) -> None:
        """Build the chart/reference row: browse + fields + edit + patch count."""
        self.testchart_or_reference_label = QLabel(
            lang.getstr("testchart_or_reference")
        )
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.chart_ctrl = _FileBrowse(name_func=friendly_file_name)
        layout.addWidget(self.chart_ctrl, 1)
        self.fields_ctrl = QComboBox()
        self.fields_ctrl.addItems(["CMYK", "LAB", "RGB", "XYZ"])
        self.fields_ctrl.activated.connect(lambda _i: self.fields_ctrl_handler(True))
        layout.addWidget(self.fields_ctrl)
        self.chart_btn = QPushButton()
        pixmap = get_theme_pixmap(16, "rgbsquares")
        if not pixmap.isNull():
            self.chart_btn.setIcon(QIcon(pixmap))
        self.chart_btn.setToolTip(lang.getstr("testchart.edit"))
        self.chart_btn.setFlat(True)
        self.chart_btn.setFixedWidth(28)
        self.chart_btn.clicked.connect(self.chart_btn_handler)
        layout.addWidget(self.chart_btn)
        self.chart_patches_amount = QLabel("0")
        self.chart_patches_amount.setFixedWidth(48)
        layout.addWidget(self.chart_patches_amount)
        self._add_row(self.testchart_or_reference_label, row)

    def _build_whitepoint_row(self) -> None:
        """Build the simulate-whitepoint / relative checkbox row."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.simulate_whitepoint_cb = QCheckBox(lang.getstr("whitepoint.simulate"))
        self.simulate_whitepoint_cb.toggled.connect(
            self.simulate_whitepoint_ctrl_handler
        )
        layout.addWidget(self.simulate_whitepoint_cb)
        self.simulate_whitepoint_relative_cb = QCheckBox(
            lang.getstr("whitepoint.simulate.relative")
        )
        self.simulate_whitepoint_relative_cb.toggled.connect(
            self.simulate_whitepoint_relative_ctrl_handler
        )
        layout.addWidget(self.simulate_whitepoint_relative_cb)
        layout.addStretch(1)
        self._add_row(None, row)

    def _build_simulation_rows(self) -> None:
        """Build the simulation-profile checkbox/browse and the output rows."""
        self.simulation_profile_cb = QCheckBox(lang.getstr("simulation_profile"))
        self.simulation_profile_cb.toggled.connect(
            self.use_simulation_profile_ctrl_handler
        )
        self.simulation_profile_ctrl = _FileBrowse(name_func=friendly_file_name)
        self._add_row(self.simulation_profile_cb, self.simulation_profile_ctrl)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.use_simulation_profile_as_output_cb = QCheckBox(
            lang.getstr("use_simulation_profile_as_output")
        )
        self.use_simulation_profile_as_output_cb.toggled.connect(
            self.use_simulation_profile_as_output_handler
        )
        layout.addWidget(self.use_simulation_profile_as_output_cb)
        self.enable_3dlut_cb = QCheckBox(lang.getstr("3dlut.enable"))
        self.enable_3dlut_cb.toggled.connect(self.enable_3dlut_handler)
        layout.addWidget(self.enable_3dlut_cb)
        layout.addStretch(1)
        self._add_row(None, row)

    def _build_trc_row(self) -> None:
        """Build the tone-response target label + apply-mode block."""
        self.mr_trc_label = QLabel(lang.getstr("trc"))
        self._add_row(self.mr_trc_label, self._build_trc_block())

    def _build_trc_block(self) -> QWidget:
        """Build the unmodified / black-offset / TRC radio block.

        Returns:
            QWidget: The container for the wx single-column TRC sub-sizer.
        """
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._trc_apply_group = QButtonGroup(self)

        # Unmodified radio + input-value clipping warning.
        none_row = QWidget()
        none_layout = QHBoxLayout(none_row)
        none_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_none_ctrl = QRadioButton(lang.getstr("unmodified"))
        self.apply_none_ctrl.toggled.connect(self.apply_trc_ctrl_handler)
        self._trc_apply_group.addButton(self.apply_none_ctrl)
        none_layout.addWidget(self.apply_none_ctrl)
        self.input_value_clipping_bmp = QLabel()
        pixmap = get_theme_pixmap(16, "dialog-warning")
        if not pixmap.isNull():
            self.input_value_clipping_bmp.setPixmap(pixmap)
        self.input_value_clipping_bmp.setVisible(False)
        none_layout.addWidget(self.input_value_clipping_bmp)
        self.input_value_clipping_label = QLabel(
            lang.getstr("warning.input_value_clipping")
        )
        self.input_value_clipping_label.setStyleSheet("color: #F07F00")
        self.input_value_clipping_label.setVisible(False)
        none_layout.addWidget(self.input_value_clipping_label)
        none_layout.addStretch(1)
        layout.addWidget(none_row)

        # Apply black output offset radio.
        self.apply_black_offset_ctrl = QRadioButton(
            lang.getstr("apply_black_output_offset")
        )
        self.apply_black_offset_ctrl.toggled.connect(self.apply_trc_ctrl_handler)
        self._trc_apply_group.addButton(self.apply_black_offset_ctrl)
        layout.addWidget(self.apply_black_offset_ctrl)

        # Apply TRC radio + tone-curve chooser + gamma + gamma type.
        trc_row = QWidget()
        trc_layout = QHBoxLayout(trc_row)
        trc_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_trc_ctrl = QRadioButton()
        self.apply_trc_ctrl.toggled.connect(self.apply_trc_ctrl_handler)
        self._trc_apply_group.addButton(self.apply_trc_ctrl)
        trc_layout.addWidget(self.apply_trc_ctrl)
        self.mr_trc_ctrl = QComboBox()
        self.mr_trc_ctrl.setEnabled(False)
        self.mr_trc_ctrl.activated.connect(self.mr_trc_ctrl_handler)
        trc_layout.addWidget(self.mr_trc_ctrl)
        self.mr_trc_gamma_label = QLabel(lang.getstr("trc.gamma"))
        self.mr_trc_gamma_label.setEnabled(False)
        trc_layout.addWidget(self.mr_trc_gamma_label)
        self.mr_trc_gamma_ctrl = QComboBox()
        self.mr_trc_gamma_ctrl.setEditable(True)
        self.mr_trc_gamma_ctrl.addItems(["2.2", "2.4"])
        self.mr_trc_gamma_ctrl.setFixedWidth(80)
        self.mr_trc_gamma_ctrl.setEnabled(False)
        self.mr_trc_gamma_ctrl.activated.connect(
            lambda _i: self.mr_trc_gamma_ctrl_handler()
        )
        self.mr_trc_gamma_ctrl.lineEdit().editingFinished.connect(
            self.mr_trc_gamma_ctrl_handler
        )
        trc_layout.addWidget(self.mr_trc_gamma_ctrl)
        self.mr_trc_gamma_type_ctrl = QComboBox()
        self.mr_trc_gamma_type_ctrl.setEnabled(False)
        self.mr_trc_gamma_type_ctrl.activated.connect(
            self.mr_trc_gamma_type_ctrl_handler
        )
        trc_layout.addWidget(self.mr_trc_gamma_type_ctrl)
        trc_layout.addStretch(1)
        layout.addWidget(trc_row)

        layout.addWidget(self._build_black_offset_row())
        return block

    def _build_black_offset_row(self) -> QWidget:
        """Build the black-output-offset label + slider + spin row.

        Returns:
            QWidget: The black-output-offset row widget.
        """
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mr_black_output_offset_label = QLabel(
            lang.getstr("calibration.black_output_offset")
        )
        self.mr_black_output_offset_label.setEnabled(False)
        self.mr_black_output_offset_label.setVisible(False)
        layout.addWidget(self.mr_black_output_offset_label)
        self.mr_black_output_offset_ctrl = QSlider(Qt.Horizontal)
        self.mr_black_output_offset_ctrl.setRange(0, 100)
        self.mr_black_output_offset_ctrl.setFixedWidth(128)
        self.mr_black_output_offset_ctrl.setEnabled(False)
        self.mr_black_output_offset_ctrl.setVisible(False)
        self.mr_black_output_offset_ctrl.valueChanged.connect(
            self._on_black_offset_slider
        )
        layout.addWidget(self.mr_black_output_offset_ctrl)
        self.mr_black_output_offset_intctrl = QSpinBox()
        self.mr_black_output_offset_intctrl.setRange(0, 100)
        self.mr_black_output_offset_intctrl.setEnabled(False)
        self.mr_black_output_offset_intctrl.setVisible(False)
        self.mr_black_output_offset_intctrl.valueChanged.connect(
            self._on_black_offset_spin
        )
        layout.addWidget(self.mr_black_output_offset_intctrl)
        self.mr_black_output_offset_intctrl_label = QLabel("%")
        self.mr_black_output_offset_intctrl_label.setEnabled(False)
        self.mr_black_output_offset_intctrl_label.setVisible(False)
        layout.addWidget(self.mr_black_output_offset_intctrl_label)
        layout.addStretch(1)
        return row

    def _build_devlink_row(self) -> None:
        """Build the device-link profile checkbox/browse row."""
        self.devlink_profile_cb = QCheckBox(lang.getstr("devicelink_profile"))
        self.devlink_profile_cb.toggled.connect(self.use_devlink_profile_ctrl_handler)
        self.devlink_profile_ctrl = _FileBrowse(name_func=friendly_file_name)
        self._add_row(self.devlink_profile_cb, self.devlink_profile_ctrl)

        # Hint shown when the simulation profile stands in as the display
        # profile but no device link is used, i.e. no 3D LUT gets verified.
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.devlink_profile_missing_bmp = QLabel()
        pixmap = get_theme_pixmap(16, "dialog-warning")
        if not pixmap.isNull():
            self.devlink_profile_missing_bmp.setPixmap(pixmap)
        layout.addWidget(self.devlink_profile_missing_bmp, 0, Qt.AlignTop)
        self.devlink_profile_missing_label = QLabel(
            lang.getstr("warning.devlink_profile.missing")
        )
        self.devlink_profile_missing_label.setStyleSheet("color: #F07F00")
        self.devlink_profile_missing_label.setWordWrap(True)
        layout.addWidget(self.devlink_profile_missing_label, 1)
        self.devlink_profile_missing_row = row
        row.setVisible(False)
        self._add_row(None, row)

    def _build_output_row(self) -> None:
        """Build the output-profile label + browse + current button row."""
        self.output_profile_label = QLabel(lang.getstr("output.profile"))
        self.output_profile_label.setVisible(False)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.output_profile_ctrl = _FileBrowse(name_func=friendly_file_name)
        self.output_profile_ctrl.setVisible(False)
        layout.addWidget(self.output_profile_ctrl, 1)
        self.output_profile_current_btn = QPushButton(lang.getstr("profile.current"))
        self.output_profile_current_btn.setVisible(False)
        self.output_profile_current_btn.clicked.connect(
            self.output_profile_current_ctrl_handler
        )
        layout.addWidget(self.output_profile_current_btn)
        self._add_row(self.output_profile_label, row)

    def _build_info_panel(self) -> QWidget:
        """Build the bottom info panel (icon + explanatory text).

        Returns:
            QWidget: The info panel widget.
        """
        panel = QWidget()
        # wx's info panel doesn't set an explicit background either (it
        # inherits the app's BGCOLOUR/FGCOLOUR like everything else) --
        # matches DisplayCAL.ui.main_window.MainWindow._build_info_panel's
        # equivalent for the other four tabs, so this one follows the app's
        # light/dark theme instead of staying hardcoded white.
        # The rule must be scoped by object name: an unscoped declaration is
        # an implicit universal ("*") selector, so it would paint its own
        # top border on every descendant widget (the icon and text labels)
        # instead of just the panel.
        panel.setObjectName("infoPanel")
        panel.setStyleSheet("QWidget#infoPanel { border-top: 1px solid palette(mid); }")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 8, 16, 16)
        info_row = QHBoxLayout()
        icon = QLabel()
        pixmap = get_theme_pixmap(32, "dialog-information")
        if not pixmap.isNull():
            icon.setPixmap(pixmap)
        icon.setAlignment(Qt.AlignTop)
        info_row.addWidget(icon)
        self.mr_settings_info_text = QLabel(info_text_html("info.mr_settings"))
        self.mr_settings_info_text.setTextFormat(Qt.RichText)
        self.mr_settings_info_text.setWordWrap(True)
        self.mr_settings_info_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        info_row.addWidget(self.mr_settings_info_text, 1)
        outer.addLayout(info_row)
        return panel

    # -- language / combo population ---------------------------------------

    def mr_setup_language(self) -> None:
        """Populate combo boxes and configure the file-browse controls."""
        specs = {
            "chart": (
                "measurement_report_choose_chart_or_reference",
                f"{lang.getstr('filetype.ti1_ti3_txt')} "
                "(*.cgats *.cie *.ti1 *.ti2 *.ti3 *.txt)",
            ),
            "simulation_profile": (
                "simulation_profile",
                f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
            ),
            "devlink_profile": (
                "devicelink_profile",
                f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
            ),
            "output_profile": (
                "measurement_report_choose_profile",
                f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
            ),
        }
        for which, (msg, wildcard) in specs.items():
            ctrl = getattr(self, f"{which}_ctrl")
            ctrl._dialog_title = lang.getstr(msg)
            ctrl._wildcard = wildcard
            ctrl.setToolTip(lang.getstr(msg).rstrip(":"))

        self.mr_trc_ctrl.clear()
        self.mr_trc_ctrl.addItems([lang.getstr(item) for item in TRC_ITEMS])

        self.trc_gamma_types_ab = {0: "b", 1: "B"}
        self.trc_gamma_types_ba = {"b": 0, "B": 1}
        self.mr_trc_gamma_type_ctrl.clear()
        self.mr_trc_gamma_type_ctrl.addItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )

    def _chart_history(self) -> list[str]:
        """Return the sorted chart/reference drop-down history.

        Returns:
            list[str]: Absolute paths of the bundled reference charts.
        """
        wildcard = r"\.(cie|ti1|ti3)$"
        paths = get_data_path("ref", wildcard) or []
        history = []
        for path in paths:
            basepath, _ext = os.path.splitext(path)
            if not (path.lower().endswith(".ti2") and f"{basepath}.cie" in paths):
                history.append(path)
        natsort_key = natsort_key_factory()
        return sorted(history, key=lambda p: natsort_key(os.path.basename(p)))

    def _simulation_history(self) -> list[str]:
        """Return the simulation-profile drop-down history.

        Returns:
            list[str]: Absolute paths of the bundled standard profiles, unique
            by basename.
        """
        history = []
        basenames = []
        for path in config.get_standard_profiles(True):
            basename = os.path.basename(path)
            if basename not in basenames:
                basenames.append(basename)
                history.append(path)
        natsort_key = natsort_key_factory()
        return sorted(history, key=lambda p: natsort_key(os.path.basename(p)))

    # -- TRC controls ------------------------------------------------------

    def apply_trc_ctrl_handler(self, _checked: bool = False) -> None:
        """Persist the apply-mode radio selection.

        Args:
            _checked (bool): Unused Qt toggle state.
        """
        if self._updating:
            return
        setcfg("measurement_report.apply_trc", int(self.apply_trc_ctrl.isChecked()))
        setcfg(
            "measurement_report.apply_black_offset",
            int(self.apply_black_offset_ctrl.isChecked()),
        )
        self.mr_update_main_controls()

    def _on_black_offset_slider(self, value: int) -> None:
        """Handle the black-output-offset slider moving.

        Args:
            value (int): New slider value (0..100).
        """
        if self._updating:
            return
        with self._guard():
            self.mr_black_output_offset_intctrl.setValue(value)
        self._commit_black_output_offset(value)

    def _on_black_offset_spin(self, value: int) -> None:
        """Handle the black-output-offset spin box changing.

        Args:
            value (int): New spin value (0..100).
        """
        if self._updating:
            return
        with self._guard():
            self.mr_black_output_offset_ctrl.setValue(value)
        self._commit_black_output_offset(value)

    def _commit_black_output_offset(self, value: int) -> None:
        """Persist the black-output-offset percentage and refresh the TRC label.

        Args:
            value (int): The offset percentage (0..100).
        """
        v = value / 100.0
        if v != getcfg("measurement_report.trc_output_offset"):
            setcfg("measurement_report.trc_output_offset", v)
            self.mr_update_trc_control()

    def mr_trc_gamma_ctrl_handler(self) -> None:
        """Validate and persist the TRC gamma value."""
        if self._updating:
            return
        try:
            v = float(self.mr_trc_gamma_ctrl.currentText().replace(",", "."))
            if (
                v < config.VALID_RANGES["measurement_report.trc_gamma"][0]
                or v > config.VALID_RANGES["measurement_report.trc_gamma"][1]
            ):
                raise ValueError
        except ValueError:
            with self._guard():
                self.mr_trc_gamma_ctrl.setEditText(
                    str(getcfg("measurement_report.trc_gamma"))
                )
            return
        if str(v) != self.mr_trc_gamma_ctrl.currentText():
            with self._guard():
                self.mr_trc_gamma_ctrl.setEditText(str(v))
        if v != getcfg("measurement_report.trc_gamma"):
            setcfg("measurement_report.trc_gamma", v)
            self.mr_update_trc_control()
            self.mr_show_trc_controls()

    def mr_trc_ctrl_handler(self, _index: int = 0) -> None:
        """Handle the tone-curve chooser selection.

        Args:
            _index (int): Unused Qt combo index.
        """
        selection = self.mr_trc_ctrl.currentIndex()
        if selection == 1:
            # BT.1886
            setcfg("measurement_report.trc_gamma", 2.4)
            setcfg("measurement_report.trc_gamma_type", "B")
            setcfg("measurement_report.trc_output_offset", 0.0)
            self.mr_update_trc_controls()
        elif selection == 0:
            # Pure power gamma 2.2
            setcfg("measurement_report.trc_gamma", 2.2)
            setcfg("measurement_report.trc_gamma_type", "b")
            setcfg("measurement_report.trc_output_offset", 1.0)
            self.mr_update_trc_controls()
        else:
            # Custom
            self.mr_trc_gamma_ctrl.setFocus()
            self.mr_trc_gamma_ctrl.lineEdit().selectAll()
        self.mr_show_trc_controls()

    def mr_trc_gamma_type_ctrl_handler(self, _index: int = 0) -> None:
        """Persist the TRC gamma-type selection.

        Args:
            _index (int): Unused Qt combo index.
        """
        v = self.trc_gamma_types_ab[self.mr_trc_gamma_type_ctrl.currentIndex()]
        if v != getcfg("measurement_report.trc_gamma_type"):
            setcfg("measurement_report.trc_gamma_type", v)
            self.mr_update_trc_control()
            self.mr_show_trc_controls()

    def mr_update_trc_control(self) -> None:
        """Sync the tone-curve chooser selection to the current config."""
        with self._guard():
            if (
                getcfg("measurement_report.trc_gamma_type") == "B"
                and getcfg("measurement_report.trc_output_offset") == 0
                and getcfg("measurement_report.trc_gamma") == 2.4
            ):
                self.mr_trc_ctrl.setCurrentIndex(1)  # BT.1886
            elif (
                getcfg("measurement_report.trc_gamma_type") == "b"
                and getcfg("measurement_report.trc_output_offset") == 1
                and getcfg("measurement_report.trc_gamma") == 2.2
            ):
                self.mr_trc_ctrl.setCurrentIndex(0)  # Pure power gamma 2.2
            else:
                self.mr_trc_ctrl.setCurrentIndex(2)  # Custom

    def mr_update_trc_controls(self) -> None:
        """Sync every TRC control to the current config."""
        self.mr_update_trc_control()
        with self._guard():
            self.mr_trc_gamma_ctrl.setEditText(
                str(getcfg("measurement_report.trc_gamma"))
            )
            self.mr_trc_gamma_type_ctrl.setCurrentIndex(
                self.trc_gamma_types_ba[getcfg("measurement_report.trc_gamma_type")]
            )
            outoffset = int(getcfg("measurement_report.trc_output_offset") * 100)
            self.mr_black_output_offset_ctrl.setValue(outoffset)
            self.mr_black_output_offset_intctrl.setValue(outoffset)

    def mr_show_trc_controls(self) -> None:
        """Show/hide/enable the TRC controls based on the current selection."""
        shown = self.apply_trc_ctrl.isVisible()
        enable6 = shown and bool(getcfg("measurement_report.apply_trc"))
        show = shown and (
            self.mr_trc_ctrl.currentIndex() == 2 or getcfg("show_advanced_options")
        )
        has_bp = bool(self.XYZbpout and self.XYZbpout > [0, 0, 0])
        self.mr_trc_ctrl.setEnabled(enable6)
        self.mr_trc_ctrl.setVisible(shown)
        self.mr_trc_gamma_label.setEnabled(enable6)
        self.mr_trc_gamma_label.setVisible(show)
        self.mr_trc_gamma_ctrl.setEnabled(enable6)
        self.mr_trc_gamma_ctrl.setVisible(show)
        self.mr_trc_gamma_type_ctrl.setEnabled(enable6)
        self.mr_black_output_offset_label.setEnabled(enable6 and has_bp)
        self.mr_black_output_offset_label.setVisible(show and has_bp)
        self.mr_black_output_offset_ctrl.setEnabled(enable6 and has_bp)
        self.mr_black_output_offset_ctrl.setVisible(show and has_bp)
        self.mr_black_output_offset_intctrl.setEnabled(enable6 and has_bp)
        self.mr_black_output_offset_intctrl.setVisible(show and has_bp)
        self.mr_black_output_offset_intctrl_label.setEnabled(enable6 and has_bp)
        self.mr_black_output_offset_intctrl_label.setVisible(show and has_bp)
        self.mr_trc_gamma_type_ctrl.setVisible(show and has_bp)

    # -- chart -------------------------------------------------------------

    def chart_btn_handler(self, _checked: bool = False) -> None:
        """Request the test-chart editor be opened for the current chart."""
        self.edit_chart_requested.emit()

    def chart_ctrl_handler(self, event: object = True) -> None:
        """Load the selected chart and populate the fields chooser.

        Args:
            event (object): Truthy when triggered by the user.
        """
        chart = self.chart_ctrl.path()
        values: list[str] = []
        try:
            cgats = CGATS(chart)
        except (
            OSError,
            CGATSInvalidError,
            CGATSInvalidOperationError,
            CGATSKeyError,
            CGATSTypeError,
            CGATSValueError,
        ) as exception:
            self._error(str(exception))
        else:
            data_format = cgats.queryv1("DATA_FORMAT")
            accurate = cgats.queryv1("ACCURATE_EXPECTED_VALUES") == "true"
            if data_format:
                _basename, ext = os.path.splitext(chart)
                for column in data_format.values():
                    column_prefix = column.split(b"_")[0].decode("utf-8")
                    if (
                        column_prefix in ("CMYK", "LAB", "RGB", "XYZ")
                        and column_prefix not in values
                        and (
                            (
                                (ext.lower() == ".cie" or accurate)
                                and column_prefix in ("LAB", "XYZ")
                            )
                            or (
                                ext.lower() == ".ti1"
                                and column_prefix in ("CMYK", "RGB")
                            )
                            or (ext.lower() not in (".cie", ".ti1"))
                        )
                    ):
                        values.append(column_prefix)
                if values:
                    self.fields_ctrl.clear()
                    self.fields_ctrl.addItems(values)
                    if ext.lower() == ".ti1":
                        index = 0
                    elif "RGB" in values and ext.lower() != ".cie":
                        index = values.index("RGB")
                    elif "CMYK" in values:
                        index = values.index("CMYK")
                    elif "XYZ" in values:
                        index = values.index("XYZ")
                    elif "LAB" in values:
                        index = values.index("LAB")
                    else:
                        index = 0
                    self.fields_ctrl.setCurrentIndex(index)
                    setcfg("measurement_report.chart", chart)
                    self.chart_patches_amount.setText(
                        str(cgats.queryv1("NUMBER_OF_SETS") or "")
                    )
                    self.update_estimated_measurement_time("chart")
                    self.chart_white = cgats.get_white_cie()
            if not values:
                if chart:
                    self._error(
                        lang.getstr(
                            "error.testchart.missing_fields",
                            (chart, f"RGB/CMYK {lang.getstr('or')} LAB/XYZ"),
                        )
                    )
                self.chart_ctrl.set_path(getcfg("measurement_report.chart"))
            else:
                self.chart_btn.setEnabled("RGB" in values)
        self.fields_ctrl.setEnabled(self.fields_ctrl.count() > 1)
        self.fields_ctrl_handler(event)

    def chart_drop_handler(self, path: str) -> None:
        """Set the chart from a dropped file.

        Args:
            path (str): The dropped chart path.
        """
        if not self.worker.is_working():
            self.chart_ctrl.set_path(path)
            self.chart_ctrl_handler(True)

    def fields_ctrl_handler(self, event: object = True) -> None:
        """Persist the selected fields and refresh the main controls.

        Args:
            event (object): Truthy when triggered by the user.
        """
        setcfg("measurement_report.chart.fields", self.fields_ctrl.currentText())
        if event:
            self.mr_update_main_controls(event)

    def mr_set_testchart(self, path: str, load: bool = True) -> None:
        """Set the test chart shown in the chart control.

        Args:
            path (str): Path to the test chart file.
            load (bool): Load the chart and refresh the controls when True.
        """
        self.chart_ctrl.set_path(path)
        if load:
            self.chart_ctrl_handler(None)

    # -- whitepoint --------------------------------------------------------

    def _field_items(self) -> list[str]:
        """Return the current fields-chooser item labels.

        Returns:
            list[str]: The chart-field labels currently offered.
        """
        return [self.fields_ctrl.itemText(i) for i in range(self.fields_ctrl.count())]

    def set_simulate_whitepoint(
        self, set_whitepoint_simulate_relative: bool = False
    ) -> None:
        """Derive the whitepoint-simulation config from the current selection.

        Args:
            set_whitepoint_simulate_relative (bool): Also set the
                ``whitepoint.simulate`` key when True.
        """
        sim_profile = self.get_simulation_profile()
        is_prtr_profile = sim_profile and sim_profile.profileClass == b"prtr"
        field_items = self._field_items()
        if set_whitepoint_simulate_relative:
            setcfg(
                "measurement_report.whitepoint.simulate",
                int(
                    not getattr(self, "chart_white", None)
                    or "RGB" not in field_items
                    or is_prtr_profile
                ),
            )
        setcfg(
            "measurement_report.whitepoint.simulate.relative",
            int("LAB" in field_items or is_prtr_profile),
        )

    def simulate_whitepoint_ctrl_handler(self, _checked: bool = False) -> None:
        """Persist the simulate-whitepoint checkbox.

        Args:
            _checked (bool): Unused Qt toggle state.
        """
        if self._updating:
            return
        setcfg(
            "measurement_report.whitepoint.simulate",
            int(self.simulate_whitepoint_cb.isChecked()),
        )
        self.mr_update_main_controls()

    def simulate_whitepoint_relative_ctrl_handler(self, _checked: bool = False) -> None:
        """Persist the simulate-whitepoint-relative checkbox.

        Args:
            _checked (bool): Unused Qt toggle state.
        """
        if self._updating:
            return
        setcfg(
            "measurement_report.whitepoint.simulate.relative",
            int(self.simulate_whitepoint_relative_cb.isChecked()),
        )

    # -- simulation / devlink / output profiles ----------------------------

    def get_simulation_profile(self) -> ICCProfile | None:
        """Return the simulation profile if simulation is enabled.

        Returns:
            ICCProfile | None: The simulation profile, or a falsy value.
        """
        use_sim_profile = getcfg("measurement_report.use_simulation_profile")
        return use_sim_profile and getattr(self, "simulation_profile", None)

    def simulation_profile_ctrl_handler(self, event: object = True) -> None:
        """Handle a change to the simulation-profile control.

        Args:
            event (object): Truthy when triggered by the user.
        """
        self.set_profile("simulation")

    def simulation_profile_drop_handler(self, path: str) -> None:
        """Set the simulation profile from a dropped file.

        Args:
            path (str): The dropped profile path.
        """
        if not self.worker.is_working():
            self.simulation_profile_ctrl.set_path(path)
            self.set_profile("simulation")

    def devlink_profile_ctrl_handler(self, event: object = True) -> None:
        """Handle a change to the device-link profile control.

        Args:
            event (object): Truthy when triggered by the user.
        """
        self.set_profile("devlink")

    def devlink_profile_drop_handler(self, path: str) -> None:
        """Set the device-link profile from a dropped file.

        Args:
            path (str): The dropped profile path.
        """
        if not self.worker.is_working():
            self.devlink_profile_ctrl.set_path(path)
            self.set_profile("devlink")

    def output_profile_ctrl_handler(self, event: object = True) -> None:
        """Handle a change to the output-profile control.

        Args:
            event (object): Truthy when triggered by the user.
        """
        self.set_profile("output")

    def output_profile_drop_handler(self, path: str) -> None:
        """Set the output profile from a dropped file.

        Args:
            path (str): The dropped profile path.
        """
        if not self.worker.is_working():
            self.output_profile_ctrl.set_path(path)
            self.set_profile("output")

    def output_profile_current_ctrl_handler(self, _checked: bool = False) -> None:
        """Set the output profile to the currently installed display profile."""
        profile_path = get_current_profile_path(True, True)
        if profile_path and os.path.isfile(profile_path):
            self.output_profile_ctrl.set_path(profile_path)
            self.set_profile("output")

    def use_simulation_profile_as_output_handler(self, _checked: bool = False) -> None:
        """Persist the use-simulation-as-output checkbox.

        Args:
            _checked (bool): Unused Qt toggle state.
        """
        if self._updating:
            return
        setcfg(
            "measurement_report.use_simulation_profile_as_output",
            int(self.use_simulation_profile_as_output_cb.isChecked()),
        )
        self.mr_update_main_controls()

    def enable_3dlut_handler(self, _checked: bool = False) -> None:
        """Persist the enable-3D-LUT checkbox.

        Args:
            _checked (bool): Unused Qt toggle state.
        """
        if self._updating:
            return
        setcfg("3dlut.enable", int(self.enable_3dlut_cb.isChecked()))
        setcfg("measurement_report.use_devlink_profile", 0)
        self.mr_update_main_controls()

    def use_devlink_profile_ctrl_handler(self, _checked: bool = False) -> None:
        """Persist the use-device-link checkbox.

        Args:
            _checked (bool): Unused Qt toggle state.
        """
        if self._updating:
            return
        setcfg("3dlut.enable", 0)
        setcfg(
            "measurement_report.use_devlink_profile",
            int(self.devlink_profile_cb.isChecked()),
        )
        self.mr_update_main_controls()

    def set_profile_ctrl_path(self, which: str) -> None:
        """Reset a profile control's shown path from config.

        Args:
            which (str): One of ``"simulation"``, ``"devlink"``, ``"output"``.
        """
        getattr(self, f"{which}_profile_ctrl").set_path(
            getcfg(f"measurement_report.{which}_profile")
        )

    def set_profile(
        self, which: str, profile_path: str | None = None, silent: bool = False
    ) -> ICCProfile | None:
        """Validate and apply a profile for one of the profile controls.

        Standalone-window subset of the wx ``ReportFrame.set_profile`` (the
        blackpoint lookups for simulation/output and the profile-class checks
        are preserved).

        Args:
            which (str): One of ``"simulation"``, ``"devlink"``, ``"output"``.
            profile_path (str | None): Unused (kept for signature parity).
            silent (bool): Suppress error dialogs and config writes when True.

        Returns:
            ICCProfile | None: The applied profile, or ``None``.
        """
        path = getattr(self, f"{which}_profile_ctrl").path()
        if which == "output":
            profile = config.get_current_profile(True)
            path = profile.filename if profile else None
            setcfg("measurement_report.output_profile", path)
            XYZbpout = self.XYZbpout
            # Seed slightly above zero so output-offset controls show if the
            # selected profile doesn't exist.
            self.XYZbpout = [0.001, 0.001, 0.001]
        else:
            profile = None
        if not path and not profile:
            setattr(self, f"{which}_profile", None)
            if not silent:
                setcfg(f"measurement_report.{which}_profile", None)
                self.mr_update_main_controls()
            return None
        if path and not os.path.isfile(path):
            if not silent:
                self._error(lang.getstr("file.missing", path))
            return None
        if not profile:
            try:
                profile = ICCProfile(path)
            except ICCProfileInvalidError:
                if not silent:
                    self._error(f"{lang.getstr('profile.invalid')}\n{path}")
            except OSError as exception:
                if not silent:
                    self._error(str(exception))
        if profile:
            if (
                (
                    which == "simulation"
                    and (
                        profile.profileClass not in (b"mntr", b"prtr")
                        or profile.colorSpace not in (b"CMYK", b"RGB")
                    )
                )
                or (
                    which == "output"
                    and (
                        profile.profileClass != b"mntr" or profile.colorSpace != b"RGB"
                    )
                )
                or (which == "devlink" and profile.profileClass != b"link")
            ):
                if not silent:
                    self._error(
                        lang.getstr(
                            "profile.unsupported",
                            (
                                profile.profileClass.decode("utf-8"),
                                profile.colorSpace.decode("utf-8"),
                            ),
                        )
                    )
            else:
                result = self._apply_valid_profile(
                    which, profile, XYZbpout if which == "output" else None, silent
                )
                if result is not False:
                    return result
        if path:
            self.set_profile_ctrl_path(which)
        return None

    def _apply_valid_profile(
        self, which: str, profile: ICCProfile, XYZbpout: list | None, silent: bool
    ) -> ICCProfile | None | bool:
        """Apply an already class-validated profile and refresh dependents.

        Args:
            which (str): One of ``"simulation"``, ``"devlink"``, ``"output"``.
            profile (ICCProfile): The loaded, validated profile.
            XYZbpout (list | None): The cached output blackpoint to restore when
                the output-profile selection has not changed.
            silent (bool): Suppress config writes / follow-on handlers when True.

        Returns:
            ICCProfile | None | bool: The applied profile, or ``False`` on a
            recoverable lookup error (caller resets the control path).
        """
        changed = (
            not getattr(self, f"{which}_profile", None)
            or getattr(self, f"{which}_profile").filename != profile.filename
        )
        if changed:
            if which == "simulation":
                odata = self._lookup_blackpoint(profile)
                if odata is None:
                    return False
                self.XYZbpin = odata
            elif which == "output":
                odata = self._lookup_blackpoint(profile)
                if odata is None:
                    return False
                if odata[1]:
                    self.XYZbpout = odata
                else:
                    XYZbp = profile.get_chardata_bkpt()
                    self.XYZbpout = XYZbp if XYZbp else [0, 0, 0]
        elif which == "output":
            self.XYZbpout = XYZbpout
        setattr(self, f"{which}_profile", profile)
        if not silent:
            setcfg(f"measurement_report.{which}_profile", profile.filename)
            if which == "simulation":
                self.use_simulation_profile_ctrl_handler(None)
            elif self.XYZbpin is not None:
                self.mr_update_main_controls()
        return profile

    def _lookup_blackpoint(self, profile: ICCProfile) -> list | None:
        """Look up a profile's XYZ blackpoint via ``xicclu``.

        Args:
            profile (ICCProfile): The profile to look up.

        Returns:
            list | None: The XYZ blackpoint, or ``None`` on error (the control
            path is reset by the caller).
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

    def use_simulation_profile_ctrl_handler(
        self, event: object = True, update_trc: bool = True
    ) -> None:
        """Handle the use-simulation-profile checkbox and derive TRC defaults.

        Args:
            event (object): Truthy when triggered by the user (persists the
                checkbox); ``None`` when called programmatically.
            update_trc (bool): Recompute the TRC apply defaults when True.
        """
        if event:
            setcfg(
                "measurement_report.use_simulation_profile",
                int(self.simulation_profile_cb.isChecked()),
            )
        sim_profile = self.get_simulation_profile()
        enable = False
        if sim_profile:
            self.set_simulate_whitepoint()
            if (
                "rTRC" in sim_profile.tags
                and "gTRC" in sim_profile.tags
                and "bTRC" in sim_profile.tags
                and sim_profile.tags.rTRC
                == sim_profile.tags.gTRC
                == sim_profile.tags.bTRC
                and isinstance(sim_profile.tags.rTRC, CurveType)
            ):
                tf = sim_profile.tags.rTRC.get_transfer_function(outoffset=1.0)
                if update_trc or self.XYZbpin == self.XYZbpout:
                    setcfg(
                        "measurement_report.apply_black_offset",
                        int(
                            tf[0][1] not in (-240, -709)
                            and (not tf[0][0].startswith("Gamma") or tf[1] < 0.95)
                            and self.XYZbpin != self.XYZbpout
                        ),
                    )
                if update_trc:
                    setcfg(
                        "measurement_report.apply_trc",
                        int(
                            tf[0][1] in (-240, -709)
                            or (tf[0][0].startswith("Gamma") and tf[1] >= 0.95)
                        ),
                    )
                    if tf[0][0].startswith("Gamma") and tf[1] >= 0.95:
                        if not getcfg("measurement_report.trc_gamma.backup", False):
                            setcfg(
                                "measurement_report.trc_gamma.backup",
                                getcfg("measurement_report.trc_gamma"),
                            )
                        setcfg("measurement_report.trc_gamma", round(tf[0][1], 2))
                    elif getcfg("measurement_report.trc_gamma.backup", False):
                        setcfg(
                            "measurement_report.trc_gamma",
                            getcfg("measurement_report.trc_gamma.backup"),
                        )
                        setcfg("measurement_report.trc_gamma.backup", None)
                self.mr_update_trc_controls()
                enable = tf[0][1] not in (-240, -709) and self.XYZbpin != self.XYZbpout
            elif update_trc:
                enable = self.XYZbpin != self.XYZbpout
                setcfg("measurement_report.apply_black_offset", int(enable))
                setcfg("measurement_report.apply_trc", 0)
        self.apply_black_offset_ctrl.setEnabled(bool(sim_profile) and enable)
        self.mr_update_main_controls()

    # -- bulk control refresh ----------------------------------------------

    def mr_set_filebrowse_paths(self) -> None:
        """Populate history and reset the profile/chart control paths."""
        self.chart_ctrl.set_history(self._chart_history())
        self.simulation_profile_ctrl.set_history(self._simulation_history())
        for which in ("simulation", "devlink", "output"):
            self.set_profile_ctrl_path(which)
        chart = getcfg("measurement_report.chart")
        if not chart or not os.path.isfile(chart):
            chart = config.DEFAULTS["measurement_report.chart"]
            setcfg("measurement_report.chart", chart)
        self.mr_set_testchart(chart, load=False)

    def mr_update_controls(self, set_filebrowse_paths: bool = True) -> None:
        """Refresh every control from the current config.

        Args:
            set_filebrowse_paths (bool): Repopulate the chart/profile paths and
                history when True.
        """
        if set_filebrowse_paths:
            self.mr_set_filebrowse_paths()
        self.set_profile("simulation", silent=True)
        self.mr_update_trc_controls()
        self.set_profile("devlink", silent=True)
        self.set_profile("output", silent=True)
        self.chart_ctrl_handler(None)
        self.use_simulation_profile_ctrl_handler(None, update_trc=False)

    def mr_update_main_controls(self, event: object = None) -> None:
        """Show/hide/enable the main controls to match the current config.

        Args:
            event (object): Truthy when triggered by a user field change, in
                which case the whitepoint-simulation defaults are recomputed.
        """
        with self._guard():
            self._mr_update_main_controls(event)

    def _mr_update_main_controls(self, event: object) -> None:
        chart_has_white = bool(getattr(self, "chart_white", None))
        color = getcfg("measurement_report.chart.fields")
        sim_profile_color = (
            getattr(self, "simulation_profile", None)
            and self.simulation_profile.colorSpace
        )
        if isinstance(sim_profile_color, bytes):
            sim_profile_color = sim_profile_color.decode("utf-8")
        if getcfg("measurement_report.use_simulation_profile"):
            setcfg(
                "measurement_report.use_simulation_profile",
                int(sim_profile_color == color),
            )
        self.simulation_profile_cb.setEnabled(sim_profile_color == color)
        self.simulation_profile_cb.setVisible(color in ("CMYK", "RGB"))
        enable1 = bool(getcfg("measurement_report.use_simulation_profile"))
        enable2 = sim_profile_color == "RGB" and bool(
            getcfg("measurement_report.use_simulation_profile_as_output")
        )
        self.simulation_profile_cb.setChecked(enable1)
        self.simulation_profile_ctrl.setVisible(color in ("CMYK", "RGB"))
        self.use_simulation_profile_as_output_cb.setVisible(
            enable1 and sim_profile_color == "RGB"
        )
        self.use_simulation_profile_as_output_cb.setChecked(enable1 and enable2)
        self.enable_3dlut_cb.setEnabled(enable1 and enable2)
        self.enable_3dlut_cb.setChecked(
            enable1 and enable2 and bool(getcfg("3dlut.enable"))
        )
        self.enable_3dlut_cb.setVisible(
            enable1
            and sim_profile_color == "RGB"
            and config.get_display_name() in ("madVR", "Prisma")
        )
        enable5 = (
            sim_profile_color == "RGB"
            and isinstance(self.simulation_profile.tags.get("rXYZ"), XYZType)
            and isinstance(self.simulation_profile.tags.get("gXYZ"), XYZType)
            and isinstance(self.simulation_profile.tags.get("bXYZ"), XYZType)
            and not isinstance(self.simulation_profile.tags.get("A2B0"), LUT16Type)
        )
        self.mr_trc_label.setVisible(enable1 and enable5)
        self.apply_none_ctrl.setVisible(enable1 and enable5)
        self.apply_none_ctrl.setChecked(
            (
                not getcfg("measurement_report.apply_black_offset")
                and not getcfg("measurement_report.apply_trc")
            )
            or not enable5
        )
        self.apply_black_offset_ctrl.setVisible(enable1 and enable5)
        self.apply_black_offset_ctrl.setChecked(
            enable5 and bool(getcfg("measurement_report.apply_black_offset"))
        )
        self.apply_trc_ctrl.setVisible(enable1 and enable5)
        self.apply_trc_ctrl.setChecked(
            enable5 and bool(getcfg("measurement_report.apply_trc"))
        )
        enable6 = (
            enable1
            and enable5
            and bool(
                getcfg("measurement_report.apply_trc")
                or getcfg("measurement_report.apply_black_offset")
            )
        )
        self.mr_show_trc_controls()
        show = (
            self.apply_none_ctrl.isChecked()
            and enable1
            and enable5
            and self.XYZbpout is not None
            and self.XYZbpin is not None
            and self.XYZbpout > self.XYZbpin
        )
        self.input_value_clipping_bmp.setVisible(show)
        self.input_value_clipping_label.setVisible(show)
        if event:
            self.set_simulate_whitepoint(True)
        self.simulate_whitepoint_cb.setEnabled(
            (enable1 and not enable2) or (color in ("LAB", "XYZ") and chart_has_white)
        )
        enable3 = bool(getcfg("measurement_report.whitepoint.simulate"))
        self.simulate_whitepoint_cb.setChecked(
            ((enable1 and not enable2) or color in ("LAB", "XYZ")) and enable3
        )
        self.simulate_whitepoint_relative_cb.setEnabled(
            ((enable1 and not enable2) or color in ("LAB", "XYZ")) and enable3
        )
        self.simulate_whitepoint_relative_cb.setChecked(
            ((enable1 and not enable2) or color in ("LAB", "XYZ"))
            and enable3
            and bool(getcfg("measurement_report.whitepoint.simulate.relative"))
        )
        self.devlink_profile_cb.setVisible(enable1 and enable2)
        enable4 = bool(getcfg("measurement_report.use_devlink_profile"))
        self.devlink_profile_cb.setChecked(enable1 and enable2 and enable4)
        self.devlink_profile_ctrl.setEnabled(enable1 and enable2 and enable4)
        self.devlink_profile_ctrl.setVisible(enable1 and enable2)
        devlink_used = enable4 and os.path.isfile(
            getcfg("measurement_report.devlink_profile") or ""
        )
        # madVR/Prisma apply the 3D LUT themselves when it is enabled
        lut_in_renderer = config.get_display_name() in ("madVR", "Prisma") and bool(
            getcfg("3dlut.enable")
        )
        self.devlink_profile_missing_row.setVisible(
            enable1 and enable2 and not devlink_used and not lut_in_renderer
        )
        output_enabled = (color in ("LAB", "RGB", "XYZ") or enable1) and (
            not enable1
            or not enable2
            or self.apply_trc_ctrl.isChecked()
            or self.apply_black_offset_ctrl.isChecked()
        )
        self.output_profile_label.setEnabled(output_enabled)
        self.output_profile_ctrl.setEnabled(output_enabled)
        output_profile = bool(getattr(self, "output_profile", None))
        self._mr_can_measure = (
            (
                (
                    enable1
                    and enable2
                    and (not enable6 or output_profile)
                    and (
                        not enable4
                        or (
                            bool(getcfg("measurement_report.devlink_profile"))
                            and os.path.isfile(
                                getcfg("measurement_report.devlink_profile")
                            )
                        )
                    )
                )
                or (
                    (
                        (not enable1 and color in ("LAB", "RGB", "XYZ"))
                        or (enable1 and sim_profile_color == color and not enable2)
                    )
                    and output_profile
                )
            )
            and bool(getcfg("measurement_report.chart"))
            and os.path.isfile(getcfg("measurement_report.chart"))
        )
        if self._show_measure_button:
            self.measurement_report_btn.setEnabled(self._mr_can_measure)

    def can_measure(self) -> bool:
        """Whether the current settings allow a report measurement to run.

        For the embedded Verification tab (no internal button), the Qt main
        window's shared action-bar Measure button uses this to mirror what
        the standalone window would otherwise show via
        :attr:`measurement_report_btn`'s enabled state.

        Returns:
            bool: True if a report measurement/self-check can be started.
        """
        return self._mr_can_measure

    # -- estimated measurement time ----------------------------------------

    def update_estimated_measurement_time(
        self, which: str, patches: int | None = None
    ) -> None:
        """Update the estimated-measurement-time label for ``which``.

        Args:
            which (str): The row prefix, e.g. ``"chart"``.
            patches (int | None): Patch count; taken from the patch-count label
                when omitted.
        """
        integration_time = self.worker.get_instrument_features().get("integration_time")
        if integration_time:
            if which == "chart" and not patches:
                patches = int(self.chart_patches_amount.text())
            opatches = patches
            tech = getcfg("display.technology").lower()
            if isinstance(tech, bytes):
                tech = tech.decode("utf-8")
            prop = [1, 1]
            if "plasma" in tech or "crt" in tech:
                prop[0] = 1.9
            elif "projector" in tech or "dlp" in tech:
                prop[0] = 2.2
                prop[1] = 2.2
            elif "oled" in tech:
                prop[0] = 2.2
            integration_time = [
                min(prop[i] * v, 20) for i, v in enumerate(integration_time)
            ]
            tpp = list(integration_time)
            if (
                "plasma" in tech
                or "crt" in tech
                or "projector" in tech
                or "dlp" in tech
            ) and self.worker.get_instrument_features().get("refresh"):
                tpp = [v + 0.25 for v in tpp]
            if config.get_display_name() == "madVR":
                tpp = [v + 0.45 for v in tpp]
            min_delay_s = 0.2
            if getcfg("measure.override_min_display_update_delay_ms"):
                min_delay_ms = getcfg("measure.min_display_update_delay_ms")
                min_delay_s = max(min_delay_ms / 1000.0, min_delay_s)
            if getcfg("measure.override_display_settle_time_mult"):
                settle_mult = getcfg("measure.display_settle_time_mult")
            else:
                settle_mult = 1.0
            tpp = [v + min_delay_s + 0.145 * settle_mult for v in tpp]
            avg_delay = sum(tpp) / (8 / 3.0)
            seconds = avg_delay * patches
            oseconds = seconds
            if getcfg("drift_compensation.blacklevel"):
                seconds += math.ceil(oseconds / 60.0) * ((20 - tpp[0]) / 2.0 + tpp[0])
                seconds += math.ceil(opatches / 40.0) * ((20 - tpp[0]) / 2.0 + tpp[0])
            if getcfg("drift_compensation.whitelevel"):
                seconds += math.ceil(oseconds / 60.0) * tpp[1]
                seconds += math.ceil(opatches / 40.0) * tpp[1]
            if (
                which in ("testchart", "chart")
                and getcfg("testchart.patch_sequence")
                != "optimize_display_response_delay"
            ):
                seconds -= 0.65 / 1.75 * patches
                seconds += 0.65 * patches
            timestamp = gmtime(seconds)
            hours = int(strftime("%H", timestamp))
            minutes = int(strftime("%M", timestamp))
            minutes += math.ceil(int(strftime("%S", timestamp)) / 60.0)
            if minutes > 59:
                minutes = 0
                hours += 1
        else:
            hours, minutes = "--", "--"
        label = getattr(self, f"{which}_meas_time")
        label.setText(lang.getstr("estimated_measurement_time", (hours, minutes)))
        if hours != "--" and hours > 7:
            color = "#FF3300"
        elif hours != "--" and hours > 3:
            color = "#F07F00"
        else:
            color = ""
        label.setStyleSheet(f"color: {color}" if color else "")

    # -- misc --------------------------------------------------------------

    def _error(self, message: str) -> None:
        """Show a modal error dialog.

        Args:
            message (str): The message to display.
        """
        message_box.critical(self, lang.getstr("error"), message)


class ReportWindow(BaseWindow):
    """Standalone top-level window wrapping :class:`ReportPanel`.

    Used by the ``python -m DisplayCAL.ui.measurement_report`` entry point
    (:func:`main`); the Qt main window instead embeds a bare
    :class:`ReportPanel` directly as its Verification tab. Every attribute
    not found on the window itself (e.g. ``measurement_report_btn``,
    ``mr_update_controls``, the ``measure_requested``/``edit_chart_requested``
    signals) is transparently forwarded to the wrapped panel.

    Args:
        parent (QWidget | None): Optional parent window.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent=parent,
            name="reportframe",
            title=lang.getstr("measurement_report"),
            icon_name=APPNAME.lower(),
        )
        self.panel = ReportPanel(self)
        self.setCentralWidget(self.panel)
        self.restore_position()

    def __getattr__(self, name: str):
        # Only consulted when normal attribute lookup fails, so this never
        # shadows anything defined on ``BaseWindow``/``ReportWindow`` itself.
        return getattr(self.panel, name)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist geometry and config before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        # BaseWindow.closeEvent persists the window position; mirror the wx
        # frame's OnClose by flushing config to disk as well.
        super().closeEvent(event)
        config.writecfg()


def main() -> int:
    """Entry point for the standalone Qt measurement-report window.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg()
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = ReportWindow()
    app.top_window = window
    window.measure_requested.connect(
        lambda: window.measurement_report_btn.setEnabled(True)
    )
    window.show()
    window.listen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
