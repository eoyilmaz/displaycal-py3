"""
This module contains constants and configuration settings for DisplayCAL.

It defines various paths and directories used by the application,
as well as platform-specific settings such as the executable extension.
"""

import os
import sys

from DisplayCAL.shared_constants import isexe, pydir, pypath

# TODO: Modifying ``data_dirs`` here was not an elegant solution,                       # noqa: SC100
# and it is not solving the problem either.
data_dirs = [
    # venv/share/DisplayCAL                                                             # noqa: SC100
    os.path.join(os.path.dirname(os.path.dirname(pypath)), "share", "DisplayCAL"),
    # venv/lib/python3.x/site-packages/DisplayCAL                                       # noqa: SC100
    pydir,
    # venv/share                                                                        # noqa: SC100
    os.path.join(os.path.dirname(pydir), "share"),
    # venv/lib/python3.x/site-packages/DisplayCAL-*.egg/share/DisplayCAL                # noqa: SC100
    os.path.join(os.path.dirname(pydir), "share", "DisplayCAL"),
]

if sys.platform == "win32":
    exe_ext = ".exe"
else:
    exe_ext = ""

extra_data_dirs = []
