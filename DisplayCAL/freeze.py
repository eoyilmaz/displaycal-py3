# -*- coding: utf-8 -*-
"""This script is used by the py2exe to freeze the library into executables.
"""
import sys
import functools
import shutil
import os
import platform
from setuptools import Extension, setup
from distutils.util import change_root, get_platform
from fnmatch import fnmatch
from configparser import ConfigParser
import ctypes.util
from time import strftime

from py2exe import freeze


# Borrowed from setuptools
def _find_all_simple(path):
    """Find all files under 'path'."""
    results = (
        os.path.join(base, file)
        for base, dirs, files in os.walk(path, followlinks=True)
        for file in files
    )
    return filter(os.path.isfile, results)


def findall(dir=os.curdir):
    """Find all files under 'dir' and return the list of full filenames.

    Unless dir is '.', return full filenames with dir prepended.
    """
    files = _find_all_simple(dir)
    if dir == os.curdir:
        make_rel = functools.partial(os.path.relpath, start=dir)
        files = map(make_rel, files)
    return list(files)


import distutils.filelist

distutils.filelist.findall = findall  # Fix findall bug in distutils


bits = platform.architecture()[0][:2]
pypath = os.path.abspath(__file__)
pydir = os.path.dirname(pypath)
source_dir = os.path.dirname(pydir)

print(f"pydir     : {pydir}")
print(f"source_dir: {source_dir}")
sys.path.append(source_dir)


from DisplayCAL.defaultpaths import autostart, autostart_home
from DisplayCAL.meta import (
    appstream_id,
    author,
    author_ascii,
    author_email,
    description,
    development_home_page,
    DOMAIN,
    longdesc,
    name,
    py_maxversion,
    py_minversion,
    script2pywname,
    version,
    version_tuple,
    wx_minversion,
)
from DisplayCAL.util_list import intlist
from DisplayCAL.util_os import getenvu, relpath, safe_glob
from DisplayCAL.util_str import safe_str

appname = name


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
        "CHANGES.html",
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
    # Use pyglet with OpenAL as audio backend. We only need
    # pyglet, pyglet.app and pyglet.media
    "excludes": {
        "all": [
            "Tkconstants",
            "Tkinter",
            "pygame",
            "pyglet.canvas",
            "pyglet.extlibs",
            "pyglet.font",
            "pyglet.gl",
            "pyglet.graphics",
            "pyglet.image",
            "pyglet.input",
            "pyglet.text",
            "pyglet.window",
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
        name: [
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
        ]
    },
    "xtra_package_data": {name: {"win32": [f"theme/icons/{name}-uninstall.ico"]}},
}


def add_lib_excludes(key, excludebits):
    for exclude in excludebits:
        config["excludes"][key].extend([f"{name}.lib{exclude}", f"lib{exclude}"])

    for exclude in ("32", "64"):
        for pycompat in ("38", "39", "310", "311", "312", "313"):
            if key == "win32" and (
                pycompat == str(sys.version_info[0]) + str(sys.version_info[1])
                or exclude == excludebits[0]
            ):
                continue
            config["excludes"][key].extend(
                [
                    f"{name}.lib{exclude}.python{pycompat}",
                    f"{name}.lib{exclude}.python{pycompat}.RealDisplaySizeMM",
                ]
            )


add_lib_excludes("darwin", ["64" if bits == "32" else "32"])
add_lib_excludes("win32", ["64" if bits == "32" else "32"])


msiversion = ".".join(
    (
        str(version_tuple[0]),
        str(version_tuple[1]),
        str(version_tuple[2]),
    )
)


class Target:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def get_data(tgt_dir, key, pkgname=None, subkey=None, excludes=None):
    """Return configured data files."""
    files = config[key]
    src_dir = source_dir
    resource_dir = src_dir
    if pkgname:
        files = files[pkgname]
        resource_dir = os.path.join(src_dir, pkgname)
        if subkey:
            if subkey in files:
                files = files[subkey]
            else:
                files = []
    data = []
    for pth in files:
        if not [exclude for exclude in excludes or [] if fnmatch(pth, exclude)]:
            normalized_path = os.path.normpath(
                os.path.join(tgt_dir, os.path.dirname(pth))
            )
            safe_path = [
                relpath(p, src_dir) for p in safe_glob(os.path.join(resource_dir, pth))
            ]
            data.append((normalized_path, safe_path))
    return data


def get_scripts(excludes=None):
    # It is required that each script has an accompanying .desktop file
    scripts_with_desc = []
    scripts = safe_glob(os.path.join(pydir, "..", "scripts", appname.lower() + "*"))

    def sortbyname(a, b):
        a, b = [os.path.splitext(v)[0] for v in (a, b)]
        if a > b:
            return 1
        elif a < b:
            return -1
        else:
            return 0

    import functools

    scripts = sorted(scripts, key=functools.cmp_to_key(sortbyname))
    for script in scripts:
        script = os.path.basename(script)
        if script == appname.lower() + "-apply-profiles-launcher":
            continue
        desktopfile = os.path.join(pydir, "..", "misc", f"{script}.desktop")
        if os.path.isfile(desktopfile):
            cfg = ConfigParser()
            cfg.read(desktopfile)
            script = cfg.get("Desktop Entry", "Exec").split()[0]
            desc = cfg.get("Desktop Entry", "Name")
        else:
            desc = ""
        if not [exclude for exclude in excludes or [] if fnmatch(script, exclude)]:
            scripts_with_desc.append((script, desc))
    return scripts_with_desc


def build_py2exe():
    """py2exe builder that uses the new freeze API."""

    use_sdl = False
    sys.path.insert(1, os.path.join(pydir, "..", "util"))

    setuptools = True
    debug = False
    dry_run = False
    do_full_install = False

    doc = "."
    data = "."
    # Use CA file from certifi project
    import certifi

    cacert = certifi.where()
    if cacert:
        shutil.copyfile(cacert, os.path.join(pydir, "cacert.pem"))
        config["package_data"][name].append("cacert.pem")
    else:
        print("WARNING: cacert.pem from certifi project not found!")

    # on Mac OS X and Windows, we want data files in the package dir
    # (package_data will be ignored when using py2exe)
    package_data = {
        name: ["theme/icons/22x22/*.png", "theme/icons/24x24/*.png"],
    }
    scripts = get_scripts()
    # Doc files
    data_files = []
    data_files += get_data(doc, "doc", excludes=["LICENSE.txt"])
    if data_files:
        data_files.append(
            (doc, [relpath(os.path.join(pydir, "..", "LICENSE.txt"), source_dir)])
        )
    # metainfo / appdata.xml
    data_files.append(
        (
            os.path.join(os.path.dirname(data), "metainfo"),
            [
                relpath(
                    os.path.normpath(
                        os.path.join(pydir, "..", "dist", f"{appstream_id}.appdata.xml")
                    ),
                    source_dir,
                )
            ],
        )
    )
    data_files += get_data(data, "package_data", name, excludes=["theme/icons/*"])
    data_files += get_data(data, "data")
    data_files += get_data(data, "xtra_package_data", name, sys.platform)

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
            if not os.path.basename(iconpath).startswith(name.lower()) or (
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
    sources = [os.path.join(name, "RealDisplaySizeMM.c")]
    macros = [("NT", None)]
    libraries = ["user32", "gdi32"]
    link_args = None
    extname = f"{name}.lib{bits}.python{sys.version_info[0]}{sys.version_info[1]}.RealDisplaySizeMM"
    RealDisplaySizeMM = Extension(
        extname,
        sources=sources,
        define_macros=macros,
        libraries=libraries,
        extra_link_args=link_args,
    )
    ext_modules = [RealDisplaySizeMM]
    requires = []
    requires.append("pywin32 (>= 213.0)")
    packages = [name, f"{name}.lib", f"{name}.lib.agw"]
    # On Windows we want separate libraries
    packages.extend(
        [
            f"{name}.lib{bits}",
            f"{name}.lib{bits}.python{sys.version_info[0]}{sys.version_info[1]}",
        ]
    )

    attrs = {
        "author": author_ascii,
        "author_email": author_email,
        "classifiers": [
            "Development Status :: 5 - Production/Stable",
            "Environment :: MacOS X",
            "Environment :: Win32 (MS Windows)",
            "Environment :: X11 Applications",
            "Intended Audience :: End Users/Desktop",
            "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Programming Language :: Python :: 3.13",
            "Topic :: Multimedia :: Graphics",
        ],
        "data_files": data_files,
        "description": description,
        "download_url": f"{development_home_page}/releases/download/{version}/{name}-{version}.tar.gz",
        "ext_modules": ext_modules,
        "license": "GPL v3",
        "long_description": longdesc,
        "long_description_content_type": "text/x-rst",
        "name": name,
        "packages": packages,
        "package_data": package_data,
        "package_dir": {name: name},
        "platforms": [
            "Python >= {} <= {}".format(
                ".".join(str(n) for n in py_minversion),
                ".".join(str(n) for n in py_maxversion),
            ),
            "Linux/Unix with X11",
            "Mac OS X >= 10.4",
            "Windows 2000 and newer",
        ],
        "requires": requires,
        "provides": [name],
        "scripts": [],
        "url": f"https://{DOMAIN}/",
        "version": msiversion if "bdist_msi" in sys.argv[1:] else version,
    }
    if setuptools:
        attrs["entry_points"] = {
            "gui_scripts": [
                "{} = {}.main:main{}".format(
                    script,
                    name,
                    (
                        ""
                        if script == name.lower()
                        else script[len(name) :].lower().replace("-", "_")
                    ),
                )
                for script, desc in scripts
            ]
        }
        attrs["exclude_package_data"] = {name: ["RealDisplaySizeMM.c"]}
        attrs["include_package_data"] = False
        install_requires = [req.replace("(", "").replace(")", "") for req in requires]
        attrs["install_requires"] = install_requires
        attrs["zip_safe"] = False
    else:
        attrs["scripts"].extend(
            os.path.join("scripts", script)
            for script, desc in [
                script_desc
                for script_desc in scripts
                if script_desc[0] != f"{name.lower()}-apply-profiles"
                or sys.platform != "darwin"
            ]
        )

    import wx
    from winmanifest_util import getmanifestxml

    if platform.architecture()[0] == "64bit":
        arch = "amd64"
    else:
        arch = "x86"
    manifest_xml = getmanifestxml(
        os.path.join(
            pydir,
            "..",
            "misc",
            name
            + (
                ".exe.%s.VC90.manifest" % arch
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
    for script, desc in scripts + [apply_profiles_launcher]:
        shutil.copy(
            os.path.join(source_dir, "scripts", script),
            os.path.join(tmp_scripts_dir, script2pywname(script)),
        )
    attrs["windows"] = [
        Target(
            **{
                "script": os.path.join(tmp_scripts_dir, script2pywname(script)),
                "icon_resources": [
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
                "other_resources": [(24, 1, manifest_xml)],
                "copyright": "© %s %s" % (strftime("%Y"), author),
                "description": desc,
            }
        )
        for script, desc in [
            script_desc1
            for script_desc1 in scripts
            if script_desc1[0] != appname.lower() + "-eecolor-to-madvr-converter"
            and not script_desc1[0].endswith("-console")
        ]
    ]

    # Add profile loader launcher
    attrs["windows"].append(
        Target(
            **{
                "script": os.path.join(
                    tmp_scripts_dir, script2pywname(apply_profiles_launcher[0])
                ),
                "icon_resources": [
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
                "other_resources": [(24, 1, manifest_xml)],
                "copyright": "© %s %s" % (strftime("%Y"), author),
                "description": apply_profiles_launcher[1],
            }
        )
    )

    # Programs that can run with and without GUI
    console_scripts = [f"{name}-VRML-to-X3D-converter"]  # No "-console" suffix!
    for console_script in console_scripts:
        console_script_path = os.path.join(tmp_scripts_dir, console_script + "-console")
        if not os.path.isfile(console_script_path):
            shutil.copy(
                os.path.join(
                    source_dir, "scripts", console_script.lower() + "-console"
                ),
                console_script_path,
            )
    attrs["console"] = [
        Target(
            **{
                "script": os.path.join(
                    tmp_scripts_dir, script2pywname(script) + "-console"
                ),
                "icon_resources": [
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
                "other_resources": [(24, 1, manifest_xml)],
                "copyright": "© %s %s" % (strftime("%Y"), author),
                "description": desc,
            }
        )
        for script, desc in [
            script_desc2
            for script_desc2 in scripts
            if script2pywname(script_desc2[0]) in console_scripts
        ]
    ]

    # Programs without GUI
    attrs["console"].append(
        Target(
            **{
                "script": os.path.join(
                    tmp_scripts_dir, appname + "-eeColor-to-madVR-converter"
                ),
                "icon_resources": [
                    (
                        1,
                        os.path.join(
                            pydir, "theme", "icons", appname + "-3DLUT-maker.ico"
                        ),
                    )
                ],
                "other_resources": [(24, 1, manifest_xml)],
                "copyright": "© %s %s" % (strftime("%Y"), author),
                "description": "Convert eeColor 65^3 to madVR 256^3 3D LUT "
                "(video levels in, video levels out)",
            }
        )
    )

    dist_dir = os.path.join(
        pydir,
        "..",
        "dist",
        f"py2exe.{get_platform()}-py{sys.version_info[0]}.{sys.version_info[1]}",
        f"{name}-{version}",
    )
    os.makedirs(dist_dir, exist_ok=True)
    attrs["options"] = {
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
            "bundle_files": 3,  # if wx.VERSION >= (2, 8, 10, 1) else 1,
            "compressed": 1,
            "optimize": 0,  # 0 = don’t optimize (generate .pyc)
            # 1 = normal optimization (like python -O)
            # 2 = extra optimization (like python -OO)
        }
    }
    if debug:
        attrs["options"]["py2exe"].update(
            {"bundle_files": 3, "compressed": 0, "optimize": 0, "skip_archive": 1}
        )
    if setuptools:
        attrs["setup_requires"] = ["py2exe"]
    attrs["zipfile"] = os.path.join("lib", "library.zip")

    # To have a working sdist and bdist_rpm when using distutils,
    # we go to the length of generating MANIFEST.in from scratch everytime,
    # using the information available from setup.
    manifest_in = ["# This file will be re-generated by setup.py - do not edit"]
    manifest_in.extend(
        [
            "include LICENSE.txt",
            "include MANIFEST",
            "include MANIFEST.in",
            "include README.html",
            "include README-fr.html",
            "include CHANGES.html",
            f"include {name}*.pyw",
            f"include {name}-*.pyw",
            f"include {name}-*.py",
            "include use-distutils",
        ]
    )
    manifest_in.append("include " + os.path.basename(sys.argv[0]))
    manifest_in.append(
        "include " + os.path.splitext(os.path.basename(sys.argv[0]))[0] + ".cfg"
    )
    for _datadir, datafiles in attrs.get("data_files", []):
        for datafile in datafiles:
            manifest_in.append(
                "include {}".format(
                    relpath(os.path.sep.join(datafile.split("/")), source_dir)
                    or datafile
                )
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
        for obj in attrs.get("package_data", {}).get(pkg, []):
            print(f"obj: {obj}")
            manifest_in.append("include " + os.path.sep.join([pkgdir] + obj.split("/")))
    for pymod in attrs.get("py_modules", []):
        manifest_in.append("include {}".format(os.path.join(*pymod.split("."))))
    manifest_in.append(
        "include {}".format(os.path.join(name, "theme", "theme-info.txt"))
    )
    manifest_in.append(
        "recursive-include {} {} {}".format(
            os.path.join(name, "theme", "icons"), "*.icns", "*.ico"
        )
    )
    manifest_in.append("include {}".format(os.path.join("man", "*.1")))
    manifest_in.append("recursive-include misc *")
    # if skip_instrument_conf_files:
    #     manifest_in.extend(
    #         [
    #             "exclude misc/Argyll",
    #             "exclude misc/*.rules",
    #             "exclude misc/*.usermap",
    #         ]
    #     )
    manifest_in.append("include {}".format(os.path.join("screenshots", "*.png")))
    manifest_in.append("include {}".format(os.path.join("scripts", "*")))
    manifest_in.append("include {}".format(os.path.join("tests", "*")))
    manifest_in.append("recursive-include theme *")
    manifest_in.append("recursive-include util *.cmd *.py *.sh")
    manifest_in.append("global-exclude *~")
    manifest_in.append("global-exclude *.backup")
    manifest_in.append("global-exclude *.bak")
    if not dry_run:
        manifest = open("MANIFEST.in", "w")
        manifest.write("\n".join(manifest_in))
        manifest.close()
        if os.path.exists("MANIFEST"):
            os.remove("MANIFEST")

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

    shutil.copy(
        os.path.join(dist_dir, f"python{sys.version_info[0]}{sys.version_info[1]}.dll"),
        os.path.join(
            dist_dir, "lib", f"python{sys.version_info[0]}{sys.version_info[1]}.dll"
        ),
    )

    from vc90crt import name as vc90crt_name, vc90crt_copy_files

    vc90crt_copy_files(dist_dir)
    vc90crt_copy_files(os.path.join(dist_dir, "lib"))


if __name__ == "__main__":
    build_py2exe()
