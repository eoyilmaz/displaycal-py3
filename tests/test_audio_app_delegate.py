"""pyglet (the sounds) leaves Qt's application delegate alone on macOS.

Loaded before Qt's event loop runs (the startup sound), pyglet made its own
delegate the application's. That delegate lets macOS end the process at once
on a Quit from the Dock, at logout or shutdown: DisplayCAL's windows never
closed (window position unsaved, listening socket left open) and PySide
crashed tearing them down. Run in a process of its own: the delegate is the
whole application's.
"""

import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")

CHILD = textwrap.dedent(
    """
    from qtpy.QtWidgets import QApplication

    from DisplayCAL import audio, util_mac

    app = QApplication([])
    before = util_mac.app_delegate_class()
    audio._init_pyglet()
    import pyglet.media  # what the first sound does

    pyglet.media.Player  # noqa: B018
    print(before, util_mac.app_delegate_class())
    """
)


def test_pyglet_keeps_the_qt_application_delegate():
    result = subprocess.run(
        [sys.executable, "-c", CHILD],
        # Qt's own delegate comes with the real (Cocoa) platform only
        env=dict(os.environ, QT_QPA_PLATFORM="cocoa"),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    before, after = result.stdout.split()[-2:]
    assert before.startswith("QCocoa")
    assert after == before
