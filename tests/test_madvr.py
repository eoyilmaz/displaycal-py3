"""madTPG stream framing and measurement setup regressions."""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from DisplayCAL import config, madvr
from DisplayCAL import worker as worker_module
from DisplayCAL.debughelpers import UnloggedInfo
from DisplayCAL.worker import Worker

_PROTOCOL = json.loads(
    (Path(__file__).parent / "data" / "madvr-protocol.json").read_text(encoding="utf-8")
)
_HELLO = bytes.fromhex(_PROTOCOL["hello"]["hex"])
_CONFIRM = bytes.fromhex(_PROTOCOL["confirm"]["hex"])
_HELLO_PARAMS = _PROTOCOL["hello"]["expected"]["params"]


@pytest.fixture
def madtpg_client(monkeypatch: pytest.MonkeyPatch) -> madvr.MadTPGNet:
    """Keep interface discovery local; protocol methods run unchanged."""
    monkeypatch.setattr(madvr, "get_network_addr", lambda: "127.0.0.1")
    return madvr.MadTPGNet()


@pytest.mark.parametrize("name", ["stop", "hello", "confirm"])
def test_parse_vendor_protocol_examples(
    madtpg_client: madvr.MadTPGNet, name: str
) -> None:
    """Check every decoded field against the vendor specification's examples."""
    fixture = _PROTOCOL[name]
    expected = dict(fixture["expected"], magic=b"mad.")
    expected["component"] = expected["component"].encode("ascii")
    if isinstance(expected["params"], str):
        expected["params"] = expected["params"].encode("ascii")

    record, remaining = madtpg_client._parse(bytes.fromhex(fixture["hex"]))

    assert record == expected
    assert remaining == b""


def receive_chunks(client: madvr.MadTPGNet, chunks: list[bytes]) -> tuple[list, dict]:
    """Run the receiver and observe its state immediately before EOF cleanup."""
    addr = ("127.0.0.2", 60562)  # Higher-IP peer is the master (section C).
    conn = MagicMock(spec=socket.socket)
    conn.getpeername.return_value = addr
    conn.getsockname.return_value = ("127.0.0.1", 60562)
    conn.send.side_effect = len
    fragments = iter(chunks)
    received = []
    peer_state = {}

    def recv(size: int) -> bytes:
        fragment = next(fragments, b"")
        assert len(fragment) <= size
        if not fragment:
            received.extend(client._incoming[addr])
            peer_state.update(client.clients.get(addr, {}))
        return fragment

    conn.recv.side_effect = recv
    client._client_sockets[addr] = conn
    client.listening = True
    client._receive_handler(addr, conn)

    assert addr not in client._client_sockets
    assert addr not in client._incoming
    assert addr not in client.clients
    conn.close.assert_called_once()
    return received, peer_state


@pytest.mark.parametrize(
    "chunks, expected",
    [
        ([_HELLO[:8], _HELLO[8:20], _HELLO[20:] + _CONFIRM], ["hello", "confirm"]),
        ([_HELLO + _CONFIRM[:20], _CONFIRM[20:]], ["hello", "confirm"]),
        ([_HELLO + _CONFIRM], ["hello", "confirm"]),
        ([_HELLO[:20]], []),
        ([_HELLO + _CONFIRM[:20]], ["hello"]),
    ],
    ids=[
        "split-header-and-body",
        "complete-plus-partial",
        "coalesced",
        "partial-eof",
        "complete-plus-partial-eof",
    ],
)
def test_receive_handler_preserves_packet_boundaries(
    madtpg_client: madvr.MadTPGNet, chunks: list[bytes], expected: list[str]
) -> None:
    """Fragmented messages must reach real decoding and connection processing."""
    received, peer_state = receive_chunks(madtpg_client, chunks)
    messages = {
        "hello": (1, "hello", _HELLO_PARAMS, b""),
        "confirm": (2, "confirm", b"", b""),
    }
    assert received == [messages[name] for name in expected]
    if "hello" in expected:
        assert peer_state == {
            "processId": 160,
            "module": 1073741824,
            "component": b"",
            "instance": 0,
            **_HELLO_PARAMS,
            **({"confirmed": True} if "confirm" in expected else {}),
        }
    else:
        assert peer_state == {}


def test_receive_handler_discards_bad_packet_then_receives_next(
    madtpg_client: madvr.MadTPGNet,
) -> None:
    """A deliberately damaged CRC must not poison the next valid message."""
    damaged = bytearray(_HELLO)
    damaged[8] ^= 1  # Alter only the CRC of the otherwise valid vendor example.
    received, peer_state = receive_chunks(madtpg_client, [bytes(damaged), _HELLO])

    assert received == [(1, "hello", _HELLO_PARAMS, b"")]
    assert peer_state["computerName"] == "HTPC"


@pytest.mark.parametrize("network", [True, False], ids=["network-type", "native-type"])
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
    # Resolve Argyll utility names without an installed Argyll on PATH.
    monkeypatch.setattr(
        worker_module, "get_argyll_utilname", lambda name, paths=None: name
    )
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
