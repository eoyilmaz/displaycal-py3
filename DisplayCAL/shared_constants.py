import os
import sys

from DisplayCAL.common_constants import exe, exedir, isapp, pyfile


isexe = sys.platform != "darwin" and getattr(sys, "frozen", False)
pydir = (
    os.path.normpath(os.path.join(exedir, "..", "Resources"))
    if isapp
    else os.path.dirname(exe if isexe else os.path.abspath(__file__))
)
pypath = exe if isexe else os.path.abspath(pyfile)
