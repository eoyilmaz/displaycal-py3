# -*- coding: utf-8 -*-
"""Argyll utilities situated here.

The utilities that were previously spread around are gathered here.
"""

# Standard Library Imports
from functools import cache

import os
import re
import string
import subprocess as sp
import sys
import urllib.error
import urllib.request
from typing import List, Optional, Union

# Local Imports
from DisplayCAL.argyll_names import (
    names as argyll_names,
    altnames as argyll_altnames,
    optional as argyll_optional,
)
from DisplayCAL import config, localization as lang
from DisplayCAL.config import (
    exe_ext,
    fs_enc,
    get_data_path,
    get_verified_path,
    getcfg,
    geticon,
    setcfg,
    writecfg,
)
from DisplayCAL.options import debug, verbose
from DisplayCAL.util_os import getenvu, safe_glob, which
from DisplayCAL.util_str import make_filename_safe

argyll_utils = {}


def check_argyll_bin(paths: Optional[List[str]] = None) -> bool:
    """Check if the Argyll binaries can be found.

    Args:
        paths (Optional[List[str]]): The paths to look for.

    Returns:
        bool: True if all required Argyll binaries are found, False otherwise.
    """
    prev_dir = None
    cur_dir = os.curdir
    for name in argyll_names:
        exe = get_argyll_util(name, paths)
        if not exe:
            if name in argyll_optional:
                continue
            return False
        cur_dir = os.path.dirname(exe)
        if not prev_dir:
            prev_dir = cur_dir
            continue
        if cur_dir == prev_dir:
            continue
        if name in argyll_optional:
            if verbose:
                print(
                    f"Warning: Optional Argyll executable {exe} is not "
                    "in the same directory as the main executables "
                    f"({prev_dir})."
                )
        else:
            if verbose:
                print(
                    f"Error: Main Argyll executable {exe} is not in the "
                    f"same directory as the other executables ({prev_dir})."
                )
            return False

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
        print("[D] Search path:\n  ", "\n  ".join(paths))
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


def set_argyll_bin(parent=None, silent=False, callafter=None, callafter_args=()):
    """Set the directory containing the Argyll CMS binary executables."""
    # TODO: This function contains UI stuff, please refactor it so that it is
    #       split into a separate function that can be called from the UI.
    from DisplayCAL.wxaddons import wx
    from DisplayCAL.wxwindows import ConfirmDialog, InfoDialog

    if parent and not parent.IsShownOnScreen():
        parent = None  # do not center on parent if not visible
    # Check if Argyll version on PATH is newer than configured Argyll version
    paths = getenvu("PATH", os.defpath).split(os.pathsep)
    argyll_version_string = get_argyll_version_string("dispwin", True, paths)
    argyll_version = parse_argyll_version_string(argyll_version_string)
    argyll_version_string_cfg = get_argyll_version_string("dispwin", True)
    argyll_version_cfg = parse_argyll_version_string(argyll_version_string_cfg)
    # Don't prompt for 1.2.3_foo if current version is 1.2.3
    # but prompt for 1.2.3 if current version is 1.2.3_foo
    # Also prompt for 1.2.3_beta2 if current version is 1.2.3_beta
    if (
        argyll_version > argyll_version_cfg
        and (
            argyll_version[:4] == argyll_version_cfg[:4]
            or not argyll_version_string.startswith(argyll_version_string_cfg)
        )
    ) or (
        argyll_version < argyll_version_cfg
        and argyll_version_string_cfg.startswith(argyll_version_string)
        and "beta" in argyll_version_string_cfg.lower()
    ):
        argyll_dir = os.path.dirname(get_argyll_util("dispwin", paths) or "")
        dlg = ConfirmDialog(
            parent,
            msg=lang.getstr(
                "dialog.select_argyll_version",
                (argyll_version_string, argyll_version_string_cfg),
            ),
            ok=lang.getstr("ok"),
            cancel=lang.getstr("cancel"),
            alt=lang.getstr("browse"),
            bitmap=geticon(32, "dialog-question"),
        )
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if dlg_result == wx.ID_OK:
            setcfg("argyll.dir", None)
            # Always write cfg directly after setting Argyll directory so
            # subprocesses that read the configuration will use the right
            # executables
            writecfg()
            return True
        if dlg_result == wx.ID_CANCEL:
            if callafter:
                callafter(*callafter_args)
            return False
    else:
        argyll_dir = None
    if parent and not check_argyll_bin():
        dlg = ConfirmDialog(
            parent,
            msg=lang.getstr("dialog.argyll.notfound.choice"),
            ok=lang.getstr("download"),
            cancel=lang.getstr("cancel"),
            alt=lang.getstr("browse"),
            bitmap=geticon(32, "dialog-question"),
        )
        dlg_result = dlg.ShowModal()
        dlg.Destroy()
        if dlg_result == wx.ID_OK:
            # Download Argyll CMS
            from DisplayCAL.display_cal import app_update_check

            app_update_check(parent, silent, argyll=True)
            return False
        elif dlg_result == wx.ID_CANCEL:
            if callafter:
                callafter(*callafter_args)
            return False
    defaultPath = os.path.join(*get_verified_path("argyll.dir", path=argyll_dir))
    dlg = wx.DirDialog(
        parent,
        lang.getstr("dialog.set_argyll_bin"),
        defaultPath=defaultPath,
        style=wx.DD_DIR_MUST_EXIST,
    )
    dlg.Center(wx.BOTH)
    result = False
    while not result:
        result = dlg.ShowModal() == wx.ID_OK
        if result:
            path = dlg.GetPath().rstrip(os.path.sep)
            if os.path.basename(path) != "bin":
                path = os.path.join(path, "bin")
            result = check_argyll_bin([path])
            if result:
                if verbose >= 3:
                    print("Setting Argyll binary directory:", path)
                setcfg("argyll.dir", path)
                # Always write cfg directly after setting Argyll directory so
                # subprocesses that read the configuration will use the right
                # executables
                writecfg()
                break
            else:
                not_found = []
                for name in argyll_names:
                    if (
                        not get_argyll_util(name, [path])
                        and name not in argyll_optional
                    ):
                        not_found.append(
                            f" {lang.getstr('or')} ".join(
                                [
                                    altname
                                    for altname in [
                                        altname + exe_ext
                                        for altname in argyll_altnames[name]
                                    ]
                                    if "argyll" not in altname
                                ]
                            )
                        )
                InfoDialog(
                    parent,
                    msg="{}\n\n{}".format(
                        path, lang.getstr("argyll.dir.invalid", ", ".join(not_found))
                    ),
                    ok=lang.getstr("ok"),
                    bitmap=geticon(32, "dialog-error"),
                )
        else:
            break
    dlg.Destroy()
    if not result and callafter:
        callafter(*callafter_args)
    return result


def check_set_argyll_bin(paths: Optional[List[str]] = None) -> bool:
    """Check if Argyll binaries can be found, otherwise let the user choose.

    Args:
        paths (Optional[List[str]]): The paths to look for.
    """
    if check_argyll_bin(paths):
        return True
    else:
        return set_argyll_bin()


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
            exe = which(f"{altname}{exe_ext}", [path])
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


def get_argyll_version(name, silent=False, paths=None):
    """Determine version of a certain Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        silent (bool): Silently check Argyll version. Default is False.
        paths (Union[list, None]): Paths to look for Argyll executables.

    Returns:
        str: The Argyll utility version.
    """
    argyll_version_string = get_argyll_version_string(name, silent, paths)
    return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(name, silent=False, paths=None):
    """Return the version of the requested Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        silent (bool): Silently check Argyll version. Default is False.
        paths (Union[list, None]): Paths to look for Argyll executables.

    Returns:
        str: The Argyll utility version.
    """
    argyll_version_string = "0.0.0"
    if (not silent or not check_argyll_bin(paths)) and (
        silent or not check_set_argyll_bin(paths)
    ):
        return argyll_version_string

    # Try getting the version from the log.txt file first
    argyll_dir = getcfg("argyll.dir")
    if argyll_dir:
        log_path = os.path.join(argyll_dir, "log.txt")
        if os.path.isfile(log_path):
            try:
                with open(log_path, "rb") as f:
                    log_data = f.read(150)
                match = re.search(rb"(?<=Version )\d+\.\d+\.\d+(_\w+)?", log_data)
                if match:
                    return match.group().decode("utf-8")
            except Exception as e:
                print(f"Error reading {log_path}: {e}")
    else:
        print("Warning: Argyll directory not set in config.")

    # If the log.txt file is not available or doesn't contain the version,
    # fall back to using the utility itself
    # to get the version

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
        return argyll_version_string

    for line in (p.communicate(timeout=30)[0] or b"").splitlines():
        line = line.strip()
        if b"version" in line.lower():
            argyll_version_string = line[line.lower().find(b"version") + 8 :].decode(
                "utf-8"
            )
            break

    return argyll_version_string


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


@cache
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
            .read(100)
            .decode("utf-8"),
        )
    except urllib.error.URLError as e:
        # no internet connection
        # return the default version
        return config.defaults.get("argyll.version")
    result = changelog.group()
    print(f"Latest ArgyllCMS version: {result} (from {argyll_domain}/log.txt)")
    if not result:
        # no version found
        return config.defaults.get("argyll.version")
    return result


def make_argyll_compatible_path(path):
    """Make the path compatible with the Argyll utilities.

    This is currently only effective under Windows to make sure that any
    unicode 'division' slashes in the profile name are replaced with
    underscores.

    Args:
        path (Union[bytes, str]): The path to be made compatible.

    Returns:
        Union[bytes, str]: The compatible path.
    """
    skip = -1
    regex = r"\\\\\?\\"
    driver_letter_escape_char = ":"
    os_path_sep = os.path.sep
    string_ascii_uppercase = string.ascii_uppercase
    if isinstance(path, bytes):
        regex = regex.encode("utf-8")
        driver_letter_escape_char = driver_letter_escape_char.encode("utf-8")
        os_path_sep = os_path_sep.encode("utf-8")
        string_ascii_uppercase = string_ascii_uppercase.encode("utf-8")

    if re.match(regex, path, re.I):
        # Don't forget about UNC paths:
        # \\?\UNC\Server\Volume\File
        # \\?\C:\File
        skip = 2

    parts = path.split(os_path_sep)
    if sys.platform == "win32" and len(parts) > skip + 1:
        driveletterpart = parts[skip + 1]
        if (
            len(driveletterpart) == 2
            and driveletterpart[0:1].upper() in string_ascii_uppercase
            and driveletterpart[1:2] == driver_letter_escape_char
        ):
            skip += 1

    for i, part in enumerate(parts):
        if i > skip:
            parts[i] = make_filename_safe(part)
    return os_path_sep.join(parts)


def get_argyll_instrument_config(what=None):
    """Check for Argyll CMS udev rules/hotplug scripts."""
    filenames = []
    if what == "installed":
        for filename in (
            "/etc/udev/rules.d/55-Argyll.rules",
            "/etc/udev/rules.d/45-Argyll.rules",
            "/etc/hotplug/Argyll",
            "/etc/hotplug/Argyll.usermap",
            "/lib/udev/rules.d/55-Argyll.rules",
            "/lib/udev/rules.d/69-cd-sensors.rules",
        ):
            if os.path.isfile(filename):
                filenames.append(filename)
    else:
        if what == "expected":
            fn = lambda filename: filename
        else:
            fn = get_data_path
        if os.path.isdir("/etc/udev/rules.d"):
            if safe_glob("/dev/bus/usb/*/*"):
                # USB and serial instruments using udev, where udev
                # already creates /dev/bus/usb/00X/00X devices
                filenames.append(fn("usb/55-Argyll.rules"))
            else:
                # USB using udev, where there are NOT /dev/bus/usb/00X/00X
                # devices
                filenames.append(fn("usb/45-Argyll.rules"))
        else:
            if os.path.isdir("/etc/hotplug"):
                # USB using hotplug and Serial using udev
                # (older versions of Linux)
                filenames.extend(
                    fn(filename) for filename in ("usb/Argyll", "usb/Argyll.usermap")
                )
    return [filename for filename in filenames if filename]
