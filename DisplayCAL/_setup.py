"""DisplayCAL _setup.py script.

Can be used with setuptools or pure distutils (the latter can be forced
with the --use-distutils option, otherwise it will try to use setuptools
by default).

Also supported in addition to standard distutils/setuptools commands is
the py2app command (if the appropriate package is installed), which
makes this file your all-around building/bundling powerhouse for
DisplayCAL on macOS. Please note that py2app *requires* setuptools.
Windows executables are built via `DisplayCAL/freeze.py` (py2exe)
instead.

IMPORTANT NOTE:
If called from within the installed package, should only be used to
uninstall (_setup.py uninstall --record=INSTALLED_FILES). Otherwise, a
plain `pip install .`/`python -m build` in the root directory of the
source tar.gz/zip already routes here through the thin root `setup.py`;
for native-packaging/freeze commands (py2app, inno, ...) use
`native_build.py` there instead.

"""

# Standard Library Imports
from __future__ import annotations

import ctypes.util
import distutils.core
import functools
import os
import platform
import re
import shutil
import sys
from configparser import ConfigParser
from distutils.command.install import install
from distutils.util import change_root, get_platform
from fnmatch import fnmatch
from time import strftime
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from modulegraph.modulegraph import Package


# Borrowed from setuptools
def _find_all_simple(path: str) -> list[str]:
    """Find all files under 'path'.

    Returns:
        list[str]: A list of all file paths found under 'path'.
    """
    results = (
        os.path.join(base, file)
        for base, dirs, files in os.walk(path, followlinks=True)
        for file in files
    )
    return list(filter(os.path.isfile, results))


def findall(directory: str = os.curdir) -> list[str]:
    """Find all files under 'dir' and return the list of full filenames.

    Unless dir is '.', return full filenames with dir prepended.

    Args:
        directory (str): The directory to search. Default is os.curdir.
    """
    files = _find_all_simple(directory)
    if directory == os.curdir:
        make_rel = functools.partial(os.path.relpath, start=directory)
        files = map(make_rel, files)
    return list(files)


import distutils.filelist

distutils.filelist.findall = findall  # Fix findall bug in distutils


from DisplayCAL.defaultpaths import AUTOSTART, AUTOSTART_HOME
from DisplayCAL.meta import (
    APPSTREAM_ID,
    AUTHOR,
    AUTHOR_ASCII,
    AUTHOR_EMAIL,
    DEVELOPMENT_HOME_PAGE,
    DOMAIN,
    NAME,
    PY_MAXVERSION,
    PY_MINVERSION,
    VERSION_STRING,
    VERSION_TUPLE,
    WX_MINVERSION,
    script2pywname,
)
from DisplayCAL.util_os import getenvu, safe_glob
from DisplayCAL.util_str import safe_str

appname = NAME

bits = platform.architecture()[0][:2]
pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)
source_dir = os.path.dirname(pydir)


if sys.platform in ("darwin", "win32"):
    # Adjust PATH so ctypes.util.find_library can find SDL2 DLLs (if present)
    pth = getenvu("PATH")
    libpth = os.path.join(pydir, "lib")
    if not pth.startswith(libpth + os.pathsep):
        pth = libpth + os.pathsep + pth
        os.environ["PATH"] = safe_str(pth)

config = {
    "data": ["tests/*.icc"],
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
            "theme/icons/flags/*.png",
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

plist_dict = {
    "CFBundleDevelopmentRegion": "English",
    "CFBundleExecutable": NAME,
    "CFBundleGetInfoString": VERSION_STRING,
    "CFBundleIdentifier": ".".join(reversed(DOMAIN.split("."))) + "." + NAME,
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleLongVersionString": VERSION_STRING,
    "CFBundleName": NAME,
    "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": VERSION_STRING,
    "CFBundleSignature": "????",
    "CFBundleVersion": ".".join(map(str, VERSION_TUPLE)),
    "NSHumanReadableCopyright": f"© {strftime('%Y')} {AUTHOR}",
    "LSMinimumSystemVersion": "11.0",  # Required for native ARM64 support
    "com.apple.security.cs.disable-library-validation": True,  # Critical fix
    "com.apple.security.cs.allow-unsigned-executable-memory": True,
}


def create_app_symlinks(dist_dir: str, scripts: list[tuple[str, str]]) -> None:
    """Create symlinks for the app bundle and standalone tools.

    Args:
        dist_dir (str): The distribution directory.
        scripts (list[tuple[str, str]]): List of tuples containing script names
            and their descriptions.
    """
    main_contents_rel = os.path.join(f"{NAME}.app", "Contents")
    # Create ref, ReadMe and license symlinks in directory
    # containing the app bundle
    for src, tgt in [
        ("ref", "Reference"),
        ("CHANGELOG.md", "CHANGELOG.md"),
        ("README.html", "README.html"),
        ("README-fr.html", "README-fr.html"),
        ("LICENSE.txt", "LICENSE.txt"),
    ]:
        tgt = os.path.join(dist_dir, tgt)
        if os.path.islink(tgt):
            os.unlink(tgt)
        os.symlink(os.path.join(main_contents_rel, "Resources", src), tgt)
    # Create standalone tools app bundles by symlinking to the main bundle
    scripts = [(script2pywname(script), desc) for script, desc in scripts]
    tool_scripts = [
        script for script in [script for script, desc in scripts] if script != NAME
    ]
    for script, desc in scripts:
        if script in (
            NAME,
            f"{NAME}-apply-profiles",
            f"{NAME}-eeColor-to-madVR-converter",
        ) or script.endswith("-console"):
            continue
        tool_name = desc.replace(NAME, "").strip()
        tool_app = os.path.join(dist_dir, f"{tool_name}.app")
        if os.path.isdir(tool_app):
            if (
                input(
                    f'WARNING: The output directory "{tool_app}" and ALL ITS '
                    "CONTENTS will be REMOVED! Continue? (y/n)"
                ).lower()
                == "y"
            ):
                print("Removing dir", tool_app)
                shutil.rmtree(tool_app)
            else:
                raise SystemExit("User aborted")
        tool_script = os.path.join(dist_dir, main_contents_rel, "MacOS", script)
        has_tool_script = os.path.exists(tool_script)
        tool_contents = os.path.join(tool_app, "Contents")
        os.makedirs(tool_contents)
        # Always include MacOS so the tool binary lives inside the tool app's
        # own bundle — py2app resolves Resources relative to the executable's
        # physical location, so placing it in the main app's MacOS would make
        # it load the main app's Resources instead of the tool's.
        subdirs = ["Frameworks", "Resources", "MacOS"]
        for entry in os.listdir(os.path.join(dist_dir, main_contents_rel)):
            if entry in subdirs:
                os.makedirs(os.path.join(tool_contents, entry))
                for subentry in os.listdir(
                    os.path.join(dist_dir, main_contents_rel, entry)
                ):
                    src = os.path.join(dist_dir, main_contents_rel, entry, subentry)
                    tgt = os.path.join(tool_contents, entry, subentry)
                    if subentry == "main.py":
                        # py2app
                        with open(src) as main_in:
                            py = main_in.read()
                        py = py.replace("main()", f"main({script[len(NAME) + 1 :]!r})")
                        with open(tgt, "wb") as main_out:
                            main_out.write(py.encode())
                        continue
                    if subentry in ("__boot__.py", "site.py", "site.pyc"):
                        shutil.copy(src, tgt)
                        continue
                    if subentry == f"{NAME}.icns":
                        shutil.copy(
                            os.path.join(pydir, "theme", "icons", f"{script}.icns"),
                            os.path.join(tool_contents, entry, f"{script}.icns"),
                        )
                        continue
                    if (
                        entry == "MacOS"
                        and not has_tool_script
                        and subentry != appname
                        and not os.path.islink(src)
                    ):
                        # py2app: the bundled Python interpreter in
                        # Contents/MacOS (named "python") must be a real file,
                        # not a symlink. The py2app launcher only sets
                        # PYTHONHOME to the bundle's Resources when
                        # Contents/MacOS/python is NOT a symlink (see lstat /
                        # S_IFLNK check in py2app's main.c). A symlinked
                        # interpreter makes the tool app fall back to the system
                        # Python framework and fail to find its stdlib
                        # ("No module named 'encodings'").
                        shutil.copy(src, tgt)
                    elif subentry not in tool_scripts:
                        os.symlink(
                            os.path.join(
                                "..", "..", "..", main_contents_rel, entry, subentry
                            ),
                            tgt,
                        )
                if entry == "MacOS" and not has_tool_script:
                    # py2app: the main app only has one launcher binary (appname).
                    # Copy it into the tool app's own MacOS directory under the
                    # tool's name so py2app resolves Resources from the tool app's
                    # bundle, not the main app's.
                    shutil.copy(
                        os.path.join(dist_dir, main_contents_rel, "MacOS", appname),
                        os.path.join(tool_contents, "MacOS", script),
                    )
            elif entry == "Info.plist":
                with open(
                    os.path.join(dist_dir, main_contents_rel, entry),
                    encoding="utf-8",
                ) as info_in:
                    info_xml = info_in.read()
                # TODO: use an XML library to manipulate the data!
                # CFBundleName / CFBundleDisplayName
                info_xml = re.sub(
                    rf"(Name</key>\s*<string>){NAME}",
                    lambda match, toolname=tool_name: match.group(1) + toolname,
                    info_xml,
                )
                # CFBundleIdentifier
                info_xml = info_xml.replace(f".{NAME}</string>", f".{script}</string>")
                # CFBundleIconFile
                info_xml = info_xml.replace(
                    f"{NAME}.icns</string>", f"{script}.icns</string>"
                )
                # CFBundleExecutable
                info_xml = re.sub(
                    rf"(Executable</key>\s*<string>){NAME}",
                    lambda match, script=script: match.group(1) + script,
                    info_xml,
                )
                with open(
                    os.path.join(tool_contents, entry), "w", encoding="utf-8"
                ) as info_out:
                    info_out.write(info_xml)
            else:
                os.symlink(
                    os.path.join("..", "..", main_contents_rel, entry),
                    os.path.join(tool_contents, entry),
                )


def get_data(
    tgt_dir: str,
    key: str,
    pkgname: None | str = None,
    subkey: None | str = None,
    excludes: None | list[str] = None,
) -> list[tuple[str, list[str]]]:
    """Return configured data files.

    Args:
        tgt_dir (str): The target directory.
        key (str): The config key.
        pkgname (None | str): Name of the package. Default is None.
        subkey (None | str): Name of the subkey. Default is None.
        excludes (None | list[str]): List of files to exclude. Default is None.

    Returns:
        list[tuple[str, list[str]]]: A list of tuples which contains the
            normalized path of the data files and the list of paths of the
            data files.
    """
    files = config[key]
    src_dir = source_dir
    if pkgname:
        files = files[pkgname]
        # modifying the src_dir is not working with py2app, so disabling it.
        # src_dir = os.path.join(src_dir, pkgname)
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
                for p in safe_glob(os.path.join(src_dir, pth))
            ]
            if pkgname:
                # try looking for the "{src_dir}/{pkgname}/{pth}" too
                safe_path += [
                    os.path.relpath(p, src_dir)
                    for p in safe_glob(os.path.join(src_dir, pkgname, pth))
                ]
            data.append((normalized_path, safe_path))
    return data


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
    scripts = safe_glob(os.path.join(pydir, "..", "scripts", f"{appname.lower()}*"))

    def sortbyname(a: str, b: str) -> int:
        """Sort two script names by their base names."""
        a, b = [os.path.splitext(v)[0] for v in (a, b)]
        if a > b:
            return 1
        if a < b:
            return -1
        return 0

    import functools

    scripts = sorted(scripts, key=functools.cmp_to_key(sortbyname))
    for script in scripts:
        script = os.path.basename(script)
        if script == f"{appname.lower()}-apply-profiles-launcher":
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


def _collect_data_files(
    do_py2app: bool,
    sdist: bool,
    doc_layout: str,
    install_data: str | None,
    is_rpm_build: bool,
    skip_instrument_conf_files: bool,
    prefix: str,
    use_sdl: bool,
) -> tuple[str, str, dict, list[tuple[str, str]], list]:
    """Resolve the doc/data install paths and assemble package_data/scripts/data_files.

    Returns:
        tuple[str, str, dict, list[tuple[str, str]], list]: The ``doc`` and
            ``data`` install paths, the ``package_data`` dict, the ``scripts``
            list, and the ``data_files`` list.
    """
    if sys.platform in ("darwin", "win32") or "bdist_egg" in sys.argv[1:]:
        doc = data = "." if do_py2app else NAME
    else:
        # Linux/Unix
        data = NAME
        if doc_layout.startswith("deb"):
            doc = os.path.join("doc", NAME.lower())
        elif "suse" in doc_layout:
            doc = os.path.join("doc", "packages", NAME)
        else:
            doc = os.path.join("doc", f"{NAME}-{VERSION_STRING}")

        if not install_data:
            data = os.path.join("share", data)
            doc = os.path.join("share", doc)
            if is_rpm_build:
                doc = os.path.join(os.path.sep, "usr", doc)

    # Use CA file from certifi project
    if do_py2app:
        import certifi

        cacert = certifi.where()
        if cacert:
            shutil.copyfile(cacert, os.path.join(pydir, "cacert.pem"))
            config["package_data"][NAME].append("cacert.pem")
        else:
            print("WARNING: cacert.pem from certifi project not found!")

    # on Mac OS X and Windows, we want data files in the package dir
    package_data = {
        NAME: (
            config["package_data"][NAME]
            if sys.platform in ("darwin", "win32") and not do_py2app
            else []
        )
    }
    if sdist and sys.platform in ("darwin", "win32"):
        package_data[NAME].extend(
            ["theme/icons/22x22/*.png", "theme/icons/24x24/*.png"]
        )
    if sys.platform == "win32":
        package_data[NAME].append("theme/icons/*.ico")
    # Scripts
    if sys.platform == "darwin":
        scripts = get_scripts(excludes=[appname.lower() + "-apply-profiles"])
    else:
        scripts = get_scripts()
    # Doc files
    data_files = []
    if not is_rpm_build or doc_layout.startswith("deb"):
        data_files += get_data(doc, "doc", excludes=["LICENSE.txt"])
    if data_files:
        data_files.append((doc, [os.path.join(pydir, "..", "dist", "copyright")]))
        data_files.append(
            (
                os.path.join(os.path.dirname(data), "doc-base"),
                [os.path.join(pydir, "..", "misc", appname.lower() + "-readme")],
            )
        )
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

    if sys.platform not in ("darwin", "win32") or do_py2app:
        # Linux/Unix or py2app
        data_files += get_data(data, "package_data", NAME, excludes=["theme/icons/*"])
        data_files += get_data(data, "data")
        data_files += get_data(data, "xtra_package_data", NAME, sys.platform)
        if sys.platform == "win32":
            # Add python and pythonw
            data_files.extend(
                [
                    (
                        os.path.join(data, "lib"),
                        [
                            sys.executable,
                            os.path.join(
                                os.path.dirname(sys.executable), "pythonw.exe"
                            ),
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
        elif sys.platform != "darwin":
            # Linux
            data_files.append(
                (
                    os.path.join(os.path.dirname(data), "applications"),
                    [
                        os.path.join(pydir, "..", "misc", f"{NAME.lower()}.desktop"),
                        *safe_glob(
                            os.path.join(
                                pydir, "..", "misc", f"{NAME.lower()}-*.desktop"
                            )
                        ),
                    ],
                )
            )
            data_files.append(
                (
                    (
                        AUTOSTART
                        if os.geteuid() == 0 or prefix.startswith("/")
                        else AUTOSTART_HOME
                    ),
                    [
                        os.path.join(
                            pydir,
                            "..",
                            "misc",
                            f"z-{NAME.lower()}-apply-profiles.desktop",
                        )
                    ],
                )
            )
            data_files.append(
                (
                    os.path.join(os.path.dirname(data), "man", "man1"),
                    safe_glob(os.path.join(pydir, "..", "man", "*.1")),
                )
            )
            if not skip_instrument_conf_files:
                # device configuration / permission stuff
                if is_rpm_build:
                    # RPM postinstall script will install these to the correct
                    # locations. This allows us compatibility with Argyll
                    # packages which may also contain same udev rules / hotplug
                    # scripts, thus avoiding file conflicts
                    data_files.append(
                        (
                            os.path.join(data, "usb"),
                            [os.path.join(pydir, "..", "misc", "45-Argyll.rules")],
                        )
                    )
                    data_files.append(
                        (
                            os.path.join(data, "usb"),
                            [os.path.join(pydir, "..", "misc", "55-Argyll.rules")],
                        )
                    )
                    data_files.append(
                        (
                            os.path.join(data, "usb"),
                            [os.path.join(pydir, "..", "misc", "Argyll")],
                        )
                    )
                    data_files.append(
                        (
                            os.path.join(data, "usb"),
                            [os.path.join(pydir, "..", "misc", "Argyll.usermap")],
                        )
                    )
                else:
                    devconf_files = []
                    if os.path.isdir("/etc/udev/rules.d"):
                        if safe_glob("/dev/bus/usb/*/*"):
                            # USB and serial instruments using udev, where udev
                            # already creates /dev/bus/usb/00X/00X devices
                            devconf_files.append(
                                (
                                    "/etc/udev/rules.d",
                                    [
                                        os.path.join(
                                            pydir, "..", "misc", "55-Argyll.rules"
                                        )
                                    ],
                                )
                            )
                        else:
                            # USB using udev, where there are NOT /dev/bus/usb/00X/00X
                            # devices
                            devconf_files.append(
                                (
                                    "/etc/udev/rules.d",
                                    [
                                        os.path.join(
                                            pydir, "..", "misc", "45-Argyll.rules"
                                        )
                                    ],
                                )
                            )
                    elif os.path.isdir("/etc/hotplug"):
                        # USB using hotplug and Serial using udev
                        # (older versions of Linux)
                        devconf_files.append(
                            (
                                "/etc/hotplug/usb",
                                [
                                    os.path.join(pydir, "..", "misc", fname)
                                    for fname in ["Argyll", "Argyll.usermap"]
                                ],
                            )
                        )
                    for entry in devconf_files:
                        for fname in entry[1]:
                            if os.path.isfile(fname):
                                data_files.extend([(entry[0], [fname])])
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
                    and dname
                    in ("16x16", "32x32", "48x48", largest_iconbundle_icon_size)
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
    if do_py2app:
        data_files.append(
            (
                os.path.join(data, "scripts"),
                [
                    os.path.join(
                        pydir,
                        "..",
                        "scripts",
                        f"{NAME.lower()}-eecolor-to-madvr-converter",
                    )
                ],
            )
        )

    return doc, data, package_data, scripts, data_files


def _build_base_attrs(
    do_py2app: bool,
    setuptools_flag: bool | None,
    scripts: list[tuple[str, str]],
    package_data: dict,
    data_files: list,
) -> dict:
    """Assemble the base distutils/setuptools ``attrs`` dict.

    Returns:
        dict: The ``attrs`` dict to be passed to ``setup(**attrs)``.
    """
    # sources = []
    # if sys.platform == "win32":
    #     macros = [("NT", None)]
    #     libraries = ["user32", "gdi32"]
    #     link_args = None
    # elif sys.platform == "darwin":
    #     macros = [("__APPLE__", None), ("UNIX", None)]
    #     libraries = None
    #     # XXX: Not sure which macOS version exactly removed the need
    #     # to specify -framework
    #     if intlist(platform.mac_ver()[0].split(".")) >= [10, 7]:
    #         link_args = None
    #     else:
    #         link_args = [
    #             "-framework Carbon",
    #             "-framework CoreFoundation",
    #             "-framework Python",
    #             "-framework IOKit",
    #         ]
    # else:
    #     macros = [("UNIX", None)]
    #     libraries = ["X11", "Xinerama", "Xrandr", "Xxf86vm"]
    #     link_args = None

    ext_modules = []

    requires = []
    if not setuptools_flag or sys.platform != "win32":
        # wxPython windows installer doesn't add egg-info entry, so
        # a dependency check from pkg_resources would always fail
        requires.append(
            "wxPython (>= {})".format(".".join(str(n) for n in WX_MINVERSION))
        )
    if sys.platform == "win32":
        requires.append("pywin32 (>= 213.0)")

    packages = [NAME, f"{NAME}.lib", f"{NAME}.lib.agw"]

    # name/version/description/license/classifiers/readme/entry_points
    # (gui_scripts) live in pyproject.toml's [project] table, which always
    # wins over the corresponding keys here (setuptools applies it on top of
    # whatever `distutils.core.setup(**attrs)`/`setuptools.setup(**attrs)` is
    # given, confirmed empirically via sdist/wheel METADATA), so they are not
    # duplicated in this dict.
    attrs = {
        "author": AUTHOR_ASCII,
        "author_email": AUTHOR_EMAIL,
        "data_files": data_files,
        "download_url": f"{DEVELOPMENT_HOME_PAGE}/releases/download/"
        f"{VERSION_STRING}/{NAME}-{VERSION_STRING}.tar.gz",
        "ext_modules": ext_modules,
        "packages": packages,
        "package_data": package_data,
        "package_dir": {NAME: NAME},
        "platforms": [
            "Python >= {} <= {}".format(
                ".".join(str(n) for n in PY_MINVERSION),
                ".".join(str(n) for n in PY_MAXVERSION),
            ),
            "Linux/Unix with X11",
            "Mac OS X >= 10.4",
            "Windows 2000 and newer",
        ],
        "requires": requires,
        "provides": [NAME],
        "scripts": [],
        "url": f"https://{DOMAIN}/",
        "version": msiversion if "bdist_msi" in sys.argv[1:] else VERSION_STRING,
    }

    if setuptools_flag:
        # gui_scripts entry points live in pyproject.toml's
        # [project.gui-scripts] table, which wins over anything set here.
        attrs["exclude_package_data"] = {NAME: []}
        attrs["include_package_data"] = (
            sys.platform in ("darwin", "win32") and not do_py2app
        )
        # Modern py2app build flow errors out when install_requires is present.
        # Keep runtime metadata for normal installs, but skip it for app bundling.
        if not do_py2app:
            install_requires = [
                req.replace("(", "").replace(")", "") for req in requires
            ]
            attrs["install_requires"] = install_requires
        attrs["zip_safe"] = False
    else:
        attrs["scripts"].extend(
            os.path.join("scripts", script)
            for script, desc in [
                script_desc
                for script_desc in scripts
                if script_desc[0] != f"{NAME.lower()}-apply-profiles"
                or sys.platform != "darwin"
            ]
        )

    if "bdist_wininst" in sys.argv[1:]:
        attrs["scripts"].append(os.path.join("util", f"{NAME}_postinstall.py"))

    return attrs


def _configure_py2app(
    attrs: dict, do_py2app: bool, use_sdl: bool, dist_dir: str | None
) -> str | None:
    """Populate the py2app-specific entries of ``attrs`` in place.

    Returns:
        str | None: The resolved ``dist_dir``, unchanged if not building
            via py2app.
    """
    if not do_py2app:
        return dist_dir

    mainpy = os.path.join(source_dir, "main.py")
    if not os.path.exists(mainpy):
        shutil.copy(os.path.join(source_dir, "scripts", NAME.lower()), mainpy)
    attrs["app"] = [mainpy]
    dist_dir = os.path.join(
        pydir,
        "..",
        "dist",
        f"py2app.{get_platform()}-py{sys.version_info[0]}.{sys.version_info[1]}",
        f"{NAME}-{VERSION_STRING}",
    )
    import py2app.build_app as py2app_build_app
    from py2app import util as py2app_util
    from py2app.build_app import py2app as py2app_cls

    def _skip_codesign_adhoc(bundle: str) -> None:
        print(f"Skipping ad-hoc codesign for bundle: {bundle}")

    py2app_util.codesign_adhoc = _skip_codesign_adhoc
    py2app_build_app.codesign_adhoc = _skip_codesign_adhoc

    class DisplayCALPy2App(py2app_cls):
        """py2app wrapper that tolerates PEP 621 dependencies metadata."""

        def finalize_options(self) -> None:
            # py2app 0.28+ errors out when install_requires is populated.
            # Under setuptools+pyproject, install_requires can be injected
            # from project.dependencies even if setup.py does not set it.
            self.distribution.install_requires = []
            if hasattr(self.distribution.metadata, "requires_dist"):
                self.distribution.metadata.requires_dist = []
            super().finalize_options()

    py2app_cls._copy_package_data = py2app_cls.copy_package_data

    def copy_package_data(self: py2app_cls, package: Package, target_dir: str) -> None:
        """Override copy_package_data to skip package data from other packages.

        Copy any package data in a python package into the target_dir.

        This is a bit of a hack, it would be better to identify python eggs
        and copy those in whole.

        Args:
            self (py2app_cls): The py2app class instance.
            package (Package): The package to copy data from.
            target_dir (str): The target directory to copy data to.
        """
        # Skip package data which is already included as data files
        if package.identifier.split(".")[0] != NAME:
            self._copy_package_data(package, target_dir)

    py2app_cls.copy_package_data = copy_package_data
    attrs.setdefault("cmdclass", {})
    attrs["cmdclass"]["py2app"] = DisplayCALPy2App
    attrs["options"] = {
        "py2app": {
            "argv_emulation": False,
            "dist_dir": dist_dir,
            "excludes": config["excludes"]["all"] + config["excludes"]["darwin"],
            "iconfile": os.path.join(pydir, "theme", "icons", f"{NAME}.icns"),
            "no_strip": True,
            "optimize": 0,
            "plist": plist_dict,
            # py2app's pyside6 recipe only copies Qt's plugin binaries
            # (e.g. platforms/libqcocoa.dylib, needed for QApplication to
            # start at all) when this is set; it defaults to empty and
            # silently bundles none of them otherwise.
            "qt_plugins": [
                "iconengines/*",
                "imageformats/*",
                "platforms/*",
                "styles/*",
            ],
        }
    }
    if use_sdl:
        attrs["options"]["py2app"]["frameworks"] = ["SDL2", "SDL2_mixer"]
    attrs["setup_requires"] = ["py2app"]

    return dist_dir


def _run_install_or_uninstall(
    attrs: dict,
    data: str,
    doc: str,
    do_uninstall: bool,
    do_install: bool,
    bdist_win: bool,
    bdist_dumb: bool,
    print_help: bool,
    dry_run: bool,
    debug: int,
    install_data: str | None,
    setuptools_flag: bool | None,
    recordfile_name: str | None,
    dist_setup: Callable,
) -> tuple[bool, object, str, str]:
    """Run the install/uninstall command dispatch.

    Returns:
        tuple[bool, object, str, str]: Whether the request was fully handled
            (in which case the caller should return without doing a normal
            build), the finalized "install" command object (or None if the
            first branch below didn't run), and the (possibly change_root'd)
            ``data``/``doc`` paths.
    """
    cmd = None

    if (do_uninstall or do_install or bdist_win or bdist_dumb) and not print_help:
        distutils.core._setup_stop_after = "commandline"
        dist = dist_setup(**attrs)
        distutils.core._setup_stop_after = None
        cmd = install(dist).get_finalized_command("install")
        if debug > 0:
            for attrname in [
                "base",
                "data",
                "headers",
                "lib",
                "libbase",
                "platbase",
                "platlib",
                "prefix",
                "purelib",
                "root",
                "scripts",
                "userbase",
            ]:
                if attrname not in ["prefix", "root"]:
                    attrname = "install_" + attrname
                if hasattr(cmd, attrname):
                    print(attrname, getattr(cmd, attrname))
        if debug > 1:
            try:
                from util.ppdir import ppdir
            except ImportError:
                pass
            else:
                ppdir(cmd, types=[dict, list, str, tuple, type, str])
        if not install_data:
            if sys.platform in ("darwin", "win32"):
                # on Mac OS X and Windows, we want data files in the package dir
                data_basedir = cmd.install_lib
            else:
                data_basedir = cmd.install_data
        else:
            data_basedir = install_data

        data = change_root(data_basedir, data)
        doc = change_root(data_basedir, doc)
        # determine in which cases we want to make data file paths relative to
        # site-packages (on Mac and Windows) and when we want to make them
        # absolute (Linux)
        linux = sys.platform not in ("darwin", "win32") and (
            not cmd.root and setuptools_flag
        )
        dar_win = (
            sys.platform in ("darwin", "win32") and (cmd.root or not setuptools_flag)
        ) or bdist_win
        if (
            not do_uninstall
            and not install_data
            and (linux or dar_win)
            and attrs["data_files"]
        ):
            if data_basedir.startswith(cmd.install_data + os.path.sep):
                data_basedir = os.path.relpath(data_basedir, cmd.install_data)
            for i, f in enumerate(attrs["data_files"]):
                if isinstance(f, str):
                    attrs["data_files"][i] = change_root(data_basedir, f)
                else:
                    attrs["data_files"][i] = (change_root(data_basedir, f[0]), f[1])

    if do_uninstall and not print_help:
        # Quick and dirty uninstall
        if dry_run:
            print("dry run - nothing will be removed")
        else:
            from DisplayCAL.postinstall import postuninstall

            # Yeah, yeah - its actually pre-uninstall
            if cmd.root:
                postuninstall(prefix=change_root(cmd.root, cmd.prefix))
            else:
                postuninstall(prefix=cmd.prefix)

        removed = []
        visited = []

        if os.path.exists(recordfile_name):
            with open(recordfile_name) as f:
                paths = [
                    (
                        change_root(cmd.root, line.rstrip("\n"))
                        if cmd.root
                        else line.rstrip("\n")
                    )
                    for line in f
                ]
        else:
            paths = []

        if not paths:
            # If the installed files have not been recorded, use some fallback
            # logic to find them
            paths = safe_glob(os.path.join(cmd.install_scripts, NAME))
            if sys.platform == "win32":
                if setuptools_flag:
                    paths += safe_glob(os.path.join(cmd.install_scripts, f"{NAME}.exe"))
                    paths += safe_glob(
                        os.path.join(cmd.install_scripts, f"{NAME}-script.py")
                    )
                else:
                    paths += safe_glob(os.path.join(cmd.install_scripts, f"{NAME}.cmd"))
            paths += safe_glob(
                os.path.join(cmd.install_scripts, f"{NAME}_postinstall.py")
            )
            for attrname in ["data", "headers", "lib", "libbase", "platlib", "purelib"]:
                path = os.path.join(getattr(cmd, f"install_{attrname}"), NAME)
                if path not in paths:
                    # Using sys.version in this way is consistent with
                    # setuptools
                    paths += (
                        safe_glob(path)
                        + safe_glob(
                            f"{path}-{VERSION_STRING}-py{sys.version_info[0]}.{sys.version_info[1]}*.egg"
                        )
                        + safe_glob(
                            f"{path}-{VERSION_STRING}-py{sys.version_info[0]}.{sys.version_info[1]}*.egg-info"
                        )
                    )

            if os.path.isabs(data) and data not in paths:
                for fname in [
                    "lang",
                    "presets",
                    "ref",
                    "report",
                    "screenshots",
                    "theme",
                    "ti1",
                    "x3d-viewer",
                    "CHANGELOG.md",
                    "CHANGELOG-legacy.html",
                    "LICENSE.txt",
                    "README.html",
                    "README-fr.html",
                    "beep.wav",
                    "cacert.pem",
                    "camera_shutter.wav",
                    "ColorLookupTable.fx",
                    f"{NAME.lower()}.desktop",
                    f"{NAME.lower()}-3dlut-maker.desktop",
                    f"{NAME.lower()}-curve-viewer.desktop",
                    f"{NAME.lower()}-profile-info.desktop",
                    f"{NAME.lower()}-scripting-client.desktop",
                    f"{NAME.lower()}-synthprofile.desktop",
                    f"{NAME.lower()}-testchart-editor.desktop",
                    "pnp.ids",
                    "quirk.json",
                    "linear.cal",
                    "test.cal",
                ]:
                    path = os.path.join(data, fname)
                    if path not in paths:
                        paths += safe_glob(path)
            if os.path.isabs(doc) and doc not in paths:
                for fname in [
                    "screenshots",
                    "theme",
                    "CHANGELOG.md",
                    "CHANGELOG-legacy.html",
                    "LICENSE.txt",
                    "README.html",
                    "README-fr.html",
                ]:
                    path = os.path.join(doc, fname)
                    if path not in paths:
                        paths += safe_glob(path)
            if sys.platform == "win32":
                from DisplayCAL.postinstall import get_special_folder_path

                startmenu_programs_common = get_special_folder_path(
                    "CSIDL_COMMON_PROGRAMS"
                )
                startmenu_programs = get_special_folder_path("CSIDL_PROGRAMS")
                for path in (startmenu_programs_common, startmenu_programs):
                    if path:
                        for filename in (
                            NAME,
                            "CHANGES",
                            "LICENSE",
                            "README",
                            "Uninstall",
                        ):
                            paths += safe_glob(
                                os.path.join(path, NAME, f"{filename}.lnk")
                            )

        for path in paths:
            if os.path.exists(path):
                if path in visited:
                    continue
                visited.append(path)
                if dry_run:
                    print(path)
                    continue
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        os.rmdir(path)
                except Exception as exception:
                    print("could'nt remove", path)
                    print("   ", exception)
                else:
                    print("removed", path)
                    removed.append(path)
            while path != os.path.dirname(path):
                # remove parent directories if empty
                # could also use os.removedirs(path) but we want some status
                # info
                path = os.path.dirname(path)
                if os.path.isdir(path):
                    if len(os.listdir(path)) == 0:
                        if path in visited:
                            continue
                        visited.append(path)
                        if dry_run:
                            print(path)
                            continue
                        try:
                            os.rmdir(path)
                        except Exception as exception:
                            print("could'nt remove", path)
                            print("   ", exception)
                        else:
                            print("removed", path)
                            removed.append(path)
                    else:
                        break

        if not removed:
            print(len(visited), "entries found")
        else:
            print(len(removed), "entries removed")

        return True, cmd, data, doc

    return False, cmd, data, doc


def _write_manifest_in(
    attrs: dict,
    skip_instrument_conf_files: bool,
    setuptools_flag: bool | None,
    do_generate_manifest: bool,
    dry_run: bool,
) -> bool:
    """Build MANIFEST.in's contents and write it out if requested.

    Returns:
        bool: True if manifest generation was requested (in which case the
            caller should return without doing a normal build).
    """
    # MANIFEST.in used to be regenerated from scratch as a side effect of
    # every build (bdist_wheel, sdist, egg_info, ...), silently rewriting
    # a tracked source file on each invocation. It's now only written out
    # when explicitly requested via `python native_build.py manifest`
    # (do_generate_manifest below), the list itself is still built here
    # since it depends on the `attrs` this function assembles.
    manifest_in = ["# Regenerate via `python native_build.py manifest`, do not edit"]
    manifest_in.extend(
        [
            "include LICENSE.txt",
            "include DisplayCAL/VERSION",
            "include MANIFEST.in",
            "include README.html",
            "include README-fr.html",
            "include CHANGELOG.md",
            "include CHANGELOG-legacy.html",
            f"include {NAME}*.pyw",
            f"include {NAME}-*.pyw",
            f"include {NAME}-*.py",
            "include native_build.py",
            "recursive-include _native_build *.py",
        ]
    )
    for _datadir, datafiles in attrs.get("data_files", []):
        manifest_in.extend(
            "include {}".format(
                os.path.relpath(os.path.sep.join(datafile.split("/")), source_dir)
                or datafile
            )
            for datafile in datafiles
        )
    for extmod in attrs.get("ext_modules", []):
        manifest_in.extend(
            "include " + os.path.sep.join(src.split("/")) for src in extmod.sources
        )
    for pkg in attrs.get("packages", []):
        pkg = os.path.join(*pkg.split("."))
        pkgdir = os.path.sep.join(attrs.get("package_dir", {}).get(pkg, pkg).split("/"))
        manifest_in.append("include " + os.path.join(pkgdir, "*.py"))
        # manifest_in.append("include " + os.path.join(pkgdir, "*.pyd"))
        # manifest_in.append("include " + os.path.join(pkgdir, "*.so"))
        manifest_in.extend(
            f"include {os.path.sep.join([pkgdir, *obj.split('/')])}"
            for obj in attrs.get("package_data", {}).get(pkg, [])
        )
    manifest_in.extend(
        "include {}".format(os.path.join(*pymod.split(".")))
        for pymod in attrs.get("py_modules", [])
    )
    manifest_in.append(
        "include {}".format(os.path.join(NAME, "theme", "theme-info.txt"))
    )
    manifest_in.append(
        "recursive-include {} {} {}".format(
            os.path.join(NAME, "theme", "icons"), "*.icns", "*.ico"
        )
    )
    manifest_in.append("include {}".format(os.path.join("man", "*.1")))
    manifest_in.append("recursive-include misc *")
    if skip_instrument_conf_files:
        manifest_in.extend(
            [
                "exclude misc/Argyll",
                "exclude misc/*.rules",
                "exclude misc/*.usermap",
            ]
        )
    manifest_in.append("include {}".format(os.path.join("screenshots", "*.png")))
    manifest_in.append("include {}".format(os.path.join("scripts", "*")))
    manifest_in.append("include {}".format(os.path.join("tests", "*")))
    manifest_in.append("recursive-include theme *")
    manifest_in.append("recursive-include util *.cmd *.py *.sh")
    if sys.platform == "win32" and not setuptools_flag:
        # Only needed under Windows
        manifest_in.append("global-exclude .svn/*")
    manifest_in.append("global-exclude *~")
    manifest_in.append("global-exclude *.backup")
    manifest_in.append("global-exclude */__pycache__/*")
    manifest_in.append("global-exclude *.bak")
    if do_generate_manifest:
        if not dry_run:
            with open("MANIFEST.in", "w") as manifest:
                manifest.write("\n".join(manifest_in))
            if os.path.exists("MANIFEST"):
                os.remove("MANIFEST")
        return True

    return False


def main() -> None:
    """Entry point that assembles `attrs` and runs the real distutils/setuptools setup()."""
    print("***", os.path.abspath(sys.argv[0]), " ".join(sys.argv[1:]))

    bdist_dumb = "bdist_dumb" in sys.argv[1:]
    bdist_win = "bdist_msi" in sys.argv[1:] or "bdist_wininst" in sys.argv[1:]
    debug = 0
    do_full_install = False
    do_generate_manifest = "generate_manifest_in" in sys.argv[1:]
    do_install = False
    do_py2app = "py2app" in sys.argv[1:]
    do_uninstall = "uninstall" in sys.argv[1:]
    doc_layout = "deb" if os.path.exists("/etc/debian_version") else ""
    dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
    print_help = False
    install_data = None  # data files install path (only if given)
    is_rpm_build = "bdist_rpm" in sys.argv[1:] or os.path.abspath(sys.argv[0]).endswith(
        os.path.join(
            os.path.sep,
            "rpm",
            "BUILD",
            f"{NAME}-{VERSION_STRING}",
            os.path.basename(os.path.abspath(sys.argv[0])),
        )
    )
    prefix = ""
    recordfile_name = None  # record installed files to this file
    sdist = "sdist" in sys.argv[1:]
    setuptools = None
    skip_postinstall = "--skip-postinstall" in sys.argv[1:]
    use_distutils = not do_py2app
    use_setuptools = (
        not use_distutils
        or "--use-setuptools" in sys.argv[1:]
        or (os.path.exists("use-setuptools") and "--use-distutils" not in sys.argv[1:])
    )
    use_sdl = "--use-sdl" in sys.argv[1:]

    sys.path.insert(1, os.path.join(os.path.dirname(pydir), "util"))

    current_findall = distutils.filelist.findall

    if use_setuptools:
        if "--use-setuptools" in sys.argv[1:] and not os.path.exists("use-setuptools"):
            open("use-setuptools", "w").close()
        try:
            from setuptools import find_packages, setup

            setuptools = True
            print("using setuptools")
            current_findall = find_packages
        except ImportError:
            pass
    elif os.path.exists("use-setuptools"):
        os.remove("use-setuptools")

    if distutils.filelist.findall is current_findall:
        # Fix traversing unneeded dirs which can take a long time (minutes)
        def findall(
            directory: str = os.curdir,
            original: Callable = distutils.filelist.findall,
            listdir: Callable = os.listdir,
            basename: str = os.path.basename,
        ) -> list[str]:
            """Find all files under 'dir' and return the list of full filenames.

            Unless dir is '.', return full filenames with dir prepended.

            Args:
                directory (str): The directory to search. Default is os.curdir.
                original (Callable): The original findall function.
                listdir (Callable): The os.listdir function.
                basename (str): The os.path.basename function.

            Returns:
                list[str]: List of full filenames found under 'dir'.
            """
            os.listdir = lambda path: [
                entry
                for entry in listdir(path)
                if entry not in ("build", "dist") and not entry.startswith(".")
            ]
            try:
                return original(directory)
            finally:
                os.listdir = listdir

        distutils.filelist.findall = findall

    if not setuptools:
        from distutils.core import setup

        print("using distutils")

    if do_uninstall:
        i = sys.argv.index("uninstall")
        sys.argv = [*sys.argv[:i], "install", *sys.argv[i + 1 :]]
        install.create_home_path = lambda self: None

    if (
        skip_instrument_conf_files := "--skip-instrument-configuration-files"
        in sys.argv[1:]
    ):
        i = sys.argv.index("--skip-instrument-configuration-files")
        sys.argv = sys.argv[:i] + sys.argv[i + 1 :]

    if not is_rpm_build:
        skip_instrument_conf_files = True

    if skip_postinstall:
        i = sys.argv.index("--skip-postinstall")
        sys.argv = sys.argv[:i] + sys.argv[i + 1 :]

    if "--use-distutils" in sys.argv[1:]:
        i = sys.argv.index("--use-distutils")
        sys.argv = sys.argv[:i] + sys.argv[i + 1 :]

    if "--use-setuptools" in sys.argv[1:]:
        i = sys.argv.index("--use-setuptools")
        sys.argv = sys.argv[:i] + sys.argv[i + 1 :]

    dist_dir = None
    argv = list(sys.argv[1:])
    for i, arg in enumerate(reversed(argv)):
        n = len(sys.argv) - i - 1
        if arg in (
            "install",
            "install_lib",
            "install_headers",
            "install_scripts",
            "install_data",
        ):
            if arg == "install":
                do_full_install = True
            do_install = True
        elif arg == "-d" and len(sys.argv[1:]) > i:
            dist_dir = sys.argv[i + 2]
        else:
            arg = arg.split("=")
            if arg[0] == "--debug":
                debug = 1 if len(arg) == 1 else int(arg[1])
                sys.argv = sys.argv[:n] + sys.argv[n + 1 :]
            elif len(arg) == 2:
                if arg[0] == "--dist-dir":
                    dist_dir = arg[1]
                elif arg[0] == "--doc-layout":
                    doc_layout = arg[1]
                    sys.argv = sys.argv[:n] + sys.argv[n + 1 :]
                elif arg[0] == "--install-data":
                    install_data = arg[1]
                elif arg[0] == "--prefix":
                    prefix = arg[1]
                elif arg[0] == "--record":
                    recordfile_name = arg[1]
            elif arg[0] == "-h" or arg[0].startswith("--help"):
                print_help = True

    if not recordfile_name and (do_full_install or do_uninstall):
        recordfile_name = "INSTALLED_FILES"
    # if not do_uninstall:
    # sys.argv.append("--record=" + "INSTALLED_FILES")

    doc, data, package_data, scripts, data_files = _collect_data_files(
        do_py2app,
        sdist,
        doc_layout,
        install_data,
        is_rpm_build,
        skip_instrument_conf_files,
        prefix,
        use_sdl,
    )

    attrs = _build_base_attrs(do_py2app, setuptools, scripts, package_data, data_files)

    dist_dir = _configure_py2app(attrs, do_py2app, use_sdl, dist_dir)

    handled, cmd, data, doc = _run_install_or_uninstall(
        attrs,
        data,
        doc,
        do_uninstall,
        do_install,
        bdist_win,
        bdist_dumb,
        print_help,
        dry_run,
        debug,
        install_data,
        setuptools,
        recordfile_name,
        setup,
    )
    if handled:
        return

    if _write_manifest_in(
        attrs, skip_instrument_conf_files, setuptools, do_generate_manifest, dry_run
    ):
        return

    if do_py2app:
        sys.path.insert(1, pydir)
        i = sys.argv.index("py2app")
        if "build_ext" not in sys.argv[1:i]:
            sys.argv.insert(i, "build_ext")

    setup(**attrs)

    if dry_run or print_help:
        return

    if do_py2app:
        frameworks_dir = os.path.join(dist_dir, f"{NAME}.app", "Contents", "Frameworks")
        lib_dynload_dir = os.path.join(
            dist_dir,
            f"{NAME}.app",
            "Contents",
            "Resources",
            "lib",
            "python{}.{}".format(*sys.version_info[:2]),
            "lib-dynload",
        )
        # Fix Pillow (PIL) dylibs not being included
        pil_dylibs = os.path.join(lib_dynload_dir, "PIL", ".dylibs")
        if not os.path.isdir(pil_dylibs):
            import PIL

            pil_installed_dylibs = os.path.join(
                os.path.dirname(PIL.__file__), ".dylibs"
            )
            print("Copying", pil_installed_dylibs, "->", pil_dylibs)
            shutil.copytree(pil_installed_dylibs, pil_dylibs)
            # ADD THIS: Remove existing signatures so the later deep-sign works properly
            for root, _dirs, files in os.walk(pil_dylibs):
                for file in files:
                    if file.endswith(".dylib"):
                        os.system(
                            f"codesign --remove-signature '{os.path.join(root, file)}'"
                        )
            for entry in os.listdir(pil_dylibs):
                print(os.path.join(pil_dylibs, entry))
            # Remove wrongly included frameworks
            dylibs_entries = os.listdir(pil_installed_dylibs)
            for entry in os.listdir(frameworks_dir):
                if entry in dylibs_entries:
                    dylib = os.path.join(frameworks_dir, entry)
                    print("Removing", dylib)
                    os.remove(dylib)
        import wx

        if wx.VERSION >= (4,):
            # Fix wxPython 4 dylibs being included in wrong location
            wx_dylibs = os.path.join(lib_dynload_dir, "wx")
            for entry in os.listdir(frameworks_dir):
                if entry.startswith("libwx"):
                    dylib = os.path.join(frameworks_dir, entry)
                    lib_dylib = os.path.join(wx_dylibs, entry)
                    print("Moving", dylib, "->", lib_dylib)
                    shutil.move(dylib, lib_dylib)

        create_app_symlinks(dist_dir, scripts)

    if do_full_install and not is_rpm_build and not skip_postinstall:
        from DisplayCAL.postinstall import postinstall

        if sys.platform == "win32":
            path = os.path.join(cmd.install_lib, NAME)
            # Using sys.version in this way is consistent with setuptools
            for path_ in safe_glob(path) + safe_glob(
                os.path.join(
                    f"{path}-{VERSION_STRING}-py{sys.version_info[0]}.{sys.version_info[1]}*.egg",
                    NAME,
                )
            ):
                if cmd.root:
                    postinstall(prefix=change_root(cmd.root, path_))
                else:
                    postinstall(prefix=path_)

        elif cmd.root:
            postinstall(prefix=change_root(cmd.root, cmd.prefix))
        else:
            postinstall(prefix=cmd.prefix)


if __name__ == "__main__":
    main()
