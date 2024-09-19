from DisplayCAL.config import exe, exedir, isapp, pyfile


import os


pydir = (
    os.path.normpath(os.path.join(exedir, "..", "Resources"))
    if isapp
    else os.path.dirname(exe if isexe else os.path.abspath(__file__))
)
pypath = exe if isexe else os.path.abspath(pyfile)
