"""Logging utilities for file-based, rotating, and safe Unicode logging."""

from __future__ import annotations

import atexit
import contextlib
import logging
import logging.handlers
import os
import re
import sys
import threading
import warnings
from codecs import EncodedFile
from hashlib import md5
from io import BytesIO
from time import localtime, strftime, time
from typing import TYPE_CHECKING, Callable, TextIO

from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.meta import script2pywname
from DisplayCAL.multiprocess import mp
from DisplayCAL.options import DEBUG
from DisplayCAL.safe_print import SafePrinter
from DisplayCAL.safe_print import safe_print as _safe_print
from DisplayCAL.util_os import safe_glob

if TYPE_CHECKING:
    import wx  # noqa: TC004

logging.raiseExceptions = 0
logging._warnings_showwarning = warnings.showwarning


LOGLEVEL = logging.DEBUG if DEBUG else logging.INFO


LOGGER = None
_LOGDIR = None


def showwarning(
    message: Warning,
    category: Warning,
    filename: str,
    lineno: int,
    file: None | TextIO = None,
    line: str = "",
) -> None:
    # Adapted from _showwarning in Python2.7/lib/logging/__init__.py
    """Implementation of `showwarnings` which redirects to logging.

    It will first check to see if the file parameter is None. If a file is
    specified, it will delegate to the original warnings implementation of
    showwarning. Otherwise, it will call warnings.formatwarning and will log
    the resulting string to a warnings logger named "py.warnings" with level
    logging.WARNING.

    Unlike the default implementation, the line is omitted from the warning,
    and the warning does not end with a newline.

    Args:
        message (Warning): The warning message.
        category (Warning): The warning category.
        filename (str): The filename where the warning occurred.
        lineno (int): The line number where the warning occurred.
        file (None | TextIO, optional): The file to write the warning to.
        line (str, optional): The line of code that caused the warning.
    """
    if file is not None:
        if logging._warnings_showwarning is not None:
            logging._warnings_showwarning(
                message, category, filename, lineno, file, line
            )
    else:
        s = warnings.formatwarning(message, category, filename, lineno, line)
        logger = logging.getLogger("py.warnings")
        if not logger.handlers:
            if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
                handler = logging.StreamHandler()  # Logs to stderr by default
            else:
                handler = logging.NullHandler()
            logger.addHandler(handler)
        LOG(s.strip(), fn=logger.warning)


warnings.showwarning = showwarning

LOGBUFFER = EncodedFile(BytesIO(), "UTF-8", errors="replace")


def wx_log(logwindow: wx.Window, msg: str) -> None:
    """Log a message to the wxPython log window.

    Args:
        logwindow (wx.Window): The wxPython log window to log to.
        msg (str): The message to log.
    """
    if logwindow.IsShownOnScreen() and LOGBUFFER.tell():
        # Check if log buffer has been emptied or not.
        # If it has, our log message is already included.
        logwindow.Log(msg)


class DummyLogger:
    """Dummy logger class.

    This is used when logging is disabled or not available.
    """

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log a critical message.

        Args:
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log a debug message.

        Args:
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log an error message.

        Args:
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log an exception message.

        Args:
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log an info message.

        Args:
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        """Log a message with the specified level.

        Args:
            level (int): The logging level (e.g., logging.INFO).
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log a warning message.

        Args:
            msg (str): The message to log.
            *args: Additional arguments to format the message.
            **kwargs: Additional keyword arguments for logging.
        """


class Log:
    """Log class.

    This is a wrapper around the logging module.
    """

    def __call__(self, msg: str, fn: None | Callable = None) -> None:
        """Log a message.

        Optionally use function 'fn' instead of logging.info.

        Args:
            msg (str): The message to log.
            fn (None | Callable, optional): Function to use for logging. If None,
                it will use logging.info if available, otherwise it will
                default to a dummy logger.
        """
        global LOGGER
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", "replace")

        msg = msg.replace("\r\n", "\n").replace("\r", "")
        if fn is None and LOGGER and LOGGER.handlers:
            fn = LOGGER.info
        if fn:
            for line in msg.split("\n"):
                fn(line)
        # If wxPython itself calls warnings.warn on import, it is not yet fully
        # imported at the point our showwarning() function calls log().
        # Check for presence of our wx_fixes module and if it has an attribute
        # "wx", in which case wxPython has finished importing.
        wx_fixes = sys.modules.get(f"{APPNAME}.wx_fixes")
        # wx_fixes = sys.modules.get("wx_fixes")
        if (
            wx_fixes
            and hasattr(wx_fixes, "wx")
            and mp.current_process().name == "MainProcess"
        ):
            wx = wx_fixes.wx
            if (
                wx.GetApp() is not None
                and hasattr(wx.GetApp(), "frame")
                and hasattr(wx.GetApp().frame, "infoframe")
            ):
                wx.CallAfter(wx_log, wx.GetApp().frame.infoframe, msg)

    def flush(self) -> None:
        """Flush the log."""

    def write(self, msg: str) -> None:
        """Write a message to the log.

        Args:
            msg (str): The message to write to the log.
        """
        self(msg.rstrip())


LOG = Log()


class LogFile:
    """Logfile class. Default is to not rotate.

    Args:
        filename (str): The name of the log file.
        logdir (str): The directory where the log file will be stored.
        when (str, optional): When to rotate the log file. Defaults to "never".
        backup_count (int, optional): Number of backup files to keep. Defaults
            to 0
    """

    def __init__(
        self,
        filename: str,
        logdir: str,
        when: str = "never",
        backup_count: int = 0,
    ) -> None:
        self.filename = filename
        self._logger = get_file_logger(
            md5(filename.encode()).hexdigest(),  # noqa: S324
            when=when,
            backup_count=backup_count,
            logdir=logdir,
            filename=filename,
        )

    def close(self) -> None:
        """Close the log file."""
        for handler in reversed(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)

    def flush(self) -> None:
        """Flush the log file."""
        for handler in self._logger.handlers:
            handler.flush()

    def write(self, msg: str) -> None:
        """Write a message to the log file.

        Args:
            msg (str): The message to write to the log file.
        """
        for line in msg.rstrip().replace("\r\n", "\n").replace("\r", "").split("\n"):
            self._logger.info(line)


class SafeLogger(SafePrinter):
    """Safely print and log, avoiding Unicode errors.

    Args:
        log (bool, optional): Whether to log the messages. Defaults to True.
        print_ (None | bool, optional): Whether to print the messages. If None,
            it will check if sys.stdout is a TTY.
    """

    def __init__(self, log: bool = True, print_: None | bool = None) -> None:
        SafePrinter.__init__(self)
        self.log = log
        if print_ is None:
            print_ = (
                sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
            )
        self.print_ = print_

    def write(self, *args, **kwargs) -> None:
        """Write the given arguments to the stream, formatted and encoded."""
        if kwargs.get("print_", self.print_):
            _safe_print(*args, **kwargs)
        if kwargs.get("log", self.log):
            kwargs.update(fn=LOG, encoding=None)
            _safe_print(*args, **kwargs)


safe_log = SafeLogger(print_=False)
safe_print = SafeLogger()


class StdoutLogger:
    """Pass-through ``sys.stdout`` replacement that also logs what is printed.

    The codebase uses plain ``print()`` where the Python 2 version used
    ``safe_print``, which always logged. ``print()`` only reaches
    ``sys.stdout``, which a frozen windowed executable discards (and which may
    be None), so none of it ended up in the log file (issue #986). Every
    complete line is logged, and everything is still written to the wrapped
    stream if there is one.

    Truthiness and attributes other than ``write``/``flush`` are those of the
    wrapped stream, so existing ``sys.stdout and sys.stdout.isatty()`` checks
    behave as before.

    Args:
        stream (None | TextIO): The stream to wrap, usually ``sys.stdout``.
    """

    def __init__(self, stream: None | TextIO) -> None:
        self.stream = stream
        # Per-thread line buffer, so lines printed concurrently from
        # different threads don't get mixed up
        self._local = threading.local()

    def __bool__(self) -> bool:
        """Return the truthiness of the wrapped stream."""
        return bool(self.stream)

    def __getattr__(self, name: str):  # noqa: ANN204
        """Delegate everything else to the wrapped stream."""
        if name == "stream":
            # Not yet set, e.g. during unpickling
            raise AttributeError(name)
        return getattr(self.stream, name)

    def write(self, text: str) -> int:
        """Log complete lines and write text to the wrapped stream.

        Args:
            text (str): The text to write.

        Returns:
            int: The number of characters written.
        """
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        local = self._local
        # Don't recurse if logging itself ends up printing something
        if not getattr(local, "logging", False):
            *lines, local.buffer = (getattr(local, "buffer", "") + text).split("\n")
            if lines:
                local.logging = True
                try:
                    for line in lines:
                        LOG(line)
                finally:
                    local.logging = False
        if self.stream is not None:
            self.stream.write(text)
        return len(text)

    def flush(self) -> None:
        """Flush the wrapped stream."""
        if self.stream is not None and hasattr(self.stream, "flush"):
            self.stream.flush()


def install_stdout_logger() -> None:
    """Replace ``sys.stdout`` with a StdoutLogger wrapping it (once)."""
    if not isinstance(sys.stdout, StdoutLogger):
        sys.stdout = StdoutLogger(sys.stdout)


def get_file_logger(
    name: str,
    level: int = LOGLEVEL,
    when: str = "midnight",
    backup_count: int = 5,
    logdir: None | str = None,
    filename: None | str = None,
    confighome: None | str = None,
) -> logging.Logger:
    """Return logger object.

    A TimedRotatingFileHandler or FileHandler (if when == "never") will be used.

    Args:
        name (str): Name of the logger.
        level (int, optional): Logging level. Defaults to LOGLEVEL.
        when (str, optional): When to rotate the log file. Defaults to
            "midnight".
        backup_count (int, optional): Number of backup files to keep. Defaults
            to 5
        logdir (str, optional): Directory where log files will be stored.
        filename (None | str, optional): Name of the log file. If None, it will
            use the name parameter.
        confighome (None | str, optional): Configuration home directory, used
            for unique log file names. If None, it will not use a unique name.

    Returns:
        logging.Logger: The logger object.
    """
    global _LOGDIR
    global LOGGER
    if logdir is None:
        logdir = _LOGDIR
    LOGGER = logging.getLogger(name)
    if not filename:
        filename = name
    mode = "a"
    if confighome:
        when, filename, mode = update_filename_for_confighome(
            when,
            logdir,
            filename,
            confighome,
            mode,
        )
    logfile = os.path.join(logdir, filename + ".log")
    for handler in LOGGER.handlers:
        if isinstance(
            handler, logging.FileHandler
        ) and handler.baseFilename == os.path.abspath(logfile):
            return LOGGER
    LOGGER.propagate = 0
    LOGGER.setLevel(level)
    if not os.path.exists(logdir):
        try:
            os.makedirs(logdir)
        except Exception as exception:
            print(
                f"Warning - log directory '{logdir}' could not be created: {exception}"
            )
    elif when != "never" and os.path.exists(logfile):
        rotate_log_files(backup_count, logdir, logfile)
    if os.path.exists(logdir):
        try:
            if when != "never":
                filehandler = logging.handlers.TimedRotatingFileHandler(
                    logfile, when=when, backupCount=backup_count
                )
            else:
                filehandler = logging.FileHandler(logfile, mode)
            fileformatter = logging.Formatter("%(asctime)s %(message)s")
            filehandler.setFormatter(fileformatter)
            LOGGER.addHandler(filehandler)
        except Exception as exception:
            print(f"Warning - logging to file '{logfile}' not possible: {exception}")
    return LOGGER


def update_filename_for_confighome(
    when: str,
    logdir: str,
    filename: str,
    confighome: str,
    mode: str,
) -> None:
    """Update the filename for the log file based on the configuration home.

    Args:
        when (str): When to rotate the log file.
        logdir (str): Directory where log files will be stored.
        filename (str): Name of the log file.
        confighome (str): Configuration home directory, used for unique log
            file names.
        mode (str): Mode for opening the log file.

    Returns:
        tuple[str, str, str]: A tuple containing the updated 'when',
            'filename', and 'mode'.
    """
    # Use different logfile name (append number) for each additional instance
    is_main_process = mp.current_process().name == "MainProcess"
    if os.path.basename(confighome).lower() == "dispcalgui":
        lockbasename = filename.replace(APPNAME, "dispcalGUI")
    else:
        lockbasename = filename
    lockfilepath = os.path.join(confighome, f"{lockbasename}.lock")
    if os.path.isfile(lockfilepath):
        filename = update_filename_with_lockfile(logdir, filename, lockfilepath)
    if is_main_process:
        for lockfilepath in safe_glob(
            os.path.join(confighome, f"{lockbasename}.mp-worker-*.lock")
        ):
            with contextlib.suppress(Exception):
                os.remove(lockfilepath)
    else:
        # Running as child from multiprocessing under Windows
        lockbasename = f"{lockbasename}.mp-worker-"
        process_num = 1
        while os.path.isfile(
            os.path.join(confighome, f"{lockbasename}{process_num}.lock")
        ):
            process_num += 1
        lockfilepath = os.path.join(confighome, f"{lockbasename}{process_num}.lock")
        try:
            with open(lockfilepath, "w"):
                pass
        except Exception:
            pass
        else:
            atexit.register(os.remove, lockfilepath)
        when = "never"
        filename = f"{filename}.mp-worker-{process_num}"
        mode = "w"

    return when, filename, mode


def update_filename_with_lockfile(
    logdir: str,
    filename: str,
    lockfilepath: str,
) -> str:
    """Update the filename based on the lock file.

    Args:
        logdir (str): Directory where log files will be stored.
        filename (str): Name of the log file.
        lockfilepath (str): Path to the lock file.
    """
    is_main_process = mp.current_process().name == "MainProcess"
    try:
        with open(lockfilepath) as lockfile:
            instances = len(lockfile.read().splitlines())
    except Exception:
        return filename

    if not is_main_process:
        # Running as child from multiprocessing under Windows
        instances -= 1
    if not instances:
        return filename

    filenames = [filename]
    filename = f"{filename}.{instances}"
    filenames.append(filename)
    if not filenames[0].endswith("-apply-profiles"):
        return filename
    # Running the profile loader always sends a close
    # request to an already running instance, so there
    # will be at most two logfiles, and we want to use
    # the one not currently in use.
    mtimes = {}
    for filename in filenames:
        logfile = os.path.join(logdir, f"{filename}.log")
        if not os.path.isfile(logfile):
            mtimes[0] = filename
            continue
        try:
            logstat = os.stat(logfile)
        except Exception as exception:
            print(f"Warning - os.stat('{logfile}') failed: {exception}")
        else:
            mtimes[logstat.st_mtime] = filename
    if mtimes:
        filename = mtimes[sorted(mtimes.keys())[0]]
    return filename


def rotate_log_files(backup_count: int, logdir: str, logfile: str) -> None:
    """Rotate log files if needed.

    Args:
        backup_count (int): Number of backup files to keep.
        logdir (str): Directory where log files are stored.
        logfile (str): Path to the current log file.
    """
    try:
        logstat = os.stat(logfile)
    except Exception as exception:
        print(f"Warning - os.stat('{logfile}') failed: {exception}")
        return

    # rollover needed?
    now = localtime()
    mtime = get_log_mtime(logstat, now)
    if now[:3] <= mtime[:3]:
        return

    # do rollover
    logbackup = logfile + strftime(".%Y-%m-%d", mtime)
    validate_and_rename_logfile(logfile, logbackup)
    ext_match = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    base_name = os.path.basename(logfile)
    try:
        file_names = os.listdir(logdir)
    except Exception as exception:
        print(
            f"Warning - log directory '{logdir}' "
            f"listing failed during rollover: {exception}"
        )
        return

    result = []
    prefix = base_name + "."
    plen = len(prefix)
    for file_name in file_names:
        if file_name[:plen] != prefix:
            continue
        suffix = file_name[plen:]
        if ext_match.match(suffix):
            result.append(os.path.join(logdir, file_name))
    result.sort()
    if len(result) <= backup_count:
        return
    for logbackup in result[: len(result) - backup_count]:
        try:
            os.remove(logbackup)
        except Exception as exception:
            print(
                f"Warning - logfile backup '{logbackup}' "
                f"could not be removed during rollover: {exception}"
            )


def get_log_mtime(
    logstat: os.stat_result,
    now: tuple[int, int, int, int, int, int],
) -> tuple[int, int, int, int, int, int]:
    """Get the modification time of the log file.

    Args:
        logstat (os.stat_result): The stat result of the log file.
        now (tuple[int, int, int, int, int, int]): The current time as a tuple
            of (year, month, day, hour, minute, second).

    Returns:
        tuple[int, int, int, int, int, int]: The modification time as a
            tuple of (year, month, day, hour, minute, second).
    """
    t = logstat.st_mtime
    try:
        mtime = localtime(t)
    except ValueError:
        # This can happen on Windows because localtime() is buggy on
        # that platform. See:
        # http://stackoverflow.com/questions/4434629/zipfile-module-in-python-runtime-problems
        # http://bugs.python.org/issue1760357
        # To overcome this problem, we ignore the real modification
        # date and force a rollover
        t = time() - 60 * 60 * 24
        mtime = localtime(t)
        # Deal with DST

    dst_now = now[-1]
    dst_then = mtime[-1]
    if dst_now != dst_then:
        addend = 3600 if dst_now else -3600
        mtime = localtime(t + addend)

    return mtime


def validate_and_rename_logfile(logfile: str, logbackup: str) -> None:
    """Validate and rename the log file to a backup.

    Args:
        logfile (str): Path to the current log file.
        logbackup (str): Path to the backup log file.
    """
    if os.path.exists(logbackup):
        try:
            os.remove(logbackup)
        except Exception as exception:
            print(
                f"Warning - logfile backup '{logbackup}' "
                f"could not be removed during rollover: {exception}"
            )

    try:
        os.rename(logfile, logbackup)
    except Exception as exception:
        print(
            f"Warning - logfile '{logfile}' could not be renamed to "
            f"'{os.path.basename(logbackup)}' during rollover: {exception}"
        )
        # Adapted from Python 2.6's
        # logging.handlers.TimedRotatingFileHandler.getFilesToDelete


def setup_logging(
    logdir: str,
    name: str = APPNAME,
    ext: str = ".py",
    backup_count: int = 5,
    confighome: None | str = None,
) -> None:
    """Setup the logging facility.

    Args:
        logdir (str): Directory where log files will be stored.
        name (str, optional): Name of the application or script.
        ext (str, optional): File extension for the log file.
        backup_count (int, optional): Number of backup log files to keep.
        confighome (None | str, optional): Configuration home directory, used
            for unique log file names.
    """
    global _LOGDIR, LOGGER
    _LOGDIR = logdir
    name = script2pywname(name)
    if name.startswith((APPNAME, "dispcalGUI")) or ext in (".app", ".exe", ".pyw"):
        LOGGER = get_file_logger(
            None,
            LOGLEVEL,
            "midnight",
            backup_count,
            filename=name,
            confighome=confighome,
        )
        if name in (APPNAME, "dispcalGUI"):
            streamhandler = logging.StreamHandler(LOGBUFFER)
            streamformatter = logging.Formatter("%(asctime)s %(message)s")
            streamhandler.setFormatter(streamformatter)
            LOGGER.addHandler(streamhandler)
        # Make print() output end up in the log file like it used to with
        # Python 2 era safe_print
        install_stdout_logger()
