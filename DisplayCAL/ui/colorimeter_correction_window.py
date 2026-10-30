"""Colorimeter-correction creation window — Qt port.

Qt equivalent of the "create wizard" part of
:meth:`DisplayCAL.display_cal.MainFrame.create_colorimeter_correction_handler`
(the 1700-line handler that builds a CCMX or CCSS colorimeter-correction file
from one or two ``.ti3`` measurement files): correction type (matrix/spectral,
optional four-color-matrix method), reference and colorimeter
instrument/measurement-mode/observer/TI3 selection, the auto-derived
description/display/manufacturer/technology metadata, and — unlike the other
ported settings windows — the actual Argyll run (``spec2cie`` / ``ccxxmake`` /
:meth:`DisplayCAL.worker.Worker.create_ccxx`), because producing a correction
file needs only the worker and TI3 files already on disk, not a live display
(the same reasoning that let :mod:`DisplayCAL.ui.tools.lut3d` run
``collink`` standalone).

Reuses the toolkit-neutral :mod:`DisplayCAL.colorimeter_correction` helpers
(``inject_ccxx_metadata``, ``get_cgats_path``) shared with the still-shipping
wx path.

Deliberately dropped / simplified versus the wx handler:

* The "Measure reference" / "Measure colorimeter" buttons need to switch the
  live instrument/display and drive the full measurement flow (main-window
  territory), so — matching the deferral :class:`DisplayCAL.ui.measure_frame
  .MeasureFrame` and :class:`DisplayCAL.ui.measurement_report.ReportWindow`
  made for their own Measure buttons — they only emit
  :attr:`CreateCorrectionWindow.measure_reference_requested` /
  :attr:`.measure_colorimeter_requested` here; the actual instrument switch
  and measurement run live in :meth:`DisplayCAL.ui.main_window.MainWindow
  ._ccxx_measure_requested`, which reuses the same "characterize only, no
  colprof" pipeline as the standalone "Measure testchart..." tool
  (:meth:`~DisplayCAL.ui.main_window.MainWindow
  ._measure_testchart_action_handler`).
* TI3 controls only accept ``.ti3`` files (the wx path also accepted
  ``.icc``/``.icm`` and derived a synthetic EDID-based measurement via
  ``ti1_lookup_to_ti3``; that alternate input path is dropped).
* The web-check / import / upload entry points, and the ``CCXXPlot``
  spectral/matrix visualization, are separate features left for future slices
  (the plan already tracked import/upload as their own items).
* The ``spec2cie`` reference-observer override (converting spectral reference
  data to a non-default observer before ``ccxxmake`` runs) and the
  provenance-only ``REFERENCE_FILENAME`` / ``*_HASH`` metadata fields are not
  reproduced; both are refinements on top of an already-correct correction
  file, not required to produce one.

The reference-vs-corrected preview grid (with per-patch xyY + delta-E*00 and
sRGB swatches) is kept as a modal :class:`_PreviewDialog`, the Qt stand-in for
the wx confirmation dialog shown before saving a two-file (CCMX) correction.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import argyll_instruments, colord, colormath
from DisplayCAL import colorimeter_correction as ccxx_helpers
from DisplayCAL import localization as lang
from DisplayCAL.argyll import get_argyll_version
from DisplayCAL.argyll_instruments import get_canonical_instrument_name
from DisplayCAL.cgats import CGATS, CGATSError
from DisplayCAL.config import DEFAULTS, get_argyll_data_dir, getcfg, setcfg
from DisplayCAL.edid import PNP_ID_CACHE, get_manufacturer_name
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.measurement_flow import observer_items
from DisplayCAL.ui.tooltip_window import TooltipWindow, info_text_html
from DisplayCAL.util_str import safe_str
from DisplayCAL.worker import Worker, check_create_dir, get_options_from_ti3

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent

#: File suffix accepted for the TI3 controls / drag-and-drop.
TI3_SUFFIXES = (".ti3",)

#: The four device combinations the CCXX testchart (and therefore every
#: correction TI3) is expected to contain, mapped to their display name.
_DEVICE_COMBINATIONS = {
    (100, 0, 0): "red",
    (0, 100, 0): "green",
    (0, 0, 100): "blue",
    (100, 100, 100): "white",
}


class _Ti3Browse(QWidget):
    """An editable path combo box plus a browse button, restricted to ``.ti3``.

    Args:
        dialog_title (str): Title for the file-open dialog.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted when the path changes (browse, history pick or typed entry).
    changed = Signal()

    def __init__(self, dialog_title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._committed = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.NoInsert)
        self._combo.activated.connect(self._on_activated)
        self._combo.lineEdit().editingFinished.connect(self._on_edit_finished)
        layout.addWidget(self._combo, 1)
        self._btn = QPushButton("…")
        self._btn.setFixedWidth(32)
        self._btn.clicked.connect(self._on_browse)
        layout.addWidget(self._btn)

    def path(self) -> str:
        """Return the current path (may be empty)."""
        return self._combo.currentText()

    def set_path(self, path: str | None) -> None:
        """Set the current path without emitting :attr:`changed`."""
        path = path or ""
        if path and self._combo.findText(path) == -1:
            self._combo.addItem(path)
        self._committed = path
        self._combo.setEditText(path)

    def _on_activated(self, _index: int) -> None:
        self._committed = self._combo.currentText()
        self.changed.emit()

    def _on_edit_finished(self) -> None:
        if self._combo.currentText() != self._committed:
            self._committed = self._combo.currentText()
            self.changed.emit()

    def _on_browse(self) -> None:
        default_dir = os.path.dirname(self.path()) if self.path() else ""
        wildcard = f"{lang.getstr('filetype.ti3')} (*.ti3)"
        path, _ = file_dialog.get_open_file_name(
            self, self._dialog_title, default_dir, wildcard
        )
        if path:
            self.set_path(path)
            self.changed.emit()


class _CreateThread(QThread):
    """Run the ``spec2cie`` / ``ccxxmake`` pipeline off the GUI thread.

    Args:
        window (CreateCorrectionWindow): The owning window (provides
            ``_build_correction``).
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with a result dict on success, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, window: CreateCorrectionWindow, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window

    def run(self) -> None:
        try:
            result = self._window._build_correction()
        except Exception as exception:  # noqa: BLE001  (reported on GUI thread)
            result = exception
        self.done.emit(result)


class _PreviewDialog(QDialog):
    """Reference-vs-corrected preview grid shown before saving a CCMX.

    Args:
        rows (list[dict]): Per-patch preview rows (see
            :meth:`CreateCorrectionWindow._compute_preview`).
        parent (QWidget | None): Optional Qt parent.
    """

    def __init__(self, rows: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang.getstr("colorimeter_correction.create"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(lang.getstr("colorimeter_correction.create.success")))

        table = QTableWidget(len(rows), 7, self)
        table.setHorizontalHeaderLabels(
            [
                lang.getstr("reference") + " x",
                "y",
                "Y",
                lang.getstr("corrected") + " x",
                "y",
                "Y",
                "ΔE*00",
            ]
        )
        table.setVerticalHeaderLabels([str(row["sample_id"]) for row in rows])
        for r, row in enumerate(rows):
            for c, value in enumerate((*row["ref_xyY"], *row["corrected_xyY"])):
                table.setItem(r, c, QTableWidgetItem(f"{value:.4f}"))
            de_item = QTableWidgetItem(f"{row['delta_e00']:.4f}")
            table.setItem(r, 6, de_item)
        # Colour swatches: colour the reference/corrected xyY columns using the
        # sRGB approximation of the measured patch.
        for r, row in enumerate(rows):
            for col_start, rgb in ((0, row["ref_rgb"]), (3, row["corrected_rgb"])):
                colour = QColor(*rgb)
                for c in range(col_start, col_start + 3):
                    item = table.item(r, c)
                    if item is not None:
                        item.setBackground(colour)
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Discard)
        buttons.button(QDialogButtonBox.Save).setText(lang.getstr("save"))
        buttons.button(QDialogButtonBox.Discard).setText(
            lang.getstr("testchart.discard")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(640, 320)


class CreateCorrectionWindow(BaseWindow):
    """Window for creating a CCMX or CCSS colorimeter-correction file."""

    #: Emitted when the user wants to measure the reference instrument
    #: (needs the live measurement flow the Qt main window owns).
    measure_reference_requested = Signal()
    #: Emitted when the user wants to measure the colorimeter.
    measure_colorimeter_requested = Signal()
    #: Emitted with ``(path, is_ccmx)`` once a correction file has been
    #: written to disk, so the main window can refresh its instrument /
    #: correction-matrix selection the way wx's
    #: ``colorimeter_correction_check_overwrite`` does after a save.
    correction_created = Signal(str, bool)

    def __init__(self) -> None:
        super().__init__(
            name="colorimetercorrectioncreate",
            title=lang.getstr("colorimeter_correction.create"),
            icon_name=f"{APPNAME}-CCXX-maker".lower(),
        )
        self.worker = Worker()
        self.worker.set_argyll_version("ccxxmake")
        self.worker.enumerate_displays_and_ports(silent=True)
        self._mode_keys: dict[str, list[str]] = {}
        self._technology_keys: list[str] = []
        self._thread: _CreateThread | None = None
        self._progress: QProgressDialog | None = None

        self._build_ui()
        self._populate_instruments()
        self.update_controls()
        # update_controls (via _maybe_reveal_details) may have left the
        # details box hidden, unlike _build_ui's initial resize() which
        # assumed it visible; snap to whatever's actually showing.
        self._sync_window_size()
        self.restore_position()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        info_row = QHBoxLayout()
        info_icon = QLabel()
        info_pixmap = get_theme_pixmap(32, "dialog-information")
        if not info_pixmap.isNull():
            info_icon.setPixmap(info_pixmap)
        info_icon.setAlignment(Qt.AlignTop)
        info_icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        info_row.addWidget(info_icon)
        info_label = QLabel(lang.getstr("colorimeter_correction.create.info"))
        info_label.setWordWrap(True)
        info_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        info_row.addWidget(info_label, 1)
        layout.addLayout(info_row)

        warning_row = QHBoxLayout()
        warning_icon = QLabel()
        warning_pixmap = get_theme_pixmap(16, "dialog-warning")
        if not warning_pixmap.isNull():
            warning_icon.setPixmap(warning_pixmap)
        warning_icon.setAlignment(Qt.AlignTop)
        warning_icon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        warning_row.addWidget(warning_icon)
        warning_label = QLabel(lang.getstr("colorimeter_correction.create.warning"))
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #F07F00;")
        warning_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        warning_row.addWidget(warning_label, 1)
        layout.addLayout(warning_row)

        layout.addWidget(self._build_type_box())
        layout.addWidget(self._build_instrument_box("reference"))
        self.colorimeter_box = self._build_instrument_box("colorimeter")
        layout.addWidget(self.colorimeter_box)
        self.details_box = self._build_details_box()
        # wx only shows these fields in a second confirmation dialog once
        # the user has picked/measured real TI3 files; this single-window
        # port keeps them inline but hidden until there's something real to
        # review (see _maybe_reveal_details).
        self.details_box.setVisible(False)
        layout.addWidget(self.details_box)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.cancel_btn = QPushButton(lang.getstr("cancel"))
        self.cancel_btn.clicked.connect(self.close)
        button_row.addWidget(self.cancel_btn)
        self.create_btn = QPushButton(lang.getstr("colorimeter_correction.create"))
        self.create_btn.setEnabled(False)
        self.create_btn.setDefault(True)
        self.create_btn.clicked.connect(self.create_handler)
        button_row.addWidget(self.create_btn)
        layout.addLayout(button_row)

        self.setCentralWidget(central)
        layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        self.resize(650, 760)
        # Floor the width: the instrument rows (combo + mode combo + Measure
        # button) technically survive narrower via Qt's own text elision, but
        # wx never let this dialog get that cramped.
        min_size = central.minimumSizeHint()
        min_size.setWidth(max(min_size.width(), 620))
        self.setMinimumSize(min_size)

    def _build_type_box(self) -> QGroupBox:
        box = QGroupBox(lang.getstr("type"))
        v = QVBoxLayout(box)
        row = QHBoxLayout()
        self.correction_type_matrix = QRadioButton(lang.getstr("matrix"))
        self.correction_type_spectral = QRadioButton(
            lang.getstr("spectral") + " (i1 DisplayPro, ColorMunki Display, Spyder4/5)"
        )
        group = QButtonGroup(self)
        group.addButton(self.correction_type_matrix)
        group.addButton(self.correction_type_spectral)
        self.correction_type_matrix.toggled.connect(self.correction_type_handler)
        row.addWidget(self.correction_type_matrix)
        self.four_color_matrix = QCheckBox(
            lang.getstr("ccmx.use_four_color_matrix_method")
        )
        self.four_color_matrix.toggled.connect(self.four_color_matrix_handler)
        row.addWidget(self.four_color_matrix)
        v.addLayout(row)
        v.addWidget(self.correction_type_spectral)
        # Without a stretch elsewhere to absorb extra vertical space, a plain
        # QGroupBox is happy to grow past its content; pin it to its natural
        # height instead of stretching when the window's taller than needed.
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return box

    def _build_instrument_box(self, which: str) -> QGroupBox:
        title = (
            f"{lang.getstr('instrument')} ({lang.getstr('reference')})"
            if which == "reference"
            else lang.getstr("instrument")
        )
        box = QGroupBox(title)
        v = QVBoxLayout(box)

        row = QHBoxLayout()
        instrument_ctrl = QComboBox()
        row.addWidget(instrument_ctrl, 1)
        row.addWidget(QLabel(lang.getstr("measurement_mode")))
        mode_ctrl = QComboBox()
        row.addWidget(mode_ctrl)
        measure_btn = QPushButton(lang.getstr("measure"))
        row.addWidget(measure_btn)
        v.addLayout(row)

        observer_row = QHBoxLayout()
        observer_label = QLabel(lang.getstr("observer"))
        observer_row.addWidget(observer_label)
        observer_ctrl = QComboBox()
        observer_row.addWidget(observer_ctrl)
        observer_row.addStretch(1)
        v.addLayout(observer_row)

        ti3_ctrl = _Ti3Browse(lang.getstr(f"measurement_file.choose.{which}"))
        v.addWidget(ti3_ctrl)

        setattr(self, f"{which}_instrument", instrument_ctrl)
        setattr(self, f"{which}_measurement_mode", mode_ctrl)
        setattr(self, f"{which}_observer", observer_ctrl)
        setattr(self, f"{which}_observer_label", observer_label)
        setattr(self, f"{which}_ti3", ti3_ctrl)
        setattr(self, f"measure_{which}_btn", measure_btn)

        instrument_ctrl.activated.connect(
            lambda _i, w=which: self._instrument_handler(w)
        )
        ti3_ctrl.changed.connect(lambda w=which: self._ti3_changed(w))
        droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(
                TI3_SUFFIXES, lambda p, w=which: self._ti3_dropped(w, p)
            ),
            parent=self,
        )
        droptarget.install_on(ti3_ctrl)
        if which == "reference":
            measure_btn.clicked.connect(self.measure_reference_requested.emit)
        else:
            measure_btn.clicked.connect(self.measure_colorimeter_requested.emit)

        # See _build_type_box: without a stretch to absorb leftover vertical
        # space, plain QGroupBoxes grow to fill it instead of staying put.
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return box

    def _build_details_box(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        # A wrapped label rather than the box's own title: a QGroupBox title
        # doesn't wrap, and this sentence is long enough to force the window
        # to an unreasonably wide natural size if used as one.
        details_label = QLabel(lang.getstr("colorimeter_correction.create.details"))
        details_label.setWordWrap(True)
        outer.addWidget(details_label)
        box = QGroupBox()
        outer.addWidget(box)
        grid = QGridLayout(box)
        self.description_ctrl = QLineEdit()
        grid.addWidget(QLabel(lang.getstr("description")), 0, 0)
        grid.addWidget(self.description_ctrl, 0, 1)
        self.display_ctrl = QLineEdit()
        grid.addWidget(QLabel(lang.getstr("display")), 1, 0)
        grid.addWidget(self.display_ctrl, 1, 1)
        self.manufacturer_ctrl = QComboBox()
        self.manufacturer_ctrl.setEditable(True)
        grid.addWidget(QLabel(lang.getstr("display.manufacturer")), 2, 0)
        grid.addWidget(self.manufacturer_ctrl, 2, 1)
        self.technology_ctrl = QComboBox()
        grid.addWidget(QLabel(lang.getstr("display.tech")), 3, 0)
        grid.addWidget(self.technology_ctrl, 3, 1)
        tech_info_btn = QToolButton()
        tech_info_btn.setAutoRaise(True)
        tech_info_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tech_info_pixmap = get_theme_pixmap(16, "info")
        if not tech_info_pixmap.isNull():
            tech_info_btn.setIcon(tech_info_pixmap)
        tech_info_btn.setText(lang.getstr("info.display_tech.show"))
        tech_info_btn.clicked.connect(self._display_tech_info_show_btn_handler)
        grid.addWidget(tech_info_btn, 4, 1)
        # See _build_type_box: without a stretch to absorb leftover vertical
        # space, plain QGroupBoxes grow to fill it instead of staying put.
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return container

    # -- instrument / mode / observer population -----------------------------

    def _populate_instruments(self) -> None:
        reference_instruments = []
        colorimeters = []
        for instrument in self.worker.instruments:
            if argyll_instruments.instruments.get(instrument, {}).get("spectral"):
                reference_instruments.append(instrument)
            else:
                colorimeters.append(instrument)
        self.reference_instrument.clear()
        self.reference_instrument.addItems(reference_instruments)
        self.colorimeter_instrument.clear()
        self.colorimeter_instrument.addItems(colorimeters)
        self.measure_reference_btn.setEnabled(
            bool(self.worker.displays and reference_instruments)
        )
        self.measure_colorimeter_btn.setEnabled(
            bool(self.worker.displays and colorimeters)
        )

        current_reference = getcfg("colorimeter_correction.instrument.reference")
        if current_reference in reference_instruments:
            self.reference_instrument.setCurrentText(current_reference)
        current_colorimeter = getcfg("colorimeter_correction.instrument")
        if current_colorimeter in colorimeters:
            self.colorimeter_instrument.setCurrentText(current_colorimeter)

        if reference_instruments:
            self._instrument_handler("reference")
        if colorimeters:
            self._instrument_handler("colorimeter")
        # Matches wx locking the combo when there's nothing to switch between.
        self.reference_instrument.setEnabled(len(reference_instruments) >= 2)
        self.colorimeter_instrument.setEnabled(len(colorimeters) >= 2)

    def _instrument_handler(self, which: str) -> None:
        combo = getattr(self, f"{which}_instrument")
        name = combo.currentText()
        mode_ctrl = getattr(self, f"{which}_measurement_mode")
        cfgname = (
            "colorimeter_correction.measurement_mode.reference"
            if which == "reference"
            else "colorimeter_correction.measurement_mode"
        )
        keys: list[str] = []
        labels: list[str] = []
        if name:
            if which == "reference":
                # Matches wx's ``get_measurement_modes(..., "spect", ...)``:
                # spectrometers have no Argyll ``-y`` modes of their own (see
                # ``Worker.get_instrument_measurement_modes``), so the
                # reference role uses the same generic
                # Refresh/LCD(+adaptive/high-res/projector) mode set the main
                # window's own measurement-mode combo does.
                features = self.worker.get_instrument_features(name)
                instrument_type = "spect" if features.get("spectral") else "color"
                try:
                    result = ccxx_helpers.compute_measurement_modes(
                        self.worker, name, instrument_type, cfgname
                    )
                except Exception:  # noqa: BLE001 - keep the wizard usable
                    result = None
                if result is not None:
                    labels = result.measurement_modes.get(instrument_type, [])
                    ab = result.measurement_modes_ab.get(instrument_type, {})
                    keys = [ab[i] for i in range(len(labels))]
            else:
                # Matches wx's ``get_ccxx_measurement_modes``: a pure
                # per-instrument-name lookup, not the live Argyll ``-y`` mode
                # list (which needs a connected colorimeter instrument to
                # answer at all).
                modes = ccxx_helpers.get_ccxx_measurement_modes(name)
                keys = list(modes.keys())
                labels = list(modes.values())
        self._mode_keys[which] = keys
        mode_ctrl.clear()
        mode_ctrl.addItems(labels)
        mode_ctrl.setEnabled(bool(labels))

        current_mode = getcfg(cfgname)
        if current_mode in keys:
            mode_ctrl.setCurrentIndex(keys.index(current_mode))

        observer_ctrl = getattr(self, f"{which}_observer")
        can_observe = bool(name) and self.worker.instrument_can_use_nondefault_observer(
            name
        )
        observer_ctrl.setEnabled(can_observe)
        if can_observe and observer_ctrl.count() == 0:
            items = observer_items()
            observer_keys = getattr(self, f"_observer_keys_{which}", None)
            if observer_keys is None:
                observer_keys = {}
            observer_ctrl.clear()
            for i, (key, label) in enumerate(items.items()):
                observer_ctrl.addItem(label)
                observer_keys[i] = key
            setattr(self, f"_observer_keys_{which}", observer_keys)
            observer_cfgname = (
                "colorimeter_correction.observer.reference"
                if which == "reference"
                else "colorimeter_correction.observer"
            )
            current_observer = getcfg(observer_cfgname)
            for i, key in observer_keys.items():
                if key == current_observer:
                    observer_ctrl.setCurrentIndex(i)
                    break

        self._update_observer_visibility(which, can_observe)
        self._update_ok_state()

    def _update_observer_visibility(self, which: str, can_observe: bool) -> None:
        """Show the observer row, mirroring wx's stickier per-role rules.

        The reference observer is only relevant when building a CCMX (it
        feeds ``spec2cie``), so it's gated on the matrix radio button too.
        The colorimeter observer is left hidden unless it was already set to
        something other than the default, matching wx's
        ``show_observer_ctrl`` (avoids surfacing a rarely-needed control for
        the common case).
        """
        advanced = bool(getcfg("show_advanced_options"))
        if which == "reference":
            show_observer = (
                advanced and can_observe and self.correction_type_matrix.isChecked()
            )
        else:
            current_observer = getcfg("colorimeter_correction.observer")
            show_observer = (
                advanced
                and can_observe
                and current_observer != DEFAULTS["colorimeter_correction.observer"]
            )
        observer_ctrl = getattr(self, f"{which}_observer")
        observer_label = getattr(self, f"{which}_observer_label")
        observer_ctrl.setVisible(show_observer)
        observer_label.setVisible(show_observer)

    def selection_for_measurement(
        self, which: str
    ) -> tuple[str, str | None, str | None] | None:
        """Return ``(instrument, mode_key, observer_key)`` for a Measure click.

        Read by :meth:`DisplayCAL.ui.main_window.MainWindow
        ._ccxx_measure_requested`, the Qt port of wx's
        ``id_measure_reference``/``id_measure_colorimeter`` branch, to know
        which live instrument/mode/observer to switch the main window to
        before running the measurement. Returns ``None`` if no instrument is
        selected for ``which``.
        """
        instrument_ctrl = getattr(self, f"{which}_instrument")
        instrument = instrument_ctrl.currentText()
        if not instrument:
            return None
        mode_ctrl = getattr(self, f"{which}_measurement_mode")
        keys = self._mode_keys.get(which, [])
        index = mode_ctrl.currentIndex()
        mode_key = keys[index] if 0 <= index < len(keys) else None
        observer_key = None
        observer_ctrl = getattr(self, f"{which}_observer")
        if observer_ctrl.isVisible():
            observer_keys = getattr(self, f"_observer_keys_{which}", {})
            observer_key = observer_keys.get(observer_ctrl.currentIndex())
        return instrument, mode_key, observer_key

    # -- TI3 handling ---------------------------------------------------------

    def _ti3_changed(self, which: str) -> None:
        cfgname = (
            "last_reference_ti3_path"
            if which == "reference"
            else "last_colorimeter_ti3_path"
        )
        setcfg(cfgname, getattr(self, f"{which}_ti3").path())
        self._update_ok_state()
        self._maybe_reveal_details()

    def _ti3_dropped(self, which: str, path: str) -> None:
        getattr(self, f"{which}_ti3").set_path(path)
        self._ti3_changed(which)

    def _update_ok_state(self) -> None:
        reference_path = self.reference_ti3.path()
        colorimeter_path = self.colorimeter_ti3.path()
        ok = bool(reference_path and os.path.isfile(reference_path)) and (
            self.correction_type_spectral.isChecked()
            or bool(colorimeter_path and os.path.isfile(colorimeter_path))
        )
        self.create_btn.setEnabled(ok)

    def _maybe_reveal_details(self) -> None:
        """Populate and reveal the details box once there's a real TI3 to describe.

        wx only shows these fields ("please check the fields below...") in a
        second confirmation dialog once the user has selected/measured
        actual TI3 file(s), not from the moment the window opens. This
        single-window port keeps the same fields hidden until the currently
        selected TI3(s) load and validate cleanly, then reveals and
        populates them from that data (re-populated on every subsequent TI3
        change, and again right before the actual Argyll run in
        :meth:`create_handler` for freshness).
        """
        try:
            self._reference_cgats, self._colorimeter_cgats = self._load_ti3_files()
        except Exception:  # noqa: BLE001 - just means "nothing to show yet"
            was_visible = self.details_box.isVisible()
            self.details_box.setVisible(False)
            if was_visible:
                self._sync_window_size()
            return
        self._populate_details()
        was_visible = self.details_box.isVisible()
        self.details_box.setVisible(True)
        if not was_visible:
            self._sync_window_size()

    def _sync_window_size(self) -> None:
        """Shrink/grow the window to fit the currently visible content.

        Qt's layout system happily leaves behind blank space where a widget
        used to be when it's hidden (unlike wx, which rebuilds each dialog
        step from scratch already sized to fit); call this after toggling a
        section's visibility so the window follows suit, matching
        ``dlg.sizer0.SetSizeHints(dlg)`` + ``Layout()`` calls sprinkled
        through the wx handler's own show/hide branches. Never shrinks below
        :meth:`_build_ui`'s floor (``setMinimumSize``).
        """
        self.adjustSize()

    def correction_type_handler(self, _checked: bool = False) -> None:
        """Show/hide the colorimeter box and four-color-matrix checkbox."""
        matrix = self.correction_type_matrix.isChecked()
        setcfg("colorimeter_correction.type", "matrix" if matrix else "spectral")
        self.four_color_matrix.setEnabled(matrix)
        if not matrix:
            self.four_color_matrix.setChecked(False)
        colorimeter_was_visible = self.colorimeter_box.isVisible()
        self.colorimeter_box.setVisible(matrix)
        name = self.reference_instrument.currentText()
        can_observe = bool(name) and self.worker.instrument_can_use_nondefault_observer(
            name
        )
        self._update_observer_visibility("reference", can_observe)
        self._update_ok_state()
        self._maybe_reveal_details()
        if colorimeter_was_visible != matrix:
            self._sync_window_size()

    def four_color_matrix_handler(self, checked: bool = False) -> None:
        """Persist the four-color-matrix checkbox (``Worker.create_ccxx`` reads it)."""
        setcfg("ccmx.use_four_color_matrix_method", int(checked))

    def update_controls(self) -> None:
        """Load control values from config."""
        self.correction_type_matrix.setChecked(
            getcfg("colorimeter_correction.type") != "spectral"
        )
        self.correction_type_spectral.setChecked(
            getcfg("colorimeter_correction.type") == "spectral"
        )
        self.four_color_matrix.setChecked(
            bool(getcfg("ccmx.use_four_color_matrix_method"))
        )
        # Matches wx calling correction_type_handler(None) once right after
        # binding it: without this, the colorimeter box's initial visibility
        # never reflects a config-loaded "spectral" selection, since
        # setChecked() only emits toggled() on an actual state change and
        # correction_type_matrix starts out unchecked by default anyway.
        self.correction_type_handler()
        # Matches wx's get_verified_path(): only pre-fill a remembered path if
        # it still exists on disk (the config default is an "~/Unnamed"
        # placeholder used purely as a browse-dialog starting point, never
        # meant to appear as a real selection).
        reference_path = getcfg("last_reference_ti3_path")
        self.reference_ti3.set_path(
            reference_path if os.path.isfile(reference_path) else ""
        )
        colorimeter_path = getcfg("last_colorimeter_ti3_path")
        self.colorimeter_ti3.set_path(
            colorimeter_path if os.path.isfile(colorimeter_path) else ""
        )
        self._update_ok_state()
        self._maybe_reveal_details()

    # -- create pipeline ------------------------------------------------------

    def create_handler(self, _checked: bool = False) -> None:
        """Validate the TI3 selection and start the create pipeline."""
        self.create_btn.setEnabled(False)
        try:
            self._reference_cgats, self._colorimeter_cgats = self._load_ti3_files()
        except Exception as exception:  # noqa: BLE001
            self._error(str(exception))
            self.create_btn.setEnabled(True)
            return
        self._populate_details()
        self._progress = QProgressDialog(
            lang.getstr("colorimeter_correction.create"), "", 0, 0, self
        )
        self._progress.setCancelButton(None)
        self._progress.setWindowModality(Qt.WindowModal)
        self._progress.show()
        self._thread = _CreateThread(self)
        self._thread.done.connect(self._on_create_done)
        self._thread.start()

    def _load_ti3_files(self) -> tuple[CGATS, CGATS | None]:
        """Load and validate the reference (and optional colorimeter) TI3."""
        reference_path = self.reference_ti3.path()
        reference = CGATS(reference_path)
        if not reference.queryv1("DATA"):
            raise CGATSError(
                lang.getstr("error.measurement.file_invalid", reference_path)
            )
        reference.filename = reference_path

        colorimeter = None
        if self.correction_type_matrix.isChecked():
            colorimeter_path = self.colorimeter_ti3.path()
            colorimeter = CGATS(colorimeter_path)
            if not colorimeter.queryv1("DATA"):
                raise CGATSError(
                    lang.getstr("error.measurement.file_invalid", colorimeter_path)
                )
            colorimeter.filename = colorimeter_path
            self._trim_to_ccxx_patches(reference, colorimeter)
            # ccxxmake needs to know the calibration base display mode
            # (refresh/non-refresh) the colorimeter measurements were taken in.
            self.worker.check_add_display_type_base_id(
                colorimeter, "colorimeter_correction.measurement_mode"
            )
        for cgats in (reference, colorimeter):
            if cgats is not None and not cgats.queryv1("DISPLAY_TYPE_REFRESH"):
                cgats[0].add_keyword(
                    "DISPLAY_TYPE_REFRESH",
                    {"c": b"YES", "l": b"NO"}.get(
                        getcfg("colorimeter_correction.measurement_mode"), b"NO"
                    ),
                )
        return reference, colorimeter

    def _trim_to_ccxx_patches(self, reference: CGATS, colorimeter: CGATS) -> None:
        """Keep only the white/red/green/blue patches, matched between files."""
        reference_new = CGATS(b"BEGIN_DATA\nEND_DATA")
        reference_new.DATA_FORMAT = reference.queryv1("DATA_FORMAT")
        colorimeter_new = CGATS(b"BEGIN_DATA\nEND_DATA")
        colorimeter_new.DATA_FORMAT = colorimeter.queryv1("DATA_FORMAT")
        data_reference = reference.queryv1("DATA")
        data_colorimeter = colorimeter.queryv1("DATA")
        for rgb, name in _DEVICE_COMBINATIONS.items():
            patch = {"RGB_R": rgb[0], "RGB_G": rgb[1], "RGB_B": rgb[2]}
            item = data_reference.queryi1(patch)
            if not item:
                raise CGATSError(
                    lang.getstr(
                        "error.testchart.missing_fields",
                        (os.path.basename(reference.filename), lang.getstr(name)),
                    )
                )
            reference_new.DATA.add_data(item)
            item = data_colorimeter.queryi1(patch)
            if not item:
                raise CGATSError(
                    lang.getstr(
                        "error.testchart.missing_fields",
                        (os.path.basename(colorimeter.filename), lang.getstr(name)),
                    )
                )
            colorimeter_new.DATA.add_data(item)
        reference.queryi1("DATA").DATA = reference_new.DATA
        colorimeter.queryi1("DATA").DATA = colorimeter_new.DATA

    def _populate_details(self) -> None:
        reference = self._reference_cgats
        display, manufacturer = self._display_and_manufacturer_from_ti3(reference)
        manufacturer_display = self._manufacturer_display(manufacturer, display)

        instrument = reference.queryv1("TARGET_INSTRUMENT")
        if instrument:
            instrument = get_canonical_instrument_name(instrument)
        if isinstance(instrument, bytes):
            instrument = instrument.decode("utf-8")
        description = manufacturer_display or self.worker.get_display_name(True, True)
        if self._colorimeter_cgats is not None:
            instrument_label = instrument or self.worker.get_instrument_name()
            description = f"{instrument_label} & {description}"
        self.description_ctrl.setText(description)
        self.display_ctrl.setText(
            display or self.worker.get_display_name(False, True, False)
        )

        if not PNP_ID_CACHE:
            get_manufacturer_name("???")
        self.manufacturer_ctrl.clear()
        self.manufacturer_ctrl.addItems(sorted(PNP_ID_CACHE.values()))
        if manufacturer:
            self.manufacturer_ctrl.setCurrentText(manufacturer)

        self._populate_technology(reference)

    def _display_and_manufacturer_from_ti3(
        self, reference: CGATS
    ) -> tuple[str | None, str | None]:
        """Extract the ``-M``/``-A`` colprof options recorded in the TI3."""
        _, options_colprof = get_options_from_ti3(reference)
        display = None
        manufacturer = None
        for option in options_colprof:
            if option.startswith("M"):
                display = option[1:].strip(' "')
            elif option.startswith("A"):
                manufacturer = option[1:].strip(' "')
        return display, manufacturer

    def _manufacturer_display(
        self, manufacturer: str | None, display: str | None
    ) -> str | None:
        """Combine manufacturer + display, quirked, for the default description."""
        manufacturer_display = None
        if manufacturer and display:
            quirk = colord.quirk_manufacturer(manufacturer)
            manufacturer_display = (
                display if quirk.lower() in display.lower() else f"{quirk} {display}"
            )
        elif display:
            manufacturer_display = display
        if isinstance(manufacturer_display, bytes):
            manufacturer_display = manufacturer_display.decode("utf-8")
        return manufacturer_display

    def _populate_technology(self, reference: CGATS) -> None:
        technology_strings = self.worker.get_technology_strings()
        refresh = reference.queryv1("DISPLAY_TYPE_REFRESH")
        if isinstance(refresh, bytes):
            refresh = refresh.decode("utf-8")
        tech = "Unknown" if refresh == "YES" else "LCD"
        self._technology_keys = list(technology_strings.values())
        self.technology_ctrl.clear()
        self.technology_ctrl.addItems(
            [
                lang.getstr(f"display.tech.{value}", default=value)
                for value in self._technology_keys
            ]
        )
        if tech in self._technology_keys:
            self.technology_ctrl.setCurrentIndex(self._technology_keys.index(tech))

    def _display_tech_info_show_btn_handler(self) -> None:
        """Show (or raise) the display-technology info popup.

        Matches wx's ``display_tech_info_show_handler``, reused here from
        the same button placed next to the Technology combo; shares its
        popup content/markup translation with
        :meth:`DisplayCAL.ui.main_window.MainWindow
        ._display_tech_info_show_btn_handler` via
        :func:`DisplayCAL.ui.tooltip_window.info_text_html`.
        """
        if getattr(self, "_display_tech_info_window", None) is None:
            self._display_tech_info_window = TooltipWindow(
                self,
                lang.getstr("display.tech"),
                info_text_html("info.display_tech"),
                bitmap=get_theme_pixmap(32, "dialog-information"),
                links=[
                    (
                        lang.getstr(
                            "info.display_tech.linklabel.displayspecifications.com"
                        ),
                        "https://www.displayspecifications.com/",
                    ),
                    (
                        lang.getstr("info.display_tech.linklabel.everymac.com"),
                        "https://everymac.com/",
                    ),
                ],
            )
        self._display_tech_info_window.show_and_raise()

    def _build_correction(self) -> dict:
        """Run the Argyll pipeline. Executed on :class:`_CreateThread`."""
        reference = self._reference_cgats
        colorimeter = self._colorimeter_cgats
        description = self.description_ctrl.text().strip()
        display = self.display_ctrl.text().strip()
        manufacturer = self.manufacturer_ctrl.currentText().strip() or None
        tech = (
            self._technology_keys[self.technology_ctrl.currentIndex()]
            if self._technology_keys
            else "LCD"
        )

        args = ["-E", safe_str(description, "UTF-8")]
        if display:
            args.extend(["-I", safe_str(display, "UTF-8")])
        technology_strings = self.worker.get_technology_strings()
        ccxxmake_version = get_argyll_version("ccxxmake")
        if ccxxmake_version >= [1, 7]:
            technology_ids = {v: k for k, v in technology_strings.items()}
            args.extend(["-t", technology_ids.get(tech, "u")])
        else:
            args.extend(["-T", safe_str(tech, "UTF-8")])

        cwd = self.worker.create_tempdir()
        ti3_names = ["reference.ti3"]
        reference.write(os.path.join(cwd, "reference.ti3"))
        observer = None
        reference_observer = None
        if colorimeter is not None:
            colorimeter.write(os.path.join(cwd, "colorimeter.ti3"))
            ti3_names.append("colorimeter.ti3")
            name, ext = "correction", ".ccmx"
            observer = colorimeter.queryv1("OBSERVER")
            reference_observer = getcfg("colorimeter_correction.observer.reference")
        else:
            args.append("-S")
            name, ext = "calibration", ".ccss"
        args.extend(["-f", ",".join(ti3_names), name + ext])
        if not getcfg("ccmx.use_four_color_matrix_method"):
            args.insert(0, "-v")

        result = self.worker.create_ccxx(args, cwd)
        if isinstance(result, Exception):
            return result
        source = os.path.join(self.worker.tempdir, name + ext)
        if not (result and os.path.isfile(source)):
            return CGATSError(
                lang.getstr("colorimeter_correction.create.failure")
                + "\n"
                + "".join(self.worker.errors)
            )

        preview_rows = []
        fit_de94 = fit_de00 = None
        if colorimeter is not None:
            ccmx = CGATS(source)
            if getcfg("ccmx.use_four_color_matrix_method"):
                self._apply_four_color_matrix(ccmx, reference, colorimeter)
                ccmx.write()
            preview_rows, fit_de94, fit_de00 = self._compute_preview(
                ccmx, reference, colorimeter
            )

        with open(source, "rb") as cgatsfile:
            cgats_bytes = cgatsfile.read()
        cgats_bytes = ccxx_helpers.inject_ccxx_metadata(
            cgats_bytes,
            reference=reference[0].get("TARGET_INSTRUMENT"),
            technology=tech,
            manufacturer_id=self._manufacturer_id(manufacturer),
            manufacturer=manufacturer,
            observer=observer,
            reference_observer=reference_observer,
        )
        metadata = []
        if fit_de94 is not None:
            metadata.extend(
                [
                    f'FIT_MAX_DE94 "{max(fit_de94):.6f}"',
                    f'FIT_AVG_DE94 "{sum(fit_de94) / len(fit_de94):.6f}"',
                    f'FIT_MAX_DE00 "{max(fit_de00):.6f}"',
                    f'FIT_AVG_DE00 "{sum(fit_de00) / len(fit_de00):.6f}"',
                ]
            )
        metadata.append(
            'FIT_METHOD "xy"'
            if colorimeter is not None and getcfg("ccmx.use_four_color_matrix_method")
            else 'FIT_METHOD "ΔE*94"'
        )
        cgats_bytes = re.sub(
            rb'(\nREFERENCE\s+"[^"]*"\n)',
            ("\\1{}\n".format("\n".join(metadata))).encode("utf-8"),
            cgats_bytes,
        )

        result_check = check_create_dir(get_argyll_data_dir())
        if isinstance(result_check, Exception):
            return result_check

        return {
            "cgats": cgats_bytes,
            "preview_rows": preview_rows,
            "is_ccmx": colorimeter is not None,
        }

    def _manufacturer_id(self, manufacturer: str | None) -> str | None:
        if not manufacturer:
            return None
        manufacturers = {name: id_ for id_, name in PNP_ID_CACHE.items()}
        return manufacturers.get(manufacturer)

    def _apply_four_color_matrix(
        self, ccmx: CGATS, reference: CGATS, colorimeter: CGATS
    ) -> None:
        white_abs = [self._white_abs(meas) for meas in (reference, colorimeter)]
        xyz = []
        for j, meas in enumerate((reference, colorimeter)):
            for r, g, b in ((100, 0, 0), (0, 100, 0), (0, 0, 100), (100, 100, 100)):
                patch = {"RGB_R": r, "RGB_G": g, "RGB_B": b}
                item = meas.queryi1("DATA").queryi1(patch)
                x, y, z = item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"]
                x, y, z = (v * white_abs[j][1] / 100.0 for v in (x, y, z))
                xyz.extend((x, y, z))
        matrix = colormath.four_color_matrix(*xyz)
        for i in range(3):
            for j, component in enumerate("XYZ"):
                ccmx[0].DATA[i][f"XYZ_{component}"] = matrix[i][j]

    def _white_abs(self, meas: CGATS) -> list[float]:
        luminance = meas.queryv1("LUMINANCE_XYZ_CDM2")
        white = luminance.decode("utf-8") if luminance is not None else None
        if white:
            return [float(v) for v in white.split()]
        white = meas.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
        return [white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]]

    def _compute_preview(
        self, ccmx: CGATS, reference: CGATS, colorimeter: CGATS
    ) -> tuple[list[dict], list[float], list[float]]:
        matrix = colormath.Matrix3x3()
        for sample in ccmx.queryv1("DATA").values():
            matrix.append([sample[f"XYZ_{c}"] for c in "XYZ"])
        white_abs = [self._white_abs(meas) for meas in (reference, colorimeter)]
        white_ref = [v / white_abs[0][1] for v in white_abs[0]]

        ref_data = reference.queryv1("DATA")
        tgt_data = colorimeter.queryv1("DATA")
        rows = []
        delta_e94 = []
        delta_e00 = []
        for i in ref_data:
            ref = ref_data[i]
            tgt = tgt_data[i]
            xyz_abs = []
            xyY = []  # noqa: N806
            rgb_swatches = []
            for j, sample in enumerate((ref, tgt)):
                values = [sample[f"XYZ_{c}"] * white_abs[j][1] / 100.0 for c in "XYZ"]
                if j == 1:
                    values = matrix * values
                xyz_abs.append(values)
                xyY.append(colormath.XYZ2xyY(*values))
                scale = max(white_abs[0][1], (matrix * white_abs[1])[1])
                scaled = (v / scale for v in values)
                x, y, z = colormath.adapt(*scaled, white_ref, "D65")
                rgb_swatches.append(
                    [round(v) for v in colormath.XYZ2RGB(x, y, z, scale=255)]
                )
            lab_ref = colormath.XYZ2Lab(*xyz_abs[0], white_abs[0])
            lab_tgt = colormath.XYZ2Lab(*xyz_abs[1], white_abs[0])
            delta_e94.append(colormath.delta(*lab_ref, *lab_tgt, "94")["E"])
            delta_e00.append(colormath.delta(*lab_ref, *lab_tgt, "00")["E"])
            rows.append(
                {
                    "sample_id": f"{ref.SAMPLE_ID:.0f}",
                    "ref_xyY": xyY[0],
                    "corrected_xyY": xyY[1],
                    "ref_rgb": rgb_swatches[0],
                    "corrected_rgb": rgb_swatches[1],
                    "delta_e00": delta_e00[-1],
                }
            )
        return rows, delta_e94, delta_e00

    def _on_create_done(self, result: object) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        self.create_btn.setEnabled(True)
        if isinstance(result, Exception):
            self._error(str(result))
            return
        cgats_bytes = result["cgats"]
        is_ccmx = result["is_ccmx"]
        if is_ccmx:
            dlg = _PreviewDialog(result["preview_rows"], self)
            if dlg.exec_() != QDialog.Accepted:
                return
        self._save(cgats_bytes, is_ccmx)

    def _save(self, cgats_bytes: bytes, is_ccmx: bool) -> None:
        path = ccxx_helpers.get_cgats_path(cgats_bytes)
        if os.path.isfile(path):
            reply = message_box.question(
                self,
                lang.getstr("colorimeter_correction.create"),
                lang.getstr("dialog.confirm_overwrite", os.path.basename(path)),
            )
            if reply != QMessageBox.Yes:
                return
        try:
            with open(path, "wb") as cgatsfile:
                cgatsfile.write(cgats_bytes.rstrip(b"\n") + b"\n")
        except OSError as exception:
            self._error(str(exception))
            return
        setcfg("colorimeter_correction_matrix_file", ":" + path)
        # wx's dialog is already gone by the time the Argyll run even
        # starts (it's a blocking modal that returns before processing);
        # this single-window port keeps it open through the run/preview, so
        # close it here once there's a finished file, matching wx's "the
        # wizard is done" end state instead of leaving a stale window up.
        self.correction_created.emit(path, is_ccmx)
        self.close()

    def _error(self, message: str) -> None:
        title = lang.getstr("colorimeter_correction.create")
        message_box.critical(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist config on close, matching the other ported windows."""
        super().closeEvent(event)
        from DisplayCAL import config

        config.writecfg()


def main() -> None:
    """Run the colorimeter-correction create window standalone."""
    from DisplayCAL.ui.application import Application

    app = Application([])
    window = CreateCorrectionWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
