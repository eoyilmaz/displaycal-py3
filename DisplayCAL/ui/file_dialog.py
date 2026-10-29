"""Wrappers around the static :class:`QFileDialog` getters.

Qt always returns paths with forward slashes, on Windows too
(``C:/Users/...``), while wx's ``FileDialog`` returned native backslash
paths. Paths the rest of DisplayCAL builds itself with
``os.path`` use backslashes on Windows, so a dialog path compared against or
looked up in one of those (e.g. the testchart list) never matches, see issue
1028. Every path these wrappers return is run through
:func:`os.path.normpath`, which converts it to native separators. It is a
no-op for the absolute paths the dialogs return on macOS and Linux.
"""

from __future__ import annotations

import os

from qtpy.QtWidgets import QFileDialog


def get_open_file_name(*args, **kwargs) -> tuple[str, str]:
    """Wrap :meth:`QFileDialog.getOpenFileName` (see module docstring)."""
    path, selected_filter = QFileDialog.getOpenFileName(*args, **kwargs)
    return (os.path.normpath(path) if path else path), selected_filter


def get_open_file_names(*args, **kwargs) -> tuple[list[str], str]:
    """Wrap :meth:`QFileDialog.getOpenFileNames` (see module docstring)."""
    paths, selected_filter = QFileDialog.getOpenFileNames(*args, **kwargs)
    return [os.path.normpath(path) for path in paths], selected_filter


def get_save_file_name(*args, **kwargs) -> tuple[str, str]:
    """Wrap :meth:`QFileDialog.getSaveFileName` (see module docstring)."""
    path, selected_filter = QFileDialog.getSaveFileName(*args, **kwargs)
    return (os.path.normpath(path) if path else path), selected_filter


def get_existing_directory(*args, **kwargs) -> str:
    """Wrap :meth:`QFileDialog.getExistingDirectory` (see module docstring)."""
    path = QFileDialog.getExistingDirectory(*args, **kwargs)
    return os.path.normpath(path) if path else path
