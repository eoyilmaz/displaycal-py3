"""Headless tests for the Qt log window ``DisplayCAL.ui.tools.log_window``.

Exercises ``LogWindow`` under the shared offscreen ``QApplication``:
construction, appending text, and position/size persistence round-trips.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtGui import QFont, QFontDatabase, QFontInfo  # noqa: E402

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.config import getcfg, setcfg  # noqa: E402
from DisplayCAL.ui.tools import log_window as lw  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from qtpy.QtWidgets import QApplication

    lang.init()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    # Several tests below intentionally set position.info.*/size.info.* to
    # exercise persistence; reset them afterward so they don't leak into
    # other tests in this file (or other test files sharing this xdist
    # worker) that construct a LogWindow expecting default geometry.
    config.initcfg()
    yield
    for key in (
        "position.info.x",
        "position.info.y",
        "size.info.w",
        "size.info.h",
    ):
        setcfg(key, config.DEFAULTS[key])


def test_construction_uses_infoframe_title_by_default(qapp):
    window = lw.LogWindow()
    assert window.windowTitle() == lang.getstr("infoframe.title")


def test_construction_accepts_custom_title(qapp):
    window = lw.LogWindow(title="Custom Report")
    assert window.windowTitle() == "Custom Report"


def test_log_appends_text(qapp):
    window = lw.LogWindow()
    window.Log("first line")
    window.Log("second line")
    assert "first line" in window._text.toPlainText()
    assert "second line" in window._text.toPlainText()


def test_text_widget_is_read_only(qapp):
    window = lw.LogWindow()
    assert window._text.isReadOnly()


def test_text_honors_platform_fixed_font(qapp, monkeypatch):
    fixed_font = QFont()
    fixed_font.setFixedPitch(True)
    fixed_font.setPointSize(13)
    monkeypatch.setattr(
        QFontDatabase,
        "systemFont",
        lambda role: fixed_font if role == QFontDatabase.FixedFont else QFont(),
    )
    window = lw.LogWindow()
    assert window._text.font().fixedPitch()
    assert window._text.font().pointSize() == 13


def test_text_resolves_to_fixed_pitch_on_native_platform(qapp):
    if qapp.platformName() in ("offscreen", "minimal"):
        pytest.skip("Requires the native platform's font database")
    window = lw.LogWindow()
    assert QFontInfo(window._text.font()).fixedPitch()


def test_position_persists_across_instances(qapp):
    setcfg("position.info.x", 123)
    setcfg("position.info.y", 45)
    window = lw.LogWindow()
    assert window.pos().x() == 123
    assert window.pos().y() == 45


def test_size_persists_round_trip(qapp):
    window = lw.LogWindow()
    window.resize(700, 500)
    window.save_size()
    assert getcfg("size.info.w") == 700
    assert getcfg("size.info.h") == 500
    reopened = lw.LogWindow()
    assert reopened.size().width() == 700
    assert reopened.size().height() == 500


def test_close_event_saves_size(qapp):
    window = lw.LogWindow()
    window.resize(640, 480)
    window.close()
    assert getcfg("size.info.w") == 640
    assert getcfg("size.info.h") == 480
