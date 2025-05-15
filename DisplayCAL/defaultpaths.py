import os
import sys

if sys.platform not in ("darwin", "win32"):
    # Linux
    import gettext

    LOCALEDIR = os.path.join(sys.prefix, "share", "locale")

elif sys.platform == "win32":
    try:
        from win32comext.shell.shell import SHGetSpecialFolderPath
        from win32comext.shell.shellcon import (
            CSIDL_APPDATA,
            CSIDL_COMMON_APPDATA,
            CSIDL_COMMON_PROGRAMS,
            CSIDL_COMMON_STARTUP,
            CSIDL_LOCAL_APPDATA,
            CSIDL_PROFILE,
            CSIDL_PROGRAM_FILES_COMMON,
            CSIDL_PROGRAMS,
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
            """Ctypes wrapper around shell32.SHGetSpecialFolderPathW"""
            buffer = ctypes.create_unicode_buffer("\0" * MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buffer, nFolder, create)
            return buffer.value


from DisplayCAL.util_os import expanduseru, expandvarsu, getenvu

HOME = expanduseru("~")
if sys.platform == "win32":
    # Always specify create=1 for SHGetSpecialFolderPath so we don't get an
    # exception if the folder does not yet exist
    try:
        LIBRARY_HOME = APPDATA = SHGetSpecialFolderPath(0, CSIDL_APPDATA, 1)
    except Exception as exception:
        raise Exception(
            f"FATAL - Could not get/create user application data folder: {exception}"
        ) from exception
    try:
        LOCALAPPDATA = SHGetSpecialFolderPath(0, CSIDL_LOCAL_APPDATA, 1)
    except Exception:
        LOCALAPPDATA = os.path.join(APPDATA, "Local")
    CACHE = LOCALAPPDATA
    # Argyll CMS uses ALLUSERSPROFILE for local system wide app related data
    # Note: On Windows Vista and later, ALLUSERSPROFILE and COMMON_APPDATA
    # are actually the same ('C:\ProgramData'), but under Windows XP the former
    # points to 'C:\Documents and Settings\All Users' while COMMON_APPDATA
    # points to 'C:\Documents and Settings\All Users\Application Data'
    ALLUSERSPROFILE = getenvu("ALLUSERSPROFILE")
    if ALLUSERSPROFILE:
        COMMONAPPDATA = [ALLUSERSPROFILE]
    else:
        try:
            COMMONAPPDATA = [SHGetSpecialFolderPath(0, CSIDL_COMMON_APPDATA, 1)]
        except Exception as exception:
            raise Exception(
                "FATAL - Could not get/create common application data folder: "
                f"{exception}"
            ) from exception
    LIBRARY = COMMONAPPDATA[0]
    try:
        COMMON_PROGRAM_FILES = SHGetSpecialFolderPath(0, CSIDL_PROGRAM_FILES_COMMON, 1)
    except Exception as exception:
        raise Exception(
            f"FATAL - Could not get/create common program files folder: {exception}"
        ) from exception
    try:
        AUTOSTART = SHGetSpecialFolderPath(0, CSIDL_COMMON_STARTUP, 1)
    except Exception:
        AUTOSTART = None
    try:
        AUTOSTART_HOME = SHGetSpecialFolderPath(0, CSIDL_STARTUP, 1)
    except Exception:
        AUTOSTART_HOME = None
    try:
        ICCPROFILES = [
            os.path.join(
                SHGetSpecialFolderPath(0, CSIDL_SYSTEM), "spool", "drivers", "color"
            )
        ]
    except Exception as exception:
        raise Exception(
            f"FATAL - Could not get system folder: {exception}"
        ) from exception
    ICCPROFILES_HOME = ICCPROFILES
    try:
        PROGRAMS = SHGetSpecialFolderPath(0, CSIDL_PROGRAMS, 1)
    except Exception:
        PROGRAMS = None
    try:
        COMMON_PROGRAMS = [SHGetSpecialFolderPath(0, CSIDL_COMMON_PROGRAMS, 1)]
    except Exception:
        COMMON_PROGRAMS = []
elif sys.platform == "darwin":
    LIBRARY_HOME = os.path.join(HOME, "Library")
    CACHE = os.path.join(LIBRARY_HOME, "Caches")
    LIBRARY = os.path.join(os.path.sep, "Library")
    PREFS = os.path.join(os.path.sep, "Library", "Preferences")
    PREFS_HOME = os.path.join(HOME, "Library", "Preferences")
    APPDATA = os.path.join(HOME, "Library", "Application Support")
    COMMONAPPDATA = [os.path.join(os.path.sep, "Library", "Application Support")]
    AUTOSTART = AUTOSTART_HOME = None
    ICCPROFILES = [
        os.path.join(os.path.sep, "Library", "ColorSync", "Profiles"),
        os.path.join(os.path.sep, "System", "Library", "ColorSync", "Profiles"),
    ]
    ICCPROFILES_HOME = [os.path.join(HOME, "Library", "ColorSync", "Profiles")]
    PROGRAMS = os.path.join(os.path.sep, "Applications")
    COMMON_PROGRAMS = []
else:
    # Linux

    class XDG:
        # TODO: This class is a complete hack and it should be refactored,
        #       and no hacks like relaying on `locals()` should be used.

        CACHE_HOME = getenvu("XDG_CACHE_HOME", expandvarsu("$HOME/.cache"))
        CONFIG_HOME = getenvu("XDG_CONFIG_HOME", expandvarsu("$HOME/.config"))
        CONFIG_DIR_DEFAULT = "/etc/xdg"
        CONFIG_DIRS = list(
            map(
                os.path.normpath,
                getenvu("XDG_CONFIG_DIRS", CONFIG_DIR_DEFAULT).split(os.pathsep),
            )
        )
        if CONFIG_DIR_DEFAULT not in CONFIG_DIRS:
            CONFIG_DIRS.append(CONFIG_DIR_DEFAULT)
        DATA_HOME_DEFAULT = expandvarsu("$HOME/.local/share")
        DATA_HOME = getenvu("XDG_DATA_HOME", DATA_HOME_DEFAULT)
        DATA_DIRS_DEFAULT = "/usr/local/share:/usr/share:/var/lib"
        DATA_DIRS = list(
            map(
                os.path.normpath,
                getenvu("XDG_DATA_DIRS", DATA_DIRS_DEFAULT).split(os.pathsep),
            )
        )
        DATA_DIRS.extend(
            list(
                filter(
                    lambda data_dir, data_dirs=DATA_DIRS: data_dir not in data_dirs,
                    DATA_DIRS_DEFAULT.split(os.pathsep),
                )
            )
        )

        @staticmethod
        def set_translation(obj):
            locale_dir = LOCALEDIR

            if not os.path.isdir(locale_dir):
                for path in XDG.DATA_DIRS:
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
            except OSError as exception:
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

            for config_dir in [XDG.CONFIG_HOME] + XDG.CONFIG_DIRS:
                path = os.path.join(config_dir, filename)
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
                with open(path) as f:
                    for key, value in XDG.config_file_parser(f):
                        fn(key, value)
            except OSError as exception:
                print(f"XDG: Couldn't read '{path}':", exception)
                return False
            return True

    for name in dir(XDG):
        attr = getattr(XDG, name)
        if isinstance(attr, (str, list)):
            # TODO: Using `locals()` is not a good practice.
            locals()[f"XDG_{name}"] = attr
    del name, attr

    CACHE = XDG.CACHE_HOME
    LIBRARY_HOME = APPDATA = XDG.DATA_HOME
    COMMONAPPDATA = XDG.DATA_DIRS
    LIBRARY = COMMONAPPDATA[0]
    AUTOSTART = None
    for dir_ in XDG.CONFIG_DIRS:
        if os.path.isdir(dir_):
            AUTOSTART = os.path.join(dir_, "autostart")
            break
    if not AUTOSTART:
        AUTOSTART = os.path.join(XDG.CONFIG_DIR_DEFAULT, "autostart")
    AUTOSTART_HOME = os.path.join(XDG.CONFIG_HOME, "autostart")
    ICCPROFILES = []
    for dir_ in XDG.DATA_DIRS:
        if os.path.isdir(dir_):
            ICCPROFILES.append(os.path.join(dir_, "color", "icc"))
    ICCPROFILES.append("/var/lib/color")
    ICCPROFILES_HOME = [
        os.path.join(XDG.DATA_HOME, "color", "icc"),
        os.path.join(XDG.DATA_HOME, "icc"),
        expandvarsu("$HOME/.color/icc"),
    ]
    PROGRAMS = os.path.join(XDG.DATA_HOME, "applications")
    COMMON_PROGRAMS = [os.path.join(dir_, "applications") for dir_ in XDG.DATA_DIRS]

if sys.platform in ("darwin", "win32"):
    ICCPROFILES_DISPLAY = ICCPROFILES
    ICCPROFILES_DISPLAY_HOME = ICCPROFILES_HOME
else:
    ICCPROFILES_DISPLAY = [
        os.path.join(dir_, "devices", "display") for dir_ in ICCPROFILES
    ]
    ICCPROFILES_DISPLAY_HOME = [
        os.path.join(dir_, "devices", "display") for dir_ in ICCPROFILES_HOME
    ]
    del dir_
