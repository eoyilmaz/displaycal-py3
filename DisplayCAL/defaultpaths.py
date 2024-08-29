# -*- coding: utf-8 -*-


import os
import sys

if sys.platform not in ("darwin", "win32"):
    # Linux
    import codecs
    import locale
    import gettext

    LOCALEDIR = os.path.join(sys.prefix, "share", "locale")

elif sys.platform == "win32":
    try:
        from win32comext.shell.shell import SHGetSpecialFolderPath
        from win32comext.shell.shellcon import (
            CSIDL_APPDATA,
            CSIDL_COMMON_APPDATA,
            CSIDL_COMMON_STARTUP,
            CSIDL_LOCAL_APPDATA,
            CSIDL_PROFILE,
            CSIDL_PROGRAMS,
            CSIDL_COMMON_PROGRAMS,
            CSIDL_PROGRAM_FILES_COMMON,
            CSIDL_STARTUP,
            CSIDL_SYSTEM,
        )
    except ImportError:
        import ctypes

        (
            CSIDL_APPDATA,
            CSIDL_COMMON_APPDATA,
            CSIDL_COMMON_STARTUP,
            CSIDL_LOCAL_APPDATA,
            CSIDL_PROFILE,
            CSIDL_PROGRAMS,
            CSIDL_COMMON_PROGRAMS,
            CSIDL_PROGRAM_FILES_COMMON,
            CSIDL_STARTUP,
            CSIDL_SYSTEM,
        ) = (26, 35, 24, 28, 40, 43, 2, 23, 7, 37)
        MAX_PATH = 260

        def SHGetSpecialFolderPath(hwndOwner, nFolder, create=0):
            """ctypes wrapper around shell32.SHGetSpecialFolderPathW"""
            buffer = ctypes.create_unicode_buffer("\0" * MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buffer, nFolder, create)
            return buffer.value


from DisplayCAL.util_os import expanduseru, expandvarsu, getenvu, waccess


home = expanduseru("~")
if sys.platform == "win32":
    # Always specify create=1 for SHGetSpecialFolderPath so we don't get an
    # exception if the folder does not yet exist
    try:
        library_home = appdata = SHGetSpecialFolderPath(0, CSIDL_APPDATA, 1)
    except Exception as exception:
        raise Exception(
            "FATAL - Could not get/create user application data folder: %s" % exception
        )
    try:
        localappdata = SHGetSpecialFolderPath(0, CSIDL_LOCAL_APPDATA, 1)
    except Exception:
        localappdata = os.path.join(appdata, "Local")
    cache = localappdata
    # Argyll CMS uses ALLUSERSPROFILE for local system wide app related data
    # Note: On Windows Vista and later, ALLUSERSPROFILE and COMMON_APPDATA
    # are actually the same ('C:\ProgramData'), but under Windows XP the former
    # points to 'C:\Documents and Settings\All Users' while COMMON_APPDATA
    # points to 'C:\Documents and Settings\All Users\Application Data'
    allusersprofile = getenvu("ALLUSERSPROFILE")
    if allusersprofile:
        commonappdata = [allusersprofile]
    else:
        try:
            commonappdata = [SHGetSpecialFolderPath(0, CSIDL_COMMON_APPDATA, 1)]
        except Exception as exception:
            raise Exception(
                "FATAL - Could not get/create common application data folder: %s"
                % exception
            )
    library = commonappdata[0]
    try:
        commonprogramfiles = SHGetSpecialFolderPath(0, CSIDL_PROGRAM_FILES_COMMON, 1)
    except Exception as exception:
        raise Exception(
            "FATAL - Could not get/create common program files folder: %s" % exception
        )
    try:
        autostart = SHGetSpecialFolderPath(0, CSIDL_COMMON_STARTUP, 1)
    except Exception:
        autostart = None
    try:
        autostart_home = SHGetSpecialFolderPath(0, CSIDL_STARTUP, 1)
    except Exception:
        autostart_home = None
    try:
        iccprofiles = [
            os.path.join(
                SHGetSpecialFolderPath(0, CSIDL_SYSTEM), "spool", "drivers", "color"
            )
        ]
    except Exception as exception:
        raise Exception("FATAL - Could not get system folder: %s" % exception)
    iccprofiles_home = iccprofiles
    try:
        programs = SHGetSpecialFolderPath(0, CSIDL_PROGRAMS, 1)
    except Exception:
        programs = None
    try:
        commonprograms = [SHGetSpecialFolderPath(0, CSIDL_COMMON_PROGRAMS, 1)]
    except Exception:
        commonprograms = []
elif sys.platform == "darwin":
    library_home = os.path.join(home, "Library")
    cache = os.path.join(library_home, "Caches")
    library = os.path.join(os.path.sep, "Library")
    prefs = os.path.join(os.path.sep, "Library", "Preferences")
    prefs_home = os.path.join(home, "Library", "Preferences")
    appdata = os.path.join(home, "Library", "Application Support")
    commonappdata = [os.path.join(os.path.sep, "Library", "Application Support")]
    autostart = autostart_home = None
    iccprofiles = [
        os.path.join(os.path.sep, "Library", "ColorSync", "Profiles"),
        os.path.join(os.path.sep, "System", "Library", "ColorSync", "Profiles"),
    ]
    iccprofiles_home = [os.path.join(home, "Library", "ColorSync", "Profiles")]
    programs = os.path.join(os.path.sep, "Applications")
    commonprograms = []
else:
    # Linux

    class XDG:

        cache_home = getenvu("XDG_CACHE_HOME", expandvarsu("$HOME/.cache"))
        config_home = getenvu("XDG_CONFIG_HOME", expandvarsu("$HOME/.config"))
        config_dir_default = "/etc/xdg"
        config_dirs = list(
            map(
                os.path.normpath,
                getenvu("XDG_CONFIG_DIRS", config_dir_default).split(os.pathsep),
            )
        )
        if config_dir_default not in config_dirs:
            config_dirs.append(config_dir_default)
        data_home_default = expandvarsu("$HOME/.local/share")
        data_home = getenvu("XDG_DATA_HOME", data_home_default)
        data_dirs_default = "/usr/local/share:/usr/share:/var/lib"
        data_dirs = list(
            map(
                os.path.normpath,
                getenvu("XDG_DATA_DIRS", data_dirs_default).split(os.pathsep),
            )
        )
        data_dirs.extend(
            list(
                filter(
                    lambda data_dir, data_dirs=data_dirs: data_dir not in data_dirs,
                    data_dirs_default.split(os.pathsep),
                )
            )
        )

        @staticmethod
        def set_translation(obj):
            locale_dir = LOCALEDIR

            if not os.path.isdir(locale_dir):
                for path in XDG.data_dirs:
                    path = os.path.join(path, "locale")
                    if os.path.isdir(path):
                        locale_dir = path
                        break

            # codeset is deprecated with python 3.11
            try:
                obj.translation = gettext.translation(
                    obj.GETTEXT_PACKAGE, locale_dir, codeset="UTF-8"
                )
            except TypeError:
                try:
                    obj.translation = gettext.translation(
                        obj.GETTEXT_PACKAGE, locale_dir
                    )
                except FileNotFoundError as exc:
                    print("XDG:", exc)
                    obj.translation = gettext.NullTranslations()
                    return False
            except IOError as exception:
                print("XDG:", exception)
                obj.translation = gettext.NullTranslations()
                return False
            return True

        @staticmethod
        def is_true(s):
            return s == "1" or s.startswith("True") or s.startswith("true")

        @staticmethod
        def get_config_files(filename):
            paths = []

            for xdg_config_dir in [XDG.config_home] + XDG.config_dirs:
                path = os.path.join(xdg_config_dir, filename)
                if os.path.isfile(path):
                    paths.append(path)

            return paths

        @staticmethod
        def shell_unescape(s):
            a = [c for i, c in enumerate(s) if c != "\\" or len(s) <= i + 1]
            return "".join(a)

        @staticmethod
        def config_file_parser(f):
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                yield tuple(s.strip() for s in line.split("=", 1))

        @staticmethod
        def process_config_file(path, fn):
            try:
                with open(path, "r") as f:
                    for key, value in XDG.config_file_parser(f):
                        fn(key, value)
            except EnvironmentError as exception:
                print("XDG: Couldn't read '%s':" % path, exception)
                return False
            return True

    for name in dir(XDG):
        attr = getattr(XDG, name)
        if isinstance(attr, (str, list)):
            locals()["xdg_" + name] = attr
    del name, attr

    cache = XDG.cache_home
    library_home = appdata = XDG.data_home
    commonappdata = XDG.data_dirs
    library = commonappdata[0]
    autostart = None
    for dir_ in XDG.config_dirs:
        if os.path.isdir(dir_):
            autostart = os.path.join(dir_, "autostart")
            break
    if not autostart:
        autostart = os.path.join(XDG.config_dir_default, "autostart")
    autostart_home = os.path.join(XDG.config_home, "autostart")
    iccprofiles = []
    for dir_ in XDG.data_dirs:
        if os.path.isdir(dir_):
            iccprofiles.append(os.path.join(dir_, "color", "icc"))
    iccprofiles.append("/var/lib/color")
    iccprofiles_home = [
        os.path.join(XDG.data_home, "color", "icc"),
        os.path.join(XDG.data_home, "icc"),
        expandvarsu("$HOME/.color/icc"),
    ]
    programs = os.path.join(XDG.data_home, "applications")
    commonprograms = [os.path.join(dir_, "applications") for dir_ in XDG.data_dirs]
if sys.platform in ("darwin", "win32"):
    iccprofiles_display = iccprofiles
    iccprofiles_display_home = iccprofiles_home
else:
    iccprofiles_display = [
        os.path.join(dir_, "devices", "display") for dir_ in iccprofiles
    ]
    iccprofiles_display_home = [
        os.path.join(dir_, "devices", "display") for dir_ in iccprofiles_home
    ]
    del dir_
