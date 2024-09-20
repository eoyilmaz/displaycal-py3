"""
This module contains constants and configuration settings for DisplayCAL.

It defines various paths and directories used by the application,
as well as platform-specific settings such as the executable extension.
"""

import os
import sys


isexe = sys.platform != "darwin" and getattr(sys, "frozen", False)
exe = sys.executable
exedir = os.path.dirname(exe)
# Mac OS X: isapp should only be true for standalone, not 0install                      # noqa: SC100
isapp = (
    sys.platform == "darwin"
    and exe.split(os.path.sep)[-3:-1] == ["Contents", "MacOS"]
    and os.path.exists(os.path.join(exedir, "..", "Resources", "xrc"))
)
pyfile = (
    exe
    if isexe
    else (os.path.isfile(sys.argv[0]) and sys.argv[0])
    or os.path.join(os.path.dirname(__file__), "main.py")
)
pydir = (
    os.path.normpath(os.path.join(exedir, "..", "Resources"))
    if isapp
    else os.path.dirname(exe if isexe else os.path.abspath(__file__))
)
pypath = exe if isexe else os.path.abspath(pyfile)
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
