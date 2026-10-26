import io
import json
import os
import platform
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock
from zlib import crc32

import pytest
import requests
import wx
from wx import AppConsole, Button

from DisplayCAL import config, display_cal
from DisplayCAL import localization as lang
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import get_ccxx_testchart, get_icon, getcfg, setcfg
from DisplayCAL.dev.mocks import check_call, check_call_str
from DisplayCAL.display_cal import (
    ExtraArgsFrame,
    GamapFrame,
    IncrementingInt,
    MainFrame,
    MeasurementFileCheckSanityDialog,
    StartupFrame,
    app_up_to_date,
    app_update_check,
    check_donation,
    colorimeter_correction_check_overwrite,
    colorimeter_correction_web_check_choose,
    donation_message,
    get_cgats_measurement_mode,
    get_cgats_path,
    get_profile_load_on_login_label,
    install_scope_handler,
    qt_ui_message,
    show_ccxx_error_dialog,
    webbrowser_open,
)
from DisplayCAL.util_list import intlist
from DisplayCAL.util_str import universal_newlines
from DisplayCAL.worker import Worker, check_ti3
from DisplayCAL.wx_windows import BaseInteractiveDialog, ConfirmDialog, InfoDialog


@pytest.fixture(scope="session", name="app", autouse=True)
def fixture_app() -> AppConsole:
    """Return app for tests."""
    return wx.GetApp() or wx.App()


@pytest.fixture(scope="module", name="mainframe")
def fixture_mainframe() -> MainFrame:
    """Return mainframe for tests.

    Module-scoped (not class-scoped) because MainFrame() also creates hidden
    child top-level windows (infoframe, measureframe, ...) that wx never
    fully releases without a running MainLoop(); building a fresh MainFrame()
    per test function leaked dozens of native windows over the file and
    caused multi-minute stalls on macOS CI runners (#778).
    """
    worker = Worker()
    return display_cal.MainFrame(worker=worker)


def test_update_colorimeter_correction_matrix_ctrl_items_1(
    mainframe: MainFrame,
) -> None:
    """MainFrame.update_colorimeter_correction_matrix_ctrl_items() method."""
    # I have no idea how it works, let's see...
    assert mainframe.colorimeter_correction_matrix_ctrl.Items != []
    before_items = mainframe.colorimeter_correction_matrix_ctrl.Items
    before_length = len(before_items)
    mainframe.update_colorimeter_correction_matrix_ctrl_items()
    after_items = mainframe.colorimeter_correction_matrix_ctrl.Items
    after_length = len(after_items)
    assert before_length == after_length
    assert before_items == after_items  # Really don't know anything about the method
    # but it was raising errors before, now it is fixed.


def test_show_ccxx_error_dialog(mainframe: MainFrame) -> None:
    """Test if error message is shown."""
    with check_call_str("DisplayCAL.display_cal.show_result_dialog"):
        show_ccxx_error_dialog(Exception("Malformed demo"), "path", mainframe)


@pytest.mark.skipif(
    sys.platform == "darwin" and os.getenv("GITHUB_ACTIONS") == "true",
    reason="ShowResultDialog is failing on CI macOS machines, skipping test.",
)
@pytest.mark.parametrize("argyll", (True, False), ids=("With argyll", "without argyll"))
@pytest.mark.parametrize("snapshot", (True, False), ids=("Snapshot", "No snapshot"))
@pytest.mark.parametrize("silent", (True, False), ids=("Silent", "Not silent"))
def test_app_update_check(
    mainframe: MainFrame, silent: bool, snapshot: bool, argyll: bool
) -> None:
    """Test the application update check."""
    with check_call(wx, "CallAfter", call_count=1):
        app_update_check(mainframe, silent, snapshot, argyll)


def test_check_donation(mainframe: MainFrame) -> None:
    """Test check for user disabled donation."""
    with check_call(wx, "CallAfter", call_count=-1):
        check_donation(mainframe, False)


@pytest.mark.parametrize("offer_qt", (True, False), ids=("Qt offer", "Donation"))
def test_check_donation_shows_one_startup_dialog(
    mainframe: MainFrame, monkeypatch: pytest.MonkeyPatch, offer_qt: bool
) -> None:
    """The Qt UI offer replaces the donation message for that launch."""
    monkeypatch.setattr(display_cal, "should_offer_qt_ui", lambda: offer_qt)
    setcfg("show_donation_message", 1)
    calls = []
    monkeypatch.setattr(wx, "CallAfter", lambda func, *args: calls.append(func))
    check_donation(mainframe, True)
    assert calls == [qt_ui_message if offer_qt else donation_message]


@pytest.mark.parametrize(
    "response, do_not_show_again, toolkit, offer_qt, restarted",
    [
        (wx.ID_OK, False, "qt", 0, True),
        (wx.ID_CANCEL, False, "wx", 1, False),
        (wx.ID_CANCEL, True, "wx", 0, False),
    ],
    ids=("Switch", "Not now", "Do not show again"),
)
def test_qt_ui_message(
    mainframe: MainFrame,
    monkeypatch: pytest.MonkeyPatch,
    response: int,
    do_not_show_again: bool,
    toolkit: str,
    offer_qt: int,
    restarted: bool,
) -> None:
    """The Qt UI offer persists the user's choice and restarts on accept."""
    setcfg("ui.toolkit", "wx")
    setcfg("ui.offer_qt", 1)
    restarts = []
    monkeypatch.setattr(display_cal, "restart_application", lambda: restarts.append(1))
    monkeypatch.setattr(display_cal, "writecfg", lambda: None)
    monkeypatch.setattr(wx.CheckBox, "GetValue", lambda self: do_not_show_again)
    try:
        with check_call(BaseInteractiveDialog, "ShowModal", response, call_count=1):
            qt_ui_message(mainframe)
        assert getcfg("ui.toolkit") == toolkit
        assert getcfg("ui.offer_qt") == offer_qt
        assert bool(restarts) is restarted
    finally:
        setcfg("ui.toolkit", None)
        setcfg("ui.offer_qt", None)


def test_app_up_to_date(mainframe: MainFrame) -> None:
    """Test if 'up to date' messagebox is shown."""
    with check_call(BaseInteractiveDialog, "ShowModalThenDestroy", call_count=1):
        app_up_to_date(mainframe)


@pytest.mark.parametrize("response", (wx.ID_OK, wx.ID_NO), ids=("Ok", "Cancel"))
def test_donation_message(mainframe: MainFrame, response: int) -> None:
    """Test if donation messagebox is shown as expected."""
    with check_call(BaseInteractiveDialog, "ShowModal", response, call_count=1):
        with check_call_str(
            "DisplayCAL.display_cal.launch_file",
            call_count=1 if response == wx.ID_OK else 0,
        ):
            donation_message(mainframe)


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Seems like the first call of ShowWindowModalBlocking always fails on remote."
    "Locally however the problem cannot be reproduced, skipping test for now.",
)
@pytest.mark.parametrize(
    "update",
    (True, False),
    ids=("update comports", "don't update comports"),
)
@pytest.mark.parametrize(
    "response, value",
    (
        (wx.ID_OK, True),
        (wx.ID_NO, False),
    ),
    ids=("Ok", "Cancel"),
)
def test_colorimeter_correction_check_overwrite(
    data_files, mainframe: MainFrame, response: int, value: bool, update: bool
) -> None:
    """Test if function reacts as expected to user input."""
    path = data_files["0_16.ti3"].absolute()
    with open(path, "rb") as cgatsfile:
        cgats = universal_newlines(cgatsfile.read())
    # Pre-create the target file so os.path.isfile() returns True and the
    # overwrite dialog is always triggered, making the test self-contained.
    target_path = get_cgats_path(cgats)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(b"placeholder")
    try:
        with check_call(BaseInteractiveDialog, "ShowWindowModalBlocking", response):
            assert (
                colorimeter_correction_check_overwrite(mainframe, cgats, update)
                == value
            )
    finally:
        if os.path.exists(target_path):
            os.remove(target_path)


def test_colorimeter_correction_web_check_choose_observer_column(
    mainframe: MainFrame,
) -> None:
    """Regression test: REFERENCE_OBSERVER bytes vs str mismatch.

    ``CGATS.queryv1()`` returns bytes for "REFERENCE_OBSERVER", but
    ``MainFrame.observers_ab`` (built from ``config.VALID_VALUES["observer"]``)
    is keyed by str. Looking the bytes value up directly always missed, so the
    web-check dialog's "observer" column silently fell back to "unknown" for
    every CCMX correction instead of resolving the real label.
    """
    cgats_text = (
        "CCMX\n\n"
        'DESCRIPTOR "test"\n'
        'DISPLAY "LCD Monitor"\n'
        'REFERENCE_OBSERVER "1931_2"\n'
        'FIT_METHOD "xy"\n'
    )
    entry = {
        "cgats": cgats_text,
        "type": "ccmx",
        "display": "Dell U2413",
        "manufacturer": "Dell",
        "reference": "i1 Pro",
        "description": "i1 DisplayPro, ColorMunki Display",
    }
    resp = io.BytesIO(json.dumps([entry]).encode("utf-8"))
    expected_label = mainframe.observers_ab["1931_2"]
    # On GTK3, wx.ListCtrl is DisplayCAL.wx_fixes.ListCtrl, a DataViewListCtrl
    # shim whose SetStringItem() only creates the real row once every column
    # has been set. Spy on it (call through to the original) rather than
    # replacing it outright, otherwise the shim never gets a real row and the
    # dialog's later GetItem(0) call crashes with a wx assertion error.
    original_set_string_item = wx.ListCtrl.SetStringItem
    with check_call(BaseInteractiveDialog, "ShowWindowModalBlocking", wx.ID_CANCEL):
        with check_call(
            wx.ListCtrl, "SetStringItem", original_set_string_item, call_count=-1
        ) as calls:
            colorimeter_correction_web_check_choose(resp, mainframe)
    # SetStringItem(index, col, label) is called on the ListCtrl instance, so
    # the recorded args are (self, index, col, label).
    observer_values = [args[3] for args, _kwargs in calls if args[2] == 5]
    assert observer_values
    assert expected_label in observer_values
    assert lang.getstr("unknown") not in observer_values


def test_upload_colorimeter_correction_accepts_str_cgats(mainframe: MainFrame) -> None:
    """Regression test: a str ``cgats`` argument must not raise ``TypeError``.

    ``upload_colorimeter_correction_handler`` reads the file as str
    (``.decode()``) before calling ``MainFrame.upload_colorimeter_correction``,
    but that method ran a bytes-pattern regex directly against it, raising
    ``TypeError`` for every manually-chosen upload file.
    """
    cgats_text = 'CCMX\n\nORIGINATOR "Argyll dispcal"\nDISPLAY "LCD Monitor"\n'
    with check_call(BaseInteractiveDialog, "ShowWindowModalBlocking", wx.ID_OK):
        with check_call(Worker, "start", call_count=1):
            mainframe.upload_colorimeter_correction(cgats_text)


@pytest.mark.parametrize("file", ("0_16.ti3", "0_16_with_refresh.ti3", "default.ti3"))
@pytest.mark.parametrize(
    "instrument,modes",
    (
        ("ColorHug", ("F", "c", None)),
        ("ColorHug2", ("F", "c", None)),
        ("ColorMunki Smile", ("f", "c", None)),
        ("Colorimtre HCFR", ("R", "c", None)),
        ("K-10", ("F", "c", None)),
        ("fake_instrument", ("l", "c", None)),
    ),
)
def test_get_cgats_measurement_mode(
    data_files, instrument: str, file: str, modes: tuple[str, str, None]
) -> None:
    """Test if expected measurement mode is returned."""
    path = data_files[file].absolute()
    cgats = CGATS(cgats=path)
    if file == "0_16.ti3":
        mode = modes[0]
    elif file == "0_16_with_refresh.ti3":
        mode = modes[1]
    else:
        mode = modes[2]
    assert get_cgats_measurement_mode(cgats, instrument) == mode


def test_get_cgats_path(data_files) -> None:
    """Test if correct cgats path is returned."""
    path = data_files["default.ti3"].absolute()
    with open(path, "rb") as cgatsfile:
        cgats = universal_newlines(cgatsfile.read())
    assert Path(
        config.get_argyll_data_dir()
    ) / "Argyll Calibration Target chart information 3.cti3" == Path(
        get_cgats_path(cgats)
    )


def test_restore_testchart_clears_crash_state(mainframe: MainFrame) -> None:
    """restore_testchart() should clear testchart.file.backup left by a crash.

    If DisplayCAL crashes during a CCXX measurement, testchart.file is set to
    the CCXX testchart and testchart.file.backup holds the original path.
    restore_testchart() must restore the original and clear the backup so that
    is_ccxx_testchart() returns False and the correction section is shown.
    """
    from DisplayCAL.config import is_ccxx_testchart

    original_testchart = getcfg("testchart.file")
    ccxx_testchart = get_ccxx_testchart()

    # Simulate the config state left after a crash mid-CCXX measurement.
    setcfg("testchart.file.backup", original_testchart)
    setcfg("testchart.file", ccxx_testchart)

    try:
        assert is_ccxx_testchart(), "Pre-condition: should look like a CCXX testchart"
        mainframe.restore_testchart()
        assert not is_ccxx_testchart(), (
            "After restore, should no longer be CCXX testchart"
        )
        assert getcfg("testchart.file") == original_testchart
        assert getcfg("testchart.file.backup", False) is None
    finally:
        # Ensure clean state for other tests regardless of assertion outcome.
        setcfg("testchart.file", original_testchart)
        setcfg("testchart.file.backup", None)


def test_restore_measurement_mode_clears_crash_state(mainframe: MainFrame) -> None:
    """restore_measurement_mode() should clear backup values left by a crash.

    If DisplayCAL crashes during a CCXX measurement, measurement_mode.backup
    holds the original mode. restore_measurement_mode() must restore it and
    clear the backup.
    """
    original_mode = getcfg("measurement_mode")

    setcfg("measurement_mode.backup", original_mode)
    setcfg("measurement_mode", "c")  # Simulate mode changed for CCXX measurement.

    try:
        mainframe.restore_measurement_mode()
        assert getcfg("measurement_mode") == original_mode
        assert getcfg("measurement_mode.backup", False) is None
    finally:
        setcfg("measurement_mode", original_mode)
        setcfg("measurement_mode.backup", None)


def test_get_profile_load_on_login_label() -> None:
    """Test if load on login label is returned."""
    assert get_profile_load_on_login_label(True) == "profile.load_on_login"


def test_install_scope_handler(mainframe: MainFrame) -> None:
    """Test if install scope handler calls the correct methods for authentication dialog."""
    dlg = ConfirmDialog(
        mainframe,
        title="colorimeter_correction.import",
        msg="msg",
        ok="ok",
        cancel="cancel",
        bitmap=get_icon(32, "dialog-information"),
        alt="file.select",
    )
    dlg.install_systemwide = wx.RadioButton(dlg, -1, "install_local_system")
    dlg.install_systemwide.Bind(wx.EVT_RADIOBUTTON, install_scope_handler)
    with check_call(Button, "SetAuthNeeded", call_count=2):
        install_scope_handler(dlg=dlg)


def test_webbrowser_open(monkeypatch) -> None:
    """Test if function calls browser as expected."""
    opened_urls = []

    class PatchedWebBrowser:
        @staticmethod
        def open(url: str, new: int = 0, autoraise: bool = True) -> bool:
            opened_urls.append(url)
            return True

    # patch webbrowser.open
    monkeypatch.setattr("DisplayCAL.display_cal.webbrowser", PatchedWebBrowser)
    assert opened_urls == []
    url = "https://github.com/eoyilmaz/displaycal-py3"
    assert webbrowser_open(url)
    assert opened_urls == [url]


def test_incrementing_int() -> None:
    """Testing if self incrementing int increments every time it is used."""
    inc_integer = IncrementingInt()
    assert int(inc_integer) == 0
    [int(inc_integer) for _ in range(9)]
    assert int(inc_integer) == 10


def test_init_extra_args_frame(mainframe: MainFrame) -> None:
    """Test if ExtraArgsFrame is initialized properly"""
    with check_call(ExtraArgsFrame, "update_controls"):
        ExtraArgsFrame(mainframe)


def test_init_gamap_frame(mainframe: MainFrame) -> None:
    """Test if GamapFrame is initialized properly."""
    with check_call(GamapFrame, "update_layout"):
        GamapFrame(mainframe)


@pytest.mark.skipif(
    sys.platform == "darwin" and os.getenv("GITHUB_ACTIONS") == "true",
    reason="StartupFrame is failing on CI macOS machines, skipping test.",
)
def test_init_startup_frame(monkeypatch) -> None:
    """Test if StartupFrame is initialized properly."""
    show_func_name = "Show"
    if (
        sys.platform == "darwin"
        and intlist(platform.mac_ver()[0].split(".")) >= [10, 10]
    ) or os.getenv("XDG_SESSION_TYPE") == "wayland":
        show_func_name = "ShowModal"

    # StartupFrame.__init__() schedules wx.CallLater(1, self.startup), which
    # self-reschedules every tick to drive the splash animation and, once the
    # animation finishes, calls delayedresult.startWorker() to enumerate
    # displays/ports on a real background thread, delivering the result via
    # setup_frame() -> a real MainFrame() -> a real (unmocked)
    # Worker.get_instrument_measurement_modes() subprocess call. Nothing in
    # this test ever pumps the module-scoped wx.App()'s event loop, so none
    # of that fires *during* this test -- but the CallLater outlives it (it
    # holds a strong reference to self.startup, keeping the frame alive) and
    # fires whenever the shared wx.App's event loop is next pumped, which can
    # be arbitrarily far into an unrelated later test. On Linux CI this
    # showed up as a hang deep inside tests/test_ui_startup.py's Qt-based
    # qapp.processEvents() calls, minutes and files away, because Qt's GLib
    # event-dispatcher integration also services wx's GTK-backed timers.
    # Stub out the whole chain at its root before construction (the CallLater
    # captures the bound method at __init__ time, so this must be patched
    # first) so this test only checks Show()/ShowModal() as intended.
    monkeypatch.setattr(StartupFrame, "startup", lambda self: None)

    with check_call(StartupFrame, show_func_name):
        StartupFrame()


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="MeasurementFileCheckSanityDialog hard-crashes the pytest-xdist worker "
    "process on macOS due to wxPython grid widget creation in a subprocess context.",
)
def test_init_measurement_file_check_sanity_dialog_frame(
    data_files, mainframe: MainFrame
) -> None:
    """Test if MeasurementFileCheckSanityDialog is initialized properly."""
    path = data_files["0_16.ti3"].absolute()
    cgats = CGATS(cgats=path)
    with check_call(MeasurementFileCheckSanityDialog, "Center"):
        MeasurementFileCheckSanityDialog(mainframe, cgats[0], check_ti3(cgats), False)


# ---------------------------------------------------------------------------
# is_new_update() unit tests
# ---------------------------------------------------------------------------


def test_is_new_update_returns_version_when_newer(monkeypatch):
    """is_new_update() returns a version tuple when a newer release exists."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tag_name": "99.0.0", "assets": []}
    monkeypatch.setattr(
        "DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp
    )
    result = display_cal.is_new_update()
    assert result == (99, 0, 0)


def test_is_new_update_returns_false_when_current(monkeypatch):
    """is_new_update() returns False when already on the latest version."""
    from DisplayCAL.meta import VERSION_TUPLE

    tag = ".".join(str(n) for n in VERSION_TUPLE[:3])
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tag_name": tag, "assets": []}
    monkeypatch.setattr(
        "DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp
    )
    monkeypatch.setattr(display_cal, "VERSION_IS_PRERELEASE", False)
    assert display_cal.is_new_update() is False


def test_is_new_update_offers_release_of_running_prerelease(monkeypatch):
    """is_new_update() offers 3.10.0 to a 3.10.0rc1 (or .dev) build."""
    from DisplayCAL.meta import VERSION_TUPLE

    tag = ".".join(str(n) for n in VERSION_TUPLE[:3])
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tag_name": tag, "assets": []}
    monkeypatch.setattr(
        "DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp
    )
    monkeypatch.setattr(display_cal, "VERSION_IS_PRERELEASE", True)
    assert display_cal.is_new_update() == VERSION_TUPLE[:3]


def test_is_new_update_returns_none_on_network_error(monkeypatch):
    """is_new_update() returns None and does not raise on network failures."""

    def raise_error(*a, **kw):
        raise requests.RequestException("connection refused")

    monkeypatch.setattr("DisplayCAL.display_cal.requests.get", raise_error)
    assert display_cal.is_new_update() is None


def test_is_new_update_returns_none_on_bad_json(monkeypatch):
    """is_new_update() returns None when the response JSON is missing expected keys."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"unexpected_key": "value"}
    monkeypatch.setattr(
        "DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp
    )
    assert display_cal.is_new_update() is None


@pytest.mark.parametrize(
    "is_new_update_result", (False, None), ids=("no update", "check failed")
)
def test_app_update_check_silent_reaches_argyll_prompt_when_missing(
    monkeypatch, mainframe: MainFrame, is_new_update_result: bool | None
) -> None:
    """Silent startup falls through to the Argyll prompt when Argyll is missing.

    Regression test for #956: previously a silent update check that came
    back False/None returned early and never reached the ArgyllCMS check.
    """
    monkeypatch.setattr(display_cal, "is_new_update", lambda: is_new_update_result)
    monkeypatch.setattr(display_cal, "http_request", lambda *a, **kw: False)
    monkeypatch.setattr(display_cal, "check_argyll_bin", lambda: False)
    with check_call(wx, "CallAfter", call_count=1) as calls:
        app_update_check(mainframe, silent=True)
    assert calls[0][0][0] == mainframe.set_argyll_bin_handler


# ---------------------------------------------------------------------------
# get_download_url() unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "plat,machine,version,expected_filename",
    [
        ("win32", "AMD64", "3.9.0", "DisplayCAL-3.9.0-Windows-x64.exe"),
        ("win32", "ARM64", "3.9.0", "DisplayCAL-3.9.0-Windows-arm64.exe"),
        ("darwin", "arm64", "3.9.0", "DisplayCAL-3.9.0-macOS-arm64.dmg"),
        ("darwin", "aarch64", "3.9.0", "DisplayCAL-3.9.0-macOS-arm64.dmg"),
        ("darwin", "x86_64", "3.9.0", "DisplayCAL-3.9.0-macOS-x86.dmg"),
        ("linux", "x86_64", "3.9.0", "displaycal-3.9.0.tar.gz"),
    ],
)
def test_get_download_url(monkeypatch, plat, machine, version, expected_filename):
    """get_download_url() returns the correct asset URL for each platform."""
    fake_assets = [
        {
            "name": expected_filename,
            "browser_download_url": f"https://example.com/{expected_filename}",
        },
    ]
    monkeypatch.setattr(display_cal, "RELEASE_DATA", {"assets": fake_assets})
    monkeypatch.setattr(display_cal.sys, "platform", plat)
    monkeypatch.setattr(display_cal.platform, "machine", lambda: machine)
    assert (
        display_cal.get_download_url(version)
        == f"https://example.com/{expected_filename}"
    )


def test_get_download_url_returns_none_when_no_matching_asset(monkeypatch):
    """get_download_url() returns None when no asset matches the current platform."""
    monkeypatch.setattr(display_cal, "RELEASE_DATA", {"assets": []})
    monkeypatch.setattr(display_cal.sys, "platform", "linux")
    monkeypatch.setattr(display_cal.platform, "machine", lambda: "x86_64")
    assert display_cal.get_download_url("3.9.0") is None


def test_get_download_url_returns_none_before_release_data_loaded(monkeypatch):
    """get_download_url() returns None gracefully when called before is_new_update()."""
    monkeypatch.setattr(display_cal, "RELEASE_DATA", None)
    assert display_cal.get_download_url("3.9.0") is None


def test_create_profile_name_crc32_with_bytes_edid(
    mainframe: MainFrame, monkeypatch
) -> None:
    """create_profile_name() resolves %crc32 when EDID data is bytes (#776)."""
    raw_edid = b"\x00\xff\xff\xff\xff\xff\xff\x00test-edid-payload"
    monkeypatch.setattr(
        mainframe.worker, "get_display_edid", lambda: {"edid": raw_edid}
    )
    mainframe.profile_name_textctrl.SetValue("%crc32")
    expected = "%X" % (crc32(raw_edid) & 0xFFFFFFFF)
    assert mainframe.create_profile_name() == expected


def test_create_profile_name_crc32_with_str_edid(
    mainframe: MainFrame, monkeypatch
) -> None:
    """create_profile_name() resolves %crc32 when EDID data is a str."""
    raw_edid = "test-edid-payload"
    monkeypatch.setattr(
        mainframe.worker, "get_display_edid", lambda: {"edid": raw_edid}
    )
    mainframe.profile_name_textctrl.SetValue("%crc32")
    expected = "%X" % (crc32(raw_edid.encode("utf-8")) & 0xFFFFFFFF)
    assert mainframe.create_profile_name() == expected


def test_create_profile_name_crc32_without_edid(
    mainframe: MainFrame, monkeypatch
) -> None:
    """create_profile_name() strips %crc32 when no EDID data is available."""
    monkeypatch.setattr(mainframe.worker, "get_display_edid", dict)
    mainframe.profile_name_textctrl.SetValue("name-%crc32-suffix")
    assert mainframe.create_profile_name() == "name-suffix"


def test_create_profile_handler_accepts_valid_embedded_cti3(
    data_files, mainframe: MainFrame
) -> None:
    """Regression test for issue #811: bytes-vs-str "CTI3" comparison bug.

    ``(profile.tags.get("CIED", "") or profile.tags.get("targ", ""))[0:4] !=
    "CTI3"`` compared the ``bytes`` slice of an embedded ``Text`` tag against
    the ``str`` literal ``"CTI3"``, which is never equal in Python 3, so the
    "no embedded ti3" error fired for every ICC profile regardless of its
    actual content. Uses a real profile with a valid embedded CTI3 chart and
    asserts the ``profile.no_embedded_ti3`` ``InfoDialog`` is never shown.
    """
    icc_path = str(
        data_files[
            "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
        ].absolute()
    )
    with check_call(InfoDialog, "ShowModal", wx.ID_OK, call_count=0):
        # check_show_macos_bugs_warning() shows this ConfirmDialog on macOS
        # when profile.type/profile.black_point_compensation hit the BPC/S-
        # curve bug; answer "yes" so the handler proceeds to the FileDialog
        # instead of bailing out early on wx.ID_CANCEL.
        with check_call(ConfirmDialog, "ShowModal", wx.ID_OK, call_count=-1):
            with check_call(wx.FileDialog, "ShowModal", wx.ID_CANCEL, call_count=1):
                mainframe.create_profile_handler(None, icc_path, False)


def test_measurement_file_check_handler_regenerates_profile_without_typeerror(
    data_files, mainframe: MainFrame, monkeypatch
) -> None:
    """Regression test for issue #811.

    Covers two bugs in ``measurement_file_check_handler()``'s profile
    regeneration branch:

    1. The bytes-vs-str "CTI3" comparison (same bug as
       ``test_create_profile_handler_accepts_valid_embedded_cti3`` above, but
       at this method's own call site): asserted via the
       ``profile.no_embedded_ti3`` ``InfoDialog`` never being shown.
    2. ``profile.tags.targ = TextType(b"text\\0\\0\\0\\0" + ti3 + b"\\0", ...)``
       concatenated ``bytes`` with a ``CGATS`` instance (``ti3`` is reassigned
       to ``CGATS(ti3)`` earlier in the method), raising ``TypeError`` on
       every profile regeneration. Fixed by using ``bytes(ti3)``.
    """
    icc_path = str(
        data_files[
            "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
        ].absolute()
    )

    def _fake_confirm(self, ti3=None, force=False, parent=None):
        # Skip the sanity-check dialog itself (covered elsewhere); pretend
        # the user removed a suspicious patch so the regeneration branch runs.
        ti3.modified = True
        return True

    # wx.FileDialog is DisplayCAL.wx_fixes.FileDialog, whose GetPath()/etc.
    # are proxied to an inner ``self.filedialog`` via __getattr__ rather than
    # being real class attributes, so stub GetPath as an instance attribute
    # (which __getattr__ never intercepts) right after construction.
    original_filedialog_init = wx.FileDialog.__init__

    def _fake_filedialog_init(self, *args, **kwargs):
        original_filedialog_init(self, *args, **kwargs)
        self.GetPath = lambda: icc_path

    monkeypatch.setattr(wx.FileDialog, "__init__", _fake_filedialog_init)
    monkeypatch.setattr(wx.FileDialog, "ShowModal", lambda self: wx.ID_OK)
    monkeypatch.setattr(MainFrame, "measurement_file_check_confirm", _fake_confirm)
    monkeypatch.setattr(ConfirmDialog, "ShowModal", lambda self: wx.ID_OK)
    create_profile_calls = []
    monkeypatch.setattr(
        MainFrame,
        "create_profile_handler",
        lambda self, event, path, skip_ti3_check: create_profile_calls.append(path),
    )
    with check_call(InfoDialog, "ShowModal", wx.ID_OK, call_count=0):
        mainframe.measurement_file_check_handler(None)
    assert len(create_profile_calls) == 1
    assert create_profile_calls[0].endswith(os.path.basename(icc_path))


def test_import_session_archive_producer_returns_extracted_file_extension(
    tmp_path, mainframe: MainFrame
) -> None:
    """Regression test for issue #817.

    ``import_session_archive_producer()`` used to return a path built from
    the archive's own extension (``.zip``/``.7z``/``.tgz``) instead of the
    extension of the file actually extracted from it (``.cal``/``.icc``/
    ``.icm``), so ``load_cal_handler()`` was handed a path to a file that
    never existed on disk and silently treated the import as missing.
    """
    basename = "test"
    archive_path = tmp_path / f"{basename}.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(f"{basename}/{basename}.cal", b"dummy calibration data")

    result = mainframe.import_session_archive_producer(
        str(archive_path), basename, ".zip"
    )

    assert not isinstance(result, Exception)
    assert result == os.path.join(
        getcfg("profile.save_path"), basename, f"{basename}.cal"
    )


def test_load_cal_handler_proceeds_for_cal_files_with_no_profile(
    data_files, mainframe: MainFrame, monkeypatch
) -> None:
    """Regression test for issue #820.

    ``parse_calibration_file()`` only ever returns a non-``None`` ``profile``
    for ``.icc``/``.icm`` paths (it stays ``None`` for ``.cal`` files, which
    have no embedded ``ICCProfile`` at all). But ``load_cal_handler()``'s
    early-out checked ``if profile is None or ti3_lines is None: return``,
    so it always bailed before doing anything for every ``.cal`` file,
    regardless of whether it parsed successfully. Only ``ti3_lines`` (the
    actual parse-failure signal) should gate the early return.
    """
    monkeypatch.setattr(
        display_cal, "check_set_argyll_bin", lambda *args, **kwargs: True
    )
    # load_cal_handler() bails immediately if a previous test left this set;
    # it is unrelated to the bug under test here.
    setcfg("settings.changed", 0)
    path = str(
        data_files[
            "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.cal"
        ].absolute()
    )

    mainframe.load_cal_handler(None, path=path)

    assert getcfg("last_cal_or_icc_path") == path


def test_load_cal_handler_config_mapper_block_bytes_str_bugs(
    data_files, tmp_path, mainframe: MainFrame, monkeypatch
) -> None:
    """Regression test for issue #820.

    Covers all four bugs in ``load_cal_handler()``'s 3D LUT / profile-B2A
    config-mapper block (the ``BEGIN_DATA_FORMAT``-guarded block that reads
    ``PATCH_SEQUENCE``, ``3DLUT_GAMUT_MAPPING_MODE``, etc. from a saved
    ``.cal``/profile file):

    1. ``"BEGIN_DATA_FORMAT" in ti3_lines`` compared a ``str`` literal
       against ``ti3_lines`` (``list[bytes]``), so the whole block, along
       with the five smaller ``ti3_lines`` checks above it, was unreachable
       dead code.
    2. ``cfgvalue = 0 if cfgvalue == "G" else 1`` compared ``bytes`` against
       a ``str`` literal, always forcing ``3dlut.gamap.use_b2a`` to ``1``.
    3. ``cfgvalue.lower().replace("_rgb_", "_RGB_")`` called ``bytes``
       methods with ``str`` arguments, raising ``TypeError`` for
       ``PATCH_SEQUENCE``.
    4. ``cfgvalue = str(cfgvalue)`` stringified the ``bytes`` repr (e.g.
       ``"b'...'"``) instead of decoding it, corrupting every keyword
       ``CGATS.queryv1()`` left as ``bytes``.

    Builds a ``.cal`` file from a real fixture with ``PATCH_SEQUENCE`` and
    ``3DLUT_GAMUT_MAPPING_MODE`` keywords inserted ahead of the first
    ``BEGIN_DATA_FORMAT`` marker (mirroring how Argyll writes these), then
    asserts both end up correctly decoded/mapped instead of at their
    (different) config defaults.
    """
    monkeypatch.setattr(
        display_cal, "check_set_argyll_bin", lambda *args, **kwargs: True
    )
    # load_cal_handler() bails immediately if a previous test left this set;
    # it is unrelated to the bugs under test here.
    setcfg("settings.changed", 0)
    fixture_path = data_files[
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.cal"
    ]
    # splitlines() (not split(b"\n")) so this is robust to Windows checkouts
    # where git's core.autocrlf normalizes this text fixture to CRLF,
    # otherwise a trailing "\r" on every line would break the exact-bytes
    # index() lookup below.
    lines = fixture_path.read_bytes().splitlines()
    data_format_index = lines.index(b"BEGIN_DATA_FORMAT")
    lines[data_format_index:data_format_index] = [
        b'PATCH_SEQUENCE "MAXIMIZE_RGB_DIFFERENCE"',
        b'3DLUT_GAMUT_MAPPING_MODE "G"',
    ]
    cal_path = tmp_path / fixture_path.name
    cal_path.write_bytes(b"\n".join(lines))

    mainframe.load_cal_handler(None, path=str(cal_path))

    # Defaults are "optimize_display_response_delay" / 1, so these values
    # only end up here if the block ran and decoded/compared correctly.
    assert getcfg("testchart.patch_sequence") == "maximize_RGB_difference"
    assert getcfg("3dlut.gamap.use_b2a") == 0
