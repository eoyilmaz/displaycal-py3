"""Headless tests for the Qt madVR/Prisma pattern-generator connection setup.

Exercises ``DisplayCAL.ui.patterngenerator_setup``: the pure
``prisma_upload_filename`` helper, ``PrismaHostDialog``'s discovery/
connectivity-check flow, ``connect_madvr``'s fast/slow/cancel paths,
``connect_patterngenerator``'s dispatch, ``connect_live_patterngenerator``'s
already-connected/wait/cancel paths (Resolve/Web @ localhost/Chromecast, used
by the visual whitepoint editor's live patch streaming), and
``Lut3DAPIInstallController``. Real sockets/madTPG are never touched --
``Worker.madtpg_connect``/``Worker.setup_patterngenerator`` and the pattern
generator's own ``listen``/``announce``/``connect``/``wait`` are stubbed with
fakes. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``.
"""

import os
import socket
import sys
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtWidgets import QMessageBox  # noqa: E402

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.config import getcfg, setcfg  # noqa: E402
from DisplayCAL.debughelpers import Error, Info  # noqa: E402
from DisplayCAL.ui import patterngenerator_setup as pgs  # noqa: E402
from DisplayCAL.worker import Worker  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


@pytest.fixture
def worker(qapp):
    return Worker()


def _spin_until(qapp, predicate, timeout_s=30.0):
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


class _FakePatternGenerator:
    """Minimal stand-in for ``PrismaPatternGeneratorClient``."""

    def __init__(self) -> None:
        self.listening = False
        self.host = None
        self.connected = False
        self._handlers: dict = {}

    def bind(self, event_name, handler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def disconnect_client(self) -> None:
        self.listening = False

    def listen(self) -> None:
        self.listening = True

    def announce(self) -> None:
        pass

    def connect(self) -> None:
        self.connected = True

    def emit_client_added(self, name: str) -> None:
        for handler in self._handlers.get("on_client_added", []):
            handler((None, {"name": name}))


class TestPrismaUploadFilename:
    def test_uses_input_profile_basename(self, worker, tmp_path):
        setcfg("3dlut.input.profile", "/some/path/MyProfile.icc")
        lut_path = tmp_path / "lut.3dlut"
        lut_path.write_bytes(b"x")

        filename = pgs.prisma_upload_filename(str(lut_path))

        assert filename.startswith("MyProfile-")
        assert filename.endswith(".3dl")

    def test_shortens_known_gamut_presets(self, worker, tmp_path):
        setcfg("3dlut.input.profile", "/some/path/SMPTE_RP145_NTSC.icc")
        lut_path = tmp_path / "lut.3dlut"
        lut_path.write_bytes(b"x")

        filename = pgs.prisma_upload_filename(str(lut_path))

        assert filename.startswith("NTSC-")


class TestPrismaHostDialog:
    def test_discovered_client_added_to_combo(self, qapp, worker):
        fake_pg = _FakePatternGenerator()
        worker.patterngenerator = fake_pg
        dialog = pgs.PrismaHostDialog(worker, "title", upload=False, parent=None)
        # The ".local" mDNS suffix is only appended off Windows (see
        # PrismaHostDialog's on_client_added: `sys.platform != "win32"`).
        expected = "myhost" if sys.platform == "win32" else "myhost.local"
        try:
            fake_pg.emit_client_added("myhost")
            assert dialog.host_ctrl.findText(expected) >= 0
            assert dialog.host_ctrl.currentText() == expected
        finally:
            fake_pg.listening = False

    def test_check_and_accept_success(self, qapp, worker, monkeypatch):
        fake_pg = _FakePatternGenerator()
        worker.patterngenerator = fake_pg
        monkeypatch.setattr(pgs.socket, "gethostbyname", lambda host: "1.2.3.4")
        dialog = pgs.PrismaHostDialog(worker, "title", upload=False, parent=None)
        dialog.host_ctrl.setCurrentText("prisma.local")

        dialog._check_and_accept()

        assert _spin_until(qapp, lambda: dialog.result() == pgs.QDialog.Accepted)
        assert fake_pg.host == "1.2.3.4"
        assert fake_pg.connected is True
        assert getcfg("patterngenerator.prisma.host") == "prisma.local"

    def test_check_and_accept_failure_shows_error_and_reenables_ok(
        self, qapp, worker, monkeypatch
    ):
        fake_pg = _FakePatternGenerator()
        worker.patterngenerator = fake_pg

        def _raise(host):
            raise socket.gaierror("lookup failed")

        monkeypatch.setattr(pgs.socket, "gethostbyname", _raise)
        dialog = pgs.PrismaHostDialog(worker, "title", upload=False, parent=None)
        dialog.host_ctrl.setCurrentText("bad-host")

        dialog._check_and_accept()

        assert _spin_until(
            qapp, lambda: dialog.error_label.text() != lang.getstr("please_wait")
        )
        assert dialog.error_label.text() == lang.getstr("host.invalid.lookup_failed")
        assert dialog.result() != pgs.QDialog.Accepted
        assert dialog.buttons.button(pgs.QDialogButtonBox.Ok).isEnabled()

    def test_upload_shows_preset_and_filename(self, qapp, worker, tmp_path):
        fake_pg = _FakePatternGenerator()
        worker.patterngenerator = fake_pg
        setcfg("3dlut.input.profile", "/some/path/MyProfile.icc")
        lut_path = tmp_path / "lut.3dlut"
        lut_path.write_bytes(b"x")

        dialog = pgs.PrismaHostDialog(
            worker, "title", upload=True, lut3d_path=str(lut_path), parent=None
        )

        assert dialog.preset_ctrl is not None
        assert dialog.filename.startswith("MyProfile-")

    def test_accept_persists_selected_preset(self, qapp, worker, monkeypatch, tmp_path):
        fake_pg = _FakePatternGenerator()
        worker.patterngenerator = fake_pg
        setcfg("3dlut.input.profile", "/some/path/MyProfile.icc")
        lut_path = tmp_path / "lut.3dlut"
        lut_path.write_bytes(b"x")
        monkeypatch.setattr(pgs.socket, "gethostbyname", lambda host: "1.2.3.4")
        dialog = pgs.PrismaHostDialog(
            worker, "title", upload=True, lut3d_path=str(lut_path), parent=None
        )
        dialog.host_ctrl.setCurrentText("prisma.local")
        presets = config.VALID_VALUES["patterngenerator.prisma.preset"]
        dialog.preset_ctrl.setCurrentText(presets[-1])

        dialog._check_and_accept()

        assert _spin_until(qapp, lambda: dialog.result() == pgs.QDialog.Accepted)
        assert getcfg("patterngenerator.prisma.preset") == presets[-1]


class TestConnectMadvr:
    def test_fast_success(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(worker, "madtpg_connect", lambda: True)

        result = pgs.connect_madvr(worker, None, "title")

        assert result is True

    def test_fast_failure_shows_error(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(worker, "madtpg_connect", lambda: False)
        shown = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))

        result = pgs.connect_madvr(worker, None, "title")

        assert result is False
        assert shown == [lang.getstr("madtpg.launch.failure")]

    def test_slow_success_shows_and_closes_wait_dialog(self, qapp, worker, monkeypatch):
        def _slow_connect():
            time.sleep(0.3)
            return True

        monkeypatch.setattr(worker, "madtpg_connect", _slow_connect)

        result = pgs.connect_madvr(worker, None, "title")

        assert result is True

    def test_slow_cancel_returns_none(self, qapp, worker, monkeypatch):
        def _slow_connect():
            time.sleep(0.3)
            return True

        monkeypatch.setattr(worker, "madtpg_connect", _slow_connect)

        def _fake_exec(self):
            self.canceled.emit()
            return 0

        monkeypatch.setattr(pgs.QProgressDialog, "exec_", _fake_exec)

        result = pgs.connect_madvr(worker, None, "title")

        assert result is None


class TestConnectPatterngenerator:
    def test_prisma_dispatches_to_dialog(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs.config, "get_display_name", lambda *a, **k: "Prisma")

        def _fake_exec(self):
            self.host_ctrl.setCurrentText("prisma.local")
            return pgs.QDialog.Accepted

        monkeypatch.setattr(pgs.PrismaHostDialog, "exec_", _fake_exec)
        worker.patterngenerator = _FakePatternGenerator()

        result = pgs.connect_patterngenerator(worker, None, "title", upload=False)

        assert result is True

    def test_prisma_cancelled_returns_none(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs.config, "get_display_name", lambda *a, **k: "Prisma")
        monkeypatch.setattr(
            pgs.PrismaHostDialog, "exec_", lambda self: pgs.QDialog.Rejected
        )
        worker.patterngenerator = _FakePatternGenerator()

        result = pgs.connect_patterngenerator(worker, None, "title")

        assert result is None

    def test_madvr_dispatches_to_connect_madvr(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs.config, "get_display_name", lambda *a, **k: "madVR")
        calls = []
        monkeypatch.setattr(
            pgs,
            "connect_madvr",
            lambda w, parent, title: calls.append((w, parent, title)) or True,
        )

        result = pgs.connect_patterngenerator(worker, "parent", "title")

        assert result is True
        assert calls == [(worker, "parent", "title")]

    def test_unsupported_display_returns_false(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs.config, "get_display_name", lambda *a, **k: "Resolve")

        result = pgs.connect_patterngenerator(worker, None, "title")

        assert result is False


class _FakeLivePatternGenerator:
    """Minimal stand-in for a Resolve/Web/Chromecast server-style client.

    Those classes signal "connected" by having ``wait()`` set a ``conn``
    attribute (absent until then), unlike Prisma's ``connect()``-based
    ``GenHTTPPatternGeneratorClient``.
    """

    def __init__(self, wait_func=None) -> None:
        self.listening = False
        self._wait_func = wait_func or (lambda pg: None)

    def wait(self) -> None:
        self._wait_func(self)


class TestConnectLivePatterngenerator:
    def test_already_connected_skips_dialog(self, qapp, worker, monkeypatch):
        fake_pg = _FakeLivePatternGenerator()
        fake_pg.conn = True
        monkeypatch.setattr(worker, "setup_patterngenerator", lambda logfile=None: None)
        worker.patterngenerator = fake_pg
        monkeypatch.setattr(
            pgs.QProgressDialog,
            "exec_",
            lambda self: (_ for _ in ()).throw(AssertionError("dialog shown")),
        )

        result = pgs.connect_live_patterngenerator(worker, None, "title")

        assert result is True

    def test_setup_exception_shows_critical_and_returns_false(
        self, qapp, worker, monkeypatch
    ):
        def _raise(logfile=None):
            raise Error("boom")

        monkeypatch.setattr(worker, "setup_patterngenerator", _raise)
        shown = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))

        result = pgs.connect_live_patterngenerator(worker, None, "title")

        assert result is False
        assert shown == ["boom"]

    def test_wait_success_returns_true(self, qapp, worker, monkeypatch):
        def _wait(pg):
            time.sleep(0.1)
            pg.conn = True

        fake_pg = _FakeLivePatternGenerator(_wait)
        monkeypatch.setattr(
            worker,
            "setup_patterngenerator",
            lambda logfile=None: setattr(worker, "patterngenerator", fake_pg),
        )

        result = pgs.connect_live_patterngenerator(worker, None, "title")

        assert result is True
        assert hasattr(fake_pg, "conn")

    def test_wait_failure_shows_error_and_returns_false(
        self, qapp, worker, monkeypatch
    ):
        def _wait(pg):
            raise OSError("connection refused")

        fake_pg = _FakeLivePatternGenerator(_wait)
        monkeypatch.setattr(
            worker,
            "setup_patterngenerator",
            lambda logfile=None: setattr(worker, "patterngenerator", fake_pg),
        )
        shown = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))

        result = pgs.connect_live_patterngenerator(worker, None, "title")

        assert result is False
        assert shown == ["connection refused"]

    def test_cancel_stops_listening_and_returns_false(self, qapp, worker, monkeypatch):
        def _wait(pg):
            time.sleep(0.3)
            pg.conn = True

        fake_pg = _FakeLivePatternGenerator(_wait)
        monkeypatch.setattr(
            worker,
            "setup_patterngenerator",
            lambda logfile=None: setattr(worker, "patterngenerator", fake_pg),
        )

        def _fake_exec(self):
            self.canceled.emit()
            return 0

        monkeypatch.setattr(pgs.QProgressDialog, "exec_", _fake_exec)

        result = pgs.connect_live_patterngenerator(worker, None, "title")

        assert result is False
        assert fake_pg.listening is False


class TestLut3DAPIInstallController:
    def test_cancelled_connect_finishes_without_install(
        self, qapp, worker, monkeypatch
    ):
        monkeypatch.setattr(pgs, "connect_patterngenerator", lambda *a, **k: None)
        installed = []
        monkeypatch.setattr(
            worker, "install_3dlut", lambda *a, **k: installed.append(True)
        )
        controller = pgs.Lut3DAPIInstallController(
            worker, "/tmp/lut.3dlut", False, None
        )
        results = []
        controller.finished.connect(lambda: results.append(True))

        controller.run()

        assert results == [True]
        assert installed == []

    def test_failed_connect_finishes_without_install(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs, "connect_patterngenerator", lambda *a, **k: False)
        installed = []
        monkeypatch.setattr(
            worker, "install_3dlut", lambda *a, **k: installed.append(True)
        )
        controller = pgs.Lut3DAPIInstallController(
            worker, "/tmp/lut.3dlut", False, None
        )
        results = []
        controller.finished.connect(lambda: results.append(True))

        controller.run()

        assert results == [True]
        assert installed == []

    def test_successful_install_shows_info_message(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs, "connect_patterngenerator", lambda *a, **k: True)
        monkeypatch.setattr(
            worker, "install_3dlut", lambda path, filename: Info("done")
        )
        shown = []
        monkeypatch.setattr(
            QMessageBox, "information", lambda *a, **k: shown.append(a[2])
        )
        controller = pgs.Lut3DAPIInstallController(
            worker, "/tmp/lut.3dlut", False, None
        )
        results = []
        controller.finished.connect(lambda: results.append(True))

        controller.run()

        assert _spin_until(qapp, lambda: results)
        assert shown == ["done"]

    def test_prisma_install_passes_upload_filename(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(
            pgs, "connect_patterngenerator", lambda *a, **k: "upload.3dl"
        )
        received = []
        monkeypatch.setattr(
            worker,
            "install_3dlut",
            lambda path, filename: received.append((path, filename)) or Info("ok"),
        )
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
        controller = pgs.Lut3DAPIInstallController(worker, "/tmp/lut.3dlut", True, None)
        results = []
        controller.finished.connect(lambda: results.append(True))

        controller.run()

        assert _spin_until(qapp, lambda: results)
        assert received == [("/tmp/lut.3dlut", "upload.3dl")]

    def test_install_error_shows_critical_message(self, qapp, worker, monkeypatch):
        monkeypatch.setattr(pgs, "connect_patterngenerator", lambda *a, **k: True)
        monkeypatch.setattr(
            worker, "install_3dlut", lambda path, filename: Error("nope")
        )
        shown = []
        monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
        controller = pgs.Lut3DAPIInstallController(
            worker, "/tmp/lut.3dlut", False, None
        )
        results = []
        controller.finished.connect(lambda: results.append(True))

        controller.run()

        assert _spin_until(qapp, lambda: results)
        assert shown == ["nope"]
