"""DisplayCAL's exit handler runs when the Qt UI quits.

It takes this instance's port out of the lock file (the next start would try
it first), ends child processes and waits for threads. It was registered
with wx's BaseApp only, which never runs with the Qt UI.
"""

import os
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("qtpy")

from DisplayCAL import main  # noqa: E402
from DisplayCAL.ui.application import Application  # noqa: E402


@pytest.fixture
def lock_file(tmp_path):
    """A lock file listing this instance (PID:port), as initialize_app writes it."""
    path = tmp_path / "DisplayCAL.lock"
    path.write_text(f"{os.getpid()}:{15411}\n")
    return str(path)


def test_quitting_the_qt_ui_takes_our_port_out_of_the_lock_file(lock_file, monkeypatch):
    monkeypatch.setattr(main, "get_ui_toolkit", lambda: "qt")
    monkeypatch.setattr(main, "initialize_qt_module", lambda: None)
    # The Qt app quitting: Application runs its exit handlers on aboutToQuit
    monkeypatch.setattr(main, "_get_qt_main", lambda module: Application._run_exitfuncs)
    monkeypatch.setattr(main, "_EXIT_ARGS", (lock_file, 15411))
    monkeypatch.setattr(Application, "_exithandlers", [])

    main.run_app("")

    remaining = Path(lock_file).read_text() if os.path.exists(lock_file) else ""
    assert "15411" not in remaining


def test_a_hanging_thread_does_not_hold_the_quit(monkeypatch):
    monkeypatch.setattr(main, "_THREAD_EXIT_TIMEOUT", 0.2)
    release = threading.Event()
    thread = threading.Thread(target=release.wait, name="stuck", daemon=False)
    thread.start()
    try:
        start = time.monotonic()
        main._exit("", "")
        assert time.monotonic() - start < 5
    finally:
        release.set()
        thread.join()
