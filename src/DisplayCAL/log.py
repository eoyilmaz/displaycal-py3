# -*- coding: utf-8 -*-


from codecs import EncodedFile
from hashlib import md5
import atexit
import logging
import logging.handlers
import os
import re
import sys
import warnings
from io import BytesIO
from time import localtime, strftime, time

from DisplayCAL.meta import name as appname, script2pywname
from DisplayCAL.multiprocess import mp
from DisplayCAL.options import debug
from DisplayCAL.safe_print import SafePrinter, safe_print as _safe_print
from DisplayCAL.util_os import safe_glob

logging.raiseExceptions = 0
logging._warnings_showwarning = warnings.showwarning


if debug:
    loglevel = logging.DEBUG
else:
    loglevel = logging.INFO


logger = None
_logdir = None


def showwarning(message, category, filename, lineno, file=None, line=""):
    # Adapted from _showwarning in Python2.7/lib/logging/__init__.py
    """
    Implementation of showwarnings which redirects to logging, which will first
    check to see if the file parameter is None. If a file is specified, it will
    delegate to the original warnings implementation of showwarning. Otherwise,
    it will call warnings.formatwarning and will log the resulting string to a
    warnings logger named "py.warnings" with level logging.WARNING.

    UNlike the default implementation, the line is omitted from the warning,
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
        log(s.strip(), fn=logger.warning)


warnings.showwarning = showwarning

logbuffer = EncodedFile(BytesIO(), "UTF-8", errors="replace")


def wx_log(logwindow, msg):
    if logwindow.IsShownOnScreen():
        # Check if log buffer has been emptied or not.
        # If it has, our log message is already included.
        if logbuffer.tell():
            logwindow.Log(msg)


class DummyLogger:
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
    def __call__(self, msg, fn=None):
        """Log a message.

        Optionally use function 'fn' instead of logging.info.

        """
        global logger
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", "replace")

        msg = msg.replace("\r\n", "\n").replace("\r", "")
        if fn is None and logger and logger.handlers:
            fn = logger.info
        if fn:
            for line in msg.split("\n"):
                fn(line)
        # If wxPython itself calls warnings.warn on import, it is not yet fully
        # imported at the point our showwarning() function calls log().
        # Check for presence of our wxfixes module and if it has an attribute
        # "wx", in which case wxPython has finished importing.
        wxfixes = sys.modules.get("%s.wxfixes" % appname)
        # wxfixes = sys.modules.get("wxfixes")
        if (
            wxfixes
            and hasattr(wxfixes, "wx")
            and mp.current_process().name == "MainProcess"
        ):
            wx = wxfixes.wx
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


log = Log()


class LogFile:
    """Logfile class. Default is to not rotate."""

    def __init__(self, filename, logdir, when="never", backupCount=0):
        self.filename = filename
        self._logger = get_file_logger(
            md5(filename.encode()).hexdigest(),
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
            kwargs.update(fn=log, encoding=None)
            _safe_print(*args, **kwargs)


safe_log = SafeLogger(print_=False)
safe_print = SafeLogger()


safe_log = SafeLogger(print_=False)
safe_print = SafeLogger()


def get_file_logger(
    name,
    level=loglevel,
    when="midnight",
    backupCount=5,
    logdir=None,
    filename=None,
    confighome=None,
):
    """Return logger object.

    A TimedRotatingFileHandler or FileHandler (if when == "never") will be used.

    """
    global _logdir
    global logger
    if logdir is None:
        logdir = _logdir
    logger = logging.getLogger(name)
    if not filename:
        filename = name
    mode = "a"
    if confighome:
        # Use different logfile name (append number) for each additional instance
        is_main_process = mp.current_process().name == "MainProcess"
        if os.path.basename(confighome).lower() == "dispcalgui":
            lockbasename = filename.replace(appname, "dispcalGUI")
        else:
            lockbasename = filename
        lockfilepath = os.path.join(confighome, lockbasename + ".lock")
        if os.path.isfile(lockfilepath):
            try:
                with open(lockfilepath, "r") as lockfile:
                    instances = len(lockfile.read().splitlines())
            except Exception:
                pass
            else:
                if not is_main_process:
                    # Running as child from multiprocessing under Windows
                    instances -= 1
                if instances:
                    filenames = [filename]
                    filename += ".%i" % instances
                    filenames.append(filename)
                    if filenames[0].endswith("-apply-profiles"):
                        # Running the profile loader always sends a close
                        # request to an already running instance, so there
                        # will be at most two logfiles, and we want to use
                        # the one not currently in use.
                        mtimes = {}
                        for filename in filenames:
                            logfile = os.path.join(logdir, filename + ".log")
                            if not os.path.isfile(logfile):
                                mtimes[0] = filename
                                continue
                            try:
                                logstat = os.stat(logfile)
                            except Exception as exception:
                                print(
                                    "Warning - os.stat('%s') failed: %s"
                                    % (logfile, exception)
                                )
                            else:
                                mtimes[logstat.st_mtime] = filename
                        if mtimes:
                            filename = mtimes[sorted(mtimes.keys())[0]]
        if is_main_process:
            for lockfilepath in safe_glob(
                os.path.join(confighome, lockbasename + ".mp-worker-*.lock")
            ):
                try:
                    os.remove(lockfilepath)
                except Exception:
                    pass
        else:
            # Running as child from multiprocessing under Windows
            lockbasename += ".mp-worker-"
            process_num = 1
            while os.path.isfile(
                os.path.join(confighome, lockbasename + "%i.lock" % process_num)
            ):
                process_num += 1
            lockfilepath = os.path.join(
                confighome, lockbasename + "%i.lock" % process_num
            )
            try:
                with open(lockfilepath, "w") as lockfile:
                    pass
            except Exception:
                pass
            else:
                atexit.register(os.remove, lockfilepath)
            when = "never"
            filename += ".mp-worker-%i" % process_num
            mode = "w"
    logfile = os.path.join(logdir, filename + ".log")
    for handler in logger.handlers:
        if isinstance(
            handler, logging.FileHandler
        ) and handler.baseFilename == os.path.abspath(logfile):
            return logger
    logger.propagate = 0
    logger.setLevel(level)
    if not os.path.exists(logdir):
        try:
            os.makedirs(logdir)
        except Exception as exception:
            print(
                "Warning - log directory '%s' could not be created: %s"
                % (logdir, exception)
            )
    elif when != "never" and os.path.exists(logfile):
        try:
            logstat = os.stat(logfile)
        except Exception as exception:
            print("Warning - os.stat('%s') failed: %s" % (logfile, exception))
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
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                mtime = localtime(t + addend)
            if now[:3] > mtime[:3]:
                # do rollover
                logbackup = logfile + strftime(".%Y-%m-%d", mtime)
                if os.path.exists(logbackup):
                    try:
                        os.remove(logbackup)
                    except Exception as exception:
                        print(
                            "Warning - logfile backup '%s' could not be removed during rollover: %s"
                            % (logbackup, exception)
                        )
                try:
                    os.rename(logfile, logbackup)
                except Exception as exception:
                    print(
                        "Warning - logfile '%s' could not be renamed to '%s' during rollover: %s"
                        % (logfile, os.path.basename(logbackup), exception)
                    )
                # Adapted from Python 2.6's
                # logging.handlers.TimedRotatingFileHandler.getFilesToDelete
                extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")
                baseName = os.path.basename(logfile)
                try:
                    fileNames = os.listdir(logdir)
                except Exception as exception:
                    print(
                        "Warning - log directory '%s' listing failed during rollover: %s"
                        % (logdir, exception)
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
                                    "Warning - logfile backup '%s' could not be removed during rollover: %s"
                                    % (logbackup, exception)
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
            logger.addHandler(filehandler)
        except Exception as exception:
            print(
                "Warning - logging to file '%s' not possible: %s" % (logfile, exception)
            )
    return logger


def setup_logging(logdir, name=appname, ext=".py", backupCount=5, confighome=None):
    """Setup the logging facility."""
    global _logdir, logger
    _logdir = logdir
    name = script2pywname(name)
    if (
        name.startswith(appname)
        or name.startswith("dispcalGUI")
        or ext in (".app", ".exe", ".pyw")
    ):
        logger = get_file_logger(
            None,
            loglevel,
            "midnight",
            backupCount,
            filename=name,
            confighome=confighome,
        )
        if name == appname or name == "dispcalGUI":
            streamhandler = logging.StreamHandler(logbuffer)
            streamformatter = logging.Formatter("%(asctime)s %(message)s")
            streamhandler.setFormatter(streamformatter)
            logger.addHandler(streamhandler)
