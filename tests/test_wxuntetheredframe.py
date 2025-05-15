import contextlib
import os
import random
from _thread import start_new_thread
from time import sleep

import pytest

from DisplayCAL import localization as lang
from DisplayCAL import (config, worker)
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import getcfg
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.util_io import Files
from DisplayCAL.wxUntetheredFrame import UntetheredFrame
from DisplayCAL.wxaddons import wx
from DisplayCAL.wxwindows import BaseApp


class Subprocess:
    def send(self, bytes_):
        start_new_thread(setup_app, (bytes_,))


class Worker(worker.Worker):
    def __init__(self):
        worker.Worker.__init__(self)
        self.finished = False
        self.instrument_calibration_complete = False
        self.instrument_place_on_screen_msg = False
        self.instrument_sensor_position_msg = False
        self.is_ambient_measuring = False
        self.subprocess = Subprocess()
        self.subprocess_abort = False

    def abort_subprocess(self):
        self.safe_send("Q")

    def safe_send(self, bytes_):
        print(f"*** Sending {bytes_!r}")
        self.subprocess.send(bytes_)
        return True


@pytest.fixture(scope="function")
def setup_test_app_and_data():
    """Set up the tests."""
    config.initcfg()
    print("untethered.min_delta", getcfg("untethered.min_delta"))
    print("untethered.min_delta.lightness", getcfg("untethered.min_delta.lightness"))
    print("untethered.max_delta.chroma", getcfg("untethered.max_delta.chroma"))
    lang.init()
    lang.update_defaults()
    app = BaseApp(0)
    app.TopWindow = UntetheredFrame(start_timer=False)
    test_chart = getcfg("testchart.file")
    if os.path.splitext(test_chart)[1].lower() in (".icc", ".icm"):
        with contextlib.suppress(Exception):
            test_chart = ICCProfile(test_chart).tags.targ
    try:
        app.TopWindow.cgats = CGATS(test_chart)
    except Exception:
        app.TopWindow.cgats = CGATS(
            """TI1
    BEGIN_DATA_FORMAT
    SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT
    BEGIN_DATA
    1 0 0 0 0 0 0
    END_DATA
    """
        )
    app.TopWindow.worker = Worker()
    app.TopWindow.worker.progress_wnd = app.TopWindow
    app.TopWindow.Show()
    files = Files([app.TopWindow.worker, app.TopWindow])
    yield app, files


def setup_app(setup_test_app_and_data, bytes_):
    app, files = setup_test_app_and_data
    print(f"*** Received {bytes_!r}")
    menu = r"""Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:"""
    if not bytes_:
        txt = menu
    elif bytes_ == " ":
        i = app.TopWindow.index
        row = app.TopWindow.cgats[0].DATA[i]
        txt = [
            f"""
Result is XYZ: {row.XYZ_X:.6f} {row.XYZ_Y:.6f} {row.XYZ_Z:.6f}

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""",
            f""""
Result is XYZ: {row.XYZ_X:.6f} {row.XYZ_Y:.6f} {row.XYZ_Z:.6f}

Spot read needs a calibration before continuing
Place cap on the instrument, or place on a dark surface,
or place on the white calibration reference,
and then hit any key to continue,
or hit Esc or Q to abort:""",
        ][random.choice([0, 1])]
    elif bytes_ in ("Q", "q"):
        wx.CallAfter(app.TopWindow.Close)
        return
    else:
        return
    for line in txt.split("\n"):
        sleep(0.03125)
        if app.TopWindow:
            wx.CallAfter(files.write, line)
            print(line)


@pytest.mark.skip(reason="Not implemented yet")
def test_wxuntetheredframe(setup_app):
    start_new_thread(setup_app, ())
    app.MainLoop()
