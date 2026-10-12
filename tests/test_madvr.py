"""madTPG stream framing and measurement setup regressions."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from DisplayCAL import config, madvr
from DisplayCAL import worker as worker_module
from DisplayCAL.debughelpers import UnloggedInfo
from DisplayCAL.worker import Worker

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "chunks, expected",
    [
        ([slice(0, 8), slice(8, 20), slice(20, None)], [1, 2]),
        ([slice(0, 70), slice(70, None)], [1, 2]),
        ([slice(None)], [1, 2]),
        ([slice(0, 20)], []),
    ],
    ids=["split-header-and-body", "complete-plus-partial", "coalesced", "partial-eof"],
)
def test_receive_handler_preserves_packet_boundaries(
    monkeypatch: pytest.MonkeyPatch, chunks: list[slice], expected: list[int]
) -> None:
    """TCP recv boundaries must not truncate or replay protocol records."""
    monkeypatch.setattr(madvr, "get_network_addr", lambda: "127.0.0.1")
    client = madvr.MadTPGNet()
    addr = ("127.0.0.1", 60562)
    conn = MagicMock()
    conn.getpeername.return_value = addr
    packets = b"".join(
        client._assemble(conn, number, "ShowRGB", b"payload") for number in (1, 2)
    )
    conn.recv.side_effect = [packets[chunk] for chunk in chunks] + [b""]
    client._client_sockets[addr] = conn
    client.listening = True
    monkeypatch.setattr(client, "_hello", lambda conn: True)
    processed = MagicMock()
    monkeypatch.setattr(client, "_process", processed)

    client._receive_handler(addr, conn)

    assert [call.args[0]["commandNo"] for call in processed.call_args_list] == expected
    assert addr not in client._client_sockets
    assert addr not in client._incoming


def test_receive_handler_discards_bad_packet_then_receives_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid CRC must not leave a text buffer for the next byte packet."""
    monkeypatch.setattr(madvr, "get_network_addr", lambda: "127.0.0.1")
    client = madvr.MadTPGNet()
    addr = ("127.0.0.1", 60562)
    conn = MagicMock()
    conn.getpeername.return_value = addr
    packet = client._assemble(conn, 1, "ShowRGB", b"payload")
    conn.recv.side_effect = [b"bad!" + packet[4:], packet, b""]
    client._client_sockets[addr] = conn
    client.listening = True
    monkeypatch.setattr(client, "_hello", lambda conn: True)
    processed = MagicMock()
    monkeypatch.setattr(client, "_process", processed)

    client._receive_handler(addr, conn)

    processed.assert_called_once()
    assert processed.call_args.args[0]["commandNo"] == 1


@pytest.mark.parametrize("network", [True, False], ids=["network", "native"])
@pytest.mark.parametrize("connect_error", [False, True], ids=["setup", "failure"])
def test_worker_madtpg_measurement_setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    network: bool,
    connect_error: bool,
) -> None:
    """Exercise actual worker setup and cleanup without Argyll or a live display."""
    config.initcfg()
    config.setcfg("patterngenerator.use_pattern_window", 0)
    config.setcfg("patterngenerator.ffp_insertion", 0)
    monkeypatch.setattr(config, "get_display_name", lambda *args: "madVR")
    monkeypatch.setattr(worker_module.wx, "CallAfter", lambda *args: None)
    peer = MagicMock()
    peer.__class__ = madvr.MadTPGNet if network else madvr.MadTPG
    peer.get_version.return_value = madvr.MIN_VERSION
    peer.is_use_fullscreen_button_pressed.return_value = False
    peer.get_black_and_white_level.return_value = (0, 255)
    peer.get_pattern_config.return_value = (10, 0, 0, 0)
    failure = OSError("connection failed")
    if connect_error:
        peer.connect.side_effect = failure
    worker = Worker()
    worker.madtpg = peer
    worker.instrument_on_screen = True
    worker.argyll_virtual_display = "dummy" if network else None
    worker.argyll_version = [3, 3, 0]
    worker.tempdir = os.fspath(tmp_path)
    worker.log = MagicMock()

    result = worker.exec_cmd(
        "dispread",
        ["-dmadvr", os.fspath(tmp_path / "probe")],
        dry_run=True,
        skip_scripts=True,
        log_output=False,
    )

    if connect_error:
        assert result is failure
        if network:
            peer.disconnect.assert_called_once()
    else:
        assert isinstance(result, UnloggedInfo)
        assert bool(worker.use_madnet_tpg) is network
        peer.set_device_gamma_ramp.assert_called_once_with(None)
        peer.disable_3dlut.assert_called_once()
        if network:
            peer.disconnect.assert_called_once()
