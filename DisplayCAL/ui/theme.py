"""Theme helpers for the Qt UI.

Some legacy wx canvases (the LUT viewer, profile-info plots, CCXX plot, the
interactive display-adjustment window) are hard-coded to a fixed dark scheme
(``BGCOLOUR = "#333333"``, ``FGCOLOUR = "#999999"``, ``GRIDCOLOUR =
"#444444"``) regardless of the OS -- but the ordinary wx ``MainFrame`` window
chrome is *not*: it paints with ``wx.SystemSettings.GetColour(wx
.SYS_COLOUR_WINDOW)``, the real OS window-background colour, which on a
Mac in Dark Mode is much darker than ``#333333`` (the raw ``NSColor
.windowBackgroundColor`` query reports ``#171717``, but macOS composites a
vibrancy/tint pass on top of it, so a real on-screen wx window actually
samples as ``#232323`` -- the query alone understates it). The Qt UI keeps
the DisplayCAL look but **selects it from the OS light/dark preference**:
:func:`apply_theme` detects the scheme (:func:`is_dark`) and installs a
matching :class:`QPalette`, tuned to match that real *on-screen* native
window background rather than the plot canvases' brighter fixed grey or the
raw (uncomposited) system colour query. On Windows this also means
switching to the Fusion style, since the native ``windowsvista`` style
ignores custom palette colours for several controls (combo-box popups in
particular); macOS and Linux native styles honour the palette as-is. Plot
colours (:func:`plot_colors`) are then derived from that palette, so the
plots match the surrounding chrome exactly.

The per-datum plot colours (RGB curve pens, gamut-hull vertex colours) are
inherent to the data, not the theme, and stay constant in both schemes.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NamedTuple

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QStyleFactory

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

#: RGB tone-curve pen colours (from ``wx_lut_viewer.LUTCanvas.colors``). These
#: are data colours, identical in light and dark themes.
CHANNEL_COLORS = {
    "R": QColor("#FF0000"),
    "G": QColor("#00FF00"),
    "B": QColor("#0080FF"),
    "Gray": QColor("#CCCCCC"),
}

#: *Maximum* point size for UI text, matching wx's ``SetMaxFontSize(11)``.
#: wx's helper (:func:`DisplayCAL.wx_addons.SetMaxFontSize`) only *shrinks*
#: the native font if it exceeds this -- it never grows a smaller native
#: default up to it. :func:`apply_theme` must mirror that asymmetry: the
#: native default is ~13pt on macOS (capped down to 11, matching wx) but only
#: ~9pt on Windows (Segoe UI) -- unconditionally forcing 11pt there, as a
#: naive ``setPointSize(11)`` would, makes the whole Qt UI noticeably larger
#: than its wx counterpart on Windows while happening to still match on
#: macOS, which is what made this asymmetry easy to miss.
FONT_POINT_SIZE = 11

#: Palette role → colour for the dark scheme, tuned to match wx's actual
#: *on-screen* native window background. ``wx.SystemSettings.GetColour(wx
#: .SYS_COLOUR_WINDOW)`` reports ``#171717`` on macOS Dark Mode, but that raw
#: ``NSColor.windowBackgroundColor`` value is not what's actually painted:
#: AppKit composites a vibrancy/tint pass on top of it, so a real on-screen
#: wx window samples as ``#232323`` (confirmed via `screencapture` + pixel
#: sampling of a live wx frame, not just the colour-query API). Qt's opaque
#: palette fill has no such compositing step and renders exactly as
#: specified, so matching the raw query left Qt visibly darker than wx even
#: though the two hex values looked close. Tuned to ``#232323`` instead, the
#: same offset from the plot canvases' fixed ``BGCOLOUR = "#333333"``.
_DARK = {
    QPalette.Window: "#232323",
    QPalette.WindowText: "#999999",
    QPalette.Base: "#232323",
    QPalette.AlternateBase: "#2c2c2c",
    QPalette.Text: "#cccccc",
    QPalette.Button: "#343434",
    QPalette.ButtonText: "#cccccc",
    QPalette.ToolTipBase: "#232323",
    QPalette.ToolTipText: "#cccccc",
    QPalette.Highlight: "#4d7ea5",
    QPalette.HighlightedText: "#ffffff",
    QPalette.PlaceholderText: "#777777",
    QPalette.Link: "#5a9fd4",
}

#: Palette role → colour for the light scheme (a light counterpart).
_LIGHT = {
    QPalette.Window: "#ececec",
    QPalette.WindowText: "#606060",
    QPalette.Base: "#fbfbfb",
    QPalette.AlternateBase: "#f0f0f0",
    QPalette.Text: "#222222",
    QPalette.Button: "#e4e4e4",
    QPalette.ButtonText: "#333333",
    QPalette.ToolTipBase: "#fbfbfb",
    QPalette.ToolTipText: "#222222",
    QPalette.Highlight: "#3d7eb8",
    QPalette.HighlightedText: "#ffffff",
    QPalette.PlaceholderText: "#999999",
    QPalette.Link: "#2a6fb0",
}

#: Disabled-state text colour per scheme.
_DISABLED = {True: "#666666", False: "#a0a0a0"}


def is_dark(source: QWidget | None = None) -> bool:
    """Return whether the current OS colour scheme is dark.

    Prefers the explicit OS colour-scheme hint (Qt 6.5+); otherwise infers it
    from the window background's lightness.

    Args:
        source (QWidget | None): Widget whose palette to inspect for the
            fallback; defaults to the application palette.

    Returns:
        bool: True if the effective scheme is dark.
    """
    app = QApplication.instance()
    if app is not None:
        color_scheme = getattr(app.styleHints(), "colorScheme", None)
        if callable(color_scheme):
            try:
                scheme = color_scheme()
                if scheme == Qt.ColorScheme.Dark:
                    return True
                if scheme == Qt.ColorScheme.Light:
                    return False
            except (AttributeError, TypeError):
                pass  # older Qt without ColorScheme; fall through
    palette = source.palette() if source is not None else QApplication.palette()
    return palette.color(QPalette.Window).lightness() < 128


def build_palette(dark: bool) -> QPalette:
    """Return the DisplayCAL :class:`QPalette` for the given scheme.

    Args:
        dark (bool): Whether to build the dark (wx-style) palette.

    Returns:
        QPalette: The configured palette.
    """
    colors = _DARK if dark else _LIGHT
    palette = QPalette()
    for role, hexcolor in colors.items():
        palette.setColor(role, QColor(hexcolor))
    disabled = QColor(_DISABLED[dark])
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, disabled)
    return palette


def apply_theme(app: QApplication) -> None:
    """Apply the DisplayCAL theme (palette + font) to ``app``.

    Selects the dark or light palette from the OS colour scheme and caps the
    base font at wx's 11-point size (see :data:`FONT_POINT_SIZE`), only
    shrinking it, never growing it beyond the platform's native default. On
    Windows, also switches the style to **Fusion**: the native
    ``windowsvista`` style renders combo-box popups and
    several other controls via the OS's own (always-light, unless the OS is
    told otherwise through undocumented dark-mode APIs) theme engine and
    ignores the application :class:`QPalette` entirely, which left combo boxes
    white in dark mode regardless of the palette set here. Fusion is the only
    built-in style that honours a custom palette consistently, so it is used
    to keep Windows dark mode faithful even though it costs the native
    chevron/corner rendering. macOS and Linux native styles already honour the
    palette and keep their native look. Container backgrounds are painted with
    the palette ``Window`` colour by the windows themselves (via
    ``setAutoFillBackground``), so the themed grey shows through while the
    controls draw over it.

    Args:
        app (QApplication): The application to theme.
    """
    if sys.platform == "win32":
        app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(build_palette(is_dark()))
    font = app.font()
    if font.pointSize() > FONT_POINT_SIZE:
        font.setPointSize(FONT_POINT_SIZE)
        app.setFont(font)


def label_color(source: QWidget | None = None) -> QColor:
    """Return the grayish colour for secondary text (e.g. table label column).

    Args:
        source (QWidget | None): Widget whose palette to read; defaults to the
            application palette.

    Returns:
        QColor: The ``WindowText`` (grayish) colour.
    """
    palette = source.palette() if source is not None else QApplication.palette()
    return palette.color(QPalette.WindowText)


class PlotColors(NamedTuple):
    """Theme-derived colours for a pyqtgraph plot.

    Attributes:
        background (QColor): Plot canvas background.
        foreground (QColor): Axis lines, ticks and labels.
        grid (QColor): Grid-line colour (same hue as foreground; pyqtgraph
            applies its own alpha).
        linear (QColor): The faint ``y = x`` reference diagonal.
        locus (QColor): High-contrast overlay lines (e.g. colour-temperature
            locus) that need to stand out against the background.
    """

    background: QColor
    foreground: QColor
    grid: QColor
    linear: QColor
    locus: QColor


def _blend(a: QColor, b: QColor, t: float) -> QColor:
    """Return the linear blend ``a*(1-t) + b*t`` of two colours.

    Args:
        a (QColor): The colour at ``t = 0``.
        b (QColor): The colour at ``t = 1``.
        t (float): The blend factor in 0..1.

    Returns:
        QColor: The blended (opaque) colour.
    """
    return QColor(
        round(a.red() * (1 - t) + b.red() * t),
        round(a.green() * (1 - t) + b.green() * t),
        round(a.blue() * (1 - t) + b.blue() * t),
    )


def plot_colors(source: QWidget | None = None) -> PlotColors:
    """Return plot colours derived from the current palette.

    The plot background/foreground are taken from the widget's palette
    (``Window``/``WindowText``) so the plot matches the surrounding themed
    chrome exactly, with the grid and reference lines blended between the two.

    Args:
        source (QWidget | None): Widget whose palette to read; defaults to the
            application palette.

    Returns:
        PlotColors: The background/foreground/grid/linear/locus colours.
    """
    palette = source.palette() if source is not None else QApplication.palette()
    background = palette.color(QPalette.Window)
    foreground = palette.color(QPalette.WindowText)
    grid = _blend(background, foreground, 0.35)
    linear = QColor(foreground)
    linear.setAlpha(150)
    locus = _blend(background, foreground, 0.85)
    locus.setAlpha(220)
    return PlotColors(
        background=background,
        foreground=foreground,
        grid=grid,
        linear=linear,
        locus=locus,
    )
