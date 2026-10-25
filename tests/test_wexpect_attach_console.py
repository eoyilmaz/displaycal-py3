"""Tests for the AttachConsole retry logic in DisplayCAL.wexpect (issue #990)."""

# Standard Library Imports
from __future__ import annotations

import sys
import time
from unittest.mock import patch

# Third Party Imports
import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="wexpect console switching is Windows only"
)

if sys.platform == "win32":
    # Third Party Imports
    import pywintypes

    # Local Imports
    from DisplayCAL import wexpect


def _make_wtty() -> wexpect.Wtty:
    """Return a Wtty instance without spawning a real console process."""
    wtty = object.__new__(wexpect.Wtty)
    wtty._Wtty__switch = True
    wtty._Wtty__oproc = object()
    wtty.conpid = 1234
    wtty._Wtty__parentPid = 5678
    wtty.console = True
    wtty.processList = [5678, 1234]
    wtty.getConsoleOut = lambda: "CONOUT"
    return wtty


def _flaky_attach(fail_count: int, fail_pid: int | None = None) -> tuple:
    """Return an AttachConsole replacement that fails ``fail_count`` times.

    If ``fail_pid`` is given, only attaching to that pid fails.
    """
    calls = {"n": 0, "pids": []}

    def attach(pid: int) -> None:
        calls["pids"].append(pid)
        if fail_pid is not None and pid != fail_pid:
            return
        calls["n"] += 1
        if calls["n"] <= fail_count:
            raise pywintypes.error(1, "AttachConsole", "Incorrect function.")

    return attach, calls


def _patches(attach: object) -> tuple:
    return (
        patch.object(wexpect, "AttachConsole", attach),
        patch.object(wexpect, "FreeConsole", lambda: None),
        patch.object(wexpect, "GetStdHandle", lambda handle: "CONIN"),
        patch.object(wexpect, "GetExitCodeProcess", lambda h: wexpect.STILL_ACTIVE),
        patch.object(wexpect, "log", lambda *args, **kwargs: None),
    )


def test_switch_to_retries_transient_attach_console_failure() -> None:
    """A few transient AttachConsole failures must not raise."""
    wtty = _make_wtty()
    attach, calls = _flaky_attach(5)
    p1, p2, p3, p4, p5 = _patches(attach)
    with p1, p2, p3, p4, p5:
        wtty.switchTo()
    assert calls["n"] == 6
    assert wtty._Wtty__consout == "CONOUT"


def test_switch_to_raises_after_retry_timeout() -> None:
    """A persistent failure still raises once the retry window is exhausted."""
    wtty = _make_wtty()
    attach, _calls = _flaky_attach(10**9)
    p1, p2, p3, p4, p5 = _patches(attach)
    start = time.time()
    with p1, p2, p3, p4, p5, pytest.raises(pywintypes.error):
        wtty.switchTo(retry_timeout=0.2)
    assert time.time() - start < 5


def test_read_nonblocking_returns_no_data_when_attach_keeps_failing() -> None:
    """read_nonblocking must report "no data" instead of crashing."""
    wtty = _make_wtty()
    attach, _calls = _flaky_attach(10**9)
    p1, p2, p3, p4, p5 = _patches(attach)
    with p1, p2, p3, p4, p5:
        assert wtty.read_nonblocking(0.1, 1) == ""


def test_read_nonblocking_reattaches_parent_console_on_failure() -> None:
    """Giving up on the child console must re-attach the parent console."""
    wtty = _make_wtty()
    attach, calls = _flaky_attach(10**9, fail_pid=1234)
    p1, p2, p3, p4, p5 = _patches(attach)
    with p1, p2, p3, p4, p5:
        assert wtty.read_nonblocking(0.1, 1) == ""
    assert calls["pids"][-1] == 5678
    assert wtty._Wtty__consout is None


def test_switch_back_retries_transient_attach_console_failure() -> None:
    """A few transient failures re-attaching the parent console must not raise."""
    wtty = _make_wtty()
    attach, calls = _flaky_attach(3)
    p1, p2, p3, p4, p5 = _patches(attach)
    with p1, p2, p3, p4, p5:
        wtty.switchBack()
    assert calls["pids"] == [5678] * 4
    assert wtty._Wtty__consout is None
