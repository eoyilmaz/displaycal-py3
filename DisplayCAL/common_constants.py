import os
import sys

from DisplayCAL.shared_constants import isexe

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
