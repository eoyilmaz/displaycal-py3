# -*- coding: utf-8 -*-

import fnmatch
import ctypes
import errno
import glob
import locale
import os
import pathlib
import re
import shutil
import struct
import subprocess as sp
import sys
import tempfile
import time
import importlib

if sys.platform not in ("darwin", "win32"):
    # Linux
    import grp
    import pwd

if sys.platform != "win32":
    import fcntl

try:
    reloaded
except NameError:
    # First import. All fine
    reloaded = 0
else:
    # Module is being reloaded. NOT recommended.
    reloaded += 1
    import warnings

    warnings.warn(
        "Module %s is being reloaded. This is NOT recommended." % __name__,
        RuntimeWarning,
    )
    warnings.warn("Implicitly reloading builtins", RuntimeWarning)
    if sys.platform == "win32":
        importlib.reload(__builtin__)
    warnings.warn("Implicitly reloading os", RuntimeWarning)
    importlib.reload(os)
    warnings.warn("Implicitly reloading os.path", RuntimeWarning)
    importlib.reload(os.path)
    if sys.platform == "win32":
        warnings.warn("Implicitly reloading win32api", RuntimeWarning)
        importlib.reload(win32api)

if sys.platform == "win32":
    from win32file import *
    from winioctlcon import FSCTL_GET_REPARSE_POINT
    import win32file
    import win32con
    import pywintypes
    import winerror

# Cache used for safe_shell_filter() function
_cache = {}
_MAXCACHE = 100

FILE_ATTRIBUTE_REPARSE_POINT = 1024
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # Junction
IO_REPARSE_TAG_SYMLINK = 0xA000000C

from DisplayCAL.encoding import get_encodings

fs_enc = get_encodings()[1]

_listdir = os.listdir

if sys.platform == "win32":
    # Add support for long paths (> 260 chars)
    # and retry ERROR_SHARING_VIOLATION
    import builtins
    import winerror
    import win32api

    _open = builtins.open

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

    def open(path, *args, **kwargs):
        """Wrapper around __builtin__.open dealing with win32 long paths"""
        return _open(make_win32_compatible_long_path(path), *args, **kwargs)

    builtins.open = open

    _access = os.access

    def access(path, mode, *args, **kwargs):
        return _access(make_win32_compatible_long_path(path), mode, *args, **kwargs)

    os.access = access

    _exists = os.path.exists

    def exists(path, *args, **kwargs):
        return _exists(make_win32_compatible_long_path(path), *args, **kwargs)

    os.path.exists = exists

    _isdir = os.path.isdir

    def isdir(path, *args, **kwargs):
        return _isdir(make_win32_compatible_long_path(path), *args, **kwargs)

    os.path.isdir = isdir

    _isfile = os.path.isfile

    def isfile(path, *args, **kwargs):
        return _isfile(make_win32_compatible_long_path(path), *args, **kwargs)

    os.path.isfile = isfile

    def listdir(path, *args, **kwargs):
        return _listdir(make_win32_compatible_long_path(path), *args, **kwargs)

    _lstat = os.lstat

    def lstat(path, *args, **kwargs):
        return _lstat(make_win32_compatible_long_path(path), *args, **kwargs)

    os.lstat = lstat

    _mkdir = os.mkdir

    def mkdir(path, mode=0o777, *args, **kwargs):
        return _mkdir(make_win32_compatible_long_path(path, 247), mode, *args, **kwargs)

    os.mkdir = mkdir

    _makedirs = os.makedirs

    def makedirs(path, mode=0o777, *args, **kwargs):
        return _makedirs(make_win32_compatible_long_path(path, 247), mode, *args, **kwargs)

    os.makedirs = makedirs

    _remove = os.remove

    def remove(path, *args, **kwargs):
        return _remove(make_win32_compatible_long_path(path), *args, **kwargs)

    os.remove = retry_sharing_violation_factory(remove)

    _rename = os.rename

    def rename(src, dst, *args, **kwargs):
        src, dst = [make_win32_compatible_long_path(path) for path in (src, dst)]
        return _rename(src, dst, *args, **kwargs)

    os.rename = retry_sharing_violation_factory(rename)

    _stat = os.stat

    def stat(path, *args, **kwargs):
        return _stat(make_win32_compatible_long_path(path), *args, **kwargs)

    os.stat = stat

    _unlink = os.unlink

    def unlink(path, *args, **kwargs):
        return _unlink(make_win32_compatible_long_path(path), *args, **kwargs)

    os.unlink = retry_sharing_violation_factory(unlink)

    _GetShortPathName = win32api.GetShortPathName

    def GetShortPathName(path, *args, **kwargs):
        return _GetShortPathName(make_win32_compatible_long_path(path), *args, **kwargs)

    win32api.GetShortPathName = GetShortPathName
else:

    def listdir(path, *args, **kwargs):
        paths = _listdir(path, *args, **kwargs)
        if isinstance(path, str):
            # Undecodable filenames will still be string objects. Ignore them.
            paths = [path for path in paths if isinstance(path, str)]
        return paths


os.listdir = listdir


def quote_args(args):
    """Quote commandline arguments where needed. It quotes all arguments that
    contain spaces or any of the characters ^!$%&()[]{}=;'+,`~"""
    args_out = []
    for arg in args:
        if re.search(r"[\^!$%&()[\]{}=;'+,`~\s]", arg):
            arg = '"' + arg + '"'
        args_out.append(arg)
    return args_out


def dlopen(name, handle=None):
    try:
        return ctypes.CDLL(name, handle=handle)
    except Exception:
        pass


def find_library(pattern, arch=None):
    """Use ldconfig cache to find installed library.

    Can use fnmatch-style pattern matching.

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
            # BuildID[sha1]=41a1f0d4da3afee8f22d1947cc13a9f33f59f2b8, stripped
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
    """Unicode version of os.path.expanduser"""
    return str(pathlib.Path(path).expanduser())


def expandvarsu(path):
    """Unicode version of os.path.expandvars"""
    if sys.platform == "win32":
        # The code in this if-statement is copied from Python 2.7's expandvars
        # in ntpath.py, but uses getenvu() instead of os.environ[]
        if "$" not in path and "%" not in path:
            return path
        import string

        varchars = string.ascii_letters + string.digits + "_-"
        res = ""
        index = 0
        pathlen = len(path)
        while index < pathlen:
            c = path[index]
            if c == "'":  # no expansion within single quotes
                path = path[index + 1:]
                pathlen = len(path)
                try:
                    index = path.index("'")
                    res = res + "'" + path[: index + 1]
                except ValueError:
                    res = res + path
                    index = pathlen - 1
            elif c == "%":  # variable or '%'
                if path[index + 1: index + 2] == "%":
                    res = res + c
                    index = index + 1
                else:
                    path = path[index + 1:]
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
            elif c == "$":  # variable or '$$'
                if path[index + 1: index + 2] == "$":
                    res = res + c
                    index = index + 1
                elif path[index + 1: index + 2] == "{":
                    path = path[index + 2:]
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
                    c = path[index: index + 1]
                    while c != "" and c in varchars:
                        var = var + c
                        index = index + 1
                        c = path[index: index + 1]
                    if var in os.environ:
                        res = res + getenvu(var)
                    else:
                        res = res + "$" + var
                    if c != "":
                        index = index - 1
            else:
                res = res + c
            index = index + 1
        return res
    return os.path.expandvars(path)


def fname_ext(path):
    """Get filename and extension"""
    return os.path.splitext(os.path.basename(path))


def get_program_file(name, foldername):
    """Get path to program file"""
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
    """Unicode version of os.getenv"""
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
    """Return a list of groups that user is member of, or groups of current
    process if username not given

    """
    if username is None:
        groups = [grp.getgrgid(g) for g in os.getgroups()]
    else:
        groups = [g for g in grp.getgrall() if username in g.gr_mem]
        gid = pwd.getpwnam(username).pw_gid
        groups.append(grp.getgrgid(gid))
    if names_only:
        groups = [g.gr_name for g in groups]
    return groups


def islink(path):
    """Cross-platform islink implementation.

    Supports Windows NT symbolic links and reparse points.

    """
    if sys.platform != "win32" or sys.getwindowsversion()[0] < 6:
        return os.path.islink(path)
    return bool(
        os.path.exists(path)
        and GetFileAttributes(path) & FILE_ATTRIBUTE_REPARSE_POINT
        == FILE_ATTRIBUTE_REPARSE_POINT
    )


def is_superuser():
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
    """Open a file with its assigned default app.

    Return tuple(returncode, stdout, stderr) or None if functionality not available

    """
    filepath = filepath.encode(fs_enc)
    retcode = None
    kwargs = dict(stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    if sys.platform == "darwin":
        retcode = sp.call(["open", filepath], **kwargs)
    elif sys.platform == "win32":
        # for win32, we could use os.startfile, but then we'd not be able
        # to return exitcode (does it matter?)
        kwargs = {"startupinfo": sp.STARTUPINFO()}
        kwargs["startupinfo"].dwFlags |= sp.STARTF_USESHOWWINDOW
        kwargs["startupinfo"].wShowWindow = sp.SW_HIDE
        kwargs["shell"] = True
        kwargs["close_fds"] = True
        retcode = sp.call('start "" "%s"' % filepath, **kwargs)
    elif which("xdg-open"):
        retcode = sp.call(["xdg-open", filepath], **kwargs)
    return retcode


def listdir_re(path, rex=None):
    """Filter directory contents through a regular expression"""
    files = os.listdir(path)
    if rex:
        rex = re.compile(rex, re.IGNORECASE)
        files = list(filter(rex.search, files))
    return files


def make_win32_compatible_long_path(path, maxpath=259):
    if (
        sys.platform == "win32"
        and len(str(path)) > maxpath
        and os.path.isabs(path)
        and not str(path).startswith("\\\\?\\")
    ):
        path = "\\\\?\\" + path
    return path


def mkstemp_bypath(path, dir=None, text=False):
    """Wrapper around mkstemp that uses filename and extension from path as prefix
    and suffix for the temporary file, and the directory component as temporary
    file directory if 'dir' is not given.

    """
    fname, ext = fname_ext(path)
    if not dir:
        dir = os.path.dirname(path)
    return tempfile.mkstemp(ext, fname + "-", dir, text)


#
# This is from Python2.7 version of tempfile
#
try:
    import fcntl as _fcntl
except ImportError:

    def _set_cloexec(fd):
        return None

else:

    def _set_cloexec(fd):
        try:
            flags = _fcntl.fcntl(fd, _fcntl.F_GETFD, 0)
        except IOError:
            pass
        else:
            # flags read successfully, modify
            flags |= _fcntl.FD_CLOEXEC
            _fcntl.fcntl(fd, _fcntl.F_SETFD, flags)


def mksfile(filename):
    """Create a file safely and return (fd, abspath)

    If filename already exists, add '(n)' as suffix before extension (will try up to os.TMP_MAX or 10000 for n)

    Basically, this works in a similar way as _mkstemp_inner from the
    standard library 'tempfile' module.
    """

    flags = tempfile._bin_openflags

    fname, ext = os.path.splitext(filename)
    for seq in range(tempfile.TMP_MAX):
        if not seq:
            pth = filename
        else:
            pth = "%s(%i)%s" % (fname, seq, ext)
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
    """Move a file to another location.

    dst can be a directory in which case a file with the same basename as src
    will be created in it.

    Set overwrite to True to make sure existing files are overwritten.

    """
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    if os.path.isfile(dst) and overwrite:
        os.remove(dst)
    shutil.move(src, dst)


def putenvu(name, value):
    """Unicode version of os.putenv (also correctly updates os.environ)"""
    if sys.platform == "win32" and isinstance(value, str):
        ctypes.windll.kernel32.SetEnvironmentVariableW(str(name), value)
    else:
        os.environ[name] = value.encode(fs_enc)


def parse_reparse_buffer(buf):
    """Implementing the below in Python:

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

    """
    # See https://docs.microsoft.com/en-us/windows-hardware/drivers/ddi/content/ntifs/ns-ntifs-_reparse_data_buffer

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
    """Cross-platform implenentation of readlink.

    Supports Windows NT symbolic links and reparse points.

    """
    if sys.platform != "win32":
        return os.readlink(path)

    # This wouldn't return true if the file didn't exist
    if not islink(path):
        # Mimic POSIX error
        raise OSError(22, "Invalid argument", path)

    # Open the file correctly depending on the string type.
    if isinstance(path, str):
        createfilefn = CreateFileW
    else:
        createfilefn = CreateFile
    # FILE_FLAG_OPEN_REPARSE_POINT alone is not enough if 'path'
    # is a symbolic link to a directory or a NTFS junction.
    # We need to set FILE_FLAG_BACKUP_SEMANTICS as well.
    # See https://docs.microsoft.com/en-us/windows/desktop/api/fileapi/nf-fileapi-createfilea
    handle = createfilefn(
        path,
        GENERIC_READ,
        0,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        0,
    )

    # MAXIMUM_REPARSE_DATA_BUFFER_SIZE = 16384 = (16 * 1024)
    buf = DeviceIoControl(handle, FSCTL_GET_REPARSE_POINT, None, 16 * 1024)
    # Above will return an ugly string (byte array), so we'll need to parse it.

    # But first, we'll close the handle to our file so we're not locking it anymore.
    CloseHandle(handle)

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
    """Return a relative version of a path"""
    path = os.path.abspath(path).split(os.path.sep)
    start = os.path.abspath(start).split(os.path.sep)
    if path == start:
        return "."
    elif path[: len(start)] == start:
        return os.path.sep.join(path[len(start):])
    elif start[: len(path)] == path:
        return os.path.sep.join([".."] * (len(start) - len(path)))


def safe_glob(pathname):
    """Return a list of paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la
    fnmatch. However, unlike fnmatch, filenames starting with a
    dot are special cases that are not matched by '*' and '?'
    patterns.

    Like fnmatch.glob, but suppresses re.compile errors by escaping
    uncompilable path components.

    See https://bugs.python.org/issue738361

    """
    return list(safe_iglob(pathname))


def safe_iglob(pathname):
    """Return an iterator which yields the paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la
    fnmatch. However, unlike fnmatch, filenames starting with a
    dot are special cases that are not matched by '*' and '?'
    patterns.

    Like fnmatch.iglob, but suppresses re.compile errors by escaping
    uncompilable path components.

    See https://bugs.python.org/issue738361

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
    # drive or UNC path.  Prevent an infinite recursion if a drive or UNC path
    # contains magic characters (i.e. r'\\?\C:').
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
    """Return the subset of the list NAMES that match PAT

    Like fnmatch.filter, but suppresses re.compile errors by escaping
    uncompilable path components.

    See https://bugs.python.org/issue738361

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
    """Translate a shell PATTERN to a regular expression.

    Like fnmatch.translate, but suppresses re.compile errors by escaping
    uncompilable path components.

    See https://bugs.python.org/issue738361

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
    """Test access to path"""
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
    """Return the full path of executable"""
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
    """Wrapper around whereis"""
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
    if isinstance(names, str):
        names = [names]
    p = sp.Popen(["whereis"] + args + names, stdout=sp.PIPE)
    stdout, stderr = p.communicate()
    result = {}
    for line in stdout.decode().strip().splitlines():
        # $ whereis abc xyz
        # abc: /bin/abc
        # xyz: /bin/xyz /usr/bin/xyz
        match = line.split(":", 1)
        if match:
            result[match[0]] = match[-1].split()
    return result


class FileLock(object):

    if sys.platform == "win32":
        _exception_cls = pywintypes.error
    else:
        _exception_cls = IOError

    def __init__(self, file_, exclusive=False, blocking=False):
        self._file = file_
        self.exclusive = exclusive
        self.blocking = blocking
        self.lock()

    def __enter__(self):
        return self

    def __exit__(self, etype, value, traceback):
        self.unlock()

    def lock(self):
        if sys.platform == "win32":
            mode = 0
            if self.exclusive:
                mode |= win32con.LOCKFILE_EXCLUSIVE_LOCK
            if not self.blocking:
                mode |= win32con.LOCKFILE_FAIL_IMMEDIATELY
            self._handle = win32file._get_osfhandle(self._file.fileno())
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
        try:
            fn(*args)
        except FileLock._exception_cls as exception:
            raise exception_cls(*exception.args)


class Error(Exception):
    pass


class LockingError(Error):
    pass


class UnlockingError(Error):
    pass


if sys.platform == "win32" and sys.getwindowsversion() >= (6,):

    class win64_disable_file_system_redirection:
        r"""Disable Windows File System Redirection.

        When a 32 bit program runs on a 64 bit Windows the paths to
        C:\Windows\System32 automatically get redirected to the 32 bit version
        (C:\Windows\SysWow64), if you really do need to access the contents of
        System32, you need to disable the file system redirection first.

        # http://code.activestate.com/recipes/578035-disable-file-system-redirector/
        """

        _disable = ctypes.windll.kernel32.Wow64DisableWow64FsRedirection
        _revert = ctypes.windll.kernel32.Wow64RevertWow64FsRedirection

        def __enter__(self):
            self.old_value = ctypes.c_long()
            self.success = self._disable(ctypes.byref(self.old_value))

        def __exit__(self, type, value, traceback):
            if self.success:
                self._revert(self.old_value)
