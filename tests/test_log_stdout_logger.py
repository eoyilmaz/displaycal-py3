"""Tests for DisplayCAL.log.StdoutLogger (issue #986).

print() output has to reach the log file even when sys.stdout is discarded,
like it is in a frozen windowed executable.
"""

import io
import logging
import sys
import threading

import pytest

from DisplayCAL import log


@pytest.fixture
def logged(monkeypatch):
    """Capture lines passed to log.LOG."""
    lines = []
    monkeypatch.setattr(log, "LOG", lines.append)
    return lines


class Blackhole:
    """Mimic py2exe's windowed sys.stdout, which has no isatty()."""

    def write(self, text):
        pass

    def flush(self):
        pass


def test_complete_lines_are_logged_and_passed_through(logged):
    stream = io.StringIO()
    out = log.StdoutLogger(stream)
    print("Loading calibration curves...", file=out)
    print("1.", "PA279CRV", "...ok.", file=out)
    assert logged == ["Loading calibration curves...", "1. PA279CRV ...ok."]
    assert stream.getvalue() == ("Loading calibration curves...\n1. PA279CRV ...ok.\n")


def test_partial_line_is_logged_once_complete(logged):
    out = log.StdoutLogger(None)
    print("Menu command:", end=" ", file=out)
    assert logged == []
    print("Set calibration state to load profile vcgt", file=out)
    assert logged == ["Menu command: Set calibration state to load profile vcgt"]


def test_none_stream_is_logged_and_stays_falsy(logged):
    out = log.StdoutLogger(None)
    print("no console", file=out)
    assert logged == ["no console"]
    # existing `sys.stdout and hasattr(sys.stdout, "isatty")` checks must not
    # change behavior just because stdout got wrapped
    assert not out
    assert not hasattr(out, "isatty")


def test_attributes_are_delegated_to_wrapped_stream(logged):
    out = log.StdoutLogger(Blackhole())
    assert out
    # py2exe's Blackhole has no isatty(), so Worker.exec_cmd() must keep
    # seeing no isatty() either
    assert not hasattr(out, "isatty")
    tty = log.StdoutLogger(io.StringIO())
    assert tty.isatty() is False
    assert tty.getvalue() == ""


def test_lines_from_different_threads_are_not_mixed(logged):
    out = log.StdoutLogger(None)
    print("main thread:", end=" ", file=out)

    def other():
        print("other thread", file=out)

    thread = threading.Thread(target=other)
    thread.start()
    thread.join()
    print("done", file=out)
    assert logged == ["other thread", "main thread: done"]


def test_logging_that_prints_does_not_recurse(monkeypatch):
    lines = []
    out = log.StdoutLogger(None)

    def log_and_print(line):
        lines.append(line)
        out.write("printed while logging\n")

    monkeypatch.setattr(log, "LOG", log_and_print)
    print("hello", file=out)
    assert lines == ["hello"]


def test_install_stdout_logger_wraps_only_once(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    log.install_stdout_logger()
    wrapped = sys.stdout
    assert isinstance(wrapped, log.StdoutLogger)
    assert wrapped.stream is stream
    log.install_stdout_logger()
    assert sys.stdout is wrapped


def test_setup_logging_writes_print_output_to_log_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(log, "LOGGER", None)
    monkeypatch.setattr(log, "_LOGDIR", None)
    # setup_logging() configures the root logger, restore it afterwards
    root = logging.getLogger()
    monkeypatch.setattr(root, "level", root.level)
    monkeypatch.setattr(root, "propagate", root.propagate)
    handlers = list(root.handlers)
    log.setup_logging(str(tmp_path), "DisplayCAL-apply-profiles", ".exe")
    try:
        print("Enumerating display adapters and devices:")
        for handler in log.LOGGER.handlers:
            handler.flush()
        logfile = tmp_path / "DisplayCAL-apply-profiles.log"
        assert "Enumerating display adapters and devices:" in logfile.read_text()
    finally:
        for handler in list(root.handlers):
            if handler not in handlers:
                handler.close()
                root.removeHandler(handler)
