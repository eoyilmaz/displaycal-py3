"""Application / ArgyllCMS update-check dialogs — Qt port.

Qt port of the update-check portion of ``display_cal.py``'s
``app_update_check`` / ``app_update_confirm`` / ``app_up_to_date`` chain (the
instrument-setup / donation-nag half that wx chains into afterwards is a
separate concern, ported directly on ``MainWindow``, see its module
docstring). Reuses the toolkit-neutral :mod:`DisplayCAL.update_check` for the
network calls; this module only builds and shows the dialogs.

:class:`UpdateCheckController` checks both the DisplayCAL and ArgyllCMS
release channels off the GUI thread in a single background call, then shows
an :class:`_UpdateAvailableDialog` for whichever has a newer version (app
first, then Argyll — both, if both do), or, for a manual/non-silent check,
a plain "up to date" ``QMessageBox`` when neither does. A silent (startup)
check that finds nothing emits :attr:`UpdateCheckController.finished` with
``False`` so the caller can chain into the instrument-setup / donation-nag
check, matching wx's ``app_update_check`` -> ``check_instrument_setup`` chain.

Simplified versus the wx dialog (documented in :mod:`DisplayCAL.update_check`
too): a single "Download" / "Go to website" button opens the resolved URL in
the system browser rather than reproducing wx's in-app auto-download-and-run
flow; the snapshot/beta channel and wx's self-chained "check the other
channel after declining" behaviour are dropped, since this controller already
checks both channels in one pass.
"""

from __future__ import annotations

from typing import ClassVar

from qtpy.QtCore import QObject, QThread, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL import update_check as uc
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import message_box
from DisplayCAL.util_os import launch_file
from DisplayCAL.worker import Worker


class _CallThread(QThread):
    """Run a zero-argument callable off the GUI thread.

    Args:
        func: Callable returning a result (or raising, in which case the
            exception is delivered via :attr:`done` instead of propagating).
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the callable's return value.
    done = Signal(object)

    def __init__(self, func, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._func = func

    def run(self) -> None:
        self.done.emit(self._func())


class _UpdateAvailableDialog(QDialog):
    """Show a newer version's changelog and let the user get it or dismiss."""

    _TITLES: ClassVar[dict[str, str]] = {"app": APPNAME, "argyll": "ArgyllCMS"}

    def __init__(
        self, result: uc.UpdateCheckResult, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        title = self._TITLES.get(result.component, result.component)
        self.setWindowTitle(title)
        self._url = result.download_url or result.release_page_url

        layout = QVBoxLayout(self)
        msg = lang.getstr("update_check.new_version", f"{title} {result.new_version}")
        label = QLabel(msg, self)
        label.setWordWrap(True)
        layout.addWidget(label)

        if result.changelog_html:
            browser = QTextBrowser(self)
            browser.setOpenExternalLinks(True)
            browser.setHtml(result.changelog_html)
            browser.setMinimumSize(500, 300)
            layout.addWidget(browser)

        self._onstartup_checkbox = QCheckBox(
            lang.getstr("update_check.onstartup"), self
        )
        self._onstartup_checkbox.setChecked(bool(getcfg("update_check")))
        layout.addWidget(self._onstartup_checkbox)

        buttons = QDialogButtonBox(self)
        get_button = buttons.addButton(
            lang.getstr("download" if result.download_url else "go_to_website"),
            QDialogButtonBox.AcceptRole,
        )
        get_button.setDefault(True)
        get_button.clicked.connect(self._open_url)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_url(self) -> None:
        launch_file(self._url)
        self.accept()

    def accept(self) -> None:  # noqa: D102 (Qt override)
        setcfg("update_check", int(self._onstartup_checkbox.isChecked()))
        super().accept()

    def reject(self) -> None:  # noqa: D102 (Qt override)
        setcfg("update_check", int(self._onstartup_checkbox.isChecked()))
        super().reject()


def show_up_to_date_dialog(parent: QWidget | None = None) -> None:
    """Port of ``app_up_to_date``: a plain "up to date" notice with the checkbox."""
    box = QMessageBox(
        QMessageBox.Information,
        APPNAME,
        lang.getstr("update_check.uptodate", APPNAME),
        QMessageBox.Ok,
        parent,
    )
    checkbox = QCheckBox(lang.getstr("update_check.onstartup"))
    checkbox.setChecked(bool(getcfg("update_check")))
    box.setCheckBox(checkbox)
    message_box.exec_box(box)
    setcfg("update_check", int(checkbox.isChecked()))


class UpdateCheckController(QObject):
    """Check for DisplayCAL/ArgyllCMS updates and show the result."""

    #: Emitted once the check (and any dialog it triggered) is done. The
    #: bool is True if an update was found (and its dialog shown).
    finished = Signal(bool)

    def __init__(self, worker: Worker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        self._parent = parent
        self._silent = False
        self._thread: _CallThread | None = None

    def run(self, silent: bool = False) -> None:
        """Start the update check in the background.

        Args:
            silent: If True, show no dialog when both channels are up to
                date (used for the startup check).
        """
        self._silent = silent
        self._thread = _CallThread(self._fetch, parent=self)
        self._thread.done.connect(self._on_fetched)
        self._thread.start()

    def _fetch(self) -> tuple:
        app_result = uc.check_app_update()
        argyll_result = uc.check_argyll_update(
            getattr(self._worker, "argyll_version", None)
        )
        return app_result, argyll_result

    def _on_fetched(self, results: tuple) -> None:
        app_result, argyll_result = results
        found = False
        if app_result is not None:
            found = True
            _UpdateAvailableDialog(app_result, self._parent).exec_()
        if argyll_result is not None:
            found = True
            _UpdateAvailableDialog(argyll_result, self._parent).exec_()
        if not found and not self._silent:
            show_up_to_date_dialog(self._parent)
        self.finished.emit(found)
