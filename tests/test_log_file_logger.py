"""The application log keeps working while other file loggers come and go.

``get_file_logger()`` used to rebind the module-wide ``LOGGER`` that ``LOG()``
(and so every ``print()``) writes to. Creating the "interact" logger moved the
application log into interact.log, a session log moved it into the session
log (every line written there twice), and once the session log was closed
everything was silently dropped: the application log stopped at
"Enumerating display devices..." and the log window stayed empty.
"""

import logging
import sys

import pytest

from DisplayCAL import log

APP = "DisplayCAL-apply-profiles"


@pytest.fixture
def app_log(tmp_path, monkeypatch):
    """Return a function that sets up the application log in tmp_path.

    It has to be called inside the test: pytest swaps sys.stdout between
    fixture setup and the test call, which would drop the StdoutLogger.
    """
    monkeypatch.setattr(log, "LOGGER", None)
    monkeypatch.setattr(log, "_LOGDIR", None)
    root = logging.getLogger()
    monkeypatch.setattr(root, "level", root.level)
    monkeypatch.setattr(root, "propagate", root.propagate)
    handlers = list(root.handlers)

    def setup():
        monkeypatch.setattr(sys, "stdout", None)
        log.setup_logging(str(tmp_path), APP, ".exe")
        return tmp_path / f"{APP}.log"

    yield setup
    for handler in list(root.handlers):
        if handler not in handlers:
            handler.close()
            root.removeHandler(handler)
    for name in ("interact", "adjust"):
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def _flush_all():
    for logger in [logging.getLogger(), *logging.root.manager.loggerDict.values()]:
        for handler in getattr(logger, "handlers", []):
            handler.flush()


def _lines(path):
    if not path.exists():
        return []
    return [line.split(" ", 2)[2] for line in path.read_text().splitlines()]


def test_other_file_loggers_do_not_take_over_the_application_log(app_log, tmp_path):
    app_log = app_log()
    main_logger = log.LOGGER

    log.get_file_logger("interact", logdir=str(tmp_path))
    session = log.LogFile("session", str(tmp_path))
    print("Enumerating display devices and communication ports...")
    _flush_all()

    assert log.LOGGER is main_logger
    assert "Enumerating display devices and communication ports..." in _lines(
        app_log
    )
    assert _lines(tmp_path / "interact.log") == []
    assert _lines(tmp_path / "session.log") == []
    session.close()


def test_application_log_keeps_working_after_a_session_log_is_closed(
    app_log, tmp_path
):
    app_log = app_log()
    session = log.LogFile("session", str(tmp_path))
    session.write("Patch 64 of 64")
    session.close()

    print("Profile check complete")
    _flush_all()

    assert "Profile check complete" in _lines(app_log)


def test_session_log_lines_are_written_once(app_log, tmp_path):
    """The worker writes a line to the session log and prints it as well."""
    app_log()
    session = log.LogFile("session", str(tmp_path))

    session.write("Patch 63 of 64 DE 0.307134")
    print("Patch 63 of 64 DE 0.307134")
    _flush_all()

    assert _lines(tmp_path / "session.log") == ["Patch 63 of 64 DE 0.307134"]
    session.close()
