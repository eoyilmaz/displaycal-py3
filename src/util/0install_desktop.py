#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from glob import glob
import os
import re
import shutil
import sys

from DisplayCAL.meta import name as appname, DOMAIN, script2pywname


def zeroinstall_desktop(datadir="/usr/share"):
    """Install icon and desktop files for 0install implementation"""
    appdir = os.path.join(datadir, "applications")
    if not os.path.isdir(appdir):
        os.makedirs(appdir)
    feeduri = f"http://{DOMAIN}/0install/{appname}.xml"
    for desktopfilename in glob(os.path.join("misc", "%s*.desktop" % appname.lower())):
        desktopbasename = os.path.basename(desktopfilename)
        scriptname = re.sub(r"\.desktop$", "", desktopbasename)
        for size in [16, 22, 24, 32, 48, 128, 256]:
            icondir = os.path.join(
                datadir, "icons", "hicolor", "%sx%s" % (size, size), "apps"
            )
            if not os.path.isdir(icondir):
                os.makedirs(icondir)
            shutil.copy(
                os.path.join(
                    appname,
                    "theme",
                    "icons",
                    "%sx%s" % (size, size),
                    scriptname + ".png",
                ),
                icondir,
            )
        with open(desktopfilename) as desktopfile:
            contents = desktopfile.read()
        cmdname = script2pywname(scriptname)
        if cmdname == appname:
            cmd = ""
        else:
            cmd = re.sub(r"^%s" % appname, " --command=run", cmdname)
        for pattern, repl in [("Exec=.+", "Exec=0launch%s -- %s %%f" % (cmd, feeduri))]:
            contents = re.sub(pattern, repl, contents)
        if cmdname == appname:
            desktopbasename = ("zeroinstall-" + desktopbasename).lower()
        with open(os.path.join(appdir, desktopbasename), "w") as desktopfile:
            desktopfile.write(contents)


if __name__ == "__main__":
    zeroinstall_desktop(*sys.argv[1:])
