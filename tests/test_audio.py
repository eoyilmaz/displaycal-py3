"""Audio backend initialization regressions."""

from __future__ import annotations

import importlib
import sys

import pytest

from DisplayCAL import audio

pytest.importorskip("pyglet")


def test_init_pyglet_blocks_gstreamer_decoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """pyglet must not load its GStreamer decoder (#1022).

    The decoder runs a GLib main loop on the default main context in a
    background thread, which then dispatches wx's GTK timers off the main
    thread.
    """
    monkeypatch.delitem(sys.modules, "pyglet.media.codecs.gstreamer", raising=False)
    # _init_pyglet() sets these, have monkeypatch restore them afterwards
    for name in ("_SERVER", "_LIB", "_LIB_VERSION"):
        monkeypatch.setattr(audio, name, getattr(audio, name))

    audio._init_pyglet()

    assert audio._LIB == "pyglet"
    assert sys.modules["pyglet.media.codecs.gstreamer"] is None
    with pytest.raises(ImportError):
        importlib.import_module("pyglet.media.codecs.gstreamer")
