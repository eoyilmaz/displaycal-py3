"""Tests for util_os.waccess() on Windows folders refusing new files."""

import os

# --- waccess on a folder that refuses new files ----------------------------
# tempfile retries up to 10000 names on Windows when creating a file is
# refused but os.access() says the folder is writable (it only looks at the
# read-only attribute), so waccess(r"C:\Windows\System32", W_OK) took minutes
# and froze whatever called it.


def test_waccess_on_folder_refusing_files_gives_up_after_one_try(tmp_path, monkeypatch):
    from DisplayCAL import util_os

    calls = []
    real_open = os.open

    def refusing_open(path, flags, *args, **kwargs):
        if os.path.dirname(path) == str(tmp_path):
            calls.append(path)
            raise PermissionError(13, "Access is denied", path)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(util_os.os, "open", refusing_open)

    assert util_os.waccess(str(tmp_path), os.W_OK) is False
    assert len(calls) == 1


def test_waccess_on_writable_folder_leaves_nothing_behind(tmp_path):
    from DisplayCAL.util_os import waccess

    assert waccess(str(tmp_path), os.W_OK) is True
    assert list(tmp_path.iterdir()) == []


def test_waccess_on_missing_folder_is_false(tmp_path):
    from DisplayCAL.util_os import waccess

    assert waccess(str(tmp_path / "missing" / "deeper"), os.W_OK) is False
