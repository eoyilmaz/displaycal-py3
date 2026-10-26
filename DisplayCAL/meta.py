"""Meta information."""

from __future__ import annotations

import os
import sys

# globals
VERSION_STRING = None
if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
    if sys.platform == "darwin":
        _base_path = os.path.join(os.path.dirname(base_path), "Resources")
        if os.path.isdir(_base_path):
            base_path = _base_path
else:
    base_path = os.path.dirname(__file__)
VERSION_FILE = os.path.join(base_path, "VERSION")

# If it's not in the root, check the DisplayCAL subfolder just in case
if not os.path.isfile(VERSION_FILE):
    VERSION_FILE = os.path.join(base_path, "DisplayCAL", "VERSION")

if os.path.isfile(VERSION_FILE):
    with open(VERSION_FILE, encoding="utf-8") as f:
        VERSION_STRING = f.read().strip()
VERSION_STRING = VERSION_STRING or "0.0.0"
"""str: The version number of DisplayCAL."""

AUTHOR = "Florian Höch, Erkan Özgür Yılmaz"  # noqa: RUF001
AUTHOR_ASCII = "Florian Hoech, Erkan Ozgur Yilmaz"
DESCRIPTION = (
    "Display calibration and profiling with a focus on accuracy and versatility"
)
LONG_DESCRIPTION = (
    "Calibrate and characterize your display devices using one of many supported "
    "measurement instruments, with support for multi-display setups and a variety of "
    "available options for advanced users, such as  verification and reporting "
    "functionality to evaluate ICC profiles and display devices, creating video 3D "
    "LUTs, as well as optional CIECAM02 gamut mapping to take into account varying "
    "viewing conditions."
)
DOMAIN = "displaycal.net"
DEVELOPMENT_HOME_PAGE = "https://github.com/eoyilmaz/displaycal-py3"
GITHUB_API_URL = "https://api.github.com/repos/eoyilmaz/displaycal-py3"
# ArgyllCMS publishes its own changelog; displaycal.net only ever mirrored an
# old copy of it (last updated for V3.0.1), so fetch it straight from the
# source instead of the stale local mirror.
ARGYLL_CHANGELOG_DOMAIN = "www.argyllcms.com"
ARGYLL_CHANGELOG_PATH = "doc/ChangesSummary.html"

AUTHOR_EMAIL = ", ".join(
    [
        f"florian{chr(0o100)}{DOMAIN}",
        f"eoyilmaz{chr(0o100)}gmail.com",
    ]
)
NAME = "DisplayCAL"
APPSTREAM_ID = ".".join(reversed([NAME, *DOMAIN.split(".")]))
NAME_HTML = '<span class="appname">Display<span>CAL</span></span>'

PY_MINVERSION = (3, 10)
PY_MAXVERSION = (3, 14)

VERSION_LIN = VERSION_STRING  # Linux
VERSION_MAC = VERSION_STRING  # Mac OS X
VERSION_WIN = VERSION_STRING  # Windows
VERSION_SRC = VERSION_STRING
# follow semver format
VERSION_TUPLE = tuple(int(n) for n in VERSION_STRING.split("-")[0].split(".")[:3])
"""tuple[int, int, int]: The version number as a tuple of integers."""

WX_MINVERSION = (4, 0, 0)
WX_RECVERSION = (4, 2, 0)


def script2pywname(script: str) -> str:
    """Convert all-lowercase script name to mixed-case pyw name."""
    a2b = {
        f"{NAME}-3dlut-maker": f"{NAME}-3DLUT-maker",
        f"{NAME}-vrml-to-x3d-converter": f"{NAME}-VRML-to-X3D-converter",
        f"{NAME}-eecolor-to-madvr-converter": f"{NAME}-eeColor-to-madVR-converter",
    }
    if script.lower().startswith(NAME.lower()):
        pyw = f"{NAME}{script[len(NAME) :]}"
        return a2b.get(pyw, pyw)
    return script
