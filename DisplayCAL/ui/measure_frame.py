"""Measurement-area frame — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_measure_frame`. ``MeasureFrame`` is the
small rectangular window that represents the *measurement area* handed to
Argyll's ``dispcal`` / ``dispread``: the user sizes and positions it on the
target display (zoom in/out/normal/max, centre) and its geometry is stored, in
Argyll's relative ``x,y,scale`` coordinates (``0.0..1.0`` for position, up to
``50`` for scale), under the ``dimensions.measureframe`` config keys. It also
doubles as a software pattern window (:meth:`MeasureFrame.show_rgb`) and can hide
its controls to present a clean patch during measurement
(:meth:`MeasureFrame.show_controls`).

The relative<->pixel geometry maths is the load-bearing part and is toolkit
neutral, so it is factored out into the module-level
:func:`compute_frame_geometry` / :func:`compute_dimensions` /
:func:`default_measureframe_size` functions (unit-tested without a screen). The
window itself uses Qt ``QScreen`` for display enumeration in place of
``wx.Display``, and native widgets for the controls.

Parent integration is exposed as the :attr:`MeasureFrame.measure_requested`
signal rather than the wx tool's direct ``self.Parent.call_pending_function()``
call, so the not-yet-ported Qt main window can wire the Measure button to its
measurement flow later; run standalone (``python -m
DisplayCAL.ui.measure_frame``) the signal just closes the window. The wx-only
DPI-correction hack (``_last_set_size``) and the multi-X-screen / TwinView
display heuristics in ``get_display`` are dropped, matching the simplifications
the other ported tools made (Qt handles high-DPI in logical coordinates).
"""

from __future__ import annotations

import math
import sys
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QIcon, QImage, QPainter
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import (
    DEFAULTS,
    SCALE_ADJUSTMENT_FACTOR,
    get_argyll_display_number,
    getcfg,
    setcfg,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_themed_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.theme import is_dark
from DisplayCAL.util_list import strlist
from DisplayCAL.worker import Worker

try:
    from DisplayCAL import real_display_size_mm
except ImportError:
    real_display_size_mm = None

if TYPE_CHECKING:
    from qtpy.QtGui import (
        QCloseEvent,
        QHideEvent,
        QMoveEvent,
        QPaintEvent,
        QScreen,
        QShowEvent,
    )


# -- toolkit-neutral geometry maths (extracted from wx place_n_zoom /
#    get_dimensions so it can be unit-tested without a screen) ----------------


def default_measureframe_size(
    display_size_px: tuple[int, int], display_size_mm: tuple[float, float]
) -> int:
    """Return the 100x100 mm default patch size, in pixels, for a display.

    Mirrors ``wx_measure_frame.get_default_size``: the default patch is always
    100 mm square, converted to pixels via the display's physical size.

    Args:
        display_size_px (tuple[int, int]): Display size in pixels (w, h).
        display_size_mm (tuple[float, float]): Display size in millimetres.

    Returns:
        int: The 100 mm patch edge length in pixels.
    """
    px_per_mm = max(
        display_size_px[0] / display_size_mm[0],
        display_size_px[1] / display_size_mm[1],
    )
    return round(100.0 * px_per_mm)


def resolve_screen_size_mm(
    screen: QScreen, geometry: tuple[int, int, int, int]
) -> list[float] | None:
    """Resolve a screen's physical size in millimetres, or ``None`` if unknown.

    Shared by :class:`MeasureFrame` and other windows that need a
    physically-sized default (e.g. :class:`~DisplayCAL.ui.main_window
    ._LuminancePatchWindow`). Tries Argyll's ``real_display_size_mm`` first,
    falling back to Qt's own per-screen physical-size query -- the
    equivalent of wx's ``wx.DisplaySizeMM()`` fallback in
    ``wx_measure_frame.get_default_size()`` -- since ``real_display_size_mm``
    only resolves on Wayland and returns ``(0, 0)`` on macOS/Windows.

    Args:
        screen (QScreen): The screen to measure.
        geometry (tuple[int, int, int, int]): That screen's ``(x, y, w, h)``
            pixel geometry, used to look up its Argyll display number.

    Returns:
        list[float] | None: ``[width_mm, height_mm]``, or ``None`` if
        neither source could resolve a non-zero size.
    """
    if real_display_size_mm is not None:
        display_no = get_argyll_display_number(geometry)
        if display_no is not None:
            try:
                size_mm = real_display_size_mm.real_display_size_mm(display_no)
            except Exception:
                size_mm = None
            if size_mm and 0 not in size_mm:
                return [float(v) for v in size_mm]
    physical = screen.physicalSize()
    if physical.width() and physical.height():
        return [physical.width(), physical.height()]
    return None


def compute_frame_geometry(
    x: float,
    y: float,
    scale: float,
    display_rect: tuple[int, int, int, int],
    client_rect: tuple[int, int, int, int],
    default_size: float,
    min_size: int,
    titlebar: int,
) -> tuple[int, tuple[int, int], float]:
    """Convert relative Argyll coordinates to a pixel size and position.

    Extracted from ``wx_measure_frame.MeasureFrame.place_n_zoom``.

    Args:
        x (float): Relative horizontal position (0.0..1.0).
        y (float): Relative vertical position (0.0..1.0).
        scale (float): Requested scale (up to 50.0, Argyll's maximum).
        display_rect (tuple[int, int, int, int]): Full display geometry
            (x, y, w, h).
        client_rect (tuple[int, int, int, int]): Usable display area
            (x, y, w, h).
        default_size (float): 100 mm patch edge in pixels for this display.
        min_size (int): Minimum square edge needed to fit the controls.
        titlebar (int): Assumed title-bar height to offset the frame by.

    Returns:
        tuple[int, tuple[int, int], float]: The square edge length in pixels,
        the (x, y) top-left position in pixels, and the effective scale to
        persist to config.
    """
    scale = min(scale, 50.0)  # Argyll max
    scale /= float(SCALE_ADJUSTMENT_FACTOR)
    client_size = client_rect[2:]
    size = [
        min(client_size[0], default_size * scale),
        min(client_size[1], default_size * scale),
    ]
    if min_size > size[0]:
        size = [min_size, min_size]
    size[0] = min(size[0], client_size[0])
    size[1] = min(size[1], client_size[1])
    if max(size) >= max(client_size):
        scale = 50
    side = int(max(size))
    display_size = display_rect[2:]
    pos = [
        display_rect[0] + round((display_size[0] - side) * x),
        display_rect[1] + round((display_size[1] - side) * y) - titlebar,
    ]
    pos[0] = max(pos[0], client_rect[0])
    pos[1] = max(pos[1], client_rect[1])
    return side, (pos[0], pos[1]), scale


def compute_dimensions(
    size: tuple[int, int],
    screen_pos: tuple[int, int],
    display_rect: tuple[int, int, int, int],
    client_rect: tuple[int, int, int, int],
    default_size: float,
    titlebar: int,
) -> str:
    """Convert a pixel size and position back to relative Argyll coordinates.

    Extracted from ``wx_measure_frame.MeasureFrame.get_dimensions``.

    Args:
        size (tuple[int, int]): Current window size in pixels (w, h).
        screen_pos (tuple[int, int]): Current window top-left in screen pixels.
        display_rect (tuple[int, int, int, int]): Full display geometry.
        client_rect (tuple[int, int, int, int]): Usable display area.
        default_size (float): 100 mm patch edge in pixels for this display.
        titlebar (int): Assumed title-bar height.

    Returns:
        str: ``"x,y,scale"`` in Argyll relative coordinates.
    """
    display_size = display_rect[2:]
    client_size = client_rect[2:]
    pos = [
        float(screen_pos[0]) - display_rect[0],
        float(screen_pos[1]) - display_rect[1],
    ]
    width = float(size[0])
    height = float(size[1])
    if max(width, height) >= max(client_size) - 50:
        # Fullscreen?
        scale = 50.0  # Argyll max is 50
        pos = [0.5, 0.5]
    else:
        scale = width / default_size
        scale *= float(SCALE_ADJUSTMENT_FACTOR)
        if width >= client_size[0]:
            pos[0] = 0.5
        elif pos[0] != 0:
            pos[0] = min(pos[0], display_size[0] - width)
            pos[0] = 1.0 / ((float(display_size[0]) - width) / pos[0])
        if height >= client_size[1]:
            pos[1] = 0.5
        elif pos[1] != 0:
            pos[1] = min(pos[1], display_size[1] - height)
            pos[1] = 1.0 / (
                (float(display_size[1] - height)) / (float(pos[1] + titlebar))
            )
    return ",".join(str(max(0, n)) for n in [*pos, scale])


def _dither_rgb_image(
    width: int,
    height: int,
    values: tuple[float, float, float],
    floor: tuple[int, int, int],
    ceil: tuple[int, int, int],
) -> QImage:
    """Build an ordered-dithered 8-bit patch for a fractional RGB value.

    Mirrors the intent of ``wx_measure_frame.MeasureFrame.show_rgb``'s dither:
    for each channel a ``value - floor`` fraction of pixels are bumped from
    ``floor`` to ``ceil`` in a regular spatial pattern, so the average is the
    exact requested (sub-integer) level.

    Args:
        width (int): Patch width in pixels.
        height (int): Patch height in pixels.
        values (tuple[float, float, float]): Exact per-channel 8-bit levels.
        floor (tuple[int, int, int]): Per-channel floor of ``values``.
        ceil (tuple[int, int, int]): Per-channel ceil of ``values``.

    Returns:
        QImage: An ``RGB888`` image detached from its backing buffer.
    """
    import numpy as np

    count = width * height
    index = np.arange(count)
    pixels = np.empty((count, 3), dtype=np.uint8)
    for channel in range(3):
        frac = values[channel] - floor[channel]
        if frac <= 0:
            pixels[:, channel] = floor[channel]
        else:
            select = np.floor((index + 1) * frac) > np.floor(index * frac)
            pixels[:, channel] = np.where(select, ceil[channel], floor[channel])
    pixels = np.ascontiguousarray(pixels.reshape(height, width, 3))
    image = QImage(pixels.data, width, height, 3 * width, QImage.Format_RGB888)
    return image.copy()  # detach from the numpy buffer


# -- widgets ------------------------------------------------------------------


def _icon_button(name: str, tooltip: str, *, dark: bool) -> QToolButton:
    """Return a small flat tool button with a themed 16px icon.

    Args:
        name (str): Themed icon base name.
        tooltip (str): The button tooltip.
        dark (bool): Whether the app is in its dark scheme -- the zoom/center
            glyphs are plain gray monochrome icons designed for a light
            background (like wx's), so without recoloring them the same way
            :meth:`MainWindow._pixmap` does for the rest of the app, they are
            nearly invisible against a dark window.

    Returns:
        QToolButton: The configured button.
    """
    button = QToolButton()
    pixmap = get_themed_pixmap(16, name, dark)
    if not pixmap.isNull():
        button.setIcon(QIcon(pixmap))
    button.setAutoRaise(True)
    button.setToolTip(tooltip)
    return button


class _MeasurePanel(QWidget):
    """Central widget that hosts the controls and paints the measured patch.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self._image: QImage | None = None
        self._color: QColor | None = None

    def set_image(self, image: QImage) -> None:
        """Fill the panel with a dithered image and repaint.

        Args:
            image (QImage): The image to display.
        """
        self._image = image
        self._color = None
        self.update()

    def set_color(self, color: QColor) -> None:
        """Fill the panel with a solid colour and repaint.

        Args:
            color (QColor): The colour to display.
        """
        self._color = color
        self._image = None
        self.update()

    def clear_fill(self) -> None:
        """Drop any patch fill and revert to the themed background."""
        self._image = None
        self._color = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Paint the patch fill, if any, over the whole panel.

        Args:
            event (QPaintEvent): The Qt paint event.
        """
        if self._image is None and self._color is None:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        if self._image is not None:
            painter.drawImage(self.rect(), self._image)
        else:
            painter.fillRect(self.rect(), self._color)


class MeasureFrame(BaseWindow):
    """The measurement-area window.

    Args:
        parent (QWidget | None): Optional parent window.
    """

    #: Process exit code for the standalone tool, matching the wx module.
    exitcode = 1

    #: Emitted when the Measure button is pressed. The Qt main window connects
    #: this to its measurement flow; standalone it just closes the window.
    measure_requested = Signal()

    #: Emitted after :meth:`show_rgb` has painted a pattern, so a pattern
    #: generator can await display.
    pattern_shown = Signal()

    #: Emitted when the user closes the frame directly (X button / window
    #: manager close) rather than by pressing Measure, once :attr:`close_guard`
    #: (if any) has allowed it. The owner uses this to bring itself back,
    #: mirroring wx's ``MeasureFrame.close_handler`` hide+show pair.
    frame_closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent=parent,
            name="measureframe",
            title=lang.getstr("measureframe.title"),
            icon_name=APPNAME.lower(),
        )
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        if not config.is_ui_native_wayland() and getcfg(
            "patterngenerator.use_pattern_window"
        ):
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.display_size_mm: dict[tuple[int, int, int, int], list[float]] = {}
        # Argyll's X11 test window is sized from the X screen, so its density
        # takes precedence over the monitor's own size where there is one
        self.x_screen_px_per_mm = (
            real_display_size_mm.get_x_screen_px_per_mm()
            if real_display_size_mm is not None
            else None
        )
        self.default_size = float(DEFAULTS.get("size.measureframe", 300))
        self._current_geometry: tuple[int, int, int, int] | None = None

        #: Optional veto hook set by the owner (``MainWindow``) to guard a
        #: user-initiated close while a measurement worker is running,
        #: mirroring wx's ``close_handler`` (which aborts the subprocess with
        #: confirmation instead of closing). Return ``False`` to veto the
        #: close. ``None`` (the standalone entry point's default) always
        #: allows it.
        self.close_guard: Callable[[], bool] | None = None

        self._panel = _MeasurePanel(self)
        self._build_controls()
        self.setCentralWidget(self._panel)

    # -- construction ------------------------------------------------------

    def _build_controls(self) -> None:
        """Build the zoom / centre / measure controls on the panel."""
        native_wayland = config.is_ui_native_wayland()
        dark = is_dark(self)

        root = QVBoxLayout(self._panel)
        root.setContentsMargins(0, 0, 0, 0)

        # Row 1 (top): zoom buttons.
        zoom_row = QHBoxLayout()
        self.zoommax_button = _icon_button(
            "zoom-best-fit", lang.getstr("measureframe.zoommax"), dark=dark
        )
        self.zoommax_button.clicked.connect(self.zoommax_handler)
        self.zoomin_button = _icon_button(
            "zoom-in", lang.getstr("measureframe.zoomin"), dark=dark
        )
        self.zoomin_button.clicked.connect(self.zoomin_handler)
        self.zoomnormal_button = _icon_button(
            "zoom-original", lang.getstr("measureframe.zoomnormal"), dark=dark
        )
        self.zoomnormal_button.clicked.connect(self.zoomnormal_handler)
        self.zoomout_button = _icon_button(
            "zoom-out", lang.getstr("measureframe.zoomout"), dark=dark
        )
        self.zoomout_button.clicked.connect(self.zoomout_handler)
        zoom_row.addStretch(1)
        for button in (
            self.zoommax_button,
            self.zoomin_button,
            self.zoomnormal_button,
            self.zoomout_button,
        ):
            zoom_row.addWidget(button)
            zoom_row.addSpacing(8)
        zoom_row.addStretch(1)

        root.addLayout(zoom_row)
        root.addStretch(1)

        # Row 2 (middle): centre. No manual centring under native Wayland.
        center_row = QHBoxLayout()
        center_row.addStretch(1)
        if native_wayland:
            self.center_widget: QWidget = QLabel(
                lang.getstr("measureframe.center.manual")
            )
            self.center_widget.setAlignment(Qt.AlignCenter)
            self.center_widget.setWordWrap(True)
        else:
            self.center_widget = _icon_button(
                "window-center", lang.getstr("measureframe.center"), dark=dark
            )
            self.center_widget.clicked.connect(self.center_handler)
        center_row.addWidget(self.center_widget)
        center_row.addStretch(1)
        root.addLayout(center_row)
        root.addStretch(1)

        # Row 3 (bottom): darken-background checkbox and Measure button.
        bottom = QVBoxLayout()
        self.darken_cb: QCheckBox | None = None
        if not native_wayland or config.is_virtual_display():
            self.darken_cb = QCheckBox(lang.getstr("measure.darken_background"))
            self.darken_cb.setChecked(bool(int(getcfg("measure.darken_background"))))
            self.darken_cb.toggled.connect(self._darken_handler)
            darken_row = QHBoxLayout()
            darken_row.addStretch(1)
            darken_row.addWidget(self.darken_cb)
            darken_row.addStretch(1)
            bottom.addLayout(darken_row)

        self.measure_button = QPushButton(lang.getstr("measureframe.measurebutton"))
        self.measure_button.setDefault(True)
        self.measure_button.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.measure_button.clicked.connect(self.measure_requested.emit)
        measure_row = QHBoxLayout()
        measure_row.addStretch(1)
        measure_row.addWidget(self.measure_button)
        measure_row.addStretch(1)
        bottom.addLayout(measure_row)
        bottom.setContentsMargins(10, 10, 10, 10)
        root.addLayout(bottom)

    # -- control lists -----------------------------------------------------

    def _controls(self) -> list[QWidget]:
        """Return every control widget on the panel.

        Returns:
            list[QWidget]: The zoom / centre / darken / measure widgets.
        """
        controls = [
            self.zoommax_button,
            self.zoomin_button,
            self.zoomnormal_button,
            self.zoomout_button,
            self.center_widget,
            self.measure_button,
        ]
        if self.darken_cb is not None:
            controls.append(self.darken_cb)
        return controls

    # -- display helpers ---------------------------------------------------

    def _current_screen(self) -> QScreen | None:
        """Return the screen the window is on, falling back to the primary.

        Returns:
            QScreen | None: The resolved screen.
        """
        handle = self.windowHandle()
        screen = handle.screen() if handle is not None else None
        return screen or QApplication.primaryScreen()

    def _get_display(
        self,
    ) -> tuple[int | None, tuple[int, int, int, int], tuple[int, int, int, int]]:
        """Return the current display number, geometry and usable client area.

        Returns:
            tuple: ``(argyll_display_no, geometry, client_rect)`` where the
            rects are ``(x, y, w, h)`` pixel tuples.
        """
        screen = self._current_screen()
        if screen is None:
            return None, (0, 0, 0, 0), (0, 0, 0, 0)
        geo = screen.geometry()
        avail = screen.availableGeometry()
        geometry = (geo.x(), geo.y(), geo.width(), geo.height())
        client = (avail.x(), avail.y(), avail.width(), avail.height())
        return get_argyll_display_number(geometry), geometry, client

    def _default_measureframe_size(self) -> float:
        """Return the 100 mm patch edge in pixels for the current display.

        Falls back to the built-in default when the physical size is unknown.

        Returns:
            float: The default patch edge length in pixels.
        """
        if self.x_screen_px_per_mm:
            return float(round(100.0 * max(self.x_screen_px_per_mm)))
        screen = self._current_screen()
        if screen is None:
            return float(DEFAULTS.get("size.measureframe", 300))
        geo = screen.geometry()
        geometry = (geo.x(), geo.y(), geo.width(), geo.height())
        size_mm = self.display_size_mm.get(geometry)
        if size_mm is None:
            size_mm = resolve_screen_size_mm(screen, geometry)
            if size_mm is not None:
                self.display_size_mm[geometry] = size_mm
        if size_mm:
            return float(
                default_measureframe_size((geo.width(), geo.height()), size_mm)
            )
        return float(DEFAULTS.get("size.measureframe", 300))

    @staticmethod
    def _titlebar() -> int:
        """Return the assumed title-bar height for the current platform.

        Returns:
            int: 0 on macOS/Windows (decorations already counted), else 25.
        """
        return 0 if sys.platform in ("darwin", "win32") else 25

    def _min_side(self) -> int:
        """Return the minimum square edge that fits the controls.

        Returns:
            int: The larger of the panel's minimum width and height.
        """
        hint = self._panel.minimumSizeHint()
        return max(hint.width(), hint.height())

    # -- geometry ----------------------------------------------------------

    def place_n_zoom(
        self,
        x: float | None = None,
        y: float | None = None,
        scale: float | None = None,
    ) -> None:
        """Place and scale the window from Argyll relative coordinates.

        Missing arguments are read back from the window's current geometry.

        Args:
            x (float | None): Relative horizontal position (0.0..1.0).
            y (float | None): Relative vertical position (0.0..1.0).
            scale (float | None): Scale factor (0.0..50.0).
        """
        if None in (x, y, scale):
            cur_x, cur_y, cur_scale = (
                float(v) for v in self.get_dimensions().split(",")
            )
            if x is None:
                x = cur_x
            if y is None:
                y = cur_y
            if scale is None:
                scale = cur_scale
        default_size = self._default_measureframe_size()
        DEFAULTS["size.measureframe"] = default_size
        _, geometry, client = self._get_display()
        side, pos, saved_scale = compute_frame_geometry(
            x,
            y,
            scale,
            geometry,
            client,
            default_size,
            self._min_side(),
            self._titlebar(),
        )
        self.setFixedSize(side, side)
        setcfg("dimensions.measureframe", ",".join(strlist((x, y, saved_scale))))
        self.move(*pos)

    def get_dimensions(self) -> str:
        """Return the current geometry in Argyll relative coordinates.

        Returns:
            str: ``"x,y,scale"`` with position in 0.0..1.0 and scale up to 50.
        """
        _, geometry, client = self._get_display()
        default_size = self._default_measureframe_size()
        pos = self.pos()
        size = self.size()
        return compute_dimensions(
            (size.width(), size.height()),
            (pos.x(), pos.y()),
            geometry,
            client,
            default_size,
            self._titlebar(),
        )

    def save_dimensions(self) -> None:
        """Persist the current geometry to ``dimensions.measureframe``."""
        setcfg("dimensions.measureframe", self.get_dimensions())

    # -- zoom / centre handlers -------------------------------------------

    def zoomin_handler(self) -> None:
        """Zoom the measurement area in by one step."""
        display_size = self._get_display()[1][2:]
        default_size = self._default_measureframe_size()
        side = float(self.size().width())
        scale = (float(display_size[0]) / default_size) / (
            float(display_size[0]) / side
        ) + 0.125
        self.place_n_zoom(scale=scale)

    def zoomout_handler(self) -> None:
        """Zoom the measurement area out by one step."""
        display_size = self._get_display()[1][2:]
        default_size = self._default_measureframe_size()
        side = float(self.size().width())
        scale = (float(display_size[0]) / default_size) / (
            float(display_size[0]) / side
        ) - 0.125
        self.place_n_zoom(scale=scale)

    def zoomnormal_handler(self) -> None:
        """Reset the measurement area to its default (unzoomed) scale."""
        scale = float(DEFAULTS["dimensions.measureframe"].split(",")[2])
        self.place_n_zoom(scale=scale)

    def zoommax_handler(self) -> None:
        """Toggle between fullscreen and the last unzoomed geometry."""
        client_size = self._get_display()[2][2:]
        size = self.size()
        if max(size.width(), size.height()) >= max(client_size) - 50:
            dim = getcfg("dimensions.measureframe.unzoomed")
            self.place_n_zoom(*(float(v) for v in dim.split(",")))
        else:
            setcfg("dimensions.measureframe.unzoomed", self.get_dimensions())
            self.place_n_zoom(x=0.5, y=0.5, scale=50.0)

    def center_handler(self) -> None:
        """Centre the measurement area on the display."""
        x, y = (float(v) for v in DEFAULTS["dimensions.measureframe"].split(",")[:2])
        self.place_n_zoom(x, y)

    # -- darken background -------------------------------------------------

    def _darken_handler(self, checked: bool) -> None:
        """Handle the darken-background checkbox, warning on first enable.

        Args:
            checked (bool): The new checkbox state.
        """
        if checked and getcfg("measure.darken_background.show_warning"):
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setText(lang.getstr("measure.darken_background.warning"))
            box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            do_not_show = QCheckBox(lang.getstr("dialog.do_not_show_again"))
            box.setCheckBox(do_not_show)
            result = message_box.exec_box(box)
            if do_not_show.isChecked():
                setcfg("measure.darken_background.show_warning", 0)
            if result == QMessageBox.Cancel:
                self.darken_cb.blockSignals(True)
                self.darken_cb.setChecked(False)
                self.darken_cb.blockSignals(False)
        setcfg("measure.darken_background", int(self.darken_cb.isChecked()))

    # -- patch display -----------------------------------------------------

    def show_controls(self, show: bool = True) -> None:
        """Show or hide the controls, blanking the cursor while measuring.

        Args:
            show (bool): True to show the controls, False to present a bare
                patch.
        """
        for control in self._controls():
            control.setVisible(show)
        if show:
            self._panel.clear_fill()
            self._panel.unsetCursor()
        else:
            self._panel.setCursor(Qt.BlankCursor)

    def show_rgb(self, rgb: tuple[float, float, float]) -> None:
        """Fill the whole window with an RGB colour (pattern-window output).

        Args:
            rgb (tuple[float, float, float]): RGB in the range 0.0..1.0.
        """
        if getcfg("patterngenerator.use_video_levels"):
            minv, maxv = 16, 235
        else:
            minv, maxv = 0, 255
        values = tuple(minv + v * (maxv - minv) for v in rgb)
        floor = tuple(math.floor(v) for v in values)
        ceil = tuple(math.ceil(v) for v in values)
        size = self._panel.size()
        if floor != ceil and size.width() and size.height():
            image = _dither_rgb_image(size.width(), size.height(), values, floor, ceil)
            self._panel.set_image(image)
        else:
            self._panel.set_color(QColor(*floor))
        self.pattern_shown.emit()

    # -- Qt lifecycle ------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        """Show the controls and apply the stored geometry.

        Mirrors wx's ``MeasureFrame.Show(True)``: since the main window keeps
        a single frame instance alive across a whole session (hiding rather
        than closing it between measurement steps, see
        ``MainWindow._present_measureframe``), geometry is re-applied on
        *every* show, not just the first -- otherwise a size/position picked
        up from config after this frame was last hidden (e.g. by
        :meth:`hideEvent`) would never actually reach the window.

        Args:
            event (QShowEvent): The Qt show event.
        """
        super().showEvent(event)
        self.show_controls(True)
        if self.darken_cb is not None:
            self.darken_cb.setChecked(bool(int(getcfg("measure.darken_background"))))
        self.place_n_zoom(
            *(float(v) for v in getcfg("dimensions.measureframe").split(","))
        )
        _, self._current_geometry, _ = self._get_display()

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802 (Qt override)
        """Track the display the window moves to and update ``display.number``.

        Args:
            event (QMoveEvent): The Qt move event.
        """
        super().moveEvent(event)
        if not self.isVisible() or config.is_ui_native_wayland():
            return
        if config.is_virtual_display():
            return
        _, geometry, _ = self._get_display()
        if geometry == self._current_geometry:
            return
        self._current_geometry = geometry
        display_no = get_argyll_display_number(geometry)
        if display_no is not None:
            setcfg("display.number", display_no + 1)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802 (Qt override)
        """Persist the geometry whenever the frame is hidden.

        The main window keeps this frame alive for the whole session and
        hides it (rather than closing it) between the interactive-placement
        step and the actual measurement -- ``MainWindow.call_pending_function``
        calls ``self.measureframe.hide()`` directly. Without saving here (wx's
        ``MeasureFrame.Show(False)`` does the equivalent
        ``setcfg("dimensions.measureframe", self.get_dimensions())``), any
        position/size the user picked by dragging or resizing (as opposed to
        the zoom buttons, which already call :meth:`place_n_zoom` ->
        ``setcfg``) would be discarded and ``dispread`` would draw its patch
        wherever the frame was last placed instead of where the user left it.

        Args:
            event (QHideEvent): The Qt hide event.
        """
        # Guard against saving a bogus (never-placed) geometry: _current_geometry
        # is only set once showEvent has run place_n_zoom() at least once.
        if self._current_geometry is not None:
            self.save_dimensions()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist the geometry before the base class handles closing.

        Consults :attr:`close_guard` first (set by the owning ``MainWindow``)
        so a close while the worker is mid-measurement can be vetoed rather
        than silently leaving the caller with no visible window, matching
        wx's ``MeasureFrame.close_handler``.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        if self.close_guard is not None and not self.close_guard():
            event.ignore()
            return
        if self.isVisible():
            self.save_dimensions()
        super().closeEvent(event)
        if event.isAccepted():
            self.frame_closed.emit()


def main() -> int:
    """Run the standalone Qt measurement-area frame.

    This is the entry point the measurement-flow subprocess drives (see
    :mod:`DisplayCAL.ui.measurement_flow`). The exit code is the contract with
    the parent process: ``255`` means the user pressed **Measure** (proceed to
    the pending measurement), ``0`` means the frame was closed/cancelled
    cleanly. That mirrors the wx :mod:`DisplayCAL.wx_measure_frame` behaviour.

    Returns:
        int: The measure-frame exit code (see :attr:`MeasureFrame.exitcode`).
    """
    config.initcfg()
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    worker = Worker()
    worker.enumerate_displays_and_ports(check_lut_access=False, enumerate_ports=False)
    window = MeasureFrame()

    def _request_measure() -> None:
        """Signal the parent to run the pending measurement, then close."""
        MeasureFrame.exitcode = 255
        window.close()

    window.measure_requested.connect(_request_measure)
    app.top_window = window
    window.show()
    window.listen()
    app.exec()
    # The parent process reloads the config once we exit, so the geometry and
    # display the user picked have to be on disk by then
    config.writecfg()
    if MeasureFrame.exitcode != 255:
        # A plain close/cancel reports success (0); the default of 1 only
        # survives if the process is killed before the event loop returns.
        MeasureFrame.exitcode = 0
    return MeasureFrame.exitcode


if __name__ == "__main__":
    sys.exit(main())
