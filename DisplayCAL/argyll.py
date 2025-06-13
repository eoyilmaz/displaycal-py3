"""Argyll utilities situated here.

The utilities that were previously spread around are gathered here.
"""

# Standard Library Imports
from __future__ import annotations

import contextlib
import os
import re
import string
import subprocess as sp
import sys
import urllib.error
import urllib.request
from functools import cache
from typing import TYPE_CHECKING, Callable, overload

# Local Imports
from DisplayCAL import config, options
from DisplayCAL import localization as lang
from DisplayCAL.argyll_names import ALTNAMES as ARGYLL_ALTNAMES
from DisplayCAL.argyll_names import NAMES as ARGYLL_NAMES
from DisplayCAL.argyll_names import OPTIONAL as ARGYLL_OPTIONAL
from DisplayCAL.config import (
    EXE_EXT,
    FS_ENC,
    get_data_path,
    get_verified_path,
    getcfg,
    geticon,
    setcfg,
    writecfg,
)
from DisplayCAL.util_os import getenvu, safe_glob, which
from DisplayCAL.util_str import make_filename_safe

if TYPE_CHECKING:
    import wx  # noqa: TC004

ARGYLL_UTILS = {}


def debug_print(*args, **kwargs) -> None:
    """Prints messages if DEBUG is set to 1 or higher."""
    if kwargs.pop("debug_level", 1) <= options.DEBUG:
        print(*args, **kwargs)


def verbose_print(*args, **kwargs) -> None:
    """Prints messages if VERBOSE is set to 1 or higher."""
    if kwargs.pop("verbose_level", 1) <= options.VERBOSE:
        print(*args, **kwargs)


def get_path_from_env() -> list[str]:
    """Parse environment paths into a list.

    Returns:
        list[str]: A list of paths.
    """
    return getenvu("PATH", os.defpath).split(os.pathsep)


def check_argyll_bin(paths: None | list[str] = None) -> bool:
    """Check if the Argyll binaries can be found.

    Args:
        paths (None | list[str]): The paths to look for.

    Returns:
        bool: True if all required Argyll binaries are found, False otherwise.
    """
    prev_dir = None
    cur_dir = os.curdir
    for name in ARGYLL_NAMES:
        exe = get_argyll_util(name, paths)
        if not exe:
            if name in ARGYLL_OPTIONAL:
                continue
            return False
        cur_dir = os.path.dirname(exe)
        if not prev_dir:
            prev_dir = cur_dir
            continue
        if cur_dir == prev_dir:
            continue
        if name in ARGYLL_OPTIONAL:
            verbose_print(
                f"Warning: Optional Argyll executable {exe} is not "
                "in the same directory as the main executables "
                f"({prev_dir})."
            )
        else:
            verbose_print(
                f"Error: Main Argyll executable {exe} is not in the "
                f"same directory as the other executables ({prev_dir})."
            )
            return False

    verbose_print("Argyll binary directory:", cur_dir, verbose_level=3)
    debug_print("[D] check_argyll_bin OK")
    if options.DEBUG >= 2:
        if not paths:
            paths = get_path_from_env()
            argyll_dir = (getcfg("argyll.dir") or "").rstrip(os.path.sep)
            if argyll_dir:
                if argyll_dir in paths:
                    paths.remove(argyll_dir)
                paths = [argyll_dir, *paths]
        print("[D] Search path:\n  ", "\n  ".join(paths))
    # Fedora doesn't ship Rec709.icm
    config.DEFAULTS["3dlut.input.profile"] = (
        get_data_path(os.path.join("ref", "Rec709.icm"))
        or get_data_path(os.path.join("ref", "sRGB.icm"))
        or ""
    )
    config.DEFAULTS["testchart.reference"] = (
        get_data_path(os.path.join("ref", "ColorChecker.cie")) or ""
    )
    config.DEFAULTS["gamap_profile"] = (
        get_data_path(os.path.join("ref", "sRGB.icm")) or ""
    )
    return True


def prompt_argyll_dir(
    parent: wx.Window = None,
    callafter: None | Callable = None,
    callafter_args: None | tuple = None,
) -> str:
    """Prompt the user for the Argyll CMS directory.

    Args:
        parent (wx.Window): The parent window for dialogs.
        callafter (callable): A function to call after setting the Argyll bin.
        callafter_args (None | tuple): Arguments to pass to the callafter
            function.

    Returns:
        str: The path to the Argyll CMS directory.
    """
    # Check if Argyll version on PATH is newer than configured Argyll version
    paths = get_path_from_env()
    argyll_version_string = get_argyll_version_string("dispwin", True, paths)
    argyll_version = parse_argyll_version_string(argyll_version_string)
    argyll_version_string_cfg = get_argyll_version_string("dispwin", True)
    argyll_version_cfg = parse_argyll_version_string(argyll_version_string_cfg)
    # Don't prompt for 1.2.3_foo if current version is 1.2.3
    # but prompt for 1.2.3 if current version is 1.2.3_foo
    # Also prompt for 1.2.3_beta2 if current version is 1.2.3_beta
    argyll_dir = None
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
        from DisplayCAL.wx_windows import ConfirmDialog

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

    return argyll_dir


def set_argyll_bin(
    parent: wx.Window = None,
    silent: bool = False,
    callafter: None | Callable = None,
    callafter_args: None | tuple = None,
) -> bool:
    """Set the directory containing the Argyll CMS binary executables.

    Args:
        parent (wx.Window): The parent window for dialogs.
        silent (bool): If True, do not show any dialogs.
        callafter (callable): A function to call after setting the Argyll bin.
        callafter_args (None | tuple): Arguments to pass to the callafter
            function.

    Returns:
        bool: True if the Argyll bin was set successfully, False otherwise.
    """
    # TODO: This function contains UI stuff, please refactor it so that it is
    #       split into a separate function that can be called from the UI.
    from DisplayCAL.wx_addons import wx
    from DisplayCAL.wx_windows import ConfirmDialog, InfoDialog

    # Tests fails if wx.App is not initialized...
    _ = wx.GetApp() or wx.App()

    callafter_args = () if callafter_args is None else callafter_args

    # do not center on parent if not visible
    parent = None if parent and not parent.IsShownOnScreen() else parent
    argyll_dir = prompt_argyll_dir(parent, callafter, callafter_args)
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
        if dlg_result == wx.ID_CANCEL:
            if callafter:
                callafter(*callafter_args)
            return False
    dlg = wx.DirDialog(
        parent,
        lang.getstr("dialog.set_argyll_bin"),
        defaultPath=os.path.join(*get_verified_path("argyll.dir", path=argyll_dir)),
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
                verbose_print("Setting Argyll binary directory:", path, verbose_level=3)
                setcfg("argyll.dir", path)
                # Always write cfg directly after setting Argyll directory so
                # subprocesses that read the configuration will use the right
                # executables
                writecfg()
                break
            not_found = [
                f" {lang.getstr('or')} ".join(
                    [
                        altname
                        for altname in [
                            altname + EXE_EXT for altname in ARGYLL_ALTNAMES[name]
                        ]
                        if "argyll" not in altname
                    ]
                )
                for name in ARGYLL_NAMES
                if not get_argyll_util(name, [path]) and name not in ARGYLL_OPTIONAL
            ]
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


def check_set_argyll_bin(paths: None | list[str] = None) -> bool:
    """Check if Argyll binaries can be found, otherwise let the user choose.

    Args:
        paths (list[str]): The paths to look for.
    """
    if check_argyll_bin(paths):
        return True
    return set_argyll_bin()


def validate_search_paths(paths: None | list[str] = None) -> list[str]:
    """Validate the paths to look for Argyll utilities.

    Args:
        paths (None | list[str]): The paths to look for.

    Returns:
        list[str]: A list of paths to look for Argyll utilities.
    """
    cfg_argyll_dir = getcfg("argyll.dir")
    if not paths:
        paths = get_path_from_env()
        if argyll_dir := (cfg_argyll_dir or "").rstrip(os.path.sep):
            with contextlib.suppress(ValueError):
                paths.remove(argyll_dir)
            paths = [argyll_dir, *paths]
    return paths


def get_argyll_util(name: str, paths: None | list[str] = None) -> None | str:
    """Find a single Argyll utility. Return the full path.

    Args:
        name (str): The name of the utility.
        paths (None | list[str]): The paths to look for.

    Returns:
        None | str: None if not found or the path of the utility.
    """
    paths = validate_search_paths(paths)
    cache_key = os.pathsep.join(paths)
    if exe := ARGYLL_UTILS.get(cache_key, {}).get(name, None):
        return exe
    verbose_print(
        "Info: Searching for", name, "in", os.pathsep.join(paths), verbose_level=4
    )
    for path in paths:
        for altname in ARGYLL_ALTNAMES.get(name, []):
            if exe := which(f"{altname}{EXE_EXT}", [path]):
                break
        if exe:
            break

    verbose_print(
        *(
            ["Info:", name, "=", exe]
            if exe
            else [
                "Info:",
                "|".join(ARGYLL_ALTNAMES[name]),
                "not found in",
                os.pathsep.join(paths),
            ]
        ),
        verbose_level=4,
    )
    if exe:
        if cache_key not in ARGYLL_UTILS:
            ARGYLL_UTILS[cache_key] = {}
        ARGYLL_UTILS[cache_key][name] = exe
    return exe


def get_argyll_utilname(name: str, paths: None | list[str] = None) -> str:
    """Find a single Argyll utility.

    Args:
        name (str): The name of the utility.
        paths (None | list[str]): The paths to look for.

    Returns:
        str: The basename of the utility without extension, or an empty string
            if not found.
    """
    exe = get_argyll_util(name, paths)
    if exe:
        exe = os.path.basename(os.path.splitext(exe)[0])
    return exe


def get_argyll_version(
    name: str, silent: bool = False, paths: None | list[str] = None
) -> str:
    """Determine version of a certain Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        silent (bool): Silently check Argyll version. Default is False.
        paths (None | list[str]): Paths to look for Argyll executables.

    Returns:
        str: The Argyll utility version.
    """
    argyll_version_string = get_argyll_version_string(name, silent, paths)
    return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(
    name: str, silent: bool = False, paths: None | str = None
) -> str:
    """Return the version of the requested Argyll utility.

    Args:
        name (str): The name of the Argyll utility.
        silent (bool): Silently check Argyll version. Default is False.
        paths (None | str): Paths to look for Argyll executables.

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
            [cmd.encode(FS_ENC), "-?"],
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


def parse_argyll_version_string(argyll_version_string: str) -> list[int | str]:
    """Parse the Argyll version string.

    Args:
        argyll_version_string (str): The version string to parse.

    Returns:
        list[int | str]: A list of version components.
    """
    if isinstance(argyll_version_string, bytes):
        argyll_version_string = argyll_version_string.decode()
    argyll_version = re.findall(r"(\d+|[^.\d]+)", argyll_version_string)
    for i, v in enumerate(argyll_version):
        with contextlib.suppress(ValueError):
            argyll_version[i] = int(v)
    return argyll_version


@cache
def get_argyll_latest_version() -> str:
    """Return the latest ArgyllCMS version from argyllcms.com.

    Returns:
        str: The latest version number. Returns
    """
    argyll_domain = config.DEFAULTS.get("argyll.domain", "")
    try:
        changelog = re.search(
            r"(?<=Version ).{5}",
            urllib.request.urlopen(f"{argyll_domain}/log.txt")  # noqa: S310
            .read(100)
            .decode("utf-8"),
        )
    except urllib.error.URLError:
        # no internet connection
        # return the default version
        return config.DEFAULTS.get("argyll.version")
    result = changelog.group()
    print(f"Latest ArgyllCMS version: {result} (from {argyll_domain}/log.txt)")
    if not result:
        # no version found
        return config.DEFAULTS.get("argyll.version")
    return result


@overload
def make_argyll_compatible_path(path: bytes) -> bytes: ...


@overload
def make_argyll_compatible_path(path: str) -> str: ...


def make_argyll_compatible_path(path):
    """Make the path compatible with the Argyll utilities.

    This is currently only effective under Windows to make sure that any
    unicode 'division' slashes in the profile name are replaced with
    underscores.

    Args:
        path (bytes | str): The path to be made compatible.

    Returns:
        bytes | str: The compatible path.
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


def get_argyll_instrument_config(what: None | str = None) -> list[str]:
    """Check for Argyll CMS udev rules/hotplug scripts.

    Args:
        what (str): The type of files to look for. Can be "installed",
            "expected", or None.

    Returns:
        list[str]: A list of file paths that match the criteria.
    """
    filenames = []
    if what == "installed":
        argyll_rule_filepaths = (
            "/etc/udev/rules.d/55-Argyll.rules",
            "/etc/udev/rules.d/45-Argyll.rules",
            "/etc/hotplug/Argyll",
            "/etc/hotplug/Argyll.usermap",
            "/lib/udev/rules.d/55-Argyll.rules",
            "/lib/udev/rules.d/69-cd-sensors.rules",
        )
        filenames = [
            filename for filename in argyll_rule_filepaths if os.path.isfile(filename)
        ]
    else:
        if what == "expected":

            def fn(filename: bytes | str) -> bytes | str:
                """Return the full path to the Argyll utility."""
                return filename
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
        elif os.path.isdir("/etc/hotplug"):
            # USB using hotplug and Serial using udev
            # (older versions of Linux)
            filenames.extend(
                fn(filename) for filename in ("usb/Argyll", "usb/Argyll.usermap")
            )
    return [filename for filename in filenames if filename]
