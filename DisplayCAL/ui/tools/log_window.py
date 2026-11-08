"""Log window — Qt port.

Qt equivalent of :class:`DisplayCAL.wx_windows.LogWindow`: a read-only
scrollback view for plain-text log output. Used two ways, matching wx:

* a persistent singleton (:class:`~DisplayCAL.ui.main_window.MainWindow`'s
  ``_log_window``) toggled by the Tools menu's "Show log window" action,
  fed from the global :data:`DisplayCAL.log.LOGBUFFER`,
* fresh, disposable instances for one-off report/verify output
  (:meth:`~DisplayCAL.ui.main_window.MainWindow._on_report_finished`),
  mirroring wx's ``show_additional_infoframe``.

Deliberately narrower than wx's version: no save-as/archive/clear toolbar
(cosmetic-only, deferred to a follow-up) and no live tee of new log calls
while shown (wx's own ``wx.CallAfter(wx_log, ...)`` hook) -- only draining
on toggle, which is the persistent singleton's caller's responsibility.
"""

from __future__ import annotations

import sys

from qtpy.QtGui import QFontDatabase
from qtpy.QtWidgets import QPlainTextEdit

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow


class LogWindow(BaseWindow):
    """Read-only scrollback window for plain-text log output."""

    def __init__(self, parent=None, title: str | None = None) -> None:
        super().__init__(
            parent,
            name="info",
            title=title or lang.getstr("infoframe.title"),
        )
        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.setCentralWidget(self._text)
        self.restore_position()
        if not self.restore_size():
            self.resize(config.getcfg("size.info.w"), config.getcfg("size.info.h"))

    def Log(self, txt: str) -> None:  # noqa: N802 (wx-parity method name)
        """Append ``txt`` to the log view, scrolling to show it.

        Args:
            txt (str): The text to append.
        """
        self._text.appendPlainText(txt)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.save_size()
        super().closeEvent(event)


def main() -> int:
    """Entry point for the standalone Qt log window.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("log-window")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = LogWindow()
    app.top_window = window
    window.show()
    window.listen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
