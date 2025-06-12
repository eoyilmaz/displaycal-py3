import sys

import pytest

from DisplayCAL.wx_windows import fancytext_RenderToRenderer


def test_fancytext_render_to_renderer():
    """Testing DisplayCAL.wx_windows.fancytext_RenderToRenderer()"""

    class FakeRenderer:
        def __init__(self):
            self.startElement = None
            self.endElement = None
            self.characterData = None

    renderer = FakeRenderer()
    some_test_str = "some_str_"
    fancytext_RenderToRenderer(some_test_str, renderer, enclose=True)


@pytest.mark.skip(reason="TODO: This test is moved from the module, properly implement it.")
def test_wxwindows():
    import wx
    from DisplayCAL import config
    from DisplayCAL import localization as lang
    from DisplayCAL.wx_windows import BaseApp, ProgressDialog, SimpleTerminal

    config.initcfg()
    lang.init()

    def key_handler(self, event):
        if event.GetEventType() == wx.EVT_CHAR_HOOK.typeId:
            print(
                "Received EVT_CHAR_HOOK",
                event.GetKeyCode(),
                repr(chr(event.GetKeyCode())),
            )
        elif event.GetEventType() == wx.EVT_KEY_DOWN.typeId:
            print(
                "Received EVT_KEY_DOWN",
                event.GetKeyCode(),
                repr(chr(event.GetKeyCode())),
            )
        elif event.GetEventType() == wx.EVT_MENU.typeId:
            print(
                "Received EVT_MENU",
                self.id_to_keycode.get(event.GetId()),
                repr(chr(self.id_to_keycode.get(event.GetId()))),
            )
        event.Skip()

    ProgressDialog.key_handler = key_handler
    SimpleTerminal.key_handler = key_handler

    app = BaseApp(0)
    style = wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH
    _ = ProgressDialog(
        msg="".join("Test " * 5),
        maximum=10000,
        style=style,
        pauseable=True,
        fancy="+fancy" not in sys.argv[1:],
        allow_close=True,
    )
    # t = SimpleTerminal(start_timer=False)
    app.MainLoop()
