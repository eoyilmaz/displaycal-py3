"""Tests for the "already running" check of DisplayCAL.main on Windows.

Started through the ``displaycal.exe`` launcher that pip/uv create for the
gui-script entry point, DisplayCAL runs in a child of a process that is itself
named ``displaycal.exe``. The check used to take that launcher for another
running instance and refused to start ("already running").
"""

import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_get_ancestor_pids_contains_parent_of_child_process():
    """A child process sees the test process among its ancestors."""
    code = (
        "from DisplayCAL.util_win import get_ancestor_pids; "
        "print(sorted(get_ancestor_pids()))"
    )
    output = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout

    ancestors = eval(output)  # list of ints printed by the child
    assert os.getpid() in ancestors


def test_get_ancestor_pids_excludes_own_pid():
    """The process itself isn't one of its ancestors."""
    from DisplayCAL.util_win import get_ancestor_pids

    assert os.getpid() not in get_ancestor_pids()


def _run_check(monkeypatch, processes, ancestors):
    """Run terminate_conflicting_instance with a fake process list."""
    import win32ts

    from DisplayCAL import main, util_win

    monkeypatch.setattr(win32ts, "WTSEnumerateProcesses", lambda: processes)
    monkeypatch.setattr(win32ts, "ProcessIdToSessionId", lambda pid: 1)
    monkeypatch.setattr(util_win, "get_ancestor_pids", lambda pid=None: ancestors)
    return main.terminate_conflicting_instance(None, "unused.lock", None, None, None)


def test_launcher_named_like_the_app_is_not_another_instance(monkeypatch):
    """Our own displaycal.exe launcher doesn't block the start."""
    launcher_pid = 4242
    processes = [(1, launcher_pid, "displaycal.exe", None)]

    incoming = _run_check(monkeypatch, processes, {launcher_pid})

    assert incoming is None


def test_other_instance_in_same_session_is_still_detected(monkeypatch):
    """A displaycal.exe that isn't our ancestor is another instance."""
    processes = [(1, 4243, "displaycal.exe", None)]

    incoming = _run_check(monkeypatch, processes, {4242})

    assert incoming is False


def test_a_reused_pid_of_a_dead_ancestor_is_not_an_ancestor(monkeypatch):
    """The launcher (PID 50) exited and PID 20 now belongs to a process created
    after it, e.g. another DisplayCAL: that one isn't ours."""
    from DisplayCAL import util_win

    monkeypatch.setattr(util_win, "_get_parent_pids", lambda: {100: 50, 50: 20, 20: 4})
    created = {100: 10.0, 50: 5.0, 20: 30.0, 4: 1.0}
    monkeypatch.setattr(util_win, "_creation_time", created.get)

    assert util_win.get_ancestor_pids(100) == {50}


def test_ancestors_with_unknown_creation_time_end_the_walk(monkeypatch):
    from DisplayCAL import util_win

    monkeypatch.setattr(util_win, "_get_parent_pids", lambda: {100: 50, 50: 20})
    created = {100: 10.0, 50: None}
    monkeypatch.setattr(util_win, "_creation_time", created.get)

    assert util_win.get_ancestor_pids(100) == set()
