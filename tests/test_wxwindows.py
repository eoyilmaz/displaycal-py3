import sys
from unittest import mock

import pytest

from DisplayCAL import wx_windows
from DisplayCAL.wx_windows import BaseFrame, fancytext_RenderToRenderer, responseformats


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


@pytest.mark.parametrize(
    "progress_type,expected_count",
    [(0, 137), (1, 15), (2, 63)],
)
def test_progress_dialog_get_bitmaps_frame_counts(progress_type, expected_count):
    """ProgressDialog.get_bitmaps() must not silently return [] on a frame-count mismatch.

    Regression test for the processing (progress_type 0) animation having
    silently shown nothing since #45 added a 10th shutter_anim frame in 2022,
    breaking get_bitmaps' hardcoded "needs exactly 17 images" sanity check.
    """
    import wx

    from DisplayCAL.wx_windows import ProgressDialog

    app = wx.GetApp() or wx.App()  # noqa: F841 -- must stay referenced, see wx docs.
    # get_bitmaps caches per progress_type at the class level; clear it so
    # this test doesn't depend on execution order.
    ProgressDialog.bitmaps.pop(progress_type, None)
    bitmaps = ProgressDialog.get_bitmaps(progress_type)
    assert len(bitmaps) == expected_count


@pytest.mark.skip(
    reason="TODO: This test is moved from the module, properly implement it."
)
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


@pytest.fixture
def scripting_conn():
    """Provide a mock client connection registered with the scripting host."""
    conn = mock.MagicMock()
    responseformats[conn] = "json"
    yield conn
    responseformats.pop(conn, None)


def test_send_response_ignores_client_that_disconnects_while_responding(
    scripting_conn,
):
    """A client disconnecting during send_response must not raise KeyError."""

    def disconnect(*args):
        responseformats.pop(scripting_conn, None)
        scripting_conn.sendall.side_effect = ConnectionResetError()
        return "invalid"

    with mock.patch.object(wx_windows.lang, "getstr", side_effect=disconnect):
        BaseFrame.send_response(None, "invalid", ["GET"], scripting_conn, "now")


def test_finish_processing_ignores_client_that_disconnects_mid_command(
    scripting_conn,
):
    """A client disconnecting during finish_processing must not raise KeyError."""
    frame = mock.MagicMock()
    frame.get_top_window.return_value = None
    frame.process_data.side_effect = RuntimeError("boom")

    def disconnect(file_format):
        responseformats.pop(scripting_conn, None)
        return "idle"

    frame.get_app_state.side_effect = disconnect

    BaseFrame.finish_processing(frame, ["GET", "/", "HTTP/1.1"], scripting_conn, "now")

    frame.send_response.assert_called_once()
