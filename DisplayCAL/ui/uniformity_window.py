"""Native Qt display-uniformity measurement grid window (issue #947).

Qt port of ``wx_display_uniformity_frame.py::DisplayUniformityFrame``: the
interactive window shown for *Tools > Report > Measure display device
uniformity...*. It fills the target display with a grid of ``rows x cols``
swatches, each with its own "Measure" button; clicking a swatch's button (or
pressing any key while it is focused) drives ``spotread`` through four
brightness levels (white, 75%, 50%, 25% grey), recording a result at each
level, then marks the swatch done with a checkmark. Once every swatch in the
grid has been measured, the window prompts for a save location and writes an
HTML uniformity report (see :mod:`DisplayCAL.report`).

As with the other interactive ports (see
``DisplayCAL/ui/untethered_window.py``), the window is toolkit- and
worker-agnostic: instead of calling ``worker.safe_send`` directly it emits the
key to send on :attr:`UniformityWindow.send_requested`. Wiring that to a
running interactive ``spotread`` (with a thread-safe proxy of this window as
the worker's ``terminal``/``progress_wnd``) is
:class:`DisplayCAL.ui.worker_runner.UniformityController`.
"""

from __future__ import annotations

import functools
import os
import re
from time import strftime
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QGuiApplication, QIcon
from qtpy.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL import report
from DisplayCAL.config import (
    get_argyll_display_number,
    get_verified_path,
    getcfg,
    setcfg,
)
from DisplayCAL.log import get_file_logger
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.meta import VERSION_STRING as APPVERSION
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.util_os import launch_file, waccess

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QKeyEvent, QScreen
    from qtpy.QtWidgets import QWidget as QtWidget

# Background colour the wx frame uses verbatim.
BGCOLOUR = "#333333"

# Brightness levels measured per swatch (white, 75%, 50%, 25% grey). Despite a
# stray wx comment saying "5 different brightness levels", the wx frame's own
# ``self.colors`` tuple -- and the loop bound it drives (``len(self.colors)``)
# -- has always had exactly 4 entries; ported verbatim, not "fixed".
_SWATCH_COLORS = ((255, 255, 255), (192, 192, 192), (128, 128, 128), (64, 64, 64))

_LOCI = {"t": "Daylight", "T": "Planckian"}

# Port of FlatShadedButton's flat, rounded-pill look (wx_windows.py): a dark
# #222 fill, #999 text, no border, 8px corner radius, with a lighter fill/text
# on hover or focus.
_MEASURE_BUTTON_STYLE = """
    QPushButton {
        background-color: #222222;
        color: #999999;
        border: none;
        border-radius: 8px;
        padding: 3px 10px;
    }
    QPushButton:hover, QPushButton:focus {
        background-color: #282828;
        color: #a8a8a8;
    }
    QPushButton:disabled {
        color: #555555;
    }
"""


def _icon(size: int, name: str) -> QIcon:
    """Return a themed pixmap wrapped as a ``QIcon`` (possibly empty)."""
    return QIcon(get_theme_pixmap(size, name))


class _SwatchButton(QPushButton):
    """A grid "Measure" button that reports focus gain to the parent window.

    Port of ``FlatShadedNumberedButton.OnGainFocus``: the wx frame tracks
    which swatch a keypress should apply to via whichever button last gained
    keyboard focus (Tab-navigated or clicked), not a separately-clicked
    state. This lets an operator Tab to a swatch and press any key to start
    its measurement, without a separate "select" step.

    Args:
        index (int): This button's swatch index in the grid.
        on_focus (Callable[[int], None]): Called with :attr:`index` when the
            button gains keyboard focus.
        parent (QtWidget | None): Optional parent widget.
    """

    def __init__(self, index: int, on_focus, parent: QtWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self._on_focus = on_focus

    def focusInEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Report focus gain to the parent window before the default handling."""
        self._on_focus(self.index)
        super().focusInEvent(event)


class UniformityWindow(BaseWindow):
    """Interactive display-uniformity measurement grid.

    Feed each ``spotread`` output chunk to :meth:`parse_txt` (or :meth:`write`);
    the window tracks the current swatch, drives it through its 4 brightness
    levels, and shows a checkmark once a swatch is fully measured. User
    actions (clicking a swatch, pressing a key while one is focused) are
    surfaced as the key string to send to ``spotread`` on
    :attr:`send_requested`.

    Args:
        parent (QtWidget | None): Optional parent widget.
        rows (int | None): Grid row count. Defaults to the
            ``uniformity.rows`` config value.
        cols (int | None): Grid column count. Defaults to the
            ``uniformity.cols`` config value.
    """

    #: Emitted with the key string to send to the interactive ``spotread``
    #: (``" "`` to trigger a reading).
    send_requested = Signal(str)

    #: Emitted once the window has accepted a close request, so the driver
    #: can abort a still-running ``spotread`` subprocess.
    closing = Signal()

    #: Emitted on Escape / "Q": a full worker abort, mirroring
    #: ``UntetheredWindow.abort_requested``.
    abort_requested = Signal()

    def __init__(
        self,
        parent: QtWidget | None = None,
        rows: int | None = None,
        cols: int | None = None,
    ) -> None:
        super().__init__(
            parent,
            name="displayuniformityframe",
            title=lang.getstr("report.uniformity"),
            icon_name=APPNAME.lower(),
        )
        self.setStyleSheet(
            f"QMainWindow, QWidget {{ background-color: {BGCOLOUR}; }}"
        )

        self.rows = rows or getcfg("uniformity.rows")
        self.cols = cols or getcfg("uniformity.cols")
        self.logger = get_file_logger("uniformity")

        self.labels: dict[int, QLabel] = {}
        self.buttons: list[_SwatchButton] = []
        self.panels: list[QWidget] = []
        self._record_icon = _icon(10, "record")
        self._checkmark_icon = _icon(16, "checkmark")
        self._cursor_hidden = False
        self._geometry: tuple[int, int, int, int] = (0, 0, 0, 0)

        central = QWidget()
        self.setCentralWidget(central)
        grid = QGridLayout(central)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        index = 0
        for row in range(self.rows):
            for col in range(self.cols):
                panel = QWidget()
                panel.setStyleSheet(f"background-color: {BGCOLOUR};")
                layout = QVBoxLayout(panel)
                label = QLabel("")
                label.setStyleSheet("color: white;")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label, 1, Qt.AlignmentFlag.AlignCenter)
                button = _SwatchButton(index, self._on_button_focus)
                # Leading space to match FlatShadedButton's icon/text gap.
                button.setText(f" {lang.getstr('measure')}")
                button.setIcon(self._record_icon)
                button.setStyleSheet(_MEASURE_BUTTON_STYLE)
                button.clicked.connect(functools.partial(self._measure_btn_handler, index))
                layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
                layout.setContentsMargins(4, 4, 4, 8)
                grid.addWidget(panel, row, col)
                self.panels.append(panel)
                self.buttons.append(button)
                self.labels[index] = label
                index += 1

        self._setup()
        self._disable_buttons()

    # -- setup / reset -------------------------------------------------------

    def _setup(self) -> None:
        """Reset all per-run state to its initial values."""
        self.logger.info("-" * 80)
        self.index = 0
        self.is_measuring = False
        self.keep_going = True
        self.last_error: str | None = None
        self.results: dict[int, list[dict]] = {}

    def reset(self) -> None:
        """Reset the window to its pre-measurement state (driver hook)."""
        self._setup()
        for panel in self.panels:
            panel.setStyleSheet(f"background-color: {BGCOLOUR};")
        for button in self.buttons:
            button.setIcon(self._record_icon)
            button.show()
        for label in self.labels.values():
            label.setText("")
        self._show_cursor()
        self._disable_buttons()

    # -- rendering ------------------------------------------------------------

    def parse_txt(self, txt: str) -> None:
        """Parse one ``spotread`` output chunk and render it.

        Port of ``DisplayUniformityFrame.parse_txt``.

        Args:
            txt (str): A chunk of ``spotread`` output.
        """
        if not txt:
            return
        self.logger.info(f"{txt!r}")
        if "Spot read failed" in txt:
            self.last_error = txt
        if "Result is XYZ:" in txt:
            match = re.search(r"XYZ:\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)", txt)
            if match:
                self.results[self.index].append(
                    {"XYZ": [float(value) for value in match.groups()]}
                )
            self.last_error = None
        for locus in _LOCI.values():
            if locus in txt and self.results.get(self.index):
                match = re.search(
                    rf"Closest\s+{locus}\s+temperature\s+=\s+(\d+)K", txt, re.IGNORECASE
                )
                if match:
                    self.results[self.index][-1][f"C{locus[0]}T"] = int(match.group(1))
        if "key to take a reading" not in txt or self.last_error:
            return
        if not self.is_measuring:
            self._enable_buttons()
            return
        if len(self.results[self.index]) < len(_SWATCH_COLORS):
            # Take readings at each brightness level per swatch.
            self._apply_swatch_color()
        else:
            self._finish_swatch()

    def write(self, txt: str) -> None:
        """Render a ``spotread`` chunk (the worker's ``progress_wnd.write``)."""
        self.parse_txt(txt)

    def _on_button_focus(self, index: int) -> None:
        """Track which swatch a bare keypress should apply to (see
        :class:`_SwatchButton`)."""
        self.index = index

    def _start_measure(self, index: int) -> None:
        """Begin (or restart) measuring the swatch at ``index``.

        Port of ``DisplayUniformityFrame.measure`` with an event (a fresh
        button click / key press / continuous-mode restart): resets that
        swatch's results and starts the first (white) brightness reading.
        """
        self.index = index
        self.is_measuring = True
        self.results[self.index] = []
        self.labels[self.index].setText("")
        self._hide_cursor()
        self._disable_buttons()
        self.buttons[self.index].hide()
        self._apply_swatch_color()

    def _apply_swatch_color(self) -> None:
        """Paint the current swatch at its next brightness level and read it.

        Port of the tail of ``DisplayUniformityFrame.measure`` (the no-event
        call from ``parse_txt`` advancing to the next brightness level shares
        this same paint-and-send tail).
        """
        color = _SWATCH_COLORS[len(self.results[self.index])]
        self.panels[self.index].setStyleSheet(
            f"background-color: rgb({color[0]}, {color[1]}, {color[2]});"
        )
        # Use a delay to allow for TFT lag.
        QTimer.singleShot(200, lambda: self._send(" "))

    def _finish_swatch(self) -> None:
        """Mark the current swatch done; if all swatches are done, report.

        Port of the "else" branch of ``DisplayUniformityFrame.parse_txt``.
        """
        self.is_measuring = False
        self._show_cursor()
        self._enable_buttons()
        button = self.buttons[self.index]
        button.show()
        button.setFocus()
        button.setIcon(self._checkmark_icon)
        self.panels[self.index].setStyleSheet(f"background-color: {BGCOLOUR};")
        if len(self.results) == self.rows * self.cols:
            self._finish_all()
        if getcfg("uniformity.measure.continuous"):
            self._start_measure(self.index)

    def _finish_all(self) -> None:
        """Prompt for a save location and write the HTML uniformity report.

        Port of the "all swatches measured" branch of
        ``DisplayUniformityFrame.parse_txt``.
        """
        display_no = get_argyll_display_number(self._geometry)
        displays = getcfg("displays")
        display = (
            displays[display_no]
            if display_no is not None and 0 <= display_no < len(displays)
            else ""
        )
        display = display.replace(" [PRIMARY]", "")
        default_file = "Uniformity Check {} — {} — {}".format(
            APPVERSION,
            re.sub(r'[\\/:*?"<>|]+', "_", display),
            strftime("%Y-%m-%d %H-%M.html"),
        )
        default_dir, _default_file = get_verified_path(
            None, os.path.join(getcfg("profile.save_path"), default_file)
        )
        path, _filter = file_dialog.get_save_file_name(
            self,
            lang.getstr("save_as"),
            os.path.join(default_dir, default_file),
            f"{lang.getstr('filetype.html')} (*.html *.htm)",
        )
        if not path:
            return
        if not waccess(os.path.dirname(path) or ".", os.W_OK):
            message_box.critical(
                self, APPNAME, lang.getstr("error.access_denied.write", path)
            )
            return
        save_path = os.path.splitext(path)[0] + ".html"
        setcfg("last_filedialog_path", save_path)
        locus = _LOCI.get(getcfg("whitepoint.colortemp.locus"))
        try:
            report.create(
                save_path,
                {
                    "${REPORT_VERSION}": APPVERSION,
                    "${DISPLAY}": display,
                    "${DATETIME}": strftime("%Y-%m-%d %H:%M:%S"),
                    "${ROWS}": str(self.rows),
                    "${COLS}": str(self.cols),
                    "${RESULTS}": str(self.results),
                    "${LOCUS}": locus,
                },
                getcfg("report.pack_js"),
                "uniformity",
            )
        except OSError as exception:
            message_box.critical(self, APPNAME, str(exception))
        else:
            launch_file(save_path)

    # -- buttons / cursor -----------------------------------------------------

    def _enable_buttons(self, enable: bool = True) -> None:
        for button in self.buttons:
            button.setEnabled(enable)

    def _disable_buttons(self) -> None:
        self._enable_buttons(False)

    def _hide_cursor(self) -> None:
        if not self._cursor_hidden:
            self._cursor_hidden = True
            QGuiApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)

    def _show_cursor(self) -> None:
        if self._cursor_hidden:
            self._cursor_hidden = False
            QGuiApplication.restoreOverrideCursor()

    def _measure_btn_handler(self, index: int) -> None:
        self._start_measure(index)

    def _send(self, key: str) -> None:
        """Request that ``key`` be sent to the interactive ``spotread``."""
        self.send_requested.emit(key)

    # -- keyboard -------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle Escape/"Q" (abort) and any-other-key (measure) bindings.

        Port of ``DisplayUniformityFrame.key_handler``'s non-navigation
        branches; Tab-based focus movement between swatches is native Qt
        behaviour and needs no port (see :class:`_SwatchButton`).

        Args:
            event (QKeyEvent): The Qt key event.
        """
        text = event.text()
        if event.key() == Qt.Key.Key_Escape or text.upper() == "Q":
            self.abort_requested.emit()
            return
        if (
            text
            and self.index > -1
            and not self.is_measuring
            and self.buttons[self.index].isEnabled()
        ):
            self._measure_btn_handler(self.index)
            return
        super().keyPressEvent(event)

    # -- geometry / lifecycle ------------------------------------------------

    def _target_screen(self) -> QScreen | None:
        """Return the ``QScreen`` matching the configured Argyll display number.

        Qt-native equivalent of wx's ``config.get_display_number`` (Argyll
        display index -> OS display), used to place the grid on the
        configured display exactly like the wx frame's ``Show()`` override.
        """
        display_no = getcfg("display.number") - 1
        for screen in QGuiApplication.screens():
            geo = screen.geometry()
            geometry = (geo.x(), geo.y(), geo.width(), geo.height())
            if get_argyll_display_number(geometry) == display_no:
                return screen
        return QGuiApplication.primaryScreen()

    def place(self) -> None:
        """Move/size the window to fill the configured target display.

        Port of ``DisplayUniformityFrame.Show()``'s display placement: moves
        to that display's *client* area (``availableGeometry()``, excluding
        the menu bar / dock / taskbar, matching wx's ``ClientArea``) and
        sizes to fill it. Confirmed against the live wx frame: it covers the
        screen this way, not via native OS fullscreen (macOS's menu bar and
        dock stay visible), so this deliberately doesn't use
        ``showFullScreen()`` either -- which also avoids that native
        fullscreen's animated exit transition complicating hide()/close().
        """
        screen = self._target_screen()
        if screen is None:
            return
        # The raw (non-client) geometry is what Argyll's display list and
        # get_argyll_display_number() key off of, so it's kept for the report
        # (_finish_all) even though the window itself is placed within the
        # client area.
        geo = screen.geometry()
        self._geometry = (geo.x(), geo.y(), geo.width(), geo.height())
        client = screen.availableGeometry()
        self.move(client.topLeft())
        self.resize(client.size())

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Focus the first swatch once shown, mirroring the wx frame."""
        super().showEvent(event)
        if self.buttons:
            self.buttons[0].setFocus()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Tell the driver to abort a still-running measurement on close.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.keep_going = False
        self._show_cursor()
        super().closeEvent(event)
        if event.isAccepted():
            self.closing.emit()
