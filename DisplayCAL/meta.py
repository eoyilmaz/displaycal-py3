"""Meta information."""

import re

try:
    from DisplayCAL.__version__ import (
        BUILD_DATE as BUILD,
    )
    from DisplayCAL.__version__ import (
        LASTMOD,
        VERSION,
        VERSION_BASE,
        VERSION_STRING,
    )
except ImportError:
    BUILD = LASTMOD = "1970-01-01T00:00:00Z"
    VERSION = None
    VERSION_STRING = None

from DisplayCAL.options import TEST_UPDATE

if not VERSION or TEST_UPDATE:
    VERSION = VERSION_BASE = (0, 0, 0)
    VERSION_STRING = ".".join(str(n) for n in VERSION)

AUTHOR = ", ".join(["Florian Höch", "Erkan Özgür Yılmaz", "Patrick Zwerschke"])
AUTHOR_ASCII = ", ".join(["Florian Hoech", "Erkan Ozgur Yilmaz", "Patrick Zwerschke"])
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

AUTHOR_EMAIL = ", ".join(
    [
        f"florian{chr(0o100)}{DOMAIN}",
        f"eoyilmaz{chr(0o100)}gmail.com",
        f"patrick{chr(0o100)}p5k.org",
    ]
)
NAME = "DisplayCAL"
APPSTREAM_ID = ".".join(reversed([NAME] + DOMAIN.split(".")))
NAME_HTML = '<span class="appname">Display<span>CAL</span></span>'

PY_MINVERSION = (3, 9)
PY_MAXVERSION = (3, 13)

VERSION_STRING = VERSION_STRING
VERSION_LIN = VERSION_STRING  # Linux
VERSION_MAC = VERSION_STRING  # Mac OS X
VERSION_WIN = VERSION_STRING  # Windows
VERSION_SRC = VERSION_STRING
VERSION_SHORT = re.sub(r"(?:\.0){1,2}$", "", VERSION_STRING)
VERSION_TUPLE = VERSION  # only ints allowed and must be exactly 3 values

WX_MINVERSION = (4, 0, 0)
WX_RECVERSION = (4, 2, 0)


def get_latest_changelog_entry(readme):
    """Get changelog entry for latest version from ReadMe HTML"""
    changelog = re.search(
        r'<div id="(?:changelog|history)">.+?<h2>.+?</h2>.+?<dl>.+?</dd>', readme, re.S
    )

    if changelog:
        changelog = changelog.group()
        changelog = re.sub(r'\s*<div id="(?:changelog|history)">\n?', "", changelog)
        changelog = re.sub(r"\s*</?d[ld]>\n?", "", changelog)
        changelog = re.sub(r"\s*<(h[23])>.+?</\1>\n?", "", changelog)

    return changelog


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
