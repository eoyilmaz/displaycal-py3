"""Tests for the Qt scripting host's handling of clients that disconnect early."""

import os
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui import scripting  # noqa: E402
from DisplayCAL.ui.scripting import ScriptingHostMixin, responseformats  # noqa: E402


class _Host(ScriptingHostMixin):
    def __init__(self, conn, fail=False):
        self.conn = conn
        self.fail = fail

    def get_app_state(self, file_format):
        # The client's message handler thread drops the connection here.
        responseformats.pop(self.conn, None)
        return "idle"

    def process_data(self, data):
        if self.fail:
            raise RuntimeError("boom")
        return "invalid"


@pytest.fixture
def conn():
    """Provide a mock client connection registered with the scripting host."""
    conn = mock.MagicMock()
    responseformats[conn] = "json"
    yield conn
    responseformats.pop(conn, None)


def test_send_response_ignores_client_that_disconnects_while_responding(conn):
    """A client disconnecting during send_response must not raise KeyError."""

    def disconnect(*args):
        responseformats.pop(conn, None)
        conn.sendall.side_effect = ConnectionResetError()
        return "invalid"

    with mock.patch.object(scripting.lang, "getstr", side_effect=disconnect):
        ScriptingHostMixin.send_response(None, "invalid", ["GET"], conn, "now")


@pytest.mark.parametrize("fail", [False, True])
def test_finish_processing_ignores_client_that_disconnects_mid_command(conn, fail):
    """A client disconnecting during finish_processing must not raise KeyError."""
    _Host(conn, fail).finish_processing(["GET", "/", "HTTP/1.1"], conn, "now")

    conn.sendall.assert_not_called()


def test_finish_processing_still_answers_connected_client():
    """A connected client still gets the response to its command."""
    conn = mock.MagicMock()
    responseformats[conn] = "plain"
    host = _Host(conn)
    host.get_app_state = lambda file_format: "idle"
    try:
        host.finish_processing(["GET", "/", "HTTP/1.1"], conn, "now")
    finally:
        responseformats.pop(conn, None)

    conn.sendall.assert_called_once_with(b"invalid\x04")
