"""This module provides utility classes and functions for handling file I/O
operations. It includes tools for encoding/decoding data during file writes,
managing multiple file objects, working with GZIP and TAR files, buffering
line-based streams, and other file-related utilities.
"""

from __future__ import annotations

import contextlib
import copy
import gzip
import operator
import os
import sys
import tarfile
from io import StringIO
from time import time
from typing import TYPE_CHECKING, Any, Self

# from safe_print import safe_print
from DisplayCAL.util_str import universal_newlines

if TYPE_CHECKING:
    from collections.abc import Iterator


class EncodedWriter:
    """Decode data with data_encoding and encode it with file_encoding before
    writing it to file_obj.

    Either data_encoding or file_encoding can be None.
    """

    def __init__(
        self, file_obj, data_encoding=None, file_encoding=None, errors="replace"
    ):
        self.file = file_obj
        self.data_encoding = data_encoding
        self.file_encoding = file_encoding
        self.errors = errors

    def __getattr__(self, name: str) -> Any:
        """Get attribute from the file object.

        Args:
            name (str): The name of the attribute to get.

        Returns:
            Any: The value of the attribute from the file object.
        """
        return getattr(self.file, name)

    def write(self, data):
        if self.data_encoding and not isinstance(data, str):
            data = data.decode(self.data_encoding, self.errors)
        if self.file_encoding and isinstance(data, str):
            data = data.encode(self.file_encoding, self.errors)
        self.file.write(data.decode())


class Files:
    """Read and/or write from/to several files at once."""

    def __init__(self, files, mode="r"):
        """Return a Files object.

        files must be a list or tuple of file objects or filenames
        (the mode parameter is only used in the latter case).

        """
        self.files = []
        for item in files:
            if isinstance(item, str):
                self.files.append(open(item, mode))  # noqa: SIM115
            else:
                self.files.append(item)

    def __iter__(self) -> Iterator:
        """Return an iterator over the files in the Files object.

        Returns:
            iterator: An iterator over the files in the Files object.
        """
        return iter(self.files)

    def close(self):
        for item in self.files:
            item.close()

    def flush(self):
        for item in self.files:
            with contextlib.suppress(AttributeError):
                # TODO: Restore safe_log
                item.flush()

    def seek(self, pos, mode=0):
        for item in self.files:
            item.seek(pos, mode)

    def truncate(self, size=None):
        for item in self.files:
            item.truncate(size)

    def write(self, data):
        for item in self.files:
            try:
                item.write(data)
            except AttributeError:  # TODO: restore safe_log, safe_print etc...
                with contextlib.suppress(TypeError):
                    item(data)

    def writelines(self, str_sequence):
        self.write("".join(str_sequence))


class GzipFileProper(gzip.GzipFile):
    """Proper GZIP file implementation, where the optional filename in the
    header has directory components removed, and is converted to ISO 8859-1
    (Latin-1). On Windows, the filename will also be forced to lowercase.

    See RFC 1952 GZIP File Format Specification	version 4.3
    """

    def _write_gzip_header(self, compresslevel):
        self.fileobj.write(b"\037\213")  # magic header
        self.fileobj.write(b"\010")  # compression method
        fname = os.path.basename(self.name)
        if fname.endswith(".gz"):
            fname = fname[:-3]
        elif fname.endswith(".tgz"):
            fname = f"{fname[:-4]}.tar"
        elif fname.endswith(".wrz"):
            fname = f"{fname[:-4]}.wrl"
        flags = 0
        if fname:
            flags = gzip.FNAME
        self.fileobj.write(chr(flags).encode())
        gzip.write32u(self.fileobj, int(time()))
        self.fileobj.write(b"\002")
        self.fileobj.write(b"\377")
        if fname:
            if sys.platform == "win32":
                # Windows is case insensitive by default (although it can be
                # set to case sensitive), so according to the GZIP spec, we
                # force the name to lowercase
                fname = fname.lower()
            self.fileobj.write(
                fname.encode("ISO-8859-1", "replace").replace(b"?", b"_") + b"\000"
            )

    def __enter__(self) -> Self:
        """Enter the runtime context related to this object.

        Returns:
            GzipFileProper: The GzipFileProper object itself.
        """
        return self

    def __exit__(self, exc_type, exc_value, tb) -> None:
        """Exit the runtime context related to this object.

        Args:
            exc_type: The exception type.
            exc_value: The exception value.
            tb: The traceback object.

        Returns:
            None: No return value.
        """
        self.close()


class LineBufferedStream:
    """Buffer lines and only write them to stream if line separator is detected"""

    def __init__(
        self,
        stream,
        data_encoding=None,
        file_encoding=None,
        errors="replace",
        linesep_in="\r\n",
        linesep_out="",
    ):
        self.buf = ""
        self.data_encoding = data_encoding
        self.file_encoding = file_encoding
        self.errors = errors
        self.linesep_in = linesep_in
        self.linesep_out = linesep_out
        self.stream = stream

    def __del__(self) -> None:
        """Destructor to ensure the stream is closed properly."""
        self.commit()

    def __getattr__(self, name: str) -> Any:
        """Get attribute from the stream.

        Args:
            name (str): The name of the attribute to get.

        Returns:
            Any: The value of the attribute from the stream.
        """
        return getattr(self.stream, name)

    def close(self):
        self.commit()
        self.stream.close()

    def commit(self):
        if not self.buf:
            return
        if self.data_encoding and isinstance(self.buf, bytes):
            self.buf = self.buf.decode(self.data_encoding, self.errors)
        if self.file_encoding:
            self.buf = self.buf.encode(self.file_encoding, self.errors)
        self.stream.write(self.buf)
        self.buf = ""

    def write(self, data: str | bytes | bytearray) -> None:
        """Write data to the stream, buffering it until a line separator is detected.

        Args:
            data (str | bytes): The data to write to the stream.

        Raises:
            TypeError: If the data is not of type str, bytes, or bytearray.
        """
        if isinstance(data, bytes):
            data = data.decode()
        if not isinstance(data, str):
            raise TypeError(
                f"Expected str, bytes or bytearray, got {type(data).__name__}"
            )
        data = data.replace(self.linesep_in, "\n")
        for char in data:
            if char == "\r":
                while self.buf and not self.buf.endswith("\n"):
                    self.buf = self.buf[:-1]
            elif char == "\n":
                self.buf += self.linesep_out
                self.commit()
            else:
                self.buf += char


class LineCache:
    """When written to it, stores only the last n + 1 lines and
    returns only the last n non-empty lines when read."""

    def __init__(self, maxlines=1):
        self.clear()
        self.maxlines = maxlines

    def clear(self):
        self.cache = [""]

    def flush(self):
        pass

    def read(self, triggers=None):
        lines = [""]
        for line in self.cache:
            read = True
            if triggers:
                for trigger in triggers:
                    if trigger.lower() in line.lower():
                        read = False
                        break
            if read and line:
                lines.append(line)
        return "\n".join([line for line in lines if line][-self.maxlines :])

    def write(self, data):
        cache = list(self.cache)
        for char in data:
            if char == "\r":
                cache[-1] = ""
            elif char == "\n":
                cache.append("")
            else:
                cache[-1] += char
        self.cache = ([line for line in cache[:-1] if line] + cache[-1:])[
            -self.maxlines - 1 :
        ]


class StringIOu(StringIO):
    """StringIO which converts all new line formats in buf to POSIX newlines."""

    def __init__(self, buf=""):
        StringIO.__init__(self, universal_newlines(buf))


class Tee(Files):
    """Write to a file and stdout."""

    def __init__(self, file_obj):
        Files.__init__((sys.stdout, file_obj))

    def __getattr__(self, name):
        """Get attribute from the second file object.

        Args:
            name (str): The name of the attribute to get.

        Returns:
            Any: The value of the attribute from the second file object.
        """
        return getattr(self.files[1], name)

    def close(self):
        self.files[1].close()

    def seek(self, pos, mode=0):
        return self.files[1].seek(pos, mode)

    def truncate(self, size=None):
        return self.files[1].truncate(size)


class TarFileProper(tarfile.TarFile):
    """Support extracting to unicode location and using base name"""

    def extract(self, member, path="", full=True):
        """Extract a member from the archive to the current working directory,
        using its full name or base name. Its file information is extracted
        as accurately as possible. `member' may be a filename or a TarInfo
        object. You can specify a different directory using `path'.
        """
        self._check("r")
        tarinfo = self.getmember(member) if isinstance(member, str) else member

        # Prepare the link target for makelink().
        if tarinfo.islnk():
            name = tarinfo.linkname.decode(self.encoding)
            if not full:
                name = os.path.basename(name)
            tarinfo._link_target = os.path.join(path, name)

        try:
            name = tarinfo.name
            if not full:
                name = os.path.basename(name)
            self._extract_member(tarinfo, os.path.join(path, name))
        except OSError as e:
            if self.errorlevel > 0:
                raise e
            if e.filename is None:
                self._dbg(1, f"tarfile: {e.strerror}")
            else:
                self._dbg(1, f"tarfile: {e.strerror} {e.filename!r}")
        except tarfile.ExtractError as e:
            if self.errorlevel > 1:
                raise e
            self._dbg(1, f"tarfile: {e}")

    def extractall(self, path=".", members=None, full=True):
        """Extract all members from the archive to the current working
        directory and set owner, modification time and permissions on
        directories afterwards. `path' specifies a different directory
        to extract to. `members' is optional and must be a subset of the
        list returned by getmembers().
        """
        directories = []

        if members is None:
            members = self

        for tarinfo in members:
            if tarinfo.isdir():
                # Extract directories with a safe mode.
                directories.append(tarinfo)
                tarinfo = copy.copy(tarinfo)
                tarinfo.mode = 0o700
            self.extract(tarinfo, path, full)

        # Reverse sort directories.
        directories.sort(key=operator.attrgetter("name"))
        directories.reverse()

        # Set correct owner, mtime and filemode on directories.
        for tarinfo in directories:
            name = tarinfo.name
            if not full:
                name = os.path.basename(name)
            dirpath = os.path.join(path, name)
            try:
                self.chown(tarinfo, dirpath, numeric_owner=False)
                self.utime(tarinfo, dirpath)
                self.chmod(tarinfo, dirpath)
            except tarfile.ExtractError as e:
                if self.errorlevel > 1:
                    raise e
                self._dbg(1, f"tarfile: {e}")
