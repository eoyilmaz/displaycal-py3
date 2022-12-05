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
        from win32com.shell.shell import SHGetSpecialFolderPath
        from win32com.shell.shellcon import (
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


def get_known_folder_path(folderid, user=True):
    """Get known folder path.

    Uses GetKnownFolderPath API on Windows Vista and later, and XDG user dirs
    on Linux.

    Falls back to ~/<folderid> in all other cases.

    folderid can be "Desktop", "Downloads", "Documents", "Music", "Pictures",
    "Public", "Templates", or "Videos".

    user   Return user folder instead of common (Windows) or default (Linux)

    """
    folder_path = os.path.join(home, folderid)
    if sys.platform == "win32" and sys.getwindowsversion() >= (6,):
        # Windows Vista or newer
        from DisplayCAL import win_knownpaths

        try:
            folder_path = win_knownpaths.get_path(
                getattr(win_knownpaths.FOLDERID, folderid),
                getattr(win_knownpaths.UserHandle, "current" if user else "common"),
            )
        except Exception:
            print("Warning: Could not get known folder %r" % folderid)
    elif sys.platform not in ("darwin", "win32"):
        # Linux
        user_dir = folderid
        folderid = (
            {"Downloads": folderid[:-1], "Public": folderid + "share"}
            .get(folderid, folderid)
            .upper()
        )
        if folderid != "DESKTOP" or XDG.UserDirs.enabled:
            user_dir = XDG.UserDirs.default_dirs.get(folderid)
        if user:
            user_dir = XDG.UserDirs.user_dirs.get(folderid, user_dir)
        if user_dir:
            folder_path = os.path.join(home, user_dir)
        if (
            folderid != "DESKTOP"
            and (
                not user_dir
                or (not os.path.isdir(folder_path) and not XDG.UserDirs.enabled)
            )
        ) or not waccess(folder_path, os.W_OK):
            folder_path = home
    return folder_path


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

        class _UserDirs(object):

            GETTEXT_PACKAGE = "xdg-user-dirs"

            enabled = True
            filename_encoding = "UTF-8"
            default_dirs = {}
            user_dirs = {}

            _initialized = False

            def __getattribute__(self, name):
                if name != "init" and not object.__getattribute__(self, "_initialized"):
                    object.__getattribute__(self, "init")()
                return object.__getattribute__(self, name)

            def load_config(self, path):
                def fn(key, value):
                    if key == "enabled":
                        self.enabled = XDG.is_true(value)
                    elif key == "filename_encoding":
                        value = value.upper()
                        if value == "LOCALE":
                            current_locale = locale.getlocale()
                            locale.setlocale(locale.LC_ALL, "")
                            self.filename_encoding = locale.nl_langinfo(locale.CODESET)
                            locale.setlocale(locale.LC_ALL, current_locale)
                        else:
                            self.filename_encoding = value

                return XDG.process_config_file(path, fn)

            def load_all_configs(self):
                for path in reversed(XDG.get_config_files("user-dirs.conf")):
                    self.load_config(path)

            def load_default_dirs(self):
                paths = XDG.get_config_files("user-dirs.defaults")
                if not paths:
                    print("XDG.UserDirs: No default user directories")
                    return False

                def fn(name, path):
                    self.default_dirs[name] = self.localize_path_name(path)

                return XDG.process_config_file(paths[0], fn)

            def load_user_dirs(self):
                path = os.path.join(XDG.config_home, "user-dirs.dirs")
                if not path or not os.path.isfile(path):
                    return False

                def fn(key, value):
                    if (
                        key.startswith("XDG_")
                        and key.endswith("_DIR")
                        and value.startswith('"')
                        and value.endswith('"')
                    ):
                        name = key[4:-4]
                        if not name:
                            return
                        value = value.strip('"')
                        if value.startswith("$HOME"):
                            value = value[5:]
                            if value.startswith("/"):
                                value = value[1:]
                            elif value:
                                # Not ending after $HOME, nor followed by slash.
                                # Ignore
                                return
                        elif not value.startswith("/"):
                            return
                        self.user_dirs[name] = XDG.shell_unescape(value).decode(
                            "UTF-8", "ignore"
                        )

                return XDG.process_config_file(path, fn)

            def localize_path_name(self, path):
                elements = path.split(os.path.sep)

                for i, element in enumerate(elements):
                    elements[i] = self.translation.ugettext(element)

                return os.path.join(*elements)

            def init(self):
                self._initialized = True

                XDG.set_translation(self)

                self.load_all_configs()
                try:
                    codecs.lookup(self.filename_encoding)
                except LookupError:
                    print(
                        "XDG.UserDirs: Can't convert from UTF-8 to",
                        self.filename_encoding,
                    )
                    return False

                self.load_default_dirs()
                self.load_user_dirs()

        UserDirs = _UserDirs()

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
