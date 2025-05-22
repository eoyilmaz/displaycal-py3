"""This module provides logging functionality for the application, including
custom loggers, file-based logging with rotation, and safe logging mechanisms
to handle Unicode and multiprocessing scenarios.
"""

import atexit
import contextlib
import logging
import logging.handlers
import os
import re
import sys
import warnings
from codecs import EncodedFile
from hashlib import md5
from io import BytesIO
from time import localtime, strftime, time

from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.meta import script2pywname
from DisplayCAL.multiprocess import mp
from DisplayCAL.options import DEBUG
from DisplayCAL.safe_print import SafePrinter
from DisplayCAL.safe_print import safe_print as _safe_print
from DisplayCAL.util_os import safe_glob

logging.raiseExceptions = 0
logging._warnings_showwarning = warnings.showwarning


LOGLEVEL = logging.DEBUG if DEBUG else logging.INFO


LOGGER = None
_LOGDIR = None


def showwarning(message, category, filename, lineno, file=None, line=""):
    # Adapted from _showwarning in Python2.7/lib/logging/__init__.py
    """Implementation of `showwarnings` which redirects to logging.

    It will first check to see if the file parameter is None. If a file is
    specified, it will delegate to the original warnings implementation of
    showwarning. Otherwise, it will call warnings.formatwarning and will log
    the resulting string to a warnings logger named "py.warnings" with level
    logging.WARNING.

    Unlike the default implementation, the line is omitted from the warning,
    and the warning does not end with a newline.
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


def wx_log(logwindow, msg):
    if logwindow.IsShownOnScreen() and LOGBUFFER.tell():
        # Check if log buffer has been emptied or not.
        # If it has, our log message is already included.
        logwindow.Log(msg)


class DummyLogger:
    """Dummy logger class.

    This is used when logging is disabled or not available.
    """

    def critical(self, msg, *args, **kwargs):
        pass

    def debug(self, msg, *args, **kwargs):
        pass

    def error(self, msg, *args, **kwargs):
        pass

    def exception(self, msg, *args, **kwargs):
        pass

    def info(self, msg, *args, **kwargs):
        pass

    def log(self, level, msg, *args, **kwargs):
        pass

    def warning(self, msg, *args, **kwargs):
        pass


class Log:
    """Log class.

    This is a wrapper around the logging module.
    """

    def __call__(self, msg, fn=None):
        """Log a message.

        Optionally use function 'fn' instead of logging.info.
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

    def flush(self):
        pass

    def write(self, msg):
        self(msg.rstrip())


LOG = Log()


class LogFile:
    """Logfile class. Default is to not rotate."""

    def __init__(self, filename, logdir, when="never", backupCount=0):
        self.filename = filename
        self._logger = get_file_logger(
            md5(filename.encode()).hexdigest(),  # noqa: S324
            when=when,
            backupCount=backupCount,
            logdir=logdir,
            filename=filename,
        )

    def close(self):
        for handler in reversed(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)

    def flush(self):
        for handler in self._logger.handlers:
            handler.flush()

    def write(self, msg):
        for line in msg.rstrip().replace("\r\n", "\n").replace("\r", "").split("\n"):
            self._logger.info(line)


class SafeLogger(SafePrinter):
    """Print and log safely, avoiding any UnicodeDe-/EncodingErrors on strings
    and converting all other objects to safe string representations.
    """

    def __init__(self, log=True, print_=None):
        SafePrinter.__init__(self)
        self.log = log
        if print_ is None:
            print_ = (
                sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
            )
        self.print_ = print_

    def write(self, *args, **kwargs):
        if kwargs.get("print_", self.print_):
            _safe_print(*args, **kwargs)
        if kwargs.get("log", self.log):
            kwargs.update(fn=LOG, encoding=None)
            _safe_print(*args, **kwargs)


safe_log = SafeLogger(print_=False)
safe_print = SafeLogger()


def get_file_logger(
    name,
    level=LOGLEVEL,
    when="midnight",
    backupCount=5,
    logdir=None,
    filename=None,
    confighome=None,
):
    """Return logger object.

    A TimedRotatingFileHandler or FileHandler (if when == "never") will be used.

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
        # Use different logfile name (append number) for each additional instance
        is_main_process = mp.current_process().name == "MainProcess"
        if os.path.basename(confighome).lower() == "dispcalgui":
            lockbasename = filename.replace(APPNAME, "dispcalGUI")
        else:
            lockbasename = filename
        lockfilepath = os.path.join(confighome, lockbasename + ".lock")
        if os.path.isfile(lockfilepath):
            try:
                with open(lockfilepath) as lockfile:
                    instances = len(lockfile.read().splitlines())
            except Exception:
                pass
            else:
                if not is_main_process:
                    # Running as child from multiprocessing under Windows
                    instances -= 1
                if instances:
                    filenames = [filename]
                    filename = f"{filename}.{instances}"
                    filenames.append(filename)
                    if filenames[0].endswith("-apply-profiles"):
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
                                print(
                                    f"Warning - os.stat('{logfile}') failed: "
                                    f"{exception}"
                                )
                            else:
                                mtimes[logstat.st_mtime] = filename
                        if mtimes:
                            filename = mtimes[sorted(mtimes.keys())[0]]
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
                with open(lockfilepath, "w") as lockfile:
                    pass
            except Exception:
                pass
            else:
                atexit.register(os.remove, lockfilepath)
            when = "never"
            filename = f"{filename}.mp-worker-{process_num}"
            mode = "w"
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
        try:
            logstat = os.stat(logfile)
        except Exception as exception:
            print(f"Warning - os.stat('{logfile}') failed: {exception}")
        else:
            # rollover needed?
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
            now = localtime()
            dstNow = now[-1]
            dstThen = mtime[-1]
            if dstNow != dstThen:
                addend = 3600 if dstNow else -3600
                mtime = localtime(t + addend)
            if now[:3] > mtime[:3]:
                # do rollover
                logbackup = logfile + strftime(".%Y-%m-%d", mtime)
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
                extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")
                baseName = os.path.basename(logfile)
                try:
                    fileNames = os.listdir(logdir)
                except Exception as exception:
                    print(
                        f"Warning - log directory '{logdir}' "
                        f"listing failed during rollover: {exception}"
                    )
                else:
                    result = []
                    prefix = baseName + "."
                    plen = len(prefix)
                    for fileName in fileNames:
                        if fileName[:plen] == prefix:
                            suffix = fileName[plen:]
                            if extMatch.match(suffix):
                                result.append(os.path.join(logdir, fileName))
                    result.sort()
                    if len(result) > backupCount:
                        for logbackup in result[: len(result) - backupCount]:
                            try:
                                os.remove(logbackup)
                            except Exception as exception:
                                print(
                                    f"Warning - logfile backup '{logbackup}' "
                                    f"could not be removed during rollover: {exception}"
                                )
    if os.path.exists(logdir):
        try:
            if when != "never":
                filehandler = logging.handlers.TimedRotatingFileHandler(
                    logfile, when=when, backupCount=backupCount
                )
            else:
                filehandler = logging.FileHandler(logfile, mode)
            fileformatter = logging.Formatter("%(asctime)s %(message)s")
            filehandler.setFormatter(fileformatter)
            LOGGER.addHandler(filehandler)
        except Exception as exception:
            print(f"Warning - logging to file '{logfile}' not possible: {exception}")
    return LOGGER


def setup_logging(logdir, name=APPNAME, ext=".py", backupCount=5, confighome=None):
    """Setup the logging facility."""
    global _LOGDIR, LOGGER
    _LOGDIR = logdir
    name = script2pywname(name)
    if name.startswith((APPNAME, "dispcalGUI")) or ext in (".app", ".exe", ".pyw"):
        LOGGER = get_file_logger(
            None,
            LOGLEVEL,
            "midnight",
            backupCount,
            filename=name,
            confighome=confighome,
        )
        if name in (APPNAME, "dispcalGUI"):
            streamhandler = logging.StreamHandler(LOGBUFFER)
            streamformatter = logging.Formatter("%(asctime)s %(message)s")
            streamhandler.setFormatter(streamformatter)
            LOGGER.addHandler(streamhandler)
