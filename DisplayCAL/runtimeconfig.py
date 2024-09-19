from DisplayCAL.config import confighome, defaults, exedir, isapp, logdir, pydir, pyext, pyname
from DisplayCAL.constants import data_dirs, exe_ext
from DisplayCAL.get_data_path import get_data_path
from DisplayCAL.meta import name as appname
from DisplayCAL.options import debug
from DisplayCAL.safe_print import fs_enc
from DisplayCAL.util_os import getenvu


import os
import sys


def runtimeconfig(pyfile):
    """
    Configure remaining runtime options and return runtype.

    You need to pass in a path to the calling script (e.g. use the __file__ attribute).
    """
    # global safe_log
    from DisplayCAL.log import setup_logging

    setup_logging(logdir, pyname, pyext, confighome=confighome)
    if debug:
        print("[D] pydir:", pydir)
    if isapp:
        runtype = ".app"
    elif isexe:
        if debug:
            print("[D] _MEIPASS2 or pydir:", getenvu("_MEIPASS2", exedir))
        if getenvu("_MEIPASS2", exedir) not in data_dirs:
            data_dirs.insert(1, getenvu("_MEIPASS2", exedir))
        runtype = exe_ext
    else:
        pydir_parent = os.path.dirname(pydir)
        if debug:
            print(
                "[D] dirname(os.path.abspath(sys.argv[0])):",
                os.path.dirname(os.path.abspath(sys.argv[0])),
            )
            print("[D] pydir parent:", pydir_parent)
        if (
            os.path.dirname(os.path.abspath(sys.argv[0])) == pydir_parent
            and pydir_parent not in data_dirs
        ):
            # Add the parent directory of the package directory to our list of
            # data directories if it is the directory containing the currently
            # run script (e.g. when running from source)
            data_dirs.insert(1, pydir_parent)
        runtype = pyext
    for dir_ in sys.path:
        if not isinstance(dir_, str):
            dir_ = dir_.encode(fs_enc)
        dir_ = os.path.abspath(os.path.join(dir_, appname))
        if dir_ not in data_dirs and os.path.isdir(dir_):
            data_dirs.append(dir_)
            if debug:
                print("[D] from sys.path:", dir_)
    if sys.platform not in ("darwin", "win32"):
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", f"{appname}-{version}")
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", "packages", appname)
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", appname)
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "doc", appname.lower())  # Debian
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
        data_dirs.extend(
            [
                os.path.join(dir_, "icons", "hicolor")
                for dir_ in xdg_data_dirs + [xdg_data_home]
            ]
        )
    if debug:
        print("[D] Data files search paths:\n[D]", "\n[D] ".join(data_dirs))
    defaults["calibration.file"] = get_data_path("presets/default.icc") or ""
    defaults["measurement_report.chart"] = (
        get_data_path(os.path.join("ref", "verify_extended.ti1")) or ""
    )
    return runtype
