"""check_set_argyll_bin() uses the active UI's own "Argyll not found" prompt.

The Qt UI calls argyll.check_set_argyll_bin() from 22 places (calibrate,
profile, 3D LUT, testchart editor, ...). When Argyll was missing it opened
the wx dialogs of argyll.set_argyll_bin(), creating a wx.App inside the Qt
application; wx and Qt in one process crash with an access violation on
Windows (seen in the test suite on 2026-11-11).
"""

import gc

import pytest

from DisplayCAL import argyll, config


@pytest.fixture
def argyll_missing(monkeypatch):
    """Argyll is not found until the prompt "installs" it."""
    state = {"found": False, "wx_dialog": 0}
    monkeypatch.setattr(argyll, "check_argyll_bin", lambda paths=None: state["found"])

    def wx_set_argyll_bin(*args, **kwargs):
        state["wx_dialog"] += 1
        return False

    monkeypatch.setattr(argyll, "set_argyll_bin", wx_set_argyll_bin)
    yield state
    argyll.set_missing_argyll_prompt(None)


class Window:
    def __init__(self, state):
        self.state = state
        self.prompts = 0

    def prompt(self):
        self.prompts += 1
        self.state["found"] = True


def test_qt_prompt_is_used_when_running_qt(argyll_missing, monkeypatch):
    monkeypatch.setattr(config, "get_ui_toolkit", lambda: "qt")
    window = Window(argyll_missing)
    argyll.set_missing_argyll_prompt(window.prompt)

    assert argyll.check_set_argyll_bin() is True
    assert window.prompts == 1
    assert argyll_missing["wx_dialog"] == 0


def test_result_is_false_when_the_prompt_was_cancelled(argyll_missing, monkeypatch):
    monkeypatch.setattr(config, "get_ui_toolkit", lambda: "qt")
    cancelled = []
    argyll.set_missing_argyll_prompt(lambda: cancelled.append(True))

    assert argyll.check_set_argyll_bin() is False
    assert cancelled == [True]
    assert argyll_missing["wx_dialog"] == 0


def test_wx_dialog_is_kept_when_running_wx(argyll_missing, monkeypatch):
    monkeypatch.setattr(config, "get_ui_toolkit", lambda: "wx")
    window = Window(argyll_missing)
    argyll.set_missing_argyll_prompt(window.prompt)

    assert argyll.check_set_argyll_bin() is False
    assert window.prompts == 0
    assert argyll_missing["wx_dialog"] == 1


def test_closed_window_prompt_is_not_kept_alive(argyll_missing, monkeypatch):
    monkeypatch.setattr(config, "get_ui_toolkit", lambda: "qt")
    window = Window(argyll_missing)
    argyll.set_missing_argyll_prompt(window.prompt)
    del window
    gc.collect()

    assert argyll.check_set_argyll_bin() is False
    assert argyll_missing["wx_dialog"] == 1


def test_found_argyll_needs_no_prompt(argyll_missing, monkeypatch):
    monkeypatch.setattr(config, "get_ui_toolkit", lambda: "qt")
    argyll_missing["found"] = True
    argyll.set_missing_argyll_prompt(lambda: pytest.fail("no prompt needed"))

    assert argyll.check_set_argyll_bin() is True
