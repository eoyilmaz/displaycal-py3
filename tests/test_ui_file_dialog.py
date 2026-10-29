"""Tests for DisplayCAL.ui.file_dialog."""

import ntpath
import os

import pytest

pytest.importorskip("qtpy")

from DisplayCAL.ui import file_dialog  # noqa: E402


@pytest.fixture
def windows_paths(monkeypatch):
    """Make os.path behave like on Windows, where Qt returns forward slashes."""
    monkeypatch.setattr(os, "path", ntpath)


def test_get_open_file_name_returns_native_separators(windows_paths, monkeypatch):
    monkeypatch.setattr(
        file_dialog.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: ("C:/Program Files/DisplayCAL/ti1/a.ti1", "f")),
    )
    assert file_dialog.get_open_file_name(None, "caption") == (
        "C:\\Program Files\\DisplayCAL\\ti1\\a.ti1",
        "f",
    )


def test_get_open_file_names_returns_native_separators(windows_paths, monkeypatch):
    monkeypatch.setattr(
        file_dialog.QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *a, **k: (["C:/a/b.ti3", "C:/a/c.ti3"], "f")),
    )
    assert file_dialog.get_open_file_names(None, "caption") == (
        ["C:\\a\\b.ti3", "C:\\a\\c.ti3"],
        "f",
    )


def test_get_save_file_name_returns_native_separators(windows_paths, monkeypatch):
    monkeypatch.setattr(
        file_dialog.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("C:/a/b.icc", "f")),
    )
    assert file_dialog.get_save_file_name(None, "caption") == ("C:\\a\\b.icc", "f")


def test_get_existing_directory_returns_native_separators(windows_paths, monkeypatch):
    monkeypatch.setattr(
        file_dialog.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *a, **k: "C:/a/b"),
    )
    assert file_dialog.get_existing_directory(None, "caption") == "C:\\a\\b"


@pytest.mark.parametrize(
    "name, cancelled",
    [
        ("getOpenFileName", ("", "")),
        ("getSaveFileName", ("", "")),
        ("getExistingDirectory", ""),
        ("getOpenFileNames", ([], "")),
    ],
)
def test_cancelled_dialog_returns_empty(monkeypatch, name, cancelled):
    # os.path.normpath("") would return "." and look like a chosen path
    monkeypatch.setattr(
        file_dialog.QFileDialog, name, staticmethod(lambda *a, **k: cancelled)
    )
    wrapper = {
        "getOpenFileName": file_dialog.get_open_file_name,
        "getSaveFileName": file_dialog.get_save_file_name,
        "getExistingDirectory": file_dialog.get_existing_directory,
        "getOpenFileNames": file_dialog.get_open_file_names,
    }[name]
    assert wrapper(None, "caption") == cancelled
