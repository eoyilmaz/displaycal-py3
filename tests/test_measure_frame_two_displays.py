"""The measurement area opens on the display chosen for measuring.

With two displays, the chosen one (the one picked in the main window) isn't
where Qt opens a new window. Run in a process of its own: Qt's offscreen
platform gets two screens there, laid out like a laptop with an external
display on its right.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("qtpy")

SCREENS = {
    "screens": [
        {
            "name": "Built-in Retina Display",
            "x": 0,
            "y": 0,
            "width": 1680,
            "height": 1050,
            "logicalDpi": 96,
            "dpr": 1,
        },
        {
            "name": "TYPE-C",
            "x": 1680,
            "y": 0,
            "width": 1920,
            "height": 1080,
            "logicalDpi": 96,
            "dpr": 1,
        },
    ]
}

CHILD = textwrap.dedent(
    """
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication([])

    from DisplayCAL import config
    from DisplayCAL import localization as lang
    from DisplayCAL.config import getcfg, setcfg
    from DisplayCAL.ui import main_window as mw
    from DisplayCAL.worker import Worker

    DISPLAYS = [
        "MacBookPro17,1 @ 0, 0, 1680x1050 [PRIMARY]",
        "TYPE-C @ 1680, 0, 1920x1080",
        "Web @ localhost",
    ]

    def enumerate_displays(self, *args, **kwargs):
        self.displays = list(DISPLAYS)
        self.instruments = []

    Worker.enumerate_displays_and_ports = enumerate_displays
    config.get_display_profile = lambda *a, **k: None
    lang.init()
    window = mw.MainWindow()
    window.worker.displays = list(DISPLAYS)
    setcfg("displays", DISPLAYS)
    setcfg("dimensions.measureframe", "0.5,0.5,1.0")
    setcfg("display.number", int(sys.argv[1]))

    window._present_measureframe()
    app.processEvents()

    frame = window.measureframe
    centre = frame.frameGeometry().center()
    print(QApplication.screenAt(centre).name(), getcfg("display.number"))
    """
)


def _present(tmp_path, display_number, *flags):
    """Show the measurement area for a display, return its screen and display."""
    screens = tmp_path / "screens.json"
    screens.write_text(json.dumps(SCREENS))
    env = dict(
        os.environ,
        QT_QPA_PLATFORM=f"offscreen:configfile={screens}",
        # Settings in a folder of its own, not the user's
        DISPLAYCAL_PORTABLE=str(tmp_path),
    )
    os.makedirs(tmp_path / "data", exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(display_number), *flags],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    screen, number = result.stdout.strip().splitlines()[-1].rsplit(" ", 1)
    return screen, int(number)


def test_measurement_area_opens_on_the_chosen_display(tmp_path):
    assert _present(tmp_path, 2) == ("TYPE-C", 2)


def test_measurement_area_on_the_first_display(tmp_path):
    assert _present(tmp_path, 1) == ("Built-in Retina Display", 1)
