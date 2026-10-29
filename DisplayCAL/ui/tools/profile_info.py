"""Profile information / gamut viewer — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_profile_info`. It loads an ICC profile,
computes its gamut surface through Argyll's ``xicclu`` (off the GUI thread)
and shows it in a :class:`~DisplayCAL.ui.plot.gamut.GamutPlot` alongside a
profile-information panel, with colorspace, white-point, rendering-intent and
lookup-direction controls, an optional comparison-profile overlay, a
:class:`~DisplayCAL.ui.tools.curve_viewer.CurvePanel` tone-response view, and
3D (VRML/X3D/HTML) gamut export.
"""

from __future__ import annotations

import os
import sys

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config, x3dom
from DisplayCAL import localization as lang
from DisplayCAL.argyll import make_argyll_compatible_path
from DisplayCAL.config import get_data_path, getcfg, setcfg
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.plot.colorspaces import COLORSPACES
from DisplayCAL.ui.plot.curve_data import CURVE_MODES, available_curve_modes
from DisplayCAL.ui.plot.gamut import GamutPlot
from DisplayCAL.ui.plot.gamut_data import compute_profile_gamut, is_supported
from DisplayCAL.ui.theme import label_color
from DisplayCAL.ui.tools.curve_viewer import INTENTS, CurvePanel
from DisplayCAL.util_os import launch_file, make_win32_compatible_long_path, waccess
from DisplayCAL.worker import Worker

#: Profile file suffixes accepted for opening / drag-and-drop.
PROFILE_SUFFIXES = (".icc", ".icm")

#: Colour-temperature locus options: label -> draw_gamut code. "<None>" first
#: and labelled like the comparison-profile combo's no-selection entry.
WHITEPOINTS = {"<None>": 0, "Daylight (CIE 1931)": 1, "Black body (Planckian)": 2}

#: Gamut lookup directions: label -> compute_profile_gamut code.
DIRECTIONS = {
    "direction.forward": "f",
    "direction.backward.inverted": "ib",
}

#: The "no comparison profile" sentinel entry, first in the combo.
_NO_COMPARISON = "calibration.file.none"

#: Trailing combo entry that opens a file dialog for an arbitrary profile.
_BROWSE_COMPARISON = "browse"

#: This window's fixed background, matching wx's ``BGCOLOUR`` constant
#: (``wx_profile_info.py``) applied to its ``canvaspanel``/options/status
#: panels. Like the gamut plot (see ``ui/plot/gamut.py``), wx keeps this
#: dialog on its own fixed dark-grey scheme rather than following the OS
#: light/dark theme the rest of the Qt UI uses.
_BGCOLOUR = "#333333"


def _bounded_combo(contents_length: int = 16) -> QComboBox:
    """Return a size-bounded ``QComboBox``.

    Its width follows ``contents_length``, not its widest item. Profile
    descriptions and other combo items can be arbitrarily long; the
    default ``QComboBox`` sizing policy grows the widget to fit the widest
    item, which can force the whole window wider than the screen. The full
    text remains available in the dropdown popup.

    Args:
        contents_length (int): Target width in characters.

    Returns:
        QComboBox: The size-bounded combo box.
    """
    combo = QComboBox()
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(contents_length)
    return combo


class _GamutThread(QThread):
    """Compute one or two profiles' gamut samples off the GUI thread.

    Args:
        profile (ICCProfile): The primary profile to sample.
        comparison (ICCProfile | None): An optional comparison profile.
        worker (Worker): The worker driving ``xicclu``.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        direction (str): Lookup direction (``f``/``ib``).
        order (str): ``xicclu`` lookup order - ``n`` normal (prefers the
            profile's CLUT, if present) or ``r`` reverse (matrix/shaper only).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with ``(pcs_data, profile, comparison)`` or, on failure,
    #: ``(exception, None, None)``.
    done = Signal(object, object, object)

    def __init__(
        self,
        profile: ICCProfile,
        comparison: ICCProfile | None,
        worker: Worker,
        intent: str,
        direction: str,
        order: str = "n",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._comparison = comparison
        self._worker = worker
        self._intent = intent
        self._direction = direction
        self._order = order

    def run(self) -> None:
        try:
            pcs_data = [
                compute_profile_gamut(
                    self._profile,
                    self._worker,
                    self._intent,
                    self._direction,
                    self._order,
                )
            ]
            if self._comparison is not None:
                pcs_data.append(
                    compute_profile_gamut(
                        self._comparison,
                        self._worker,
                        self._intent,
                        self._direction,
                        self._order,
                    )
                )
            self.done.emit(pcs_data, self._profile, self._comparison)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception, None, None)
        finally:
            self._worker.wrapup(False)


class _Export3DThread(QThread):
    """Run the VRML gamut export (and optional X3D/HTML conversion) off-thread.

    Args:
        worker (Worker): The worker driving ``iccgamut``/``viewgam``.
        profile_paths (list[str]): Paths of the profile(s) to export.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        direction (str): Lookup direction (``f``/``ib``).
        vrml_path (str): The expected VRML output path.
        x3d_path (str): The X3D output path (used when ``fmt`` requests it).
        fmt (str): One of ``"VRML"``, ``"X3D"``, ``"HTML"``.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the final viewable path, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self,
        worker: Worker,
        profile_paths: list[str],
        intent: str,
        direction: str,
        vrml_path: str,
        x3d_path: str,
        fmt: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._profile_paths = profile_paths
        self._intent = intent
        self._direction = direction
        self._vrml_path = vrml_path
        self._x3d_path = x3d_path
        self._fmt = fmt

    def run(self) -> None:
        try:
            self._worker.calculate_gamut(
                self._profile_paths,
                self._intent,
                self._direction,
                "n",
                compare_standard_gamuts=False,
            )
            if not os.path.isfile(self._vrml_path):
                raise OSError(lang.getstr("file.missing", self._vrml_path))
            if self._fmt == "VRML":
                self.done.emit(self._vrml_path)
                return
            ok = x3dom.vrmlfile2x3dfile(
                self._vrml_path,
                self._x3d_path,
                html=self._fmt == "HTML",
                embed=getcfg("x3dom.embed"),
                cache=getcfg("x3dom.cache"),
                worker=self._worker,
            )
            if not ok:
                raise OSError(f"{lang.getstr('error.generic')}: {self._x3d_path}")
            final_path = (
                f"{self._x3d_path}.html" if self._fmt == "HTML" else self._x3d_path
            )
            self.done.emit(final_path)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception)
        finally:
            self._worker.wrapup(False)


class ProfileInfoWindow(BaseWindow):
    """Window showing a profile's gamut, tone response and information."""

    def __init__(self) -> None:
        super().__init__(
            name="profile-info",
            title=lang.getstr("profile.info"),
            icon_name=f"{APPNAME}-profile-info".lower(),
        )
        self.worker = Worker()
        self._thread: _GamutThread | None = None
        self._export_thread: _Export3DThread | None = None
        self._pcs_data: list[list[float]] = []
        self._profile: ICCProfile | None = None
        self._comparison_profile: ICCProfile | None = None

        self.colorspace_combo = QComboBox()
        self.colorspace_combo.addItems(list(COLORSPACES))
        self.colorspace_combo.setCurrentText("a*b*")
        self.colorspace_combo.currentTextChanged.connect(self._redraw)

        self.outline_check = QCheckBox(lang.getstr("colorspace.show_outline"))
        self.outline_check.setChecked(True)
        self.outline_check.toggled.connect(self._redraw)

        # Matches wx_profile_info.GamutViewOptions's defaults: no colour-temp
        # locus, absolute colorimetric intent (the LUT/curve view elsewhere
        # defaults to relative colorimetric instead; these are independent).
        self.whitepoint_combo = QComboBox()
        self.whitepoint_combo.addItems(list(WHITEPOINTS))
        self.whitepoint_combo.setCurrentText("<None>")
        self.whitepoint_combo.currentTextChanged.connect(self._redraw)

        self.intent_combo = QComboBox()
        for key in INTENTS:
            self.intent_combo.addItem(lang.getstr(key), INTENTS[key])
        self.intent_combo.setCurrentIndex(list(INTENTS.values()).index("a"))
        self.intent_combo.currentIndexChanged.connect(self._recompute)

        self.direction_combo = QComboBox()
        for key, code in DIRECTIONS.items():
            self.direction_combo.addItem(lang.getstr(key), code)
        self.direction_combo.currentIndexChanged.connect(self._recompute)

        # Gamut lookup order: use the profile's CLUT (A2B0/B2A0) if present,
        # or force the matrix/shaper path instead. Literal "LUT" label
        # (untranslated), matching wx GamutViewOptions.toggle_clut. Shown
        # only for profiles that actually have a CLUT to toggle to/from.
        self.gamut_clut_check = QCheckBox("LUT")
        self.gamut_clut_check.setToolTip(
            "Use the profile's CLUT for the gamut lookup, if present "
            "(unchecked uses the matrix/shaper path instead)"
        )
        self.gamut_clut_check.setChecked(True)
        self.gamut_clut_check.toggled.connect(self._recompute)

        # Comparison profile descriptions can be very long (e.g. "EBU 3213
        # (PAL) primaries with Rec709 transfer function"); cap the combo's
        # own width to that, not its widest item, so it doesn't force the
        # whole window wider than the screen. The full text is still
        # available in the dropdown popup and as a tooltip.
        self.comparison_combo = _bounded_combo(contents_length=22)
        self._comparison_profiles: dict[str, ICCProfile | None] = {}
        self._populate_comparison_profiles()
        self.comparison_combo.currentIndexChanged.connect(self._on_comparison_selected)

        # Single plot-mode combo, matching wx ``plot_mode_select``: one entry
        # per available tone-curve mode (vcgt / [rgb]TRC / measured) followed
        # by a trailing ``gamut`` entry. Populated per profile in
        # ``_populate_mode_combo``; gamut is always last.
        self.mode_combo = _bounded_combo(contents_length=8)
        self.mode_combo.addItem(lang.getstr("gamut"), "gamut")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        # Toolbar help (?) and save-plot buttons, matching wx's [?] [Save].
        self.help_button = QPushButton("?")
        self.help_button.setToolTip(lang.getstr("gamut_plot.tooltip"))
        self.help_button.clicked.connect(self._show_help)
        self.save_button = QPushButton(lang.getstr("save").rstrip("."))
        self.save_button.setToolTip(lang.getstr("save_as"))
        self.save_button.clicked.connect(self._save_plot)

        self.plot = GamutPlot()
        # Live mouse-position readout at the bottom of the plot (wx status bar).
        self.coords_label = QLabel("")
        self.coords_label.setAlignment(Qt.AlignCenter)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        # Gamut coverage summary (wx ``gamut_status``); empty unless the profile
        # carries ``GAMUT_coverage`` metadata.
        self.gamut_status_label = QLabel("")
        self.gamut_status_label.setAlignment(Qt.AlignCenter)

        self.info = self._build_info_table()
        # The embedded curve panel is driven by the shared mode combo above, so
        # hide its own mode selector. The "show actual LUT" checkbox reads back
        # the *live video-card LUT* (wx_lut_viewer's own feature, driven by
        # ``calibration.show_actual_lut``) - unrelated to this window's static
        # profile comparison, so it stays hidden here too. The comparison this
        # issue's wx counterpart offers (parametric TRC tags vs the profile's
        # actual CLUT-derived response) is instead available through the mode
        # combo's "[rgb]TRC" vs "measured" entries plus the panel's own "LUT"
        # checkbox (shown for "measured" mode on cLUT profiles). The cursor
        # readout is shown in this window's shared ``coords_label`` (same place
        # as the gamut view), not the panel's own, so hide the latter.
        self.curve_panel = CurvePanel(
            show_mode_selector=False, show_actual_lut=False, show_coords=False
        )
        self.curve_panel.cursor_moved.connect(self.coords_label.setText)

        self.view_3d_format_combo = _bounded_combo(contents_length=6)
        self.view_3d_format_combo.addItems(config.VALID_VALUES["3d.format"])
        self.view_3d_format_combo.setCurrentText(getcfg("3d.format"))
        self.view_3d_format_combo.currentTextChanged.connect(self._on_3d_format_changed)
        self.view_3d_button = QPushButton(lang.getstr("view.3d"))
        self.view_3d_button.clicked.connect(self._export_3d)

        self.setCentralWidget(self._build_central())
        # Match wx_profile_info's default window size (config
        # ``size.profile_info.split.w`` by ``size.profile_info.h``).
        self.resize(
            getcfg("size.profile_info.split.w") or 960,
            getcfg("size.profile_info.h") or 552,
        )

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(PROFILE_SUFFIXES, self.load_profile),
            parent=self,
        )
        self.droptarget.install_on(self)
        self.init_menubar()

    def _build_info_table(self) -> QTableWidget:
        """Build the profile-information table (property/value with row numbers).

        Qt equivalent of ``wx_profile_info``'s two-column grid: no column
        headers, row numbers down the left, non-editable, no selection.

        Returns:
            QTableWidget: The configured (empty) info table.
        """
        table = QTableWidget(0, 2)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(True)  # 1, 2, 3 … row numbers
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setAlternatingRowColors(True)
        table.setTextElideMode(Qt.ElideRight)
        # Property column: user-resizable with a sensible default (so it does
        # not grab all the width for the longest label and hide the values);
        # value column takes the rest.
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.resizeSection(0, 180)
        row_header = table.verticalHeader()
        row_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        # Drop the per-row divider lines the Fusion style draws on the
        # row-number sections (they render as thin white lines); keep a flat
        # palette-driven background so it still adapts to light/dark.
        row_header.setStyleSheet(
            "QHeaderView::section {"
            " border: none;"
            " background-color: palette(window);"
            " padding: 0 4px;"
            " }"
        )
        table.setMinimumWidth(320)
        return table

    def _marker(self, text: str) -> QLabel:
        """Return a small grey plot-legend marker label (e.g. ``—``, ``=``).

        Args:
            text (str): The marker glyph.

        Returns:
            QLabel: The styled marker label.
        """
        label = QLabel(text)
        label.setStyleSheet(f"color: {label_color(self).name()};")
        label.setAlignment(Qt.AlignCenter)
        return label

    def _build_gamut_controls(self) -> QGridLayout:
        """Build the gamut controls grid (legend, markers, labels, fields).

        Mirrors wx ``GamutViewOptions``: a whitepoint-marker legend row, then a
        narrow line-style-marker column, the labels and the fields — in the wx
        order (colorspace, show-outline, whitepoint locus, comparison, intent,
        direction).

        Returns:
            QGridLayout: The populated controls grid.
        """
        grid = QGridLayout()
        # Centre the control block: equal stretch spacer columns on both sides
        # (0 and 4), with marker (1), label (2) and fixed-width field (3) in the
        # middle — so the group sits centred with equal left/right gaps, like
        # wx's fixed-width combos rather than filling the pane.
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(4, 1)

        # Whitepoint legend, split so the comparison (cross) part can be hidden
        # independently of the profile (plus) part (wx whitepoint_legend vs.
        # comparison_whitepoint_legend).
        self.whitepoint_legend = QLabel(f"+  {lang.getstr('whitepoint')}")
        self.comparison_whitepoint_legend = QLabel(
            "×  {} ({})".format(  # noqa: RUF001 (cross marker glyph)
                lang.getstr("whitepoint"),
                lang.getstr("comparison_profile"),
            )
        )
        for legend in (self.whitepoint_legend, self.comparison_whitepoint_legend):
            legend.setStyleSheet(f"color: {label_color(self).name()};")
        legend_row = QHBoxLayout()
        legend_row.addStretch(1)
        legend_row.addWidget(self.whitepoint_legend)
        legend_row.addSpacing(20)
        legend_row.addWidget(self.comparison_whitepoint_legend)
        legend_row.addStretch(1)
        grid.addLayout(legend_row, 0, 1, 1, 3)

        # Line-style markers kept as attributes so their visibility can track
        # the relevant control (wx colorspace_outline_bmp / whitepoint_bmp /
        # comparison_profile_bmp).
        self.colorspace_marker = self._marker("—")
        self.whitepoint_marker = self._marker("—")
        self.comparison_marker = self._marker("=")

        rows = [
            (self.colorspace_marker, lang.getstr("colorspace"), self.colorspace_combo),
            (None, "", self.outline_check),
            (
                self.whitepoint_marker,
                lang.getstr("whitepoint.colortemp.locus.curve"),
                self.whitepoint_combo,
            ),
            (
                self.comparison_marker,
                lang.getstr("comparison_profile"),
                self.comparison_combo,
            ),
            (None, lang.getstr("rendering_intent"), self.intent_combo),
            # wx order: LUT toggle right after rendering intent, before the
            # direction combo.
            (None, "", self.gamut_clut_check),
            # wx gives the gamut direction combo no label; its items
            # ("Device → A2B → PCS" …) are self-describing.
            (None, "", self.direction_combo),
        ]
        for field in (
            self.colorspace_combo,
            self.whitepoint_combo,
            self.comparison_combo,
            self.intent_combo,
            self.direction_combo,
        ):
            field.setMinimumWidth(240)
        for row, (marker, label, field) in enumerate(rows, start=1):
            if marker is not None:
                grid.addWidget(marker, row, 1)
            if label:
                grid.addWidget(QLabel(label), row, 2)
            grid.addWidget(field, row, 3)
        self._update_gamut_legend()
        return grid

    def _update_gamut_legend(self) -> None:
        """Show/hide the gamut legend markers to match wx.

        * colorspace outline marker — only when "show outline" is checked,
        * whitepoint locus marker — only when a colour-temperature locus is set,
        * comparison marker and its comparison-whitepoint legend — only when a
          comparison profile is selected.
        * gamut CLUT toggle — only for profiles that actually have a CLUT
          (``A2B0``/``B2A0``) to toggle to/from.
        """
        self.colorspace_marker.setVisible(self.outline_check.isChecked())
        has_locus = WHITEPOINTS.get(self.whitepoint_combo.currentText(), 0) != 0
        self.whitepoint_marker.setVisible(has_locus)
        has_comparison = self._comparison_profile is not None
        self.comparison_marker.setVisible(has_comparison)
        self.comparison_whitepoint_legend.setVisible(has_comparison)
        has_clut = bool(
            self._profile
            and ("A2B0" in self._profile.tags or "B2A0" in self._profile.tags)
        )
        self.gamut_clut_check.setVisible(has_clut)

    def _build_central(self) -> QWidget:
        """Assemble the toolbar, plot/curve views, controls and info table.

        Matches wx_profile_info.ProfileInfoFrame's layout: a splitter with the
        plot (gamut or curves) on the left — a small toolbar above it and the
        mode-specific controls stacked one-per-row below it — and the
        profile-info table as a separate column on the right.

        Returns:
            QWidget: The central widget holding the toolbar, views and table.
        """
        # Top toolbar: all controls kept together and centred, in wx order —
        # [mode] [?] [Save] [3D view] [format v].
        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        toolbar.addWidget(self.mode_combo)
        toolbar.addWidget(self.help_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.view_3d_button)
        toolbar.addWidget(self.view_3d_format_combo)
        toolbar.addStretch(1)
        # Give every toolbar control the same height (native combos and buttons
        # otherwise report slightly different heights).
        toolbar_widgets = (
            self.mode_combo,
            self.help_button,
            self.save_button,
            self.view_3d_format_combo,
            self.view_3d_button,
        )
        toolbar_height = max(w.sizeHint().height() for w in toolbar_widgets)
        for widget in toolbar_widgets:
            widget.setFixedHeight(toolbar_height)

        gamut_layout = QVBoxLayout()
        gamut_layout.setContentsMargins(0, 0, 0, 0)
        gamut_layout.addWidget(self.plot, 1)
        gamut_layout.addLayout(self._build_gamut_controls())

        gamut_page = QWidget()
        gamut_page.setLayout(gamut_layout)

        self.views = QStackedWidget()
        self.views.addWidget(gamut_page)
        self.views.addWidget(self.curve_panel)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(toolbar)
        left_layout.addWidget(self.views, 1)
        left_layout.addWidget(self.coords_label)  # mouse readout, bottom
        left_layout.addWidget(self.gamut_status_label)  # gamut coverage summary

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.info)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        # A default-width handle is nearly invisible against this dialog's
        # dark background, making the table hard to discover as resizable.
        # Widen it and give it a distinct colour (plus a hover highlight) so
        # the divider itself reads as a grabbable splitter.
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            "QSplitter::handle {"
            " background-color: #555555;"
            " border-left: 1px solid #222222;"
            " border-right: 1px solid #222222;"
            "}"
            "QSplitter::handle:hover {"
            " background-color: #777777;"
            "}"
        )

        central = QWidget(self)
        # Paint this dialog's own fixed background (wx's BGCOLOUR, matching
        # the gamut canvas) behind the native controls, which draw over it —
        # not the app-wide themed palette, which is darker and follows the OS
        # light/dark setting that this dialog doesn't. Setting the colour
        # directly on the widget's own palette (rather than
        # ``setAutoFillBackground`` alone, which paints whatever the
        # inherited/app palette's Window colour is) is what makes it stick
        # regardless of the app theme.
        central.setAutoFillBackground(True)
        palette = central.palette()
        palette.setColor(QPalette.Window, QColor(_BGCOLOUR))
        central.setPalette(palette)
        layout = QVBoxLayout(central)
        layout.addWidget(splitter, 1)
        return central

    def _populate_comparison_profiles(self) -> None:
        """Fill the comparison combo with "none", sRGB, standard profiles."""
        self._comparison_profiles = {lang.getstr(_NO_COMPARISON): None}
        try:
            srgb = ICCProfile(get_data_path("ref/sRGB.icm"))
        except Exception:  # noqa: BLE001  (best-effort default entry)
            srgb = None
        if srgb:
            self._comparison_profiles[srgb.getDescription()] = srgb
        for profile in config.get_standard_profiles():
            desc = profile.getDescription()
            if desc not in self._comparison_profiles:
                self._comparison_profiles[desc] = profile
        self.comparison_combo.blockSignals(True)
        self.comparison_combo.clear()
        self.comparison_combo.addItems(list(self._comparison_profiles))
        self.comparison_combo.addItem(lang.getstr("file.select") + "…")
        self.comparison_combo.blockSignals(False)

    # -- loading -------------------------------------------------------------

    def load_profile(self, path: str) -> None:
        """Load the profile at ``path`` and start computing its gamut.

        Args:
            path (str): Path to the ICC profile to load.
        """
        if self._thread is not None and self._thread.isRunning():
            return
        try:
            profile = ICCProfile(path)
        except Exception as exception:  # noqa: BLE001
            self._show_error(f"{lang.getstr('error')}: {exception}")
            return
        self._show_info(profile, computing=True)
        self.curve_panel.set_profile(profile)
        self._populate_mode_combo(profile)
        if not is_supported(profile):
            self._show_info(profile, computing=False)
            return
        self.setWindowTitle(
            f"{lang.getstr('profile.info')} — {profile.getDescription()}"
        )
        self._profile = profile
        # A freshly loaded profile defaults back to preferring its CLUT
        # (matches wx, which resets this per profile rather than remembering
        # a prior profile's unchecked state).
        self.gamut_clut_check.blockSignals(True)
        self.gamut_clut_check.setChecked(True)
        self.gamut_clut_check.blockSignals(False)
        self._recompute()

    def _on_comparison_selected(self, index: int) -> None:
        """Handle a comparison-profile combo selection.

        Args:
            index (int): The newly selected combo index.
        """
        if index == self.comparison_combo.count() - 1:
            # "Browse…" — pick a file, or revert to "none" if cancelled.
            default_dir, default_file = config.get_verified_path("last_icc_path")
            default_path = (
                os.path.join(default_dir, default_file) if default_file else default_dir
            )
            path, _ = file_dialog.get_open_file_name(
                self,
                lang.getstr("profile.choose"),
                default_path,
                lang.getstr("filetype.icc") + " (*.icc *.icm)",
            )
            if not path:
                self.comparison_combo.blockSignals(True)
                self.comparison_combo.setCurrentIndex(0)
                self.comparison_combo.blockSignals(False)
                self.comparison_combo.setToolTip(self.comparison_combo.currentText())
                self._comparison_profile = None
                self._recompute()
                return
            try:
                profile = ICCProfile(path)
            except Exception as exception:  # noqa: BLE001
                message_box.critical(self, self.windowTitle(), str(exception))
                self.comparison_combo.blockSignals(True)
                self.comparison_combo.setCurrentIndex(0)
                self.comparison_combo.blockSignals(False)
                self.comparison_combo.setToolTip(self.comparison_combo.currentText())
                self._comparison_profile = None
                self._recompute()
                return
            config.setcfg("last_icc_path", path)
            desc = profile.getDescription()
            self._comparison_profiles[desc] = profile
            self.comparison_combo.blockSignals(True)
            self.comparison_combo.insertItem(self.comparison_combo.count() - 1, desc)
            self.comparison_combo.setCurrentIndex(self.comparison_combo.count() - 2)
            self.comparison_combo.blockSignals(False)
            self._comparison_profile = profile
        else:
            desc = self.comparison_combo.itemText(index)
            self._comparison_profile = self._comparison_profiles.get(desc)
        self.comparison_combo.setToolTip(self.comparison_combo.currentText())
        self._recompute()

    def _recompute(self) -> None:
        """Recompute the gamut(s) for the current profile/intent/direction."""
        self._update_gamut_legend()
        if self._profile is None or not is_supported(self._profile):
            return
        if self._thread is not None and self._thread.isRunning():
            return
        self._show_info(self._profile, computing=True)
        self._thread = _GamutThread(
            self._profile,
            self._comparison_profile,
            self.worker,
            self.intent_combo.currentData(),
            self.direction_combo.currentData(),
            "n" if self.gamut_clut_check.isChecked() else "r",
            parent=self,
        )
        self._thread.done.connect(self._on_gamut_ready)
        self._thread.start()

    def _on_gamut_ready(
        self, result: object, profile: object, comparison: object
    ) -> None:
        """Receive computed gamut data on the GUI thread and draw it.

        Args:
            result (object): The gamut ``pcs_data`` list, or an ``Exception``
                on failure.
            profile (object): The primary profile the gamut was computed for
                (or ``None`` on failure).
            comparison (object): The comparison profile, if any (or ``None``).
        """
        self._thread = None
        if isinstance(result, Exception):
            self._show_error(f"{lang.getstr('error')}: {result}")
            return
        self._pcs_data = result
        profiles = {0: profile}
        if comparison is not None:
            profiles[1] = comparison
        self.plot.set_data(result, profiles=profiles)
        self._show_info(profile, computing=False)
        self.gamut_status_label.setText(self._gamut_coverage_text(profile))
        self._redraw()

    @staticmethod
    def _gamut_coverage_text(profile: ICCProfile) -> str:
        """Return the gamut-coverage summary from a profile's metadata.

        Args:
            profile (ICCProfile): The profile whose ``GAMUT_coverage`` metadata
                to read.

        Returns:
            str: A summary like ``"99.9% sRGB    78.4% Adobe RGB …"``, or an
            empty string when the profile carries no coverage metadata.
        """
        meta = profile.tags.get("meta")
        if not meta:
            return ""
        parts = []
        for key, name in (
            ("srgb", "sRGB"),
            ("adobe-rgb", "Adobe RGB"),
            ("dci-p3", "DCI P3"),
        ):
            try:
                coverage = meta.getvalue(f"GAMUT_coverage({key})")
                coverage = float(coverage) if coverage is not None else None
            except (TypeError, ValueError):
                coverage = None
            if coverage:
                parts.append(f"{coverage * 100:.1f}% {name}")
        return "    ".join(parts)

    # -- view ------------------------------------------------------------

    def _redraw(self) -> None:
        """Redraw the gamut for the current control selections."""
        self._update_gamut_legend()
        if not self._pcs_data:
            return
        self.plot.draw_gamut(
            colorspace=self.colorspace_combo.currentText(),
            whitepoint=WHITEPOINTS[self.whitepoint_combo.currentText()],
            show_outline=self.outline_check.isChecked(),
        )

    def _populate_mode_combo(self, profile: ICCProfile) -> None:
        """Rebuild the plot-mode combo for ``profile`` (curve modes + gamut).

        Mirrors wx ``plot_mode_select``: one entry per available tone-curve
        mode (vcgt / [rgb]TRC / measured), then a trailing ``gamut`` entry.
        Preserves the current selection where possible, else falls back to
        gamut (the last entry), as in wx.

        Args:
            profile (ICCProfile): The profile whose modes to offer.
        """
        previous = self.mode_combo.currentData()
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        for mode in available_curve_modes(profile):
            label = lang.getstr(CURVE_MODES[mode], default="Measured tone response")
            self.mode_combo.addItem(label, mode)
        self.mode_combo.addItem(lang.getstr("gamut"), "gamut")
        index = self.mode_combo.findData(previous)
        self.mode_combo.setCurrentIndex(
            index if index >= 0 else self.mode_combo.count() - 1
        )
        self.mode_combo.blockSignals(False)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        """Switch the central stack to the gamut or curve view for the mode.

        Gamut mode shows the gamut page and its 3D-export controls; a curve
        mode shows the embedded ``CurvePanel`` driven to that mode and hides
        the 3D controls — matching wx ``plot_mode_select``. Each page owns its
        own controls, so switching pages hides/shows them automatically.
        """
        mode = self.mode_combo.currentData()
        is_gamut = mode == "gamut"
        self.views.setCurrentIndex(0 if is_gamut else 1)
        self.view_3d_button.setVisible(is_gamut)
        self.view_3d_format_combo.setVisible(is_gamut)
        # Clear the shared readout so the previous view's last cursor position
        # doesn't linger until the mouse moves over the newly shown plot.
        self.coords_label.setText("")
        if not is_gamut:
            self.curve_panel.set_mode(mode)

    def _on_mouse_moved(self, pos: object) -> None:
        """Update the coordinate readout as the mouse moves over the plot.

        Args:
            pos (object): The scene position emitted by pyqtgraph.
        """
        plot_item = self.plot.getPlotItem()
        if plot_item.sceneBoundingRect().contains(pos):
            point = plot_item.vb.mapSceneToView(pos)
            self.coords_label.setText(f"{point.x():.2f}   {point.y():.2f}")
        else:
            self.coords_label.setText("")

    def _show_info(self, profile: ICCProfile, computing: bool) -> None:
        """Populate the information table from ``profile``.

        Mirrors the wx grid: two columns (property, value) with row numbers in
        the vertical header. Section rows (``value == ""``) show the label only.

        Args:
            profile (ICCProfile): The profile to describe.
            computing (bool): Whether a gamut computation is in progress (adds a
                "please wait" note).
        """
        rows = list(profile.get_info())
        if computing:
            rows.append((lang.getstr("please_wait"), ""))
        grey = label_color(self)
        self.info.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            # Property (label) column uses the grey secondary text colour, as
            # in wx; the value column keeps the palette's primary text colour.
            label_item = QTableWidgetItem(str(label))
            label_item.setForeground(grey)
            self.info.setItem(row, 0, label_item)
            self.info.setItem(row, 1, QTableWidgetItem(str(value)))

    def _show_error(self, message: str) -> None:
        """Show a one-line error in the information table.

        Args:
            message (str): The error message to display.
        """
        self.info.setRowCount(1)
        self.info.setItem(0, 0, QTableWidgetItem(message))
        self.info.setItem(0, 1, QTableWidgetItem(""))

    # -- toolbar -----------------------------------------------------------

    def _show_help(self) -> None:
        """Show the plot navigation help (the wx ``?`` tooltip button)."""
        message_box.information(
            self, self.windowTitle(), lang.getstr("gamut_plot.tooltip")
        )

    def _save_plot(self) -> None:
        """Save the current plot view as an image (the wx ``Save`` button)."""
        # Grab whichever plot is showing (gamut page vs the curve panel).
        target = self.plot if self.views.currentIndex() == 0 else self.curve_panel.plot
        default = f"{self.mode_combo.currentText()}.png"
        path, _ = file_dialog.get_save_file_name(
            self,
            lang.getstr("save_as"),
            default,
            "PNG (*.png);;JPEG (*.jpg)",
        )
        if not path:
            return
        pixmap = target.grab()
        if not pixmap.save(path):
            message_box.warning(
                self, self.windowTitle(), lang.getstr("error.file.create", path)
            )

    # -- 3D export -------------------------------------------------------

    def _on_3d_format_changed(self, fmt: str) -> None:
        """Persist the selected 3D export format.

        Args:
            fmt (str): The newly selected format (``VRML``/``X3D``/``HTML``).
        """
        setcfg("3d.format", fmt)

    def _export_3d(self) -> None:
        """Export the current gamut (and comparison, if any) to VRML/X3D/HTML."""
        if self._profile is None:
            return
        if self._export_thread is not None and self._export_thread.isRunning():
            return
        try:
            profile_path = self._writable_profile_path(self._profile)
            profile_paths = [profile_path]
            if self._comparison_profile is not None:
                profile_paths.append(
                    self._writable_profile_path(self._comparison_profile)
                )
        except OSError as exception:
            message_box.critical(self, self.windowTitle(), str(exception))
            return

        intent = self.intent_combo.currentData()
        direction = self.direction_combo.currentData()
        mods = "".join(
            f"[{mod.upper()}]" for mod in (intent, direction) if mod not in ("r", "f")
        )
        name = os.path.splitext(profile_paths[0])[0]
        if mods:
            name = f"{name} {mods}"
        vrml_ext = ".wrz" if getcfg("vrml.compress") else ".wrl"
        vrml_path = f"{name}{vrml_ext}"
        x3d_path = f"{name}.x3d"
        if sys.platform == "win32":
            vrml_path = make_win32_compatible_long_path(vrml_path)
            x3d_path = make_win32_compatible_long_path(x3d_path)

        fmt = self.view_3d_format_combo.currentText()
        self.view_3d_button.setEnabled(False)
        self._export_thread = _Export3DThread(
            self.worker,
            profile_paths,
            intent,
            direction,
            vrml_path,
            x3d_path,
            fmt,
            parent=self,
        )
        self._export_thread.done.connect(self._on_3d_export_done)
        self._export_thread.start()

    def _writable_profile_path(self, profile: ICCProfile) -> str:
        """Return a filesystem path for ``profile``, writing it out if needed.

        Args:
            profile (ICCProfile): The profile to locate/write.

        Returns:
            str: A path to the profile in a directory Argyll can write its
            gamut/VRML output to.

        Raises:
            OSError: If a temporary directory could not be created.
        """
        path = profile.filename
        if path and os.path.isfile(path) and waccess(os.path.dirname(path), os.W_OK):
            return path
        result = self.worker.create_tempdir()
        if isinstance(result, Exception):
            raise OSError(str(result)) from result
        desc = profile.getDescription()
        path = os.path.join(
            self.worker.tempdir,
            f"{make_argyll_compatible_path(desc, is_name=True)}{config.PROFILE_EXT}",
        )
        profile.write(path)
        return path

    def _on_3d_export_done(self, result: object) -> None:
        """Handle the background 3D export result on the GUI thread.

        Args:
            result (object): The viewable output path, or an ``Exception`` on
                failure.
        """
        self.view_3d_button.setEnabled(True)
        self._export_thread = None
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
            return
        launch_file(result)

    # -- scripting ---------------------------------------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's file-opening commands.
        """
        return [
            *self.get_common_commands(),
            "profile-info [filename]",
            "load <filename>",
        ]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"``, ``"fail"`` or ``"invalid"``.
        """
        return self.open_files_command(data, "profile-info")


def main() -> int:
    """Entry point for the Qt profile information viewer.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("profile-info")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = ProfileInfoWindow()
    app.top_window = window
    window.show()
    window.listen()

    profiles = [a for a in sys.argv[1:] if os.path.isfile(a)]
    window.load_profile(profiles[0] if profiles else get_data_path("ref/sRGB.icm"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
