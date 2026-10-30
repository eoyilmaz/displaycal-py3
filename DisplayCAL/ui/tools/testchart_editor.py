"""Testchart editor — Qt port (Stages 1-3).

Qt equivalent of :mod:`DisplayCAL.wx_testchart_editor` (the ``testchart-editor``
tool). It builds and edits Argyll TI1 test charts: a grid of RGB patches plus
the ``targen`` parameter controls that drive their generation (white / black /
single-channel / gray / multi-dimensional / full-spread patch counts, the
point-distribution algorithm and its adaption / angle / gamma / neutral-axis and
dark-region emphasis).

Generation runs Argyll ``targen`` via :meth:`DisplayCAL.worker.Worker.prepare_targen`
(entirely config-driven and binding-agnostic) on a :class:`QThread`, reading the
resulting ``temp.ti1`` back as a :class:`~DisplayCAL.cgats.CGATS` object. Loading
reads a ``.ti1`` / ``.ti3`` / ``.cgats`` / ``.txt`` (or an ICC's embedded chart)
and reconstructs the control values from the chart's keywords, on a background
thread. Charts save as ``.ti1`` (``bytes(cgats)``).

**Stage 2** adds the self-contained output paths: **CSV export** (0..100 /
0..255 / 0..1023 device-value scaling) and the **3D view / export** (VRML / X3D /
HTML via :meth:`DisplayCAL.cgats.CGATS.export_3d`, with the device / CIE
colorspace selection, black-point offset, D50 normalization and gzip
compression). Both run off a :class:`QThread` behind an indeterminate progress
dialog.

**Stage 3** adds the patch-*adding* paths, all gated on a **preconditioning
profile** (also new here, alongside its **CIE-sphere filter** controls that feed
``targen``): **saturation sweeps** towards the RGB/CMY primaries or a custom
target, and **reference-patch import** from TI3 / CGATS / CIE / GAM / Named-Color
ICC files and from **images** (whose pixels are converted through ``cctiff`` and
averaged into weighted Lab points). Dropping a **CSV** converts it to a temporary
TI1 and loads it. The lookups run off a :class:`QThread` behind a progress
dialog.

The 23-way **patch reordering** ("change patch order" combo + apply button) is
also ported, reusing :class:`DisplayCAL.cgats.CGATS`'s existing sort/checkerboard
methods.

Still deferred to later stages (and to the not-yet-ported main window for its
parent integration): the **image / DPX video-pattern export** (it depends on the
measurement-frame display geometry that lives in the measurement flow). The
per-parameter reconstruction of hand-authored charts that carry no ``targen``
keywords is also approximate for now.
"""

from __future__ import annotations

import csv
import math
import os
import sys
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtGui import QColor, QImage
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import argyll_rgb2xyz, colormath, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll import check_set_argyll_bin, get_argyll_util
from DisplayCAL.argyll_cgats import ti3_to_ti1, verify_cgats
from DisplayCAL.cgats import (
    CGATS,
    CGATSError,
    CGATSKeyError,
    sort_by_rec709_luma,
    sort_by_rgb,
    sort_by_rgb_sum,
    stable_sort_by_l,
)
from DisplayCAL.config import (
    DEFAULTS,
    VALID_VALUES,
    get_data_path,
    get_total_patches,
    get_verified_path,
    getcfg,
    setcfg,
)
from DisplayCAL.icc_profile import (
    ICCProfile,
    ICCProfileInvalidError,
    NamedColor2Type,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.util_dict import swap_dict_keys_values
from DisplayCAL.util_os import launch_file, waccess
from DisplayCAL.worker import (
    Error,
    Worker,
    check_file_isfile,
    get_current_profile_path,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QKeyEvent

#: File suffixes accepted for loading (drag-and-drop / open), replacing the chart.
LOAD_SUFFIXES = (".ti1", ".ti3", ".cgats", ".txt", ".icc", ".icm")

#: Image suffixes whose pixels are sampled into reference patches.
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff")

#: File suffixes whose patches are *added* to the chart (needs a precond profile).
ADD_TI3_SUFFIXES = (".cie", ".gam", *IMAGE_SUFFIXES)

#: (R, G, B) primaries/secondaries offered as saturation-sweep buttons.
SATURATION_SWEEP_RGB = {
    "R": (1, 0, 0),
    "G": (0, 1, 0),
    "B": (0, 0, 1),
    "C": (0, 1, 1),
    "M": (1, 0, 1),
    "Y": (1, 1, 0),
}

#: CSV export formats offered by the export dialog: (label, device-value scale).
CSV_EXPORT_FORMATS = (
    ("CSV (0.0..100.0)", 100),
    ("CSV (0..255)", 255),
    ("CSV (0..1023)", 1023),
)

#: Localization keys for the 23 "change patch order" modes, in combo-box order.
PATCH_ORDER_LSTRS = (
    "testchart.sort_RGB_gray_to_top",
    "testchart.sort_RGB_white_to_top",
    "testchart.sort_RGB_red_to_top",
    "testchart.sort_RGB_green_to_top",
    "testchart.sort_RGB_blue_to_top",
    "testchart.sort_RGB_cyan_to_top",
    "testchart.sort_RGB_magenta_to_top",
    "testchart.sort_RGB_yellow_to_top",
    "testchart.sort_by_HSI",
    "testchart.sort_by_HSL",
    "testchart.sort_by_HSV",
    "testchart.sort_by_L",
    "testchart.sort_by_rec709_luma",
    "testchart.sort_by_RGB",
    "testchart.sort_by_RGB_sum",
    "testchart.sort_by_BGR",
    "testchart.optimize_display_response_delay",
    "testchart.interleave",
    "testchart.shift_interleave",
    "testchart.maximize_lightness_difference",
    "testchart.maximize_rec709_luma_difference",
    "testchart.maximize_RGB_difference",
    "testchart.vary_RGB_difference",
)

#: Fullspread-algorithm TI1 keyword → targen algo code, for load reconstruction.
FULLSPREAD_KEYWORD_TO_ALGO = {
    "ERROR_OPTIMISED_PATCHES": "",
    "IFP_PATCHES": "t",
    "INC_FAR_PATCHES": "t",
    "OFPS_PATCHES": "",
    "RANDOM_DEVICE_PATCHES": "r",
    "RANDOM_PATCHES": "r",
    "RANDOM_PERCEPTUAL_PATCHES": "R",
    "SIMPLEX_DEVICE_PATCHES": "i",
    "SIMPLEX_PERCEPTUAL_PATCHES": "I",
    "SPACEFILING_RANDOM_PATCHES": "q",
    "SPACEFILLING_RANDOM_PATCHES": "q",
}


class _GenerateThread(QThread):
    """Run testchart generation off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_create``).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the generated :class:`CGATS`, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, window: TestchartEditorWindow, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window

    def run(self) -> None:
        try:
            result = self._window.tc_create()
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _LoadThread(QThread):
    """Read and interpret a testchart file off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_load_worker``).
        path (str): The chart file to read.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the reconstructed parameter tuple, or an ``Exception``.
    done = Signal(object)

    def __init__(
        self, window: TestchartEditorWindow, path: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._path = path

    def run(self) -> None:
        try:
            result = self._window.tc_load_worker(self._path)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _ExportThread(QThread):
    """Export the chart to CSV off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_export``).
        path (str): Destination file path.
        scale (int): Device-value scale (100, 255 or 1023).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with ``None`` on success, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self,
        window: TestchartEditorWindow,
        path: str,
        scale: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._path = path
        self._scale = scale

    def run(self) -> None:
        try:
            self._window.tc_export(self._path, self._scale)
            result: object = None
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _View3DThread(QThread):
    """Generate the 3D representation(s) off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_save_3d``).
        base (str): The output path with neither colorspace suffix nor extension.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the list of written paths, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, window: TestchartEditorWindow, base: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._base = base

    def run(self) -> None:
        try:
            result: object = self._window.tc_save_3d(self._base)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _AddPatchesThread(QThread):
    """Look up reference / image patches through the profile off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_add_ti3``).
        chart (str | list): A path, or the CGATS lines describing the reference.
        image (QImage | None): The loaded image when importing image patches.
        use_gamut (bool): Whether to run the image through ``tiffgamut``.
        profile (ICCProfile): The preconditioning profile.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the looked-up :class:`CGATS`, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self,
        window: TestchartEditorWindow,
        chart: object,
        image: QImage | None,
        use_gamut: bool,
        profile: ICCProfile,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._chart = chart
        self._image = image
        self._use_gamut = use_gamut
        self._profile = profile

    def run(self) -> None:
        try:
            result: object = self._window.tc_add_ti3(
                self._chart, self._image, self._use_gamut, self._profile
            )
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _CSVConvertThread(QThread):
    """Convert a CSV file to a temporary TI1 off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``csv_convert``).
        path (str): The CSV file to convert.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the converted :class:`CGATS`, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, window: TestchartEditorWindow, path: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._path = path

    def run(self) -> None:
        try:
            result: object = self._window.csv_convert(self._path)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class TestchartEditorWindow(BaseWindow):
    """Standalone testchart editor window (Stages 1-3)."""

    #: Grid columns holding editable device values.
    _RGB_COLUMNS = ("R %", "G %", "B %")

    def __init__(
        self,
        cfg: str = "testchart.file",
        chart_selected_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the testchart editor window.

        Args:
            cfg: Config key the editor's active chart is bound to. Defaults
                to the Profiling tab's ``testchart.file``; the Verification
                tab's editor passes ``measurement_report.chart`` instead so
                saving-as offers to (and, once confirmed, does) retarget the
                report's chart rather than the profiling one.
            chart_selected_callback: Called with the saved path once it
                matches ``cfg``, mirroring wx's
                ``parent_set_chart_methodname`` -- lets the caller (e.g.
                :meth:`ReportPanel.mr_set_testchart
                <DisplayCAL.ui.measurement_report.ReportPanel.mr_set_testchart>`)
                react to the newly selected chart.
        """
        super().__init__(
            name="tcgen",
            title=lang.getstr("testchart.edit"),
            icon_name=f"{APPNAME}-testchart-editor".lower(),
        )
        self.worker = Worker()
        self.worker.set_argyll_version("targen")
        self.argyll_version = self.worker.argyll_version
        self.cfg = cfg
        self._chart_selected_callback = chart_selected_callback
        self.ti1: CGATS | None = None
        self.tc_amount = 0
        self._loading = False
        self._gen_thread: _GenerateThread | None = None
        self._load_thread: _LoadThread | None = None
        self._export_thread: _ExportThread | None = None
        self._view_thread: _View3DThread | None = None
        self._add_thread: _AddPatchesThread | None = None
        self._csv_thread: _CSVConvertThread | None = None
        self._progress: QProgressDialog | None = None

        self.tc_algos_ab = {
            "": lang.getstr("tc.ofp"),
            "t": lang.getstr("tc.t"),
            "r": lang.getstr("tc.r"),
            "R": lang.getstr("tc.R"),
            "q": lang.getstr("tc.q"),
            "i": lang.getstr("tc.i"),
            "I": lang.getstr("tc.I"),
        }
        if self.argyll_version >= [1, 1, 0]:
            self.tc_algos_ab["Q"] = lang.getstr("tc.Q")
        self.tc_algos_ba = swap_dict_keys_values(self.tc_algos_ab)

        self._build_ui()

        drophandlers = dict.fromkeys(LOAD_SUFFIXES, self.load_file)
        drophandlers[".csv"] = self.csv_drop_handler
        drophandlers.update(dict.fromkeys(ADD_TI3_SUFFIXES, self.tc_drop_ti3_handler))
        self.droptarget = FileDropTarget(drophandlers=drophandlers, parent=self)
        self.droptarget.install_on(self)
        self.init_menubar()
        self.resize(760, 640)

        self.tc_update_controls()
        self.tc_check()

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the parameter controls, buttons and patch grid."""
        central = QWidget(self)
        root = QVBoxLayout(central)

        params = QGridLayout()
        params.setHorizontalSpacing(8)
        root.addLayout(params)
        row = 0

        self.tc_white_patches = self._spin(0, 9999)
        params.addWidget(QLabel(lang.getstr("tc.white")), row, 0)
        params.addWidget(self.tc_white_patches, row, 1)
        self.tc_single_channel_patches = self._spin(0, 256)
        params.addWidget(QLabel(lang.getstr("tc.single")), row, 2)
        single_cell = QHBoxLayout()
        single_cell.addWidget(self.tc_single_channel_patches)
        single_cell.addWidget(QLabel(lang.getstr("tc.single.perchannel")))
        single_cell.addStretch(1)
        params.addLayout(single_cell, row, 3)
        row += 1

        self.tc_black_patches: QSpinBox | None = None
        if self.argyll_version >= [1, 6]:
            self.tc_black_patches = self._spin(0, 9999)
            params.addWidget(QLabel(lang.getstr("tc.black")), row, 0)
            params.addWidget(self.tc_black_patches, row, 1)
        self.tc_gray_patches = self._spin(0, 256)
        params.addWidget(QLabel(lang.getstr("tc.gray")), row, 2)
        params.addWidget(self.tc_gray_patches, row, 3)
        row += 1

        self.tc_multi_steps = self._spin(0, 21)
        params.addWidget(QLabel(lang.getstr("tc.multidim")), row, 0)
        multi_cell = QHBoxLayout()
        multi_cell.addWidget(self.tc_multi_steps)
        self.tc_multi_bcc_cb: QCheckBox | None = None
        if self.argyll_version >= [1, 6, 0]:
            self.tc_multi_bcc_cb = QCheckBox(lang.getstr("centered"))
            self.tc_multi_bcc_cb.toggled.connect(self._on_multi_bcc)
            multi_cell.addWidget(self.tc_multi_bcc_cb)
        self.tc_multi_patches = QLabel("")
        multi_cell.addWidget(self.tc_multi_patches)
        multi_cell.addStretch(1)
        params.addLayout(multi_cell, row, 1, 1, 3)
        row += 1

        self.tc_fullspread_patches = self._spin(0, 9999)
        params.addWidget(QLabel(lang.getstr("tc.fullspread")), row, 0)
        params.addWidget(self.tc_fullspread_patches, row, 1)
        algos = sorted(self.tc_algos_ab.values())
        self.tc_algo = QComboBox()
        self.tc_algo.addItems(algos)
        self.tc_algo.currentIndexChanged.connect(self._on_algo)
        params.addWidget(QLabel(lang.getstr("tc.algo")), row, 2)
        params.addWidget(self.tc_algo, row, 3)
        row += 1

        self.tc_adaption_slider, self.tc_adaption_intctrl = self._slider_spin(
            0, 100, self._on_adaption
        )
        params.addWidget(QLabel(lang.getstr("tc.adaption")), row, 0)
        params.addLayout(
            self._pair_layout(self.tc_adaption_slider, self.tc_adaption_intctrl, "%"),
            row,
            1,
            1,
            3,
        )
        row += 1

        self.tc_angle_slider, self.tc_angle_intctrl = self._slider_spin(
            0, 5000, self._on_angle
        )
        params.addWidget(QLabel(lang.getstr("tc.angle")), row, 0)
        params.addLayout(
            self._pair_layout(self.tc_angle_slider, self.tc_angle_intctrl), row, 1, 1, 3
        )
        row += 1

        self.tc_gamma_floatctrl = QDoubleSpinBox()
        self.tc_gamma_floatctrl.setRange(0.0, 9.9)
        self.tc_gamma_floatctrl.setSingleStep(0.05)
        self.tc_gamma_floatctrl.setDecimals(2)
        self.tc_gamma_floatctrl.valueChanged.connect(self._save_and_check)
        params.addWidget(QLabel(lang.getstr("trc.gamma")), row, 0)
        params.addWidget(self.tc_gamma_floatctrl, row, 1)
        row += 1

        self.tc_neutral_axis_emphasis_slider: QSlider | None = None
        self.tc_neutral_axis_emphasis_intctrl: QSpinBox | None = None
        if self.argyll_version >= [1, 3, 3]:
            (
                self.tc_neutral_axis_emphasis_slider,
                self.tc_neutral_axis_emphasis_intctrl,
            ) = self._slider_spin(0, 100, self._on_neutral_axis_emphasis)
            params.addWidget(QLabel(lang.getstr("tc.neutral_axis_emphasis")), row, 0)
            params.addLayout(
                self._pair_layout(
                    self.tc_neutral_axis_emphasis_slider,
                    self.tc_neutral_axis_emphasis_intctrl,
                    "%",
                ),
                row,
                1,
                1,
                3,
            )
            row += 1

        self.tc_dark_emphasis_slider: QSlider | None = None
        self.tc_dark_emphasis_intctrl: QSpinBox | None = None
        if self.argyll_version >= [1, 6, 2]:
            (
                self.tc_dark_emphasis_slider,
                self.tc_dark_emphasis_intctrl,
            ) = self._slider_spin(0, 100, self._on_dark_emphasis)
            params.addWidget(QLabel(lang.getstr("tc.dark_emphasis")), row, 0)
            params.addLayout(
                self._pair_layout(
                    self.tc_dark_emphasis_slider, self.tc_dark_emphasis_intctrl, "%"
                ),
                row,
                1,
                1,
                3,
            )
            row += 1

        # Patch-count spinners share one plain handler (recount + persist).
        for spin in (
            self.tc_white_patches,
            self.tc_single_channel_patches,
            self.tc_gray_patches,
            self.tc_multi_steps,
            self.tc_fullspread_patches,
        ):
            spin.valueChanged.connect(self._on_patch_count)
        if self.tc_black_patches is not None:
            self.tc_black_patches.valueChanged.connect(self._on_patch_count)

        # Preconditioning profile + CIE-sphere filter.
        root.addLayout(self._build_precond_row())
        root.addLayout(self._build_filter_row())

        # 3D view / export controls.
        root.addLayout(self._build_3d_row())

        # Buttons.
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.preview_btn = QPushButton(lang.getstr("testchart.create"))
        self.preview_btn.clicked.connect(self.tc_generate)
        self.save_btn = QPushButton(lang.getstr("save"))
        self.save_btn.clicked.connect(self.tc_save)
        self.save_as_btn = QPushButton(lang.getstr("save_as"))
        self.save_as_btn.clicked.connect(lambda: self.tc_save_as())
        self.export_btn = QPushButton(lang.getstr("export"))
        self.export_btn.clicked.connect(self.tc_export_handler)
        self.clear_btn = QPushButton(lang.getstr("testchart.discard"))
        self.clear_btn.clicked.connect(self.tc_clear)
        for button in (
            self.preview_btn,
            self.save_btn,
            self.save_as_btn,
            self.export_btn,
            self.clear_btn,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        root.addLayout(buttons)

        # Add-patches controls (saturation sweeps + reference/image import).
        root.addLayout(self._build_saturation_row())
        root.addLayout(self._build_add_ti3_row())

        # Grid.
        self.grid = QTableWidget(0, len(self._RGB_COLUMNS) + 1)
        self.grid.setHorizontalHeaderLabels([*self._RGB_COLUMNS, ""])
        self.grid.verticalHeader().setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.grid.setShowGrid(False)
        header = self.grid.horizontalHeader()
        for col in range(len(self._RGB_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        header.setSectionResizeMode(len(self._RGB_COLUMNS), QHeaderView.Fixed)
        self.grid.setColumnWidth(len(self._RGB_COLUMNS), 44)
        self.grid.itemChanged.connect(self._on_cell_changed)
        self.grid.itemSelectionChanged.connect(self.tc_set_default_status)
        self.grid.verticalHeader().sectionDoubleClicked.connect(
            self._on_row_label_dclick
        )
        root.addWidget(self.grid, 1)

        self.setCentralWidget(central)
        self.setStatusBar(self.statusBar())

    def _spin(self, minimum: int, maximum: int) -> QSpinBox:
        """Return a range-bounded integer spin box.

        Args:
            minimum (int): Minimum value.
            maximum (int): Maximum value.

        Returns:
            QSpinBox: The configured spin box.
        """
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setAlignment(Qt.AlignRight)
        return spin

    def _slider_spin(
        self, minimum: int, maximum: int, on_change: Callable[[], None]
    ) -> tuple[QSlider, QSpinBox]:
        """Return a linked (slider, spin) pair sharing a value range.

        Args:
            minimum (int): Minimum value.
            maximum (int): Maximum value.
            on_change (Callable): Slot invoked (with no useful arg) on any change.

        Returns:
            tuple[QSlider, QSpinBox]: The linked controls.
        """
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setAlignment(Qt.AlignRight)
        slider.valueChanged.connect(
            lambda v: self._sync_pair(slider, spin, v, on_change)
        )
        spin.valueChanged.connect(lambda v: self._sync_pair(spin, slider, v, on_change))
        return slider, spin

    def _sync_pair(
        self,
        source: QWidget,
        target: QWidget,
        value: int,
        on_change: Callable[[], None],
    ) -> None:
        """Mirror ``value`` from ``source`` onto ``target`` and fire ``on_change``.

        Args:
            source (QWidget): The control that changed.
            target (QWidget): The paired control to update.
            value (int): The new value.
            on_change (Callable): Slot to invoke after syncing.
        """
        if target.value() != value:
            target.blockSignals(True)
            target.setValue(value)
            target.blockSignals(False)
        if not self._loading:
            on_change()

    @staticmethod
    def _pair_layout(slider: QSlider, spin: QSpinBox, suffix: str = "") -> QHBoxLayout:
        """Return a horizontal layout holding a slider, spin and optional suffix.

        Args:
            slider (QSlider): The slider.
            spin (QSpinBox): The spin box.
            suffix (str): Optional trailing label (e.g. ``"%"``).

        Returns:
            QHBoxLayout: The assembled layout.
        """
        layout = QHBoxLayout()
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        if suffix:
            layout.addWidget(QLabel(suffix))
        return layout

    def _build_3d_row(self) -> QHBoxLayout:
        """Build the diagnostic-3D controls row (view button + VRML options).

        Returns:
            QHBoxLayout: The assembled row.
        """
        row = QHBoxLayout()
        self.view_3d_btn = QPushButton(lang.getstr("view.3d"))
        self.view_3d_btn.setToolTip(lang.getstr("tc.3d"))
        self.view_3d_btn.clicked.connect(self.tc_view_3d)
        row.addWidget(self.view_3d_btn)

        self.view_3d_format_ctrl = QComboBox()
        self.view_3d_format_ctrl.addItems(VALID_VALUES["3d.format"])
        self.view_3d_format_ctrl.currentTextChanged.connect(self._on_3d_format)
        row.addWidget(self.view_3d_format_ctrl)

        row.addSpacing(8)
        self.tc_vrml_device = QCheckBox(lang.getstr("device"))
        self.tc_vrml_device.setToolTip(lang.getstr("tc.3d"))
        self.tc_vrml_device.toggled.connect(self.tc_vrml_handler)
        row.addWidget(self.tc_vrml_device)
        self.tc_vrml_device_colorspace_ctrl = QComboBox()
        self.tc_vrml_device_colorspace_ctrl.addItems(
            VALID_VALUES["tc_vrml_device_colorspace"]
        )
        self.tc_vrml_device_colorspace_ctrl.currentTextChanged.connect(
            self.tc_vrml_handler
        )
        row.addWidget(self.tc_vrml_device_colorspace_ctrl)

        self.tc_vrml_cie = QCheckBox("CIE")
        self.tc_vrml_cie.setToolTip(lang.getstr("tc.3d"))
        self.tc_vrml_cie.toggled.connect(self.tc_vrml_handler)
        row.addWidget(self.tc_vrml_cie)
        self.tc_vrml_cie_colorspace_ctrl = QComboBox()
        self.tc_vrml_cie_colorspace_ctrl.addItems(
            VALID_VALUES["tc_vrml_cie_colorspace"]
        )
        self.tc_vrml_cie_colorspace_ctrl.currentTextChanged.connect(
            self.tc_vrml_handler
        )
        row.addWidget(self.tc_vrml_cie_colorspace_ctrl)

        row.addSpacing(8)
        row.addWidget(QLabel(lang.getstr("tc.vrml.black_offset")))
        self.tc_vrml_black_offset_intctrl = self._spin(0, 40)
        self.tc_vrml_black_offset_intctrl.valueChanged.connect(self.tc_vrml_handler)
        row.addWidget(self.tc_vrml_black_offset_intctrl)

        self.tc_vrml_use_D50_cb = QCheckBox(lang.getstr("tc.vrml.use_D50"))
        self.tc_vrml_use_D50_cb.toggled.connect(self.tc_vrml_handler)
        row.addWidget(self.tc_vrml_use_D50_cb)

        self.tc_vrml_compress_cb = QCheckBox(lang.getstr("compression.gzip"))
        self.tc_vrml_compress_cb.toggled.connect(self.tc_vrml_handler)
        row.addWidget(self.tc_vrml_compress_cb)
        row.addStretch(1)
        return row

    def _build_precond_row(self) -> QHBoxLayout:
        """Build the preconditioning-profile row (checkbox + path + browse).

        Returns:
            QHBoxLayout: The assembled row.
        """
        row = QHBoxLayout()
        self.tc_precond = QCheckBox(lang.getstr("tc.precond"))
        self.tc_precond.setEnabled(False)
        self.tc_precond.toggled.connect(self._on_precond)
        row.addWidget(self.tc_precond)

        #: Editable combo seeded with the reference profiles shipped with Argyll.
        self.tc_precond_profile = QComboBox()
        self.tc_precond_profile.setEditable(True)
        self.tc_precond_profile.setInsertPolicy(QComboBox.NoInsert)
        self.tc_precond_profile.lineEdit().setReadOnly(True)
        self.tc_precond_profile.setToolTip(lang.getstr("tc.precond"))
        history = get_data_path("ref", r"\.(icm|icc)$") or []
        if isinstance(history, str):
            history = [history]
        for path in history:
            self.tc_precond_profile.addItem(os.path.basename(path), path)
        self.tc_precond_profile.currentIndexChanged.connect(
            self._on_precond_profile_index
        )
        # Dropping a profile onto the combo sets it as the preconditioning
        # profile (a chart-replacing load, as elsewhere, needs the main window).
        self.precond_droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(
                (".icc", ".icm"), self.precond_profile_drop_handler
            ),
            parent=self,
        )
        self.precond_droptarget.install_on(self.tc_precond_profile)
        row.addWidget(self.tc_precond_profile, 1)

        self.tc_precond_profile_browse_btn = QPushButton("...")
        self.tc_precond_profile_browse_btn.setToolTip(lang.getstr("tc.precond"))
        self.tc_precond_profile_browse_btn.clicked.connect(
            self._on_precond_profile_browse
        )
        row.addWidget(self.tc_precond_profile_browse_btn)

        self.tc_precond_profile_current_btn = QPushButton(
            lang.getstr("profile.current")
        )
        self.tc_precond_profile_current_btn.clicked.connect(
            self._on_precond_profile_current
        )
        row.addWidget(self.tc_precond_profile_current_btn)
        return row

    def _build_filter_row(self) -> QHBoxLayout:
        """Build the "limit samples to Lab sphere" filter row.

        Returns:
            QHBoxLayout: The assembled row.
        """
        row = QHBoxLayout()
        self.tc_filter = QCheckBox(lang.getstr("tc.limit.sphere"))
        self.tc_filter.toggled.connect(self._on_filter)
        row.addWidget(self.tc_filter)
        row.addWidget(QLabel("L"))
        self.tc_filter_L = self._spin(0, 100)
        self.tc_filter_L.valueChanged.connect(self._on_filter)
        row.addWidget(self.tc_filter_L)
        row.addWidget(QLabel("a"))
        self.tc_filter_a = self._spin(-128, 127)
        self.tc_filter_a.valueChanged.connect(self._on_filter)
        row.addWidget(self.tc_filter_a)
        row.addWidget(QLabel("b"))
        self.tc_filter_b = self._spin(-128, 127)
        self.tc_filter_b.valueChanged.connect(self._on_filter)
        row.addWidget(self.tc_filter_b)
        row.addWidget(QLabel(lang.getstr("tc.limit.sphere_radius")))
        self.tc_filter_rad = self._spin(1, 255)
        self.tc_filter_rad.valueChanged.connect(self._on_filter)
        row.addWidget(self.tc_filter_rad)
        row.addStretch(1)
        return row

    def _build_saturation_row(self) -> QHBoxLayout:
        """Build the saturation-sweep controls (count + colour buttons + custom).

        Returns:
            QHBoxLayout: The assembled row.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.getstr("testchart.add_saturation_sweeps")))
        self.saturation_sweeps_intctrl = self._spin(2, 255)
        row.addWidget(self.saturation_sweeps_intctrl)

        #: The primary/secondary sweep buttons, keyed by colour letter.
        self.saturation_sweeps_btns: dict[str, QPushButton] = {}
        for color in SATURATION_SWEEP_RGB:
            button = QPushButton(color)
            button.setFixedWidth(45)
            button.clicked.connect(
                lambda _checked=False, c=color: self.tc_add_saturation_sweeps(c)
            )
            self.saturation_sweeps_btns[color] = button
            row.addWidget(button)

        self.saturation_sweeps_custom_btn = QPushButton("=")
        self.saturation_sweeps_custom_btn.setFixedWidth(45)
        self.saturation_sweeps_custom_btn.clicked.connect(
            lambda: self.tc_add_saturation_sweeps(None)
        )
        row.addWidget(self.saturation_sweeps_custom_btn)

        #: The custom-RGB sweep target spinners, keyed by component letter.
        self.saturation_sweeps_custom_ctrls: dict[str, QDoubleSpinBox] = {}
        for component in ("R", "G", "B"):
            row.addWidget(QLabel(component))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(2)
            spin.setSingleStep(100.0 / 255)
            spin.valueChanged.connect(self._on_saturation_custom)
            self.saturation_sweeps_custom_ctrls[component] = spin
            row.addWidget(spin)
        row.addStretch(1)
        return row

    def _build_add_ti3_row(self) -> QHBoxLayout:
        """Build the "add reference patches" row.

        Matches wx's "buttons row 3": the add-reference button + its
        relative-adaptation toggle, followed by the patch-reordering combo
        box and its Apply button.

        Returns:
            QHBoxLayout: The assembled row.
        """
        row = QHBoxLayout()
        self.add_ti3_btn = QPushButton(lang.getstr("testchart.add_ti3_patches"))
        self.add_ti3_btn.clicked.connect(self.tc_add_ti3_handler)
        row.addWidget(self.add_ti3_btn)
        self.add_ti3_relative_cb = QCheckBox(
            lang.getstr("whitepoint.simulate.relative")
        )
        self.add_ti3_relative_cb.toggled.connect(self._on_add_ti3_relative)
        row.addWidget(self.add_ti3_relative_cb)
        row.addSpacing(50)

        self.change_patch_order_ctrl = QComboBox()
        self.change_patch_order_ctrl.addItems(
            [lang.getstr(lstr) for lstr in PATCH_ORDER_LSTRS]
        )
        self.change_patch_order_ctrl.setToolTip(
            lang.getstr("testchart.change_patch_order")
        )
        row.addWidget(self.change_patch_order_ctrl)
        self.change_patch_order_btn = QPushButton(lang.getstr("apply"))
        self.change_patch_order_btn.clicked.connect(self.tc_sort_handler)
        row.addWidget(self.change_patch_order_btn)

        row.addStretch(1)
        return row

    # -- config sync -------------------------------------------------------

    def tc_update_controls(self) -> None:
        """Load every control's value from the current configuration."""
        self._loading = True
        try:
            self.tc_algo.setCurrentText(
                self.tc_algos_ab.get(
                    getcfg("tc_algo"), self.tc_algos_ab.get(DEFAULTS["tc_algo"])
                )
            )
            self.tc_white_patches.setValue(getcfg("tc_white_patches"))
            if self.tc_black_patches is not None:
                self.tc_black_patches.setValue(getcfg("tc_black_patches"))
            self.tc_single_channel_patches.setValue(getcfg("tc_single_channel_patches"))
            self.tc_gray_patches.setValue(getcfg("tc_gray_patches"))
            if getcfg("tc_multi_bcc_steps"):
                setcfg("tc_multi_bcc", 1)
                self.tc_multi_steps.setValue(getcfg("tc_multi_bcc_steps"))
            else:
                setcfg("tc_multi_bcc", 0)
                self.tc_multi_steps.setValue(getcfg("tc_multi_steps"))
            if self.tc_multi_bcc_cb is not None:
                self.tc_multi_bcc_cb.setChecked(bool(getcfg("tc_multi_bcc")))
            self.tc_fullspread_patches.setValue(getcfg("tc_fullspread_patches"))
            self.tc_angle_intctrl.setValue(int(getcfg("tc_angle") * 10000))
            self.tc_adaption_intctrl.setValue(int(getcfg("tc_adaption") * 100))
            self.tc_gamma_floatctrl.setValue(getcfg("tc_gamma"))
            if self.tc_neutral_axis_emphasis_intctrl is not None:
                self.tc_neutral_axis_emphasis_intctrl.setValue(
                    int(getcfg("tc_neutral_axis_emphasis") * 100)
                )
            if self.tc_dark_emphasis_intctrl is not None:
                self.tc_dark_emphasis_intctrl.setValue(
                    int(getcfg("tc_dark_emphasis") * 100)
                )
            self.view_3d_format_ctrl.setCurrentText(getcfg("3d.format"))
            self.tc_vrml_device.setChecked(bool(int(getcfg("tc_vrml_device"))))
            self.tc_vrml_device_colorspace_ctrl.setCurrentText(
                getcfg("tc_vrml_device_colorspace")
            )
            self.tc_vrml_cie.setChecked(bool(int(getcfg("tc_vrml_cie"))))
            self.tc_vrml_cie_colorspace_ctrl.setCurrentText(
                getcfg("tc_vrml_cie_colorspace")
            )
            self.tc_vrml_black_offset_intctrl.setValue(getcfg("tc_vrml_black_offset"))
            self.tc_vrml_use_D50_cb.setChecked(bool(int(getcfg("tc_vrml_use_D50"))))
            self.tc_vrml_compress_cb.setChecked(bool(int(getcfg("vrml.compress"))))
            self._select_precond_profile(getcfg("tc_precond_profile"))
            self.tc_precond.setChecked(bool(int(getcfg("tc_precond"))))
            self.tc_filter.setChecked(bool(int(getcfg("tc_filter"))))
            self.tc_filter_L.setValue(getcfg("tc_filter_L"))
            self.tc_filter_a.setValue(getcfg("tc_filter_a"))
            self.tc_filter_b.setValue(getcfg("tc_filter_b"))
            self.tc_filter_rad.setValue(getcfg("tc_filter_rad"))
            self.saturation_sweeps_intctrl.setValue(getcfg("tc.saturation_sweeps"))
            for component, spin in self.saturation_sweeps_custom_ctrls.items():
                spin.setValue(getcfg(f"tc.saturation_sweeps.custom.{component}"))
            self.add_ti3_relative_cb.setChecked(
                bool(int(getcfg("tc_add_ti3_relative")))
            )
        finally:
            self._loading = False
        self._update_multi_patches_label()
        self._update_enabled_states()
        self.tc_vrml_update_enabled()

    def tc_save_cfg(self) -> None:
        """Persist the core control values to configuration."""
        setcfg("tc_white_patches", self.tc_white_patches.value())
        if self.tc_black_patches is not None:
            setcfg("tc_black_patches", self.tc_black_patches.value())
        setcfg("tc_single_channel_patches", self.tc_single_channel_patches.value())
        setcfg("tc_gray_patches", self.tc_gray_patches.value())
        if self.tc_multi_bcc_cb is not None and self.tc_multi_bcc_cb.isChecked():
            setcfg("tc_multi_bcc", 1)
            setcfg("tc_multi_bcc_steps", self.tc_multi_steps.value())
            setcfg("tc_multi_steps", 0)
        else:
            setcfg("tc_multi_bcc", 0)
            setcfg("tc_multi_bcc_steps", 0)
            setcfg("tc_multi_steps", self.tc_multi_steps.value())
        setcfg("tc_fullspread_patches", self.tc_fullspread_patches.value())
        tc_algo = self.tc_algos_ba[self.tc_algo.currentText()]
        setcfg("tc_algo", tc_algo)
        setcfg("tc_angle", self.tc_angle_intctrl.value() / 10000.0)
        setcfg("tc_adaption", self.tc_adaption_intctrl.value() / 100.0)
        setcfg("tc_gamma", self.tc_gamma_floatctrl.value())
        if self.tc_neutral_axis_emphasis_intctrl is not None:
            setcfg(
                "tc_neutral_axis_emphasis",
                self.tc_neutral_axis_emphasis_intctrl.value() / 100.0,
            )
        if self.tc_dark_emphasis_intctrl is not None:
            setcfg("tc_dark_emphasis", self.tc_dark_emphasis_intctrl.value() / 100.0)
        setcfg("tc.saturation_sweeps", self.saturation_sweeps_intctrl.value())
        for component, spin in self.saturation_sweeps_custom_ctrls.items():
            setcfg(f"tc.saturation_sweeps.custom.{component}", spin.value())

    def writecfg(self) -> None:
        """Write the testchart-editor configuration to disk."""
        config.writecfg(
            module="testchart-editor",
            options=(
                "3d.",
                "last_ti1_path",
                "last_testchart_export_path",
                "last_vrml_path",
                "position.tcgen",
                "size.tcgen",
                "tc.",
                "tc_",
                "vrml.",
            ),
        )

    # -- control handlers --------------------------------------------------

    def _save_and_check(self, *_args) -> None:
        """Persist config and refresh derived state (buttons, status, labels)."""
        if self._loading:
            return
        self.tc_save_cfg()
        self._update_multi_patches_label()
        self.tc_check()

    def _on_patch_count(self, *_args) -> None:
        """React to any patch-count spin change."""
        self._save_and_check()

    def _on_multi_bcc(self, *_args) -> None:
        """React to the body-centered-cubic multi-dim toggle."""
        self._save_and_check()

    def _on_algo(self, *_args) -> None:
        """React to an algorithm change (re-enable dependent controls)."""
        self._save_and_check()

    def _on_adaption(self) -> None:
        """React to an adaption change."""
        self._save_and_check()

    def _on_angle(self) -> None:
        """React to an angle change."""
        self._save_and_check()

    def _on_neutral_axis_emphasis(self) -> None:
        """React to a neutral-axis-emphasis change."""
        self._save_and_check()

    def _on_dark_emphasis(self) -> None:
        """React to a dark-region-emphasis change."""
        self._save_and_check()

    # -- preconditioning / filter handlers ---------------------------------

    def _select_precond_profile(self, path: str) -> None:
        """Show ``path`` in the profile combo, adding it if not already listed.

        Args:
            path (str): The profile path to select (may be empty).
        """
        block = self.tc_precond_profile.blockSignals(True)
        try:
            if not path:
                self.tc_precond_profile.setCurrentIndex(-1)
                self.tc_precond_profile.lineEdit().clear()
                return
            index = self.tc_precond_profile.findData(path)
            if index < 0:
                self.tc_precond_profile.addItem(os.path.basename(path), path)
                index = self.tc_precond_profile.count() - 1
            self.tc_precond_profile.setCurrentIndex(index)
        finally:
            self.tc_precond_profile.blockSignals(block)

    def _set_precond_profile(self, path: str) -> None:
        """Persist ``path`` as the preconditioning profile and refresh state.

        Args:
            path (str): The chosen profile path.
        """
        self._select_precond_profile(path)
        setcfg("tc_precond_profile", path)
        if not path:
            setcfg("tc_precond", 0)
            self.tc_precond.setChecked(False)
        self._update_enabled_states()

    def _on_precond_profile_index(self, index: int) -> None:
        """React to a profile chosen from the combo's history.

        Args:
            index (int): The selected combo index (``-1`` when cleared).
        """
        if self._loading or index < 0:
            return
        self._set_precond_profile(self.tc_precond_profile.itemData(index) or "")

    def _on_precond_profile_browse(self) -> None:
        """Browse for a preconditioning profile."""
        default_dir = get_verified_path("tc_precond_profile")[0]
        path, _selected = file_dialog.get_open_file_name(
            self,
            lang.getstr("tc.precond"),
            default_dir,
            lang.getstr("filetype.icc_mpp") + " (*.icc *.icm *.mpp)",
        )
        if path:
            self._set_precond_profile(path)

    def _on_precond_profile_current(self) -> None:
        """Use the current display profile as the preconditioning profile."""
        profile_path = get_current_profile_path(True, True)
        if profile_path:
            self._set_precond_profile(profile_path)
        else:
            message_box.critical(
                self,
                self.windowTitle(),
                lang.getstr(
                    "display_profile.not_detected",
                    config.get_display_name(None, True),
                ),
            )

    def precond_profile_drop_handler(self, path: str) -> None:
        """Set a profile dropped onto the editor as the preconditioning profile.

        Args:
            path (str): The dropped ``.icc``/``.icm`` path.
        """
        self._set_precond_profile(path)

    def _on_precond(self, checked: bool) -> None:
        """Persist the preconditioning toggle and reset adaption accordingly.

        Args:
            checked (bool): The new checkbox state.
        """
        if self._loading:
            return
        setcfg("tc_precond", int(checked))
        self.tc_adaption_intctrl.setValue(
            int((1 if checked else DEFAULTS["tc_adaption"]) * 100)
        )
        self._save_and_check()

    def _on_filter(self, *_args) -> None:
        """Persist the Lab-sphere filter controls."""
        if self._loading:
            return
        setcfg("tc_filter", int(self.tc_filter.isChecked()))
        setcfg("tc_filter_L", self.tc_filter_L.value())
        setcfg("tc_filter_a", self.tc_filter_a.value())
        setcfg("tc_filter_b", self.tc_filter_b.value())
        setcfg("tc_filter_rad", self.tc_filter_rad.value())

    def _on_saturation_custom(self, *_args) -> None:
        """Persist the custom saturation-sweep target and refresh button state."""
        if self._loading:
            return
        for component, spin in self.saturation_sweeps_custom_ctrls.items():
            setcfg(f"tc.saturation_sweeps.custom.{component}", spin.value())
        self._update_add_precond_controls()

    def _on_add_ti3_relative(self, checked: bool) -> None:
        """Persist the "relative to display whitepoint" import toggle.

        Args:
            checked (bool): The new checkbox state.
        """
        if self._loading:
            return
        setcfg("tc_add_ti3_relative", int(checked))

    def tc_vrml_handler(self, *_args) -> None:
        """Persist the diagnostic-3D options and refresh the view button state."""
        if self._loading:
            return
        setcfg("tc_vrml_device", int(self.tc_vrml_device.isChecked()))
        setcfg("tc_vrml_cie", int(self.tc_vrml_cie.isChecked()))
        setcfg(
            "tc_vrml_device_colorspace",
            self.tc_vrml_device_colorspace_ctrl.currentText(),
        )
        setcfg("tc_vrml_cie_colorspace", self.tc_vrml_cie_colorspace_ctrl.currentText())
        setcfg("tc_vrml_black_offset", self.tc_vrml_black_offset_intctrl.value())
        setcfg("tc_vrml_use_D50", int(self.tc_vrml_use_D50_cb.isChecked()))
        setcfg("vrml.compress", int(self.tc_vrml_compress_cb.isChecked()))
        self.tc_vrml_update_enabled()

    def _on_3d_format(self, text: str) -> None:
        """Persist the selected diagnostic-3D file format.

        Args:
            text (str): The chosen format (``HTML`` / ``VRML`` / ``X3D``).
        """
        if self._loading:
            return
        setcfg("3d.format", text)

    def tc_vrml_update_enabled(self) -> None:
        """Enable the 3D-view button only for a chart with a colorspace chosen."""
        enabled = self.ti1 is not None and (
            self.tc_vrml_device.isChecked() or self.tc_vrml_cie.isChecked()
        )
        self.view_3d_btn.setEnabled(enabled)

    def _update_multi_patches_label(self) -> None:
        """Show the patch count implied by the multi-dimensional steps."""
        steps = self.tc_multi_steps.value()
        count = int(math.pow(steps, 3)) if steps > 1 else 0
        self.tc_multi_patches.setText(str(count) if count else "")

    def _update_enabled_states(self) -> None:
        """Enable/disable the algorithm-dependent controls (matches wx)."""
        algo_enable = self.tc_fullspread_patches.value() > 0
        self.tc_algo.setEnabled(algo_enable)
        algo = self.tc_algos_ba.get(self.tc_algo.currentText(), "")
        self.tc_adaption_slider.setEnabled(algo_enable and algo == "")
        self.tc_adaption_intctrl.setEnabled(algo_enable and algo == "")
        self.tc_angle_slider.setEnabled(algo_enable and algo in ("i", "I"))
        self.tc_angle_intctrl.setEnabled(algo_enable and algo in ("i", "I"))
        precond_enable = algo in ("I", "Q", "R", "t") or (
            algo == "" and self.tc_adaption_intctrl.value() > 0
        )
        if self.tc_neutral_axis_emphasis_slider is not None:
            self.tc_neutral_axis_emphasis_slider.setEnabled(
                algo_enable and precond_enable
            )
            self.tc_neutral_axis_emphasis_intctrl.setEnabled(
                algo_enable and precond_enable
            )
        if self.tc_dark_emphasis_slider is not None:
            dark_enable = self.argyll_version >= [1, 6, 3] or (
                precond_enable
                and bool(int(getcfg("tc_precond")))
                and bool(getcfg("tc_precond_profile"))
            )
            self.tc_dark_emphasis_slider.setEnabled(dark_enable)
            self.tc_dark_emphasis_intctrl.setEnabled(dark_enable)
        self.tc_precond.setEnabled(bool(getcfg("tc_precond_profile")))
        self._update_add_precond_controls()
        self._update_sort_controls()

    def _update_sort_controls(self) -> None:
        """Enable the patch-reordering combo/button only for a loaded chart.

        Ports ``wx_testchart_editor.tc_enable_sort_controls``.
        """
        enabled = self.ti1 is not None
        self.change_patch_order_ctrl.setEnabled(enabled)
        self.change_patch_order_btn.setEnabled(enabled)

    def _update_add_precond_controls(self) -> None:
        """Enable the saturation-sweep / add-reference controls (matches wx).

        These need both a loaded chart to append to and a preconditioning
        profile to look reference values up through.
        """
        enabled = self.ti1 is not None and bool(getcfg("tc_precond_profile"))
        self.saturation_sweeps_intctrl.setEnabled(enabled)
        for button in self.saturation_sweeps_btns.values():
            button.setEnabled(enabled)
        rgb = [spin.value() for spin in self.saturation_sweeps_custom_ctrls.values()]
        for spin in self.saturation_sweeps_custom_ctrls.values():
            spin.setEnabled(enabled)
        self.saturation_sweeps_custom_btn.setEnabled(
            enabled and not (rgb[0] == rgb[1] == rgb[2])
        )
        self.add_ti3_btn.setEnabled(enabled)
        self.add_ti3_relative_cb.setEnabled(enabled)

    # -- patch counting ----------------------------------------------------

    def tc_get_total_patches(
        self,
        white_patches: int | None = None,
        black_patches: int | None = None,
        single_channel_patches: int | None = None,
        gray_patches: int | None = None,
        multi_steps: int | None = None,
        multi_bcc_steps: int | None = None,
        fullspread_patches: int | None = None,
    ) -> int:
        """Return the total patch count for the given (or current) parameters.

        Args:
            white_patches (int | None): White patch count.
            black_patches (int | None): Black patch count.
            single_channel_patches (int | None): Single-channel patch count.
            gray_patches (int | None): Gray patch count.
            multi_steps (int | None): Multi-dimensional steps.
            multi_bcc_steps (int | None): Body-centered-cubic multi-dim steps.
            fullspread_patches (int | None): Full-spread patch count.

        Returns:
            int: The total number of patches.
        """
        if (
            self.ti1 is not None
            and [
                white_patches,
                black_patches,
                single_channel_patches,
                gray_patches,
                multi_steps,
                multi_bcc_steps,
                fullspread_patches,
            ]
            == [None] * 7
        ):
            return self.ti1.queryv1("NUMBER_OF_SETS")
        if white_patches is None:
            white_patches = self.tc_white_patches.value()
        if black_patches is None:
            black_patches = (
                self.tc_black_patches.value()
                if self.tc_black_patches is not None
                else 0
            )
        if single_channel_patches is None:
            single_channel_patches = self.tc_single_channel_patches.value()
        if gray_patches is None:
            gray_patches = self.tc_gray_patches.value()
        if (
            gray_patches == 0
            and (single_channel_patches > 0 or black_patches > 0)
            and white_patches > 0
        ):
            gray_patches = 2
        if multi_steps is None:
            multi_steps = self.tc_multi_steps.value()
        if (
            multi_bcc_steps is None
            and getcfg("tc_multi_bcc")
            and self.argyll_version >= [1, 6]
        ):
            multi_bcc_steps = self.tc_multi_steps.value()
        if fullspread_patches is None:
            fullspread_patches = self.tc_fullspread_patches.value()
        return get_total_patches(
            white_patches,
            black_patches,
            single_channel_patches,
            gray_patches,
            multi_steps,
            multi_bcc_steps,
            fullspread_patches,
        )

    def tc_get_black_patches(self) -> int:
        """Return the effective number of black patches.

        Returns:
            int: The black patch count after gray/multi adjustments.
        """
        black_patches = (
            self.tc_black_patches.value() if self.tc_black_patches is not None else 0
        )
        single = self.tc_single_channel_patches.value()
        gray = self.tc_gray_patches.value()
        if gray == 0 and single > 0 and black_patches > 0:
            gray = 2
        if self.tc_multi_steps.value() > 1 or gray > 1:
            black_patches -= 1
        return max(0, black_patches)

    def tc_get_white_patches(self) -> int:
        """Return the effective number of white patches.

        Returns:
            int: The white patch count after gray/multi adjustments.
        """
        white = self.tc_white_patches.value()
        single = self.tc_single_channel_patches.value()
        gray = self.tc_gray_patches.value()
        if gray == 0 and single > 0 and white > 0:
            gray = 2
        if self.tc_multi_steps.value() > 1 or gray > 1:
            white -= 1
        return max(0, white)

    # -- state -------------------------------------------------------------

    def tc_check(self) -> None:
        """Enable/disable buttons and refresh the status line for the state."""
        self.tc_amount = self.tc_get_total_patches(self.tc_white_patches.value())
        can_create = (
            self.tc_amount
            - max(0, self.tc_get_white_patches())
            - max(0, self.tc_get_black_patches())
            >= 8
        )
        self.preview_btn.setEnabled(can_create)
        self.clear_btn.setEnabled(self.ti1 is not None)
        self.save_as_btn.setEnabled(self.ti1 is not None)
        self.export_btn.setEnabled(self.ti1 is not None)
        self.tc_save_check()
        self.tc_vrml_update_enabled()
        self._update_add_precond_controls()
        self._update_sort_controls()
        self.tc_set_default_status()

    def tc_save_check(self) -> None:
        """Enable the Save button only for a modified, user-owned chart."""
        ti1 = self.ti1
        enabled = bool(
            ti1 is not None
            and ti1.modified
            and ti1.filename
            and os.path.exists(ti1.filename)
            and get_data_path(os.path.join("ref", os.path.basename(ti1.filename)))
            != ti1.filename
            and get_data_path(os.path.join("ti1", os.path.basename(ti1.filename)))
            != ti1.filename
        )
        self.save_btn.setEnabled(enabled)

    def tc_set_default_status(self) -> None:
        """Show the total (and selected) patch count in the status bar."""
        if not self.tc_amount:
            self.statusBar().clearMessage()
            return
        text = f"{lang.getstr('tc.patches.total')}: {self.tc_amount}"
        rows = {index.row() for index in self.grid.selectionModel().selectedRows()}
        if rows:
            text += f" / {lang.getstr('tc.patches.selected')}: {len(rows)}"
        self.statusBar().showMessage(text)

    # -- colour label ------------------------------------------------------

    def _get_color_label(self, sample: object) -> tuple[QColor, str, QColor | None]:
        """Return the swatch colour, marker text and text colour for a sample.

        Ports ``wx_testchart_editor.tc_getcolorlabel``: classifies each patch
        (white/black/neutral, primaries and secondaries plus their light
        variants) and picks a legible label colour.

        Args:
            sample: A CGATS sample with ``RGB_R``/``RGB_G``/``RGB_B`` (0..100).

        Returns:
            tuple[QColor, str, QColor | None]: Background colour, label text and
            optional text colour.
        """
        r, g, b = sample.RGB_R, sample.RGB_G, sample.RGB_B
        color = QColor(
            round(r / 100.0 * 255), round(g / 100.0 * 255), round(b / 100.0 * 255)
        )
        white = QColor(255, 255, 255)
        black = QColor(0, 0, 0)
        if r == g == b:  # neutral / black / white
            label_color = white if r < 50 else black
            text = "K" if r <= 50 else ("W" if r == 100 else "k")
        elif (g == 0 and b == 0) or (r == 100 and g == b):  # red
            label_color = black if r > 75 else white
            text = "r" if r == 100 and g > 0 else "R"
        elif (r == 0 and b == 0) or (g == 100 and r == b):  # green
            label_color = black if g > 75 else white
            text = "g" if g == 100 and r > 0 else "G"
        elif (r == 0 and g == 0) or (b == 100 and r == g):  # blue
            label_color = black if r > 25 else white
            text = "b" if b == 100 and r > 0 else "B"
        elif (r == 0 or b == 100) and g == b:  # cyan
            label_color = black if g > 75 else white
            text = "c" if g == 100 and r > 0 else "C"
        elif (g == 0 or r == 100) and r == b:  # magenta
            label_color = black if r > 75 else white
            text = "m" if r == 100 and g > 0 else "M"
        elif (b == 0 or g == 100) and r == g:  # yellow
            label_color = black if g > 75 else white
            text = "y" if b > 0 else "Y"
        else:
            return color, "", None
        return color, text, label_color

    # -- grid --------------------------------------------------------------

    def _populate_grid(self) -> None:
        """Fill the grid from ``self.ti1`` (RGB columns + swatch)."""
        self.grid.blockSignals(True)
        self.grid.clearContents()
        data = self.ti1.queryv1("DATA")
        count = self.ti1.queryv1("NUMBER_OF_SETS")
        self.grid.setRowCount(count)
        for row in range(count):
            sample = data[row]
            for col, label in enumerate(("RGB_R", "RGB_G", "RGB_B")):
                item = QTableWidgetItem(self._fmt(sample[label]))
                item.setTextAlignment(Qt.AlignCenter)
                self.grid.setItem(row, col, item)
            self._set_swatch(row, sample)
        self.grid.blockSignals(False)
        self.tc_amount = count
        self.tc_set_default_status()

    def _set_swatch(self, row: int, sample: object) -> None:
        """Set the swatch cell's colour and marker text for ``row``.

        Args:
            row (int): The grid row.
            sample: The CGATS sample for that row.
        """
        color, text, text_color = self._get_color_label(sample)
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(color)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if text_color is not None:
            item.setForeground(text_color)
        self.grid.setItem(row, len(self._RGB_COLUMNS), item)

    @staticmethod
    def _fmt(value: float) -> str:
        """Format a 0..100 device value for display.

        Args:
            value (float): The device value.

        Returns:
            str: A trimmed decimal string (integers shown without a point).
        """
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        """Apply an edited RGB cell back to the chart and recolour the swatch.

        Args:
            item (QTableWidgetItem): The edited grid item.
        """
        if self.ti1 is None or item.column() >= len(self._RGB_COLUMNS):
            return
        try:
            value = max(0.0, min(float(item.text()), 100.0))
        except ValueError:
            return
        data = self.ti1.queryv1("DATA")
        sample = data[item.row()]
        label = ("RGB_R", "RGB_G", "RGB_B")[item.column()]
        sample[label] = value
        self.ti1.setmodified(True)
        self.grid.blockSignals(True)
        item.setText(self._fmt(value))
        self._set_swatch(item.row(), sample)
        self.grid.blockSignals(False)
        self.tc_save_check()

    # -- keyboard / row editing ----------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Handle Ctrl/Cmd+S (save) and Delete/Backspace (remove selected rows).

        Ports ``wx_testchart_editor.tc_key_handler``.

        Args:
            event (QKeyEvent): The Qt key event.
        """
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            if event.key() == Qt.Key_S:
                if self.ti1 is not None:
                    if not self.ti1.filename or not os.path.exists(self.ti1.filename):
                        self.tc_save_as()
                    elif self.ti1.modified:
                        self.tc_save()
                return
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                rows = sorted(
                    index.row() for index in self.grid.selectionModel().selectedRows()
                )
                if rows:
                    if len(rows) == self.grid.rowCount():
                        self.tc_clear()
                    else:
                        self.tc_delete_rows(rows)
                return
        super().keyPressEvent(event)

    def _on_row_label_dclick(self, row: int) -> None:
        """Insert a new white patch row below a double-clicked row label.

        Ports ``wx_testchart_editor.tc_grid_label_left_dclick_handler``.

        Args:
            row (int): The grid row whose vertical-header label was
                double-clicked.
        """
        if self.ti1 is None:
            return
        approx_wp = self.ti1.queryv1("APPROX_WHITE_POINT")
        if approx_wp:
            wp = [float(v) for v in approx_wp.split()]
            wp = [(v / wp[1]) * 100.0 for v in wp]
        else:
            wp = colormath.get_standard_illuminant("D65", scale=100)
        newdata = {
            "SAMPLE_ID": row + 2,
            "RGB_R": 100.0,
            "RGB_G": 100.0,
            "RGB_B": 100.0,
            "XYZ_X": wp[0],
            "XYZ_Y": 100.0,
            "XYZ_Z": wp[2],
        }
        self.tc_add_data(row, [newdata])

    def tc_delete_rows(self, rows: list[int]) -> None:
        """Delete the given grid rows and renumber the underlying chart data.

        Ports ``wx_testchart_editor.tc_delete_rows``.

        Args:
            rows (list[int]): Row indices to delete.
        """
        if self.ti1 is None or not rows:
            return
        data = self.ti1.queryv1("DATA")
        for row in sorted(rows, reverse=True):
            data.moveby1(row + 1, -1)
            del data[len(data) - 1]
        self.ti1.setmodified(True)
        self._populate_grid()
        self._select_row(min(rows))
        self.tc_check()

    # -- patch reordering ----------------------------------------------------

    def tc_sort_handler(self, *_args) -> None:
        """Reorder the chart's patches per the selected mode and refresh the grid.

        Ports ``wx_testchart_editor.tc_sort_handler``'s 23 modes (gray/white/
        primary-to-top, hue-space sorts, and checkerboard interleave patterns)
        onto the same :class:`DisplayCAL.cgats.CGATS` sort/checkerboard methods.
        """
        if self.ti1 is None:
            return
        idx = self.change_patch_order_ctrl.currentIndex()
        if idx == 0:
            self.ti1.sort_rgb_gray_to_top()
        elif idx == 1:
            self.ti1.sort_rgb_white_to_top()
        elif idx == 2:
            self.ti1.sort_rgb_to_top(red=True)  # Red
        elif idx == 3:
            self.ti1.sort_rgb_to_top(green=True)  # Green
        elif idx == 4:
            self.ti1.sort_rgb_to_top(blue=True)  # Blue
        elif idx == 5:
            self.ti1.sort_rgb_to_top(green=True, blue=True)  # Cyan
        elif idx == 6:
            self.ti1.sort_rgb_to_top(red=True, blue=True)  # Magenta
        elif idx == 7:
            self.ti1.sort_rgb_to_top(red=True, green=True)  # Yellow
        elif idx == 8:
            self.ti1.sort_by_hsi()
        elif idx == 9:
            self.ti1.sort_by_hsl()
        elif idx == 10:
            self.ti1.sort_by_hsv()
        elif idx == 11:
            self.ti1.sort_by_l()
        elif idx == 12:
            self.ti1.sort_by_rec709_luma()
        elif idx == 13:
            self.ti1.sort_by_rgb()
        elif idx == 14:
            self.ti1.sort_by_rgb_sum()
        elif idx == 15:
            self.ti1.sort_by_bgr()
        elif idx == 16:
            # Minimize display response delay
            self.ti1.sort_by_bgr()
            self.ti1.sort_rgb_gray_to_top()
            self.ti1.sort_rgb_white_to_top()
        elif idx == 17:
            # Interleave
            self.ti1.checkerboard(None, None)
        elif idx == 18:
            # Shift & interleave
            self.ti1.checkerboard(None, None, split_grays=True, shift=True)
        elif idx == 19:
            # Maximize L* difference
            self.ti1.checkerboard(sort1=stable_sort_by_l)
        elif idx == 20:
            # Maximize Rec. 709 luma difference
            self.ti1.checkerboard(sort_by_rec709_luma)
        elif idx == 21:
            # Maximize RGB difference
            self.ti1.checkerboard(sort_by_rgb_sum)
        elif idx == 22:
            # Vary RGB difference
            self.ti1.checkerboard(sort_by_rgb, None, split_grays=True, shift=True)
        self.ti1.setmodified(True)
        self._populate_grid()
        self.tc_save_check()

    # -- generation --------------------------------------------------------

    def tc_generate(self) -> None:
        """Generate a new testchart via Argyll ``targen`` (off-thread)."""
        if self._gen_thread is not None and self._gen_thread.isRunning():
            return
        if not check_set_argyll_bin():
            message_box.warning(
                self, self.windowTitle(), lang.getstr("argyll.dir.invalid", "")
            )
            return
        self.tc_save_cfg()
        self.writecfg()
        self.worker.interactive = False
        self.preview_btn.setEnabled(False)
        self.statusBar().showMessage(lang.getstr("testchart.create"))
        self._gen_thread = _GenerateThread(self, parent=self)
        self._gen_thread.done.connect(self._on_generated)
        self._gen_thread.start()

    def tc_create(self) -> CGATS | Exception:
        """Run ``targen`` and return the resulting chart (off the GUI thread).

        Returns:
            CGATS | Exception: The generated chart, or the raised error.
        """
        cmd, args = self.worker.prepare_targen()
        if isinstance(cmd, Exception):
            return cmd
        result = self.worker.exec_cmd(
            cmd, args, low_contrast=False, skip_scripts=True, silent=False
        )
        if isinstance(result, Exception):
            self.worker.wrapup(False)
            return result
        if not result:
            self.worker.wrapup(False)
            return Error("".join(self.worker.errors) or "targen failed")
        path = os.path.join(self.worker.tempdir, "temp.ti1")
        checked = check_file_isfile(path, silent=False)
        if isinstance(checked, Exception):
            self.worker.wrapup(False)
            return checked
        try:
            chart = CGATS(path)
            chart.filename = None
        except Exception as exception:  # noqa: BLE001
            self.worker.wrapup(False)
            return Error(f"Error - testchart file could not be read: {exception!s} ")
        self.worker.wrapup(False)
        return chart

    def _on_generated(self, result: object) -> None:
        """Receive a generated chart on the GUI thread and display it.

        Args:
            result (object): The generated ``CGATS`` or an ``Exception``.
        """
        self._gen_thread = None
        self.preview_btn.setEnabled(True)
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
            self.tc_check()
            return
        self.ti1 = result
        self._populate_grid()
        self.tc_check()

    # -- loading -----------------------------------------------------------

    def load_file(self, path: str) -> None:
        """Load a testchart file at ``path`` (off-thread).

        Args:
            path (str): Path to a ``.ti1``/``.ti3``/``.cgats``/``.txt`` or ICC file.
        """
        if self._load_thread is not None and self._load_thread.isRunning():
            return
        self.statusBar().showMessage(lang.getstr("testchart.read"))
        self._load_thread = _LoadThread(self, os.path.abspath(path), parent=self)
        self._load_thread.done.connect(self._on_loaded)
        self._load_thread.start()

    def tc_load_worker(self, path: str) -> tuple | Exception:
        """Read ``path`` into ``self.ti1`` and reconstruct its parameters.

        Args:
            path (str): The chart file to read.

        Returns:
            tuple | Exception: ``(white, black, single, gray, multi, multi_bcc,
            fullspread, gamma, dark_emphasis)`` or the raised error.
        """
        filename, ext = os.path.splitext(path)
        try:
            if ext.lower() in (".icc", ".icm"):
                profile = ICCProfile(path)
                ti1 = CGATS(
                    ti3_to_ti1(
                        profile.tags.get("CIED", "") or profile.tags.get("targ", "")
                    )
                )
                ti1.filename = filename + ".ti1"
            elif ext.lower() == ".ti3":
                with open(path, "rb") as handle:
                    ti1 = CGATS(ti3_to_ti1(handle.read()))
                ti1.filename = filename + ".ti1"
            else:
                ti1 = CGATS(path)
                ti1.filename = path
            ti1.fix_device_values_scaling()
            try:
                ti1_1 = verify_cgats(ti1, ("RGB_R", "RGB_B", "RGB_G"))
            except CGATSError as exception:
                msg = {
                    CGATSKeyError: lang.getstr(
                        "error.testchart.missing_fields",
                        (path, "RGB_R, RGB_G, RGB_B"),
                    )
                }.get(
                    exception.__class__,
                    lang.getstr("error.testchart.invalid", path)
                    + "\n"
                    + lang.getstr(str(exception)),
                )
                return Error(msg)
            try:
                verify_cgats(ti1, ("XYZ_X", "XYZ_Y", "XYZ_Z"))
            except CGATSKeyError:
                data = ti1_1.queryv1("DATA")
                data.parent.DATA_FORMAT.add_data(("XYZ_X", "XYZ_Y", "XYZ_Z"))
                for sample in data.values():
                    xyz = argyll_rgb2xyz.rgb2xyz(
                        *[sample["RGB_" + channel] / 100.0 for channel in "RGB"]
                    )
                    for i, component in enumerate("XYZ"):
                        sample["XYZ_" + component] = xyz[i] * 100
            else:
                if ext.lower() not in (".ti1", ".ti2") and ti1_1:
                    ti1_1.add_keyword("ACCURATE_EXPECTED_VALUES", "true")
            ti1.root.setmodified(False)
            self.ti1 = ti1
        except Exception as exception:  # noqa: BLE001
            return Error(
                "{}\n\n{}".format(lang.getstr("error.testchart.read", path), exception)
            )
        return self._reconstruct_params()

    def _reconstruct_params(self) -> tuple:
        """Derive control values from the loaded chart's keywords.

        Charts carrying targen keywords restore exactly; keyword-less charts fall
        back to counting white/black patches (full parity for the latter is a
        later stage).

        Returns:
            tuple: ``(white, black, single, gray, multi, multi_bcc, fullspread,
            gamma, dark_emphasis)``.
        """
        ti1 = self.ti1
        white = ti1.queryv1("WHITE_COLOR_PATCHES")
        black = ti1.queryv1("BLACK_COLOR_PATCHES")
        single = ti1.queryv1("SINGLE_DIM_STEPS")
        gray = ti1.queryv1("COMP_GREY_STEPS")
        multi_bcc = ti1.queryv1("MULTI_DIM_BCC_STEPS") or 0
        multi = ti1.queryv1("MULTI_DIM_STEPS") or multi_bcc
        gamma = ti1.queryv1("EXTRA_DEV_POW") or 1.0
        dark_emphasis = ((ti1.queryv1("DARK_REGION_EMPHASIS") or 1.0) - 1.0) / 3.0
        if None in (white, single, gray, multi):
            # Keyword-less chart: count only the unambiguous white/black patches.
            white = len(ti1[0].queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}))
            black = len(ti1[0].queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0}))
            single = single or 0
            gray = gray or 0
            multi = multi or 0
        return white, black, single, gray, multi, multi_bcc, None, gamma, dark_emphasis

    def _on_loaded(self, result: object) -> None:
        """Apply a loaded chart's parameters and display it (GUI thread).

        Args:
            result (object): The parameter tuple or an ``Exception``.
        """
        self._load_thread = None
        if isinstance(result, Exception):
            self.statusBar().clearMessage()
            message_box.critical(self, self.windowTitle(), str(result))
            return
        (white, black, single, gray, multi, multi_bcc, _fs, gamma, dark) = result
        algo = None
        for keyword, code in FULLSPREAD_KEYWORD_TO_ALGO.items():
            value = self.ti1.queryv1(keyword)
            if value is not None and value > 0:
                algo = code
                break
        if white is not None:
            setcfg("tc_white_patches", white)
        if black is not None:
            setcfg("tc_black_patches", black)
        if single is not None:
            setcfg("tc_single_channel_patches", single)
        if gray is not None:
            setcfg("tc_gray_patches", gray)
        if multi is not None:
            setcfg("tc_multi_steps", multi)
        setcfg("tc_multi_bcc_steps", multi_bcc)
        setcfg(
            "tc_fullspread_patches",
            self.ti1.queryv1("NUMBER_OF_SETS")
            - self.tc_get_total_patches(
                white, black, single, gray, multi, multi_bcc, 0
            ),
        )
        if gamma is not None:
            setcfg("tc_gamma", gamma)
        if dark is not None:
            setcfg("tc_dark_emphasis", dark)
        if algo is not None:
            setcfg("tc_algo", algo)
        self.writecfg()
        self.tc_update_controls()
        self.setWindowTitle(
            f"{lang.getstr('testchart.edit').rstrip('.')}: "
            f"{os.path.basename(self.ti1.filename)}"
        )
        self._populate_grid()
        self.tc_check()

    # -- adding patches ----------------------------------------------------

    def _selected_or_last_row(self) -> int:
        """Return the last selected grid row, or the final row when none is.

        Returns:
            int: The row after which new patches are inserted.
        """
        rows = sorted(
            index.row() for index in self.grid.selectionModel().selectedRows()
        )
        return rows[-1] if rows else self.grid.rowCount() - 1

    def _select_row(self, row: int) -> None:
        """Select ``row`` in the grid (clamped to the valid range).

        Args:
            row (int): The row index to select.
        """
        row = max(0, min(row, self.grid.rowCount() - 1))
        if self.grid.rowCount():
            self.grid.clearSelection()
            self.grid.selectRow(row)

    def tc_add_data(self, row: int, newdata: list[dict]) -> None:
        """Insert ``newdata`` samples into the chart after ``row``.

        Args:
            row (int): The row after which to insert (``-1`` for the top).
            newdata (list[dict]): The samples to add; each maps CGATS field
                names (``RGB_R`` etc.) to values.
        """
        if self.ti1 is None or not newdata:
            return
        data = self.ti1.queryv1("DATA")
        data_format = self.ti1.queryv1("DATA_FORMAT")
        data.moveby1(row + 1, len(newdata))
        for offset, sample in enumerate(newdata):
            dataset = CGATS()
            for label in data_format.values():
                label = label.decode("utf-8")
                dataset[label] = sample.get(label, 0.0)
            dataset.key = row + 1 + offset
            dataset.parent = data
            dataset.root = data.root
            dataset.type = b"SAMPLE"
            data[dataset.key] = dataset
        self.ti1.setmodified(True)
        self._populate_grid()
        self._select_row(row + len(newdata))
        self.tc_check()

    def tc_add_saturation_sweeps(self, color: str | None) -> None:
        """Add a saturation sweep towards ``color`` (or the custom RGB target).

        Args:
            color (str | None): One of ``R``/``G``/``B``/``C``/``M``/``Y``, or
                ``None`` for the custom RGB spinners.
        """
        if self.ti1 is None:
            return
        try:
            profile = ICCProfile(getcfg("tc_precond_profile"))
        except (OSError, ICCProfileInvalidError) as exception:
            message_box.critical(self, self.windowTitle(), str(exception))
            return
        rgb_space = profile.get_rgb_space()
        if not rgb_space:
            message_box.critical(
                self,
                self.windowTitle(),
                lang.getstr(
                    "profile.required_tags_missing",
                    lang.getstr("profile.type.shaper_matrix"),
                ),
            )
            return
        if color is None:
            r, g, b = (
                spin.value() / 100.0
                for spin in self.saturation_sweeps_custom_ctrls.values()
            )
        else:
            r, g, b = SATURATION_SWEEP_RGB[color]
        maxv = self.saturation_sweeps_intctrl.value()
        row = self._selected_or_last_row()
        newdata = []
        for i in range(maxv):
            rgb, xyy = colormath.RGBsaturation(r, g, b, 1.0 / (maxv - 1) * i, rgb_space)
            x, y, z = colormath.xyY2XYZ(*xyy)
            newdata.append(
                {
                    "SAMPLE_ID": row + 2,
                    "RGB_R": round(rgb[0] * 100, 4),
                    "RGB_G": round(rgb[1] * 100, 4),
                    "RGB_B": round(rgb[2] * 100, 4),
                    "XYZ_X": x * 100,
                    "XYZ_Y": y * 100,
                    "XYZ_Z": z * 100,
                }
            )
        self.tc_add_data(row, newdata)

    def tc_drop_ti3_handler(self, path: str) -> None:
        """Handle a reference/image file dropped onto the editor.

        Args:
            path (str): The dropped file path.
        """
        if self.ti1 is None:
            Application.instance().beep()
        elif getcfg("tc_precond_profile"):
            self.tc_add_ti3_handler(path)
        else:
            message_box.critical(
                self, self.windowTitle(), lang.getstr("tc.precond.notset")
            )

    def tc_add_ti3_handler(self, chart: str | None = None) -> None:
        """Add reference / image patches, prompting for a file when needed.

        Args:
            chart (str | None): A file path to import, or ``None`` to prompt.
        """
        if self._add_thread is not None and self._add_thread.isRunning():
            return
        try:
            profile = ICCProfile(getcfg("tc_precond_profile"))
        except (OSError, ICCProfileInvalidError) as exception:
            message_box.critical(self, self.windowTitle(), str(exception))
            return
        if not chart:
            default_dir, default_file = get_verified_path("testchart.reference")
            chart, _selected = file_dialog.get_open_file_name(
                self,
                lang.getstr("testchart_or_reference"),
                os.path.join(default_dir, default_file),
                lang.getstr("filetype.ti1_ti3_txt")
                + " (*.cgats *.cie *.gam *.icc *.icm *.jpg *.jpeg *.png *.ti1 "
                "*.ti2 *.ti3 *.tif *.tiff *.txt)",
            )
            if not chart:
                return
            setcfg("testchart.reference", chart)
        image = None
        ext = os.path.splitext(chart)[1].lower()
        if ext in IMAGE_SUFFIXES:
            image = QImage(chart)
            if image.isNull():
                message_box.critical(
                    self,
                    self.windowTitle(),
                    lang.getstr("error.file_type_unsupported"),
                )
                return
        elif ext in (".icc", ".icm"):
            try:
                chart = self._named_color_chart(chart)
            except Exception as exception:  # noqa: BLE001
                message_box.critical(self, self.windowTitle(), str(exception))
                return
        self._progress = self._make_progress(lang.getstr("testchart.add_ti3_patches"))
        self.add_ti3_btn.setEnabled(False)
        self._add_thread = _AddPatchesThread(
            self, chart, image, False, profile, parent=self
        )
        self._add_thread.done.connect(lambda result: self._on_added(result, profile))
        self._add_thread.start()

    def _named_color_chart(self, path: str) -> bytes:
        """Build GAMUT chart lines from a Named-Color ICC profile.

        Args:
            path (str): The ``.icc``/``.icm`` Named-Color profile.

        Returns:
            bytes: The CGATS text describing the profile's colours.

        Raises:
            Error: If the profile is not a usable Named-Color profile.
        """
        nclprof = ICCProfile(path)
        if (
            nclprof.profileClass != b"nmcl"
            or "ncl2" not in nclprof.tags
            or not isinstance(nclprof.tags.ncl2, NamedColor2Type)
            or nclprof.connectionColorSpace not in (b"Lab", b"XYZ")
        ):
            raise Error(lang.getstr("profile.only_named_color"))
        if nclprof.connectionColorSpace == b"Lab":
            data_format = "LAB_L LAB_A LAB_B"
        else:
            data_format = " XYZ_X XYZ_Y XYZ_Z"
        lines = [
            "GAMUT  ",
            "BEGIN_DATA_FORMAT",
            data_format,
            "END_DATA_FORMAT",
            "BEGIN_DATA",
            "END_DATA",
        ]
        if "wtpt" in nclprof.tags:
            lines.insert(1, 'KEYWORD "APPROX_WHITE_POINT"')
            lines.insert(
                2,
                'APPROX_WHITE_POINT "{:.4f} {:.4f} {:.4f}"'.format(
                    *(v * 100 for v in nclprof.tags.wtpt.ir.values())
                ),
            )
        for key in nclprof.tags.ncl2:
            value = nclprof.tags.ncl2[key]
            lines.insert(-1, "{:.4f} {:.4f} {:.4f}".format(*value.pcs.values()))
        return "\n".join(lines).encode("utf-8")

    def tc_add_ti3(
        self,
        chart: object,
        image: QImage | None,
        use_gamut: bool,
        profile: ICCProfile,
    ) -> CGATS | Exception:
        """Turn a reference / image into a looked-up chart (worker thread).

        Args:
            chart (object): A file path or the CGATS lines to import.
            image (QImage | None): The loaded image when importing pixels.
            use_gamut (bool): Whether to run the image through ``tiffgamut``.
            profile (ICCProfile): The preconditioning profile.

        Returns:
            CGATS | Exception: A chart carrying RGB and CIE values, or an error.
        """
        intent = "r" if getcfg("tc_add_ti3_relative") else "a"
        if image is not None:
            chart = self._image_to_chart(chart, image, use_gamut, profile, intent)
            if isinstance(chart, Exception):
                return chart
        try:
            chart = CGATS(chart)
            if not chart.queryv1("DATA_FORMAT"):
                raise CGATSError(
                    lang.getstr(
                        "error.testchart.missing_fields",
                        (chart.filename, "DATA_FORMAT"),
                    )
                )
        except (OSError, CGATSError) as exception:
            return exception
        finally:
            path = chart.filename if isinstance(chart, CGATS) else None
            if path and os.path.dirname(path) == self.worker.tempdir:
                self.worker.wrapup(False)
        if image is not None:
            return self._average_image_chart(chart, use_gamut, profile, intent)
        chart.fix_device_values_scaling()
        return chart

    def _average_image_chart(
        self, chart: CGATS, use_gamut: bool, profile: ICCProfile, intent: str
    ) -> CGATS | Exception:
        """Reduce an image's pixels to a compact weighted GAMUT chart.

        Ports the ``if img:`` block of ``wx_testchart_editor.tc_add_ti3``: bins
        the (looked-up) Lab points on a coarse grid, weights each bin by its
        lightness (biased by the dark-emphasis setting) and averages the bins
        that clear the weight threshold into representative reference points.

        Args:
            chart (CGATS): The image chart (RGB pixels, or gamut Lab points).
            use_gamut (bool): Whether the image came through ``tiffgamut``.
            profile (ICCProfile): The preconditioning profile.
            intent (str): The rendering intent (``"r"`` or ``"a"``).

        Returns:
            CGATS | Exception: The averaged GAMUT chart, or an error.
        """
        if use_gamut:
            threshold = 2
        else:
            threshold = 4
            try:
                _void, ti3, _void2 = self.worker.chart_lookup(
                    chart,
                    profile,
                    intent=intent,
                    white_patches=False,
                    raise_exceptions=True,
                )
            except Exception as exception:  # noqa: BLE001
                return exception
            if not ti3:
                return Error(lang.getstr("error.generic", (-1, lang.getstr("unknown"))))
            chart = ti3
        colorsets: dict[tuple, list[tuple]] = {}
        weights: dict[tuple, float] = {}
        demph = getcfg("tc_dark_emphasis")
        for sample in chart.queryv1("DATA").values():
            rgb = (
                None
                if use_gamut
                else (sample["RGB_R"], sample["RGB_G"], sample["RGB_B"])
            )
            lab = (sample["LAB_L"], sample["LAB_A"], sample["LAB_B"])
            key = round(lab[0] / 10), round(lab[1] / 15), round(lab[2] / 15)
            if key not in colorsets:
                weights[key] = 0
                colorsets[key] = []
            weights[key] += lab[0] / 50 + (-demph if lab[0] >= 50 else demph)
            colorsets[key].append(lab if rgb is None else lab + rgb)
        data_format = "LAB_L LAB_A LAB_B"
        if not use_gamut:
            data_format += " RGB_R RGB_G RGB_B"
        lines = [
            "GAMUT  ",
            "BEGIN_DATA_FORMAT",
            data_format,
            "END_DATA_FORMAT",
            "BEGIN_DATA",
            "END_DATA",
        ]
        weighted = any(weight >= threshold for weight in weights.values())
        for key, colors in colorsets.items():
            if weighted and weights[key] < threshold:
                continue
            count = len(colors)
            averaged = [sum(values) / count for values in zip(*colors)]
            lines.insert(-1, "{:.4f} {:.4f} {:.4f}".format(*averaged[:3]))
            if not use_gamut:
                lines[-2] += " {:.4f} {:.4f} {:.4f}".format(*averaged[3:6])
        self.worker.wrapup(False)
        return CGATS("\n".join(lines).encode("utf-8"))

    def _image_to_chart(
        self,
        chart: str,
        image: QImage,
        use_gamut: bool,
        profile: ICCProfile,
        intent: str,
    ) -> object:
        """Sample an image into a GAMUT chart (worker thread).

        Ports ``wx_testchart_editor.tc_add_ti3``'s image branch: the pixels are
        converted through the embedded / preconditioning profile with ``cctiff``
        (or ``tiffgamut``), then averaged into a compact set of Lab (and RGB)
        reference points weighted by lightness.

        Args:
            chart (str): The source image path.
            image (QImage): The loaded image.
            use_gamut (bool): Whether to use ``tiffgamut`` instead of ``cctiff``.
            profile (ICCProfile): The preconditioning profile.
            intent (str): The rendering intent (``"r"`` or ``"a"``).

        Returns:
            object: A CGATS text/CGATS ready for lookup, or an ``Exception``.
        """
        cwd = self.worker.create_tempdir()
        if isinstance(cwd, Exception):
            return cwd
        size = 70.0
        scale = math.sqrt((image.width() * image.height()) / (size * size))
        w = round(image.width() / scale)
        h = round(image.height() / scale)
        ext = os.path.splitext(chart)[1].lower()
        if ext in (".tif", ".tiff") or (
            self.worker.argyll_version >= [1, 4] and ext in (".jpeg", ".jpg")
        ):
            imgpath = chart
        else:
            imgpath = os.path.join(cwd, "image.tif")
            if not image.save(imgpath, "TIFF"):
                return Error(lang.getstr("error.file_type_unsupported"))
        outpath = os.path.join(cwd, "imageout.tif")
        gam = os.path.join(cwd, "image.gam")
        result = self._run_image_conversion(
            use_gamut, imgpath, imgpath == chart, outpath, gam, intent
        )
        if isinstance(result, Exception):
            self.worker.wrapup(False)
            return result
        if use_gamut:
            return gam
        converted = outpath if result == "RGB" else imgpath
        image = QImage(converted)
        if image.isNull():
            self.worker.wrapup(False)
            return Error(lang.getstr("error.file_type_unsupported"))
        if image.width() != w or image.height() != h:
            image = image.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        return self._image_pixels_to_ti1(image)

    def _run_image_conversion(
        self,
        use_gamut: bool,
        imgpath: str,
        is_source: bool,
        outpath: str,
        gam: str,
        intent: str,
    ) -> str | Exception:
        """Run ``cctiff``/``tiffgamut`` over ``imgpath`` (worker thread).

        Tries the image's embedded profile first, then falls back to the
        preconditioning profile (matching the wx retry).

        Args:
            use_gamut (bool): Whether to use ``tiffgamut`` instead of ``cctiff``.
            imgpath (str): The (TIFF/JPEG) image to convert.
            is_source (bool): Whether ``imgpath`` is the original source file.
            outpath (str): The ``cctiff`` output TIFF path.
            gam (str): The ``tiffgamut`` output gamut path.
            intent (str): The rendering intent (``"r"`` or ``"a"``).

        Returns:
            str | Exception: The last reported ``cctiff`` output space (``""``
            for ``tiffgamut``), or an ``Exception`` on failure.
        """
        cmdname = "tiffgamut" if use_gamut else "cctiff"
        cmd = get_argyll_util(cmdname)
        if not cmd:
            return Error(lang.getstr("argyll.util.not_found", cmdname))
        ppath = getcfg("tc_precond_profile")
        result: object = False
        for attempt in range(2 if ppath else 1):
            args = self._image_conversion_args(
                use_gamut, imgpath, is_source, outpath, gam, ppath, intent, attempt
            )
            result = self.worker.exec_cmd(
                cmd, ["-v", *args], capture_output=True, skip_scripts=True
            )
            if not result:
                errors = "".join(self.worker.errors)
                if (
                    "Error - Can't open profile in file" in errors
                    or "Error - Can't read profile" in errors
                ):
                    continue
            break
        if isinstance(result, Exception):
            return result
        if not result:
            return Error("\n".join(self.worker.errors or self.worker.output))
        output_space = ""
        for line in self.worker.output:
            if line.startswith("Output space ="):
                output_space = line.split("=")[1].strip()
        return output_space

    def _image_conversion_args(
        self,
        use_gamut: bool,
        imgpath: str,
        is_source: bool,
        outpath: str,
        gam: str,
        ppath: str,
        intent: str,
        attempt: int,
    ) -> list[str]:
        """Build the ``cctiff``/``tiffgamut`` argument list for one attempt.

        Args:
            use_gamut (bool): Whether to use ``tiffgamut`` instead of ``cctiff``.
            imgpath (str): The image to convert.
            is_source (bool): Whether ``imgpath`` is the original source file.
            outpath (str): The ``cctiff`` output TIFF path.
            gam (str): The ``tiffgamut`` output gamut path.
            ppath (str): The preconditioning profile path.
            intent (str): The rendering intent (``"r"`` or ``"a"``).
            attempt (int): ``0`` tries the embedded profile, ``1`` falls back.

        Returns:
            list[str]: The argument list (without the leading ``-v``).
        """
        if use_gamut:
            args = [f"-d{10 if is_source else 1}", "-O", gam]
        else:
            args = ["-a"]
            if self.worker.argyll_version >= [1, 4]:
                args.append("-fT")
            elif self.worker.argyll_version >= [1, 1]:
                args.append("-t1")
            else:
                args.append("-e1")
        args.append(f"-i{intent}")
        if attempt == 0:
            args.append(imgpath)
            if not use_gamut:
                args.append(f"-i{intent}")
                args.append(ppath)
        else:
            args.append(ppath)
        args.append(imgpath)
        if not use_gamut:
            args.append(outpath)
        return args

    @staticmethod
    def _image_pixels_to_ti1(image: QImage) -> bytes:
        """Return a device-RGB TI1 chart of every pixel in ``image``.

        Args:
            image (QImage): The (downscaled) converted image.

        Returns:
            bytes: The CGATS TI1 text with one ``RGB_R RGB_G RGB_B`` row per pixel.
        """
        lines = [
            "TI1    ",
            "BEGIN_DATA_FORMAT",
            "RGB_R RGB_G RGB_B",
            "END_DATA_FORMAT",
            "BEGIN_DATA",
            "END_DATA",
        ]
        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixelColor(x, y)
                lines.insert(
                    -1,
                    f"{pixel.red() / 2.55:.4f} {pixel.green() / 2.55:.4f} "
                    f"{pixel.blue() / 2.55:.4f}",
                )
        return "\n".join(lines).encode("utf-8")

    def _on_added(self, result: object, profile: ICCProfile) -> None:
        """Look up the imported chart and add its patches (GUI thread).

        Args:
            result (object): The chart returned by the worker, or an ``Exception``.
            profile (ICCProfile): The preconditioning profile.
        """
        self._add_thread = None
        self._close_progress()
        self.add_ti3_btn.setEnabled(
            self.ti1 is not None and bool(getcfg("tc_precond_profile"))
        )
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
            return
        try:
            newdata = self._reference_to_patches(result, profile)
        except Exception as exception:  # noqa: BLE001
            message_box.critical(self, self.windowTitle(), str(exception))
            return
        if not newdata:
            return
        row = self._selected_or_last_row()
        for offset, entry in enumerate(newdata):
            entry["SAMPLE_ID"] = row + 2 + offset
        self.tc_add_data(row, newdata)

    def _reference_to_patches(self, chart: CGATS, profile: ICCProfile) -> list[dict]:
        """Look reference CIE values up through the profile into patch dicts.

        Ports ``wx_testchart_editor.tc_add_ti3_consumer``.

        Args:
            chart (CGATS): The reference chart returned by :meth:`tc_add_ti3`.
            profile (ICCProfile): The preconditioning profile.

        Returns:
            list[dict]: Patches mapping ``RGB_*``/``XYZ_*`` field names to values.
        """
        data_format = list(chart.queryv1("DATA_FORMAT").values())
        intent = "r" if getcfg("tc_add_ti3_relative") else "a"
        is_rgb_gamut = (
            chart[0].type.strip() == b"GAMUT"
            and b"RGB_R" in data_format
            and b"RGB_G" in data_format
            and b"RGB_B" in data_format
        )
        if not is_rgb_gamut:
            as_ti3 = all(
                label in data_format for label in (b"LAB_L", b"LAB_A", b"LAB_B")
            ) or all(label in data_format for label in (b"XYZ_X", b"XYZ_Y", b"XYZ_Z"))
            if intent == "r":
                chart.adapt()
            ti1, ti3, _void = self.worker.chart_lookup(
                chart, profile, as_ti3, intent=intent, white_patches=False
            )
            if not ti1 or not ti3:
                return []
            chart = ti1 if as_ti3 else ti3
        dataset = chart.queryi1("DATA")
        data_format = list(dataset.queryv1("DATA_FORMAT").values())
        cie = (
            "Lab"
            if all(label in data_format for label in (b"LAB_L", b"LAB_A", b"LAB_B"))
            else "XYZ"
        )
        newdata = []
        for i in dataset.DATA:
            sample = dataset.DATA[i]
            if cie == "Lab":
                sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"] = colormath.Lab2XYZ(
                    sample["LAB_L"], sample["LAB_A"], sample["LAB_B"], scale=100
                )
            if intent == "r":
                sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"] = colormath.adapt(
                    sample["XYZ_X"],
                    sample["XYZ_Y"],
                    sample["XYZ_Z"],
                    "D50",
                    list(profile.tags.wtpt.values()),
                )
            newdata.append(
                {
                    label: round(sample[label], 4)
                    for label in ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
                }
            )
        return newdata

    # -- CSV import --------------------------------------------------------

    def csv_drop_handler(self, path: str) -> None:
        """Convert and load a dropped CSV file (replacing the chart, off-thread).

        Args:
            path (str): The dropped ``.csv`` path.
        """
        if self._csv_thread is not None and self._csv_thread.isRunning():
            return
        self._progress = self._make_progress(lang.getstr("testchart.read"))
        self._csv_thread = _CSVConvertThread(self, path, parent=self)
        self._csv_thread.done.connect(self._on_csv_converted)
        self._csv_thread.start()

    def csv_convert(self, path: str) -> CGATS:
        """Convert a CSV file to a temporary TI1 chart (worker thread).

        Accepts rows of ``RGB`` or ``RGB + XYZ`` values (with an optional leading
        index and header), auto-scaling device values above ``100`` down to a
        ``0..100`` range and synthesising missing XYZ via a simple sRGB model.

        Args:
            path (str): The CSV file to convert.

        Returns:
            CGATS: The converted chart (written to a temporary ``.ti1``).

        Raises:
            ValueError: If a row does not have 3, 4, 6 or 7 columns.
        """
        rows = []
        maxval = 100.0
        with open(path, "rb") as csvfile:
            sniffer = csv.Sniffer()
            rawcsv = csvfile.read().decode("utf-8", "replace")
            dialect = sniffer.sniff(rawcsv, delimiters=",;\t")
            has_header = sniffer.has_header(rawcsv)
        for i, row in enumerate(rawcsv.splitlines()):
            fields = next(csv.reader([row], dialect=dialect), [])
            if not fields:
                continue
            if has_header and i == 0:
                continue
            if len(fields) in (3, 6):
                fields.insert(0, i)
            if len(fields) not in (4, 7):
                raise ValueError(lang.getstr("error.testchart.invalid", path))
            values = [int(fields[0])] + [float(v) for v in fields[1:]]
            maxval = max(maxval, *values[1:])
            rows.append(values)
        if maxval > 100:
            for values in rows:
                values[1:] = [v / maxval * 100 for v in values[1:]]
        ti1 = CGATS(
            b"""CTI1
KEYWORD "COLOR_REP"
COLOR_REP "RGB"
NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 4
BEGIN_DATA
END_DATA"""
        )
        data = ti1[0].DATA
        for values in rows:
            if len(values) < 7:
                values.extend(
                    v * 100
                    for v in argyll_rgb2xyz.rgb2xyz(*(v / 100.0 for v in values[1:]))
                )
            data.add_data(values)
        tmp = self.worker.create_tempdir()
        if isinstance(tmp, Exception):
            raise tmp
        ti1.filename = os.path.join(
            tmp, os.path.splitext(os.path.basename(path))[0] + ".ti1"
        )
        ti1.write()
        return ti1

    def _on_csv_converted(self, result: object) -> None:
        """Load the converted CSV chart on the GUI thread.

        Args:
            result (object): The converted ``CGATS``, or an ``Exception``.
        """
        self._csv_thread = None
        self._close_progress()
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
            return
        self.load_file(result.filename)

    # -- save / clear ------------------------------------------------------

    def tc_save(self) -> None:
        """Save the chart to its current filename."""
        if self.ti1 is not None and self.ti1.filename:
            self.tc_save_as(self.ti1.filename)

    def tc_save_as(self, path: str | None = None) -> bool:
        """Save the chart as a ``.ti1`` file.

        Args:
            path (str | None): Target path; prompts with a dialog when ``None``.

        Returns:
            bool: ``True`` if the chart was written.
        """
        if self.ti1 is None:
            return False
        if path is None:
            default_dir = get_verified_path("last_ti1_path")[0]
            if self.ti1.filename:
                if os.path.isfile(self.ti1.filename):
                    default_dir = os.path.dirname(self.ti1.filename)
                default_file = os.path.basename(self.ti1.filename)
            else:
                default_file = os.path.basename(DEFAULTS["last_ti1_path"])
            path, _ = file_dialog.get_save_file_name(
                self,
                lang.getstr("save_as"),
                os.path.join(default_dir, default_file),
                f"{lang.getstr('filetype.ti1')} (*.ti1)",
            )
            if not path:
                return False
            if os.path.splitext(path)[1].lower() != ".ti1":
                path += ".ti1"
        if not waccess(path, os.W_OK):
            message_box.critical(
                self, self.windowTitle(), lang.getstr("error.access_denied.write", path)
            )
            return False
        setcfg("last_ti1_path", path)
        try:
            with open(path, "wb") as handle:
                handle.write(bytes(self.ti1))
        except Exception as exception:  # noqa: BLE001
            message_box.critical(
                self,
                self.windowTitle(),
                f"Error - testchart could not be saved: {exception!s}",
            )
            return False
        self.ti1.filename = path
        self.ti1.root.setmodified(False)
        self.setWindowTitle(
            f"{lang.getstr('testchart.edit').rstrip('.')}: {os.path.basename(path)}"
        )
        self.save_btn.setEnabled(False)
        if self._chart_selected_callback is not None:
            if path != getcfg(self.cfg) and self._confirm_select_chart():
                setcfg(self.cfg, path)
                self.writecfg()
            if path == getcfg(self.cfg):
                self._chart_selected_callback(path)
        return True

    def _confirm_select_chart(self) -> bool:
        """Ask whether the just-saved chart should become the active one.

        Mirrors wx's ``tc_save_as_handler`` confirm dialog, shown only when
        saving as a path different from the bound ``cfg`` key's current
        value (e.g. the Verification tab's ``measurement_report.chart``).
        """
        box = QMessageBox(self)
        box.setWindowTitle(self.windowTitle())
        box.setIcon(QMessageBox.Question)
        box.setText(lang.getstr("testchart.confirm_select"))
        ok_button = box.addButton(
            lang.getstr("testchart.select"), QMessageBox.AcceptRole
        )
        box.addButton(lang.getstr("testchart.dont_select"), QMessageBox.RejectRole)
        message_box.exec_box(box)
        return box.clickedButton() is ok_button

    def tc_clear(self) -> None:
        """Discard the current chart and reset the editor."""
        self.grid.blockSignals(True)
        self.grid.clearContents()
        self.grid.setRowCount(0)
        self.grid.blockSignals(False)
        self.ti1 = None
        self.tc_amount = 0
        self.setWindowTitle(lang.getstr("testchart.edit"))
        self.tc_update_controls()
        self.tc_check()

    # -- export ------------------------------------------------------------

    def tc_export_handler(self) -> None:
        """Prompt for a CSV destination and export the chart (off-thread)."""
        if self.ti1 is None:
            return
        if self._export_thread is not None and self._export_thread.isRunning():
            return
        default_dir = get_verified_path("last_testchart_export_path")[0]
        default_file = os.path.basename(
            os.path.splitext(
                self.ti1.filename or DEFAULTS["last_testchart_export_path"]
            )[0]
        )
        labels = {f"{label} (*.csv)": scale for label, scale in CSV_EXPORT_FORMATS}
        path, selected = file_dialog.get_save_file_name(
            self,
            lang.getstr("export"),
            os.path.join(default_dir, default_file),
            ";;".join(labels),
        )
        if not path:
            return
        if os.path.splitext(path)[1].lower() != ".csv":
            path += ".csv"
        if not waccess(path, os.W_OK):
            message_box.critical(
                self,
                self.windowTitle(),
                lang.getstr("error.access_denied.write", path),
            )
            return
        setcfg("last_testchart_export_path", path)
        self.writecfg()
        self.export_btn.setEnabled(False)
        self._progress = self._make_progress(lang.getstr("export"))
        self._export_thread = _ExportThread(
            self, path, labels.get(selected, 100), parent=self
        )
        self._export_thread.done.connect(self._on_exported)
        self._export_thread.start()

    def tc_export(self, path: str, scale: int) -> None:
        """Write the chart's device values to ``path`` as CSV.

        Args:
            path (str): Destination file.
            scale (int): Device-value scale (100 for 0..100, 255 or 1023).
        """
        data = self.ti1.queryv1("DATA")
        with open(path, "w", newline="") as handle:
            writer = csv.writer(handle)
            for index in range(self.ti1.queryv1("NUMBER_OF_SETS")):
                sample = data[index]
                rgb = [sample["RGB_R"], sample["RGB_G"], sample["RGB_B"]]
                if scale != 100:
                    # Scale carefully: round(v / 100.0 * scale), not v * (scale / 100).
                    rgb = [round(v / 100.0 * scale) for v in rgb]
                writer.writerow([index, *rgb])

    def _on_exported(self, result: object) -> None:
        """Finish a CSV export on the GUI thread.

        Args:
            result (object): ``None`` on success, or an ``Exception``.
        """
        self._export_thread = None
        self._close_progress()
        self.export_btn.setEnabled(self.ti1 is not None)
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))

    # -- 3D view -----------------------------------------------------------

    def tc_view_3d(self) -> None:
        """Generate and open the diagnostic 3D file(s) for the chart."""
        if self.ti1 is None:
            return
        if self._view_thread is not None and self._view_thread.isRunning():
            return
        filename = self.ti1.filename
        if (
            filename
            and not (self.worker.tempdir and filename.startswith(self.worker.tempdir))
            and waccess(os.path.dirname(filename) or ".", os.W_OK)
        ):
            base = os.path.splitext(filename)[0]
        else:
            base = self._prompt_3d_basepath()
            if base is None:
                return
        self.view_3d_btn.setEnabled(False)
        self._progress = self._make_progress(lang.getstr("view.3d"))
        self._view_thread = _View3DThread(self, base, parent=self)
        self._view_thread.done.connect(self._on_view_3d_done)
        self._view_thread.start()

    def _prompt_3d_basepath(self) -> str | None:
        """Prompt for a 3D output location, returning its extension-less base.

        Returns:
            str | None: The chosen path without extension, or ``None`` if cancelled.
        """
        formatext = self._view_3d_formatext()
        if (
            self.ti1 is not None
            and self.ti1.filename
            and os.path.isfile(self.ti1.filename)
        ):
            default_dir = os.path.dirname(self.ti1.filename)
            default_file = os.path.basename(self.ti1.filename)
        else:
            default_dir = get_verified_path("last_vrml_path")[0]
            default_file = os.path.basename(DEFAULTS["last_vrml_path"])
        default_file = os.path.splitext(default_file)[0] + formatext
        path, _ = file_dialog.get_save_file_name(
            self,
            lang.getstr("save_as"),
            os.path.join(default_dir, default_file),
            f"{lang.getstr('view.3d')} (*{formatext})",
        )
        if not path:
            return None
        filename, ext = os.path.splitext(path)
        if ext.lower() != formatext:
            path += formatext
        setcfg("last_vrml_path", path)
        return filename

    def _view_3d_formatext(self) -> str:
        """Return the file extension for the configured 3D format.

        Returns:
            str: ``.wrz`` / ``.wrl`` for VRML, ``.x3d`` for X3D, ``.x3d.html``
            for HTML.
        """
        view_3d_format = getcfg("3d.format")
        if view_3d_format == "VRML":
            return ".wrz" if getcfg("vrml.compress") else ".wrl"
        formatext = ".x3d"
        if view_3d_format == "HTML":
            formatext += ".html"
        return formatext

    def tc_save_3d(self, base: str) -> list[str]:
        """Write the diagnostic 3D file(s) and return their paths.

        Runs on a worker thread; overwrites any existing per-colorspace files.

        Args:
            base (str): Output path without colorspace suffix or extension.

        Returns:
            list[str]: The written file paths.
        """
        view_3d_format = getcfg("3d.format")
        formatext = self._view_3d_formatext()
        colorspaces = []
        if getcfg("tc_vrml_device"):
            colorspaces.append(getcfg("tc_vrml_device_colorspace"))
        if getcfg("tc_vrml_cie"):
            colorspaces.append(getcfg("tc_vrml_cie_colorspace"))
        paths = []
        for colorspace in colorspaces:
            path = f"{base} {colorspace}{formatext}"
            self.ti1[0].export_3d(
                path,
                colorspace,
                rgb_black_offset=getcfg("tc_vrml_black_offset"),
                normalize_rgb_white=bool(getcfg("tc_vrml_use_D50")),
                compress=formatext == ".wrz",
                file_format=view_3d_format,
            )
            paths.append(path)
        return paths

    def _on_view_3d_done(self, result: object) -> None:
        """Open the generated 3D file(s), or report an error (GUI thread).

        Args:
            result (object): The list of written paths, or an ``Exception``.
        """
        self._view_thread = None
        self._close_progress()
        self.tc_vrml_update_enabled()
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
            return
        for path in result:
            launch_file(path)

    # -- progress helpers --------------------------------------------------

    def _make_progress(self, message: str) -> QProgressDialog:
        """Return a shown, indeterminate, un-cancellable modal progress dialog.

        Args:
            message (str): The label text.

        Returns:
            QProgressDialog: The dialog.
        """
        progress = QProgressDialog(message, "", 0, 0, self)
        progress.setWindowTitle(self.windowTitle())
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        return progress

    def _close_progress(self) -> None:
        """Close and drop the active progress dialog, if any."""
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    # -- scripting ---------------------------------------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's file-opening commands.
        """
        return [
            *self.get_common_commands(),
            "testchart-editor [filename]",
            "load <filename>",
        ]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"``, ``"fail"`` or ``"invalid"``.
        """
        return self.open_files_command(data, "testchart-editor")

    # -- lifecycle ---------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist configuration before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.tc_save_cfg()
        self.writecfg()
        super().closeEvent(event)


def main() -> int:
    """Entry point for the Qt testchart editor.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("testchart-editor")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = TestchartEditorWindow()
    app.top_window = window
    window.show()
    window.listen()

    charts = [a for a in sys.argv[1:] if os.path.isfile(a)]
    if charts:
        window.load_file(charts[0])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
