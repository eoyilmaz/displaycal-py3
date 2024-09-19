"""
This module contains shared constants and configuration settings for DisplayCAL.

It includes paths and flags that are used throughout the application to
determine the execution environment and locate necessary files and directories.
"""

import os
import sys

from DisplayCAL.config import exe, exedir, isapp, pyfile

isexe = sys.platform != "darwin" and getattr(sys, "frozen", False)
pydir = (
    os.path.normpath(os.path.join(exedir, "..", "Resources"))
    if isapp
    else os.path.dirname(exe if isexe else os.path.abspath(__file__))
)
pypath = exe if isexe else os.path.abspath(pyfile)
