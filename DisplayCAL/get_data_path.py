from DisplayCAL.constants import extra_data_dirs
from DisplayCAL.constants import data_dirs, exe_ext
from DisplayCAL.getcfg import getcfg
from DisplayCAL.util_os import listdir_re, which


import os


def get_data_path(relpath, rex=None):
    """
    Search data_dirs for relpath and return the path or a file list.

    If relpath is a file, return the full path, if relpath is a directory,
    return a list of files in the intersection of searched directories.
    """
    if (
        not relpath
        or relpath.endswith(os.path.sep)
        or (isinstance(os.path.altsep, str) and relpath.endswith(os.path.altsep))
    ):
        return None
    dirs = list(data_dirs)
    argyll_dir = getcfg("argyll.dir") or os.path.dirname(
        os.path.realpath(which(f"dispcal{exe_ext}") or "")
    )
    if argyll_dir and os.path.isdir(os.path.join(argyll_dir, "..", "ref")):
        dirs.append(os.path.dirname(argyll_dir))
    dirs.extend(extra_data_dirs)
    intersection = []
    paths = []
    for dir_ in dirs:
        curpath = os.path.join(dir_, relpath)
        if (
            dir_.endswith("/argyll")
            and f"{relpath}/".startswith("ref/")
            and not os.path.exists(curpath)
        ):
            # Work-around distribution-specific differences for location of
            # Argyll reference files                                                    # noqa: SC100
            # Fedora and Ubuntu: /usr/share/color/argyll/ref                            # noqa: SC100
            # openSUSE: /usr/share/color/argyll                                         # noqa: SC100
            pth = relpath.split("/", 1)[-1]
            if pth != "ref":
                curpath = os.path.join(dir_, pth)
            else:
                curpath = dir_
        if os.path.exists(curpath):
            curpath = os.path.normpath(curpath)
            if os.path.isdir(curpath):
                try:
                    filelist = listdir_re(curpath, rex)
                except Exception as exception:
                    print(f"Error - directory '{curpath}' listing failed: {exception}")
                else:
                    for filename in filelist:
                        if filename not in intersection:
                            intersection.append(filename)
                            paths.append(os.path.join(curpath, filename))
            else:
                return curpath
    if paths:
        paths.sort(key=lambda path: os.path.basename(path).lower())
    return None if len(paths) == 0 else paths
