"""The "ArgyllCMS not found" choice dialog shows a wrapped message.

wx.SingleChoiceDialog doesn't wrap its message, so the one long sentence
made a very wide, flat dialog.
"""

from DisplayCAL import argyll
from DisplayCAL import localization as lang
from DisplayCAL.wx_addons import wx


class _Parent:
    def IsShownOnScreen(self):  # noqa: N802
        return True


def test_argyll_not_found_choice_message_is_wrapped(monkeypatch):
    lang.init()
    captured = {}

    class FakeSingleChoiceDialog:
        def __init__(self, parent, message, caption, choices, style=0):
            captured["message"] = message

        def SetSelection(self, index):  # noqa: N802
            pass

        def ShowModal(self):  # noqa: N802
            return wx.ID_CANCEL

        def GetSelection(self):  # noqa: N802
            return 0

        def Destroy(self):  # noqa: N802
            pass

    # No real wx.App: one in the same process as the Qt tests makes those
    # crash with an access violation on Windows
    monkeypatch.setattr(wx, "GetApp", lambda: object())
    monkeypatch.setattr(argyll, "prompt_argyll_dir", lambda *args: None)
    monkeypatch.setattr(argyll, "check_argyll_bin", lambda *args: False)
    monkeypatch.setattr(argyll, "get_homebrew_argyll_bin", lambda: None)
    monkeypatch.setattr(wx, "SingleChoiceDialog", FakeSingleChoiceDialog)

    assert argyll.set_argyll_bin(_Parent()) is False

    message = captured["message"]
    assert " ".join(message.split()) == " ".join(
        lang.getstr("dialog.argyll.notfound.choice").split()
    )
    assert max(len(line) for line in message.splitlines()) <= 70
