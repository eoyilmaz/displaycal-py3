# -*- coding: utf-8 -*-
"""
Meta information
"""

import re
import sys


try:
    from DisplayCAL.__version__ import (
        BUILD_DATE as build,
        LASTMOD as lastmod,
        VERSION,
        VERSION_BASE,
        VERSION_STRING,
    )
except ImportError:
    build = lastmod = "1970-01-01T00:00:00Z"
    VERSION = None
    VERSION_STRING = None

from DisplayCAL.options import test_update

if not VERSION or test_update:
    VERSION = VERSION_BASE = (0, 0, 0)
    VERSION_STRING = ".".join(str(n) for n in VERSION)

author = ", ".join(["Florian Höch", "Erkan Özgür Yılmaz", "Patrick Zwerschke"])
author_ascii = ", ".join(["Florian Hoech", "Erkan Ozgur Yilmaz", "Patrick Zwerschke"])
description = (
    "Display calibration and profiling with a focus on accuracy and versatility"
)
longdesc = (
    "Calibrate and characterize your display devices using one of many supported "
    "measurement instruments, with support for multi-display setups and a variety of "
    "available options for advanced users, such as  verification and reporting "
    "functionality to evaluate ICC profiles and display devices, creating video 3D "
    "LUTs, as well as optional CIECAM02 gamut mapping to take into account varying "
    "viewing conditions."
)
DOMAIN = "displaycal.net"
development_home_page = "https://github.com/eoyilmaz/displaycal-py3"

author_email = ", ".join(
    [
        f"florian{chr(0o100)}{DOMAIN}",
        f"eoyilmaz{chr(0o100)}gmail.com",
        f"patrick{chr(0o100)}p5k.org",
    ]
)
name = "DisplayCAL"
appstream_id = ".".join(reversed([name] + DOMAIN.split(".")))
name_html = '<span class="appname">Display<span>CAL</span></span>'

py_minversion = (3, 8)
py_maxversion = (3, 13)

version = VERSION_STRING
version_lin = VERSION_STRING  # Linux
version_mac = VERSION_STRING  # Mac OS X
version_win = VERSION_STRING  # Windows
version_src = VERSION_STRING
version_short = re.sub(r"(?:\.0){1,2}$", "", version)
version_tuple = VERSION  # only ints allowed and must be exactly 3 values

wx_minversion = (2, 8, 11)
wx_recversion = (4, 2, 0)


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


def script2pywname(script):
    """Convert all-lowercase script name to mixed-case pyw name"""
    a2b = {
        name + "-3dlut-maker": name + "-3DLUT-maker",
        name + "-vrml-to-x3d-converter": name + "-VRML-to-X3D-converter",
        name + "-eecolor-to-madvr-converter": name + "-eeColor-to-madVR-converter",
    }
    if script.lower().startswith(name.lower()):
        pyw = name + script[len(name) :]
        return a2b.get(pyw, pyw)
    return script
