# -*- coding: utf-8 -*-
import os
import platform
import sys
from pathlib import Path
from typing import Tuple

import pytest
import wx
from wx import AppConsole, Button

from DisplayCAL import display_cal, config
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import geticon
from DisplayCAL.dev.mocks import check_call, check_call_str
from DisplayCAL.display_cal import (
    app_update_check,
    app_uptodate,
    check_donation,
    colorimeter_correction_check_overwrite,
    donation_message,
    ExtraArgsFrame,
    GamapFrame,
    get_cgats_measurement_mode,
    get_cgats_path,
    get_profile_load_on_login_label,
    IncrementingInt,
    install_scope_handler,
    MainFrame,
    MeasurementFileCheckSanityDialog,
    show_ccxx_error_dialog,
    StartupFrame,
    webbrowser_open,
)
from DisplayCAL.util_str import universal_newlines
from DisplayCAL.util_list import intlist
from DisplayCAL.worker import Worker, check_ti3
from DisplayCAL.wxwindows import ConfirmDialog, BaseInteractiveDialog


@pytest.fixture(scope="class", name="app", autouse=True)
def fixture_app() -> AppConsole:
    """Return app for tests."""
    return wx.GetApp() or wx.App()


@pytest.fixture(scope="class", name="mainframe")
def fixture_mainframe() -> MainFrame:
    """Return mainframe for tests."""
    worker = Worker()
    return display_cal.MainFrame(worker=worker)


def test_update_colorimeter_correction_matrix_ctrl_items_1(
    mainframe: MainFrame,
) -> None:
    """testing the MainFrame.update_colorimeter_correction_matrix_ctrl_items() method"""
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


def test_app_uptodate(mainframe: MainFrame) -> None:
    """Test if 'up to date' messagebox is shown."""
    with check_call(BaseInteractiveDialog, "ShowModalThenDestroy", call_count=1):
        app_uptodate(mainframe)


@pytest.mark.parametrize("response", (wx.ID_OK, wx.ID_NO), ids=("Ok", "Cancel"))
def test_donation_message(mainframe: MainFrame, response: int) -> None:
    """Test if donation messagebox is shown as expected."""
    with check_call(BaseInteractiveDialog, "ShowModal", response, call_count=1):
        with check_call_str(
            "DisplayCAL.display_cal.launch_file",
            call_count=1 if response == wx.ID_OK else 0,
        ):
            donation_message(mainframe)


# todo: test is working locally but not on CI
@pytest.mark.skip(
    reason="Seems like the first call of ShowWindowModalBlocking always fails on remote."
    "Locally however the problem cannot be reproduced, skipping test for now."
)
@pytest.mark.parametrize(
    "update", (True, False), ids=("update comports", "dont update comports")
)
@pytest.mark.parametrize(
    "response,value", ((wx.ID_OK, True), (wx.ID_NO, False)), ids=("Ok", "Cancel")
)
def test_colorimeter_correction_check_overwrite(
    data_files, mainframe: MainFrame, response: int, value: bool, update: bool
) -> None:
    """Test if function reacts as expected to user input."""
    path = data_files["0_16.ti3"].absolute()
    with open(path, "rb") as cgatsfile:
        cgats = universal_newlines(cgatsfile.read())
    with check_call(BaseInteractiveDialog, "ShowWindowModalBlocking", response):
        assert colorimeter_correction_check_overwrite(mainframe, cgats, update) == value


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
    data_files, instrument: str, file: str, modes: Tuple[str, str, None]
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
        bitmap=geticon(32, "dialog-information"),
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


def test_init_startup_frame() -> None:
    """Test if StartupFrame is initialized properly."""
    show_func_name = "Show"
    if (
        sys.platform == "darwin"
        and intlist(platform.mac_ver()[0].split(".")) >= [10, 10]
    ) or os.getenv("XDG_SESSION_TYPE") == "wayland":
        show_func_name = "ShowModal"

    with check_call(StartupFrame, show_func_name):
        StartupFrame()


def test_init_measurement_file_check_sanity_dialog_frame(
    data_files, mainframe: MainFrame
) -> None:
    """Test if MeasurementFileCheckSanityDialog is initialized properly."""
    path = data_files["0_16.ti3"].absolute()
    cgats = CGATS(cgats=path)
    with check_call(MeasurementFileCheckSanityDialog, "Center"):
        MeasurementFileCheckSanityDialog(mainframe, cgats[0], check_ti3(cgats), False)
