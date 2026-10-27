"""This script is used by the py2exe to freeze the library into executables."""

from __future__ import annotations

import ctypes.util
import functools
import os
import platform
import shutil
import sys
from configparser import ConfigParser
from fnmatch import fnmatch
from sysconfig import get_platform
from time import strftime

from py2exe import freeze

pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)
source_dir = os.path.dirname(pydir)

print(f"pydir     : {pydir}")
print(f"source_dir: {source_dir}")
sys.path.append(source_dir)


from DisplayCAL.meta import (
    APPSTREAM_ID,
    AUTHOR,
    NAME,
    VERSION_STRING,
    VERSION_TUPLE,
    script2pywname,
)
from DisplayCAL.util_os import getenvu, safe_glob
from DisplayCAL.util_str import safe_str

appname = NAME


if sys.platform in ("darwin", "win32"):
    # Adjust PATH so ctypes.util.find_library can find SDL2 DLLs (if present)
    pth = getenvu("PATH")
    libpth = os.path.join(pydir, "lib")
    if not pth.startswith(libpth + os.pathsep):
        pth = libpth + os.pathsep + pth
        os.environ["PATH"] = safe_str(pth)


config = {
    "data": ["tests/data/icc/*.icc"],
    "doc": [
        "CHANGELOG.md",
        "CHANGELOG-legacy.html",
        "LICENSE.txt",
        "README.html",
        "README-fr.html",
        "screenshots/*.png",
        "theme/*.png",
        "theme/*.css",
        "theme/*.js",
        "theme/*.svg",
        "theme/icons/favicon.ico",
        "theme/slimbox2/*.css",
        "theme/slimbox2/*.js",
    ],
    # Excludes for .app/.exe builds
    # numpy.lib.utils imports pydoc, which imports Tkinter, but
    # numpy.lib.utils is not even used by DisplayCAL, so omit all
    # Tk stuff
    # Use pyglet with OpenAL as audio backend. pyglet 2.x media import paths
    # pull in additional submodules dynamically, so don't exclude pyglet.*
    "excludes": {
        "all": [
            "Tkconstants",
            "Tkinter",
            "pygame",
            "pyo",
            "setuptools",
            "tcl",
            "test",
            "yaml",
            "zeroconf",
        ],
        "darwin": ["gdbm"],
        "win32": ["gi", "win32com.client.genpy"],
    },
    "package_data": {
        NAME: [
            "beep.wav",
            "camera_shutter.wav",
            "ColorLookupTable.fx",
            "lang/*.yaml",
            "linear.cal",
            "pnp.ids",
            "presets/*.icc",
            "quirk.json",
            "ref/*.cie",
            "ref/*.gam",
            "ref/*.icm",
            "ref/*.ti1",
            "report/*.css",
            "report/*.html",
            "report/*.js",
            "test.cal",
            "theme/*.png",
            "theme/*.wav",
            "theme/icons/10x10/*.png",
            "theme/icons/16x16/*.png",
            "theme/icons/32x32/*.png",
            "theme/icons/48x48/*.png",
            "theme/icons/72x72/*.png",
            "theme/icons/128x128/*.png",
            "theme/icons/256x256/*.png",
            "theme/icons/512x512/*.png",
            "theme/jet_anim/*.png",
            "theme/patch_anim/*.png",
            "theme/splash_anim/*.png",
            "theme/shutter_anim/*.png",
            "ti1/*.ti1",
            "x3d-viewer/*.css",
            "x3d-viewer/*.html",
            "x3d-viewer/*.js",
            "xrc/*.xrc",
            "VERSION",
        ]
    },
    "xtra_package_data": {NAME: {"win32": [f"theme/icons/{NAME}-uninstall.ico"]}},
}


msiversion = ".".join(
    (
        str(VERSION_TUPLE[0]),
        str(VERSION_TUPLE[1]),
        str(VERSION_TUPLE[2]),
    )
)


class Target:
    """Target class for py2exe."""

    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


def get_data(
    tgt_dir: str,
    key: str,
    pkgname: None | str = None,
    subkey: None | str = None,
    excludes: None | list[str] = None,
) -> list[tuple[str, list[str]]]:
    """Return configured data files.

    Args:
        tgt_dir (str): Target directory where the files should be placed.
        key (str): Key in the config dictionary to retrieve the file paths.
        pkgname (None | str, optional): Package name to filter the files.
            Default is None.
        subkey (None | str, optional): Subkey to further filter the files.
            Default is None.
        excludes (None | list[str], optional): List of patterns to exclude
            files. Default is None.

    Returns:
        list[tuple[str, list[str]]]: List of tuples where each tuple contains
            the target directory and a list of file paths that match the
            specified key and package name.
    """
    files = config[key]
    src_dir = source_dir
    resource_dir = src_dir
    if pkgname:
        files = files[pkgname]
        resource_dir = os.path.join(src_dir, pkgname)
        if subkey:
            files = files.get(subkey, [])
    data = []
    for pth in files:
        if not [exclude for exclude in excludes or [] if fnmatch(pth, exclude)]:
            normalized_path = os.path.normpath(
                os.path.join(tgt_dir, os.path.dirname(pth))
            )
            safe_path = [
                os.path.relpath(p, src_dir)
                for p in safe_glob(os.path.join(resource_dir, pth))
            ]
            data.append((normalized_path, safe_path))
    return data


def sort_by_name(a: str, b: str) -> int:
    """Compare two script names for sorting.

    Args:
        a (str): First script name.
        b (str): Second script name.

    Returns:
        int: -1 if a < b, 1 if a > b, 0 if a == b.
    """
    a, b = [os.path.splitext(v)[0] for v in (a, b)]
    if a > b:
        return 1
    if a < b:
        return -1
    return 0


def get_scripts(excludes: None | list[str] = None) -> list[tuple[str, str]]:
    """Return a list of scripts with their descriptions.

    Args:
        excludes (None | list[str]): List of scripts to exclude. Default is
            None.

    Returns:
        list[tuple[str, str]]: List of tuples containing script names and their
            descriptions.
    """
    # It is required that each script has an accompanying .desktop file
    scripts_with_desc = []
    scripts = safe_glob(os.path.join(pydir, "..", "scripts", appname.lower() + "*"))

    scripts = sorted(scripts, key=functools.cmp_to_key(sort_by_name))
    for script in scripts:
        script = os.path.basename(script)
        if script == appname.lower() + "-apply-profiles-launcher":
            continue
        desktop_file = os.path.join(pydir, "..", "misc", f"{script}.desktop")
        if os.path.isfile(desktop_file):
            cfg = ConfigParser()
            cfg.read(desktop_file)
            script = cfg.get("Desktop Entry", "Exec").split()[0]
            desc = cfg.get("Desktop Entry", "Name")
        else:
            desc = ""
        if not [exclude for exclude in excludes or [] if fnmatch(script, exclude)]:
            scripts_with_desc.append((script, desc))
    return scripts_with_desc


def copy_qt_plugins(dist_dir: str) -> None:
    """Copy PySide6's Qt plugin binaries into the frozen dist_dir.

    Unlike py2app (which ships a "pyside6" recipe for exactly this), py2exe
    has no Qt-aware hook: its dependency analysis only follows Python import
    statements, so the plugin binaries QApplication discovers by scanning a
    "plugins" directory at runtime (e.g. platforms/qwindows.dll, without
    which Qt can't even start) are never picked up and would otherwise be
    silently missing from the frozen build.

    Args:
        dist_dir (str): The py2exe frozen output directory.
    """
    try:
        from PySide6 import QtCore
    except ImportError:
        print("WARNING: PySide6 not found, Qt UI plugins will not be bundled!")
        return

    plugin_dir = QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.PluginsPath)
    for subdir in ("platforms", "styles", "imageformats", "iconengines"):
        src = os.path.join(plugin_dir, subdir)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(dist_dir, "PySide6", "plugins", subdir)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"Copied Qt plugin dir: {src} -> {dst}")

    # Qt looks for qt.conf next to the running executable and, if found,
    # resolves plugin paths relative to it. This decouples plugin discovery
    # from wherever py2exe actually ends up extracting PySide6's own DLLs
    # (bundle_files=3 doesn't preserve site-packages' package layout), rather
    # than relying on Qt's default "plugins/ next to Qt6Core.dll" heuristic.
    qt_conf_path = os.path.join(dist_dir, "qt.conf")
    with open(qt_conf_path, "w", encoding="utf-8") as qt_conf:
        qt_conf.write("[Paths]\nPlugins = PySide6/plugins\n")
    print(f"Wrote {qt_conf_path}")


def _collect_data_files(
    use_sdl: bool, doc: str, data: str
) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]]]:
    """Collect the script list and data files for the frozen build.

    Args:
        use_sdl (bool): Whether to bundle SDL2 audio DLLs.
        doc (str): Target directory for doc/appdata files.
        data (str): Target directory for package/data files.

    Returns:
        tuple[list[tuple[str, str]], list[tuple[str, list[str]]]]: The
            scripts list (as returned by get_scripts()), and the data_files
            list understood by py2exe.freeze().
    """
    # Use CA file from certifi project
    import certifi

    if cacert := certifi.where():
        shutil.copyfile(cacert, os.path.join(pydir, "cacert.pem"))
        config["package_data"][NAME].append("cacert.pem")
    else:
        print("WARNING: cacert.pem from certifi project not found!")

    scripts = get_scripts()
    # Doc files
    data_files = []
    data_files += get_data(doc, "doc", excludes=["LICENSE.txt"])
    if data_files:
        data_files.append(
            (
                doc,
                [os.path.relpath(os.path.join(pydir, "..", "LICENSE.txt"), source_dir)],
            )
        )
    # metainfo / appdata.xml
    data_files.append(
        (
            os.path.join(os.path.dirname(data), "metainfo"),
            [
                os.path.relpath(
                    os.path.normpath(
                        os.path.join(pydir, "..", "dist", f"{APPSTREAM_ID}.appdata.xml")
                    ),
                    source_dir,
                )
            ],
        )
    )
    data_files += get_data(data, "package_data", NAME, excludes=["theme/icons/*"])
    data_files += get_data(data, "data")
    data_files += get_data(data, "xtra_package_data", NAME, sys.platform)

    # Add python and pythonw
    data_files.extend(
        [
            (
                os.path.join(data, "lib"),
                [
                    sys.executable,
                    os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
                ],
            )
        ]
    )
    if use_sdl:
        # SDL DLLs for audio module
        sdl2 = ctypes.util.find_library("SDL2")
        sdl2_mixer = ctypes.util.find_library("SDL2_mixer")
        if sdl2:
            sdl2_libs = [sdl2]
            if sdl2_mixer:
                sdl2_libs.append(sdl2_mixer)
                data_files.append((os.path.join(data, "lib"), sdl2_libs))
                config["excludes"]["all"].append("pyglet")
            else:
                print("WARNING: SDL2_mixer not found!")
        else:
            print("WARNING: SDL2 not found!")
    if "pyglet" not in config["excludes"]["all"]:
        # OpenAL DLLs for pyglet
        openal32 = ctypes.util.find_library("OpenAL32.dll")
        wrap_oal = ctypes.util.find_library("wrap_oal.dll")
        if openal32:
            oal = [openal32]
            if wrap_oal:
                oal.append(wrap_oal)
            else:
                print("WARNING: wrap_oal.dll not found!")
            data_files.append((data, oal))
        else:
            print("WARNING: OpenAL32.dll not found!")

    for dname in (
        "10x10",
        "16x16",
        "22x22",
        "24x24",
        "32x32",
        "48x48",
        "64x64",
        "72x72",
        "128x128",
        "256x256",
        "512x512",
    ):
        # Get all the icons needed, depending on platform
        # Only the icon sizes 10, 16, 32, 72, 256 and 512 include icons
        # that are used exclusively for UI elements.
        # These should be installed in an app-specific location, e.g.
        # under Linux $XDG_DATA_DIRS/DisplayCAL/theme/icons/
        # The app icon sizes 16, 32, 48 and 256 (128 under Mac OS X),
        # which are used for taskbar icons and the like, as well as the
        # other sizes can be installed in a generic location, e.g.
        # under Linux $XDG_DATA_DIRS/icons/hicolor/<size>/apps/
        # Generally, icon filenames starting with the lowercase app name
        # should be installed in the generic location.
        icons = []
        desktopicons = []
        if sys.platform == "darwin":
            largest_iconbundle_icon_size = "128x128"
        else:
            largest_iconbundle_icon_size = "256x256"
        for iconpath in safe_glob(
            os.path.join(pydir, "theme", "icons", dname, "*.png")
        ):
            if not os.path.basename(iconpath).startswith(NAME.lower()) or (
                sys.platform in ("darwin", "win32")
                and dname in ("16x16", "32x32", "48x48", largest_iconbundle_icon_size)
            ):
                # In addition to UI element icons, we also need all the app
                # icons we use in get_icon_bundle under macOS/Windows,
                # otherwise they wouldn't be included (under Linux, these
                # are included for installation to the system-wide icon
                # theme location instead)
                icons.append(iconpath)
            elif sys.platform not in ("darwin", "win32"):
                desktopicons.append(iconpath)
        if icons:
            data_files.append((os.path.join(data, "theme", "icons", dname), icons))
        if desktopicons:
            data_files.append(
                (
                    os.path.join(
                        os.path.dirname(data), "icons", "hicolor", dname, "apps"
                    ),
                    desktopicons,
                )
            )
    return scripts, data_files


def _build_targets(
    scripts: list[tuple[str, str]],
) -> tuple[list[Target], list[Target]]:
    """Build the py2exe ``windows``/``console`` Target lists.

    Args:
        scripts (list[tuple[str, str]]): Script names and descriptions, as
            returned by get_scripts().

    Returns:
        tuple[list[Target], list[Target]]: The windows and console Target
            lists understood by py2exe.freeze().
    """
    from winmanifest_util import getmanifestxml

    arch = "amd64" if platform.architecture()[0] == "64bit" else "x86"
    manifest_xml = getmanifestxml(
        os.path.join(
            pydir,
            "..",
            "misc",
            NAME
            + (
                f".exe.{arch}.VC90.manifest"
                if hasattr(sys, "version_info") and sys.version_info[:2] >= (3, 8)
                else ".exe.manifest"
            ),
        )
    )
    tmp_scripts_dir = os.path.join(source_dir, "build", "temp.scripts")
    if not os.path.isdir(tmp_scripts_dir):
        os.makedirs(tmp_scripts_dir)
    apply_profiles_launcher = (
        f"{appname.lower()}-apply-profiles-launcher",
        f"{appname} Profile Loader Launcher",
    )
    for script, _desc in [*scripts, apply_profiles_launcher]:
        shutil.copy(
            os.path.join(source_dir, "scripts", script),
            os.path.join(tmp_scripts_dir, script2pywname(script)),
        )
    windows = [
        Target(
            script=os.path.join(tmp_scripts_dir, script2pywname(script)),
            icon_resources=[
                (
                    1,
                    os.path.join(
                        pydir,
                        "theme",
                        "icons",
                        os.path.splitext(os.path.basename(script))[0] + ".ico",
                    ),
                )
            ],
            other_resources=[(24, 1, manifest_xml)],
            copyright="© {} {}".format(strftime("%Y"), AUTHOR),
            description=desc,
        )
        for script, desc in [
            script_desc1
            for script_desc1 in scripts
            if script_desc1[0] != appname.lower() + "-eecolor-to-madvr-converter"
            and not script_desc1[0].endswith("-console")
        ]
    ]

    # Add profile loader launcher
    windows.append(
        Target(
            script=os.path.join(
                tmp_scripts_dir, script2pywname(apply_profiles_launcher[0])
            ),
            icon_resources=[
                (
                    1,
                    os.path.join(
                        pydir,
                        "theme",
                        "icons",
                        appname + "-apply-profiles" + ".ico",
                    ),
                )
            ],
            other_resources=[(24, 1, manifest_xml)],
            copyright="© {} {}".format(strftime("%Y"), AUTHOR),
            description=apply_profiles_launcher[1],
        )
    )

    # Programs that can run with and without GUI
    console_scripts = [f"{NAME}-VRML-to-X3D-converter"]  # No "-console" suffix!
    for console_script in console_scripts:
        console_script_path = os.path.join(tmp_scripts_dir, console_script + "-console")
        if not os.path.isfile(console_script_path):
            shutil.copy(
                os.path.join(
                    source_dir, "scripts", console_script.lower() + "-console"
                ),
                console_script_path,
            )
    console = [
        Target(
            script=os.path.join(tmp_scripts_dir, script2pywname(script) + "-console"),
            icon_resources=[
                (
                    1,
                    os.path.join(
                        pydir,
                        "theme",
                        "icons",
                        os.path.splitext(os.path.basename(script))[0] + ".ico",
                    ),
                )
            ],
            other_resources=[(24, 1, manifest_xml)],
            copyright="© {} {}".format(strftime("%Y"), AUTHOR),
            description=desc,
        )
        for script, desc in [
            script_desc2
            for script_desc2 in scripts
            if script2pywname(script_desc2[0]) in console_scripts
        ]
    ]

    # Programs without GUI
    console.append(
        Target(
            script=os.path.join(
                tmp_scripts_dir, appname + "-eeColor-to-madVR-converter"
            ),
            icon_resources=[
                (
                    1,
                    os.path.join(pydir, "theme", "icons", appname + "-3DLUT-maker.ico"),
                )
            ],
            other_resources=[(24, 1, manifest_xml)],
            copyright="© {} {}".format(strftime("%Y"), AUTHOR),
            description="Convert eeColor 65^3 to madVR 256^3 3D LUT "
            "(video levels in, video levels out)",
        )
    )

    return windows, console


def _build_py2exe_options(dist_dir: str, debug: bool) -> dict:
    """Build the ``options`` dict passed to py2exe.freeze().

    Args:
        dist_dir (str): The py2exe frozen output directory.
        debug (bool): Whether to build with debug-friendly py2exe options.

    Returns:
        dict: The ``options`` dict understood by py2exe.freeze().
    """
    options = {
        "py2exe": {
            "dist_dir": dist_dir,
            "dll_excludes": [
                "iertutil.dll",
                "MPR.dll",
                "msvcm90.dll",
                "msvcp90.dll",
                "msvcr90.dll",
                "mswsock.dll",
                "urlmon.dll",
                "w9xpopen.exe",
                "gdiplus.dll",
                "mfc90.dll",
            ],
            "excludes": config["excludes"]["all"] + config["excludes"]["win32"],
            # Force whole-package inclusion for the Qt UI stack: it's only
            # reached via a runtime `if get_ui_toolkit() == "qt":` branch, and
            # while py2exe's static import analysis does still discover it
            # through that branch, this guards against any submodule pulled
            # in dynamically at runtime rather than via a literal import.
            "packages": ["PySide6", "shiboken6", "qtpy", f"{NAME}.ui"],
            "bundle_files": 3,  # if wx.VERSION >= (2, 8, 10, 1) else 1,
            "compressed": 1,
            "optimize": 0,  # 0 = don't optimize (generate .pyc)
            # 1 = normal optimization (like python -O)
            # 2 = extra optimization (like python -OO)
        }
    }
    if debug:
        options["py2exe"].update(
            {"bundle_files": 3, "compressed": 0, "optimize": 0, "skip_archive": 1}
        )
    return options


def build_py2exe() -> None:
    """py2exe builder that uses the new freeze API."""
    use_sdl = False
    sys.path.insert(1, os.path.join(pydir, "..", "util"))

    debug = False
    # do_full_install = False

    doc = "."
    data = "."

    scripts, data_files = _collect_data_files(use_sdl, doc, data)
    # `attrs` only carries the fields py2exe_kwargs (further below) actually
    # reads: name/version/classifiers/description/license/entry_points/
    # package_data/etc. all live in pyproject.toml's `[project]` table (see
    # DisplayCAL/_setup.py's own `attrs`), and were never passed to a real
    # setup() call from here to begin with.
    attrs = {
        "data_files": data_files,
    }

    attrs["windows"], attrs["console"] = _build_targets(scripts)

    dist_dir = os.path.join(
        pydir,
        "..",
        "dist",
        f"py2exe.{get_platform()}-py{sys.version_info[0]}.{sys.version_info[1]}",
        f"{NAME}-{VERSION_STRING}",
    )
    os.makedirs(dist_dir, exist_ok=True)
    attrs["options"] = _build_py2exe_options(dist_dir, debug)
    attrs["zipfile"] = os.path.join("lib", "library.zip")

    py2exe_kwargs = {
        "console": attrs["console"],
        "windows": attrs["windows"],
        "data_files": attrs["data_files"],
        "zipfile": attrs["zipfile"],
        "options": attrs["options"],
    }

    print("Running py2exe.freeze!")
    freeze(**py2exe_kwargs)
    # setup(**attrs)
    print("py2exe.freeze DONE!")

    copy_qt_plugins(dist_dir)

    shutil.copy(
        os.path.join(dist_dir, f"python{sys.version_info[0]}{sys.version_info[1]}.dll"),
        os.path.join(
            dist_dir, "lib", f"python{sys.version_info[0]}{sys.version_info[1]}.dll"
        ),
    )

    from vc90crt import vc90crt_copy_files

    vc90crt_copy_files(dist_dir)
    vc90crt_copy_files(os.path.join(dist_dir, "lib"))


if __name__ == "__main__":
    build_py2exe()
