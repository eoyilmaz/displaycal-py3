"""Tests for the Qt profile-loader exceptions dialog (issue #890).

Drives ``DisplayCAL.ui.tools.profile_loader_exceptions.ProfileLoaderExceptionsDialog``
headless via the shared offscreen ``QApplication`` fixture, the same pattern
as ``tests/test_ui_fix_profile_associations.py``.

Sample paths are built with ``os.path.join`` rather than hardcoded literals:
the dialog round-trips paths through ``os.path.dirname``/``basename``/``join``/
``normpath``, which on Windows (``ntpath``) do not treat ``/`` the same way
``posixpath`` does on Linux/macOS -- a literal forward-slash path would
silently pick up a mixed separator on ``join`` and stop matching its own dict
key on Windows CI.
"""

import os

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui import file_dialog  # noqa: E402
from DisplayCAL.ui.tools import profile_loader_exceptions as ple  # noqa: E402

BAR_PATH = os.path.join("apps", "bar", "bar.exe")
BAR_DIR = os.path.dirname(BAR_PATH)
FOO_PATH = os.path.join("apps", "foo", "foo.exe")
PROGRAM_FILES_PATH = os.path.join("apps", "program files", "foo", "foo.exe")
NEW_PATH = os.path.join("apps", "new", "new.exe")
KNOWN_APP_PATH = os.path.join("apps", "somewhere", "known.exe")


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


def _make_dialog(qapp, exceptions=None, known_apps=None):
    return ple.ProfileLoaderExceptionsDialog(exceptions or {}, known_apps)


def test_construct_with_no_exceptions(qapp):
    dialog = _make_dialog(qapp)
    try:
        assert dialog.table.rowCount() == 0
        ok_button = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
        assert not ok_button.isEnabled()
    finally:
        dialog.close()


def test_table_populated_sorted_by_key(qapp):
    exceptions = {
        BAR_PATH.lower(): (0, 1, BAR_PATH),
        PROGRAM_FILES_PATH.lower(): (1, 0, PROGRAM_FILES_PATH),
    }
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        assert dialog.table.rowCount() == 2
        # Sorted by dict key, so "apps/bar..." comes first.
        assert dialog.table.item(0, ple._COL_EXECUTABLE).text() == "bar.exe"
        assert dialog.table.item(0, ple._COL_DIRECTORY).text() == BAR_DIR
        assert dialog.table.item(1, ple._COL_EXECUTABLE).text() == "foo.exe"
        from qtpy.QtCore import Qt

        assert (
            dialog.table.item(0, ple._COL_ENABLED).checkState()
            == Qt.CheckState.Unchecked
        )
        assert (
            dialog.table.item(0, ple._COL_RESET).checkState() == Qt.CheckState.Checked
        )
        assert (
            dialog.table.item(1, ple._COL_ENABLED).checkState() == Qt.CheckState.Checked
        )
    finally:
        dialog.close()


def test_toggling_checkbox_updates_exceptions_and_enables_ok(qapp):
    exceptions = {BAR_PATH.lower(): (0, 0, BAR_PATH)}
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        ok_button = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
        assert not ok_button.isEnabled()
        from qtpy.QtCore import Qt

        dialog.table.item(0, ple._COL_ENABLED).setCheckState(Qt.CheckState.Checked)
        assert ok_button.isEnabled()
        assert dialog._exceptions[BAR_PATH.lower()] == (1, 0, BAR_PATH)
    finally:
        dialog.close()


def test_selection_controls_button_state(qapp):
    exceptions = {BAR_PATH.lower(): (0, 0, BAR_PATH)}
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        assert not dialog.browse_btn.isEnabled()
        assert not dialog.delete_btn.isEnabled()
        dialog.table.selectRow(0)
        assert dialog.browse_btn.isEnabled()
        assert dialog.delete_btn.isEnabled()
    finally:
        dialog.close()


def test_delete_removes_row_and_exception_and_enables_ok(qapp):
    exceptions = {
        BAR_PATH.lower(): (0, 0, BAR_PATH),
        FOO_PATH.lower(): (1, 0, FOO_PATH),
    }
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        dialog.table.selectRow(0)
        dialog._on_delete()
        assert dialog.table.rowCount() == 1
        assert BAR_PATH.lower() not in dialog._exceptions
        assert FOO_PATH.lower() in dialog._exceptions
        ok_button = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
        assert ok_button.isEnabled()
    finally:
        dialog.close()


def test_known_app_rejected_on_browse(qapp, monkeypatch):
    dialog = _make_dialog(qapp, known_apps={"known.exe"})
    try:
        monkeypatch.setattr(
            file_dialog.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (KNOWN_APP_PATH, "")),
        )
        shown = {}

        def _fake_critical(*args, **kwargs):
            shown["called"] = True

        monkeypatch.setattr(ple.QMessageBox, "critical", _fake_critical)
        dialog._on_add()
        assert shown.get("called") is True
        assert dialog.table.rowCount() == 0
    finally:
        dialog.close()


def test_add_new_executable(qapp, monkeypatch):
    dialog = _make_dialog(qapp)
    try:
        monkeypatch.setattr(
            file_dialog.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (NEW_PATH, "")),
        )
        dialog._on_add()
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0, ple._COL_EXECUTABLE).text() == "new.exe"
        assert dialog._exceptions[NEW_PATH.lower()] == (1, 0, NEW_PATH)
        ok_button = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
        assert ok_button.isEnabled()
    finally:
        dialog.close()


def test_add_existing_selects_row_without_duplicating(qapp, monkeypatch):
    exceptions = {NEW_PATH.lower(): (1, 0, NEW_PATH)}
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        monkeypatch.setattr(
            file_dialog.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (NEW_PATH, "")),
        )
        dialog._on_add()
        assert dialog.table.rowCount() == 1
        assert dialog.table.currentRow() == 0
    finally:
        dialog.close()


def test_browse_edit_to_different_exe_drops_stale_entry(qapp, monkeypatch):
    exceptions = {FOO_PATH.lower(): (1, 0, FOO_PATH)}
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        dialog.table.selectRow(0)
        monkeypatch.setattr(
            file_dialog.QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *a, **k: (BAR_PATH, "")),
        )
        dialog._on_browse()
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0, ple._COL_EXECUTABLE).text() == "bar.exe"
        assert FOO_PATH.lower() not in dialog._exceptions
        assert dialog._exceptions[BAR_PATH.lower()] == (1, 0, BAR_PATH)
    finally:
        dialog.close()


def test_delete_key_shortcut_triggers_delete(qapp):
    exceptions = {BAR_PATH.lower(): (0, 0, BAR_PATH)}
    dialog = _make_dialog(qapp, exceptions=exceptions)
    try:
        dialog.table.selectRow(0)
        dialog.table.delete_requested.emit()
        assert dialog.table.rowCount() == 0
    finally:
        dialog.close()
