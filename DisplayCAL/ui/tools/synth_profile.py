"""Synthetic ICC profile creator — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_synth_icc_frame` (the ``synthprofile``
tool). It builds a synthetic ICC profile from user-entered colorimetry: RGB or
grayscale primaries, white/black point, luminance, and a transfer function
(plain gamma, BT.1886, DICOM, L*, Rec. 709/1886, SMPTE 240M, SMPTE 2084/PQ
with optional roll-off, HLG, sRGB). Colorimetry can be seeded from a dropped
ICC profile or ``.ti3`` measurement file, or from a built-in RGB-space preset.

Notable differences versus the wx version:

* Controls are built directly with Qt layouts instead of the ``synthicc.xrc``
  resource; the HDR roll-off controls (SMPTE 2084 / HLG) are inlined here rather
  than inherited from the large ``LUT3DMixin``.
* The expensive HDR cLUT generation (SMPTE 2084 roll-off / HLG) runs on a small
  :class:`QThread` (:class:`_CreateThread`) instead of the heavyweight
  :class:`DisplayCAL.worker.Worker` progress dialog; non-HDR profiles are built
  synchronously, as in the wx version.
* The binding-agnostic profile-building backend (:meth:`SynthICCWindow.create_profile`)
  is carried over essentially verbatim — it only touches
  :mod:`DisplayCAL.icc_profile`, :mod:`DisplayCAL.colormath`, the worker and
  config, none of which are wx-specific.
"""

from __future__ import annotations

import math
import os
import sys
from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
from DisplayCAL.argyll_cgats import extract_device_gray_primaries
from DisplayCAL.cgats import CGATS, CGATSInvalidError
from DisplayCAL.config import (
    ENC,
    PROFILE_EXT,
    get_verified_path,
    getcfg,
    setcfg,
)
from DisplayCAL.debughelpers import Error
from DisplayCAL.icc_profile import (
    CIIS,
    PROFILE_CLASS,
    TECH,
    CurveType,
    ICCProfile,
    ICCProfileInvalidError,
    SignatureType,
    Text,
    XYZType,
    create_synthetic_hdr_clut_profile,
    s15f16_is_equal,
)
from DisplayCAL.log import LOG
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_dict import dict_sort
from DisplayCAL.util_io import Files
from DisplayCAL.util_os import waccess
from DisplayCAL.worker import (
    FilteredStream,
    LineBufferedStream,
    Worker,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

#: File suffixes accepted for opening / drag-and-drop.
PROFILE_SUFFIXES = (".icc", ".icm", ".ti3")

#: Transfer-function choices, in control order. Each entry is a localization
#: key; the index is what the logic below switches on (mirrors the wx XRC).
TRC_ITEMS = (
    "custom",  # 0 - plain gamma
    "trc.dicom",  # 1
    "trc.hlg",  # 2
    "trc.lstar",  # 3
    "trc.rec709",  # 4
    "trc.rec1886",  # 5
    "trc.smpte240m",  # 6
    "trc.smpte2084.hardclip",  # 7
    "trc.smpte2084.rolloffclip",  # 8
    "trc.srgb",  # 9
)


def get_mapping(mapping: Iterable, keys: Iterable) -> list:
    """Return ``(key, localized-label)`` pairs for ``keys``, sorted by key.

    Args:
        mapping (Iterable[tuple]): ``(key, raw_label)`` pairs to filter.
        keys (Iterable): The subset of keys to keep.

    Returns:
        list[tuple]: ``(key, localized label)`` pairs sorted by key.
    """
    return sorted(
        [
            (k, lang.getstr(v.lower().replace(" ", "_")))
            for k, v in [item for item in mapping if item[0] in keys]
        ],
        key=lambda item: item[0],
    )


class _CreateThread(QThread):
    """Run :meth:`SynthICCWindow.create_profile` off the GUI thread.

    Used only for the expensive HDR cases (SMPTE 2084 roll-off / HLG), which
    build a synthetic cLUT through Argyll. Simpler profiles are created inline.

    Args:
        window (SynthICCWindow): The owning window (provides ``create_profile``).
        args (tuple): Positional arguments for ``create_profile``.
        kwargs (dict): Keyword arguments for ``create_profile``.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with ``None`` on success or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self,
        window: SynthICCWindow,
        args: tuple,
        kwargs: dict,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._window.create_profile(*self._args, **self._kwargs)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _GuardContext:
    """Context manager that suppresses re-entrant control-change handlers.

    While active, :attr:`SynthICCWindow._updating` is ``True``, so the slots
    connected to spin boxes / combos return early instead of recursing when the
    code sets control values programmatically (Qt, unlike wx ``FloatSpin``,
    emits change signals from ``setValue``).

    Args:
        window (SynthICCWindow): The window whose update guard to toggle.
    """

    def __init__(self, window: SynthICCWindow) -> None:
        self._window = window

    def __enter__(self) -> None:
        self._window._updating = True

    def __exit__(self, *exc) -> None:
        self._window._updating = False


class SynthICCWindow(BaseWindow):
    """Window for creating synthetic ICC profiles from colorimetry."""

    def __init__(self) -> None:
        super().__init__(
            name="synthiccframe",
            title=lang.getstr("synthicc.create"),
            icon_name=f"{APPNAME}-synthprofile".lower(),
        )
        self.worker = Worker()
        self.cat = "Bradford"
        self._updating = False
        self._thread: _CreateThread | None = None

        self.trc_gamma_types_ab = {0: "g", 1: "G"}
        self.trc_gamma_types_ba = {"g": 0, "G": 1}

        self._build_ui()

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(PROFILE_SUFFIXES, self.drop_handler),
            parent=self,
        )
        self.droptarget.install_on(self)
        self.init_menubar()

        self.update_controls()
        self.update_trc_controls()
        self.restore_position()

    # -- guard helper ------------------------------------------------------

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
        """Build the scrollable control panel and bottom button bar."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        outer.addLayout(self._build_preset_row())
        outer.addWidget(self._build_color_grid())
        outer.addLayout(self._build_luminance_row())
        outer.addLayout(self._build_trc_row())
        outer.addWidget(self._build_hdr_group())
        outer.addLayout(self._build_black_offset_row())
        outer.addLayout(self._build_class_row())
        outer.addWidget(self._build_metadata_group())
        outer.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._build_button_bar())
        self.setCentralWidget(central)
        self.resize(900, 760)

    def _build_preset_row(self) -> QHBoxLayout:
        """Build the preset chooser and RGB/grayscale colorspace selector.

        Returns:
            QHBoxLayout: The assembled top control row.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.getstr("preset")))
        self.preset_ctrl = QComboBox()
        self.preset_ctrl.addItems(["", *sorted(colormath.rgb_spaces.keys())])
        self.preset_ctrl.activated.connect(self._on_preset)
        row.addWidget(self.preset_ctrl)
        row.addSpacing(16)

        self.colorspace_rgb_ctrl = QRadioButton("RGB")
        self.colorspace_rgb_ctrl.setChecked(True)
        self.colorspace_gray_ctrl = QRadioButton(lang.getstr("grayscale"))
        self._colorspace_group = QButtonGroup(self)
        self._colorspace_group.addButton(self.colorspace_rgb_ctrl)
        self._colorspace_group.addButton(self.colorspace_gray_ctrl)
        self.colorspace_rgb_ctrl.toggled.connect(self._on_colorspace)
        row.addWidget(self.colorspace_rgb_ctrl)
        row.addWidget(self.colorspace_gray_ctrl)
        row.addStretch(1)
        return row

    def _build_color_grid(self) -> QWidget:
        """Build the white/red/green/blue/black by XYZxy spin-box grid.

        Returns:
            QWidget: The grid container widget.
        """
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        headers = {"X": "X", "Y": "Y", "Z": "Z", "x": "x", "y": "y"}
        for col, comp in enumerate("XYZxy"):
            label = QLabel(headers[comp])
            setattr(self, f"label_{comp}", label)
            grid.addWidget(label, 0, col + 1)

        # XYZ spin ranges/digits and xy ranges/digits from the wx XRC.
        rows = (
            ("white", "whitepoint"),
            ("red", "red"),
            ("green", "green"),
            ("blue", "blue"),
        )
        for r, (color, label_key) in enumerate(rows, start=1):
            label = QLabel(lang.getstr(label_key))
            setattr(self, f"label_{color}", label)
            grid.addWidget(label, r, 0)
            self._add_color_spins(grid, color, r)

        # Black row: checkbox label, special Y range/increment.
        self.black_point_cb = QCheckBox(lang.getstr("black_point"))
        self.black_point_cb.toggled.connect(self._on_black_point_enable)
        black_row = len(rows) + 1
        grid.addWidget(self.black_point_cb, black_row, 0)
        self._add_color_spins(grid, "black", black_row, black=True)

        # Chromatic-adaptation button under the grid.
        self.chromatic_adaptation_btn = QPushButton(lang.getstr("chromatic_adaptation"))
        self.chromatic_adaptation_btn.setEnabled(False)
        self.chromatic_adaptation_btn.clicked.connect(self._on_chromatic_adaptation)
        grid.addWidget(self.chromatic_adaptation_btn, black_row + 1, 1, 1, 3)
        return widget

    def _add_color_spins(
        self, grid: QGridLayout, color: str, row: int, black: bool = False
    ) -> None:
        """Add the XYZ + xy spin boxes for one color to ``grid``.

        Args:
            grid (QGridLayout): The grid to populate.
            color (str): Color name (``white``/``red``/``green``/``blue``/``black``).
            row (int): Grid row index.
            black (bool): Whether this is the black row (different Y range).
        """
        for col, comp in enumerate("XYZ"):
            if comp == "Y" and color in ("white", "black"):
                spin = self._spin(0.0, 100.0, 0.0001, 4)
            else:
                spin = self._spin(-99.0, 999.0, 0.0001, 4)
            setattr(self, f"{color}_{comp}", spin)
            handler = "XYZ"
            spin.valueChanged.connect(
                lambda _v, c=color, h=handler: self._on_color_changed(c, h)
            )
            grid.addWidget(spin, row, col + 1)
        for col, comp in enumerate("xy", start=3):
            spin = self._spin(-1.0, 1.0, 0.00001, 5)
            setattr(self, f"{color}_{comp}", spin)
            spin.valueChanged.connect(
                lambda _v, c=color: self._on_color_changed(c, "xy")
            )
            grid.addWidget(spin, row, col + 1)

    def _build_luminance_row(self) -> QHBoxLayout:
        """Build the white/black luminance spin boxes.

        Returns:
            QHBoxLayout: The luminance control row.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.getstr("calibration.luminance")))
        self.luminance_ctrl = self._spin(10.0, 10000.0, 0.1, 2, width=135)
        self.luminance_ctrl.valueChanged.connect(self._on_luminance)
        row.addWidget(self.luminance_ctrl)
        row.addWidget(QLabel("cd/m²"))
        row.addSpacing(16)
        self.label_black_luminance = QLabel(lang.getstr("calibration.black_luminance"))
        row.addWidget(self.label_black_luminance)
        self.black_luminance_ctrl = self._spin(0.0, 10000.0, 0.000001, 6, width=145)
        self.black_luminance_ctrl.valueChanged.connect(self._on_black_luminance)
        row.addWidget(self.black_luminance_ctrl)
        row.addWidget(QLabel("cd/m²"))
        row.addStretch(1)
        return row

    def _build_trc_row(self) -> QHBoxLayout:
        """Build the transfer-function chooser, gamma and BPC controls.

        Returns:
            QHBoxLayout: The TRC control row.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.getstr("trc")))
        self.trc_ctrl = QComboBox()
        self.trc_ctrl.addItems([lang.getstr(item) for item in TRC_ITEMS])
        self.trc_ctrl.activated.connect(self._on_trc)
        row.addWidget(self.trc_ctrl)

        self.trc_gamma_label = QLabel(lang.getstr("trc.gamma"))
        row.addWidget(self.trc_gamma_label)
        self.trc_gamma_ctrl = QComboBox()
        self.trc_gamma_ctrl.setEditable(True)
        self.trc_gamma_ctrl.addItems([f"{v / 10:.1f}" for v in range(10, 31, 2)])
        self.trc_gamma_ctrl.setFixedWidth(80)
        self.trc_gamma_ctrl.activated.connect(lambda _i: self._on_trc_gamma())
        self.trc_gamma_ctrl.lineEdit().editingFinished.connect(self._on_trc_gamma)
        row.addWidget(self.trc_gamma_ctrl)

        self.trc_gamma_type_ctrl = QComboBox()
        self.trc_gamma_type_ctrl.addItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )
        self.trc_gamma_type_ctrl.activated.connect(self._on_trc_gamma_type)
        row.addWidget(self.trc_gamma_type_ctrl)

        self.bpc_ctrl = QCheckBox(lang.getstr("black_point_compensation"))
        row.addWidget(self.bpc_ctrl)
        row.addStretch(1)
        return row

    def _build_hdr_group(self) -> QWidget:
        """Build the HDR roll-off controls (SMPTE 2084 / HLG).

        Returns:
            QWidget: A container widget holding all HDR control rows.
        """
        self.hdr_group = QWidget()
        layout = QVBoxLayout(self.hdr_group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Saturation slider (preserve luminance <-> saturation).
        self.hdr_sat_row = QWidget()
        sat_layout = QHBoxLayout(self.hdr_sat_row)
        sat_layout.setContentsMargins(0, 0, 0, 0)
        sat_layout.addWidget(QLabel(lang.getstr("preserve_luminance")))
        self.lut3d_hdr_sat_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_hdr_sat_ctrl.setRange(0, 100)
        self.lut3d_hdr_sat_ctrl.setFixedWidth(160)
        self.lut3d_hdr_sat_ctrl.valueChanged.connect(self._on_hdr_sat)
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
        self.lut3d_hdr_hue_ctrl.setFixedWidth(160)
        self.lut3d_hdr_hue_ctrl.valueChanged.connect(self._on_hdr_hue_slider)
        hue_layout.addWidget(self.lut3d_hdr_hue_ctrl)
        self.lut3d_hdr_hue_intctrl = QSpinBox()
        self.lut3d_hdr_hue_intctrl.setRange(0, 100)
        self.lut3d_hdr_hue_intctrl.setSuffix(" %")
        self.lut3d_hdr_hue_intctrl.valueChanged.connect(self._on_hdr_hue_spin)
        hue_layout.addWidget(self.lut3d_hdr_hue_intctrl)
        hue_layout.addStretch(1)
        layout.addWidget(self.hdr_hue_row)

        # Mastering display min luminance (SMPTE 2084).
        self.hdr_minmll_row = QWidget()
        minmll_layout = QHBoxLayout(self.hdr_minmll_row)
        minmll_layout.setContentsMargins(0, 0, 0, 0)
        minmll_layout.addWidget(
            QLabel(lang.getstr("mastering_display_black_luminance"))
        )
        self.lut3d_hdr_minmll_ctrl = self._spin(0.0, 0.1, 0.0001, 4, width=85)
        self.lut3d_hdr_minmll_ctrl.valueChanged.connect(self._on_hdr_minmll)
        minmll_layout.addWidget(self.lut3d_hdr_minmll_ctrl)
        minmll_layout.addWidget(QLabel("cd/m²"))
        minmll_layout.addStretch(1)
        layout.addWidget(self.hdr_minmll_row)

        # Mastering display peak luminance + alt-clip checkbox (SMPTE 2084 roll-off).
        self.hdr_maxmll_row = QWidget()
        maxmll_layout = QHBoxLayout(self.hdr_maxmll_row)
        maxmll_layout.setContentsMargins(0, 0, 0, 0)
        maxmll_layout.addWidget(QLabel(lang.getstr("mastering_display_peak_luminance")))
        self.lut3d_hdr_maxmll_ctrl = self._spin(100.0, 10000.0, 1.0, 0, width=85)
        self.lut3d_hdr_maxmll_ctrl.valueChanged.connect(self._on_hdr_maxmll)
        maxmll_layout.addWidget(self.lut3d_hdr_maxmll_ctrl)
        maxmll_layout.addWidget(QLabel("cd/m²"))
        self.lut3d_hdr_maxmll_alt_clip_cb = QCheckBox(lang.getstr("adjust_rolloff"))
        self.lut3d_hdr_maxmll_alt_clip_cb.toggled.connect(self._on_hdr_maxmll_alt_clip)
        maxmll_layout.addWidget(self.lut3d_hdr_maxmll_alt_clip_cb)
        maxmll_layout.addStretch(1)
        layout.addWidget(self.hdr_maxmll_row)

        # Diffuse-white readout (SMPTE 2084 roll-off).
        self.hdr_diffuse_white_row = QWidget()
        diffuse_layout = QHBoxLayout(self.hdr_diffuse_white_row)
        diffuse_layout.setContentsMargins(0, 0, 0, 0)
        diffuse_layout.addWidget(QLabel(lang.getstr("3dlut.hdr.rolloff.diffuse_white")))
        self.lut3d_hdr_diffuse_white_txt = QLabel("")
        diffuse_layout.addWidget(self.lut3d_hdr_diffuse_white_txt)
        diffuse_layout.addWidget(QLabel("cd/m²"))
        diffuse_layout.addStretch(1)
        layout.addWidget(self.hdr_diffuse_white_row)

        # Ambient luminance (HLG).
        self.hdr_ambient_row = QWidget()
        ambient_layout = QHBoxLayout(self.hdr_ambient_row)
        ambient_layout.setContentsMargins(0, 0, 0, 0)
        ambient_layout.addWidget(
            QLabel(lang.getstr("calibration.ambient_viewcond_adjust"))
        )
        self.lut3d_hdr_ambient_luminance_ctrl = self._spin(
            0.01, 10000.0, 0.01, 2, width=85
        )
        self.lut3d_hdr_ambient_luminance_ctrl.valueChanged.connect(self._on_hdr_ambient)
        ambient_layout.addWidget(self.lut3d_hdr_ambient_luminance_ctrl)
        ambient_layout.addWidget(QLabel("cd/m²"))
        ambient_layout.addStretch(1)
        layout.addWidget(self.hdr_ambient_row)

        # System gamma readout (HLG).
        self.hdr_system_gamma_row = QWidget()
        sysgamma_layout = QHBoxLayout(self.hdr_system_gamma_row)
        sysgamma_layout.setContentsMargins(0, 0, 0, 0)
        sysgamma_layout.addWidget(QLabel(lang.getstr("3dlut.hdr.system_gamma")))
        self.lut3d_hdr_system_gamma_txt = QLabel("")
        sysgamma_layout.addWidget(self.lut3d_hdr_system_gamma_txt)
        sysgamma_layout.addStretch(1)
        layout.addWidget(self.hdr_system_gamma_row)
        return self.hdr_group

    def _build_black_offset_row(self) -> QHBoxLayout:
        """Build the black output offset slider + spin.

        Returns:
            QHBoxLayout: The black-output-offset control row.
        """
        row = QHBoxLayout()
        self.black_output_offset_label = QLabel(
            lang.getstr("calibration.black_output_offset")
        )
        row.addWidget(self.black_output_offset_label)
        self.black_output_offset_ctrl = QSlider(Qt.Horizontal)
        self.black_output_offset_ctrl.setRange(0, 100)
        self.black_output_offset_ctrl.setFixedWidth(160)
        self.black_output_offset_ctrl.valueChanged.connect(self._on_black_offset_slider)
        row.addWidget(self.black_output_offset_ctrl)
        self.black_output_offset_intctrl = QSpinBox()
        self.black_output_offset_intctrl.setRange(0, 100)
        self.black_output_offset_intctrl.setSuffix(" %")
        self.black_output_offset_intctrl.valueChanged.connect(
            self._on_black_offset_spin
        )
        row.addWidget(self.black_output_offset_intctrl)
        row.addStretch(1)
        return row

    def _build_class_row(self) -> QHBoxLayout:
        """Build the profile-class chooser.

        Returns:
            QHBoxLayout: The profile-class control row.
        """
        row = QHBoxLayout()
        row.addWidget(QLabel(lang.getstr("profile_class")))
        self.profile_classes = dict(
            get_mapping(list(PROFILE_CLASS.items()), [b"mntr", b"scnr"])
        )
        self.profile_class_ctrl = QComboBox()
        self.profile_class_ctrl.addItems(list(self.profile_classes.values()))
        row.addWidget(self.profile_class_ctrl)
        row.addStretch(1)
        return row

    def _build_metadata_group(self) -> QGroupBox:
        """Build the technology / colorimetric-intent metadata group.

        Returns:
            QGroupBox: The metadata group box.
        """
        group = QGroupBox(lang.getstr("metadata"))
        layout = QGridLayout(group)
        layout.addWidget(QLabel(lang.getstr("technology")), 0, 0)
        self.tech = dict(
            get_mapping(
                [("", "unspecified"), *list(TECH.items())],
                [
                    "",
                    "fscn",
                    "dcam",
                    "rscn",
                    "vidm",
                    "vidc",
                    "pjtv",
                    "CRT ",
                    "PMD ",
                    "AMD ",
                    "mpfs",
                    "dmpc",
                    "dcpj",
                ],
            )
        )
        self.tech_ctrl = QComboBox()
        self.tech_ctrl.addItems(list(self.tech.values()))
        layout.addWidget(self.tech_ctrl, 0, 1)
        layout.addWidget(QLabel(lang.getstr("colorimetric_intent_image_state")), 1, 0)
        self.ciis = dict(
            get_mapping(
                [("", "unspecified"), *list(CIIS.items())],
                ["", "scoe", "sape", "fpce"],
            )
        )
        self.ciis_ctrl = QComboBox()
        self.ciis_ctrl.addItems(list(self.ciis.values()))
        layout.addWidget(self.ciis_ctrl, 1, 1)
        layout.setColumnStretch(1, 1)
        return group

    def _build_button_bar(self) -> QWidget:
        """Build the bottom bar with the Save As button.

        Returns:
            QWidget: The button-bar widget.
        """
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addStretch(1)
        self.save_as_btn = QPushButton(lang.getstr("save_as"))
        self.save_as_btn.setEnabled(False)
        self.save_as_btn.setDefault(True)
        self.save_as_btn.clicked.connect(self._on_save_as)
        layout.addWidget(self.save_as_btn)
        return bar

    # -- small Qt-flavored helpers for parity with the wx code -------------

    def _set_spin(self, name: str, value: float) -> None:
        """Set a spin box value without re-triggering handlers.

        Args:
            name (str): Attribute name of the spin box (e.g. ``"white_X"``).
            value (float): The value to set.
        """
        getattr(self, name).setValue(value)

    def _color_value(self, color: str, component: str) -> float:
        """Return a color spin box's current value.

        Args:
            color (str): Color name.
            component (str): One of ``XYZxy``.

        Returns:
            float: The control's value.
        """
        return getattr(self, f"{color}_{component}").value()

    # -- signal slots (guard + delegate to the wx-derived logic) ----------

    def _on_preset(self, _index: int) -> None:
        if self._updating:
            return
        self.preset_ctrl_handler()

    def _on_colorspace(self, _checked: bool) -> None:
        if self._updating:
            return
        self.colorspace_ctrl_handler()

    def _on_color_changed(self, color: str, handler: str) -> None:
        if self._updating:
            return
        with self._guard():
            if color == "white":
                if handler == "XYZ":
                    self.parse_XYZ("white")
                    self.parse_xy()
                else:
                    self.parse_xy("white")
            elif color == "black":
                if handler == "XYZ":
                    self.black_XYZ_ctrl_handler()
                else:
                    self.black_xy_ctrl_handler()
            elif handler == "XYZ":
                self.parse_XYZ(color)
            else:
                self.parse_xy(color)

    def _on_black_point_enable(self, _checked: bool) -> None:
        if self._updating:
            return
        self.black_point_enable_handler()

    def _on_luminance(self, _value: float) -> None:
        if self._updating:
            return
        with self._guard():
            self.luminance_ctrl_handler(True)

    def _on_black_luminance(self, _value: float) -> None:
        if self._updating:
            return
        with self._guard():
            self.black_luminance_ctrl_handler(True)

    def _on_trc(self, _index: int) -> None:
        if self._updating:
            return
        self.trc_ctrl_handler()

    def _on_trc_gamma(self) -> None:
        if self._updating:
            return
        self.trc_gamma_ctrl_handler()

    def _on_trc_gamma_type(self, _index: int) -> None:
        if self._updating:
            return
        self.trc_gamma_type_ctrl_handler()

    def _on_black_offset_slider(self, value: int) -> None:
        if self._updating:
            return
        with self._guard():
            self.black_output_offset_intctrl.setValue(value)
        self.black_output_offset_ctrl_handler()

    def _on_black_offset_spin(self, value: int) -> None:
        if self._updating:
            return
        with self._guard():
            self.black_output_offset_ctrl.setValue(value)
        self.black_output_offset_ctrl_handler()

    def _on_hdr_sat(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_sat", value / 100.0)
        self.lut3d_hdr_update_sat_val()

    def _on_hdr_hue_slider(self, value: int) -> None:
        if self._updating:
            return
        with self._guard():
            self.lut3d_hdr_hue_intctrl.setValue(value)
        if value / 100.0 != getcfg("3dlut.hdr_hue"):
            self.lut3d_set_option("3dlut.hdr_hue", value / 100.0)

    def _on_hdr_hue_spin(self, value: int) -> None:
        if self._updating:
            return
        with self._guard():
            self.lut3d_hdr_hue_ctrl.setValue(value)
        if value / 100.0 != getcfg("3dlut.hdr_hue"):
            self.lut3d_set_option("3dlut.hdr_hue", value / 100.0)

    def _on_hdr_minmll(self, value: float) -> None:
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_minmll", value)

    def _on_hdr_maxmll(self, value: float) -> None:
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_maxmll", value)

    def _on_hdr_maxmll_alt_clip(self, _checked: bool) -> None:
        if self._updating:
            return
        self.lut3d_set_option(
            "3dlut.hdr_maxmll_alt_clip",
            int(not self.lut3d_hdr_maxmll_alt_clip_cb.isChecked()),
        )
        self.lut3d_hdr_update_diffuse_white()

    def _on_hdr_ambient(self, value: float) -> None:
        if self._updating:
            return
        self.lut3d_set_option("3dlut.hdr_ambient_luminance", value)

    # -- HDR helpers (inlined from LUT3DMixin) -----------------------------

    def lut3d_set_option(self, option: str, value: object) -> None:
        """Persist a 3D-LUT/HDR option and refresh dependent readouts.

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

    def lut3d_show_hdr_maxmll_alt_clip_ctrl(self) -> None:
        """Show the alt-clip checkbox only when peak roll-off applies."""
        show = self.hdr_maxmll_row.isVisible()
        self.lut3d_hdr_maxmll_alt_clip_cb.setVisible(
            show and getcfg("3dlut.hdr_maxmll") < 10000
        )

    # -- drag and drop -----------------------------------------------------

    def drop_handler(self, path: str) -> None:
        """Route a dropped file to the ICC or TI3 handler.

        Args:
            path (str): The dropped file path.
        """
        _, ext = os.path.splitext(path)
        if ext.lower() == ".ti3":
            self.ti3_drop_handler(path)
        else:
            self.icc_drop_handler(path)

    def icc_drop_handler(self, path: str) -> None:
        """Seed the controls from a dropped ICC profile.

        Args:
            path (str): Path to the ICC profile.
        """
        try:
            profile = ICCProfile(path)
        except (OSError, ICCProfileInvalidError):
            message_box.critical(
                self, self.windowTitle(), lang.getstr("profile.invalid") + "\n" + path
            )
            return
        if profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
            message_box.critical(
                self, self.windowTitle(), lang.getstr("profile.iccv4.unsupported")
            )
            return
        if profile.colorSpace not in (b"RGB", b"GRAY") or (
            profile.connectionColorSpace not in (b"Lab", b"XYZ")
        ):
            message_box.critical(
                self,
                self.windowTitle(),
                lang.getstr(
                    "profile.unsupported",
                    (
                        profile.profileClass.decode("utf-8"),
                        profile.colorSpace.decode("utf-8"),
                    ),
                ),
            )
            return
        rgb = [(1, 1, 1), (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        rgb.extend((1.0 / 255 * i, 1.0 / 255 * i, 1.0 / 255 * i) for i in range(256))
        try:
            colors = self.worker.xicclu(profile, rgb, intent="a", pcs="x")
        except Exception as exception:  # noqa: BLE001
            message_box.critical(self, self.windowTitle(), str(exception))
            return
        finally:
            self.worker.wrapup(False)
        luminance = profile.tags.lumi.Y if "lumi" in profile.tags else 100
        if not colors[1][1] and isinstance(profile.tags.get("targ"), Text):
            # Lookup gave black = 0; fall back to the embedded TI3 black point.
            XYZbp = profile.get_chardata_bkpt(True)
            if XYZbp:
                colors[1] = [v * XYZbp[1] for v in colors[0]]
        self.set_colors(colors, luminance, profile.colorSpace)

    def ti3_drop_handler(self, path: str) -> None:
        """Seed the controls from a dropped TI3 measurement file.

        Args:
            path (str): Path to the TI3 file.
        """
        try:
            ti3 = CGATS(path)
        except (OSError, CGATSInvalidError):
            message_box.critical(
                self,
                self.windowTitle(),
                lang.getstr("error.measurement.file_invalid", path),
            )
            return
        ti3[0].normalize_to_y_100()
        rgb = [(100, 100, 100), (0, 0, 0), (100, 0, 0), (0, 100, 0), (0, 0, 100)]
        colors = []
        for R, G, B in rgb:
            result = ti3.queryi1({"RGB_R": R, "RGB_G": G, "RGB_B": B})
            color = []
            if result:
                for component in "XYZ":
                    label = "XYZ_" + component
                    if label in result:
                        color.append(result[label])
            if not result or len(color) < 3:
                color = (0, 0, 0)
            colors.append(color)
        try:
            _, RGB_XYZ_extracted, _ = extract_device_gray_primaries(ti3)
        except Error as exception:
            message_box.critical(self, self.windowTitle(), str(exception))
            return
        RGB_XYZ_extracted = dict_sort(RGB_XYZ_extracted)
        colors.extend(list(RGB_XYZ_extracted.values()))
        luminance = ti3.queryv1("LUMINANCE_XYZ_CDM2")
        if luminance:
            try:
                luminance = float(luminance.split()[1])
            except (TypeError, ValueError):
                luminance = 100
        else:
            luminance = 100
        self.set_colors(colors, luminance, "RGB")

    def set_colors(
        self, colors: list, luminance: float, colorspace: bytes | str
    ) -> None:
        """Populate all controls from looked-up/measured colorimetry.

        Args:
            colors (list): XYZ triplets for white, black, red, green, blue and
                (optionally) a gray ramp.
            luminance (float): White luminance in cd/m².
            colorspace (bytes | str): ``RGB`` or ``GRAY``.
        """
        if isinstance(colorspace, bytes):
            colorspace = colorspace.decode("utf-8", "replace")
        with self._guard():
            self.colorspace_rgb_ctrl.setChecked(colorspace == "RGB")
            self.colorspace_gray_ctrl.setChecked(colorspace == "GRAY")
        self.colorspace_ctrl_handler()
        with self._guard():
            setcfg("synthprofile.luminance", luminance)
            self.luminance_ctrl.setValue(luminance)
            for i, color in enumerate(("white", "black")):
                for j, component in enumerate("XYZ"):
                    self._set_spin(
                        f"{color}_{component}", colors[i][j] / colors[0][1] * 100
                    )
                self.parse_XYZ(color)
            for i, color in enumerate(("red", "green", "blue")):
                xyY = colormath.XYZ2xyY(*colors[2 + i])
                for j, component in enumerate("xy"):
                    self._set_spin(f"{color}_{component}", xyY[j])
            self.parse_xy(None)
            self.black_XYZ_ctrl_handler()
            if len(colors[5:]) > 2:
                trc = CurveType()
                for XYZ in colors[5:]:
                    trc.append(XYZ[1] / colors[0][1] * 65535)
                transfer_function = trc.get_transfer_function(outoffset=1.0)
                if transfer_function and transfer_function[1] >= 0.95:
                    gamma = transfer_function[0][1]
                else:
                    gamma = math.log(colors[132][1]) / math.log(128.0 / 255)
                self.set_trc(round(gamma, 2))
                setcfg("synthprofile.trc_gamma_type", "g")
                self.trc_gamma_type_ctrl.setCurrentIndex(self.trc_gamma_types_ba["g"])

    # -- colorimetry logic (ported from the wx frame) ---------------------

    def enable_btns(self) -> None:
        """Enable Save As / chromatic adaptation when colorimetry is valid."""
        enable = bool(self.get_XYZ())
        self.save_as_btn.setEnabled(enable)
        self.chromatic_adaptation_btn.setEnabled(enable)

    def get_XYZ(self) -> dict | None:
        """Return the entered colorimetry as a dict, or ``None`` if invalid.

        Returns:
            dict | None: XYZ values keyed by ``"<channel><component>"`` (e.g.
            ``"wX"``, ``"kZ"``) in the 0..1 range, or ``None`` if incomplete.
        """
        XYZ = {}
        black_Y = getcfg("synthprofile.black_luminance") / getcfg(
            "synthprofile.luminance"
        )
        for color in ("white", "red", "green", "blue", "black"):
            for component in "XYZ":
                v = self._color_value(color, component) / 100.0
                if color == "black":
                    key = "k"
                    if not self.black_point_cb.isChecked():
                        v = XYZ[f"w{component}"] * black_Y
                else:
                    key = color[0]
                XYZ[key + component] = v
        if (
            XYZ["wX"]
            and XYZ["wY"]
            and XYZ["wZ"]
            and (
                self.colorspace_gray_ctrl.isChecked()
                or (XYZ["rX"] and XYZ["gY"] and XYZ["bZ"])
            )
        ):
            return XYZ
        return None

    def colorspace_ctrl_handler(self) -> None:
        """Show/hide the RGB primary controls based on the colorspace choice."""
        show = self.colorspace_rgb_ctrl.isChecked()
        for color in ("red", "green", "blue"):
            getattr(self, f"label_{color}").setVisible(show)
            for component in "XYZxy":
                getattr(self, f"{color}_{component}").setVisible(show)
        self.enable_btns()

    def black_point_enable_handler(self) -> None:
        """Enable the black chromaticity controls when applicable."""
        v = getcfg("synthprofile.black_luminance")
        for component in "XYZxy":
            getattr(self, f"black_{component}").setEnabled(
                v > 0 and self.black_point_cb.isChecked()
            )

    def black_XYZ_ctrl_handler(self) -> None:
        """Sync black luminance / chromaticity from the black XYZ controls."""
        luminance = getcfg("synthprofile.luminance")
        XYZ = []
        for component in "XYZ":
            XYZ.append(self._color_value("black", component) / 100.0)
            if component == "Y":
                self.black_luminance_ctrl.setValue(XYZ[-1] * luminance)
                self.black_luminance_ctrl_handler(None)
                if not XYZ[-1]:
                    for i in range(3):
                        self._set_spin(f"black_{'XYZ'[i]}", 0)
                    break
        self.parse_XYZ("black")

    def black_xy_ctrl_handler(self) -> None:
        """Recompute black XYZ from its chromaticity and luminance."""
        Y = getcfg("synthprofile.black_luminance") / getcfg("synthprofile.luminance")
        xy = []
        for component in "xy":
            xy.append(self._color_value("black", component) or 1.0 / 3)
            self._set_spin(f"black_{component}", xy[-1])
        for i, v in enumerate(colormath.xyY2XYZ(*[*xy, Y])):
            self._set_spin(f"black_{'XYZ'[i]}", v * 100)

    def parse_XYZ(self, name: str, set_blackpoint: bool | None = None) -> None:
        """Recompute a color's chromaticity from its XYZ and refresh state.

        Args:
            name (str): Color name (e.g. ``"white"``).
            set_blackpoint (bool | None): Whether to also set the black point
                from the white point; defaults to "when the black-point box is
                unchecked".
        """
        if set_blackpoint is None:
            set_blackpoint = not self.black_point_cb.isChecked()
        if not self._updating:
            self.preset_ctrl.setCurrentIndex(0)
        XYZ = {}
        black_Y = getcfg("synthprofile.black_luminance") / getcfg(
            "synthprofile.luminance"
        )
        for component in "XYZ":
            v = self._color_value(name, component)
            XYZ[component] = v
            if name == "white" and set_blackpoint:
                self._set_spin(f"black_{component}", v * black_Y)
        if "X" in XYZ and "Y" in XYZ and "Z" in XYZ:
            if XYZ["X"] + XYZ["Y"] + XYZ["Z"] == 0:
                xyY = [self._color_value("white", c) for c in "xy"]
            else:
                xyY = colormath.XYZ2xyY(XYZ["X"], XYZ["Y"], XYZ["Z"])
            for i, component in enumerate("xy"):
                self._set_spin(f"{name}_{component}", xyY[i])
                if name == "white" and set_blackpoint:
                    self._set_spin(f"black_{component}", xyY[i])
        self.enable_btns()

    def parse_xy(self, name: str | None = None, set_blackpoint: bool = False) -> None:
        """Recompute primaries' XYZ from chromaticities and the white point.

        Args:
            name (str | None): Color name being edited (e.g. ``"white"``), or
                ``None`` to recompute all primaries.
            set_blackpoint (bool): Whether to also set the black point from the
                white point.
        """
        if not set_blackpoint:
            set_blackpoint = not self.black_point_cb.isChecked()
        if not self._updating:
            self.preset_ctrl.setCurrentIndex(0)
        xy = {}
        for color in ("white", "red", "green", "blue"):
            for component in "xy":
                xy[color[0] + component] = self._color_value(color, component)
        if name == "white":
            wXYZ = colormath.xyY2XYZ(xy["wx"], xy["wy"], 1.0)
        else:
            wXYZ = [self._color_value("white", c) / 100.0 for c in "XYZ"]
        if name == "white":
            black_Y = getcfg("synthprofile.black_luminance") / getcfg(
                "synthprofile.luminance"
            )
            for i, component in enumerate("XYZ"):
                self._set_spin(f"white_{component}", wXYZ[i] * 100)
                if set_blackpoint:
                    self._set_spin(f"black_{component}", wXYZ[i] * black_Y * 100)
        has_rgb_xy = True
        try:
            mtx = colormath.rgb_to_xyz_matrix(
                xy["rx"], xy["ry"], xy["gx"], xy["gy"], xy["bx"], xy["by"], wXYZ
            )
        except ZeroDivisionError:
            has_rgb_xy = False
        rgb = {"r": (1.0, 0.0, 0.0), "g": (0.0, 1.0, 0.0), "b": (0.0, 0.0, 1.0)}
        for color in ("red", "green", "blue"):
            v = mtx * rgb[color[0]] if has_rgb_xy else (0, 0, 0)
            for i, component in enumerate("XYZ"):
                self._set_spin(f"{color}_{component}", v[i] * 100)
        self.enable_btns()

    def preset_ctrl_handler(self) -> None:
        """Load a built-in RGB-space preset into the controls."""
        preset_name = self.preset_ctrl.currentText()
        if not preset_name:
            return
        self.cat = "Bradford"
        gamma, white, red, green, blue = colormath.rgb_spaces[preset_name]
        white = colormath.get_whitepoint(white)
        with self._guard():
            tech = self.tech["dcpj"] if preset_name == "DCI P3" else self.tech[""]
            self.tech_ctrl.setCurrentText(tech)
            self._set_spin("white_X", white[0] * 100)
            self._set_spin("white_Y", white[1] * 100)
            self._set_spin("white_Z", white[2] * 100)
            self.parse_XYZ("white", True)
            self._set_spin("red_x", red[0])
            self._set_spin("red_y", red[1])
            self._set_spin("green_x", green[0])
            self._set_spin("green_y", green[1])
            self._set_spin("blue_x", blue[0])
            self._set_spin("blue_y", blue[1])
            self.parse_xy(None)
            self.set_trc(gamma)

    def luminance_ctrl_handler(self, event: object) -> None:
        """Apply a new white luminance and propagate HDR peak constraints.

        Args:
            event: Truthy when triggered by a user edit (matches the wx API).
        """
        v = self.luminance_ctrl.value()
        setcfg("synthprofile.luminance", v)
        target_peak = v
        if self.lut3d_hdr_maxmll_ctrl.value() < target_peak:
            setcfg("3dlut.hdr_maxmll", target_peak)
        self.lut3d_hdr_maxmll_ctrl.setRange(target_peak, 10000)
        self.lut3d_set_option("3dlut.hdr_peak_luminance", v)
        self.black_luminance_ctrl_handler(event)

    def black_luminance_ctrl_handler(self, event: object) -> None:
        """Clamp/snap the black luminance and refresh dependent controls.

        Args:
            event: Truthy when triggered by user interaction (matches the wx
                API); ``True`` additionally forces a visibility refresh.
        """
        v = self.black_luminance_ctrl.value()
        white_Y = getcfg("synthprofile.luminance")
        if v >= white_Y * 0.9:
            if event:
                QApplication.beep()
            v = white_Y * 0.9
        if event:
            min_Y = 0.000001
            increment = 0.000001
            if increment < min_Y:
                increment = min_Y * (white_Y / 100.0)
            min_inc = 1.0 / (10.0 ** self.black_luminance_ctrl.decimals())
            increment = max(increment, min_inc)
            self.black_luminance_ctrl.setSingleStep(increment)
            fmt = f"{{:.{self.black_luminance_ctrl.decimals()}f}}"
            if fmt.format(0) < fmt.format(v) < fmt.format(increment):
                v = increment if event else 0
            elif fmt.format(v) == fmt.format(0):
                v = 0
            v = round(v / increment) * increment
        self.black_luminance_ctrl.setValue(v)

        old = getcfg("synthprofile.black_luminance")
        setcfg("synthprofile.black_luminance", v)
        if event:
            self.black_xy_ctrl_handler()
        self.black_point_cb.setEnabled(v > 0)
        self.black_point_enable_handler()
        if (v != old and (old == 0 or v == 0)) or event is True:
            i = self.trc_ctrl.currentIndex()
            self.trc_gamma_type_ctrl.setVisible(i in (0, 5) and bool(v))
            if not v:
                self.bpc_ctrl.setChecked(False)
            self.bpc_ctrl.setEnabled(bool(v))
            show = i in (0, 5, 7, 8) and bool(v)
            self.black_output_offset_label.setVisible(show)
            self.black_output_offset_ctrl.setVisible(show)
            self.black_output_offset_intctrl.setVisible(show)

    def black_output_offset_ctrl_handler(self) -> None:
        """Store the black output offset and refresh the TRC control."""
        v = self.black_output_offset_ctrl.value() / 100.0
        setcfg("synthprofile.trc_output_offset", v)
        self.update_trc_control()

    def set_trc(self, gamma: float) -> None:
        """Select the TRC control entry matching ``gamma``.

        Args:
            gamma (float | int): A gamma value, or a negative sentinel for a
                named transfer function (e.g. ``-2084`` for SMPTE 2084).
        """
        sentinel = {
            -1023: 1,  # DICOM
            -2.0: 2,  # HLG
            -3.0: 3,  # L*
            -709: 4,  # Rec. 709
            -240: 6,  # SMPTE 240M
            -2084: 8,  # SMPTE 2084 (roll-off clip)
            -2.4: 9,  # sRGB
        }
        if gamma == -1886:
            self.trc_ctrl.setCurrentIndex(5)  # Rec. 1886
            self.trc_ctrl_handler()
        elif gamma in sentinel:
            self.trc_ctrl.setCurrentIndex(sentinel[gamma])
        else:
            self.trc_ctrl.setCurrentIndex(0)  # Gamma
            setcfg("synthprofile.trc_gamma", gamma)
        self.update_trc_controls()

    def trc_ctrl_handler(self) -> None:
        """React to a transfer-function selection change."""
        if not self._updating:
            self.preset_ctrl.setCurrentIndex(0)
        i = self.trc_ctrl.currentIndex()
        if i == 5:
            # BT.1886
            setcfg("synthprofile.trc_gamma", 2.4)
            setcfg("synthprofile.trc_gamma_type", "G")
            setcfg("synthprofile.trc_output_offset", 0.0)
        if not self._updating:
            self.update_trc_controls()

    def trc_gamma_type_ctrl_handler(self) -> None:
        """Store the relative/absolute gamma type and refresh the TRC control."""
        setcfg(
            "synthprofile.trc_gamma_type",
            self.trc_gamma_types_ab[self.trc_gamma_type_ctrl.currentIndex()],
        )
        self.update_trc_control()

    def trc_gamma_ctrl_handler(self) -> None:
        """Validate the typed/selected gamma value and store it."""
        text = self.trc_gamma_ctrl.currentText().replace(",", ".")
        try:
            v = float(text)
            if (
                v < config.VALID_RANGES["gamma"][0]
                or v > config.VALID_RANGES["gamma"][1]
            ):
                raise ValueError
        except ValueError:
            QApplication.beep()
            with self._guard():
                self.trc_gamma_ctrl.setCurrentText(
                    str(getcfg("synthprofile.trc_gamma"))
                )
            return
        with self._guard():
            if str(v) != self.trc_gamma_ctrl.currentText():
                self.trc_gamma_ctrl.setCurrentText(str(v))
        setcfg("synthprofile.trc_gamma", v)
        self.preset_ctrl.setCurrentIndex(0)
        self.update_trc_control()

    def update_controls(self) -> None:
        """Initialize the controls from the saved configuration."""
        with self._guard():
            self.luminance_ctrl.setValue(getcfg("synthprofile.luminance"))
            self.black_luminance_ctrl.setValue(getcfg("synthprofile.black_luminance"))
        self.update_trc_control()

    def update_trc_control(self) -> None:
        """Pick Gamma vs. BT.1886 based on the current gamma/offset config."""
        if self.trc_ctrl.currentIndex() in (0, 5):
            if (
                getcfg("synthprofile.trc_gamma_type") == "G"
                and getcfg("synthprofile.trc_output_offset") == 0
                and getcfg("synthprofile.trc_gamma") == 2.4
            ):
                self.trc_ctrl.setCurrentIndex(5)  # BT.1886
            else:
                self.trc_ctrl.setCurrentIndex(0)  # Gamma

    def update_trc_controls(self) -> None:
        """Refresh all TRC/HDR control values and visibility for the selection."""
        i = self.trc_ctrl.currentIndex()
        with self._guard():
            self.trc_gamma_label.setVisible(i in (0, 5))
            self.trc_gamma_ctrl.setCurrentText(str(getcfg("synthprofile.trc_gamma")))
            self.trc_gamma_ctrl.setVisible(i in (0, 5))
            self.trc_gamma_type_ctrl.setCurrentIndex(
                self.trc_gamma_types_ba[getcfg("synthprofile.trc_gamma_type")]
            )
            if i in (0, 5, 7, 8):
                outoffset = int(getcfg("synthprofile.trc_output_offset") * 100)
            else:
                outoffset = 100
            self.black_output_offset_ctrl.setValue(outoffset)
            self.black_output_offset_intctrl.setValue(outoffset)

            target_peak = getcfg("synthprofile.luminance")
            maxmll = getcfg("3dlut.hdr_maxmll")
            if maxmll < target_peak:
                maxmll = target_peak
                setcfg("3dlut.hdr_maxmll", maxmll)
            self.lut3d_hdr_maxmll_ctrl.setRange(target_peak, 10000)
            self.luminance_ctrl.setValue(target_peak)
            self.lut3d_hdr_minmll_ctrl.setValue(getcfg("3dlut.hdr_minmll"))
            self.lut3d_hdr_maxmll_ctrl.setValue(maxmll)
            self.lut3d_hdr_maxmll_alt_clip_cb.setChecked(
                not bool(getcfg("3dlut.hdr_maxmll_alt_clip"))
            )
            self.lut3d_hdr_sat_ctrl.setValue(round(getcfg("3dlut.hdr_sat") * 100))
            self.lut3d_hdr_update_sat_val()
            hue = round(getcfg("3dlut.hdr_hue") * 100)
            self.lut3d_hdr_hue_ctrl.setValue(hue)
            self.lut3d_hdr_hue_intctrl.setValue(hue)
            setcfg("3dlut.hdr_peak_luminance", getcfg("synthprofile.luminance"))
            self.lut3d_hdr_update_diffuse_white()
            self.lut3d_hdr_ambient_luminance_ctrl.setValue(
                getcfg("3dlut.hdr_ambient_luminance")
            )
            self.lut3d_hdr_update_system_gamma()

        # Visibility of HDR rows (7/8 = SMPTE 2084, 2 = HLG).
        self.hdr_group.setVisible(i in (2, 7, 8))
        self.hdr_minmll_row.setVisible(i in (7, 8))
        self.hdr_maxmll_row.setVisible(i == 8)
        self.hdr_diffuse_white_row.setVisible(i == 8)
        self.hdr_sat_row.setVisible(i == 8)
        self.hdr_hue_row.setVisible(i == 8)
        self.hdr_ambient_row.setVisible(i == 2)
        self.hdr_system_gamma_row.setVisible(i == 2)
        self.lut3d_show_hdr_maxmll_alt_clip_ctrl()

        self.black_luminance_ctrl_handler(True)
        with self._guard():
            if i in (4, 6):
                # Rec. 709 / SMPTE 240M: match Adobe 'video' profiles.
                self.profile_class_ctrl.setCurrentText(self.profile_classes[b"scnr"])
                self.tech_ctrl.setCurrentText(self.tech["vidc"])
                self.ciis_ctrl.setCurrentText(self.ciis["fpce"])
            elif self.profile_class_ctrl.currentText() == self.profile_classes[b"scnr"]:
                self.profile_class_ctrl.setCurrentText(self.profile_classes[b"mntr"])
                self.tech_ctrl.setCurrentText(self.tech[""])
                self.ciis_ctrl.setCurrentText(self.ciis[""])

    # -- chromatic adaptation ---------------------------------------------

    def _on_chromatic_adaptation(self) -> None:
        """Show the chromatic-adaptation dialog and apply the result."""
        dlg = QDialog(self)
        dlg.setWindowTitle(lang.getstr("chromatic_adaptation"))
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(lang.getstr("whitepoint.xy")))

        xy_row = QHBoxLayout()
        x_ctrl = QDoubleSpinBox()
        x_ctrl.setDecimals(5)
        x_ctrl.setRange(0.00001, 1.0)
        x_ctrl.setSingleStep(0.00001)
        x_ctrl.setValue(self._color_value("white", "x"))
        y_ctrl = QDoubleSpinBox()
        y_ctrl.setDecimals(5)
        y_ctrl.setRange(0.00001, 1.0)
        y_ctrl.setSingleStep(0.00001)
        y_ctrl.setValue(self._color_value("white", "y"))
        xy_row.addWidget(x_ctrl)
        xy_row.addWidget(QLabel("x"))
        xy_row.addWidget(y_ctrl)
        xy_row.addWidget(QLabel("y"))
        xy_row.addStretch(1)
        layout.addLayout(xy_row)

        layout.addWidget(QLabel(lang.getstr("chromatic_adaptation_transform")))
        if getcfg("show_advanced_options"):
            cat_choices = ["Bradford", "CAT02BS"]
        else:
            cat_choices = ["Bradford"]
        cat_choices_ab = dict(
            get_mapping(((k, k) for k in colormath.CAT_MATRICES), cat_choices)
        )
        cat_choices_ba = {v: k for k, v in cat_choices_ab.items()}
        cat_ctrl = QComboBox()
        cat_ctrl.addItems(list(cat_choices_ab.values()))
        cat_ctrl.setCurrentText(cat_choices_ab[self.cat])
        layout.addWidget(cat_ctrl)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(lang.getstr("apply"))
        buttons.button(QDialogButtonBox.Cancel).setText(lang.getstr("cancel"))
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return
        x = x_ctrl.value()
        y = y_ctrl.value()
        cat = cat_choices_ba[cat_ctrl.currentText()]
        wp_src = [self._color_value("white", c) for c in "XYZ"]
        wp_tgt = colormath.xyY2XYZ(x, y)
        self.cat = cat
        with self._guard():
            for color in ("red", "green", "blue", "white", "black"):
                X, Y, Z = (self._color_value(color, c) for c in "XYZ")
                XYZa = colormath.adapt(X, Y, Z, wp_src, wp_tgt, cat)
                for i, component in enumerate("XYZ"):
                    self._set_spin(f"{color}_{component}", XYZa[i])
                self.parse_XYZ(color, False)

    # -- saving ------------------------------------------------------------

    def _on_save_as(self) -> None:
        """Prompt for an output path and create the profile."""
        try:
            gamma = float(self.trc_gamma_ctrl.currentText())
        except ValueError:
            QApplication.beep()
            gamma = 2.2
            self.trc_gamma_ctrl.setCurrentText(str(gamma))

        default_dir, _ = get_verified_path("last_icc_path")
        default_file = lang.getstr("unnamed")
        wildcard = f"{lang.getstr('filetype.icc')} (*{PROFILE_EXT})"
        path, _ = file_dialog.get_save_file_name(
            self,
            lang.getstr("save_as"),
            os.path.join(default_dir, default_file),
            wildcard,
        )
        if not path:
            return
        if os.path.splitext(path)[1].lower() not in (".icc", ".icm"):
            path += PROFILE_EXT
        if not waccess(path, os.W_OK):
            message_box.critical(
                self,
                self.windowTitle(),
                lang.getstr("error.access_denied.write", path),
            )
            return
        setcfg("last_icc_path", path)

        XYZ = self.get_XYZ()
        sel = self.trc_ctrl.currentIndex()
        trc_for_index = {
            0: gamma,  # Gamma
            5: gamma,  # Rec. 1886 (only used if black == 0)
            1: -1,  # DICOM
            2: -2,  # HLG
            3: -3.0,  # L*
            4: -709,  # Rec. 709
            6: -240,  # SMPTE 240M
            7: -2084,  # SMPTE 2084 hard clip
            8: -2084,  # SMPTE 2084 roll-off clip
            9: -2.4,  # sRGB
        }
        trc = trc_for_index[sel]
        rolloff = sel == 8
        class_i = self.profile_class_ctrl.currentIndex()
        tech_i = self.tech_ctrl.currentIndex()
        ciis_i = self.ciis_ctrl.currentIndex()

        kwargs = {
            "rgb": self.colorspace_rgb_ctrl.isChecked(),
            "rolloff": rolloff,
            "bpc": self.bpc_ctrl.isChecked(),
            "profile_class": list(self.profile_classes.keys())[class_i],
            "tech": list(self.tech.keys())[tech_i],
            "ciis": list(self.ciis.keys())[ciis_i],
        }
        args = (XYZ, trc, path)
        if (trc == -2084 and rolloff) or trc == -2:
            # HDR cLUT generation is slow: run it off the GUI thread.
            if self._thread is not None and self._thread.isRunning():
                return
            msg = "smpte2084.rolloffclip" if trc == -2084 else "hlg"
            self.worker.recent.write(lang.getstr("trc." + msg) + "\n")
            self.save_as_btn.setEnabled(False)
            self._thread = _CreateThread(self, args, kwargs, parent=self)
            self._thread.done.connect(self._on_create_done)
            self._thread.start()
        else:
            self._on_create_done(self.create_profile(*args, **kwargs))

    def _on_create_done(self, result: object) -> None:
        """Handle a finished profile creation on the GUI thread.

        Args:
            result: ``None`` on success, or an ``Exception`` on failure.
        """
        self._thread = None
        self.save_as_btn.setEnabled(True)
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))

    def create_profile(
        self,
        XYZ: dict,
        trc: float,
        path: str,
        rgb: bool = True,
        rolloff: bool = True,
        bpc: bool = False,
        profile_class: bytes = b"mntr",
        tech: str | bytes | None = None,
        ciis: str | bytes | None = None,
    ) -> Exception | None:
        """Create and write the synthetic ICC profile.

        Args:
            XYZ (dict): XYZ values keyed by ``"<channel><component>"`` (e.g.
                ``"wX"``, ``"kZ"``) in the 0..1 range.
            trc (float): A gamma value, or a negative sentinel for a named
                transfer function (e.g. ``-2084`` for SMPTE 2084).
            path (str): Output path to write the profile to.
            rgb (bool): Create an RGB (vs. grayscale) profile.
            rolloff (bool): Use BT.2390 roll-off for HDR PQ.
            bpc (bool): Apply black-point compensation.
            profile_class (bytes): ICC profile class signature.
            tech (str | bytes | None): Technology signature, if any.
            ciis (str | bytes | None): Colorimetric-intent image-state signature.

        Returns:
            Exception | None: An exception on failure, or ``None`` on success.
        """
        white = XYZ["wX"], XYZ["wY"], XYZ["wZ"]
        if rgb:
            profile = ICCProfile.from_XYZ(
                (XYZ["rX"], XYZ["rY"], XYZ["rZ"]),
                (XYZ["gX"], XYZ["gY"], XYZ["gZ"]),
                (XYZ["bX"], XYZ["bY"], XYZ["bZ"]),
                (XYZ["wX"], XYZ["wY"], XYZ["wZ"]),
                1.0,
                "",
                getcfg("copyright"),
                cat=self.cat,
                profile_class=profile_class,
            )
            black = colormath.adapt(XYZ["kX"], XYZ["kY"], XYZ["kZ"], white)
            profile.tags.rTRC = CurveType(profile=profile)
            profile.tags.gTRC = CurveType(profile=profile)
            profile.tags.bTRC = CurveType(profile=profile)
            channels = "rgb"
        else:
            profile = ICCProfile()
            profile.profileClass = profile_class
            if not s15f16_is_equal(
                (XYZ["wX"], XYZ["wY"], XYZ["wZ"]), colormath.get_whitepoint("D50")
            ) and (
                profile.profileClass not in (b"mntr", b"prtr")
                or colormath.is_similar_matrix(
                    colormath.get_cat_matrix(self.cat),
                    colormath.get_cat_matrix("Bradford"),
                )
            ):
                profile.version = 2.2  # Match ArgyllCMS
            profile.colorSpace = b"GRAY"
            profile.setCopyright(getcfg("copyright"))
            profile.set_wtpt((XYZ["wX"], XYZ["wY"], XYZ["wZ"]), self.cat)
            black = [
                XYZ["wY"]
                * (
                    getcfg("synthprofile.black_luminance")
                    / getcfg("synthprofile.luminance")
                )
            ] * 3
            profile.tags.kTRC = CurveType(profile=profile)
            channels = "k"
        outoffset = 1 if trc == -2 else getcfg("synthprofile.trc_output_offset")
        if trc == -1:
            # DICOM (absolute luminance)
            try:
                if rgb:
                    profile.set_dicom_trc(
                        [v * getcfg("synthprofile.luminance") for v in black],
                        getcfg("synthprofile.luminance"),
                    )
                else:
                    profile.tags.kTRC.set_dicom_trc(
                        getcfg("synthprofile.black_luminance"),
                        getcfg("synthprofile.luminance"),
                    )
            except ValueError as exception:
                return exception
        elif trc > -1 and black != [0, 0, 0]:
            # Gamma with output offset or Rec. 1886-like
            if rgb:
                profile.set_bt1886_trc(
                    black, outoffset, trc, getcfg("synthprofile.trc_gamma_type")
                )
            else:
                profile.tags.kTRC.set_bt1886_trc(
                    black[1], outoffset, trc, getcfg("synthprofile.trc_gamma_type")
                )
        elif trc in (-2084, -2):
            # SMPTE 2084 or HLG
            hdr_format = "PQ" if trc == -2084 else "HLG"
            minmll = getcfg("3dlut.hdr_minmll")
            maxmll = (
                getcfg("3dlut.hdr_maxmll")
                if rolloff
                else getcfg("synthprofile.luminance")
            )
            if rgb:
                if trc == -2084:
                    profile.set_smpte2084_trc(
                        [
                            v * getcfg("synthprofile.luminance") * (1 - outoffset)
                            for v in black
                        ],
                        getcfg("synthprofile.luminance"),
                        minmll,
                        maxmll,
                        getcfg("3dlut.hdr_maxmll_alt_clip"),
                        rolloff=True,
                        blend_blackpoint=False,
                    )
                else:
                    profile.set_hlg_trc(
                        (0, 0, 0),
                        getcfg("synthprofile.luminance"),
                        1.2,
                        getcfg("3dlut.hdr_ambient_luminance"),
                        blend_blackpoint=False,
                    )
                if rolloff or trc == -2:
                    rgb_space = profile.get_rgb_space()
                    rgb_space[0] = 1.0  # gamma 1.0 (unused)
                    rgb_space = colormath.get_rgb_space(rgb_space)
                    linebuffered_logfiles = []
                    if (
                        sys.stdout
                        and hasattr(sys.stdout, "isatty")
                        and sys.stdout.isatty()
                    ):
                        linebuffered_logfiles.append(print)
                    else:
                        linebuffered_logfiles.append(LOG)
                    logfiles = Files(
                        [
                            LineBufferedStream(
                                FilteredStream(
                                    Files(linebuffered_logfiles),
                                    ENC,
                                    discard="",
                                    linesep_in="\n",
                                    triggers=[],
                                )
                            ),
                            self.worker.recent,
                            self.worker.lastmsg,
                        ]
                    )
                    quality = getcfg("profile.quality")
                    clutres = {"m": 17, "l": 9}.get(quality, 33)
                    hdr_clut_profile = create_synthetic_hdr_clut_profile(
                        hdr_format,
                        rgb_space,
                        "",
                        getcfg("synthprofile.black_luminance") * (1 - outoffset),
                        getcfg("synthprofile.luminance"),
                        minmll,
                        maxmll,
                        getcfg("3dlut.hdr_maxmll_alt_clip"),
                        1.2,
                        getcfg("3dlut.hdr_ambient_luminance"),
                        clutres=clutres,
                        sat=getcfg("3dlut.hdr_sat"),
                        hue=getcfg("3dlut.hdr_hue"),
                        generate_B2A=trc == -2,
                        worker=self.worker,
                        logfile=logfiles,
                        cat=self.cat,
                    )
                    profile.tags.A2B0 = hdr_clut_profile.tags.A2B0
                    if trc == -2:
                        profile.tags.B2A0 = hdr_clut_profile.tags.B2A0
                if black != [0, 0, 0] and outoffset and not bpc:
                    profile.apply_black_offset(black)
            else:
                if trc == -2084:
                    profile.tags.kTRC.set_smpte2084_trc(
                        getcfg("synthprofile.black_luminance") * (1 - outoffset),
                        getcfg("synthprofile.luminance"),
                        minmll,
                        maxmll,
                        getcfg("3dlut.hdr_maxmll_alt_clip"),
                        rolloff=True,
                    )
                else:
                    profile.tags.kTRC.set_hlg_trc(
                        0,
                        getcfg("synthprofile.luminance"),
                        1.2,
                        getcfg("3dlut.hdr_ambient_luminance"),
                    )
                if black != [0, 0, 0] and outoffset and not bpc:
                    profile.tags.kTRC.apply_bpc(black[1])
        elif black != [0, 0, 0]:
            vmin = 0 if rgb else black[1]
            for channel in channels:
                profile.tags[f"{channel}TRC"].set_trc(trc, 1024, vmin=vmin * 65535)
            if rgb:
                profile.apply_black_offset(black)
        else:
            for channel in channels:
                profile.tags[f"{channel}TRC"].set_trc(trc, 1)
        if black != [0, 0, 0] and bpc:
            if rgb:
                profile.apply_black_offset((0, 0, 0))
            else:
                profile.tags.kTRC.apply_bpc()
        for tagname in ("lumi", "bkpt"):
            if tagname == "lumi":
                X, Y, Z = [
                    (v / XYZ["wY"]) * getcfg("synthprofile.luminance")
                    for v in (XYZ["wX"], XYZ["wY"], XYZ["wZ"])
                ]
            else:
                X, Y, Z = (XYZ["kX"], XYZ["kY"], XYZ["kZ"])
            profile.tags[tagname] = XYZType()
            (
                profile.tags[tagname].X,
                profile.tags[tagname].Y,
                profile.tags[tagname].Z,
            ) = (X, Y, Z)
        if tech:
            if not isinstance(tech, bytes):
                tech = tech.encode("utf-8")
            profile.tags.tech = SignatureType(b"sig \0\0\0\0" + tech, "tech")
        if ciis:
            if not isinstance(ciis, bytes):
                ciis = ciis.encode("utf-8")
            profile.tags.ciis = SignatureType(b"sig \0\0\0\0" + ciis, "ciis")
        profile.setDescription(os.path.splitext(os.path.basename(path))[0])
        profile.calculate_id()
        try:
            profile.write(path)
        except Exception as exception:  # noqa: BLE001
            return exception
        return None

    # -- scripting ---------------------------------------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's file-opening commands.
        """
        return [
            *self.get_common_commands(),
            "synthprofile [filename]",
            "load <filename>",
        ]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"``, ``"fail"`` or ``"invalid"``.
        """
        return self.open_files_command(data, "synthprofile")

    # -- lifecycle ---------------------------------------------------------

    def closeEvent(self, event: object) -> None:  # noqa: N802
        """Persist settings and position before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait()
        config.writecfg(
            module="synthprofile",
            options=(
                "synthprofile.",
                "last_icc_path",
                "position.synthiccframe",
                "size.synthiccframe",
                "3dlut.hdr_",
            ),
        )
        super().closeEvent(event)


def main() -> int:
    """Entry point for the Qt synthetic ICC profile creator.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("synthprofile")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = SynthICCWindow()
    app.top_window = window
    window.show()
    window.listen()
    app.process_argv()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
