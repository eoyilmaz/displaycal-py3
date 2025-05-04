#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from glob import glob
from subprocess import call
from tempfile import mkdtemp
import os
import re
import sys


appname = "DisplayCAL"
feeduri = "http://displaycal.net/0install/%s.xml" % appname


def script2pywname(script):
    """Convert all-lowercase script name to mixed-case pyw name"""
    a2b = {
        appname + "-3dlut-maker": appname + "-3DLUT-maker",
        appname + "-vrml-to-x3d-converter": appname + "-VRML-to-X3D-converter",
    }
    pyw = appname + script[len(appname):]
    return a2b.get(pyw, pyw)


def installer(action="install"):
    if action not in ("install", "uninstall"):
        raise ValueError("Invalid action %r" % action)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if action == "install":
        tmpdir = mkdtemp()
    tmpfilenames = []
    try:
        for desktopfilename in glob(
            os.path.join(root, "misc", "%s-*.desktop" % appname.lower())
        ):
            desktopbasename = os.path.basename(desktopfilename)
            scriptname = re.sub(r"\.desktop$", "", desktopbasename)
            if action == "install":
                try:
                    for size in [16, 22, 24, 32, 48, 256]:
                        call(
                            [
                                "xdg-icon-resource",
                                action,
                                "--noupdate",
                                "--novendor",
                                "--size",
                                str(size),
                                os.path.join(
                                    root,
                                    appname,
                                    "theme",
                                    "icons",
                                    "%sx%s" % (size, size),
                                    scriptname + ".png",
                                ),
                            ]
                        )
                except EnvironmentError as exception:
                    exception.filename = "xdg-icon-resource"
                    raise exception
                with open(desktopfilename) as desktopfile:
                    contents = desktopfile.read()
                cmdname = script2pywname(scriptname)
                cmd = re.sub(r"^%s-" % appname, "run-", cmdname)
                for pattern, repl in [
                    ("Exec=.+", "Exec=0launch --command=%s -- %s %%f" % (cmd, feeduri))
                ]:
                    contents = re.sub(pattern, repl, contents)
                tmpfilename = os.path.join(tmpdir, desktopbasename)
                tmpfilenames.append(tmpfilename)
                with open(tmpfilename, "w") as tmpfile:
                    tmpfile.write(contents)
                try:
                    call(
                        [
                            "xdg-desktop-menu",
                            action,
                            "--noupdate",
                            "--novendor",
                            tmpfilename,
                        ]
                    )
                except EnvironmentError as exception:
                    exception.filename = "xdg-desktop-menu"
                    raise exception
            else:
                try:
                    for size in [16, 22, 24, 32, 48, 256]:
                        call(
                            [
                                "xdg-icon-resource",
                                action,
                                "--noupdate",
                                "--size",
                                str(size),
                                scriptname,
                            ]
                        )
                except EnvironmentError as exception:
                    exception.filename = "xdg-icon-resource"
                    raise exception
                try:
                    call(["xdg-desktop-menu", action, "--noupdate", desktopfilename])
                except EnvironmentError as exception:
                    exception.filename = "xdg-desktop-menu"
                    raise exception
    finally:
        if action == "install":
            try:
                for tmpfilename in tmpfilenames:
                    if tmpfilename and os.path.isfile(tmpfilename):
                        os.unlink(tmpfilename)
                os.rmdir(tmpdir)
            except Exception as exception:
                import warnings

                warnings.warn(exception, Warning)
    if os.geteuid() == 0:
        data_dirs = os.getenv("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(
            os.pathsep
        )
    else:
        data_dirs = os.getenv(
            "XDG_DATA_HOME", os.path.expandvars("$HOME/.local/share")
        ).split(os.pathsep)
    for data_dir in data_dirs:
        call(["touch", "--no-create", data_dir.rstrip("/") + "/icons/hicolor"])
    call(["xdg-icon-resource", "forceupdate"])
    call(["xdg-desktop-menu", "forceupdate"])


if __name__ == "__main__":
    if len(sys.argv) == 2:
        try:
            installer(sys.argv[1])
        except Exception as exception:
            print(exception)
    else:
        print("Usage: %s install | uninstall" % os.path.basename(__file__))
