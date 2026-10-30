"""VRML-to-X3D converter — Qt port.

Reference vertical slice for the DisplayCAL 4.0 wx-to-Qt migration. It is the
Qt equivalent of :mod:`DisplayCAL.wx_vrml_2_x3d`, built entirely on
:mod:`DisplayCAL.ui` and the binding-agnostic backend in
:mod:`DisplayCAL.x3dom`.

Notable simplifications versus the wx version:

* The conversion runs on a small ``QThread`` (:class:`_ConversionThread`)
  instead of going through the heavyweight :class:`DisplayCAL.worker.Worker`
  and its custom progress dialog; we only need to keep the UI responsive and
  report success/failure.
* File-type drag-and-drop is handled by the reusable
  :class:`DisplayCAL.ui.file_drop.FileDropTarget`.
* The console / ``--no-gui`` path still delegates to the existing
  :func:`DisplayCAL.wx_vrml_2_x3d.main`, so no behaviour is lost there.
"""

from __future__ import annotations

import os
import sys

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from DisplayCAL import config, x3dom
from DisplayCAL import localization as lang
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import file_dialog, message_box
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.util_os import launch_file, make_win32_compatible_long_path, waccess

#: Suffixes the converter accepts (lowercased), longest first matters for the
#: drop target's matching.
VRML_SUFFIXES = (".vrml.gz", ".wrl.gz", ".vrml", ".wrl", ".wrz")


class _ConversionThread(QThread):
    """Run :func:`DisplayCAL.x3dom.vrmlfile2x3dfile` off the GUI thread.

    Args:
        vrmlpath (str): Path to the source VRML file.
        x3dpath (str): Path to write the X3D output to.
        html (bool): Whether to wrap the X3D in an HTML viewer.
        embed (bool): Whether to embed the viewer components in the HTML.
        force (bool): Whether to force a fresh download of viewer components.
        cache (bool): Whether to use the viewer-components cache.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the backend result: ``True``, ``False`` or an ``Exception``.
    done = Signal(object)

    def __init__(
        self,
        vrmlpath: str,
        x3dpath: str,
        html: bool,
        embed: bool,
        force: bool,
        cache: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._args = (vrmlpath, x3dpath, html, embed, force, cache)

    def run(self) -> None:
        try:
            result = x3dom.vrmlfile2x3dfile(*self._args, worker=None)
        except Exception as exception:  # noqa: BLE001  (report, don't crash thread)
            result = exception
        self.done.emit(result)


class VRML2X3DWindow(BaseWindow):
    """Single-button window that converts dropped/selected VRML files.

    Args:
        html (bool): Whether to wrap the X3D output in an HTML viewer.
        embed (bool): Whether to embed the viewer components in the HTML.
        view (bool): Whether to open the result after a successful conversion.
        force (bool): Whether to force a fresh download of viewer components.
        cache (bool): Whether to use the viewer-components cache.
    """

    def __init__(
        self, html: bool, embed: bool, view: bool, force: bool, cache: bool
    ) -> None:
        super().__init__(
            name="vrml2x3dframe",
            title=lang.getstr("vrml_to_x3d_converter"),
            icon_name=f"{APPNAME}-VRML-to-X3D-converter".lower(),
        )
        self.html = html
        self.embed = embed
        self.view = view
        self.force = force
        self.cache = cache
        self._thread: _ConversionThread | None = None

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)

        self.button = QPushButton(central)
        self.button.setFlat(True)
        self.button.setCursor(Qt.PointingHandCursor)
        pixmap = get_theme_pixmap(256, "3d-primitives")
        if not pixmap.isNull():
            self.button.setIcon(pixmap)
            self.button.setIconSize(pixmap.size())
        self.button.setToolTip(lang.getstr("file.select"))
        self.button.clicked.connect(lambda: self.convert(None))
        layout.addWidget(self.button)

        self.setCentralWidget(central)
        self.setFixedSize(self.sizeHint())

        # Drag-and-drop: route any accepted VRML file through ``convert``.
        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(VRML_SUFFIXES, self.convert),
            unsupported_handler=self._on_unsupported,
            parent=self,
        )
        self.droptarget.install_on(self)
        self.droptarget.install_on(self.button)

    # -- conversion --------------------------------------------------------

    def convert(self, vrmlpath: str | None) -> None:
        """Prompt for paths as needed and start a background conversion.

        Args:
            vrmlpath (str | None): The VRML file to convert, or ``None`` to
                prompt with a file dialog.
        """
        if self._thread is not None and self._thread.isRunning():
            return  # one conversion at a time
        vrmlpath = self._resolve_input_path(vrmlpath)
        if not vrmlpath:
            return
        x3dpath = self._resolve_output_path(vrmlpath)
        if not x3dpath:
            return

        vrmlpath, x3dpath = (str(p) for p in (vrmlpath, x3dpath))
        if sys.platform == "win32":
            vrmlpath = make_win32_compatible_long_path(vrmlpath)
            x3dpath = make_win32_compatible_long_path(x3dpath)
        if self.html:
            self._finalpath = f"{x3dpath}.html"
            if sys.platform == "win32":
                self._finalpath = make_win32_compatible_long_path(self._finalpath)
                x3dpath = self._finalpath[:-5]
        else:
            self._finalpath = x3dpath

        self.setEnabled(False)
        self._thread = _ConversionThread(
            vrmlpath,
            x3dpath,
            self.html,
            self.embed,
            self.force,
            self.cache,
            parent=self,
        )
        self._thread.done.connect(self._on_conversion_done)
        self._thread.start()

    def _resolve_input_path(self, vrmlpath: str | None) -> str | None:
        """Return an existing VRML path, prompting with a dialog if needed.

        Args:
            vrmlpath (str | None): A candidate path, or ``None`` to prompt.

        Returns:
            str | None: An existing VRML file path, or ``None`` if cancelled.
        """
        if vrmlpath and os.path.isfile(vrmlpath):
            return vrmlpath
        default_dir, default_file = config.get_verified_path("last_vrml_path")
        wildcard = (
            lang.getstr("filetype.vrml") + " (*.vrml *.vrml.gz *.wrl.gz *.wrl *.wrz)"
        )
        path, _ = file_dialog.get_open_file_name(
            self,
            lang.getstr("file.select"),
            os.path.join(default_dir, default_file) if default_file else default_dir,
            wildcard,
        )
        if not path:
            return None
        config.setcfg("last_vrml_path", path)
        config.writecfg(module="VRML-to-X3D-converter", options=("last_vrml_path",))
        return path

    def _resolve_output_path(self, vrmlpath: str) -> str | None:
        """Return a writable ``.x3d`` output path, prompting if necessary.

        Args:
            vrmlpath (str): The source VRML path the output is derived from.

        Returns:
            str | None: A writable ``.x3d`` path, or ``None`` if cancelled.
        """
        filename = os.path.splitext(vrmlpath)[0]
        x3dpath = f"{filename}.x3d"
        if waccess(os.path.dirname(x3dpath), os.W_OK):
            return x3dpath
        path, _ = file_dialog.get_save_file_name(
            self,
            lang.getstr("error.access_denied.write", os.path.dirname(x3dpath)),
            f"{os.path.basename(filename)}.x3d",
            lang.getstr("filetype.x3d") + " (*.x3d)",
        )
        return path or None

    def _on_conversion_done(self, result: bool | Exception) -> None:
        """Handle the background conversion result on the GUI thread.

        Args:
            result (bool | Exception): The backend result; an exception on
                failure, otherwise truthy on success.
        """
        self.setEnabled(True)
        self._thread = None
        if isinstance(result, Exception):
            message_box.critical(self, self.windowTitle(), str(result))
        elif result and self.view:
            launch_file(self._finalpath)

    def _on_unsupported(self, paths: list[str]) -> None:
        """Report files the converter cannot handle.

        Args:
            paths (list[str]): The unsupported dropped file paths.
        """
        message_box.warning(
            self,
            self.windowTitle(),
            lang.getstr("error.file_type_unsupported") + "\n\n" + "\n".join(paths),
        )

    # -- scripting ---------------------------------------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's file-opening commands.
        """
        return [
            *self.get_common_commands(),
            "VRML-to-X3D-converter [filename...]",
            "load <filename...>",
        ]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"``, ``"fail"`` or ``"invalid"``.
        """
        return self.open_files_command(data, "VRML-to-X3D-converter", multi=True)


def main() -> int:
    """Entry point for the Qt VRML-to-X3D converter.

    Returns:
        int: Process exit code (0 on success). Returned rather than passed to
        ``sys.exit`` so callers (e.g. the shared launcher in
        :mod:`DisplayCAL.main`) can still run their own cleanup.
    """
    # Console / help mode is unchanged; defer to the existing implementation.
    if "--help" in sys.argv[1:] or "--no-gui" in sys.argv[1:]:
        from DisplayCAL.wx_vrml_2_x3d import main as console_main

        console_main()
        return 0

    config.initcfg("VRML-to-X3D-converter")
    lang.init()
    lang.update_defaults()

    cache = "--no-cache" not in sys.argv[1:]
    embed = "--embed" in sys.argv[1:]
    force = "--force" in sys.argv[1:]
    html = "--no-html" not in sys.argv[1:]
    view = "--no-view" not in sys.argv[1:]

    app = Application(sys.argv)
    window = VRML2X3DWindow(html, embed, view, force, cache)
    app.top_window = window
    if sys.platform == "darwin":
        window.init_menubar()
    window.show()
    window.listen()
    app.process_argv()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
