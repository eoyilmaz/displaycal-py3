"""Profile-loader exceptions dialog -- Qt port.

Qt counterpart of
:class:`DisplayCAL.profile_loader.ProfileLoaderExceptionsDialog`: lets the
user manage per-executable exceptions for the apply-profiles tray daemon --
disable profile loading entirely while a given executable is running, or
force a gamma-ramp reset instead of loading a profile. See
:mod:`DisplayCAL.ui.tools.apply_profiles` for where the tray's "Exceptions"
menu item wires this dialog up and persists the result via
``config.setcfg("profile_loader.exceptions", ...)``.

Column 0/1 use native Qt checkboxes rather than wx's custom
``CustomCellBoolRenderer`` icon-swap cells; the legend below the table still
shows the real ``apply-profiles-reset`` icon (normal/disabled) so the
disable-vs-reset distinction reads the same as the wx dialog.
"""

from __future__ import annotations

import os

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QIcon, QKeyEvent
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL.ui import file_dialog
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.util_os import getenvu

#: Column indices of the exceptions table.
_COL_ENABLED = 0
_COL_RESET = 1
_COL_EXECUTABLE = 2
_COL_DIRECTORY = 3


class _ExceptionsTable(QTableWidget):
    """A ``QTableWidget`` that emits ``delete_requested`` on Delete/Backspace.

    Mirrors wx's ``ProfileLoaderExceptionsDialog.key_handler``, which routes
    those two keys to the delete action (Space's checkbox-toggle behaviour is
    already native to Qt's checkable table items, so it needs no override
    here).
    """

    delete_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Emit ``delete_requested`` for Delete/Backspace, else default handling.

        Args:
            event (QKeyEvent): The key event.
        """
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
        else:
            super().keyPressEvent(event)


class ProfileLoaderExceptionsDialog(QDialog):
    """Manage per-executable profile-loader exceptions.

    Args:
        exceptions (dict): Mapping of ``path.lower()`` ->
            ``(enabled, reset, path)``, as stored on
            ``ProfileLoader._exceptions``.
        known_apps (set | None): Executable basenames (lowercase) that cannot
            be added as exceptions -- the profile loader already disables
            itself automatically while they run.
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(
        self,
        exceptions: dict,
        known_apps: set | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._exceptions = dict(exceptions)
        self.known_apps = known_apps or set()

        self.setWindowTitle(lang.getstr("exceptions"))
        self.setWindowIcon(QIcon(get_theme_pixmap(32, "displaycal-apply-profiles")))

        self.table = _ExceptionsTable(0, 4, self)
        self.table.setHorizontalHeaderLabels(
            ["", "", lang.getstr("executable"), lang.getstr("directory")]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(_COL_DIRECTORY, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(_COL_ENABLED, 28)
        self.table.setColumnWidth(_COL_RESET, 28)
        self.table.setColumnWidth(_COL_EXECUTABLE, 140)
        self.table.setMinimumSize(648, 200)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_button_state)
        self.table.delete_requested.connect(self._on_delete)

        self._populate_table()

        self.add_btn = QPushButton(lang.getstr("add"))
        self.browse_btn = QPushButton(lang.getstr("browse"))
        self.delete_btn = QPushButton(lang.getstr("delete"))
        self.add_btn.clicked.connect(self._on_add)
        self.browse_btn.clicked.connect(self._on_browse)
        self.delete_btn.clicked.connect(self._on_delete)

        button_row = QHBoxLayout()
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.browse_btn)
        button_row.addWidget(self.delete_btn)
        button_row.addStretch(1)

        reset_icon = QIcon(get_theme_pixmap(16, "apply-profiles-reset"))
        legend = QHBoxLayout()
        disable_label = QLabel()
        disable_label.setPixmap(reset_icon.pixmap(16, QIcon.Mode.Disabled))
        legend.addWidget(disable_label)
        legend.addWidget(QLabel(" = " + lang.getstr("profile_loader.disable")))
        reset_label = QLabel()
        reset_label.setPixmap(reset_icon.pixmap(16, QIcon.Mode.Normal))
        legend.addWidget(reset_label)
        legend.addWidget(QLabel(" = " + lang.getstr("calibration.reset")))
        legend.addStretch(1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            lang.getstr("ok")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            lang.getstr("cancel")
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        layout.addLayout(button_row)
        layout.addLayout(legend)
        layout.addWidget(self.buttons)
        self.resize(680, 420)

        self._update_button_state()

    # -- table population -------------------------------------------------

    def _populate_table(self) -> None:
        """(Re)populate the table from ``self._exceptions``, sorted by key."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for _key, (enabled, reset, path) in sorted(self._exceptions.items()):
            self._append_row(enabled, reset, path)
        self.table.blockSignals(False)

    def _append_row(self, enabled: int, reset: int, path: str) -> int:
        """Append a row for ``path`` and return its index.

        Args:
            enabled (int): Whether the exception is active.
            reset (int): Whether the exception's action is "reset" (True) or
                "disable" (False).
            path (str): The full path of the executable.

        Returns:
            int: The row index that was appended.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        checkable_flags = (
            Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )

        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(checkable_flags)
        enabled_item.setCheckState(
            Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, _COL_ENABLED, enabled_item)

        reset_item = QTableWidgetItem()
        reset_item.setFlags(checkable_flags)
        reset_item.setCheckState(
            Qt.CheckState.Checked if reset else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, _COL_RESET, reset_item)

        self.table.setItem(
            row, _COL_EXECUTABLE, QTableWidgetItem(os.path.basename(path))
        )
        self.table.setItem(row, _COL_DIRECTORY, QTableWidgetItem(os.path.dirname(path)))
        return row

    def _row_path(self, row: int) -> str:
        """Return the full path of the exception at ``row``."""
        return os.path.join(
            self.table.item(row, _COL_DIRECTORY).text(),
            self.table.item(row, _COL_EXECUTABLE).text(),
        )

    def _update_exception(self, row: int) -> None:
        """Recompute ``self._exceptions`` for ``row`` from its current cells."""
        path = self._row_path(row)
        enabled = int(
            self.table.item(row, _COL_ENABLED).checkState() == Qt.CheckState.Checked
        )
        reset = int(
            self.table.item(row, _COL_RESET).checkState() == Qt.CheckState.Checked
        )
        self._exceptions[path.lower()] = (enabled, reset, path)

    # -- signal handlers ----------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Persist a checkbox toggle and enable the OK button.

        Args:
            item (QTableWidgetItem): The item that changed.
        """
        if item.column() in (_COL_ENABLED, _COL_RESET):
            self._update_exception(item.row())
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _update_button_state(self) -> None:
        """Enable/disable Browse and Delete based on the current selection."""
        rows = {index.row() for index in self.table.selectedIndexes()}
        self.browse_btn.setEnabled(len(rows) == 1)
        self.delete_btn.setEnabled(bool(rows))

    def _on_add(self) -> None:
        """Browse for a new executable to add as an exception."""
        default_dir = getenvu("ProgramW6432", "") or getenvu("ProgramFiles", "")
        self._browse(is_add=True, default_dir=default_dir, default_file="")

    def _on_browse(self) -> None:
        """Browse for a replacement executable for the selected row."""
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        if not rows:
            return
        row = rows[0]
        default_dir = self.table.item(row, _COL_DIRECTORY).text()
        default_file = self.table.item(row, _COL_EXECUTABLE).text()
        self._browse(
            is_add=False, default_dir=default_dir, default_file=default_file, row=row
        )

    def _browse(
        self,
        is_add: bool,
        default_dir: str,
        default_file: str,
        row: int | None = None,
    ) -> None:
        """Run the file picker and add/update an exception.

        Mirrors wx's ``browse_handler``.

        Args:
            is_add (bool): True for the Add button, False for Browse.
            default_dir (str): The directory the file picker should start in.
            default_file (str): The file name to preselect.
            row (int | None): The row being edited (Browse only).
        """
        start = (
            os.path.join(default_dir, default_file)
            if default_dir or default_file
            else ""
        )
        path, _selected_filter = file_dialog.get_open_file_name(
            self, lang.getstr("add" if is_add else "browse"), start, "*.exe"
        )
        if not path:
            return
        path = os.path.normpath(path)
        if os.path.basename(path).lower() in self.known_apps:
            QMessageBox.critical(
                self,
                self.windowTitle(),
                lang.getstr(
                    "profile_loader.exceptions.known_app.error",
                    os.path.basename(path),
                ),
            )
            return

        self.table.blockSignals(True)
        try:
            if is_add:
                key = path.lower()
                if key in self._exceptions:
                    # Already present: select its row instead of duplicating it.
                    for existing_row in range(self.table.rowCount()):
                        if self._row_path(existing_row).lower() == key:
                            row = existing_row
                            break
                else:
                    row = self._append_row(1, 0, path)
                    self._exceptions[key] = (1, 0, path)
            else:
                old_key = self._row_path(row).lower()
                self.table.item(row, _COL_EXECUTABLE).setText(os.path.basename(path))
                self.table.item(row, _COL_DIRECTORY).setText(os.path.dirname(path))
                self._update_exception(row)
                if old_key != path.lower():
                    # The row now points at a different executable: drop the
                    # stale entry so it doesn't linger invisibly in
                    # self._exceptions (never shown in the table again, but
                    # still written out to config on OK).
                    self._exceptions.pop(old_key, None)
        finally:
            self.table.blockSignals(False)

        self.table.selectRow(row)
        self._update_button_state()
        self.table.scrollToItem(self.table.item(row, _COL_EXECUTABLE))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _on_delete(self) -> None:
        """Delete the selected exception rows."""
        rows = sorted(
            {index.row() for index in self.table.selectedIndexes()}, reverse=True
        )
        if not rows:
            return
        self.table.blockSignals(True)
        try:
            for row in rows:
                del self._exceptions[self._row_path(row).lower()]
                self.table.removeRow(row)
        finally:
            self.table.blockSignals(False)
        self._update_button_state()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
