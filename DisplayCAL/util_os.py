# -*- coding: utf-8 -*-

"""This module provides utility functions for operating system-related tasks."""

import builtins
import ctypes
import errno
import fnmatch
import glob
import importlib
import os
import pathlib
import re
import shutil
import struct
import subprocess as sp
import sys
import tempfile
import time

from DisplayCAL.encoding import get_encodings

if sys.platform == "win32":
    from win32file import GetFileAttributes
    from winioctlcon import FSCTL_GET_REPARSE_POINT
    import msvcrt
    import pywintypes
    import win32api
    import win32con
    import win32file
    import win32security
    import winerror

if sys.platform != "win32":
    # Linux
    import fcntl
    import grp
    import pwd

try:
    reloaded  # type: ignore
except NameError:
    # First import. All fine
    reloaded = 0
else:
    # Module is being reloaded. NOT recommended.
    reloaded += 1  # type: ignore
    import warnings

    warnings.warn(
        "Module {} is being reloaded. This is NOT recommended.".format(__name__),
        RuntimeWarning,
        stacklevel=2,
    )
    warnings.warn(
        "Implicitly reloading builtins",
        RuntimeWarning,
        stacklevel=2,
    )
    if sys.platform == "win32":
        importlib.reload(builtins)
    warnings.warn(
        "Implicitly reloading os",
        RuntimeWarning,
        stacklevel=2,
    )
    importlib.reload(os)
    warnings.warn(
        "Implicitly reloading os.path",
        RuntimeWarning,
        stacklevel=2,
    )
    importlib.reload(os.path)
    if sys.platform == "win32":
        warnings.warn(
            "Implicitly reloading win32api",
            RuntimeWarning,
            stacklevel=2,
        )
        importlib.reload(win32api)

# Cache used for safe_shell_filter() function
_cache = {}
_MAXCACHE = 100

FILE_ATTRIBUTE_REPARSE_POINT = 1024
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # Junction
IO_REPARSE_TAG_SYMLINK = 0xA000000C

fs_enc = get_encodings()[1]

_listdir = os.listdir


def setup_win32_long_paths():
    """Add support for long paths (> 260 chars) and retry ERROR_SHARING_VIOLATION."""

    def retry_sharing_violation_factory(fn, delay=0.25, maxretries=20):
        def retry_sharing_violation(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except WindowsError as exception:
                    if exception.winerror == winerror.ERROR_SHARING_VIOLATION:
                        if retries < maxretries:
                            retries += 1
                            time.sleep(delay)
                            continue
                    raise

        return retry_sharing_violation

    def make_win32_compatible_long_path_wrapper(fn):
        return lambda path, *args, **kwargs: fn(
            make_win32_compatible_long_path(path), *args, **kwargs
        )

    def make_win32_compatible_long_path_with_mode_wrapper(fn):
        return lambda path, mode=0o777, *args, **kwargs: fn(
            make_win32_compatible_long_path(path, 247), mode, *args, **kwargs
        )

    def make_win32_compatible_long_path_with_src_dst_wrapper(fn):
        return lambda src, dst, *args, **kwargs: fn(
            *[make_win32_compatible_long_path(path) for path in (src, dst)],
            *args,
            **kwargs,
        )

    builtins.open = make_win32_compatible_long_path_wrapper(builtins.open)
    os.access = make_win32_compatible_long_path_wrapper(os.access)
    os.path.exists = make_win32_compatible_long_path_wrapper(os.path.exists)
    os.path.isdir = make_win32_compatible_long_path_wrapper(os.path.isdir)
    os.path.isfile = make_win32_compatible_long_path_wrapper(os.path.isfile)
    os.listdir = make_win32_compatible_long_path_wrapper(os.listdir)
    os.lstat = make_win32_compatible_long_path_wrapper(os.lstat)
    os.mkdir = make_win32_compatible_long_path_with_mode_wrapper(os.mkdir)
    os.makedirs = make_win32_compatible_long_path_with_mode_wrapper(os.makedirs)
    os.remove = retry_sharing_violation_factory(
        make_win32_compatible_long_path_wrapper(os.remove)
    )
    os.rename = retry_sharing_violation_factory(
        make_win32_compatible_long_path_with_src_dst_wrapper(os.rename)
    )
    os.stat = make_win32_compatible_long_path_wrapper(os.stat)
    os.unlink = retry_sharing_violation_factory(
        make_win32_compatible_long_path_wrapper(os.unlink)
    )
    win32api.GetShortPathName = make_win32_compatible_long_path_wrapper(
        win32api.GetShortPathName
    )


if sys.platform == "win32":
    setup_win32_long_paths()
else:

    def listdir(path, *args, **kwargs):
        """
        List directory contents.

        This function lists the contents of the specified directory,
        filtering out undecodable filenames if the path is a string.

        Args:
            path (str): The path to the directory.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            list: A list of filenames in the directory.
        """
        paths = _listdir(path, *args, **kwargs)
        if isinstance(path, str):
            # Undecodable filenames will still be string objects.
            # Ignore them.
            paths = [path for path in paths if isinstance(path, str)]
        return paths

    os.listdir = listdir


def quote_args(args):
    """
    Quote commandline arguments where needed.

    It quotes all arguments that contain spaces or any of the characters
    ^!$%&()[]{}=;'+,`~

    Args:
        args: (list of str): List of commandline arguments to be quoted.

    Returns:
        list of str: List of quoted commandline arguments.
    """
    args_out = []
    for arg in args:
        if re.search(r"[\^!$%&()[\]{}=;'+,`~\s]", arg):
            arg = '"' + arg + '"'
        args_out.append(arg)
    return args_out


def dlopen(name, handle=None):
    """
    Load a shared library.

    Args:
        name (str): The name of the shared library.
        handle (int, optional): The handle of the shared library. Defaults to None.

    Returns:
        ctypes.CDLL: The loaded shared library.
    """
    try:
        return ctypes.CDLL(name, handle=handle)
    except Exception:
        pass


def find_library(pattern, arch=None):
    """
    Use ldconfig cache to find installed library.

    Can use fnmatch-style pattern matching.

    Args:
        pattern (str): The pattern to match the library name.
        arch (str, optional): The architecture of the library. Defaults to None.

    Returns:
        str: The path to the library if found, otherwise None.
    """
    try:
        p = sp.Popen(["/sbin/ldconfig", "-p"], stdout=sp.PIPE)
        stdout, stderr = p.communicate()
    except Exception:
        return

    if not arch:
        try:
            p = sp.Popen(["file", "-L", sys.executable], stdout=sp.PIPE)
            file_stdout, file_stderr = p.communicate()
            file_stdout = file_stdout.decode()
            file_stderr = file_stderr.decode()
        except Exception:
            pass
        else:
            # /usr/bin/python3.7: ELF 64-bit LSB shared object, x86-64,
            # version 1 (SYSV), dynamically linked, interpreter
            # /lib64/ld-linux-x86-64.so.2, for GNU/Linux 3.2.0,
            # BuildID[sha1]=41a1f0d4da3afee8f22d1947cc13a9f33f59f2b8,
            # stripped
            parts = file_stdout.split(",")
            if len(parts) > 1:
                arch = parts[1].strip()

    for line in stdout.decode().splitlines():
        # libxyz.so (libc6,x86_64) => /lib64/libxyz.so.1
        parts = line.split("=>", 1)
        candidate = parts[0].split(None, 1)
        if len(parts) < 2 or len(candidate) < 2:
            continue
        info = candidate[1].strip("( )").split(",")
        if arch and len(info) > 1 and info[1].strip() != arch:
            # Skip libs for wrong arch
            continue
        filename = candidate[0]
        if fnmatch.fnmatch(filename, pattern):
            path = parts[1].strip()
            return path


def expanduseru(path):
    """
    Unicode version of os.path.expanduser.

    Args:
        path (str): The path to expand.

    Returns:
        str: The expanded path.
    """
    return str(pathlib.Path(path).expanduser())


def expandvarsu(path):
    """
    Unicode version of os.path.expandvars.

    Args:
        path (str): The path to expand.

    Returns:
        str: The expanded path.
    """
    if sys.platform == "win32":
        return _expandvarsu_win32(path)
    return os.path.expandvars(path)


def _expandvarsu_win32(path):
    """
    Expand environment variables in a path for Windows.

    Args:
        path (str): The path to expand.

    Returns:
        str: The expanded path.
    """
    if "$" not in path and "%" not in path:
        return path

    res = ""
    index = 0
    pathlen = len(path)

    while index < pathlen:
        c = path[index]
        if c == "'":  # no expansion within single quotes
            path = path[index + 1 :]
            pathlen = len(path)
            try:
                index = path.index("'")
                res = res + "'" + path[: index + 1]
            except ValueError:
                res = res + path
                index = pathlen - 1
        elif c == "%":  # variable or '%'
            res = _handle_percent_sign(path, index, res)
        elif c == "$":  # variable or '$$'
            res = _handle_dollar_sign(path, index, res)
        else:
            res = res + c
        index = index + 1

    return res


def _handle_percent_sign(path, index, res):
    if path[index + 1 : index + 2] == "%":
        res = res + "%"
        index = index + 1
    else:
        path = path[index + 1 :]
        pathlen = len(path)
        try:
            index = path.index("%")
        except ValueError:
            res = res + "%" + path
            index = pathlen - 1
        else:
            var = path[:index]
            if var in os.environ:
                res = res + getenvu(var)
            else:
                res = res + "%" + var + "%"
    return res


def _handle_dollar_sign(path, index, res):
    import string

    varchars = string.ascii_letters + string.digits + "_-"

    if path[index + 1 : index + 2] == "$":
        res = res + "$"
        index = index + 1
    elif path[index + 1 : index + 2] == "{":
        path = path[index + 2 :]
        pathlen = len(path)
        try:
            index = path.index("}")
            var = path[:index]
            if var in os.environ:
                res = res + getenvu(var)
            else:
                res = res + "${" + var + "}"
        except ValueError:
            res = res + "${" + path
            index = pathlen - 1
    else:
        var = ""
        index = index + 1
        c = path[index : index + 1]
        while c != "" and c in varchars:
            var = var + c
            index = index + 1
            c = path[index : index + 1]
        if var in os.environ:
            res = res + getenvu(var)
        else:
            res = res + "$" + var
        if c != "":
            index = index - 1
    return res


def fname_ext(path):
    """
    Get filename and extension.

    Args:
        path (str): The path to the file.

    Returns:
        tuple: A tuple containing the filename and extension.
    """
    return os.path.splitext(os.path.basename(path))


def get_program_file(name, foldername):
    """
    Get path to program file.

    Args:
        name (str): The name of the program.
        foldername (str): The folder name.

    Returns:
        str: The path to the program file.
    """
    if sys.platform == "win32":
        paths = getenvu("PATH", os.defpath).split(os.pathsep)
        paths += safe_glob(os.path.join(getenvu("PROGRAMFILES", ""), foldername))
        paths += safe_glob(os.path.join(getenvu("PROGRAMW6432", ""), foldername))
        exe_ext = ".exe"
    else:
        paths = None
        exe_ext = ""
    return which(name + exe_ext, paths=paths)


def getenvu(name, default=None):
    """
    Unicode version of os.getenv.

    Args:
        name (str): The name of the environment variable.
        default (str, optional):
            The default value if the environment variable is not found.
            Defaults to None.

    Returns:
        str: The value of the environment variable.
    """
    if sys.platform == "win32":
        name = str(name)
        # http://stackoverflow.com/questions/2608200/problems-with-umlauts-in-python-appdata-environvent-variable
        length = ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0)
        if length == 0:
            return default
        buffer = ctypes.create_unicode_buffer("\0" * length)
        ctypes.windll.kernel32.GetEnvironmentVariableW(name, buffer, length)
        return buffer.value
    var = os.getenv(name, default)
    if isinstance(var, str):
        return var if isinstance(var, str) else var.encode(fs_enc)


def getgroups(username=None, names_only=False):
    """
    Return a list of groups that user is member of.

    Or groups of current process if username not given.

    Args:
        username (str, optional): The username. Defaults to None.
        names_only (bool, optional): Whether to return only the group names.
            Defaults to False.

    Returns:
        list: A list of groups.
    """
    if sys.platform == "win32":
        return _getgroups_win32(username, names_only)
    else:
        return _getgroups_unix(username, names_only)


def _getgroups_win32(username=None, names_only=False):
    if username is None:
        username = getenvu("USERNAME")

    if not username:
        return []

    groups = []

    try:
        sid, domain, type = win32security.LookupAccountName("", username)
        groups_sids = win32security.GetTokenInformation(
            win32security.OpenProcessToken(
                win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
            ),
            win32security.TokenGroups,
        )
        for group_sid in groups_sids:
            try:
                group_name, domain, type = win32security.LookupAccountSid(
                    "", group_sid.Sid
                )
                groups.append(group_name)
            except pywintypes.error:
                pass
    except ImportError:
        pass

    return groups if names_only else groups


if sys.platform != "win32":

    def _getgroups_unix(username=None, names_only=False):
        groups = []

        if username is None:
            groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
        else:
            all_groups = grp.getgrall()
            groups = [g.gr_name for g in all_groups if username in g.gr_mem]
            gid = pwd.getpwnam(username).pw_gid
            groups.append(grp.getgrgid(gid).gr_name)

        return groups


def islink(path):
    """
    Cross-platform islink implementation.

    Supports Windows NT symbolic links and reparse points.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path is a symbolic link or reparse point, otherwise False.
    """
    if sys.platform != "win32" or sys.getwindowsversion()[0] < 6:
        return os.path.islink(path)
    return bool(
        os.path.exists(path)
        and GetFileAttributes(path) & FILE_ATTRIBUTE_REPARSE_POINT
        == FILE_ATTRIBUTE_REPARSE_POINT
    )


def is_superuser():
    """
    Check if the current user is a superuser.

    Returns:
        bool: True if the user is a superuser, otherwise False.
    """
    if sys.platform == "win32":
        if sys.getwindowsversion() >= (5, 1):
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        else:
            try:
                return bool(ctypes.windll.advpack.IsNTAdmin(0, 0))
            except Exception:
                return False
    else:
        return os.geteuid() == 0


def launch_file(filepath):
    """
    Open a file with its assigned default app.

    Return tuple(returncode, stdout, stderr) or None if functionality not available.

    Args:
        filepath (str): The path to the file.

    Returns:
        int: The return code of the launched application.
    """
    filepath = filepath.encode(fs_enc)
    retcode = None
    kwargs = {"startupinfo": sp.STARTUPINFO(), "shell": True, "close_fds": True}
    kwargs["startupinfo"].dwFlags |= sp.STARTF_USESHOWWINDOW
    kwargs["startupinfo"].wShowWindow = sp.SW_HIDE

    if sys.platform == "darwin":
        retcode = sp.call(["open", filepath], **kwargs)
    elif sys.platform == "win32":
        # for win32, we could use os.startfile,
        # but then we'd not be able to return exitcode (does it matter?)
        retcode = sp.call(f'start "" "{filepath}"', **kwargs)
    elif which("xdg-open"):
        retcode = sp.call(["xdg-open", filepath], **kwargs)
    return retcode


def listdir_re(path, rex=None):
    """
    Filter directory contents through a regular expression.

    Args:
        path (str): The path to the directory.
        rex (str, optional): The regular expression pattern. Defaults to None.

    Returns:
        list: A list of files matching the regular expression.
    """
    files = os.listdir(path)
    if rex:
        rex = re.compile(rex, re.IGNORECASE)
        files = list(filter(rex.search, files))
    return files


def make_win32_compatible_long_path(path, maxpath=259):
    """
    Make a path compatible with Windows long path limitations.

    Args:
        path (str): The path to make compatible.
        maxpath (int, optional): The maximum path length. Defaults to 259.

    Returns:
        str: The compatible path.
    """
    if (
        sys.platform == "win32"
        and len(str(path)) > maxpath
        and os.path.isabs(path)
        and not str(path).startswith("\\\\?\\")
    ):
        path = "\\\\?\\" + path
    return path


def mkstemp_bypath(path, dir=None, text=False):
    """
    Wrap around mkstemp.

    Uses filename and extension from path as prefix and suffix for the temporary file.

    Args:
        path (str): The path to use for generating the temporary file name.
        dir (str, optional): The directory in which to create the temporary file.
                         Defaults to None.
        text (bool, optional): Whether to open the file in text mode. Defaults to False.

    Returns:
        tuple:
            A tuple containing the file descriptor and the path of the temporary file.
    """
    fname, ext = fname_ext(path)
    if not dir:
        dir = os.path.dirname(path)
    return tempfile.mkstemp(ext, fname + "-", dir, text)


#
# This is from Python2.7 version of tempfile
#
if sys.platform != "win32":
    import fcntl as _fcntl


def _set_cloexec(fd):
    if sys.platform != "win32":
        try:
            flags = _fcntl.fcntl(fd, _fcntl.F_GETFD, 0)
        except IOError:
            pass
        else:
            # flags read successfully, modify
            flags |= _fcntl.FD_CLOEXEC
            _fcntl.fcntl(fd, _fcntl.F_SETFD, flags)


def mksfile(filename):
    """
    Create a file safely and return (fd, abspath).

    If filename already exists, add '(n)' as suffix before extension
    (will try up to os.TMP_MAX or 10000 for n).

    Args:
        filename (str): The name of the file to be created.

    Returns:
        tuple: A tuple containing the file descriptor and the absolute path of
            the created file.

    Raises:
        IOError: If no usable temporary file name is found.
        OSError: If an OS error occurs during file creation.
    """
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    fname, ext = os.path.splitext(filename)
    for seq in range(tempfile.TMP_MAX):
        if not seq:
            pth = filename
        else:
            pth = f"{fname}({seq}){ext}"
        try:
            fd = os.open(pth, flags, 0o600)
            _set_cloexec(fd)
            return fd, os.path.abspath(pth)
        except OSError as e:
            if e.errno == errno.EEXIST:
                continue  # Try again
            raise

    raise IOError(errno.EEXIST, "No usable temporary file name found")


def movefile(src, dst, overwrite=True):
    """
    Move a file to another location.

    dst can be a directory in which case a file with the same basename as src
    will be created in it.

    Set overwrite to True to make sure existing files are overwritten.

    Args:
        src (str): The source path.
        dst (str): The destination path.
        overwrite (bool, optional): Whether to overwrite existing files.
            Defaults to True.
    """
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    if os.path.isfile(dst) and overwrite:
        os.remove(dst)
    shutil.move(src, dst)


def putenvu(name, value):
    """
    Unicode version of os.putenv (also correctly updates os.environ).

    Args:
        name (str): The name of the environment variable.
        value (str): The value of the environment variable.
    """
    if sys.platform == "win32" and isinstance(value, str):
        ctypes.windll.kernel32.SetEnvironmentVariableW(str(name), value)
    else:
        os.environ[name] = value.encode(fs_enc)


def parse_reparse_buffer(buf):
    """
    Implement the below in Python:.

    typedef struct _REPARSE_DATA_BUFFER {
        ULONG  ReparseTag;
        USHORT ReparseDataLength;
        USHORT Reserved;
        union {
            struct {
                USHORT SubstituteNameOffset;
                USHORT SubstituteNameLength;
                USHORT PrintNameOffset;
                USHORT PrintNameLength;
                ULONG Flags;
                WCHAR PathBuffer[1];
            } SymbolicLinkReparseBuffer;
            struct {
                USHORT SubstituteNameOffset;
                USHORT SubstituteNameLength;
                USHORT PrintNameOffset;
                USHORT PrintNameLength;
                WCHAR PathBuffer[1];
            } MountPointReparseBuffer;
            struct {
                UCHAR  DataBuffer[1];
            } GenericReparseBuffer;
        } DUMMYUNIONNAME;
    } REPARSE_DATA_BUFFER, *PREPARSE_DATA_BUFFER;

    Args:
        buf (bytes): The buffer to parse.

    Returns:
        dict: A dictionary containing the parsed reparse data.
    """
    # See
    # https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/content/ntifs/ns-ntifs-_reparse_data_buffer

    data = {
        "tag": struct.unpack("<I", buf[:4])[0],
        "data_length": struct.unpack("<H", buf[4:6])[0],
        "reserved": struct.unpack("<H", buf[6:8])[0],
    }
    buf = buf[8:]

    if data["tag"] in (IO_REPARSE_TAG_MOUNT_POINT, IO_REPARSE_TAG_SYMLINK):
        keys = [
            "substitute_name_offset",
            "substitute_name_length",
            "print_name_offset",
            "print_name_length",
        ]
        if data["tag"] == IO_REPARSE_TAG_SYMLINK:
            keys.append("flags")

        # Parsing
        for k in keys:
            if k == "flags":
                fmt, sz = "<I", 4
            else:
                fmt, sz = "<H", 2
            data[k] = struct.unpack(fmt, buf[:sz])[0]
            buf = buf[sz:]

    # Using the offset and lengths grabbed, we'll set the buffer.
    data["buffer"] = buf

    return data


def readlink(path):
    """
    Cross-platform implementation of readlink.

    Supports Windows NT symbolic links and reparse points.

    Args:
        path (str): The path to the symbolic link or reparse point.

    Returns:
        str: The target path of the symbolic link or reparse point.

    Raises:
        OSError: If the path is not a symbolic link or reparse point.
    """
    if sys.platform != "win32":
        return os.readlink(path)

    # This wouldn't return true if the file didn't exist
    if not islink(path):
        # Mimic POSIX error
        raise OSError(22, "Invalid argument", path)

    # Open the file correctly depending on the string type.
    if isinstance(path, str):
        createfilefn = win32file.CreateFileW
    else:
        createfilefn = win32file.CreateFile

    # Create a PySECURITY_ATTRIBUTES object
    security_attributes = win32security.SECURITY_ATTRIBUTES()

    # FILE_FLAG_OPEN_REPARSE_POINT alone is not enough if 'path' is a symbolic
    # link to a directory or a NTFS junction.
    # We need to set FILE_FLAG_BACKUP_SEMANTICS as well. See
    # https://docs.microsoft.com/en-us/windows/desktop/api/fileapi/nf-fileapi-createfilea
    # Now use this security_attributes object in the CreateFileW call
    handle = createfilefn(
        path,
        win32file.GENERIC_READ,
        0,
        security_attributes,
        win32file.OPEN_EXISTING,
        win32file.FILE_FLAG_BACKUP_SEMANTICS | win32file.FILE_FLAG_OPEN_REPARSE_POINT,
        0,
    )

    # Ensure handle is of type int
    if isinstance(handle, pywintypes.HANDLEType):
        handle = int(handle)
    elif isinstance(handle, int):
        handle = msvcrt.get_osfhandle(handle)
    else:
        handle = int(str(handle))

    # MAXIMUM_REPARSE_DATA_BUFFER_SIZE = 16384 = (16 * 1024)
    buf = win32file.DeviceIoControl(handle, FSCTL_GET_REPARSE_POINT, None, 16 * 1024)
    # Above will return an ugly string (byte array), so we'll need to parse it.

    # But first, we'll close the handle to our file so we're not locking it anymore.
    win32file.CloseHandle(handle)

    # Minimum possible length (assuming that the length is bigger than 0)
    if len(buf) < 9:
        return type(path)()
    # Parse and return our result.
    result = parse_reparse_buffer(buf)
    if result["tag"] in (IO_REPARSE_TAG_MOUNT_POINT, IO_REPARSE_TAG_SYMLINK):
        offset = result["substitute_name_offset"]
        ending = offset + result["substitute_name_length"]
        rpath = result["buffer"][offset:ending].decode("UTF-16-LE")
    else:
        rpath = result["buffer"]
    if len(rpath) > 4 and rpath[0:4] == "\\??\\":
        rpath = rpath[4:]
    return rpath


def relpath(path, start):
    """
    Return a relative version of a path.

    Args:
        path (str): The path to convert.
        start (str): The starting path.

    Returns:
        str: The relative path.
    """
    path = os.path.abspath(path).split(os.path.sep)
    start = os.path.abspath(start).split(os.path.sep)
    if path == start:
        return "."
    elif path[: len(start)] == start:
        return os.path.sep.join(path[len(start) :])
    elif start[: len(path)] == path:
        return os.path.sep.join([".."] * (len(start) - len(path)))


def safe_glob(pathname):
    """
    Return a list of paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la fnmatch.
    However, unlike fnmatch, filenames starting with a dot are special cases
    that are not matched by '*' and '?' patterns.

    Like fnmatch.glob,
    but suppresses re.compile errors by escaping uncompilable path components.

    See https://bugs.python.org/issue738361

    Args:
        pathname (str): The pathname pattern.

    Returns:
        list: A list of paths matching the pattern.
    """
    return list(safe_iglob(pathname))


def safe_iglob(pathname):
    """
    Return an iterator which yields the paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la fnmatch.
    However, unlike fnmatch, filenames starting with a dot are special cases
    that are not matched by '*' and '?' patterns.

    Like fnmatch.iglob,
    but suppresses re.compile errors by escaping uncompilable path components.

    See https://bugs.python.org/issue738361

    Args:
        pathname (str): The pathname pattern.

    Yields:
        str: The paths matching the pattern.
    """
    dirname, basename = os.path.split(pathname)
    if not glob.has_magic(pathname):
        if basename:
            if os.path.lexists(pathname):
                yield pathname
        else:
            # Patterns ending with a slash should match only directories
            if os.path.isdir(dirname):
                yield pathname
        return
    if not dirname:
        for name in safe_glob1(os.curdir, basename):
            yield name
        return
    # `os.path.split()` returns the argument itself as a dirname if it is a
    # drive or UNC path.
    # Prevent an infinite recursion if a drive or UNC path contains magic
    # characters (i.e. r'\\?\C:').
    if dirname != pathname and glob.has_magic(dirname):
        dirs = safe_iglob(dirname)
    else:
        dirs = [dirname]
    if glob.has_magic(basename):
        glob_in_dir = safe_glob1
    else:
        glob_in_dir = glob.glob0
    for dirname in dirs:
        for name in glob_in_dir(dirname, basename):
            yield os.path.join(dirname, name)


def safe_glob1(dirname, pattern):
    """
    Return the subset of the list NAMES that match PAT.

    Args:
        dirname (str): The directory name.
        pattern (str): The pattern to match.

    Returns:
        list: The subset of names that match the pattern.
    """
    if not dirname:
        dirname = os.curdir
    if isinstance(pattern, str) and not isinstance(dirname, str):
        dirname = str(dirname, sys.getfilesystemencoding() or sys.getdefaultencoding())
    try:
        names = os.listdir(dirname)
    except os.error:
        return []
    if pattern[0] != ".":
        names = [x for x in names if x[0] != "."]
    return safe_shell_filter(names, pattern)


def safe_shell_filter(names, pat):
    """
    Return the subset of the list NAMES that match PAT.

    Like fnmatch.filter,
    but suppresses re.compile errors by escaping uncompilable path components.

    See https://bugs.python.org/issue738361

    Args:
        names (list): The list of names.
        pat (str): The pattern to match.

    Returns:
        list: The subset of names that match the pattern.
    """
    import posixpath

    result = []
    pat = os.path.normcase(pat)
    try:
        re_pat = _cache[pat]
    except KeyError:
        res = safe_translate(pat)
        if len(_cache) >= _MAXCACHE:
            _cache.clear()
        _cache[pat] = re_pat = re.compile(res)
    match = re_pat.match
    if os.path is posixpath:
        # normcase on posix is NOP. Optimize it away from the loop.
        for name in names:
            if match(name):
                result.append(name)
    else:
        for name in names:
            if match(os.path.normcase(name)):
                result.append(name)
    return result


def safe_translate(pat):
    """
    Translate a shell PATTERN to a regular expression.

    Like fnmatch.translate,
    but suppresses re.compile errors by escaping uncompilable path components.

    See https://bugs.python.org/issue738361

    Args:
        pat (str): The shell pattern.

    Returns:
        str: The translated regular expression.
    """
    if isinstance(getattr(os.path, "altsep", None), str):
        # Normalize path separators
        pat = pat.replace(os.path.altsep, os.path.sep)
    components = pat.split(os.path.sep)
    for i, component in enumerate(components):
        translated = fnmatch.translate(component)
        try:
            re.compile(translated)
        except re.error:
            translated = re.escape(component)
        components[i] = translated
    return re.escape(os.path.sep).join(components)


def waccess(path, mode):
    """
    Test access to path.

    Args:
        path (str): The path to test.
        mode (int): The access mode.

    Returns:
        bool: True if access is granted, otherwise False.
    """
    if mode & os.R_OK:
        try:
            test = open(path, "rb")
        except EnvironmentError:
            return False
        test.close()
    if mode & os.W_OK:
        if os.path.isdir(path):
            dir = path
        else:
            dir = os.path.dirname(path)
        try:
            if os.path.isfile(path):
                test = open(path, "ab")
            else:
                test = tempfile.TemporaryFile(prefix=".", dir=dir)
        except EnvironmentError:
            return False
        test.close()
    if mode & os.X_OK:
        return os.access(path, mode)
    return True


def which(executable, paths=None):
    """
    Return the full path of executable.

    Args:
        executable (str): The name of the executable.
        paths (list, optional): The list of paths to search. Defaults to None.

    Returns:
        str: The full path of the executable if found, otherwise None.
    """
    if not paths:
        paths = getenvu("PATH", os.defpath).split(os.pathsep)
    for cur_dir in paths:
        filename = os.path.join(cur_dir, executable)
        if os.path.isfile(filename):
            try:
                # make sure file is actually executable
                if os.access(filename, os.X_OK):
                    return filename
            except Exception:
                pass
    return None


def whereis(
    names,
    bin=True,
    bin_paths=None,
    man=True,
    man_paths=None,
    src=True,
    src_paths=None,
    unusual=False,
    list_paths=False,
):
    """
    Wrap around whereis.

    Args:
        names (list): The names to search for.
        bin (bool, optional): Whether to search for binaries. Defaults to True.
        bin_paths (list, optional): The list of binary paths. Defaults to None.
        man (bool, optional): Whether to search for man pages. Defaults to True.
        man_paths (list, optional): The list of man paths. Defaults to None.
        src (bool, optional): Whether to search for source files. Defaults to True.
        src_paths (list, optional): The list of source paths. Defaults to None.
        unusual (bool, optional): Whether to search for unusual files.
            Defaults to False.
        list_paths (bool, optional): Whether to list paths. Defaults to False.

    Returns:
        dict: The results of the whereis command.
    """
    args = build_whereis_args(
        bin, bin_paths, man, man_paths, src, src_paths, unusual, list_paths
    )
    return execute_whereis(names, args)


def build_whereis_args(
    bin, bin_paths, man, man_paths, src, src_paths, unusual, list_paths
):
    """
    Build arguments for the whereis command.

    Args:
        bin (bool): Whether to search for binaries.
        bin_paths (list): The list of binary paths.
        man (bool): Whether to search for man pages.
        man_paths (list): The list of man paths.
        src (bool): Whether to search for source files.
        src_paths (list): The list of source paths.
        unusual (bool): Whether to search for unusual files.
        list_paths (bool): Whether to list paths.

    Returns:
        list: The list of arguments for the whereis command.
    """
    args = []
    if bin:
        args.append("-b")
    if bin_paths:
        args.append("-B")
        args.extend(bin_paths)
    if man:
        args.append("-m")
    if man_paths:
        args.append("-M")
        args.extend(man_paths)
    if src:
        args.append("-s")
    if src_paths:
        args.append("-S")
        args.extend(src_paths)
    if bin_paths or man_paths or src_paths:
        args.append("-f")
    if unusual:
        args.append("-u")
    if list_paths:
        args.append("-l")
    return args


def execute_whereis(names, args):
    """
    Execute the whereis command with the given arguments.

    Args:
        names (list): The names to search for.
        args (list): The list of arguments for the whereis command.

    Returns:
        dict: The results of the whereis command.
    """
    if isinstance(names, str):
        names = [names]
    p = sp.Popen(["whereis"] + args + names, stdout=sp.PIPE)
    stdout, stderr = p.communicate()
    return parse_whereis_output(stdout)


def parse_whereis_output(stdout):
    """
    Parse the output of the whereis command.

    Args:
        stdout (bytes): The output of the whereis command.

    Returns:
        dict: The parsed results of the whereis command.
    """
    result = {}
    for line in stdout.decode().strip().splitlines():
        match = line.split(":", 1)
        if match:
            result[match[0]] = match[-1].split()
    return result


class FileLock(object):
    """A context manager for file locking."""

    if sys.platform == "win32":
        _exception_cls = pywintypes.error
    else:
        _exception_cls = IOError

    def __init__(self, file_, exclusive=False, blocking=False):
        """
        Initialize the FileLock.

        Args:
            file_ (file): The file to lock.
            exclusive (bool, optional): Whether to acquire an exclusive lock.
                Defaults to False.
            blocking (bool, optional): Whether to block until the lock is acquired.
                Defaults to False.
        """
        self._file = file_
        self.exclusive = exclusive
        self.blocking = blocking
        self.lock()

    def __enter__(self):
        """
        Enter the context manager.

        Returns:
            FileLock: The FileLock instance.
        """
        return self

    def __exit__(self):
        """Exit the context manager."""
        self.unlock()

    def lock(self):
        """Acquire the lock."""
        if sys.platform == "win32":
            mode = 0
            if self.exclusive:
                mode |= win32con.LOCKFILE_EXCLUSIVE_LOCK
            if not self.blocking:
                mode |= win32con.LOCKFILE_FAIL_IMMEDIATELY
            self._handle = msvcrt.get_osfhandle(self._file.fileno())
            self._overlapped = pywintypes.OVERLAPPED()
            fn = win32file.LockFileEx
            args = (self._handle, mode, 0, -0x10000, self._overlapped)
        else:
            if self.exclusive:
                op = fcntl.LOCK_EX
            else:
                op = fcntl.LOCK_SH
            if not self.blocking:
                op |= fcntl.LOCK_NB
            fn = fcntl.flock
            args = (self._file.fileno(), op)
        self._call(fn, args, LockingError)

    def unlock(self):
        """Release the lock."""
        if self._file.closed:
            return
        if sys.platform == "win32":
            fn = win32file.UnlockFileEx
            args = (self._handle, 0, -0x10000, self._overlapped)
        else:
            fn = fcntl.flock
            args = (self._file.fileno(), fcntl.LOCK_UN)
        self._call(fn, args, UnlockingError)

    @staticmethod
    def _call(fn, args, exception_cls):
        """
        Call the function with the given arguments.

        Args:
            fn (callable): The function to call.
            args (tuple): The arguments to pass to the function.
            exception_cls (type): The exception class to raise.

        Raises:
            exception_cls: If the function call fails.
        """
        try:
            fn(*args)
        except FileLock._exception_cls as exception:
            raise exception_cls(*exception.args)


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class LockingError(Error):
    """Exception raised for errors in locking."""

    pass


class UnlockingError(Error):
    """Exception raised for errors in unlocking."""

    pass


if sys.platform == "win32" and sys.getwindowsversion() >= (6,):

    class win64_disable_file_system_redirection:
        r"""
        Disable Windows File System Redirection.

        When a 32 bit program runs on a 64 bit Windows the paths to C:\Windows\System32
        automatically get redirected to the 32 bit version (C:\Windows\SysWow64),
        if you really do need to access the contents of System32,
        you need to disable the file system redirection first.

        # http://code.activestate.com/recipes/578035-disable-file-system-redirector/
        """

        _disable = ctypes.windll.kernel32.Wow64DisableWow64FsRedirection
        _revert = ctypes.windll.kernel32.Wow64RevertWow64FsRedirection

        def __enter__(self):
            """Enter the context manager."""
            self.old_value = ctypes.c_long()
            self.success = self._disable(ctypes.byref(self.old_value))

        def __exit__(self):
            """Exit the context manager."""
            if self.success:
                self._revert(self.old_value)
