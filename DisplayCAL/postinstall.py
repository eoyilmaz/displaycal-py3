"""This module handles post-installation and uninstallation tasks for
DisplayCAL across different platforms (Windows, macOS, and Linux). It includes
functions to create shortcuts, manage installed files, and update system
resources such as icons and desktop menu entries.
"""

import contextlib
import os
import shutil
import sys
import traceback
from io import StringIO
from os.path import basename, splitext
from subprocess import call

from DisplayCAL.meta import NAME
from DisplayCAL.util_os import safe_glob, which

recordfile_name = "INSTALLED_FILES"

if sys.stdout and hasattr(sys.stdout, "isatty") and not sys.stdout.isatty():
    sys.stdout = StringIO()

if sys.platform == "win32":
    if "create_shortcut" not in globals():
        # this function is only available within bdist_wininst installers
        try:
            import win32con
            from pythoncom import (
                CLSCTX_INPROC_SERVER,
                CoCreateInstance,
                IID_IPersistFile,
            )
            from win32com.shell import shell
        except ImportError:

            def create_shortcut(*args):
                pass

        else:

            def create_shortcut(*args):
                shortcut = CoCreateInstance(
                    shell.CLSID_ShellLink,
                    None,
                    CLSCTX_INPROC_SERVER,
                    shell.IID_IShellLink,
                )
                shortcut.SetPath(args[0])
                shortcut.SetDescription(args[1])
                if len(args) > 3:
                    shortcut.SetArguments(args[3])
                if len(args) > 4:
                    shortcut.SetWorkingDirectory(args[4])
                if len(args) > 5:
                    shortcut.SetIconLocation(args[5], args[6] if len(args) > 6 else 0)
                shortcut.SetShowCmd(win32con.SW_SHOWNORMAL)
                shortcut.QueryInterface(IID_IPersistFile).Save(args[2], 0)

    if "directory_created" not in globals():
        # this function is only available within bdist_wininst installers

        def directory_created(path):
            pass

    if "file_created" not in globals():
        # this function is only available within bdist_wininst installers
        try:
            import win32api
        except ImportError:

            def file_created(path):
                pass

        else:

            def file_created(path):
                if not os.path.exists(recordfile_name):
                    return
                installed_files = []
                if os.path.exists(recordfile_name):
                    with open(recordfile_name) as recordfile:
                        installed_files.extend(line.rstrip("\n") for line in recordfile)
                try:
                    path.encode("ASCII")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    # the contents of the record file used by distutils
                    # must be ASCII GetShortPathName allows us to avoid
                    # any issues with encoding because it returns the
                    # short path as 7-bit string (while still being a
                    # valid path)
                    path = win32api.GetShortPathName(path)
                installed_files.append(path)
                with open(recordfile_name, "w") as recordfile:
                    recordfile.write("\n".join(installed_files))

    if "get_special_folder_path" not in globals():
        # this function is only available within bdist_wininst installers
        try:
            from win32com.shell import shell, shellcon
        except ImportError:

            def get_special_folder_path(csidl_string):
                pass

        else:

            def get_special_folder_path(csidl_string):
                return shell.SHGetSpecialFolderPath(
                    0, getattr(shellcon, csidl_string), 1
                )


def postinstall_macos(prefix=None):
    """Do postinstall actions for macOS."""
    # TODO: implement


def postinstall_windows(prefix):
    """Do postinstall actions for Windows."""
    # assume we are running from bdist_wininst installer if prefix is None,
    # otherwise assume we are running from source dir, or from install dir
    modpath = os.path.dirname(os.path.abspath(__file__)) if prefix is None else prefix
    if not os.path.exists(modpath):
        print("warning - '{}' not found".format(modpath.encode("MBCS", "replace")))
        return

    if os.path.exists(recordfile_name):
        irecordfile_name = os.path.join(modpath, "INSTALLED_FILES")
        with open(irecordfile_name, "w"):  # touch create the file
            pass
        file_created(irecordfile_name)
        shutil.copy2(recordfile_name, irecordfile_name)

    mainicon = os.path.join(modpath, "theme", "icons", f"{NAME}.ico")
    if not os.path.exists(mainicon):
        print("warning - '{}' not found".format(mainicon.encode("MBCS", "replace")))
        return

    try:
        startmenu_programs_common = get_special_folder_path("CSIDL_COMMON_PROGRAMS")
        startmenu_programs = get_special_folder_path("CSIDL_PROGRAMS")
        startmenu_common = get_special_folder_path("CSIDL_COMMON_STARTMENU")
        startmenu = get_special_folder_path("CSIDL_STARTMENU")
    except OSError:
        traceback.print_exc()
        return

    filenames = [
        filename
        for filename in safe_glob(os.path.join(sys.prefix, "Scripts", f"{NAME}*"))
        if not filename.endswith("-script.py")
        and not filename.endswith("-script.pyw")
        and not filename.endswith(".manifest")
        and not filename.endswith(".pyc")
        and not filename.endswith(".pyo")
        and not filename.endswith("_postinstall.py")
    ] + ["LICENSE.txt", "README.html", "Uninstall"]
    installed_shortcuts = []
    for path in (startmenu_programs_common, startmenu_programs):
        if not path:
            continue
        grppath = os.path.join(path, NAME)
        if path == startmenu_programs:
            group = os.path.relpath(grppath, startmenu)
        else:
            group = os.path.relpath(grppath, startmenu_common)

        if not os.path.exists(grppath):
            with contextlib.suppress(Exception):
                os.makedirs(grppath)
                # maybe insufficient privileges?

        if os.path.exists(grppath):
            print(
                ("Created start menu group '{}' in {}").format(
                    NAME,
                    (
                        str(path, "MBCS", "replace")
                        if not isinstance(path, str)
                        else path
                    ).encode("MBCS", "replace"),
                )
            )
        else:
            print(
                ("Failed to create start menu group '{}' in {}").format(
                    NAME,
                    (
                        str(path, "MBCS", "replace")
                        if not isinstance(path, str)
                        else path
                    ).encode("MBCS", "replace"),
                )
            )
            continue
        directory_created(grppath)
        for filename in filenames:
            lnkname = splitext(basename(filename))[0]
            lnkpath = os.path.join(grppath, f"{lnkname}.lnk")
            if os.path.exists(lnkpath):
                try:
                    os.remove(lnkpath)
                except Exception:
                    # maybe insufficient privileges?
                    print(
                        ("Failed to create start menu entry '{}' in {}").format(
                            lnkname,
                            (
                                str(grppath, "MBCS", "replace")
                                if not isinstance(grppath, str)
                                else grppath
                            ).encode("MBCS", "replace"),
                        )
                    )
                    continue
            if not os.path.exists(lnkpath):
                if lnkname != "Uninstall":
                    tgtpath = os.path.join(modpath, filename)
                try:
                    if lnkname == "Uninstall":
                        uninstaller = os.path.join(sys.prefix, f"Remove{NAME}.exe")
                        if os.path.exists(uninstaller):
                            create_shortcut(
                                uninstaller,
                                lnkname,
                                lnkpath,
                                f'-u "{os.path.join(sys.prefix, NAME)}-wininst.log"',
                                sys.prefix,
                                os.path.join(
                                    modpath,
                                    "theme",
                                    "icons",
                                    f"{NAME}-uninstall.ico",
                                ),
                            )
                        else:
                            # When running from a
                            # bdist_wininst or bdist_msi
                            # installer, sys.executable
                            # points to the installer
                            # executable, not python.exe
                            create_shortcut(
                                os.path.join(sys.prefix, "python.exe"),
                                lnkname,
                                lnkpath,
                                '"{}" uninstall --record="{}"'.format(
                                    os.path.join(modpath, "setup.py"),
                                    os.path.join(modpath, "INSTALLED_FILES"),
                                ),
                                sys.prefix,
                                os.path.join(
                                    modpath,
                                    "theme",
                                    "icons",
                                    f"{NAME}-uninstall.ico",
                                ),
                            )
                    elif lnkname.startswith(NAME):
                        # When running from a
                        # bdist_wininst or bdist_msi
                        # installer, sys.executable
                        # points to the installer
                        # executable, not python.exe
                        icon = os.path.join(
                            modpath,
                            "theme",
                            "icons",
                            f"{lnkname}.ico",
                        )
                        icon = mainicon if not os.path.isfile(icon) else icon
                        if filename.endswith(".exe"):
                            exe = filename
                            args = ""
                        else:
                            exe = os.path.join(sys.prefix, "pythonw.exe")
                            args = f'"{tgtpath}"'
                        create_shortcut(
                            exe,
                            lnkname,
                            lnkpath,
                            args,
                            modpath,
                            icon,
                        )
                    else:
                        create_shortcut(tgtpath, lnkname, lnkpath, "", modpath)
                except Exception:
                    # maybe insufficient privileges?
                    print(
                        ("Failed to create start menu entry '{}' in {}").format(
                            lnkname,
                            (
                                str(grppath, "MBCS", "replace")
                                if not isinstance(grppath, str)
                                else grppath
                            ).encode("MBCS", "replace"),
                        )
                    )
                    continue
                print(
                    ("Installed start menu entry '{}' to {}").format(
                        lnkname,
                        (
                            str(group, "MBCS", "replace")
                            if not isinstance(group, str)
                            else group
                        ).encode("MBCS", "replace"),
                    )
                )
            file_created(lnkpath)
            installed_shortcuts.append(filename)
        if installed_shortcuts == filenames:
            break


def postinstall_linux(prefix=None):
    """Do postinstall actions for Linux."""
    # Linux/Unix
    if prefix is None:
        prefix = sys.prefix
    if which("touch"):
        call(["touch", "--no-create", f"{prefix}/share/icons/hicolor"])  # noqa: S607
    if which("xdg-icon-resource"):
        # print("installing icon resources...")
        # for size in [16, 22, 24, 32, 48, 256]:
        # call([
        #     "xdg-icon-resource",
        #     "install",
        #     "--noupdate",
        #     "--novendor",
        #     "--size",
        #     str(size),
        #     f"{prefix}/share/{name}/theme/icons/{size}x{size}/{name}.png"
        # ])
        call(["xdg-icon-resource", "forceupdate"])  # noqa: S607
    if which("xdg-desktop-menu"):
        # print("installing desktop menu entry...")
        # call([
        #     "xdg-desktop-menu",
        #     "install",
        #     "--novendor",
        #     f"{prefix}/share/{name}/{name}.desktop"
        # ])
        call(["xdg-desktop-menu", "forceupdate"])  # noqa: S607


def postinstall(prefix=None):
    if sys.platform == "darwin":
        postinstall_macos()
    elif sys.platform == "win32":
        postinstall_windows(prefix)
    else:
        postinstall_linux(prefix)


def postuninstall(prefix=None):
    if sys.platform == "darwin":
        # TODO: implement
        pass
    elif sys.platform == "win32":
        # nothing to do
        pass
    else:
        # Linux/Unix
        if prefix is None:
            prefix = sys.prefix
        if which("xdg-desktop-menu"):
            # print("uninstalling desktop menu entry...")
            # call(["xdg-desktop-menu", "uninstall", prefix +
            # (f"/share/applications/{name}.desktop")])
            call(["xdg-desktop-menu", "forceupdate"])  # noqa: S607
        if which("xdg-icon-resource"):
            # print("uninstalling icon resources...")
            # for size in [16, 22, 24, 32, 48, 256]:
            # call(["xdg-icon-resource", "uninstall", "--noupdate", "--size",
            # str(size), name])
            call(["xdg-icon-resource", "forceupdate"])  # noqa: S607


def main():
    prefix = None
    for arg in sys.argv[1:]:
        arg = arg.split("=")
        if len(arg) == 2 and arg[0] == "--prefix":
            prefix = arg[1]
    try:
        if "-remove" in sys.argv[1:]:
            postuninstall(prefix)
        else:
            postinstall(prefix)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
