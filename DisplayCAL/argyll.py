# -*- coding: utf-8 -*-
"""Argyll utilities situated here.

The utilities that were previously spread around are gathered here.
"""
# Standard Library Imports
import os
import re
import subprocess as sp
import sys
import urllib.error
import urllib.request

# Local Imports
from DisplayCAL.argyll_names import (
    names as argyll_names,
    altnames as argyll_altnames,
    optional as argyll_optional,
)
from DisplayCAL import config
from DisplayCAL.config import exe_ext, fs_enc, get_data_path, getcfg
from DisplayCAL.options import debug, verbose
from DisplayCAL.util_os import getenvu, which

argyll_utils = {}


def check_argyll_bin(paths=None):
    """Check if the Argyll binaries can be found."""
    prev_dir = None
    cur_dir = os.curdir
    for name in argyll_names:
        exe = get_argyll_util(name, paths)
        if not exe:
            if name in argyll_optional:
                continue
            return False
        cur_dir = os.path.dirname(exe)
        if prev_dir:
            if cur_dir != prev_dir:
                if name in argyll_optional:
                    if verbose:
                        print(
                            "Warning: Optional Argyll executable %s is not in the same "
                            "directory as the main executables (%s)." % (exe, prev_dir)
                        )
                else:
                    if verbose:
                        print(
                            "Error: Main Argyll executable %s is not in the same "
                            "directory as the other executables (%s)." % (exe, prev_dir)
                        )
                    return False
        else:
            prev_dir = cur_dir
    if verbose >= 3:
        print("Argyll binary directory:", cur_dir)
    if debug:
        print("[D] check_argyll_bin OK")
    if debug >= 2:
        if not paths:
            paths = getenvu("PATH", os.defpath).split(os.pathsep)
            argyll_dir = (getcfg("argyll.dir") or "").rstrip(os.path.sep)
            if argyll_dir:
                if argyll_dir in paths:
                    paths.remove(argyll_dir)
                paths = [argyll_dir] + paths
        print("[D] Searchpath:\n  ", "\n  ".join(paths))
    # Fedora doesn't ship Rec709.icm
    config.defaults["3dlut.input.profile"] = (
        get_data_path(os.path.join("ref", "Rec709.icm"))
        or get_data_path(os.path.join("ref", "sRGB.icm"))
        or ""
    )
    config.defaults["testchart.reference"] = (
        get_data_path(os.path.join("ref", "ColorChecker.cie")) or ""
    )
    config.defaults["gamap_profile"] = (
        get_data_path(os.path.join("ref", "sRGB.icm")) or ""
    )
    return True


def get_argyll_util(name, paths=None):
    """Find a single Argyll utility. Return the full path.

    Args:
        name (str): The name of the utility.
        paths (Union[None, List[str]]): The paths to look for.

    Returns:
        Union[None, str]: None if not found or the path of the utility.
    """
    cfg_argyll_dir = getcfg("argyll.dir")
    if not paths:
        paths = getenvu("PATH", os.defpath).split(os.pathsep)
        argyll_dir = (cfg_argyll_dir or "").rstrip(os.path.sep)
        if argyll_dir:
            if argyll_dir in paths:
                paths.remove(argyll_dir)
            paths = [argyll_dir] + paths
    cache_key = os.pathsep.join(paths)
    exe = argyll_utils.get(cache_key, {}).get(name, None)
    if exe:
        return exe
    elif verbose >= 4:
        print("Info: Searching for", name, "in", os.pathsep.join(paths))
    for path in paths:
        for altname in argyll_altnames.get(name, []):
            exe = which(altname + exe_ext, [path])
            if exe:
                break
        if exe:
            break
    if verbose >= 4:
        if exe:
            print("Info:", name, "=", exe)
        else:
            print(
                "Info:",
                "|".join(argyll_altnames[name]),
                "not found in",
                os.pathsep.join(paths),
            )
    if exe:
        if cache_key not in argyll_utils:
            argyll_utils[cache_key] = {}
        argyll_utils[cache_key][name] = exe
    return exe


def get_argyll_utilname(name, paths=None):
    """Find a single Argyll utility.

    Return the basename without extension.
    """
    exe = get_argyll_util(name, paths)
    if exe:
        exe = os.path.basename(os.path.splitext(exe)[0])
    return exe


def get_argyll_version(name, paths=None):
    """Determine version of a certain Argyll utility."""
    argyll_version_string = get_argyll_version_string(name, paths)
    return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(name, paths=None):
    """Return the version of the requested Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        paths (Union[list, None]): Paths to look for Argyll executables.

    Returns:
        str: The Argyll utility version.
    """
    argyll_version_string = b"0.0.0"
    cmd = get_argyll_util(name, paths)
    if sys.platform == "win32":
        startupinfo = sp.STARTUPINFO()
        startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = sp.SW_HIDE
    else:
        startupinfo = None
    try:
        p = sp.Popen(
            [cmd.encode(fs_enc), "-?"],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            startupinfo=startupinfo,
        )
    except Exception as exception:
        print(exception)
        return argyll_version_string.decode("utf-8")
    for line in (p.communicate(timeout=30)[0] or b"").splitlines():
        line = line.strip()
        if b"version" in line.lower():
            argyll_version_string = line[line.lower().find(b"version") + 8:]
            break
    return argyll_version_string.decode("utf-8")


def parse_argyll_version_string(argyll_version_string):
    if isinstance(argyll_version_string, bytes):
        argyll_version_string = argyll_version_string.decode()
    argyll_version = re.findall(r"(\d+|[^.\d]+)", argyll_version_string)
    for i, v in enumerate(argyll_version):
        try:
            argyll_version[i] = int(v)
        except ValueError:
            pass
    return argyll_version


def get_argyll_latest_version():
    """Return the latest ArgyllCMS version from argyllcms.com.

    Returns:
        str: The latest version number. Returns
    """
    argyll_domain = config.defaults.get("argyll.domain", "")
    try:
        changelog = re.search(
            r"(?<=Version ).{5}",
            urllib.request.urlopen(f"{argyll_domain}/log.txt")
            .read(150)
            .decode("utf-8"),
        )
    except urllib.error.URLError as e:
        # no internet connection
        # return the default version
        return config.defaults.get("argyll.version")
    return changelog.group()
